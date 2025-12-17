from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime

type UserId = int

@dataclass
class User:
    id: UserId
    group_id: str
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
