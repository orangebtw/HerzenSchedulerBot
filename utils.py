from typing import Iterable
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, time, timedelta, date
from zoneinfo import ZoneInfo
from contextlib import contextmanager

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd.calendar_kbd import Calendar, CalendarConfig, CalendarUserConfig, CalendarScope, CalendarScopeView, CalendarDaysView, CalendarMonthView, CalendarYearsView
from aiogram_dialog.widgets.text import Format, Text

from babel.dates import get_day_names, get_month_names

import threading
import locale
import models
from callbacks import NumCallback

DEFAULT_TIMEZONE = ZoneInfo("Europe/Moscow")


class WeekDay(Text):
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        locale = manager.event.from_user.language_code
        return get_day_names(width="abbreviated", context="stand-alone", locale=locale)[selected_date.weekday()].title()


class Month(Text):
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        locale = manager.event.from_user.language_code
        return get_month_names("wide", context="stand-alone", locale=locale)[selected_date.month].title()


class CustomCalendar(Calendar):
    def __init__(self, id, on_click = None, config = None, when = None):
        super().__init__(id, on_click, config if config else CalendarConfig(firstweekday=0, timezone=DEFAULT_TIMEZONE), when)
    
    def _init_views(self) -> dict[CalendarScope, CalendarScopeView]:
        return {
            CalendarScope.DAYS: CalendarDaysView(
                self._item_callback_data,
                weekday_text=WeekDay(),
                header_text="🗓 " + Month() + " " + Format("{date:%Y}"),
                next_month_text=Month() + ' >>',
                prev_month_text='<< ' + Month()
            ),
            CalendarScope.MONTHS: CalendarMonthView(
                self._item_callback_data,
                month_text=Month(),
                this_month_text="[" + Month() + "]",
            ),
            CalendarScope.YEARS: CalendarYearsView(
                self._item_callback_data,
            ),
        }

    async def _get_user_config(self, data: dict, manager: DialogManager) -> CalendarUserConfig:
        return CalendarUserConfig(min_date=data['calendar_min_date'])


def seconds_before_time(t: str) -> float:
    now = datetime.now(tz=DEFAULT_TIMEZONE)
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
        builder.button(text=str(i+1), callback_data=NumCallback(num=i).pack())
    return (msg_text, builder)

def seconds_to_text(seconds: int) -> str:
    text = ""
    
    if seconds >= 86400:
        d = int(seconds / 86400)
        seconds -= d * 86400
        text += f"<b>{d} д.</b>"
        if seconds > 0:
            text += " "
        
    if seconds >= 3600:
        h = int(seconds / 3600)
        seconds -= h * 3600
        text += f"<b>{h} ч.</b>"
        if seconds > 0:
            text += " "
        
    if seconds >= 60:
        m = int(seconds / 60)
        seconds -= m * 60
        text += f"<b>{m} м.</b>"
    
    return text

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
            
        reminder_times_text += seconds_to_text(t.total_seconds())
        
    return reminder_times_text

LOCALE_LOCK = threading.Lock()

@contextmanager
def time_locale(name: str):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_TIME)
        try:
            yield locale.setlocale(locale.LC_TIME, name)
        finally:
            locale.setlocale(locale.LC_TIME, saved)
            
            
async def schedule_reminder(until: datetime):
    pass

def tz_now() -> datetime:
    return datetime.now(tz=DEFAULT_TIMEZONE)