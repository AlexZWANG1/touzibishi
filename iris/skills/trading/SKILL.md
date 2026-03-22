# Trading

Three tools: `generate_trade_signal`, `execute_trade`, `get_portfolio`.

Always call `get_portfolio` before generating a signal — you need to know what you hold and how much cash you have.

A signal must be anchored in a valuation conclusion. If your valuation didn't produce a clear fair value, don't force a trade. "No trade" is a valid output.

---

## Example: BUY with anchor (NVDA)

After valuation concluded fair value ~$155, current price $118:

```
get_portfolio()
# → $100K total, no NVDA, 15% cash

generate_trade_signal(
  ticker='NVDA', action='BUY', price=118.0,
  target_price=155.0, stop_loss=98.0, position_pct=8.0,
  catalysts="Q4 earnings Feb 26, AI capex cycle acceleration",
  reasoning="DCF fair value $155, cross-check aligned. Stop at $98 = pre-earnings support. R:R = (155-118)/(118-98) = 1.85:1."
)
```

---

## Example: no trade (COST)

Valuation shows fair value ~$920, current price $950:

Don't call generate_trade_signal. Write in your conclusion:
"Costco at $950 vs fair value $920 — margin of safety too thin. Revisit below $880."

---

## Example: adding to existing (MSFT)

```
get_portfolio()
# → Holding 50 MSFT @ $410 (5% of portfolio), $12K cash

generate_trade_signal(
  ticker='MSFT', action='BUY', price=425.0,
  target_price=500.0, stop_loss=395.0, position_pct=4.0,
  reasoning="Adding post-earnings. Updated fair value $490. New capital $4K brings exposure to ~9%. R:R on addition: (500-425)/(425-395) = 2.5:1."
)
```

---

## Example: SELL — thesis invalidated (BABA)

```
get_portfolio()
# → Holding 200 BABA @ $88, current $82

generate_trade_signal(
  ticker='BABA', action='SELL', price=82.0,
  reasoning="Cloud growth decelerated to 7% — original thesis (regulatory normalization + Cloud re-acceleration) invalidated. Exit at -6.8% loss."
)
```

SELL because the thesis broke, not because the price dropped.
