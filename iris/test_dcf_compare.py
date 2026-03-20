"""Compare DCF valuations across sectors — traditional vs tech."""
import sys
sys.path.insert(0, ".")

from skills.dcf.tools import build_dcf, _revision_history
from core.config import register_skill_config, reset_skill_configs

reset_skill_configs()
register_skill_config("dcf", {
    "max_projection_years": 10,
    "terminal_growth_max": 0.04,
    "wacc_range": [0.05, 0.20],
    "comps_outlier_threshold": 0.50,
    "sensitivity": {
        "wacc_steps": [-0.02, -0.01, 0, 0.01, 0.02],
        "growth_steps": [-0.01, -0.005, 0, 0.005, 0.01],
    },
})

companies = [
    # ── Traditional / Value ──
    {
        "label": "JNJ (Johnson & Johnson) - Healthcare",
        "assumptions": {
            "company": "Johnson & Johnson", "ticker": "JNJ",
            "projection_years": 5,
            "segments": [
                {"name": "Innovative Medicine", "current_annual_revenue": 55000,
                 "growth_rates": [0.04, 0.03, 0.03, 0.02, 0.02], "reasoning": "Pharma pipeline"},
                {"name": "MedTech", "current_annual_revenue": 31000,
                 "growth_rates": [0.05, 0.04, 0.04, 0.03, 0.03], "reasoning": "Devices"},
            ],
            "gross_margin": {"value": 0.69},
            "opex_pct_of_revenue": {"value": 0.28},
            "tax_rate": {"value": 0.16},
            "capex_pct_of_revenue": {"value": 0.04},
            "da_pct_of_revenue": {"value": 0.05},
            "working_capital_change_pct": {"value": 0.01},
            "wacc": 0.08, "terminal_growth": 0.025,
            "net_cash": -15000,
            "shares_outstanding": 2410,
            "current_price": 156.0,
        },
    },
    {
        "label": "KO (Coca-Cola) - Consumer Staples",
        "assumptions": {
            "company": "Coca-Cola", "ticker": "KO",
            "projection_years": 5,
            "segments": [
                {"name": "Beverages", "current_annual_revenue": 46000,
                 "growth_rates": [0.03, 0.03, 0.02, 0.02, 0.02], "reasoning": "Stable"},
            ],
            "gross_margin": {"value": 0.60},
            "opex_pct_of_revenue": {"value": 0.19},
            "tax_rate": {"value": 0.19},
            "capex_pct_of_revenue": {"value": 0.04},
            "da_pct_of_revenue": {"value": 0.05},
            "working_capital_change_pct": {"value": 0.005},
            "wacc": 0.075, "terminal_growth": 0.025,
            "net_cash": -30000,
            "shares_outstanding": 4310,
            "current_price": 72.0,
        },
    },
    {
        "label": "PG (Procter & Gamble) - Consumer Staples",
        "assumptions": {
            "company": "Procter & Gamble", "ticker": "PG",
            "projection_years": 5,
            "segments": [
                {"name": "Beauty", "current_annual_revenue": 15000,
                 "growth_rates": [0.04, 0.03, 0.03, 0.02, 0.02], "reasoning": "Beauty"},
                {"name": "Health", "current_annual_revenue": 11000,
                 "growth_rates": [0.05, 0.04, 0.03, 0.03, 0.02], "reasoning": "Health"},
                {"name": "Home/Baby", "current_annual_revenue": 30000,
                 "growth_rates": [0.02, 0.02, 0.02, 0.02, 0.02], "reasoning": "Staples"},
                {"name": "Grooming", "current_annual_revenue": 7000,
                 "growth_rates": [0.02, 0.02, 0.01, 0.01, 0.01], "reasoning": "Mature"},
            ],
            "gross_margin": {"value": 0.52},
            "opex_pct_of_revenue": {"value": 0.18},
            "tax_rate": {"value": 0.20},
            "capex_pct_of_revenue": {"value": 0.05},
            "da_pct_of_revenue": {"value": 0.05},
            "working_capital_change_pct": {"value": 0.005},
            "wacc": 0.075, "terminal_growth": 0.025,
            "net_cash": -25000,
            "shares_outstanding": 2360,
            "current_price": 170.0,
        },
    },
    {
        "label": "JPM (JPMorgan) - Financials",
        "assumptions": {
            "company": "JPMorgan Chase", "ticker": "JPM",
            "projection_years": 5,
            "segments": [
                {"name": "Consumer Banking", "current_annual_revenue": 72000,
                 "growth_rates": [0.03, 0.02, 0.02, 0.02, 0.02], "reasoning": "Consumer"},
                {"name": "CIB", "current_annual_revenue": 55000,
                 "growth_rates": [0.04, 0.03, 0.02, 0.02, 0.01], "reasoning": "IB/Markets"},
                {"name": "AWM", "current_annual_revenue": 21000,
                 "growth_rates": [0.06, 0.05, 0.04, 0.03, 0.03], "reasoning": "AUM"},
            ],
            "gross_margin": {"value": 0.75},
            "opex_pct_of_revenue": {"value": 0.40},
            "tax_rate": {"value": 0.22},
            "capex_pct_of_revenue": {"value": 0.04},
            "da_pct_of_revenue": {"value": 0.03},
            "working_capital_change_pct": {"value": 0.01},
            "wacc": 0.09, "terminal_growth": 0.025,
            "net_cash": 50000,
            "shares_outstanding": 2850,
            "current_price": 262.0,
        },
    },
    # ── Tech (with better assumptions this time) ──
    {
        "label": "AAPL (Apple) - Tech [manual params]",
        "assumptions": {
            "company": "Apple", "ticker": "AAPL",
            "projection_years": 5,
            "segments": [
                {"name": "iPhone", "current_annual_revenue": 201000,
                 "growth_rates": [0.02, 0.03, 0.02, 0.02, 0.01], "reasoning": "Upgrade cycles"},
                {"name": "Services", "current_annual_revenue": 96000,
                 "growth_rates": [0.12, 0.10, 0.09, 0.08, 0.07], "reasoning": "High-margin recurring"},
                {"name": "Mac/iPad/Wearables", "current_annual_revenue": 94000,
                 "growth_rates": [0.03, 0.02, 0.02, 0.01, 0.01], "reasoning": "Ecosystem"},
            ],
            "gross_margin": {"value": 0.46},
            "opex_pct_of_revenue": {"value": 0.07},
            "tax_rate": {"value": 0.15},
            "capex_pct_of_revenue": {"value": 0.03},
            "da_pct_of_revenue": {"value": 0.03},
            "working_capital_change_pct": {"value": 0.005},
            "wacc": 0.09, "terminal_growth": 0.03,
            "net_cash": -49000,
            "shares_outstanding": 15200,
            "current_price": 250.0,
        },
    },
    {
        "label": "NVDA (NVIDIA) - Tech [manual params]",
        "assumptions": {
            "company": "NVIDIA", "ticker": "NVDA",
            "projection_years": 5,
            "segments": [
                {"name": "Data Center", "current_annual_revenue": 115000,
                 "growth_rates": [0.45, 0.30, 0.22, 0.18, 0.15], "reasoning": "AI infra"},
                {"name": "Gaming", "current_annual_revenue": 12000,
                 "growth_rates": [0.08, 0.06, 0.05, 0.04, 0.03], "reasoning": "Gaming"},
                {"name": "Auto/Other", "current_annual_revenue": 4000,
                 "growth_rates": [0.15, 0.12, 0.10, 0.08, 0.06], "reasoning": "Auto"},
            ],
            "gross_margin": {"value": 0.73},
            "opex_pct_of_revenue": {"value": 0.11},
            "tax_rate": {"value": 0.12},
            "capex_pct_of_revenue": {"value": 0.03},
            "da_pct_of_revenue": {"value": 0.03},
            "working_capital_change_pct": {"value": 0.015},
            "wacc": 0.11, "terminal_growth": 0.03,
            "net_cash": 35000,
            "shares_outstanding": 24500,
            "current_price": 180.0,
        },
    },
]

print("=" * 90)
print(f"{'Company':<40} {'FV':>8} {'Price':>8} {'Gap%':>8} {'P/E':>6} {'EV/EB':>7} {'TV%':>6}")
print("=" * 90)

for co in companies:
    _revision_history.clear()
    r = build_dcf(co["assumptions"])
    if r.status != "ok":
        print(f"{co['label']:<40} ERROR: {r.error}")
        continue
    d = r.data
    tv_pct = d["discounted_terminal_value"] / d["enterprise_value"] * 100 if d["enterprise_value"] > 0 else 0
    pe = d["implied_multiples"]["fwd_pe"] or 0
    ev_eb = d["implied_multiples"]["ev_ebitda"] or 0
    print(f"{co['label']:<40} ${d['fair_value_per_share']:>7.2f} ${co['assumptions']['current_price']:>6.0f} {d['gap_pct']:>7.1f}% {pe:>5.1f}x {ev_eb:>6.1f}x {tv_pct:>5.1f}%")

print()
print("=" * 90)
print("Year-by-year detail for AAPL:")
_revision_history.clear()
r = build_dcf(companies[4]["assumptions"])
for row in r.data["year_by_year"]:
    print(f"  Y{row['year']}: Rev={row['revenue']:>12,.0f}  GP={row['gross_profit']:>12,.0f}  EBIT={row['ebit']:>12,.0f}  NOPAT={row['nopat']:>12,.0f}  D&A={row['da']:>10,.0f}  FCF={row['fcf']:>12,.0f}  Growth={row['revenue_growth']*100:.1f}%")
print(f"  Terminal Value: {r.data['terminal_value']:>15,.0f}")
print(f"  Discounted TV:  {r.data['discounted_terminal_value']:>15,.0f}")
print(f"  Sum Disc FCF:   {sum(row['discounted_fcf'] for row in r.data['year_by_year']):>15,.0f}")
print(f"  Enterprise Val: {r.data['enterprise_value']:>15,.0f}")
print(f"  + Net Cash:     {companies[4]['assumptions']['net_cash']:>15,.0f}")
print(f"  = Equity Value: {r.data['equity_value']:>15,.0f}")
print(f"  / Shares:       {companies[4]['assumptions']['shares_outstanding']:>15,.0f}")
print(f"  = Fair Value:   ${r.data['fair_value_per_share']:>14.2f}")

print()
print("Year-by-year detail for NVDA:")
_revision_history.clear()
r = build_dcf(companies[5]["assumptions"])
for row in r.data["year_by_year"]:
    print(f"  Y{row['year']}: Rev={row['revenue']:>12,.0f}  GP={row['gross_profit']:>12,.0f}  EBIT={row['ebit']:>12,.0f}  NOPAT={row['nopat']:>12,.0f}  D&A={row['da']:>10,.0f}  FCF={row['fcf']:>12,.0f}  Growth={row['revenue_growth']*100:.1f}%")
print(f"  Terminal Value: {r.data['terminal_value']:>15,.0f}")
print(f"  Discounted TV:  {r.data['discounted_terminal_value']:>15,.0f}")
print(f"  Sum Disc FCF:   {sum(row['discounted_fcf'] for row in r.data['year_by_year']):>15,.0f}")
print(f"  Enterprise Val: {r.data['enterprise_value']:>15,.0f}")
print(f"  + Net Cash:     {companies[5]['assumptions']['net_cash']:>15,.0f}")
print(f"  = Equity Value: {r.data['equity_value']:>15,.0f}")
print(f"  / Shares:       {companies[5]['assumptions']['shares_outstanding']:>15,.0f}")
print(f"  = Fair Value:   ${r.data['fair_value_per_share']:>14.2f}")
