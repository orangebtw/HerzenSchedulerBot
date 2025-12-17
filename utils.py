from typing import Iterable
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import models

DEFAULT_TIMEZONE = "Europe/Moscow"

class NumCallbackData(CallbackData, prefix="data-int"):
    num: int

def seconds_before_time(t: str) -> float:
    now = datetime.now(tz=ZoneInfo(DEFAULT_TIMEZONE))
    wait_for = time.fromisoformat(t)
    target = datetime.combine(now, wait_for, now.tzinfo)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()

def generate_choice_message(iterable: Iterable) -> tuple[str, InlineKeyboardBuilder]:
    msg_text = ""
    builder = InlineKeyboardBuilder()
    
    for i, form in enumerate(iterable):
        msg_text += f"{i+1}. "
        msg_text += f"<b>{form.name}</b>"
        msg_text += '\n'
        builder.button(text=str(i+1), callback_data=NumCallbackData(num=i).pack())
    return (msg_text, builder)

def user_reminder_times_to_text(user: models.User) -> str:
    reminder_times_length = sum(True for x in user.reminder_times if x is not None)
    reminder_times_text = "За "
    
    for i, reminder_time in enumerate(user.reminder_times):
        if reminder_time is None:
            continue
        
        t = reminder_time.value
        
        if i > 0 and i == reminder_times_length - 1:
            reminder_times_text += " и за "
        elif i > 0 and i < reminder_times_length - 1:
            reminder_times_text += ", за "
            
        secs = t.total_seconds()
        
        if secs >= 86400:
            d = int(secs / 86400)
            secs -= secs * 86400
            reminder_times_text += f"<b>{d} д.</b>"
            if secs > 0:
                reminder_times_text += " "
            
        if secs >= 3600:
            h = int(secs / 3600)
            secs -= secs * 3600
            reminder_times_text += f"<b>{h} ч.</b>"
            if secs > 0:
                reminder_times_text += " "
            
        if secs >= 60:
            m = int(secs / 60)
            reminder_times_text += f"<b>{m} м.</b>"
    return reminder_times_text