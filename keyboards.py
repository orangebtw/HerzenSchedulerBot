from aiogram import types

CONFIGURE_GROUP_BUTTON = types.KeyboardButton(text="Настроить группу")
CANCEL_BUTTON = types.InlineKeyboardButton(text="Отмена", callback_data='cancel')

START_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[CONFIGURE_GROUP_BUTTON]], resize_keyboard=True)

SETTINGS_BUTTON = types.KeyboardButton(text="⚙️ Настройки")

MAIN_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[SETTINGS_BUTTON]], resize_keyboard=True)