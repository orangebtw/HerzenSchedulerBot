from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.chat_action import ChatActionSender
from aiogram.enums.chat_action import ChatAction
from aiogram.fsm.state import StatesGroup, State

from aiogram_dialog import DialogManager, StartMode, Dialog, Window
from aiogram_dialog.widgets.kbd.button import Button
from aiogram_dialog.widgets.kbd.state import Cancel
from aiogram_dialog.widgets.kbd.calendar_kbd import Calendar, CalendarConfig, CalendarScope, CalendarScopeView, CalendarDaysView, CalendarMonthView, CalendarYearsView
from aiogram_dialog.widgets.text import Const, Format, Text

from babel.dates import get_day_names, get_month_names

from datetime import datetime, timedelta, date, time

from states import NoteCreationState
from utils import NumCallbackData
from handlers.utils import check_user_exists

import keyboards
import database
import utils
import parse
import models

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
    
    user = users_database.get_user_by_id(message.from_user.id)
    assert(user is not None)

    async with ChatActionSender(bot=bot, chat_id=message.chat.id, action=ChatAction.TYPING):
        # date = message.date.astimezone(utils.DEFAULT_TIMEZONE)
        date = datetime.combine(message.date.date(), time(hour=9, minute=50), tzinfo=utils.DEFAULT_TIMEZONE)
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
                                       data={'subject': last_subject.name,
                                             'note_text': message.text,
                                             'user_id': user.id,
                                             'notes_database': notes_database})
        else:
            builder = InlineKeyboardBuilder()
            builder.row(keyboards.INLINE_YES_BUTTON, keyboards.INLINE_NO_BUTTON)
            builder.row(keyboards.CANCEL_BUTTON)
            
            await message.reply(f"Сейчас идёт пара \"<b>{found_subject.name}</b>\", верно?",
                                reply_markup=builder.as_markup())
            await state.update_data(subject=found_subject)
            await state.update_data(note_text=message.text)
            await state.set_state(NoteCreationState.IsCurrentSubjectCorrect)


async def handle_due_date_selected(
    call: types.CallbackQuery,
    widget,
    manager: DialogManager,
    selected_date: date
):  
    subject: parse.ScheduleSubject = manager.start_data['subject']
    note_text: str = manager.start_data['note_text']
    user_id: int = manager.start_data['user_id']
    notes_database: database.NotesDatabase = manager.start_data['notes_database']
    
    with utils.time_locale('ru_RU.UTF-8'):
        date_text: str = selected_date.strftime("%d %b %Y")
    
    notes_database.insert_note(models.UserNote(user_id, subject, note_text, datetime.combine(selected_date, time(hour=23, minute=59), tzinfo=utils.DEFAULT_TIMEZONE)))
    
    await call.message.edit_text(f"✅ Сохранено задание по предмету <b>{subject}</b>: \"{note_text}\" к <b>{date_text}</b>.")
    
    await manager.done()

async def handle_subject_not_correct(
    call: types.CallbackQuery,
    state: FSMContext,
    schedules_database: database.SchedulesDatabase,
    users_database: database.UsersDatabase
):
    await call.answer()
    
    user = users_database.get_user_by_id(call.from_user.id)
    assert(user is not None)
    
    with schedules_database.get_subjects(user.group.id, user.group.subgroup) as subjects:
        assert(subjects is not None)
        
    subject_names = set((subj.name for subj in subjects))
    
    await state.update_data(subject_names=tuple(subject_names))
    
    subjects_text = ""
    builder = InlineKeyboardBuilder()
    
    for i, subject_name in enumerate(subject_names):
        subjects_text += f"{i+1}. <b>{subject_name}</b>\n"
        builder.add(types.InlineKeyboardButton(text=str(i+1), callback_data=NumCallbackData(num=i).pack()))
        
    builder.row(keyboards.INLINE_CREATE_NOTE_BUTTON)
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text(f"<b>Нажмите на кнопку ниже с цифрой, соответствующей нужному предмету:</b>\n\n{subjects_text}",
                                reply_markup=builder.as_markup())
    
    await state.set_state(NoteCreationState.AskCustomSubject)


async def handle_subject_is_correct(
    call: types.CallbackQuery,
    state: FSMContext,
    dialog_manager: DialogManager,
    notes_database: database.NotesDatabase
):
    await call.answer()
    
    subject: parse.ScheduleSubject = await state.get_value('subject')
    note_text = await state.get_value("note_text")
    
    await state.clear()
    
    await dialog_manager.start(DialogState.AskDueDate,
                               mode=StartMode.RESET_STACK,
                               data={'subject': subject.name,
                                     'note_text': note_text,
                                     'user_id': call.from_user.id,
                                     'notes_database': notes_database})

async def handle_get_custom_subject(call: types.CallbackQuery, callback_data: NumCallbackData, state: FSMContext, dialog_manager: DialogManager, notes_database: database.NotesDatabase):
    await call.answer()
    
    note_text = await state.get_value("note_text")
    subject_name = (await state.get_value('subject_names'))[callback_data.num]
    
    await state.clear()
    
    await dialog_manager.start(DialogState.AskDueDate,
                               mode=StartMode.RESET_STACK,
                               data={'subject': subject_name,
                                     'note_text': note_text,
                                     'user_id': call.from_user.id,
                                     'notes_database': notes_database})


async def handle_create_note(call: types.CallbackQuery, state: FSMContext):
    pass

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
    raise NotImplementedError

async def on_cancel_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    await call.message.edit_text("Отменено.")

def register(router: Router):
    router.message.register(handle_new_reminder, StateFilter(None))
    router.callback_query.register(handle_subject_not_correct, StateFilter(NoteCreationState.IsCurrentSubjectCorrect), F.data == keyboards.INLINE_NO_BUTTON.callback_data)
    router.callback_query.register(handle_subject_is_correct, StateFilter(NoteCreationState.IsCurrentSubjectCorrect), F.data == keyboards.INLINE_YES_BUTTON.callback_data)
    router.callback_query.register(handle_create_note, StateFilter(NoteCreationState.AskCustomSubject), F.data == keyboards.INLINE_CREATE_NOTE_BUTTON.callback_data)
    router.callback_query.register(handle_get_custom_subject, StateFilter(NoteCreationState.AskCustomSubject), NumCallbackData.filter())

    router.include_router(Dialog(
        Window(
            Const("❗ Сейчас не идёт никакой пары"),
            Button(text=Const("🗒️ Создать личную заметку"), id='create_note', on_click=on_create_note_button_click),
            Button(text=Format("Недавняя пара: {recent_subject}"), id="select_recent_subject", on_click=on_recent_subject_button_click),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            getter=no_subject_currently_getter,
            state=DialogState.NoSubjectCurrently,
        ),
        Window(
            Const("📅 Когда дедлайн?"),
            CustomCalendar(id='due_date_calendar', on_click=handle_due_date_selected, config=CalendarConfig(timezone=utils.DEFAULT_TIMEZONE)),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            state=DialogState.AskDueDate,
        ),
    ))