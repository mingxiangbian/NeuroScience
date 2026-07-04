# Paper Reader Hybrid Search Polish 设计

## Summary

本轮针对 `papers/brain-memory-for-ai-agents/` 的 paper reader 搜索体验做“克制全量版”优化。

目标是解决四类问题：

- 搜索结果横向溢出和内容截断。
- 搜索结果单条卡片阴影过重、视觉割裂。
- 顶部搜索框、夜间模式按钮、笔记收放按钮高度和圆角不统一。
- 当前语义分数过宽松，低相关搜索仍返回噪音结果。

同时加入轻量增强：

- `hybrid search`：字面匹配优先，语义分数补充。
- `debounce`：输入后延迟搜索，减少抖动。
- 小型 `spinner`：搜索计算期间给出微弱反馈。
- 暗黑/浅色主题切换过渡。

整体保持水墨玻璃风，不做大型产品化搜索页，不新增后端。

## Scope

### In Scope

- `papers/shared/reader.css` 中搜索 modal、搜索结果列表、顶部控件尺寸、主题过渡样式。
- `papers/shared/reader.js` 中本地 `hybrid search`、阈值过滤、debounce、loading 状态。
- `papers/brain-memory-for-ai-agents/index.html` 中必要的搜索状态元素，例如小型 spinner 或结果前缀 icon 容器。
- `tests/paper-reader-requirements.mjs` 中对应需求断言。

### Out of Scope

- 不改 `papers/manifest.json`。
- 不改 `readings/**` 数据内容或 schema。
- 不新增 SurrealDB、backend、AI provider、`/api/`、localhost dependency 或 build system。
- 不做大插图空状态、热门搜索标签、最近搜索或反馈入口。
- 不改 `/papers/` 文献阁首页。

## Design Decisions

### 1. Search Results Layout

搜索结果从“每条都是独立玻璃卡片”改成“统一玻璃列表”。

规则：

- `#search-results` 是一个统一容器，负责玻璃背景、圆角、边缘高光和整体阴影。
- `.result-item` 不再有常驻 `box-shadow`。
- 单条结果之间用细 `border-top` 或 divider 分隔。
- hover 时允许轻微背景变化和极轻阴影，但静默状态不做卡片堆叠。
- 结果内容使用 `min-width: 0`、`max-width: 100%`、`overflow: hidden`、`text-overflow: ellipsis`，消除水平滚动条。
- 每条结果保持两行：标题一行，snippet 一行。

### 2. Leading Icons

每条搜索结果左侧增加轻量 leading icon，提升信息类型识别。

第一版只需要两类：

- `paper`：跨论文结果，使用 document/page icon。
- `chunk`：当前论文或具体段落结果，使用 text/paragraph icon。

实现方式：

- 使用 inline SVG 或 CSS class，不引入外部 icon package。
- icon 尺寸约 `18px`，颜色使用 `var(--reader-blue)` 或低对比墨色。
- icon 只作为视觉前缀，不改变结果排序。

### 3. Toolbar Component Sizing

顶部控件统一为同一套尺寸系统。

普通状态：

- 搜索框高度约 `42px`。
- `toolbar-controls` 内的 icon button 高度与搜索框视觉对齐。
- 圆角统一到 `14px-16px` 的小玻璃控件风格。
- 搜索框和右侧按钮在同一 vertical axis 上，不出现一个高一个矮。

Modal 状态：

- 搜索框仍可放大到 centered modal。
- 放大状态不强行要求与右侧按钮同尺寸，因为右侧按钮被 overlay 弱化；但搜索框内部 icon、spinner、快捷键提示要保持居中。

### 4. Hybrid Search

搜索逻辑改为本地 `hybrid search`，不调用任何 provider。

评分由两部分组成：

- `lexical score`：字面匹配，优先检查 paper title、shortTitle、section title、sourceText、zhExplanation、keywords。
- `semantic score`：沿用当前 `embedQuery()` 和 `cosineSimilarity()` 计算出的本地语义分数。

排序策略：

- 标题、shortTitle、section title 的字面命中权重大于正文命中。
- `sourceText` 和 `zhExplanation` 命中视为强相关。
- 没有任何字面命中的纯语义结果必须超过更高阈值才保留。
- 结果总数仍限制在 `top 8`。

建议阈值：

- `lexical score > 0`：保留，并按综合分排序。
- `lexical score === 0` 且 `semantic score >= 0.42`：保留。
- `semantic score < 0.42`：丢弃。

这个阈值是本地启发式，不伪装成真实 embedding confidence。后续如果接入正式向量模型，可以重新校准。

### 5. Search State Feedback

输入使用轻量 debounce。

规则：

- 输入后等待约 `260ms` 再执行搜索。
- 等待期间搜索框右侧显示微型 spinner。
- 如果输入为空，保持 modal 打开，但不显示结果、不显示提示文字。
- 如果输入后没有结果，显示小号低对比 `No results found`。
- 不显示插图、热门标签、最近搜索或长提示。

### 6. Dark Mode Transition

暗黑/浅色切换加入轻量过渡。

规则：

- 对 `body`、主要玻璃控件、正文卡片、note panel、search modal 的 `color`、`background`、`border-color` 做约 `240ms ease` transition。
- 不对 `all` 做全局 transition，避免 layout 和 transform 被拖慢。
- 过渡只服务明暗变化，不新增动画装饰。

## Data Flow

搜索输入流程：

1. 用户 focus 搜索框，打开 `is-searching` modal。
2. 用户输入 query。
3. JS 清掉旧 debounce timer，设置新 timer。
4. timer 触发时进入 `is-search-loading`。
5. 对 `state.searchItems` 计算 lexical score 和 semantic score。
6. 根据阈值过滤低相关结果。
7. 渲染最多 8 条结果。
8. 退出 loading。

点击结果流程：

1. 读取 result 的 `paperId` 和 `chunkId`。
2. 调用 `openPaper(paperId)`。
3. 滚动到对应 chunk。
4. 关闭 search modal。

## Error Handling

- `state.searchItems` 为空时，输入后显示 `No results found`，不抛出可见错误。
- debounce timer 在关闭 modal 时清理，避免关闭后又渲染结果。
- 如果 result 的 chunk 不存在，只切换 paper，不中断页面。
- 纯语义结果低于阈值时丢弃；零结果触发低对比空状态。

## Testing

更新 `tests/paper-reader-requirements.mjs`，断言：

- 搜索结果容器没有水平溢出相关风险：结果项使用 `min-width: 0`、`overflow: hidden` 和 ellipsis。
- `.result-item` 静默状态没有常驻 `box-shadow`。
- `.search-results` 作为统一列表容器承担整体玻璃背景和阴影。
- 结果项有 leading icon markup 或 class。
- 顶部搜索框和 toolbar icon button 共享高度 token 或显式相同高度。
- 存在 `debounce` timer 逻辑。
- 存在 `is-search-loading` 或等价 loading class。
- 存在 `lexical score` 与 `semantic score` 组合逻辑。
- 存在硬阈值过滤，低相关结果不会返回。
- 无结果文案仍是小号低对比 `No results found`。
- 不引入 `/api/`、localhost、SurrealDB runtime、AI provider 或生成式回答。

实现后运行：

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

视觉检查：

- 桌面：搜索结果无水平滚动条，结果列表更像统一面板，单条不再堆阴影。
- 桌面：顶部搜索框和右侧按钮高度/圆角对齐。
- 移动端：搜索 modal 无横向溢出，结果前缀 icon 不挤压文本。
- 无效搜索：显示小号 `No results found`，不会返回明显无关结果。

## Decision Log

- 用户选择方案 C，但确认采用“克制全量版”。
- 保留小号空状态，不做插图、热门标签或长引导文案。
- Hybrid search 只做本地启发式，不接入 AI provider。
- 视觉目标是降低噪音，而不是增加更重的搜索产品感。
