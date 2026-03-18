from guards.guards import InvestmentGuards


def test_wacc_out_of_range_blocked():
    g = InvestmentGuards()
    result = g.check("run_valuation", {"wacc": 0.35, "terminal_growth_rate": 0.03, "reasoning": "test"})
    assert result.blocked
    assert "WACC" in result.error


def test_terminal_growth_exceeds_wacc_blocked():
    g = InvestmentGuards()
    result = g.check("run_valuation", {"wacc": 0.08, "terminal_growth_rate": 0.10, "reasoning": "test"})
    assert result.blocked


def test_valid_valuation_passes():
    g = InvestmentGuards()
    result = g.check("run_valuation", {"wacc": 0.10, "terminal_growth_rate": 0.025, "reasoning": "Valid DCF assumptions"})
    assert not result.blocked


def test_add_evidence_requires_hypothesis_id():
    g = InvestmentGuards()
    result = g.check("add_evidence_card", {"observation_id": "obs_001", "direction": "supports", "reasoning": "test"})
    assert result.blocked


def test_compute_trade_score_requires_reasoning():
    g = InvestmentGuards()
    result = g.check("compute_trade_score", {
        "hypothesis_id": "hyp_001", "valuation_id": "val_001",
        "fundamental_quality": 0.8, "catalyst_timing": 0.7, "risk_penalty": 0.2, "reasoning": "",
    })
    assert result.blocked


def test_unknown_tool_passes_guards():
    g = InvestmentGuards()
    result = g.check("perplexity_search", {"query": "NVDA earnings"})
    assert not result.blocked
