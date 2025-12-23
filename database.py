import parse
import threading
import models
import sqlite3
from datetime import timedelta, datetime, date

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
    def get_subjects(self, group: models.UserGroup, date_from: date | None = None, date_to: date | None = None) -> Generator[list[parse.ScheduleSubject] | None]:
        self.lock.acquire()
        try:
            if group not in self.schedules:
                self.schedules[group] = parse.parse_schedule(group.id, group.subgroup, date_from, date_to)
            yield self.schedules[group]
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
        
    def row_to_user(row: tuple) -> models.User:
        reminder1 = models.UserReminderTime(timedelta(seconds=row[4]))
        reminder2 = models.UserReminderTime(timedelta(seconds=row[5])) if row[5] is not None else None
        reminder3 = models.UserReminderTime(timedelta(seconds=row[6])) if row[6] is not None else None
        return models.User(id=row[0], group=models.UserGroupWithName(name=row[1], id=row[2], subgroup=row[3]), reminder_times=(reminder1, reminder2, reminder3))
        
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
            
        return UsersDatabase.row_to_user(row)
    
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
    DATABASE_NAME = "Notes"
    
    def __init__(self):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(constants.NOTES_DATABASE_PATH)
        self.cur = self.db.cursor()
        
        self.cur.execute(f"""CREATE TABLE IF NOT EXISTS {NotesDatabase.DATABASE_NAME} (
            id INTEGER PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            subject_id TEXT,
            content TEXT NOT NULL,
            due_date TIMESTAMP NOT NULL,
            reminded_times INTEGER NOT NULL DEFAULT 0,
            is_completed BOOLEAN NOT NULL DEFAULT 0
        )""")
        
        self.db.commit()
        
    def row_to_note(row) -> models.UserNote:
        return models.UserNote(id=row[0], user_id=row[1], subject_id=row[2], text=row[3], due_date=datetime.fromtimestamp(row[4], tz=utils.DEFAULT_TIMEZONE), reminded_times=row[5], is_completed=row[6])
    
    def insert_note(self, note: models.UserNote):
        with self.lock:
            self.cur.execute(f"INSERT OR REPLACE INTO {NotesDatabase.DATABASE_NAME} (user_id, subject_id, content, due_date) VALUES (?, ?, ?, ?)",
                             (note.user_id, note.subject_id, note.text, int(note.due_date.timestamp())))
            self.db.commit()
            
    def update_note(self, note: models.UserNote):
        with self.lock:
            self.cur.execute(f"UPDATE {NotesDatabase.DATABASE_NAME} SET subject_id = ?, content = ?, due_date = ?, reminded_times = ?, is_completed = ? WHERE id = ?",
                             (note.subject_id, note.text, int(note.due_date.timestamp()), note.reminded_times, note.is_completed, note.id))
            self.db.commit()
            
    def delete_note_by_id(self, note_id: models.UserId):
        with self.lock:
            self.cur.execute(f"DELETE FROM {NotesDatabase.DATABASE_NAME} WHERE id = ?", (note_id,))
            self.db.commit()

    def delete_all_by_user_id(self, user_id: models.UserId):
        with self.lock:
            self.cur.execute(f"DELETE FROM {NotesDatabase.DATABASE_NAME} WHERE user_id = ?", (user_id,))
            self.db.commit()

    def get_note_by_id(self, note_id: int) -> Optional[models.UserNote]:
        with self.lock:
            self.cur.execute(f"SELECT * FROM {NotesDatabase.DATABASE_NAME} WHERE id = ?", (note_id,))
            row = self.cur.fetchone()
            
        if row is None:
            return None
        
        return NotesDatabase.row_to_note(row)

    def get_notes_by_user_id(self, user_id: models.UserId) -> tuple[int, Iterable[models.UserNote]]:
        with self.lock:
            self.cur.execute(f"SELECT * FROM {NotesDatabase.DATABASE_NAME} WHERE user_id = ?", (user_id,))
            rows = self.cur.fetchall() 
        return len(rows), map(NotesDatabase.row_to_note, rows)
        
    def get_current_notes_by_user_id(self, user_id: models.UserId):
        with self.lock:
            self.cur.execute(f"SELECT * FROM {NotesDatabase.DATABASE_NAME} WHERE user_id = ? AND is_completed IS FALSE", (user_id,))
            rows = self.cur.fetchall() 
        return len(rows), map(NotesDatabase.row_to_note, rows)
        
    def get_current_notes(self):
        with self.lock:
            self.cur.execute(f"SELECT * FROM {NotesDatabase.DATABASE_NAME} WHERE is_completed IS FALSE")
            rows = self.cur.fetchall() 
        return len(rows), map(NotesDatabase.row_to_note, rows)
            
    def update_note_completed(self, note_id: int, is_completed: bool):
        with self.lock:
            self.cur.execute(f"UPDATE {NotesDatabase.DATABASE_NAME} SET is_completed = ? WHERE id = ?", (is_completed, note_id))
            self.db.commit()
    
    def update_note_text(self, note_id: int, new_text: str):
        with self.lock:
            self.cur.execute(f"UPDATE {NotesDatabase.DATABASE_NAME} SET content = ? WHERE id = ?", (new_text, note_id))
            self.db.commit()
        
    def update_note_due_date(self, note_id: int, new_due_date: datetime):
        with self.lock:
            self.cur.execute(f"UPDATE {NotesDatabase.DATABASE_NAME} SET due_date = ? WHERE id = ?", (int(new_due_date.timestamp()), note_id))
            self.db.commit()
        
    def close(self):
        with self.lock:
            self.db.commit()
            self.db.close()
