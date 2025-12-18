from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums.parse_mode import ParseMode

from datetime import datetime

import constants
import keyboards
import database
import utils
import parse

from states import MainState

from utils import NumCallbackData

async def handle_start(message: types.Message):
    await message.reply(f"Привет! Я <b>{constants.BOT_NAME}</b> – помогу организовать учебный процесс. Я буду запоминать твои заметки и дедлайны, привязывая их к расписанию.",
                        reply_markup=keyboards.START_KEYBOARD,
                        parse_mode=ParseMode.HTML)


async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    await call.answer()
    await call.message.reply("Настройка отменена.")
    await call.message.delete_reply_markup()


async def check_user_exists(message: types.Message) -> bool:
    assert(message.from_user is not None)
    
    if not database.user_exists(message.from_user.id):
        await message.answer("Я тебя не знаю. Пожалуйста, напиши /start и пройди регистрацию.")
        return False
    return True

async def handle_new_note(message: types.Message):
    if not await check_user_exists(message): return
    
    user = database.get_user_by_id(message.from_user.id)
    assert(user is not None)
    
    date = message.date.astimezone(utils.DEFAULT_TIMEZONE)
    
    subjects = database.get_subjects(user.group.id, user.group.subgroup)
    
    found_subject: parse.ScheduleSubject | None = None
    
    for subject in subjects:
        if subject.time_start <= date <= subject.time_end:
            found_subject = subject
            break
        
    if found_subject is None:
        await message.reply("Сейчас не идёт никакой пары")
    else:
        await message.reply(f"Сейчас идёт пара \"<b>{found_subject.name}</b>\", верно?",
                            parse_mode=ParseMode.HTML)

async def handle_settings(message: types.Message, state: FSMContext):
    if not await check_user_exists(message): return
    
    assert(message.from_user is not None)
    
    user = database.get_user_by_id(message.from_user.id)
    assert(user is not None)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1", callback_data=NumCallbackData(num=1).pack()))
    builder.add(types.InlineKeyboardButton(text="2", callback_data=NumCallbackData(num=2).pack()))
    builder.add(types.InlineKeyboardButton(text="3", callback_data=NumCallbackData(num=3).pack()))
    builder.add(types.InlineKeyboardButton(text="4", callback_data=NumCallbackData(num=4).pack()))
    builder.add(types.InlineKeyboardButton(text="5", callback_data=NumCallbackData(num=5).pack()))
    builder.add(types.InlineKeyboardButton(text="6", callback_data=NumCallbackData(num=6).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    reminder_times_text = utils.user_reminder_times_to_text(user)
    
    await message.answer("<b>Введите номер пункта, который хотите изменить.</b>\n"
                         f"1. 🎓  Группа: {user.group.name}\n"
                         f"2. 🔔  Напоминания о дедлайнах: {reminder_times_text}\n"
                         f"3. 📊  Сводка: В 18:00\n"
                         f"4. 📝  Расписание на день: За 1 час до первой пары\n"
                         f"5. 🎯  Убеждаться в успешном выполнении задания: вкл\n"
                         f"6. ℹ️  Связаться с админом\n",
                         parse_mode=ParseMode.HTML,
                         reply_markup=builder.as_markup())
    
    await state.set_state(MainState.Settings)

def register(router: Router):
    router.message.register(handle_start, CommandStart())
    router.callback_query.register(handle_cancel, F.data == keyboards.CANCEL_BUTTON.callback_data)
    router.message.register(handle_settings, StateFilter(None), F.text == keyboards.SETTINGS_BUTTON.text)
    router.message.register(handle_new_note, StateFilter(None))