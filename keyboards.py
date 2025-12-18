from aiogram import types

CONFIGURE_GROUP_BUTTON = types.KeyboardButton(text="Настроить группу")
CANCEL_BUTTON = types.InlineKeyboardButton(text="Отмена", callback_data='cancel')

START_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[CONFIGURE_GROUP_BUTTON]], resize_keyboard=True)

SETTINGS_BUTTON = types.KeyboardButton(text="⚙️ Настройки")

MAIN_KEYBOARD = types.ReplyKeyboardMarkup(keyboard=[[SETTINGS_BUTTON]], resize_keyboard=True)

INLINE_YES_BUTTON = types.InlineKeyboardButton(text="Да", callback_data='yes')
INLINE_NO_BUTTON = types.InlineKeyboardButton(text="Нет", callback_data='no')

INLINE_CREATE_NOTE_BUTTON = types.InlineKeyboardButton(text="🗒️ Создать личную заметку", callback_data='create_note')

YES_OR_NO_KEYBOARD = types.InlineKeyboardMarkup(inline_keyboard=[[INLINE_YES_BUTTON, INLINE_NO_BUTTON]])