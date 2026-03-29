"""
DCF Valuation Skill — build_dcf and get_comps tools.

build_dcf: Full discounted cash flow engine with segment-level revenue,
           sensitivity matrix, scenario weighting, and revision history.
get_comps: Peer comparison via FMP API for cross-checking implied multiples.
"""

from datetime import date
from typing import Any

from core.config import get_skill_config
from tools.base import Tool, ToolResult, make_tool_schema


# ── Revision history (module-level, persists across calls in same session) ──

_revision_history: list[dict] = []


# ── Tool Schemas ─────────────────────────────────────────────

BUILD_DCF_SCHEMA = make_tool_schema(
    name="build_dcf",
    description=(
        "Build a full DCF valuation model. Returns fair value per share, implied multiples, "
        "sensitivity matrix, and year-by-year projections.\n\n"
        "FCF formula: NOPAT + D&A - CapEx - ΔWC (unlevered free cash flow).\n\n"
        "Example call:\n"
        '{"assumptions": {\n'
        '  "company": "NVIDIA", "ticker": "NVDA", "projection_years": 5,\n'
        '  "segments": [\n'
        '    {"name": "Data Center", "current_annual_revenue": 115000,\n'
        '     "growth_rates": [0.45, 0.30, 0.22, 0.18, 0.15],\n'
        '     "reasoning": "AI infrastructure demand"},\n'
        '    {"name": "Gaming", "current_annual_revenue": 12000,\n'
        '     "growth_rates": [0.10, 0.08, 0.06, 0.05, 0.04],\n'
        '     "reasoning": "Mature segment"}\n'
        '  ],\n'
        '  "gross_margin": {"value": 0.73},\n'
        '  "opex_pct_of_revenue": {"value": 0.12},\n'
        '  "da_pct_of_revenue": {"value": 0.05},\n'
        '  "wacc": 0.11, "terminal_growth": 0.03,\n'
        '  "tax_rate": {"value": 0.12},\n'
        '  "capex_pct_of_revenue": {"value": 0.07},\n'
        '  "working_capital_change_pct": {"value": 0.015},\n'
        '  "shares_outstanding": 24500, "net_cash": 30000,\n'
        '  "current_price": 135.0\n'
        "}}\n\n"
        "Each segment needs exactly projection_years growth_rates entries. "
        "da_pct_of_revenue is D&A as fraction of revenue (depreciationAndAmortization / revenue)."
    ),
    properties={
        "assumptions": {
            "type": "object",
            "description": (
                "All DCF assumptions.\n\n"
                "Required fields:\n"
                "  company (str), ticker (str), projection_years (int),\n"
                "  segments (array of {name, current_annual_revenue (in $M, matching financials output), "
                "growth_rates: [float per year], reasoning}),\n"
                "  gross_margin ({value: float}), wacc (float 0.05-0.20), "
                "terminal_growth (float, must be < wacc),\n"
                "  net_cash (float, $M — = cashAndShortTermInvestments - totalDebt from balance sheet; "
                "negative means net debt, pass the negative number),\n"
                "  shares_outstanding (float — ACTUAL SHARE COUNT, not in millions; "
                "get from income-statement weightedAverageShsOutDil),\n"
                "  current_price (float).\n\n"
                "Optional fields:\n"
                "  opex_pct_of_revenue, tax_rate, capex_pct_of_revenue,\n"
                "  da_pct_of_revenue (D&A / revenue — from cash-flow-statement depreciationAndAmortization / revenue; "
                "if omitted, defaults to capex_pct which may overstate D&A for companies in heavy investment phases),\n"
                "  working_capital_change_pct (all as {value: float} or [float per year]),\n"
                "  scenarios (array for probability-weighted analysis)."
            ),
        },
    },
    required=["assumptions"],
)

GET_COMPS_SCHEMA = make_tool_schema(
    name="get_comps",
    description=(
        "Get peer comparison multiples for a target company. Fetches Fwd P/E, EV/EBITDA, "
        "revenue growth, and gross margin for the target and each peer. Computes median "
        "and target-vs-median premium/discount."
    ),
    properties={
        "ticker": {"type": "string", "description": "Target company ticker, e.g. 'NVDA'"},
        "peers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of peer tickers, e.g. ['AMD', 'INTC', 'AVGO']",
        },
    },
    required=["ticker", "peers"],
)


# ── Helpers ──────────────────────────────────────────────────

def _resolve_per_year(param: Any, n_years: int, default_value: float) -> list[float]:
    """Resolve a parameter that can be a single-value dict, a list, or None."""
    if param is None:
        return [default_value] * n_years
    if isinstance(param, dict):
        return [param.get("value", default_value)] * n_years
    if isinstance(param, list):
        return [float(v) for v in param]
    # scalar fallback
    return [float(param)] * n_years


def _resolve_tax_rate(param: Any, n_years: int) -> list[float]:
    """Resolve tax rate — can be dict with 'value', list, or None."""
    default = 0.21
    if param is None:
        return [default] * n_years
    if isinstance(param, dict):
        return [param.get("value", default)] * n_years
    if isinstance(param, list):
        return [float(v) for v in param]
    return [float(param)] * n_years


# ── build_dcf implementation ─────────────────────────────────

def build_dcf(assumptions: dict) -> ToolResult:
    """Full DCF engine."""
    cfg = get_skill_config("dcf")
    wacc_range = cfg.get("wacc_range", [0.05, 0.20])
    sensitivity_cfg = cfg.get("sensitivity", {})
    wacc_steps = sensitivity_cfg.get("wacc_steps", [-0.02, -0.01, 0, 0.01, 0.02])
    growth_steps = sensitivity_cfg.get("growth_steps", [-0.01, -0.005, 0, 0.005, 0.01])

    # ── Extract required fields ──
    required_fields = [
        "company", "ticker", "projection_years", "segments",
        "gross_margin", "wacc", "terminal_growth",
        "net_cash", "shares_outstanding", "current_price",
    ]
    for field in required_fields:
        if field not in assumptions:
            return ToolResult.fail(
                f"Missing required field: {field}",
                hint=f"Add '{field}' to assumptions dict",
            )

    company = assumptions["company"]
    ticker = assumptions["ticker"]
    projection_years = int(assumptions["projection_years"])
    segments = assumptions["segments"]
    wacc = float(assumptions["wacc"])
    terminal_growth = float(assumptions["terminal_growth"])
    net_cash = float(assumptions["net_cash"])
    shares_outstanding = float(assumptions["shares_outstanding"])
    current_price = float(assumptions["current_price"])
    analysis_date = assumptions.get("analysis_date", date.today().isoformat())
    scenarios = assumptions.get("scenarios", [])

    # ── Validation ──
    if not segments:
        return ToolResult.fail(
            "segments must not be empty",
            hint="Provide at least one revenue segment with growth rates",
        )

    if terminal_growth >= wacc:
        return ToolResult.fail(
            f"terminal_growth ({terminal_growth}) must be less than WACC ({wacc})",
            hint="Terminal growth rate should be below WACC for the model to converge",
        )

    if wacc < wacc_range[0] or wacc > wacc_range[1]:
        return ToolResult.fail(
            f"WACC ({wacc}) outside allowed range [{wacc_range[0]}, {wacc_range[1]}]",
            hint="Adjust WACC to be within the configured range",
        )

    for seg in segments:
        if len(seg.get("growth_rates", [])) != projection_years:
            return ToolResult.fail(
                f"Segment '{seg.get('name', '?')}' has {len(seg.get('growth_rates', []))} "
                f"growth_rates but projection_years is {projection_years}",
                hint="Each segment's growth_rates list must have exactly projection_years entries",
            )

    # ── Resolve per-year parameters ──
    gross_margin = _resolve_per_year(assumptions["gross_margin"], projection_years, 0.50)
    opex_pct = _resolve_per_year(
        assumptions.get("opex_pct_of_revenue"), projection_years, 0.20
    )
    tax_rate = _resolve_tax_rate(assumptions.get("tax_rate"), projection_years)
    capex_pct = _resolve_per_year(
        assumptions.get("capex_pct_of_revenue"), projection_years, 0.05
    )
    # D&A as pct of revenue — defaults to capex_pct if not provided (steady-state assumption)
    da_default = capex_pct[0] if capex_pct else 0.05
    da_pct = _resolve_per_year(
        assumptions.get("da_pct_of_revenue"), projection_years, da_default
    )
    wc_change_pct = _resolve_per_year(
        assumptions.get("working_capital_change_pct"), projection_years, 0.01
    )

    # ── Compute base-case DCF ──
    result = _compute_dcf(
        segments=segments,
        projection_years=projection_years,
        gross_margin=gross_margin,
        opex_pct=opex_pct,
        tax_rate=tax_rate,
        capex_pct=capex_pct,
        da_pct=da_pct,
        wc_change_pct=wc_change_pct,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_cash=net_cash,
        shares_outstanding=shares_outstanding,
        current_price=current_price,
    )

    # ── Sensitivity matrix ──
    sensitivity_wacc_values = [wacc + step for step in wacc_steps]
    sensitivity_growth_values = [terminal_growth + step for step in growth_steps]
    sensitivity_matrix = []
    for w in sensitivity_wacc_values:
        row = []
        for g in sensitivity_growth_values:
            if g >= w:
                row.append(None)  # invalid combo
            else:
                sv = _compute_dcf(
                    segments=segments,
                    projection_years=projection_years,
                    gross_margin=gross_margin,
                    opex_pct=opex_pct,
                    tax_rate=tax_rate,
                    capex_pct=capex_pct,
                    da_pct=da_pct,
                    wc_change_pct=wc_change_pct,
                    wacc=w,
                    terminal_growth=g,
                    net_cash=net_cash,
                    shares_outstanding=shares_outstanding,
                    current_price=current_price,
                )
                row.append(round(sv["fair_value_per_share"], 2))
        sensitivity_matrix.append(row)

    result["sensitivity"] = {
        "wacc_values": [round(v, 4) for v in sensitivity_wacc_values],
        "growth_values": [round(v, 4) for v in sensitivity_growth_values],
        "matrix": sensitivity_matrix,
    }

    # ── Scenario weighting ──
    scenario_weighted_value = None
    if scenarios:
        weighted_sum = 0.0
        for scenario in scenarios:
            name = scenario.get("name", "unnamed")
            probability = float(scenario.get("probability", 0))
            key_override = scenario.get("key_override", {})

            # Build overridden assumptions
            s_assumptions = dict(assumptions)
            s_assumptions.update(key_override)

            s_gross_margin = _resolve_per_year(
                s_assumptions.get("gross_margin", assumptions["gross_margin"]),
                projection_years, 0.50,
            )
            s_opex_pct = _resolve_per_year(
                s_assumptions.get("opex_pct_of_revenue", assumptions.get("opex_pct_of_revenue")),
                projection_years, 0.20,
            )
            s_tax_rate = _resolve_tax_rate(
                s_assumptions.get("tax_rate", assumptions.get("tax_rate")),
                projection_years,
            )
            s_capex_pct = _resolve_per_year(
                s_assumptions.get("capex_pct_of_revenue", assumptions.get("capex_pct_of_revenue")),
                projection_years, 0.05,
            )
            s_da_pct = _resolve_per_year(
                s_assumptions.get("da_pct_of_revenue", assumptions.get("da_pct_of_revenue")),
                projection_years, s_capex_pct[0] if s_capex_pct else 0.05,
            )
            s_wc_change_pct = _resolve_per_year(
                s_assumptions.get("working_capital_change_pct", assumptions.get("working_capital_change_pct")),
                projection_years, 0.01,
            )
            s_wacc = float(s_assumptions.get("wacc", wacc))
            s_tg = float(s_assumptions.get("terminal_growth", terminal_growth))
            s_net_cash = float(s_assumptions.get("net_cash", net_cash))
            s_shares = float(s_assumptions.get("shares_outstanding", shares_outstanding))
            s_segments = s_assumptions.get("segments", segments)

            s_result = _compute_dcf(
                segments=s_segments,
                projection_years=projection_years,
                gross_margin=s_gross_margin,
                opex_pct=s_opex_pct,
                tax_rate=s_tax_rate,
                capex_pct=s_capex_pct,
                da_pct=s_da_pct,
                wc_change_pct=s_wc_change_pct,
                wacc=s_wacc,
                terminal_growth=s_tg,
                net_cash=s_net_cash,
                shares_outstanding=s_shares,
                current_price=current_price,
            )
            weighted_sum += probability * s_result["fair_value_per_share"]

        scenario_weighted_value = round(weighted_sum, 2)

    result["scenario_weighted_value"] = scenario_weighted_value

    # ── Soft warnings ──
    warnings = []
    if assumptions.get("da_pct_of_revenue") is None:
        warnings.append(
            "D&A defaulted to CapEx rate. If this company is in a heavy investment phase "
            "(data centers, fabs), D&A on existing assets is usually lower than current CapEx — "
            "consider setting da_pct_of_revenue explicitly from cash-flow-statement."
        )
    tv_pct = (result["discounted_terminal_value"] / result["enterprise_value"] * 100) if result["enterprise_value"] != 0 else 0
    if tv_pct > 75:
        warnings.append(
            f"Terminal value is {tv_pct:.0f}% of enterprise value. Near-term FCF may be "
            "understated — either CapEx is high, margins are thin, or growth assumptions "
            "are conservative relative to terminal expectations."
        )
    if len(segments) == 1:
        seg_rev = float(segments[0].get("current_annual_revenue", 0))
        if seg_rev > 50000:
            warnings.append(
                "Single-segment model for a large-revenue company. Consider checking "
                "financials(ticker, 'segments') for business-line breakdowns."
            )
    result["warnings"] = warnings

    # ── Revision history ──
    round_num = len(_revision_history) + 1
    _revision_history.append({
        "round": round_num,
        "fair_value": result["fair_value_per_share"],
        "revision_reason": assumptions.get("revision_reason"),
    })
    result["revision_history"] = list(_revision_history)

    return ToolResult.ok(result)


def _compute_dcf(
    segments: list[dict],
    projection_years: int,
    gross_margin: list[float],
    opex_pct: list[float],
    tax_rate: list[float],
    capex_pct: list[float],
    da_pct: list[float],
    wc_change_pct: list[float],
    wacc: float,
    terminal_growth: float,
    net_cash: float,
    shares_outstanding: float,
    current_price: float,
) -> dict:
    """Core DCF computation — returns dict with all outputs.

    FCF = NOPAT + D&A - CapEx - ΔWC  (unlevered free cash flow)
    """
    year_by_year = []
    fcf_list = []
    nopat_list = []
    ebit_list = []
    prev_revenue = sum(float(seg["current_annual_revenue"]) for seg in segments)

    for t in range(projection_years):
        # Revenue = sum of all segments' projected revenue for year t
        total_revenue = 0.0
        for seg in segments:
            seg_revenue = float(seg["current_annual_revenue"])
            for i in range(t + 1):
                seg_revenue *= (1.0 + float(seg["growth_rates"][i]))
            total_revenue += seg_revenue

        revenue_growth = (total_revenue - prev_revenue) / prev_revenue if prev_revenue else 0

        cogs = total_revenue * (1.0 - gross_margin[t])
        gross_profit = total_revenue - cogs
        opex = total_revenue * opex_pct[t]
        ebit = gross_profit - opex
        tax = ebit * tax_rate[t]
        nopat = ebit - tax
        da = total_revenue * da_pct[t]
        capex = total_revenue * capex_pct[t]
        delta_wc = total_revenue * wc_change_pct[t]
        fcf = nopat + da - capex - delta_wc

        discount_factor = (1.0 + wacc) ** (t + 1)
        discounted_fcf = fcf / discount_factor

        year_by_year.append({
            "year": t + 1,
            "revenue": round(total_revenue, 2),
            "revenue_growth": round(revenue_growth, 4),
            "gross_profit": round(gross_profit, 2),
            "ebit": round(ebit, 2),
            "nopat": round(nopat, 2),
            "da": round(da, 2),
            "fcf": round(fcf, 2),
            "discounted_fcf": round(discounted_fcf, 2),
        })

        fcf_list.append(fcf)
        nopat_list.append(nopat)
        ebit_list.append(ebit)
        prev_revenue = total_revenue

    # Terminal value
    terminal_value = fcf_list[-1] * (1.0 + terminal_growth) / (wacc - terminal_growth)
    discounted_tv = terminal_value / ((1.0 + wacc) ** projection_years)

    # Enterprise and equity value
    # All values (revenue, FCF, net_cash) are in $M.
    # shares_outstanding is actual count. Convert equity to $ before dividing.
    sum_discounted_fcf = sum(row["discounted_fcf"] for row in year_by_year)
    enterprise_value = sum_discounted_fcf + discounted_tv
    equity_value = enterprise_value + net_cash
    fair_value_per_share = (equity_value * 1_000_000) / shares_outstanding
    gap_pct = (fair_value_per_share - current_price) / current_price * 100.0

    # Implied multiples
    eps_y1 = (nopat_list[0] * 1_000_000) / shares_outstanding
    fwd_pe = fair_value_per_share / eps_y1 if eps_y1 != 0 else None
    ev_ebitda = enterprise_value / ebit_list[0] if ebit_list[0] != 0 else None
    # FCF is in $M, equity_value is in $M — use equity_value directly
    fcf_yield = fcf_list[0] / equity_value if equity_value != 0 else None

    # Revenue growth Y1: compute total revenue Y1 vs base year total revenue
    base_revenue = sum(float(seg["current_annual_revenue"]) for seg in segments)
    y1_revenue = year_by_year[0]["revenue"]
    revenue_growth_y1 = (y1_revenue - base_revenue) / base_revenue if base_revenue != 0 else 0
    peg_ratio = fwd_pe / (revenue_growth_y1 * 100) if (fwd_pe and revenue_growth_y1 != 0) else None

    implied_multiples = {
        "fwd_pe": round(fwd_pe, 2) if fwd_pe is not None else None,
        "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda is not None else None,
        "fcf_yield": round(fcf_yield, 4) if fcf_yield is not None else None,
        "peg_ratio": round(peg_ratio, 2) if peg_ratio is not None else None,
    }

    return {
        "fair_value_per_share": round(fair_value_per_share, 2),
        "current_price": current_price,
        "gap_pct": round(gap_pct, 2),
        "year_by_year": year_by_year,
        "terminal_value": round(terminal_value, 2),
        "discounted_terminal_value": round(discounted_tv, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "implied_multiples": implied_multiples,
    }


# ── get_comps implementation ─────────────────────────────────

def get_comps(ticker: str, peers: list[str]) -> ToolResult:
    """Peer comparison via FMP API."""
    try:
        from tools.financials import fmp_get_financials
    except ImportError:
        return ToolResult.fail(
            "Could not import fmp_get_financials",
            hint="Ensure tools.financials module is available",
        )

    all_tickers = [ticker.upper()] + [p.upper() for p in peers]
    results = []

    for t in all_tickers:
        entry = {
            "ticker": t,
            "fwd_pe": None,
            "ev_ebitda": None,
            "revenue_growth": None,
            "gross_margin": None,
            "market_cap": None,
            "is_target": t == ticker.upper(),
        }

        # Fetch ratios
        ratios_result = fmp_get_financials(ticker=t, statement_type="ratios")
        if ratios_result.status == "ok" and ratios_result.data:
            ratios_data = ratios_result.data.get("data", [])
            if ratios_data:
                latest = ratios_data[0]
                entry["fwd_pe"] = latest.get("priceToEarningsRatio") or latest.get("priceEarningsRatio")
                entry["ev_ebitda"] = latest.get("enterpriseValueMultiple") or latest.get("enterpriseValueOverEBITDA")
                entry["gross_margin"] = latest.get("grossProfitMargin")
                entry["revenue_growth"] = latest.get("revenuePerShare")  # fallback; true growth needs two periods
                entry["market_cap"] = latest.get("marketCap")

        # If ratios didn't have everything, try profile
        if entry["fwd_pe"] is None or entry["ev_ebitda"] is None or entry["market_cap"] is None:
            profile_result = fmp_get_financials(ticker=t, statement_type="profile")
            if profile_result.status == "ok" and profile_result.data:
                profile_data = profile_result.data.get("data", [])
                if profile_data:
                    p = profile_data[0] if isinstance(profile_data, list) else profile_data
                    if entry["fwd_pe"] is None:
                        entry["fwd_pe"] = p.get("pe")
                    if entry["ev_ebitda"] is None:
                        entry["ev_ebitda"] = p.get("enterpriseValueOverEBITDA")
                    if entry["market_cap"] is None:
                        entry["market_cap"] = p.get("marketCap") or p.get("mktCap")

        results.append(entry)

    # Compute median for each metric
    def _median(values):
        clean = [v for v in values if v is not None]
        if not clean:
            return None
        clean.sort()
        n = len(clean)
        if n % 2 == 1:
            return clean[n // 2]
        return (clean[n // 2 - 1] + clean[n // 2]) / 2.0

    median = {
        "fwd_pe": _median([r["fwd_pe"] for r in results]),
        "ev_ebitda": _median([r["ev_ebitda"] for r in results]),
        "revenue_growth": _median([r["revenue_growth"] for r in results]),
        "gross_margin": _median([r["gross_margin"] for r in results]),
    }

    # Target vs median premium/discount
    target_entry = results[0]
    target_vs_median = {}
    for metric in ["fwd_pe", "ev_ebitda", "revenue_growth", "gross_margin"]:
        t_val = target_entry.get(metric)
        m_val = median.get(metric)
        if t_val is not None and m_val is not None and m_val != 0:
            target_vs_median[f"{metric}_premium"] = round((t_val - m_val) / m_val, 4)
        else:
            target_vs_median[f"{metric}_premium"] = None

    return ToolResult.ok({
        "target": ticker.upper(),
        "peers": results,
        "median": median,
        "target_vs_median": target_vs_median,
    })


# ── Registration ─────────────────────────────────────────────

def register(context: dict) -> list[Tool]:
    """DCF/comps exposed only through the unified valuation skill entry point."""
    return []
