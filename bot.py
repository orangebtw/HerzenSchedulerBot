import asyncio
from aiogram import Router, Bot, Dispatcher
from aiogram_dialog import setup_dialogs

from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

from handlers import base_handler, register_handler, configure_user_handler, configure_reminders_handler, reminder_creation_handler

import utils
import database
import constants

bot = Bot(token=constants.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def update_groups_and_clear_schedules(time: str, groups_database: database.GroupsDatabase, schedules_database: database.SchedulesDatabase):
    while True:
        groups_database.fetch_groups()
        schedules_database.clear_subjects()
        await asyncio.sleep(utils.seconds_before_time(time))

async def on_startup(groups_database: database.GroupsDatabase, schedules_database: database.SchedulesDatabase):
    await bot.delete_webhook(drop_pending_updates=True)
    
    loop = asyncio.get_event_loop()
    loop.create_task(update_groups_and_clear_schedules('00:00', groups_database=groups_database, schedules_database=schedules_database))
    
async def on_shutdown(users_database: database.UsersDatabase, notes_database: database.NotesDatabase):
    users_database.close()
    notes_database.close()
    
async def main():
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
