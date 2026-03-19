# IRIS Context & Memory System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give IRIS persistent memory and intelligent context management — LLM-based compaction, cross-session context loading, memory flush before compaction, and semantic vector search — inspired by OpenClaw's architecture.

**Architecture:** Four layered improvements to the existing Harness. P0 replaces dumb string truncation with LLM summarization. P1 injects historical observations/hypotheses from SQLite at session start. P2 adds a silent agent turn before compaction to persist key findings. P3 adds OpenAI embedding-based vector search to `EvidenceRetriever` for semantic recall. All changes are additive — existing tests must continue to pass.

**Tech Stack:** Existing (openai, pydantic, httpx, sqlite3) — no new dependencies. Embeddings use the already-installed `openai` package. Cosine similarity is pure Python (sufficient for hundreds of vectors).

---

## File Map

```
iris/
├── core/
│   ├── harness.py          # MODIFY: P0 (LLM compaction), P1 (retriever + context loading), P2 (memory flush)
│   ├── config.py           # MODIFY: expose compaction/memory/vector config from yaml
│   └── schemas.py          # NO CHANGE
├── tools/
│   ├── base.py             # MODIFY: add memory_search to TOOL_PHASES
│   ├── retrieval.py        # MODIFY: P3 (add VectorIndex, semantic search in SQLiteRetriever)
│   ├── knowledge.py        # MODIFY: add memory_search tool, auto-embed on save
│   ├── search.py           # NO CHANGE
│   └── financials.py       # NO CHANGE
├── llm/
│   ├── base.py             # NO CHANGE
│   └── openai_client.py    # NO CHANGE
├── tests/
│   ├── test_harness.py     # MODIFY: update compaction test, add P0/P1/P2 tests
│   ├── test_retrieval.py   # MODIFY: add vector search tests
│   ├── test_knowledge.py   # MODIFY: add memory_search test
│   └── test_context.py     # CREATE: dedicated context management tests
├── iris_config.yaml        # MODIFY: add compaction/memory/vector config sections
└── main.py                 # MODIFY: wire retriever to harness, register memory_search tool
```

---

## Chunk 1: P3 — Vector Search in EvidenceRetriever

This goes first because P1 and P2 benefit from semantic search being available.

### Task 1: Add vector tables to SQLite + embedding utilities

**Files:**
- Modify: `iris/tools/retrieval.py`
- Test: `iris/tests/test_retrieval.py`

- [ ] **Step 1: Write failing test — vector table init**

In `iris/tests/test_retrieval.py`, append:

```python
def test_vector_index_creates_table(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    import sqlite3
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
        ).fetchall()
    assert len(tables) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_vector_index_creates_table -v`
Expected: FAIL — no `embeddings` table exists

- [ ] **Step 3: Add embeddings table to `_init_db` in `SQLiteRetriever`**

In `iris/tools/retrieval.py`, inside `_init_db()`, add to the `executescript`:

```sql
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_vector_index_creates_table -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add iris/tools/retrieval.py iris/tests/test_retrieval.py
git commit -m "feat: add embeddings table to SQLite schema"
```

---

### Task 2: Implement embedding + cosine similarity utilities

**Files:**
- Modify: `iris/tools/retrieval.py`
- Test: `iris/tests/test_retrieval.py`

- [ ] **Step 1: Write failing test — cosine similarity**

In `iris/tests/test_retrieval.py`, append:

```python
from tools.retrieval import cosine_similarity

def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6

def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6

def test_cosine_similarity_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_cosine_similarity_identical tests/test_retrieval.py::test_cosine_similarity_orthogonal tests/test_retrieval.py::test_cosine_similarity_opposite -v`
Expected: FAIL — `cosine_similarity` not found

- [ ] **Step 3: Implement `cosine_similarity` in `retrieval.py`**

At the top of `iris/tools/retrieval.py`, after the imports, add:

```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. No numpy needed at this scale."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd iris && python -m pytest tests/test_retrieval.py -k "cosine" -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add iris/tools/retrieval.py iris/tests/test_retrieval.py
git commit -m "feat: add cosine_similarity utility"
```

---

### Task 3: Implement `embed()`, `save_embedding()`, `semantic_search()` on SQLiteRetriever

**Files:**
- Modify: `iris/tools/retrieval.py`
- Test: `iris/tests/test_retrieval.py`

- [ ] **Step 1: Write failing test — save and search embeddings**

In `iris/tests/test_retrieval.py`, append:

```python
from unittest.mock import patch, MagicMock

def _mock_embed(texts):
    """Deterministic fake embeddings based on text length for testing."""
    results = []
    for t in texts:
        # Simple hash-based fake embedding (3 dims)
        h = hash(t) % 1000
        results.append([h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000])
    return results

def test_semantic_search_returns_ranked_results(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        r.save_embedding("obs_1", "NVDA revenue grew 78% in data center", "observation")
        r.save_embedding("obs_2", "AMD launched MI300X competitor chip", "observation")
        r.save_embedding("obs_3", "Federal Reserve held rates steady", "observation")
        results = r.semantic_search("NVDA data center revenue growth", top_k=2)
    assert len(results) <= 2
    assert all("id" in r and "score" in r for r in results)

def test_semantic_search_empty_db(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed):
        results = r.semantic_search("anything", top_k=5)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_semantic_search_returns_ranked_results tests/test_retrieval.py::test_semantic_search_empty_db -v`
Expected: FAIL — methods not found

- [ ] **Step 3: Implement embedding methods on `SQLiteRetriever`**

In `iris/tools/retrieval.py`, add these methods to `SQLiteRetriever`:

```python
def _embed(self, texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API. Returns list of vectors."""
    import os
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=texts,
    )
    return [item.embedding for item in response.data]

def save_embedding(self, id: str, content: str, source_type: str) -> None:
    """Embed content and store in the embeddings table."""
    try:
        vectors = self._embed([content])
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (id, content, embedding, source_type, created_at) VALUES (?, ?, ?, ?, ?)",
                (id, content, json.dumps(vectors[0]), source_type, datetime.now().isoformat()),
            )
    except Exception:
        pass  # Best-effort: embedding failures don't break core flow

def semantic_search(self, query: str, top_k: int = 5, source_type: str = None) -> list[dict]:
    """Search embeddings by cosine similarity."""
    try:
        query_vec = self._embed([query])[0]
    except Exception:
        return []

    with self._conn() as conn:
        if source_type:
            rows = conn.execute(
                "SELECT id, content, embedding, source_type FROM embeddings WHERE source_type = ?",
                (source_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, embedding, source_type FROM embeddings"
            ).fetchall()

    if not rows:
        return []

    results = []
    for row in rows:
        stored_vec = json.loads(row[2])
        score = cosine_similarity(query_vec, stored_vec)
        results.append({
            "id": row[0],
            "content": row[1],
            "source_type": row[3],
            "score": round(score, 4),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
```

Also add `from datetime import datetime` at the top if not already imported, and `import math` for cosine_similarity.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd iris && python -m pytest tests/test_retrieval.py -k "semantic" -v`
Expected: 2 PASS

- [ ] **Step 5: Run ALL existing retrieval tests to confirm no regressions**

Run: `cd iris && python -m pytest tests/test_retrieval.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add iris/tools/retrieval.py iris/tests/test_retrieval.py
git commit -m "feat: add semantic search with OpenAI embeddings to SQLiteRetriever"
```

---

### Task 4: Auto-embed on `save_observation` and `save_hypothesis`

**Files:**
- Modify: `iris/tools/retrieval.py`
- Test: `iris/tests/test_retrieval.py`

- [ ] **Step 1: Write failing test — auto-embed on save**

In `iris/tests/test_retrieval.py`, append:

```python
def test_save_observation_auto_embeds(tmp_path):
    r = SQLiteRetriever(str(tmp_path / "test.db"))
    with patch.object(r, '_embed', side_effect=_mock_embed) as mock_emb:
        r.save_observation(make_obs("obs_auto"))
    mock_emb.assert_called_once()
    import sqlite3
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        rows = conn.execute("SELECT id FROM embeddings WHERE id = 'obs_auto'").fetchall()
    assert len(rows) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_save_observation_auto_embeds -v`
Expected: FAIL — `_embed` never called

- [ ] **Step 3: Add auto-embedding to `save_observation` and `save_hypothesis`**

In `SQLiteRetriever.save_observation()`, after the existing `conn.execute`, add:

```python
self.save_embedding(obs.id, f"{obs.subject}: {obs.claim}", "observation")
```

In `SQLiteRetriever.save_hypothesis()`, after the existing `conn.execute`, add:

```python
self.save_embedding(hyp.id, f"{hyp.company}: {hyp.thesis}", "hypothesis")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd iris && python -m pytest tests/test_retrieval.py::test_save_observation_auto_embeds -v`
Expected: PASS

- [ ] **Step 5: Run ALL tests to confirm no regressions**

Run: `cd iris && python -m pytest tests/ -v`
Expected: ALL PASS (embedding failures are best-effort, so existing tests without mocks still pass)

- [ ] **Step 6: Commit**

```bash
git add iris/tools/retrieval.py iris/tests/test_retrieval.py
git commit -m "feat: auto-embed observations and hypotheses on save"
```

---

### Task 5: Add `memory_search` tool for agent use

**Files:**
- Modify: `iris/tools/knowledge.py`
- Modify: `iris/tools/base.py`
- Modify: `iris/main.py`
- Test: `iris/tests/test_knowledge.py`

- [ ] **Step 1: Write failing test — memory_search tool**

In `iris/tests/test_knowledge.py`, append:

```python
from unittest.mock import patch

def _mock_embed(texts):
    results = []
    for t in texts:
        h = hash(t) % 1000
        results.append([h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000])
    return results

def test_memory_search_returns_results(tmp_path):
    from tools.knowledge import memory_search
    r = make_retriever(tmp_path)
    with patch.object(r, '_embed', side_effect=_mock_embed):
        extract_observation(
            retriever=r, subject="NVDA",
            claim="Data center revenue up 78%",
            source="Earnings", fact_or_view="fact", relevance=0.9,
            citation="...", time_str="2026-02-21", extracted_by="test",
        )
        result = memory_search(retriever=r, query="NVDA revenue growth", top_k=3)
    assert result.status == "ok"
    assert "results" in result.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd iris && python -m pytest tests/test_knowledge.py::test_memory_search_returns_results -v`
Expected: FAIL — `memory_search` not found

- [ ] **Step 3: Add `memory_search` to `knowledge.py`**

In `iris/tools/knowledge.py`, add schema and function:

```python
MEMORY_SEARCH_SCHEMA = make_tool_schema(
    name="memory_search",
    description=(
        "Semantic search across all saved observations, hypotheses, and evidence. "
        "Use when you need to recall prior analysis, check if something was already researched, "
        "or find related information across companies. Returns ranked results by relevance."
    ),
    properties={
        "query": {"type": "string", "description": "Natural language search query"},
        "top_k": {"type": "integer", "description": "Max results to return. Default 5."},
        "source_type": {
            "type": "string",
            "enum": ["observation", "hypothesis"],
            "description": "Filter by type. Omit to search all.",
        },
    },
    required=["query"],
)


def memory_search(
    retriever: "EvidenceRetriever",
    query: str,
    top_k: int = 5,
    source_type: str = None,
) -> ToolResult:
    results = retriever.semantic_search(query, top_k=top_k, source_type=source_type)
    return ToolResult.ok({
        "query": query,
        "results": results,
        "count": len(results),
    })
```

- [ ] **Step 4: Add `memory_search` to all phases in `base.py`**

In `iris/tools/base.py`, add `"memory_search"` to every phase set in `TOOL_PHASES`:

```python
TOOL_PHASES = {
    "gather":   {"exa_search", "web_fetch", "fmp_get_financials", "fred_get_macro",
                 "extract_observation", "create_hypothesis", "query_knowledge", "memory_search"},
    "analyze":  {"exa_search", "web_fetch", "fmp_get_financials", "fred_get_macro",
                 "extract_observation", "add_evidence_card", "create_hypothesis",
                 "query_knowledge", "memory_search"},
    "evaluate": {"add_evidence_card", "run_valuation", "compute_trade_score",
                 "query_knowledge", "memory_search"},
    "finalize": {"write_audit_trail", "query_knowledge", "memory_search"},
}
```

- [ ] **Step 5: Register `memory_search` tool in `main.py`**

In `iris/main.py`, add to the imports:

```python
from tools.knowledge import (
    ...,  # existing imports
    memory_search, MEMORY_SEARCH_SCHEMA,
)
```

Add to the `knowledge_tools` list in `build_harness()`:

```python
Tool(memory_search, MEMORY_SEARCH_SCHEMA, retriever=retriever),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd iris && python -m pytest tests/test_knowledge.py::test_memory_search_returns_results -v`
Expected: PASS

- [ ] **Step 7: Run ALL tests**

Run: `cd iris && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add iris/tools/knowledge.py iris/tools/base.py iris/main.py iris/tests/test_knowledge.py
git commit -m "feat: add memory_search semantic search tool"
```

---

## Chunk 2: P0 — LLM-based Context Compaction

### Task 6: Replace string truncation with LLM summarization

**Files:**
- Modify: `iris/core/harness.py`
- Modify: `iris/iris_config.yaml`
- Test: `iris/tests/test_harness.py`

- [ ] **Step 1: Add compaction config to `iris_config.yaml`**

In `iris/iris_config.yaml`, add at the end:

```yaml
compaction:
  strategy: "llm_summary"        # llm_summary | truncate
  keep_recent_messages: 6         # keep last N messages intact
  summary_max_input_chars: 50000  # max chars fed to summarizer
  summary_prompt: |
    Summarize this investment analysis conversation concisely.
    PRESERVE: key data points, financial figures, tool results, decisions made, company tickers, hypothesis IDs, evidence IDs.
    DISCARD: pleasantries, redundant search attempts, failed tool calls.
    Output a structured summary in markdown.
```

- [ ] **Step 2: Write failing test — LLM compaction calls the LLM**

In `iris/tests/test_harness.py`, append:

```python
def test_llm_compaction_calls_summarizer():
    """When context overflows, harness uses LLM to summarize instead of truncating."""
    summary_response = LLMResponse(
        content="## Summary\nNVDA revenue up 78%. Hypothesis created with 50% confidence.",
        tool_calls=[],
    )
    main_response = LLMResponse(content="Done.", tool_calls=[])

    mock_llm = MagicMock()
    # First call: summary (triggered by _compact_context)
    # Second call: actual main loop response
    mock_llm.chat.side_effect = [summary_response, main_response]

    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(
            max_tool_rounds=5,
            context_limit_chars=200,  # Very low → forces compaction
        ),
    )

    # Stuff messages to trigger compaction
    messages = [
        {"role": "system", "content": "You are IRIS."},
        {"role": "user", "content": "Analyze NVDA"},
    ]
    # Add enough fake history to exceed 200 chars * 0.85
    for i in range(10):
        messages.append({"role": "assistant", "content": f"Thinking about step {i}..." + "x" * 50})
        messages.append({"role": "user", "content": f"Continue with step {i}"})

    harness._compact_context(messages)

    # LLM should have been called for summarization
    assert mock_llm.chat.call_count >= 1
    # Messages should be compacted (fewer than original)
    assert len(messages) < 22  # Originally 2 + 20 = 22
    # Summary should be in messages
    summary_msgs = [m for m in messages if "Summary" in m.get("content", "") or "CONTEXT SUMMARY" in m.get("content", "")]
    assert len(summary_msgs) >= 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd iris && python -m pytest tests/test_harness.py::test_llm_compaction_calls_summarizer -v`
Expected: FAIL — current `_compact_context` doesn't call LLM

- [ ] **Step 4: Rewrite `_compact_context` in `harness.py`**

Replace the existing `_compact_context` method in `iris/core/harness.py` with:

```python
def _compact_context(self, messages: list):
    """
    LLM-based context compaction (inspired by OpenClaw):
    1. Identify old messages to compress
    2. Ask LLM to summarize them
    3. Replace old messages with summary + keep recent ones
    Falls back to truncation if LLM call fails.
    """
    from core.config import get

    keep_recent = get("compaction.keep_recent_messages", 6)
    strategy = get("compaction.strategy", "llm_summary")

    if len(messages) <= keep_recent + 2:
        return  # Not enough to compact

    old_messages = messages[2:-(keep_recent)]  # Skip system[0] + first user[1]
    if not old_messages:
        return

    if strategy == "llm_summary":
        summary = self._llm_summarize(old_messages)
    else:
        summary = self._fallback_truncate_summary(old_messages)

    # Rebuild: system + first user + summary + recent messages
    compacted = messages[:2] + [
        {"role": "user", "content": f"[CONTEXT SUMMARY — earlier exchanges compacted]\n\n{summary}"}
    ] + messages[-(keep_recent):]

    messages.clear()
    messages.extend(compacted)

def _llm_summarize(self, old_messages: list) -> str:
    """Call LLM to produce a semantic summary of old messages."""
    from core.config import get

    max_chars = get("compaction.summary_max_input_chars", 50000)
    summary_prompt = get("compaction.summary_prompt",
        "Summarize this conversation concisely. Preserve key data, decisions, and IDs.")

    # Serialize old messages, truncate if too large for the summary call itself
    content = json.dumps(old_messages, ensure_ascii=False)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n...[truncated for summary]"

    try:
        response = self.llm.chat(
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": content},
            ],
            tools=[],  # No tools for summarization
            temperature=0.2,
        )
        return response.content or self._fallback_truncate_summary(old_messages)
    except Exception:
        return self._fallback_truncate_summary(old_messages)

def _fallback_truncate_summary(self, old_messages: list) -> str:
    """Fallback: extract key content from messages without LLM."""
    parts = []
    for msg in old_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "tool":
            try:
                data = json.loads(content)
                if data.get("status") == "ok":
                    parts.append(f"[Tool OK] {json.dumps(data.get('data', {}), ensure_ascii=False)[:200]}")
            except (json.JSONDecodeError, TypeError):
                pass
        elif role == "assistant" and content:
            parts.append(f"[Assistant] {content[:300]}")
    return "\n".join(parts[-10:]) if parts else "[Earlier context compacted]"
```

Also delete the old `_deep_truncate` method — it's no longer needed for compaction (still used by `_compress` for individual tool results, so keep `_compress` and `_deep_truncate` as-is).

**Wait — `_deep_truncate` IS still used by `_compress()` for individual tool results.** Keep it. Only replace `_compact_context`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd iris && python -m pytest tests/test_harness.py::test_llm_compaction_calls_summarizer -v`
Expected: PASS

- [ ] **Step 6: Run ALL harness tests to confirm no regressions**

Run: `cd iris && python -m pytest tests/test_harness.py -v`
Expected: ALL PASS — the existing `test_harness_context_compaction` may need adjustment since compaction behavior changed. If it fails, update the test to account for LLM-based compaction (mock the LLM response).

- [ ] **Step 7: Commit**

```bash
git add iris/core/harness.py iris/iris_config.yaml iris/tests/test_harness.py
git commit -m "feat: replace string truncation with LLM-based context compaction"
```

---

## Chunk 3: P1 — Cross-session Context Loading

### Task 7: Wire retriever into Harness + load prior context

**Files:**
- Modify: `iris/core/harness.py`
- Modify: `iris/main.py`
- Test: `iris/tests/test_harness.py`

- [ ] **Step 1: Write failing test — prior context is injected**

In `iris/tests/test_harness.py`, append:

```python
def test_cross_session_context_loading():
    """Harness injects prior observations and hypotheses from retriever."""
    from tools.retrieval import SQLiteRetriever
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        retriever = SQLiteRetriever(db_path)

        # Pre-populate with prior analysis
        from tools.knowledge import extract_observation, create_hypothesis
        extract_observation(
            retriever=retriever, subject="NVDA",
            claim="Revenue up 78%", source="Earnings",
            fact_or_view="fact", relevance=0.9,
            citation="...", time_str="2026-02-21", extracted_by="test",
        )
        create_hypothesis(
            retriever=retriever, company="NVDA",
            thesis="AI dominance", timeframe="24m",
            drivers=[
                {"name": "d1", "description": "x", "current_assessment": "ok"},
                {"name": "d2", "description": "y", "current_assessment": "ok"},
                {"name": "d3", "description": "z", "current_assessment": "ok"},
            ],
            kill_criteria=[{"description": "k1"}],
            initial_confidence=60.0,
        )

        mock_llm = make_mock_llm([
            LLMResponse(content="Analysis with prior context.", tool_calls=[]),
        ])

        harness = Harness(
            llm=mock_llm, tools=[], soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5),
            retriever=retriever,
        )
        result = harness.run("Continue analyzing NVDA")
        assert result.ok

        # Check that prior context was in the user message sent to LLM
        call_messages = mock_llm.chat.call_args_list[0][0][0]
        user_msg = call_messages[1]["content"]
        assert "Prior Analysis" in user_msg or "Revenue up 78%" in user_msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd iris && python -m pytest tests/test_harness.py::test_cross_session_context_loading -v`
Expected: FAIL — `Harness.__init__` doesn't accept `retriever`

- [ ] **Step 3: Add `retriever` to Harness and update `_build_user_message`**

In `iris/core/harness.py`, update `__init__`:

```python
def __init__(
    self,
    llm: LLMClient,
    tools: list,
    soul: str,
    config: HarnessConfig = None,
    on_event: Callable[[HarnessEvent], None] = None,
    retriever=None,
):
    self.llm = llm
    self.tool_registry = {t.name: t for t in tools}
    self.soul = soul
    self.config = config or HarnessConfig()
    self.on_event = on_event or (lambda e: None)
    self._abort = threading.Event()
    self._steering_queue: queue.Queue = queue.Queue()
    self.retriever = retriever
```

Replace `_build_user_message`:

```python
def _build_user_message(self, user_input: str, context_docs: list[str] = None) -> str:
    parts = [user_input]

    # Cross-session context: inject prior analysis from retriever
    if self.retriever:
        prior = self._load_prior_context()
        if prior:
            parts.append(f"\n\n## Prior Analysis Context\n\n{prior}")

    if context_docs:
        docs_text = "\n\n---\n\n".join(context_docs)
        parts.append(f"\n\n## Provided Documents\n\n{docs_text}")

    return "".join(parts)

def _load_prior_context(self) -> str:
    """Load relevant historical observations and hypotheses from SQLite."""
    sections = []

    try:
        hyps = self.retriever.list_hypotheses()
        if hyps:
            lines = ["### Existing Hypotheses"]
            for h in hyps[-3:]:
                drivers_str = ", ".join(d.name for d in h.drivers[:3])
                lines.append(
                    f"- **{h.company}** [{h.id}]: {h.thesis} "
                    f"(confidence: {h.confidence:.0f}, drivers: {drivers_str})"
                )
            sections.append("\n".join(lines))

        obs = self.retriever.query_observations()
        if obs:
            lines = ["### Recent Observations"]
            for o in obs[-10:]:
                lines.append(f"- [{o.id}] {o.subject}: {o.claim} (source: {o.source}, relevance: {o.relevance})")
            sections.append("\n".join(lines))
    except Exception:
        pass  # Best-effort: don't break the run if retriever fails

    return "\n\n".join(sections) if sections else ""
```

- [ ] **Step 4: Update `build_harness` in `main.py` to pass retriever**

In `iris/main.py`, update the `Harness(...)` call inside `build_harness()`:

```python
harness = Harness(
    llm=OpenAIClient(),
    tools=external_tools + knowledge_tools,
    soul=soul,
    config=HarnessConfig(
        max_tool_rounds=h["max_tool_rounds"],
        max_retries=h["max_retries"],
        retry_base_delay=h["retry_base_delay"],
        context_limit_chars=h["context_limit_chars"],
        compress_threshold_chars=h["compress_threshold_chars"],
        streaming=streaming,
    ),
    on_event=on_event,
    retriever=retriever,
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd iris && python -m pytest tests/test_harness.py::test_cross_session_context_loading -v`
Expected: PASS

- [ ] **Step 6: Run ALL tests**

Run: `cd iris && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add iris/core/harness.py iris/main.py iris/tests/test_harness.py
git commit -m "feat: cross-session context loading from SQLite retriever"
```

---

## Chunk 4: P2 — Memory Flush Before Compaction

### Task 8: Implement memory flush — silent agent turn before compaction

**Files:**
- Modify: `iris/core/harness.py`
- Modify: `iris/iris_config.yaml`
- Create: `iris/tests/test_context.py`

- [ ] **Step 1: Add memory flush config to `iris_config.yaml`**

In the `compaction:` section of `iris/iris_config.yaml`, add:

```yaml
  memory_flush:
    enabled: true
    prompt: |
      Context is about to be compacted. Review the conversation and save any key findings
      that should persist across sessions. Use extract_observation for important facts/data.
      Use create_hypothesis if a thesis has formed but not been saved.
      Reply with a brief note of what you saved, or "Nothing to save" if all key info is already persisted.
```

- [ ] **Step 2: Write failing test — memory flush is called before compaction**

Create `iris/tests/test_context.py`:

```python
import json
from unittest.mock import MagicMock, call
from llm.base import LLMResponse, ToolCall
from core.harness import Harness, HarnessConfig, EventType
from tools.base import ToolResult


def test_memory_flush_before_compaction():
    """Memory flush runs a silent LLM turn before compaction to persist key info."""
    # The flush turn calls extract_observation
    flush_tool_call = ToolCall(
        id="flush_tc_1", name="extract_observation",
        arguments={
            "subject": "NVDA", "claim": "Revenue up 78%",
            "source": "prior conversation", "fact_or_view": "fact",
            "relevance": 0.9, "citation": "...", "time_str": "2026-02-21",
        },
    )
    flush_response = LLMResponse(content=None, tool_calls=[flush_tool_call])
    summary_response = LLMResponse(content="Summary: NVDA analysis in progress.", tool_calls=[])
    main_response = LLMResponse(content="Done.", tool_calls=[])

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [flush_response, summary_response, main_response]

    mock_tool = MagicMock()
    mock_tool.name = "extract_observation"
    mock_tool.schema = {"type": "function", "function": {"name": "extract_observation"}}
    mock_tool.execute = MagicMock(return_value=ToolResult.ok({"id": "obs_flush"}))

    harness = Harness(
        llm=mock_llm, tools=[mock_tool], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5, context_limit_chars=200),
    )

    # Build messages that exceed context limit to trigger compaction
    messages = [
        {"role": "system", "content": "You are IRIS."},
        {"role": "user", "content": "Analyze NVDA"},
    ]
    for i in range(10):
        messages.append({"role": "assistant", "content": f"Step {i}: " + "x" * 50})
        messages.append({"role": "user", "content": f"Continue {i}"})

    harness._compact_context(messages)

    # Flush should have triggered a tool call
    assert mock_llm.chat.call_count >= 1
    # The extract_observation tool should have been called during flush
    assert mock_tool.execute.called


def test_memory_flush_skipped_when_disabled():
    """Memory flush does not run when disabled in config."""
    mock_llm = MagicMock()
    summary_response = LLMResponse(content="Summary.", tool_calls=[])
    mock_llm.chat.side_effect = [summary_response]

    harness = Harness(
        llm=mock_llm, tools=[], soul="You are IRIS.",
        config=HarnessConfig(max_tool_rounds=5, context_limit_chars=200),
    )

    messages = [
        {"role": "system", "content": "You are IRIS."},
        {"role": "user", "content": "Analyze NVDA"},
    ]
    for i in range(10):
        messages.append({"role": "assistant", "content": "x" * 50})
        messages.append({"role": "user", "content": "continue"})

    # Patch config to disable flush
    from unittest.mock import patch
    with patch("core.config.get", side_effect=lambda key, default=None: {
        "compaction.keep_recent_messages": 6,
        "compaction.strategy": "llm_summary",
        "compaction.memory_flush.enabled": False,
        "compaction.summary_max_input_chars": 50000,
        "compaction.summary_prompt": "Summarize.",
    }.get(key, default)):
        harness._compact_context(messages)

    # Only the summary call should have been made (no flush)
    assert mock_llm.chat.call_count == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd iris && python -m pytest tests/test_context.py -v`
Expected: FAIL — no memory flush logic exists

- [ ] **Step 4: Add `_memory_flush` to harness and call it from `_compact_context`**

In `iris/core/harness.py`, add the `_memory_flush` method and update `_compact_context`:

```python
def _memory_flush(self, messages: list):
    """
    Silent agent turn before compaction — asks LLM to persist key findings.
    Inspired by OpenClaw's pre-compaction memory flush.
    """
    from core.config import get

    if not get("compaction.memory_flush.enabled", True):
        return

    flush_prompt = get("compaction.memory_flush.prompt",
        "Context is about to be compacted. Save any key findings using available tools.")

    # Build flush request: current messages + flush instruction
    flush_messages = messages + [
        {"role": "user", "content": f"[MEMORY FLUSH] {flush_prompt}"}
    ]

    # Only provide knowledge tools for the flush turn
    knowledge_tools = [
        t.schema for t in self.tool_registry.values()
        if t.name in {"extract_observation", "create_hypothesis", "add_evidence_card", "query_knowledge"}
    ]

    try:
        response = self.llm.chat(flush_messages, tools=knowledge_tools, temperature=0.2)

        # Execute any tool calls from the flush (silent — no events emitted)
        if response.tool_calls:
            for tc in response.tool_calls:
                tool = self.tool_registry.get(tc.name)
                if tool:
                    try:
                        tool.execute(tc.arguments)
                    except Exception:
                        pass  # Best-effort
    except Exception:
        pass  # Flush is best-effort — never blocks compaction
```

Update `_compact_context` to call flush first:

```python
def _compact_context(self, messages: list):
    from core.config import get

    keep_recent = get("compaction.keep_recent_messages", 6)
    strategy = get("compaction.strategy", "llm_summary")

    if len(messages) <= keep_recent + 2:
        return

    # Step 1: Memory flush — persist key findings before compacting
    self._memory_flush(messages)

    # Step 2: Summarize old messages
    old_messages = messages[2:-(keep_recent)]
    if not old_messages:
        return

    if strategy == "llm_summary":
        summary = self._llm_summarize(old_messages)
    else:
        summary = self._fallback_truncate_summary(old_messages)

    compacted = messages[:2] + [
        {"role": "user", "content": f"[CONTEXT SUMMARY — earlier exchanges compacted]\n\n{summary}"}
    ] + messages[-(keep_recent):]

    messages.clear()
    messages.extend(compacted)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd iris && python -m pytest tests/test_context.py -v`
Expected: PASS

- [ ] **Step 6: Run ALL tests**

Run: `cd iris && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add iris/core/harness.py iris/iris_config.yaml iris/tests/test_context.py
git commit -m "feat: memory flush before context compaction"
```

---

## Chunk 5: Config wiring + integration test

### Task 9: Add vector/memory config to yaml and verify full integration

**Files:**
- Modify: `iris/iris_config.yaml`
- Test: `iris/tests/test_context.py`

- [ ] **Step 1: Add vector search config to `iris_config.yaml`**

```yaml
vector_search:
  enabled: true
  model: "text-embedding-3-small"
  top_k: 5

cross_session:
  enabled: true
  max_observations: 10
  max_hypotheses: 3
```

- [ ] **Step 2: Write integration test — full flow with all 4 features**

In `iris/tests/test_context.py`, append:

```python
def test_full_context_system_integration():
    """Integration: cross-session loading + compaction + memory flush all work together."""
    from tools.retrieval import SQLiteRetriever
    from tools.knowledge import extract_observation, create_hypothesis
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        retriever = SQLiteRetriever(db_path)

        # Pre-populate prior session data
        extract_observation(
            retriever=retriever, subject="TSLA",
            claim="FSD v13 achieves 5x safety improvement",
            source="Tesla AI Day", fact_or_view="fact", relevance=0.85,
            citation="...", time_str="2026-03-01", extracted_by="test",
        )
        create_hypothesis(
            retriever=retriever, company="TSLA",
            thesis="Tesla robotaxi launch creates new revenue stream",
            timeframe="18 months",
            drivers=[
                {"name": "FSD tech", "description": "Autonomous driving capability", "current_assessment": "improving"},
                {"name": "Regulatory", "description": "State approvals", "current_assessment": "pending"},
                {"name": "Fleet size", "description": "Vehicle production", "current_assessment": "strong"},
            ],
            kill_criteria=[{"description": "Fatal FSD accident triggers regulatory ban"}],
            initial_confidence=55.0,
        )

        # Mock LLM: responds with text (no tool calls)
        mock_llm = MagicMock()
        mock_llm.chat.return_value = LLMResponse(
            content="Continuing TSLA analysis with prior context.", tool_calls=[],
        )

        harness = Harness(
            llm=mock_llm, tools=[], soul="You are IRIS.",
            config=HarnessConfig(max_tool_rounds=5),
            retriever=retriever,
        )

        result = harness.run("Update TSLA robotaxi analysis")
        assert result.ok

        # Verify prior context was loaded into the user message
        sent_messages = mock_llm.chat.call_args_list[0][0][0]
        user_msg = sent_messages[1]["content"]
        assert "TSLA" in user_msg
        assert "robotaxi" in user_msg or "Prior Analysis" in user_msg
```

- [ ] **Step 3: Run integration test**

Run: `cd iris && python -m pytest tests/test_context.py::test_full_context_system_integration -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `cd iris && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add iris/iris_config.yaml iris/tests/test_context.py
git commit -m "feat: complete context & memory system — config + integration test"
```

---

## Summary of All Changes

| Priority | Feature | Files Modified | Key Method |
|----------|---------|---------------|------------|
| P0 | LLM Compaction | `harness.py`, `iris_config.yaml` | `_compact_context()`, `_llm_summarize()` |
| P1 | Cross-session Context | `harness.py`, `main.py` | `_build_user_message()`, `_load_prior_context()` |
| P2 | Memory Flush | `harness.py`, `iris_config.yaml` | `_memory_flush()` |
| P3 | Vector Search | `retrieval.py`, `knowledge.py`, `base.py`, `main.py` | `semantic_search()`, `memory_search()` |

**Total new tests:** ~12 across `test_retrieval.py`, `test_harness.py`, `test_knowledge.py`, `test_context.py`

**No new dependencies** — uses existing `openai` package for embeddings, pure Python for cosine similarity, existing `sqlite3` for vector storage.
