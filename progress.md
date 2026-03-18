# Progress Log

## Session: 2026-03-18 (Feedback One-Shot Refactor)

### Phase 1: Baseline & Scope Lock
- **Status:** complete
- Actions taken:
  - 读取并解析 `改造方案反馈.md` 全文。
  - 核验当前 `harness/retrieval/knowledge/app/tests` 与反馈差距。
  - 明确一次性改造范围与验收项。

### Phase 2: Core Runtime Refactor
- **Status:** complete
- Actions taken:
  - 新增 `core/budget.py`。
  - 新增 `core/loop_detector.py`。
  - 新增 `core/context.py`。
  - 新增 `core/tool_hooks.py`。
  - 重构 `core/harness.py` 接入四大模块，并增加 run_log 持久化。

### Phase 3: Retrieval + Config + Routing
- **Status:** complete
- Actions taken:
  - `retrieval.py` 增加 `by_subject`，并新增 embedding usage tracker 回调。
  - `knowledge.py` 让 `memory_search` 根据 `vector_search.enabled` 决策检索路径。
  - `iris_config.yaml` 新增 `budget`/`loop_detection`/`tool_triggers`，并更新压缩阈值。
  - 清理运行时 phase 残留（参数、事件、配置）。

### Phase 4: Observability + Tests
- **Status:** complete
- Actions taken:
  - `main.py` CLI 输出 run_id、预算、loop detector 信息。
  - `ui/app.py` 侧边栏新增预算进度条、工具调用计数、停止原因。
  - 兼容旧测试调用（`_manage_context` wrapper）。
  - 全量测试通过。

## Test Results
| Test | Command | Result |
|------|---------|--------|
| Harness tests | `pytest -q iris/tests/test_harness.py` | 13 passed |
| Context/Memory tests | `pytest -q iris/tests/test_context.py iris/tests/test_e2e_context.py iris/tests/test_knowledge.py iris/tests/test_retrieval.py` | 34 passed |
| Full suite | `pytest -q iris/tests` | 61 passed, 2 skipped |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-03-18 | `AttributeError: Harness has no _manage_context` | 1 | 增加兼容 wrapper 并复用 `ContextAssembler` |
