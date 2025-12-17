import asyncio
from aiogram import Router, Bot, Dispatcher

from handlers import configure_handler, base_handler

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
    user_data_router = Router()
    configure_handler.register(dp, user_data_router)
    base_handler.register(dp)
    
    dp.startup.register(on_startup)
    dp.include_router(user_data_router)
    
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    asyncio.run(main())
