from dataclasses import dataclass
from enum import Enum, auto


DEFAULT_BACKEND_URL = "http://localhost:8000"


class StreamEventType(Enum):
    MESSAGE_START = auto()
    TEXT_DELTA = auto()
    THINKING_DELTA = auto()
    MESSAGE_END = auto()
    ERROR = auto()


@dataclass
class StreamEvent:
    type: StreamEventType
    content_delta: str = ""
    thinking_content: str = ""
    error: str = ""
    message_id: str = ""
