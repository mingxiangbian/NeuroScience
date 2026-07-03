# Paper Reader 玻璃层与线性笔记视觉修正设计

## Summary

本轮只修正 `papers/brain-memory-for-ai-agents/` 阅读器的视觉层级，不改 chunk 数据结构、不改搜索逻辑、不新增后端。

目标是把当前“米色卡片玻璃”调整为更清晰的 **冷白青灰玻璃层**，并把右侧蓝色笔记区从卡片结构改为 **线性边栏**：用一条竖线和正文区分，用横线组织笔记，降低拥挤感。

## Current Problem

当前玻璃效果不明显，核心原因不是 `blur` 不够，而是颜色关系不成立：

- 页面背景是暖米色宣纸，玻璃面板也是暖米白，两者色相和明度太接近。
- 侧栏、工具栏、笔记栏都有完整卡片边界，页面被多个盒子切碎。
- 右侧笔记区带蓝色调和卡片外框，视觉重量偏高，压缩了正文阅读感。
- 玻璃层缺少明确的上方高光、下方淡墨阴影和冷暖对比，因此更像淡色面板。

## Design Direction

采用 **方案 A：冷白青灰玻璃 + 右侧线性笔记**。

### 1. 玻璃层颜色

将主要玻璃变量从暖米白改为冷白青灰：

- light mode：倾向 `rgba(238, 247, 242, 0.42)` 到 `rgba(244, 249, 245, 0.56)`。
- dark mode：保持低明度青黑，但减少蓝色饱和度，避免夜间变成发光色块。
- 保留宣纸背景，不把整页改成冷色；玻璃只作为浮层，与背景形成冷暖差。

玻璃层需要同时具备：

- 半透明底色。
- 较强 `backdrop-filter`。
- 顶部白色高光。
- 底部淡墨阴影。
- 极细冷色边缘，而不是平均一圈重边框。

### 2. 顶栏与左侧目录

顶部栏和左侧目录仍保留玻璃拟态，但降低“卡片感”：

- 圆角可以保留，但从大圆角收敛到更克制的 `14px-18px`。
- 边框改为更淡的上亮下暗层级。
- 背景下方的纸纹和网格需要能透出一点，给 blur 提供可见采样。
- 左侧目录仍保持固定目录功能，不改论文切换交互。

### 3. 右侧笔记区

右侧笔记区改成参考网页那类文档式线性边栏：

- 不再做完整玻璃卡片容器。
- 使用透明背景或极弱半透明底色。
- 用左侧一条细竖线区分正文区。
- 笔记条目之间用细横线分隔。
- 空笔记仍保持连续留白，不显示“没有笔记”类文字。
- 当前段落对应的笔记可用很轻的背景或线色变化提示，但不做大块卡片。

这能保留平行笔记结构，同时让右侧不再像一个独立 dashboard 面板。

### 4. 正文区与 Chunk 卡片

正文区保持主阅读区域的最大权重：

- chunk 容器继续存在，但弱化卡片感。
- 只保留轻线框、顶部层级和微弱阴影。
- section tags 继续低对比，不抢正文。
- 不恢复 `原文 / 中文精读 / 来源` 等普通阅读入口。

### 5. 搜索层

搜索焦点层维持全局玻璃拟态，但同步使用新的冷白青灰玻璃变量：

- 背景 blur 可以更强。
- 搜索结果仍用横线分隔。
- 不新增圆角结果卡片。

## Interaction Rules

- 左侧按钮仍只控制论文目录。
- 右侧按钮仍控制平行笔记显示。
- 竖屏默认只显示中间阅读区，不显示折叠章节线。
- 右侧线性笔记不改变 note 数据结构，也不引入 hover-only 关键信息。

## Non-goals

本轮不做：

- 不改 `papers/brain-memory-for-ai-agents/data/*.json`。
- 不新增 SurrealDB、embedding、AI provider、`/api/` 或 localhost backend。
- 不改 chunk 划分、中文解释质量、公式或图表抽取。
- 不做新的项目页或 Papers 首页改版。

## Test Plan

实现时更新 `tests/paper-reader-requirements.mjs`，至少断言：

- 玻璃变量改为冷白青灰色系，不再以暖米白作为主要玻璃底色。
- 顶栏、左侧目录、搜索焦点层仍使用 `backdrop-filter`。
- 右侧 `.note-panel` 不再使用完整卡片边框结构，改为左侧竖线分隔。
- 笔记条目之间存在横线分隔。
- 空笔记不显示占位文字。
- 移动端仍隐藏右侧笔记区和折叠章节线。
- 继续断言无 backend、无 AI provider、无 SurrealDB runtime。

实现后运行：

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

并用本地预览检查：

- `http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/`
- desktop：顶部栏和左侧目录有明显玻璃层次，右侧是线性笔记，不像卡片。
- mobile：默认只显示正文区，左侧按钮只打开论文目录。

## References

- `NN/g: Glassmorphism: Definition and Best Practices`：玻璃拟态需要半透明、模糊、边缘和背景差异共同成立。
- `Apple Human Interface Guidelines: Materials`：半透明材质应服务层级和上下文，而不是降低可读性。
- `Axess Lab: Glassmorphism Meets Accessibility`：玻璃效果需要保证文字对比度，不能只依赖 blur。
- 用户提供的参考页 `https://ayaskt.github.io/Y3S2/EMFT/EMFT-README.html`：右侧或辅助信息可用线性文档结构替代卡片面板。
