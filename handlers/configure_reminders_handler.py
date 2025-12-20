from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import timedelta
import logging

import utils
import keyboards
import models
import database
from callbacks import NumCallback
from states import ConfigureReminderState, MainState

logger = logging.getLogger(__name__)

async def handle_configure_reminders(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="1 раз", callback_data=NumCallback(num=1).pack()))
    builder.add(types.InlineKeyboardButton(text="2 раза", callback_data=NumCallback(num=2).pack()))
    builder.add(types.InlineKeyboardButton(text="3 раза", callback_data=NumCallback(num=3).pack()))
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text("Укажите сколько раз вам напомнить о дедлайне?", reply_markup=builder.as_markup())
    
    await state.set_state(ConfigureReminderState.AskTime)


async def handle_ask_time(call: types.CallbackQuery, callback_data: NumCallback, state: FSMContext):
    await call.answer()
    
    range_from = callback_data.num
    
    await state.update_data(total=callback_data.num)
    await state.update_data(current=1)
    
    builder = InlineKeyboardBuilder()
    builder.row(keyboards.CANCEL_BUTTON)
    
    await call.message.edit_text(f"⏰ Укажите количесто <b>часов</b> от {range_from} до 168 включительно, за которое необходимо напоминать в 1-й раз.",
                                 reply_markup=builder.as_markup())
    
    await state.set_state(ConfigureReminderState.GetTime)


async def handle_get_time(message: types.Message, state: FSMContext, users_database: database.UsersDatabase):
    total = await state.get_value("total")
    current = await state.get_value("current", 1)
        
    values: list[int] = await state.get_value("values", [])
    
    range_start = total - current + 1
    range_end = values[current-2]-1 if current > 1 else 168
    
    if total > 1 and current == total:
        range_end *= 60
    
    value = int(message.text)
    if not (range_start <= value <= range_end):
        await message.answer(f"Значение не входит в нужный диапазон. Попробуйте ещё раз.")
        return
    
    values.append(value)
    
    range_start -= 1
    range_end = value - 1
    current += 1
    
    if current <= total:
        if total > 1 and current == total:
            range_end *= 60
        
        await state.update_data(current=current)
        await state.update_data(values=values)
        
        builder = InlineKeyboardBuilder()
        builder.row(keyboards.CANCEL_BUTTON)
        
        if total > 1 and current == total:
            await message.answer(f"⏰ Укажите количесто <b>минут</b> от {range_start} до {range_end} включительно, за которое необходимо напоминать в {current}-й раз.",
                                reply_markup=builder.as_markup())
        else:
            await message.answer(f"⏰ Укажите количесто <b>часов</b> от {range_start} до {range_end} включительно, за которое необходимо напоминать в {current}-й раз.",
                                reply_markup=builder.as_markup())
    else:
        user = users_database.get_user_by_id(message.from_user.id)
        assert(user is not None)
        
        reminder_times = list(user.reminder_times)
    
        for i in range(0, len(values) - 1):
            reminder_times[i] = models.UserReminderTime(timedelta(hours=values[i]))
        reminder_times[-1] = models.UserReminderTime(timedelta(minutes=values[-1]))

        user.reminder_times = tuple(reminder_times)
        
        users_database.insert_user(user)
        
        await message.answer("✅ <b>Напоминания о дедлайнах успешно обновлены!</b>")
        
        await state.clear()
        
        logger.info(f"User '{message.from_user.id}' updated reminder times")

def register(router: Router):
    router.callback_query.register(handle_configure_reminders, StateFilter(MainState.Settings), NumCallback.filter(F.num == 2))
    router.callback_query.register(handle_ask_time, StateFilter(ConfigureReminderState.AskTime), NumCallback.filter())
    router.message.register(handle_get_time, StateFilter(ConfigureReminderState.GetTime), F.text.isdigit())