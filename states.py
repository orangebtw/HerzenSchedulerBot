from aiogram.fsm.state import StatesGroup, State

class RegisterUserState(StatesGroup):
    Faculty = State()
    Form = State()
    Stage = State()
    Course = State()
    Group = State()
    SubGroup = State()
    
class MainState(StatesGroup):
    Menu = State()
    Settings = State()
    
class ConfigureUserState(StatesGroup):
    Faculty = State()
    Form = State()
    Stage = State()
    Course = State()
    Group = State()
    SubGroup = State()
    
class ConfigureReminderState(StatesGroup):
    AskTime = State()
    GetTime = State()
    
class NoteCreationState(StatesGroup):
    IsCurrentSubjectCorrect = State()
    NoSubjectCurrently = State()
    AskDueDate = State()
    AskCustomSubject = State()