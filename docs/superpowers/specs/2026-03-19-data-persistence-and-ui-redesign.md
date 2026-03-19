# IRIS Data Persistence & UI Redesign

**Date:** 2026-03-19
**Status:** Approved (pending implementation)

## Problem Statement

The IRIS platform has a "one-shot" problem: analysis results exist only in browser memory during the SSE stream and are permanently lost when the page closes. The backend has well-designed Pydantic models and SQLite tables (`valuations`, `hypotheses`, `trade_scores`, `audit_trails`) that are never written to. Meanwhile, the watchlist uses fragile regex extraction from free-text markdown files, frequently failing to parse fair_value, thesis, and market_price.

### Issues Identified (7 anti-patterns)

1. `save_memory` stores free-text md → regex re-extracts fair_value (circular, fragile)
2. `valuations` table exists but is dead code — never written by `build_dcf`
3. `hypotheses` table has structured thesis/confidence but watchlist doesn't read it
4. `audit_trails` table has full analysis snapshots but no API endpoint
5. `trade_scores` table has recommendations but frontend doesn't display them
6. SSE tool_end results are the only panel data source — lost when browser closes
7. `harness.run_log` writes to SQLite but has no API

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Persistence granularity | Full snapshot (timeline + panels + reasoning + thinking) | Enough to reproduce the complete analysis page |
| Homepage layout | Vertical split (watchlist top, history bottom) | Simple, both visible at once |
| Price refresh | Parallel all tickers + refresh button | 6 tickers ~2-3s, simple implementation |
| Thinking display | Inline in Timeline as collapsible entries | Shows causal relationship (thought → tool call) |
| Regex cleanup scope | Full — activate all dead tables | Eliminate all regex extraction, connect structured data end-to-end |
| Watchlist row click | Open most recent analysis replay | Natural intent is "see last analysis", not "re-run" |

## Architecture

### New Table: `analysis_runs`

```sql
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    ticker TEXT,
    status TEXT NOT NULL,         -- 'complete' | 'error'
    created_at TEXT NOT NULL,     -- ISO 8601
    reasoning_text TEXT,
    thinking_text TEXT,
    timeline_json TEXT,           -- JSON array of timeline events
    panels_json TEXT,             -- JSON object {data, model, comps, memory}
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_ticker ON analysis_runs(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created ON analysis_runs(created_at DESC);
```

### Schema Migrations for Existing Tables

The `valuations` table currently has no `ticker` column (only `id` and `data`). The `trade_scores` table has no `ticker` column either (only `id`, `hypothesis_id`, `data`). Both need a `ticker` column for direct watchlist queries:

```sql
-- Added to _init_db() alongside CREATE TABLE IF NOT EXISTS
-- SQLite ALTER TABLE is safe — adds column with NULL default to existing rows
ALTER TABLE valuations ADD COLUMN ticker TEXT;
ALTER TABLE trade_scores ADD COLUMN ticker TEXT;
CREATE INDEX IF NOT EXISTS idx_valuations_ticker ON valuations(ticker);
CREATE INDEX IF NOT EXISTS idx_trade_scores_ticker ON trade_scores(ticker);
```

The `ALTER TABLE` calls should be wrapped in try/except to handle the case where columns already exist (idempotent migration). The `ValuationOutput` Pydantic model does not need a `ticker` field — the ticker is stored as a table column alongside the JSON `data` blob, matching the existing pattern used by `hypotheses` (which has `company` column + `data`).

### Activate Existing Dead Tables

These tables already exist in `retrieval.py` with full CRUD methods. Changes needed:

- **`build_dcf`** → calls `retriever.save_valuation(valuation, id, ticker=ticker)` after computing results. The `save_valuation()` method signature gains an optional `ticker` parameter.
- **`create_hypothesis`** → already calls `retriever.save_hypothesis()` (confirmed in `iris/skills/hypothesis/tools.py:172,232`). No change needed — this is NOT dead code.
- **`add_evidence_card`** → already updates hypothesis evidence_log in `iris/skills/hypothesis/tools.py`. No change needed.
- **Analysis completion** → calls `retriever.save_audit_trail()` to capture full audit

**Note:** `save_valuation()` and `save_trade_score()` method signatures must be updated to accept and persist the `ticker` parameter.

### Data Flow (After)

```
User submits query
  → POST /api/analyze → session created → SSE stream starts
  │
  ├─ Each tool call → SSE push to frontend + session.accumulate() on backend
  ├─ <thinking> blocks → SSE push + accumulated as timeline thinking entries
  ├─ build_dcf() → SSE push + retriever.save_valuation()
  ├─ create_hypothesis() → SSE push + retriever.save_hypothesis()
  ├─ get_comps() → SSE push + accumulated in session
  ├─ save_memory() → writes md note (free text only, no regex extraction)
  │
  ▼ Analysis complete
  ├─ retriever.save_audit_trail()
  ├─ db.save_analysis_run() (full snapshot from session accumulator)
  ├─ calibration entry (reads fair_value from valuations table, not regex)
  └─ SSE: analysis_complete → done
```

### Server-Side Session Accumulator

`AnalysisSession` gains an accumulator that mirrors what the frontend collects from SSE:

```python
@dataclass
class AnalysisSession:
    # ... existing fields ...

    # New: server-side accumulator
    accumulated_timeline: list[dict] = field(default_factory=list)
    accumulated_reasoning: str = ""
    accumulated_thinking: str = ""
    accumulated_panels: dict = field(default_factory=dict)
```

`sse_bridge.py`'s `harness_event_to_sse()` remains a pure function (event → dict). The accumulation happens in `api.py`'s `on_event` callback, which already has access to the session object:

```python
# In api.py start_analysis()
def on_event(event: HarnessEvent) -> None:
    sse = harness_event_to_sse(event)
    if sse is not None:
        session.events.put(sse)
        session.accumulate(sse)  # NEW: server-side accumulation
        session.touch()
```

This avoids changing `harness_event_to_sse()`'s pure function signature.

### API Changes

#### New Endpoints

**`GET /api/history?ticker=AAPL&limit=30&offset=0`**

Returns paginated list of analysis runs. All query params optional.

```json
{
  "items": [
    {
      "id": "abc123def456",
      "query": "分析 NVDA 在 AI 基础设施赛道的投资机会",
      "ticker": "NVDA",
      "status": "complete",
      "created_at": "2026-03-19T10:30:00Z",
      "tokens_in": 8500,
      "tokens_out": 3800
    }
  ],
  "total": 42,
  "limit": 30,
  "offset": 0
}
```

**`GET /api/history/{run_id}`**

Returns full snapshot for replay. The response shape matches what `loadSnapshot()` expects on the frontend.

```json
{
  "id": "abc123def456",
  "query": "分析 NVDA",
  "ticker": "NVDA",
  "status": "complete",
  "created_at": "2026-03-19T10:30:00Z",
  "reasoning_text": "...",
  "thinking_text": "...",
  "timeline": [
    {"id": "tool-yf_quote-1710...", "timestamp": 1710..., "tool": "yf_quote", "message": "...", "phase": "gather", "color": "green", "status": "complete"},
    {"id": "thinking-1710...", "tool": "thinking", "message": "preview...", "fullText": "...", "phase": "gather", "color": "gold", "status": "complete"}
  ],
  "panels": {
    "data": {"metrics": [...], "financialTables": [...]},
    "model": {"fairValue": {...}, "sensitivityData": [...], ...},
    "comps": {"peers": [...], "scatterData": [...]},
    "memory": {"calibrationHits": 0, "calibrationMisses": 0, "recentRecalls": [...]}
  },
  "tokens_in": 8500,
  "tokens_out": 3800
}
```

#### Modified Endpoints

| Endpoint | Change |
|----------|--------|
| `GET /api/watchlist` | Rewrite: DB for fair_value/thesis/recommendation + parallel yf_quote for live price/name |
| `GET /api/calibration` | Read fair_value from valuations table instead of regex |

#### Deleted Code

- `api.py`: `_parse_company_file()`, `_extract_number()`, `_extract_section()`, `_compute_alerts()`, `_extract_kill_section()`, `_check_calibration_warning()` — all regex-based parsers
- `memory.py`: `_extract_fair_value()` — regex extraction
- `memory.py`: `_append_calibration_entry()` regex logic — replaced with DB read. The new implementation queries `valuations` table for the latest `predicted` value for the ticker. If no valuation exists (e.g., `build_dcf` was never called), no calibration entry is created — this is correct behavior since there's nothing to calibrate.

### Watchlist Data Sources (After)

| Field | Source | Mechanism |
|-------|--------|-----------|
| ticker | `analysis_runs` + `hypotheses` | Deduplicated set of all analyzed tickers |
| name | `yf_quote()` | Real-time, parallel on page load |
| market_price | `yf_quote()` | Real-time, parallel on page load |
| fair_value | `valuations` table | Latest record for ticker |
| gap | Computed | `(fair_value - market_price) / market_price` |
| thesis | `hypotheses` table | Latest record's `thesis` field |
| recommendation | `trade_scores` table | Latest record for ticker (uses new `ticker` column) |
| alerts | Computed from DB | Kill criteria from hypotheses + staleness from analysis_runs |
| latest_run_id | `analysis_runs` table | Most recent run_id for this ticker (for click → replay) |

## Frontend Changes

### Homepage (`/`)

**Layout:** Search bar + refresh button → Watchlist table → History list

**Data loading:**
- Page load → parallel `GET /api/watchlist` + `GET /api/history`
- Refresh button → re-fetch `/api/watchlist` with loading state

**Interactions:**
- Click watchlist row → navigate to `/analysis/{latest_run_id}` (replay mode). If no analysis exists, show prompt.
- Click history row → navigate to `/analysis/{run_id}` (replay mode)
- Search bar submit → `POST /api/analyze` → navigate to `/analysis/{new_id}` (live mode)

### Analysis Page (`/analysis/[id]`) — Dual Mode

**Mode detection:**
```
Enter /analysis/[id]
  → Try SSE connection to /api/analyze/{id}/stream
  → If 404 → fallback to GET /api/history/{id}
  → Load snapshot into store, pageState = "COMPLETE"
```

**Replay mode differences:**
- Top banner: "历史回看 — {date} {query}"
- Bottom SteeringInput hidden
- All other components identical (same panels, timeline, reasoning area)

### Timeline — Thinking Entries

Thinking blocks become first-class timeline items:

```typescript
// New timeline event type
{
    id: "thinking-{timestamp}",
    timestamp: number,
    tool: "thinking",        // special type
    message: "数据够了，准备构建 DCF...",  // first line as preview
    fullText: "...",         // complete thinking block
    phase: currentPhase,
    color: "gold",           // distinct from tool colors
    status: "complete",
    collapsed: true,         // default collapsed
}
```

**Rendering:** Gold left border, "AI 思考" label, click to expand/collapse.

**SSE parsing change:** `handleSSEEvent` for `text_delta` detects `<thinking>` boundaries and emits timeline thinking entries in addition to accumulating thinkingText.

### Store Changes (`useAnalysisStore`)

New action:
```typescript
loadSnapshot: (snapshot: AnalysisSnapshot) => void
// Populates timeline, reasoningText, thinkingText, all panels from snapshot
// Sets pageState to "COMPLETE"
```

## Key Invariant: Session ID = analysis_runs ID

The `session.id` (generated in `sessions.py` as `uuid.uuid4().hex[:16]`) is reused as the `analysis_runs.id`. This is critical because:

1. `POST /api/analyze` returns `analysisId` (= session.id) to the frontend
2. Frontend navigates to `/analysis/{analysisId}` and connects SSE via session.id
3. When analysis completes, `analysis_runs` is written with `id = session.id`
4. Later, `/analysis/{same_id}` can fall back to `GET /api/history/{same_id}`

If these IDs diverged, the dual-mode detection on the analysis page would break.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Browser closes mid-analysis | Backend continues, session accumulator captures all data, writes to DB on completion |
| Backend crashes mid-analysis | analysis_runs not written (writes on completion). Analysis lost. Acceptable — no regression from current behavior |
| build_dcf not called (macro question) | valuations empty, watchlist shows "—" for fair_value. analysis_runs still recorded |
| Same ticker analyzed multiple times | Watchlist shows latest fair_value/thesis. History shows all runs. All versions preserved in DB |
| yf_quote fails for some tickers | Those rows show "—" for price/name, others display normally. Non-blocking |
| First use, empty DB | Watchlist empty with guide text. History section hidden |
| analysis_runs snapshot is large | panels_json may be large for complex analyses. Acceptable — SQLite handles multi-MB TEXT fields fine. Consider VACUUM schedule if DB grows past 100MB |

## Files to Modify

### Backend
- `iris/backend/api.py` — rewrite watchlist endpoint, add history endpoints, delete regex functions
- `iris/backend/sessions.py` — add accumulator fields to AnalysisSession
- `iris/backend/sse_bridge.py` — no change needed (accumulation happens in api.py's on_event callback)
- `iris/tools/memory.py` — delete `_extract_fair_value`, change calibration to read from DB
- `iris/tools/retrieval.py` — add `analysis_runs` table to `_init_db`, add `ticker` column to `valuations` and `trade_scores` (ALTER TABLE with try/except for idempotency), add save/query methods for analysis_runs
- `iris/skills/dcf/tools.py` — call `save_valuation()` after DCF computation (note: file is `tools.py` plural)
- `iris/skills/hypothesis/tools.py` — already calls `save_hypothesis()`, no change needed
- `iris/core/harness.py` — call `save_audit_trail()` on run completion

### Frontend
- `iris-frontend/src/app/page.tsx` — new layout with watchlist + history sections + refresh button
- `iris-frontend/src/app/analysis/[id]/page.tsx` — dual mode (live vs replay), replay banner
- `iris-frontend/src/hooks/useAnalysisStore.ts` — add loadSnapshot action, thinking timeline entries
- `iris-frontend/src/hooks/useAnalysisStream.ts` — add 404 fallback to snapshot loading
- `iris-frontend/src/components/StreamingTimeline.tsx` — render thinking entries (collapsible, gold)
- `iris-frontend/src/components/TimelineItem.tsx` — new thinking item variant
- `iris-frontend/src/components/WatchlistGrid.tsx` — add name, recommendation columns
- `iris-frontend/src/components/WatchlistCard.tsx` — fix click behavior, add recommendation display
- `iris-frontend/src/utils/api.ts` — add getHistory, getHistoryDetail, updated getWatchlist
- `iris-frontend/src/types/analysis.ts` — add AnalysisSnapshot, ThinkingTimelineEvent types

### Delete
- All regex parsing functions in `api.py` and `memory.py` (listed above)
