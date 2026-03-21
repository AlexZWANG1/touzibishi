# Fundamentals Skill Design

## Summary

Merge deep_research methodology + lightweight research UI into a single `fundamentals` skill. Drop hypothesis/evidence_card from analysis mode. Add one `emit_research_section` tool as a UI data channel, and a new `FundamentalsPanel` frontend component.

## Scope

**Do:**
- Create `iris/skills/fundamentals/` with SKILL.md (deep_research methodology), tools.py (one emit tool), config.yaml
- Add `FundamentalsPanel` component to frontend
- Add "研究" tab to PanelTabBar
- Wire `emit_research_section` tool_end events to fundamentalsPanel store
- Update `iris_config.yaml` modes.analysis.skills to include `fundamentals`

**Don't:**
- Don't touch hypothesis skill directory (leave as-is for future learning mode)
- Don't modify valuation/trading/dcf skills
- Don't modify existing Data/Model/Comps/Strategy panels
- Don't change learning mode

## Backend

### New skill: `iris/skills/fundamentals/`

**SKILL.md** — User's deep_research methodology verbatim (research philosophy, 6-step framework, information processing rules, output standards). Appended with a short section instructing Agent to use `emit_research_section` to push completed sections to the UI.

**tools.py** — One tool:

```python
emit_research_section(title: str, content: str) -> ToolResult
```

- `title`: free-form string, AI decides (e.g. "生意本质", "技术拆解与产品分析", "竞争格局")
- `content`: markdown string, the research output for that section
- Implementation: zero logic, returns `ToolResult.ok({"title": title, "content": content})`
- Registered via `register(context)` returning `[Tool(emit_research_section, SCHEMA)]`

**config.yaml** — Minimal:

```yaml
name: fundamentals
version: "0.1"
default_language: "zh-CN"
```

### Config change: `iris_config.yaml`

In `modes.analysis.skills`, add `fundamentals`. Keep existing skills as-is.

## Frontend

### New type: `FundamentalsPanelState`

In `src/types/analysis.ts`:

```ts
interface ResearchSection {
  title: string;
  content: string;
  timestamp: number;
}

interface FundamentalsPanelState {
  sections: ResearchSection[];
  loading: boolean;
}
```

### Store changes: `useAnalysisStore.ts`

- Add `fundamentalsPanel: FundamentalsPanelState` to store
- Add initial state: `{ sections: [], loading: false }`
- In `_extractPanelData`, add case for `"emit_research_section"`: append `{title, content, timestamp}` to `fundamentalsPanel.sections`
- In `reset()` and `loadSnapshot()`, handle `fundamentalsPanel`

### New component: `FundamentalsPanel.tsx`

- Left sidebar: section list (titles), clickable, highlights active
- Right area: renders selected section's markdown content
- Sections appear incrementally as Agent emits them
- Empty state: "研究进行中..." or "等待研究产出..."
- Uses existing markdown rendering approach from ChatPanel

### Tab bar change: `PanelTabBar.tsx`

- Add `{ key: "fundamentals", label: "研究" }` tab after "对话"
- ActiveTab type extended with `"fundamentals"`
- Count = `fundamentalsPanel.sections.length`

### Analysis page change: `analysis/[id]/page.tsx`

- Import and render `FundamentalsPanel` when `activeTab === "fundamentals"`
- Add `fundamentals` to `tabsWithData` check

## Data Flow

```
Agent follows SKILL.md methodology
  → Completes a research section
  → Calls emit_research_section(title="...", content="...")
  → Backend returns ToolResult.ok({title, content})
  → SSE tool_end event: {tool: "emit_research_section", result: {title, content}}
  → Frontend _extractPanelData matches "emit_research_section"
  → Appends to fundamentalsPanel.sections
  → FundamentalsPanel renders new section
  → "研究" tab badge count increments
```
