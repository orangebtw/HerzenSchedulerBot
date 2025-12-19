from aiogram import types

import database

async def check_user_exists(message: types.Message, users_database: database.UsersDatabase) -> bool:
    assert(message.from_user is not None)
    
    if not users_database.user_exists(message.from_user.id):
        await message.answer("Я тебя не знаю. Пожалуйста, напиши /start и пройди регистрацию.")
        return False
    return True