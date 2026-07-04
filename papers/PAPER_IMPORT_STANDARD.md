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

- `categoryZh`、`relationZh`、`descriptionZh` 优先用于中文 reader。
- `readingFocus` 是中文阅读提示，不是论文摘要；控制在 3 到 5 条。
- `sections[].id` 必须被 `chunks.json` 的 `sectionId` 引用。
- `titleZh` 用于章节 chip 和折叠索引 hover。

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
- 如果图像文件暂时缺失，reader 会跳过，不显示破图或占位符。

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
- 页面截图可以作为临时真实图像资源，但长期最好裁成单独图表。

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
      "canonicalSectionId": "sec-intro",
      "status": "extracted-page"
    }
  ]
}
```

规则：

- `id` 使用稳定编号，例如 `fig-001`。
- `file` 是相对 reading package 的路径。
- `sourcePage` 记录 PDF 页码；HTML 来源可记录 `null`。
- `canonicalSectionId` 指向主要归属章节。
- `status` 可使用 `extracted`, `extracted-page`, `cropped`, `redrawn`, `missing`。

## notes.json Contract

`notes.json` 是平行笔记层。每个 chunk 都必须有一条 note 记录，即使没有笔记。

```json
{
  "paperId": "zhang-2024-memory-mechanism-llm-agents",
  "notes": [
    {
      "chunkId": "ch-001",
      "note": ""
    }
  ]
}
```

规则：

- `chunkId` 必须存在于 `chunks.json`。
- 没有笔记时，`note` 使用空字符串。
- 前端不要显示“这一段还没有笔记”之类的占位文字；空笔记保持连续拟态表面。
- 笔记和 chunk 平行，而不是把所有笔记集中到文末。

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
5. 写 `paper.json`，先定义章节 `sections` 和中文阅读简介。
6. 从源文件抽取论文原文，按完整论点单元划分 chunk。
7. 为每个 chunk 写 `sourceText`，确保它是论文原文或源文件文本，不是摘要。
8. 为每个 chunk 写 `zhTranslation`，只做忠实翻译。
9. 为每个 chunk 写 `zhExplanation`，说明它和当前项目的关系。
10. 把公式写成 `math` block，把代码或伪代码写成 `code` block，把表格写成 `table` block。
11. 抽取或裁剪关键图表，写入 `figures.json`，并用 `figureRefs` 处理跨页图表。
12. 为每个 chunk 在 `notes.json` 写一条 note；没有笔记就写空字符串。
13. 为每个 chunk 在 `embeddings.json` 写一个本地检索向量。
14. 运行 `node tests/paper-reader-requirements.mjs`。
15. 运行 `node tests/paper-import-standard-requirements.mjs`。
16. 运行 `git diff --check`。

## Quality Boundary

一个 reading package 只有在这些条件满足时才算可用：

- 原文、翻译、解释三层分开。
- chunk 边界能服务阅读，而不是机械分块。
- 图表、公式、代码和表格不丢失关键上下文。
- 笔记与正文平行，不在后面集中堆叠。
- 搜索至少覆盖原文、中文翻译和中文解释。
- 页面仍可作为静态 GitHub Pages 文件运行。

如果只能做展示样本，要在计划或提交说明里明确写成 sample，不要把它当作完整论文导入。
