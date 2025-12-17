from typing import Iterable
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

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