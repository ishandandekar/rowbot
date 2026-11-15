from rich.text import Text
from pydantic_ai_harness.compaction import ContextUsageMeasuredEvent
from pydantic_ai_harness.subagents import (
    DelegationStartedEvent,
    DelegationFinishedEvent,
)
from pydantic_ai_harness.planning import (
    PlanCreatedEvent,
    PlanUpdatedEvent,
    PlanStatusChangedEvent,
    PlanCompletedEvent,
    PlanDeletedEvent,
)
import asyncio
from itertools import count
from typing import ClassVar

import logfire
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
    AgentRunResultEvent,
)
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, Label

from textual.theme import Theme
from src.agent import agent as _agent
from src.tui_elements import ToolWidget, TaskWidget

BOX_COUNTER = count(start=1)
tools_to_not_show = [
    "write_plan",
    "read_plan",
    "add_task",
    "update_task_status",
    "update_task_statuses",
    "remove_task",
    "create_agent",
    "delegate_task",
]


catppuccin_mocha = Theme(
    name="catppuccin-mocha",
    primary="#89B4FA",  # Blue
    secondary="#B4BEFE",  # Lavender
    accent="#CBA6F7",  # Mauve
    foreground="#CDD6F4",  # Text
    background="#11111b",  # Base
    success="#A6E3A1",  # Green
    warning="#F9E2AF",  # Yellow
    error="#F38BA8",  # Red
    surface="#313244",  # Surface 0
    panel="#45475A",  # Surface 1
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#89B4FA",
        "input-selection-background": "#B4BEFE 35%",
    },
)


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
    }

    #plan-container {
        width: 100%;
        height: auto;
    }

    #plan-container TaskWidget {
        width: 1fr;
        height: auto;
    }

    #input-row {
        width: 1fr;
        height: auto;
    }
    #context-length {
        width: 1fr;
        height: auto;
        color: #f9e2af;
        padding-left: 2;
    }

    #message_input {
        width: 100%;
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
        margin: 0 0;
        padding: 1 3;
    }

    .bubble.user {
        border: round #cba6f7;
        color: #cba6f7;
    }

    .bubble.ai {
        color: #94e2d5;    
        text-style: bold;
    }
    .bubble.thinking {
        color: #eff1f5;
        text-style: italic;
    }

    .bubble MarkdownBlock {
        width: auto;
        max-width: 100%;
    }
    """

    def on_mount(self):
        self._task_widget: TaskWidget | None = None
        self.register_theme(catppuccin_mocha)
        self.theme = "catppuccin-mocha"

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="conversation")
        with Vertical(id="input-box"):
            yield Horizontal(id="plan-container")
            yield Label(id="context-length")
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="Enter your message...", id="message_input"
                ).focus()
        yield Footer()

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

        plan_container = self.query_one("#plan-container", Horizontal)
        context_label_container = self.query_one("#context-length", Label)

        if self._task_widget is not None:
            self._task_widget.remove()
        self._task_widget = None

        conversation.anchor()

        blocks: dict[int, Markdown] = {}
        tool_registry: dict[str, ToolWidget] = {}
        async with _agent.run_stream_events(user_prompt=user_message) as events:
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
                        str(part.content) if part.content is not None else "",
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
                    if part.tool_name in tools_to_not_show:
                        continue
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
                if isinstance(event, PlanCreatedEvent):
                    if self._task_widget is None or self._task_widget.parent is None:
                        self._task_widget = TaskWidget()
                        await plan_container.mount(self._task_widget)
                    self._task_widget.create_plan_item(event.item)
                if (
                    isinstance(event, PlanUpdatedEvent)
                    and self._task_widget is not None
                ):
                    self._task_widget.update_plan_item(event.item)
                if (
                    isinstance(event, PlanStatusChangedEvent)
                    and self._task_widget is not None
                ):
                    self._task_widget.update_plan_item(event.item)
                if (
                    isinstance(event, PlanCompletedEvent)
                    and self._task_widget is not None
                ):
                    self._task_widget.complete_plan_item(event.item)
                if (
                    isinstance(event, PlanDeletedEvent)
                    and self._task_widget is not None
                ):
                    self._task_widget.delete_plan_item(event.item.id)
                if (
                    isinstance(event, DelegationStartedEvent)
                    and event.tool_call_id is not None
                ):
                    if self._task_widget is None or self._task_widget.parent is None:
                        self._task_widget = TaskWidget()
                        await plan_container.mount(self._task_widget)
                    self._task_widget.create_subagent_task(
                        task_id=event.tool_call_id,
                        task_description=event.task,
                        subagent_name=event.agent_name,
                    )
                if (
                    isinstance(event, DelegationFinishedEvent)
                    and event.tool_call_id is not None
                    and self._task_widget is not None
                ):
                    self._task_widget.complete_subagent_task(task_id=event.tool_call_id)
                if isinstance(event, ContextUsageMeasuredEvent):
                    context_label_container.update(
                        Text(
                            "Context: " + str(round(event.fraction * 100, 2)) + " %",
                            style="bold italic",
                        )
                    )
                if isinstance(event, AgentRunResultEvent):
                    all_messages = event.result.all_messages()

        conversation.anchor()
        message_input.focus()
        await asyncio.to_thread(logfire.force_flush)


def run_tui_app() -> None:
    """Run the Rowbot TUI app."""
    RowbotTuiApp().run()


if __name__ == "__main__":
    run_tui_app()
