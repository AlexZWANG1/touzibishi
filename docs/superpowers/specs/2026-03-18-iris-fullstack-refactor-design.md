# IRIS Full-Stack Refactor Design

> Skills architecture + Memory system + FastAPI backend + Next.js frontend
>
> Source specs: `IRIS_Development_Spec_v0.4.md` + `iris_ui_spec_v1.0.md`

---

## 1. Overview

Transform IRIS from a monolithic CLI + Streamlit app into a full-stack system with:

- **Skills architecture**: Pluggable analysis capabilities (DCF, Hypothesis tracking, future skills)
- **Memory system**: Persistent file-based memory for research compounding
- **FastAPI backend**: REST + SSE API wrapping the existing harness
- **Next.js frontend**: Three-page app (Home, Analysis Workspace, Memory Manager)

### Execution Strategy

```
Step 1 (serial):    Backend core refactoring — touches shared files
Step 2 (parallel):  Agent A: DCF Skill | Agent B: Memory | Agent C: FastAPI | Agent D: Frontend
Step 3 (serial):    Integration + end-to-end testing
```

---

## 2. Current State

### File inventory (iris/)

```
iris/
├── core/
│   ├── __init__.py
│   ├── budget.py            # BudgetTracker, BudgetPolicy — KEEP
│   ├── config.py            # load_config(), load_soul() — MODIFY
│   ├── context.py           # ContextAssembler — KEEP
│   ├── harness.py           # Agent loop — MODIFY (minor)
│   ├── invariants.py        # Post-execution checks — DELETE
│   ├── loop_detector.py     # Loop detection — KEEP
│   ├── schemas.py           # Pydantic models — KEEP
│   └── tool_hooks.py        # ToolHooks system — MODIFY
├── guards/
│   ├── __init__.py          # DELETE entire directory
│   └── guards.py            # DELETE
├── llm/
│   ├── __init__.py          # KEEP
│   ├── base.py              # KEEP
│   └── openai_client.py     # KEEP
├── soul/
│   ├── v0.1.md              # KEEP
│   ├── role.md              # KEEP
│   └── analysis_guide.md    # REPLACE with analysis_process.md
├── tools/
│   ├── __init__.py          # KEEP
│   ├── base.py              # KEEP (no TOOL_PHASES to remove)
│   ├── search.py            # KEEP
│   ├── financials.py        # KEEP
│   ├── knowledge.py         # DELETE after migration to skills/hypothesis/
│   └── retrieval.py         # KEEP
├── tests/                   # UPDATE to match new structure
├── ui/
│   └── app.py               # DELETE (replaced by Next.js)
├── main.py                  # MODIFY for skill_loader
├── iris_config.yaml         # MODIFY (slim down)
└── pyproject.toml           # UPDATE dependencies
```

### Key architectural discovery

Guards and invariants are NOT called directly in `harness._dispatch()`. They operate through the `ToolHooks` system in `core/tool_hooks.py`:

- `before_tool_call(ctx)` — pre-execution validation
- `after_tool_call(ctx, result)` — post-execution checks

This means "deleting guards" = removing their hook registration + inlining validation into each tool function. The harness dispatch flow itself does not need to change.

---

## 3. Step 1: Backend Core Refactoring (Serial)

### 3.1 Skill Loader — NEW `core/skill_loader.py`

```python
def load_skills(skills_dir: str, context: dict = None) -> tuple[list[Tool], str]:
    """
    Scan skills/ folder. For each subfolder:
      - SKILL.md → collected into skill_soul text
      - tools.py → module.TOOLS list or module.register(context) → tools
      - config.yaml → loaded into skill-specific config namespace
    Returns (all_skill_tools, combined_skill_soul_text)
    """
```

Design:
- `sorted(Path(skills_dir).iterdir())` for deterministic load order
- Each skill's `tools.py` exports either:
  - A `TOOLS` list of `Tool` instances (for skills with no external dependencies)
  - A `register(context: dict) -> list[Tool]` function (for skills needing shared dependencies like `retriever`)
- `context` dict passed from `main.py` carries shared dependencies (e.g., `{"retriever": retriever}`)
- Each skill's `config.yaml` accessible via `get_skill_config(skill_name, key)`
- Missing files are silently skipped (a skill can have only SKILL.md)
- Duplicate tool names across skills → raise `SkillLoadError`

### 3.2 config.py Changes

`load_soul()` changes from hardcoded filenames to directory scan:

```python
def load_soul(soul_dir: Path = None) -> str:
    soul_dir = soul_dir or Path(__file__).parent.parent / "soul"
    parts = []
    for md_file in sorted(soul_dir.glob("*.md")):
        parts.append(md_file.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts) if parts else FALLBACK_SOUL
```

New function for skill config:

```python
_skill_configs: dict[str, dict] = {}

def register_skill_config(skill_name: str, config: dict):
    _skill_configs[skill_name] = config

def get_skill_config(skill_name: str, key: str, default=None):
    return _skill_configs.get(skill_name, {}).get(key, default)
```

### 3.3 main.py Refactoring

Before:
```python
external_tools = [Tool(exa_search, ...), Tool(web_fetch, ...), ...]
knowledge_tools = [Tool(extract_observation, ...), ..., Tool(memory_search, ...)]
tools = external_tools + knowledge_tools
```

After:
```python
from core.skill_loader import load_skills

core_tools = [
    Tool(exa_search, EXA_SEARCH_SCHEMA),
    Tool(web_fetch, WEB_FETCH_SCHEMA),
    Tool(fmp_get_financials, FMP_GET_FINANCIALS_SCHEMA),
    Tool(fred_get_macro, FRED_GET_MACRO_SCHEMA),
]
memory_tools = [
    Tool(recall_memory, RECALL_MEMORY_SCHEMA),
    Tool(save_memory, SAVE_MEMORY_SCHEMA),
    Tool(check_calibration, CHECK_CALIBRATION_SCHEMA),
]
skill_tools, skill_soul = load_skills("./skills")

base_soul = load_soul()
full_soul = base_soul + "\n\n---\n\n" + skill_soul

harness = Harness(
    tools=core_tools + memory_tools + skill_tools,
    soul=full_soul,
    ...
)
```

### 3.4 ToolHooks Simplification

Current `tool_hooks.py` has `DefaultToolHooks` that does arg normalization + error tagging. The guard/invariant behavior is separate.

Change: Remove any guard/invariant hook registration. Keep `DefaultToolHooks` for arg normalization and error tagging (these are useful). Each tool function now does its own input validation and returns `ToolResult(status="error", hint=...)` on bad input.

### 3.5 Delete Dead Code

- Delete `guards/` directory entirely
- Delete `core/invariants.py`
- Delete `ui/app.py` (Streamlit)
- Delete `tools/knowledge.py` after migrating to `skills/hypothesis/`
- Update any imports that reference deleted modules

### 3.6 iris_config.yaml Slimming

Remove these sections (they move to skill configs):
- `scoring` (weights, caps, recommendation_tiers) → `skills/dcf/config.yaml` or `skills/hypothesis/config.yaml`
- `evidence` (scaling_factor, direction_map, min_count_for_action) → `skills/hypothesis/config.yaml`
- `constraints` (min_bull_bear_spread) → `skills/dcf/config.yaml`

Add:
```yaml
memory:
  base_dir: "./memory"
  calibration_review_days: 90

skills:
  dir: "./skills"
```

Keep:
- `harness` section (all params)
- `compaction` section
- `vector_search` section
- `cross_session` section
- `loop_detection` section (in code, referenced by loop_detector.py)

### 3.7 Hypothesis Skill Migration

Create `skills/hypothesis/` from existing `tools/knowledge.py`:

**`skills/hypothesis/tools.py`** — migrated functions:
- `extract_observation` — unchanged logic, add inline validation (was in guards)
- `create_hypothesis` — add inline validation: 3-6 drivers, confidence 0-100
- `add_evidence_card` — unchanged Bayesian update logic, add inline validation
- `query_knowledge` — unchanged

Note: `memory_search` is NOT migrated here. It stays as a core tool in `tools/retrieval.py` because it provides cross-skill semantic search over all stored objects (observations, hypotheses, etc.). It is registered in `main.py` alongside core tools, not as part of any skill.

These functions keep their dependency on `retriever` (SQLiteRetriever). The `TOOLS` list passes `retriever` at registration time via closure or partial application.

**Retriever initialization**: `SQLiteRetriever` is instantiated in `main.py` using `DB_PATH` from `core/config.py` (env var `IRIS_DB_PATH`, default `./iris.db`). The retriever instance is passed to hypothesis skill tools during Skill Loader registration. The Skill Loader's `load_skills()` accepts an optional `context` dict that skills can use for shared dependencies:

```python
skill_tools, skill_soul = load_skills("./skills", context={"retriever": retriever})
```

Each skill's `tools.py` defines `def register(context: dict) -> list[Tool]` instead of a static `TOOLS` list when it needs dependencies.

**Removed from migration** (replaced by DCF Skill):
- `run_valuation` — replaced by `build_dcf`
- `compute_trade_score` — removed, scoring logic moves to DCF skill or is eliminated
- `write_audit_trail` — removed for now, audit is implicit in memory system

**`skills/hypothesis/SKILL.md`**:
```markdown
# Hypothesis Tracking Skill

## When to use
Use this skill throughout any analysis to structure your research.
Observations capture facts. Hypotheses capture your thesis.
Evidence cards link observations to hypotheses with Bayesian updates.

## How to think
1. Extract observations from every source you read
2. Form a hypothesis with 3-6 drivers and kill criteria
3. Link evidence to hypothesis — confidence updates automatically
4. High confidence + strong evidence → proceed to valuation

## Key constraints
- Every observation needs a citation
- Hypothesis must have 3-6 drivers (not fewer, not more)
- Confidence is 0-100 (50=uncertain, 80=strong, 90+=rare)
```

**`skills/hypothesis/config.yaml`**:
```yaml
scaling_factor: 10
min_evidence_count: 3
direction_map:
  supports: 1.0
  refutes: -1.0
  mixed: 0.2
  neutral: 0.0
```

### 3.8 Soul File Changes

**Keep unchanged:**
- `soul/v0.1.md` — investment philosophy (excellent as-is)
- `soul/role.md` — behavior rules (excellent as-is)

**Delete:**
- `soul/analysis_guide.md`

**New files:**

**`soul/analysis_process.md`** (replaces analysis_guide.md):
Content from v0.4 spec section 5.3: Read memory → Research → Choose skill → Self-check → Output → Update memory.

**`soul/self_check.md`**:
Content from v0.4 spec section 5.4: Implied P/E check, FCF yield check, terminal value % check, bull/bear spread check, assumption reasonableness, vs consensus.

**`soul/steering.md`**:
Content from UI spec section 6.1: Four steering categories (SUGGESTION, OVERRIDE, QUESTION, REDIRECT) + section 6.2: `request_user_input` usage rules (use sparingly, 0-1 per analysis).

---

## 4. Step 2A: DCF Skill (Agent A, parallel)

### 4.1 Files

```
skills/dcf/
├── SKILL.md        # When to use, how to think, constraints
├── tools.py        # build_dcf() + get_comps()
└── config.yaml     # wacc_range, terminal_growth_max, etc.
```

### 4.2 `build_dcf(assumptions: dict)` — Full DCF Engine

**Input schema** (v0.4 spec section 2.3):

```python
BUILD_DCF_SCHEMA = make_tool_schema(
    name="build_dcf",
    description="Build a DCF model from assumptions. Code computes fair value — you provide the inputs.",
    properties={
        "assumptions": {
            "type": "object",
            "description": "DCF assumptions JSON with segments, margins, WACC, etc.",
            "properties": {
                "company": {"type": "string"},
                "ticker": {"type": "string"},
                "analysis_date": {"type": "string"},
                "projection_years": {"type": "integer"},
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "current_annual_revenue": {"type": "number"},
                            "growth_rates": {"type": "array", "items": {"type": "number"}},
                            "reasoning": {"type": "string"}
                        },
                        "required": ["name", "current_annual_revenue", "growth_rates", "reasoning"]
                    }
                },
                "gross_margin": {"type": "object"},
                "opex_pct_of_revenue": {"type": "object"},
                "tax_rate": {"type": "object"},
                "capex_pct_of_revenue": {"type": "object"},
                "working_capital_change_pct": {"type": "object"},
                "wacc": {"type": "object"},
                "terminal_growth": {"type": "object"},
                "net_cash": {"type": "number"},
                "shares_outstanding": {"type": "number"},
                "current_price": {"type": "number"},
                "scenarios": {"type": "array"}
            },
            "required": ["company", "ticker", "projection_years", "segments",
                         "gross_margin", "wacc", "terminal_growth",
                         "net_cash", "shares_outstanding", "current_price"]
        }
    },
    required=["assumptions"],
)
```

**Computation logic** (all math hardcoded):

```
For each year t (1..projection_years):
  1. Revenue = sum of all segments' projected revenue for year t
     segment_revenue[t] = segment.current_annual_revenue * product(1 + growth_rates[0..t])
  2. COGS = Revenue * (1 - gross_margin[t])
  3. Gross_Profit = Revenue - COGS
  4. OpEx = Revenue * opex_pct[t]
  5. EBIT = Gross_Profit - OpEx
  6. Tax = EBIT * tax_rate
  7. NOPAT = EBIT - Tax
  8. CapEx = Revenue * capex_pct[t]
  9. Delta_WC = Revenue * wc_change_pct[t]
  10. FCF = NOPAT - CapEx - Delta_WC

Terminal_Value = FCF[n] * (1 + terminal_growth) / (WACC - terminal_growth)
Discounted_FCF[t] = FCF[t] / (1 + WACC)^t
Discounted_TV = Terminal_Value / (1 + WACC)^n
Enterprise_Value = sum(Discounted_FCF) + Discounted_TV
Equity_Value = Enterprise_Value + net_cash
Fair_Value_Per_Share = Equity_Value / shares_outstanding
Gap_Pct = (Fair_Value_Per_Share - current_price) / current_price * 100
```

**Default values for optional parameters** (used when AI omits them):
- `opex_pct_of_revenue`: `[0.20] * projection_years` (20% of revenue)
- `tax_rate`: `{"value": 0.21}` (US corporate rate)
- `capex_pct_of_revenue`: `[0.05] * projection_years` (5% of revenue)
- `working_capital_change_pct`: `[0.01] * projection_years` (1% of revenue)
- `analysis_date`: today's date
- `scenarios`: `[]` (no scenarios, base case only)

**Implied multiples** (computed from the model output):
- Fwd P/E = Fair_Value_Per_Share / (NOPAT[1] / shares_outstanding)
  - Note: uses NOPAT as proxy for earnings. For leveraged companies this overstates P/E slightly. Documented as known simplification.
- EV/EBITDA = Enterprise_Value / EBIT[1]
- FCF Yield = FCF[1] / (Fair_Value_Per_Share * shares_outstanding)
- PEG = Fwd_PE / (revenue_growth_Y1 * 100)

**Sensitivity matrix** (deliberate enhancement over v0.4 spec's 1D format — uses 2D matrix for richer frontend heatmap):
- WACC axis: [wacc-2%, wacc-1%, wacc, wacc+1%, wacc+2%]
- Terminal growth axis: [tg-1%, tg-0.5%, tg, tg+0.5%, tg+1%]
- Each cell: recompute fair_value_per_share with that (WACC, TG) pair
- Result: 5x5 matrix of fair values

**Scenario weighting** (if `scenarios` provided):
- For each scenario: apply `key_override` to base assumptions, recompute fair value
- Weighted value = base_probability * base_fv + sum(scenario_probability * scenario_fv)

**Inline validation**:
- terminal_growth >= WACC → error with hint
- WACC outside config range → error with hint
- segments empty → error
- growth_rates length != projection_years → error

**Output** (v0.4 spec section 2.4):
```json
{
  "fair_value_per_share": 165.2,
  "current_price": 142.0,
  "gap_pct": 16.3,
  "year_by_year": [{"year": 1, "revenue": 193.5e9, "fcf": 75.5e9, "discounted_fcf": 67.4e9}, ...],
  "terminal_value": 730e9,
  "discounted_terminal_value": 387e9,
  "enterprise_value": 617e9,
  "implied_multiples": {"fwd_pe": 38.2, "ev_ebitda": 28.1, "fcf_yield": 0.042, "peg_ratio": 1.09},
  "sensitivity": {"wacc_values": [...], "growth_values": [...], "matrix": [[...]]},
  "scenario_weighted_value": 168.5,
  "revision_history": [{"round": 1, "fair_value": 178, "revision_reason": null}]
}
```

Revision history: maintained as module-level state per analysis session, appended each time `build_dcf` is called within the same harness run.

### 4.3 `get_comps(ticker: str, peers: list[str])` — Peer Comparison

**Input**: ticker + list of peer tickers (AI chooses peers)

**Logic**:
1. For each company (target + peers): call FMP API for profile + ratios
2. Extract: Fwd P/E, EV/EBITDA, Revenue Growth, Gross Margin
3. Compute median row
4. Compute target vs median premium/discount for each metric

**Output**:
```json
{
  "target": "NVDA",
  "peers": [
    {"ticker": "NVDA", "fwd_pe": 38, "ev_ebitda": 28, "revenue_growth": 0.30, "gross_margin": 0.76, "is_target": true},
    {"ticker": "AMD", "fwd_pe": 32, ...},
    ...
  ],
  "median": {"fwd_pe": 28, "ev_ebitda": 22, "revenue_growth": 0.18, "gross_margin": 0.58},
  "target_vs_median": {"fwd_pe_premium": 0.36, "ev_ebitda_premium": 0.27, ...}
}
```

### 4.4 `skills/dcf/config.yaml`

```yaml
max_projection_years: 10
terminal_growth_max: 0.04
wacc_range: [0.05, 0.20]
comps_outlier_threshold: 0.50
sensitivity:
  wacc_steps: [-0.02, -0.01, 0, 0.01, 0.02]
  growth_steps: [-0.01, -0.005, 0, 0.005, 0.01]
```

### 4.5 `skills/dcf/SKILL.md`

Content from v0.4 spec section 4.4:
- When to use DCF (predictable cash flows)
- How to build assumptions (segments, reasoning required)
- Comps cross-check is REQUIRED after Round 1
- Multiple rounds expected
- Key constraints (terminal growth < WACC, growth deceleration, etc.)

### 4.6 Tests — `tests/test_dcf_skill.py`

| Test | Description |
|------|-------------|
| `test_build_dcf_basic` | Minimal 2-segment, 3-year projection → correct fair value |
| `test_build_dcf_nvda_example` | Full NVDA example from spec → matches expected output |
| `test_terminal_growth_exceeds_wacc` | terminal_growth >= WACC → error with hint |
| `test_wacc_out_of_range` | WACC < 5% or > 20% → error |
| `test_empty_segments` | No segments → error |
| `test_growth_rates_length_mismatch` | growth_rates length != projection_years → error |
| `test_sensitivity_matrix` | 5x5 matrix correctly computed |
| `test_scenario_weighting` | Bull/bear scenarios produce weighted value |
| `test_implied_multiples` | P/E, EV/EBITDA, FCF yield, PEG all correct |
| `test_revision_history` | Two calls → two entries in revision_history |
| `test_get_comps_output_format` | Mock FMP data → correct peer table + median |
| `test_get_comps_premium_calculation` | Target vs median premium % correct |
| `test_single_segment` | Single segment company works |
| `test_ten_year_projection` | max_projection_years = 10 works |
| `test_zero_net_cash` | net_cash = 0 or negative (net debt) works |

---

## 5. Step 2B: Memory System (Agent B, parallel)

### 5.1 Files

```
iris/tools/memory.py           # 3 tool functions
iris/memory/
├── companies/.gitkeep
├── sectors/.gitkeep
├── patterns/.gitkeep
└── calibration/
    └── prediction_log.jsonl   # empty initially
```

### 5.2 `recall_memory(company, memory_type)`

- `memory_type` = "company" | "sector" | "patterns" | "calibration"
- Maps to directory: `memory/{memory_type_plural}/`
  - "company" → `memory/companies/{company}.md`
  - "sector" → `memory/sectors/{company}.md` (company = sector name like "semiconductors")
  - "patterns" → `memory/patterns/{company}.md` (company = pattern name)
  - "calibration" → reads `memory/calibration/prediction_log.jsonl`, filters by company
- File not found → `ToolResult(status="ok", data={"content": null, "message": "No prior memory for {company}"})`
- File found → `ToolResult(status="ok", data={"content": "<file contents>", "path": "companies/NVDA.md"})`

### 5.3 `save_memory(company, memory_type, content)`

- Same path mapping as recall_memory
- Creates parent directory if needed
- Writes content to file (overwrite if exists)
- If memory_type == "company": also appends a calibration entry to `prediction_log.jsonl`
  - Parses content for "Fair Value" line → extracts predicted value
  - Entry: `{"date": today, "company": company, "metric": "fair_value", "predicted": value, "actual": null, "analyst_consensus": null, "note": "pending 90-day review"}`
  - The `analyst_consensus` field is preserved from v0.4 spec for future comparison against sell-side estimates. Set to null initially; can be populated by AI if consensus data is found during research.
- Returns `ToolResult(status="ok", data={"status": "ok", "path": "companies/{company}.md"})`

### 5.4 `check_calibration(company=None)`

- Reads `memory/calibration/prediction_log.jsonl`
- If company specified: filter entries
- Computes:
  - `total_predictions`: count of entries
  - `resolved_predictions`: count where actual is not null
  - `average_error`: mean of `error_pct` for resolved entries
  - `bias_direction`: "overestimate" if avg_error > 0.02, "underestimate" if < -0.02, else "balanced"
  - `bias_note`: human-readable summary (e.g., "连续 3 次低估 DC revenue 6-9%")
- Output matches UI spec section 7.2.4 `CalibrationResponse`:
  ```json
  {
    "entries": [...],
    "summary": {
      "totalPredictions": 5,
      "averageError": -0.07,
      "biasDirection": "underestimate",
      "biasNote": "连续低估 DC revenue 6-9%"
    }
  }
  ```

### 5.5 Memory config in iris_config.yaml

```yaml
memory:
  base_dir: "./memory"
  calibration_review_days: 90
```

### 5.6 Tests — `tests/test_memory.py`

| Test | Description |
|------|-------------|
| `test_recall_memory_no_file` | Non-existent company → content: null |
| `test_save_and_recall` | Save → recall → content matches |
| `test_save_creates_directory` | Save to non-existent subdir → auto-creates |
| `test_save_overwrites` | Save twice → second content wins |
| `test_save_company_appends_calibration` | Save company memory → prediction_log.jsonl gets entry |
| `test_check_calibration_empty` | Empty log → zero predictions |
| `test_check_calibration_filters_company` | Multiple companies in log → filter works |
| `test_check_calibration_bias_detection` | 3 consecutive underestimates → bias_direction = "underestimate" |
| `test_recall_sector` | Save/recall sector memory works |
| `test_recall_patterns` | Save/recall pattern memory works |
| `test_recall_calibration_type` | memory_type="calibration" reads jsonl filtered by company |
| `test_save_memory_tool_result_format` | ToolResult has correct status and path |

---

## 6. Step 2C: FastAPI Backend (Agent C, parallel)

### 6.1 Files

```
iris/backend/
├── __init__.py
├── api.py              # FastAPI app + all routes
├── sessions.py         # AnalysisSession class
├── sse_bridge.py       # HarnessEvent → SSE event conversion
└── user_input_tool.py  # request_user_input tool implementation
```

### 6.2 API Endpoints (complete list from UI spec section 7.2)

#### Analysis

**`POST /api/analyze`**
- Body: `{"query": str, "contextDocs": list[str] | null}`
- Creates `AnalysisSession`, starts harness in background thread
- Returns: `{"analysisId": uuid, "streamUrl": "/api/analyze/{id}/stream"}`

**`GET /api/analyze/{id}/stream`** (SSE)
- Opens Server-Sent Events stream
- Reads from `session.events` queue (thread-safe `queue.Queue`)
- Each event: `data: {"type": "...", "data": {...}}\n\n`
- Stream ends on `complete` or `error` event

**`POST /api/analyze/{id}/steer`**
- Body: `{"message": str}`
- Calls `session.harness.steer(message)`
- Returns: `{"status": "ok"}`

**`POST /api/analyze/{id}/respond`**
- Body: `{"response": str}`
- Submits response to blocked `request_user_input` tool
- Returns: `{"status": "ok"}`

#### Memory

**`GET /api/memory`**
- Scans `memory/` directory tree
- Returns: `{"companies": [...], "sectors": [...], "patterns": [...], "calibration": [...]}`
- Each entry: `{"name": str, "path": str, "lastModified": str, "sizeBytes": int}`

**`GET /api/memory/{type}/{filename}`**
- Reads file content
- Returns: `{"path": str, "content": str, "lastModified": str}`

**`PUT /api/memory/{type}/{filename}`**
- Body: `{"content": str}`
- Writes file
- Returns: `{"status": "ok", "lastModified": str}`

**`DELETE /api/memory/{type}/{filename}`**
- Deletes the specified memory file
- Returns: `{"status": "ok"}`
- 404 if file does not exist

#### Watchlist

**`GET /api/watchlist`**
- Scans `memory/companies/*.md`
- Parses each file for: ticker, fair value, market price, gap%, last analysis date, thesis status
- Parsing strategy: regex on "## Key Numbers" section for structured values
- **Alert generation logic**:
  - `stale_analysis`: lastAnalysisDate > 30 days ago
  - `kill_triggered`: parse "## Kill Criteria Status" section, check for lines containing "triggered" or `[x]`
  - `calibration_warning`: cross-reference with `prediction_log.jsonl` — if 3+ consecutive same-direction errors > 5%, generate warning
  - `earnings_upcoming`: NOT implemented in MVP (requires external calendar data source). Omitted from alerts.
- Returns: `WatchlistItem[]`

#### Calibration

**`GET /api/calibration?company=NVDA`**
- Delegates to `check_calibration()` tool function
- Returns: `CalibrationResponse` (entries + summary)

### 6.3 AnalysisSession

```python
class AnalysisSession:
    id: str
    harness: Harness
    events: queue.Queue[dict]           # threading.Queue, NOT asyncio.Queue
    status: Literal["running", "waiting", "complete", "error"]
    created_at: datetime
    user_input_event: threading.Event   # for request_user_input blocking
    user_input_response: str | None
```

**Thread safety note**: The `events` queue uses `queue.Queue` (from `threading` stdlib), NOT `asyncio.Queue`. This is because the harness runs in a separate thread and calls `on_event` from that thread. `asyncio.Queue` is not thread-safe. The SSE endpoint's async generator reads from this `queue.Queue` using `asyncio.get_event_loop().run_in_executor(None, session.events.get)` to avoid blocking the event loop.

Session lifecycle:
1. Created on POST /api/analyze
2. Harness runs in `threading.Thread(daemon=True)`
3. Harness `on_event` callback puts events into `queue.Queue` (thread-safe)
4. SSE endpoint reads from queue via executor (async-compatible)
5. Session stored in `dict[str, AnalysisSession]` (in-memory, MVP)
6. Background `asyncio.Task` runs every 60s, removes sessions inactive > 30 minutes

### 6.4 SSE Bridge

Maps harness `EventType` → SSE event format. Complete mapping of ALL harness event types:

| Harness EventType | SSE type | data fields |
|---|---|---|
| `RUN_START` | (not sent) | — |
| `RUN_END` | (not sent) | — |
| `TURN_START` | (not sent) | — |
| `TURN_END` | (not sent) | — |
| `TOOL_START` | `tool_start` | `{tool, args}` |
| `TOOL_END` | `tool_end` | `{tool, status, result}` |
| `TEXT_DELTA` | `text_delta` | `{content}` |
| `TEXT` | `text` | `{content}` |
| `CONTEXT_COMPACTED` | `context_compacted` | `{}` |
| `RETRY` | `retry` | `{attempt, reason}` |
| `ABORTED` | `error` | `{message, recoverable: false}` |
| `LOOP_DETECTED` | `system` | `{message: "Loop detected: {type}"}` |
| `BUDGET_TRIMMED` | `system` | `{message: "Budget trimmed: {reason}"}` |
| `STEERING_INJECTED` | `steering` | `{message: "{user_message}"}` |
| (from user_input_tool) | `user_input_needed` | `{question, context, options}` |
| (harness.run returns) | `complete` | `{ok, reply, toolLog, tokens}` |

**Phase tracking**: The actual harness does NOT emit a `PHASE_CHANGE` event. Phases are inferred on the **frontend side** by the `eventTranslator` based on which tools are being called:
- `gather`: exa_search, web_fetch, fmp_get_financials, fred_get_macro, recall_memory
- `analyze`: extract_observation, create_hypothesis, add_evidence_card
- `evaluate`: build_dcf, get_comps
- `finalize`: save_memory

The `PhaseIndicator` component tracks the highest phase seen so far (phases only advance forward). This is simpler than adding a new event type to the harness and avoids coupling the harness to UI concerns.

Tool results in `tool_end` events may be large. SSE bridge truncates `result` to 10KB max for transmission; full results are kept server-side.

### 6.5 `request_user_input` Tool

```python
def request_user_input(question: str, context: str, options: list[str] = None,
                       *, session: AnalysisSession) -> ToolResult:
    # 1. Push SSE event (thread-safe queue.Queue)
    session.events.put_nowait({
        "type": "user_input_needed",
        "data": {"question": question, "context": context, "options": options or []}
    })
    session.status = "waiting"

    # 2. Block until user responds
    session.user_input_event.clear()
    session.user_input_event.wait(timeout=300)  # 5 min timeout

    if session.user_input_response is None:
        return ToolResult(status="error", error="User did not respond within 5 minutes",
                          hint="Continue analysis with your best judgment", recoverable=True)

    # 3. Return user's response
    response = session.user_input_response
    session.user_input_response = None
    session.status = "running"
    return ToolResult(status="ok", data={"user_response": response})
```

The `/api/analyze/{id}/respond` endpoint sets `session.user_input_response` and calls `session.user_input_event.set()`.

### 6.6 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 6.7 Tests — `tests/test_api.py`

| Test | Description |
|------|-------------|
| `test_start_analysis` | POST /api/analyze → returns analysisId + streamUrl |
| `test_stream_events` | Start analysis → SSE stream produces events |
| `test_steer` | POST /api/steer during running analysis → message injected |
| `test_respond_to_input` | Trigger request_user_input → POST /respond → tool unblocks |
| `test_respond_timeout` | request_user_input with no response → timeout error |
| `test_memory_list` | GET /api/memory → correct directory tree |
| `test_memory_read` | GET /api/memory/companies/NVDA.md → file content |
| `test_memory_write` | PUT /api/memory/companies/NVDA.md → file updated |
| `test_memory_read_nonexistent` | GET nonexistent file → 404 |
| `test_watchlist_empty` | No company files → empty list |
| `test_watchlist_parses_md` | Company .md with Key Numbers → parsed correctly |
| `test_calibration_endpoint` | GET /api/calibration?company=NVDA → CalibrationResponse |
| `test_sse_bridge_tool_start` | TOOL_START event → correct SSE format |
| `test_sse_bridge_tool_end` | TOOL_END event → correct SSE format |
| `test_sse_bridge_text_delta` | TEXT_DELTA event → correct SSE format |
| `test_sse_bridge_complete` | Harness returns → complete event with reply |
| `test_sse_bridge_truncates_large_results` | >10KB result → truncated in SSE |
| `test_memory_delete` | DELETE /api/memory/companies/NVDA.md → file removed |
| `test_memory_delete_nonexistent` | DELETE nonexistent file → 404 |
| `test_watchlist_stale_alert` | Company with analysis > 30 days ago → stale_analysis alert |
| `test_watchlist_kill_triggered_alert` | Company md with `[x]` kill criterion → kill_triggered alert |
| `test_sse_bridge_steering_injected` | STEERING_INJECTED event → steering SSE type |
| `test_sse_bridge_loop_detected` | LOOP_DETECTED event → system SSE type |
| `test_session_cleanup` | Inactive session → cleaned up after timeout |

---

## 7. Step 2D: Next.js Frontend (Agent D, parallel)

### 7.1 Project Setup

```
iris-frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   ├── components/             # React components (~28 files)
│   ├── hooks/                  # Custom hooks (3 files)
│   ├── utils/                  # Utilities (3 files)
│   └── types/                  # TypeScript type definitions (3 files)
├── tailwind.config.ts
├── next.config.ts
├── package.json
└── tsconfig.json
```

Dependencies:
- `next`, `react`, `react-dom`
- `zustand` (state management)
- `recharts` (scatter chart)
- `react-markdown` (memory viewer)
- `tailwindcss`, `@tailwindcss/typography`

### 7.2 Page: Home (`/`)

**Components:**
- `SearchBar` — full-width input + "Analyze" button → navigates to `/analysis/new?q={query}`
- `WatchlistGrid` — fetches `GET /api/watchlist`, renders `WatchlistCard` grid
- `WatchlistCard` — ticker, gap% badge (green/red), fair value, market price, last date, thesis status, alerts
- `RecentAnalysisList` — fetches calibration log, renders list of recent analyses

**Empty state:** "还没有追踪任何公司。在上方输入 ticker 开始你的第一次分析。"

**Interactions:**
- Click WatchlistCard → `/analysis/new?ticker=TICKER&mode=update`
- Click RecentAnalysis row → `/analysis/{id}`

### 7.3 Page: Analysis Workspace (`/analysis/[id]`)

**State machine:** `IDLE → RUNNING → COMPLETE` (may pass through `WAITING`)

**Layout:** Left 45% | Right 55%, fixed split.

**Left Panel components:**
- `StreamingTimeline` — scrollable event list, auto-scroll to bottom
  - `TimelineItem` — colored dot (🟢search 🔵analyze 🟠model ⚪system 🟣user) + semantic text + expandable detail
- `AIReasoningArea` — 80-120px fixed height, streams `text_delta` content, light gray bg
- `SteeringInput` — always visible input, state-dependent placeholder/style
  - `PendingQuestionCard` — shown above input during WAITING state, blue bg, option buttons
- `PhaseIndicator` — 24px progress bar: gather → analyze → evaluate → finalize

**Right Panel components:**
- `PanelTabBar` — 4 tabs: Data | Model | Comps | Memory
- Auto-switch logic: switch to relevant tab on new data, unless user manually switched in last 5s

**Data Tab:**
- `MetricCardGrid` — 2x3 grid of key metrics (13px label, 24px value, change badge)
- `FinancialTable` — collapsible income/balance/cashflow tables
- Macro data section (rates, CPI if available)
- Populates on `fmp_get_financials` / `fred_get_macro` tool_end

**Model Tab:**
- `FairValueCard` — large fair value, gap% badge, round history dots (clickable)
- `AssumptionList` — each assumption one row, expandable reasoning
- `ImpliedMultiples` — 4 MetricCards horizontal: P/E, EV/EBITDA, FCF Yield, PEG
- `SensitivityHeatmap` — HTML table, green-yellow-red gradient cells, current assumption highlighted, hover tooltip
- `YearByYearTable` — collapsible: Year | Revenue | FCF | Discounted FCF + Terminal Value row
- Populates on `build_dcf` tool_end, round selector for multiple rounds

**Comps Tab:**
- `PeerComparisonTable` — target row bold, above-median amber, below-median blue, median row
- `CompsScatter` — Recharts scatter, X=Revenue Growth, Y=Fwd P/E, target=large highlighted dot
- Alert when implied P/E vs median > 50%
- Populates on `get_comps` tool_end

**Memory Tab:**
- `CalibrationSummary` — historical prediction errors + pattern warning
- `LastAnalysisSummary` — previous fair value, thesis, kill criteria checklist, past mistakes
- `SectorMemorySummary` — sector knowledge digest
- Populates on `recall_memory` tool_end
- Empty: "首次分析此公司，无历史记忆。分析完成后将自动创建。"

**Completion behavior:**
- Timeline preserved, reasoning shows full reply, all phases green, Model tab active, no page redirect

### 7.4 Page: Memory Manager (`/memory`)

**Layout:** Left sidebar (file tree) | Right main (file viewer)

**Components:**
- `MemoryFileTree` — directories: companies/sectors/patterns/calibration, files alphabetical, click to select
- `MemoryFileViewer`:
  - Render mode (default): react-markdown HTML
  - Raw mode: monospace text
  - Edit mode: textarea, Save button → PUT to backend
  - calibration/log.jsonl: special handling → `CalibrationTable` (parsed JSONL → table, filter by company)
- "Run Update Analysis" button in company files → `/analysis/new?ticker=TICKER&mode=update`

### 7.5 State Management — Zustand Store

```typescript
interface AnalysisStore {
  // Page state
  pageState: "IDLE" | "RUNNING" | "WAITING" | "COMPLETE";
  analysisId: string | null;

  // Left panel
  timeline: TimelineEvent[];
  reasoningText: string;
  currentPhase: string;
  pendingQuestion: {question: string, context: string, options: string[]} | null;

  // Right panel
  activeTab: "data" | "model" | "comps" | "memory";
  lastUserTabSwitch: number;
  dataPanel: DataPanelState;
  modelPanel: ModelPanelState;
  compsPanel: CompsPanelState;
  memoryPanel: MemoryPanelState;

  // Actions
  startAnalysis: (query: string, contextDocs?: string[]) => Promise<void>;
  sendSteering: (message: string) => Promise<void>;
  respondToInput: (response: string) => Promise<void>;
  setActiveTab: (tab: PanelTab) => void;
  appendTimelineEvent: (event: TimelineEvent) => void;
  handleSSEEvent: (event: SSEEvent) => void;
}
```

### 7.6 SSE Hook — `useAnalysisStream`

```typescript
function useAnalysisStream(analysisId: string | null) {
  // EventSource connection to /api/analyze/{id}/stream
  // onmessage → parse JSON → handleSSEEvent()
  // onerror → exponential backoff reconnect (max 5 attempts)
  // cleanup on unmount
}
```

`handleSSEEvent()` dispatches to:
1. Always: append to timeline via `eventTranslator`
2. By tool name: update right panel state (fmp→data, build_dcf→model, get_comps→comps, recall_memory→memory)
3. text_delta → append to reasoningText
4. phase_change → update currentPhase
5. user_input_needed → set WAITING + pendingQuestion
6. complete → set COMPLETE + finalReply

### 7.7 Event Translator — `eventTranslator.ts`

Full mapping from UI spec section 10:

| tool_start tool | Timeline message |
|---|---|
| exa_search | 搜索: "{query}" |
| web_fetch | 阅读: {hostname} |
| fmp_get_financials | 拉取 {ticker} {statement_type} 数据 |
| fred_get_macro | 拉取宏观数据: {series_id} |
| recall_memory | 回忆 {company} 历史分析 |
| save_memory | 保存分析记忆 |
| build_dcf | 构建 DCF 模型 |
| get_comps | 对比同行: {peers} |
| extract_observation | 提取观察: {claim preview} |
| create_hypothesis | 创建投资假说: {company} |
| add_evidence_card | 评估证据 |
| memory_search | 搜索相关记忆: {query preview} |
| request_user_input | 向用户提问: {question preview} |

tool_end summaries (status="ok"):

| tool_end tool | Summary message |
|---|---|
| exa_search | 找到 {N} 篇相关文章 |
| web_fetch | 提取到 {char_count} 字符 |
| fmp_get_financials | {ticker} 数据就绪 |
| fred_get_macro | {series_id} 数据就绪 ({N} 条记录) |
| recall_memory | 找到历史记录 / 无历史记录 |
| save_memory | 记忆已更新 |
| build_dcf | Fair Value: ${value}/share |
| get_comps | Comps 对比完成 |
| extract_observation | 观察已提取 |
| create_hypothesis | 假说已创建 (confidence: {N}%) |
| add_evidence_card | 证据已评估 ({direction}) |
| memory_search | 找到 {N} 条相关记录 |

**Phase inference from tool names** (used by PhaseIndicator, NOT from harness events):

```typescript
const TOOL_PHASE_MAP: Record<string, string> = {
  recall_memory: "gather", exa_search: "gather", web_fetch: "gather",
  fmp_get_financials: "gather", fred_get_macro: "gather", memory_search: "gather",
  extract_observation: "analyze", create_hypothesis: "analyze", add_evidence_card: "analyze",
  build_dcf: "evaluate", get_comps: "evaluate",
  save_memory: "finalize",
};
// PhaseIndicator advances to max(current, TOOL_PHASE_MAP[tool]) on each tool_start
```

Color coding:
- 🟢 green: search, fetch, fmp, fred, recall_memory
- 🔵 blue: extract_observation, create_hypothesis, add_evidence_card
- 🟠 amber: build_dcf, get_comps
- ⚪ gray: save_memory, phase_change
- 🟣 purple: steering, request_user_input

### 7.8 Visual Design

Per UI spec section 11:
- Fonts: Inter (sans), JetBrains Mono (mono)
- Colors: CSS custom properties for gap, phase, event, status colors
- Dark mode: Tailwind `dark:` variants for all colors
- Border radius: 4/8/12px scale
- Shadows: hover/focus only

### 7.9 Responsive Design

Per UI spec section 12:
- Desktop (≥1024px): left/right split
- Tablet (768-1023px): compact split
- Mobile (<768px): bottom tab switch Timeline | Panels, steering input fixed at bottom

### 7.10 Error Handling

Per UI spec section 13:
- SSE disconnect: toast + auto-reconnect (exponential backoff, max 5)
- Analysis error (ok: false): red error in timeline, error in reasoning area, panel data preserved
- Tool error: ✗ in timeline, no panel impact

### 7.11 Tests — Frontend

| Test file | Tests |
|---|---|
| `eventTranslator.test.ts` | All tool_start translations, all tool_end translations, unknown tool fallback |
| `useAnalysisStore.test.ts` | State transitions (IDLE→RUNNING→COMPLETE, RUNNING→WAITING→RUNNING), tab auto-switch, 5s user override |
| `components/TimelineItem.test.tsx` | Renders correct icon/color per event type, expandable detail |
| `components/SteeringInput.test.tsx` | Disabled in IDLE, enabled in RUNNING, highlighted in WAITING, placeholder changes |
| `components/ModelPanel.test.tsx` | Renders fair value card, assumptions, multiples, sensitivity heatmap, round selector |
| `components/CompsPanel.test.tsx` | Renders peer table with correct formatting, scatter chart, alert threshold |
| `components/MemoryPanel.test.tsx` | Renders calibration summary, empty state message |
| `components/WatchlistCard.test.tsx` | Renders gap% color, alerts badge, click navigation |
| `components/SensitivityHeatmap.test.tsx` | Correct cell colors, current assumption highlighted |
| `pages/analysis.test.tsx` | Full page render, SSE mock → panels populate |
| `pages/home.test.tsx` | Search bar submit, watchlist render, empty state |
| `pages/memory.test.tsx` | File tree navigation, markdown render, edit mode |

---

## 8. Step 3: Integration

### 8.1 Merge Order

1. Merge backend core refactoring (Step 1) — modifies existing files
2. Copy in DCF Skill (Agent A output) — new `skills/dcf/` directory
3. Copy in Memory system (Agent B output) — new `tools/memory.py` + `memory/` directory
4. Copy in FastAPI layer (Agent C output) — new `backend/` directory
5. Frontend (Agent D output) is already separate in `iris-frontend/`

### 8.2 Integration Wiring

After merge, wire together:
- `main.py` imports memory tools from `tools/memory.py`
- `main.py` uses `load_skills("./skills")` which picks up `skills/dcf/` and `skills/hypothesis/`
- `backend/api.py` imports `build_harness` from `main.py`
- `backend/user_input_tool.py` registered as a tool in the harness (via api.py, not via skills)
- Frontend `next.config.ts` proxies `/api/*` to FastAPI backend during development
- `iris_config.yaml` has `harness.always_exposed_tools` updated to include memory tools

### 8.3 End-to-End Test

`tests/test_e2e_fullstack.py`:

1. Start FastAPI server programmatically
2. POST /api/analyze with "分析 NVDA"
3. Connect to SSE stream
4. Assert events arrive in expected order:
   - tool_start/tool_end for recall_memory
   - tool_start/tool_end for exa_search / fmp_get_financials
   - tool_start/tool_end for build_dcf
   - tool_start/tool_end for get_comps
   - tool_start/tool_end for save_memory
   - complete event with ok=true
5. GET /api/memory/companies/NVDA.md → file exists with content
6. GET /api/watchlist → contains NVDA entry
7. GET /api/calibration?company=NVDA → has prediction entry

This test uses mocked LLM responses to ensure deterministic behavior.

### 8.4 Integration Tests

| Test | Description |
|------|-------------|
| `test_skill_loader_discovers_dcf` | load_skills finds skills/dcf and registers build_dcf + get_comps |
| `test_skill_loader_discovers_hypothesis` | load_skills finds skills/hypothesis and registers 5 tools |
| `test_skill_loader_loads_skill_md` | SKILL.md content appears in returned soul text |
| `test_skill_loader_loads_config` | skill config accessible via get_skill_config() |
| `test_harness_with_skills` | Build harness with loaded skills → all tools in registry |
| `test_memory_tools_in_harness` | recall_memory / save_memory / check_calibration work in harness context |
| `test_analysis_creates_memory` | Full analysis run → memory/companies/ file created |
| `test_analysis_updates_calibration` | Full analysis run → prediction_log.jsonl has entry |

---

## 9. Dependency Management

### Python (iris/pyproject.toml additions)

```toml
[project.dependencies]
# Existing: openai, pydantic, pyyaml, httpx, python-dotenv
# New:
fastapi = ">=0.110"
uvicorn = {version = ">=0.27", extras = ["standard"]}
sse-starlette = ">=2.0"

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",  # for TestClient
]
```

### Node.js (iris-frontend/package.json)

```json
{
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "react-dom": "^19",
    "zustand": "^5",
    "recharts": "^2",
    "react-markdown": "^9"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/react": "^19",
    "tailwindcss": "^4",
    "@tailwindcss/typography": "^0.5",
    "vitest": "^2",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6"
  }
}
```

---

## 10. Running the System

### Development

```bash
# Terminal 1: FastAPI backend
cd iris && uvicorn backend.api:app --reload --port 8000

# Terminal 2: Next.js frontend
cd iris-frontend && npm run dev  # port 3000, proxies /api to :8000
```

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
EXA_API_KEY=...
FMP_API_KEY=...
FRED_API_KEY=...

# Optional
OPENAI_MODEL=gpt-4o          # default
OPENAI_BASE_URL=...           # for proxy
EMBEDDING_MODEL=text-embedding-3-small
IRIS_DB_PATH=./iris.db
```

---

## 11. Design Decisions Record

| Decision | Choice | Rationale |
|---|---|---|
| Execution strategy | Backend serial → 4 agents parallel → integrate | Shared files must be serial; new files can parallel safely |
| Guards removal | Inline validation into each tool function | Simpler, no cross-cutting concerns, each tool self-contained |
| ToolHooks | Keep DefaultToolHooks for arg normalization | Still useful for string stripping and error tagging |
| run_valuation removed | Replaced by build_dcf | DCF engine does real math; old tool was just passthrough |
| compute_trade_score removed | Eliminated | Scoring logic was tightly coupled to old pipeline; memory system replaces its purpose |
| write_audit_trail removed | Implicit in memory | save_memory captures analysis conclusions; audit is the memory file itself |
| DCF revision history | Module-level state per harness run | Simple; resets each analysis; no persistence needed beyond memory |
| Memory file format | Markdown (companies/sectors/patterns) + JSONL (calibration) | Human-readable, hand-editable, git-friendly |
| Session storage | In-memory dict | MVP; production would use Redis or similar |
| request_user_input blocking | threading.Event | Harness runs in thread; Event.wait() blocks tool without blocking FastAPI |
| Frontend state | Zustand | Lighter than Redux, sufficient for this scale |
| Charts | Recharts (scatter) + HTML table (heatmap) | Minimal dependencies; heatmap doesn't need a chart library |
| Tab auto-switch | 5-second user override window | Balance automation with respect for user intent |
