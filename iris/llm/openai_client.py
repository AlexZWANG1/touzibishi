import json
import os
from typing import Generator
from openai import OpenAI
from .base import LLMClient, LLMResponse, ToolCall, StreamEvent


class OpenAIClient(LLMClient):
    def __init__(self, model: str = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.3,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.3,
    ) -> Generator[StreamEvent, None, None]:
        """Streaming response — yields text deltas, then a final 'done' with full LLMResponse."""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        content_parts = []
        tool_calls_acc: dict[int, dict] = {}
        input_tokens = 0
        output_tokens = 0

        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            # Usage info comes in the final chunk (choices may be empty)
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Text content
            if delta.content:
                yield StreamEvent(type="text_delta", content=delta.content)
                content_parts.append(delta.content)

            # Tool call deltas — accumulate across chunks
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "name": (tc_delta.function.name if tc_delta.function else "") or "",
                            "args": "",
                        }
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["args"] += tc_delta.function.arguments

        # Build final tool calls
        tool_calls = []
        for idx in sorted(tool_calls_acc.keys()):
            tc = tool_calls_acc[idx]
            tool_calls.append(ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=json.loads(tc["args"]) if tc["args"] else {},
            ))

        yield StreamEvent(
            type="done",
            response=LLMResponse(
                content="".join(content_parts) or None,
                tool_calls=tool_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )
