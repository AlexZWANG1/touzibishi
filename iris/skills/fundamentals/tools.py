"""
Fundamentals Skill — Deep Research methodology.

Tools: emit_report (UI data channel only)
"""

from tools.base import Tool, ToolResult, make_tool_schema


EMIT_REPORT_SCHEMA = make_tool_schema(
    name="emit_report",
    description=(
        "Output a completed research report to the research panel. "
        "Call this ONCE after finishing all research — do NOT call multiple times. "
        "Title is free-form. Content is a full markdown report (1500-2500 words)."
    ),
    properties={
        "title": {
            "type": "string",
            "description": "Report title, e.g. 'AI芯片行业竞争格局深度研究'",
        },
        "content": {
            "type": "string",
            "description": "Full report content in markdown format (1500-2500 words)",
        },
    },
    required=["title", "content"],
)


def emit_report(title: str, content: str) -> ToolResult:
    """Pure UI channel — no logic, just pass data through to frontend."""
    return ToolResult.ok({"title": title, "content": content})


def register(context: dict) -> list[Tool]:
    return [
        Tool(emit_report, EMIT_REPORT_SCHEMA),
    ]
