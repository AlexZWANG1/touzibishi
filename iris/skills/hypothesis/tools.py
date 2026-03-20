"""
Hypothesis Tracking Skill.

Tools: create_hypothesis, add_evidence_card
"""

import uuid
from datetime import datetime

from core.config import get_skill_config
from core.schemas import Driver, KillCriterion, EvidenceCard, Hypothesis
from tools.base import Tool, ToolResult, make_tool_schema
from tools.retrieval import EvidenceRetriever


# ── Tool Schemas ──────────────────────────────────────────────

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
            "type": "number", "minimum": 0, "maximum": 100,
            "description": "Starting confidence 0-100. Use 50 if genuinely uncertain.",
        },
    },
    required=["company", "thesis", "timeframe", "drivers", "kill_criteria", "initial_confidence"],
)

ADD_EVIDENCE_CARD_SCHEMA = make_tool_schema(
    name="add_evidence_card",
    description=(
        "Evaluate evidence for/against the hypothesis and update belief confidence "
        "with a Bayesian-style score update."
    ),
    properties={
        "hypothesis_id": {"type": "string", "description": "ID from create_hypothesis"},
        "observation_id": {
            "type": "string",
            "description": "Optional existing observation ID. If omitted, tool will create an inline evidence ID.",
        },
        "evidence_text": {
            "type": "string",
            "description": "Optional short evidence statement when no observation_id is provided.",
        },
        "direction": {"type": "string", "enum": ["supports", "refutes", "mixed", "neutral"]},
        "reliability": {"type": "number", "minimum": 0, "maximum": 1, "description": "Source credibility (earnings call=0.9, blog=0.3)"},
        "independence": {"type": "number", "minimum": 0, "maximum": 1, "description": "How independent from existing evidence"},
        "novelty": {"type": "number", "minimum": 0, "maximum": 1, "description": "How new/surprising is this information"},
        "driver_link": {"type": "string", "description": "Which driver this evidence relates to"},
        "reasoning": {"type": "string", "description": "Why you rated direction/reliability/independence/novelty this way"},
    },
    required=["hypothesis_id", "direction", "reliability",
              "independence", "novelty", "driver_link", "reasoning"],
)

# ── Tool Implementations ──────────────────────────────────────

def create_hypothesis(
    retriever: EvidenceRetriever,
    company: str, thesis: str, timeframe: str,
    drivers: list[dict], kill_criteria: list[dict],
    initial_confidence: float,
) -> ToolResult:
    if not (0 <= initial_confidence <= 100):
        return ToolResult.fail(
            f"initial_confidence {initial_confidence} out of range [0, 100]"
        )
    if len(drivers) < 3:
        return ToolResult.fail(
            f"At least 3 drivers required, got {len(drivers)}",
            hint="Identify the key factors that must hold true for the thesis to work",
        )
    if len(drivers) > 6:
        return ToolResult.fail(
            f"Maximum 6 drivers allowed, got {len(drivers)}",
            hint="Focus on the most important factors",
        )
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
        return ToolResult.fail(f"Failed to create hypothesis: {e}")


def add_evidence_card(
    retriever: EvidenceRetriever,
    hypothesis_id: str,
    direction: str, reliability: float, independence: float,
    novelty: float, driver_link: str, reasoning: str,
    observation_id: str = "",
    evidence_text: str = "",
) -> ToolResult:
    if not reasoning.strip():
        return ToolResult.fail(
            "reasoning must not be empty",
            hint="Explain why you rated direction/reliability/independence/novelty as you did",
        )

    hyp = retriever.get_hypothesis(hypothesis_id)
    if not hyp:
        return ToolResult.fail(
            f"Hypothesis {hypothesis_id} not found",
            hint="Call create_hypothesis first or check the ID"
        )

    card = EvidenceCard(
        id=f"ev_{uuid.uuid4().hex[:8]}",
        observation_id=observation_id or f"obs_inline_{uuid.uuid4().hex[:8]}",
        hypothesis_id=hypothesis_id,
        direction=direction,
        reliability=reliability,
        independence=independence,
        novelty=novelty,
        driver_link=driver_link,
        reasoning=reasoning,
        created_at=datetime.now(),
    )

    # Bayesian update — formula is deterministic, parameters from skill config
    skill_cfg = get_skill_config("hypothesis")
    direction_map = skill_cfg.get("direction_map", {"supports": 1.0, "refutes": -1.0, "mixed": 0.2, "neutral": 0.0})
    scaling = skill_cfg.get("scaling_factor", 10)
    sign = direction_map.get(direction, 0)
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
        "observation_id": card.observation_id,
        "evidence_text": evidence_text or None,
        "direction": direction,
        "old_confidence": round(old_confidence, 1),
        "delta": round(delta, 2),
        "new_confidence": round(hyp.confidence, 1),
    })


# ── Registration ──────────────────────────────────────────────

def register(context: dict) -> list[Tool]:
    """Called by skill_loader with shared dependencies."""
    retriever = context.get("retriever")
    if retriever is None:
        raise ValueError("hypothesis skill requires 'retriever' in context")

    return [
        Tool(create_hypothesis, CREATE_HYPOTHESIS_SCHEMA, retriever=retriever),
        Tool(add_evidence_card, ADD_EVIDENCE_CARD_SCHEMA, retriever=retriever),
    ]
