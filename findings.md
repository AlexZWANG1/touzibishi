# Findings & Decisions

## Task Source
- 用户指定执行文件：`D:/项目开发/二级投研自动化/改造方案反馈.md`
- 要求：一次性完整改造 + commit + push。

## Delivered Changes
1. 新增 `core/budget.py`：
   - 统一计量 LLM 调用（main/flush/compaction/embedding）
   - 工具执行前额度裁剪（pre-round trim）
   - `HarnessResult.budget_breakdown` 输出分项统计
2. 新增 `core/loop_detector.py`：
   - `generic_repeat`、`ping_pong`、`no_progress_poll`
   - 支持 `steer_then_stop | hard_stop | warn_only`
3. 新增 `core/context.py`（`ContextAssembler`）：
   - subject 提取
   - 按主题注入历史（并降级摘要无关主题）
   - compaction + memory flush 迁移
4. 新增 `core/tool_hooks.py`：
   - `ToolHookContext` / `ToolHooks` / 默认 hooks
   - before 参数标准化、after 错误分类标签
5. 重构 `core/harness.py`：
   - 接入 budget/loop/context/hooks
   - 删除 phase 参数与 phase event
   - `_emit` 持久化到 `run_log` 单表
6. 更新 `tools/retrieval.py`：
   - 增加 `by_subject(...)`
   - embedding 使用量回调（计入 budget）
7. 更新 `tools/knowledge.py`：
   - `memory_search` 读取 `vector_search.enabled`
   - 向量检索不可用时关键词 fallback
8. 更新 `iris_config.yaml`：
   - 新增 `budget`/`loop_detection`
   - `compress_threshold_chars` -> 5000
   - `tool_compress_overrides` 与 `tool_triggers`
9. 观测增强：
   - `main.py` CLI 显示 run_id、预算、loop 状态
   - `ui/app.py` 侧边栏显示预算进度、工具计数、停止原因

## Validation
- `pytest -q iris/tests/test_harness.py` -> 13 passed
- `pytest -q iris/tests/test_context.py iris/tests/test_e2e_context.py iris/tests/test_knowledge.py iris/tests/test_retrieval.py` -> 34 passed
- `pytest -q iris/tests` -> 61 passed, 2 skipped
- `rg -n "phase|Phase|PHASE" iris -g"*.py" -g"*.yaml"` -> no matches

## Key Decision
- 向量检索采用“接通并保留”路径，并把 embedding 调用计入预算，避免“配置启用但实现空壳”。
