# IRIS — Intelligent Research & Investment System
## 系统规格说明书 (System Specification Document)
### Version 0.1 MVP · March 2026

---

## 0. 项目背景

### 0.1 任务来源

本项目源自 Lollapalooza Capital AI实习生技术能力专项笔试 **任务二**：「AI 驱动的一二级投研工作流构建与评估」。

任务要求：
- 从一二级投研框架中选择至少3个关键环节进行自动化
- 为每个环节调研并选择最适合的 AI 工具
- 提交《AI 工具选型与评估报告》
- 选择一个前沿赛道执行完整研究分析流程
- 提交《AI 辅助投研报告》（≥1500字）

### 0.2 系统愿景

构建一个 **约束引导的 AI 原生投资系统**（Constraint-Guided AI-Native Investment System），核心理念：

1. **相信模型的推理能力**：不用 LangGraph 等确定性编排框架，采用基于 Loop 的 Harness 系统
2. **Enforce invariants, not implementations**：Python 代码层定义不可违反的约束（风控、schema、可追溯性），不规定 AI 具体怎么分析
3. **方法论指导而非命令**：Soul 文件定义投资哲学和分析框架，AI 默认遵循但可合理偏离
4. **自进化能力**：参考 Karpathy 的 autoresearch 和 ATLAS 的 Adaptive-OPRO，系统可通过市场反馈优化自身参数和分析策略

### 0.3 系统定位——与传统量化的区别

| 维度 | 传统量化 | 本系统 (IRIS) |
|------|----------|---------------|
| 决策来源 | 预定义因子和规则 | AI 在约束内自主推理 |
| Alpha 来源 | 因子发现 | 方法论约束设计 + AI 推理质量 + 信息优势 |
| 进化方式 | 人工调参、回测、上线 | Adaptive-OPRO 自动进化 prompt 和参数 |
| 信息处理 | 结构化数据为主 | 结构化 + 非结构化（研报、纪要、新闻） |
| 核心loop | 因子→信号→执行 | 信息→推理→假说→验证→决策 |

### 0.4 核心参考系统与文献

| 项目/文献 | 核心借鉴 |
|-----------|----------|
| NanoClaw | 极简 Harness 哲学：~500行核心代码，完全可审计，Skills 扩展机制 |
| OpenAI Harness Engineering | Enforce invariants not implementations；自定义 linter error 即 remediation instruction |
| ATLAS (alphaXiv 2510.15949) | Adaptive-OPRO：通过市场反馈进化 prompt；25个 agent 4层架构；达尔文权重机制 |
| Karpathy autoresearch | Agent Loop：假说→实验→评估→keep or revert；Git 作为版本控制记忆 |
| Anthropic Building Effective Agents | Agent = LLM + tools in a loop；渐进式自主；做最简单的可行方案 |
| Anthropic Effective Context Engineering | 混合策略：预加载 + just-in-time 检索；渐进式信息披露 |
| Darwin Gödel Machine | 达尔文进化 + 经验验证：organism + evaluator + mutator |

---

## 1. 系统架构总览

### 1.1 四层约束框架

系统的核心设计原则是 **分层信任**：不同层面的规则有不同的刚性程度。

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1：Python 硬约束（Invariants）                     │
│  风控规则 / Schema 验证 / 可追溯性要求                      │
│  ⚡ 永远不变 · AI 不能碰 · 代码机械式强制执行                │
├─────────────────────────────────────────────────────────┤
│  Layer 2：Soul 文件（Investment Methodology）              │
│  估值方法偏好 / 分析权重逻辑 / 贝叶斯更新原则               │
│  📌 AI 默认遵循 · 可偏离但必须在 reasoning chain 中解释     │
│  🔒 进化需人工审批                                        │
├─────────────────────────────────────────────────────────┤
│  Layer 3：可进化区域（Evolvable Parameters & Prompts）     │
│  3A: 数值参数（置信度阈值、权重比例、scaling factors）       │
│  3B: Analysis Prompts（公司研究思考框架、风险分析角度）      │
│  🔄 Adaptive-OPRO 机制 · keep or revert · Git 版本控制    │
├─────────────────────────────────────────────────────────┤
│  Layer 4：AI 完全自由区域                                  │
│  具体假设数字 / 公司选择 / 叙事措辞 / 搜索策略 / 证据解读   │
│  🧠 这就是 intelligence 和 alpha 的来源                    │
└─────────────────────────────────────────────────────────┘
```

#### Layer 1 详细定义：Python 硬约束

这些约束跟投资观点无关，是风控和系统完整性保障。AI 输出必须通过所有检查，否则被 reject 并要求修正。

```python
INVARIANTS = {
    # 风控
    "max_single_position": 0.15,        # 单标的仓位上限 15%
    "stop_loss_trigger": -0.20,         # 跌 20% 触发强制 review
    "max_sector_concentration": 0.40,   # 单行业集中度上限 40%
    
    # Schema 完整性
    "every_conclusion_needs_reasoning_chain": True,
    "every_assumption_needs_source": True,
    "every_hypothesis_needs_kill_criteria": True,
    "confidence_range": (0, 100),
    
    # 可追溯性
    "every_decision_needs_audit_trail": True,
    "every_belief_update_needs_log": True,
}
```

#### Layer 2 详细定义：Soul 文件

Soul 文件是 Markdown 格式，注入到 system prompt。内容包含投资方法论的 **第一性原理推导**（不是规则清单）。

关键原则：**写推导过程，不写规则。** AI 理解 "Why" 远胜于理解 "What"。

Soul 文件的结构框架（具体内容待填充）：

```markdown
# IRIS Soul File v0.1

## 投资哲学（WHY we invest this way）
[待定：核心投资信念的推导]

## 分析框架（HOW we analyze）
### 估值方法选择指引
- [待定：什么情况用什么估值方法，以及为什么]
- AI 可以使用 Anthropic Skills 进行具体估值计算

### 分析维度与权重逻辑
- [待定：基本面/技术面/情绪面的关系推导]

### 贝叶斯更新原则
- 每条新信息都是证据
- 先问：如果假说成立，看到这个证据的概率是多少？
- 再问：如果假说不成立呢？
- 用简化的 delta-based 更新而非精确贝叶斯公式

## 风险管理原则
- [待定：风险评估的思考框架]

## 偏离规则
- 当 AI 认为 Soul 文件的指导不适用于当前情景时
- 必须在 reasoning_chain 中明确标注 [DEVIATION]
- 必须解释为什么偏离、预期什么后果
```

#### Layer 3 详细定义：可进化区域

**3A：数值参数**

```python
EVOLVABLE_PARAMS = {
    "confidence_threshold_to_act": 65,      # Trade Score 多高才出手
    "belief_update_scaling_factor": 10,     # 置信度更新的 scaling
    "news_recency_weight": 0.8,            # 近期信息的权重偏好
    "rebalance_review_days": 7,            # 多久做一次 portfolio review
    "min_evidence_count_for_action": 3,    # 至少多少条证据才能行动
    
    # Trade Score 权重
    "weight_fundamental_quality": 0.25,
    "weight_valuation_gap": 0.25,
    "weight_belief_confidence": 0.25,
    "weight_catalyst_timing": 0.15,
    "weight_risk_penalty": 0.10,
}
```

**3B：Analysis Prompts**（示例，具体内容待设计）

```markdown
# company_research_prompt.md
当分析一家公司时，按以下顺序思考：
1. 这家公司解决什么问题？这个问题有多大？
2. 它的护城河是什么？护城河在加深还是变浅？
3. 管理层有没有 skin in the game？
4. 单位经济模型是否健康？
5. 当前估值隐含了什么假设？这些假设合理吗？
```

#### Layer 4：AI 自由区域

以下事项完全由 AI 自主判断，系统不做任何限制：

- 选择研究哪家公司
- 估值模型中的具体假设数字（增长率、折现率等）
- 如何措辞投资假说
- 信息检索的具体搜索策略
- 哪些信息重要哪些可以忽略
- Bull case 和 Bear case 的具体叙事
- Evidence card 中 direction/reliability/independence 的具体判断

### 1.2 Harness 核心架构

```
┌──────────────────────────────────────────────┐
│                 Main Loop                     │
│                                               │
│   while True:                                 │
│     1. Load context (memory + knowledge)      │
│     2. Determine current task                 │
│     3. Call LLM with Soul + Schema + Task     │
│     4. Parse & validate output (Pydantic)     │
│     5. If validation fails → error feedback   │
│        → retry with remediation instruction   │
│     6. If validation passes → execute action  │
│     7. Store results → update memory          │
│     8. Check if loop should continue          │
│                                               │
│   Tools available via MCP:                    │
│     - Web search (Perplexity)                 │
│     - Financial data (FMP, FRED)              │
│     - Knowledge base read/write               │
│     - Anthropic Skills (估值计算等)             │
│                                               │
│   Invariant Checker runs after every output   │
└──────────────────────────────────────────────┘
```

**不使用 LangGraph/LangChain/LlamaIndex 的理由**：

1. **确定性太强**：LangGraph 把 workflow 硬编码成 DAG，但真实投资分析是非线性的——分析财务时可能突然发现宏观风险，需要跳回重新评估
2. **透明性**：核心 loop 代码 ~300行 Python，任何人（或 AI）都能 8 分钟读完。框架会引入大量你不需要的抽象层
3. **AI-native 哲学**：参考 NanoClaw——系统本身应该足够简单，AI 可以理解、修改、扩展它
4. **Harness Engineering 原则**：OpenAI 的实践表明，约束应该是机械式强制执行的（linter/test），而不是靠框架的流程编排

---

## 2. 投资决策链——四模块设计

### 2.0 数据流总览

```
原始材料（手动输入 / Perplexity 搜索 / 金融 API）
        │
        ▼
   ┌──────────┐
   │  OBSERVE  │  AI 提取 Observations → Python 验证 Schema → SQLite 存储
   └────┬──────┘
        │ List[Observation]
        ▼
   ┌──────────┐
   │  BELIEVE  │  AI 评判 Evidence → Python 算 delta → 更新 Confidence
   └────┬──────┘
        │ Hypothesis (with updated confidence)
        ▼
   ┌──────────┐
   │  VALUE    │  AI 做估值推理（via Skills）→ Python 验证格式 → 算 Trade Score
   └────┬──────┘
        │ TradeScore + ValuationOutput
        ▼
   ┌──────────┐
   │  CHECK    │  Python 硬约束门槛 → 生成 Audit Trail → 输出最终建议
   └──────────┘
        │
        ▼
   最终输出：结构化投资建议 + 完整审计日志
```

### 2.1 模块 A：OBSERVE

**职责**：吃原始材料，吐结构化观察（Observation）

**对应原始设计**：Step 1 (Collect) + Step 2 (Observation Extraction)

#### 输入
- 手动输入的文档（财报、研报、纪要 PDF/文本）
- Perplexity API 搜索结果
- FMP/FRED API 结构化数据

#### 输出 Schema

```python
class Observation(BaseModel):
    id: str                                     # 唯一标识
    subject: str                                # 标的/主题，如 "NVDA"
    claim: str                                  # 核心论断
    time: datetime                              # 信息时间
    source: str                                 # 来源文档/URL
    fact_or_view: Literal["fact", "view"]       # 事实 vs 观点
    relevance: float                            # 0-1, AI 判断
    citation: str                               # 原文引用
    
    # Metadata
    extracted_at: datetime
    extracted_by: str                           # model version
```

#### AI 与 Python 分工

| 谁做 | 做什么 |
|------|--------|
| AI | 读材料、提取 observations、判断 fact_or_view、评估 relevance |
| Python | 验证 schema 完整性、去重、存入 SQLite |

#### MVP 简化

- **不做自动抓取**：材料来源是手动喂入或通过搜索工具获取
- **不做复杂的信息源质量评估**：relevance 由 AI 直接判断
- 每次分析一家公司时，先搜集材料，跑一次 Observe 模块

#### 示例

输入：NVDA Q4 2026 Earnings Call Transcript

输出：
```json
[
  {
    "id": "obs_001",
    "subject": "NVDA",
    "claim": "管理层将 2026 CAPEX 指引上调 18%，从 $12B 到 $14.2B",
    "time": "2026-02-21",
    "source": "NVDA Q4 2026 Earnings Call Transcript",
    "fact_or_view": "fact",
    "relevance": 0.9,
    "citation": "Jensen Huang: We are raising our capital expenditure guidance..."
  },
  {
    "id": "obs_002",
    "subject": "NVDA",
    "claim": "数据中心收入同比增长 78%，连续第 4 个季度加速",
    "time": "2026-02-21",
    "source": "NVDA Q4 2026 10-Q",
    "fact_or_view": "fact",
    "relevance": 0.95,
    "citation": "Data Center revenue was $XX billion, up 78% year-over-year..."
  }
]
```

---

### 2.2 模块 B：BELIEVE

**职责**：把 Observations 转化为 Evidence Cards，更新 Hypothesis 的置信度

**对应原始设计**：Step 3 (Evidence Card) + Step 4 (Hypothesis & Driver Map) + Step 5 (Belief Update)

#### 核心数据结构

```python
class Driver(BaseModel):
    name: str                                   # 如 "产品可靠性"
    description: str                            # 详细说明
    current_assessment: str                     # AI 当前评估
    evidence_count: int                         # 关联的证据数量

class KillCriterion(BaseModel):
    description: str                            # 如 "核心客户流失超过 20%"
    resolved: bool                              # 是否已被排除
    resolution_evidence: Optional[str]          # 排除的证据

class Hypothesis(BaseModel):
    id: str
    thesis: str                                 # 核心投资假说
    company: str
    timeframe: str                              # 如 "24 months"
    drivers: List[Driver]                       # 关键驱动因素（5-6个上限）
    kill_criteria: List[KillCriterion]          # 否决条件
    confidence: float                           # 当前置信度 0-100
    evidence_log: List[EvidenceCard]            # 所有证据记录
    created_at: datetime
    last_updated: datetime

class EvidenceCard(BaseModel):
    id: str
    observation_id: str                         # 关联的 observation
    direction: Literal["supports", "refutes", "mixed", "neutral"]
    reliability: float                          # 0-1，信源可靠度
    independence: float                         # 0-1，跟已有证据的独立性
    novelty: float                              # 0-1，信息新颖度
    driver_link: str                            # 关联到哪个 driver
    hypothesis_id: str
    reasoning: str                              # AI 必须解释判断理由
    created_at: datetime
```

#### 置信度更新逻辑（简化贝叶斯）

```python
def update_belief(hypothesis: Hypothesis, evidence: EvidenceCard) -> float:
    """
    使用简化的 delta-based 更新，而非精确贝叶斯公式。
    
    设计理由：
    1. 可解释：每次变化都能追溯到具体证据和具体权重
    2. 可调试：每个参数（direction/reliability/independence/novelty）都可检查
    3. 可进化：scaling_factor 是可进化参数
    """
    direction_map = {
        "supports": +1,
        "refutes": -1,
        "mixed": +0.2,    # 混合证据轻微偏正
        "neutral": 0
    }
    
    direction_sign = direction_map[evidence.direction]
    
    delta = (
        direction_sign
        * evidence.reliability
        * evidence.independence
        * evidence.novelty
        * EVOLVABLE_PARAMS["belief_update_scaling_factor"]
    )
    
    new_confidence = max(0, min(100, hypothesis.confidence + delta))
    
    # 审计日志
    log_belief_update(
        hypothesis_id=hypothesis.id,
        evidence_id=evidence.id,
        old_confidence=hypothesis.confidence,
        delta=delta,
        new_confidence=new_confidence,
        reasoning=evidence.reasoning
    )
    
    hypothesis.confidence = new_confidence
    hypothesis.evidence_log.append(evidence)
    hypothesis.last_updated = datetime.now()
    
    return new_confidence
```

#### AI 与 Python 分工

| 谁做 | 做什么 |
|------|--------|
| AI | 生成候选 Hypothesis + Drivers + Kill Criteria |
| AI | 对每条 Observation 生成 Evidence Card（判断 direction/reliability/independence/novelty） |
| AI | 提供每个判断的 reasoning |
| Python | 验证 Evidence Card schema |
| Python | 执行 update_belief 数学计算 |
| Python | 写审计日志 |
| Python | 检查 kill criteria 是否被触发 |

#### Hypothesis & Driver Map 的结构

结构写死在 Python（schema），内容由 AI 生成：

```
Hypothesis: "公司 X 将在未来 24 个月完成从 demo 到规模商业化的跃迁。"

Drivers (5-6个上限):
├── 产品可靠性
├── 单位经济性
├── 客户验证进度
├── 产能扩张
├── 竞争壁垒
└── 管理层执行力

Kill Criteria:
├── 核心客户流失超过 20%
├── 单位经济持续恶化 3 个季度
└── 核心技术被开源替代方案超越
```

---

### 2.3 模块 C：VALUE

**职责**：基于置信度和分析，输出估值判断和 Trade Score

**对应原始设计**：Step 6 (Model Router & Valuation) + Step 7 (Trade Score)

#### 估值输出 Schema

```python
class Assumption(BaseModel):
    name: str                                   # 如 "Revenue Growth Rate 2027"
    value: str                                  # 如 "25-30%"
    reasoning: str                              # 为什么选这个数字
    source: str                                 # 数据来源

class ValuationOutput(BaseModel):
    methodology: str                            # DCF / comps / scenario / SOTP / milestone
    methodology_reasoning: str                  # 为什么选这个方法
    fair_value_range: Tuple[float, float]       # 估值区间
    current_price: float
    valuation_gap: float                        # (fair_value_mid - current) / current
    key_assumptions: List[Assumption]
    bull_case: dict                             # {"fair_value": float, "key_assumption": str}
    bear_case: dict                             # {"fair_value": float, "key_assumption": str}
    
    # 使用 Anthropic Skills 完成的具体计算
    skill_used: Optional[str]                   # 如 "dcf_model", "comps_analysis"
    skill_output: Optional[dict]                # Skills 的原始输出
```

#### MVP 估值方法

**关键设计决策：估值计算通过 Anthropic Skills 完成，不在 Python 中写死 DCF 公式。**

理由：
1. 具体用什么估值方法还在设计中（DCF/comps/scenario 等待定）
2. Skills 可以灵活扩展——后续想加新的估值方法只需新增 Skill
3. Python 层只验证输出格式，不规定具体计算方式
4. 这符合 "enforce invariants, not implementations" 原则

AI 的工作流程：
1. 根据公司特征选择估值方法（参考 Soul 文件指导）
2. 调用对应的 Skill 完成估值计算
3. 输出结构化的 ValuationOutput

Python 的工作：
- 验证 ValuationOutput schema 完整性
- 确保 key_assumptions 每条都有 source
- 确保 bull/bear case 都存在

#### Model Router 逻辑（Soul 文件指导，非 Python 硬约束）

```markdown
# 估值方法选择指引（Soul 文件内容）
- 有稳定现金流的成熟公司 → 优先 DCF + comps 交叉验证
- 周期性行业 → comps + 正常化盈利情景
- 分部复杂的集团 → SOTP（分部加总）
- 早期/高不确定性 → 情景分析 / milestone valuation
- 如果 AI 认为以上都不适用，可以使用其他方法但必须解释
```

#### Trade Score 计算

```python
def compute_trade_score(
    hypothesis: Hypothesis,
    valuation: ValuationOutput,
    evidence_cards: List[EvidenceCard]
) -> float:
    """
    综合评分，权重为可进化参数。
    各分项由 AI 评分（0-1），Python 做加权计算。
    """
    # AI 评估各维度（每个都返回 0-1 分值 + reasoning）
    fundamental_quality = ai_assess("fundamental_quality", evidence_cards)
    catalyst_timing = ai_assess("catalyst_timing", evidence_cards)
    risk_penalty = ai_assess("risk_factors", hypothesis.kill_criteria)
    
    # Python 做数学
    score = (
        EVOLVABLE_PARAMS["weight_fundamental_quality"] * fundamental_quality
        + EVOLVABLE_PARAMS["weight_valuation_gap"] * normalize(valuation.valuation_gap)
        + EVOLVABLE_PARAMS["weight_belief_confidence"] * (hypothesis.confidence / 100)
        + EVOLVABLE_PARAMS["weight_catalyst_timing"] * catalyst_timing
        - EVOLVABLE_PARAMS["weight_risk_penalty"] * risk_penalty
    )
    
    return score * 100  # 映射到 0-100
```

#### Trade Score → 行动映射

```
0-49:  WATCH           — 持续关注但不行动
50-64: RESEARCH MORE   — 需要更多证据
65-74: CANDIDATE       — 进入候选池
75-84: INITIATE SMALL  — 可以建小仓位
85+:   HIGH CONVICTION — 高确信度标的
```

---

### 2.4 模块 D：CHECK

**职责**：硬约束门槛检查 + 生成完整审计日志

**对应原始设计**：Step 8 (Portfolio Policy) + Step 9 (Decision Audit)

#### 硬约束门槛（Python 强制执行）

```python
def apply_hard_constraints(
    trade_score: float,
    valuation: Optional[ValuationOutput],
    hypothesis: Hypothesis
) -> float:
    """
    硬约束覆盖 trade_score。
    这些规则 AI 无法绕过。
    """
    constrained_score = trade_score
    reasons = []
    
    # 约束1：没有估值输出，不得超过 CANDIDATE
    if valuation is None:
        constrained_score = min(constrained_score, 64)
        reasons.append("No valuation output → capped at RESEARCH MORE")
    
    # 约束2：证据不足，不得超过 WATCH
    evidence_count = len(hypothesis.evidence_log)
    min_evidence = EVOLVABLE_PARAMS["min_evidence_count_for_action"]
    if evidence_count < min_evidence:
        constrained_score = min(constrained_score, 49)
        reasons.append(f"Only {evidence_count} evidence cards < {min_evidence} → capped at WATCH")
    
    # 约束3：有未排除的 kill criteria，不得 HIGH CONVICTION
    unresolved_kills = [k for k in hypothesis.kill_criteria if not k.resolved]
    if unresolved_kills:
        constrained_score = min(constrained_score, 74)
        reasons.append(f"{len(unresolved_kills)} unresolved kill criteria → capped at CANDIDATE")
    
    # 约束4：bull/bear spread 太小，降级
    if valuation and valuation.bull_case and valuation.bear_case:
        spread = (valuation.bull_case["fair_value"] - valuation.bear_case["fair_value"]) / valuation.current_price
        if spread < 0.30:
            constrained_score = min(constrained_score, 64)
            reasons.append(f"Bull/Bear spread {spread:.0%} < 30% → insufficient margin of safety")
    
    return constrained_score, reasons
```

#### 审计日志生成

```python
class AuditTrail(BaseModel):
    # 输入追溯
    documents_used: List[str]                   # 用了哪些原始文档
    observations_extracted: int                 # 提取了多少条 observation
    
    # 分析追溯
    evidence_supporting: List[str]              # 支持假说的证据摘要
    evidence_refuting: List[str]                # 反驳假说的证据摘要
    belief_trajectory: List[dict]               # 置信度变化轨迹
    
    # 估值追溯
    valuation_method: str
    key_assumptions: List[str]
    
    # 决策追溯
    raw_trade_score: float
    constrained_trade_score: float
    constraint_reasons: List[str]               # 哪些约束触发了
    final_recommendation: str                   # WATCH/RESEARCH/CANDIDATE/INITIATE/HIGH CONVICTION
    
    # 偏离记录
    soul_deviations: List[str]                  # AI 偏离 Soul 文件的记录
    
    # 元信息
    model_used: str
    timestamp: datetime
    total_llm_calls: int
    total_cost_usd: float
```

#### Portfolio Policy（MVP 简化版）

MVP 阶段只做单标的分析，不做组合优化。硬约束直接在 Check 模块中执行：

```python
PORTFOLIO_CONSTRAINTS = {
    "max_single_position": 0.15,        # 单标的 ≤ 15%
    "max_sector_concentration": 0.40,   # 单行业 ≤ 40%
    "max_total_exposure": 1.0,          # 总暴露 ≤ 100%（不加杠杆）
}
```

组合优化（相关性分析、风险预算等）留到 V2。

---

## 3. 自进化机制

### 3.1 设计哲学

参考 ATLAS 的 Adaptive-OPRO + Karpathy 的 autoresearch：

- **Prompt 是权重**：analysis prompt 的措辞直接影响分析质量
- **市场结果是 loss function**：决策的对错通过市场反馈验证
- **进化 = 变异 + 选择**：提出修改假说 → 评估 → keep or revert

### 3.2 评估指标

不能只用收益率（周期太长、噪音太大）。使用复合 proxy 指标：

**主指标：置信度校准度（Calibration Score）**

系统说 70% 置信度，那在所有 70% 置信度的预测中，胜率应该接近 70%。

```python
def calibration_score(predictions: List[Prediction]) -> float:
    """
    把所有预测按置信度分桶（0-20, 20-40, 40-60, 60-80, 80-100）
    每个桶里：actual_win_rate vs predicted_confidence
    差距越小 = 校准越好
    """
    buckets = defaultdict(list)
    for p in predictions:
        bucket = int(p.confidence // 20) * 20
        buckets[bucket].append(p.outcome)  # 1=对, 0=错
    
    total_error = 0
    for bucket, outcomes in buckets.items():
        expected = (bucket + 10) / 100  # 桶中点
        actual = sum(outcomes) / len(outcomes)
        total_error += abs(expected - actual)
    
    return 1 - (total_error / len(buckets))  # 1=完美校准
```

**辅助指标**：
- Reasoning Quality Score：Optimizer Agent (Opus) 对分析报告评分 1-10
- Information Coverage：分析中引用了多少独立信息源
- Prediction Accuracy：最终方向是否正确（longer-term metric）

### 3.3 进化 Loop

```
频率：每周运行一次（周日）

1. 收集本周所有决策记录和市场结果
2. 计算评估指标（calibration + quality + coverage）
3. Optimizer Agent (Claude Opus) 分析：
   - 哪些决策对了？为什么？
   - 哪些决策错了？错在哪里？
   - 置信度校准度如何？
4. Optimizer 提出修改假说（参照 ATLAS 的四部分结构）：
   - Performance Analysis：本周表现瓶颈
   - Proposed Update：具体修改内容
   - Key Improvements：改了什么
   - Expected Impact：预期效果
5. Git 创建新分支，应用修改
6. 回测对比（如果可能）
7. Keep or Revert
8. 记录进化日志（包括失败的变异——防止重复尝试）
```

### 3.4 进化边界控制

```python
EVOLUTION_CONSTRAINTS = {
    "max_param_change_per_iteration": 0.20,     # 单次参数变化 ≤ 20%
    "min_evaluation_window_days": 7,            # 至少 7 天数据才能评估
    "min_sample_size": 5,                       # 至少 5 个决策样本
    "max_consecutive_mutations": 3,             # 连续 3 次变异后稳定 1 周
}
```

### 3.5 进化范围

| 内容 | 进化方式 | 审批 |
|------|----------|------|
| Layer 1 硬约束 | ❌ 不可进化 | — |
| Layer 2 Soul 文件 | AI 提议 → 人工审批 | 必须 |
| Layer 3A 数值参数 | Optimizer 自动 keep/revert | 自动 |
| Layer 3B Analysis Prompt | Adaptive-OPRO 机制 | 自动（但需兼容 schema） |
| Layer 4 AI 自由区域 | 每次推理自然不同 | — |

---

## 4. 技术选型

### 4.1 选型总表

| 层面 | 选择 | 备选（被淘汰） | 选择理由 |
|------|------|----------------|----------|
| **Harness 核心** | 自建 Python Loop (~300行) | LangGraph, LangChain | 完全可控可审计，AI-native 哲学 |
| **LLM (日常分析)** | Claude Sonnet API | GPT-4o | ATLAS 验证、性价比、schema 遵循度高 |
| **LLM (关键决策)** | Claude Opus | GPT-o3 | 关键节点用最强模型 |
| **LLM (进化优化)** | Claude Opus | — | 低频调用，需要最强推理能力 |
| **金融数据** | FMP API + FRED | Finnhub, Alpha Vantage, Bloomberg | 覆盖度 + 成本平衡 |
| **信息搜索** | Perplexity API | Exa AI, Claude Web Search | 金融信息覆盖度好，返回带来源 |
| **短期记忆** | SQLite | PostgreSQL | 极简、无服务器、Python 原生 |
| **长期语义检索** | Qdrant (本地) | Chroma, Pinecone | 语义检索质量好，可本地部署 |
| **版本控制** | Git | — | autoresearch 标准方案 |
| **Schema 验证** | Pydantic | jsonschema | Python 生态标准，错误信息清晰 |
| **贝叶斯引擎** | 自建 Python (~50行) | PyMC, scipy | 逻辑太简单不需要库 |
| **工具连接** | MCP 协议 | 自定义 API wrapper | Anthropic 标准，生态支持好 |
| **估值计算** | Anthropic Skills | 硬编码 Python | 灵活可扩展，不锁死方法论 |

### 4.2 各环节评估标准

#### 环节1：Knowledge Sourcing & Management

**评估维度**：

| 标准 | 权重 | 评估方法 |
|------|------|----------|
| 信息源覆盖度 | 30% | 测试能否获取：财报、研报、新闻、专利、社交媒体 |
| 信息新鲜度 | 20% | 从事件发生到系统获取的延迟 |
| 结构化质量 | 20% | Observation extraction 的准确率（人工抽样验证） |
| API 稳定性 | 15% | 连续 7 天调用成功率 |
| 成本 | 15% | 每月 API 费用控制在合理范围 |

**被淘汰的备选及理由**：

- **Bloomberg Terminal API**：覆盖度最佳但成本过高（$2k+/月），不适合 MVP
- **Alpha Vantage**：免费层够用但数据质量一般，金融数据准确性不足
- **Exa AI**：语义搜索能力强但对金融场景的覆盖不如 Perplexity

#### 环节2：Bayesian Thesis Analysis

**评估维度**：

| 标准 | 权重 | 评估方法 |
|------|------|----------|
| 置信度校准度 | 35% | Calibration Score（见 3.2） |
| 推理可追溯性 | 25% | 每个置信度变化是否可追溯到具体证据 |
| Evidence 判断准确性 | 20% | direction/reliability 的人工抽样验证 |
| 更新速度 | 10% | 从新信息到置信度更新的延迟 |
| 计算正确性 | 10% | delta 计算是否数学正确（单元测试） |

**被淘汰的备选及理由**：

- **PyMC / 概率编程**：对 MVP 场景过于复杂，简化 delta 方法更可解释
- **LangChain 的 Structured Output**：增加不必要的依赖，Pydantic 直接更可控

#### 环节3：Decision Integration & Self-Evolution

**评估维度**：

| 标准 | 权重 | 评估方法 |
|------|------|----------|
| 进化有效性 | 30% | 进化前后的 calibration score 对比 |
| 进化稳定性 | 25% | 是否避免过拟合（连续 revert 率） |
| 审计完整性 | 20% | audit trail 是否覆盖全链路 |
| 成本可控性 | 15% | Opus 调用的月度成本 |
| 版本可追溯 | 10% | Git log 是否清晰记录每次进化 |

**被淘汰的备选及理由**：

- **LangSmith / LangFuse（观测平台）**：增加外部依赖，SQLite + Git 足够 MVP 的追溯需求
- **Weights & Biases（实验追踪）**：对 ML 实验设计的，对 prompt 进化场景太重

---

## 5. 三个投研环节定义

对应笔试要求的"至少选择 3 个关键环节"。

### 环节1：Knowledge Sourcing & Management

**映射关系**：一级市场 Sourcing + 二级市场 Research 的信息获取层

**任务目标**：从多源异构信息中自动提取结构化 Observations，构建可检索的知识库

**输入**：
- 财报/10-K/20-F（PDF/文本）
- Sell-side 研报
- 行业新闻（Perplexity 搜索）
- 宏观经济数据（FRED API）
- 公司基本面数据（FMP API）

**输出**：
- 结构化 Observation 列表（存入 SQLite）
- 可语义检索的知识库（Qdrant 向量索引）

**AI 工具**：Claude Sonnet（extraction） + Perplexity（search） + FMP/FRED（structured data）

### 环节2：Bayesian Thesis Analysis

**映射关系**：一级市场 Analyzing + 二级市场 Research 的深度分析层

**任务目标**：对投资假说进行结构化的置信度分析，基于证据累积更新信念

**输入**：
- Observation 列表（来自环节1）
- 现有 Hypothesis 和 Driver Map

**输出**：
- 更新后的 Hypothesis（含置信度、证据日志）
- Evidence Cards（含 direction/reliability/independence/novelty）
- ValuationOutput（通过 Skills 完成估值计算）
- Trade Score

**AI 工具**：Claude Sonnet（evidence judgment） + Claude Opus（关键决策节点） + Anthropic Skills（估值计算）

### 环节3：Decision Integration & Self-Evolution

**映射关系**：二级市场 Investment 决策 + Monitoring 投后跟踪

**任务目标**：将分析结论落地为可执行建议，并通过市场反馈优化系统

**输入**：
- Trade Score + Hypothesis + ValuationOutput（来自环节2）
- 历史决策记录 + 市场结果

**输出**：
- 约束检查后的最终投资建议
- 完整审计日志
- 进化后的参数/prompt（每周）

**AI 工具**：Claude Opus（Optimizer Agent） + Git（版本控制）

---

## 6. MVP 实现路线图

### Phase 1：搭建骨架（Day 1-2）
- [ ] 实现 Main Loop（Python harness ~300行）
- [ ] 定义所有 Pydantic Schema（Observation, EvidenceCard, Hypothesis, ValuationOutput, AuditTrail）
- [ ] 实现 Invariant Checker
- [ ] 搭建 SQLite 存储层
- [ ] 编写 Soul 文件 v0.1（框架，内容待填充）

### Phase 2：打通链条（Day 2-3）
- [ ] 实现 OBSERVE 模块（材料输入 → Observation 提取）
- [ ] 实现 BELIEVE 模块（Evidence Card 生成 → Belief Update）
- [ ] 实现 VALUE 模块（估值推理 → Trade Score）
- [ ] 实现 CHECK 模块（硬约束 + Audit Trail）
- [ ] 端到端测试：选一家公司跑完整链条

### Phase 3：赛道研究（Day 3）
- [ ] 选择赛道（具身智能 / 商业航天 / AI 制药）
- [ ] 使用系统执行完整研究分析流程
- [ ] 生成《AI 辅助投研报告》

### Phase 4：自进化（如果时间允许）
- [ ] 实现 Optimizer Agent 基础版本
- [ ] 实现参数进化 Loop
- [ ] 跑一次进化 cycle 作为 demo

### 交付物清单
1. 完整项目代码 + README.md
2. 《AI 工具选型与评估报告》
3. 《AI 辅助投研报告》（≥1500字）
4. 设计文档（本 Spec 的精简版）

---

## 7. 关键设计决策记录（ADR）

### ADR-001：不使用 LangGraph 编排
- **状态**：已决定
- **理由**：确定性太强，不适合非线性投资推理。自建 Loop 更灵活、更透明。
- **参考**：NanoClaw 极简哲学、Anthropic "做最简单的可行方案"

### ADR-002：简化贝叶斯而非精确贝叶斯
- **状态**：已决定
- **理由**：精确贝叶斯需要估计准确的 likelihood，在投资场景不现实。Delta-based 方法更可解释、可调试、可进化。
- **参考**：ATLAS 也使用简化的评分机制而非精确概率模型

### ADR-003：估值计算通过 Skills 而非硬编码
- **状态**：已决定
- **理由**：具体估值方法论待定，Skills 可灵活扩展。符合 "enforce invariants, not implementations" 原则。
- **风险**：Skills 的计算质量取决于 LLM 能力。通过 schema 验证和 assumption source 追溯来控制。

### ADR-004：自进化采用 Adaptive-OPRO 模式
- **状态**：已决定
- **理由**：ATLAS 在 378 个交易日内验证了该模式有效（54次修改，16次存活，+22% 回报）。关键是每次修改有透明的 rationale。
- **边界**：参数和 prompt 自动进化，Soul 文件进化需人工审批。

### ADR-005：四层约束框架
- **状态**：已决定
- **理由**：平衡自主性和控制力。参考 Anthropic agent safety framework 的"自主性和人类监督的核心张力"。
- **关键原则**：定义 shape 不定义 content；定义 invariant 不定义 implementation。

### ADR-006（待定）：具体投资方法论
- **状态**：待定
- **影响**：不影响技术架构。方法论内容填入 Soul 文件即可。
- **待决内容**：估值方法偏好、分析维度权重、风险评估框架

### ADR-007（待定）：Analysis Prompt 自进化的审批级别
- **状态**：待定
- **选项 A**：全自动（参照 ATLAS），keep/revert 由回测结果决定
- **选项 B**：AI 提议 + 人工审批（更保守）
- **建议**：MVP 阶段用选项 B（保守），积累足够 track record 后切换到 A

---

## 附录 A：完整 Schema 定义汇总

```python
from pydantic import BaseModel
from typing import List, Literal, Optional, Tuple
from datetime import datetime

# === OBSERVE 模块 ===

class Observation(BaseModel):
    id: str
    subject: str
    claim: str
    time: datetime
    source: str
    fact_or_view: Literal["fact", "view"]
    relevance: float  # 0-1
    citation: str
    extracted_at: datetime
    extracted_by: str

# === BELIEVE 模块 ===

class Driver(BaseModel):
    name: str
    description: str
    current_assessment: str
    evidence_count: int

class KillCriterion(BaseModel):
    description: str
    resolved: bool
    resolution_evidence: Optional[str]

class EvidenceCard(BaseModel):
    id: str
    observation_id: str
    direction: Literal["supports", "refutes", "mixed", "neutral"]
    reliability: float  # 0-1
    independence: float  # 0-1
    novelty: float  # 0-1
    driver_link: str
    hypothesis_id: str
    reasoning: str
    created_at: datetime

class Hypothesis(BaseModel):
    id: str
    thesis: str
    company: str
    timeframe: str
    drivers: List[Driver]
    kill_criteria: List[KillCriterion]
    confidence: float  # 0-100
    evidence_log: List[EvidenceCard]
    created_at: datetime
    last_updated: datetime

# === VALUE 模块 ===

class Assumption(BaseModel):
    name: str
    value: str
    reasoning: str
    source: str

class ValuationOutput(BaseModel):
    methodology: str
    methodology_reasoning: str
    fair_value_range: Tuple[float, float]
    current_price: float
    valuation_gap: float
    key_assumptions: List[Assumption]
    bull_case: dict
    bear_case: dict
    skill_used: Optional[str]
    skill_output: Optional[dict]

# === CHECK 模块 ===

class TradeRecommendation(BaseModel):
    company: str
    hypothesis_id: str
    raw_trade_score: float
    constrained_trade_score: float
    constraint_reasons: List[str]
    recommendation: Literal["WATCH", "RESEARCH_MORE", "CANDIDATE", "INITIATE_SMALL", "HIGH_CONVICTION"]
    valuation: ValuationOutput
    hypothesis: Hypothesis
    audit_trail: "AuditTrail"

class AuditTrail(BaseModel):
    documents_used: List[str]
    observations_extracted: int
    evidence_supporting: List[str]
    evidence_refuting: List[str]
    belief_trajectory: List[dict]
    valuation_method: str
    key_assumptions: List[str]
    raw_trade_score: float
    constrained_trade_score: float
    constraint_reasons: List[str]
    final_recommendation: str
    soul_deviations: List[str]
    model_used: str
    timestamp: datetime
    total_llm_calls: int
    total_cost_usd: float

# === 进化模块 ===

class EvolutionProposal(BaseModel):
    id: str
    timestamp: datetime
    performance_analysis: str
    proposed_update: dict  # 具体修改内容
    key_improvements: List[str]
    expected_impact: str
    backtest_result: Optional[dict]
    status: Literal["proposed", "accepted", "rejected", "reverted"]
    rejection_reason: Optional[str]
```

---

## 附录 B：可进化参数完整列表

```python
EVOLVABLE_PARAMS = {
    # 置信度与行动阈值
    "confidence_threshold_to_act": 65,
    "belief_update_scaling_factor": 10,
    "min_evidence_count_for_action": 3,
    
    # Trade Score 权重
    "weight_fundamental_quality": 0.25,
    "weight_valuation_gap": 0.25,
    "weight_belief_confidence": 0.25,
    "weight_catalyst_timing": 0.15,
    "weight_risk_penalty": 0.10,
    
    # 信息处理
    "news_recency_weight": 0.8,
    "min_source_reliability_threshold": 0.3,
    
    # 进化控制
    "rebalance_review_days": 7,
    "max_param_change_per_iteration": 0.20,
    "min_evaluation_window_days": 7,
    "min_sample_size_for_evolution": 5,
    "max_consecutive_mutations": 3,
}
```

---

## 附录 C：Layer 1 Invariants 完整列表

```python
INVARIANTS = {
    # 风控硬约束
    "max_single_position": 0.15,
    "stop_loss_trigger": -0.20,
    "max_sector_concentration": 0.40,
    "max_total_exposure": 1.0,
    
    # Schema 完整性
    "every_conclusion_needs_reasoning_chain": True,
    "every_assumption_needs_source": True,
    "every_hypothesis_needs_kill_criteria": True,
    "confidence_range": (0, 100),
    "min_drivers_per_hypothesis": 3,
    "max_drivers_per_hypothesis": 6,
    
    # 可追溯性
    "every_decision_needs_audit_trail": True,
    "every_belief_update_needs_log": True,
    "every_valuation_needs_bull_bear_case": True,
    
    # Trade Score 硬门槛
    "no_valuation_cap": 64,           # 没估值 → 最高 RESEARCH MORE
    "low_evidence_cap": 49,           # 证据不足 → 最高 WATCH
    "unresolved_kill_cap": 74,        # 有未排除反例 → 最高 CANDIDATE
    "min_bull_bear_spread": 0.30,     # bull/bear 差距 < 30% → 降级
}
```

---

*本文档为 IRIS 系统的 MVP 规格说明书。具体投资方法论（Soul 文件内容、估值方法选择、分析维度权重等）待后续迭代填充。技术架构和四层约束框架已确定，可作为 Claude Code 开发的参考基准。*
