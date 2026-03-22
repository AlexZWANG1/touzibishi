# 任务：为 IRIS 投研Agent系统设计 deep_research Skill

## 你的角色
你是一个高级AI系统设计师。你需要为一个已有的二级市场投研Agent系统（IRIS）设计一个新的 `deep_research` Skill。这个Skill的核心产出是 **SKILL.md**（研究方法论prompt指令），不需要创建新的工具(tool)。

---

## IRIS 系统架构概述

IRIS 是一个基于 OpenAI GPT 的投研Agent，采用 harness 循环架构（不是pipeline）。核心组件：

- **Harness**: Agent控制循环，管理budget（max 25轮、60次tool call、480秒）、loop detection、context压缩
- **Soul**: system prompt，由 `soul/*.md` + 所有Skill的 `SKILL.md` 拼接而成
- **Skills**: 模块化能力单元，每个Skill包含 SKILL.md + config.yaml + tools.py
- **Tools**: Agent可调用的工具函数

### Skill 加载机制

```
skill_loader.load_skills()
  → 按字母序遍历 skills/ 下每个文件夹
  → 读 SKILL.md → 拼接进 system prompt (soul)
  → 读 config.yaml → 存入 _skill_configs 字典
  → 调 tools.py 的 register(context) → 收集 Tool 对象
  → 返回 (all_tools, combined_soul)
```

SKILL.md 的内容会直接成为 system prompt 的一部分，Agent每次LLM调用都带着这些指令。

### 现有 Soul（system prompt 基础）

```markdown
# IRIS

You are IRIS — an AI investment analyst that combines deep research, valuation modeling,
trading judgment, and self-learning from outcomes.

## Iron Rules
1. Never invent data. Every claim must trace to a specific source.
2. Learn from facts, not prices. Revenue, margins, CapEx — verifiable. Stock price = noise.
3. Kill criteria are non-negotiable. Triggered = exit.
4. Recommend, don't execute. Human decides.
5. Mark deviations with [DEVIATION] tag.

## Investment Philosophy
We look for companies the market temporarily misunderstands but whose fundamental logic is clear.
Edge is depth, not speed:
- Market hasn't grasped magnitude of structural change
- Short-term fears obscure long-term compounding power
- Industry noise mistaken for fundamental deterioration

Evidence follows Bayesian principles: high-quality = primary-source + independent + surprising.
Risk = P(permanent capital loss) × magnitude. Volatility is NOT risk.
```

---

## 现有 Skill 列表（供参考，不要重复）

### 1. DCF Skill
- **SKILL.md**: 何时用DCF、如何构建假设、交叉验证implied multiples
- **Tools**: `build_dcf`（完整DCF引擎）, `get_comps`（同业对比）

### 2. Hypothesis Skill
- **SKILL.md**: 假设追踪框架，3-6个driver，kill criteria，贝叶斯置信度更新
- **Tools**: `create_hypothesis`（创建投资假设）, `add_evidence_card`（添加证据卡片）

### 3. Trading Skill
- **SKILL.md**: 交易判断原则，安全边际，仓位管理
- **Tools**: `generate_trade_signal`, `get_portfolio`, `run_attribution`

### 4. Valuation Skill
- **SKILL.md**: 统一估值入口，mode=dcf|comps|full
- **Tools**: `valuation`（wrapper）

---

## 所有可用工具（deep_research 应复用这些，不要造新的）

**搜索与信息获取：**
- `exa_search` — 语义搜索（Exa API），返回标题、URL、摘要、高亮
- `web_fetch` — 抓取任意URL转markdown（Jina Reader）

**财务数据：**
- `financials` — 结构化财务数据（FMP + yfinance fallback）：利润表、资产负债表、现金流量表、公司概况、财务比率
- `quote` — 实时股票行情 + 关键指标
- `history` — 历史OHLCV数据
- `macro` — 宏观经济数据（FRED）

**分析工具：**
- `create_hypothesis` — 创建投资假设（3-6个driver + kill criteria）
- `add_evidence_card` — 贝叶斯证据更新
- `build_dcf` — DCF估值模型
- `get_comps` — 同业对比
- `valuation` — 统一估值入口

**记忆与知识：**
- `remember` — 保存关键发现到持久记忆
- `recall` — 检索历史记忆
- `search_knowledge` / `search_documents` — 搜索用户上传的文档

---

## 用户的研究方法论（必须完整融入 SKILL.md）

以下是用户多年投研实践总结的思维方式，这是 deep_research Skill 的灵魂：

### 核心原则

1. **从产品和技术出发，不从概念出发**
   - 先看具体的公司在做什么产品、用什么技术、解决什么问题
   - 从各种产品的例子里出发，得到实际的感觉，而不是虚无的分析
   - 确保了解各类玩家同和不同的差异，然后从中提炼，判断市场趋势

2. **每一个判断都要落到底层**
   - 像产品经理一样理解产品：每一步怎么做的、难点在哪、核心概念是什么
   - 不能解决的痛点和反馈是什么？未来可能需要迭代的功能是什么？
   - 每个产品细节都要落实到客户场景、客户反馈中
   - 比如"快"——快了多少？具体的指标差了多少？不是笼统概念

3. **第一性原理思考**
   - 技术壁垒要追问到底：是程序员写的代码？数据积累？人才密度？工程堆叠？规模效应？
   - 这个解决问题的要素是稀缺的吗？
   - 云厂商能不能做到？企业会不会因为利益原因必须采纳？

4. **收集事实，但更重要的是从事实中提炼洞见**
   - 需要大量Facts，但不能陷在Facts里
   - 更重要的是透过现象看本质
   - 找到不同概念背后的共同点
   - 行业分析核心是看壁垒——壁垒决定格局

5. **证据驱动，反面验证**
   - 寻找尽可能多的证据，无论学术的、业界的
   - 仔细研究公司的产品技术文档和手册
   - 仔细看社区Reddit的真实反馈
   - 捕捉最前沿的行业信号
   - 不断论证反思
   - 不仅有定性分析，更需要定量佐证：市场增速？多少客户了？

6. **表达要求**
   - 讲人话，避免Jargon堆叠
   - 如果有jargon，必须说清楚是什么意思
   - 不要停留在表面定义，要融会贯通
   - 对标 Ben Thompson、Eugene Wei 的分析深度
   - 每个KSF（关键成功要素）怎么达成的，技术难点是什么

---

## 你需要产出的文件

### 1. `skills/deep_research/SKILL.md`

这是核心交付物。要求：

- **长度控制**：1500-2500字（中文）。太短没有指导力，太长浪费system prompt token
- **不要写成教科书**：写成Agent可以直接执行的操作指令
- **融合赛道研究和公司研究**：不分"赛道模式"和"公司模式"，研究赛道必然落到公司
- **明确调用哪些现有工具**：在具体步骤中指出用 `exa_search`、`web_fetch`、`financials` 等
- **包含信息分层标注**：Facts / Views / Impact 三层
- **包含来源标注规范**
- **包含反面证据要求**
- **包含产出格式要求**（写作风格、断言强度匹配证据）
- **包含自检清单**
- **用户的方法论要自然融入，不要单独列一节"用户方法论"**

### 2. `skills/deep_research/config.yaml`

极简配置：
```yaml
name: deep_research
version: "0.1"
```
如果有必要加参数（如最少信息源数量），加上。但不要过度设计。

### 3. `skills/deep_research/tools.py`

空壳，不注册任何新工具：
```python
def register(context: dict) -> list:
    return []
```

### 4. 在 `iris_config.yaml` 中的注册方式（说明即可，不需要改文件）

告诉我应该在 modes.analysis.skills 列表中加入 `deep_research`。

---

## 质量标准

1. SKILL.md 读起来应该像一个资深分析师在教新人怎么做研究，而不是一份产品文档
2. 每个指令都应该是可执行的（Agent看了知道具体做什么），而不是泛泛的原则
3. 要和现有的 role.md（Investment Philosophy）互补而不是重复
4. 特别注意：用户的方法论强调"从具体产品/公司/技术出发"——这和很多投研报告"先讲宏观再讲行业再讲公司"的自上而下顺序是不同的，要体现这个差异
5. SKILL.md中涉及的工具调用要准确——只用上面列出的工具名，不要编造不存在的工具

---

## 参考：现有 SKILL.md 的风格

以下是现有Skill的写法风格，保持一致：

**DCF Skill（简洁指令型）：**
```markdown
# DCF Valuation Skill

## When DCF works well
- Mature companies with stable or steadily growing revenue
- Recurring revenue models (SaaS, subscriptions)

## Building good assumptions
1. Break revenue into segments with individual growth trajectories
2. Use historical margins as anchors, adjust for thesis-specific views
3. WACC from CAPM, sanity-checked against peers

## After building a DCF
Always cross-check implied multiples against peer actuals via get_comps.
```

**Hypothesis Skill（约束型）：**
```markdown
# Hypothesis Tracking Skill

## How to think
1. Form an initial thesis for the target company
2. Define 3-6 drivers and explicit kill criteria
3. Link each new piece of evidence with add_evidence_card

## Key constraints
- Hypothesis must have 3-6 drivers (not fewer, not more)
- Confidence is 0-100 (50=uncertain, 80=strong, 90+=rare)
```

你的 deep_research SKILL.md 应该比这些更长（因为方法论更复杂），但风格保持一致：简洁、指令化、可执行。
