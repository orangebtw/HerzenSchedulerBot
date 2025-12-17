from aiogram.fsm.state import StatesGroup, State

class RegisterUserState(StatesGroup):
    Faculty = State()
    Form = State()
    Stage = State()
    Course = State()
    Group = State()
    SubGroup = State()
    
class MainState(StatesGroup):
    Settings = State()
    
class ConfigureUserState(StatesGroup):
    Faculty = State()
    Form = State()
    Stage = State()
    Course = State()
    Group = State()
    SubGroup = State()