# Paper Import Standard

这个标准适用于 `papers/` 下所有子项目阅读器，不只服务 `brain-memory-for-ai-agents`。任何项目页只要使用当前 reader，都应该把每篇论文整理成同一种 reading package：

`papers/<project-id>/readings/<paper-id>/`

目标是让后续 agent 导入新 paper 时有统一标准：原文、中文翻译、中文解释、图表、公式、表格、代码、笔记和本地检索索引都能稳定被同一个阅读器展示。

## Scope

- `papers/manifest.json` 负责登记项目和 paper 列表。
- `papers/<project-id>/index.html` 负责展示该子项目的 reader 页面。
- `papers/<project-id>/readings/<paper-id>/` 负责保存单篇论文的结构化阅读包。
- 本标准不要求一次导入所有 paper。只有确认质量够的 paper 才设置 `hasReading: true` 并创建 reading package。
- 如果暂时没有可靠原文抽取、翻译或图表，不要伪造完整 reading package；保持 paper 登记即可。

## Required Package Files

每个完整 reading package 必须包含：

- `paper.json`：论文元信息、中文阅读简介、章节索引。
- `chunks.json`：论文原文 chunk、中文翻译、中文解释、结构化 block。
- `notes.json`：与 chunk 平行的个人笔记。
- `embeddings.json`：静态本地检索向量或可替换的本地索引结果。
- `figures.json`：图表元信息和图像文件引用。
- `figures/`：可选目录，用于保存本地图像资源。

最小目录形态：

```text
papers/<project-id>/readings/<paper-id>/
  paper.json
  chunks.json
  notes.json
  embeddings.json
  figures.json
  figures/
```

## Manifest Contract

`papers/manifest.json` 中的 paper 项用于左侧论文目录。字段应保持短而可扫读：

```json
{
  "id": "zhang-2024-memory-mechanism-llm-agents",
  "title": "A Survey on the Memory Mechanism of Large Language Model based Agents",
  "shortTitle": "LLM Agent Memory Survey",
  "hasReading": true,
  "authors": "Zhang et al.",
  "year": 2024,
  "source": "https://arxiv.org/abs/2404.13501",
  "localFile": "pdfs/2024-zhang-survey-memory-llm-agents.pdf",
  "noteFile": "notes-cn/reading-packet-cn.md#..."
}
```

规则：

- `id` 必须和 reading package 文件夹名一致。
- `shortTitle` 用于目录展示，尽量不超过 42 个字符。
- `hasReading: true` 只能在 reading package 完整存在时添加。
- `localFile` 指向项目内 PDF、HTML 或 Markdown 源文件。

## paper.json Contract

`paper.json` 用于中间正文顶部信息区。推荐字段：

```json
{
  "id": "zhang-2024-memory-mechanism-llm-agents",
  "title": "A Survey on the Memory Mechanism of Large Language Model based Agents",
  "shortTitle": "LLM Agent Memory Survey",
  "authors": "Zhang et al.",
  "year": 2024,
  "category": "AI agent memory",
  "categoryZh": "AI 智能体记忆机制综述",
  "relation": "Maps engineering memory modules to agent capabilities.",
  "relationZh": "这篇综述适合作为理解 AI agent memory 的入口。",
  "description": "A survey framing memory as storage, retrieval, update, and reflection.",
  "descriptionZh": "文章讨论智能体怎样把交互经验保存成可检索、可更新、可用于后续决策的记忆结构。",
  "readingFocus": [
    "先抓住 memory 定义。",
    "重点看 writing、management、reading。",
    "评价部分区分直接评价和间接任务表现。"
  ],
  "source": "https://arxiv.org/abs/2404.13501",
  "license": "CC BY 4.0",
  "sourceFile": "../../pdfs/2024-zhang-survey-memory-llm-agents.pdf",
  "noteFile": "../../notes-cn/reading-packet-cn.md#...",
  "sections": [
    {
      "id": "sec-intro",
      "title": "Introduction",
      "titleZh": "引言"
    }
  ]
}
```

规则：

- `sourceMode` 可选，默认视为 `verbatim`。`verbatim` 表示 `sourceText` 来自本地 PDF/HTML/Markdown 的论文原文；`source-linked` 表示源材料是外部网页或不适合整篇复制的文章，reading package 只保存 source-linked 精读锚点和中文阅读转写。
- `source-linked` 包必须在 `paper.json.source` 写外部来源 URL，并且不应在 manifest 中伪造不存在的本地全文文件。
- `categoryZh`、`relationZh`、`descriptionZh` 优先用于中文 reader。
- `readingFocus` 是中文阅读提示，不是论文摘要；控制在 3 到 5 条。
- `sections[].id` 必须被 `chunks.json` 的 `sectionId` 引用。
- `titleZh` 用于章节 chip 和折叠索引 hover。

## Deep Reading Package Standard

复杂 paper 必须写成 deep reading package，尤其是 mechanistic interpretability、AI x neuroscience、方法密集型论文、互动网页型 source-linked essay。deep reading 的目标是减少碎片化：先给读者前提和叙事主线，再进入 chunk 原文、中文转写和项目解释。

### Paper-Level Fields

`paper.json` 可以增加这些字段：

```json
{
  "readingGroups": [
    {
      "id": "group-method",
      "title": "J-lens 与 J-space 的方法前提",
      "summary": "先解释读出工具和表征空间，避免后面证据突兀。"
    }
  ],
  "premises": [
    {
      "title": "不要把 workspace 直接等同于意识体验",
      "body": "这里讨论的是可报告、可调制、可用于推理的功能通达。"
    }
  ],
  "narrativeSpine": [
    {
      "groupId": "group-method",
      "summary": "先理解方法，再读功能证据。"
    }
  ],
  "misreadings": [
    {
      "groupId": "group-workspace-evidence",
      "text": "不要把可线性读出误解为模型一定在因果使用这类信息。"
    }
  ]
}
```

规则：

- `readingGroups` 是本篇 deep reading 的结构来源；每个 group 必须有唯一 `id`、`title`、`summary`。
- `premises` 写正式阅读前必须补齐的前提，控制在 3 到 6 条。
- `narrativeSpine` 必须通过 `groupId` 绑定 `readingGroups`，不能写成独立散句。
- `misreadings` 写常见误读；如果误读明显属于某个 group，必须写 `groupId`，并且该 `groupId` 必须存在于 `readingGroups`。
- `readingGroups` 第一版不要求做成 reader 左侧导航；可以先在正文里作为轻量分组提示。

### Chunk-Level Fields

deep reading chunk 在原有字段外必须增加：

```json
{
  "groupId": "group-workspace-evidence",
  "premise": "如果只是局部特征，它不应同时支持报告、调制和泛化。",
  "claim": "J-space 被作者解释为更全局、更可调制的信息形态。",
  "evidence": [
    "reportability 任务可读出",
    "modulation 干预会改变输出",
    "generalization 不只绑定单一模板"
  ]
}
```

规则：

- `groupId` 必须指向 `paper.json.readingGroups[].id`。
- `premise` 只写一句，说明读这段前需要理解的前提。
- `claim` 只写一句，说明该 chunk 的核心主张。
- `evidence` 最多 3 条，每条写成短语或短句，避免把证据区写成第二篇摘要。
- `claim` 与 `zhExplanation` 不能语义重复。`claim` 回答“这一段主张什么”；`zhExplanation` 回答“它和项目、已有论文或后续问题有什么关系”。
- 如果 `claim` 和 `zhExplanation` 可以互换位置而不影响理解，说明写法失败，需要重写。

### Public Screenshot Crop Boundary

GitHub Pages 是公开页面，所以 deep reading 的本地图像必须遵守最小必要裁剪：

- 只裁当前 `claim` 需要的核心结构、关键坐标轴、必要图例和紧邻 caption。
- 不裁完整长页、完整网页 section、完整实验组面板合集或与当前 `claim` 无关的数据区域。
- 如果完整 figure 过大，优先拆成多个语义裁剪图，而不是把整图缩到难以阅读。
- `figures.json` 必须保留 `sourceUrl`、`sourceAnchor`、`sourceFigure`、`bbox` 或裁剪说明。
- 对互动网页，截取一个有代表性的静态状态，并在 caption 中说明来源是互动网页。
- 无法裁剪时可以保留 `source-linked`，但必须写清原因；不要只放裸链接。

## chunks.json Contract

`chunks.json` 是阅读器最核心的数据。每个 chunk 必须是完整论点单元，避免按固定字数机械切分。

```json
{
  "paperId": "zhang-2024-memory-mechanism-llm-agents",
  "chunks": [
    {
      "id": "ch-001",
      "sectionId": "sec-intro",
      "order": 1,
      "title": "记忆作为智能体能力",
      "sourceText": "Original paper text extracted from the source document.",
      "zhTranslation": "对 sourceText 的忠实翻译。",
      "zhExplanation": "这一段对当前项目有什么意义的解释。",
      "blocks": [],
      "figureRefs": [],
      "keywords": ["agent", "memory", "retrieval"]
    }
  ]
}
```

字段规则：

- `id` 使用稳定的 `ch-001`、`ch-002` 格式；后续不要因为插入 chunk 轻易重排旧 id。
- `sectionId` 必须存在于 `paper.json.sections`。
- `title` 是中文短标题，用于正文中的段落标题；不要直接塞完整论文标题。
- `sourceText` 必须来自论文原文或源文件文本。它可以是经过排版清理的论文原文，但不能写成 agent 自己的英文摘要。
- `zhTranslation` 是 `sourceText` 的忠实翻译，不加入项目判断，不扩写。
- `zhExplanation` 是解释、评注和项目关联，可以写“这一段为什么重要”。
- `keywords` 用于本地检索和后续 embedding，保持少量关键术语即可。

### Source Mode

两种导入模式：

- `verbatim`：用于本地 PDF、PMC HTML、开放全文 HTML 或 Markdown。`sourceText` 保存论文原文或源文件原文，`zhTranslation` 做忠实翻译，图表优先保存真实来源图或语义裁剪图。
- `source-linked`：用于外部 web essay、互动网页或版权/体量上不适合整篇复制的来源。`sourceText` 保存英文 source-linked reading anchor，也就是围绕来源段落写成的非整篇复制精读锚点；`zhTranslation` 是这段本地 anchor 的中文阅读转写，不是整篇文章的完整翻译；`zhExplanation` 继续承担项目解释。

`source-linked` chunk 必须额外包含：

```json
{
  "sourceMode": "source-linked",
  "sourceAnchor": "The Jacobian Lens",
  "sourceSection": "Methods",
  "sourceUrl": "https://transformer-circuits.pub/2026/workspace/index.html#methods"
}
```

规则：

- `sourceAnchor` 写源网页的小节、图号或稳定锚点名称；`sourceUrl` 必须是可打开的外部锚点 URL，优先使用页面内 hash；`sourceSection` 写读者可在源网页中定位的上级章节。
- 不要把 `source-linked` 包写成完整搬运；它的职责是建立可核对、可搜索、可精读的阅读入口。
- 如果后续确认许可证允许全文本地化，可以单独把模式升级为 `verbatim`，并补齐本地源文件。

### Chunk Boundary

chunk 边界优先级：

1. 完整论点单元。
2. 原文段落群。
3. 图表、公式或代码引用附近的上下文。
4. 章节结构。

不要按固定字数切分。一个 chunk 可以跨原文多个短段，但不能把一个公式、图表说明或关键论证拆断。

如果原文第 3 页引用第 4 页图表，chunk 仍以论点为中心，同时用 `figureRefs` 召回图表。

## Block Types

`blocks` 控制中间原文卡片里的结构化展示。支持五种类型：`paragraph`、`math`、`code`、`table`、`figure`。

### paragraph

```json
{
  "type": "paragraph",
  "text": "Original paragraph text."
}
```

`paragraph.text` 应和 `sourceText` 对齐，可以拆成多个段落展示。

### math

```json
{
  "type": "math",
  "label": "Cosine retrieval",
  "latex": "score(q,m_i)=\\frac{q\\cdot m_i}{\\lVert q\\rVert\\lVert m_i\\rVert}"
}
```

规则：

- `latex` 保存原始 LaTeX 或可渲染的公式文本。
- 阅读器使用 KaTeX 渲染 `latex`；优先使用 KaTeX 支持的标准 LaTeX 语法。
- 不要把 `$...$` 或 `$$...$$` 分隔符写进 `latex` 字段；字段里只放公式主体。
- 如果原文公式过复杂且 KaTeX 不支持，保留原始公式文本，并在相邻解释中说明该公式含义。
- 公式上下文仍要保留在 `sourceText` 或相邻 `paragraph` 中。
- 不要只放公式而丢掉公式解释。

### code

```json
{
  "type": "code",
  "language": "python",
  "caption": "Reader-side retrieval sketch",
  "code": "query_vector = embed(current_question)"
}
```

规则：

- 如果代码来自论文，保留论文原始代码或伪代码。
- 如果是 reader-side sketch，必须在 `caption` 或 `zhExplanation` 中说明它不是论文原始实现。

### table

```json
{
  "type": "table",
  "caption": "Memory sources",
  "columns": ["Source type", "Meaning"],
  "rows": [
    ["Inside-trial", "Current local context"]
  ]
}
```

规则：

- 表格用于结构化论文表格或阅读器侧整理。
- 如果是阅读器侧整理，`caption` 要标明不是论文原表。

### figure

```json
{
  "type": "figure",
  "id": "fig-001",
  "relation": "near"
}
```

规则：

- `id` 必须存在于 `figures.json`。
- `relation` 使用 `near`、`supporting` 或 `deferred`。
- 如果图像文件暂时缺失但 `figures.json` 有 `sourceUrl`，reader 会显示 source-linked 图表卡片；如果连 `sourceUrl` 也没有，reader 会跳过，不显示破图或占位符。

## Cross-Page Figure Rules

学术论文经常出现文字和图表跨页分离。用 `figureRefs` 表达这种关系：

```json
{
  "figureRefs": [
    {
      "id": "fig-004",
      "relation": "deferred"
    }
  ]
}
```

`relation` 含义：

- `near`：图表就在当前 chunk 附近，适合放进 `blocks`。
- `supporting`：图表支持当前论点，但不一定紧邻原文。
- `deferred`：原文引用了图表，但图表在后续页或其他位置。

原则：

- 重要图表宁可用 `figureRefs` 召回，也不要让读者只看到文字。
- 图片资源必须统一视觉尺寸；前端会用固定高度和 `object-fit: contain` 控制显示。
- 不要默认截取整页论文作为 figure。优先只截取当前 chunk 需要的图、表、框图、算法块或关键公式区域。
- 页面截图只能作为临时 fallback；如果必须使用整页截图，必须标记为 `page-fallback`，后续导入 agent 要把它视为待裁剪资源。

### Figure Crop Rules

图像资源应按语义对象裁剪，而不是按 PDF 页面裁剪：

- `source-figure`：优先模式，从 HTML、PMC、期刊页面或原始补充资源中取得真实来源图。
- `semantic-crop`：推荐模式，从 PDF 渲染页中只裁出图表主体、caption 和少量边距。
- `paper-extract`：从 PDF 内嵌图片对象直接抽取出的真实来源图。
- `manual-redraw`：fallback 模式，只用于真实图无法清晰裁取、或需要读者侧解释图时。
- `source-linked`：外部网页型模式，只保存 `sourceUrl`、`sourceAnchor`、`sourceFigure` 和 caption，不复制互动图或整页截图。
- `page-fallback`：临时模式，表示当前只能提供整页截图；不能作为长期合格图像。

真实图、真实来源图或 source-backed figure 必须优先于重绘图。导入 agent 的顺序是：

1. 先找 HTML/PMC/期刊页面里的 `source-figure`。
2. 找不到时渲染 PDF 页面并做 `semantic-crop`。
3. PDF 有可用图片对象时可以用 `paper-extract`。
4. 只有上述方式都不适合，才使用 `manual-redraw`。
5. 如果来源是互动网页且不宜复制图像，用 `source-linked` 保存来源锚点。
6. `page-fallback` 只能临时使用，不能作为合格 reading package 的最终图。

每个已裁剪图像应在 `figures.json` 中记录 `bbox`，用于让后续 agent 追溯裁剪来源：

```json
{
  "cropMode": "semantic-crop",
  "bbox": {
    "x": 210,
    "y": 820,
    "width": 620,
    "height": 380
  }
}
```

`bbox` 使用源图像或源 PDF 渲染图的像素坐标，字段必须包含 `x`、`y`、`width`、`height`。如果 `cropMode` 是 `source-figure` 或 `paper-extract`，可以省略 `bbox`，但必须写清 `sourceFigure` 或 `sourcePage`。如果 `cropMode` 是 `manual-redraw`，必须记录：

```json
{
  "cropMode": "manual-redraw",
  "redrawType": "reader-side-fallback",
  "sourceBasis": "Redrawn from the paper's Figure 1 taxonomy and caption because the source image is unavailable or unsuitable for direct display."
}
```

如果 `cropMode` 是 `page-fallback`，`bbox` 可以省略，但 `status` 不能写成 `cropped`。

## figures.json Contract

```json
{
  "paperId": "zhang-2024-memory-mechanism-llm-agents",
  "figures": [
    {
      "id": "fig-001",
      "label": "Figure 1",
      "file": "figures/figure-1-memory-module.png",
      "caption": "Memory-module overview.",
      "sourcePage": 1,
      "cropMode": "semantic-crop",
      "bbox": {
        "x": 210,
        "y": 820,
        "width": 620,
        "height": 380
      },
      "canonicalSectionId": "sec-intro",
      "status": "cropped"
    }
  ]
}
```

规则：

- `id` 使用稳定编号，例如 `fig-001`。
- `file` 是相对 reading package 的路径。
- `sourcePage` 记录 PDF 页码；HTML 来源可记录 `null`。
- `sourceFigure` 记录论文中的图号，例如 `Figure 1` 或 `Fig. 3`。
- `cropMode` 使用 `source-figure`、`semantic-crop`、`paper-extract`、`manual-redraw` 或 `page-fallback`。
- `source-linked` figure 可以不写 `file`，但必须写 `sourceUrl`、`sourceAnchor`、`sourceFigure`，并把 `status` 设为 `source-linked`。
- `bbox` 记录裁剪区域；`semantic-crop` 图像必须提供。
- `manual-redraw` 必须写 `redrawType: "reader-side-fallback"` 和 `sourceBasis`。
- `canonicalSectionId` 指向主要归属章节。
- `status` 可使用 `cropped`、`extracted`、`page-fallback`, `redrawn`, `missing`。

## notes.json Contract

`notes.json` 是平行笔记层。每个 chunk 都必须有一条 note 记录，即使没有笔记。

```json
{
  "paperId": "zhang-2024-memory-mechanism-llm-agents",
  "noteMode": "public",
  "noteSource": "polished-local-annotations",
  "updatedAt": "2026-07-07",
  "notes": [
    {
      "chunkId": "ch-001",
      "note": "经过整理的稳定公开笔记。"
    }
  ]
}
```

规则：

- `chunkId` 必须存在于 `chunks.json`。
- 没有笔记时，`note` 使用空字符串。
- 默认模式下，所有 `note` 必须保持空字符串；个人阅读批注先留在浏览器本地。
- 只有经过人工确认、润色并准备公开上传的笔记，才可以设置 `noteMode: "public"` 并写入非空 `note`。
- `noteMode: "public"` 至少需要一条非空 note；其余 chunk 仍可保留空字符串。
- `noteSource` 可说明来源，例如 `polished-local-annotations`。
- 前端不要显示“这一段还没有笔记”之类的占位文字；空笔记保持连续拟态表面。
- 笔记和 chunk 平行，而不是把所有笔记集中到文末。

## Runtime Local Annotations

本地高亮和批注是 reader runtime 的个人层，不属于 reading package 源文件。

- 前端可以用 `localStorage` 保存 `paperReader.annotations.v1.<projectId>`。
- annotation 可以记录 `paperId`、`chunkId`、`selectedText`、`matchIndex`、`mode`、`note` 和 `highlightActive`。
- 当前 chunk 的自由笔记可以记录在同一个本地 store 的 `chunkNotes` 中，key 使用 `paperId:chunkId`。
- `Highlight` 只恢复原文高亮；`Note` 同时把选中原文作为引用放入右侧平行笔记区。
- 本地 annotation 和自由笔记默认不写回 `notes.json`，也不要求进入 GitHub commit。
- 如果需要长期沉淀，必须先导出、润色、回答其中的问题，再以 `noteMode: "public"` 写入 `notes.json`。

## embeddings.json Contract

`embeddings.json` 是静态检索索引。当前 reader 可以用本地向量或轻量关键词向量，不要求在线 provider。

```json
{
  "paperId": "zhang-2024-memory-mechanism-llm-agents",
  "model": "static-domain-keyword-v1",
  "dimensions": ["agent", "retrieval", "embedding"],
  "indexedFields": ["sourceText", "zhTranslation", "zhExplanation"],
  "items": [
    {
      "chunkId": "ch-001",
      "vector": [0.12, 0.44, 0.31]
    }
  ]
}
```

规则：

- `indexedFields` 必须包含 `sourceText`、`zhTranslation`、`zhExplanation`。
- deep reading package 的 `indexedFields` 还必须包含 `premise`、`claim`、`evidence`，让搜索能命中前提、主张和证据。
- 每个 chunk 必须有一个向量项。
- `vector` 必须是有限数字数组。
- 如果未来改用真实 embedding model，向量可以离线生成后提交为静态 JSON。
- 不引入 `/api/`、localhost backend、provider key、SurrealDB 或在线 AI provider 依赖。
- SurrealDB 和 embedding 可以作为未来架构参考，但当前 GitHub Pages reader 必须保持纯静态。

## Import Checklist

导入新 paper 时按这个顺序执行：

1. 在 `papers/manifest.json` 登记 paper，先写 `id/title/shortTitle/authors/year/source/localFile/noteFile`。
2. 确认本地源文件存在，例如 PDF、HTML 或 Markdown。
3. 只有准备创建完整 reading package 时，才设置 `hasReading: true`。
4. 创建 `papers/<project-id>/readings/<paper-id>/`。
5. 写 `paper.json`，先定义章节 `sections` 和中文阅读简介；复杂 paper 还要写 `readingGroups`、`premises`、`narrativeSpine`、`misreadings`。
6. 从源文件抽取论文原文，按完整论点单元划分 chunk。
7. 为每个 chunk 写 `sourceText`，确保它是论文原文或源文件文本，不是摘要。
8. 为每个 chunk 写 `zhTranslation`，只做忠实翻译。
9. 为每个 chunk 写 `zhExplanation`，说明它和当前项目的关系。
10. deep reading package 为每个 chunk 写 `groupId`、`premise`、`claim`、`evidence`；`premise` 和 `claim` 各一句，`evidence` 最多 3 条，且 `claim` 与 `zhExplanation` 不能语义重复。
11. 把公式写成 `math` block，把代码或伪代码写成 `code` block，把表格写成 `table` block。
12. 先抽取真实来源图，再裁剪关键图表，最后才考虑 reader-side fallback 重绘；公开 GitHub Pages 图像必须使用最小必要裁剪；写入 `figures.json`，并用 `figureRefs` 处理跨页图表。
13. 为每个 chunk 在 `notes.json` 写一条 note；没有笔记就写空字符串。
14. 为每个 chunk 在 `embeddings.json` 写一个本地检索向量；deep reading package 的 `indexedFields` 要包含 `premise`、`claim`、`evidence`。
15. 运行 `node scripts/validate-reading-packages.mjs <project-id>`，例如 `node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents`。
16. 运行 `node tests/paper-reader-requirements.mjs`。
17. 运行 `node tests/paper-import-standard-requirements.mjs`。
18. 运行 `git diff --check`。

## Quality Boundary

一个 reading package 只有在这些条件满足时才算可用：

- 原文、翻译、解释三层分开。
- chunk 边界能服务阅读，而不是机械分块。
- 图表、公式、代码和表格不丢失关键上下文。
- 笔记与正文平行，不在后面集中堆叠。
- 搜索至少覆盖原文、中文翻译和中文解释。
- 页面仍可作为静态 GitHub Pages 文件运行。

如果只能做展示样本，要在计划或提交说明里明确写成 sample，不要把它当作完整论文导入。
