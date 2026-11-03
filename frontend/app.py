from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static

from frontend.backend_client import BackendClient
from frontend.state import TuiState
from frontend.widgets import PromptInput, TranscriptView
from shared.models import DEFAULT_BACKEND_URL, StreamEventType


class RowbotTuiApp(App):
    """Textual TUI app for Rowbot chat frontend."""

    TITLE = "Rowbot"
    SUB_TITLE = "Chat with your AI assistant"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
    ]

    CSS = """
    #workspace {
        height: 1fr;
    }

    #transcript {
        height: 1fr;
        border: solid $primary;
        margin: 1 1 0 1;
    }

    #prompt-area {
        height: auto;
        margin: 0 1 1 1;
    }

    #prompt-input {
        width: 1fr;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
    }
    """

    def __init__(self, backend_url: str = DEFAULT_BACKEND_URL) -> None:
        super().__init__()
        self.state = TuiState()
        self.backend = BackendClient(base_url=backend_url)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"), Vertical(id="main-pane"):
            yield TranscriptView(id="transcript")
            with Horizontal(id="prompt-area"):
                yield PromptInput(id="prompt-input")
        yield Static("Ready", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        prompt = self.query_one("#prompt-input", PromptInput)
        prompt.focus()
        self._update_transcript()
        self._update_status("Ready")

    @on(Input.Submitted, "#prompt-input")
    async def action_submit_prompt(self) -> None:
        prompt = self.query_one("#prompt-input", PromptInput)
        message = prompt.value.strip()
        if not message:
            return

        prompt.value = ""
        self.state.add_user_message(message)
        self.state.start_streaming()
        self._update_transcript()
        self._update_status("Thinking...")

        await self._stream_response(message)

    async def _stream_response(self, message: str) -> None:
        try:
            async for event in self.backend.stream_chat(message):
                match event.type:
                    case StreamEventType.MESSAGE_START:
                        self.state.current_response = ""
                        self.state.current_thinking = ""
                    case StreamEventType.THINKING_DELTA:
                        self.state.append_thinking_token(event.thinking_content)
                    case StreamEventType.TEXT_DELTA:
                        self.state.append_streaming_token(event.content_delta)
                    case StreamEventType.MESSAGE_END:
                        self.state.finish_streaming()
                        self._update_transcript()
                        self._update_status("Ready")
                        return
                    case StreamEventType.ERROR:
                        self.state.finish_streaming()
                        self._update_transcript()
                        self._update_status(f"Error: {event.error}")
                        return
                self._update_transcript()
        except Exception as e:
            self.state.finish_streaming()
            self._update_transcript()
            self._update_status(f"Connection error: {e}")

    def action_clear(self) -> None:
        self.state.clear()
        self.query_one("#transcript", TranscriptView).clear()
        self._update_status("Cleared")

    def _update_transcript(self) -> None:
        transcript = self.query_one("#transcript", TranscriptView)
        transcript.render_messages(
            self.state.messages,
            self.state.is_streaming,
            self.state.current_thinking,
            self.state.current_response,
        )

    def _update_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)


async def run_tui_app(
    *,
    backend_url: str = DEFAULT_BACKEND_URL,
) -> None:
    """Run the Textual TUI app (TAU-style entry point)."""
    app = RowbotTuiApp(backend_url=backend_url)
    await app.run_async()
