# Task Plan: Prism Frontend Redesign

## Goal
将 `iris-frontend` 从现有 IRIS 风格重构为 Prism 品牌前端，严格参考 `prism-v1.html` 与用户提供的设计规范，完成首页、分析页、知识库、记忆页以及相关基础组件改造，同时保留原有核心功能、状态流和已修复的对话链路行为，避免引入 UI 回归或交互 bug。

## Current Phase
Phase 7

## Phases
### Phase 1: Baseline Audit & Risk Lock
- [x] 审查 `prism-v1.html`、现有页面结构、状态管理、API 依赖
- [x] 核对脏工作区中与本任务相关的现有改动，避免覆盖
- [x] 明确高风险交互点（聊天输入、流式分析、知识库上传/文档阅读、记忆编辑）
- **Status:** complete

### Phase 2: Design System & App Shell
- [x] 重写 `globals.css` 变量、字体、圆角、阴影与基础排版
- [x] 更新 `tailwind.config.ts`
- [x] 重构 `src/app/layout.tsx` 导航、logo、metadata、全局壳层
- **Status:** complete

### Phase 3: Homepage Redesign
- [x] 重写 `src/app/page.tsx`
- [x] 将 `SearchBar` 改为多行 `textarea`
- [x] 更新 onboarding、capabilities、quick templates、watchlist UI
- **Status:** complete

### Phase 4: Analysis Experience Redesign
- [x] 重构 `src/app/analysis/[id]/page.tsx` 两栏结构
- [x] 更新聊天、调试侧栏、phase pills、timeline、tab bar
- [x] 更新数据、模型、可比、策略相关面板与图表视觉
- **Status:** complete

### Phase 5: Knowledge & Memory Redesign
- [x] 更新 `src/app/knowledge/page.tsx` 及相关知识库组件
- [x] 更新 `src/app/memory/page.tsx` 与记忆树/查看器
- [x] 保持上传、列表、渲染、编辑交互可用
- **Status:** complete

### Phase 6: Regression Hardening & Verification
- [x] 自查关键交互回归风险
- [x] 运行 lint / build / 关键测试
- [x] 修复改造过程中暴露的小型后端/接口适配问题
- **Status:** complete

### Phase 7: Runtime CSS Regression Recovery
- [x] 复现用户截图中的“裸 HTML”运行态
- [x] 区分是代码缺陷还是旧 dev server / `.next` 缓存损坏
- [x] 恢复本地 3000 端口前端到正确的 Prism 样式状态
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 使用 planning-with-files 工作流 | 本任务跨多个页面和组件，持续时间长，必须保持磁盘级上下文 |
| 先做全量审查再动手 | 用户明确要求先看完整个代码，且当前工作区存在未提交改动 |
| 优先保留现有行为，再做视觉升级 | 该项目包含流式对话、知识库、记忆编辑等高耦合交互，视觉重构不能破坏功能链路 |
| 策略 tab 做成真实 panel 而不是纯占位 | 后端已存在交易技能与 portfolio 数据，补齐 session snapshot 提取即可闭环 |
| 用户截图优先按运行态故障排查 | 现象表现为样式完全失效，必须先分清是代码缺陷还是本地 dev server/缓存异常 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| PowerShell `Get-Content` 直接读取 `src/app/analysis/[id]/page.tsx` 失败 | 1 | 改用 `-LiteralPath` 读取带方括号的动态路由文件 |
| 首页样式完全丢失，页面退化为裸 HTML | 1 | 复现后确认首页 HTML 正常且包含 CSS link，但旧 3000 dev 进程返回的 `/_next/static/css/app/layout.css` 为 404；全新 3001 dev 进程同一代码可正常返回 CSS 200，说明是运行态缓存/旧进程损坏而非组件代码整体失效 |
