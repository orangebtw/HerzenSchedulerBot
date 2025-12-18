import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.chat_action import ChatActionSender
from aiogram.enums.chat_action import ChatAction
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.state import StatesGroup, State

from babel.dates import get_day_names, get_month_names

from aiogram_dialog import DialogManager, StartMode, Dialog, Window, ShowMode
from aiogram_dialog.widgets.kbd.button import Button
from aiogram_dialog.widgets.kbd.calendar_kbd import Calendar, CalendarConfig, CalendarScope, CalendarScopeView, CalendarDaysView, CalendarMonthView, CalendarYearsView
from aiogram_dialog.widgets.text import Const, Format, Text

from datetime import datetime, timedelta, date, time

import constants
import keyboards
import database
import utils
import parse
import models
from states import MainState, NoteCreationState
from utils import NumCallbackData


class DialogState(StatesGroup):
    NoSubjectCurrently = State()
    AskDueDate = State()
    
class WeekDay(Text):
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        locale = manager.event.from_user.language_code
        return get_day_names(width="abbreviated", context="stand-alone", locale=locale)[selected_date.weekday()].title()
    
class Month(Text):
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        locale = manager.event.from_user.language_code
        return get_month_names("wide", context="stand-alone", locale=locale)[selected_date.month].title()
    
class CustomCalendar(Calendar):
    def _init_views(self) -> dict[CalendarScope, CalendarScopeView]:
        return {
            CalendarScope.DAYS: CalendarDaysView(
                self._item_callback_data,
                weekday_text=WeekDay(),
                header_text="🗓 " + Month() + " " + Format("{date:%Y}"),
                next_month_text=Month() + ' >>',
                prev_month_text='<< ' + Month()
            ),
            CalendarScope.MONTHS: CalendarMonthView(
                self._item_callback_data,
                month_text=Month(),
                this_month_text="[" + Month() + "]",
            ),
            CalendarScope.YEARS: CalendarYearsView(
                self._item_callback_data,
            ),
        }

async def handle_start(message: types.Message):
    await message.reply(f"Привет! Я <b>{constants.BOT_NAME}</b> – помогу организовать учебный процесс. Я буду запоминать твои заметки и дедлайны, привязывая их к расписанию.",
                        reply_markup=keyboards.START_KEYBOARD)


async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    await call.answer()
    await call.message.reply("Настройка отменена.")
    await call.message.delete_reply_markup()


async def check_user_exists(message: types.Message, users_database: database.UsersDatabase) -> bool:
    assert(message.from_user is not None)
    
    if not users_database.user_exists(message.from_user.id):
        await message.answer("Я тебя не знаю. Пожалуйста, напиши /start и пройди регистрацию.")
        return False
    return True

async def handle_new_reminder(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
    dialog_manager: DialogManager,
    schedules_database: database.SchedulesDatabase,
    users_database: database.UsersDatabase,
    notes_database: database.NotesDatabase
):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    with users_database.get_user_by_id(message.from_user.id) as user:
        assert(user is not None)
    
        async with ChatActionSender(bot=bot, chat_id=message.chat.id, action=ChatAction.TYPING):
            date = message.date.astimezone(utils.DEFAULT_TIMEZONE)
            found_subject: parse.ScheduleSubject | None = None
            last_subject: parse.ScheduleSubject = None
            
            with schedules_database.get_subjects(user.group.id, user.group.subgroup) as subjects:
                last_subject = subjects[-1]
                
                for subject in subjects:
                    start = subject.time_start - timedelta(minutes=3)
                    end = subject.time_end + timedelta(minutes=7)
                    
                    if start <= date <= end:
                        found_subject = subject
                        break
                
            if found_subject is None:
                await dialog_manager.start(DialogState.NoSubjectCurrently,
                                        mode=StartMode.RESET_STACK,
                                        data={
                                            'subject': last_subject,
                                            'note_text': message.text,
                                            'user_id': user.id,
                                            'notes_database': notes_database})
            else:
                await message.reply(f"Сейчас идёт пара \"<b>{found_subject.name}</b>\", верно?",
                                    reply_markup=keyboards.YES_OR_NO_KEYBOARD)
                await state.update_data(subject=found_subject)
                await state.set_state(NoteCreationState.IsCurrentSubjectCorrect)


async def handle_due_date_selected(
    call: types.CallbackQuery,
    widget,
    manager: DialogManager,
    selected_date: date,
    **kwargs
):
    subject: parse.ScheduleSubject = manager.start_data['subject']
    note_text: str = manager.start_data['note_text']
    user_id: int = manager.start_data['user_id']
    notes_databse: database.NotesDatabase = manager.start_data['notes_database']
    
    with utils.set_time_locale('ru_RU.UTF-8'):
        date_text: str = selected_date.strftime("%d %b %Y")

    await call.message.edit_text(f"✅ Сохранено задание по предмету <b>{subject.name}</b>: \"{note_text}\" к <b>{date_text}</b>.")
    
    notes_databse.add_note(models.UserNote(user_id, subject.name, note_text, datetime.combine(selected_date, time(hour=23, minute=59), tzinfo=utils.DEFAULT_TIMEZONE)))
    
    await manager.done()

async def handle_subject_not_correct(
    call: types.CallbackQuery,
    state: FSMContext,
    schedules_database: database.SchedulesDatabase,
    users_database: database.UsersDatabase
):
    await call.answer()
    
    subjects_text = ""
    builder = InlineKeyboardBuilder()
    
    with users_database.get_user_by_id(call.from_user.id) as user:
        assert(user is not None)
    
        with schedules_database.get_subjects(user.group.id, user.group.subgroup) as subjects:
            for i, subject in enumerate(subjects, 1):
                subjects_text += f"{i}. <b>{subject.name}</b>"
                builder.add(types.InlineKeyboardButton(text=str(i), callback_data=NumCallbackData(num=i).pack()))
    
    await call.message.edit_text("<b>Нажмите на кнопку ниже с цифрой, соответствующей нужному предмету:</b>\n\n",
                                reply_markup=builder.as_markup())
    
    await state.set_state(NoteCreationState.AskCustomSubject)


async def handle_create_note(call: types.CallbackQuery, state: FSMContext):
    pass


async def handle_settings(message: types.Message, state: FSMContext, users_database: database.UsersDatabase):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    assert(message.from_user is not None)
    
    with users_database.get_user_by_id(message.from_user.id) as user:
        assert(user is not None)
        reminder_times_text = utils.user_reminder_times_to_text(user)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1", callback_data=NumCallbackData(num=1).pack()))
    builder.add(types.InlineKeyboardButton(text="2", callback_data=NumCallbackData(num=2).pack()))
    builder.add(types.InlineKeyboardButton(text="3", callback_data=NumCallbackData(num=3).pack()))
    builder.add(types.InlineKeyboardButton(text="4", callback_data=NumCallbackData(num=4).pack()))
    builder.add(types.InlineKeyboardButton(text="5", callback_data=NumCallbackData(num=5).pack()))
    builder.add(types.InlineKeyboardButton(text="6", callback_data=NumCallbackData(num=6).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    await message.answer("<b>Введите номер пункта, который хотите изменить.</b>\n"
                         f"1. 🎓  Группа: {user.group.name}\n"
                         f"2. 🔔  Напоминания о дедлайнах: {reminder_times_text}\n"
                         f"3. 📊  Сводка: В 18:00\n"
                         f"4. 📝  Расписание на день: За 1 час до первой пары\n"
                         f"5. 🎯  Убеждаться в успешном выполнении задания: вкл\n"
                         f"6. ℹ️  Связаться с админом\n",
                         reply_markup=builder.as_markup())
    
    await state.set_state(MainState.Settings)

async def no_subject_currently_getter(dialog_manager: DialogManager, **kwargs):
    subject: parse.ScheduleSubject = dialog_manager.start_data['subject']
    return {
        'recent_subject': subject.name
    }
    
async def on_recent_subject_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    if manager.is_preview():
        await manager.next()
        return
    await manager.next()
    

async def on_create_note_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    await manager.done()
    await manager.switch_to()

async def on_cancel_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    await call.message.edit_text("Отменено.")
    await manager.done()

def register(router: Router):
    router.message.register(handle_start, CommandStart())
    router.callback_query.register(handle_cancel, F.data == keyboards.CANCEL_BUTTON.callback_data)
    router.message.register(handle_settings, StateFilter(None), F.text == keyboards.SETTINGS_BUTTON.text)
    router.message.register(handle_new_reminder, StateFilter(None))

    router.include_router(Dialog(
        Window(
            Const("❗ Сейчас не идёт никакой пары"),
            Button(text=Const("🗒️ Создать личную заметку"), id='create_note', on_click=on_create_note_button_click),
            Button(text=Format("Недавняя пара: {recent_subject}"), id="select_recent_subject", on_click=on_recent_subject_button_click),
            Button(text=Const("Отмена"), id="cancel_button", on_click=on_cancel_button_click),
            getter=no_subject_currently_getter,
            state=DialogState.NoSubjectCurrently,
        ),
        Window(
            Const("📅 Когда дедлайн?"),
            CustomCalendar(id='due_date_calendar', on_click=handle_due_date_selected, config=CalendarConfig(timezone=utils.DEFAULT_TIMEZONE)),
            Button(text=Const("Отмена"), id="cancel_button", on_click=on_cancel_button_click),
            state=DialogState.AskDueDate,
            on_process_result=handle_due_date_selected
        ),
    ))