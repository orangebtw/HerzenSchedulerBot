import asyncio
from aiogram import Router, Bot, Dispatcher
from aiogram_dialog import setup_dialogs

from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from datetime import datetime
import logging

from handlers import base_handler, register_handler, configure_user_handler, configure_reminders_handler, reminder_creation_handler

import utils
import database
import constants
import models

logger = logging.getLogger(__name__)

bot = Bot(token=constants.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def update_groups_and_clear_schedules(time: str, groups_database: database.GroupsDatabase, schedules_database: database.SchedulesDatabase):
    while True:
        groups_database.fetch_groups()
        schedules_database.clear_subjects()
        logging.info("Fetched schedules")
        await asyncio.sleep(utils.seconds_before_time(time))

async def notify_of_reminders(notes_database: database.NotesDatabase, users_database: database.UsersDatabase):
    while True:
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
                logger.error(f"Failed to check for reminders: user {note.user_id} not found")
                continue
            
            if note.reminded_times >= sum((True for t in user.reminder_times if t is not None)):
                note.is_completed = True
            else:
                reminder_time = user.reminder_times[note.reminded_times]
                if now >= note.due_date - reminder_time.value:
                    remaining_text = utils.seconds_to_text((note.due_date - now).total_seconds())
                    try:
                        await bot.send_message(note.user_id, text=f"📣 <b>Напоминание о дедлайне</b>\n\nОсталось {remaining_text}, чтобы сдать задание по дисциплине \"{note.subject_id}\": \"{note.text}\".")
                        note.reminded_times += 1
                        logger.info(f"Sent {note.reminded_times} reminder to user {note.user_id}")
                    except:
                        pass
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
    
    registration_router = Router()
    configure_user_router = Router()
    configure_reminders_router = Router()
    reminder_creation_router = Router()
    base_router = Router()
    
    register_handler.register(registration_router)
    configure_user_handler.register(configure_user_router)
    configure_reminders_handler.register(configure_reminders_router)
    base_handler.register(base_router)
    reminder_creation_handler.register(reminder_creation_router)
    
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
    dp.include_router(reminder_creation_router)
    
    setup_dialogs(dp)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
