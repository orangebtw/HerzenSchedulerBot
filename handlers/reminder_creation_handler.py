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
from aiogram_dialog.widgets.kbd.select import Select
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.kbd.group import Group

from datetime import datetime, timedelta, date, time

from itertools import islice
from cytoolz.itertoolz import unique

from states import NoteCreationState
from callbacks import NumCallback
from handlers.utils import check_user_exists

import operator

import keyboards
import database
import utils
import parse
import models


class DueDateDialogState(StatesGroup):
    NoSubjectCurrently = State()
    AskDueDate = State()
    AskCustomDueDate = State()

async def handle_new_reminder(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
    dialog_manager: DialogManager,
    schedules_database: database.SchedulesDatabase,
    users_database: database.UsersDatabase,
):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    user = users_database.get_user_by_id(message.from_user.id)
    assert(user is not None)

    async with ChatActionSender(bot=bot, chat_id=message.chat.id, action=ChatAction.TYPING):
        date = message.date.astimezone(utils.DEFAULT_TIMEZONE)
        found_subject: parse.ScheduleSubject | None = None
        last_subject: parse.ScheduleSubject = None
        
        with schedules_database.get_subjects(user.group.without_name(), date_from=date.date()) as subjects:
            last_subject = subjects[-1]
            
            for subject in subjects:
                start = subject.time_start - timedelta(minutes=3)
                end = subject.time_end + timedelta(minutes=7)
                
                if start <= date <= end:
                    found_subject = subject
                    break
            
        if found_subject is None:
            await dialog_manager.start(DueDateDialogState.NoSubjectCurrently,
                                       mode=StartMode.RESET_STACK,
                                       data={'subject': last_subject.name,
                                             'note_text': message.text,
                                             'user': user})
        else:
            builder = InlineKeyboardBuilder()
            builder.row(keyboards.INLINE_YES_BUTTON, keyboards.INLINE_NO_BUTTON)
            builder.row(keyboards.CANCEL_BUTTON)
            
            await message.reply(f"Сейчас идёт пара \"<b>{found_subject.name}</b>\", верно?",
                                reply_markup=builder.as_markup())
            await state.update_data(subject=found_subject)
            await state.update_data(note_text=message.text)
            await state.update_data(user=user)
            await state.set_state(NoteCreationState.IsCurrentSubjectCorrect)


async def handle_subject_not_correct(
    call: types.CallbackQuery,
    state: FSMContext,
    schedules_database: database.SchedulesDatabase,
    users_database: database.UsersDatabase
):
    await call.answer()
    
    user = users_database.get_user_by_id(call.from_user.id)
    assert(user is not None)
    
    with schedules_database.get_subjects(user.group.without_name()) as subjects:
        assert(subjects is not None)
        
    subject_names = set((subj.name for subj in subjects))
    
    await state.update_data(subject_names=tuple(subject_names))
    
    subjects_text = ""
    builder = InlineKeyboardBuilder()
    
    for i, subject_name in enumerate(subject_names):
        subjects_text += f"{i+1}. <b>{subject_name}</b>\n"
        builder.add(types.InlineKeyboardButton(text=str(i+1), callback_data=NumCallback(num=i).pack()))
        
    builder.row(keyboards.INLINE_CREATE_NOTE_BUTTON)
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text(f"<b>Нажмите на кнопку ниже с цифрой, соответствующей нужному предмету:</b>\n\n{subjects_text}",
                                reply_markup=builder.as_markup())
    
    await state.set_state(NoteCreationState.AskCustomSubject)


def get_next_classes(schedules_database: database.SchedulesDatabase, user: models.User, subject: str, count: int) -> list[parse.ScheduleSubject]:
    now = utils.tz_now()
    with schedules_database.get_subjects(user.group.without_name(), date_from=now.date()) as schedules:
        next_classes = islice(unique(filter(lambda subj: subj.name == subject and subj.time_end.date() > now.date(), schedules), key=lambda subj: subj.time_start.date()), count)
    return list(next_classes)


async def handle_subject_is_correct(
    call: types.CallbackQuery,
    state: FSMContext,
    dialog_manager: DialogManager,
    schedules_database: database.SchedulesDatabase
):
    await call.answer()
    
    subject: parse.ScheduleSubject = await state.get_value('subject')
    note_text = await state.get_value("note_text")
    user = await state.get_value("user")
    
    await state.clear()
    
    next_classes = get_next_classes(schedules_database, user, subject.name, 3)
    if len(next_classes) > 0:
        await dialog_manager.start(DueDateDialogState.AskDueDate,
                                mode=StartMode.RESET_STACK,
                                data={'subject': subject.name,
                                      'note_text': note_text,
                                      'user': user,
                                      'next_classes': next_classes})
    else:
        await dialog_manager.start(DueDateDialogState.AskCustomDueDate,
                                mode=StartMode.RESET_STACK,
                                data={'subject': subject.name,
                                      'note_text': note_text,
                                      'user': user,})


async def handle_get_custom_subject(
    call: types.CallbackQuery,
    callback_data: NumCallback,
    state: FSMContext,
    dialog_manager: DialogManager,
    schedules_database: database.SchedulesDatabase
):
    await call.answer()
    
    note_text = await state.get_value("note_text")
    subject_name = (await state.get_value('subject_names'))[callback_data.num]
    user = await state.get_value('user')
    
    await state.clear()
    
    next_classes = get_next_classes(schedules_database, user, subject_name, 3)
    
    await dialog_manager.start(DueDateDialogState.AskDueDate,
                               mode=StartMode.RESET_STACK,
                               data={'subject': subject_name,
                                     'note_text': note_text,
                                     'user': user,
                                     'next_classes': next_classes})


async def handle_create_note(call: types.CallbackQuery, state: FSMContext, dialog_manager: DialogManager):
    await call.answer()
    
    note_text = await state.get_value("note_text")
    user = await state.get_value("user")
    
    await state.clear()
    
    await dialog_manager.start(DueDateDialogState.AskCustomDueDate,
                               mode=StartMode.RESET_STACK,
                               data={'note_text': note_text,
                                     'user': user})


async def handle_due_date_selected(
    call: types.CallbackQuery,
    widget,
    manager: DialogManager,
    selected_date: date
):  
    subject: parse.ScheduleSubject | None = manager.start_data.get('subject', None)
    note_text: str = manager.start_data['note_text']
    user: models.User = manager.start_data['user']
    notes_database: database.NotesDatabase = manager.middleware_data['notes_database']
    
    if selected_date < utils.tz_now().date():
        await call.message.reply("❗ Дата не должна быть раньше сегодняшнего дня.")
        await manager.done()
        return
    
    with utils.time_locale('ru_RU.UTF-8'):
        date_text: str = selected_date.strftime("%d %b %Y")
    
    notes_database.insert_note(models.UserNote(user.id, subject, note_text, datetime.combine(selected_date - timedelta(days=1), time(hour=23, minute=59), tzinfo=utils.DEFAULT_TIMEZONE)))
    
    if subject is not None:
        await call.message.edit_text(f"✅ Сохранено задание по предмету <b>{subject}</b>: \"{note_text}\" к <b>{date_text}</b>.")
    else:
        await call.message.edit_text(f"✅ Сохранена личная заметка: \"{note_text}\" к <b>{date_text}</b>.")
    
    await manager.done()


async def on_class_selected(call: types.CallbackQuery, widget, manager: DialogManager, item_id: int):
    next_class: parse.ScheduleSubject = manager.start_data['next_classes'][item_id]
    
    await handle_due_date_selected(call, widget, manager, selected_date=next_class.time_start.date())

async def no_subject_currently_getter(dialog_manager: DialogManager, **kwargs):
    subject: parse.ScheduleSubject = dialog_manager.start_data['subject']
    return {
        'recent_subject': subject
    }


async def ask_custom_deadline_getter(dialog_manager: DialogManager, **kwargs):
    min_date = utils.tz_now().date()
    return {
        'calendar_min_date': min_date
    }

async def ask_deadline_getter(dialog_manager: DialogManager, **kwargs):
    def map_subject():
        now = utils.tz_now()
        
        def inner(subject: parse.ScheduleSubject) -> str:
            with utils.time_locale('ru_RU.UTF-8'):
                delta = subject.time_start - now
                date_text = subject.time_start.strftime("%a, %d %b")
                if delta.days == 0:
                    text = f"{date_text} (завтра)"
                elif delta.days == 1:
                    text = f"{date_text} (послезавтра)"
                else:
                    text = f"{date_text} (Через {delta.days} д.)"
                
                return (subject.time_start, text)
        return inner
    
    next_classes = map(map_subject(), dialog_manager.start_data['next_classes'])
    
    return {
        "next_classes": enumerate(next_classes)
    }

async def on_recent_subject_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    if manager.is_preview():
        await manager.next()
        return
    
    schedules_database: database.SchedulesDatabase = manager.middleware_data['schedules_database']
    user: models.User = manager.start_data['user']
    subject: str = manager.start_data['subject']
    
    manager.start_data['next_classes'] = get_next_classes(schedules_database, user, subject, 3)
    
    await manager.next()
    

async def on_custom_due_date_button_clicK(call: types.CallbackQuery, button: Button, manager: DialogManager):
    await manager.next()

async def on_create_note_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    manager.start_data['subject'] = None
    await manager.switch_to(DueDateDialogState.AskCustomDueDate)


async def on_custom_subject_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    state: FSMContext = manager.middleware_data['state']
    schedules_database: database.SchedulesDatabase = manager.middleware_data['schedules_database']
    users_database: database.SchedulesDatabase = manager.middleware_data['users_database']
    user: models.User = manager.start_data['user']
    note_text: models.User = manager.start_data['note_text']
    
    await manager.done()
    
    await state.update_data(user=user)
    await state.update_data(note_text=note_text)
    
    await handle_subject_not_correct(call, state, schedules_database, users_database)


async def on_cancel_button_click(call: types.CallbackQuery, button: Button, manager: DialogManager):
    await call.message.edit_text("Отменено")


def register(router: Router):
    router.message.register(handle_new_reminder, StateFilter(None))
    router.callback_query.register(handle_subject_not_correct, StateFilter(NoteCreationState.IsCurrentSubjectCorrect), F.data == keyboards.INLINE_NO_BUTTON.callback_data)
    router.callback_query.register(handle_subject_is_correct, StateFilter(NoteCreationState.IsCurrentSubjectCorrect), F.data == keyboards.INLINE_YES_BUTTON.callback_data)
    router.callback_query.register(handle_create_note, StateFilter(NoteCreationState.AskCustomSubject), F.data == keyboards.INLINE_CREATE_NOTE_BUTTON.callback_data)
    router.callback_query.register(handle_get_custom_subject, StateFilter(NoteCreationState.AskCustomSubject), NumCallback.filter())

    router.include_router(Dialog(
        Window(
            Const("❗ Сейчас не идёт никакой пары"),
            Button(text=Const("🗒️ Создать личную заметку"), id='create_note', on_click=on_create_note_button_click),
            Button(text=Format("Недавняя пара: {recent_subject}"), id="select_recent_subject", on_click=on_recent_subject_button_click),
            Button(text=Format("Выбрать другой предмет"), id="select_custom_subject", on_click=on_custom_subject_button_click),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            getter=no_subject_currently_getter,
            state=DueDateDialogState.NoSubjectCurrently,
        ),
        Window(
            Const("📅 Когда дедлайн?"),
            Group(
                Select(
                    Format("{item[1][1]}"),
                    id="select_next_class",
                    item_id_getter=operator.itemgetter(0),
                    type_factory=int,
                    items="next_classes",
                    on_click=on_class_selected,
                ),
                width=2
            ),
            Button(text=Const("📅 Выбрать другую дату"), id="button_custom_due_date", on_click=on_custom_due_date_button_clicK),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            getter=ask_deadline_getter,
            state=DueDateDialogState.AskDueDate
        ),
        Window(
            Const("📅 Укажите свою дату"),
            utils.CustomCalendar(id='due_date_calendar', on_click=handle_due_date_selected),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            getter=ask_custom_deadline_getter,
            state=DueDateDialogState.AskCustomDueDate,
        ),
    ))