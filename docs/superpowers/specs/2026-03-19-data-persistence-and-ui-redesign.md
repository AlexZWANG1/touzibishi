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

### Activate Existing Dead Tables

These tables already exist in `retrieval.py` with full CRUD methods. The change is making tools actually call the save methods:

- **`build_dcf`** → calls `retriever.save_valuation()` after computing results
- **`create_hypothesis`** → calls `retriever.save_hypothesis()` after creating hypothesis
- **`add_evidence_card`** → updates hypothesis evidence_log via retriever
- **Analysis completion** → calls `retriever.save_audit_trail()` to capture full audit

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

`sse_bridge.py` is modified so `harness_event_to_sse()` also writes to the session accumulator. This ensures data is captured server-side even if the browser disconnects.

### API Changes

#### New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/history` | GET | List analysis runs (paginated, filterable by ticker) |
| `GET /api/history/{run_id}` | GET | Full snapshot for replay |

#### Modified Endpoints

| Endpoint | Change |
|----------|--------|
| `GET /api/watchlist` | Rewrite: DB for fair_value/thesis/recommendation + parallel yf_quote for live price/name |
| `GET /api/calibration` | Read fair_value from valuations table instead of regex |

#### Deleted Code

- `api.py`: `_parse_company_file()`, `_extract_number()`, `_extract_section()`, `_compute_alerts()`, `_extract_kill_section()`, `_check_calibration_warning()` — all regex-based parsers
- `memory.py`: `_extract_fair_value()` — regex extraction
- `memory.py`: `_append_calibration_entry()` regex logic — replaced with DB read

### Watchlist Data Sources (After)

| Field | Source | Mechanism |
|-------|--------|-----------|
| ticker | `analysis_runs` + `hypotheses` | Deduplicated set of all analyzed tickers |
| name | `yf_quote()` | Real-time, parallel on page load |
| market_price | `yf_quote()` | Real-time, parallel on page load |
| fair_value | `valuations` table | Latest record for ticker |
| gap | Computed | `(fair_value - market_price) / market_price` |
| thesis | `hypotheses` table | Latest record's `thesis` field |
| recommendation | `trade_scores` table | Latest record's `recommendation` field |
| alerts | Computed from DB | Kill criteria from hypotheses + staleness from analysis_runs |

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
- `iris/backend/sse_bridge.py` — accumulate into session alongside SSE conversion
- `iris/tools/memory.py` — delete `_extract_fair_value`, change calibration to read from DB
- `iris/tools/retrieval.py` — add `analysis_runs` table to `_init_db`, add save/query methods
- `iris/skills/dcf/tool.py` — call `save_valuation()` after DCF computation
- `iris/skills/hypothesis/tool.py` — call `save_hypothesis()` after creation
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
