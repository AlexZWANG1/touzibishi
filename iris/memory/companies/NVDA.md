## NVDA postmortem update
- User requested a postmortem on NVDA.
- Retrieved prior NVDA note: previous work mainly stored a conservative DCF framing and a qualitative conclusion ('hold / wait for pullback'), with growth assumptions of 22%, 16%, 12%, 9%, 7% for future years.
- Limitation discovered: prior note did **not** preserve a structured forecast table for revenue, gross margin, capex, or FCF, so this review cannot compute a clean predicted-vs-actual error table for core operating metrics.
- Verifiable facts available in current context:
  - FY2026 revenue: $215.9B.
  - FY2026 gross margin: 71.1%.
  - FY2026 free cash flow: about $96.7B.
  - FY2026 ending cash + short-term investments: about $62.6B; total debt about $11.4B.
  - Q1 FY2026 revenue: $44.1B.
  - Q1 FY2026 export-control-related H20 charge: $4.5B.
- Main learning from the postmortem:
  1. Future analyses must save a structured forecast table for operating metrics, not just valuation conclusions.
  2. For NVDA, policy/export shocks should be modeled separately from core AI demand, because a large one-time charge can coexist with very strong company-wide revenue, margin, and FCF.
- Calibration data found only pending fair-value entries; no resolved operating-metric prediction records yet.