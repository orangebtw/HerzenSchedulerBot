import asyncio
from aiogram import Router, Bot, Dispatcher

from handlers import base_handler, register_handler, configure_user_handler, configure_reminders_handler

import utils
import database
import constants

bot = Bot(token=constants.BOT_TOKEN)
dp = Dispatcher()

async def update_groups_and_clear_schedules(time: str):
    global SCHEDULES
    while True:
        database.update_groups()
        database.clear_subjects()
        await asyncio.sleep(utils.seconds_before_time(time))

async def on_startup():
    await bot.delete_webhook(drop_pending_updates=True)
    
    loop = asyncio.get_event_loop()
    loop.create_task(update_groups_and_clear_schedules('00:00'))
    
async def main():
    registration_router = Router()
    configure_user_router = Router()
    configure_reminders_router = Router()
    base_router = Router()
    
    register_handler.register(registration_router)
    configure_user_handler.register(configure_user_router)
    configure_reminders_handler.register(configure_reminders_router)
    base_handler.register(base_router)
    
    dp.startup.register(on_startup)
    dp.include_router(registration_router)
    dp.include_router(configure_user_router)
    dp.include_router(configure_reminders_router)
    dp.include_router(base_router)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
