# IRIS Learning Mode Design Spec

> IRIS 学习模式设计：让 AI 通过结构化复盘积累可复用的过程知识（procedural knowledge），从基于启发式的探索转变为确定性的 solve-verify 循环。

---

## 1. 问题陈述

IRIS 的经验学习系统（FLEX 式三层双区经验库）代码已完整实现（735 行），但从未被使用过。experience_library.json 不存在，prediction_log 9 条记录 actual 全为 null，run_reflection / distill_patterns 从未被调用。

根本原因：
1. 分析模式下 dynamic tool injection 导致经验工具不可见
2. 没有明确的学习流程指令
3. 学习和分析混在一起，没有独立的模式

## 2. 设计目标

- 在 harness 层新增 `mode` 参数，实现分析/学习两种模式的彻底隔离
- 学习模式通过 reflection skill 引导 Agent 执行复盘
- 经验 schema 增加 `methodology` 字段，存储过程知识而非观察感想
- 模式切换只能由人触发，AI 不能自行切换
- 最大化复用现有基础设施：同一个 harness loop、LLM 调用链、事件系统、前端 streaming

## 3. 核心设计决策

### 3.1 为什么分两种模式

分析和学习的运行特征不同：

| 维度 | 分析模式 | 学习模式 |
|------|---------|---------|
| 目标 | 产出投资结论 | 验证过去的预测、积累方法论 |
| 有 ground truth? | 没有 | 有（实际财报） |
| 工具集 | 搜索/财务数据/DCF/假设 | 记忆回忆/经验存取/反思/财务数据 |
| 典型 tool rounds | 10-20 | 20-40（可能遍历多家公司）|
| 产出 | 分析笔记 + hypothesis | 经验条目 + 复盘报告 |

混在一起的问题：Agent 分析时可能被反思工具分心；分析时没有 ground truth 产出的"经验"质量低，会污染经验库。

### 3.2 为什么经验要存方法论（methodology）

受 FLEX 论文启发：经验库应存储"结构化过程知识"（procedural knowledge），而非"我低估了 43pp"这种观察。

观察式经验：Agent 看到"你上次低估了"→ 不知道下次该怎么做 → 只能"多加点" → 启发式。

方法论式经验：Agent 看到"上次用线性外推，错了，下次应该先查 hyperscaler capex 判断是否加速周期"→ 按步骤执行 → 确定性。

### 3.3 为什么给 AI 自由度

- 经验存几条、拆不拆 driver → AI 决定
- 标 warning 还是 golden → AI 决定
- 标 factual 还是 pattern → AI 决定
- methodology 写多细 → AI 决定
- 复盘报告格式 → AI 自由发挥

系统层只做存取和去重，不做行为约束。

### 3.4 学习什么

两种 reward signal：

**主通道：事实偏差（每次财报后）**
- revenue growth 预测 35% vs 实际 78% → 偏差 -43pp
- 可精确计算，不受市场情绪影响，信噪比高
- 1 次就能产出有效经验

**辅通道：交易统计（批量复盘）**
- confidence 校准（HIGH confidence 历史胜率是否真比 MEDIUM 高）
- 过程纪律（thesis broken 是否及时退出）
- 信噪比低，需要 10+ 笔交易的统计样本
- 产出统计性经验，不是单笔归因

### 3.5 模式切换权限

只有人（前端）可以切换模式。AI 在分析模式中不能自行决定"我要去学习"。AI 在学习模式内可以自由决定执行哪个流程。

---

## 4. 架构设计

### 4.1 Mode 切换机制：每个 mode 构建独立的 Harness 实例

当前 `build_harness()` 在 `main.py` 中一次性构建 Harness（固定 tools、soul、config）。mode 的实现方式是：**给 `build_harness()` 加 mode 参数，按 mode 构建不同的 Harness 实例**。不是在 `run()` 里动态切换。

```
用户点「复盘 NVDA」
  → 前端发请求 mode="learning"
  → sessions.py: create_session(mode="learning")
  → build_harness(mode="learning")  ← 构建学习模式专用的 Harness
      → load_soul(file_list=["role.md", "reflection.md"])  ← 只加载指定 soul 文件
      → load_skills(skill_names=["reflection", "experience"])  ← 只加载指定 skills
      → 只注册学习模式的工具集
      → HarnessConfig 使用学习模式的 budget
  → harness.run(message)  ← run() 本身不感知 mode
```

这比在 `run()` 里动态切换更简单：每个 Harness 实例是完全独立的，tools/soul/config 在构建时就固定了。

### 4.2 现有代码的必要改动

**`load_soul()` (iris/core/config.py:65)**：当前 glob 扫描 soul/ 下所有 *.md。需要加 `file_list` 参数：

```python
def load_soul(soul_dir: Path = None, file_list: list[str] = None) -> str:
    soul_dir = soul_dir or Path(__file__).parent.parent / "soul"
    if file_list:
        files = [soul_dir / f for f in file_list if (soul_dir / f).exists()]
    else:
        files = sorted(soul_dir.glob("*.md"))
    parts = [f.read_text(encoding="utf-8") for f in files]
    return "\n\n---\n\n".join(parts) if parts else FALLBACK_SOUL
```

**`load_skills()` (iris/core/skill_loader.py:24)**：当前扫描 skills/ 下所有子目录。需要加 `skill_names` 过滤：

```python
def load_skills(
    skills_dir: str,
    context: dict | None = None,
    skill_names: list[str] | None = None,  # 新增：只加载指定 skills
) -> tuple[list[Tool], str]:
    # ...
    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        if skill_names and skill_dir.name not in skill_names:
            continue  # 跳过不在列表中的 skill
        # ... 原有逻辑
```

**`build_harness()` (iris/main.py:74)**：加 mode 参数，按 mode 从 config 读取不同的 soul_files、skills、tools、budget：

```python
def build_harness(
    db_path: str = None,
    on_event=None,
    streaming: bool = False,
    mode: str = "analysis",  # 新增
) -> tuple[Harness, SQLiteRetriever]:
    cfg = load_config()
    mode_cfg = cfg.get("modes", {}).get(mode, {})
    h = cfg["harness"]
    # mode_cfg 覆盖 harness 默认值
    max_tool_rounds = mode_cfg.get("max_tool_rounds", h.get("max_tool_rounds", 25))
    max_total_tool_calls = mode_cfg.get("max_total_tool_calls", h.get("max_total_tool_calls", 60))
    max_wall_time = mode_cfg.get("max_wall_time_seconds", h.get("max_wall_time_seconds", 480.0))
    # ...

    # Soul: 按 mode 加载指定文件
    soul_file_list = mode_cfg.get("soul_files", None)  # None = 加载全部（向后兼容）
    base_soul = load_soul(file_list=soul_file_list)

    # Skills: 按 mode 加载指定 skills
    skill_name_list = mode_cfg.get("skills", None)  # None = 加载全部
    skill_tools, skill_soul = load_skills(
        skills_dir, context={"retriever": retriever, "mode": mode},
        skill_names=skill_name_list,
    )

    # Tools: 按 mode 过滤（只注册 mode 需要的工具）
    all_candidate_tools = core_tools + memory_tools + skill_tools
    exposed = set(mode_cfg.get("always_exposed_tools", []))
    if exposed:
        all_tools = [t for t in all_candidate_tools if t.schema["function"]["name"] in exposed]
    else:
        all_tools = all_candidate_tools  # 向后兼容：无 mode 配置时全部注册
    # ...
```

关键点：`context={"retriever": retriever, "mode": mode}` 把 mode 传递给 skill tools 的 `register(context)` 函数。这样 `save_experience` 可以通过 `context["mode"]` 感知当前模式。

### 4.3 Config 结构

`iris_config.yaml` 新增 modes 配置块：

```yaml
modes:
  analysis:
    soul_files: [role.md, process.md]
    skills: [hypothesis, dcf, trading]
    tool_injection_mode: "dynamic"
    always_exposed_tools:
      - recall_memory
      - save_memory
      - save_experience
      - memory_search
      - recall_experiences
      - build_dcf
      - get_comps
      - create_hypothesis
      - extract_observation
      - add_evidence_card
      - exa_search
      - web_fetch
      - fmp_get_financials
      - fred_get_macro
      - yf_quote
      - yf_history
    max_tool_rounds: 25
    max_total_tool_calls: 60
    max_wall_time_seconds: 480

  learning:
    soul_files: [role.md, reflection.md]
    skills: [reflection, experience]
    tool_injection_mode: "all"
    always_exposed_tools:
      - recall_memory
      - save_memory
      - recall_experiences
      - save_experience
      - run_reflection
      - distill_patterns
      - fmp_get_financials
      - yf_quote
      - check_calibration
    max_tool_rounds: 40
    max_total_tool_calls: 120
    max_wall_time_seconds: 600
```

关键点：
- 分析模式暴露 `save_experience` 但代码强制不能标 warning/golden（只记录方法论）
- 学习模式不注册 `build_dcf` / `exa_search`（不做新分析）
- 学习模式 `tool_injection_mode: "all"`（工具集已精简到 9 个，不需要动态注入）
- 学习模式 budget 更宽松（40 轮 / 120 次调用 / 10 分钟）
- 分析模式工具列表是完整列表，包含现有 `always_exposed_tools` 中的 `memory_search` 以及所有 skill tools

### 4.4 现有 Soul 文件处理

当前 5 个 soul 文件的去向：

| 现有文件 | analysis 模式 | learning 模式 | 说明 |
|---------|:---:|:---:|------|
| `role.md` | ✅ | ✅ | 两个模式共享身份和投资哲学 |
| `analysis_process.md` → 重命名为 `process.md` | ✅ | ❌ | 分析流程，学习模式不需要 |
| `v0.1.md` | 合并入 `role.md` | - | 解决 DCF 矛盾 |
| `self_check.md` | 关键项合并入 `process.md` | - | 简化 |
| `steering.md` | 删除 | - | 过度分类，模型不需要 |
| `reflection.md`（新增）| ❌ | ✅ | 学习模式专用 |

### 4.5 文件结构

```
新增：
  iris/soul/reflection.md                    ← 学习模式 soul
  iris/skills/reflection/SKILL.md            ← 学习流程指令
  iris/skills/reflection/config.yaml         ← 工具声明

改动：
  iris/core/config.py                        ← load_soul() 加 file_list 参数
  iris/core/skill_loader.py                  ← load_skills() 加 skill_names 过滤
  iris/main.py                               ← build_harness() 加 mode 参数
  iris/iris_config.yaml                      ← 加 modes 配置块
  iris/skills/experience/tools.py            ← methodology 字段 + 分析模式 zone 限制
  iris/backend/sessions.py                   ← create_session 传递 mode
  iris/backend/api.py                        ← start_analysis 端点接受 mode 参数
  iris-frontend/                             ← 加学习模式入口

Soul 文件整理：
  iris/soul/v0.1.md                          ← 合并入 role.md 后删除
  iris/soul/self_check.md                    ← 关键项合并入 process.md 后删除
  iris/soul/steering.md                      ← 删除
  iris/soul/analysis_process.md              ← 重命名为 process.md
```

---

## 5. 经验 Schema

### 5.1 现有 schema vs 升级

现有 `SAVE_EXPERIENCE_SCHEMA`（experience/tools.py:87）的 required 字段：`zone, level, content, companies, confidence`。

升级策略：**在现有 schema 基础上加 `methodology` 字段，保持向后兼容。**

```python
# 现有字段（保留，不改名）
"zone":       {"type": "string", "enum": ["golden", "warning"]}     # 保留
"level":      {"type": "string", "enum": ["strategic", "pattern", "factual"]}  # 保留
"content":    {"type": "string"}     # 保留
"companies":  {"type": "array"}      # 保留为 array（不改为 company 单值）
"sector":     {"type": "string"}     # 保留
"confidence": {"type": "number"}     # 保留
"evidence":   {"type": "array"}      # 保留
"source_attribution_id": {"type": "string"}  # 保留

# 新增字段
"methodology": {
    "type": "object",
    "description": "过程知识：你做了什么、哪里错了、下次怎么做。尽量具体到方法和工具。",
    "properties": {
        "what_i_did":      {"type": "string", "description": "这次分析用了什么方法"},
        "what_went_wrong": {"type": "string", "description": "复盘时填：为什么偏了"},
        "what_to_do_next": {
            "type": "array", "items": {"type": "string"},
            "description": "复盘时填：下次该怎么做，自然语言步骤列表"
        }
    }
}
```

变更点：
- `methodology`：新增，optional，object
- `zone` 和 `level`：从 required 改为 optional（分析模式下可以不传）
- 其他字段不变

存储后的完整条目示例：

```json
{
  "id": "exp_001",
  "zone": "warning",
  "level": "factual",
  "content": "NVDA DC revenue growth 严重低估，预测 35% 实际 78%",
  "companies": ["NVDA"],
  "sector": "semiconductor",
  "confidence": 0.8,
  "methodology": {
    "what_i_did": "用历史 3 年 CAGR 线性外推，参考了 TSMC 产能数据但判断为短期波动未采纳",
    "what_went_wrong": "AI 采购是指数型增长，线性外推天然低估加速周期",
    "what_to_do_next": [
      "查 hyperscaler capex 指引判断是否在加速周期",
      "如果是加速周期，线性估算基础上乘以 1.4~1.8",
      "用 TSMC 对应制程收入增速做上限检查"
    ]
  },
  "evidence": [],
  "created_at": "2026-01-15",
  "times_retrieved": 0,
  "times_useful": 0
}
```

### 5.2 字段说明

- `zone`：AI 自己判断。warning = 踩坑教训，golden = 有效方法。分析模式下可省略
- `level`：AI 自己判断。factual = 具体到一家公司，pattern = 跨公司规律，strategic = 跨行业认知。分析模式下可省略
- `content`：一句话总结，recall 时快速扫描用
- `methodology`：过程知识。what_i_did 在分析模式结束时写入，what_went_wrong 和 what_to_do_next 在学习模式复盘时填入。全部可选，AI 决定写多细
- `companies`：array，保持现有格式。pattern 级可能是多家公司
- `sector`：可选
- `confidence`：AI 对这条经验的确信度
- `evidence`：可选，保持现有格式
- `times_retrieved` / `times_useful`：系统自动维护，用于经验质量衰减

### 5.3 分析模式下的 save_experience 行为

分析模式下 `save_experience` 通过 `context["mode"]` 感知当前模式。行为变更：

```python
# experience/tools.py 中的 register(context) 已经接收 context dict
# context["mode"] 由 build_harness 传入

async def save_experience(params, *, context):
    mode = context.get("mode", "analysis")
    if mode == "analysis":
        # 分析模式：强制清除 zone/level，只允许记录方法论
        params.pop("zone", None)
        params.pop("level", None)

    # methodology 字段直接传入存储
    # ... 正常存储逻辑（去重、写入 experience_library.json）
```

这样分析模式存入的条目没有 zone/level，`recall_experiences` 在检索时自然不会把它们作为 warning/golden 返回给未来的分析。学习模式复盘时可以通过 companies + created_at 找到这些"待验证"的条目，更新它们的 zone/level/methodology。

### 5.4 去重规则

沿用现有设计：
- 相似度 > 0.90 → 重复，不存，增加已有条目的 times_retrieved
- 相似度 0.70-0.90 → 合并到已有条目
- 相似度 < 0.70 → 新条目

---

## 6. Reflection Skill

### 6.1 结构

```
iris/skills/reflection/
  ├── SKILL.md       ← 学习流程指令（核心）
  └── config.yaml    ← 工具声明
```

不需要独立的 tools.py，复用 experience skill 和 core tools 的工具。

### 6.2 config.yaml

```yaml
name: reflection
description: 季度复盘与经验学习
trigger_keywords: [复盘, 验证, reflection, 回顾, 校准, calibration, 学习, 教训]
tools:
  - recall_memory
  - fmp_get_financials
  - yf_quote
  - recall_experiences
  - save_experience
  - run_reflection
  - distill_patterns
  - check_calibration
```

### 6.3 SKILL.md

```markdown
# Reflection & Learning

## 何时使用
用户要求复盘、验证预测、回顾经验、发现规律时使用。

## 核心原则
- 从事实偏差学习，不从价格波动学习
- 经验要包含方法论：你做了什么、哪里错了、下次怎么做
- factual 和 pattern 级经验你自主写入
- strategic 级经验你只能提议，输出给用户确认
- 即使预测错了，如果推理过程高质量 → 也可以存 golden

## 流程 1：单公司复盘

当用户说"复盘 XXX"、"验证 XXX 的预测"时：

1. recall_memory(company) → 拿到上次分析笔记和预测
2. fmp_get_financials(company) → 最新实际数据
3. 逐个关键指标对比预测 vs 实际，计算偏差
4. 对每个显著偏差，分析原因：
   - 你当时用了什么方法？
   - 为什么偏了？是方法问题还是信息不足？
   - 下次遇到类似情况该怎么做？
5. save_experience → 存入经验，包含 methodology
6. save_memory → 更新公司笔记，加入最新数据
7. 输出复盘报告

## 流程 2：交易复盘

当用户说"复盘交易记录"、"交易表现怎么样"时：

1. 读取 trade_log 中已关闭的交易
2. 统计分析：胜率、按 confidence 分组、按 sector 分组
3. 检查过程纪律：
   - thesis_broken 的是否及时退出？
   - 止损纪律是否执行？
   - confidence 标注和实际胜率是否匹配？
4. 存入统计性经验（不是单笔归因）
5. 输出交易复盘报告

## 流程 3：模式发现

当用户说"看看 XX 行业有没有规律"时，或你在复盘中发现同类经验反复出现时：

1. recall_experiences(sector=xxx) → 所有相关经验
2. 寻找重复模式
3. distill_patterns → 总结成可复用的方法论模板
4. save_experience(level="pattern") → 存入

## 评估标准

分开评估，分开记录：
- 预测方向对不对（涨了还是跌了）
- 预测幅度准不准（偏差多大）
- 推理过程质量（逻辑是否自洽，是否考虑了反驳证据）
```

---

## 7. Soul 文件：reflection.md

学习模式的 soul 文件，与 role.md 搭配使用：

```markdown
# Learning Mode

你现在处于学习模式。你的任务不是分析新公司，而是验证过去的预测、从偏差中提炼方法论、积累可复用的经验。

## 你的工作方式

1. 用户会告诉你复盘哪家公司、哪段交易、或哪个行业
2. 你拉取历史预测和最新实际数据进行对比
3. 你分析偏差原因，提炼出下次可复用的方法论
4. 你把经验存入经验库，供未来分析时 recall

## 关键约束

- 不要做新的分析或估值，你没有分析工具
- 专注于"为什么偏了"和"下次怎么做"
- 方法论越具体越好：具体到该用什么工具、该查什么数据、该怎么验证
- 如果你觉得某条经验适用范围超出单个公司（行业级或更广），标注为 pattern 或 strategic
```

---

## 8. 代码改动详解

### 8.1 harness.py —— 不改

`Harness` 类本身不感知 mode。mode 的影响在 `build_harness()` 构建时就决定了（tools、soul、config 不同），`run()` 签名不变。

### 8.2 main.py —— build_harness() 加 mode 参数

见 Section 4.2 的完整伪代码。核心改动：
1. 读取 `modes.{mode}` 配置块
2. `load_soul(file_list=...)` 按 mode 选择 soul 文件
3. `load_skills(skill_names=...)` 按 mode 选择 skills
4. 按 `always_exposed_tools` 过滤注册的工具集
5. `context={"retriever": retriever, "mode": mode}` 传递 mode 给 skill tools

### 8.3 config.py —— load_soul() 加 file_list 参数

见 Section 4.2 的完整伪代码。向后兼容：file_list=None 时行为不变（加载所有 *.md）。

### 8.4 skill_loader.py —— load_skills() 加 skill_names 过滤

见 Section 4.2 的完整伪代码。向后兼容：skill_names=None 时行为不变（加载所有 skills）。

### 8.5 experience/tools.py —— save_experience 改动

两个变更：
1. `SAVE_EXPERIENCE_SCHEMA` 加 `methodology` 字段（Section 5.1）
2. `zone` 和 `level` 从 required 改为 optional
3. save_experience 函数通过 `context["mode"]` 感知模式（Section 5.3）

### 8.6 sessions.py —— 传递 mode

```python
# create_session 接受 mode 参数
async def create_session(mode: str = "analysis") -> AnalysisSession:
    session_id = generate_id()
    harness, retriever = build_harness(
        on_event=..., streaming=True, mode=mode
    )
    session = AnalysisSession(session_id, harness, retriever)
    return session
```

### 8.7 api.py —— 端点接受 mode

```python
@app.post("/api/sessions")
async def start_analysis(request: StartRequest):
    mode = request.mode or "analysis"  # 默认 analysis
    session = await create_session(mode=mode)
    # ...
```

---

## 9. 前端改动

### 9.1 学习模式入口

在现有 UI 中添加触发学习模式的方式：

- Watchlist 卡片上加「复盘」按钮
- 聊天框支持模式切换（下拉选择 Analysis / Learning）

按钮点击时：
```typescript
const startReflection = (ticker: string) => {
  createSession({ mode: "learning" });
  sendMessage(`复盘 ${ticker} 的最新财报表现`);
};
```

### 9.2 学习模式的 UI 区分

学习模式的 session 在 UI 上应有视觉区分（如不同的主题色或标签），让用户清楚当前处于哪种模式。

---

## 10. 实施顺序

### Phase 1：Mode 基础设施（使 build_harness 支持 mode）
1. `iris_config.yaml` 加 modes 配置块
2. `iris/core/config.py` 的 `load_soul()` 加 `file_list` 参数
3. `iris/core/skill_loader.py` 的 `load_skills()` 加 `skill_names` 过滤
4. `iris/main.py` 的 `build_harness()` 加 `mode` 参数，按 mode 分发 soul/skill/tool/budget
5. Soul 文件整理：合并 v0.1.md → role.md，合并 self_check.md → process.md，删除 steering.md，重命名 analysis_process.md → process.md

### Phase 2：学习模式内容（新 soul + 新 skill）
6. 创建 `soul/reflection.md`
7. 创建 `skills/reflection/SKILL.md` + `config.yaml`

### Phase 3：经验系统增强
8. `experience/tools.py` 的 `SAVE_EXPERIENCE_SCHEMA` 加 `methodology` 字段，zone/level 改为 optional
9. `experience/tools.py` 的 `save_experience` 函数通过 `context["mode"]` 感知模式，分析模式下清除 zone/level

### Phase 4：后端接入
10. `iris/backend/sessions.py` 的 `create_session` 接受 mode 参数
11. `iris/backend/api.py` 的端点接受 mode 参数

### Phase 5：前端
12. 前端加学习模式入口（复盘按钮 + 模式选择）
13. 学习模式 session 视觉区分（不同主题色/标签）
14. 学习模式下隐藏不相关的面板（model/comps 面板为空时不显示）

### Phase 6：端到端验证
15. 手动选一家已出财报的公司，在学习模式下跑一次完整复盘
16. 确认经验被正确存入 experience_library.json（含 methodology）
17. 切回分析模式，分析同 sector 另一家公司，确认 recall_experiences 能返回上一步存的经验
18. 在分析模式下确认 save_experience 只能记录方法论（无 zone/level）

---

## 11. 不做的事

- 不做自动触发（cron / 财报日历）—— 先手动触发
- 不做独立的 learning pipeline —— 复用 harness
- 不改 harness 核心循环逻辑 —— 只加 mode 分发
- 不强制经验结构（driver 拆分、zone 标注等）—— AI 自由决定
- AI 不能自行切换模式 —— 只有人可以

---

## 12. 关键设计来源

| 组件 | 来源 | 借鉴内容 |
|------|------|---------|
| 经验库架构 | FLEX（清华/字节, 2025） | 三层双区 + gradient-free + 经验继承 |
| 过程知识 | FLEX | 从观察升级为 procedural template |
| 双层反思时间 | FinCon（NeurIPS 2024） | 分析时记录 + 财报后复盘 |
| 事实偏差 reward | IRIS 独创 | driver-level 偏差作为主 reward signal |
| 交易统计 reward | 综合 | 批量统计，不单笔归因 |
| 评估分离 | SEP（WWW 2024） | 预测准确度和推理质量分开评估 |
