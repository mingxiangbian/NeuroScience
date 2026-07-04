# Zhang 2024 Complete Reader Sample Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `zhang-2024-memory-mechanism-llm-agents` 从 demo chunk 升级成一个可作为后续论文标准的完整阅读样板。

**Architecture:** 继续使用当前静态 reader：`paper.json` 提供元信息，`chunks.json` 提供正文阅读单元，`figures.json` 提供图像引用，`notes.json` 提供平行笔记，`embeddings.json` 提供本地搜索向量。前端只做最小渲染增强：展示中文简介、`zhTranslation`、真实图像和更稳的表格/公式样式。

**Tech Stack:** Static HTML/CSS/JS, JSON reading packages, Node-based requirement tests, local figure assets under `papers/brain-memory-for-ai-agents/readings/.../figures/`.

---

## File Map

- Modify: `tests/paper-reader-requirements.mjs`
  - Add Zhang 2024 completeness checks.
  - Add `zhTranslation` schema checks.
  - Assert real figure files exist for referenced Zhang figures.
  - Assert reader indexes `zhTranslation`.
- Modify: `papers/shared/reader.js`
  - Prefer Chinese paper metadata fields in header.
  - Render `chunk.title`.
  - Render `zhTranslation` before `zhExplanation`.
  - Include `zhTranslation` in search text and lexical scoring.
  - Skip rendering figure placeholders for figures with no file.
- Modify: `papers/shared/reader.css`
  - Style chunk title, translation, explanation, figures and tables for longer reading.
- Modify: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/paper.json`
  - Add Chinese metadata and richer section structure.
- Modify: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/chunks.json`
  - Replace 4 demo chunks with 18+ high-quality source-backed chunks.
- Modify: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/notes.json`
  - Add matching note entries for every chunk.
- Modify: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/embeddings.json`
  - Add vectors for every new chunk and update `indexedFields`.
- Modify: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures.json`
  - Point at real local figure files.
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/`
  - Store extracted figure assets.

## Task 1: Strengthen Tests First

- [ ] **Step 1: Add failing checks for Zhang 2024 completeness**

Add assertions to `tests/paper-reader-requirements.mjs` after the generic reading package checks:

```js
const zhangBase = new URL(`../papers/${projectId}/readings/zhang-2024-memory-mechanism-llm-agents/`, import.meta.url);
const zhangPaper = JSON.parse(readFileSync(new URL("paper.json", zhangBase), "utf8"));
const zhangChunks = JSON.parse(readFileSync(new URL("chunks.json", zhangBase), "utf8")).chunks;
const zhangFigures = JSON.parse(readFileSync(new URL("figures.json", zhangBase), "utf8")).figures;

assert.ok(zhangChunks.length >= 18, "Zhang 2024 should be expanded beyond the demo chunk set");
assert.equal(typeof zhangPaper.categoryZh, "string", "Zhang 2024 should include Chinese category metadata");
assert.equal(typeof zhangPaper.relationZh, "string", "Zhang 2024 should include Chinese relation metadata");
assert.equal(typeof zhangPaper.descriptionZh, "string", "Zhang 2024 should include Chinese description metadata");
assert.ok(Array.isArray(zhangPaper.readingFocus) && zhangPaper.readingFocus.length >= 3, "Zhang 2024 should include Chinese reading focus items");

for (const chunk of zhangChunks) {
  assert.equal(typeof chunk.title, "string", `Zhang 2024 ${chunk.id} should include a Chinese short title`);
  assert.ok(chunk.title.trim().length >= 4, `Zhang 2024 ${chunk.id} title should be meaningful`);
  assert.equal(typeof chunk.zhTranslation, "string", `Zhang 2024 ${chunk.id} should include zhTranslation`);
  assert.ok(chunk.zhTranslation.trim().length > 40, `Zhang 2024 ${chunk.id} zhTranslation should be substantive`);
}

const zhangRenderedFigures = zhangFigures.filter((figure) => figure.file);
assert.ok(zhangRenderedFigures.length >= 2, "Zhang 2024 should render at least two real local figures");
for (const figure of zhangRenderedFigures) {
  assert.equal(existsSync(new URL(figure.file, zhangBase)), true, `Zhang 2024 figure file ${figure.file} should exist`);
}

assert.ok(zhangChunks.some((chunk) => chunk.blocks?.some((block) => block.type === "table")), "Zhang 2024 should include at least one table block");
assert.ok(zhangChunks.some((chunk) => chunk.blocks?.some((block) => block.type === "math")), "Zhang 2024 should include at least one math block");
```

- [ ] **Step 2: Update existing generic assertions for `zhTranslation`**

Change the generic chunk loop so every chunk in reading packages has `zhTranslation`, not only Zhang:

```js
assert.equal(typeof chunk.zhTranslation, "string", `${paperId} ${chunk.id} should include zhTranslation`);
assert.ok(chunk.zhTranslation.trim().length > 20, `${paperId} ${chunk.id} zhTranslation should be substantive`);
```

Update embedding index expectation:

```js
assert.deepEqual(embeddingsData.indexedFields, ["sourceText", "zhTranslation", "zhExplanation"], `${paperId} embeddings should index sourceText, zhTranslation, and zhExplanation`);
```

- [ ] **Step 3: Add reader rendering checks**

Add assertions near the existing JS/CSS chunk rendering checks:

```js
assert.match(js, /chunk\.zhTranslation/, "reader should render Chinese translations from chunk data");
assert.match(js, /paperData\.categoryZh/, "reader should prefer Chinese paper category metadata");
assert.match(js, /paperData\.readingFocus/, "reader should render Chinese reading focus metadata");
assert.match(css, /\.chunk-title/, "reader CSS should style chunk short titles");
assert.match(css, /\.chunk-translation/, "reader CSS should style Chinese translation separately from explanation");
assert.match(css, /\.reading-focus/, "reader CSS should style Chinese reading focus metadata");
```

- [ ] **Step 4: Run tests and confirm red**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: fails because Zhang still has 4 chunks, no `zhTranslation`, and no real figure files.

## Task 2: Expand Zhang 2024 Reading Data

- [ ] **Step 1: Add local figure files**

Create:

```text
papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/
```

Download at least these CC BY 4.0 ar5iv figure assets:

```bash
curl -L "https://ar5iv.labs.arxiv.org/html/2404.13501/assets/x1.png" -o "papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/figure-1-memory-module.png"
curl -L "https://ar5iv.labs.arxiv.org/html/2404.13501/assets/cx1.png" -o "papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/figure-3-memory-process.png"
curl -L "https://ar5iv.labs.arxiv.org/html/2404.13501/assets/cx2.png" -o "papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures/figure-4-memory-overview.png"
```

- [ ] **Step 2: Replace `paper.json` metadata**

Add Chinese display fields, source attribution, and 9 section anchors:

```json
{
  "categoryZh": "AI 智能体记忆",
  "relationZh": "这篇综述把 LLM-based agent 的 memory module 拆成定义、必要性、实现方式和评价方式，是本项目理解工程记忆系统的入口论文。",
  "descriptionZh": "阅读重点不是记住所有系统名称，而是理解 memory 在 agent 中承担的写入、读取、管理和评估角色。",
  "readingFocus": [
    "memory module 和 long context 的区别",
    "memory writing、reading、management 的工程分工",
    "评价 memory system 时为什么不能只看存储量"
  ],
  "license": "CC BY 4.0",
  "licenseUrl": "https://creativecommons.org/licenses/by/4.0/"
}
```

Keep existing English fields and source links.

- [ ] **Step 3: Replace `chunks.json` with 18+ chunks**

Build chunks around the approved main spine:

```text
Abstract
Introduction
Related surveys
Memory definition
Why memory is needed
Implementation
Evaluation
Future directions
Conclusion
```

Each chunk must include:

```json
{
  "id": "ch-001",
  "sectionId": "abstract",
  "order": 1,
  "title": "记忆模块为什么重要",
  "sourceText": "Real paper source passage...",
  "blocks": [{ "type": "paragraph", "text": "Real paper source passage..." }],
  "zhTranslation": "忠实中文翻译……",
  "zhExplanation": "精读解释……",
  "figureRefs": [],
  "keywords": ["memory module", "LLM agent"]
}
```

Use real paper excerpts from ar5iv/PDF. Avoid copying the whole paper; this is a main-spine study sample.

- [ ] **Step 4: Update `figures.json`**

Use real local figure paths for referenced figures:

```json
{
  "id": "fig-001",
  "label": "Figure 1",
  "file": "figures/figure-1-memory-module.png",
  "caption": "The importance of the memory module in LLM-based agents.",
  "sourceSection": "Introduction",
  "canonicalSectionId": "introduction",
  "status": "extracted"
}
```

- [ ] **Step 5: Update `notes.json`**

Provide one note entry for every chunk. Key chunks get real notes; other chunks use empty strings to keep the continuous blank surface:

```json
{
  "chunkId": "ch-001",
  "note": "这篇可以作为工程 memory module 的入口综述，先看定义和模块边界。"
}
```

- [ ] **Step 6: Update `embeddings.json`**

Set:

```json
"indexedFields": ["sourceText", "zhTranslation", "zhExplanation"]
```

Add one vector for every chunk. Reuse the current 12-dimensional local domain vector style.

## Task 3: Render Translation And Chinese Header

- [ ] **Step 1: Update `reader.js` header rendering**

In `renderPaperHeader`, prefer Chinese display fields:

```js
const category = paperData.categoryZh ?? paperData.category ?? "Paper";
const relation = paperData.relationZh ?? paperData.relation;
const description = paperData.descriptionZh ?? paperData.description;
const readingFocus = Array.isArray(paperData.readingFocus)
  ? `<ul class="reading-focus">${paperData.readingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
  : "";
```

Render `readingFocus` below description.

- [ ] **Step 2: Update `reader.js` chunk rendering**

In `renderChunk`, add title and translation:

```js
const title = chunk.title ? `<h2 class="chunk-title">${escapeHtml(chunk.title)}</h2>` : "";
const translation = chunk.zhTranslation ? `<p>${escapeHtml(chunk.zhTranslation)}</p>` : "";
const explanation = chunk.zhExplanation ? `<p class="chunk-explanation-note">${escapeHtml(chunk.zhExplanation)}</p>` : "";
```

Render order:

```html
${title}
<p class="chunk-heading">...</p>
<div class="chunk-source-card">...</div>
<div class="chunk-divider"></div>
<div class="chunk-translation">${translation}</div>
<div class="chunk-explanation">${explanation}</div>
```

- [ ] **Step 3: Update search fields**

Include `zhTranslation` in:

```js
searchText: `${chunk.sourceText ?? ""}\n${chunk.zhTranslation ?? ""}\n${chunk.zhExplanation ?? ""}`
```

And in lexical weighted fields:

```js
[item.chunk.zhTranslation, 2],
```

- [ ] **Step 4: Skip empty figure placeholders in normal flow**

In `renderFigure`, return empty string when a figure has no file:

```js
if (!figure?.file) return "";
```

This prevents empty placeholder panels from appearing in the upgraded sample.

## Task 4: Polish Center Reader CSS

- [ ] **Step 1: Add chunk title and translation styles**

Add:

```css
.chunk-title {
  margin: 0 0 8px;
  color: var(--reader-blue);
  font-family: var(--reader-serif);
  font-size: clamp(22px, 2.3vw, 30px);
  line-height: 1.28;
}

.chunk-translation {
  color: var(--reader-ink);
  font-size: 16px;
  line-height: 1.9;
  overflow-wrap: anywhere;
}

.chunk-explanation-note {
  margin-top: 12px;
  color: var(--reader-ink-muted);
}
```

- [ ] **Step 2: Add reading focus styles**

Add:

```css
.reading-focus {
  margin: 14px 0 0;
  padding-left: 18px;
  color: var(--reader-ink-muted);
  line-height: 1.72;
}
```

- [ ] **Step 3: Harden table and figure styles**

Update:

```css
.table-block {
  overflow-x: auto;
}

.table-block th,
.table-block td {
  min-width: 120px;
  vertical-align: top;
  white-space: normal;
}

.figure-frame {
  margin: 16px 0 0;
}

.figure-frame img {
  max-height: 420px;
  object-fit: contain;
}
```

## Task 5: Verify And Commit

- [ ] **Step 1: Run targeted test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: pass.

- [ ] **Step 2: Run full static checks**

Run:

```bash
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all pass.

- [ ] **Step 3: Visual sanity check**

Open local preview for:

```text
http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/?paper=zhang-2024-memory-mechanism-llm-agents
```

Verify:

- Zhang page has 18+ chunks.
- Header description is Chinese.
- English source card is followed by Chinese translation.
- At least two real images render.
- No empty figure placeholders render.
- Table does not overflow the viewport.

- [ ] **Step 4: Commit**

Commit implementation:

```bash
git add docs/superpowers/plans/2026-07-04-zhang-2024-complete-reader-sample.md tests/paper-reader-requirements.mjs papers/shared/reader.js papers/shared/reader.css papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents
git commit -m "Expand Zhang paper reader sample"
```

