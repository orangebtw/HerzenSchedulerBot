import parse
import threading
import models

from typing import Iterable, Optional, Generator

from contextlib import contextmanager

class GroupsDatabase:
    def __init__(self):
        self.groups: list[parse.ScheduleFaculty] = []
        self.lock = threading.Lock()
        
    def fetch_groups(self):
        with self.lock:
            self.groups = parse.parse_groups()
        
    @contextmanager    
    def get_groups(self):
        self.lock.acquire()
        try:
            yield self.groups
        finally:
            self.lock.release()
            
class SchedulesDatabase:
    def __init__(self):
        self.schedules: dict[models.UserGroup, list[parse.ScheduleSubject]] = {}
        self.lock = threading.Lock()
        
    def clear_subjects(self):
        with self.lock:
            self.schedules.clear()
        
    @contextmanager    
    def get_subjects(self, group_id: str, subgroup: int | None = None):
        self.lock.acquire()
        try:
            g = models.UserGroup(group_id, subgroup)
            if g not in self.schedules:
                self.schedules[g] = parse.parse_schedule(group_id, subgroup)
            yield self.schedules[g]
        finally:
            self.lock.release()

class UsersDatabase:
    def __init__(self):
        self.users: set[models.User] = set()
        self.lock = threading.Lock()
        
    def add_user(self, user: models.User):
        with self.lock:
            self.users.add(user)
        
    @contextmanager
    def get_user_by_id(self, id: models.UserId) -> Generator[Optional[models.User]]:
        self.lock.acquire()
        try:
            yield next((user for user in self.users if user.id == id), None)
        finally:
            self.lock.release()
    
    def user_exists(self, user_id: models.UserId) -> bool:
        with self.lock:
            return any((True for user in self.users if user.id == user_id))

class NotesDatabase:
    def __init__(self):
        self.notes: set[models.UserNote] = set()
        self.lock = threading.Lock()
    
    def add_note(self, note: models.UserNote):
        with self.lock:
            self.notes.add(note)

    def get_notes_by_user_id(self, user_id: models.UserId) -> Iterable[models.UserNote]:
        with self.lock:
            return filter(lambda note: note.user_id == user_id, self.notes)
