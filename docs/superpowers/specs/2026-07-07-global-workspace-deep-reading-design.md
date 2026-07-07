# Global Workspace Deep Reading Design

Date: 2026-07-07
Status: Draft design, awaiting review

## Summary

把 `Global Workspace in LMs` 从“source-linked 精读锚点集合”升级成这个项目下的第一份深读模板。目标不是搬运整篇网页原文，而是让读者在当前 Paper Representation 阅读器里先获得必要前提、研究问题、证据链和项目关联，再逐段阅读来源锚点、中文转写和个人笔记。

这次设计同时更新 `Paper Import Standard` 的方向：以后所有复杂 AI x neuroscience / mechanistic interpretability paper，都需要在 reading package 里显式保存阅读前提、叙事主线、论点结构、关键证据截图和常见误读边界。

## Problem

当前 `gurnee-2026-global-workspace-language-models` reading package 能打开，也能通过来源链接追溯，但仍有三个核心问题：

- 信息太碎。chunk 更像逐条索引，缺少“为什么先看这篇、这篇在项目里解决什么问题、读者需要先知道什么”的连续铺垫。
- 前提不足。`J-lens`、`J-space`、global workspace、reportability、broadcast、alignment auditing 等概念直接出现，会让阅读突兀。
- 图像证据弱。很多 figure 只有外部网页链接，没有本地裁剪截图；读者必须跳出阅读器才能看到关键结构图或实验结果。

这些问题不是 UI 本身造成的，而是 reading package 数据层缺少深读标准。只修样式不能解决“读不懂”和“证据链断裂”。

## Goals

- 先把 `Global Workspace in LMs` 做成深读模板，不同时重写所有既有 paper。
- 在 `paper.json` 增加中文阅读前提、叙事主线、常见误读和限制。
- 在 `chunks.json` 增加 `groupId`、`premise`、`claim`、`evidence`，让每个 chunk 不只是片段，而是可读的论证单元。
- 用本地裁剪截图承载关键图表证据，同时保留 `sourceUrl`、`sourceAnchor` 和来源说明。
- 更新 `PAPER_IMPORT_STANDARD.md`，让后续 agent 导入新 paper 时有同一套深读要求。
- 保持当前静态 GitHub Pages 架构，不新增后端、AI provider、SurrealDB runtime 或在线同步。

## Non-Goals

- 不复制或翻译整篇外部网页全文。
- 不把 source-linked package 升级成 verbatim package，除非之后确认许可证和全文本地化边界。
- 不重做三栏阅读器架构。
- 不新增 AI 自动回答、实时文件同步或数据库写入。
- 不在本轮同时修完所有 reading package。

## Deep Reading Content Model

### paper.json

`paper.json` 继续保存元信息，同时新增深读入口字段：

```json
{
  "premises": [
    {
      "title": "这篇文章讨论的不是普通注意力头解释",
      "body": "它把语言模型内部能被读出、调制和泛化的信息子空间，与 global workspace 理论中的可报告、可广播信息进行类比和检验。"
    }
  ],
  "narrativeSpine": [
    "先说明为什么 global workspace 是这里的比较对象。",
    "再解释 J-lens 和 J-space 如何把模型内部状态投影成可测对象。",
    "然后阅读 report、modulation、reasoning、generalization、selectivity 五组证据。"
  ],
  "misreadings": [
    "不要把模型中的 workspace 直接等同于生物大脑的意识机制。",
    "不要把可线性读出的信息误解为模型一定在因果使用这类信息。"
  ]
}
```

字段规则：

- `premises` 是正式阅读前必须补齐的前提，使用中文，控制在 3 到 6 条。
- `narrativeSpine` 是整篇文章的阅读路线，按实际论证顺序写。
- `misreadings` 写容易误解的边界，用于防止把类比当作机制证据。
- 这些字段服务读者，不替代论文摘要、作者 claim 或原文来源。

### Reading Groups

`Global Workspace in LMs` 第一版深读分成 7 个 reading groups：

```json
[
  {
    "id": "group-project-fit",
    "title": "为什么这篇属于记忆与智能体项目"
  },
  {
    "id": "group-method",
    "title": "J-lens 与 J-space 的方法前提"
  },
  {
    "id": "group-workspace-evidence",
    "title": "workspace-like 行为证据"
  },
  {
    "id": "group-structure",
    "title": "层级、容量与广播结构"
  },
  {
    "id": "group-auditing",
    "title": "用 workspace 表征做行为审计"
  },
  {
    "id": "group-training",
    "title": "反事实反思训练"
  },
  {
    "id": "group-limits",
    "title": "限制、误读与下一步问题"
  }
]
```

规则：

- group 用于给 chunk 提供上下文，不替代章节目录。
- 当前 22 个 chunk 可以合并或重排为更少的论证单元，但旧 `ch-xxx` id 一旦发布后不要无意义重排。
- UI 可以先只把 group 标题作为段落上方的轻量提示，不需要新增复杂导航。

### chunks.json

每个 chunk 保留当前字段，并增加深读结构：

```json
{
  "id": "ch-006",
  "groupId": "group-workspace-evidence",
  "title": "可报告信息不是普通局部特征",
  "premise": "如果一个内部表征只是局部相关特征，它不应稳定支持 report、调制和跨任务泛化。",
  "claim": "作者把 J-space 中可读出的 workspace information 视作一种更全局、更可调制的信息形态。",
  "evidence": [
    "Reportability 任务显示相关信息可以被 probe 读出。",
    "Modulation 结果显示干预这类方向会影响模型行为。",
    "Generalization 结果显示该表征不只绑定在单一 prompt 模板上。"
  ],
  "sourceText": "A source-linked reading anchor grounded in the external article section.",
  "zhTranslation": "对 source-linked anchor 的中文转写。",
  "zhExplanation": "解释这段为什么服务当前项目。"
}
```

字段规则：

- `premise` 写读这段前必须先接受或理解的条件。
- `claim` 写这一 chunk 的核心主张，必须和来源锚点可核对。
- `evidence` 写支撑 claim 的证据点，可以引用 figure、实验名、来源小节或作者报告的结果。
- `sourceText` 在 `source-linked` 模式下仍是本地阅读锚点，不伪装成网页全文原文。
- `zhTranslation` 翻译 `sourceText`，不混入额外评注。
- `zhExplanation` 承担项目解释、读法提醒，以及与已有论文的连接。

## Screenshot And Figure Policy

关键图表应从源网页或原始论文中裁剪成本地图片，放在 reading package 的 `figures/` 目录里。默认不使用整页截图。

`figures.json` 使用这个形态：

```json
{
  "id": "fig-j-lens",
  "title": "J-lens maps residual stream directions into token-level effects",
  "titleZh": "J-lens 把残差流方向映射为 token 层影响",
  "file": "figures/fig-j-lens.png",
  "sourceUrl": "https://transformer-circuits.pub/2026/workspace/index.html#methods",
  "sourceAnchor": "The Jacobian Lens",
  "sourceFigure": "Methods figure",
  "cropMode": "web-screenshot-crop",
  "bbox": "cropped to the method diagram and caption area only",
  "status": "cropped",
  "captionZh": "这张图用于说明后续 J-space 证据的测量工具，不是最终结论本身。"
}
```

规则：

- 优先裁剪“读者理解当前 claim 所必需”的图，不把整页网页截图塞进阅读器。
- 每张截图必须保留 `sourceUrl` 和 `sourceAnchor`，便于回到原始上下文核对。
- 交互图只截取一个有代表性的静态状态，并在 caption 中说明它来自交互网页。
- 如果某张图因为交互、版权或技术原因暂时不能裁剪，可以保留 `source-linked` 记录，但必须写清楚原因和下一步。
- 截图的视觉目标是证据可读，不是装饰；统一最大宽度、最大高度和 object-fit，避免图表大小失控。

`Global Workspace in LMs` 第一版至少需要这些本地证据图：

- workspace / project overview 图。
- `J-lens` 或 `J-space` 方法图。
- reportability / modulation / generalization 中至少两张直接证据图。
- layer / capacity / broadcast structure 相关图。
- alignment auditing 或 counterfactual reflection training 的关键结果图。

## Reader UI Impact

这轮实现不需要重做阅读器，只需让现有中间正文能展示新增深读字段：

- 在论文顶部显示中文 `premises` 和 `narrativeSpine`，位置在简介下方、chunk 列表上方。
- chunk 标题下方显示一行较轻的 `premise`。
- `claim` 和 `evidence` 放在原文卡片之前或之后的轻量结构区，避免做成厚重卡片。
- 图表跟随 `figureRefs` 出现在相关 chunk 附近，仍使用当前统一 figure 样式。
- 右侧 parallel note 行为不变：滚动到哪个 chunk，就显示哪个 chunk 的笔记和本地 annotation。
- 搜索仍覆盖 `sourceText`、`zhTranslation`、`zhExplanation`，新增字段可纳入本地索引，但不新增后端语义服务。

## Paper Import Standard Update

`PAPER_IMPORT_STANDARD.md` 新增一节 `Deep Reading Package Standard`，用于复杂论文：

- 复杂 paper 必须有 `premises`、`narrativeSpine`、`misreadings`。
- 每个 chunk 必须说明 `premise`、`claim`、`evidence`。
- 如果 paper 是 mechanistic interpretability、AI x neuroscience 或方法密集型文章，不能只给短摘要式 chunk。
- 关键证据图优先使用本地裁剪截图；无法裁剪时必须保留原因，而不是只丢一个裸链接。
- `source-linked` 模式允许不保存完整原文，但不允许缺少可核对来源和证据链。
- agent 导入新 paper 时，必须先写“这篇为什么属于当前项目”，再写 chunk。

## Validation Plan

实现时同步更新或新增这些验证：

- `tests/paper-import-standard-requirements.mjs`
  - 断言标准包含 `Deep Reading Package Standard`。
  - 断言标准要求 `premises`、`narrativeSpine`、`misreadings`。
  - 断言标准要求 `premise`、`claim`、`evidence`。
  - 断言标准要求本地裁剪截图和来源元数据。
- `tests/paper-reader-requirements.mjs`
  - 断言 reader 能显示 `premises` 和 `narrativeSpine`。
  - 断言 chunk 能渲染 `premise`、`claim`、`evidence`。
  - 断言新增字段不会破坏平行笔记、annotation 和搜索。
- `scripts/validate-reading-packages.mjs`
  - 对 `source-linked` 包允许短锚点，但要求 `sourceUrl`、`sourceAnchor`。
  - 对深读包要求关键 figures 有本地 `file` 或明确 `status`。

实现后运行：

```text
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

## Risks And Boundaries

- 版权边界：本设计只要求选择性证据截图和 source-linked anchor，不要求复制整篇外部文章。
- 图像稳定性：源网页布局可能变化，所以本地截图必须保存来源元数据和裁剪说明。
- 内容质量：深读字段不能写成泛泛总结，必须围绕“前提、主张、证据、限制”组织。
- 范围控制：本轮模板只锁定 `Global Workspace in LMs`，后续再按这个标准补其他 paper。
- 工程边界：保持静态站点；SurrealDB、在线 embedding、RAG 回答不进入这轮实现。

## Review Questions

- 这个深读模板是否足够解决“信息碎片化”和“前提不足”的问题？
- 第一版本地截图最小集是否覆盖了理解这篇文章所需的关键证据？
- `premise / claim / evidence` 是否是后续 agent 导入新 paper 时能稳定执行的标准？
- 是否需要把 `readingGroups` 做成正式 UI 导航，还是先只作为 chunk 上下文信息？
