from tools.base import ToolResult


class InvariantChecker:
    """
    Layer 1 hard constraints checked AFTER tool execution.
    Guards handle pre-execution; invariants are the post-execution safety net.
    Returns list of violation strings (empty = all good).
    """

    def check(self, tool_name: str, result: ToolResult) -> list[str]:
        if result.status != "ok":
            return []
        handler = getattr(self, f"_check_{tool_name}", None)
        if handler:
            return handler(result.data)
        return []

    def _check_extract_observation(self, data: dict) -> list[str]:
        violations = []
        if not data.get("citation", "").strip():
            violations.append("INVARIANT: extract_observation result missing citation")
        return violations

    def _check_run_valuation(self, data: dict) -> list[str]:
        violations = []
        if data.get("bull_case") is None or data.get("bear_case") is None:
            violations.append("INVARIANT: valuation must have both bull and bear case")
        return violations

    def _check_compute_trade_score(self, data: dict) -> list[str]:
        violations = []
        score = data.get("constrained_score", 0)
        if not (0 <= score <= 100):
            violations.append(f"INVARIANT: constrained_score {score} out of [0, 100]")
        return violations
