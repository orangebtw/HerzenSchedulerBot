from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from itertools import groupby

import constants
import keyboards
import database
import utils
from states import MainState, NoteEditState, DeleteUserDataState
from callbacks import NumCallback, NotificationCompleteCallback, NoteEditCallback
from handlers.utils import check_user_exists

MENU_MY_DEADLINES_ID = 1
MENU_SETTINGS_ID = 2

async def handle_start(message: types.Message, users_database: database.UsersDatabase, state: FSMContext):
    await state.clear()
    
    if users_database.user_exists(message.from_user.id):
        await state.set_state(DeleteUserDataState.Confirmation)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text='Да', callback_data='yes')],
            [keyboards.CANCEL_BUTTON]
        ])
        
        await message.reply("⚠️ <b>Внимание!</b>\n\n"
                            "Вы уже зарегистрированы, хотите ли вы удалить информацию о себе?",
                            reply_markup=keyboard)
        return
    
    await message.reply(f"Привет! Я <b>{constants.BOT_NAME}</b> – помогу организовать учебный процесс. Я буду запоминать твои заметки и дедлайны, привязывая их к расписанию.",
                        reply_markup=keyboards.START_KEYBOARD)


async def handle_confirm_delete_info(call: types.CallbackQuery, state: FSMContext, users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    users_database.delete_by_id(call.from_user.id)
    notes_database.delete_all_by_user_id(call.from_user.id)
    
    await call.message.edit_text("<b>Информация о вас успешна удалена!</b>\n\nЧтобы продолжать пользоваться ботом, вам нужно снова пройти регистрацию с помощью /start.")
    
    await state.clear()

async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    await call.answer()
    await call.message.edit_text("Отменено")


async def handle_menu(message: types.Message, state: FSMContext, users_database: database.UsersDatabase):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text="1", callback_data=NumCallback(num=MENU_MY_DEADLINES_ID).pack()))
    keyboard.add(types.InlineKeyboardButton(text="2", callback_data=NumCallback(num=MENU_SETTINGS_ID).pack()))
    keyboard.row(keyboards.CANCEL_BUTTON)
    
    await message.reply("<b>Меню</b>\n\n"
                        "1) 📅 Мои дедлайны\n\n"
                        "2) ⚙️ Настройки\n",
                        reply_markup=keyboard.as_markup())
    
    await state.set_state(MainState.Menu)
    

async def handle_settings(call: types.CallbackQuery, state: FSMContext, users_database: database.UsersDatabase):
    user = users_database.get_user_by_id(call.from_user.id)
    assert(user is not None)
    
    reminder_times_text = utils.user_reminder_times_to_text(user)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1", callback_data=NumCallback(num=1).pack()))
    builder.add(types.InlineKeyboardButton(text="2", callback_data=NumCallback(num=2).pack()))
    builder.add(types.InlineKeyboardButton(text="3", callback_data=NumCallback(num=3).pack()))
    # builder.add(types.InlineKeyboardButton(text="4", callback_data=NumCallbackData(num=4).pack()))
    # builder.add(types.InlineKeyboardButton(text="5", callback_data=NumCallbackData(num=5).pack()))
    # builder.add(types.InlineKeyboardButton(text="6", callback_data=NumCallbackData(num=6).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text("<b>Выберите номер пункта, который хотите изменить:</b>\n"
                         f"1. 🎓  Группа: {user.group.name}\n"
                         f"2. 🔔  Напоминания о дедлайнах: {reminder_times_text}\n"
                        #  f"3. 📊  Сводка: В 18:00\n"
                        #  f"4. 📝  Расписание на день: За 1 час до первой пары\n"
                        #  f"5. 🎯  Убеждаться в успешном выполнении задания: вкл\n"
                         f"3. ℹ️  Связаться с админом\n",
                         reply_markup=builder.as_markup())
    
    await state.set_state(MainState.Settings)


async def handle_my_deadlines(call: types.CallbackQuery, state: FSMContext, notes_database: database.NotesDatabase):
    count, total_notes = notes_database.get_notes_by_user_id(call.from_user.id)
    
    if count > 0:
        builder = InlineKeyboardBuilder()
        
        total_notes = list(total_notes)
        
        subject_notes = filter(lambda n: n.subject_id is not None, total_notes)
        personal_notes = filter(lambda n: n.subject_id is None, total_notes) 
        
        sorted_subject_notes = sorted(subject_notes, key=lambda n: n.subject_id)
        
        msg_text = ""
        i = 1
        
        grouped_notes = groupby(sorted_subject_notes, key=lambda n: n.subject_id)
        for subject, notes in grouped_notes:
            msg_text += f"<b>{subject}</b>:\n"
            sorted_notes = sorted(notes, key=lambda n: n.due_date and n.is_completed)
            with utils.time_locale('ru_RU.UTF-8'):
                for note in sorted_notes:
                    date_text: str = note.due_date.strftime("%d %b %Y")
                    msg_text += f"    {i}) "
                    if note.is_completed:
                        msg_text += f"<s>\"{note.text}\" — к {date_text}</s>"
                    else:
                        msg_text += f"\"{note.text}\" — к {date_text}"
                    msg_text += '\n'
                    builder.add(types.InlineKeyboardButton(text=str(i), callback_data=NoteEditCallback(note_id=note.id).pack()))
                    i += 1
            msg_text += "\n"
            
        sorted_personal_notes = sorted(personal_notes, key=lambda n: n.due_date and n.is_completed)
            
        if len(sorted_personal_notes) > 0:
            msg_text += "<b>Личные заметки</b>:\n"
            with utils.time_locale('ru_RU.UTF-8'):
                for note in sorted_personal_notes:
                    date_text: str = note.due_date.strftime("%d %b %Y")
                    msg_text += f"    {i}) "
                    if note.is_completed:
                        msg_text += f"<s>\"{note.text}\" — к {date_text}</s>"
                    else:
                        msg_text += f"\"{note.text}\" — к {date_text}"
                    msg_text += '\n'
                    builder.add(types.InlineKeyboardButton(text=str(i), callback_data=NoteEditCallback(note_id=note.id).pack()))
                    i += 1
            
        builder.row(keyboards.CANCEL_BUTTON)
            
        await call.message.edit_text("<b>Ваши дедлайны:</b>\n\n"
                                     "<i>Для внесения изменений нажмите на кнопку, соответствующей номеру дедлайна.</i>\n\n"
                                     f"{msg_text}",
                                     reply_markup=builder.as_markup(resize_keyboard=True))
        await state.set_state(NoteEditState.Menu)
    else:
        await call.message.edit_text("У вас пока нет дедлайнов.")
        await state.clear()


async def handle_admins_info(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("<b>Наши контакты:</b>\n"
                                 "@hghhdhdhshshshsh\n"
                                 "@orangebtw\n"
                                 "@ekumekum\n")
    await state.clear()


async def handle_notification_complete(
    call: types.CallbackQuery,
    callback_data: NotificationCompleteCallback,
    notes_database: database.NotesDatabase
):
    notes_database.update_note_completed(callback_data.note_id, True)
    
    await call.answer("Задание помечено как выполненное")
    await call.message.edit_reply_markup(reply_markup=None)

def register(router: Router):
    router.callback_query.register(handle_cancel, F.data == keyboards.CANCEL_BUTTON.callback_data)
    router.callback_query.register(handle_confirm_delete_info, StateFilter(DeleteUserDataState.Confirmation), F.data == 'yes')
    
    router.message.register(handle_start, CommandStart())
    router.message.register(handle_menu, StateFilter(None), Command("menu"))
    
    router.callback_query.register(handle_settings, StateFilter(MainState.Menu), NumCallback.filter(F.num == MENU_SETTINGS_ID))
    router.callback_query.register(handle_my_deadlines, StateFilter(MainState.Menu), NumCallback.filter(F.num == MENU_MY_DEADLINES_ID))
    router.callback_query.register(handle_admins_info, StateFilter(MainState.Settings), NumCallback.filter(F.num == 3))
    router.callback_query.register(handle_notification_complete, StateFilter(None), NotificationCompleteCallback.filter())