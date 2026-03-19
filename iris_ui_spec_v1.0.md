# IRIS UI/Frontend Specification v1.0

> 本文档是 IRIS 前端的完整开发规范。与 `IRIS Development Specification v0.3` 配套使用。
>
> 技术栈：Next.js (App Router) + React + TypeScript + Tailwind CSS
>
> 后端：Python (FastAPI) wrapping existing harness + tools

---

## 1. 设计哲学

### 1.1 核心体验

IRIS 是一个**透明的 AI 研究伙伴**。用户发起一个分析请求，AI 全速自动执行，用户实时观察过程，随时可以介入（steering），最终得到结构化的分析报告。

类比：一个优秀的初级分析师和 PM 的关系——分析师自主完成研究，PM 随时可以看进度、提问、给方向，但不需要每一步都批准。

### 1.2 交互模式

**Full Auto + 随时可 Steer**：
- AI 默认全程自动跑，不暂停
- 所有过程实时 streaming 展示
- 用户随时可以发送 steering 消息介入
- AI 对 steering 采用"建议模式"——会 pushback 但尊重用户最终权威
- AI 在极少数真正不确定的情况下可主动暂停（通过 `request_user_input` tool）

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| 过程透明 | 用户能看到 AI 在搜索什么、发现了什么、为什么修正假设 |
| 渐进填充 | 面板内容随分析推进逐步出现，不需要等全部完成 |
| 对话即控制 | 所有介入都通过自然语言，不需要复杂的 UI 操作 |
| 结构化展示 | 关键输出（数据、模型、对比）用结构化面板，不是纯文字 |
| 记忆可见 | 用户能看到 AI 带了什么历史上下文进入分析 |

---

## 2. 页面架构

### 2.1 页面总览

```
IRIS App
├── /                    → Home (Watchlist + 快速入口)
├── /analysis/:id        → Analysis Workspace (核心工作区)
└── /memory              → Memory Manager (查看/编辑记忆文件)
    ├── /memory/companies/:ticker
    ├── /memory/sectors/:name
    ├── /memory/patterns/:name
    └── /memory/calibration
```

### 2.2 全局导航

顶部导航栏，始终可见：

```
┌──────────────────────────────────────────────────┐
│ IRIS    Home    Analysis    Memory           [?]  │
└──────────────────────────────────────────────────┘
```

- **IRIS** logo/名称，点击回 Home
- **Home** / **Analysis** / **Memory** — 页面切换
- **Analysis** 如果当前有进行中的分析，tab 显示 ticker（如 "Analysis: NVDA"）
- **[?]** — settings/help

导航高度 48px，固定在顶部。

---

## 3. Home 页面 (`/`)

### 3.1 页面结构

```
┌──────────────────────────────────────────────────┐
│ [全局导航]                                        │
├──────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────────────────────────────────┐      │
│  │ 🔍 New analysis: enter ticker or question │      │
│  └──────────────────────────────────────────┘      │
│                                                    │
│  Watchlist                        from memory/     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  NVDA    │  │  AMD     │  │  TSLA    │         │
│  │  +16.3%  │  │  -5.2%   │  │  +22.1%  │         │
│  │  FV $165 │  │  FV $182 │  │  FV $245 │         │
│  │  Mar 18  │  │  Feb 20  │  │  Jan 15  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                    │
│  Recent analyses                                   │
│  ┌──────────────────────────────────────────┐      │
│  │ NVDA  $165 FV (+16.3%)  2026-03-18      │      │
│  │ AMD   $182 FV (-5.2%)   2026-02-20      │      │
│  └──────────────────────────────────────────┘      │
│                                                    │
└──────────────────────────────────────────────────┘
```

### 3.2 组件：SearchBar

全宽搜索栏，Home 页面最顶部（导航下方）。

```typescript
interface SearchBarProps {
  placeholder: string; // "Enter ticker or research question..."
  onSubmit: (query: string) => void; // 导航到 /analysis/new?q=query
}
```

- 输入框 + "Analyze" 按钮
- 回车或点击按钮 → 创建新分析，跳转到 `/analysis/:id`
- 支持 ticker（"NVDA"）和自然语言（"分析 NVDA 在 AI 基础设施赛道的投资机会"）

### 3.3 组件：WatchlistCard

每张卡片对应 `memory/companies/` 里的一个 markdown 文件。

```typescript
interface WatchlistCardProps {
  ticker: string;
  fairValue: number | null;
  marketPrice: number | null;
  gapPercent: number | null;
  lastAnalysisDate: string | null;
  thesisStatus: "bullish" | "neutral" | "bearish" | null;
  alerts: Alert[];  // kill criteria triggered, upcoming earnings, etc.
}

interface Alert {
  type: "kill_triggered" | "earnings_upcoming" | "stale_analysis" | "calibration_warning";
  message: string;
}
```

视觉设计：
- 白色卡片，0.5px border，border-radius 8px
- 左上：ticker (bold, 16px)
- 右上：gap% badge（绿色正值，红色负值）
- 中间：Fair Value | Market Price
- 下面：上次分析日期 | thesis 状态
- 如有 alert：底部显示 alert badge（如 "kill triggered" 红色标签）

交互：
- 点击卡片 → 导航到 `/analysis/new?ticker=TICKER&mode=update`
- 鼠标悬停 → 轻微 elevation 变化

### 3.4 组件：RecentAnalysisList

从 `memory/calibration/prediction_log.jsonl` + 最近分析记录生成的列表。

每行：ticker | fair value | gap% | 分析日期 | tool calls 数量

点击 → 导航到对应分析的 result 视图。

### 3.5 空状态

如果没有任何 memory 文件（首次使用）：
- Watchlist 区域显示："还没有追踪任何公司。在上方输入 ticker 开始你的第一次分析。"
- 不显示 Recent analyses

---

## 4. Analysis Workspace (`/analysis/:id`)

这是 IRIS 最核心的页面。左右分栏布局。

### 4.1 页面状态机

```
┌─────────┐    用户提交查询    ┌────────────┐    harness 完成    ┌───────────┐
│  IDLE   │ ──────────────── │  RUNNING   │ ──────────────── │ COMPLETE  │
└─────────┘                   └────────────┘                   └───────────┘
                                    │                              │
                                    │ request_user_input           │ 用户发起
                                    ▼                              │ "更新分析"
                              ┌────────────┐                       │
                              │  WAITING   │                       │
                              │ (for user) │                       │
                              └────────────┘                       │
                                    │ 用户回复                     │
                                    ▼                              │
                              ┌────────────┐                       │
                              │  RUNNING   │ ◄─────────────────────┘
                              └────────────┘
```

- **IDLE**：初始状态，等待用户输入查询
- **RUNNING**：分析进行中，streaming events
- **WAITING**：AI 通过 `request_user_input` 暂停，等待用户回复
- **COMPLETE**：分析完成，展示最终结果

### 4.2 整体布局

```
┌──────────────────────────────────────────────────┐
│ [全局导航]                                        │
├───────────────────────┬──────────────────────────┤
│                       │                          │
│   左侧面板 (45%)       │   右侧面板 (55%)         │
│   Conversation Flow   │   Structured Panels      │
│                       │                          │
│   ┌─────────────┐     │   ┌────────────────┐     │
│   │ Streaming   │     │   │ Tab: Data      │     │
│   │ Timeline    │     │   │ Tab: Model     │     │
│   │             │     │   │ Tab: Comps     │     │
│   │ (scrollable)│     │   │ Tab: Memory    │     │
│   │             │     │   │                │     │
│   │             │     │   │ (tab content   │     │
│   │             │     │   │  scrollable)   │     │
│   │             │     │   │                │     │
│   └─────────────┘     │   └────────────────┘     │
│                       │                          │
│   ┌─────────────┐     │                          │
│   │ AI 当前思考  │     │                          │
│   │ (streaming)  │     │                          │
│   └─────────────┘     │                          │
│                       │                          │
│   ┌─────────────┐     │                          │
│   │ Steering    │     │                          │
│   │ Input       │     │                          │
│   └─────────────┘     │                          │
│                       │                          │
│   [phase indicator]   │                          │
│                       │                          │
├───────────────────────┴──────────────────────────┤
```

宽度比例：左 45% / 右 55%。不支持拖拽调整（简化实现）。

### 4.3 左侧面板：Conversation Flow

从上到下包含 4 个区域：

#### 4.3.1 Streaming Timeline

占左侧面板大部分高度（flex-grow）。滚动容器，新事件追加到底部，自动滚动到最新。

每个事件是一行，包含：
- 状态图标（彩色圆点或 spinner）
- 语义级描述文字

```typescript
interface TimelineEvent {
  id: string;
  timestamp: number;
  type: "search" | "fetch" | "data" | "extract" | "model" | "comps" | "memory" | "steer" | "system";
  status: "running" | "done" | "error";
  message: string;           // 展示给用户的语义描述
  detail?: string;           // 可展开的详细信息
  toolName?: string;         // 原始 tool name（用于右侧面板联动）
  toolResult?: any;          // 原始 tool result（用于右侧面板数据填充）
}
```

事件展示规则：

| harness EventType | Timeline 展示 |
|-------------------|---------------|
| TOOL_START (exa_search) | 🔍 搜索: "{query}"... |
| TOOL_END (exa_search, ok) | ✓ 找到 {N} 篇相关文章 |
| TOOL_START (web_fetch) | 📖 阅读: {url_domain}... |
| TOOL_END (web_fetch, ok) | ✓ 提取到 {char_count} 字符 |
| TOOL_START (fmp_get_financials) | 📊 拉取 {ticker} 财务数据... |
| TOOL_END (fmp_get_financials, ok) | ✓ {ticker} {statement_type} 数据就绪 |
| TOOL_START (recall_memory) | 🧠 回忆 {company} 历史分析... |
| TOOL_END (recall_memory, ok) | ✓ 找到上次分析记录 / ○ 无历史记录 |
| TOOL_START (build_dcf) | 🧮 构建 DCF 模型 Round {N}... |
| TOOL_END (build_dcf, ok) | ✓ Fair Value: ${value}/share |
| TOOL_START (get_comps) | 📏 对比同行估值... |
| TOOL_END (get_comps, ok) | ✓ Comps: 隐含 P/E {x} vs 中位数 {y} |
| TOOL_START (save_memory) | 💾 保存分析记忆... |
| TOOL_END (save_memory, ok) | ✓ 记忆已更新 |
| TOOL_END (any, error) | ✗ {error_message} |
| PHASE_CHANGE | ── Phase: {from} → {to} ── |
| STEERING_INJECTED | 📝 用户: "{message}" |
| TEXT (AI reasoning between tool calls) | 作为 AI 思考区域的内容显示 |

颜色编码：
- 🟢 绿色圆点 = 信息收集相关 (search, fetch, fmp, fred, recall_memory)
- 🔵 蓝色圆点 = 分析处理相关 (extract_observation, create_hypothesis, add_evidence_card)
- 🟠 琥珀色圆点 = 模型构建相关 (build_dcf, get_comps)
- ⚪ 灰色圆点 = 系统事件 (phase_change, save_memory)
- 🟣 紫色 = 用户 steering

可展开细节：点击事件行 → 展开显示原始 tool arguments 和 result（开发者/高级用户使用）。

#### 4.3.2 AI Reasoning Area

固定高度区域（约 80-120px），展示 AI 的当前思考。

这是 harness 的 TEXT_DELTA streaming content 的展示区。当 AI 在 tool call 之间输出文字（如 "Comps 显示 45x P/E，高于中位数 28x。我准备下调 Y3-5 增长假设..."），流式渲染在这里。

- RUNNING 状态：流式展示当前思考文字
- COMPLETE 状态：展示最终分析总结的前几行，可展开查看完整内容

视觉：浅灰背景，区别于 timeline 区域。

#### 4.3.3 Steering Input

始终可用的文本输入框。

```typescript
interface SteeringInputProps {
  disabled: boolean;          // IDLE 状态时 disabled
  placeholder: string;        // 根据状态变化
  onSubmit: (message: string) => void;
  waitingForInput: boolean;   // request_user_input 触发时高亮
  pendingQuestion?: string;   // AI 的提问内容
}
```

状态变化：

| 页面状态 | 输入框状态 | placeholder |
|----------|-----------|-------------|
| IDLE | disabled | "开始分析后可以在这里介入..." |
| RUNNING | enabled | "输入以介入分析..." |
| WAITING | enabled + 高亮 | AI 的问题文字 |
| COMPLETE | enabled | "追问或发起新分析..." |

WAITING 状态时：
- 输入框上方显示 AI 的问题和选项（如果有）
- 输入框边框变为蓝色，吸引注意
- 用户回复后 → 状态回到 RUNNING

COMPLETE 状态时：
- 用户输入新查询 → 创建新分析
- 用户输入 follow-up → 作为 steering 发送到同一 harness（如果架构支持）或创建新分析

#### 4.3.4 Phase Indicator

底部小巧的进度条。

```
gather → analyze → evaluate → finalize
 [✓]      [●]       [ ]        [ ]
```

- 当前 phase：蓝色高亮
- 已完成 phase：绿色打勾
- 未到达 phase：灰色
- 高度约 24px，不抢眼

### 4.4 右侧面板：Structured Panels

Tab 切换，内容根据分析数据动态填充。

#### 4.4.1 Tab 结构

```typescript
type PanelTab = "data" | "model" | "comps" | "memory";

interface PanelState {
  activeTab: PanelTab;
  data: DataPanelState;
  model: ModelPanelState;
  comps: CompsPanelState;
  memory: MemoryPanelState;
}
```

Tab 自动切换逻辑：当有新数据到达时，自动切换到相关 tab（除非用户手动选了别的 tab）。

| 事件 | 自动切换到 |
|------|-----------|
| fmp_get_financials 返回 | Data |
| build_dcf 返回 | Model |
| get_comps 返回 | Comps |
| recall_memory 返回 | Memory（仅首次） |

如果用户在过去 5 秒内手动切换过 tab，则不自动切换（尊重用户意图）。

#### 4.4.2 Data Tab

展示从 FMP/FRED 拉取的关键财务数据。

```typescript
interface DataPanelState {
  ticker: string;
  metrics: MetricCard[];       // 关键指标卡片
  financials: FinancialTable;  // 财务数据表
  macroData: MacroData[];      // 宏观数据
  loading: boolean;
}

interface MetricCard {
  label: string;     // "DC Revenue", "Gross Margin", "Market Cap"
  value: string;     // "$38.5B/qtr", "76.5%", "$3.48T"
  change?: string;   // "+78% YoY", "-1.5pp"
  changeType?: "positive" | "negative" | "neutral";
}
```

布局：
- 顶部：2×2 或 3×2 MetricCard 网格（最重要的 4-6 个指标）
- 下方：可折叠的详细财务数据表（income statement / balance sheet / cash flow）
- 再下方：宏观数据（如果有）— 利率、CPI 等

MetricCard 视觉：
- 浅灰背景（`bg-secondary`），no border，border-radius 8px
- 13px muted label 在上
- 24px/500 数值在下
- 右上角小字 change（绿/红）

数据渐进填充：每当 `fmp_get_financials` 返回时，相应数据出现在面板上。

#### 4.4.3 Model Tab

展示 DCF 模型结果。这是分析的核心输出。

```typescript
interface ModelPanelState {
  rounds: DCFRound[];           // 每轮估值结果
  currentRound: number;
  activeRoundView: number;      // 用户当前查看的是哪一轮
  sensitivityData: SensitivityData | null;
  loading: boolean;
}

interface DCFRound {
  roundNumber: number;
  fairValuePerShare: number;
  currentPrice: number;
  gapPercent: number;
  impliedMultiples: {
    fwdPE: number;
    evEbitda: number;
    fcfYield: number;
    pegRatio: number;
  };
  keyAssumptions: Assumption[];
  revisionReason: string | null;  // null for Round 1
  yearByYear: YearProjection[];
  scenarioWeightedValue: number | null;
}

interface Assumption {
  name: string;
  value: string;
  reasoning: string;
}

interface SensitivityData {
  waccValues: number[];    // [0.10, 0.11, 0.12, 0.13, 0.14]
  growthValues: number[];  // [0.02, 0.025, 0.03, 0.035, 0.04]
  matrix: number[][];      // fair value for each (wacc, growth) pair
}
```

布局（从上到下）：

**1. 核心结论卡片**
```
┌──────────────────────────────────────┐
│ Fair Value: $165/share               │
│ Market Price: $142                   │
│ Gap: +16.3% (低估)                   │
│                                      │
│ Round: ● 1 ($178) → ● 2 ($165)      │
│ Revision: Y3-5 DC growth revised ↓  │
└──────────────────────────────────────┘
```

- 大号字体 fair value
- Gap% 用绿色（低估）或红色（高估）badge
- Round history：可点击的圆点，点击切换查看不同 round 的假设

**2. 关键假设列表**

当前 round 的主要假设。每个假设一行：

```
DC Revenue Growth Y1: +35%
  └ 管理层 guidance + 供应链验证 + 校准偏差调整 (+5%)

Gross Margin Y1: 74.5%
  └ 竞争压力 + 软件 mix 提升

WACC: 12%
  └ Beta 调整: CUDA 护城河降低现金流波动性
```

每个假设可展开查看完整 reasoning。

**3. 隐含倍数卡片**

```
Fwd P/E: 38x  |  EV/EBITDA: 28x  |  FCF Yield: 4.2%  |  PEG: 1.09
```

4 个 MetricCard 横排。

**4. Sensitivity 热力图**

WACC × Terminal Growth → Fair Value 矩阵。

静态渲染（Phase 1），hover 显示具体数值。当前假设的交叉点高亮标记。

用 HTML table 渲染，单元格背景色用绿-黄-红渐变表示 gap%。

**5. 年度预测表（可折叠）**

```
Year | Revenue  | FCF    | Discounted FCF
  1  | $193.5B  | $75.5B | $67.4B
  2  | $240.1B  | $91.2B | $72.8B
  ...
TV   |          |        | $387.0B
```

建模状态：
- RUNNING 且尚未跑 DCF：显示 "Waiting for DCF model..." 占位
- build_dcf 正在运行：显示 spinner + "Building Round {N}..."
- build_dcf 返回：渲染结果
- 多轮修正：Round selector 切换不同结果

#### 4.4.4 Comps Tab

同行对比。

```typescript
interface CompsPanelState {
  targetTicker: string;
  peers: PeerComparison[];
  scatterData: ScatterPoint[];  // P/E vs Growth 散点图
  loading: boolean;
}

interface PeerComparison {
  ticker: string;
  fwdPE: number;
  evEbitda: number;
  revenueGrowth: number;
  grossMargin: number;
  isTarget: boolean;  // true for the company being analyzed
}
```

布局：

**1. 对比表**

| Company | Fwd P/E | EV/EBITDA | Rev Growth | Gross Margin |
|---------|---------|-----------|------------|--------------|
| **NVDA** | **38x** | **28x** | **+30%** | **76%** |
| AVGO | 25x | 20x | +15% | 65% |
| AMD | 32x | 25x | +22% | 52% |
| Median | 28x | 22x | +18% | 58% |

目标公司行加粗。高于中位数的值标为琥珀色，低于中位数标为蓝色。

**2. Comps 散点图**

X 轴：Revenue Growth
Y 轴：Fwd P/E

每个 peer 是一个点，目标公司是一个大的高亮点。用 Chart.js 或 Recharts 渲染。

如果隐含 P/E vs 中位数差距 >50%，显示一个 alert：

```
⚠️ 隐含 P/E (38x) 比行业中位数 (28x) 高 36%
AI 判断: 2x 增速差异支撑溢价，PEG 1.1x vs 同行 1.3x
```

**空状态**: "Comps data will appear after AI runs peer comparison."

#### 4.4.5 Memory Tab

展示从 memory 系统读取的历史信息。

```typescript
interface MemoryPanelState {
  companyMemory: string | null;    // markdown content from memory/companies/TICKER.md
  sectorMemory: string | null;     // markdown content from memory/sectors/SECTOR.md
  calibration: CalibrationEntry[];
  loading: boolean;
}

interface CalibrationEntry {
  date: string;
  metric: string;
  predicted: number;
  actual: number | null;
  errorPercent: number | null;
}
```

布局：

**1. 校准记录**

```
历史预测偏差:
  Q4 DC Revenue: 预测 $35B, 实际 $38.5B (-9.1%)
  Q3 DC Revenue: 预测 $31B, 实际 $33.2B (-6.6%)
  
  ⚠️ 模式: 连续低估 DC revenue 6-9%。本次已上调。
```

**2. 上次分析要点**

从 `memory/companies/TICKER.md` 解析的关键信息：
- 上次 fair value + gap
- Thesis 概要
- Kill criteria 状态（checklist 形式）
- What I Got Wrong（上次的错误反思）

**3. 行业记忆**

从 `memory/sectors/SECTOR.md` 解析的行业认知摘要。

**空状态**: "首次分析此公司，无历史记忆。分析完成后将自动创建。"

### 4.5 分析完成后的布局变化

当 harness 返回 `ok: true` 时：

1. Timeline 区域保持不变（用户仍可回看过程）
2. AI Reasoning Area 展示最终分析总结（完整的 `result.reply`），可滚动
3. Steering Input 的 placeholder 变为 "追问或输入新 ticker..."
4. Phase indicator 所有步骤变绿
5. 右侧面板所有 tab 数据完整，默认激活 Model tab

分析完成后不做页面跳转或布局重排——平滑过渡。

---

## 5. Memory Manager (`/memory`)

### 5.1 页面结构

```
┌──────────────────────────────────────────────────┐
│ [全局导航]                                        │
├────────────────┬─────────────────────────────────┤
│                │                                 │
│  File Tree     │  File Content Viewer            │
│  (sidebar)     │  (main area)                    │
│                │                                 │
│  companies/    │  # NVDA — Accumulated Intel     │
│    NVDA.md ◄── │                                 │
│    AMD.md      │  ## Current Thesis              │
│    TSLA.md     │  NVIDIA 在 AI 基础设施赛道具有    │
│  sectors/      │  结构性优势。CUDA 生态系统...      │
│    semicon.md  │                                 │
│  patterns/     │  ## Key Numbers (latest)        │
│    earnings.md │  - DC Revenue: $38.5B/qtr       │
│  calibration/  │  - Gross Margin: 76.5%          │
│    log.jsonl   │  - My Fair Value: $165          │
│                │                                 │
│                │  [Edit] [Raw] [History]         │
│                │                                 │
└────────────────┴─────────────────────────────────┘
```

### 5.2 File Tree (Sidebar)

```typescript
interface MemoryTreeItem {
  name: string;          // "NVDA.md"
  path: string;          // "companies/NVDA.md"
  type: "file" | "directory";
  children?: MemoryTreeItem[];
  lastModified?: string;
}
```

- 根目录：companies / sectors / patterns / calibration
- 文件按字母排序
- 当前选中文件高亮
- 点击文件 → 右侧展示内容

### 5.3 File Content Viewer

- 默认渲染模式：将 markdown 渲染为 HTML（用 `react-markdown` 或类似库）
- 切换到 Raw 模式：显示原始 markdown 文本
- Edit 模式：内联编辑器（用 `textarea` 或简单的 code editor），保存后 PUT 到后端
- History：显示文件的修改历史（如果 git 跟踪的话；MVP 可省略）

calibration/log.jsonl 特殊处理：解析 JSONL 并渲染为表格，支持按公司筛选。

### 5.4 Memory 与 Analysis 的联动

Memory 页面的公司文件里应该有一个 "Run Update Analysis" 按钮，点击 → 导航到 `/analysis/new?ticker=TICKER&mode=update`。

---

## 6. Steering 协议（前端 + Soul）

### 6.1 Steering 消息分类

AI 从语义推断 steering 的意图，前端不需要区分。以下写入 `soul/steering.md`：

```
用户 steering 消息分为 4 类，由 AI 自行判断：

SUGGESTION — 用户提供一个观点。AI 参考但可以 pushback。
  信号: "我觉得...", "你有没有考虑...", "也许可以看看..."
  → AI 权衡后可以礼貌地不同意，给出理由。

OVERRIDE — 用户坚持特定参数或方向。
  信号: "请用...", "我要你...", "必须...", 同一观点第二次提出
  → AI 执行。在 reasoning 中标注 [USER OVERRIDE]。

QUESTION — 用户想在继续之前了解信息。
  信号: "为什么...", "你怎么看...", "能解释一下..."
  → AI 回答，然后继续分析。

REDIRECT — 用户要求改变研究方向。
  信号: "不要看这个了，去看...", "加上 automotive segment"
  → AI 调整范围，记录 redirect。
```

### 6.2 `request_user_input` Tool

AI 在极少数情况下主动暂停。

```python
# tools/user_input.py

REQUEST_USER_INPUT_SCHEMA = make_tool_schema(
    name="request_user_input",
    description=(
        "Pause analysis and ask the user a question. Use SPARINGLY — "
        "only when facing genuine uncertainty that search cannot resolve. "
        "Most analyses should complete with 0-1 calls to this tool."
    ),
    properties={
        "question": {
            "type": "string",
            "description": "Clear, specific question for the user"
        },
        "context": {
            "type": "string",
            "description": "What you've found so far and why you need input"
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Suggested options if applicable"
        },
    },
    required=["question", "context"],
)
```

前端处理：
1. 收到 SSE event `type: "user_input_needed"` with question/context/options
2. 页面状态 → WAITING
3. Steering input 高亮显示
4. 输入框上方展示 AI 的问题和选项按钮（如有）
5. 用户输入或点选 → POST `/api/respond`
6. 页面状态 → RUNNING

Soul 中限制使用频率：

```markdown
# soul/steering.md (添加)

## request_user_input 使用规则

仅在以下情况调用:
1. 面临显著影响结果的二选一，且双方证据大致相当
2. 发现与用户意图矛盾的关键信息（如公司正在被收购）
3. 关键数据缺失且搜索无法获取

不要调用:
- 常规确认（这是 Full Auto 模式）
- 你能通过搜索解决的问题
- 小参数决策

平均每次分析使用 0-1 次。超过 2 次说明你过于谨慎。
```

---

## 7. 前后端通信 API

### 7.1 架构总览

```
Next.js Frontend ◄──── SSE (events) ──── FastAPI Backend
                 ────► POST (actions) ──►
```

后端是现有 Python 代码上加一层 FastAPI wrapper。harness 的 `on_event` callback 桥接到 SSE stream。

### 7.2 API 端点

#### 7.2.1 分析相关

**POST `/api/analyze`**

启动新分析。返回 analysis ID + SSE stream URL。

```typescript
// Request
interface AnalyzeRequest {
  query: string;                // "分析 NVDA" 或 "NVDA"
  contextDocs?: string[];       // 可选的用户粘贴文档
}

// Response
interface AnalyzeResponse {
  analysisId: string;           // UUID
  streamUrl: string;            // "/api/analyze/{id}/stream"
}
```

**GET `/api/analyze/:id/stream`** (SSE)

Server-Sent Events stream。harness 运行过程中持续推送事件。

```typescript
// SSE event types
interface SSEEvent {
  type: "tool_start" | "tool_end" | "text_delta" | "text" | "phase_change"
      | "context_compacted" | "retry" | "user_input_needed" | "complete" | "error";
  data: any;
}

// tool_start
{ type: "tool_start", data: { tool: "exa_search", args: { query: "NVDA Q1 2027" } } }

// tool_end
{ type: "tool_end", data: { tool: "exa_search", status: "ok", result: {...} } }

// text_delta (AI streaming text)
{ type: "text_delta", data: { content: "Comps 显示 45x P/E..." } }

// text (complete AI text block)
{ type: "text", data: { content: "完整的 AI 思考文字" } }

// phase_change
{ type: "phase_change", data: { from: "gather", to: "analyze" } }

// user_input_needed (request_user_input tool triggered)
{ type: "user_input_needed", data: { question: "...", context: "...", options: ["A", "B"] } }

// complete
{ type: "complete", data: { ok: true, reply: "...", toolLog: [...], tokens: {...} } }

// error
{ type: "error", data: { message: "...", recoverable: false } }
```

**POST `/api/analyze/:id/steer`**

发送 steering 消息。

```typescript
// Request
interface SteerRequest {
  message: string;
}

// Response
{ status: "ok" }
```

**POST `/api/analyze/:id/respond`**

回复 `request_user_input` 暂停。

```typescript
// Request
interface RespondRequest {
  response: string;
}

// Response
{ status: "ok" }
```

#### 7.2.2 Memory 相关

**GET `/api/memory`**

列出所有 memory 文件。

```typescript
// Response
interface MemoryTree {
  companies: MemoryFile[];
  sectors: MemoryFile[];
  patterns: MemoryFile[];
  calibration: MemoryFile[];
}

interface MemoryFile {
  name: string;           // "NVDA.md"
  path: string;           // "companies/NVDA.md"
  lastModified: string;   // ISO datetime
  sizeBytes: number;
}
```

**GET `/api/memory/:type/:filename`**

读取 memory 文件内容。

```typescript
// Response
interface MemoryFileContent {
  path: string;
  content: string;        // raw markdown or jsonl
  lastModified: string;
}
```

**PUT `/api/memory/:type/:filename`**

更新 memory 文件（用户手动编辑）。

```typescript
// Request
interface UpdateMemoryRequest {
  content: string;
}

// Response
{ status: "ok", lastModified: "..." }
```

#### 7.2.3 Watchlist 相关

**GET `/api/watchlist`**

从 memory/companies/ 目录生成 watchlist 数据。后端解析每个 .md 文件的 header 信息。

```typescript
// Response
interface WatchlistItem {
  ticker: string;
  fairValue: number | null;
  marketPrice: number | null;
  gapPercent: number | null;
  lastAnalysisDate: string | null;
  thesisStatus: "bullish" | "neutral" | "bearish" | null;
  thesisSummary: string | null;
  alerts: Alert[];
}

type WatchlistResponse = WatchlistItem[];
```

#### 7.2.4 Calibration 相关

**GET `/api/calibration?company=NVDA`**

从 `memory/calibration/prediction_log.jsonl` 查询校准记录。

```typescript
// Response
interface CalibrationResponse {
  entries: CalibrationEntry[];
  summary: {
    totalPredictions: number;
    averageError: number;
    biasDirection: "overestimate" | "underestimate" | "balanced";
    biasNote: string;   // "连续 3 次低估 DC revenue 6-9%"
  };
}
```

### 7.3 FastAPI 后端实现要点

```python
# backend/api.py (核心结构)

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from core.harness import Harness, HarnessEvent, EventType

app = FastAPI()
analyses: dict[str, AnalysisSession] = {}  # in-memory session store

class AnalysisSession:
    def __init__(self, analysis_id: str, harness: Harness):
        self.id = analysis_id
        self.harness = harness
        self.events: asyncio.Queue = asyncio.Queue()
        self.user_input_tool: UserInputTool = None
    
    def on_event(self, event: HarnessEvent):
        """Bridge harness events to SSE queue."""
        self.events.put_nowait(self._serialize_event(event))

@app.post("/api/analyze")
async def start_analysis(request: AnalyzeRequest):
    analysis_id = str(uuid.uuid4())
    harness, _ = build_harness(on_event=session.on_event)
    session = AnalysisSession(analysis_id, harness)
    analyses[analysis_id] = session
    
    # Run harness in background thread
    thread = threading.Thread(
        target=harness.run,
        args=(request.query,),
        kwargs={"context_docs": request.context_docs},
    )
    thread.start()
    
    return {"analysisId": analysis_id, "streamUrl": f"/api/analyze/{analysis_id}/stream"}

@app.get("/api/analyze/{analysis_id}/stream")
async def stream_events(analysis_id: str):
    session = analyses[analysis_id]
    
    async def event_generator():
        while True:
            event = await session.events.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("complete", "error"):
                break
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )

@app.post("/api/analyze/{analysis_id}/steer")
async def steer(analysis_id: str, request: SteerRequest):
    session = analyses[analysis_id]
    session.harness.steer(request.message)
    return {"status": "ok"}

@app.post("/api/analyze/{analysis_id}/respond")
async def respond_to_input(analysis_id: str, request: RespondRequest):
    session = analyses[analysis_id]
    session.user_input_tool.submit_response(request.response)
    return {"status": "ok"}
```

### 7.4 SSE Event → UI 面板更新映射

前端收到 SSE event 后，需要同时更新左侧 timeline 和右侧面板。

```typescript
// frontend/hooks/useAnalysisStream.ts (核心逻辑)

function handleSSEEvent(event: SSEEvent) {
  // 1. 始终追加到 timeline
  appendTimelineEvent(toTimelineEvent(event));
  
  // 2. 根据 tool name 更新右侧面板
  if (event.type === "tool_end" && event.data.status === "ok") {
    switch (event.data.tool) {
      case "fmp_get_financials":
        updateDataPanel(event.data.result);
        autoSwitchTab("data");
        break;
      case "fred_get_macro":
        updateMacroData(event.data.result);
        break;
      case "build_dcf":
        updateModelPanel(event.data.result);
        autoSwitchTab("model");
        break;
      case "get_comps":
        updateCompsPanel(event.data.result);
        autoSwitchTab("comps");
        break;
      case "recall_memory":
        updateMemoryPanel(event.data.result);
        break;
      case "extract_observation":
        incrementObservationCount();
        break;
      case "create_hypothesis":
        updateHypothesisCard(event.data.result);
        break;
    }
  }
  
  // 3. AI streaming text → reasoning area
  if (event.type === "text_delta") {
    appendReasoningText(event.data.content);
  }
  
  // 4. Phase change → update indicator
  if (event.type === "phase_change") {
    updatePhaseIndicator(event.data.to);
  }
  
  // 5. User input needed → switch to WAITING state
  if (event.type === "user_input_needed") {
    setPageState("WAITING");
    setPendingQuestion(event.data);
  }
  
  // 6. Complete → switch to COMPLETE state
  if (event.type === "complete") {
    setPageState("COMPLETE");
    setFinalReply(event.data.reply);
  }
}
```

---

## 8. 前端状态管理

### 8.1 全局状态

```typescript
// stores/analysisStore.ts (Zustand 或类似)

interface AnalysisStore {
  // 页面状态
  pageState: "IDLE" | "RUNNING" | "WAITING" | "COMPLETE";
  analysisId: string | null;
  
  // 左侧面板
  timeline: TimelineEvent[];
  reasoningText: string;
  currentPhase: string;
  pendingQuestion: PendingQuestion | null;
  
  // 右侧面板
  activeTab: PanelTab;
  lastUserTabSwitch: number;   // timestamp，用于判断是否自动切换
  dataPanel: DataPanelState;
  modelPanel: ModelPanelState;
  compsPanel: CompsPanelState;
  memoryPanel: MemoryPanelState;
  
  // Actions
  startAnalysis: (query: string, contextDocs?: string[]) => void;
  sendSteering: (message: string) => void;
  respondToInput: (response: string) => void;
  setActiveTab: (tab: PanelTab) => void;
}
```

### 8.2 SSE 连接管理

```typescript
// hooks/useSSE.ts

function useAnalysisStream(analysisId: string | null) {
  useEffect(() => {
    if (!analysisId) return;
    
    const eventSource = new EventSource(`/api/analyze/${analysisId}/stream`);
    
    eventSource.onmessage = (e) => {
      const event: SSEEvent = JSON.parse(e.data);
      handleSSEEvent(event);
    };
    
    eventSource.onerror = () => {
      // 重连逻辑
    };
    
    return () => eventSource.close();
  }, [analysisId]);
}
```

---

## 9. 关键 React 组件树

```
App
├── GlobalNav
│
├── HomePage
│   ├── SearchBar
│   ├── WatchlistGrid
│   │   └── WatchlistCard (×N)
│   └── RecentAnalysisList
│
├── AnalysisPage
│   ├── LeftPanel
│   │   ├── StreamingTimeline
│   │   │   └── TimelineItem (×N)
│   │   ├── AIReasoningArea
│   │   ├── SteeringInput
│   │   │   └── PendingQuestionCard (conditional)
│   │   └── PhaseIndicator
│   │
│   └── RightPanel
│       ├── PanelTabBar
│       ├── DataPanel
│       │   ├── MetricCardGrid
│       │   └── FinancialTable (collapsible)
│       ├── ModelPanel
│       │   ├── FairValueCard
│       │   ├── AssumptionList
│       │   ├── ImpliedMultiples
│       │   ├── SensitivityHeatmap
│       │   └── YearByYearTable (collapsible)
│       ├── CompsPanel
│       │   ├── PeerComparisonTable
│       │   └── CompsScatterChart
│       └── MemoryPanel
│           ├── CalibrationSummary
│           ├── LastAnalysisSummary
│           └── SectorMemorySummary
│
└── MemoryPage
    ├── MemoryFileTree
    └── MemoryFileViewer
        ├── MarkdownRenderer
        ├── RawTextView
        └── CalibrationTable (for .jsonl)
```

---

## 10. Timeline Event 翻译器

将 harness 的机器级事件翻译为用户友好的 timeline 描述。

```typescript
// utils/eventTranslator.ts

function translateEvent(event: SSEEvent): TimelineEvent {
  const { type, data } = event;
  
  if (type === "tool_start") {
    return translateToolStart(data.tool, data.args);
  }
  if (type === "tool_end") {
    return translateToolEnd(data.tool, data.status, data.result);
  }
  // ... other event types
}

function translateToolStart(tool: string, args: any): TimelineEvent {
  const translations: Record<string, (args: any) => string> = {
    exa_search: (a) => `搜索: "${a.query}"`,
    web_fetch: (a) => `阅读: ${new URL(a.url).hostname}`,
    fmp_get_financials: (a) => `拉取 ${a.ticker} ${a.statement_type} 数据`,
    fred_get_macro: (a) => `拉取宏观数据: ${a.series_id}`,
    recall_memory: (a) => `回忆 ${a.company || ""} 历史分析`,
    save_memory: (a) => `保存分析记忆`,
    build_dcf: () => `构建 DCF 模型`,
    get_comps: (a) => `对比同行: ${a.peers?.join(", ") || ""}`,
    extract_observation: (a) => `提取观察: ${a.claim?.substring(0, 40)}...`,
    create_hypothesis: (a) => `创建投资假说: ${a.company}`,
    add_evidence_card: () => `评估证据`,
    request_user_input: (a) => `向用户提问: ${a.question?.substring(0, 40)}...`,
  };
  
  const translate = translations[tool] || ((a: any) => tool);
  return {
    id: generateId(),
    timestamp: Date.now(),
    type: toolToEventType(tool),
    status: "running",
    message: translate(args),
    toolName: tool,
  };
}

function translateToolEnd(tool: string, status: string, result: any): Partial<TimelineEvent> {
  if (status !== "ok") {
    return { status: "error", message: `✗ ${result?.error || "Failed"}` };
  }
  
  const summaries: Record<string, (r: any) => string> = {
    exa_search: (r) => `找到 ${r.results?.length || 0} 篇相关文章`,
    web_fetch: (r) => `提取到 ${r.char_count?.toLocaleString() || "?"} 字符`,
    fmp_get_financials: (r) => `${r.ticker} 数据就绪`,
    build_dcf: (r) => `Fair Value: $${r.fair_value_per_share}/share`,
    get_comps: (r) => `Comps 对比完成`,
    recall_memory: (r) => r?.content ? "找到历史记录" : "无历史记录",
    save_memory: () => "记忆已更新",
    create_hypothesis: (r) => `假说已创建 (confidence: ${r.initial_confidence}%)`,
  };
  
  const summarize = summaries[tool] || (() => "完成");
  return { status: "done", message: `✓ ${summarize(result)}` };
}
```

---

## 11. 视觉设计规范

### 11.1 基础

- **字体**: Inter (sans-serif), JetBrains Mono (monospace)
- **颜色**: 使用 Tailwind 默认色板 + 自定义 semantic colors
- **圆角**: 4px (small), 8px (medium/default), 12px (large/cards)
- **间距**: 4/8/12/16/24/32/48px scale
- **阴影**: 仅 hover 和 focus 状态使用微弱 shadow

### 11.2 颜色语义

```css
:root {
  /* Gap colors */
  --gap-positive: #16a34a;   /* 绿: 低估 */
  --gap-negative: #dc2626;   /* 红: 高估 */
  --gap-neutral: #6b7280;    /* 灰: 中性 */
  
  /* Phase colors */
  --phase-gather: #0f766e;   /* teal */
  --phase-analyze: #1d4ed8;  /* blue */
  --phase-evaluate: #b45309; /* amber */
  --phase-finalize: #15803d; /* green */
  
  /* Timeline event colors */
  --event-search: #16a34a;   /* green */
  --event-analyze: #2563eb;  /* blue */
  --event-model: #d97706;    /* amber */
  --event-system: #6b7280;   /* gray */
  --event-user: #7c3aed;     /* purple */
  
  /* Status */
  --status-running: #2563eb;
  --status-done: #16a34a;
  --status-error: #dc2626;
  --status-waiting: #d97706;
}
```

### 11.3 深色模式

支持 dark mode（Tailwind `dark:` 前缀）。所有颜色变量提供 dark variant。

### 11.4 关键组件样式

**MetricCard**:
```
背景: bg-gray-50 (dark: bg-gray-800)
无 border
border-radius: 8px
padding: 16px
label: 13px, text-gray-500
value: 24px, font-weight 500
```

**TimelineItem**:
```
左侧: 8px 彩色圆点 (状态色)
右侧: 14px text
running 状态: 圆点有脉冲动画
展开: 下方缩进显示 detail (12px, text-gray-400)
```

**SteeringInput**:
```
默认: 标准 input，border-gray-200
WAITING: border-blue-400, ring-2 ring-blue-100
上方 PendingQuestion: blue bg card with question + option buttons
```

**SensitivityHeatmap**:
```
HTML table
cell 背景: 绿(低估) → 黄(中性) → 红(高估)
当前假设交叉点: 加粗 border
hover: 显示具体数值 tooltip
```

---

## 12. 响应式设计

### 12.1 断点

```
Desktop: ≥ 1024px — 左右分栏
Tablet: 768px - 1023px — 左右分栏但更紧凑
Mobile: < 768px — 单栏 + tab 切换
```

### 12.2 Mobile 适配（< 768px）

Analysis 页面：
- 不做左右分栏
- 改为底部 tab 切换：Timeline | Panels
- Timeline tab：显示 streaming timeline + AI reasoning + steering input
- Panels tab：显示右侧面板的所有内容
- 底部始终固定 steering input

Home 页面：
- Watchlist cards 单列
- 搜索栏全宽

---

## 13. 错误处理

### 13.1 网络错误

SSE 连接断开：
1. 显示 "连接中断，重连中..." 的 toast
2. 自动重连（指数退避，最多 5 次）
3. 重连成功后恢复 stream（可能丢失中间事件）
4. 重连失败后显示 "连接失败，请刷新页面"

### 13.2 分析错误

harness 返回 `ok: false`：
1. Timeline 显示红色错误事件
2. AI Reasoning Area 显示错误信息
3. Steering input placeholder: "分析失败。输入新查询重试..."
4. 已经收集到的面板数据保留（不清空）

### 13.3 工具级别错误

单个 tool call 失败（但分析继续）：
- Timeline 显示 ✗ 事件
- 不影响其他面板
- AI 通常会自行重试或跳过

---

## 14. 实施路线图

### Phase 0: 后端 API Layer

| 任务 | 详情 |
|------|------|
| FastAPI wrapper | 包装现有 harness，暴露 REST + SSE 接口 |
| SSE bridge | harness `on_event` → `asyncio.Queue` → SSE stream |
| Memory REST | CRUD for memory/ 目录 |
| Watchlist endpoint | 解析 memory/companies/*.md 生成 summary |
| CORS + auth placeholder | 开发阶段 CORS 允许 localhost |

### Phase 1: Analysis Workspace

| 任务 | 详情 |
|------|------|
| 页面骨架 | 左右分栏 layout，tab bar |
| SSE 连接 | `useAnalysisStream` hook |
| Streaming Timeline | 事件列表 + 翻译器 |
| AI Reasoning Area | streaming text 渲染 |
| Steering Input | 发送 + WAITING 状态 |
| Phase Indicator | 进度条 |
| Data Panel | MetricCard 网格 |
| Model Panel (basic) | Fair value card + 假设列表 |
| Comps Panel (basic) | 对比表 |
| Memory Panel | 校准记录 + 上次分析 |

### Phase 2: Home + Memory Pages

| 任务 | 详情 |
|------|------|
| Home SearchBar | 输入 + 导航 |
| WatchlistGrid | 卡片渲染 |
| RecentAnalysisList | 列表 |
| Memory FileTree | 目录树 |
| Memory Viewer | markdown 渲染 + 编辑 |

### Phase 3: 增强

| 任务 | 详情 |
|------|------|
| Sensitivity Heatmap | 交互式热力图 |
| Comps Scatter Chart | P/E vs Growth 散点图 |
| Mobile responsive | 断点适配 |
| Dark mode | 完整深色主题 |
| Analysis history | 保存历史分析结果，可回看 |

### Phase 4: 进阶

| 任务 | 详情 |
|------|------|
| DCF Waterfall 图 | Revenue → FCF → EV → Fair Value |
| 历次 FV 变化时间线 | memory 中多次分析的 fair value 走势 |
| PDF 报告导出 | Model tab 内容导出为可分享的 PDF |
| 交互式 What-if | 用户拖滑块调参数（sandbox 模式） |

---

## 15. 文件结构（前端）

```
iris-frontend/
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── layout.tsx                # 全局 layout + GlobalNav
│   │   ├── page.tsx                  # Home page
│   │   ├── analysis/
│   │   │   └── [id]/
│   │   │       └── page.tsx          # Analysis workspace
│   │   └── memory/
│   │       ├── page.tsx              # Memory manager
│   │       └── [type]/[filename]/
│   │           └── page.tsx          # Memory file viewer
│   │
│   ├── components/
│   │   ├── nav/
│   │   │   └── GlobalNav.tsx
│   │   ├── home/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── WatchlistGrid.tsx
│   │   │   ├── WatchlistCard.tsx
│   │   │   └── RecentAnalysisList.tsx
│   │   ├── analysis/
│   │   │   ├── LeftPanel.tsx
│   │   │   ├── StreamingTimeline.tsx
│   │   │   ├── TimelineItem.tsx
│   │   │   ├── AIReasoningArea.tsx
│   │   │   ├── SteeringInput.tsx
│   │   │   ├── PendingQuestionCard.tsx
│   │   │   ├── PhaseIndicator.tsx
│   │   │   ├── RightPanel.tsx
│   │   │   ├── PanelTabBar.tsx
│   │   │   ├── panels/
│   │   │   │   ├── DataPanel.tsx
│   │   │   │   ├── ModelPanel.tsx
│   │   │   │   ├── CompsPanel.tsx
│   │   │   │   └── MemoryPanel.tsx
│   │   │   └── charts/
│   │   │       ├── SensitivityHeatmap.tsx
│   │   │       ├── CompsScatter.tsx
│   │   │       └── MetricCard.tsx
│   │   └── memory/
│   │       ├── MemoryFileTree.tsx
│   │       ├── MemoryFileViewer.tsx
│   │       └── CalibrationTable.tsx
│   │
│   ├── hooks/
│   │   ├── useAnalysisStream.ts      # SSE connection + event handling
│   │   ├── useAnalysisStore.ts       # Zustand store
│   │   └── useWatchlist.ts           # Watchlist data fetching
│   │
│   ├── utils/
│   │   ├── eventTranslator.ts        # harness event → timeline event
│   │   ├── api.ts                    # API client functions
│   │   └── formatters.ts             # number/date formatting
│   │
│   └── types/
│       ├── analysis.ts               # Analysis-related types
│       ├── memory.ts                 # Memory-related types
│       └── api.ts                    # API request/response types
│
├── tailwind.config.ts
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## 16. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | Next.js + React + TypeScript | 生态成熟，SSR 支持，TypeScript 类型安全 |
| 样式方案 | Tailwind CSS | 快速开发，一致性好，dark mode 原生支持 |
| 状态管理 | Zustand | 轻量，适合中等规模应用，比 Redux 简单 |
| 前后端通信 | SSE (events) + REST (actions) | SSE 适合单向 stream，比 WebSocket 简单 |
| 左右分栏比例 | 45:55 固定 | 简化实现，避免 resize 的复杂性 |
| 交互模式 | Full Auto + Steer | 讨论确定：不需要 Supervised 模式 |
| Steering 语义 | AI 自行判断建议/指令 | 用户不需要标记意图，更自然 |
| `request_user_input` | Tool call 实现 | 路径 A：更灵活，不需改 harness |
| Tab 自动切换 | 有新数据时自动切 + 5s 用户覆盖保护 | 平衡自动化和用户控制 |
| Mobile 适配 | 底部 tab 切换 Timeline/Panels | 无法左右分栏，tab 是最简单的方案 |
| Memory 编辑 | 内联编辑器 | Memory 本就设计为人可读可编辑的 markdown |
| 分析完成后布局 | 不做布局重排，平滑过渡 | 避免突兀的页面跳转 |
| 图表库 | Recharts (React 原生) | 比 Chart.js 更 React-friendly |
| Sensitivity 热力图 | HTML table + CSS 颜色 | 简单直接，不需要额外图表库 |
