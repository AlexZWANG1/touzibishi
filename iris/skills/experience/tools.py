"""
Experience Library Skill — FLEX-inspired self-learning system.

The experience library is a persistent, structured knowledge base that accumulates
validated lessons from analysis outcomes. It implements the FLEX (Forward Learning
from Experience) architecture: the LLM's weights are frozen, but the reference
library it consults continuously improves.

Tools:
  recall_experiences:  Retrieve relevant experiences before making judgments
  save_experience:     Write a new experience entry (golden/warning zone)
  run_reflection:      Compare predictions vs actuals, generate experience entries
  distill_patterns:    Cross-company pattern extraction from accumulated experiences
"""

import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from core.config import get_skill_config
from tools.base import Tool, ToolResult, make_tool_schema


# ── Storage layer ────────────────────────────────────────────

def _library_path() -> Path:
    return Path("memory") / "experience_library.json"


def _load_library() -> dict:
    p = _library_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"experiences": [], "attribution_log": [], "metadata": {"created": date.today().isoformat()}}


def _save_library(library: dict):
    p = _library_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    library["metadata"]["last_updated"] = datetime.now().isoformat()
    library["metadata"]["entry_count"] = len(library["experiences"])
    p.write_text(json.dumps(library, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


def _similarity_score(a: str, b: str) -> float:
    """Simple token-overlap similarity. Good enough for dedup; semantic search
    is available via SQLiteRetriever for cross-domain retrieval."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ── Tool Schemas ─────────────────────────────────────────────

RECALL_EXPERIENCES_SCHEMA = make_tool_schema(
    name="recall_experiences",
    description=(
        "Retrieve relevant experiences from the library before making predictions "
        "or assumptions. ALWAYS call this before build_dcf or generate_trade_signal.\n\n"
        "Returns Warning Zone entries (you MUST address these in your reasoning) "
        "and Golden Zone entries (useful reference patterns).\n\n"
        "Pass the company ticker and what you're about to judge (e.g., 'revenue growth prediction')."
    ),
    properties={
        "company": {
            "type": "string",
            "description": "Company ticker, e.g. 'NVDA'",
        },
        "sector": {
            "type": "string",
            "description": "Company sector for cross-company pattern matching",
        },
        "context": {
            "type": "string",
            "description": "What judgment you're about to make, e.g. 'predicting DC revenue growth for Q1'",
        },
    },
    required=["company", "context"],
)

SAVE_EXPERIENCE_SCHEMA = make_tool_schema(
    name="save_experience",
    description=(
        "Save a new experience entry to the library. Call this after run_attribution "
        "generates suggestions, or when you discover a notable pattern during research.\n\n"
        "The system automatically deduplicates: if a very similar entry exists, "
        "it will merge or skip rather than create duplicates."
    ),
    properties={
        "zone": {
            "type": "string", "enum": ["golden", "warning"],
            "description": "Golden = what worked/was accurate. Warning = what failed/was wrong.",
        },
        "level": {
            "type": "string", "enum": ["strategic", "pattern", "factual"],
            "description": (
                "Strategic = broad principle (needs human confirmation to add). "
                "Pattern = repeatable method or tendency. "
                "Factual = specific verified fact or prediction error."
            ),
        },
        "content": {
            "type": "string",
            "description": "The experience in one clear sentence. Be specific and actionable.",
        },
        "companies": {
            "type": "array", "items": {"type": "string"},
            "description": "Company tickers this experience relates to",
        },
        "sector": {
            "type": "string",
            "description": "Sector if this is a cross-company pattern",
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "metric": {"type": "string"},
                    "predicted": {"type": "number"},
                    "actual": {"type": "number"},
                    "source": {"type": "string"},
                },
            },
            "description": "Supporting evidence instances (optional but strengthens the entry)",
        },
        "confidence": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "How confident in this experience (0.5 = tentative, 0.8+ = well-established)",
        },
        "source_attribution_id": {
            "type": "string",
            "description": "ID of the attribution that generated this experience (if any)",
        },
        "methodology": {
            "type": "object",
            "description": (
                "Procedural knowledge: what method you used, what went wrong, "
                "what to do next time. Be specific about tools and data sources."
            ),
            "properties": {
                "what_i_did": {"type": "string", "description": "Method used in this analysis"},
                "what_went_wrong": {"type": "string", "description": "Filled during reflection: why the prediction deviated"},
                "what_to_do_next": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Filled during reflection: actionable steps for next time",
                },
            },
        },
    },
    required=["content", "companies", "confidence"],
)

RUN_REFLECTION_SCHEMA = make_tool_schema(
    name="run_reflection",
    description=(
        "Systematic reflection session: compare original predictions against actual "
        "results. This is the core learning loop.\n\n"
        "Call this when actual data becomes available (e.g., quarterly earnings released).\n\n"
        "Generates:\n"
        "1. Assumption-level error analysis (which assumptions were wrong, by how much)\n"
        "2. Reasoning chain review (why were they wrong)\n"
        "3. Experience library entries (golden/warning zone suggestions)\n"
        "4. Calibration bias update\n\n"
        "AI must answer 5 reflection questions for each reflection session."
    ),
    properties={
        "company": {"type": "string", "description": "Company ticker"},
        "prediction_date": {"type": "string", "description": "Date of original analysis (YYYY-MM-DD)"},
        "original_assumptions": {
            "type": "object",
            "description": (
                "Key assumptions from original analysis. Example:\n"
                "{'revenue_growth': 0.35, 'gross_margin': 0.745, 'opex_ratio': 0.165, "
                "'capex_pct': 0.07, 'tax_rate': 0.12}"
            ),
        },
        "actual_results": {
            "type": "object",
            "description": "Actual results from earnings/data. Same keys as original_assumptions.",
        },
        "original_fair_value": {
            "type": "number",
            "description": "Fair value per share from original DCF",
        },
        "original_reasoning": {
            "type": "string",
            "description": (
                "Key reasoning from the original analysis — why you made these assumptions. "
                "This is reviewed during reflection to identify where thinking went wrong."
            ),
        },
        "hypothesis_id": {"type": "string", "description": "Linked hypothesis ID"},
    },
    required=["company", "original_assumptions", "actual_results", "hypothesis_id"],
)

DISTILL_PATTERNS_SCHEMA = make_tool_schema(
    name="distill_patterns",
    description=(
        "Extract cross-company patterns from accumulated factual experiences. "
        "Call this after 5+ attribution records have been generated.\n\n"
        "Looks for repeated patterns across different companies to generate "
        "sector-level or strategic-level experience entries.\n\n"
        "Example: if 3 semiconductor companies all show management guidance "
        "underestimation, this distills into a sector-level pattern."
    ),
    properties={
        "sector": {
            "type": "string",
            "description": "Sector to analyze for cross-company patterns (optional, analyzes all if omitted)",
        },
        "min_occurrences": {
            "type": "integer",
            "description": "Minimum times a pattern must appear across companies (default: from config)",
        },
    },
    required=[],
)


# ── Tool Implementations ─────────────────────────────────────

def recall_experiences(
    company: str,
    context: str,
    sector: str = "",
) -> ToolResult:
    """Retrieve relevant experiences using company match + sector match + content match."""
    cfg = get_skill_config("experience")
    retrieval_cfg = cfg.get("retrieval", {})
    top_k = retrieval_cfg.get("top_k", 5)
    company_boost = retrieval_cfg.get("company_boost", 1.0)
    sector_boost = retrieval_cfg.get("sector_boost", 0.7)
    semantic_boost = retrieval_cfg.get("semantic_boost", 0.5)
    min_confidence = retrieval_cfg.get("min_confidence", 0.3)

    library = _load_library()
    experiences = library.get("experiences", [])

    if not experiences:
        return ToolResult.ok({
            "warning_zone": [],
            "golden_zone": [],
            "message": "Experience library is empty. This is your first analysis — no prior lessons to recall.",
            "total_library_size": 0,
        })

    # Score each experience by relevance
    scored = []
    company_upper = company.upper()
    sector_lower = sector.lower() if sector else ""

    for exp in experiences:
        if exp.get("status") != "active":
            continue
        if exp.get("confidence", 0) < min_confidence:
            continue

        relevance = 0.0

        # Company direct match
        exp_companies = [c.upper() for c in exp.get("companies", [])]
        if company_upper in exp_companies:
            relevance += company_boost

        # Sector match (for pattern/strategic level entries)
        exp_sector = (exp.get("sector") or "").lower()
        if sector_lower and exp_sector == sector_lower and exp.get("level") in ("strategic", "pattern"):
            relevance += sector_boost

        # Content similarity to current context
        content_sim = _similarity_score(context, exp.get("content", ""))
        relevance += content_sim * semantic_boost

        # Quality weighting
        quality = exp.get("confidence", 0.5)
        useful_ratio = 1.0
        if exp.get("times_retrieved", 0) > 0:
            useful_ratio = exp.get("times_useful", 0) / exp["times_retrieved"]
        relevance *= quality * max(useful_ratio, 0.3)  # floor at 0.3 to not kill new entries

        if relevance > 0.01:
            scored.append((exp, relevance))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_entries = scored[:top_k]

    # Update retrieval counts
    for exp, _ in top_entries:
        exp["times_retrieved"] = exp.get("times_retrieved", 0) + 1

    _save_library(library)

    # Split into zones (entries without zone, e.g. from analysis mode, are excluded)
    warnings = [
        {
            "id": e["id"],
            "content": e["content"],
            "level": e.get("level", "factual"),
            "confidence": e.get("confidence", 0.5),
            "evidence_count": e.get("evidence_count", 0),
            "companies": e.get("companies", []),
            "methodology": e.get("methodology"),
        }
        for e, _ in top_entries if e.get("zone") == "warning"
    ]
    goldens = [
        {
            "id": e["id"],
            "content": e["content"],
            "level": e.get("level", "factual"),
            "confidence": e.get("confidence", 0.5),
            "evidence_count": e.get("evidence_count", 0),
            "companies": e.get("companies", []),
            "methodology": e.get("methodology"),
        }
        for e, _ in top_entries if e.get("zone") == "golden"
    ]

    return ToolResult.ok({
        "warning_zone": warnings,
        "golden_zone": goldens,
        "total_library_size": len(experiences),
        "instruction": (
            "You MUST explicitly address each Warning Zone entry in your analysis. "
            "Explain whether you adjusted your assumptions based on the warning, and why."
            if warnings else
            "No warnings for this context. Golden entries are reference patterns."
        ),
    })


def save_experience(
    zone: str = None,
    level: str = None,
    content: str = "",
    companies: list[str] = None,
    confidence: float = 0.5,
    sector: str = "",
    evidence: list[dict] = None,
    source_attribution_id: str = "",
    methodology: dict = None,
) -> ToolResult:
    """Save a new experience entry with FLEX-style three-way dedup."""
    # Mode-awareness: in analysis mode, strip zone/level
    runtime_cfg = get_skill_config("_runtime")
    current_mode = runtime_cfg.get("mode", "learning") if runtime_cfg else "learning"
    if current_mode == "analysis":
        zone = None
        level = None

    companies = companies or []

    cfg = get_skill_config("experience")
    update_cfg = cfg.get("update", {})
    quality_cfg = cfg.get("quality", {})
    dup_threshold = update_cfg.get("duplicate_threshold", 0.90)
    merge_threshold = update_cfg.get("merge_threshold", 0.70)
    max_size = quality_cfg.get("max_library_size", 500)

    # Strategic level needs human confirmation — flag it
    if level == "strategic":
        return ToolResult.ok({
            "status": "pending_confirmation",
            "message": (
                "Strategic-level experience entries need human confirmation. "
                "Presenting for review."
            ),
            "proposed_entry": {
                "zone": zone,
                "level": level,
                "content": content,
                "companies": companies,
                "confidence": confidence,
                "methodology": methodology,
            },
        })

    library = _load_library()
    experiences = library.get("experiences", [])

    # Size check
    active_count = sum(1 for e in experiences if e.get("status") == "active")
    if active_count >= max_size:
        # Expire lowest-confidence entry
        active = [e for e in experiences if e.get("status") == "active"]
        active.sort(key=lambda e: e.get("confidence", 0))
        if active:
            active[0]["status"] = "expired"
            active[0]["expired_reason"] = "library_full_lowest_confidence"

    # Three-way dedup check
    best_match = None
    best_sim = 0.0
    for exp in experiences:
        if exp.get("status") != "active":
            continue
        sim = _similarity_score(content, exp.get("content", ""))
        if sim > best_sim:
            best_sim = sim
            best_match = exp

    if best_sim >= dup_threshold and best_match:
        # Duplicate — update existing
        best_match["evidence_count"] = best_match.get("evidence_count", 0) + 1
        best_match["last_validated"] = date.today().isoformat()
        if evidence:
            existing_evidence = best_match.get("evidence", [])
            existing_evidence.extend(evidence)
            best_match["evidence"] = existing_evidence
        _save_library(library)
        return ToolResult.ok({
            "action": "deduplicated",
            "existing_id": best_match["id"],
            "message": f"Merged with existing entry (similarity {best_sim:.2f}). Evidence count now {best_match['evidence_count']}.",
        })

    if best_sim >= merge_threshold and best_match:
        # Similar — merge content
        merged_content = best_match["content"]
        if len(content) > len(merged_content):
            best_match["content"] = content  # keep richer version
        best_match["evidence_count"] = best_match.get("evidence_count", 0) + 1
        best_match["last_validated"] = date.today().isoformat()
        best_match["confidence"] = max(best_match.get("confidence", 0.5), confidence)
        if evidence:
            existing_evidence = best_match.get("evidence", [])
            existing_evidence.extend(evidence)
            best_match["evidence"] = existing_evidence
        # Merge company lists
        merged_companies = list(set(best_match.get("companies", []) + companies))
        best_match["companies"] = merged_companies
        _save_library(library)
        return ToolResult.ok({
            "action": "merged",
            "existing_id": best_match["id"],
            "message": f"Merged with similar entry (similarity {best_sim:.2f}). Kept richer content.",
        })

    # Novel — insert new
    zone_prefix = zone[0] if zone else "p"  # "p" for pending (analysis mode)
    new_id = f"exp_{zone_prefix}_{uuid.uuid4().hex[:6]}"
    new_entry = {
        "id": new_id,
        "zone": zone,
        "level": level,
        "content": content,
        "companies": [c.upper() for c in companies],
        "sector": sector,
        "confidence": confidence,
        "evidence_count": len(evidence) if evidence else 1,
        "evidence": evidence or [],
        "source_attribution_id": source_attribution_id,
        "methodology": methodology,
        "times_retrieved": 0,
        "times_useful": 0,
        "created_at": datetime.now().isoformat(),
        "last_validated": date.today().isoformat(),
        "status": "active",
    }
    experiences.append(new_entry)
    library["experiences"] = experiences
    _save_library(library)

    return ToolResult.ok({
        "action": "inserted",
        "id": new_id,
        "zone": zone,
        "level": level,
        "message": f"New {zone}/{level} experience saved.",
    })


def run_reflection(
    company: str,
    original_assumptions: dict,
    actual_results: dict,
    hypothesis_id: str,
    prediction_date: str = "",
    original_fair_value: float = None,
    original_reasoning: str = "",
) -> ToolResult:
    """
    Core learning loop: compare predictions to actuals, generate experiences.

    Returns structured output that the AI must use to:
    1. Answer 5 reflection questions
    2. Generate experience library entries
    3. Update calibration records
    """
    cfg = get_skill_config("experience")
    reflection_cfg = cfg.get("reflection", {})
    min_error_warning = reflection_cfg.get("min_error_for_warning", 0.03)
    min_accuracy_golden = reflection_cfg.get("min_accuracy_for_golden", 0.02)

    # Step 1: Compute assumption-level errors
    errors = {}
    for key in original_assumptions:
        predicted = original_assumptions[key]
        actual = actual_results.get(key)
        if actual is not None and isinstance(predicted, (int, float)) and isinstance(actual, (int, float)):
            error = predicted - actual
            errors[key] = {
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "error": round(error, 4),
                "abs_error": round(abs(error), 4),
                "direction": "overestimate" if error > 0 else "underestimate",
                "is_significant": abs(error) >= min_error_warning,
            }

    # Step 2: Rank by error magnitude
    ranked = sorted(errors.items(), key=lambda x: x[1]["abs_error"], reverse=True)

    # Step 3: Generate experience suggestions
    experience_suggestions = []

    for key, err in ranked:
        if err["abs_error"] >= min_error_warning:
            experience_suggestions.append({
                "zone": "warning",
                "level": "factual",
                "content": (
                    f"{company}: {key} was {err['direction']}d by "
                    f"{err['abs_error']*100:.1f}pp "
                    f"(predicted {err['predicted']:.3f}, actual {err['actual']:.3f})"
                ),
                "confidence": 0.7,
                "evidence": [{
                    "date": date.today().isoformat(),
                    "metric": key,
                    "predicted": err["predicted"],
                    "actual": err["actual"],
                    "source": "quarterly_earnings",
                }],
            })
        elif err["abs_error"] <= min_accuracy_golden:
            experience_suggestions.append({
                "zone": "golden",
                "level": "factual",
                "content": (
                    f"{company}: {key} prediction was accurate "
                    f"(predicted {err['predicted']:.3f}, actual {err['actual']:.3f}, "
                    f"error {err['abs_error']*100:.1f}pp)"
                ),
                "confidence": 0.6,
                "evidence": [{
                    "date": date.today().isoformat(),
                    "metric": key,
                    "predicted": err["predicted"],
                    "actual": err["actual"],
                    "source": "quarterly_earnings",
                }],
            })

    # Step 4: Log the attribution
    library = _load_library()
    attribution_id = f"attr_{uuid.uuid4().hex[:8]}"
    attribution_record = {
        "id": attribution_id,
        "company": company.upper(),
        "hypothesis_id": hypothesis_id,
        "prediction_date": prediction_date,
        "reflection_date": date.today().isoformat(),
        "assumptions_compared": len(errors),
        "significant_errors": sum(1 for e in errors.values() if e["is_significant"]),
        "largest_error": ranked[0][0] if ranked else None,
        "errors": dict(ranked),
    }
    library.setdefault("attribution_log", []).append(attribution_record)
    _save_library(library)

    # Step 5: Check for bias patterns (consecutive same-direction errors)
    bias_check = _check_bias_pattern(library, company.upper())

    return ToolResult.ok({
        "attribution_id": attribution_id,
        "company": company.upper(),
        "errors": dict(ranked),
        "largest_error_source": ranked[0][0] if ranked else None,
        "experience_suggestions": experience_suggestions,
        "bias_check": bias_check,
        "reflection_questions": [
            f"1. 最大误差源是 {ranked[0][0] if ranked else 'N/A'}（误差 {ranked[0][1]['abs_error']*100:.1f}pp）。它对 fair value 影响多大？",
            "2. 回溯原始推理链：你当时的逻辑哪里出了问题？",
            "3. 你当时用了哪些经验库条目？它们的建议足够吗？",
            "4. 这个错误是系统性的还是一次性事件？",
            "5. 下次分析同一家公司时，你会改变什么？",
        ],
        "instruction": (
            "You MUST answer all 5 reflection questions above in your response. "
            "Then call save_experience for each suggestion in experience_suggestions. "
            "This is how you learn."
        ),
    })


def _check_bias_pattern(library: dict, company: str) -> dict:
    """Check attribution log for systematic bias patterns."""
    attributions = [
        a for a in library.get("attribution_log", [])
        if a.get("company") == company
    ]

    if len(attributions) < 2:
        return {"pattern_detected": False, "message": "Not enough data for bias detection."}

    # Check if the largest error has been in the same direction repeatedly
    directions = []
    metrics = []
    for attr in attributions[-5:]:  # last 5
        largest = attr.get("largest_error")
        if largest and largest in attr.get("errors", {}):
            err_data = attr["errors"][largest]
            directions.append(err_data.get("direction"))
            metrics.append(largest)

    if len(directions) >= 3:
        same_direction_count = max(
            directions.count("overestimate"),
            directions.count("underestimate"),
        )
        if same_direction_count >= 3:
            dominant = "overestimate" if directions.count("overestimate") > directions.count("underestimate") else "underestimate"
            return {
                "pattern_detected": True,
                "direction": dominant,
                "consecutive_count": same_direction_count,
                "affected_metrics": list(set(metrics)),
                "message": (
                    f"Systematic {dominant} detected: {same_direction_count} out of "
                    f"last {len(directions)} attributions show {dominant}. "
                    f"Consider creating a Warning Zone pattern entry."
                ),
            }

    return {"pattern_detected": False, "message": "No systematic bias detected."}


def distill_patterns(
    sector: str = "",
    min_occurrences: int = None,
) -> ToolResult:
    """
    Cross-company pattern extraction from accumulated factual experiences.
    Identifies repeated patterns that should be elevated to sector/strategic level.
    """
    cfg = get_skill_config("experience")
    distill_cfg = cfg.get("distillation", {})
    default_min = distill_cfg.get("cross_company_pattern_threshold", 3)
    min_occ = min_occurrences or default_min

    library = _load_library()
    experiences = [
        e for e in library.get("experiences", [])
        if e.get("status") == "active" and e.get("level") == "factual"
    ]

    if sector:
        experiences = [e for e in experiences if (e.get("sector") or "").lower() == sector.lower()]

    if len(experiences) < min_occ:
        return ToolResult.ok({
            "patterns_found": [],
            "message": f"Not enough factual experiences to distill ({len(experiences)} found, need {min_occ}).",
        })

    # Group by error direction + metric type
    patterns = {}
    for exp in experiences:
        content = exp.get("content", "")
        zone = exp.get("zone", "")

        # Extract metric name from content (simple heuristic)
        for metric in ["revenue_growth", "gross_margin", "opex_ratio", "capex_pct", "tax_rate"]:
            if metric in content.lower().replace(" ", "_"):
                key = f"{zone}:{metric}"
                patterns.setdefault(key, []).append(exp)
                break

    # Find patterns that appear across multiple companies
    cross_company_patterns = []
    for key, entries in patterns.items():
        unique_companies = set()
        for entry in entries:
            unique_companies.update(entry.get("companies", []))

        if len(unique_companies) >= min_occ:
            zone, metric = key.split(":", 1)
            # Compute average error
            all_evidence = []
            for entry in entries:
                all_evidence.extend(entry.get("evidence", []))

            avg_error = None
            if all_evidence:
                errors = [
                    e["predicted"] - e["actual"]
                    for e in all_evidence
                    if "predicted" in e and "actual" in e
                ]
                if errors:
                    avg_error = sum(errors) / len(errors)

            cross_company_patterns.append({
                "zone": zone,
                "metric": metric,
                "companies": sorted(unique_companies),
                "company_count": len(unique_companies),
                "instance_count": len(entries),
                "avg_error": round(avg_error, 4) if avg_error is not None else None,
                "suggested_content": (
                    f"{sector or 'Cross-sector'}: {metric.replace('_', ' ')} consistently "
                    f"{'over' if avg_error and avg_error > 0 else 'under'}estimated "
                    f"across {len(unique_companies)} companies "
                    f"(avg error: {abs(avg_error)*100:.1f}pp)"
                    if avg_error is not None else
                    f"{sector or 'Cross-sector'}: {metric.replace('_', ' ')} shows "
                    f"repeated {zone} pattern across {len(unique_companies)} companies"
                ),
                "suggested_level": "pattern" if len(unique_companies) < 5 else "strategic",
            })

    return ToolResult.ok({
        "patterns_found": cross_company_patterns,
        "total_factual_experiences_analyzed": len(experiences),
        "instruction": (
            "For each pattern found, call save_experience with the suggested content "
            "and elevated level. Strategic-level patterns will require human confirmation."
            if cross_company_patterns else
            "No cross-company patterns detected yet. Continue accumulating factual experiences."
        ),
    })


# ── Utility: mark experience as useful ───────────────────────

def _mark_useful(experience_id: str):
    """Called by AI after an experience influenced its judgment."""
    library = _load_library()
    for exp in library.get("experiences", []):
        if exp["id"] == experience_id:
            exp["times_useful"] = exp.get("times_useful", 0) + 1
            break
    _save_library(library)


# ── Registration ─────────────────────────────────────────────

def register(context: dict) -> list[Tool]:
    """Called by skill_loader with shared dependencies."""
    return [
        Tool(recall_experiences, RECALL_EXPERIENCES_SCHEMA),
        Tool(save_experience, SAVE_EXPERIENCE_SCHEMA),
        Tool(run_reflection, RUN_REFLECTION_SCHEMA),
        Tool(distill_patterns, DISTILL_PATTERNS_SCHEMA),
    ]
