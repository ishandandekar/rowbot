from textual.widgets.option_list import Option
from textual.fuzzy import Matcher
import httpx
import asyncio
from itertools import count
from pathlib import Path
from typing import ClassVar

import logfire
from pydantic_ai import (
    AgentRunResultEvent,
    ConversationTypeAdapter,
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
    ModelRequest,
    UserPromptPart,
    ModelResponse,
)
from pydantic_ai_harness.compaction import ContextUsageMeasuredEvent
from pydantic_ai_harness.planning import (
    PlanCompletedEvent,
    PlanCreatedEvent,
    PlanDeletedEvent,
    PlanStatusChangedEvent,
    PlanUpdatedEvent,
)
from pydantic_ai_harness.subagents import (
    DelegationFinishedEvent,
    DelegationStartedEvent,
)
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import Footer, Header, Input, Label, Markdown, OptionList

from src.agent import agent as _agent
from src.palette import (
    BASE,
    BLUE,
    CRUST,
    FLAMINGO,
    GREEN,
    LAVENDER,
    MANTLE,
    MAUVE,
    OVERLAY0,
    OVERLAY1,
    OVERLAY2,
    PEACH,
    PINK,
    RED,
    ROSEWATER,
    SAPPHIRE,
    SKY,
    SUBTEXT0,
    SUBTEXT1,
    SURFACE0,
    SURFACE1,
    SURFACE2,
    TEAL,
    TEXT,
    YELLOW,
)
from src.tui_elements import TaskWidget, ToolWidget

BOX_COUNTER = count(start=1)
TOOLS_NOT_TO_SHOW = [
    "write_plan",
    "read_plan",
    "add_task",
    "update_task_status",
    "update_task_statuses",
    "remove_task",
    "create_agent",
    "delegate_task",
]
CONVERSATIONS_DIR = Path.cwd() / "conversations"
CONVERSATIONS_DIR.mkdir(exist_ok=True)
SLASH_COMMANDS = [
    ("/help", "Show available commands"),
    ("/new", "Start a new session"),
    ("/save", "Save current session history"),
    ("/quit", "Quit application"),
]

catppuccin_mocha = Theme(
    name="catppuccin-mocha",
    primary=PINK,
    secondary=MAUVE,
    accent=PEACH,
    foreground=TEXT,
    background=CRUST,
    surface=SURFACE0,
    panel=SURFACE1,
    success=GREEN,
    warning=YELLOW,
    error=RED,
    dark=True,
    variables={
        # Built-in widget variables that the old theme was missing.
        "border": MAUVE,
        "border-blurred": SURFACE2,
        "block-cursor-foreground": BASE,
        "block-cursor-background": PINK,
        "block-cursor-text-style": "none",
        "button-color-foreground": BASE,
        "footer-background": MANTLE,
        "footer-foreground": SUBTEXT1,
        "footer-key-foreground": MAUVE,
        "footer-key-background": "transparent",
        "footer-description-foreground": SUBTEXT0,
        "input-cursor-foreground": BASE,
        "input-cursor-background": ROSEWATER,
        "input-cursor-text-style": "none",
        "input-selection-background": f"{SURFACE2} 70%",
        "scrollbar": SURFACE2,
        "scrollbar-hover": OVERLAY0,
        "scrollbar-active": MAUVE,
        "scrollbar-background": MANTLE,
        "scrollbar-background-hover": SURFACE0,
        "scrollbar-background-active": SURFACE0,
        "scrollbar-corner-color": MANTLE,
        "screen-selection-background": f"{MAUVE} 35%",
        "markdown-h1-color": MAUVE,
        "markdown-h2-color": SKY,
        "markdown-h3-color": TEAL,
        "markdown-h4-color": PEACH,
        # Full Mocha ramp, exposed to styles.tcss as $mo-* variables.
        "mo-rosewater": ROSEWATER,
        "mo-flamingo": FLAMINGO,
        "mo-pink": PINK,
        "mo-mauve": MAUVE,
        "mo-red": RED,
        "mo-peach": PEACH,
        "mo-yellow": YELLOW,
        "mo-green": GREEN,
        "mo-teal": TEAL,
        "mo-sky": SKY,
        "mo-sapphire": SAPPHIRE,
        "mo-blue": BLUE,
        "mo-lavender": LAVENDER,
        "mo-text": TEXT,
        "mo-subtext1": SUBTEXT1,
        "mo-subtext0": SUBTEXT0,
        "mo-overlay2": OVERLAY2,
        "mo-overlay1": OVERLAY1,
        "mo-overlay0": OVERLAY0,
        "mo-surface2": SURFACE2,
        "mo-surface1": SURFACE1,
        "mo-surface0": SURFACE0,
        "mo-base": CRUST,
        "mo-mantle": MANTLE,
        "mo-crust": CRUST,
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

    CSS_PATH = Path.cwd() / "src" / "styles.tcss"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.register_theme(catppuccin_mocha)
        self.theme = "catppuccin-mocha"

    def on_mount(self):
        self._latest_conversation_path = max(
            (p for p in CONVERSATIONS_DIR.glob("*.json") if p.stat().st_size > 0),
            key=lambda p: p.stat().st_mtime,
            default=None,
        )
        if self._latest_conversation_path:
            conversation_data = self._latest_conversation_path.read_bytes()
            self._conversation = ConversationTypeAdapter.validate_json(
                conversation_data
            )
        else:
            self._conversation = None
        self._task_widget: TaskWidget | None = None

        # Warm up the model in the background so the UI starts immediately.
        self._warmup_task = asyncio.create_task(self._warm_up_llm())

        # Adding session history onto UI
        if self._conversation:
            conversation_container = self.query_one("#conversation", VerticalScroll)
            for message in self._conversation.messages:
                if isinstance(message, ModelRequest):
                    for part in message.parts:
                        if isinstance(part, UserPromptPart):
                            conversation_container.mount(
                                Horizontal(
                                    Markdown(
                                        str(part.content) if part.content else "",
                                        classes="bubble user",
                                    ),
                                    classes="message-row user",
                                )
                            )
                elif isinstance(message, ModelResponse):
                    for part in message.parts:
                        if isinstance(part, ThinkingPart):
                            conversation_container.mount(
                                Horizontal(
                                    Markdown(
                                        str(part.content) if part.content else "",
                                        classes="bubble thinking",
                                    ),
                                    classes="message-row ai",
                                )
                            )
                        elif isinstance(part, TextPart):
                            conversation_container.mount(
                                Horizontal(
                                    Markdown(
                                        str(part.content) if part.content else "",
                                        classes="bubble ai",
                                    ),
                                    classes="message-row ai",
                                )
                            )

    async def _warm_up_llm(self) -> None:
        """Warm the local model off the event loop."""
        try:
            await asyncio.to_thread(
                httpx.post,
                url="http://localhost:11434/v1/chat/completions",
                json={
                    "model": "bonsai-2:4b",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "max_tokens": 1,
                },
                timeout=60.0,
            )
        except httpx.HTTPError as error:
            logfire.warning("LLM warm-up failed", error=str(error))

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="conversation")
        with Vertical(id="input-box"):
            yield Horizontal(id="plan-container")
            yield Label(id="context-length")
            yield OptionList(id="commands-popup")
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="Enter your message...", id="message_input"
                ).focus()
        yield Footer()

    async def on_input_changed(self, event: Input.Changed):
        popup = self.query_one("#commands-popup", OptionList)
        text = event.value
        if text.startswith("/") and " " not in text:
            query = text[1:]
            matcher = Matcher(query)
            popup.clear_options()

            matches = []
            for cmd, desc in SLASH_COMMANDS:
                score = matcher.match(cmd[1:]) if query else 1.0
                if score > 0:
                    matches.append((score, cmd, desc))

            matches = sorted(matches, key=lambda match: match[0], reverse=True)
            if matches:
                for _, cmd, desc in matches:
                    popup.add_option(
                        Option(
                            Text.from_markup(f"[b]{cmd}[/b]  [dim]{desc}[/dim]"), id=cmd
                        )
                    )
                popup.highlighted = 0
                popup.add_class("visible")
            else:
                popup.remove_class("visible")
        else:
            popup.remove_class("visible")

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        await self._auto_complete_command(str(event.option.id))

    async def on_key(self, event) -> None:
        popup = self.query_one("#commands-popup", OptionList)
        if not popup.has_class("visible"):
            return
        if event.key == "down":
            popup.action_cursor_down()
            event.prevent_default()
        elif event.key == "up":
            popup.action_cursor_up()
            event.prevent_default()
        elif event.key in ("tab", "enter"):
            if popup.highlighted is not None:
                option_selected = popup.get_option_at_index(popup.highlighted)
                await self._auto_complete_command(str(option_selected.id))
        elif event.key == "escape":
            popup.remove_class("visible")
            event.prevent_default()

    async def _auto_complete_command(self, cmd: str):
        prompt = self.query_one("#message_input", Input)
        popup = self.query_one("#commands-popup", OptionList)
        prompt.value = cmd + " "
        prompt.cursor_position = len(prompt.value)
        popup.remove_class("visible")
        prompt.focus()

    async def _execute_slash_command(self, command: str):
        if command == "/new":
            if self._conversation:
                if self._latest_conversation_path is None:
                    self._latest_conversation_path = (
                        CONVERSATIONS_DIR / f"{self._conversation.conversation_id}.json"
                    )
                conversation_data = ConversationTypeAdapter.dump_json(
                    self._conversation, indent=4, ensure_ascii=True
                )
                self._latest_conversation_path.write_bytes(conversation_data)
            conversation_container = self.query_one("#conversation", VerticalScroll)
            await conversation_container.remove_children()
            self._latest_conversation_path = None
            self._conversation = None

        elif command == "/quit":
            if self._conversation:
                if self._latest_conversation_path is None:
                    self._latest_conversation_path = (
                        CONVERSATIONS_DIR / f"{self._conversation.conversation_id}.json"
                    )
                conversation_data = ConversationTypeAdapter.dump_json(
                    self._conversation, indent=4, ensure_ascii=True
                )
                self._latest_conversation_path.write_bytes(conversation_data)
            await self.action_quit()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "message_input":
            return
        text = event.value.strip()
        if not text:
            return
        self.query_one("#commands-popup", OptionList).remove_class("visible")
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            await self._execute_slash_command(cmd)
            self.query_one("#message_input", Input).clear()
        else:
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
        async with _agent.run_stream_events(
            user_prompt=user_message, conversation=self._conversation
        ) as events:
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
                    if isinstance(delta, (ThinkingPartDelta, TextPartDelta)):
                        text = delta.content_delta
                    else:
                        continue
                    if text and (block := blocks.get(event.index)):
                        await block.append(text)
                if isinstance(event, PartEndEvent):
                    blocks.pop(event.index, None)
                if isinstance(event, FunctionToolCallEvent):
                    part = event.part
                    if part.tool_name in TOOLS_NOT_TO_SHOW:
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
                        preview = str(part.content)
                        if len(preview) >= 20:
                            preview = preview[:17] + "..."
                        block.finish(
                            Panel(
                                Text("✓ ", style=GREEN)
                                + Text(f"{part.tool_name} => ", style=YELLOW)
                                + Text(preview, style=TEXT),
                                title="tool",
                                title_align="left",
                                border_style=GREEN,
                                padding=(0, 1),
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
                            f"Context: {round(event.used_tokens * 100 / event.window_tokens, 2)} %",
                            style=f"bold italic {YELLOW}",
                        )
                    )
                if isinstance(event, AgentRunResultEvent):
                    self._conversation = event.result.conversation
                    if self._latest_conversation_path is None:
                        self._latest_conversation_path = (
                            CONVERSATIONS_DIR
                            / f"{self._conversation.conversation_id}.json"
                        )
                    conversation_data = ConversationTypeAdapter.dump_json(
                        self._conversation, indent=4, ensure_ascii=True
                    )
                    self._latest_conversation_path.write_bytes(conversation_data)
                    await self.action_bell()
                    self.notify("conversation saved", severity="information")

        conversation.anchor()
        message_input.focus()
        await asyncio.to_thread(logfire.force_flush)


def run_tui_app() -> None:
    """Run the Rowbot TUI app."""
    RowbotTuiApp().run()


if __name__ == "__main__":
    run_tui_app()
