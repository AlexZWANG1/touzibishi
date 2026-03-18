from __future__ import annotations

import json
import re
from typing import Optional

from core.config import get


class ContextAssembler:
    def __init__(self, llm_client, retriever=None):
        self.llm = llm_client
        self.retriever = retriever

    def extract_subject(self, user_input: str) -> Optional[str]:
        if not user_input:
            return None

        # Prefer explicit ticker-like tokens.
        tokens = re.findall(r"\b[A-Z]{1,6}\b", user_input)
        if tokens:
            return tokens[0].upper()

        # Fallback: first non-empty alpha token.
        words = re.findall(r"[A-Za-z][A-Za-z0-9._-]{1,20}", user_input)
        if words:
            return words[0].upper()
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
            sections.append(f"Previously researched subjects include {examples}. Use query_knowledge if needed.")

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

        knowledge_tools = [
            t for t in getattr(self, "_knowledge_tools", [])
            if t.name in {"extract_observation", "create_hypothesis", "add_evidence_card", "query_knowledge"}
        ]
        self.memory_flush(messages, knowledge_tools, budget)

        old_messages = messages[2:-(keep_recent)]
        if not old_messages:
            return messages

        summary = self._fallback_truncate_summary(old_messages)
        if strategy == "llm_summary" and budget.reserve_round("compaction"):
            max_chars = get("compaction.summary_max_input_chars", 50000)
            summary_prompt = get(
                "compaction.summary_prompt",
                "Summarize this conversation concisely. Preserve key data, decisions, and IDs.",
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

        flush_prompt = get(
            "compaction.memory_flush.prompt",
            "Context is about to be compacted. Save any key findings using available tools.",
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
