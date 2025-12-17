import asyncio
from aiogram import Router, Bot, Dispatcher

from handlers import base_handler, register_handler, settings_handler

import utils
import database
import constants

bot = Bot(token=constants.BOT_TOKEN)
dp = Dispatcher()

async def update_groups(time: str):
    global SCHEDULES
    while True:
        database.update_groups()
        await asyncio.sleep(utils.seconds_before_time(time))

async def on_startup():
    loop = asyncio.get_event_loop()
    loop.create_task(update_groups('00:00'))
    
async def main():
    registration_router = Router()
    settings_router = Router()
    
    register_handler.register(dp, registration_router)
    settings_handler.register(settings_router)
    base_handler.register(dp)
    
    dp.startup.register(on_startup)
    dp.include_router(registration_router)
    dp.include_router(settings_router)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
