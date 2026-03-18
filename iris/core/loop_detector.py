from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class LoopDetectionConfig:
    generic_repeat_threshold: int = 3
    ping_pong_threshold: int = 3
    no_progress_threshold: int = 3
    action: str = "steer_then_stop"  # steer_then_stop | hard_stop | warn_only


@dataclass
class LoopSignal:
    detector_names: list[str]
    message: str
    should_steer: bool
    should_stop: bool


class LoopDetector:
    def __init__(self, config: LoopDetectionConfig):
        self.config = config

        self._last_signature = None
        self._generic_repeat_count = 0

        self._signature_history: list[tuple] = []
        self._ping_pong_count = 0

        self._last_result_hash: Optional[str] = None
        self._no_progress_count = 0

        self._consecutive_trigger_rounds = 0

    def inspect_tool_signature(self, signature: tuple) -> set[str]:
        detectors: set[str] = set()

        if signature == self._last_signature:
            self._generic_repeat_count += 1
        else:
            self._generic_repeat_count = 1
        self._last_signature = signature
        if self._generic_repeat_count >= self.config.generic_repeat_threshold:
            detectors.add("generic_repeat")

        if len(self._signature_history) >= 2:
            if signature == self._signature_history[-2] and signature != self._signature_history[-1]:
                self._ping_pong_count += 1
            else:
                self._ping_pong_count = 0
            if self._ping_pong_count >= self.config.ping_pong_threshold:
                detectors.add("ping_pong")

        self._signature_history.append(signature)
        if len(self._signature_history) > 12:
            self._signature_history = self._signature_history[-12:]

        return detectors

    def inspect_tool_results(self, tool_results: list[dict]) -> set[str]:
        detectors: set[str] = set()
        digest = self._hash_payload(tool_results)

        if digest == self._last_result_hash:
            self._no_progress_count += 1
        else:
            self._no_progress_count = 1
        self._last_result_hash = digest

        if self._no_progress_count >= self.config.no_progress_threshold:
            detectors.add("no_progress_poll")

        return detectors

    def resolve_round(self, detectors: set[str]) -> Optional[LoopSignal]:
        if not detectors:
            self._consecutive_trigger_rounds = 0
            return None

        self._consecutive_trigger_rounds += 1
        ordered = sorted(detectors)
        message = f"Loop detector triggered: {', '.join(ordered)}"

        if self.config.action == "hard_stop":
            return LoopSignal(ordered, message, should_steer=False, should_stop=True)

        if self.config.action == "warn_only":
            return LoopSignal(ordered, message, should_steer=False, should_stop=False)

        # steer_then_stop
        if self._consecutive_trigger_rounds >= 2:
            return LoopSignal(ordered, message, should_steer=True, should_stop=True)
        return LoopSignal(ordered, message, should_steer=True, should_stop=False)

    def status(self) -> dict:
        return {
            "generic_repeat_count": self._generic_repeat_count,
            "ping_pong_count": self._ping_pong_count,
            "no_progress_count": self._no_progress_count,
            "consecutive_trigger_rounds": self._consecutive_trigger_rounds,
            "action": self.config.action,
        }

    def _hash_payload(self, payload) -> str:
        try:
            normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except TypeError:
            normalized = str(payload)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
