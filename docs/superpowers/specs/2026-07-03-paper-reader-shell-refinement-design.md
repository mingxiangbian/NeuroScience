# Paper Reader Shell Refinement Design

Date: 2026-07-03
Status: Approved design, pending implementation plan

## Summary

本轮只重构 `papers/<project-id>/` 子项目阅读器的壳层、视觉和交互稳定性，不重写现有三篇 paper 的 chunk 内容质量。

目标是把当前“卡片式三栏工作台”调整成更省空间、更稳定的“文档阅读器”：顶部轻薄工具栏、左侧固定玻璃论文目录、中间无界正文长流、右侧连续平行笔记。整体仍保持 `papers/` 板块的水墨宣纸、玻璃拟态和低饱和色彩，不改成参考站点的课程导航风格。

本设计参考了 `https://ayaskt.github.io/Y3S2/EMFT/EMFT-README.html` 的三个可用经验：

- 固定左侧玻璃目录，目录自身滚动。
- 正文采用长文档流，不在整篇文章外层套大卡片。
- 侧栏隐藏后形成纯净阅读状态。

不照搬参考页的站点导航、多级课程菜单、大量彩色块或右侧完整章节目录。

## Scope

包含：

- `papers/shared/reader.css` 的布局、玻璃质感、响应式断点、正文排版调整。
- `papers/shared/reader.js` 的侧栏状态、笔记渲染稳定性、搜索 placeholder、滚动锚点更新逻辑调整。
- `papers/brain-memory-for-ai-agents/index.html` 中必要的 aria、占位文案或结构 class 微调。
- `tests/paper-reader-requirements.mjs` 的行为与结构断言更新。

不包含：

- 不重写三篇 paper 的 `sourceText`、`zhExplanation`、`notes` 内容。
- 不新增本地同步、后端、`/api/`、SurrealDB runtime、AI provider 或生成式 AI 回答。
- 不新增全局 `/papers/reader/` 路由。
- 不改变 `papers/manifest.json` schema。
- 不创建新的项目内阅读页。

## Layout

### Desktop

桌面端阅读器使用固定工具栏 + 三块阅读区域：

```text
top toolbar
fixed paper directory | flowing main reader | fixed parallel note panel
```

外层 shell 应减少“卡片边距感”：

- 页面仍保留少量边缘呼吸空间，但不再用厚重 gap 和大圆角卡片把每个区域割裂。
- 中间正文区域是主要视觉焦点，宽度根据侧栏状态自动扩展。
- 左右侧栏是玻璃面板，不是正文同级的大卡片容器。

左侧论文目录：

- 展开时固定在视口内，`top` 跟随 toolbar 高度，`height` 使用视口计算。
- 目录自身滚动，不跟随正文滚动。
- 只显示每篇 paper 的 `shortTitle`。
- 当前 paper 使用按下去的 selected treatment。
- 展开状态不显示细线章节索引。

左侧折叠状态：

- 仅桌面端启用。
- 显示当前 paper 的章节线 rail。
- 章节线在 rail 内部居中，并随当前阅读位置更新 active section。
- 章节线 hover 时当前线变长、变粗、变深；相邻线只变长，不变粗变深。
- 折叠 rail 不承担移动端导航职责。

右侧平行笔记：

- 右侧 panel 固定在视口内。
- panel 始终是一整张连续玻璃纸面。
- 切换 chunk 时只替换内容，不重建 panel，不改变高度。
- 收起右侧笔记后，中间正文扩展，形成接近纯净阅读模式。
- 右侧笔记收起就是阅读空间扩展，不新增单独 zoom 或 pure mode 按钮。

### Narrow Desktop

在中等宽度设备或分屏情况下，正文优先：

- 约 `1100px` 以下默认隐藏或收起右侧笔记。
- 左侧目录仍可保留，但宽度收紧。
- 搜索框缩短并保持居中，避免挤压两侧 icon。

### Mobile / Portrait

竖屏和窄屏默认只显示中间阅读页：

- 上栏左侧收放按钮只控制论文目录，不控制章节线。
- 打开时显示正常论文目录列表，当前 paper 保持 selected treatment。
- 竖屏不显示折叠章节线，不显示阅读进度线。
- 章节跳转只保留在正文标题下方的轻量 section anchors。
- 右侧平行笔记由右侧按钮打开为底部 drawer。
- 默认不显示左目录和右笔记，避免正文被压成狭窄列。

## Toolbar

顶部栏保持轻薄固定：

- 左侧：项目 logo 返回上一级 `../`，旁边是论文目录收放按钮。
- 中间：全局搜索框，placeholder 固定为 `Searching...`。
- 右侧：夜间模式按钮和平行笔记收放按钮。

搜索交互：

- 搜索框宽度比当前版本更克制，并保持真正居中。
- 聚焦或输入时启用全局玻璃雾化层，作用于整页，不只作用于中间 reader。
- 搜索结果位于搜索框下方，用横线分隔，不做厚重圆角卡片。
- 无结果时显示 `no found`。
- 搜索结果点击后跳转到 paper + chunk，并关闭搜索雾化层。

## Visual System

玻璃拟态需要从“半透明白块”升级为更有层次的面板：

- 背景保留宣纸、淡网格和墨晕。
- toolbar、paper directory、note panel 使用更透明的暖纸/青灰底色。
- `backdrop-filter` 使用更明显的 blur 和 saturate。
- 面板边缘增加极细白色高光。
- 面板内部使用非常淡的 inset shadow，制造薄玻璃边界。
- 外阴影更柔和，不形成硬边卡片。

正文视觉去卡片化：

- `reader-main` 不再像一个被包住的 card。
- `paper-header` 更像文档标题区，不做巨大 hero。
- 论文标题字号压低，避免压迫正文。
- meta、description 的灰度提高对比度，满足长时间阅读。
- `section-chip` 改成小型 ghost anchors，体量低于正文，不抢视觉焦点。

Chunk 呈现：

- 英文 source 仍在轻框内，但边框更淡、圆角更小、阴影更弱。
- 中文解释直接接在英文卡片下方，不套卡片。
- 英文和中文之间保留淡横线。
- 空中文解释不显示空状态文案，只保持视觉连续。
- Tags 或 keywords 不作为大胶囊标签突出展示；如保留，只能是低对比、小尺寸的 ghost metadata。

## Content Chrome

正常 chunk 阅读时移除这些 header 入口：

- `原文`
- `中文精读`
- `来源`

这些链接只在无 chunk 的 metadata fallback 状态保留，作为真实论文材料入口。这样正常阅读流不会被低频操作打断。

图表与媒体：

- 有真实图片文件时使用统一最大宽度、高度和 `object-fit`。
- 没有真实图片文件时不显示破损图片。
- 未提取 figure 渲染为安静的 lightweight reference，不占用过大高度。
- `figureRefs` 继续支持 `near`、`supporting`、`deferred`。

公式和代码：

- 继续支持 `math`、`code`、`table`、`figure` blocks。
- 公式长行必须可横向滚动或响应式换行，不能撑出横向 overflow。
- 代码块只展示，不执行。
- 本轮不强制引入远程 CDN；如果后续引入 KaTeX 或 MathJax，必须优先考虑静态自托管或 vendored 资产。

## Interaction Fixes

### Right Note Panel Stability

右侧笔记必须有稳定状态机：

- loading：显示同一张 note surface，不白屏。
- 有 note：只替换文本内容。
- note 为空：surface 保持空白，不显示“没有笔记”类文案。
- 切换 paper：先保留 surface，再更新 active chunk 和 note。
- chunk 数据缺失：不让 note panel 消失或高度归零。
- 加载失败：主区域显示错误状态，note panel 仍保持稳定空白面。

实现上避免用条件渲染直接清空 note panel 根节点。

### Section Rail Scroll-Spying

桌面折叠 rail 的 active 状态由当前可见 section 驱动：

- 使用 `IntersectionObserver` 或滚动监听更新 active section。
- active line 只表示当前阅读位置。
- hover wave 是独立交互，不影响 active state。
- rail 的定位绑定在左侧 collapsed container 内，不使用脱离上下文的错误 fixed/static 绝对位置。

### Responsive Controls

同一个左侧按钮在不同断点下语义不同：

- 桌面：展开/折叠左侧目录；折叠后显示章节线 rail。
- 竖屏：打开/关闭论文目录 drawer；不显示章节线 rail。

同一个右侧按钮：

- 桌面：收起/展开右侧平行笔记，并让正文扩展。
- 竖屏：打开/关闭底部笔记 drawer。

## Testing And Acceptance

更新 `tests/paper-reader-requirements.mjs`，至少断言：

- 搜索 placeholder 是 `Searching...`。
- 正常阅读 header 不渲染 `原文`、`中文精读`、`来源` 三个入口。
- 无 chunk fallback 仍保留真实 source/local note 链接。
- 左侧展开目录只显示 paper short title 和 selected pressed state。
- 桌面左侧收起后才显示 section rail。
- 竖屏规则中 section rail 不显示，左侧按钮只控制 paper directory。
- 右侧 note panel root 始终存在，空 note 不显示“没有笔记”文案。
- 搜索层是全局 focus layer。
- 玻璃面板包含更强 blur、边缘 highlight、inset shadow。
- 正文布局不依赖整页大卡片容器。
- figure 无文件时不渲染 broken image。
- 公式、代码、表格仍有样式支持。
- 不新增 `/api/`、localhost、OpenAI、Anthropic、SurrealDB runtime 或 AI answer 依赖。

视觉验收：

- `1280x800`：左目录、中间正文、右笔记稳定，正文不被卡片边距浪费。
- `1024x768`：右笔记默认收起或不挤压正文。
- `390x844`：只显示中间阅读；左按钮打开 paper 目录；不出现章节线 rail。
- 滚动正文时，桌面 collapsed rail 的 active section 更新稳定。
- note 为空时右侧是连续空白拟态纸面，没有断裂和空状态文字。

## Assumptions

- 本轮只修阅读器 shell，不重写 paper 内容质量。
- 当前 `papers/shared/reader.css` 和 `papers/shared/reader.js` 仍是可复用边界。
- `papers/brain-memory-for-ai-agents/` 是当前验证实例，但设计适用于未来所有 `papers/<project-id>/` 子项目。
- 参考页只作为布局经验来源，不改变本项目的水墨风格。
