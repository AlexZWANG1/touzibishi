from __future__ import annotations

import json
import re
from typing import Optional

from core.config import get, get_prompt, get_langfuse_prompt


class ContextAssembler:
    def __init__(self, llm_client, retriever=None):
        self.llm = llm_client
        self.retriever = retriever

    def extract_subject(self, user_input: str) -> Optional[str]:
        """Extract the primary analysis subject (ticker) from user input.

        Uses DB-known tickers first (fast, free), then falls back to a
        lightweight LLM call for ambiguous queries like '分析 AI Agent 产业链'.
        """
        if not user_input:
            return None

        # Step 1: Collect uppercase token candidates from the query.
        candidates = re.findall(r"\b[A-Z]{1,6}\b", user_input)

        # Step 2: If we have a DB, check candidates against known tracked tickers.
        if candidates and self.retriever:
            try:
                known = set(self.retriever.get_tracked_tickers())
                for c in candidates:
                    if c in known:
                        return c
            except Exception:
                pass

        # Step 3: Use LLM to determine the actual subject — avoids false
        # positives like 'AI', 'GDP', 'EV' that look like tickers but aren't.
        try:
            import os
            from core.tracing import is_enabled as _lf_ok
            try:
                if _lf_ok():
                    from langfuse.openai import OpenAI
                else:
                    from openai import OpenAI
            except Exception:
                from openai import OpenAI

            model = os.getenv("METADATA_MODEL") or os.getenv("INGEST_METADATA_MODEL") or "gpt-5.4-mini"
            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
            prompt = get_prompt(
                "iris-ticker-extraction",
                "prompts.ticker_extraction",
                "Extract the primary stock ticker symbol from the user's investment query. "
                "Return JSON: {\"ticker\": \"NVDA\"} or {\"ticker\": null}.",
            )
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input[:500]},
                ],
            )
            import json as _json
            raw = (response.choices[0].message.content or "").strip()
            parsed = _json.loads(raw)
            ticker = parsed.get("ticker")
            if ticker:
                return str(ticker).upper()
        except Exception:
            pass

        # Step 4: Final fallback — return first DB-known candidate, or None.
        return None

    def load_prior_context(self, subject: str, retriever) -> list[dict]:
        if not retriever or not get("cross_session.enabled", True):
            return []

        max_hyps = get("cross_session.max_hypotheses", 3)
        max_obs = get("cross_session.max_observations", 10)

        try:
            if hasattr(retriever, "by_subject"):
                by_subject = retriever.by_subject(
                    subject or "",
                    max_observations=max_obs,
                    max_hypotheses=max_hyps,
                )
            else:
                raise AttributeError("retriever.by_subject unavailable")
        except Exception:
            # Backward-compatible fallback for retrievers without by_subject.
            try:
                target = (subject or "").strip().upper()
                hyps_all = retriever.list_hypotheses() if hasattr(retriever, "list_hypotheses") else []
                obs_all = retriever.query_observations() if hasattr(retriever, "query_observations") else []
                hyps_filtered = [h for h in hyps_all if getattr(h, "company", "").upper() == target][-max_hyps:]
                obs_filtered = [o for o in obs_all if getattr(o, "subject", "").upper() == target][-max_obs:]
                other_subjects = sorted(
                    {
                        getattr(h, "company", "")
                        for h in hyps_all
                        if getattr(h, "company", "").upper() != target and getattr(h, "company", "")
                    }
                    | {
                        getattr(o, "subject", "")
                        for o in obs_all
                        if getattr(o, "subject", "").upper() != target and getattr(o, "subject", "")
                    }
                )[:8]
                by_subject = {
                    "subject": target,
                    "hypotheses": [
                        {
                            "id": h.id,
                            "company": h.company,
                            "thesis": h.thesis,
                            "confidence": h.confidence,
                            "drivers": [{"name": d.name} for d in h.drivers],
                        }
                        for h in hyps_filtered
                    ],
                    "observations": [
                        {
                            "id": o.id,
                            "subject": o.subject,
                            "claim": o.claim,
                            "source": o.source,
                            "relevance": o.relevance,
                        }
                        for o in obs_filtered
                    ],
                    "other_subjects": other_subjects,
                }
            except Exception:
                return []

        hypotheses = by_subject.get("hypotheses", [])
        observations = by_subject.get("observations", [])
        other_subjects = by_subject.get("other_subjects", [])

        sections: list[str] = []

        if hypotheses:
            lines = ["### Existing Hypotheses"]
            for h in hypotheses[-max_hyps:]:
                drivers = h.get("drivers", []) if isinstance(h, dict) else []
                driver_names = ", ".join(d.get("name", "") for d in drivers[:3] if d.get("name"))
                lines.append(
                    f"- **{h.get('company', '')}** [{h.get('id', '')}]: {h.get('thesis', '')} "
                    f"(confidence: {float(h.get('confidence', 0)):.0f}, drivers: {driver_names})"
                )
            sections.append("\n".join(lines))

        if observations:
            lines = ["### Recent Observations"]
            for o in observations[-max_obs:]:
                lines.append(
                    f"- [{o.get('id', '')}] {o.get('subject', '')}: {o.get('claim', '')} "
                    f"(source: {o.get('source', '')}, relevance: {o.get('relevance', 0)})"
                )
            sections.append("\n".join(lines))

        if other_subjects:
            examples = ", ".join(other_subjects[:5])
            sections.append(f"Previously researched subjects include {examples}. Use recall if needed.")

        # Unified memory: inject knowledge_items if available
        try:
            from tools.unified_memory import auto_recall_for_context
            unified = auto_recall_for_context(retriever, subject or "")
            if unified:
                if unified.get("experiences", {}).get("warnings"):
                    lines = ["### Experience Warnings"]
                    for w in unified["experiences"]["warnings"][:5]:
                        lines.append(f"- **[WARNING]** {w.get('content', '')} (confidence: {w.get('confidence', 'N/A')})")
                    sections.append("\n".join(lines))
                if unified.get("experiences", {}).get("golden"):
                    lines = ["### Golden Experiences"]
                    for g in unified["experiences"]["golden"][:5]:
                        lines.append(f"- {g.get('content', '')}")
                    sections.append("\n".join(lines))
                if unified.get("notes"):
                    lines = ["### Prior Analysis Notes"]
                    for n in unified["notes"][:3]:
                        snippet = n.get("content", "")[:200]
                        lines.append(f"- **{n.get('subject', '')}**: {snippet}")
                    sections.append("\n".join(lines))
                if unified.get("pending_predictions"):
                    lines = ["### Pending Prediction Reviews"]
                    for p in unified["pending_predictions"]:
                        lines.append(
                            f"- **{p.get('subject', '')}** {p.get('metric', 'fair_value')}: "
                            f"predicted ${p.get('predicted', 'N/A')} — review overdue"
                        )
                    sections.append("\n".join(lines))
        except Exception:
            pass  # unified memory injection is best-effort

        if not sections:
            return []

        payload = "## Prior Analysis Context\n\n" + "\n\n".join(sections)
        return [{"role": "user", "content": payload}]

    def build_system_message(self, soul: str, tools_exposed: list[str]) -> dict:
        tool_list = ", ".join(tools_exposed) if tools_exposed else "none"
        runtime_note = (
            "\n\n[Runtime]\n"
            f"Tools exposed this round: {tool_list}. "
            "If blocked or repetitive, switch strategy instead of repeating identical calls."
        )
        return {"role": "system", "content": soul + runtime_note}

    def should_compact(self, messages: list[dict], limit: int) -> bool:
        total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        return total_chars > int(limit * 0.85)

    def compact(self, messages: list[dict], llm_client, budget) -> list[dict]:
        keep_recent = get("compaction.keep_recent_messages", 6)
        strategy = get("compaction.strategy", "llm_summary")

        if len(messages) <= keep_recent + 2:
            return messages

        # Use declarative is_knowledge flag instead of hardcoded name whitelist.
        knowledge_tools = [
            t for t in getattr(self, "_knowledge_tools", [])
            if getattr(t, "is_knowledge", False)
        ]
        self.memory_flush(messages, knowledge_tools, budget)

        old_messages = messages[2:-(keep_recent)]
        if not old_messages:
            return messages

        summary = self._fallback_truncate_summary(old_messages)
        if strategy == "llm_summary" and budget.reserve_round("compaction"):
            max_chars = get("compaction.summary_max_input_chars", 50000)
            summary_prompt = (
                get_langfuse_prompt("iris-compaction-summary")
                or get("compaction.summary_prompt",
                       "Summarize this conversation concisely. Preserve key data, decisions, and IDs.")
            )
            content = json.dumps(old_messages, ensure_ascii=False)
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...[truncated for summary]"
            try:
                response = llm_client.chat(
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": content},
                    ],
                    tools=[],
                    temperature=0.2,
                )
                budget.register_llm_call("compaction", response.input_tokens, response.output_tokens)
                summary = response.content or summary
            except Exception:
                pass

        compacted = (
            messages[:2]
            + [{"role": "user", "content": f"[CONTEXT SUMMARY - earlier exchanges compacted]\n\n{summary}"}]
            + messages[-(keep_recent):]
        )
        messages.clear()
        messages.extend(compacted)
        return messages

    def memory_flush(self, messages: list[dict], knowledge_tools: list, budget) -> None:
        if not get("compaction.memory_flush.enabled", True):
            return
        if not knowledge_tools:
            return
        if not budget.reserve_round("flush"):
            return

        flush_prompt = (
            get_langfuse_prompt("iris-memory-flush")
            or get("compaction.memory_flush.prompt",
                   "Context is about to be compacted. Save any key findings using available tools.")
        )
        flush_messages = messages + [{"role": "user", "content": f"[MEMORY FLUSH] {flush_prompt}"}]
        tool_schemas = [t.schema for t in knowledge_tools]

        try:
            response = self.llm.chat(flush_messages, tools=tool_schemas, temperature=0.2)
            budget.register_llm_call("flush", response.input_tokens, response.output_tokens)

            if not response.tool_calls:
                return

            allowed = budget.trim_tool_calls(len(response.tool_calls))
            if allowed <= 0:
                return

            budget.register_tool_calls("flush", allowed)
            tool_map = {t.name: t for t in knowledge_tools}
            for tc in response.tool_calls[:allowed]:
                tool = tool_map.get(tc.name)
                if not tool:
                    continue
                try:
                    tool.execute(tc.arguments)
                except Exception:
                    pass
        except Exception:
            pass

    def build_user_message(self, user_input: str, context_docs: list[str] = None) -> str:
        parts = [user_input]
        if context_docs:
            docs_text = "\n\n---\n\n".join(context_docs)
            parts.append(f"\n\n## Provided Documents\n\n{docs_text}")
        return "".join(parts)

    def _fallback_truncate_summary(self, old_messages: list[dict]) -> str:
        parts = []
        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "tool":
                try:
                    data = json.loads(content)
                    if data.get("status") == "ok":
                        parts.append(f"[Tool OK] {json.dumps(data.get('data', {}), ensure_ascii=False)[:280]}")
                except Exception:
                    pass
            elif role == "assistant" and content:
                parts.append(f"[Assistant] {content[:300]}")
        return "\n".join(parts[-10:]) if parts else "[Earlier context compacted]"
