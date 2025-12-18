from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime
from datetime import timedelta

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
    id: UUID = field(default_factory=UUID, init=False)
    user_id: UserId
    subject_id: str
    text: str
    time: datetime
    
    def __hash__(self):
        return hash(self.id)
