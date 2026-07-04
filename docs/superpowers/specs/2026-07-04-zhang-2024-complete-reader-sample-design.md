# Zhang 2024 完整阅读样板设计

Date: 2026-07-04
Status: Approved design, awaiting implementation plan

## Summary

本 spec 聚焦 `papers/brain-memory-for-ai-agents/` 里当前打开的 Zhang 2024 paper：

`A Survey on the Memory Mechanism of Large Language Model based Agents`

目标是把它从 4 个 demo chunk 升级成一篇真正可读的完整样板论文。这个样板会定义后续 `papers/<project-id>/readings/<paper-id>/` 的内容标准，但本轮不批量改其它论文。

本轮重点是中间正文和内容包质量：

- chunk 显示论文真实原文，而不是概括性改写。
- 横线下展示中文翻译和必要精读解释。
- 文章简介改成中文。
- 真实图表和公式进入阅读流，不再用空占位伪装。
- 右侧平行笔记继续跟 chunk 对齐，没有笔记时保持连续空白拟态。

## Scope

### In Scope

- 只把 `zhang-2024-memory-mechanism-llm-agents` 做成完整样板。
- 扩展该 paper 的 `paper.json`、`chunks.json`、`notes.json`、`embeddings.json`、`figures.json` 和本地图表资源。
- 小幅调整 `reader.js` / `reader.css`，让现有阅读器能清晰展示更长、更真实的论文内容。
- 更新测试，锁定完整样板的结构、内容质量和图表/表格/公式渲染要求。

### Out Of Scope

- 不批量补完 McClelland、Yassa 或其它 paper。
- 不新增后端、`/api/`、SurrealDB、在线 AI provider 或实时同步。
- 不做 AI 自动问答。
- 不重做整体三栏布局、搜索、左侧目录、右侧笔记的大结构。
- 不伪造论文原图、原表或原文。

## Current Problems

当前阅读器结构已经存在，但内容包仍是 demo：

- 当前 Zhang 2024 只有 4 个 chunk；参考 ar5iv HTML，该论文实际有大量段落、section、公式、图和表。
- `sourceText` 多数是导读式概括，不是论文原文。
- `figures.json` 中图像 `file` 为空，页面只能显示占位。
- 表格是手写示例，不能代表论文真实表格。
- 标题下方 `relation` / `description` 是英文，和中文阅读器氛围不统一。
- 公式和代码渲染入口存在，但内容密度太低，无法验证完整论文阅读体验。

## Target Reading Experience

中间正文要像“论文精读工具”，不是 PDF viewer，也不是普通 Markdown：

```text
chunk 短标题

[英文原文卡片]
真实论文原文段落
公式 / 表格 / 图像 / 图注

----------------

中文翻译
中文精读解释
```

阅读者应该能顺着中间正文完成这篇 paper 的主线阅读，同时通过右侧笔记看到当前 chunk 的个人理解或研究连接。

## Content Coverage

第一版完整样板不要求复制整篇论文所有 154 个段落，但必须覆盖论文主干，不再停留在摘要级别。

推荐覆盖范围：

- Abstract
- Introduction
- Related surveys 的定位性内容
- What is the memory of LLM-based agent
- Why we need memory in LLM-based agent
- How to implement memory
- How to evaluate memory
- Future directions / open problems
- Conclusion 或总结性段落

目标 chunk 数量：

- 最少 18 个高质量 chunk。
- 推荐 22-30 个 chunk。
- 每个 chunk 是完整论点单元，不按固定字数机械切分。

每个 chunk 原文长度：

- 常规 chunk 约 1-3 个英文段落。
- 如果公式、图或表是论点核心，可以单独形成一个 chunk。
- 不把过长 section 塞进单个 chunk。

## Chunk Content Standard

`chunks.json` 中每个 chunk 必须满足：

- `id` 使用稳定顺序，例如 `ch-001`。
- `sectionId` 指向 `paper.json.sections` 中存在的 section。
- `order` 是全局阅读顺序。
- `title` 可选但推荐，使用中文短标题。
- `sourceText` 存真实英文原文纯文本，用于搜索、embedding 和 fallback。
- `blocks` 存富文本结构，负责前端渲染。
- `zhTranslation` 存忠实中文翻译。
- `zhExplanation` 存必要精读解释。
- `figureRefs` 只引用 `figures.json` 中的 figure，不直接写死图片路径。
- `keywords` 用于本地搜索和后续 embedding 维护。

示例结构：

```json
{
  "id": "ch-001",
  "sectionId": "abstract",
  "order": 1,
  "title": "记忆模块为什么重要",
  "sourceText": "Large language model (LLM) based agents have recently attracted much attention...",
  "blocks": [
    {
      "type": "paragraph",
      "text": "Large language model (LLM) based agents have recently attracted much attention..."
    }
  ],
  "zhTranslation": "基于大语言模型的智能体最近受到了学术界和工业界的广泛关注……",
  "zhExplanation": "这一段建立全文问题：memory module 不是附属功能，而是让 LLM-based agent 具备持续交互和自我演化能力的关键模块。",
  "figureRefs": [],
  "keywords": ["LLM agent", "memory module", "self-evolution"]
}
```

## English Source Area

英文原文仍放在轻量卡片中，但要更适合长文：

- 卡片不能太厚、太灰或太像独立模块。
- 行宽保持易读，避免 13 寸或分屏时变成过窄竖条。
- 多段原文之间有自然段距。
- 学术元素和正文属于同一阅读流，不要被视觉上割裂成完全不同组件。

`blocks` 支持：

- `paragraph`
- `math`
- `code`
- `table`
- `figure`
- 后续可扩展 `quote` 或 `callout`，但本轮不必实现。

## Chinese Translation And Explanation

中文区分两层：

1. `zhTranslation`：忠实翻译原文，尽量保持论文语义。
2. `zhExplanation`：精读解释，说明这一段在论文论证中的作用，以及和“记忆与智能体”项目的关系。

前端展示方式：

- 横线下先展示中文翻译。
- 翻译后用较轻的样式展示精读解释。
- 如果 `zhExplanation` 为空，只显示翻译，不显示空状态文字。
- 如果 `zhTranslation` 为空，说明数据不达标，测试应失败。

## Paper Header

标题下方简介改中文。`paper.json` 可新增中文展示字段，不删除现有英文字段：

- `categoryZh`
- `relationZh`
- `descriptionZh`
- `readingFocus`

展示顺序：

1. 中文类别，例如 `AI 智能体记忆`
2. 英文论文标题
3. 作者和年份
4. 中文定位：这篇论文为什么属于“记忆与智能体”
5. 中文阅读重点：读这篇时重点看哪些问题

示例：

```json
{
  "categoryZh": "AI 智能体记忆",
  "relationZh": "这篇综述把 LLM-based agent 的 memory module 拆成定义、必要性、实现方式和评价方式，是本项目理解工程记忆系统的入口论文。",
  "descriptionZh": "阅读重点不是记住所有系统名称，而是理解 memory 在 agent 中承担的写入、读取、管理和评估角色。",
  "readingFocus": [
    "memory module 和 long context 的区别",
    "memory writing、reading、management 的工程分工",
    "评价 memory system 时为什么不能只看存储量"
  ]
}
```

## Figures

图表必须从真实来源进入本地项目，不再保留空 `file` 占位作为主要展示。

优先抽取：

- Figure 1：memory module 的重要性。
- memory reading / writing / management process 相关图。
- memory sources / forms / operations overview。
- 评价或 future direction 相关关键表格/图。

资源位置：

```text
papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/
```

`figures.json` 字段：

- `id`
- `label`
- `file`
- `caption`
- `sourcePage` 或 `sourceSection`
- `canonicalSectionId`
- `status`

如果某个图无法可靠抽取：

- 可以暂不引用。
- 不允许在正常阅读流中显示空占位。
- 可在数据备注里标注 `status: "not-extracted"`，但不要渲染成假图。

## Tables

表格分两类：

1. 论文原表：如果能稳定抽取成结构化 rows/columns，就用 `table` block 渲染。
2. reader-side summary table：如果原表过复杂，可做中文/英文摘要表，但 caption 必须明确标注为阅读器整理。

表格渲染要求：

- 不出现横向溢出破坏页面。
- 表头清楚。
- 长单元格自动换行。
- 移动端可横向滚动。
- 不出现浏览器 accessibility 树里那种重复 row/column 视觉错乱。

## Math And Code

Zhang 2024 中公式数量不少，至少要保证：

- 关键公式以 `math` block 表示。
- LaTeX 可读，不挤进普通段落。
- 公式块支持横向滚动或折行。
- 如果引入 MathJax/KaTeX，优先静态自托管；如果暂不引入渲染库，必须提供清晰的 LaTeX fallback。

代码块不是这篇 survey 的核心。仅当 chunk 用伪代码解释 retrieval 流程时才保留，但必须明确这是 reader-side sketch，不伪装成论文原文。

## Parallel Notes

右侧笔记继续保持当前设计原则：

- 与当前 chunk 对齐。
- 没有笔记时保持连续空白拟态，不显示“没有笔记”。
- 有笔记时显示简短研究笔记。
- 不把所有 chunk 的笔记堆到右栏。

Zhang 2024 样板至少为关键 chunk 写 6-10 条 note：

- memory 定义
- long context vs memory
- writing / reading / management
- embedding retrieval
- evaluation
- 和神经科学 memory 项目的连接

## Search And Embedding

本轮继续使用当前静态 embedding/search 方向，不接入后端。

要求：

- 新增 chunk 后同步更新 `embeddings.json`。
- 搜索索引覆盖 `sourceText`、`zhTranslation`、`zhExplanation`、`keywords`。
- 搜索结果仍跳转到对应 chunk。
- 不引入 AI answer generation。

Embedding 可以保持当前轻量本地向量方案。完整真实 embedding 以后再做，不阻塞本轮阅读样板。

## Implementation Boundaries

本轮实现时允许改：

- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/paper.json`
- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/chunks.json`
- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/notes.json`
- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/embeddings.json`
- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures.json`
- `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/`
- `papers/shared/reader.js`
- `papers/shared/reader.css`
- `tests/paper-reader-requirements.mjs`

如果需要新增辅助脚本用于抽取或生成数据，脚本应放在项目内清楚命名，并且生成物要可复查。实现计划里再决定是否需要脚本。

## Verification

实现后至少验证：

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

视觉验收：

- Zhang 2024 页面不再只有 4 个 chunk。
- 中间正文能连续阅读主干论文内容。
- 英文原文是真实论文原文。
- 横线下有中文翻译。
- 图像不再显示空占位。
- 表格不破版。
- 标题下方简介为中文。
- 右侧笔记无内容时保持连续空白，不出现空状态文字。
- 移动端中间正文优先显示，不被左右栏挤压。

## Acceptance Criteria

- `zhang-2024-memory-mechanism-llm-agents` 至少包含 18 个 chunk。
- 每个 chunk 都有非空 `sourceText` 和 `zhTranslation`。
- `sourceText` 是论文原文，不是导读式重写。
- 关键 chunk 有 `zhExplanation`。
- `paper.json` 有中文简介字段，前端优先展示中文简介。
- 至少 2 个真实 figure 文件被引用和渲染。
- 至少 1 个真实或明确标注的 reader-side summary table 正常渲染。
- 公式块能以可读方式展示。
- 搜索覆盖新增文本并能跳转到 chunk。
- 不新增后端、AI provider、SurrealDB 或 `/api/` 依赖。

