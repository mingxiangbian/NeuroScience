# Paper Reader Floating Layout 视觉重构设计

## Summary

本轮设计只针对 `papers/brain-memory-for-ai-agents/` 的 paper 子项目阅读器页面，不改 `papers/` 文献阁首页。

采用已确认的 **方案 A：Floating Reader Layout**：

- 左侧论文目录从 `Full-height Sidebar` 改为 `Sticky Floating Card`。
- 顶部导航从整条 `Monolithic Top Navbar` 改为分散的 `Modular Navigation`。
- 搜索从页面中心主入口降级为右侧工具组里的短搜索框。
- 正文加强 `Typography Hierarchy` 和阅读舒适度。
- 右侧平行笔记继续使用线性边栏，不恢复卡片结构。

## Scope

### In Scope

- `papers/shared/reader.css` 的布局和视觉规则。
- 必要时微调 `papers/brain-memory-for-ai-agents/index.html` 的 toolbar 结构 class，但不改变现有控件语义。
- `tests/paper-reader-requirements.mjs` 的需求断言。

### Out of Scope

- 不改 `papers/manifest.json`。
- 不改 `papers/brain-memory-for-ai-agents/readings/**` 数据。
- 不改搜索算法、embedding 数据、chunk 渲染逻辑或 note 数据结构。
- 不新增 SurrealDB、backend、AI provider、`/api/` 或 build system。
- 不改文献阁首页 `/papers/`。

## Layout Design

### 1. Left Paper Directory

将左侧目录从全高通栏改成 `Sticky Floating Card`。

目标形态：

- 宽度保持在 `220px-260px`。
- 高度由内容决定，最大高度约 `70vh-76vh`。
- 在桌面端 sticky 固定在视口内，位置为垂直居中偏上。
- 目录不再顶满上下边界，和页面背景之间留出呼吸空间。
- 当前论文使用更明确的 active state：暗红色左边条、轻微按下背景、文字颜色加深。
- 目录项标题继续用 `shortTitle`，避免长论文标题撑破布局。

保留行为：

- 左侧目录仍负责切换项目内论文。
- 左侧收起按钮仍只控制论文目录。
- 桌面端收起后仍可显示章节线索引。
- 竖屏/手机端不显示章节线，目录通过 drawer 打开。

### 2. Top Modular Navigation

顶部导航不再是一整条横向玻璃栏，而是拆成多个功能岛。

桌面结构：

- 左侧功能岛：返回上一级项目标识、目录收放按钮。
- 右侧功能岛：短搜索框、夜间模式、笔记收放按钮。
- 中间不再放大搜索框，让正文标题和内容成为视觉中心。

搜索框规则：

- 搜索框宽度约 `180px-260px`。
- placeholder 继续保持 `Searching...`。
- 搜索结果继续使用横线分隔，不做大圆角结果卡片。
- 搜索 focus 可以保留全局玻璃层，但视觉强度要比之前更克制，避免遮住阅读上下文。

导航视觉：

- 每个功能岛使用轻玻璃或透明底，避免整栏压住页面。
- 控件之间保持稳定间距，避免项目标识和目录按钮重叠。
- 顶部区域整体高度应低于当前整栏式 toolbar。

### 3. Main Reading Typography

正文阅读区优先，排版要比工具 UI 更安静。

规则：

- `paper-title` 不再过度巨大，减少对首屏的压迫。
- 正文行宽控制在 `65ch-75ch`，避免长行阅读疲劳。
- 英文原文行高保持约 `1.7-1.82`。
- 中文解释行高保持约 `1.8-1.9`。
- 标题、chunk heading、正文之间建立更稳定的字号和字重层级。
- section tags 继续低对比，不抢正文。

chunk 容器：

- 继续保留轻线框和轻微阴影。
- 不做大圆角卡片。
- 不恢复 “原文 / 中文精读 / 来源” 作为普通阅读入口。

### 4. Right Linear Notes

右侧笔记区保持上一轮确定的线性结构。

规则：

- 不恢复完整卡片边框。
- 使用一条左侧竖线和正文区分。
- 笔记条目之间用横线分隔。
- 空笔记保持连续拟态留白，不显示占位文字。
- 中等宽度下优先收起右侧笔记，让主阅读区保持足够宽度。

## Responsive Behavior

### Desktop

- 显示左侧 `Sticky Floating Card`、中间正文、右侧线性笔记。
- 顶部导航分为左右功能岛，不占满整行。
- 搜索框在右侧工具组中保持短宽度。

### Narrow Desktop / Tablet

- 右侧笔记优先自动收起。
- 左侧目录仍可保持 sticky floating card，但尺寸略收缩。
- 主阅读区不得被压成过窄文本列。

### Mobile / Portrait

- 默认只显示中间阅读区。
- 左侧目录通过 drawer 打开。
- 不显示折叠章节线。
- 右侧笔记通过现有移动抽屉打开。
- 顶部功能岛压缩为左右两组，不出现横向溢出。

## Test Plan

实现时更新 `tests/paper-reader-requirements.mjs`，至少断言：

- 左侧目录不再是 full-height sidebar，而是内容驱动高度的 floating card。
- `.reader-sidebar` 或目录 surface 有 sticky floating positioning。
- 左侧目录 max-height 使用 `vh` 上限。
- 顶部 toolbar 不再是单个 full-width monolithic bar，而是 modular navigation groups。
- 搜索框宽度缩短，不再使用大中心搜索宽度。
- 当前论文 active state 使用暗红边条或等效视觉标识。
- 主阅读区正文使用 `ch` 级别的 max-width。
- 移动端仍默认隐藏目录、右侧笔记和章节线。
- 继续断言无 backend、无 AI provider、无 SurrealDB runtime。

实现后运行：

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

视觉检查：

- `1280x800`：左侧目录像浮动卡片，不顶满页面；搜索在右侧工具区，正文居中稳定。
- `760x800`：右侧笔记可收起，正文不被挤成窄列。
- `390x844`：默认只显示正文，顶部按钮不重叠，无横向溢出。

## Decision Log

- 用户确认只改 `/papers/brain-memory-for-ai-agents/` 阅读器页，不改 `/papers/` 文献阁首页。
- 用户选择左侧目录使用 `Sticky Floating Card`，而不是随内容滚动的 `Content-flow Card`。
- 用户选择搜索框从中心移到右侧工具组，采用短搜索框，不再作为顶部主视觉。
- 用户选择整体方案 A：`Floating Reader Layout`。
