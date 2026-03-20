"""Full DCF engine integration test — run standalone, no LLM needed."""
import json
from core.config import register_skill_config, reset_skill_configs
from skills.dcf.tools import register, _revision_history, build_dcf

# Setup config
reset_skill_configs()
register_skill_config("dcf", {
    "wacc_range": [0.05, 0.20],
    "terminal_growth_max": 0.05,
    "sensitivity": {
        "wacc_steps": [-0.02, -0.01, 0, 0.01, 0.02],
        "growth_steps": [-0.01, -0.005, 0, 0.005, 0.01],
    },
})

# Register DCF tools
tools = register({})
tool_map = {t.name: t for t in tools}
print("DCF tools registered:", list(tool_map.keys()))
print()

# === Test 1: build_dcf with realistic NVDA assumptions ===
print("=" * 60)
print("TEST 1: build_dcf - NVDA DCF Model")
print("=" * 60)

nvda_assumptions = {
    "company": "NVIDIA",
    "ticker": "NVDA",
    "projection_years": 5,
    "segments": [
        {
            "name": "Data Center",
            "current_annual_revenue": 115_000,
            "growth_rates": [0.45, 0.30, 0.22, 0.18, 0.15],
            "reasoning": "AI infrastructure demand: hyperscaler capex, sovereign AI, enterprise adoption",
        },
        {
            "name": "Gaming",
            "current_annual_revenue": 12_000,
            "growth_rates": [0.10, 0.08, 0.06, 0.05, 0.04],
            "reasoning": "Mature segment, modest growth from GeForce upgrades",
        },
        {
            "name": "Auto/Other",
            "current_annual_revenue": 4_000,
            "growth_rates": [0.20, 0.15, 0.12, 0.10, 0.08],
            "reasoning": "Autonomous driving platform ramp",
        },
    ],
    "gross_margin": {"value": 0.73, "trend": "stable"},
    "opex_pct_of_revenue": {"value": 0.12},
    "wacc": 0.11,
    "terminal_growth": 0.03,
    "tax_rate": {"value": 0.12},
    "capex_pct_of_revenue": {"value": 0.07},
    "working_capital_change_pct": {"value": 0.015},
    "shares_outstanding": 24_500,
    "net_cash": 30_000,
    "current_price": 135.0,
}

result = build_dcf(nvda_assumptions)
r = result.to_dict()

if r.get("status") == "error":
    print(f"  ERROR: {json.dumps(r, indent=2)}")
else:
    d = r.get("data", r)
    fv = d["fair_value_per_share"]
    gap = d["gap_pct"]
    print(f"  Fair Value per Share: ${fv:.2f}")
    print(f"  Current Price:        $135.00")
    print(f"  Gap (upside/downside): {gap:+.1f}%")
    print(f"  Enterprise Value:     ${d['enterprise_value']:,.0f}M")
    print(f"  Terminal Value:       ${d['terminal_value']:,.0f}M")
    tv_pct = d['discounted_terminal_value'] / d['enterprise_value'] if d['enterprise_value'] else 0
    print(f"  Terminal % of EV:     {tv_pct:.1%}")
    print()

    # Year-by-year projections
    print("  Year-by-Year Projections:")
    yby = d["year_by_year"]
    first = yby[0]
    cols = [k for k in first.keys()]
    header = "  "
    for c in cols:
        header += f"{c:>14}"
    print(header)
    for yr in yby:
        row = "  "
        for c in cols:
            v = yr[c]
            if isinstance(v, float):
                row += f"{v:>14,.1f}"
            else:
                row += f"{v:>14}"
        print(row)
    print()

    # Sensitivity matrix
    if "sensitivity" in d:
        print("  Sensitivity Matrix (Fair Value per Share):")
        sm = d["sensitivity"]
        header = "  WACC \\ TGR  "
        for col in sm["growth_values"]:
            header += f"{col:>8.1%}"
        print(header)
        for i, wacc in enumerate(sm["wacc_values"]):
            row = f"  {wacc:>10.1%}  "
            for val in sm["matrix"][i]:
                if val is None:
                    row += f"{'N/A':>8}"
                else:
                    row += f"{val:>8.1f}"
            print(row)
        print()

    # Implied multiples
    if "implied_multiples" in d:
        print("  Implied Multiples:")
        for key, val in d["implied_multiples"].items():
            if val is not None:
                print(f"    {key:>20}: {val:.1f}x")
        print()

# === Test 2: Scenario-weighted DCF ===
print("=" * 60)
print("TEST 2: Scenario-weighted DCF (Bull/Base/Bear)")
print("=" * 60)

nvda_with_scenarios = {
    **nvda_assumptions,
    "scenarios": [
        {
            "name": "Bull",
            "probability": 0.25,
            "key_override": {
                "segments": [
                    {"name": "Data Center", "current_annual_revenue": 115_000,
                     "growth_rates": [0.55, 0.40, 0.30, 0.25, 0.20], "reasoning": "AI capex supercycle"},
                    {"name": "Gaming", "current_annual_revenue": 12_000,
                     "growth_rates": [0.15, 0.12, 0.10, 0.08, 0.06], "reasoning": "Strong upgrade cycle"},
                    {"name": "Auto/Other", "current_annual_revenue": 4_000,
                     "growth_rates": [0.25, 0.20, 0.15, 0.12, 0.10], "reasoning": "Fast AV ramp"},
                ],
            },
        },
        {
            "name": "Base",
            "probability": 0.50,
            "key_override": {},
        },
        {
            "name": "Bear",
            "probability": 0.25,
            "key_override": {
                "segments": [
                    {"name": "Data Center", "current_annual_revenue": 115_000,
                     "growth_rates": [0.20, 0.10, 0.08, 0.05, 0.03], "reasoning": "AI capex pullback"},
                    {"name": "Gaming", "current_annual_revenue": 12_000,
                     "growth_rates": [0.03, 0.02, 0.01, 0.01, 0.00], "reasoning": "Stagnation"},
                    {"name": "Auto/Other", "current_annual_revenue": 4_000,
                     "growth_rates": [0.08, 0.05, 0.03, 0.02, 0.01], "reasoning": "Slow adoption"},
                ],
            },
        },
    ],
}

result2 = build_dcf(nvda_with_scenarios)
r2 = result2.to_dict()

if r2.get("status") == "error":
    print(f"  ERROR: {json.dumps(r2, indent=2)}")
else:
    d2 = r2.get("data", r2)
    print(f"  Base Fair Value:     ${d2['fair_value_per_share']:.2f}")
    if d2.get("scenario_weighted_value"):
        print(f"  Weighted Fair Value: ${d2['scenario_weighted_value']:.2f}")
    if d2.get("scenario_results"):
        print()
        for sr in d2["scenario_results"]:
            print(f"    {sr['name']:>5} ({sr['probability']:.0%}): ${sr['fair_value_per_share']:.2f}/share")
    print()

# === Test 3: get_comps (will fail without FMP API but shows error handling) ===
print("=" * 60)
print("TEST 3: get_comps - NVDA vs peers")
print("=" * 60)

comps_result = tool_map["get_comps"].fn(
    ticker="NVDA",
    peers=["AMD", "AVGO", "MRVL", "INTC", "TSM"],
)
cr = comps_result.to_dict()
print(f"  Status: {cr.get('status', '?')}")
if cr.get("status") == "error":
    print(f"  Error: {cr.get('error', '?')}")
    print("  (Expected - FMP API not available in test environment)")
else:
    print(f"  Peers: {len(cr.get('peers', []))}")
    for p in cr.get("peers", []):
        print(f"    {json.dumps(p, default=str)[:100]}")
print()

# Revision history
print("=" * 60)
print("REVISION HISTORY")
print("=" * 60)
for company, revisions in _revision_history.items():
    print(f"  {company}: {len(revisions)} revision(s)")
    for rev in revisions:
        ts = str(rev.get("timestamp", "?"))[:19]
        fv = rev.get("fair_value_per_share", 0)
        sc = rev.get("scenario_name", "base")
        print(f"    {ts} | ${fv:.2f}/share | scenario={sc}")

print()
print("=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
