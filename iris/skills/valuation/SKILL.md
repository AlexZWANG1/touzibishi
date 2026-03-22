# Valuation

Use `valuation` as your only entry point. Do not call `build_dcf` or `get_comps` directly.

Always use `mode='full'` unless you have a specific reason not to — it runs DCF + comps + cross-check in one call. When cross-check comes back `stretched` or `conservative`, re-examine the assumption that matters most (usually growth or WACC) and decide whether to revise.

You need at least two independent pricing anchors for a credible valuation. DCF gives you one; comps give you another. `mode='full'` produces both.

---

## Example: AAPL (stable, profitable — DCF anchored)

After calling `financials('AAPL', 'income-statement')` and `quote('AAPL')`, you have:

- Revenue: $394B, 3-year CAGR ~4%
- Gross margin: ~46%, stable
- CapEx/Rev: ~3.5%, D&A/Rev: ~3.0% (from cash flow statement)
- Shares: 15,408,095,000 (from income statement `weightedAverageShsOutDil`)
- Net cash: $65B cash - $105B debt = -$40B (net debt, from balance sheet)

You call:

```
valuation(
  mode='full',
  ticker='AAPL',
  assumptions={
    "company": "Apple", "ticker": "AAPL", "projection_years": 5,
    "segments": [
      {"name": "Total", "current_annual_revenue": 394000,
       "growth_rates": [0.05, 0.04, 0.04, 0.03, 0.03]}
    ],
    "gross_margin": {"value": 0.46},
    "opex_pct_of_revenue": {"value": 0.14},
    "capex_pct_of_revenue": {"value": 0.035},
    "da_pct_of_revenue": {"value": 0.03},
    "wacc": 0.095,
    "terminal_growth": 0.03,
    "shares_outstanding": 15408095000,
    "net_cash": -40000,
    "current_price": 228
  },
  peers=["MSFT", "GOOGL", "AMZN", "META"]
)
```

Notice what happened:
- `da_pct_of_revenue` was explicitly set (not left to default)
- `shares_outstanding` is the actual share count from financials, not in millions
- `net_cash` is negative because Apple has net debt — passed as-is
- Growth rates are grounded in the historical 4% CAGR, not invented
- Revenue is in millions (matching how `financials` returns it)

---

## Example: GOOGL (multi-business — SOTP approach via multiple calls)

For diversified companies, call `valuation` separately per segment, then add up:

```
# 1. Google Services (80% of rev) — mature, DCF-friendly
valuation(mode='dcf', ticker='GOOGL', assumptions={
  "company": "Alphabet", "ticker": "GOOGL", "projection_years": 5,
  "segments": [{"name": "Google Services", "current_annual_revenue": 280000,
    "growth_rates": [0.08, 0.07, 0.06, 0.05, 0.04]}],
  "gross_margin": {"value": 0.58},
  "wacc": 0.09, "terminal_growth": 0.03,
  "shares_outstanding": 12200000000, "net_cash": 95000, "current_price": 170
})

# 2. Google Cloud (12% of rev) — high-growth, comps more informative
valuation(mode='comps', ticker='GOOGL',
  peers=["AMZN", "MSFT", "SNOW", "DDOG"])
# Then apply the peer median EV/Revenue multiple to Cloud's $43B revenue

# 3. Other Bets — pre-profit, use invested capital as floor
# No tool call needed; estimate directly (e.g. $5B book value)

# Sum: Services EV + Cloud EV + Other Bets + net cash → total EV / shares
```

This isn't a single tool call — it's a judgment process. You decide how to value each piece based on what data you have.

---

## When DCF doesn't work well

DCF struggles when future cash flows are unpredictable:

- **Pre-profit companies** (Rivian, many biotech) — no positive FCF to discount. Use EV/Revenue comps: `valuation(mode='comps', peers=[...])`.
- **Cyclical peaks/troughs** (steel, shipping, semiconductors at cycle extremes) — current earnings misrepresent normal earning power. Think about what mid-cycle looks like.
- **Banks and insurance** — FCF doesn't apply. P/BV and dividend discount models are standard. The `valuation` tool can still run comps for P/BV comparison.

You don't need to force every company through DCF. A well-anchored comps analysis with thoughtful peer selection is often more useful than a DCF with uncertain inputs.

---

## Common mistakes to watch for

The `valuation` tool will return warnings when it detects issues. Pay attention to them. The most frequent problems:

- Forgetting `da_pct_of_revenue` — the tool defaults it to match CapEx. For companies in heavy capex cycles (cloud, fabs), current D&A is usually lower than current CapEx. Check the cash flow statement.
- Passing `shares_outstanding` in millions instead of actual count — if the tool returns a fair value per share that's 1000x too low or high, this is probably why.
- Using a single "Total Revenue" segment when the company has clearly distinct businesses with different growth profiles — at minimum, check `financials(ticker, 'segments')` first.
- Picking peers by gut rather than checking they're actually comparable — similar market cap, same industry, similar growth stage. 4-6 peers is the sweet spot.
