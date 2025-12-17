from aiogram import Router, Dispatcher, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums.parse_mode import ParseMode

import utils
import keyboards
import models
import database
from states import ConfigureUserState, MainState

async def handle_configure_group(call: types.CallbackQuery, state: FSMContext):
    with database.SCHEDULES_LOCK:
        msg_text, keyboard = utils.generate_choice_message(database.SCHEDULES)
    
    await call.message.edit_text(f"<b>Выберите факультет</b>:\n\n{msg_text}", reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
    await state.set_state(ConfigureUserState.Faculty)


async def handle_ask_faculty(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(faculty=callback_data.num)
    
    with database.SCHEDULES_LOCK:
        faculty = database.SCHEDULES[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(faculty.forms)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Факультет: <b>{faculty.name}</b>\n\n<b>Выберите форму обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(ConfigureUserState.Form)


async def handle_ask_form(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(form=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    
    with database.SCHEDULES_LOCK:
        form = database.SCHEDULES[faculty].forms[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(form.stages)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Форма обучения: <b>{form.name}</b>\n\n<b>Выберите ступень обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(ConfigureUserState.Stage)


async def handle_ask_stage(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(stage=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    
    with database.SCHEDULES_LOCK:
        stage = database.SCHEDULES[faculty].forms[form].stages[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(stage.courses)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Ступень обучения: <b>{stage.name}</b>\n\n<b>Выберите курс</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(ConfigureUserState.Course)


async def handle_ask_course(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    await state.update_data(course=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    
    with database.SCHEDULES_LOCK:
        course = database.SCHEDULES[faculty].forms[form].stages[stage].courses[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(course.groups)

    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Курс: <b>{course.name}</b>\n\n<b>Выберите группу</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup(),
                                 parse_mode=ParseMode.HTML)
    await state.set_state(ConfigureUserState.Group)


async def handle_ask_group(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    course: int = await state.get_value("course")
    
    with database.SCHEDULES_LOCK:
        group = database.SCHEDULES[faculty].forms[form].stages[stage].courses[course].groups[callback_data.num]
    
    await state.update_data(group_id=group.id)
    await state.update_data(group_name=group.name)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text='Без подгруппы', callback_data=utils.NumCallbackData(num=0).pack()))
    builder.row(
        types.InlineKeyboardButton(text='1', callback_data=utils.NumCallbackData(num=1).pack()),
        types.InlineKeyboardButton(text='2', callback_data=utils.NumCallbackData(num=2).pack())
    )
    
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text(f"Группа: <b>{group.name}</b>\n"
                                 "Выберите номер <b>подгруппы</b>, если такая есть. Если нет, нажмите кнопку <b>\"Без подгруппы\"</b>",
                                 reply_markup=builder.as_markup(),
                                 parse_mode=ParseMode.HTML)

    await state.set_state(ConfigureUserState.SubGroup)
    

async def handle_ask_subgroup(call: types.CallbackQuery, callback_data: utils.NumCallbackData, state: FSMContext):
    await call.answer()
    
    data = await state.get_data()
    group_id = data['group_id']
    group_name = data['group_name']
    subgroup = callback_data.num
    user_id = call.from_user.id
    
    user = database.get_user_by_id(user_id)
    assert(user is not None)
    
    user.group = models.UserGroup(group_id, group_name)
    user.subgroup = subgroup
    
    await call.message.edit_text("✅ <b>Группа успешна обновлена!</b>", parse_mode=ParseMode.HTML)
    
    await state.clear()
    
    
def register(router: Router):
    router.callback_query.register(handle_configure_group, StateFilter(MainState.Settings), utils.NumCallbackData.filter(F.num == 1))
    router.callback_query.register(handle_ask_faculty, StateFilter(ConfigureUserState.Faculty), utils.NumCallbackData.filter())
    router.callback_query.register(handle_ask_form, StateFilter(ConfigureUserState.Form), utils.NumCallbackData.filter())
    router.callback_query.register(handle_ask_stage, StateFilter(ConfigureUserState.Stage), utils.NumCallbackData.filter())
    router.callback_query.register(handle_ask_course, StateFilter(ConfigureUserState.Course), utils.NumCallbackData.filter())
    router.callback_query.register(handle_ask_group, StateFilter(ConfigureUserState.Group), utils.NumCallbackData.filter())
    router.callback_query.register(handle_ask_subgroup, StateFilter(ConfigureUserState.SubGroup), utils.NumCallbackData.filter())