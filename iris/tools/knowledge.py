import os
import uuid
from datetime import datetime
from typing import Optional

from core.schemas import (
    Observation, Driver, KillCriterion, EvidenceCard,
    Hypothesis, ValuationOutput, Assumption, TradeScore,
)
from core.config import EVOLVABLE_PARAMS, INVARIANTS
from tools.base import ToolResult, make_tool_schema
from tools.retrieval import EvidenceRetriever


# ── Tool Schemas ──────────────────────────────────────────────

EXTRACT_OBSERVATION_SCHEMA = make_tool_schema(
    name="extract_observation",
    description=(
        "Extract and save a structured observation from source material. "
        "One observation = one atomic factual claim or viewpoint. "
        "Call this for each significant piece of information."
    ),
    properties={
        "subject": {"type": "string", "description": "Company ticker or topic, e.g. 'NVDA'"},
        "claim": {"type": "string", "description": "The core claim in one concise sentence"},
        "source": {"type": "string", "description": "Source name/URL"},
        "fact_or_view": {"type": "string", "enum": ["fact", "view"]},
        "relevance": {"type": "number", "description": "0.0-1.0, relevance to investment thesis"},
        "citation": {"type": "string", "description": "Exact quote or paraphrase from source"},
        "time_str": {"type": "string", "description": "Date of information in YYYY-MM-DD format"},
    },
    required=["subject", "claim", "source", "fact_or_view", "relevance", "citation", "time_str"],
)

CREATE_HYPOTHESIS_SCHEMA = make_tool_schema(
    name="create_hypothesis",
    description=(
        "Create a new investment hypothesis with drivers and kill criteria. "
        "Call ONCE after gathering initial observations. "
        "Drivers are 3-6 factors that must hold true. Kill criteria invalidate the thesis."
    ),
    properties={
        "company": {"type": "string"},
        "thesis": {"type": "string", "description": "Core investment claim in one sentence"},
        "timeframe": {"type": "string", "description": "Investment horizon, e.g. '18 months'"},
        "drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "current_assessment": {"type": "string"},
                },
                "required": ["name", "description", "current_assessment"],
            },
            "minItems": 3,
            "maxItems": 6,
        },
        "kill_criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
        "initial_confidence": {
            "type": "number",
            "description": "Starting confidence 0-100. Use 50 if genuinely uncertain.",
        },
    },
    required=["company", "thesis", "timeframe", "drivers", "kill_criteria", "initial_confidence"],
)

ADD_EVIDENCE_CARD_SCHEMA = make_tool_schema(
    name="add_evidence_card",
    description=(
        "Evaluate an observation as evidence for/against the hypothesis and update belief confidence. "
        "Call this for each observation after hypothesis is created."
    ),
    properties={
        "hypothesis_id": {"type": "string", "description": "ID from create_hypothesis"},
        "observation_id": {"type": "string", "description": "ID from extract_observation"},
        "direction": {"type": "string", "enum": ["supports", "refutes", "mixed", "neutral"]},
        "reliability": {"type": "number", "description": "0-1: source credibility (earnings call=0.9, blog=0.3)"},
        "independence": {"type": "number", "description": "0-1: how independent from existing evidence"},
        "novelty": {"type": "number", "description": "0-1: how new/surprising is this information"},
        "driver_link": {"type": "string", "description": "Which driver this evidence relates to"},
        "reasoning": {"type": "string", "description": "Why you rated direction/reliability/independence/novelty this way"},
    },
    required=["hypothesis_id", "observation_id", "direction", "reliability",
              "independence", "novelty", "driver_link", "reasoning"],
)

RUN_VALUATION_SCHEMA = make_tool_schema(
    name="run_valuation",
    description=(
        "Perform valuation analysis. Choose methodology based on company type: "
        "stable cash flows→DCF, cyclical→comps+normalized, early stage→scenario, conglomerate→SOTP. "
        "Must provide both bull and bear cases."
    ),
    properties={
        "hypothesis_id": {"type": "string"},
        "methodology": {"type": "string", "enum": ["DCF", "comps", "scenario", "SOTP", "milestone"]},
        "methodology_reasoning": {"type": "string"},
        "wacc": {"type": "number", "description": "Discount rate 0.03-0.25"},
        "terminal_growth_rate": {"type": "number", "description": "Must be < WACC"},
        "fair_value_low": {"type": "number"},
        "fair_value_high": {"type": "number"},
        "current_price": {"type": "number"},
        "key_assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["name", "value", "reasoning", "source"],
            },
        },
        "bull_case_value": {"type": "number"},
        "bull_case_assumption": {"type": "string"},
        "bear_case_value": {"type": "number"},
        "bear_case_assumption": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    required=["hypothesis_id", "methodology", "methodology_reasoning", "wacc",
              "terminal_growth_rate", "fair_value_low", "fair_value_high", "current_price",
              "key_assumptions", "bull_case_value", "bull_case_assumption",
              "bear_case_value", "bear_case_assumption", "reasoning"],
)

COMPUTE_TRADE_SCORE_SCHEMA = make_tool_schema(
    name="compute_trade_score",
    description=(
        "Compute final Trade Score and investment recommendation. "
        "Call AFTER adding evidence cards and running valuation. "
        "You assess fundamental_quality, catalyst_timing, risk_penalty (all 0-1). Python computes weighted score."
    ),
    properties={
        "hypothesis_id": {"type": "string"},
        "valuation_id": {"type": "string", "description": "ID from run_valuation, or null"},
        "fundamental_quality": {"type": "number", "description": "0-1: business quality, moat, management"},
        "catalyst_timing": {"type": "number", "description": "0-1: clarity and proximity of catalyst"},
        "risk_penalty": {"type": "number", "description": "0-1: magnitude of key risks (higher = riskier)"},
        "reasoning": {"type": "string"},
    },
    required=["hypothesis_id", "fundamental_quality", "catalyst_timing", "risk_penalty", "reasoning"],
)

WRITE_AUDIT_TRAIL_SCHEMA = make_tool_schema(
    name="write_audit_trail",
    description=(
        "Generate and save the complete audit trail. Call as the LAST step after compute_trade_score."
    ),
    properties={
        "trade_score_id": {"type": "string"},
        "documents_used": {
            "type": "array",
            "items": {"type": "string"},
        },
        "soul_deviations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any deviations from Soul file guidelines",
        },
    },
    required=["trade_score_id", "documents_used"],
)

QUERY_KNOWLEDGE_SCHEMA = make_tool_schema(
    name="query_knowledge",
    description=(
        "Query saved observations and hypotheses. Use before searching again to avoid duplication, "
        "or to retrieve existing hypothesis ID."
    ),
    properties={
        "subject": {"type": "string", "description": "Company ticker to query"},
        "object_type": {"type": "string", "enum": ["observations", "hypotheses", "both"]},
    },
    required=["subject"],
)


# ── Tool Implementations ──────────────────────────────────────

def extract_observation(
    retriever: EvidenceRetriever,
    subject: str, claim: str, source: str,
    fact_or_view: str, relevance: float, citation: str,
    time_str: str, extracted_by: str = "iris",
) -> ToolResult:
    try:
        obs = Observation(
            id=f"obs_{uuid.uuid4().hex[:8]}",
            subject=subject, claim=claim, source=source,
            fact_or_view=fact_or_view, relevance=relevance,
            citation=citation,
            time=datetime.fromisoformat(time_str),
            extracted_at=datetime.now(),
            extracted_by=extracted_by,
        )
        retriever.save_observation(obs)
        return ToolResult.ok({"id": obs.id, "subject": obs.subject, "claim": obs.claim})
    except Exception as e:
        return ToolResult.error(f"Failed to save observation: {e}")


def create_hypothesis(
    retriever: EvidenceRetriever,
    company: str, thesis: str, timeframe: str,
    drivers: list[dict], kill_criteria: list[dict],
    initial_confidence: float,
) -> ToolResult:
    try:
        hyp = Hypothesis(
            id=f"hyp_{uuid.uuid4().hex[:8]}",
            thesis=thesis, company=company, timeframe=timeframe,
            drivers=[Driver(**d) for d in drivers],
            kill_criteria=[KillCriterion(**k) for k in kill_criteria],
            confidence=initial_confidence,
            created_at=datetime.now(), last_updated=datetime.now(),
        )
        retriever.save_hypothesis(hyp)
        return ToolResult.ok({
            "id": hyp.id,
            "company": hyp.company,
            "thesis": hyp.thesis,
            "initial_confidence": hyp.confidence,
            "drivers": [d.name for d in hyp.drivers],
        })
    except Exception as e:
        return ToolResult.error(f"Failed to create hypothesis: {e}")


def add_evidence_card(
    retriever: EvidenceRetriever,
    hypothesis_id: str, observation_id: str,
    direction: str, reliability: float, independence: float,
    novelty: float, driver_link: str, reasoning: str,
) -> ToolResult:
    hyp = retriever.get_hypothesis(hypothesis_id)
    if not hyp:
        return ToolResult.error(
            f"Hypothesis {hypothesis_id} not found",
            hint="Call create_hypothesis first or check the ID"
        )

    card = EvidenceCard(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        observation_id=observation_id,
        hypothesis_id=hypothesis_id,
        direction=direction,
        reliability=reliability,
        independence=independence,
        novelty=novelty,
        driver_link=driver_link,
        reasoning=reasoning,
        created_at=datetime.now(),
    )

    direction_map = {"supports": +1, "refutes": -1, "mixed": +0.2, "neutral": 0}
    sign = direction_map.get(direction, 0)
    scaling = EVOLVABLE_PARAMS["belief_update_scaling_factor"]
    delta = sign * reliability * independence * novelty * scaling

    old_confidence = hyp.confidence
    hyp.confidence = max(0.0, min(100.0, hyp.confidence + delta))
    hyp.evidence_log.append(card)
    hyp.last_updated = datetime.now()

    for driver in hyp.drivers:
        if driver.name == driver_link:
            driver.evidence_count += 1

    retriever.save_hypothesis(hyp)
    return ToolResult.ok({
        "evidence_id": card.id,
        "direction": direction,
        "old_confidence": round(old_confidence, 1),
        "delta": round(delta, 2),
        "new_confidence": round(hyp.confidence, 1),
    })


def run_valuation(
    retriever: EvidenceRetriever,
    hypothesis_id: str,
    methodology: str, methodology_reasoning: str,
    wacc: float, terminal_growth_rate: float,
    fair_value_low: float, fair_value_high: float, current_price: float,
    key_assumptions: list[dict],
    bull_case_value: float, bull_case_assumption: str,
    bear_case_value: float, bear_case_assumption: str,
    reasoning: str,
) -> ToolResult:
    fair_value_mid = (fair_value_low + fair_value_high) / 2
    valuation_gap = (fair_value_mid - current_price) / current_price if current_price else 0

    valuation = ValuationOutput(
        methodology=methodology,
        methodology_reasoning=methodology_reasoning,
        fair_value_range=(fair_value_low, fair_value_high),
        current_price=current_price,
        valuation_gap=valuation_gap,
        key_assumptions=[Assumption(**a) for a in key_assumptions],
        bull_case={"fair_value": bull_case_value, "key_assumption": bull_case_assumption},
        bear_case={"fair_value": bear_case_value, "key_assumption": bear_case_assumption},
    )
    valuation_id = f"val_{uuid.uuid4().hex[:8]}"
    retriever.save_valuation(valuation, valuation_id)

    return ToolResult.ok({
        "valuation_id": valuation_id,
        "methodology": methodology,
        "fair_value_range": [fair_value_low, fair_value_high],
        "current_price": current_price,
        "valuation_gap_pct": round(valuation_gap * 100, 1),
        "bull_case": bull_case_value,
        "bear_case": bear_case_value,
    })


def compute_trade_score(
    retriever: EvidenceRetriever,
    hypothesis_id: str,
    fundamental_quality: float,
    catalyst_timing: float,
    risk_penalty: float,
    reasoning: str,
    valuation_id: Optional[str] = None,
) -> ToolResult:
    hyp = retriever.get_hypothesis(hypothesis_id)
    if not hyp:
        return ToolResult.error(f"Hypothesis {hypothesis_id} not found")

    valuation = retriever.get_valuation(valuation_id) if valuation_id else None

    p = EVOLVABLE_PARAMS
    valuation_gap_norm = (
        min(1.0, max(0.0, (valuation.valuation_gap + 0.5))) if valuation else 0.5
    )

    raw_score = (
        p["weight_fundamental_quality"] * fundamental_quality
        + p["weight_valuation_gap"] * valuation_gap_norm
        + p["weight_belief_confidence"] * (hyp.confidence / 100)
        + p["weight_catalyst_timing"] * catalyst_timing
        - p["weight_risk_penalty"] * risk_penalty
    ) * 100

    constrained = raw_score
    reasons = []

    if valuation is None:
        constrained = min(constrained, INVARIANTS["no_valuation_cap"])
        reasons.append("No valuation output → capped at RESEARCH_MORE (64)")

    if len(hyp.evidence_log) < p["min_evidence_count_for_action"]:
        constrained = min(constrained, INVARIANTS["low_evidence_cap"])
        reasons.append(
            f"Only {len(hyp.evidence_log)} evidence cards < {p['min_evidence_count_for_action']} min → capped at WATCH (49)"
        )

    unresolved_kills = [k for k in hyp.kill_criteria if not k.resolved]
    if unresolved_kills:
        constrained = min(constrained, INVARIANTS["unresolved_kill_cap"])
        reasons.append(f"{len(unresolved_kills)} unresolved kill criteria → capped at CANDIDATE (74)")

    if valuation and valuation.bull_case and valuation.bear_case:
        spread = (valuation.bull_case["fair_value"] - valuation.bear_case["fair_value"]) / valuation.current_price
        if spread < INVARIANTS["min_bull_bear_spread"]:
            constrained = min(constrained, 64)
            reasons.append(f"Bull/bear spread {spread:.0%} < 30% → insufficient margin of safety")

    constrained = max(0.0, min(100.0, constrained))
    recommendation = _score_to_recommendation(constrained)

    score = TradeScore(
        id=f"ts_{uuid.uuid4().hex[:8]}",
        hypothesis_id=hypothesis_id,
        valuation_id=valuation_id,
        raw_score=round(raw_score, 1),
        constrained_score=round(constrained, 1),
        constraint_reasons=reasons,
        recommendation=recommendation,
        fundamental_quality=fundamental_quality,
        catalyst_timing=catalyst_timing,
        risk_penalty=risk_penalty,
        reasoning=reasoning,
        created_at=datetime.now(),
    )
    retriever.save_trade_score(score)

    return ToolResult.ok({
        "trade_score_id": score.id,
        "raw_score": score.raw_score,
        "constrained_score": score.constrained_score,
        "recommendation": recommendation,
        "constraint_reasons": reasons,
    })


def write_audit_trail(
    retriever: EvidenceRetriever,
    trade_score_id: str,
    documents_used: list[str],
    soul_deviations: list[str] = None,
) -> ToolResult:
    from core.schemas import AuditTrail

    score = retriever.get_trade_score(trade_score_id)
    if not score:
        return ToolResult.error(
            f"TradeScore {trade_score_id} not found",
            hint="Call compute_trade_score first",
        )

    hyp = retriever.get_hypothesis(score.hypothesis_id)
    if not hyp:
        return ToolResult.error(f"Hypothesis {score.hypothesis_id} not found")

    valuation = retriever.get_valuation(score.valuation_id) if score.valuation_id else None

    supporting = [
        e.reasoning for e in hyp.evidence_log if e.direction == "supports"
    ]
    refuting = [
        e.reasoning for e in hyp.evidence_log if e.direction == "refutes"
    ]
    belief_trajectory = [
        {"evidence_id": e.id, "direction": e.direction, "driver": e.driver_link}
        for e in hyp.evidence_log
    ]

    audit = AuditTrail(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        company=hyp.company,
        documents_used=documents_used,
        observations_extracted=len(hyp.evidence_log),
        evidence_supporting=supporting,
        evidence_refuting=refuting,
        belief_trajectory=belief_trajectory,
        valuation_method=valuation.methodology if valuation else "none",
        key_assumptions=[a.name for a in valuation.key_assumptions] if valuation else [],
        raw_trade_score=score.raw_score,
        constrained_trade_score=score.constrained_score,
        constraint_reasons=score.constraint_reasons,
        final_recommendation=score.recommendation,
        soul_deviations=soul_deviations or [],
        model_used=os.getenv("OPENAI_MODEL", "gpt-4o"),
        timestamp=datetime.now(),
        total_llm_calls=0,
    )
    retriever.save_audit_trail(audit)

    return ToolResult.ok({
        "audit_id": audit.id,
        "company": audit.company,
        "final_recommendation": audit.final_recommendation,
        "constrained_score": audit.constrained_trade_score,
        "evidence_count": len(hyp.evidence_log),
        "documents_used": len(documents_used),
    })


def query_knowledge(
    retriever: EvidenceRetriever,
    subject: str,
    object_type: str = "both",
) -> ToolResult:
    result: dict = {}
    if object_type in ("observations", "both"):
        obs = retriever.query_observations(subject=subject)
        result["observations"] = [
            {"id": o.id, "claim": o.claim, "source": o.source, "relevance": o.relevance}
            for o in obs
        ]
    if object_type in ("hypotheses", "both"):
        hyps = retriever.list_hypotheses(company=subject)
        result["hypotheses"] = [
            {"id": h.id, "thesis": h.thesis, "confidence": h.confidence,
             "evidence_count": len(h.evidence_log)}
            for h in hyps
        ]
    return ToolResult.ok(result)


def _score_to_recommendation(score: float) -> str:
    if score >= 85:
        return "HIGH_CONVICTION"
    elif score >= 75:
        return "INITIATE_SMALL"
    elif score >= 65:
        return "CANDIDATE"
    elif score >= 50:
        return "RESEARCH_MORE"
    return "WATCH"
