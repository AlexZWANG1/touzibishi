"""
IRIS Unified Memory System — remember and recall tools.

Replaces the fragmented memory system (13 tools, 9 storage locations) with
2 primary tools backed by a single knowledge_items table in SQLite.
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from core.config import get as config_get, get_skill_config
from tools.base import Tool, ToolResult, make_tool_schema
from tools.retrieval import EvidenceRetriever


# ── Schemas ──────────────────────────────────────────────────

REMEMBER_SCHEMA = make_tool_schema(
    name="remember",
    description=(
        "Save any piece of knowledge to memory: observations, experiences, analysis notes, "
        "or predictions. Everything saved here is automatically indexed for semantic search "
        "and will appear in future analysis sessions via auto-recall."
    ),
    properties={
        "type": {
            "type": "string",
            "enum": ["observation", "experience", "note", "prediction"],
            "description": "What kind of knowledge this is",
        },
        "subject": {
            "type": "string",
            "description": "Company ticker or topic (e.g. 'NVDA', 'semiconductors')",
        },
        "content": {
            "type": "string",
            "description": "The main text content — a fact, lesson, analysis summary, or prediction",
        },
        "zone": {
            "type": "string",
            "enum": ["golden", "warning"],
            "description": "For experiences: golden (what worked) or warning (what failed)",
        },
        "level": {
            "type": "string",
            "enum": ["factual", "pattern", "strategic"],
            "description": "For experiences: factual, pattern, or strategic (needs human confirmation)",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence level (0-1)",
        },
        "source": {
            "type": "string",
            "description": "Where this knowledge came from. If this is an existing knowledge_item ID, that item gets credit for being useful.",
        },
        "methodology": {
            "type": "object",
            "description": "For experiences: what method was used, what went wrong, what to do next time",
            "properties": {
                "what_i_did": {"type": "string"},
                "what_went_wrong": {"type": "string"},
                "what_to_do_next": {"type": "array", "items": {"type": "string"}},
            },
        },
        "evidence": {
            "type": "array",
            "items": {"type": "object"},
            "description": "For experiences: supporting evidence instances",
        },
        "note_category": {
            "type": "string",
            "enum": ["company", "sector", "patterns"],
            "description": "For notes: what kind of note",
        },
        "metric": {
            "type": "string",
            "description": "For predictions: what metric is being predicted",
        },
        "predicted": {
            "type": "number",
            "description": "For predictions: the predicted value",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional tags for categorization",
        },
    },
    required=["type", "content"],
)


RECALL_SCHEMA = make_tool_schema(
    name="recall",
    description=(
        "Search your AI memory — observations, experiences, analysis notes, predictions, "
        "and hypotheses you have previously saved. NOT for user-uploaded documents "
        "(use search_knowledge for that)."
    ),
    properties={
        "subject": {
            "type": "string",
            "description": "Company ticker or topic to focus on",
        },
        "context": {
            "type": "string",
            "description": "What you're trying to do — e.g. 'preparing DCF assumptions for revenue growth'",
        },
        "types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["observation", "experience", "note", "prediction", "hypothesis"],
            },
            "description": "Filter by knowledge type. Omit to search all AI memory types.",
        },
    },
    required=["context"],
)


SEARCH_KNOWLEDGE_SCHEMA = make_tool_schema(
    name="search_knowledge",
    description=(
        "Search the user-uploaded knowledge base — research reports, articles, notes, "
        "and documents the user has added. Returns relevant passages with source citations."
    ),
    properties={
        "query": {
            "type": "string",
            "description": "Natural language search query, e.g. 'NVDA data center revenue drivers'",
        },
        "top_k": {
            "type": "integer",
            "description": "Max results to return. Default 5.",
        },
        "company": {
            "type": "string",
            "description": "Optional: filter by company ticker",
        },
    },
    required=["query"],
)


# ── remember implementation ──────────────────────────────────

def remember(
    retriever: EvidenceRetriever,
    type: str,
    content: str,
    subject: str = "",
    zone: str = None,
    level: str = None,
    confidence: float = None,
    source: str = "",
    methodology: dict = None,
    evidence: list = None,
    note_category: str = None,
    metric: str = None,
    predicted: float = None,
    tags: list = None,
) -> ToolResult:
    """Save any piece of knowledge to the unified memory system."""
    # Track source usefulness (Section 5)
    if source:
        _track_source_useful(retriever, source)

    if type == "experience":
        return _remember_experience(
            retriever, content=content, subject=subject, zone=zone, level=level,
            confidence=confidence or 0.5, source=source, methodology=methodology,
            evidence=evidence, tags=tags,
        )
    elif type == "observation":
        return _remember_observation(
            retriever, content=content, subject=subject, confidence=confidence,
            source=source, tags=tags,
        )
    elif type == "note":
        return _remember_note(
            retriever, content=content, subject=subject,
            note_category=note_category, source=source, tags=tags,
        )
    elif type == "prediction":
        return _remember_prediction(
            retriever, content=content, subject=subject, metric=metric,
            predicted=predicted, source=source, tags=tags,
        )
    else:
        return ToolResult.fail(
            f"Unknown type: {type}",
            hint="Use: observation, experience, note, prediction",
        )


def _remember_experience(retriever, *, content, subject, zone, level, confidence,
                         source, methodology, evidence, tags):
    """Save experience with three-way dedup using embedding similarity."""

    # Mode awareness
    runtime_cfg = get_skill_config("_runtime")
    current_mode = runtime_cfg.get("mode", "learning") if runtime_cfg else "learning"
    if current_mode == "analysis":
        zone = None
        level = None

    # Strategic level needs human confirmation
    if level == "strategic":
        return ToolResult.ok({
            "status": "pending_confirmation",
            "message": "Strategic-level experience entries need human confirmation.",
            "proposed_entry": {
                "zone": zone, "level": level, "content": content,
                "subject": subject, "confidence": confidence, "methodology": methodology,
            },
        })

    # Read dedup thresholds from config
    cfg = get_skill_config("experience")
    update_cfg = cfg.get("update", {}) if cfg else {}
    dup_threshold = update_cfg.get("duplicate_threshold", 0.90)
    merge_threshold = update_cfg.get("merge_threshold", 0.70)

    # Check for similar existing experiences using embedding search
    best_match = None
    best_sim = 0.0
    try:
        search_query = f"{subject}: {content}" if subject else content
        search_results = retriever.semantic_search(
            search_query, top_k=5, source_type="experience",
        )
        for sr in search_results:
            item = retriever.get_knowledge_item(sr["id"])
            if item and item.get("type") == "experience":
                sd = item.get("structured_data", {})
                if sd.get("status") != "active":
                    continue
                if sr["score"] > best_sim:
                    best_sim = sr["score"]
                    best_match = item
    except Exception:
        pass  # dedup is best-effort; if embedding fails, insert as novel

    # Three-way dedup
    if best_sim >= dup_threshold and best_match:
        sd = best_match["structured_data"]
        sd["evidence_count"] = sd.get("evidence_count", 0) + 1
        sd["last_validated"] = date.today().isoformat()
        if evidence:
            sd.setdefault("evidence", []).extend(evidence)
        retriever.update_knowledge_item_structured_data(best_match["id"], sd)
        return ToolResult.ok({
            "action": "deduplicated",
            "existing_id": best_match["id"],
            "message": f"Merged with existing entry (similarity {best_sim:.2f}). Evidence count now {sd['evidence_count']}.",
        })

    if best_sim >= merge_threshold and best_match:
        # Keep richer content
        if len(content) > len(best_match.get("content", "")):
            now = datetime.now(timezone.utc).isoformat()
            with retriever._conn() as conn:
                conn.execute(
                    "UPDATE knowledge_items SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, best_match["id"]),
                )
            retriever.save_embedding(best_match["id"], f"{subject}: {content}", "experience")
        sd = best_match["structured_data"]
        sd["evidence_count"] = sd.get("evidence_count", 0) + 1
        sd["last_validated"] = date.today().isoformat()
        if confidence and confidence > (best_match.get("confidence") or 0):
            with retriever._conn() as conn:
                conn.execute(
                    "UPDATE knowledge_items SET confidence = ? WHERE id = ?",
                    (confidence, best_match["id"]),
                )
        if evidence:
            sd.setdefault("evidence", []).extend(evidence)
        retriever.update_knowledge_item_structured_data(best_match["id"], sd)
        return ToolResult.ok({
            "action": "merged",
            "existing_id": best_match["id"],
            "message": f"Merged with similar entry (similarity {best_sim:.2f}). Kept richer content.",
        })

    # Novel — insert new
    structured_data = {
        "zone": zone,
        "level": level,
        "evidence": evidence or [],
        "evidence_count": len(evidence) if evidence else 1,
        "methodology": methodology,
        "times_retrieved": 0,
        "times_useful": 0,
        "status": "active",
    }

    item_id = retriever.save_knowledge_item(
        type="experience",
        subject=(subject or "").upper(),
        content=content,
        structured_data=structured_data,
        confidence=confidence,
        source=source,
        tags=tags,
    )

    return ToolResult.ok({
        "action": "inserted",
        "id": item_id,
        "zone": zone,
        "level": level,
        "message": f"New {zone or 'pending'}/{level or 'pending'} experience saved.",
    })


def _remember_observation(retriever, *, content, subject, confidence, source, tags):
    """Save an observation."""
    structured_data = {
        "fact_or_view": "fact",
        "relevance": confidence or 0.8,
        "source": source,
        "time": date.today().isoformat(),
    }

    item_id = retriever.save_knowledge_item(
        type="observation",
        subject=(subject or "").upper(),
        content=content,
        structured_data=structured_data,
        confidence=confidence,
        source=source,
        tags=tags,
    )

    return ToolResult.ok({"id": item_id, "subject": subject, "content": content})


def _remember_note(retriever, *, content, subject, note_category, source, tags):
    """Save an analysis note. Also exports markdown file for human readability."""
    structured_data = {"note_category": note_category or "company"}

    item_id = retriever.save_knowledge_item(
        type="note",
        subject=(subject or "").upper(),
        content=content,
        structured_data=structured_data,
        source=source,
        tags=tags,
    )

    # Export markdown file for human readability
    if subject:
        _export_note_markdown(subject, content, note_category)

    return ToolResult.ok({"id": item_id, "status": "ok", "subject": subject})


def _remember_prediction(retriever, *, content, subject, metric, predicted, source, tags):
    """Save a prediction with auto review_after date."""
    review_days = 90
    cfg = get_skill_config("experience")
    if cfg:
        review_days = cfg.get("reflection", {}).get("stale_prediction_days", 90)

    structured_data = {
        "metric": metric or "fair_value",
        "predicted": predicted,
        "actual": None,
        "review_after": (date.today() + timedelta(days=review_days)).isoformat(),
        "source": source,
    }

    item_id = retriever.save_knowledge_item(
        type="prediction",
        subject=(subject or "").upper(),
        content=content,
        structured_data=structured_data,
        source=source,
        tags=tags,
    )

    return ToolResult.ok({
        "id": item_id,
        "subject": subject,
        "review_after": structured_data["review_after"],
    })


def _export_note_markdown(subject: str, content: str, note_category: str = None):
    """Export note as markdown file for human readability."""
    try:
        base = Path(config_get("memory.base_dir", "./memory"))
        category = note_category or "company"
        dir_map = {"company": "companies", "sector": "sectors", "patterns": "patterns"}
        dir_name = dir_map.get(category, "companies")
        path = base / dir_name / f"{subject}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception:
        pass  # best-effort


# ── recall implementation ────────────────────────────────────

def recall(
    retriever: EvidenceRetriever,
    context: str,
    subject: str = "",
    types: list = None,
) -> ToolResult:
    """Search AI memory for relevant knowledge, grouped by type."""

    # Default: all AI memory types (no documents)
    ai_types = {"observation", "experience", "note", "prediction", "hypothesis"}
    type_filter = set(types) & ai_types if types else ai_types

    results = {
        "observations": [],
        "experiences": {"warnings": [], "golden": []},
        "notes": [],
        "hypotheses": [],
        "predictions": [],
    }
    seen_ids: set[str] = set()

    # 1. Direct query on knowledge_items by subject
    if subject:
        items = retriever.query_knowledge_items(subject=subject, limit=30)
        for item in items:
            if type_filter and item["type"] not in type_filter:
                continue
            _add_to_results(results, item)
            seen_ids.add(item["id"])

    # 2. Semantic search for broader matches
    search_query = f"{subject}: {context}" if subject else context
    try:
        search_hits = retriever.semantic_search(search_query, top_k=10)
    except Exception:
        search_hits = []

    for hit in search_hits:
        if hit["id"] in seen_ids:
            continue

        # Try to resolve from knowledge_items
        item = retriever.get_knowledge_item(hit["id"])
        if item:
            if type_filter and item["type"] not in type_filter:
                continue
            _add_to_results(results, item)
            seen_ids.add(hit["id"])
            continue

        # Legacy: observation/hypothesis in embeddings table
        st = hit.get("source_type", "")
        cat = hit.get("source_category", "")
        if st == "observation" and (not type_filter or "observation" in type_filter):
            results["observations"].append({
                "id": hit["id"], "content": hit.get("content", ""),
                "source": "legacy", "score": hit.get("score", 0),
            })
            seen_ids.add(hit["id"])
        elif st == "hypothesis" and (not type_filter or "hypothesis" in type_filter):
            results["hypotheses"].append({
                "id": hit["id"], "content": hit.get("content", ""),
                "source": "legacy", "score": hit.get("score", 0),
            })
            seen_ids.add(hit["id"])
    # 3. Query hypotheses directly if requested
    if (not type_filter or "hypothesis" in type_filter) and subject:
        try:
            hyps = retriever.list_hypotheses(company=subject)
            for h in hyps:
                if h.id not in seen_ids:
                    results["hypotheses"].append({
                        "id": h.id, "company": h.company, "thesis": h.thesis,
                        "confidence": h.confidence,
                        "drivers": [d.name for d in h.drivers],
                    })
                    seen_ids.add(h.id)
        except Exception:
            pass

    # 4. Update retrieval counts for experiences
    for exp in results["experiences"]["warnings"] + results["experiences"]["golden"]:
        try:
            item = retriever.get_knowledge_item(exp["id"])
            if item:
                sd = item["structured_data"]
                sd["times_retrieved"] = sd.get("times_retrieved", 0) + 1
                retriever.update_knowledge_item_structured_data(exp["id"], sd)
        except Exception:
            pass

    # Build instruction
    has_warnings = len(results["experiences"]["warnings"]) > 0
    total = sum([
        len(results["observations"]),
        len(results["experiences"]["warnings"]),
        len(results["experiences"]["golden"]),
        len(results["notes"]),
        len(results["hypotheses"]),
        len(results["predictions"]),
    ])

    instruction = (
        "Warning Zone experiences returned — consider whether to adjust your assumptions."
        if has_warnings else "No warnings for this context."
    )

    return ToolResult.ok({
        **results,
        "total_results": total,
        "instruction": instruction,
    })


def search_knowledge(
    retriever: EvidenceRetriever,
    query: str,
    top_k: int = 5,
    company: str = None,
) -> ToolResult:
    """Search user-uploaded knowledge base (reports, articles, notes)."""
    try:
        hits = retriever.semantic_search(
            query=query,
            top_k=top_k,
            source_category="human_knowledge",
        )
    except Exception:
        hits = []

    # Filter by company if specified
    if company:
        company_upper = company.upper()
        hits = [h for h in hits if company_upper in (h.get("content", "") + h.get("document_title", "")).upper()]

    results = []
    for hit in hits:
        results.append({
            "id": hit.get("id", ""),
            "content": hit.get("content", ""),
            "document_title": hit.get("document_title", ""),
            "document_id": hit.get("document_id", ""),
            "score": hit.get("score", 0),
        })

    return ToolResult.ok({
        "query": query,
        "results": results,
        "count": len(results),
    })


def _add_to_results(results: dict, item: dict):
    """Add a knowledge_item to the appropriate results group."""
    item_type = item.get("type", "")
    sd = item.get("structured_data", {})

    entry = {
        "id": item["id"],
        "content": item.get("content", ""),
        "subject": item.get("subject", ""),
        "confidence": item.get("confidence"),
        "created_at": item.get("created_at"),
    }

    if item_type == "observation":
        entry["source"] = sd.get("source", item.get("source", ""))
        entry["relevance"] = sd.get("relevance", item.get("confidence"))
        results["observations"].append(entry)

    elif item_type == "experience":
        entry["level"] = sd.get("level")
        entry["methodology"] = sd.get("methodology")
        entry["evidence_count"] = sd.get("evidence_count", 0)
        zone = sd.get("zone", "")
        if zone == "warning":
            results["experiences"]["warnings"].append(entry)
        else:
            results["experiences"]["golden"].append(entry)

    elif item_type == "note":
        entry["category"] = sd.get("note_category")
        results["notes"].append(entry)

    elif item_type == "prediction":
        entry["metric"] = sd.get("metric")
        entry["predicted"] = sd.get("predicted")
        entry["actual"] = sd.get("actual")
        entry["review_after"] = sd.get("review_after")
        results["predictions"].append(entry)

    elif item_type == "document":
        entry["doc_type"] = sd.get("doc_type")
        entry["title"] = sd.get("title", item.get("source", ""))
        results["documents"].append(entry)


# ── Source reference tracking (Section 5) ─────────────────────

def _track_source_useful(retriever, source: str):
    """If source references an existing knowledge_item ID, increment its times_useful."""
    if not source or not hasattr(retriever, "get_knowledge_item"):
        return
    try:
        item = retriever.get_knowledge_item(source)
        if item:
            sd = item.get("structured_data", {})
            sd["times_useful"] = sd.get("times_useful", 0) + 1
            retriever.update_knowledge_item_structured_data(source, sd)
    except Exception:
        pass


# ── Auto-recall for context injection ─────────────────────────

def auto_recall_for_context(retriever, subject: str) -> dict | None:
    """Internal function used by ContextAssembler to auto-inject memories.
    Returns a dict of grouped results, or None if nothing found."""
    if not subject or not hasattr(retriever, "query_knowledge_items"):
        return None

    items = retriever.query_knowledge_items(subject=subject, limit=20)
    if not items:
        return None

    results = {
        "observations": [],
        "experiences": {"warnings": [], "golden": []},
        "notes": [],
        "predictions": [],
    }

    for item in items:
        _add_to_results(results, item)

    # Check for pending predictions
    pending = []
    for pred in results["predictions"]:
        review_after = pred.get("review_after")
        if review_after and pred.get("actual") is None:
            try:
                review_date = date.fromisoformat(review_after)
                if review_date <= date.today():
                    pending.append(pred)
            except (ValueError, TypeError):
                pass

    has_content = any([
        results["observations"],
        results["experiences"]["warnings"],
        results["experiences"]["golden"],
        results["notes"],
        results["predictions"],
    ])

    if not has_content:
        return None

    return {**results, "pending_predictions": pending}
