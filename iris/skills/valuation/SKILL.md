# Valuation

Use `valuation` as your only entry point. Do not call `build_dcf` or `get_comps` directly.

---

## 估值方法选择

| 公司类型 | 方法 | mode | 原因 |
|---------|------|------|------|
| 成熟盈利公司 (AAPL, MSFT) | DCF + Comps | `full` | 有稳定 FCF 可折现，comps 交叉验证 |
| 高增长盈利公司 (NVDA, META) | DCF + Comps | `full` | DCF 捕捉增长价值，comps 锚定合理区间 |
| 亏损/早期公司 (RIVN, biotech) | 纯 Comps | `comps` | 无正 FCF，只能用 EV/Revenue 同业比较 |
| 周期股在极端位 (钢铁、航运) | Comps 为主 | `comps` | 当前盈利不代表正常盈利能力，用 mid-cycle 思维 |
| 银行/保险 | Comps 为主 | `comps` | FCF 不适用，用 P/BV、股息折现 |

**默认用 `mode='full'`。** 只在上面列出的特殊场景才退回 `comps`。

---

## 假设推导框架（调 DCF 前必须完成）

**不准凭感觉填 assumptions。** 每个假设必须有数据锚点：

### Revenue Growth — 怎么定

先用 `financials(ticker, 'income-statement')` 拉历史，算 3 年 CAGR。

```
Year 1-2: 参考管理层 guidance 或 consensus，
          没有的话用历史 CAGR ± 行业趋势调整
Year 3-4: 渐降至行业平均增速
Year 5:   接近 terminal growth rate (2.5-3.5%)

验证: Y1 growth 不应比历史 CAGR 偏离 >50%，除非有重大变化
```

### Margin — 怎么定

```
gross_margin:        financials → 最近 3 年 gross margin 的中位数
opex_pct_of_revenue: financials → (总运营费用 - COGS) / Revenue
                     注意: OpEx 基于 Revenue，不是 Gross Profit
capex_pct_of_revenue: cash-flow-statement → CapEx / Revenue
da_pct_of_revenue:   cash-flow-statement → D&A / Revenue
                     ⚠️ 不要省略这个参数！
                     重资产行业 (云、半导体): D&A 通常 < CapEx
                     轻资产行业 (SaaS): D&A ≈ CapEx
```

### WACC — 怎么算

**不准直接写 `wacc: 0.10`。** 用 CAPM 推导：

```
1. 用 macro(series_id='DGS10') 拿 10 年期国债收益率 → Rf
2. 用 quote(ticker) 拿 beta (5 年月度)
3. ERP = 5.5% (市场标准)
4. Ke = Rf + β × ERP

5. 用 financials(ticker, 'balance-sheet-statement') 拿:
   - Total Debt, Cash & Short-term Investments
   - 算 Net Debt = Total Debt - Cash
6. 用 financials(ticker, 'income-statement') 拿:
   - Interest Expense / Total Debt → Pre-tax Kd
   - Tax Rate (有效税率)
7. Kd_after_tax = Kd × (1 - Tax Rate)

8. 用 quote(ticker) 拿 Market Cap
9. EV = Market Cap + Net Debt
10. Equity Weight = Market Cap / EV
    Debt Weight = Net Debt / EV
11. WACC = Ke × Equity Weight + Kd_after_tax × Debt Weight

典型范围:
  大盘稳定: 7-9%
  成长股:   9-12%
  高风险:   12-15%
```

把推导过程写在 `<thinking>` 块里。最终只有算出来的 WACC 数字进入 assumptions。

### Terminal Growth — 怎么选

```
保守: 2.0-2.5% (GDP 增速)
中性: 2.5-3.5%
激进: 3.5-5.0% (只有市场领导者)

铁律: terminal_growth < WACC，否则模型发散
铁律: 不超过无风险利率 Rf
```

---

## 场景分析（Bear / Base / Bull）

**每次估值必须给三个场景，不能只给一个数字。**

调用方法：调 3 次 `valuation(mode='dcf')` + 1 次 `valuation(mode='comps')`：

```
# Step 1: Comps 先跑一次，获取 peer 基准
valuation(mode='comps', ticker='AAPL', peers=['MSFT', 'GOOGL', 'AMZN', 'META'])
# → 拿到 peer median growth, margin, P/E, EV/EBITDA 作为基准

# Step 2: Bear Case
valuation(mode='dcf', ticker='AAPL', assumptions={
  ...
  "growth_rates": [0.02, 0.02, 0.01, 0.01, 0.01],  # 低增长
  "gross_margin": {"value": 0.44},                    # margin 压缩
  "wacc": 0.105,                                      # 风险溢价升高
  "terminal_growth": 0.02,                             # 保守
})

# Step 3: Base Case
valuation(mode='dcf', ticker='AAPL', assumptions={
  ...
  "growth_rates": [0.05, 0.04, 0.04, 0.03, 0.03],  # consensus
  "gross_margin": {"value": 0.46},                    # 稳定
  "wacc": 0.095,                                      # CAPM 算出来的
  "terminal_growth": 0.03,                             # 中性
})

# Step 4: Bull Case
valuation(mode='dcf', ticker='AAPL', assumptions={
  ...
  "growth_rates": [0.08, 0.06, 0.05, 0.04, 0.04],  # 乐观
  "gross_margin": {"value": 0.48},                    # margin 扩张
  "wacc": 0.085,                                      # 风险溢价降低
  "terminal_growth": 0.035,                            # 偏高
})
```

### 三个场景的假设差异

| 维度 | Bear | Base | Bull |
|------|------|------|------|
| Revenue growth | 历史低位或更低 | Consensus/guidance | 历史高位 |
| Margin | 压缩或持平 | 稳定/适度扩张 | 显著扩张 |
| WACC | +1% (风险升高) | CAPM 计算值 | -1% (风险降低) |
| Terminal growth | 2.0-2.5% | 2.5-3.0% | 3.0-4.0% |
| CapEx | 升高 | 稳定 | 降低 |

### 输出格式

最终在分析结论中必须这样呈现：

```
估值区间: $85 (Bear) — $97 (Base) — $125 (Bull)
当前价格: $228
Base Case 隐含下行: -57%
结论: 以 Base Case 假设，AAPL 当前估值偏高。
      即便 Bull Case 也不支持当前价位。
```

---

## DCF 调用指南

### 完整例子：AAPL (Base Case)

**数据准备阶段** — 先调这些 tool：

```
financials('AAPL', 'income-statement')   → Revenue, Gross Profit, OpEx, Shares
financials('AAPL', 'balance-sheet-statement') → Debt, Cash → Net Debt
financials('AAPL', 'cash-flow-statement')  → CapEx, D&A
financials('AAPL', 'ratios')              → historical margins
quote('AAPL')                              → Current Price, Beta, Market Cap
macro(series_id='DGS10')                   → 10Y Treasury Yield (for WACC)
```

**从数据推导假设** — 在 `<thinking>` 块中：

```
Revenue: $394B, 3-year CAGR ~4%
  → Base: [5%, 4%, 4%, 3%, 3%] (略高于历史 CAGR Y1, 逐年回归)
Gross margin: 46%, 3 年稳定
  → Base: 0.46
OpEx/Rev: ~14% (SGA + R&D 合计)
  → Base: 0.14
CapEx/Rev: 3.5%, D&A/Rev: 3.0%
  → 分别设 0.035 和 0.03 (D&A < CapEx, Apple 仍在增加投资)
Shares: 15,408,095,000 (diluted, from income statement)
Net cash: $65B cash - $105B debt = -$40B (net debt)
  → net_cash: -40000 (单位 $M，负数表示净负债)

WACC 推导:
  Rf = 4.2% (10Y Treasury)
  β = 1.24 (from quote)
  ERP = 5.5%
  Ke = 4.2% + 1.24 × 5.5% = 11.0%
  Kd = 3.5% (interest_expense / total_debt)
  Tax = 16%
  Kd_after_tax = 3.5% × (1 - 0.16) = 2.94%
  Market Cap = $3.5T, Net Debt = $40B, EV = $3.54T
  Eq Weight = 98.9%, Debt Weight = 1.1%
  WACC = 11.0% × 0.989 + 2.94% × 0.011 = 10.9%
  → 但 Apple 的 WACC 10.9% 太高（大盘蓝筹通常 8-10%），
    调整为 9.5% (考虑 Apple 的低波动性和品牌护城河)
```

**调用 tool：**

```
valuation(
  mode='full',
  ticker='AAPL',
  assumptions={
    "company": "Apple", "ticker": "AAPL", "projection_years": 5,
    "segments": [
      {"name": "Total", "current_annual_revenue": 394000,
       "growth_rates": [0.05, 0.04, 0.04, 0.03, 0.03]}
    ],
    "gross_margin": {"value": 0.46},
    "opex_pct_of_revenue": {"value": 0.14},
    "capex_pct_of_revenue": {"value": 0.035},
    "da_pct_of_revenue": {"value": 0.03},
    "wacc": 0.095,
    "terminal_growth": 0.03,
    "shares_outstanding": 15408095000,
    "net_cash": -40000,
    "current_price": 228
  },
  peers=["MSFT", "GOOGL", "AMZN", "META"]
)
```

**关键注意：**
- `da_pct_of_revenue` 必须显式设置，不要依赖默认值
- `shares_outstanding` 是实际股数（不是百万）
- `net_cash` 是负数（Apple 有净负债），单位 $M
- `growth_rates` 锚定在历史 CAGR，不是凭空编造
- `current_annual_revenue` 单位是 $M（和 `financials` 返回一致）

---

## Comps 调用指南

### Peer 选择框架

**不准凭感觉选 peer。** 必须满足可比性：

```
可比维度:
  1. 核心业务模式相同（不是"都是科技股"就算可比）
  2. 规模量级接近（不要拿 $10B 和 $3T 比）
  3. 增长阶段相似（不要拿高增长和成熟期混）
  4. 地域市场相似（中美监管环境差异大）

数量: 4-6 个是最佳。3 个完美 peer 好过 8 个勉强的。

❌ 常见错误:
  - NVDA 的 peer 不是 INTC（阶段完全不同）
  - BABA 的 peer 不是 AMZN（监管环境不同）
  - TSLA 的 peer 不是 F/GM（业务模式不同）
```

### 行业差异化指标

Comps 返回 Fwd P/E、EV/EBITDA、Revenue Growth、Gross Margin。
解读时注意不同行业的合理范围：

```
SaaS/软件:    EV/EBITDA 15-30x, Gross Margin >70%
半导体:       EV/EBITDA 12-25x, 强周期性
消费品:       EV/EBITDA 10-18x, 稳定但低增长
金融:         P/E 为主 (不用 EBITDA), 看 ROE 和 P/BV
工业:         EV/EBITDA 8-15x, 看资产周转率
```

### 统计基准解读

```
comps 返回 median、target_vs_median。解读方法：

premium > +30%:  目标公司相对 peer 明显"贵"
  → 必须解释：增长更快？margin 更高？市场地位？
  → 如果找不到合理解释，可能是估值过高的信号

premium < -30%:  目标公司相对 peer 明显"便宜"
  → 必须解释：增长放缓？管理风险？市场误解？
  → 如果是市场误解，这可能是投资机会

premium ±15%:    合理区间，无需特别解释
```

### Comps 如何反哺 DCF 假设

**先跑 comps，用结果检验 DCF 假设：**

| Comps 输出 | 用来检验 |
|-----------|---------|
| Peer median EV/EBITDA | DCF implied EV/EBITDA 是否合理 |
| Peer median growth | 你的 growth_rates Y1 是否偏离太远 |
| Peer median gross margin | 你的 gross_margin 假设是否合理 |
| Peer median P/E | DCF implied P/E 是否合理 |

---

## 交叉验证清单（每次估值必须执行）

valuation(mode='full') 会返回 `cross_check`。在此基础上再做以下检查：

### 1. DCF Implied P/E vs Peer Median

```
cross_check.status == "aligned":     通过
cross_check.status == "stretched":   DCF 隐含 P/E >= 2x peer median
  → 检查 growth 假设是否过于乐观
  → 检查 WACC 是否过低
cross_check.status == "conservative": DCF 隐含 P/E <= 0.5x peer median
  → 检查 growth 假设是否过于保守
  → 检查 WACC 是否过高
```

### 2. Terminal Value 占 EV 比例

```
从 dcf 结果中计算: TV/EV = discounted_terminal_value / enterprise_value

50-70%:  正常
>75%:    近期 FCF 被低估 — 通常意味着:
         CapEx 太高 / Margin 太薄 / Growth 假设偏保守
<40%:    终态假设可能太保守
```

### 3. Implied Growth 合理性

```
DCF 算出的 fair_value 隐含市场对未来增长的预期。
如果 fair_value >> current_price:
  → 你的增长假设 可能 高于市场共识
  → 问自己：我有什么信息是市场没有的？

如果 fair_value << current_price:
  → 你的假设可能偏保守，或者市场在为 optionality 付溢价
```

### 4. 单位和符号复查

```
每次调用前在 <thinking> 中确认:
  - revenue 单位是 $M 吗？（和 financials 返回一致）
  - shares_outstanding 是实际股数吗？（不是百万）
  - net_cash 正负号对吗？（净负债 = 负数）
  - wacc 是小数吗？（9.5% → 0.095，不是 9.5）
  - growth_rates 是小数吗？（5% → 0.05，不是 5）
```

---

## 什么时候 DCF 不适用

DCF 在未来现金流不可预测时失效：

- **亏损公司** (Rivian, 多数 biotech) — 无正 FCF 可折现。用 `mode='comps'` + EV/Revenue。
- **周期股在极端位** (钢铁、航运、半导体周期顶/底) — 当前盈利不代表正常盈利能力。思考 mid-cycle 是什么样。
- **银行和保险** — FCF 不适用。P/BV 和股息折现是标准方法。`mode='comps'` 仍可用于 P/BV 比较。

**不要硬套 DCF。** 一个基于合理 peer 选择的 comps 分析，往往比一个假设不靠谱的 DCF 更有用。

---

## 错误防范清单

### DCF 假设错误

| 错误 | 症状 | 修法 |
|------|------|------|
| 忘了 `da_pct_of_revenue` | D&A 默认等于 CapEx，重资产行业 FV 偏低 | 从 cash-flow-statement 算 D&A/Revenue |
| `shares_outstanding` 用了百万 | FV 比合理值高/低 1000x | 用 income-statement 的 weightedAverageShsOutDil |
| `net_cash` 符号反了 | 净负债公司 FV 偏高 | 净负债 = 负数 |
| Revenue 单位错 | 所有输出值都离谱 | 必须用 $M (和 financials 返回一致) |
| Growth 用百分数而非小数 | 500% 增长，模型爆炸 | 5% → 0.05 |
| Terminal growth >= WACC | 模型不收敛 | terminal_growth 必须 < wacc |
| OpEx 基于 Gross Profit 而非 Revenue | Margin 失真 | OpEx % 永远基于 Revenue |

### Comps 选择错误

| 错误 | 为什么是错的 |
|------|------------|
| 不可比公司当 peer | 商业模式不同，multiples 没有可比性 |
| 只选 2 个 peer | 样本太小，median 无意义 |
| 选 8+ 个 peer | 可能为了凑数混入不可比公司 |
| 负 EBITDA 公司用 EV/EBITDA | 负数 multiple 无意义，用 EV/Revenue |
| 不同财年混在一起 | 时间不可比，seasonal 影响 |

### 估值判断错误

| 错误 | 为什么是错的 |
|------|------------|
| 只给一个 fair value | 没有不确定性表达，虚假精确 |
| 不做交叉验证 | DCF 和 comps 严重偏离没被发现 |
| TV/EV > 80% 不解释 | 近期假设可能有问题 |
| 凭感觉填 WACC | 没有 CAPM 推导，不可审计 |
| 不看 financials 就填假设 | "air assumptions" — 没有数据锚点 |
