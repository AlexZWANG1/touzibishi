# Valuation Skill

Use `valuation` as the single entry point for model valuation.

## Workflow
1. Use `mode=dcf` when you already have full assumptions.
2. Use `mode=comps` when you need peer multiple anchoring.
3. Use `mode=full` for one-call DCF + comps cross-check.

## Constraint
- In `full` mode, provide both `assumptions` and `peers`.
