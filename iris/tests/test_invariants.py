from core.invariants import InvariantChecker
from tools.base import ToolResult


def test_observation_requires_citation():
    checker = InvariantChecker()
    result = ToolResult.ok({"claim": "test", "source": "test", "citation": ""})
    violations = checker.check("extract_observation", result)
    assert len(violations) > 0
    assert any("citation" in v.lower() for v in violations)


def test_valid_observation_passes():
    checker = InvariantChecker()
    result = ToolResult.ok({
        "id": "obs_001", "claim": "Revenue up 30%",
        "source": "Earnings call", "citation": "Revenue was $5B, up 30% YoY",
    })
    violations = checker.check("extract_observation", result)
    assert len(violations) == 0


def test_trade_score_out_of_range():
    checker = InvariantChecker()
    result = ToolResult.ok({"constrained_score": 150, "recommendation": "WATCH"})
    violations = checker.check("compute_trade_score", result)
    assert len(violations) > 0


def test_failed_result_skips_invariant():
    checker = InvariantChecker()
    result = ToolResult.fail("something failed")
    violations = checker.check("extract_observation", result)
    assert violations == []
