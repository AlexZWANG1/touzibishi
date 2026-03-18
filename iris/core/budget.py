from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


BudgetCategory = Literal["main", "flush", "compaction", "embedding"]


@dataclass
class BudgetPolicy:
    max_tool_rounds: int = 25
    max_total_tool_calls: int = 60
    max_wall_time_seconds: float = 480.0
    include_flush_in_tool_rounds: bool = True
    include_compaction_in_tool_rounds: bool = True
    pre_round_trim: bool = True


@dataclass
class BudgetSnapshot:
    round_limit: int
    round_used: int
    tool_call_limit: int
    tool_call_used: int
    wall_time_limit_seconds: float
    wall_time_elapsed_seconds: float


class BudgetTracker:
    def __init__(self, policy: BudgetPolicy):
        self.policy = policy
        self.started_at = time.monotonic()

        self._counted_rounds = 0
        self._rounds_by_category = {"main": 0, "flush": 0, "compaction": 0, "embedding": 0}
        self._tool_calls_by_category = {"main": 0, "flush": 0, "compaction": 0, "embedding": 0}
        self._llm_calls_by_category = {"main": 0, "flush": 0, "compaction": 0, "embedding": 0}

        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def wall_time_exceeded(self) -> bool:
        return self.elapsed_seconds() >= float(self.policy.max_wall_time_seconds)

    def reserve_round(self, category: str) -> bool:
        counts_toward_limit = category == "main"
        if category == "flush" and self.policy.include_flush_in_tool_rounds:
            counts_toward_limit = True
        if category == "compaction" and self.policy.include_compaction_in_tool_rounds:
            counts_toward_limit = True

        if counts_toward_limit and self._counted_rounds >= self.policy.max_tool_rounds:
            return False

        self._rounds_by_category[category] = self._rounds_by_category.get(category, 0) + 1
        if counts_toward_limit:
            self._counted_rounds += 1
        return True

    def trim_tool_calls(self, requested: int) -> int:
        if requested <= 0:
            return 0
        if not self.policy.pre_round_trim:
            return requested
        return min(requested, self.remaining_tool_calls())

    def register_tool_calls(self, category: str, count: int) -> None:
        if count <= 0:
            return
        self._tool_calls_by_category[category] = self._tool_calls_by_category.get(category, 0) + count

    def register_llm_call(self, category: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._llm_calls_by_category[category] = self._llm_calls_by_category.get(category, 0) + 1
        self._total_input_tokens += int(input_tokens or 0)
        self._total_output_tokens += int(output_tokens or 0)

    def register_embedding_call(self, input_tokens: int = 0) -> None:
        self.register_llm_call("embedding", input_tokens=input_tokens, output_tokens=0)

    def remaining_tool_calls(self) -> int:
        return max(0, self.policy.max_total_tool_calls - self.total_tool_calls())

    def total_tool_calls(self) -> int:
        return sum(self._tool_calls_by_category.values())

    def tool_call_limit_reached(self) -> bool:
        return self.total_tool_calls() >= self.policy.max_total_tool_calls

    def round_limit_reached(self) -> bool:
        return self._counted_rounds >= self.policy.max_tool_rounds

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            round_limit=self.policy.max_tool_rounds,
            round_used=self._counted_rounds,
            tool_call_limit=self.policy.max_total_tool_calls,
            tool_call_used=self.total_tool_calls(),
            wall_time_limit_seconds=float(self.policy.max_wall_time_seconds),
            wall_time_elapsed_seconds=self.elapsed_seconds(),
        )

    def remaining_dict(self) -> dict:
        snap = self.snapshot()
        return {
            "tool_rounds": {
                "used": snap.round_used,
                "remaining": max(0, snap.round_limit - snap.round_used),
                "limit": snap.round_limit,
            },
            "tool_calls": {
                "used": snap.tool_call_used,
                "remaining": max(0, snap.tool_call_limit - snap.tool_call_used),
                "limit": snap.tool_call_limit,
            },
            "wall_time_seconds": {
                "elapsed": round(snap.wall_time_elapsed_seconds, 3),
                "remaining": max(0.0, snap.wall_time_limit_seconds - snap.wall_time_elapsed_seconds),
                "limit": snap.wall_time_limit_seconds,
            },
        }

    def breakdown(self) -> dict:
        return {
            "llm_calls": {
                "main": self._llm_calls_by_category.get("main", 0),
                "flush": self._llm_calls_by_category.get("flush", 0),
                "compaction": self._llm_calls_by_category.get("compaction", 0),
                "embedding": self._llm_calls_by_category.get("embedding", 0),
                "total": sum(self._llm_calls_by_category.values()),
            },
            "tool_calls": {
                "main": self._tool_calls_by_category.get("main", 0),
                "flush": self._tool_calls_by_category.get("flush", 0),
                "compaction": self._tool_calls_by_category.get("compaction", 0),
                "total": sum(self._tool_calls_by_category.values()),
                "limit": self.policy.max_total_tool_calls,
            },
            "tool_rounds": {
                "main": self._rounds_by_category.get("main", 0),
                "flush": self._rounds_by_category.get("flush", 0),
                "compaction": self._rounds_by_category.get("compaction", 0),
                "counted_total": self._counted_rounds,
                "limit": self.policy.max_tool_rounds,
                "include_flush_in_rounds": self.policy.include_flush_in_tool_rounds,
                "include_compaction_in_rounds": self.policy.include_compaction_in_tool_rounds,
            },
            "tokens": {
                "input": self._total_input_tokens,
                "output": self._total_output_tokens,
            },
            "elapsed_seconds": round(self.elapsed_seconds(), 3),
        }

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens
