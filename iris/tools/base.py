from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    status: str
    data: Any = None
    error: Optional[str] = None
    hint: Optional[str] = None
    recoverable: bool = True

    def to_dict(self) -> dict:
        if self.status == "ok":
            return {"status": "ok", "data": self.data}
        return {
            "status": "error",
            "error": self.error,
            "hint": self.hint,
            "recoverable": self.recoverable,
        }

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        return cls(status="ok", data=data)

    @classmethod
    def error(cls, error: str, hint: str = None, recoverable: bool = True) -> "ToolResult":
        return cls(status="error", error=error, hint=hint, recoverable=recoverable)


def make_tool_schema(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# ── Phase-based tool injection ─────────────────────────────────

TOOL_PHASES = {
    "gather":   {"exa_search", "web_fetch", "fmp_get_financials", "fred_get_macro",
                 "extract_observation", "create_hypothesis", "query_knowledge"},
    "analyze":  {"exa_search", "web_fetch", "fmp_get_financials", "fred_get_macro",
                 "extract_observation", "add_evidence_card", "create_hypothesis",
                 "query_knowledge"},
    "evaluate": {"add_evidence_card", "run_valuation", "compute_trade_score",
                 "query_knowledge"},
    "finalize": {"write_audit_trail", "query_knowledge"},
}

PHASE_ORDER = ["gather", "analyze", "evaluate", "finalize"]

PHASE_TRANSITIONS = {
    "create_hypothesis": "analyze",
    "run_valuation":     "evaluate",
    "write_audit_trail": "finalize",
}


class Tool:
    """Wraps a tool function with its OpenAI schema."""

    def __init__(self, fn, schema: dict, retriever=None):
        self.fn = fn
        self.schema = schema
        self.name = schema["function"]["name"]
        self.retriever = retriever

    def execute(self, args: dict) -> ToolResult:
        if self.retriever:
            return self.fn(retriever=self.retriever, **args)
        return self.fn(**args)
