import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx

from shared.models import StreamEvent, StreamEventType


@dataclass
class BackendClient:
    base_url: str

    async def stream_chat(self, message: str) -> AsyncGenerator[StreamEvent, None]:
        async with httpx.AsyncClient() as client:
            payload = {"message": message}

            async with client.stream(
                "POST",
                f"{self.base_url}/chat/stream",
                json=payload,
                timeout=300.0,
            ) as response:
                event_type: str | None = None

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and event_type is not None:
                        data_str = line.split(":", 1)[1].strip()
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event = self._parse_event(event_type, data)
                        if event:
                            yield event

    def _parse_event(self, event_type: str, data: dict) -> StreamEvent | None:
        match event_type:
            case "message_start":
                return StreamEvent(
                    type=StreamEventType.MESSAGE_START,
                    message_id=data.get("message_id", ""),
                )
            case "text_delta":
                return StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    content_delta=data.get("delta", ""),
                )
            case "thinking_delta":
                return StreamEvent(
                    type=StreamEventType.THINKING_DELTA,
                    thinking_content=data.get("thinking", ""),
                )
            case "message_end":
                return StreamEvent(
                    type=StreamEventType.MESSAGE_END,
                    message_id=data.get("message_id", ""),
                )
            case "error":
                return StreamEvent(
                    type=StreamEventType.ERROR,
                    error=data.get("error", "Unknown error"),
                )
        return None
