"""
Calibration check — used by the /api/calibration endpoint.

Not registered as an LLM tool; called directly by the backend API.
"""

import json
from pathlib import Path

from core.config import get as config_get
from tools.base import ToolResult


def _memory_base() -> Path:
    base = config_get("memory.base_dir", "./memory")
    return Path(base)


def check_calibration(company: str = None) -> ToolResult:
    log_path = _memory_base() / "calibration" / "prediction_log.jsonl"
    if not log_path.exists():
        return ToolResult.ok({
            "entries": [],
            "summary": {
                "totalPredictions": 0,
                "resolvedPredictions": 0,
                "averageError": None,
                "biasDirection": "balanced",
                "biasNote": "No predictions yet",
            },
        })

    entries = []
    for line in log_path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if company and entry.get("company") != company:
            continue
        entries.append(entry)

    total = len(entries)
    resolved = [e for e in entries if e.get("actual") is not None]
    resolved_count = len(resolved)

    if resolved_count == 0:
        return ToolResult.ok({
            "entries": entries,
            "summary": {
                "totalPredictions": total,
                "resolvedPredictions": 0,
                "averageError": None,
                "biasDirection": "balanced",
                "biasNote": f"{total} predictions pending review",
            },
        })

    errors = []
    for e in resolved:
        predicted = e["predicted"]
        actual = e["actual"]
        if actual and actual != 0:
            error_pct = (predicted - actual) / actual
            errors.append(error_pct)

    avg_error = sum(errors) / len(errors) if errors else 0.0

    if avg_error > 0.02:
        bias_direction = "overestimate"
    elif avg_error < -0.02:
        bias_direction = "underestimate"
    else:
        bias_direction = "balanced"

    bias_note = f"Average error: {avg_error:.1%}"
    consecutive_same = _count_consecutive_same_direction(errors)
    if consecutive_same >= 3:
        direction_word = "高估" if avg_error > 0 else "低估"
        pct_range = f"{abs(min(errors[-consecutive_same:])):.0%}-{abs(max(errors[-consecutive_same:])):.0%}"
        bias_note = f"连续 {consecutive_same} 次{direction_word} {pct_range}"

    return ToolResult.ok({
        "entries": entries,
        "summary": {
            "totalPredictions": total,
            "resolvedPredictions": resolved_count,
            "averageError": round(avg_error, 4),
            "biasDirection": bias_direction,
            "biasNote": bias_note,
        },
    })


def _count_consecutive_same_direction(errors: list[float]) -> int:
    if not errors:
        return 0
    last_sign = 1 if errors[-1] > 0 else -1
    count = 0
    for e in reversed(errors):
        if (e > 0 and last_sign > 0) or (e < 0 and last_sign < 0):
            count += 1
        else:
            break
    return count
