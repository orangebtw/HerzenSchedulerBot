import parse
import threading
import models

from typing import Iterable, Optional

SCHEDULES: list[parse.ScheduleFaculty] = []
SCHEDULES_LOCK = threading.Lock()

USERS: set[models.User] = set()
USERS_LOCK = threading.Lock()

NOTES: set[models.UserNote] = set()
NOTES_LOCK = threading.Lock()

def update_groups():
    global SCHEDULES
    with SCHEDULES_LOCK:
        SCHEDULES = parse.parse_groups()

def add_user(user: models.User):
    with USERS_LOCK:
        USERS.add(user)
        
def add_note(note: models.UserNote):
    with NOTES_LOCK:
        NOTES.add(note)

def get_user_by_id(id: models.UserId) -> Optional[models.User]:
    with USERS_LOCK:
        return next((user for user in USERS if user.id == id), None)

def get_notes_by_user_id(user_id: models.UserId) -> Iterable[models.UserNote]:
    with NOTES_LOCK:
        return filter(lambda note: note.user_id == user_id, NOTES)
    
def user_exists(user_id: models.UserId) -> bool:
    with USERS_LOCK:
        return any((True for user in USERS if user.id == user_id))