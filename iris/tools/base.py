from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    status: str
    data: Any = None
    error: Optional[str] = None
    hint: Optional[str] = None
    recoverable: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        if self.status == "ok":
            payload = {"status": "ok", "data": self.data}
            if self.tags:
                payload["tags"] = self.tags
            return payload
        payload = {
            "status": "error",
            "error": self.error,
            "hint": self.hint,
            "recoverable": self.recoverable,
        }
        if self.tags:
            payload["tags"] = self.tags
        return payload

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        return cls(status="ok", data=data)

    @classmethod
    def fail(cls, error: str, hint: str = None, recoverable: bool = True) -> "ToolResult":
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


class Tool:
    """Wraps a tool function with its OpenAI schema.

    Metadata attributes (set at registration, not hardcoded centrally):
      panel_type:    Frontend panel extraction method name, e.g. "valuation", "quote".
                     None means no panel extraction needed.
      is_knowledge:  True if this tool persists knowledge that must be flushed
                     before context compaction (e.g. remember, create_hypothesis).
    """

    def __init__(self, fn, schema: dict, retriever=None, *,
                 panel_type: str | None = None, is_knowledge: bool = False):
        self.fn = fn
        self.schema = schema
        self.name = schema["function"]["name"]
        self.retriever = retriever
        self.panel_type = panel_type
        self.is_knowledge = is_knowledge

    def execute(self, args: dict) -> ToolResult:
        if self.retriever:
            return self.fn(retriever=self.retriever, **args)
        return self.fn(**args)
