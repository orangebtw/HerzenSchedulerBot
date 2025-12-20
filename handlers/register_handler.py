from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import StateFilter

import utils
from callbacks import NumCallback
import keyboards
import models
import database
import logging
from states import RegisterUserState

logger = logging.getLogger(__name__)

async def handle_configure_group(message: types.Message, state: FSMContext, groups_database: database.GroupsDatabase):
    logger.info(f"User '{message.from_user.id}' has started registration")
    
    with groups_database.get_groups() as groups:
        msg_text, keyboard = utils.generate_choice_message(groups)
        
    keyboard.row(keyboards.CANCEL_BUTTON)
    
    await message.reply(f"<b>Выберите факультет</b>:\n\n{msg_text}", reply_markup=keyboard.as_markup())
    await state.set_state(RegisterUserState.Faculty)


async def handle_ask_faculty(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, groups_database: database.GroupsDatabase):
    await call.answer()
    await state.update_data(faculty=callback_data.num)
    
    with groups_database.get_groups() as groups:
        faculty = groups[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(faculty.forms)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Факультет: <b>{faculty.name}</b>\n\n<b>Выберите форму обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup())
    await state.set_state(RegisterUserState.Form)


async def handle_ask_form(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, groups_database: database.GroupsDatabase):
    await call.answer()
    await state.update_data(form=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    
    with groups_database.get_groups() as groups:
        form = groups[faculty].forms[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(form.stages)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Форма обучения: <b>{form.name}</b>\n\n<b>Выберите ступень обучения</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup())
    await state.set_state(RegisterUserState.Stage)


async def handle_ask_stage(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, groups_database: database.GroupsDatabase):
    await call.answer()
    await state.update_data(stage=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    
    with groups_database.get_groups() as groups:
        stage = groups[faculty].forms[form].stages[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(stage.courses)
    
    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Ступень обучения: <b>{stage.name}</b>\n\n<b>Выберите курс</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup())
    await state.set_state(RegisterUserState.Course)


async def handle_ask_course(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, groups_database: database.GroupsDatabase):
    await call.answer()
    await state.update_data(course=callback_data.num)
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    
    with groups_database.get_groups() as groups:
        course = groups[faculty].forms[form].stages[stage].courses[callback_data.num]
        msg_text, keyboard = utils.generate_choice_message(course.groups)

    keyboard.row(keyboards.CANCEL_BUTTON)

    await call.message.edit_text(f"Курс: <b>{course.name}</b>\n\n<b>Выберите группу</b>:\n\n{msg_text}",
                                 reply_markup=keyboard.as_markup())
    await state.set_state(RegisterUserState.Group)


async def handle_ask_group(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, groups_database: database.GroupsDatabase):
    await call.answer()
    
    faculty: int = await state.get_value("faculty")
    form: int = await state.get_value("form")
    stage: int = await state.get_value("stage")
    course: int = await state.get_value("course")
    
    with groups_database.get_groups() as groups:
        group = groups[faculty].forms[form].stages[stage].courses[course].groups[callback_data.num]
    
    await state.update_data(group_id=group.id)
    await state.update_data(group_name=group.name)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text='1', callback_data=NumCallback(num=1).pack()),
        types.InlineKeyboardButton(text='2', callback_data=NumCallback(num=2).pack())
    )
    builder.row(types.InlineKeyboardButton(text='Без подгруппы', callback_data=NumCallback(num=0).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text(f"Группа: <b>{group.name}</b>\n"
                                 "Выберите номер <b>подгруппы</b>, если такая есть. Если нет, нажмите кнопку <b>\"Без подгруппы\"</b>.",
                                 reply_markup=builder.as_markup())

    await state.set_state(RegisterUserState.SubGroup)
    

async def handle_ask_subgroup(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext, users_database: database.UsersDatabase):
    await call.answer()
    
    data = await state.get_data()
    group_id = data['group_id']
    group_name = data['group_name']
    subgroup = callback_data.num if callback_data.num > 0 else None
    user_id = call.from_user.id
    
    users_database.insert_user(models.User(user_id, models.UserGroupWithName(group_name, group_id, subgroup)))
    
    await call.message.edit_text("<b>Отлично, всё готово!</b> 🎉")
    
    await call.message.answer("Теперь я могу привязывать твои заметки к расписанию.\n"
                              "Просто напиши мне что-нибудь во время пары — я пойму, к какому предмету это относится.")
    
    await state.clear()
    
    logger.info(f"Registered user with the id '{user_id}'")
    
async def handle_cancel(call: types.CallbackQuery, state: FSMContext):
    logger.info(f"User '{call.from_user.id}' has cancelled registration")
    
    await state.clear()
    
    await call.answer()
    await call.message.edit_text("Регистрация отменена.", reply_markup=keyboards.START_KEYBOARD)
    
def register(router: Router):
    router.message.register(handle_configure_group, StateFilter(None), F.text == keyboards.CONFIGURE_GROUP_BUTTON.text)
    router.callback_query.register(handle_cancel, StateFilter(RegisterUserState), F.data == keyboards.CANCEL_BUTTON.callback_data)
    router.callback_query.register(handle_ask_faculty, StateFilter(RegisterUserState.Faculty), NumCallback.filter())
    router.callback_query.register(handle_ask_form, StateFilter(RegisterUserState.Form), NumCallback.filter())
    router.callback_query.register(handle_ask_stage, StateFilter(RegisterUserState.Stage), NumCallback.filter())
    router.callback_query.register(handle_ask_course, StateFilter(RegisterUserState.Course), NumCallback.filter())
    router.callback_query.register(handle_ask_group, StateFilter(RegisterUserState.Group), NumCallback.filter())
    router.callback_query.register(handle_ask_subgroup, StateFilter(RegisterUserState.SubGroup), NumCallback.filter())