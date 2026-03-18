# Task Plan: IRIS Feedback One-Shot Refactor

## Goal
按照 `改造方案反馈.md` 一次性完成 IRIS 架构改造：预算统一计量、循环检测、上下文组件化、工具 Hook、事件持久化、配置清理、CLI/UI 观测增强，并完成 commit + push。

## Current Phase
Phase 5

## Phases
### Phase 1: Baseline & Scope Lock
- [x] 读取反馈文档并提炼执行项
- [x] 对照当前实现确认差距
- [x] 锁定本次改造涉及文件与测试范围
- **Status:** complete

### Phase 2: Core Runtime Refactor
- [x] 新增 `core/budget.py`
- [x] 新增 `core/loop_detector.py`
- [x] 新增 `core/context.py`
- [x] 新增 `core/tool_hooks.py`
- [x] 重构 `core/harness.py` 接入以上模块
- **Status:** complete

### Phase 3: Retrieval + Config + Routing
- [x] retrieval 增加 subject 过滤接口
- [x] 配置新增 `loop_detection` / `budget` / `tool_triggers`
- [x] 向量检索路径接通并计入 budget（embedding 调用）
- [x] 截断阈值与按工具覆盖生效
- [x] 清理 phase 残留参数和事件
- **Status:** complete

### Phase 4: Observability + Tests
- [x] 增强 CLI 输出 run_id/预算/loop 状态
- [x] 增强 Streamlit 侧边栏预算进度/工具计数/停止原因
- [x] 补充/修正单测与集成测
- [x] 全量测试通过
- **Status:** complete

### Phase 5: Commit & Push
- [x] 汇总变更
- [ ] 创建 commit
- [ ] push 到远端分支
- **Status:** in_progress

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 使用 planning-with-files 工作流 | 本任务跨模块、长链路、需强追踪 |
| 向量检索选择“接通并保留”而非关闭 | 当前代码已有语义检索基础，可在不降级能力的前提下达成配置-代码一致 |
| phase 在运行时彻底移除 | 避免维护歧义，符合反馈要求 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `Harness` 缺少 `_manage_context` 兼容方法导致旧测试失败 | 1 | 新增兼容 wrapper，内部委托 `ContextAssembler` |
