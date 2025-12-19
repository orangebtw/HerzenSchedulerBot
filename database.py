import parse
import threading
import models
import sqlite3
from datetime import timedelta, datetime

from typing import Iterable, Optional, Generator

from contextlib import contextmanager

import constants
import utils

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
    def get_subjects(self, group_id: str, subgroup: int | None = None) -> Generator[list[parse.ScheduleSubject] | None]:
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
        self.lock = threading.Lock()
        self.db = sqlite3.connect(constants.USERS_DATABASE_PATH)
        self.cur = self.db.cursor()
        
        self.cur.execute("""CREATE TABLE IF NOT EXISTS Users (
            id INTEGER NOT NULL PRIMARY KEY,
            group_name TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            subgroup INTEGER,
            reminder1 TIMESTAMP NOT NULL,
            reminder2 TIMESTAMP,
            reminder3 TIMESTAMP
        )""")
        
        self.db.commit()
        
    def insert_user(self, user: models.User):
        with self.lock:
            reminder1 = user.reminder_times[0].value.total_seconds()
            reminder2 = user.reminder_times[1].value.total_seconds() if user.reminder_times[1] is not None else None
            reminder3 = user.reminder_times[2].value.total_seconds() if user.reminder_times[2] is not None else None
            
            self.cur.execute("INSERT OR REPLACE INTO Users (id, group_name, group_id, subgroup, reminder1, reminder2, reminder3) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (user.id, user.group.name, user.group.id, user.group.subgroup, reminder1, reminder2, reminder3))
            self.db.commit()
            
    def delete_by_id(self, id: models.UserId):
        with self.lock:
            self.cur.execute("DELETE FROM Users WHERE id = ?", (id,))
            self.db.commit()
    
    def get_user_by_id(self, id: models.UserId) -> Optional[models.User]:
        with self.lock:
            self.cur.execute("SELECT * FROM Users WHERE id = ?", (id,))
            row = self.cur.fetchone()
        
        if row is None:
            return None
            
        reminder1 = models.UserReminderTime(timedelta(seconds=row[4]))
        reminder2 = models.UserReminderTime(timedelta(seconds=row[5])) if row[5] is not None else None
        reminder3 = models.UserReminderTime(timedelta(seconds=row[6])) if row[6] is not None else None
            
        return models.User(id=row[0], group=models.UserGroupWithName(name=row[1], id=row[2], subgroup=row[3]), reminder_times=(reminder1, reminder2, reminder3))
    
    def user_exists(self, user_id: models.UserId) -> bool:
        with self.lock:
            self.cur.execute("SELECT EXISTS(SELECT 1 FROM Users WHERE id = ? LIMIT 1)", (user_id,))
            exists = self.cur.fetchone()[0]
            return bool(exists)
        
    def close(self):
        with self.lock:
            self.db.commit()
            self.db.close()

class NotesDatabase:
    def __init__(self):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(constants.NOTES_DATABASE_PATH)
        self.cur = self.db.cursor()
        
        self.cur.execute("""CREATE TABLE IF NOT EXISTS Notes (
            id INTEGER PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            subject_id TEXT NOT NULL,
            content TEXT NOT NULL,
            due_date TIMESTAMP NOT NULL
        )""")
        
        self.db.commit()
    
    def insert_note(self, note: models.UserNote):
        with self.lock:
            self.cur.execute("INSERT OR REPLACE INTO Notes (user_id, subject_id, content, due_date) VALUES (?, ?, ?, ?)",
                             (note.user_id, note.subject_id, note.text, int(note.due_date.timestamp())))
            self.db.commit()

    def get_notes_by_user_id(self, user_id: models.UserId) -> tuple[int, Iterable[models.UserNote]]:
        with self.lock:
            self.cur.execute("SELECT * FROM Notes WHERE user_id = ?", (user_id,))
            rows = self.cur.fetchall() 
            return len(rows), map(lambda row: models.UserNote(id=row[0], user_id=row[1], subject_id=row[2], text=row[3], due_date=datetime.fromtimestamp(row[4], tz=utils.DEFAULT_TIMEZONE)), rows)
        
    def close(self):
        with self.lock:
            self.db.commit()
            self.db.close()
