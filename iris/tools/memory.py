"""
IRIS Memory System — file-based persistent memory for research compounding.

Three tools:
  - recall_memory: Read a memory file
  - save_memory: Write a memory file (+ calibration log for company type)
  - check_calibration: Review prediction accuracy and bias
"""

import json
from datetime import datetime, date
from pathlib import Path

from core.config import get as config_get
from tools.base import ToolResult, make_tool_schema


# ── Path mapping ──────────────────────────────────────────────

_TYPE_DIR_MAP = {
    "company": "companies",
    "sector": "sectors",
    "patterns": "patterns",
    "calibration": "calibration",
}


def _memory_base() -> Path:
    base = config_get("memory.base_dir", "./memory")
    return Path(base)


def _resolve_path(memory_type: str, company: str) -> Path | None:
    dir_name = _TYPE_DIR_MAP.get(memory_type)
    if not dir_name:
        return None
    base = _memory_base()
    if memory_type == "calibration":
        return base / dir_name / "prediction_log.jsonl"
    return base / dir_name / f"{company}.md"


# ── Schemas ───────────────────────────────────────────────────

RECALL_MEMORY_SCHEMA = make_tool_schema(
    name="recall_memory",
    description=(
        "Recall what you know about a company or sector from previous analysis sessions. "
        "Always call this at the start of any analysis to check for prior research."
    ),
    properties={
        "company": {"type": "string", "description": "Company ticker or sector/pattern name"},
        "memory_type": {
            "type": "string",
            "enum": ["company", "sector", "patterns", "calibration"],
            "description": "Type of memory to recall",
        },
    },
    required=["company", "memory_type"],
)

SAVE_MEMORY_SCHEMA = make_tool_schema(
    name="save_memory",
    description=(
        "Save analysis conclusions to memory for future sessions. "
        "Call at the end of analysis to persist key findings."
    ),
    properties={
        "company": {"type": "string", "description": "Company ticker or sector/pattern name"},
        "memory_type": {
            "type": "string",
            "enum": ["company", "sector", "patterns"],
            "description": "Type of memory to save",
        },
        "content": {"type": "string", "description": "Markdown content to save"},
    },
    required=["company", "memory_type", "content"],
)

CHECK_CALIBRATION_SCHEMA = make_tool_schema(
    name="check_calibration",
    description=(
        "Check prediction accuracy and bias patterns. "
        "Use to identify systematic over/under-estimation tendencies."
    ),
    properties={
        "company": {
            "type": "string",
            "description": "Filter by company ticker. Omit for all companies.",
        },
    },
    required=[],
)


# ── Tool implementations ─────────────────────────────────────

def recall_memory(company: str, memory_type: str) -> ToolResult:
    path = _resolve_path(memory_type, company)
    if path is None:
        return ToolResult.fail(
            f"Unknown memory_type: {memory_type}",
            hint="Use one of: company, sector, patterns, calibration",
        )

    if memory_type == "calibration":
        return _recall_calibration(company, path)

    if not path.exists():
        return ToolResult.ok({
            "content": None,
            "message": f"No prior memory for {company}",
        })

    content = path.read_text(encoding="utf-8")
    rel_path = path.relative_to(_memory_base()).as_posix()
    return ToolResult.ok({"content": content, "path": rel_path})


def _recall_calibration(company: str, path: Path) -> ToolResult:
    if not path.exists():
        return ToolResult.ok({
            "content": None,
            "message": f"No calibration data for {company}",
        })
    entries = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if company and entry.get("company") != company:
            continue
        entries.append(entry)
    return ToolResult.ok({
        "content": entries if entries else None,
        "message": f"Found {len(entries)} calibration entries for {company}" if entries else f"No calibration data for {company}",
    })


def save_memory(company: str, memory_type: str, content: str) -> ToolResult:
    if memory_type == "calibration":
        return ToolResult.fail(
            "Cannot directly write to calibration log",
            hint="Calibration entries are created automatically when saving company memory",
        )

    path = _resolve_path(memory_type, company)
    if path is None:
        return ToolResult.fail(
            f"Unknown memory_type: {memory_type}",
            hint="Use one of: company, sector, patterns",
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    # Auto-create calibration entry for company memory
    if memory_type == "company":
        _append_calibration_entry(company, content)

    rel_path = path.relative_to(_memory_base()).as_posix()
    return ToolResult.ok({"status": "ok", "path": rel_path})


def _append_calibration_entry(company: str, content: str):
    """Append calibration entry using DB valuation, not regex."""
    from tools.retrieval import SQLiteRetriever
    from core.config import DB_PATH
    retriever = SQLiteRetriever(DB_PATH)
    val = retriever.get_latest_valuation(company)
    if val is None:
        return  # No valuation exists, nothing to calibrate

    # Parse fair_value from the valuation data JSON
    val_data = val.get("data")
    predicted = None
    if val_data and isinstance(val_data, str):
        try:
            parsed = json.loads(val_data)
            predicted = parsed.get("fair_value")
        except (json.JSONDecodeError, TypeError):
            pass
    elif val_data and isinstance(val_data, dict):
        predicted = val_data.get("fair_value")

    if predicted is None:
        return

    entry = {
        "date": date.today().isoformat(),
        "company": company,
        "metric": "fair_value",
        "predicted": predicted,
        "actual": None,
        "analyst_consensus": None,
        "note": "pending 90-day review",
    }
    log_path = _memory_base() / "calibration" / "prediction_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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

    # Generate bias note
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
    """Count consecutive errors in the same direction from the end."""
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
