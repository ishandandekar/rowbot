from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from frontend.models import Message, Role


PROMPT_PLACEHOLDER = "Type a message... Enter to send"


class TranscriptView(VerticalScroll):
    """Scrollable chat transcript with markdown rendering."""

    def compose(self) -> ComposeResult:
        yield Static("", id="transcript-content")

    def render_messages(
        self,
        messages: list[Message],
        streaming: bool = False,
        thinking: str = "",
        response: str = "",
    ) -> None:
        content_widget = self.query_one("#transcript-content", Static)

        lines: list[str] = []
        for msg in messages:
            if msg.role == Role.USER:
                lines.append(f"[bold blue]You:[/bold blue]\n{msg.content}")
            elif msg.role == Role.ASSISTANT:
                lines.append(f"[bold green]Assistant:[/bold green]\n{msg.content}")
            lines.append("")

        if streaming:
            if thinking:
                lines.append(f"[dim italic]● thinking: {thinking}[/dim italic]")
                lines.append("")
            if response:
                lines.append(f"[bold green]Assistant:[/bold green]\n{response}")
                lines.append("")
            elif not thinking:
                lines.append("[dim]● thinking...[/dim]")
                lines.append("")

        content_widget.update("\n".join(lines))
        self.scroll_end(animate=False)

    def clear(self) -> None:
        self.query_one("#transcript-content", Static).update("")


class PromptInput(Input):
    """Single-line prompt input. Submit handled by app via @on(Input.Submitted)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(placeholder=PROMPT_PLACEHOLDER, **kwargs)
