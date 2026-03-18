import json
from dataclasses import dataclass, field
from typing import Optional

from llm.base import LLMClient, LLMResponse, ToolCall
from guards.guards import InvestmentGuards
from core.invariants import InvariantChecker
from tools.retrieval import EvidenceRetriever
from tools.base import ToolResult


@dataclass
class HarnessConfig:
    max_tool_rounds: int = 20
    compress_threshold_chars: int = 2000


@dataclass
class HarnessResult:
    ok: bool
    reply: Optional[str] = None
    tool_log: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class Harness:
    """
    LLM interaction controller. Runs the tool-calling loop.
    Not a pipeline — LLM decides what tools to call and in what order.
    Guards block bad calls (Backpressure). Invariants check post-execution results.
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: list,
        guards: InvestmentGuards,
        invariants: InvariantChecker,
        retriever: EvidenceRetriever,
        soul: str,
        config: HarnessConfig = None,
    ):
        self.llm = llm
        self.tool_registry = {t.name: t for t in tools}
        self.guards = guards
        self.invariants = invariants
        self.retriever = retriever
        self.soul = soul
        self.config = config or HarnessConfig()

    def run(self, user_input: str, context_docs: list[str] = None) -> HarnessResult:
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_user_message(user_input, context_docs)},
        ]
        tool_schemas = self._tool_schemas()
        tool_log = []
        total_input = 0
        total_output = 0

        for _ in range(self.config.max_tool_rounds):
            response = self.llm.chat(messages, tools=tool_schemas)
            total_input += response.input_tokens
            total_output += response.output_tokens

            if not response.tool_calls:
                return HarnessResult(
                    ok=True,
                    reply=response.content,
                    tool_log=tool_log,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                )

            messages.append(response.as_message())

            for tc in response.tool_calls:
                tool_result_content = self._dispatch(tc, tool_log)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result_content),
                })

        return HarnessResult(
            ok=False,
            error=f"MAX_TOOL_ROUNDS ({self.config.max_tool_rounds}) reached — analysis incomplete.",
            tool_log=tool_log,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )

    def _dispatch(self, tc: ToolCall, tool_log: list) -> dict:
        # 1. Guard check (Backpressure)
        guard = self.guards.check(tc.name, tc.arguments)
        if guard.blocked:
            tool_log.append({"tool": tc.name, "status": "blocked", "reason": guard.error})
            return {"status": "error", "error": guard.error, "hint": guard.hint, "recoverable": True}

        # 2. Tool exists?
        tool = self.tool_registry.get(tc.name)
        if not tool:
            tool_log.append({"tool": tc.name, "status": "not_found"})
            return {
                "status": "error",
                "error": f"Tool '{tc.name}' not found",
                "hint": f"Available tools: {list(self.tool_registry.keys())}",
                "recoverable": False,
            }

        # 3. Execute
        try:
            raw_result: ToolResult = tool.execute(tc.arguments)
        except Exception as e:
            tool_log.append({"tool": tc.name, "status": "exception", "error": str(e)})
            return {"status": "error", "error": f"Tool raised exception: {str(e)}", "recoverable": False}

        # 4. Invariant check (post-execution)
        if raw_result.status == "ok":
            violations = self.invariants.check(tc.name, raw_result)
            if violations:
                tool_log.append({"tool": tc.name, "status": "invariant_violated", "violations": violations})
                return {"status": "error", "error": f"INVARIANT VIOLATED: {'; '.join(violations)}", "recoverable": False}

        # 5. Compress + return
        result_dict = raw_result.to_dict()
        compressed = self._compress(result_dict)
        tool_log.append({"tool": tc.name, "status": raw_result.status})
        return compressed

    def _compress(self, result: dict) -> dict:
        result_str = json.dumps(result)
        if len(result_str) <= self.config.compress_threshold_chars:
            return result
        compressed = {}
        for k, v in result.items():
            if isinstance(v, str) and len(v) > 500:
                compressed[k] = v[:500] + f"... [truncated, {len(v)} chars total]"
            elif isinstance(v, list) and len(v) > 10:
                compressed[k] = v[:10] + [f"... [{len(v) - 10} more items]"]
            else:
                compressed[k] = v
        return compressed

    def _build_system_prompt(self) -> str:
        return f"""{self.soul}

---

You are IRIS, an AI investment analysis system. When given a company or investment question:

1. Search for relevant information (earnings, news, analyst views, macro context)
2. Extract structured observations from what you find (extract_observation)
3. Create an investment hypothesis with key drivers and kill criteria (create_hypothesis)
4. Evaluate each observation as evidence (add_evidence_card)
5. Run a valuation analysis appropriate for the company type (run_valuation)
6. Compute the trade score (compute_trade_score)
7. Write the audit trail (write_audit_trail)

Before each tool call, briefly state what you're doing and why.
If a tool returns an error, read the error and hint carefully, then correct your approach.
When analysis is complete, give a clear summary: recommendation, confidence, key reasoning.

CRITICAL: Never invent data. Every claim must trace back to a specific source.
"""

    def _build_user_message(self, user_input: str, context_docs: list[str] = None) -> str:
        msg = user_input
        if context_docs:
            docs_text = "\n\n---\n\n".join(context_docs)
            msg += f"\n\n## Provided Documents\n\n{docs_text}"
        return msg

    def _tool_schemas(self) -> list[dict]:
        return [t.schema for t in self.tool_registry.values()]
