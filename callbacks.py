from aiogram.filters.callback_data import CallbackData

class NumCallback(CallbackData, prefix="data-int"):
    num: int
    
class NotificationCompleteCallback(CallbackData, prefix="nt-cmplt"):
    note_id: int
    
class NoteEditCallback(CallbackData, prefix="nt-edit"):
    note_id: int