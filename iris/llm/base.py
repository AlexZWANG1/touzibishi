from __future__ import annotations
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Generator


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

    def as_message(self) -> dict:
        msg: dict = {"role": "assistant"}
        if self.content:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in self.tool_calls
            ]
        return msg


@dataclass
class StreamEvent:
    """Event yielded during streaming LLM response."""
    type: str  # "text_delta" | "done"
    content: str = ""
    response: Optional[LLMResponse] = None  # set on "done"


class LLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.3,
    ) -> LLMResponse:
        ...

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.3,
    ) -> Generator[StreamEvent, None, None]:
        """Streaming LLM call. Default falls back to non-streaming."""
        response = self.chat(messages, tools, temperature)
        if response.content:
            yield StreamEvent(type="text_delta", content=response.content)
        yield StreamEvent(type="done", response=response)
