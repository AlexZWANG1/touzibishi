import os
import pytest
from dotenv import load_dotenv
load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Integration tests require OPENAI_API_KEY"
)


def test_full_pipeline_runs_without_crash(tmp_path):
    from main import build_harness
    harness, retriever = build_harness(str(tmp_path / "test.db"))
    result = harness.run(
        "Quick analysis: Is NVDA a buy? Keep it brief.",
        context_docs=["NVDA reported strong data center revenue growth in Q4 2025."]
    )
    assert result is not None
    assert isinstance(result.ok, bool)
    assert isinstance(result.tool_log, list)


def test_guard_prevents_bad_valuation():
    from guards.guards import InvestmentGuards
    guards = InvestmentGuards()
    result = guards.check("run_valuation", {
        "wacc": 0.99, "terminal_growth_rate": 0.02, "reasoning": "test",
        "hypothesis_id": "hyp_001", "methodology": "DCF",
        "methodology_reasoning": "test", "fair_value_low": 100.0,
        "fair_value_high": 130.0, "current_price": 90.0,
        "key_assumptions": [], "bull_case_value": 130.0,
        "bull_case_assumption": "high", "bear_case_value": 100.0,
        "bear_case_assumption": "low",
    })
    assert result.blocked
    assert "WACC" in result.error
