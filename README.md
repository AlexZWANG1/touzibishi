# Prism — AI 自主投研智能体

> **Decompose complexity. See clearly.**
>
> 一束复杂的市场数据进来，Prism 将它分解成清晰的光谱：基本面假说、估值模型、交易信号。

Prism 是一个 **自主投研 Agent**，把自然语言研究任务转化为结构化、有证据支撑的投资分析。它的核心不是「调 API 拼凑答案」，而是一个严肃设计的 **LLM 控制循环（Harness）**—— 带预算管理、循环检测、上下文压缩和记忆冲刷的完整 Agent 运行时。

---

## 设计哲学：三层解耦

```
┌─────────────────────────────────────────────────────┐
│  Harness（代码层）                                    │
│  公式、流程、安全检查 —— 必须稳定正确                      │
│  Agent Loop · Budget · Loop Detection · Compaction   │
├─────────────────────────────────────────────────────┤
│  Context（配置层）  iris_config.yaml                   │
│  权重、阈值、参数 —— 依赖信息，可调                        │
│  工具轮次 · 超时 · 技能组合 · 向量检索参数                  │
├─────────────────────────────────────────────────────┤
│  Prompt（灵魂层）  soul/                               │
│  哲学、风格、判断力 —— 本来就不确定                        │
│  角色定义 · 投资哲学 · 贝叶斯框架 · 自检清单                │
└─────────────────────────────────────────────────────┘
```

这个分层的核心思想：**改配置不需要碰代码，改提示词不需要碰配置**。每一层的变更频率和确定性不同，所以解耦。

---

## Harness 架构：Agent 控制循环

Harness 是整个系统的引擎。它不是简单的「LLM + tool call」，而是一个解决了 Agent 工程核心难题的运行时。

### 主循环（Main Loop）

每一轮推理经过以下阶段：

```
┌──────────────────────────────────────────────────────────────┐
│                     Harness Main Loop                        │
│                                                              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌────────────┐  │
│  │ Steering │──▶│ Context │──▶│  Tool   │──▶│    LLM     │  │
│  │ Inject   │   │ Check   │   │ Inject  │   │  Reasoning │  │
│  └─────────┘   └────┬────┘   └─────────┘   └─────┬──────┘  │
│                     │                              │         │
│              ▼ 超过 85%                      有 tool_calls?  │
│        ┌───────────┐                         ╱         ╲     │
│        │ Compaction │                       是           否    │
│        │ + Memory   │                       │           │    │
│        │   Flush    │               ┌───────▼──────┐    │    │
│        └───────────┘               │ Tool Dispatch │    │    │
│                                     │  (并行/串行)  │    │    │
│                                     └───────┬──────┘    │    │
│                                             │           │    │
│                                     ┌───────▼──────┐    │    │
│                                     │ Loop Detect  │    │    │
│                                     │ + Budget Chk │    │    │
│                                     └───────┬──────┘    │    │
│                                             │           │    │
│                                        继续循环      返回结果  │
└──────────────────────────────────────────────────────────────┘
```

1. **Steering 注入** — 支持运行中实时注入用户引导（通过 steering queue），无需重启
2. **上下文检查** — 监控消息总量，85% 阈值触发主动压缩
3. **工具注入** — 每轮动态暴露工具 schema，LLM 自主决定调用顺序
4. **LLM 推理** — 带流式输出和自动重试（限速、上下文溢出）
5. **工具分发** — 多工具并行（ThreadPoolExecutor, 4 workers），单工具串行
6. **循环检测** — 检查重复模式，决定引导还是终止
7. **预算检查** — 三维度独立约束，任一超限即停

### 预算控制（Budget）

三条独立红线，任一触发即终止：

| 维度 | 默认值 | 说明 |
|---|---|---|
| **工具轮次** | 25 轮 | 离散推理回合数，flush/compaction 可选计入 |
| **总工具调用** | 60 次 | 所有轮次累计，超限前自动裁剪请求数 |
| **墙钟时间** | 480 秒 | 单调时钟，硬性截止 |

Token 消耗按类别记账：`main`（推理）、`flush`（记忆冲刷）、`compaction`（上下文压缩）、`embedding`（向量检索）。

### 循环检测（Loop Detection）

三种重叠检测器同时运行：

| 检测器 | 检测什么 | 示例 |
|---|---|---|
| **Generic Repeat** | 连续相同工具+参数 | 连续 3 次调 `financials("AAPL")` |
| **Ping-Pong** | 交替重复模式（滑动窗口 12） | `valuation` → `quote` → `valuation` → `quote` |
| **No-Progress** | 不同调用返回相同结果（SHA256） | 换了搜索词但数据没变 |

处理策略：`steer_then_stop`（默认）—— 首次触发注入引导，二次触发直接终止。

### 上下文压缩与记忆冲刷（Compaction + Memory Flush）

上下文接近 85% 容量时，自动执行两步操作：

1. **记忆冲刷**（先执行）— 让 LLM 用 `remember` / `create_hypothesis` 等工具把关键发现持久化到数据库，**防止压缩时丢失洞察**
2. **消息摘要** — 保留最近 6 条消息，LLM 总结旧消息为 `[CONTEXT SUMMARY]`，回收上下文窗口

这个设计解决了长对话 Agent 的核心问题：**上下文有限但研究要深**。先保存再压缩，保证知识不丢失。

### 工具结果压缩

工具返回的原始数据通常很大（财报、SEC Filing）。Harness 双轨处理：

- **压缩版** → 发给 LLM（financials/valuation: 8000-10000 字符，其他: 5000 字符）
- **完整版** → 存数据库 + 发前端，不丢失任何数据

### 会话续接与可恢复性

- **同会话续接** — 追加用户消息到现有 `_messages`，刷新预算和循环检测器，同一分析持续深入
- **跨会话恢复** — 从数据库重建 Harness 状态（消息历史、时间线、面板数据），可以隔天继续昨天的研究

---

## 系统架构

```
Frontend (Next.js + React + Tailwind)
├── 首页 / 分析 / 知识库 / 记忆管理 / 开发面板
│
│── SSE（流式推理实时推送） + REST API
│
Backend (FastAPI + Uvicorn)
├── Harness（Agent 控制循环）
│   ├── 预算控制 · 循环检测 · 上下文压缩 · 记忆冲刷
│   ├── 工具分发（并行 ThreadPoolExecutor）
│   ├── 流式事件桥接（HarnessEvent → SSE）
│   └── LLM Client → cliproxy → LLM
├── Skills（领域技能 — SKILL.md + tools.py）
│   ├── fundamentals — 深度研究方法论
│   ├── valuation — DCF + 可比公司框架
│   ├── trading — 信号生成 + 模拟执行
│   └── hypothesis — 贝叶斯证据评估
├── Tools（15+ 工具）
│   ├── 市场: quote, history, financials, macro
│   ├── 研究: exa_search, web_fetch, sec_filing, transcript
│   ├── 知识: search_knowledge, url_ingest, chunker, embedder
│   └── 记忆: remember, recall, unified_memory
├── Soul（提示层 — 纯 Markdown）
│   ├── role, reflection, self_check, steering
│   └── 贝叶斯证据评估 · 风险评估框架
├── Session Manager（会话管理）
│   ├── 事件累积器（timeline, panels, raw_text）
│   ├── 面板数据提取（fairValue, financials, strategy）
│   └── DB 持久化（消息历史 + 快照）
└── SQLite (iris.db)
    └── analysis_runs · knowledge_documents · embeddings · hypotheses · valuations
```

<p align="center"><img src="docs/screenshots/dev-panel.png" alt="系统架构可视化" width="750" /></p>

---

## 两种工作模式

### 深度分析模式（Analysis）

用于实时研究。输入一个研究问题，Agent 自主完成四个阶段：

| 阶段 | 做什么 | 典型工具 |
|---|---|---|
| **收集** | 搜索新闻、拉取财报、SEC Filing、业绩电话会 | `exa_search`, `financials`, `sec_filing`, `transcript` |
| **分析** | 建立假设，贝叶斯评估证据强度 | `create_hypothesis`, `add_evidence_card` |
| **评估** | DCF 估值、可比公司分析、公允价值区间 | `valuation`, `quote`, `history` |
| **总结** | 结构化报告 + 交易信号 + 仓位建议 | `generate_trade_signal`, `execute_trade` |

### 学习模式（Learning）

用于复盘与自我校准：

- 回顾此前对某公司/行业的判断（`recall`）
- 对照最新财报数据和市场表现（`financials`, `web_fetch`）
- 识别预测偏差 — 哪些对了，哪些错了，为什么
- 将经验教训写入记忆（`remember`），供未来分析参考

学习模式有更大的预算（40 轮 / 120 次调用 / 600 秒），因为复盘需要更深的探索。

**学习模式让 Prism 不只是工具，而是持续进化的研究伙伴。** 每次复盘都在修正系统的认知模型。

---

## 界面截图

### 首页 — 研究入口

输入自然语言研究任务，选择「深度分析」或「学习模式」，一键启动。

<p align="center"><img src="docs/screenshots/home-watchlist.png" alt="首页" width="750" /></p>

### 深度分析 — AI 芯片行业竞争格局

左侧：实时工具调用日志（检索记忆 → 拉取财报 × 6 → SEC Filing × 4 → 搜索资讯 × 4 → 交易信号 × 3）。右侧：流式输出的结构化研究报告。Agent 自主完成 23 次数据调用。

<p align="center"><img src="docs/screenshots/analysis-ai-chip.png" alt="AI 芯片深度分析" width="750" /></p>

### 数据面板 — 自动收集的财务数据

分析过程中自动拉取的所有财务指标集中展示，支持多标的对比。

<p align="center"><img src="docs/screenshots/analysis-data-panel.png" alt="数据面板" width="750" /></p>

### 策略面板 — 交易信号

研究结论自动转化为策略卡片：现价、目标价、止损价、催化剂。

<p align="center"><img src="docs/screenshots/analysis-strategy.png" alt="交易策略" width="750" /></p>

### 学习模式 — META 财报复盘

学习模式下主动复盘过去的判断，对照最新财报事实，识别认知偏差。

<p align="center"><img src="docs/screenshots/analysis-meta-learning.png" alt="学习模式" width="750" /></p>

### 知识库 — 研究资料管理

拖拽上传 PDF/TXT/MD/CSV/JSON，抓取网页 URL，添加笔记。自动分块向量化，分析时智能检索。

<p align="center"><img src="docs/screenshots/knowledge.png" alt="知识库" width="750" /></p>

### 记忆管理 — 长期记忆

按公司、行业分类的持久化笔记 + 校准日志。跨会话积累。

<p align="center"><img src="docs/screenshots/memory.png" alt="记忆管理" width="750" /></p>

---

## 核心技能（Skills）

Skills 是领域能力单元：`SKILL.md`（行为提示词）+ `tools.py`（专用工具），Harness 运行时自动加载。

| 技能 | 路径 | 核心能力 |
|---|---|---|
| **基本面研究** | `iris/skills/fundamentals/` | 假设驱动 + 贝叶斯证据链 + 多来源（SEC/电话会/新闻/知识库）→ 结构化研究报告 |
| **估值分析** | `iris/skills/valuation/` | DCF 现金流折现 + 可比公司 → 公允价值区间（牛/基准/熊三场景） |
| **交易策略** | `iris/skills/trading/` | 信号生成（含置信度）+ 仓位计算 + 模拟执行 + 组合追踪 |
| **假设管理** | `iris/skills/hypothesis/` | 创建假设 + 附加证据卡片（支持/反驳/权重）+ 置信度追踪 |

### 工具套件（15+ 工具）

| 类别 | 工具 | 说明 |
|---|---|---|
| **市场数据** | `quote`, `history`, `financials`, `macro` | 实时报价、历史行情、财务报表、宏观指标 |
| **信息搜索** | `exa_search`, `web_fetch` | 全网搜索 + 网页内容提取 |
| **SEC 文件** | `sec_filing`, `transcript` | 10-K/10-Q 年报季报、业绩电话会纪要 |
| **估值** | `valuation` | DCF、可比公司、公允价值计算 |
| **知识库** | `search_knowledge`, `url_ingest` | 向量检索上传的文档 |
| **记忆** | `remember`, `recall` | 跨会话持久化记忆 |
| **交易** | `generate_trade_signal`, `execute_trade`, `get_portfolio` | 信号生成、交易执行、组合查看 |

---

## 可拓展性

### 添加新工具（零配置发现）

```python
# iris/tools/sentiment.py
def sentiment_analysis(text: str, ticker: str = "") -> dict:
    """分析文本的市场情绪倾向，返回 bullish/bearish/neutral 及置信度。"""
    # 你的实现...
    return {"sentiment": "bullish", "confidence": 0.85}
```

1. 在 `iris/tools/` 下新建文件，定义函数 + 类型注解 + docstring
2. Harness 自动发现并注册
3. 在 `iris_config.yaml` 的 `always_exposed_tools` 中启用
4. （可选）`tool_triggers` 配置关键词触发

### 添加新技能

```
iris/skills/macro_analysis/
├── SKILL.md    # 行为提示词 — 定义该领域的研究方法论
└── tools.py    # 技能专用工具函数
```

在 `iris_config.yaml` 对应模式的 `skills` 列表中注册即可。**不需要改 Harness 代码。**

可以轻松添加：宏观经济分析、期权策略、ESG 评估、量化因子分析 等。

### 自定义 Soul（人格层）

```
iris/soul/
├── role.md         # 角色定义
├── v0.1.md         # 投资哲学：贝叶斯证据评估 + 风险 = 永久亏损概率 × 幅度
├── reflection.md   # 反思方法论
├── self_check.md   # 自检清单
└── steering.md     # 行为导向
```

纯 Markdown，不需要改代码。修改这些文件会深刻影响 Agent 的判断风格。

### 配置调优（iris_config.yaml）

| 参数域 | 可调内容 |
|---|---|
| **harness** | 工具轮次、总调用上限、超时、上下文压缩阈值、工具结果压缩上限 |
| **modes** | analysis / learning 模式各自的技能组合、工具集、预算 |
| **vector_search** | 嵌入模型、top-k 检索数量 |
| **knowledge** | 文档分块大小（800）和重叠长度（200） |
| **loop_detection** | 重复/乒乓/无进展阈值、处理策略 |
| **compaction** | 压缩策略、保留消息数、摘要 prompt、记忆冲刷 prompt |

---

## 快速开始

### 前置条件

- Python 3.11+ / Node.js 18+
- API Key：OpenAI 兼容 LLM 端点、[EXA](https://exa.ai) 搜索、[FMP](https://financialmodelingprep.com) 金融数据

### 安装 & 启动

```bash
git clone https://github.com/AlexZWANG1/touzibishi.git
cd touzibishi

# 后端
pip install -r requirements.txt

# 前端
cd iris-frontend && npm install
```

```bash
# 终端 1 — 后端
cd iris && python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000

# 终端 2 — 前端
cd iris-frontend && npm run dev
```

打开 **http://localhost:3000**，输入研究任务，开始。

---

## 成本

**开源免费自托管。** 使用成本来自底层 API：

| 服务 | 用途 | 典型成本 |
|---|---|---|
| LLM API（OpenAI 兼容） | 核心推理引擎 | ~$0.05–0.50 / 次分析 |
| EXA Search | 全网搜索 | 有免费额度 |
| FMP | 金融数据 | 有免费额度 |

一次深度分析（25 轮工具调用）≈ **$0.10–0.30** LLM 费用。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 14, React, TypeScript, Tailwind CSS |
| 后端 | Python, FastAPI, Uvicorn |
| 数据库 | SQLite |
| 向量嵌入 | OpenAI `text-embedding-3-small` |
| LLM | 任何 OpenAI 兼容 API |

---

MIT License

<p align="center">
  <sub>为独立投研而生。</sub>
</p>
