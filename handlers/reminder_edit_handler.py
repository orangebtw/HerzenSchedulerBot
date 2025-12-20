from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State

from aiogram_dialog import DialogManager, StartMode, Dialog, Window, ShowMode
from aiogram_dialog.widgets.kbd.button import Button
from aiogram_dialog.widgets.kbd.state import Cancel
from aiogram_dialog.widgets.input.text import TextInput
from aiogram_dialog.widgets.kbd.calendar_kbd import CalendarConfig
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.kbd.group import Group

from datetime import date, datetime, timedelta, time

from states import NoteEditState

from callbacks import NoteEditCallback

import database
import models
import utils

class NoteEditMenuDialog(StatesGroup):
    first = State()

class NoteEditTextDialog(StatesGroup):
    first = State()
    
class NoteEditDueDateDialog(StatesGroup):
    first = State()

async def handle_reminder_edit_menu(call: types.CallbackQuery, callback_data: NoteEditCallback, state: FSMContext, dialog_manager: DialogManager):
    await call.answer()
    await state.clear()
    await dialog_manager.start(NoteEditMenuDialog.first, data={'note_id': callback_data.note_id}, mode=StartMode.RESET_STACK)


async def on_delete_button_click(call: types.CallbackQuery, button: Button, dialog_manager: DialogManager):
    notes_database: database.NotesDatabase = dialog_manager.middleware_data['notes_database']
    note_id = dialog_manager.start_data['note_id']
    
    notes_database.delete_note_by_id(note_id)
    
    await call.message.edit_text("✅ Напоминание успешно удалено!")
    
    await dialog_manager.done()


async def on_edit_text_button_click(call: types.CallbackQuery, button: Button, dialog_manager: DialogManager):
    note_id = dialog_manager.start_data['note_id']
    await dialog_manager.start(NoteEditTextDialog.first, data={'note_id': note_id}, mode=StartMode.RESET_STACK)


async def on_edit_due_date_button_click(call: types.CallbackQuery, button: Button, dialog_manager: DialogManager):
    note_id = dialog_manager.start_data['note_id']
    await dialog_manager.start(NoteEditDueDateDialog.first, data={'note_id': note_id}, mode=StartMode.RESET_STACK)

async def on_change_staus_button_click(call: types.CallbackQuery, button: Button, dialog_manager: DialogManager):
    notes_database: database.NotesDatabase = dialog_manager.middleware_data['notes_database']
    note_id = dialog_manager.start_data['note_id']
    note = notes_database.get_note_by_id(note_id)
    
    notes_database.update_note_completed(note.id, not note.is_completed)
    
    await call.message.edit_text("✅ Статус напоминания успешно изменён!")
    
    await dialog_manager.done()

async def on_cancel_button_click(call: types.CallbackQuery, button: Button, dialog_manager: DialogManager):
    await call.message.edit_text("Отменено")
    

async def on_new_text_input_success(message: types.Message, text_input: TextInput, dialog_manager: DialogManager, data: str):
    notes_database: database.NotesDatabase = dialog_manager.middleware_data['notes_database']
    note_id = dialog_manager.start_data['note_id']
    
    notes_database.update_note_text(note_id, data)
    
    await message.reply("✅ Текст напоминания успешно изменён!")
    
    await dialog_manager.done()


async def on_new_due_date_selected(
    call: types.CallbackQuery,
    widget,
    manager: DialogManager,
    selected_date: date
):
    if selected_date < utils.tz_now().date():
        await call.message.reply("❗ Дата не должна быть раньше сегодняшнего дня.")
        await manager.done()
        return
    
    notes_database: database.NotesDatabase = manager.middleware_data['notes_database']
    note_id = manager.start_data['note_id']
    
    notes_database.update_note_due_date(note_id, datetime.combine(selected_date - timedelta(days=1), time(hour=23, minute=59), tzinfo=utils.DEFAULT_TIMEZONE))
    
    await call.message.edit_text("✅ Дедлайн напоминания успешно обновлён!")
    await manager.done()


async def edit_duedate_getter(dialog_manager: DialogManager, **kwargs):
    min_date = utils.tz_now().date()
    return {
        'calendar_min_date': min_date
    }
    
    
async def menu_getter(dialog_manager: DialogManager, **kwargs):
    notes_database: database.NotesDatabase = dialog_manager.middleware_data['notes_database']
    note_id = dialog_manager.start_data['note_id']
    note = notes_database.get_note_by_id(note_id)
    
    with utils.time_locale('ru_RU.UTF-8'):
        date_text: str = note.due_date.strftime("%d %b %Y")
    
    if note.is_completed:
        reminder_text = f"<s>\"{note.text}\" — к {date_text}</s>"
    else:
        reminder_text = f"\"{note.text}\" — к {date_text}"
    change_status_text = "✅ Пометить как выполненное" if not note.is_completed else "⛔ Пометить как невыполненное"
    
    return {
        "reminder_text": reminder_text,
        "change_status_text": change_status_text
    }


def register(router: Router):
    router.callback_query.register(handle_reminder_edit_menu, StateFilter(NoteEditState.Menu), NoteEditCallback.filter())
    
    menu_dialog = Dialog(
        Window(
            Format("<b>Редактирование напоминания:</b>\n"
                   "{reminder_text}\n\n"
                    "<b>Выберите, что хотите сделать</b>\n"
                    "1) ✏️ Редактировать текст\n"
                    "2) 📅 Редактировать дедлайн\n"
                    "3) {change_status_text}\n"
                    "4) 🗑️ Удалить\n"),
            Group(
                Button(text=Const("1"), id="button_edit_text", on_click=on_edit_text_button_click),
                Button(text=Const("2"), id="button_edit_due_date", on_click=on_edit_due_date_button_click),
                Button(text=Const("3"), id="button_edit_status", on_click=on_change_staus_button_click),
                Button(text=Const("4"), id="button_delete", on_click=on_delete_button_click),
                width=2
            ),
            Cancel(text=Const("Отмена"), on_click=on_cancel_button_click),
            getter=menu_getter,
            state=NoteEditMenuDialog.first
        ),
    )
    
    edit_text_dialog = Dialog(
        Window(
            Const("✏️ Введите новый текст напоминания"),
            TextInput(id="input_new_text", on_success=on_new_text_input_success),
            state=NoteEditTextDialog.first
        ),
    )
    
    edit_due_date_dialog = Dialog(
        Window(
            Const("📅 Укажите новый дедлайн"),
            utils.CustomCalendar(id="calendar", on_click=on_new_due_date_selected),
            getter=edit_duedate_getter,
            state=NoteEditDueDateDialog.first,
        )
    )
    
    router.include_routers(menu_dialog, edit_text_dialog, edit_due_date_dialog)