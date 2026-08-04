from dataclasses import dataclass, field

from frontend.models import Message, Role


@dataclass
class TuiState:
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    current_response: str = ""
    current_thinking: str = ""

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role=Role.USER, content=content))

    def start_streaming(self) -> None:
        self.is_streaming = True
        self.current_response = ""
        self.current_thinking = ""

    def append_streaming_token(self, token: str) -> None:
        self.current_response += token

    def append_thinking_token(self, token: str) -> None:
        self.current_thinking += token

    def finish_streaming(self) -> None:
        if self.current_response:
            self.messages.append(
                Message(role=Role.ASSISTANT, content=self.current_response)
            )
        self.is_streaming = False
        self.current_response = ""
        self.current_thinking = ""

    def clear(self) -> None:
        self.messages.clear()
        self.is_streaming = False
        self.current_response = ""
        self.current_thinking = ""
