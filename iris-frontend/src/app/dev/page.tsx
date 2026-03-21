"use client";

import { useEffect, useState, useCallback } from "react";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
function api(path: string) { return BASE_URL ? `${BASE_URL}${path}` : path; }

// ─── Types ───────────────────────────────────────────────────
interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, { type?: string; description?: string; enum?: string[] }>;
  required: string[];
}

interface SkillInfo {
  name: string;
  prompt: string;
  has_tools: boolean;
  tool_functions?: string[];
  schemas?: string[];
}

interface SoulFile {
  name: string;
  content: string;
  size: number;
}

interface SystemStats {
  db_size_mb: number;
  knowledge_docs: number;
  memory_files: number;
  analysis_runs: number;
  active_sessions: number;
  config_path: string;
}

interface SessionInfo {
  id: string;
  query: string;
  status: string;
  turn_count: number;
  last_activity: string | null;
  timeline_count: number;
}

type Tab = "overview" | "tools" | "skills" | "prompts" | "config";

// ─── Component ───────────────────────────────────────────────
export default function DevPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [soulFiles, setSoulFiles] = useState<SoulFile[]>([]);
  const [config, setConfig] = useState<string>("");
  const [configDirty, setConfigDirty] = useState(false);
  const [editingSoul, setEditingSoul] = useState<string | null>(null);
  const [soulDraft, setSoulDraft] = useState("");
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }, []);

  // ── Fetch helpers ─────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    try {
      const [statsRes, sessRes] = await Promise.all([
        fetch(api("/api/dev/stats")),
        fetch(api("/api/dev/sessions")),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (sessRes.ok) {
        const data = await sessRes.json();
        setSessions(data.sessions || []);
      }
    } catch { /* ignore */ }
  }, []);

  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(api("/api/dev/tools"));
      if (res.ok) {
        const data = await res.json();
        setTools(data.tools || []);
      }
    } catch { /* ignore */ }
  }, []);

  const fetchSkills = useCallback(async () => {
    try {
      const res = await fetch(api("/api/dev/skills"));
      if (res.ok) {
        const data = await res.json();
        setSkills(data.skills || []);
      }
    } catch { /* ignore */ }
  }, []);

  const fetchSoul = useCallback(async () => {
    try {
      const res = await fetch(api("/api/dev/soul"));
      if (res.ok) {
        const data = await res.json();
        setSoulFiles(data.files || []);
      }
    } catch { /* ignore */ }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(api("/api/dev/config"));
      if (res.ok) {
        const data = await res.json();
        // Convert JSON config to YAML-like display
        setConfig(JSON.stringify(data, null, 2));
        setConfigDirty(false);
      }
    } catch { /* ignore */ }
  }, []);

  // ── Load on tab change ────────────────────────────────────
  useEffect(() => {
    if (tab === "overview") fetchStats();
    else if (tab === "tools") fetchTools();
    else if (tab === "skills") fetchSkills();
    else if (tab === "prompts") fetchSoul();
    else if (tab === "config") fetchConfig();
  }, [tab, fetchStats, fetchTools, fetchSkills, fetchSoul, fetchConfig]);

  // ── Save handlers ─────────────────────────────────────────
  const saveSoulFile = async (filename: string, content: string) => {
    setSaving(true);
    try {
      const res = await fetch(api(`/api/dev/soul/${filename}`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        showToast(`${filename} saved`);
        setEditingSoul(null);
        fetchSoul();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`Error: ${err.detail || "Save failed"}`);
      }
    } catch { showToast("Network error"); }
    setSaving(false);
  };

  // ── Tabs ──────────────────────────────────────────────────
  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "overview", label: "Overview", icon: "SYS" },
    { key: "tools", label: "Tools", icon: "FN" },
    { key: "skills", label: "Skills", icon: "SK" },
    { key: "prompts", label: "Prompts", icon: "PM" },
    { key: "config", label: "Config", icon: "CF" },
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="shrink-0 flex items-center justify-between px-4 h-10 border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] font-bold tracking-[0.15em] text-[var(--iris-accent)]">
            DEV PANEL
          </span>
          <span className="text-[10px] text-[var(--iris-text-muted)] font-mono">
            IRIS System Inspector
          </span>
        </div>
        {stats && (
          <div className="flex items-center gap-4 text-[10px] font-mono text-[var(--iris-text-muted)]">
            <span>DB {stats.db_size_mb}MB</span>
            <span>{stats.knowledge_docs} docs</span>
            <span>{stats.analysis_runs} runs</span>
            <span className={stats.active_sessions > 0 ? "text-[var(--iris-green)]" : ""}>
              {stats.active_sessions} live
            </span>
          </div>
        )}
      </div>

      {/* ── Tab Bar ── */}
      <div className="shrink-0 flex items-center gap-0 px-2 h-8 border-b border-[var(--iris-border)] bg-[var(--iris-bg)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3 h-full text-[11px] font-mono tracking-wide transition-colors border-b-2 ${
              tab === t.key
                ? "border-[var(--iris-accent)] text-[var(--iris-accent)]"
                : "border-transparent text-[var(--iris-text-muted)] hover:text-[var(--iris-text-secondary)]"
            }`}
          >
            <span className="text-[9px] font-bold opacity-60">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Toast */}
        {toast && (
          <div className="fixed top-12 right-4 z-50 bg-[var(--iris-surface)] border border-[var(--iris-accent)] text-[var(--iris-accent)] text-xs font-mono px-3 py-1.5 fade-in">
            {toast}
          </div>
        )}

        {tab === "overview" && <OverviewTab stats={stats} sessions={sessions} onRefresh={fetchStats} />}
        {tab === "tools" && <ToolsTab tools={tools} expanded={expandedTool} onToggle={setExpandedTool} />}
        {tab === "skills" && <SkillsTab skills={skills} expanded={expandedSkill} onToggle={setExpandedSkill} />}
        {tab === "prompts" && (
          <PromptsTab
            files={soulFiles}
            editingFile={editingSoul}
            draft={soulDraft}
            saving={saving}
            onEdit={(name, content) => { setEditingSoul(name); setSoulDraft(content); }}
            onCancel={() => setEditingSoul(null)}
            onDraftChange={setSoulDraft}
            onSave={saveSoulFile}
          />
        )}
        {tab === "config" && (
          <ConfigTab
            config={config}
            dirty={configDirty}
            onChange={(v) => { setConfig(v); setConfigDirty(true); }}
          />
        )}
      </div>
    </div>
  );
}

// ─── Overview Tab ────────────────────────────────────────────
function OverviewTab({
  stats,
  sessions,
  onRefresh,
}: {
  stats: SystemStats | null;
  sessions: SessionInfo[];
  onRefresh: () => void;
}) {
  if (!stats) return <div className="text-xs text-[var(--iris-text-muted)] font-mono">Loading...</div>;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Stat Cards */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: "DB Size", value: `${stats.db_size_mb} MB`, color: "" },
          { label: "Knowledge Docs", value: String(stats.knowledge_docs), color: "text-[var(--iris-data)]" },
          { label: "Memory Files", value: String(stats.memory_files), color: "text-[var(--iris-blue)]" },
          { label: "Analysis Runs", value: String(stats.analysis_runs), color: "text-[var(--iris-amber)]" },
          { label: "Active Sessions", value: String(stats.active_sessions), color: stats.active_sessions > 0 ? "text-[var(--iris-green)]" : "" },
        ].map((s) => (
          <div key={s.label} className="border border-[var(--iris-border)] bg-[var(--iris-surface)] p-3">
            <div className="text-[10px] font-mono text-[var(--iris-text-muted)] uppercase tracking-wider mb-1">{s.label}</div>
            <div className={`text-lg font-mono font-bold ${s.color || "text-[var(--iris-text)]"}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Architecture Diagram */}
      <div className="border border-[var(--iris-border)] bg-[var(--iris-surface)] p-4">
        <div className="text-[10px] font-mono text-[var(--iris-accent)] uppercase tracking-wider mb-3">System Architecture</div>
        <div className="font-mono text-[11px] text-[var(--iris-text-secondary)] leading-relaxed whitespace-pre">{`
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                     │
│  ┌──────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────┐  │
│  │ Home │ │ Analysis │ │Knowledge│ │Memory│ │  Dev   │  │
│  └──┬───┘ └────┬─────┘ └───┬────┘ └──┬───┘ └───┬────┘  │
├─────┼──────────┼───────────┼─────────┼─────────┼────────┤
│  SSE│     REST │      REST │    REST │    REST │        │
├─────┼──────────┼───────────┼─────────┼─────────┼────────┤
│  Backend (FastAPI)                                       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Harness (Agent Loop)                   │ │
│  │  ┌──────┐ ┌────────┐ ┌──────┐ ┌──────────────────┐ │ │
│  │  │Budget│ │  Loop  │ │Context│ │   LLM Client     │ │ │
│  │  │Track │ │Detector│ │Compact│ │  (OpenAI API)    │ │ │
│  │  └──────┘ └────────┘ └──────┘ └──────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌──────────────────┐  ┌───────────────────────────────┐ │
│  │     Tools (12)    │  │       Skills (4)              │ │
│  │ search·financials │  │ DCF·Valuation·Hypothesis·     │ │
│  │ market·retrieval  │  │ Trading                       │ │
│  │ knowledge·memory  │  │ (SKILL.md + tools.py)         │ │
│  └────────┬─────────┘  └──────────────────────────────┘ │
│  ┌────────┴─────────┐  ┌───────────────────────────────┐ │
│  │    Soul (Prompt)  │  │        Config (YAML)          │ │
│  │ role·v0.1·check   │  │ harness·budget·loop·modes     │ │
│  │ steering·reflect  │  │ knowledge·skills·memory       │ │
│  └──────────────────┘  └───────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │               SQLite (iris.db)                      │ │
│  │  analysis_runs · knowledge_documents · memory       │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘`}
        </div>
      </div>

      {/* Active Sessions */}
      {sessions.length > 0 && (
        <div className="border border-[var(--iris-border)] bg-[var(--iris-surface)] p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono text-[var(--iris-accent)] uppercase tracking-wider">
              Active Sessions ({sessions.length})
            </span>
            <button onClick={onRefresh} className="text-[10px] font-mono text-[var(--iris-text-muted)] hover:text-[var(--iris-accent)]">
              refresh
            </button>
          </div>
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr>
                <th className="text-left p-1 text-[var(--iris-accent)]">ID</th>
                <th className="text-left p-1 text-[var(--iris-accent)]">Query</th>
                <th className="text-left p-1 text-[var(--iris-accent)]">Status</th>
                <th className="text-right p-1 text-[var(--iris-accent)]">Turns</th>
                <th className="text-right p-1 text-[var(--iris-accent)]">Events</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-t border-[var(--iris-border)]">
                  <td className="p-1 text-[var(--iris-data)]">{s.id.slice(0, 8)}</td>
                  <td className="p-1 text-[var(--iris-text-secondary)] truncate max-w-[300px]">{s.query}</td>
                  <td className="p-1">
                    <span className={`px-1.5 py-0.5 text-[10px] ${
                      s.status === "running" ? "text-[var(--iris-green)]" :
                      s.status === "error" ? "text-[var(--iris-red)]" :
                      "text-[var(--iris-text-muted)]"
                    }`}>{s.status}</span>
                  </td>
                  <td className="p-1 text-right text-[var(--iris-text-secondary)]">{s.turn_count}</td>
                  <td className="p-1 text-right text-[var(--iris-text-secondary)]">{s.timeline_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Tools Tab ───────────────────────────────────────────────
function ToolsTab({
  tools,
  expanded,
  onToggle,
}: {
  tools: ToolInfo[];
  expanded: string | null;
  onToggle: (name: string | null) => void;
}) {
  if (!tools.length) return <div className="text-xs text-[var(--iris-text-muted)] font-mono">Loading tools...</div>;

  // Group tools by category
  const categories: Record<string, ToolInfo[]> = {};
  for (const t of tools) {
    let cat = "other";
    if (["exa_search", "web_fetch"].includes(t.name)) cat = "search";
    else if (["financials", "macro"].includes(t.name)) cat = "data";
    else if (["quote", "history"].includes(t.name)) cat = "market";
    else if (["remember", "recall", "search_knowledge"].includes(t.name)) cat = "memory";
    else if (["valuation", "build_dcf", "get_comps"].includes(t.name)) cat = "valuation";
    else if (["create_hypothesis", "add_evidence_card"].includes(t.name)) cat = "hypothesis";
    else if (["generate_trade_signal", "get_portfolio"].includes(t.name)) cat = "trading";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(t);
  }

  const catLabels: Record<string, string> = {
    search: "Search & Web",
    data: "Financial Data",
    market: "Market Data",
    memory: "Memory & Knowledge",
    valuation: "Valuation Models",
    hypothesis: "Hypothesis Engine",
    trading: "Trading Signals",
    other: "Other",
  };

  const catOrder = ["search", "data", "market", "memory", "valuation", "hypothesis", "trading", "other"];

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="text-[10px] font-mono text-[var(--iris-text-muted)]">
        {tools.length} tools registered
      </div>
      {catOrder.filter((c) => categories[c]?.length).map((cat) => (
        <div key={cat}>
          <div className="text-[10px] font-mono text-[var(--iris-accent)] uppercase tracking-wider mb-2">
            {catLabels[cat] || cat}
          </div>
          <div className="space-y-1">
            {categories[cat].map((t) => (
              <div key={t.name} className="border border-[var(--iris-border)] bg-[var(--iris-surface)]">
                <button
                  onClick={() => onToggle(expanded === t.name ? null : t.name)}
                  className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-[var(--iris-surface-hover)] transition-colors"
                >
                  <span className="text-[9px] font-mono text-[var(--iris-accent)] opacity-60">
                    {expanded === t.name ? "▼" : "▶"}
                  </span>
                  <span className="text-[12px] font-mono font-semibold text-[var(--iris-data)]">{t.name}</span>
                  <span className="text-[11px] text-[var(--iris-text-muted)] flex-1 truncate">{t.description?.slice(0, 80)}</span>
                  <span className="text-[10px] font-mono text-[var(--iris-text-muted)]">
                    {Object.keys(t.parameters).length} params
                  </span>
                </button>
                {expanded === t.name && (
                  <div className="px-4 pb-3 border-t border-[var(--iris-border)]">
                    <div className="text-[11px] text-[var(--iris-text-secondary)] mt-2 mb-3">{t.description}</div>
                    {Object.keys(t.parameters).length > 0 && (
                      <table className="w-full text-[11px] font-mono">
                        <thead>
                          <tr>
                            <th className="text-left p-1 text-[var(--iris-accent)] text-[10px]">Param</th>
                            <th className="text-left p-1 text-[var(--iris-accent)] text-[10px]">Type</th>
                            <th className="text-left p-1 text-[var(--iris-accent)] text-[10px]">Required</th>
                            <th className="text-left p-1 text-[var(--iris-accent)] text-[10px]">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(t.parameters).map(([pname, pinfo]) => (
                            <tr key={pname} className="border-t border-[var(--iris-border)]">
                              <td className="p-1 text-[var(--iris-data)]">{pname}</td>
                              <td className="p-1 text-[var(--iris-text-muted)]">
                                {pinfo.type || "any"}
                                {pinfo.enum && <span className="text-[var(--iris-amber)]"> [{pinfo.enum.join("|")}]</span>}
                              </td>
                              <td className="p-1">
                                {t.required.includes(pname) ? (
                                  <span className="text-[var(--iris-accent)]">yes</span>
                                ) : (
                                  <span className="text-[var(--iris-text-muted)]">no</span>
                                )}
                              </td>
                              <td className="p-1 text-[var(--iris-text-secondary)]">{pinfo.description || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Skills Tab ──────────────────────────────────────────────
function SkillsTab({
  skills,
  expanded,
  onToggle,
}: {
  skills: SkillInfo[];
  expanded: string | null;
  onToggle: (name: string | null) => void;
}) {
  if (!skills.length) return <div className="text-xs text-[var(--iris-text-muted)] font-mono">Loading skills...</div>;

  return (
    <div className="space-y-3 max-w-4xl">
      <div className="text-[10px] font-mono text-[var(--iris-text-muted)]">
        {skills.length} skills loaded
      </div>
      {skills.map((s) => (
        <div key={s.name} className="border border-[var(--iris-border)] bg-[var(--iris-surface)]">
          <button
            onClick={() => onToggle(expanded === s.name ? null : s.name)}
            className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-[var(--iris-surface-hover)] transition-colors"
          >
            <span className="text-[9px] font-mono text-[var(--iris-accent)] opacity-60">
              {expanded === s.name ? "▼" : "▶"}
            </span>
            <span className="text-[13px] font-mono font-semibold text-[var(--iris-data)]">{s.name}</span>
            <div className="flex items-center gap-2 ml-auto">
              {s.has_tools && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 bg-[var(--iris-accent-glow)] text-[var(--iris-accent)] border border-[var(--iris-accent-dim)]">
                  {s.tool_functions?.length || 0} tools
                </span>
              )}
              <span className="text-[10px] font-mono text-[var(--iris-text-muted)]">
                SKILL.md {s.prompt ? `(${s.prompt.length} chars)` : "(empty)"}
              </span>
            </div>
          </button>
          {expanded === s.name && (
            <div className="px-4 pb-3 border-t border-[var(--iris-border)] space-y-3">
              {/* Tool functions */}
              {s.tool_functions && s.tool_functions.length > 0 && (
                <div className="mt-2">
                  <div className="text-[10px] font-mono text-[var(--iris-accent)] uppercase tracking-wider mb-1">Tool Functions</div>
                  <div className="flex flex-wrap gap-1.5">
                    {s.tool_functions.map((fn) => (
                      <span key={fn} className="text-[11px] font-mono px-2 py-0.5 bg-[var(--iris-surface-hover)] text-[var(--iris-data)] border border-[var(--iris-border)]">
                        {fn}()
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {/* SKILL.md content */}
              {s.prompt && (
                <div className="mt-2">
                  <div className="text-[10px] font-mono text-[var(--iris-accent)] uppercase tracking-wider mb-1">SKILL.md</div>
                  <pre className="text-[11px] font-mono text-[var(--iris-text-secondary)] bg-[var(--iris-bg)] border border-[var(--iris-border)] p-3 overflow-x-auto whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                    {s.prompt}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Prompts Tab ─────────────────────────────────────────────
function PromptsTab({
  files,
  editingFile,
  draft,
  saving,
  onEdit,
  onCancel,
  onDraftChange,
  onSave,
}: {
  files: SoulFile[];
  editingFile: string | null;
  draft: string;
  saving: boolean;
  onEdit: (name: string, content: string) => void;
  onCancel: () => void;
  onDraftChange: (v: string) => void;
  onSave: (name: string, content: string) => void;
}) {
  if (!files.length) return <div className="text-xs text-[var(--iris-text-muted)] font-mono">Loading prompts...</div>;

  return (
    <div className="space-y-3 max-w-4xl">
      <div className="text-[10px] font-mono text-[var(--iris-text-muted)]">
        {files.length} soul files in soul/ directory
      </div>
      {files.map((f) => (
        <div key={f.name} className="border border-[var(--iris-border)] bg-[var(--iris-surface)]">
          <div className="flex items-center justify-between px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-mono font-semibold text-[var(--iris-data)]">{f.name}</span>
              <span className="text-[10px] font-mono text-[var(--iris-text-muted)]">{f.size}B</span>
            </div>
            {editingFile === f.name ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={onCancel}
                  className="text-[10px] font-mono px-2 py-0.5 text-[var(--iris-text-muted)] hover:text-[var(--iris-text)] border border-[var(--iris-border)]"
                >
                  Cancel
                </button>
                <button
                  onClick={() => onSave(f.name, draft)}
                  disabled={saving}
                  className="text-[10px] font-mono px-2 py-0.5 text-[var(--iris-accent)] hover:bg-[var(--iris-accent-glow)] border border-[var(--iris-accent-dim)] disabled:opacity-50"
                >
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            ) : (
              <button
                onClick={() => onEdit(f.name, f.content)}
                className="text-[10px] font-mono px-2 py-0.5 text-[var(--iris-text-muted)] hover:text-[var(--iris-accent)] border border-[var(--iris-border)]"
              >
                Edit
              </button>
            )}
          </div>
          <div className="px-3 pb-3">
            {editingFile === f.name ? (
              <textarea
                value={draft}
                onChange={(e) => onDraftChange(e.target.value)}
                className="w-full h-[300px] bg-[var(--iris-bg)] border border-[var(--iris-accent-dim)] text-[var(--iris-text-secondary)] font-mono text-[11px] p-3 resize-y focus:outline-none focus:border-[var(--iris-accent)]"
                spellCheck={false}
              />
            ) : (
              <pre className="text-[11px] font-mono text-[var(--iris-text-secondary)] bg-[var(--iris-bg)] border border-[var(--iris-border)] p-3 overflow-x-auto whitespace-pre-wrap max-h-[200px] overflow-y-auto">
                {f.content}
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Config Tab ──────────────────────────────────────────────
function ConfigTab({
  config,
  dirty,
  onChange,
}: {
  config: string;
  dirty: boolean;
  onChange: (v: string) => void;
}) {
  if (!config) return <div className="text-xs text-[var(--iris-text-muted)] font-mono">Loading config...</div>;

  // Parse to show structured view
  let parsed: Record<string, unknown> = {};
  try { parsed = JSON.parse(config); } catch { /* ignore */ }

  const sections = Object.keys(parsed);

  return (
    <div className="space-y-3 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono text-[var(--iris-text-muted)]">
          iris_config.yaml — {sections.length} sections
          {dirty && <span className="text-[var(--iris-amber)] ml-2">(modified)</span>}
        </div>
      </div>

      {/* Structured view */}
      {sections.map((section) => (
        <div key={section} className="border border-[var(--iris-border)] bg-[var(--iris-surface)]">
          <div className="px-3 py-2 text-[11px] font-mono font-semibold text-[var(--iris-accent)]">{section}</div>
          <pre className="px-3 pb-3 text-[11px] font-mono text-[var(--iris-text-secondary)] whitespace-pre-wrap overflow-x-auto max-h-[250px] overflow-y-auto">
            {JSON.stringify(parsed[section], null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}
