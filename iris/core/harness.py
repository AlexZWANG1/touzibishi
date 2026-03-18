"""
IRIS Harness — the agent loop.

Inspired by Pi Agent (inner loop) + OpenClaw (retry/context/failover):
  - Phase-gated tool access (IRIS-specific)
  - Retry with exponential backoff
  - Context overflow management (truncate → compact → drop)
  - Parallel tool execution via ThreadPoolExecutor
  - Abort support via threading.Event
  - Mid-run steering via thread-safe queue
  - Event hooks for UI/logging integration

Guards and Invariants are gone — tools validate their own inputs/outputs.
"""

import json
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from llm.base import LLMClient, LLMResponse, ToolCall, StreamEvent
from tools.base import ToolResult, TOOL_PHASES, PHASE_ORDER, PHASE_TRANSITIONS


# ── Events ────────────────────────────────────────────────────

class EventType(str, Enum):
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TEXT_DELTA = "text_delta"
    TEXT = "text"
    CONTEXT_COMPACTED = "context_compacted"
    RETRY = "retry"
    PHASE_CHANGE = "phase_change"
    ABORTED = "aborted"
    STEERING_INJECTED = "steering_injected"


@dataclass
class HarnessEvent:
    type: EventType
    data: dict = field(default_factory=dict)


# ── Config & Result ───────────────────────────────────────────

@dataclass
class HarnessConfig:
    max_tool_rounds: int = 25
    max_retries: int = 3
    retry_base_delay: float = 1.0
    context_limit_chars: int = 300_000  # ~75k tokens
    compress_threshold_chars: int = 2000
    parallel_tool_execution: bool = True
    streaming: bool = False


@dataclass
class HarnessResult:
    ok: bool
    reply: Optional[str] = None
    tool_log: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0


# ── Harness ───────────────────────────────────────────────────

class Harness:
    """
    LLM agent loop controller.
    Tools validate their own inputs. Harness manages the loop infrastructure.
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: list,
        soul: str,
        config: HarnessConfig = None,
        on_event: Callable[[HarnessEvent], None] = None,
    ):
        self.llm = llm
        self.tool_registry = {t.name: t for t in tools}
        self.soul = soul
        self.config = config or HarnessConfig()
        self.on_event = on_event or (lambda e: None)
        self._abort = threading.Event()
        self._steering_queue: queue.Queue = queue.Queue()

    # ── Public API ────────────────────────────────────────────

    def abort(self):
        """Cancel the running analysis from another thread."""
        self._abort.set()

    def steer(self, message: str):
        """Inject a message into the running loop (between tool calls)."""
        self._steering_queue.put(message)

    def run(
        self,
        user_input: str,
        context_docs: list[str] = None,
        initial_phase: str = "gather",
    ) -> HarnessResult:
        self._abort.clear()
        self.current_phase = initial_phase

        messages = [
            {"role": "system", "content": self.soul},
            {"role": "user", "content": self._build_user_message(user_input, context_docs)},
        ]
        tool_log = []
        total_input = 0
        total_output = 0

        for round_num in range(self.config.max_tool_rounds):
            # ── Abort check ──
            if self._abort.is_set():
                self._emit(EventType.ABORTED)
                return HarnessResult(
                    ok=False, error="Aborted by user",
                    tool_log=tool_log,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                )

            # ── Inject steering messages ──
            self._inject_steering(messages)

            # ── Context overflow prevention ──
            self._manage_context(messages)

            # ── Call LLM (with retry + optional streaming) ──
            self._emit(EventType.TURN_START, {"round": round_num, "phase": self.current_phase})
            tool_schemas = self._tool_schemas()

            response = self._call_with_retry(messages, tool_schemas)
            if response is None:
                return HarnessResult(
                    ok=False,
                    error="LLM call failed after all retries",
                    tool_log=tool_log,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                )

            total_input += response.input_tokens
            total_output += response.output_tokens

            # ── No tool calls → final reply ──
            if not response.tool_calls:
                self._emit(EventType.TURN_END, {"round": round_num})
                return HarnessResult(
                    ok=True,
                    reply=response.content,
                    tool_log=tool_log,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                )

            # ── Dispatch tool calls ──
            messages.append(response.as_message())

            if self.config.parallel_tool_execution and len(response.tool_calls) > 1:
                results = self._dispatch_parallel(response.tool_calls, tool_log)
            else:
                results = [self._dispatch(tc, tool_log) for tc in response.tool_calls]

            for tc, result_content in zip(response.tool_calls, results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result_content),
                })

            self._emit(EventType.TURN_END, {"round": round_num})

        return HarnessResult(
            ok=False,
            error=f"MAX_TOOL_ROUNDS ({self.config.max_tool_rounds}) reached",
            tool_log=tool_log,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )

    # ── LLM call with retry ──────────────────────────────────

    def _call_with_retry(self, messages: list, tools: list) -> Optional[LLMResponse]:
        last_error = None

        for attempt in range(self.config.max_retries):
            if self._abort.is_set():
                return None

            try:
                if self.config.streaming:
                    return self._call_streaming(messages, tools)
                return self.llm.chat(messages, tools=tools)

            except Exception as e:
                last_error = e
                err = str(e).lower()

                # Context overflow → compact and retry
                if any(kw in err for kw in ("context_length", "maximum context", "token", "too long")):
                    self._compact_context(messages)
                    self._emit(EventType.CONTEXT_COMPACTED, {"reason": str(e), "attempt": attempt})
                    continue

                # Rate limit / overload → exponential backoff
                if any(kw in err for kw in ("rate_limit", "429", "overloaded", "503", "capacity")):
                    delay = self.config.retry_base_delay * (2 ** attempt)
                    self._emit(EventType.RETRY, {"attempt": attempt + 1, "delay": delay, "error": str(e)})
                    time.sleep(delay)
                    continue

                # Other errors → don't retry
                break

        self._emit(EventType.RETRY, {"failed": True, "error": str(last_error)})
        return None

    def _call_streaming(self, messages: list, tools: list) -> LLMResponse:
        """Call LLM with streaming, emitting text deltas via events."""
        response = None
        for event in self.llm.chat_stream(messages, tools=tools):
            if event.type == "text_delta":
                self._emit(EventType.TEXT_DELTA, {"content": event.content})
            elif event.type == "done":
                response = event.response
        if response is None:
            raise RuntimeError("Stream ended without 'done' event")
        return response

    # ── Tool dispatch ─────────────────────────────────────────

    def _dispatch(self, tc: ToolCall, tool_log: list) -> dict:
        # Phase check
        allowed = TOOL_PHASES.get(self.current_phase, set())
        if tc.name not in allowed:
            tool_log.append({"tool": tc.name, "status": "phase_blocked", "phase": self.current_phase})
            return {
                "status": "error",
                "error": f"Tool '{tc.name}' not available in '{self.current_phase}' phase.",
                "hint": f"Available tools in this phase: {sorted(allowed)}",
                "recoverable": True,
            }

        # Tool exists?
        tool = self.tool_registry.get(tc.name)
        if not tool:
            tool_log.append({"tool": tc.name, "status": "not_found"})
            return {
                "status": "error",
                "error": f"Tool '{tc.name}' not found",
                "hint": f"Available: {list(self.tool_registry.keys())}",
                "recoverable": False,
            }

        # Execute — tool validates its own inputs/outputs
        self._emit(EventType.TOOL_START, {"tool": tc.name, "args": tc.arguments})
        try:
            result: ToolResult = tool.execute(tc.arguments)
        except Exception as e:
            tool_log.append({"tool": tc.name, "status": "exception", "error": str(e)})
            self._emit(EventType.TOOL_END, {"tool": tc.name, "status": "exception"})
            return {"status": "error", "error": f"Tool exception: {e}", "recoverable": False}

        # Phase transition on success
        if result.status == "ok":
            transition = PHASE_TRANSITIONS.get(tc.name)
            if transition:
                cur_idx = PHASE_ORDER.index(self.current_phase)
                new_idx = PHASE_ORDER.index(transition)
                if new_idx > cur_idx:
                    self.current_phase = transition
                    self._emit(EventType.PHASE_CHANGE, {"from": PHASE_ORDER[cur_idx], "to": transition})

        # Compress + return
        result_dict = result.to_dict()
        compressed = self._compress(result_dict)
        tool_log.append({"tool": tc.name, "status": result.status, "phase": self.current_phase})
        self._emit(EventType.TOOL_END, {"tool": tc.name, "status": result.status})
        return compressed

    def _dispatch_parallel(self, tool_calls: list[ToolCall], tool_log: list) -> list[dict]:
        """Execute multiple tool calls concurrently, return results in original order."""
        results = [None] * len(tool_calls)
        with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
            future_to_idx = {
                executor.submit(self._dispatch, tc, tool_log): i
                for i, tc in enumerate(tool_calls)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {"status": "error", "error": str(e), "recoverable": False}
        return results

    # ── Context management ────────────────────────────────────

    def _manage_context(self, messages: list):
        """Proactively compact when approaching the context limit."""
        total_chars = sum(len(json.dumps(m)) for m in messages)
        if total_chars > self.config.context_limit_chars * 0.85:
            self._compact_context(messages)
            self._emit(EventType.CONTEXT_COMPACTED, {"chars_before": total_chars})

    def _compact_context(self, messages: list):
        """
        3-pass context reduction:
        1. Truncate large tool results in-place
        2. Deep-truncate nested structures
        3. Drop middle exchanges if still too large
        """
        # Pass 1: Truncate tool result content
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > 800:
                    try:
                        data = json.loads(content)
                        msg["content"] = json.dumps(self._deep_truncate(data))
                    except (json.JSONDecodeError, TypeError):
                        msg["content"] = content[:500] + "...[truncated]"

        # Pass 2: Check if still too large → drop middle exchanges
        total_chars = sum(len(json.dumps(m)) for m in messages)
        if total_chars > self.config.context_limit_chars * 0.85 and len(messages) > 8:
            # Keep: system(0), first user(1), ... last 6 messages
            kept = messages[:2] + [
                {"role": "user", "content": "[Earlier tool exchanges compacted to save context window]"}
            ] + messages[-6:]
            messages.clear()
            messages.extend(kept)

    def _deep_truncate(self, obj, max_str=500, max_list=5):
        """Recursively truncate large strings and lists."""
        if isinstance(obj, str):
            return obj[:max_str] + f"...[{len(obj)} chars]" if len(obj) > max_str else obj
        if isinstance(obj, list):
            items = [self._deep_truncate(item) for item in obj[:max_list]]
            if len(obj) > max_list:
                items.append(f"...[{len(obj) - max_list} more]")
            return items
        if isinstance(obj, dict):
            return {k: self._deep_truncate(v) for k, v in obj.items()}
        return obj

    # ── Steering ──────────────────────────────────────────────

    def _inject_steering(self, messages: list):
        """Drain steering queue and inject as user messages."""
        while not self._steering_queue.empty():
            try:
                msg = self._steering_queue.get_nowait()
                messages.append({"role": "user", "content": f"[STEERING] {msg}"})
                self._emit(EventType.STEERING_INJECTED, {"message": msg})
            except queue.Empty:
                break

    # ── Helpers ───────────────────────────────────────────────

    def _compress(self, result: dict) -> dict:
        result_str = json.dumps(result)
        if len(result_str) <= self.config.compress_threshold_chars:
            return result
        return self._deep_truncate(result)

    def _build_user_message(self, user_input: str, context_docs: list[str] = None) -> str:
        msg = user_input
        if context_docs:
            docs_text = "\n\n---\n\n".join(context_docs)
            msg += f"\n\n## Provided Documents\n\n{docs_text}"
        return msg

    def _tool_schemas(self) -> list[dict]:
        allowed = TOOL_PHASES.get(self.current_phase, set())
        return [t.schema for t in self.tool_registry.values() if t.name in allowed]

    def _emit(self, event_type: EventType, data: dict = None):
        self.on_event(HarnessEvent(type=event_type, data=data or {}))
