from dataclasses import dataclass
from enum import Enum, auto


class Role(Enum):
    USER = auto()
    ASSISTANT = auto()


@dataclass
class Message:
    role: Role
    content: str
