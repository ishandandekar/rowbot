import json
import uuid

from fastapi import APIRouter
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    TextPartDelta,
    ThinkingPartDelta,
)
from sse_starlette.sse import EventSourceResponse

from backend.agent import agent
from backend.models import ChatRequest

router = APIRouter()

chat_history: list[ModelMessage] = []


@router.post("/chat")
async def chat(request: ChatRequest) -> dict:
    result = await agent.run(request.message, message_history=chat_history)
    chat_history[:] = result.all_messages()
    return {"response": result.output, "message_id": str(uuid.uuid4())}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    message_id = str(uuid.uuid4())
    full_response = ""

    async def event_generator():
        nonlocal full_response

        yield {"event": "message_start", "data": json.dumps({"message_id": message_id})}

        async with agent.iter(request.message, message_history=chat_history) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartDeltaEvent):
                                if isinstance(event.delta, ThinkingPartDelta):
                                    yield {
                                        "event": "thinking_delta",
                                        "data": json.dumps(
                                            {"thinking": event.delta.content_delta}
                                        ),
                                    }
                                elif isinstance(event.delta, TextPartDelta):
                                    full_response += event.delta.content_delta
                                    yield {
                                        "event": "text_delta",
                                        "data": json.dumps(
                                            {"delta": event.delta.content_delta}
                                        ),
                                    }

        chat_history[:] = run.all_messages()

        yield {"event": "message_end", "data": json.dumps({"message_id": message_id})}

    return EventSourceResponse(event_generator())
