# IRIS Product Review Report

> Date: 2026-03-20
> Reviewer: AI PM (Claude)
> Method: Chrome DevTools MCP automated browser + subjective evaluation

---

## S1 First Impression & Branding

Bloomberg-terminal 风格的深色 UI，整体视觉辨识度高。橙色主色调 (#F58025) + JetBrains Mono 等宽字体，专业金融工具感强。

**正面：**
- 导航栏简洁：IRIS / 首页 / 知识库 / 记忆管理 + LIVE 指示灯
- SearchBar 模式切换（ANL/LRN）新加入，功能完整
- Watchlist 表格 Bloomberg 风格，信息密度高

**问题：**
- 品牌定位不清晰 — 新用户第一次打开，不知道这是什么产品、能做什么。没有 onboarding / 引导
- LIVE 指示灯意义不明 — 始终亮绿灯，用户不知道它指示什么

---

## S2 Navigation & Information Architecture

| 页面 | 路由 | 状态 |
|------|------|------|
| 首页 | `/` | 正常 |
| 分析详情 | `/analysis/[id]` | 正常（回看模式） |
| 知识库 | `/knowledge` | 正常（空状态有引导） |
| 记忆管理 | `/memory` | 正常 |

**问题：**
- 从分析页返回首页，watchlist 数据可能变化（价格闪烁/消失）
- History 列表没有分页，27 条全部渲染，长列表性能待观察
- 没有「正在运行」的分析任务入口 — 如果用户关闭 tab 后想回来，无法找到

---

## S3 Watchlist 体验

**严重问题 (P0)：**

1. **FV（Fair Value）数据严重偏低** — AAPL FV $130 vs Price $248 (-47%), GOOGL FV $64 vs $305 (-79%), NVDA FV $94 vs $178 (-47%)。所有 DCF 估值都远低于市价，说明 DCF 模型的假设可能有系统性问题（增长率太保守 / 未考虑行业特征）。用户看到这些数字会立刻失去信任。

2. **Price 数据不稳定** — 多次刷新首页，AAPL/MSFT/NVDA 的 Price 和 Gap% 会交替变成 `—`。推测是 watchlist API 调用 yf_quote 时部分请求超时或被 rate limit。

3. **TSLA 没有 FV** — 显示 N/A，但 History 中有 TSLA 分析记录（74,352 tokens）。说明分析完成了但 FV 没写入 watchlist。

**中等问题 (P1)：**

4. **REC 列全部为 `—`** — 推荐列没有任何数据，占位但无价值。
5. **Gap% 全为负数且幅度巨大** — 作为用户会觉得系统有 bug 而不是分析结果。

---

## S4 Analysis Detail Page 体验

**正常分析（MSFT 77k tokens）：**

- Timeline 左侧显示完整工具调用链：recall_memory → recall_experiences → memory_search → search_documents → build_dcf → get_comps → save_memory
- 「AI 思考」展示推理过程，9 个 thinking block 全部可展开
- 模型 tab：DCF Fair Value 卡片 + Implied Multiples + Year-by-Year Projections + Sensitivity Heatmap 全部正常渲染
- 分析笔记：ReactMarkdown 渲染，加粗生效

**严重问题 (P0)：**

6. **可比分析 (Comps) tab 数据全空** — 5 个 peer (MSFT, GOOGL, AMZN, ORCL, ADBE) 的 MKT CAP、P/E、EV/EBITDA 全是 `--`，Rev Growth 和 Margin 全是 `0.0%`。说明 get_comps 工具返回了 ticker 列表但没有实际数据。

7. **数据 tab 显示「等待数据...」** — 即使分析已完成（回看模式），数据面板仍然显示空状态。可能是因为这次分析的 fmp_get_financials 没有被调用（工具不可用），导致 data panel 没有被填充。

**非分析查询（"你是谁"）：**

8. **整个分析框架对非分析查询完全不适配** — 页面 95% 空白：
   - 左侧 timeline 只显示「正在初始化分析...」（没有工具调用）
   - 右侧 4 个 tab（数据/模型/可比/记忆）全部空
   - 分析笔记有 19 行 LLM 自我介绍文本，但挤在底部 30% 高度内
   - Phase indicator 显示「收集 › 分析 › 评估 › 总结 完成」但实际没有经过任何 phase
   - **用户直觉**：系统坏了

**建议**：对于没有工具调用的纯文本响应，应该用完全不同的布局 — 直接全屏显示 LLM 的回复文本，不要渲染工具面板框架。

---

## S5 Knowledge Base 体验

- 空状态有引导：「上传研报、笔记或文章到知识库，AI 分析时会自动检索相关内容」
- 三种上传方式：NOTE / URL / FILE
- 左右分栏布局合理

**问题 (P2)：**

9. NOTE 的 input 标签显示「股票」— 应该是 company/ticker filter，但标签不够清晰

---

## S6 Memory Management 体验

- 文件树结构清晰：COMPANIES (8) / SECTORS (1) / PATTERNS (1) / CALIBRATION (1)
- 点击文件可查看内容
- 支持 render / raw / edit 三种视图模式

**问题 (P1)：**

10. **`.gitkeep` 文件暴露给用户** — Sectors 和 Patterns 目录下只有 .gitkeep，对用户毫无意义，应该过滤隐藏。
11. **GOOG.md 和 GOOGL.md 同时存在** — 同一家公司两个记忆文件，可能导致分析时 recall 不一致。

---

## S7 Interaction Quality

| 维度 | 观察 |
|------|------|
| Loading states | SearchBar 有 spinner，分析页有 shimmer，基本完整 |
| Error states | History 中 ERROR 状态有红色标识，但点进去没有错误详情 |
| Hover effects | Watchlist 行有 hover，复盘按钮有 opacity 变化 |
| 模式切换反馈 | ANL↔LRN 切换即时，placeholder 同步变化 |
| 分析笔记 | Markdown 渲染生效（加粗、列表），但面板高度受限 |

---

## S8 Overall Scores

| Dimension | Score (1-5) | Notes |
|-----------|-------------|-------|
| Visual Design | 4 | Bloomberg 风格一致，专业感强 |
| Information Architecture | 3 | 页面结构合理但缺少 context-aware 布局 |
| Data Quality | 2 | FV 系统性偏低，Price 不稳定，Comps 空数据 |
| AI Dialogue Quality | 3 | 分析流程完整，但无法处理非分析类输入 |
| Interaction Feedback | 3 | 基本 loading/hover 有，但缺错误详情和状态恢复 |
| Error Handling | 2 | 无错误详情展示，空数据无 fallback |
| Overall Product Feel | 3 | 功能架构完整的 alpha 产品，数据层和边界 case 需要打磨 |

---

## S9 Top Improvements (Prioritized)

### P0 — Blocks Core Value

1. **DCF 估值系统性偏低** — 所有公司 FV 都是市价的 25%-55%，这不是个别问题而是模型假设系统性保守。用户第一眼看 watchlist 会认为系统不可靠。需要 review build_dcf 的默认假设（增长率、terminal multiple、WACC）。

2. **Comps panel 数据全空** — get_comps 返回了 peer list 但没有 market data。需要检查 comps 工具是否正确拉取了 peer 的财务数据。

3. **Watchlist 价格不稳定** — 多次刷新会看到价格消失又出现。需要加 API 调用的 retry/cache 机制，或者把价格缓存在服务端。

### P1 — Impacts Experience

4. **非分析查询的页面布局** — 纯文本响应不应该用分析框架（4 个空 tab + 空 timeline），应检测 no-tool-call 场景，切换为纯文本布局。

5. **History 中低质量记录污染** — 5 个 "Analyze NVDA" 各 150 tokens 明显是失败的调用，"test"、"E2E" 等测试记录也混在里面。需要：(a) 过滤/隐藏失败记录 (b) 提供删除功能。

6. **隐藏 .gitkeep 文件** — 记忆管理页面不应显示 .gitkeep。

7. **Error 记录缺少详情** — History 中 ERROR 状态的记录点进去看不到错误原因。

### P2 — Polish

8. **分析笔记面板高度** — 对于纯文本响应，笔记是唯一内容但被限制在底部 30%，大量空间浪费。

9. **History 缺少分页** — 27 条全部渲染，随着使用增长会有性能问题。

10. **Timeline 时间戳全部相同** — 回看模式下所有工具调用显示同一时间 `20:45:36`，没有相对时间差，用户无法感知分析耗时。

11. **记忆文件去重** — GOOG.md / GOOGL.md 重复，应统一。

12. **Watchlist TSLA 没有 FV** — 分析完成了但 FV 未写入 watchlist，数据链断裂。

---

## S10 Screenshot Index

| File | Description |
|------|-------------|
| 01-homepage.png | 首页初始状态，Watchlist + History |
| 02-learning-mode-toggle.png | 模式切换到 LRN，placeholder 变化 |
| 03-analysis-detail-msft.png | MSFT 分析详情页，Timeline + 数据 tab |
| 04-model-tab-msft.png | MSFT 模型 tab，DCF + Sensitivity |
| 05-comps-tab-msft.png | MSFT 可比 tab，数据全空 |
| 06-reasoning-expanded-msft.png | MSFT 分析笔记展开，Markdown 渲染 |
| 07-hello-query-detail.png | "你是谁" 查询详情，大面积空白 |
| 08-hello-reasoning-expanded.png | "你是谁" 分析笔记展开 |
| 09-knowledge-page.png | 知识库页面，空状态 |
| 10-memory-page.png | 记忆管理页面，文件树 |
| 11-homepage-refresh.png | 首页刷新后，价格数据不稳定 |
