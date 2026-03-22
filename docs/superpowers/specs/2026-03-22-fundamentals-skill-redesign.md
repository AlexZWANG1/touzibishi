# Fundamentals Skill Redesign — 心法驱动 + 单次报告输出

## Problem

1. 当前 `emit_research_section` 被多次调用，产出碎片化的章节，前端用侧边栏导航展示，不像一篇连贯报告
2. SKILL.md 指示"边研究边推送"，导致 AI 每完成一步就推一段短文
3. 用户 continue 后 AI 再次调用，产生"两个报告"的问题
4. 研究方法论缺少用户真正关心的核心心法（产品手感、技术第一性原理、企业采购逻辑、壁垒→格局推演）

## Solution

### 1. Backend: `emit_research_section` → `emit_report`

**File:** `iris/skills/fundamentals/tools.py`

- 重命名为 `emit_report`
- Schema: `{ title: string, content: string }` — title 是报告标题，content 是完整 Markdown（1500-2500字）
- 仍然是 pure UI channel，无逻辑
- 一次对话只调用一次

### 2. SKILL.md 重写

**核心改动：**
- 删除"边研究边推送"的产出方式指令
- 删除一级市场扫描和二级市场分析步骤（这些属于 valuation/trading skill）
- 融入用户 Notion 中的研究心法：
  - 产品事实 → 技术原理 → 壁垒判断 → 企业采购逻辑 → 格局推演
  - 深度至少4层（表面现象→产品能力→技术难点→战略含义）
  - 一手材料优先、正反推敲、定量支撑、讲人话
  - 不限制报告固定结构，教思考方式而非模板
- 产出方式改为：研究完成后一次性调用 `emit_report` 输出完整报告

### 3. Frontend: `FundamentalsPanel.tsx` 重写

**从侧边栏章节导航 → 单篇长文全幅渲染：**
- 去掉左侧 `<nav>` 章节列表
- 去掉 `sections[]` 数组的逐章切换
- 直接渲染一篇完整 Markdown 文章（带标题）
- 保留 `ReactMarkdown` + `remarkGfm`
- 样式：干净的长文排版，类似 Notion 阅读体验
- 加载中状态：显示"研究进行中..."

### 4. State: `useAnalysisStore.ts`

- `FundamentalsPanelState` 从 `{ sections: [...] }` 改为 `{ title: string; content: string }`
- `_extractPanelData` 中 `emit_report` case 直接设置 title + content（替换，不追加）

### 5. Config: `iris_config.yaml`

- `always_exposed_tools` 中 `emit_research_section` → `emit_report`

### 6. Event Translation

- `toolRegistry.ts` / `eventTranslator.ts` 中添加 `emit_report` 的中文标签

## Files to Change

| File | Change |
|------|--------|
| `iris/skills/fundamentals/SKILL.md` | 完全重写 |
| `iris/skills/fundamentals/tools.py` | `emit_research_section` → `emit_report` |
| `iris-frontend/src/components/FundamentalsPanel.tsx` | 侧边栏 → 单篇长文 |
| `iris-frontend/src/hooks/useAnalysisStore.ts` | panel state + _extractPanelData |
| `iris-frontend/src/types/analysis.ts` | FundamentalsPanelState type |
| `iris/iris_config.yaml` | always_exposed_tools |
| `iris-frontend/src/utils/toolRegistry.ts` | tool label mapping |

## Constraints

- 报告长度 1500-2500 字
- 一次对话只产出一篇报告
- 不限制报告固定结构/section
- 核心是教研究心法，不是填模板
