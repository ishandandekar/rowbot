import time
from typing import TypedDict

from pydantic_ai_harness.planning import PlanItem as HarnessPlanItem
from pydantic_ai_harness.planning import TaskStatus
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from textual.widgets import Static

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
