from dataclasses import dataclass
from typing import Optional


@dataclass
class GuardResult:
    blocked: bool
    error: Optional[str] = None
    hint: Optional[str] = None

    @classmethod
    def pass_(cls) -> "GuardResult":
        return cls(blocked=False)

    @classmethod
    def block(cls, error: str, hint: str = None) -> "GuardResult":
        return cls(blocked=True, error=error, hint=hint)


class InvestmentGuards:
    """Per-tool guards enforcing financial domain constraints (Backpressure)."""

    def check(self, tool_name: str, args: dict) -> GuardResult:
        handler = getattr(self, f"_check_{tool_name}", None)
        if handler:
            return handler(args)
        return GuardResult.pass_()

    def _check_run_valuation(self, args: dict) -> GuardResult:
        wacc = args.get("wacc")
        tgr = args.get("terminal_growth_rate")
        reasoning = args.get("reasoning", "")

        if wacc is not None and not (0.03 <= wacc <= 0.25):
            return GuardResult.block(
                error=f"WACC {wacc:.1%} is outside valid range (3%–25%)",
                hint="Check risk-free rate + equity risk premium assumptions",
            )
        if wacc is not None and tgr is not None and tgr >= wacc:
            return GuardResult.block(
                error=f"terminal_growth_rate ({tgr:.1%}) must be less than WACC ({wacc:.1%})",
                hint="Long-term growth rate typically 2%–3%, cannot exceed cost of capital",
            )
        if not reasoning.strip():
            return GuardResult.block(
                error="reasoning is required for run_valuation",
                hint="Explain your key assumptions and methodology choice",
            )
        return GuardResult.pass_()

    def _check_add_evidence_card(self, args: dict) -> GuardResult:
        if not args.get("hypothesis_id"):
            return GuardResult.block(
                error="hypothesis_id is required — call create_hypothesis first",
                hint="Use query_knowledge to find existing hypothesis IDs",
            )
        if not args.get("observation_id"):
            return GuardResult.block(error="observation_id is required — call extract_observation first")
        if not args.get("reasoning", "").strip():
            return GuardResult.block(
                error="reasoning must not be empty for add_evidence_card",
                hint="Explain why you rated direction/reliability/independence/novelty as you did",
            )
        return GuardResult.pass_()

    def _check_compute_trade_score(self, args: dict) -> GuardResult:
        if not args.get("hypothesis_id"):
            return GuardResult.block(error="hypothesis_id is required for compute_trade_score")
        if not args.get("reasoning", "").strip():
            return GuardResult.block(
                error="reasoning must not be empty for compute_trade_score",
                hint="Explain your assessment of fundamental_quality, catalyst_timing, risk_penalty",
            )
        for field in ("fundamental_quality", "catalyst_timing", "risk_penalty"):
            v = args.get(field)
            if v is not None and not (0.0 <= v <= 1.0):
                return GuardResult.block(error=f"{field} must be between 0.0 and 1.0, got {v}")
        return GuardResult.pass_()

    def _check_write_audit_trail(self, args: dict) -> GuardResult:
        if not args.get("trade_score_id"):
            return GuardResult.block(error="trade_score_id is required — call compute_trade_score first")
        return GuardResult.pass_()

    def _check_create_hypothesis(self, args: dict) -> GuardResult:
        confidence = args.get("initial_confidence")
        if confidence is not None and not (0 <= confidence <= 100):
            return GuardResult.block(error=f"initial_confidence {confidence} out of range [0, 100]")
        drivers = args.get("drivers", [])
        if len(drivers) < 3:
            return GuardResult.block(
                error=f"At least 3 drivers required, got {len(drivers)}",
                hint="Identify the key factors that must hold true for the thesis to work",
            )
        if len(drivers) > 6:
            return GuardResult.block(
                error=f"Maximum 6 drivers allowed, got {len(drivers)}",
                hint="Focus on the most important factors",
            )
        return GuardResult.pass_()
