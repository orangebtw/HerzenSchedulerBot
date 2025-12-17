from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime

type UserId = int

@dataclass(frozen=True)
class UserGroup:
    id: str
    name: str

@dataclass
class User:
    id: UserId
    group: UserGroup
    subgroup: int
    
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
