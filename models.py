from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from datetime import timedelta
import uuid

type UserId = int

@dataclass(frozen=True)
class UserGroupWithName:
    name: str
    id: str
    subgroup: int | None = None

@dataclass(frozen=True)
class UserGroup:
    id: str
    subgroup: int | None = None

@dataclass(frozen=True)
class UserReminderTime:
    value: timedelta

@dataclass
class User:
    id: UserId
    group: UserGroupWithName
    reminder_times: tuple[UserReminderTime, Optional[UserReminderTime], Optional[UserReminderTime]] = field(default=(UserReminderTime(timedelta(hours=24)), UserReminderTime(timedelta(hours=3)), None))
    
    def __hash__(self):
        return hash(self.id)
    
@dataclass
class UserNote:
    user_id: UserId
    subject_id: str
    text: str
    due_date: datetime
    done: bool = field(default=False, init=False)
    id: int = field(default=None)
    
    def __hash__(self):
        return hash(self.id)
