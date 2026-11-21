from pydantic_ai_harness.filesystem import DirectoryListedEvent
from pydantic_ai_harness.ask_user import (
    AskUserAnswer,
    AskUserResponse,
    AskUserRequest,
    check_response,
)
import asyncio
import time
from typing import TypedDict

from pydantic_ai_harness.planning import PlanItem as HarnessPlanItem
from pydantic_ai_harness.planning import TaskStatus
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalGroup, Horizontal
from textual.widgets import (
    Static,
    TabbedContent,
    TabPane,
    Checkbox,
    RadioSet,
    RadioButton,
    Input,
    Button,
)

from src.palette import GREEN, MAUVE, RED, SUBTEXT0, SUBTEXT1, TEAL, YELLOW


class ToolWidget(Static):
    def __init__(self, text: str = "Running..."):
        self._spinner = Spinner("dots", text=text)
        panel = Panel(
            self._spinner,
            title="tool",
            title_align="left",
            border_style=YELLOW,
            padding=(0, 1),
        )
        super().__init__(panel)

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 10, self.refresh)

    def finish(self, panel: Panel) -> None:
        self._timer.stop()  # kills the 10 Hz repaint forever
        self.update(panel)


class PlanItem(TypedDict):
    id: str
    created_at: float
    updated_at: float | None
    completed_at: float | None
    status: TaskStatus
    task: str


class SubagentTask(TypedDict):
    task_id: str
    task_description: str
    subagent_name: str
    started_at: float | int
    ended_at: float | int | None


class TaskWidget(Static):
    def __init__(self):
        self.plan_items: list[PlanItem] = []
        self.subagent_tasks: list[SubagentTask] = []
        self._spinners: dict[str, Spinner] = {}
        self.widget_created_at = time.monotonic()
        super().__init__()

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 15, self._refresh_panel)
        self._refresh_panel()

    def create_plan_item(self, item: HarnessPlanItem):
        now = time.monotonic()
        self.plan_items.append(
            {
                "id": item.id,
                "created_at": now,
                "updated_at": None,
                "completed_at": now if item.status is TaskStatus.completed else None,
                "status": item.status,
                "task": item.content,
            }
        )

    def create_subagent_task(
        self, task_id: str, task_description: str, subagent_name: str
    ) -> None:
        self.subagent_tasks.append(
            {
                "task_id": task_id,
                "task_description": task_description,
                "subagent_name": subagent_name,
                "started_at": time.monotonic(),
                "ended_at": None,
            }
        )
        self._refresh_panel()

    def complete_subagent_task(self, task_id: str):
        for task in self.subagent_tasks:
            if task["task_id"] == task_id:
                task["ended_at"] = time.monotonic()
        self._refresh_panel()

    def _refresh_panel(self) -> None:

        # Plan items to show
        sorted_items = sorted(self.plan_items, key=lambda item: item["created_at"])

        _items_to_show = []
        active_ids: set[str] = set()
        panel_counter = 0
        if len(sorted_items) >= 1:
            for item in sorted_items:
                if item["status"] is TaskStatus.completed:
                    _items_to_show.append(Text("󰗠 " + item["task"], style=GREEN))
                elif item["status"] is TaskStatus.in_progress:
                    spinner = self._spinners.get(item["id"])
                    if spinner is None:
                        spinner = Spinner("arc", text=item["task"])
                        self._spinners[item["id"]] = spinner
                    else:
                        spinner.update(text=item["task"])
                    active_ids.add(item["id"])
                    _items_to_show.append(spinner)
                elif item["status"] in (TaskStatus.cancelled, TaskStatus.blocked):
                    _items_to_show.append(Text("󰜺 " + item["task"], style=f"dim {RED}"))
                else:
                    _items_to_show.append(
                        Text("○ " + item["task"], style=f"dim {SUBTEXT0}")
                    )
            panel_counter += 1

        # Prune subagent tasks
        if len(self.subagent_tasks) >= 1:
            self.subagent_tasks = list(
                filter(
                    lambda task: bool(
                        task["ended_at"] is None
                        or time.monotonic() - task["ended_at"] < 13
                    ),
                    self.subagent_tasks,
                )
            )
        _subagent_tasks_to_show = []
        if len(self.subagent_tasks) > 0:
            for task in self.subagent_tasks:
                text_suffix = Text(
                    str(task["subagent_name"]), style=f"bold {MAUVE}"
                ) + Text(
                    " | " + str(task["task_description"])[:14] + "...",
                    style=SUBTEXT1,
                )
                if task["ended_at"] is None:
                    spinner = self._spinners.get(task["task_id"])
                    if spinner is None:
                        spinner = Spinner(
                            "dots",
                            text=text_suffix,
                        )
                        self._spinners[task["task_id"]] = spinner
                    active_ids.add(task["task_id"])
                    _subagent_tasks_to_show.append(spinner)
                else:
                    _subagent_tasks_to_show.append(Text("󰗠 ", style=TEAL) + text_suffix)
            panel_counter += 1

        for stale in set(self._spinners) - active_ids:
            del self._spinners[stale]

        if panel_counter == 0:
            if (time.monotonic() - self.widget_created_at) > 15:
                self._timer.stop()
                self.remove()
            return

        # Calculating panel width
        available_width = max(1, self.size.width)
        column_gap = 1
        panel_width = max(1, (available_width - (2 * column_gap)) // panel_counter)

        # Subagent tasks
        panels = []
        if len(_items_to_show) >= 1:
            panels.append(
                Panel(
                    Group(*_items_to_show),
                    title="Plan",
                    border_style=MAUVE,
                    title_align="left",
                    padding=(0, 1),
                    width=panel_width,
                )
            )
        if len(_subagent_tasks_to_show):
            panels.append(
                Panel(
                    Group(*_subagent_tasks_to_show),
                    title="Subagents",
                    border_style=TEAL,
                    title_align="left",
                    padding=(0, 1),
                    width=panel_width,
                )
            )

        self.update(Columns(panels, equal=True, expand=True))

    def update_plan_item(self, item: HarnessPlanItem):
        for stored in self.plan_items:
            if stored["id"] == item.id:
                stored["task"] = item.content
                stored["status"] = item.status
                stored["updated_at"] = time.monotonic()
                if (
                    item.status is TaskStatus.completed
                    and stored["completed_at"] is None
                ):
                    stored["completed_at"] = time.monotonic()
        self._refresh_panel()

    def complete_plan_item(self, item: HarnessPlanItem):
        self.update_plan_item(item)

    def delete_plan_item(self, id: str):
        self.plan_items = [item for item in self.plan_items if item["id"] != id]
        self._spinners.pop(id, None)
        self._refresh_panel()


class AskUserOption(TypedDict):
    description: str
    label: str


class QuestionItem(TypedDict):
    header: str
    options: list[AskUserOption]
    question: str
    multi_select: bool


class AskUserWidget(Vertical):
    """Presents one deferred `ask_user_question` call and resolves when answered."""

    DEFAULT_CSS = """
    AskUserWidget {
        width: 100;
        max-width: 90%;
        height: auto;
        max-height: 30;
        margin: 0 1;
        background: $mo-surface0;
        border: round $mo-mauve;
        border-title-color: $mo-mauve;
        border-subtitle-color: $mo-overlay1;
        padding: 1 2;
    }
    AskUserWidget TabbedContent {
        height: auto;
        max-height: 22;
        margin-bottom: 1;
    }
    AskUserWidget TabbedContent > ContentTabs {
        background: transparent;
        border-bottom: solid $mo-surface2;
    }
    AskUserWidget Tab {
        height: 1;
        padding: 0 2;
        color: $mo-subtext0;
        text-style: none;
    }
    AskUserWidget Tab.-active {
        color: $mo-mauve;
        text-style: bold;
    }
    AskUserWidget Tab:hover {
        color: $mo-text;
    }
    AskUserWidget Underline > .underline--bar {
        color: $mo-mauve;
        background: $mo-mauve;
    }
    AskUserWidget TabPane {
        height: auto;
        padding: 1 1 0 1;
    }
    .question-text {
        width: 100%;
        height: auto;
        padding-bottom: 1;
        color: $mo-text;
        text-style: bold;
    }
    .question-hint {
        width: 100%;
        height: auto;
        padding-bottom: 1;
        color: $mo-subtext0;
        text-style: italic;
    }
    AskUserWidget RadioSet {
        width: 100%;
        height: auto;
        padding: 0;
        border: none;
        background: transparent;
    }
    AskUserWidget RadioSet:focus {
        border: none;
        background-tint: transparent;
    }
    AskUserWidget RadioSet:focus > RadioButton.-selected > .toggle--label,
    AskUserWidget RadioSet:blur > RadioButton.-selected > .toggle--label {
        background: transparent;
        color: $mo-text;
        text-style: none;
    }
    AskUserWidget RadioSet > RadioButton,
    AskUserWidget Checkbox {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $mo-surface1;
        border: none;
        border-left: thick $mo-surface2;
    }
    AskUserWidget RadioSet > RadioButton.-on,
    AskUserWidget Checkbox.-on {
        background: $mo-surface2;
        border-left: thick $mo-mauve;
    }
    AskUserWidget RadioSet > RadioButton:focus,
    AskUserWidget Checkbox:focus {
        border: none;
        border-left: thick $mo-pink;
        background-tint: $mo-pink 10%;
    }
    AskUserWidget Checkbox:focus > .toggle--label {
        background: transparent;
        color: $mo-text;
        text-style: none;
    }
    .custom-row {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    .custom-label {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
        color: $mo-overlay1;
        text-style: italic;
    }
    AskUserWidget Input {
        height: 3;
        background: $mo-mantle;
        border: round $mo-surface2;
        padding: 0 1;
    }
    AskUserWidget Input:focus {
        border: round $mo-mauve;
        background: $mo-mantle;
    }
    #ask-user-buttons {
        width: 100%;
        height: auto;
        align-horizontal: right;
        padding-top: 1;
    }
    #ask-user-buttons Button {
        min-width: 12;
        margin-left: 1;
    }
    #ask-user-submit {
        background: $mo-pink;
        color: $mo-crust;
        border: tall $mo-pink;
        text-style: bold;
    }
    #ask-user-cancel {
        color: $mo-subtext1;
        border: tall $mo-surface2;
    }
    """

    def __init__(self, request: AskUserRequest):
        super().__init__()
        self.request = request
        self.border_title = "Assistant question"
        self.border_subtitle = (
            f"{len(request.questions)} question"
            if len(request.questions) == 1
            else f"{len(request.questions)} questions"
        )
        self._answer: asyncio.Future[AskUserResponse] = (
            asyncio.get_running_loop().create_future()
        )

    def compose(self) -> ComposeResult:
        with TabbedContent(id="ask-user-tabs"):
            for idx, question in enumerate(self.request.questions):
                with TabPane(question.header, id=f"q{idx}"):
                    yield Static(
                        Text.from_markup(f"[b]{question.question}[/b]"),
                        classes="question-text",
                    )
                    if question.multi_select:
                        yield Static(
                            Text("Select all that apply (space to toggle)"),
                            classes="question-hint",
                        )
                        with VerticalGroup():
                            for option_index, option in enumerate(question.options):
                                yield Checkbox(
                                    Text.from_markup(
                                        f"[b]{option.label}[/b]"
                                        + (
                                            f"  [dim]{option.description}[/dim]"
                                            if option.description
                                            else ""
                                        )
                                    ),
                                    tooltip=option.description,
                                    id=f"q{idx}-option{option_index}",
                                )
                    else:
                        with RadioSet(id=f"q{idx}-options"):
                            for option_index, option in enumerate(question.options):
                                yield RadioButton(
                                    Text.from_markup(
                                        f"[b]{option.label}[/b]"
                                        + (
                                            f"  [dim]{option.description}[/dim]"
                                            if option.description
                                            else ""
                                        )
                                    ),
                                    tooltip=option.description,
                                    id=f"q{idx}-option{option_index}",
                                )
                    with Vertical(classes="custom-row"):
                        yield Static(
                            "Or type your own answer",
                            classes="custom-label",
                        )
                        yield Input(placeholder="Custom answer", id=f"q{idx}-custom")
        with Horizontal(id="ask-user-buttons"):
            yield Button("Decline", variant="default", id="ask-user-cancel")
            yield Button("Submit", variant="primary", id="ask-user-submit")

    async def wait_for_answer(self) -> AskUserResponse:
        return await self._answer

    def focus_first_control(self) -> None:
        first_question = self.request.questions[0]
        if first_question.multi_select:
            self.query_one("#q0-option0", Checkbox).focus()
        else:
            self.query_one("#q0-options", RadioSet).focus()

    def _finish(self, response: AskUserResponse) -> None:
        if not self._answer.done():
            self._answer.set_result(response)

    def cancel(self) -> None:
        """Decline the question, e.g. when the session is reset."""
        self._finish(AskUserResponse(cancelled=True))

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.action_cancel()

    def _create_response(self) -> AskUserResponse | None:
        answers = []

        for idx, question in enumerate(self.request.questions):
            custom_answer = self.query_one(f"#q{idx}-custom", Input).value.strip()
            if custom_answer:
                answers.append(
                    AskUserAnswer(header=question.header, custom_answer=custom_answer)
                )
                continue
            if question.multi_select:
                selected = tuple(
                    option.label
                    for option_index, option in enumerate(question.options)
                    if self.query_one(f"#q{idx}-option{option_index}", Checkbox).value
                )
            else:
                pressed = self.query_one(f"#q{idx}-options", RadioSet).pressed_button
                if pressed is None:
                    self.notify(
                        f"{question.header} still needs an answer",
                        title="Ask user",
                        severity="warning",
                    )
                    self.query_one(TabbedContent).active = f"q{idx}"
                    return None
                option_index = int(pressed.id.rsplit("-option", 1)[1])
                selected = (question.options[option_index].label,)
            if not selected:
                self.notify(
                    f"{question.header} still needs an answer",
                    title="Ask user",
                    severity="warning",
                )
                self.query_one(TabbedContent).active = f"q{idx}"
                return None
            answers.append(AskUserAnswer(header=question.header, selected=selected))

        response = AskUserResponse(answers=tuple(answers))
        try:
            check_response(self.request, response)
        except ValueError as error:
            self.notify(str(error), title="Ask user", severity="error")
            return None
        return response

    @on(Button.Pressed, "#ask-user-submit")
    def action_submit(self) -> None:
        response = self._create_response()
        if response is not None:
            self._finish(response)

    @on(Button.Pressed, "#ask-user-cancel")
    def action_cancel(self) -> None:
        self.cancel()
