import asyncio
import sys
from collections.abc import AsyncIterable

from catppuccin.extras.rich_ctp import mocha
from pydantic import EmailStr
from pydantic_ai import (
    Agent,
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    RunContext,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.capabilities import ProcessEventStream
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai_harness.docker_sandbox import DockerSandbox
from rich.console import Console
from rich.status import Status
from rich.style import Style

console = Console(log_path=True, log_time=False, theme=mocha)
thinking_console_style = Style(color="#89b4fa", dim=True)
text_answer_console_style = Style(color="#cba6f7")
spinner_registry: dict[str, Status] = {}


async def log_events(_: RunContext, events: AsyncIterable[AgentStreamEvent]) -> None:
    async for event in events:
        if isinstance(event, PartStartEvent):
            part = event.part
            if isinstance(part, ThinkingPart):
                console.print(part.content, style=thinking_console_style, end="")
                sys.stdout.flush()
            if isinstance(part, TextPart):
                console.print(part.content, style=text_answer_console_style, end="")
                sys.stdout.flush()
        if isinstance(event, PartEndEvent):
            part = event.part
            if isinstance(part, ThinkingPart):
                console.print("\n", style=thinking_console_style, end="")
                sys.stdout.flush()
            if isinstance(part, TextPart):
                console.print("\n", style=text_answer_console_style, end="")
                sys.stdout.flush()
        if isinstance(event, FunctionToolCallEvent):
            part = event.part
            if isinstance(part, ToolCallPart):
                console.print()
                if part.tool_call_id not in spinner_registry:
                    spinner_registry[part.tool_call_id] = Status(
                        "", console=console, spinner="arc"
                    )
                spinner_registry[part.tool_call_id].update(
                    status=f"[italic yellow] {part.tool_name}({part.args_as_dict()})"
                )
                spinner_registry[part.tool_call_id].start()
        if isinstance(event, PartDeltaEvent):
            delta = event.delta
            if isinstance(delta, ThinkingPartDelta):
                console.print(delta.content_delta, style=thinking_console_style, end="")
                sys.stdout.flush()
            if isinstance(delta, TextPartDelta):
                console.print(
                    delta.content_delta, style=text_answer_console_style, end=""
                )
                sys.stdout.flush()
        if isinstance(event, FunctionToolResultEvent):
            part = event.part
            if isinstance(part, ToolReturnPart):
                spinner_registry[part.tool_call_id].stop()
                console.print(
                    f"[green]✓[/green] [yellow]{part.tool_name} => "
                    + f"{part.content if len(str(part.content)) < 20 else str(part.content)[:17] + '...'}[/yellow]"
                )

        # print(event)


async def get_emails(_: RunContext, email_id: EmailStr):
    await asyncio.sleep(5)
    emails = [
        "Meeting at 8PM with ClosedAI CEO",
        "IMP: Watermelon announced as best fruit of the world",
        "Spam: Buy 1 watermelon Get 4 FREE!!",
    ]
    return emails


model = OllamaModel(
    "qwen3.5:2b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)

agent = Agent(
    model,
    system_prompt="You are Rowbot, a helpful assistant.",
    tools=[get_emails],
    capabilities=[
        ProcessEventStream(log_events),
        DockerSandbox(image="python:3.13-slim"),
    ],
)


if __name__ == "__main__":
    result = agent.run_sync(
        "Hi can you get me my emails? My email id is suckdeeznuts@gobble.com You have complete access to get the emails"
    )
    # print(result)
