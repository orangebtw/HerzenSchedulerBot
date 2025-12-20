from aiogram.filters.callback_data import CallbackData

class NumCallbackData(CallbackData, prefix="data-int"):
    num: int
    
class NotificationCompleteCallbackData(CallbackData, prefix="nt-cmplt"):
    note_id: int