# Findings & Decisions

## Task Source
- 用户要求以 `D:\项目开发\二级投研自动化\prism-v1.html` 和提供的 Prism 完整设计规范为视觉标准，对 `iris-frontend` 做一次大规模但稳定的前端重构。
- 约束：先完整审查再动手；保留已有好设计与功能；必要时允许小范围后端适配；避免把原有对话类 bug 带回去。

## Baseline Findings
- 当前仓库根目录存在 `task_plan.md` / `progress.md` / `findings.md`，但内容记录的是上一轮后端重构，需要切换到当前前端任务。
- 当前工作区存在未提交改动，且其中有本次会触达的前端文件：`iris-frontend/src/app/layout.tsx`、`iris-frontend/src/app/knowledge/page.tsx`、`iris-frontend/src/components/KnowledgeDocList.tsx`。
- 本次改造目标页面至少覆盖：首页、分析页、知识库页、记忆管理页，以及与之相关的一组共享组件。
- `iris-frontend` 技术栈为 `Next.js 15.1`、`React 19`、`Tailwind 4`、`Zustand 5`、`Recharts 2`、`react-markdown 9`。
- 未提交前端改动中，知识库页新增了 Jina Reader 文本清洗、标题净化、外链 source_path 展示和 markdown 图片渲染；`layout.tsx` 新增了 `/dev` 导航入口。这些都属于功能增强，不应在视觉重构中丢失。
- `prism-v1.html` 明确给出了目标视觉语言：暖白背景、Playfair + Sora + JetBrains Mono 字体分工、56px 顶栏、纵向 capability cards、多行 textarea 输入、浅光谱装饰、分析页两栏结构与 pill tabs。
- 现有首页 `src/app/page.tsx` 采用“搜索框 + watchlist + history”终端式布局，`SearchBar` 仍是单行 `input`，这与新设计要求的长文本 `textarea` 明显冲突。
- 分析页核心行为集中在 `useAnalysisStore.ts` 和 `useAnalysisStream.ts`：包括 SSE 连接/重连、回放模式、继续对话、resume、pending question、工具结果驱动 panel 填充。这些逻辑与样式耦合较弱，可以保留 store 和 API，重写组件外观。
- `ChatPanel.tsx` 当前把多轮对话存入 `_rawTextBuffer`，用 `<!---TURN--->` 哨兵切分 AI / 用户消息；还支持 replay/resumable 分支。输入框目前是单行 `input`，需要改为 `textarea`，但不能破坏提交、恢复和待提问逻辑。
- `StreamingTimeline.tsx` 会从 `<thinking>` block 衍生 timeline 项；`TimelineItem.tsx` 为 thinking、user_continue、tool event 三类内容做了特殊渲染。Prism 的新 debug sidebar 需要兼容这三类 event。
- 知识库页已具备完整的 note/url/file 上传、文档选择、markdown 阅读、删除等功能，且本地 diff 增加了标题清洗、Jina 元数据清洗、source_path 外链展示和图片渲染。
- 记忆页已具备文件树、render/raw/edit 三种查看模式、未保存确认和保存 API；视觉可重做，但这些编辑保护不能丢。

## High-Risk Interaction Areas
- 首页主输入：从单行改为自增高 `textarea`，需要保留 `startAnalysis`、mode 切换、loading 与路由跳转。
- 分析页聊天输入：需要新增 Enter 发送 / Shift+Enter 换行，同时保持 `RUNNING` / `WAITING` / `replay-resume` 分支。
- Tab 可见性：分析页 tab 依赖 panel 数据自动出现，不应因改动 DOM 而影响 `activeTab` 回退逻辑。
- Timeline / Thinking blocks：需要保留时间线插入顺序和 thinking 折叠能力，避免“有数据但不显示”。

## Additional Structural Findings
- 当前 `WatchlistRow` 在没有 `latest_run_id` 时会跳到 `/analysis?query=...`，而现有前端只有动态路由 `/analysis/[id]`，这是一个现存交互 bug，重构时应修正为真正启动分析。
- 前端当前没有独立的 strategy panel，但后端已经存在 `generate_trade_signal` / `get_portfolio` 工具以及交易输出 schema，因此可以用“小范围前后端适配”的方式把策略 tab 做成真实能力，而不是纯视觉占位。
- `iris/backend/sessions.py` 当前只向快照累积 `data/model/comps/memory` 四类前端 panel；若要支持策略 tab 的历史回放，需要在 session panel 提取和恢复逻辑里加入 `strategy`。

## Delivered Architecture
- 新增共享品牌组件：`PrismLogo` 与 `AppNav`，把导航、logo、live 指示器切换到 Prism 品牌。
- `globals.css` 与 `tailwind.config.ts` 已切换到亮色 Prism 设计系统，并保留了一层 `--iris-*` 别名，用来在大改过程中避免旧组件瞬间失效。
- 首页已改为 editorial hero + textarea 输入 + onboarding + vertical capability cards + watchlist / recent analyses，同时保留原有 history/watchlist 功能。
- 分析页已改为新两栏结构，并新增真实 `strategy` tab；`ChatPanel` 改为 textarea，多轮对话、resume、pending question、thinking block 逻辑保留。
- 后端 session 累积逻辑已补齐 `strategy` 与 `memory` 快照提取，确保历史回放不再只看到 data/model/comps。

## Verification
- `npm run build` 在改造前通过。
- `npm run build` 在首页/全局改造后通过。
- `npm run build` 在分析页 + 知识库 + 记忆页改造后通过。
- `python -m py_compile iris/backend/sessions.py iris/backend/api.py` 通过。
- `rg -n "F58025|scanline|Bloomberg|DM Sans|#07080C|#000000|#07080c" iris-frontend/src` 无结果，说明旧终端主题关键痕迹已移除。

## Runtime Regression Findings
- 用户截图中出现浏览器默认蓝色链接、块元素堆叠、默认表单控件样式，说明不是“设计不好”，而是 CSS 在运行时没有送达浏览器。
- 直接请求现有 `http://127.0.0.1:3000/` 时，首页 HTML 正常，且 `<head>` 中存在 `/_next/static/css/app/layout.css?...` 样式链接。
- 同一个 3000 端口进程对该 CSS 链接返回 `404 Not Found`，这正是页面退化成裸 HTML 的直接原因。
- 在相同代码、相同工作区下新起一个干净的 `next dev --port 3001` 进程后：
  - 首页 HTML 仍然输出同名 `layout.css` 链接；
  - 该 CSS 链接返回 `200`；
  - 返回内容包含 `tailwindcss v4.2.1`、`src/app/globals.css` 编译结果、`.flex` / `.hidden` / `.md:flex` 等工具类以及 Prism 自定义变量。
- 因此当前故障结论是：旧 3000 开发进程或其 `.next` 增量缓存损坏，导致 CSS 资产路由失效；不是当前组件树或样式源码整体写坏。

## Open Questions To Resolve During Audit
- 现有 `SearchBar` / `ChatPanel` 的发送与换行逻辑如何实现，哪些 bug 已经修过，哪些行为必须原样保留。
- 分析页的 tab、timeline、debug panel、streaming 状态是否依赖特定 DOM 结构或 CSS class。
- 知识库和记忆管理页是否已经有用户定制样式，需在重构中兼容。
