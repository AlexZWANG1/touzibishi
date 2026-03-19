# IRIS Development Specification v0.3

> Intelligent Research & Investment System — 开发规范文档
> 
> 本文档是 IRIS 重构的总纲。所有代码、配置、Soul 的编写都以本文档为准。
> 
> **v0.3 核心变更：DCF 不再是核心功能，而是一个 Skill。IRIS 的核心是 Agent loop + Memory + Skill loader。所有分析能力（估值方法、行业知识、报告生成）都以 Skill 形式插入。**

---

## 1. 投资哲学：我们赚什么钱

IRIS 赚的是**预期差**的钱。

核心逻辑极度简单：我们计算一只股票的内在价值（Fair Value），和市场价格比较。如果 Fair Value > Market Price，就是低估，就有机会。

```
Alpha = 我们对未来现金流的判断 − 市场对未来现金流的判断
```

我们不比市场更快（那是高频量化做的事），我们比市场**想得更深**——通过处理非结构化信息（earnings call 的语义、供应链的交叉信号）来形成比 consensus 更准确的判断。

### 1.1 IRIS 的差异化优势（vs 量化）

**语义理解**：量化模型看到 revenue = $38.5B。IRIS 看到的是"CFO 第三次在电话会上用 'inflection point'，前两次之后收入都加速了"。

**跨域推理链**：TSMC 产能利用率下降 → NVDA 供应受限？→ 但 NVDA 已锁定 CoWoS 产能 → 影响有限。同时 AMD MI300 良率提升 → 产能从 NVDA 转向 AMD？→ 不同产线，独立事件。三条信息来自不同来源，交叉验证后得出一个结论。

**这两个能力决定了 IRIS 的全部设计方向：帮助 AI 更好地估算 DCF 中的每一个参数。**

### 1.2 能力范围与扩展路线

**Phase 1 scope（当前实现）**：
- 基本面研究 + DCF 估值 + Comps 交叉验证
- 记忆系统（公司、行业、校准）
- 结构化研究（假说、证据、审计追踪）

**Future Skills（架构已支持，按需添加文件夹即可）**：

| 能力 | Skill 名 | 说明 |
|------|----------|------|
| 仓位管理 | `skills/position_sizing/` | Kelly criterion、波动率调整、组合层约束 |
| 技术面辅助 | `skills/technical/` | 均线、RSI、成交量异动 — 作为择时辅助信号 |
| 事件驱动 | `skills/event_driven/` | 财报前后、FDA审批、并购套利 |
| 自动交易 | `skills/execution/` | 连接 broker API，执行限价单 |
| 量化因子 | `skills/quant_factors/` | 动量、价值、质量因子回测 |
| 宏观 regime | `skills/macro_regime/` | 识别风险偏好周期，调整整体敞口 |

这些都不需要改核心代码。当你准备好了，写一个 `SKILL.md` + `tools.py` 放进 `skills/` 文件夹就行。

---

## 2. 核心模型：DCF + Comps 交叉验证

### 2.1 设计原则：数学固定，判断自由

**固定的（代码写死，永远不变）**：

```
FCF = Revenue − COGS − OpEx − Tax − CapEx − ΔWorkingCapital
Enterprise Value = Σ(FCF_t / (1+WACC)^t) + Terminal Value
Terminal Value = FCF_n × (1+g) / (WACC − g)
Equity Value = Enterprise Value + Cash − Debt
Fair Value per Share = Equity Value / Shares Outstanding
Gap = (Fair Value − Market Price) / Market Price
```

**自由的（AI 每次自己决定）**：

- 收入拆成几个 segment（按产品？地区？客户类型？）
- 预测几年（3 年？5 年？10 年？）
- 每个 segment 的增速是多少、为什么
- 毛利率、OpEx 比率、CapEx 比率的假设和理由
- WACC 是否需要调整、为什么
- 同行比较选哪些公司
- 对某家公司是否需要额外的场景分析（如 Tesla 的 FSD 期权价值）

**约束**：每个 AI 填入的数字都必须附带 reasoning 字段，说明依据和来源。

### 2.2 迭代式估值循环

不是线性流水线。AI 看到自己的输出后，会自我校验并修正。

```
Round 1: BUILD
  AI 收集信息 → 研究公司 → 填入 DCF 假设 JSON
  代码计算 → Fair Value per Share + 隐含倍数 (implied P/E, EV/EBITDA)

Round 2: SANITY CHECK
  AI 调用 get_comps 拉同行倍数
  AI 比较：我的隐含 P/E 是 38x，同行中位数 28x
  AI 判断：36% 溢价合理吗？PEG 对比如何？
  如果不合理 → 进入 Round 3

Round 3: REVISE（可选）
  AI 调整假设 → 标注修改原因
  代码重新计算 → 新的 Fair Value
  AI 再次检查 → 满意则完成

每轮都被完整记录。用户看到：
  "Round 1: $165 → Round 2 (post-comps): $152 → reason: Y3-5 growth revised down"
```

### 2.3 DCF 假设结构（JSON Schema — 非固定模板）

AI 填入的 JSON 只有少量必需字段，其余完全自由：

```json
{
  "company": "NVDA",
  "ticker": "NVDA",
  "analysis_date": "2026-03-18",
  "projection_years": 5,

  "segments": [
    {
      "name": "Data Center",
      "current_annual_revenue": 130e9,
      "growth_rates": [0.35, 0.28, 0.22, 0.18, 0.15],
      "reasoning": "Blackwell ramp Y1, inference demand growing..."
    },
    {
      "name": "Gaming",
      "current_annual_revenue": 12e9,
      "growth_rates": [0.08, 0.06, 0.05, 0.05, 0.04],
      "reasoning": "Mature segment, PC refresh cycle..."
    }
  ],

  "gross_margin": {
    "values": [0.745, 0.74, 0.735, 0.73, 0.73],
    "reasoning": "Slight compression from AMD competition, partially offset by software mix..."
  },

  "opex_pct_of_revenue": {
    "values": [0.165, 0.155, 0.15, 0.145, 0.14],
    "reasoning": "Operating leverage as revenue scales faster than headcount..."
  },

  "tax_rate": {
    "value": 0.12,
    "reasoning": "Effective rate ~12% due to international tax structure..."
  },

  "capex_pct_of_revenue": {
    "values": [0.04, 0.045, 0.04, 0.035, 0.035],
    "reasoning": "DGX Cloud buildout peaks Y2, then moderates..."
  },

  "working_capital_change_pct": {
    "values": [0.01, 0.01, 0.008, 0.008, 0.005],
    "reasoning": "Inventory builds for new product launches..."
  },

  "wacc": {
    "value": 0.12,
    "components": {
      "risk_free_rate": 0.043,
      "equity_risk_premium": 0.055,
      "beta": 1.4,
      "beta_reasoning": "Adjusted from market beta 1.7 — CUDA moat makes cash flows more predictable"
    },
    "reasoning": "Cost of equity ~12%, NVDA has no meaningful debt..."
  },

  "terminal_growth": {
    "value": 0.03,
    "reasoning": "GDP + inflation ~4-5%, conservatively use 3%..."
  },

  "net_cash": 30e9,
  "shares_outstanding": 24.5e9,

  "additional_notes": "可选 — AI 可以加任何它认为重要的补充说明",

  "scenarios": [
    {
      "name": "Bull case",
      "description": "AI capex accelerates, inference demand explodes",
      "key_override": {"segments[0].growth_rates": [0.45, 0.38, 0.30, 0.25, 0.20]},
      "probability": 0.25
    },
    {
      "name": "Bear case",
      "description": "AI capex cycle peaks, competition intensifies",
      "key_override": {"segments[0].growth_rates": [0.20, 0.12, 0.08, 0.05, 0.03]},
      "probability": 0.25
    }
  ]
}
```

注意：`segments` 的数量、名称、结构完全由 AI 根据公司特点决定。NVDA 可能拆 4 个产品线，Coca-Cola 可能拆 4 个地区，Tesla 可能拆 4 个业务线加一个概率加权的 FSD 场景。

### 2.4 代码计算输出

代码接收上述 JSON，输出：

```json
{
  "fair_value_per_share": 165.2,
  "current_price": 142.0,
  "gap_pct": 16.3,

  "year_by_year": [
    {"year": 1, "revenue": 193.5e9, "fcf": 75.5e9, "discounted_fcf": 67.4e9},
    {"year": 2, ...},
    ...
  ],

  "terminal_value": 730e9,
  "discounted_terminal_value": 387e9,
  "enterprise_value": 617e9,

  "implied_multiples": {
    "fwd_pe": 38.2,
    "ev_ebitda": 28.1,
    "fcf_yield": 0.042,
    "peg_ratio": 1.09
  },

  "sensitivity": {
    "wacc_impact": {"0.10": 198, "0.11": 180, "0.12": 165, "0.13": 152, "0.14": 141},
    "growth_impact": {"0.02": 148, "0.025": 155, "0.03": 165, "0.035": 177, "0.04": 192}
  },

  "scenario_weighted_value": 168.5,

  "revision_history": [
    {"round": 1, "fair_value": 178, "revision_reason": null},
    {"round": 2, "fair_value": 165, "revision_reason": "Post-comps check: implied 45x P/E too high, revised Y3-5 DC growth down"}
  ]
}
```

---

## 3. 记忆系统：让研究能复利

### 3.1 为什么需要记忆

每次分析都是独立的，AI 不知道它三个月前分析过同一家公司。这意味着：

- 无法追踪"上次预测的 +35% 增长实现了没有"
- 无法发现"这家公司的管理层总是低估 guidance"
- 无法积累"上次 TSMC 产能下降 5% 后发生了什么"
- 无法学习"我上次给 NVDA 打的 WACC 是不是太低了"

投资研究是复利系统。每一次分析都应该站在之前所有分析的肩膀上。

### 3.2 记忆架构

```
memory/
├── companies/
│   ├── NVDA.md          ← 关于 NVDA 的所有累积知识
│   ├── AMD.md
│   └── TSLA.md
├── sectors/
│   ├── semiconductors.md ← 半导体行业的累积认知
│   └── cloud_infrastructure.md
├── patterns/
│   ├── earnings_patterns.md  ← "管理层说 X 通常意味着 Y"
│   └── macro_patterns.md     ← "利率上升 100bp 对科技股估值影响约 Z"
└── calibration/
    └── prediction_log.jsonl  ← 每次预测的记录，用于校准
```

### 3.3 公司记忆文件格式

每次分析完成后，AI 生成/更新公司记忆文件：

```markdown
# NVDA — Accumulated Intelligence

## Last Updated: 2026-03-18

## Current Thesis
NVIDIA在AI基础设施赛道具有结构性优势。CUDA生态系统构成深厚护城河。
主要风险是AI capex周期何时见顶。

## Key Numbers (latest)
- DC Revenue Run Rate: $38.5B/quarter ($154B annualized)
- Gross Margin: 76.5% (Q1 FY2027)
- My Fair Value: $165 (as of 2026-03-18)
- Market Price at analysis: $142
- Gap: +16%

## Assumption Audit Trail
| Date       | Metric              | My Estimate | Actual  | Error  |
|------------|---------------------|-------------|---------|--------|
| 2025-11-15 | Q4 DC Revenue       | $35B        | $38.5B  | -9.1%  |
| 2025-11-15 | Q4 Gross Margin     | 75.0%       | 76.5%   | -1.5pp |
| 2025-08-20 | Q3 DC Revenue       | $31B        | $33.2B  | -6.6%  |

Pattern: I consistently underestimate NVDA's DC revenue. Consider 
adjusting base case up by 5-8% next time.

## Management Credibility Log
- 2025-02: Jensen guided "strong demand" → actual Q1 revenue beat by 12%. Credible.
- 2025-08: Jensen guided "unprecedented demand" → actual Q3 beat by 8%. Credible.
- Pattern: Management guidance is conservative. Their "strong" = market's "very strong".

## Competitive Dynamics
- AMD MI300: Launched Q4 2025. Revenue ~$3B/quarter by Q1 2026. 
  Growing but not taking meaningful share from NVDA training market.
- Google TPU: v5 competitive on inference cost but ecosystem is closed.
  Not a threat to NVDA's enterprise TAM.
- Custom chips (AMZN Trainium, MSFT Maia): Internal use only.
  Reduces hyperscaler NVDA purchase growth but doesn't affect enterprise.

## Kill Criteria Status
- [ ] DC revenue 连续两季度环比下降 — NOT triggered (still growing)
- [ ] AMD 拿走 >20% 训练份额 — NOT triggered (~8% estimated)
- [ ] 主要云客户削减 AI CapEx >30% — NOT triggered (all increasing)

## What I Got Wrong Last Time
- Underestimated gaming segment recovery (said flat, grew 12%)
- Overweighted China export risk (actual impact smaller than feared)
- WACC of 13% was probably too high — revised to 12% this round

## Open Questions for Next Analysis
- Blackwell yield rates at TSMC — need to track
- When does inference revenue surpass training revenue?
- Is the DGX Cloud margin profile meaningfully different from hardware?
```

### 3.4 行业记忆文件格式

```markdown
# Semiconductors — Sector Intelligence

## Industry Dynamics
- AI capex cycle: currently in acceleration phase (2024-2026)
- Historical cycles last 3-5 years before normalization
- Key leading indicator: cloud provider capex guidance

## Cross-Company Relationships
- TSMC → supplies NVDA, AMD, Apple, Qualcomm
  - TSMC utilization rate is a leading indicator for all customers
  - CoWoS advanced packaging is the current bottleneck
- NVDA ←→ AMD: direct competition in data center GPUs
  - AMD gaining in inference, NVDA dominates training
  - Software ecosystem (CUDA vs ROCm) is the real moat

## Valuation Benchmarks (updated per analysis)
| Company | Fwd P/E | EV/EBITDA | Revenue Growth | Gross Margin |
|---------|---------|-----------|----------------|--------------|
| NVDA    | 35x     | 28x       | +30%           | 76%          |
| AVGO    | 25x     | 20x       | +15%           | 65%          |
| AMD     | 32x     | 25x       | +22%           | 52%          |
| MRVL    | 28x     | 22x       | +18%           | 48%          |

## Macro Sensitivity
- 每 100bp 利率上升 → 科技股估值平均压缩 8-12%
- 半导体行业 beta 对 ISM PMI: ~1.5x
```

### 3.5 校准日志

```jsonl
{"date":"2025-11-15","company":"NVDA","metric":"Q4_DC_revenue","predicted":35e9,"actual":38.5e9,"error_pct":-0.091,"analyst_consensus":36e9}
{"date":"2025-11-15","company":"NVDA","metric":"Q4_gross_margin","predicted":0.75,"actual":0.765,"error_pct":-0.015,"analyst_consensus":0.752}
{"date":"2025-08-20","company":"NVDA","metric":"Q3_DC_revenue","predicted":31e9,"actual":33.2e9,"error_pct":-0.066,"analyst_consensus":32e9}
{"date":"2026-03-18","company":"NVDA","metric":"fair_value","predicted":165,"actual":null,"note":"pending 90-day review"}
```

这个日志的用途：
- 定期跑校准分析："我预测 65 分以上（CANDIDATE）的股票，90 天后有多少比例跑赢了？"
- 发现系统性偏差："我持续低估 NVDA 的收入 → 下次上调 base case"
- AI 在分析时会被告知这些历史偏差

### 3.6 记忆系统的工具接口

```
Tool: recall_memory
  输入: company (str), memory_type ("company" | "sector" | "patterns" | "calibration")
  输出: 对应记忆文件的内容
  用途: 分析开始前，AI 先调用，看看有没有之前的积累

Tool: save_memory
  输入: company (str), memory_type, content (str)
  输出: 保存成功
  用途: 分析完成后，AI 总结关键发现并更新记忆文件

Tool: check_calibration
  输入: company (str, optional)
  输出: 历史预测 vs 实际的统计摘要
  用途: AI 在设定假设前，先看看自己过去预测这家公司的准确度
```

### 3.7 记忆在分析流程中的位置

```
1. 用户输入 "分析 NVDA"
2. AI 调用 recall_memory("NVDA", "company") → 读取之前的分析记录
3. AI 调用 recall_memory("semiconductors", "sector") → 读取行业认知
4. AI 调用 check_calibration("NVDA") → 看到"我一直低估 DC revenue 6-9%"
5. AI 带着这些上下文开始新一轮研究
6. AI 填入 DCF 假设时，会注意到"上次低估了，这次 base case 上调 5%"
7. 分析完成 → AI 调用 save_memory 更新公司记忆
8. 90 天后 → outcome 数据自动写入 calibration log
```

---

## 4. Skills 架构：一切分析能力都是插件

### 4.1 核心原则

IRIS 的核心不知道 DCF 是什么，不知道 comps 是什么。它只知道：
- 我有一些 Skills（文件夹）
- 每个 Skill 提供一些工具（tools.py）和一段说明（SKILL.md）
- AI 自己判断什么时候用哪个 Skill

**添加新能力 = 添加一个文件夹。不改核心代码。**

### 4.2 Skill 文件夹结构

```
skills/
├── dcf/                      ← 第一个 skill：DCF 估值
│   ├── SKILL.md              ← 告诉 AI 什么时候用、怎么思考
│   ├── tools.py              ← build_dcf() + get_comps()
│   └── config.yaml           ← 默认参数（wacc 范围等）
│
├── hypothesis/               ← 结构化研究 skill
│   ├── SKILL.md
│   └── tools.py              ← extract_observation, create_hypothesis, add_evidence_card
│
├── future examples (drop in when needed):
│   ├── sotp/                 ← 分部加总估值（Berkshire, Sony）
│   ├── real_options/         ← 实物期权（biotech 管线, Tesla FSD）
│   ├── distressed/           ← 困境估值（liquidation value）
│   ├── sector_semicon/       ← 半导体行业知识（只有 SKILL.md，没有新工具）
│   └── report_generator/     ← 把分析结果变成 PDF
```

### 4.3 Skill Loader 工作方式

```python
# core/skill_loader.py

def load_skills(skills_dir: str) -> tuple[list[Tool], str]:
    """
    Scan skills/ folder.
    Returns: (all tools from all skills, combined SKILL.md text for system prompt)
    """
    all_tools = []
    soul_fragments = []
    
    for skill_path in sorted(Path(skills_dir).iterdir()):
        if not skill_path.is_dir():
            continue
        
        # SKILL.md → appended to system prompt
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            soul_fragments.append(skill_md.read_text())
        
        # tools.py → register tools
        tools_module = skill_path / "tools.py"
        if tools_module.exists():
            module = import_from_path(tools_module)
            if hasattr(module, "TOOLS"):
                all_tools.extend(module.TOOLS)
        
        # config.yaml → load skill-specific config
        config_file = skill_path / "config.yaml"
        if config_file.exists():
            register_skill_config(skill_path.name, yaml.safe_load(config_file.read_text()))
    
    return all_tools, "\n\n---\n\n".join(soul_fragments)
```

AI 看到的 system prompt = `soul/*.md`（核心哲学）+ 所有 `skills/*/SKILL.md`（能力说明）。

### 4.4 DCF Skill 详细设计

```
skills/dcf/SKILL.md 的内容（告诉 AI 怎么用这个 skill）:
```

```markdown
# DCF Valuation Skill

## When to use
Use this skill when analyzing a company with reasonably predictable cash flows.
This is the default valuation method for most public companies.

## How to think

### 1. Build assumptions
Fill in a JSON of assumptions. You decide:
- How to segment revenue (by product, geography, customer — whatever explains the business best)
- How many years to project (3-5 for stable, 5-7 for high growth)
- Every assumption MUST have a reasoning field explaining why

### 2. Call build_dcf
Code computes: fair value per share + implied multiples + sensitivity table.
You do NOT estimate fair value directly. You estimate the INPUTS. Code does the math.

### 3. Comps cross-check (REQUIRED)
After Round 1, call get_comps. Compare your implied P/E to peers.
If your implied P/E is >50% above/below sector median, you must either:
- Explain why the premium/discount is justified
- Or revise your assumptions and call build_dcf again

### 4. Multiple rounds are expected
Round 1: initial assumptions → Round 2: post-comps revision → done.
Each round is logged. The user sees your revision history and reasons.

## Key constraints
- Terminal growth rate must be < WACC
- Terminal growth should not exceed 4%
- WACC typically 5%-20%; deviations need explanation
- Revenue growth should decelerate over the projection period
  (unless you have strong evidence for S-curve acceleration)
- Every number must cite its source
```

```
skills/dcf/tools.py 导出:
  - build_dcf(assumptions: dict) → fair_value + implied multiples + sensitivity
  - get_comps(ticker: str, peers: list[str]) → peer comparison table

skills/dcf/config.yaml:
  max_projection_years: 10
  terminal_growth_max: 0.04
  wacc_range: [0.05, 0.20]
  comps_outlier_threshold: 0.50
```

### 4.5 Core Tools（不是 Skills，是核心基础设施）

有些工具属于 IRIS 核心，不是 Skill——因为所有 Skills 都可能用到它们：

| Core Tool | 用途 | 属于 |
|-----------|------|------|
| `exa_search` | 搜索网络信息 | 核心：信息收集 |
| `web_fetch` | 抓取网页全文 | 核心：信息收集 |
| `fmp_get_financials` | 拉取财务数据 | 核心：信息收集 |
| `fred_get_macro` | 拉取宏观数据 | 核心：信息收集 |
| `recall_memory` | 读取记忆 | 核心：记忆系统 |
| `save_memory` | 写入记忆 | 核心：记忆系统 |
| `check_calibration` | 校准检查 | 核心：记忆系统 |

**区分标准**：如果删掉这个工具，IRIS 还能运行但能力减弱 → Skill。如果删掉这个工具，IRIS 完全不能工作 → Core。

### 4.6 未来 Skills 示例

**skills/sotp/ — 分部加总估值**
```
SKILL.md: "当公司有多个独立业务线且估值差异大时使用。对每个业务线独立估值后加总。"
tools.py: build_sotp(segments: list[dict]) → sum-of-parts value
适用: Berkshire Hathaway, Sony, Amazon (AWS + Retail + Ads)
```

**skills/real_options/ — 实物期权估值**
```
SKILL.md: "当公司有高度不确定但潜在巨大的期权价值时使用。对不确定业务用概率加权场景估值。"
tools.py: build_option_model(scenarios: list[dict]) → probability-weighted value
适用: Biotech (drug pipeline), Tesla (FSD), early-stage tech
```

**skills/sector_semicon/ — 半导体行业知识（纯知识 skill，无工具）**
```
SKILL.md: "分析半导体公司时的额外关注点：产能利用率、ASP 趋势、design win pipeline、
          库存周期、晶圆代工合作关系。TSMC utilization 是行业领先指标。"
tools.py: (不存在 — 这个 skill 只贡献知识，不贡献工具)
```

**skills/report_pdf/ — PDF 报告生成**
```
SKILL.md: "当用户要求生成报告时使用。"
tools.py: generate_report(analysis_data: dict) → PDF file
```

---

## 5. AI 思考流程（写入 Soul）

Soul 文件是 IRIS 的核心哲学层，独立于任何 Skill。Skill 的 SKILL.md 教 AI 怎么用特定工具，Soul 教 AI 怎么**思考**。

### 5.1 soul/v0.1.md — 投资哲学（保持不变）

已有的内容很好：预期差思维、贝叶斯更新原则、风险定义。

### 5.2 soul/role.md — 行为规范

```markdown
# IRIS Role

You are IRIS, an AI investment analysis system.

Your job: estimate a company's intrinsic value more accurately than the market.
You do this by researching deeply, building models with transparent assumptions,
and cross-checking against market consensus and peer comparisons.

Rules:
- Before each tool call, briefly state what you're doing and why
- Every numerical assumption must have a reasoning field with sources
- If a tool returns an error, read the hint and correct your approach
- Never invent data — every claim must trace to a specific source
- When analysis is complete: state fair value, gap%, key assumptions, key risks
```

### 5.3 soul/analysis_process.md — 分析流程

```markdown
# Analysis Process

## 1. Read memory
Before starting, call recall_memory for:
- The company's history (prior analyses, if any)
- The sector's accumulated knowledge
- Your calibration record (past prediction accuracy)

If prior analysis exists:
- Is the previous thesis still valid?
- Which kill criteria have changed?
- What direction was your prediction bias? (consistently over/under-estimating?)

## 2. Research
Use search and financial data tools. Focus on:
- Recent 1-2 quarters of financial data
- Management earnings call — key phrases and tone shifts
- Competitor developments
- Macro environment changes

Stop searching when you have at least one source supporting each core assumption.
3-5 high-quality sources > 15 mediocre ones.

## 3. Choose and apply the right skill
Based on the company type, pick the appropriate valuation skill:
- Most public companies → DCF skill
- Multi-segment conglomerates → SOTP skill (when available)
- High-uncertainty / option-like value → real options skill (when available)
- If no specialized skill fits, use the best available and explain your reasoning

## 4. Self-check and revise
After first-round output, always do a sanity check:
- Compare implied multiples to peers
- If something looks off, revise assumptions and re-run
- Record every revision and why

## 5. Output
State clearly:
- Fair value per share and current market price
- Gap% — the core signal
- Top 2-3 assumptions with sensitivity
- Where you disagree with consensus and why
- Kill criteria to monitor

## 6. Update memory
After analysis, save to memory:
- This analysis's conclusion and fair value
- Key assumptions with reasoning
- Differences from last analysis
- New patterns or insights discovered
- Open questions for next time
```

### 5.4 soul/self_check.md — 自校验规则

```markdown
# Self-Check Rules

## After any valuation output
- Implied fwd P/E within 0.5x-2.0x of sector median?
- Implied FCF yield > 1%? (below 1% = possibly too optimistic)
- Terminal value < 75% of total value? (above 75% = weak near-term thesis)
- Bull/bear case spread > 30%? (below 30% = scenarios not differentiated enough)

If any check fails, review your assumptions before finalizing.

## Assumption reasonableness
- Revenue growth >50% in any year needs strong evidence
- Gross margin above company's historical peak — be cautious
- Terminal growth should not exceed ~3.5% (long-run GDP + inflation)
- WACC typically 5%-20%
- Growth should decelerate over projection period (unless S-curve evidence)

## vs Consensus
- Always note where you differ from consensus
- If >20% more optimistic: why doesn't the market see this?
- If >20% more pessimistic: what does the market know that you don't?
- "The market is wrong" is valid — but you must explain why
```

---

## 6. 架构总览

### 6.1 三层 + Skills

```
┌───────────────────────────────────────────────────────┐
│ Soul Layer (soul/*.md)                                 │
│ Investment philosophy, behavior rules, analysis process │
│ + auto-loaded SKILL.md from each skill                 │
├───────────────────────────────────────────────────────┤
│ Core Layer (code)                                      │
│ Agent loop, Memory CRUD, Info gathering tools,         │
│ Skill loader, Event system                             │
├───────────────────────────────────────────────────────┤
│ Config Layer (iris_config.yaml)                        │
│ Harness params (max rounds, retry, context limit)      │
│ Memory params (calibration review period)              │
│ + each skill's config.yaml loaded by skill loader      │
├───────────────────────────────────────────────────────┤
│ Skills Layer (skills/*/)                               │
│ DCF, Comps, Hypothesis tracking, SOTP, sector guides...│
│ Each skill = SKILL.md + tools.py + config.yaml         │
│ Drop in a folder → AI can use it next run              │
└───────────────────────────────────────────────────────┘
```

### 6.2 iris_config.yaml（核心配置，不含 skill 配置）

```yaml
memory:
  base_dir: "./memory"
  calibration_review_days: 90

harness:
  max_tool_rounds: 25
  max_retries: 3
  retry_base_delay: 1.0
  context_limit_chars: 300000
  compress_threshold_chars: 2000

skills:
  dir: "./skills"  # skill loader scans this directory
```

每个 skill 的参数在自己的 `skills/xxx/config.yaml` 里，不污染核心配置。

---

## 7. 用户看到什么

### 7.1 分析报告输出

（和之前一样——report 的格式由 skill 决定，不同的 skill 可以有不同的报告格式。DCF skill 产出 fair value + 假设追踪 + comps 对比 + 敏感度。SOTP skill 会产出分部估值表。）

```
═══════════════════════════════════════════════════════
 NVDA — DCF 估值分析 (skill: dcf)
 分析日期: 2026-03-18
═══════════════════════════════════════════════════════

 Fair Value: $165/share
 Market Price: $142/share
 Gap: +16.3% (低估)

 核心假设 (每个都有完整 reasoning trail):
   DC Revenue Growth Y1: +35% [管理层guidance + 供应链 + 校准偏差调整]
   Gross Margin Y1: 74.5% [竞争压力 + 软件mix提升]
   WACC: 12% [beta调整: CUDA护城河降低现金流波动性]

 Comps 交叉验证 (Round 2):
   隐含 fwd P/E: 38x → sector median 28x → 36% premium justified by 2x growth diff
   Round 1 was 45x → revised DC growth Y3-5 down

 敏感度:
   WACC ±1% → $152-$180  |  DC Growth ±10pp → $148-$185

 vs 上次分析 (from memory): Fair Value $158 → $165 (+4.4%)
 校准记录: 过去3次低估DC revenue 6-9%，本次已调整

═══════════════════════════════════════════════════════
```

### 7.2 核心可视化

1. **DCF 瀑布图**：Revenue → Gross Profit → EBIT → FCF → Discounted → Fair Value
2. **假设 vs 历史**：过去 8 季 actual + 未来 5 年 projected
3. **敏感度热力图**：WACC × Growth → Fair Value 矩阵
4. **Comps 散点图**：P/E vs Growth，标出目标和同行
5. **记忆时间线**：历次分析的 fair value 变化 + 当时市价

---

## 8. 进化机制

### 8.1 什么能学（通过记忆系统，不改代码）

| 可学习的 | 学习信号 | 存储位置 |
|----------|----------|----------|
| 对某公司预测的偏差方向 | calibration_log vs actual | memory/companies/ |
| 行业估值 benchmark | 多次分析后的均值 | memory/sectors/ |
| 管理层 guidance 可信度 | guidance vs actual 历史 | memory/companies/ |
| 有效的搜索策略 | 哪些来源 → 更准确的预测 | memory/patterns/ |

### 8.2 什么不能学（Invariants）

| 不可变的 | 原因 |
|----------|------|
| 各 Skill 内的数学公式 | 数学不变（DCF公式、期权定价公式等） |
| 每个假设必须有 reasoning | 透明性纪律 |
| Comps/sanity check 必须做 | 防止脱离现实 |
| 不编造数据 | 基本诚信 |

### 8.3 进化流程

```
每 90 天（或每次新财报后）:
1. 自动拉取 actual 数据 → 写入 calibration_log
2. AI 对比预测 vs actual → 更新公司记忆
3. 如果系统性偏差（连续 3 次同方向 >10%）:
   → calibration note 写入记忆，下次分析时 AI 自动读取并调整
4. 如果某个 Skill 的 SKILL.md 规则被反复 [DEVIATION]:
   → 提示用户更新该 Skill 的 SKILL.md
5. 如果发现需要新能力（如某类公司现有 Skill 无法分析）:
   → 提示用户考虑添加新 Skill
```

---

## 9. 实施路线图 — 映射到现有代码

### 当前代码状态

```
iris/
├── core/
│   ├── config.py          ✓ yaml loader 已实现，需改 load_soul() 为目录扫描
│   ├── harness.py         ✓ Agent loop 完整（phase、retry、parallel、abort、steering）
│   ├── invariants.py      ✗ 死代码 — harness 不再使用，删除
│   └── schemas.py         △ 保留 Observation/Hypothesis/EvidenceCard，其余随 skill 迁移
├── guards/
│   └── guards.py          ✗ 死代码，删除整个目录
├── llm/
│   ├── base.py            ✓ 完成
│   └── openai_client.py   ✓ 完成（含 streaming）
├── tools/
│   ├── base.py            ✓ TOOL_PHASES 已有，需改为动态注册
│   ├── search.py          ✓ exa_search + web_fetch 已实现
│   ├── financials.py      ✓ fmp + fred 已实现
│   ├── knowledge.py       △ 迁移到 skills/hypothesis/，删除 run_valuation + compute_trade_score
│   └── retrieval.py       ✓ SQLiteRetriever 完成
├── soul/                  △ 需重写 role.md + analysis_guide.md
├── iris_config.yaml       △ 精简：只留 harness + memory 配置
├── main.py                △ 重构为 skill loader 模式
└── tests/                 △ 随代码变化更新
```

### Phase 0: 核心重构

| 任务 | 文件 | 具体变更 |
|------|------|---------|
| Skill Loader | 新建 `core/skill_loader.py` | 扫描 `skills/`，加载 SKILL.md + tools.py + config.yaml |
| 重构 main.py | `main.py` | 用 skill_loader 替代手动工具注册 |
| 精简 config | `iris_config.yaml` | 删除 scoring/evidence/constraints 段（迁入 skill config） |
| 动态 load_soul | `core/config.py` | `load_soul()` 改为 `sorted(soul_dir.glob("*.md"))` |
| 动态 TOOL_PHASES | `tools/base.py` | Core tools 注册 phase；skill_loader 合并 skill 的 phase 声明 |
| Memory 工具 | 新建 `tools/memory.py` | `recall_memory()`, `save_memory()`, `check_calibration()` |
| Memory 目录 | 新建 `memory/{companies,sectors,patterns,calibration}/` | 空目录 + .gitkeep |
| 删除死代码 | 删 `guards/`, `core/invariants.py` | 不再使用 |

**重构后 main.py 核心逻辑**：
```python
from core.skill_loader import load_skills
core_tools = [search, web_fetch, fmp, fred] + memory_tools
skill_tools, skill_soul = load_skills("./skills")
harness = Harness(tools=core_tools + skill_tools, soul=base_soul + skill_soul)
```

### Phase 1: DCF Skill

| 文件 | 内容 |
|------|------|
| `skills/dcf/SKILL.md` | 何时使用 DCF、假设自由度、comps 必须做、自校验规则 |
| `skills/dcf/tools.py` | `build_dcf(assumptions)` → fair value + implied multiples + sensitivity |
| | `get_comps(ticker, peers)` → 同行倍数对比表 |
| `skills/dcf/config.yaml` | `wacc_range: [0.05, 0.20]`, `terminal_growth_max: 0.04`, `comps_outlier_threshold: 0.50` |
| `skills/dcf/config.yaml` → phases | `evaluate: [build_dcf, get_comps]` |

### Phase 2: Hypothesis Tracking Skill

| 文件 | 内容 |
|------|------|
| `skills/hypothesis/SKILL.md` | 贝叶斯更新原则、证据评估标准 |
| `skills/hypothesis/tools.py` | 从 `tools/knowledge.py` 迁移全部函数 |
| `skills/hypothesis/config.yaml` | `scaling_factor: 10`, `direction_map`, `min_evidence_count: 3` |

迁移后删除 `tools/knowledge.py`。

### Phase 3: Soul 更新

| 文件 | 变更 |
|------|------|
| `soul/role.md` | 重写：skill-aware，AI 自选分析方法 |
| `soul/analysis_process.md` | 新写：读记忆 → 研究 → 选 skill → 估值 → sanity check → 存记忆 |
| `soul/self_check.md` | 新写：通用自校验规则（skill 特定的在 SKILL.md 里） |
| 删除 `soul/analysis_guide.md` | 被新文件替代 |

### Phase 4+: 扩展

按需添加 skill 文件夹，不改核心代码：
- `skills/report_pdf/` — 报告生成
- `skills/sotp/` — 分部加总估值
- `skills/sector_semicon/` — 半导体行业知识（纯 SKILL.md）
- `skills/position_sizing/` — 仓位管理
- `skills/technical/` — 技术面辅助
- `skills/execution/` — 自动交易（连接 broker API）

---

## 10. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| DCF 是 Skill，不是核心 | 所有分析能力都是可插拔的 | 未来要加 SOTP、Real Options 等，不能每次改核心 |
| AI 自由决定假设结构 | 不预设 segment 模板 | 每家公司不一样，固定模板限制分析质量 |
| Skill = SKILL.md + tools.py + config.yaml | 标准化的插件格式 | 参考 Anthropic Skills 模式，简单可扩展 |
| 核心只做：agent loop + memory + info gathering | 最小核心原则 | 核心越薄，扩展越灵活 |
| 记忆用 Markdown 文件 | 不用 vector DB（暂时） | 简单、可读、可手动编辑 |
| 校准日志用 JSONL | 结构化追踪预测准确度 | 方便程序处理和统计 |
| 仓位/择时/交易是 future skill | 不是"不做"，是"现在不做" | 架构已支持，添加文件夹即可 |
| Skill 可以只有 SKILL.md | 行业知识包不需要新工具 | 有些能力是"知道什么"而不是"能做什么" |
| Phase 定义从硬编码改为动态注册 | Skill 声明自己工具的 phase | 新 skill 不需要改 tools/base.py |
