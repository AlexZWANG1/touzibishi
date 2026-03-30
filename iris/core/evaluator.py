"""
Evaluator — independent quality auditor for deep analysis mode.

Reads evidence + conclusion from RunDirectory (Generator cannot filter).
Receives query + tool_log as lightweight params.
Returns structured EvalResult with pass/fail + actionable feedback.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from core.budget import BudgetTracker
from core.run_directory import RunDirectory
from llm.base import LLMClient

log = logging.getLogger(__name__)

# ── Soul prompt for the evaluator ────────────────────────────

_SOUL_DIR = Path(__file__).resolve().parent.parent / "soul"


def _load_evaluator_prompt() -> str:
    """Load evaluator prompt: Langfuse → local file → hardcoded fallback."""
    from core.config import get_prompt
    return get_prompt(
        langfuse_name="iris-evaluator",
        yaml_key="",  # no yaml fallback for evaluator
        default=(_SOUL_DIR / "evaluator.md").read_text(encoding="utf-8")
                if (_SOUL_DIR / "evaluator.md").exists()
                else "You are a quality auditor for investment research. Cross-check conclusions against raw tool evidence. Return JSON: {passed, verdict, must_fix, suggestions, verified}.",
    )


# ── Data classes ─────────────────────────────────────────────

@dataclass
class EvalResult:
    passed: bool
    verdict: str                                  # one-sentence why pass/fail
    must_fix: list[str] = field(default_factory=list)   # blocking issues
    suggestions: list[str] = field(default_factory=list) # non-blocking improvements
    verified: list[str] = field(default_factory=list)    # facts confirmed correct

    @property
    def feedback_text(self) -> str:
        """Human-readable feedback for injecting into Generator messages."""
        parts = [self.verdict]
        if self.must_fix:
            parts.append("\nMust fix:")
            for i, item in enumerate(self.must_fix, 1):
                parts.append(f"  {i}. {item}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "must_fix": self.must_fix,
            "suggestions": self.suggestions,
            "verified": self.verified,
        }


# ── Evaluator ────────────────────────────────────────────────

@dataclass
class EvaluatorConfig:
    min_tools_for_eval: int = 2


class Evaluator:
    """Independent QA auditor for deep analysis results."""

    def __init__(
        self,
        llm: LLMClient,
        config: EvaluatorConfig,
        run_dir: RunDirectory,
    ):
        self.llm = llm
        self.config = config
        self.run_dir = run_dir
        self._system_prompt = _load_evaluator_prompt()

    def should_evaluate(self, tool_log: list[dict]) -> bool:
        """Gate: skip eval for trivial queries that barely used tools."""
        ok_tools = [t for t in tool_log if t.get("status") == "ok"]
        return len(ok_tools) >= self.config.min_tools_for_eval

    def evaluate(
        self,
        query: str,
        round_num: int,
        tool_log: list[dict],
        budget: BudgetTracker | None = None,
    ) -> EvalResult:
        """Run independent quality evaluation.

        Evidence + conclusion are read from disk (independent of Generator).
        Query + tool_log are passed as lightweight params.
        """
        # ── Independent data from disk ──
        conclusion = self.run_dir.read_conclusion(round_num)
        evidence = self.run_dir.read_latest_evidence()

        # ── Lightweight params ──
        tools_called = [t["tool"] for t in tool_log if t.get("status") == "ok"]
        tools_failed = [t["tool"] for t in tool_log if t.get("status") != "ok"]

        # ── Build evaluator's own messages ──
        evidence_text = self._format_evidence(evidence)
        user_content = (
            f"## User Query\n{query}\n\n"
            f"## Tools Called\nSuccess: {', '.join(tools_called) or 'none'}\n"
            f"{'Failed: ' + ', '.join(tools_failed) if tools_failed else ''}\n\n"
            f"## Generator Conclusion\n{conclusion[:8000]}\n\n"
            f"## Raw Evidence (tool outputs)\n{evidence_text[:20000]}"
        )

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
                tools=[],
                temperature=0.1,
            )

            # Track evaluator LLM cost in budget
            if budget:
                budget.register_llm_call(
                    "evaluator",
                    response.input_tokens,
                    response.output_tokens,
                )

            result = self._parse_response(response.content or "")

        except Exception as e:
            log.error("Evaluator LLM call failed: %s", e)
            # On failure, pass through (don't block the analysis)
            result = EvalResult(
                passed=True,
                verdict=f"Evaluator error, passing through: {e}",
            )

        # Persist eval report
        self.run_dir.write_eval_report(round_num, result.to_dict())
        return result

    def _format_evidence(self, evidence: dict[str, dict]) -> str:
        parts = []
        for tool_name, data in evidence.items():
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            if len(serialized) > 4000:
                serialized = serialized[:4000] + "...[truncated]"
            parts.append(f"### {tool_name}\n```json\n{serialized}\n```")
        return "\n\n".join(parts)

    def _parse_response(self, text: str) -> EvalResult:
        """Parse LLM response into EvalResult. Expects JSON."""
        try:
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0]
            data = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            log.warning("Evaluator returned non-JSON, treating as fail")
            return EvalResult(
                passed=False,
                verdict="Evaluator returned non-JSON response",
                must_fix=[text[:1500]],
            )

        passed = bool(data.get("passed", False))
        verdict = data.get("verdict", "")
        must_fix = data.get("must_fix", [])
        suggestions = data.get("suggestions", [])
        verified = data.get("verified", [])

        # Safety: if must_fix is non-empty, it's a fail regardless of what LLM said
        if must_fix and passed:
            log.warning("Evaluator said passed but has must_fix items — overriding to fail")
            passed = False

        return EvalResult(
            passed=passed,
            verdict=verdict,
            must_fix=[str(x) for x in must_fix] if isinstance(must_fix, list) else [str(must_fix)],
            suggestions=[str(x) for x in suggestions] if isinstance(suggestions, list) else [str(suggestions)],
            verified=[str(x) for x in verified] if isinstance(verified, list) else [str(verified)],
        )
