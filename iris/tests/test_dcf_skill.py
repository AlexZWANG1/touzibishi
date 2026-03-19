"""Tests for skills/dcf/tools.py — build_dcf and get_comps."""

import pytest

from core.config import register_skill_config, reset_skill_configs
from skills.dcf.tools import build_dcf, get_comps, _revision_history, register


# ── Fixtures ─────────────────────────────────────────────────

DCF_CONFIG = {
    "max_projection_years": 10,
    "terminal_growth_max": 0.04,
    "wacc_range": [0.05, 0.20],
    "comps_outlier_threshold": 0.50,
    "sensitivity": {
        "wacc_steps": [-0.02, -0.01, 0, 0.01, 0.02],
        "growth_steps": [-0.01, -0.005, 0, 0.005, 0.01],
    },
}


@pytest.fixture(autouse=True)
def setup_dcf_config():
    """Register DCF config and clear revision history before each test."""
    reset_skill_configs()
    register_skill_config("dcf", DCF_CONFIG)
    _revision_history.clear()
    yield
    reset_skill_configs()
    _revision_history.clear()


def _base_assumptions(projection_years=3, **overrides):
    """Helper to build a minimal valid assumptions dict."""
    assumptions = {
        "company": "TestCorp",
        "ticker": "TEST",
        "projection_years": projection_years,
        "segments": [
            {
                "name": "Product A",
                "current_annual_revenue": 100_000_000,
                "growth_rates": [0.10, 0.08, 0.06][:projection_years],
                "reasoning": "Steady growth from existing customers",
            },
            {
                "name": "Product B",
                "current_annual_revenue": 50_000_000,
                "growth_rates": [0.20, 0.15, 0.10][:projection_years],
                "reasoning": "New market expansion",
            },
        ],
        "gross_margin": {"value": 0.60},
        "opex_pct_of_revenue": {"value": 0.20},
        "tax_rate": {"value": 0.21},
        "capex_pct_of_revenue": {"value": 0.05},
        "working_capital_change_pct": {"value": 0.01},
        "wacc": 0.10,
        "terminal_growth": 0.03,
        "net_cash": 10_000_000,
        "shares_outstanding": 10_000_000,
        "current_price": 50.0,
    }
    assumptions.update(overrides)
    return assumptions


# ── Basic DCF ────────────────────────────────────────────────

class TestBuildDCFBasic:
    def test_build_dcf_basic(self):
        """Minimal 2-segment, 3-year projection produces correct structure."""
        result = build_dcf(_base_assumptions())
        assert result.status == "ok"
        data = result.data

        assert "fair_value_per_share" in data
        assert "gap_pct" in data
        assert "year_by_year" in data
        assert len(data["year_by_year"]) == 3
        assert "terminal_value" in data
        assert "enterprise_value" in data
        assert "implied_multiples" in data
        assert "sensitivity" in data
        assert "revision_history" in data

        # Fair value should be positive
        assert data["fair_value_per_share"] > 0

        # Verify year-by-year structure
        for row in data["year_by_year"]:
            assert "year" in row
            assert "revenue" in row
            assert "fcf" in row
            assert "discounted_fcf" in row

        # Verify revenue grows correctly
        # Year 1: Product A = 100M * 1.10 = 110M, Product B = 50M * 1.20 = 60M, Total = 170M
        y1_revenue = data["year_by_year"][0]["revenue"]
        assert abs(y1_revenue - 170_000_000) < 1.0

    def test_fair_value_computation(self):
        """Verify the full DCF math manually for a simple case."""
        assumptions = _base_assumptions(
            projection_years=2,
            segments=[{
                "name": "Only",
                "current_annual_revenue": 100,
                "growth_rates": [0.10, 0.10],
                "reasoning": "test",
            }],
            gross_margin={"value": 0.50},
            opex_pct_of_revenue={"value": 0.10},
            tax_rate={"value": 0.20},
            capex_pct_of_revenue={"value": 0.05},
            working_capital_change_pct={"value": 0.01},
            wacc=0.10,
            terminal_growth=0.03,
            net_cash=0,
            shares_outstanding=1,
            current_price=100,
        )
        result = build_dcf(assumptions)
        assert result.status == "ok"
        data = result.data

        # Year 1: rev=110, gp=55, opex=11, ebit=44, tax=8.8, nopat=35.2
        #          da=5.5 (default=capex_pct), capex=5.5, dwc=1.1
        #          fcf = nopat + da - capex - dwc = 35.2 + 5.5 - 5.5 - 1.1 = 34.1
        # Year 2: rev=121, gp=60.5, opex=12.1, ebit=48.4, tax=9.68, nopat=38.72
        #          da=6.05, capex=6.05, dwc=1.21
        #          fcf = 38.72 + 6.05 - 6.05 - 1.21 = 37.51
        y1 = data["year_by_year"][0]
        assert abs(y1["revenue"] - 110.0) < 0.01
        assert abs(y1["fcf"] - 34.1) < 0.01

        y2 = data["year_by_year"][1]
        assert abs(y2["revenue"] - 121.0) < 0.01
        assert abs(y2["fcf"] - 37.51) < 0.01

        # TV = 37.51 * 1.03 / (0.10 - 0.03) = 37.51 * 1.03 / 0.07
        expected_tv = 37.51 * 1.03 / 0.07
        assert abs(data["terminal_value"] - expected_tv) < 0.1

    def test_single_segment(self):
        """Single segment company works correctly."""
        assumptions = _base_assumptions(
            segments=[{
                "name": "Core",
                "current_annual_revenue": 200_000_000,
                "growth_rates": [0.05, 0.05, 0.05],
                "reasoning": "Stable growth",
            }],
        )
        result = build_dcf(assumptions)
        assert result.status == "ok"
        assert len(result.data["year_by_year"]) == 3

    def test_zero_net_cash(self):
        """net_cash = 0 works (equity_value == enterprise_value)."""
        result = build_dcf(_base_assumptions(net_cash=0))
        assert result.status == "ok"
        data = result.data
        assert abs(data["enterprise_value"] - data["equity_value"]) < 0.01


# ── Validation errors ────────────────────────────────────────

class TestBuildDCFValidation:
    def test_terminal_growth_exceeds_wacc(self):
        """terminal_growth >= WACC produces error."""
        result = build_dcf(_base_assumptions(terminal_growth=0.10, wacc=0.10))
        assert result.status == "error"
        assert "terminal_growth" in result.error

        result2 = build_dcf(_base_assumptions(terminal_growth=0.12, wacc=0.10))
        assert result2.status == "error"
        assert "terminal_growth" in result2.error

    def test_wacc_out_of_range(self):
        """WACC outside config range produces error."""
        result = build_dcf(_base_assumptions(wacc=0.03))
        assert result.status == "error"
        assert "WACC" in result.error

        result2 = build_dcf(_base_assumptions(wacc=0.25))
        assert result2.status == "error"
        assert "WACC" in result2.error

    def test_empty_segments(self):
        """No segments produces error."""
        result = build_dcf(_base_assumptions(segments=[]))
        assert result.status == "error"
        assert "segments" in result.error.lower()

    def test_growth_rates_length_mismatch(self):
        """growth_rates length != projection_years produces error."""
        assumptions = _base_assumptions(
            segments=[{
                "name": "Bad",
                "current_annual_revenue": 100_000_000,
                "growth_rates": [0.10, 0.08],  # only 2, need 3
                "reasoning": "test",
            }],
        )
        result = build_dcf(assumptions)
        assert result.status == "error"
        assert "growth_rates" in result.error.lower() or "Bad" in result.error

    def test_missing_required_field(self):
        """Missing a required field produces error."""
        a = _base_assumptions()
        del a["wacc"]
        result = build_dcf(a)
        assert result.status == "error"
        assert "wacc" in result.error.lower()


# ── Sensitivity matrix ───────────────────────────────────────

class TestSensitivityMatrix:
    def test_sensitivity_matrix_shape(self):
        """Sensitivity matrix is 5x5."""
        result = build_dcf(_base_assumptions())
        assert result.status == "ok"
        matrix = result.data["sensitivity"]["matrix"]
        assert len(matrix) == 5
        for row in matrix:
            assert len(row) == 5

    def test_sensitivity_wacc_and_growth_values(self):
        """WACC and growth axes reflect config steps."""
        result = build_dcf(_base_assumptions())
        data = result.data["sensitivity"]
        assert len(data["wacc_values"]) == 5
        assert len(data["growth_values"]) == 5
        # Center value should be the base WACC/TG
        assert abs(data["wacc_values"][2] - 0.10) < 1e-6
        assert abs(data["growth_values"][2] - 0.03) < 1e-6

    def test_sensitivity_center_matches_base(self):
        """Center cell of sensitivity matrix matches base fair value."""
        result = build_dcf(_base_assumptions())
        data = result.data
        center_value = data["sensitivity"]["matrix"][2][2]
        assert abs(center_value - data["fair_value_per_share"]) < 0.01

    def test_sensitivity_higher_wacc_lower_value(self):
        """Higher WACC (row 4) should produce lower fair value than base (row 2)."""
        result = build_dcf(_base_assumptions())
        matrix = result.data["sensitivity"]["matrix"]
        center_col = 2
        # row 2 = base WACC, row 4 = base + 0.02
        base_val = matrix[2][center_col]
        high_wacc_val = matrix[4][center_col]
        assert high_wacc_val < base_val


# ── Scenario weighting ───────────────────────────────────────

class TestScenarioWeighting:
    def test_scenario_weighting(self):
        """Bull/bear scenarios produce weighted value."""
        scenarios = [
            {
                "name": "base",
                "probability": 0.5,
                "key_override": {},
            },
            {
                "name": "bull",
                "probability": 0.3,
                "key_override": {"gross_margin": {"value": 0.70}},
            },
            {
                "name": "bear",
                "probability": 0.2,
                "key_override": {"gross_margin": {"value": 0.45}},
            },
        ]
        result = build_dcf(_base_assumptions(scenarios=scenarios))
        assert result.status == "ok"
        assert result.data["scenario_weighted_value"] is not None
        assert result.data["scenario_weighted_value"] > 0

    def test_no_scenarios_returns_none(self):
        """No scenarios → scenario_weighted_value is None."""
        result = build_dcf(_base_assumptions())
        assert result.status == "ok"
        assert result.data["scenario_weighted_value"] is None


# ── Implied multiples ────────────────────────────────────────

class TestImpliedMultiples:
    def test_implied_multiples_present(self):
        """All four implied multiples are present."""
        result = build_dcf(_base_assumptions())
        assert result.status == "ok"
        m = result.data["implied_multiples"]
        assert "fwd_pe" in m
        assert "ev_ebitda" in m
        assert "fcf_yield" in m
        assert "peg_ratio" in m

    def test_implied_multiples_values(self):
        """Implied multiples have reasonable signs."""
        result = build_dcf(_base_assumptions())
        m = result.data["implied_multiples"]
        # With positive earnings and value, all should be positive
        assert m["fwd_pe"] > 0
        assert m["ev_ebitda"] > 0
        assert m["fcf_yield"] > 0
        assert m["peg_ratio"] > 0

    def test_fwd_pe_formula(self):
        """Fwd P/E = fair_value / (NOPAT_Y1 / shares)."""
        result = build_dcf(_base_assumptions())
        data = result.data
        nopat_y1 = data["year_by_year"][0]["nopat"]
        shares = 10_000_000
        expected_pe = data["fair_value_per_share"] / (nopat_y1 / shares)
        assert abs(data["implied_multiples"]["fwd_pe"] - round(expected_pe, 2)) < 0.01


# ── Revision history ─────────────────────────────────────────

class TestRevisionHistory:
    def test_revision_history_single_call(self):
        """One call → one revision entry."""
        result = build_dcf(_base_assumptions())
        assert result.status == "ok"
        history = result.data["revision_history"]
        assert len(history) == 1
        assert history[0]["round"] == 1
        assert history[0]["fair_value"] == result.data["fair_value_per_share"]
        assert history[0]["revision_reason"] is None

    def test_revision_history_two_calls(self):
        """Two calls → two entries with incrementing round numbers."""
        r1 = build_dcf(_base_assumptions())
        assert r1.status == "ok"

        r2 = build_dcf(_base_assumptions(
            gross_margin={"value": 0.70},
            revision_reason="Increased margin estimate after comps check",
        ))
        assert r2.status == "ok"

        history = r2.data["revision_history"]
        assert len(history) == 2
        assert history[0]["round"] == 1
        assert history[1]["round"] == 2
        assert history[1]["revision_reason"] == "Increased margin estimate after comps check"
        # Different margins → different fair values
        assert history[0]["fair_value"] != history[1]["fair_value"]


# ── Default values ───────────────────────────────────────────

class TestDefaultValues:
    def test_defaults_applied(self):
        """Optional params use defaults when omitted."""
        assumptions = {
            "company": "DefaultCo",
            "ticker": "DFLT",
            "projection_years": 2,
            "segments": [{
                "name": "Main",
                "current_annual_revenue": 1_000_000,
                "growth_rates": [0.05, 0.05],
                "reasoning": "test",
            }],
            "gross_margin": {"value": 0.50},
            "wacc": 0.10,
            "terminal_growth": 0.03,
            "net_cash": 0,
            "shares_outstanding": 100_000,
            "current_price": 10.0,
            # opex_pct_of_revenue, tax_rate, capex_pct_of_revenue,
            # working_capital_change_pct all omitted
        }
        result = build_dcf(assumptions)
        assert result.status == "ok"
        data = result.data

        # With defaults: opex=20%, tax=21%, capex=5%, wc=1%
        # Revenue Y1 = 1M * 1.05 = 1,050,000
        y1 = data["year_by_year"][0]
        rev = y1["revenue"]
        expected_rev = 1_000_000 * 1.05
        assert abs(rev - expected_rev) < 1.0

        # EBIT = rev * 0.50 - rev * 0.20 = rev * 0.30
        expected_ebit = rev * 0.30
        assert abs(y1["ebit"] - expected_ebit) < 1.0

        # NOPAT = EBIT * (1 - 0.21) = EBIT * 0.79
        expected_nopat = expected_ebit * 0.79
        assert abs(y1["nopat"] - expected_nopat) < 1.0

    def test_per_year_list_params(self):
        """Parameters can be passed as per-year lists."""
        assumptions = _base_assumptions(
            gross_margin=[0.60, 0.62, 0.64],
            opex_pct_of_revenue=[0.20, 0.19, 0.18],
        )
        result = build_dcf(assumptions)
        assert result.status == "ok"


# ── Registration ─────────────────────────────────────────────

class TestRegistration:
    def test_register_returns_tools(self):
        """register() returns a list of Tool objects."""
        tools = register({})
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert "build_dcf" in names
        assert "get_comps" in names

    def test_tools_have_schemas(self):
        """Each tool has a valid schema."""
        tools = register({})
        for tool in tools:
            assert "function" in tool.schema
            assert "name" in tool.schema["function"]
            assert "parameters" in tool.schema["function"]
