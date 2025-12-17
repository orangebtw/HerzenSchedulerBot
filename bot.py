import asyncio
from typing import Iterable
from aiogram import Router, Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums.parse_mode import ParseMode
import parse
import threading
import utils

import models

BOT_TOKEN = "7452071105:AAHlweugvBzmwwKYSSWb8cWmx6t2NskBbXM"
BOT_NAME = "Herzen Organizer"

CONFIGURE_GROUP_BUTTON = types.KeyboardButton(text="Настроить группу")
CANCEL_BUTTON = types.InlineKeyboardButton(text="Отмена", callback_data='cancel')

START_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[CONFIGURE_GROUP_BUTTON]], resize_keyboard=True)

SETTINGS_BUTTON = types.KeyboardButton(text="⚙️ Настройки")

MAIN_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[SETTINGS_BUTTON]], resize_keyboard=True)

SCHEDULES: list[parse.ScheduleFaculty] = []
SCHEDULES_LOCK = threading.Lock()

USERS: list[models.User] = []
NOTES: list[models.UserNote] = []

class UserData(StatesGroup):
    Faculty = State()
    Form = State()
    Stage = State()
    Course = State()
    Group = State()
    SubGroup = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data_router = Router()

@dp.message(CommandStart())
async def handle_welcome(message: types.Message):
    await message.reply(f"Привет! Я <b>{BOT_NAME}</b> – помогу организовать учебный процесс. Я буду запоминать твои заметки и дедлайны, привязывая их к расписанию.",
                        reply_markup=START_KEYBOARD,
                        parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == CANCEL_BUTTON.callback_data)
async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    await call.answer()
    await call.message.reply("Настройка отменена.")
    await call.message.delete_reply_markup()

@dp.message(F.text == CONFIGURE_GROUP_BUTTON.text)
async def handle_configure_group(message: types.Message, state: FSMContext):
    with SCHEDULES_LOCK:
        msg_text, keyboard = utils.generate_choice_message(SCHEDULES)
    
    await message.reply(f"<b>Выберите факультет</b>:\n\n{msg_text}", reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
    await state.set_state(UserData.Faculty)

@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.Faculty)
async def handle_ask_faculty(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(faculty=callback_data.num)
    
    with SCHEDULES_LOCK:
        faculty = SCHEDULES[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(faculty.forms)
    
    keyboard.row(CANCEL_BUTTON)

    await call.message.edit_text(f"Факультет: <b>{faculty.name}</b>\n\n<b>Выберите форму обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(UserData.Form)

@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.Form)
async def handle_ask_form(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(form=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    
    with SCHEDULES_LOCK:
        form = SCHEDULES[faculty].forms[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(form.stages)
    
    keyboard.row(CANCEL_BUTTON)

    await call.message.edit_text(f"Форма обучения: <b>{form.name}</b>\n\n<b>Выберите ступень обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(UserData.Stage)

@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.Stage)
async def handle_ask_stage(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(stage=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    
    with SCHEDULES_LOCK:
        stage = SCHEDULES[faculty].forms[form].stages[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(stage.courses)
    
    keyboard.row(CANCEL_BUTTON)

    await call.message.edit_text(f"Ступень обучения: <b>{stage.name}</b>\n\n<b>Выберите курс</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(UserData.Course)

@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.Course)
async def handle_ask_course(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(course=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    
    with SCHEDULES_LOCK:
        course = SCHEDULES[faculty].forms[form].stages[stage].courses[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(course.groups)

    keyboard.row(CANCEL_BUTTON)

    await call.message.edit_text(f"Курс: <b>{course.name}</b>\n\n<b>Выберите группу</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(UserData.Group)

@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.Group)
async def handle_ask_group(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    course: int = await state.get_value("course")
    
    with SCHEDULES_LOCK:
        group_id = SCHEDULES[faculty].forms[form].stages[stage].courses[course].groups[callback_data.num].id
    
    await state.update_data(group_id=group_id)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text='Без подгруппы', callback_data=utils.NumCallbackData(num=0).pack()))
    builder.row(
        types.InlineKeyboardButton(text='1', callback_data=utils.NumCallbackData(num=1).pack()),
        types.InlineKeyboardButton(text='2', callback_data=utils.NumCallbackData(num=2).pack())
    )
    
    builder.row(CANCEL_BUTTON)
    
    await call.message.edit_text("Выберите номер <b>подгруппы</b>, если такая есть. Если нет, нажмите кнопку <b>\"Без подгруппы\"</b>",
                                 reply_markup=builder.as_markup(),
                                 parse_mode=ParseMode.HTML)

    await state.set_state(UserData.SubGroup)
    
@user_data_router.callback_query(utils.NumCallbackData.filter(), UserData.SubGroup)
async def handle_ask_subgroup(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    
    data = await state.get_data()
    group_id = data['group_id']
    subgroup = callback_data.num
    
    user_id = call.from_user.id
    
    USERS.append(models.User(user_id, group_id, subgroup))
    
    await call.message.edit_text("<b>Хорошо, всё готово!</b>", parse_mode=ParseMode.HTML)
    
    await state.clear()

async def update_groups(time: str):
    global SCHEDULES
    while True:
        with SCHEDULES_LOCK:
            SCHEDULES = parse.parse_groups()
        await asyncio.sleep(utils.seconds_before_time(time))

async def on_startup():
    loop = asyncio.get_event_loop()
    loop.create_task(update_groups('00:00'))
    
async def main():
    dp.startup.register(on_startup)
    dp.include_router(user_data_router)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
