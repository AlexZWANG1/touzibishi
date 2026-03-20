"""
IRIS Harness - order-free agent loop.

Responsibilities:
- Main reasoning loop and tool dispatch
- Budget governance (rounds/tool calls/wall-time + full LLM accounting)
- Loop detection (repeat/ping-pong/no-progress)
- Context compaction and memory flush orchestration
- Tool hooks and run event persistence
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from core.budget import BudgetPolicy, BudgetTracker
from core.context import ContextAssembler
from core.loop_detector import LoopDetectionConfig, LoopDetector
from core.tool_hooks import DefaultToolHooks, ToolHookContext, ToolHooks
from llm.base import LLMClient, LLMResponse, StreamEvent, ToolCall
from tools.base import ToolResult


class EventType(str, Enum):
    RUN_START = "run_start"
    RUN_END = "run_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOLS_SCORED = "tools_scored"
    TEXT_DELTA = "text_delta"
    TEXT = "text"
    CONTEXT_COMPACTED = "context_compacted"
    RETRY = "retry"
    ABORTED = "aborted"
    STEERING_INJECTED = "steering_injected"
    LOOP_DETECTED = "loop_detected"
    BUDGET_TRIMMED = "budget_trimmed"


@dataclass
class HarnessEvent:
    type: EventType
    data: dict = field(default_factory=dict)


@dataclass
class HarnessConfig:
    max_tool_rounds: int = 25
    max_total_tool_calls: int = 60
    max_wall_time_seconds: float = 480.0

    max_retries: int = 3
    retry_base_delay: float = 1.0

    context_limit_chars: int = 300_000
    compress_threshold_chars: int = 5000
    tool_compress_overrides: dict[str, int] = field(
        default_factory=lambda: {
            "fmp_get_financials": 8000,
            "fred_get_macro": 8000,
            "fmp_financials": 8000,
            "fred_series": 8000,
        }
    )

    tool_injection_mode: str = "dynamic"  # dynamic | all
    max_tools_per_round: int = 10
    always_exposed_tools: tuple[str, ...] = ("query_knowledge", "memory_search")
    tool_triggers: dict[str, list[str]] = field(default_factory=dict)

    include_flush_in_tool_rounds: bool = True
    include_compaction_in_tool_rounds: bool = True
    pre_round_trim: bool = True

    loop_detection: LoopDetectionConfig = field(default_factory=LoopDetectionConfig)

    parallel_tool_execution: bool = True
    streaming: bool = False
    persist_events: bool = True


@dataclass
class HarnessResult:
    ok: bool
    reply: Optional[str] = None
    tool_log: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    budget_breakdown: dict = field(default_factory=dict)
    run_id: Optional[str] = None


class Harness:
    def __init__(
        self,
        llm: LLMClient,
        tools: list,
        soul: str,
        config: HarnessConfig = None,
        on_event: Callable[[HarnessEvent], None] = None,
        retriever=None,
        tool_hooks: ToolHooks | None = None,
    ):
        self.llm = llm
        self.tool_registry = {t.name: t for t in tools}
        self.soul = soul
        self.config = config or HarnessConfig()
        self.on_event = on_event or (lambda e: None)
        self.retriever = retriever
        self.tool_hooks = tool_hooks or DefaultToolHooks()

        self.context = ContextAssembler(llm_client=self.llm, retriever=self.retriever)
        self.context._knowledge_tools = list(self.tool_registry.values())

        self._abort = threading.Event()
        self._steering_queue: queue.Queue[str] = queue.Queue()

        self._active_budget: Optional[BudgetTracker] = None
        self._current_run_id: Optional[str] = None

        self._run_log_db_path = getattr(self.retriever, "db_path", None)
        if self._run_log_db_path and self.config.persist_events:
            self._ensure_run_log_table()

        if self.retriever and hasattr(self.retriever, "set_usage_tracker"):
            self.retriever.set_usage_tracker(self._track_embedding_usage)

    # Public API -------------------------------------------------

    def abort(self):
        self._abort.set()

    def steer(self, message: str):
        self._steering_queue.put(message)

    def run(self, user_input: str, context_docs: list[str] = None) -> HarnessResult:
        self._abort.clear()
        self._current_run_id = f"run_{uuid.uuid4().hex[:12]}"

        budget = BudgetTracker(self._budget_policy())
        self._active_budget = budget
        loop_detector = LoopDetector(self.config.loop_detection)

        subject = self.context.extract_subject(user_input)
        prior_messages = self.context.load_prior_context(subject=subject, retriever=self.retriever)

        messages: list[dict] = [self.context.build_system_message(self.soul, [])]
        messages.extend(prior_messages)
        messages.append({"role": "user", "content": self.context.build_user_message(user_input, context_docs)})

        self._messages = messages

        tool_log: list[dict] = []
        recent_tool_names: list[str] = []

        self._emit(
            EventType.RUN_START,
            {
                "run_id": self._current_run_id,
                "subject": subject,
                "budget": budget.remaining_dict(),
                "loop_status": loop_detector.status(),
            },
        )

        return self._main_loop(budget, loop_detector, messages, tool_log, recent_tool_names)

    def continue_run(self, user_input: str, on_event=None, context_docs=None) -> HarnessResult:
        """Continue an existing conversation with preserved message history."""
        if not hasattr(self, '_messages') or not self._messages:
            raise RuntimeError("No prior run to continue")

        if on_event:
            self.on_event = on_event

        self._abort.clear()
        self._current_run_id = f"run_{uuid.uuid4().hex[:12]}"

        budget = BudgetTracker(self._budget_policy())
        self._active_budget = budget

        # Append new user message to existing conversation
        self._messages.append({"role": "user", "content": self.context.build_user_message(user_input, context_docs)})

        # Fresh loop detector and tool tracking for this turn
        loop_detector = LoopDetector(self.config.loop_detection)
        tool_log: list[dict] = []
        recent_tool_names: list[str] = []

        self._emit(
            EventType.RUN_START,
            {
                "run_id": self._current_run_id,
                "subject": self.context.extract_subject(user_input),
                "budget": budget.remaining_dict(),
                "is_continuation": True,
            },
        )

        return self._main_loop(budget, loop_detector, self._messages, tool_log, recent_tool_names)

    def _main_loop(
        self,
        budget: BudgetTracker,
        loop_detector: LoopDetector,
        messages: list[dict],
        tool_log: list[dict],
        recent_tool_names: list[str],
    ) -> HarnessResult:
        """Core agent loop shared by run() and continue_run()."""
        main_round = 0

        while True:
            if self._abort.is_set():
                self._emit(EventType.ABORTED, {"run_id": self._current_run_id})
                return self._final_result(False, tool_log=tool_log, error="Aborted by user", budget=budget)

            if budget.wall_time_exceeded():
                return self._final_result(
                    False,
                    tool_log=tool_log,
                    error=f"MAX_WALL_TIME_SECONDS ({self.config.max_wall_time_seconds}) reached",
                    budget=budget,
                )

            if budget.tool_call_limit_reached():
                return self._final_result(
                    False,
                    tool_log=tool_log,
                    error=f"MAX_TOTAL_TOOL_CALLS ({self.config.max_total_tool_calls}) reached",
                    budget=budget,
                )

            self._inject_steering(messages)

            if self.context.should_compact(messages, self.config.context_limit_chars):
                before_len = len(messages)
                self.context.compact(messages, self.llm, budget)
                self._emit(
                    EventType.CONTEXT_COMPACTED,
                    {
                        "run_id": self._current_run_id,
                        "messages_before": before_len,
                        "messages_after": len(messages),
                        "budget": budget.remaining_dict(),
                    },
                )

            tool_schemas = self._tool_schemas(messages, recent_tool_names)
            tools_exposed = [s["function"]["name"] for s in tool_schemas]
            messages[0] = self.context.build_system_message(self.soul, tools_exposed)

            self._emit(
                EventType.TURN_START,
                {
                    "run_id": self._current_run_id,
                    "round": main_round,
                    "tools_exposed": tools_exposed,
                    "budget": budget.remaining_dict(),
                    "loop_status": loop_detector.status(),
                },
            )

            response = self._call_with_retry(messages, tool_schemas, budget=budget, category="main")
            if response is None:
                return self._final_result(
                    False,
                    tool_log=tool_log,
                    error="LLM call failed after all retries",
                    budget=budget,
                )

            # Audit: log full assistant message (text + tool decisions)
            self._emit(
                EventType.ASSISTANT_MESSAGE,
                {
                    "run_id": self._current_run_id,
                    "round": main_round,
                    "content": (response.content or "")[:5000],
                    "tool_calls": [
                        {"name": tc.name, "arguments": tc.arguments}
                        for tc in (response.tool_calls or [])
                    ],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
            )

            if not response.tool_calls:
                self._emit(
                    EventType.TURN_END,
                    {
                        "run_id": self._current_run_id,
                        "round": main_round,
                        "tool_calls_executed": 0,
                        "budget": budget.remaining_dict(),
                        "loop_status": loop_detector.status(),
                    },
                )
                return self._final_result(True, reply=response.content, tool_log=tool_log, budget=budget)

            tool_calls = list(response.tool_calls)
            pre_detectors = loop_detector.inspect_tool_signature(self._tool_call_signature(tool_calls))

            allowed = budget.trim_tool_calls(len(tool_calls))
            if allowed < len(tool_calls):
                self._emit(
                    EventType.BUDGET_TRIMMED,
                    {
                        "run_id": self._current_run_id,
                        "round": main_round,
                        "planned": len(tool_calls),
                        "allowed": allowed,
                    },
                )
                tool_calls = tool_calls[:allowed]

            if not tool_calls:
                return self._final_result(
                    False,
                    tool_log=tool_log,
                    error=f"MAX_TOTAL_TOOL_CALLS ({self.config.max_total_tool_calls}) reached",
                    budget=budget,
                )

            if not budget.reserve_round("main"):
                return self._final_result(
                    False,
                    tool_log=tool_log,
                    error=f"MAX_TOOL_ROUNDS ({self.config.max_tool_rounds}) reached",
                    budget=budget,
                )

            if budget.total_tool_calls() + len(tool_calls) > self.config.max_total_tool_calls:
                room = budget.remaining_tool_calls()
                tool_calls = tool_calls[: max(0, room)]
                if not tool_calls:
                    return self._final_result(
                        False,
                        tool_log=tool_log,
                        error=f"MAX_TOTAL_TOOL_CALLS ({self.config.max_total_tool_calls}) reached",
                        budget=budget,
                    )

            budget.register_tool_calls("main", len(tool_calls))

            response_for_history = LLMResponse(
                content=response.content,
                tool_calls=tool_calls,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            messages.append(response_for_history.as_message())

            recent_tool_names.extend(tc.name for tc in tool_calls)
            recent_tool_names = recent_tool_names[-20:]

            if self.config.parallel_tool_execution and len(tool_calls) > 1:
                results = self._dispatch_parallel(tool_calls, tool_log, main_round, budget)
            else:
                results = [self._dispatch(tc, tool_log, main_round, budget) for tc in tool_calls]

            for tc, result_content in zip(tool_calls, results):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result_content, ensure_ascii=False),
                    }
                )

            post_detectors = loop_detector.inspect_tool_results(results)
            signal = loop_detector.resolve_round(pre_detectors | post_detectors)
            if signal:
                self._emit(
                    EventType.LOOP_DETECTED,
                    {
                        "run_id": self._current_run_id,
                        "round": main_round,
                        "detectors": signal.detector_names,
                        "message": signal.message,
                        "should_steer": signal.should_steer,
                        "should_stop": signal.should_stop,
                    },
                )
                if signal.should_steer:
                    steer_msg = "You are repeating operations. Try a different strategy or adjust tool arguments."
                    messages.append({"role": "user", "content": f"[STEERING] {steer_msg}"})
                    self._emit(
                        EventType.STEERING_INJECTED,
                        {"run_id": self._current_run_id, "message": steer_msg},
                    )
                if signal.should_stop:
                    return self._final_result(
                        False,
                        tool_log=tool_log,
                        error=signal.message,
                        budget=budget,
                    )

            self._emit(
                EventType.TURN_END,
                {
                    "run_id": self._current_run_id,
                    "round": main_round,
                    "tool_calls_executed": len(tool_calls),
                    "budget": budget.remaining_dict(),
                    "loop_status": loop_detector.status(),
                },
            )
            main_round += 1

    # LLM call ---------------------------------------------------

    def _call_with_retry(
        self,
        messages: list,
        tools: list,
        budget: BudgetTracker,
        category: str,
    ) -> Optional[LLMResponse]:
        last_error = None

        for attempt in range(self.config.max_retries):
            if self._abort.is_set():
                return None

            try:
                if self.config.streaming and category == "main":
                    response = self._call_streaming(messages, tools)
                else:
                    response = self.llm.chat(messages, tools=tools)

                budget.register_llm_call(category, response.input_tokens, response.output_tokens)
                return response

            except Exception as e:
                last_error = e
                err = str(e).lower()

                if any(kw in err for kw in ("context_length", "maximum context", "token", "too long")):
                    if self.context.should_compact(messages, self.config.context_limit_chars):
                        before_len = len(messages)
                        self.context.compact(messages, self.llm, budget)
                        self._emit(
                            EventType.CONTEXT_COMPACTED,
                            {
                                "run_id": self._current_run_id,
                                "attempt": attempt,
                                "reason": str(e),
                                "messages_before": before_len,
                                "messages_after": len(messages),
                            },
                        )
                        continue

                if any(kw in err for kw in ("rate_limit", "429", "overloaded", "503", "capacity")):
                    delay = self.config.retry_base_delay * (2 ** attempt)
                    self._emit(
                        EventType.RETRY,
                        {
                            "run_id": self._current_run_id,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)
                    continue

                break

        self._emit(
            EventType.RETRY,
            {"run_id": self._current_run_id, "failed": True, "error": str(last_error)},
        )
        return None

    def _call_streaming(self, messages: list, tools: list) -> LLMResponse:
        response = None
        for event in self.llm.chat_stream(messages, tools=tools):
            if event.type == "text_delta":
                self._emit(EventType.TEXT_DELTA, {"run_id": self._current_run_id, "content": event.content})
            elif event.type == "done":
                response = event.response
        if response is None:
            raise RuntimeError("Stream ended without 'done' event")
        return response

    # Tool dispatch ----------------------------------------------

    def _dispatch(self, tc: ToolCall, tool_log: list, round_num: int, budget: BudgetTracker) -> dict:
        hook_ctx = ToolHookContext(
            tool_name=tc.name,
            args=tc.arguments,
            run_id=self._current_run_id or "",
            round_number=round_num,
            budget_remaining=budget.remaining_dict(),
        )

        tool = self.tool_registry.get(tc.name)
        if not tool:
            result = ToolResult.fail(
                f"Tool '{tc.name}' not found",
                hint=f"Available: {list(self.tool_registry.keys())}",
                recoverable=False,
            )
            result.tags.append("tool_not_found")
            result = self.tool_hooks.after_tool_call(hook_ctx, result)
            tool_log.append({"tool": tc.name, "status": result.status, "tags": result.tags, "error": result.error})
            return self._compress(result.to_dict(), tc.name)

        before_ctx = self.tool_hooks.before_tool_call(hook_ctx)
        if before_ctx is None:
            result = ToolResult.fail(
                "Tool call blocked by hook",
                hint="Arguments failed hook validation",
                recoverable=False,
            )
            result.tags.append("blocked")
            result = self.tool_hooks.after_tool_call(hook_ctx, result)
            tool_log.append({"tool": tc.name, "status": result.status, "tags": result.tags, "error": result.error})
            return self._compress(result.to_dict(), tc.name)

        self._emit(
            EventType.TOOL_START,
            {
                "run_id": self._current_run_id,
                "round": round_num,
                "tool": tc.name,
                "args": before_ctx.args,
            },
        )

        try:
            result = tool.execute(before_ctx.args)
        except Exception as e:
            result = ToolResult.fail(f"Tool exception: {e}", recoverable=False)

        result = self.tool_hooks.after_tool_call(before_ctx, result)

        # Build audit-friendly result snapshot (truncated for storage)
        result_snapshot = self._truncate_for_audit(result.data) if result.status == "ok" else None

        tool_log.append(
            {
                "tool": tc.name,
                "status": result.status,
                "tags": result.tags,
                "error": result.error,
                "result": result_snapshot,
            }
        )

        self._emit(
            EventType.TOOL_END,
            {
                "run_id": self._current_run_id,
                "round": round_num,
                "tool": tc.name,
                "status": result.status,
                "tags": result.tags,
                "result": result_snapshot,
                "result_full": result.data if result.status == "ok" else None,
                "error": result.error if result.status != "ok" else None,
                "hint": result.hint if result.status != "ok" else None,
            },
        )

        return self._compress(result.to_dict(), tc.name)

    def _dispatch_parallel(
        self,
        tool_calls: list[ToolCall],
        tool_log: list,
        round_num: int,
        budget: BudgetTracker,
    ) -> list[dict]:
        results = [None] * len(tool_calls)
        with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
            future_to_idx = {
                executor.submit(self._dispatch, tc, tool_log, round_num, budget): i
                for i, tc in enumerate(tool_calls)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = {
                        "status": "error",
                        "error": str(e),
                        "recoverable": False,
                        "tags": ["dispatch_exception"],
                    }
        return results

    # Routing/helpers --------------------------------------------

    def _tool_schemas(self, messages: list[dict], recent_tool_names: list[str]) -> list[dict]:
        if not self.tool_registry:
            return []

        tools = list(self.tool_registry.values())
        if self.config.tool_injection_mode == "all":
            return [t.schema for t in tools]

        max_tools = max(1, min(self.config.max_tools_per_round, len(tools)))
        context = self._recent_context_text(messages).lower()
        signals = self._detect_artifact_signals(context)

        always = [n for n in self.config.always_exposed_tools if n in self.tool_registry]
        trigger_map = self.config.tool_triggers or {}

        scored: list[tuple[float, str]] = []
        for tool in tools:
            keywords = trigger_map.get(tool.name, [])
            score = 0.0
            for kw in keywords:
                if kw and kw.lower() in context:
                    score += 2.0

            if tool.name in recent_tool_names[-4:]:
                score += 0.4

            if signals["has_observation"] and tool.name == "add_evidence_card":
                score += 1.2
            if signals["has_hypothesis"] and tool.name in {"add_evidence_card", "run_valuation", "compute_trade_score", "build_dcf", "get_comps"}:
                score += 1.5
            if signals["has_valuation"] and tool.name in {"compute_trade_score", "get_comps"}:
                score += 1.5
            if signals["has_trade_score"] and tool.name == "write_audit_trail":
                score += 1.5

            scored.append((score, tool.name))

        selected: list[str] = []
        for name in always:
            if len(selected) >= max_tools:
                break
            if name not in selected:
                selected.append(name)

        for _, name in sorted(scored, key=lambda x: (x[0], x[1]), reverse=True):
            if len(selected) >= max_tools:
                break
            if name in selected:
                continue
            selected.append(name)

        # Audit: log tool selection scoring
        self._emit(
            EventType.TOOLS_SCORED,
            {
                "run_id": self._current_run_id,
                "scores": {name: score for score, name in sorted(scored, key=lambda x: x[0], reverse=True)},
                "signals": signals,
                "always_exposed": always,
                "selected": selected,
            },
        )

        if not selected:
            fallback = [
                "query_knowledge",
                "memory_search",
                "exa_search",
                "web_fetch",
                "fmp_get_financials",
                "fred_get_macro",
                "extract_observation",
                "create_hypothesis",
                "add_evidence_card",
                "run_valuation",
                "compute_trade_score",
                "write_audit_trail",
            ]
            selected = [n for n in fallback if n in self.tool_registry][:max_tools]

        return [self.tool_registry[name].schema for name in selected]

    def _recent_context_text(self, messages: list[dict]) -> str:
        considered = [m for m in messages if m.get("role") in {"user", "assistant", "tool"}]
        chunks = []
        for msg in considered[-3:]:  # short-term routing: only recent 3 messages
            content = msg.get("content")
            if isinstance(content, str):
                chunks.append(content[:1200])
        return "\n".join(chunks)

    def _detect_artifact_signals(self, text: str) -> dict:
        return {
            "has_observation": ("obs_" in text) or ("observation" in text),
            "has_hypothesis": ("hyp_" in text) or ("hypothesis" in text),
            "has_valuation": ("val_" in text) or ("valuation_id" in text),
            "has_trade_score": ("ts_" in text) or ("trade_score_id" in text),
        }

    def _tool_call_signature(self, tool_calls: list[ToolCall]) -> tuple:
        return tuple(
            (tc.name, json.dumps(tc.arguments, sort_keys=True, ensure_ascii=False))
            for tc in tool_calls
        )

    def _truncate_for_audit(self, obj, max_str: int = 2000, max_list: int = 10, max_depth: int = 4):
        """Truncate tool result data for audit logging. More generous than _deep_truncate."""
        if max_depth <= 0:
            return "...[depth limit]"
        if obj is None:
            return None
        if isinstance(obj, (int, float, bool)):
            return obj
        if isinstance(obj, str):
            if len(obj) > max_str:
                return obj[:max_str] + f"...[{len(obj)} chars total]"
            return obj
        if isinstance(obj, list):
            items = [self._truncate_for_audit(item, max_str, max_list, max_depth - 1) for item in obj[:max_list]]
            if len(obj) > max_list:
                items.append(f"...[{len(obj) - max_list} more items]")
            return items
        if isinstance(obj, dict):
            return {
                k: self._truncate_for_audit(v, max_str, max_list, max_depth - 1)
                for k, v in obj.items()
            }
        return str(obj)[:max_str]

    def _compress(self, result: dict, tool_name: str) -> dict:
        threshold = int(self.config.tool_compress_overrides.get(tool_name, self.config.compress_threshold_chars))
        payload = json.dumps(result, ensure_ascii=False)
        if len(payload) <= threshold:
            return result
        return self._deep_truncate(result)

    def _deep_truncate(self, obj, max_str: int = 500, max_list: int = 5):
        if isinstance(obj, str):
            return obj[:max_str] + f"...[{len(obj)} chars]" if len(obj) > max_str else obj
        if isinstance(obj, list):
            items = [self._deep_truncate(item, max_str=max_str, max_list=max_list) for item in obj[:max_list]]
            if len(obj) > max_list:
                items.append(f"...[{len(obj) - max_list} more]")
            return items
        if isinstance(obj, dict):
            return {k: self._deep_truncate(v, max_str=max_str, max_list=max_list) for k, v in obj.items()}
        return obj

    def _inject_steering(self, messages: list):
        while not self._steering_queue.empty():
            try:
                msg = self._steering_queue.get_nowait()
                messages.append({"role": "user", "content": f"[STEERING] {msg}"})
                self._emit(EventType.STEERING_INJECTED, {"run_id": self._current_run_id, "message": msg})
            except queue.Empty:
                break

    def _budget_policy(self) -> BudgetPolicy:
        return BudgetPolicy(
            max_tool_rounds=self.config.max_tool_rounds,
            max_total_tool_calls=self.config.max_total_tool_calls,
            max_wall_time_seconds=self.config.max_wall_time_seconds,
            include_flush_in_tool_rounds=self.config.include_flush_in_tool_rounds,
            include_compaction_in_tool_rounds=self.config.include_compaction_in_tool_rounds,
            pre_round_trim=self.config.pre_round_trim,
        )

    def _final_result(
        self,
        ok: bool,
        tool_log: list[dict],
        budget: BudgetTracker,
        reply: str | None = None,
        error: str | None = None,
    ) -> HarnessResult:
        self._emit(
            EventType.RUN_END,
            {
                "run_id": self._current_run_id,
                "ok": ok,
                "error": error,
                "budget": budget.breakdown(),
            },
        )
        return HarnessResult(
            ok=ok,
            reply=reply,
            tool_log=tool_log,
            error=error,
            total_input_tokens=budget.total_input_tokens,
            total_output_tokens=budget.total_output_tokens,
            budget_breakdown=budget.breakdown(),
            run_id=self._current_run_id,
        )

    def _track_embedding_usage(self, input_tokens: int = 0) -> None:
        if self._active_budget:
            self._active_budget.register_embedding_call(input_tokens=input_tokens)

    def _ensure_run_log_table(self):
        try:
            with sqlite3.connect(self._run_log_db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        data_json TEXT,
                        created_at REAL NOT NULL DEFAULT (julianday('now'))
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_run_log_run_id ON run_log(run_id);")
        except Exception:
            pass

    def _persist_event(self, event_type: str, data: dict):
        if not (self.config.persist_events and self._run_log_db_path and self._current_run_id):
            return
        try:
            payload = json.dumps(data or {}, ensure_ascii=False)
            with sqlite3.connect(self._run_log_db_path) as conn:
                conn.execute(
                    "INSERT INTO run_log (run_id, event_type, data_json) VALUES (?, ?, ?)",
                    (self._current_run_id, event_type, payload),
                )
        except Exception:
            pass

    def _emit(self, event_type: EventType, data: dict = None):
        payload = data or {}
        if self._current_run_id and "run_id" not in payload:
            payload["run_id"] = self._current_run_id
        self.on_event(HarnessEvent(type=event_type, data=payload))
        self._persist_event(event_type.value, payload)

    # Compatibility shims for existing tests/callers -----------------

    def _build_user_message(self, user_input: str, context_docs: list[str] = None) -> str:
        return self.context.build_user_message(user_input, context_docs)

    def _load_prior_context(self, subject: str = "") -> str:
        prior_messages = self.context.load_prior_context(subject, self.retriever)
        if not prior_messages:
            return ""
        return "\n\n".join(m.get("content", "") for m in prior_messages if m.get("content"))

    def _memory_flush(self, messages: list) -> None:
        budget = self._active_budget or BudgetTracker(self._budget_policy())
        knowledge_tools = [
            t for t in self.tool_registry.values()
            if t.name in {"extract_observation", "create_hypothesis", "add_evidence_card", "query_knowledge"}
        ]
        self.context.memory_flush(messages, knowledge_tools, budget)

    def _compact_context(self, messages: list) -> None:
        budget = self._active_budget or BudgetTracker(self._budget_policy())
        self.context.compact(messages, self.llm, budget)

    def _manage_context(self, messages: list) -> None:
        if self.context.should_compact(messages, self.config.context_limit_chars):
            before_len = len(messages)
            self._compact_context(messages)
            self._emit(
                EventType.CONTEXT_COMPACTED,
                {
                    "run_id": self._current_run_id,
                    "messages_before": before_len,
                    "messages_after": len(messages),
                },
            )
