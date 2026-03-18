import os
from pathlib import Path

INVARIANTS = {
    "max_single_position": 0.15,
    "stop_loss_trigger": -0.20,
    "max_sector_concentration": 0.40,
    "every_conclusion_needs_reasoning_chain": True,
    "every_assumption_needs_source": True,
    "every_hypothesis_needs_kill_criteria": True,
    "min_drivers_per_hypothesis": 3,
    "max_drivers_per_hypothesis": 6,
    "no_valuation_cap": 64,
    "low_evidence_cap": 49,
    "unresolved_kill_cap": 74,
    "min_bull_bear_spread": 0.30,
}

EVOLVABLE_PARAMS = {
    "confidence_threshold_to_act": 65,
    "belief_update_scaling_factor": 10,
    "min_evidence_count_for_action": 3,
    "news_recency_weight": 0.8,
    "min_source_reliability_threshold": 0.3,
    "weight_fundamental_quality": 0.25,
    "weight_valuation_gap": 0.25,
    "weight_belief_confidence": 0.25,
    "weight_catalyst_timing": 0.15,
    "weight_risk_penalty": 0.10,
    "max_tool_rounds": 20,
    "compress_threshold_chars": 2000,
}


def load_soul() -> str:
    soul_path = Path(__file__).parent.parent / "soul" / "v0.1.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return "# IRIS Investment Soul\nAnalyze investments rigorously. Every claim needs evidence."


DB_PATH = os.getenv("IRIS_DB_PATH", "./iris.db")
