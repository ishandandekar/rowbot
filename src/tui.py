import asyncio
from itertools import count
from typing import ClassVar

import logfire
import rich.spinner
from pydantic_ai import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
)
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Markdown, Static

from src.agent import agent

BOX_COUNTER = count(start=1)


class ToolWidget(Static):
    def __init__(self, text: str = "Running..."):
        self._spinner = rich.spinner.Spinner("dots", text=text)
        panel = Panel(
            self._spinner,
            title="tool",
            border_style="#f9e2af",
        )
        super().__init__(panel)

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 10, self.refresh)

    def finish(self, panel: Panel) -> None:
        self._timer.stop()  # kills the 10 Hz repaint forever
        self.update(panel)


class RowbotTuiApp(App):
    """Textual TUI app for Rowbot chat frontend."""

    TITLE = "Rowbot"
    SUB_TITLE = "chat with Excel with ease"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("escape", "interrupt", "Interrupt", show=True),
    ]

    CSS = """
    #input-box {
        dock: bottom;
        height: auto;
        width: 100%;
        margin: 0 0 2 0;
        align-horizontal: center;
    }

    #message_input {
        width: 80%;
    }

    #send_button {
        width: 20%;
        color: #11111b;
        background: #fab387;
        border: blank;
    }

    .message-row {
        width: 100%;
        height: auto;
        text-wrap: wrap;
    }

    .message-row.user {
        align-horizontal: right;
    }

    .message-row.ai {
        align-horizontal: left;
    }
    .message-row.thinking {
        align-horizontal: left;
    }

    .bubble {
        width: auto;
        max-width: 75%;
        height: auto;
        margin: 1 0;
        padding: 1 3;
    }

    .bubble.user {
        border: round #cba6f7;
        color: #cba6f7;
    }

    .bubble.ai {
        color: #94e2d5;
    }
    .bubble.thinking {
        color: #eff1f5;
    }

    .bubble MarkdownBlock {
        width: auto;
        max-width: 100%;
    }
    """

    def compose(self) -> ComposeResult:

        yield Header()
        yield VerticalScroll(id="conversation")
        with Horizontal(id="input-box"):
            yield Input(placeholder="Enter your message...", id="message_input").focus()
            yield Button(label="Send", variant="success", id="send_button")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send_button":
            await self.process_conversation()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message_input":
            await self.process_conversation()

    async def process_conversation(self) -> None:
        message_input = self.query_one("#message_input", Input)
        user_message = message_input.value.strip()
        if not user_message:
            return

        message_input.value = ""

        conversation = self.query_one("#conversation", VerticalScroll)
        await conversation.mount(
            Horizontal(
                Markdown(user_message, classes="bubble user"),
                classes="message-row user",
            )
        )

        conversation.anchor()
        # tool = Static("get_execl()")
        # await conversation.mount(tool)
        # tool.loading = True
        #
        # await asyncio.sleep(6)
        # tool.loading = False

        blocks: dict[int, Markdown] = {}
        tool_registry: dict[str, ToolWidget] = {}
        async with agent.run_stream_events(user_prompt=user_message) as events:
            async for event in events:
                if isinstance(event, PartStartEvent):
                    part = event.part
                    if not isinstance(part, (ThinkingPart, TextPart)):
                        continue
                    if isinstance(part, ThinkingPart):
                        classes, prefix = "bubble thinking", "thinking"
                    if isinstance(part, TextPart):
                        classes, prefix = "bubble ai", "ai"

                    block = Markdown(
                        str(part.content) if part.content is not None else "",  # ty:ignore[unresolved-attribute]
                        classes=classes,
                        id=prefix + "_" + str(next(BOX_COUNTER)),
                    )
                    await conversation.mount(
                        Horizontal(block, classes="message-row ai")
                    )
                    blocks[event.index] = block
                if isinstance(event, PartDeltaEvent):
                    delta = event.delta
                    if isinstance(delta, ThinkingPartDelta) or isinstance(
                        delta, TextPartDelta
                    ):
                        text = delta.content_delta
                    else:
                        continue
                    if text and (block := blocks.get(event.index)):
                        await block.append(text)
                if isinstance(event, PartEndEvent):
                    blocks.pop(event.index, None)

                if isinstance(event, FunctionToolCallEvent):
                    part = event.part
                    if isinstance(part, ToolCallPart):
                        block = ToolWidget(f"{part.tool_name}({part.args_as_dict()})")
                        await conversation.mount(block)
                        tool_registry[part.tool_call_id] = block
                if isinstance(event, FunctionToolResultEvent):
                    part = event.part
                    if isinstance(part, ToolReturnPart) and (
                        block := tool_registry.get(part.tool_call_id)
                    ):
                        block.finish(
                            Panel(
                                f"[green]✓[/green] [yellow]{part.tool_name} => "
                                f"{part.content if len(str(part.content)) < 20 else str(part.content)[:17] + '...'}",
                                title="tool",
                                border_style="#a6e3a1",
                            )
                        )

        conversation.anchor()
        message_input.focus()
        await asyncio.to_thread(logfire.force_flush)


def run_tui_app() -> None:
    """Run the Rowbot TUI app."""
    RowbotTuiApp().run()


if __name__ == "__main__":
    run_tui_app()
