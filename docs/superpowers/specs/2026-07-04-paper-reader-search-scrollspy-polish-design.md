# Paper Reader Search And Scrollspy Polish 设计

## Summary

本轮设计只针对 `papers/brain-memory-for-ai-agents/` 的 paper 子项目阅读器页面，目标是修正两个影响阅读体验的问题：

- 左侧目录收起后的章节横线索引仍像独立卡片，视觉嵌套过重，并且当前章节状态没有稳定跟随滚动。
- 搜索仍像右上工具输入框的局部展开，缺少全局聚焦感，结果列表和搜索框样式割裂。

采用用户确认的 **方案 C：完整体验 polish**，但范围保持克制：只改 reader 的前端交互和视觉，不改 `manifest`、`reading` 数据、chunk schema、embedding 生成方式、后端或部署结构。

## Scope

### In Scope

- 折叠状态下的章节横线索引视觉。
- `scrollspy` active section 同步逻辑。
- 搜索激活后的 centered modal 体验。
- 搜索结果的两行展示、关键词高亮、无结果状态。
- 搜索 modal 和左侧目录折叠的轻量过渡动画。
- `tests/paper-reader-requirements.mjs` 中对应需求断言。

### Out of Scope

- 不改 `papers/manifest.json`。
- 不改 `papers/brain-memory-for-ai-agents/readings/**` 数据内容或 schema。
- 不新增 SurrealDB、backend、AI provider、`/api/` 或 build system。
- 不改文献阁首页 `/papers/`。
- 不新增最近搜索、推荐标签、插图式空状态。
- 不实现新的横线导航参考页面；参考页只借鉴 Search 逻辑。

## Design Decisions

### 1. 折叠横线导航

折叠后的 `.section-rail` 不再渲染成玻璃卡片。

目标形态：

- 移除独立卡片背景、边框和大阴影，让横线直接承载在底层宣纸画布上。
- 保留顶部展开按钮，但按钮也应更轻，不形成新的大卡片。
- 横线整体像贴在背景上的 `Active Directory Index / Progress Indicator`，不再像一个嵌套面板。

状态规则：

- 静默状态下，所有横线长度一致。
- 当前章节只加深颜色，不加长。
- hover 当前横线时，该横线加深并加长。
- hover 相邻横线只加长，不加深。
- 移动端和竖屏下仍不显示折叠横线导航。

### 2. Scrollspy 同步逻辑

当前问题是 active section 可能被第一项长期占用，无法稳定跟随滚动位置。新逻辑应基于当前视口里的 chunk 位置重新计算，而不是只依赖一次性的进入事件。

目标规则：

- 每次滚动时，根据视口中心附近的 `.chunk` 选出当前 active chunk。
- 由 active chunk 的 `data-section-id` 更新 `.section-line.is-active`。
- 如果视口中心附近没有 chunk，则退回到距离视口顶部最近但未完全离开的 chunk。
- hover 只影响临时视觉，不改变 active section。
- 点击横线仍滚动到对应 section 的第一个 chunk。

实现时可以继续使用 `IntersectionObserver` 辅助维护可见 chunk 集合，但 active 决策必须由当前几何位置计算，避免“第一项一直最长/最亮”的状态锁定。

### 3. Search Modal

搜索参考用户给的页面，只借鉴 Search 的交互逻辑：点击搜索框或按 `⌘ K` 后进入全局居中搜索状态。

目标形态：

- 搜索激活时，页面进入 `is-searching` 状态。
- 背景出现全屏高模糊玻璃遮罩，弱化左右栏和正文。
- 搜索框从右上工具组件进入视觉上的居中放大状态。
- 桌面搜索宽度约 `min(760px, calc(100vw - 48px))`。
- 移动端搜索宽度接近全宽，不能横向溢出。
- 搜索框和结果列表使用同一套圆角、边缘高光和阴影语言。

退出逻辑：

- `Esc` 关闭搜索 modal。
- 点击遮罩空白区域关闭搜索 modal。
- 点击结果后跳转到对应 chunk，并关闭搜索 modal。
- 清空输入时保留搜索 modal，但不显示结果列表。

### 4. Search Results

结果列表应轻，不做厚重卡片区。

展示规则：

- 每条结果最多两行：第一行标题，第二行相关摘要。
- 第一行优先显示：当前论文内搜索时显示章节标题；跨论文搜索时显示 paper `shortTitle`。
- 第二行从 `sourceText` 或 `zhExplanation` 中截取最相关片段，不固定显示文本开头。
- 两行都使用 `ellipsis` 或 `line-clamp`，防止撑开结果条。
- 关键词匹配处使用轻量高亮，例如淡朱红或淡青底，不使用强黄色。
- 结果之间保留清晰但克制的分隔或同宽圆角条目。

空状态规则：

- 刚打开搜索、还没输入：不显示任何提示文字，只显示搜索框。
- 输入后无结果：只在搜索框下方显示一行小号、低对比的 `No results found`。
- 不做插图、不做大号空状态、不显示推荐标签。

### 5. Animation

动画只服务空间变化，不做复杂装饰。

搜索 modal：

- 打开时遮罩从透明到模糊。
- 搜索框从右上工具位置过渡到居中放大。
- 结果条目淡入。
- 关闭时反向淡出。
- 动画时长约 `180ms-220ms`。

左侧目录折叠：

- 目录 surface 淡出。
- 横线索引淡入。
- grid column 继续使用现有宽度 transition。
- 不做复杂 morph，不改变阅读内容位置的基本逻辑。

## Architecture

### HTML

`papers/brain-memory-for-ai-agents/index.html` 可以保留现有结构，但需要确保：

- `search-focus-layer` 可以作为可点击的 overlay。
- 搜索区域在 modal 状态下可被 CSS 重新定位。
- 结果区继续挂在 `#search-results`，便于 JS 控制。
- 折叠横线仍保留 `#section-rail` 和 `#section-lines`，不新增独立路由。

### CSS

`papers/shared/reader.css` 负责：

- `.reader-shell.is-searching` 下的 modal layout。
- `.search-focus-layer` 的全屏玻璃遮罩和 click target。
- `.toolbar-search` 在普通状态和 modal 状态之间的尺寸、位置、阴影和 transition。
- `.search-results` 的 modal 结果列表样式、两行截断和无结果样式。
- `.section-rail` 去卡片化。
- `.section-line.is-active` 只加深不加长。
- hover 和 neighbor hover 的长度动画。

### JS

`papers/shared/reader.js` 负责：

- 搜索 focus、`⌘ K`、输入、点击结果、`Esc`、点击 overlay 的状态切换。
- 搜索结果片段截取和关键词高亮。
- `scrollspy` active section 计算。
- 保持原有本地向量 ranking，不新增 AI answer 或远程 provider。

## State Model

建议明确三个 UI 状态：

- `is-searching`：搜索 modal 打开。
- `searchInput.value.trim() === ""`：modal 打开但不显示结果。
- `is-left-collapsed`：左侧目录收起，显示轻量横线索引。

active section 不应由 hover 状态写入全局状态。hover 只通过 CSS class 或临时 class 表达。

## Error Handling

- 如果搜索数据尚未加载完成，输入时可以返回空结果，但不显示大错误。
- 如果某个 result 对应的 chunk 不存在，点击后只切换 paper，不抛出可见错误。
- 如果某个 section 没有对应 chunk，横线点击不执行滚动。
- 如果用户在搜索 modal 中按 `Esc`，只关闭搜索和移动抽屉，不清空查询文本。

## Test Plan

更新 `tests/paper-reader-requirements.mjs`，至少断言：

- 折叠状态的 `.section-rail` 不再使用 `border: 1px solid var(--reader-glass-edge)` 或卡片式背景。
- `.section-line.is-active` 只改变颜色/透明度，不改变 width。
- `.section-line:hover` 可以加长加深。
- `.section-line.is-neighbor` 只加长，不加深。
- `reader.js` 的 active section 逻辑基于滚动/视口几何位置，而不是只依赖 hover 或默认第一项。
- `search-focus-layer` 可作为搜索 overlay。
- focus 搜索框或按 `⌘ K` 会进入 `is-searching`。
- `Esc`、点击 overlay、点击结果都会关闭 `is-searching`。
- 空输入不显示结果和提示。
- 无结果只显示低对比 `No results found`。
- 结果条目包含两行结构和关键词高亮 markup。
- 移动端仍默认隐藏目录、右侧笔记和折叠横线。
- 继续断言无 `/api/`、localhost backend、SurrealDB runtime、AI provider 或生成式回答。

实现后运行：

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

视觉检查：

- `1280x800`：搜索 modal 居中，结果条目同宽，背景模糊；折叠横线没有卡片背景。
- `760x800`：搜索 modal 不遮挡出横向溢出，左右栏收起逻辑稳定。
- `390x844`：默认只显示中间阅读页；搜索 modal 近全宽；不显示折叠横线导航。

## Decision Log

- 用户确认参考页只借鉴 Search，不借鉴其左侧横线导航。
- 用户选择方案 C：核心修复 + 搜索增强 + 轻量动画。
- 用户确认折叠横线静默状态下当前章节只加深，不加长。
- 用户要求未输入时不显示空状态提示文字。
- 用户确认无结果状态可以保留小号、低对比的 `No results found`。
