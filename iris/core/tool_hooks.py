from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from tools.base import ToolResult


@dataclass
class ToolHookContext:
    tool_name: str
    args: dict
    run_id: str
    round_number: int
    budget_remaining: dict


class ToolHooks:
    def before_tool_call(self, ctx: ToolHookContext) -> Optional[ToolHookContext]:
        return ctx

    def after_tool_call(self, ctx: ToolHookContext, result: ToolResult) -> ToolResult:
        return result


class DefaultToolHooks(ToolHooks):
    def before_tool_call(self, ctx: ToolHookContext) -> Optional[ToolHookContext]:
        if not isinstance(ctx.args, dict):
            return None

        normalized = {}
        for key, value in ctx.args.items():
            if isinstance(value, str):
                normalized[key] = value.strip()
            else:
                normalized[key] = value

        try:
            json.dumps(normalized, ensure_ascii=False)
        except Exception:
            return None

        ctx.args = normalized
        return ctx

    def after_tool_call(self, ctx: ToolHookContext, result: ToolResult) -> ToolResult:
        if result.status == "ok":
            return result

        error_text = (result.error or "").lower()
        tag = "unknown_error"
        if any(x in error_text for x in ("timeout", "timed out")):
            tag = "timeout"
        elif any(x in error_text for x in ("429", "rate_limit", "overload", "503", "network", "connection")):
            tag = "network_error"
        elif any(x in error_text for x in ("not found", "invalid", "schema", "argument", "parse", "json", "valueerror")):
            tag = "data_error"

        if tag not in result.tags:
            result.tags.append(tag)
        return result
