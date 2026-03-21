"""
Fundamentals Skill — Deep Research methodology.

Tools: emit_research_section (UI data channel only)
"""

from tools.base import Tool, ToolResult, make_tool_schema


EMIT_RESEARCH_SECTION_SCHEMA = make_tool_schema(
    name="emit_research_section",
    description=(
        "Push a completed research section to the research panel. "
        "Call this after finishing each research step so the user sees progress in real time. "
        "Title is free-form — name it after the section's core topic."
    ),
    properties={
        "title": {
            "type": "string",
            "description": "Section title, e.g. '生意本质', '技术拆解', '竞争格局', '投资观点'",
        },
        "content": {
            "type": "string",
            "description": "Section content in markdown format",
        },
    },
    required=["title", "content"],
)


def emit_research_section(title: str, content: str) -> ToolResult:
    """Pure UI channel — no logic, just pass data through to frontend."""
    return ToolResult.ok({"title": title, "content": content})


def register(context: dict) -> list[Tool]:
    return [
        Tool(emit_research_section, EMIT_RESEARCH_SECTION_SCHEMA),
    ]
