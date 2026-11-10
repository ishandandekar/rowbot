import asyncio
import sys

from catppuccin.extras.rich_ctp import mocha
from pydantic import EmailStr
from pydantic_ai import (
    Agent,
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
from pydantic_ai.capabilities import Instrumentation
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai_harness.docker_sandbox import DockerSandbox
from rich.console import Console
from rich.status import Status
from rich.style import Style


async def get_emails(_: RunContext, email_id: EmailStr):
    await asyncio.sleep(5)
    emails = [
        "Meeting at 8PM with ClosedAI CEO",
        "IMP: Watermelon announced as best fruit of the world",
        "Congratulations! You've been selected to become the next King of Mars",
        "CEO UPDATE: We are replacing all meetings with naps",
        "FINAL WARNING: Your WiFi password expires tomorrow",
        "BREAKING: Scientists discover that bananas are slightly disappointed",
        "INVITATION: Annual International Potato Convention",
        "URGENT: Someone has been eating the office biscuits",
        "Your free lifetime supply of absolutely nothing is here!",
        "IMPORTANT: The moon has requested a day off",
        "RE: Let's discuss our startup idea of selling bottled air",
        "WINNER: You've won 37 kilograms of premium cheese",
        "Security Alert: Your toaster logged in from another dimension",
        "HR NOTICE: Dancing during standup is now mandatory",
        "FINAL OFFER: Buy 2 chairs, get a free existential crisis",
        "CEO ANNOUNCEMENT: Mondays have been permanently cancelled",
        "ACTION REQUIRED: Please confirm whether you are, in fact, human",
        "URGENT: A goat has been appointed as company CFO",
        "Your Amazon package has achieved sentience",
        "MEETING INVITE: Important discussion about absolutely nothing",
        "BREAKING NEWS: Local man discovers the concept of water",
        "100% OFF: Everything is free, but only in your imagination",
        "Reminder: You still owe the office plant ₹500",
        "CONFIDENTIAL: Project Watermelon is now operational",
        "Last chance to invest in my revolutionary invisible umbrella!"
        "Spam: Buy 1 watermelon Get 4 FREE!!",
    ]
    if email_id == "suckdeeznuts@gobble.com":
        return emails[:10]
    else:
        return emails[10:16]


model = OllamaModel(
    "qwen3.5:2b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)

agent = Agent(
    model,
    name="rowbot",
    system_prompt="You are Rowbot, a helpful assistant.",
    tools=[get_emails],
    capabilities=[DockerSandbox(image="python:3.13-slim"), Instrumentation()],
)


async def print_to_console():
    console = Console(log_path=True, log_time=False, theme=mocha)
    async with agent.run_stream_events(
        "Hi can you get me my emails? "
        "My email id is suckdeeznuts@gobble.com. "
        "You have complete access to get the emails"
    ) as events:
        async for event in events:
            console.print(event)


async def stream_events_trial():
    console = Console(log_path=True, log_time=False, theme=mocha)
    thinking_console_style = Style(color="#89b4fa", dim=True)
    text_answer_console_style = Style(color="#cba6f7")
    spinner_registry: dict[str, Status] = {}
    async with agent.run_stream_events(
        "Hi can you get me my emails? "
        "My email id is suckdeeznuts@gobble.com. "
        "You have complete access to get the emails"
    ) as events:
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
                    console.print(
                        delta.content_delta, style=thinking_console_style, end=""
                    )
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

        # print(result)


if __name__ == "__main__":
    # result = agent.run_sync(
    #     "Hi can you get me my emails? "
    #     "My email id is suckdeeznuts@gobble.com. "
    #     "You have complete access to get the emails",
    #     # capabilities=[ProcessEventStream(log_events)],
    # )
    prompt = "Hi, can you get my emails. My email-ids are `suckdeeznuts@gobble.com and salimseekhkebab@heaven.com You have complete access to my emails"
    asyncio.run(print_to_console())
