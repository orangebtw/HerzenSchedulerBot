from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from itertools import groupby

import constants
import keyboards
import database
import utils
from states import MainState
from utils import NumCallbackData
from handlers.utils import check_user_exists

async def handle_start(message: types.Message, users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    users_database.delete_by_id(message.from_user.id)
    notes_database.delete_by_user_id(message.from_user.id)
    
    await message.reply(f"Привет! Я <b>{constants.BOT_NAME}</b> – помогу организовать учебный процесс. Я буду запоминать твои заметки и дедлайны, привязывая их к расписанию.",
                        reply_markup=keyboards.START_KEYBOARD)


async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    await call.answer()
    await call.message.edit_text("Настройка отменена.")

async def handle_settings(message: types.Message, state: FSMContext, users_database: database.UsersDatabase):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    assert(message.from_user is not None)
    
    user = users_database.get_user_by_id(message.from_user.id)
    assert(user is not None)
    
    reminder_times_text = utils.user_reminder_times_to_text(user)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1", callback_data=NumCallbackData(num=1).pack()))
    builder.add(types.InlineKeyboardButton(text="2", callback_data=NumCallbackData(num=2).pack()))
    builder.add(types.InlineKeyboardButton(text="3", callback_data=NumCallbackData(num=3).pack()))
    # builder.add(types.InlineKeyboardButton(text="4", callback_data=NumCallbackData(num=4).pack()))
    # builder.add(types.InlineKeyboardButton(text="5", callback_data=NumCallbackData(num=5).pack()))
    # builder.add(types.InlineKeyboardButton(text="6", callback_data=NumCallbackData(num=6).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    await message.answer("<b>Выберите номер пункта, который хотите изменить:</b>\n"
                         f"1. 🎓  Группа: {user.group.name}\n"
                         f"2. 🔔  Напоминания о дедлайнах: {reminder_times_text}\n"
                        #  f"3. 📊  Сводка: В 18:00\n"
                        #  f"4. 📝  Расписание на день: За 1 час до первой пары\n"
                        #  f"5. 🎯  Убеждаться в успешном выполнении задания: вкл\n"
                         f"3. ℹ️  Связаться с админом\n",
                         reply_markup=builder.as_markup())
    
    await state.set_state(MainState.Settings)


async def handle_my_deadlines(message: types.Message, state: FSMContext, users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    if not await check_user_exists(message, users_database=users_database):
        return
    
    count, notes = notes_database.get_notes_by_user_id(message.from_user.id)
    
    if count > 0:
        notes = list(notes)
        
        subject_notes = filter(lambda n: n.subject_id is not None, notes)
        personal_notes = filter(lambda n: n.subject_id is None, notes)
        
        sorted_subject_notes = sorted(subject_notes, key=lambda n: n.due_date)
        sorted_personal_notes = sorted(personal_notes, key=lambda n: n.due_date)
        
        msg_text = ""
        i = 0
        
        grouped_notes = groupby(sorted_subject_notes, lambda n: n.subject_id)
        for subject, notes in grouped_notes:
            if subject is None:
                continue
            msg_text += f"<b>{subject}</b>\n"
            for note in notes:
                with utils.time_locale('ru_RU.UTF-8'):
                    date_text: str = note.due_date.strftime("%d %b %Y")
                msg_text += f"    {i+1}) "
                if note.is_completed:
                    msg_text += f"<s>\"{note.text}\" — к {date_text}</s>"
                else:
                    msg_text += f"\"{note.text}\" — к {date_text}"
                i += 1
                msg_text += '\n'
            msg_text += "\n"
            
        msg_text += "<b>Личные заметки</b>\n"
        for note in sorted_personal_notes:
            with utils.time_locale('ru_RU.UTF-8'):
                date_text: str = note.due_date.strftime("%d %b %Y")
            msg_text += f"    {i+1}) "
            if note.is_completed:
                msg_text += f"<s>\"{note.text}\" — к {date_text}</s>"
            else:
                msg_text += f"\"{note.text}\" — к {date_text}"
            i += 1
            msg_text += '\n'
            
        await message.reply(f"<b>Ваши дедлайны:</b>\n\n{msg_text}")
    else:
        await message.reply("У вас пока нет дедлайнов.")


async def handle_admins_info(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("<b>Наши контакты:</b>\n"
                                 "@hghhdhdhshshshsh\n"
                                 "@orangebtw\n"
                                 "@ekumekum\n")
    await state.clear()


def register(router: Router):
    router.message.register(handle_start, CommandStart())
    router.callback_query.register(handle_cancel, F.data == keyboards.CANCEL_BUTTON.callback_data)
    router.message.register(handle_settings, StateFilter(None), F.text == keyboards.SETTINGS_BUTTON.text)
    router.message.register(handle_my_deadlines, StateFilter(None), F.text == keyboards.MY_DEADLINES_BUTTON.text)
    
    router.callback_query.register(handle_admins_info, StateFilter(MainState.Settings), utils.NumCallbackData.filter(F.num == 3))