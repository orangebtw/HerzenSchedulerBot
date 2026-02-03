import asyncio
from aiogram import Router, Bot, Dispatcher
from aiogram_dialog import setup_dialogs

from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram import types

from datetime import datetime
import logging
import dotenv
import os

from handlers import base_handler, register_handler, configure_user_handler, \
                        configure_reminders_handler, reminder_creation_handler, \
                        reminder_edit_handler

import utils
import database
import models
import callbacks

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def update_groups_and_clear_schedules(time: str, groups_database: database.GroupsDatabase, schedules_database: database.SchedulesDatabase):
    while True:
        logger.info("Fetching groups and schedules...")
        groups_database.fetch_groups()
        schedules_database.clear_subjects()
        logging.info("Successfully fetched groups and schedules")
        await asyncio.sleep(utils.seconds_before_time(time))

async def send_notification(note: models.UserNote, now: datetime):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Отметить как «Выполненное»", callback_data=callbacks.NotificationCompleteCallback(note_id=note.id).pack())]], resize_keyboard=True)
    
    remaining_text = utils.seconds_to_text((note.due_date - now).total_seconds())
    
    if note.subject_id is not None:
        await bot.send_message(note.user_id, text=f"📣 <b>Напоминание о дедлайне</b>\n\nПредмет: <b>{note.subject_id}</b>\nЗадание: \"{note.text}\"\n\nДо дедлайна осталось: <b>{remaining_text}</b>.", reply_markup=keyboard)
    else:
        with utils.time_locale('ru_RU.UTF-8'):
            date_text: str = note.due_date.strftime("%d %b %Y")
        await bot.send_message(note.user_id, text=f"📣 <b>Напоминание о дедлайне</b>\n\nЧерез <b>{remaining_text}</b> истечёт дедлайн по личной заметки:\n\"{note.text}\" к <b>{date_text}</b>.", reply_markup=keyboard)

async def notify_of_reminders(notes_database: database.NotesDatabase, users_database: database.UsersDatabase):
    while True:
        logger.info("Checking reminders to notify...")
        now = datetime.now(tz=utils.DEFAULT_TIMEZONE)
        cache_users: dict[models.UserId, models.User] = {}
        
        _, notes = notes_database.get_current_notes()
        for note in notes:
            if now >= note.due_date:
                note.is_completed = True
                notes_database.update_note(note)
                continue
            
            if note.user_id not in cache_users:
                cache_users[note.user_id] = users_database.get_user_by_id(note.user_id)
                
            user = cache_users[note.user_id]
            
            if user is None:
                logger.error(f"Failed to check for reminders: user '{note.user_id}' not found")
                continue
            
            if note.reminded_times >= sum((True for t in user.reminder_times if t is not None)):
                note.is_completed = True
            else:
                reminder_time = user.reminder_times[note.reminded_times]
                if now >= note.due_date - reminder_time.value:
                    try:
                        await send_notification(note, now)
                        note.reminded_times += 1
                        logger.info(f"Sent {note.reminded_times} reminder to user '{note.user_id}'")
                    except Exception as e:
                        logger.error(f"Failed to send {note.reminded_times} reminder to user '{note.user_id}': {e}")
                    await asyncio.sleep(0.5)
            
            notes_database.update_note(note)

        await asyncio.sleep(30)

async def on_startup(groups_database: database.GroupsDatabase, schedules_database: database.SchedulesDatabase, users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    await bot.delete_webhook(drop_pending_updates=True)
    
    loop = asyncio.get_event_loop()
    loop.create_task(update_groups_and_clear_schedules('00:00', groups_database=groups_database, schedules_database=schedules_database))
    loop.create_task(notify_of_reminders(users_database=users_database, notes_database=notes_database))
    
async def on_shutdown(users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    users_database.close()
    notes_database.close()
    
async def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    
    if not os.path.exists('./databases/'):
        os.mkdir('./databases/')
    
    registration_router = Router()
    configure_user_router = Router()
    configure_reminders_router = Router()
    reminder_creation_router = Router()
    reminder_edit_router = Router()
    base_router = Router()
    
    register_handler.register(registration_router)
    configure_user_handler.register(configure_user_router)
    configure_reminders_handler.register(configure_reminders_router)
    base_handler.register(base_router)
    reminder_creation_handler.register(reminder_creation_router)
    reminder_edit_handler.register(reminder_edit_router)
    
    dp = Dispatcher(
        groups_database=database.GroupsDatabase(),
        schedules_database=database.SchedulesDatabase(),
        users_database=database.UsersDatabase(),
        notes_database=database.NotesDatabase()
    )
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.include_router(registration_router)
    dp.include_router(configure_user_router)
    dp.include_router(configure_reminders_router)
    dp.include_router(base_router)
    dp.include_router(reminder_edit_router)
    dp.include_router(reminder_creation_router)
    
    setup_dialogs(dp)
    
    commands = [
        types.BotCommand(command="start", description="Пройти регистрацию"),
        types.BotCommand(command="menu", description="Меню"),
    ]
    await bot.set_my_commands(commands)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
