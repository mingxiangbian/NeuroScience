# Foundations Knowledge Article Redesign

Date: 2026-07-11

Status: Approved design

## Context

The current Foundations reader treats each `###` block under `## 知识笔记` as a small generic card. Most cards are short collections of `核心理解`、`常见误区`、`面试转译` or `复习提示`. This creates four problems:

1. A card cannot be read as a self-contained explanation of a concept.
2. Roadmap hints, interview training and stable knowledge are mixed together.
3. The right panel repeats groups extracted from the center article instead of recording the user's learning process.
4. The current handwritten Markdown renderer cannot express a clear heading hierarchy, richer code blocks, tables or visual process diagrams.

The redesign turns learned concepts into durable knowledge articles while preserving Markdown as the only authored source.

## Goals

- Make every published knowledge note independently understandable in roughly 5 to 10 minutes.
- Keep stable knowledge in the center article and personal learning records in the right panel.
- Support clear typography, semantic sections, code, comparisons and process diagrams.
- Hide shallow notes for topics that have not been learned yet without removing those topics from the roadmap.
- Preserve the existing local highlight and annotation workflow.
- Keep authoring simple: edit Markdown, run the build script, publish generated JSON.

## Non-goals

- This change does not turn every roadmap topic into an article.
- It does not add interview scripts, readiness scores or retest reminders to knowledge articles.
- It does not introduce a backend, cloud note synchronization or collaborative editing.
- It does not redesign the entire Foundations reader shell or module navigation.
- It does not require a large externally hosted Chinese webfont.

## Core Decisions

### Article model

Each `###` block under `## 知识笔记` is one complete knowledge article. Articles are created only after the user has actually learned the concept well enough to document it.

Every article requires these sections:

1. `核心定义`
2. `核心机制`
3. `逐步示例`
4. `边界与常见错误`
5. `一句话总结`

Articles may add the following sections when useful:

- `代码实现`
- `复杂度分析`
- `程序流程`
- `架构图`
- `概念对比`
- `指标与公式`
- `参考资料`

Unknown optional `####` headings remain valid and render as ordinary article sections. This keeps the fixed core strict without making the format inflexible.

### Content boundary

The center article contains stable knowledge only:

- definitions
- mechanisms and invariants
- worked examples
- code or pseudocode
- complexity or metrics
- boundaries and failure modes
- concise summary

The right panel contains personal learning-process material only:

- highlights
- the user's own explanation
- unresolved questions
- reflections
- supplementary resources attached by the user

The right panel must be blank when the active article has no local annotations. It must not silently display the previous article, the first article or a copy of center-column content.

Interview translation, training status, readiness, scoring and retest reminders belong in `Interview Sprint`, tasks, timelines or `Behavioral / Strategy`, not in knowledge articles.

## Markdown Authoring Contract

The source remains the module Markdown file. A complete article uses this shape:

````markdown
## 知识笔记

### 单调队列

> 单调队列维护窗口中仍可能成为最大值的候选，使窗口移动时不必反复扫描全部元素。

`deque` · `O(n)` · `sliding window`

#### 核心定义

队列保存候选元素的索引，队首对应当前窗口最大值。

#### 核心机制

右端删除被新值支配的候选，左端删除已经离开窗口的候选。

#### 程序流程

1. 新索引进入窗口
2. 删除被新值支配的候选
3. 清理已经离开窗口的索引
4. 从队首读取当前最大值

#### 逐步示例

在 `[3, 5, 2, 4]` 中，5 淘汰 3，4 淘汰 2，但仍保留更大的 5。

#### 代码实现

```python
while queue and values[queue[-1]] <= values[right]:
    queue.pop()
```

#### 边界与常见错误

`pop()` 处理值支配，`popleft()` 处理索引过期，二者不能混用。

#### 一句话总结

单调队列只保存仍可能成为最大值的候选索引。
````

The optional opening blockquote is the article lead. Inline code immediately following it may be styled as compact topic tags, but no dedicated metadata language is required.

Authors do not write HTML or edit `roadmap-data.json` manually.

## Build Pipeline

### Markdown rendering

`projects/foundations/scripts/build-roadmap-data.mjs` will use the repository's existing `marked` and `sanitize-html` dependencies instead of extending the current handwritten Markdown renderer.

The safe renderer must support:

- headings through `h4`
- paragraphs and blockquotes
- ordered and unordered lists
- fenced code blocks with language classes
- inline code, emphasis and strong emphasis
- links with safe schemes and `rel="noopener noreferrer"`
- tables

Scripts, event-handler attributes, unsafe URL schemes and unsupported HTML are removed at build time.

### Article parsing

The builder performs these steps:

1. Split the module at `##` as it does today.
2. Split `## 知识笔记` at `###` into articles while respecting fenced code blocks.
3. Split each article at `####` into semantic sections.
4. Validate required section titles and unique article IDs.
5. Render each section to sanitized HTML and plain searchable text.
6. Emit article-level and section-level search entries.

The public JSON field remains `knowledgeNotes` to avoid a broad, low-value rename across reader, tests and local annotation keys. Its records become richer articles:

```json
{
  "id": "coding-monotonic-queue",
  "title": "单调队列",
  "intro": "<blockquote>单调队列维护仍可能成为最大值的候选。</blockquote>",
  "introText": "单调队列维护仍可能成为最大值的候选。",
  "sections": [
    {
      "id": "coding-monotonic-queue-core-definition",
      "kind": "definition",
      "title": "核心定义",
      "body": "<p>队列保存候选元素的索引。</p>",
      "text": "队列保存候选元素的索引。"
    }
  ],
  "text": "单调队列维护仍可能成为最大值的候选。队列保存候选元素的索引。"
}
```

Known headings map to stable `kind` values such as `definition`, `mechanism`, `example`, `flow`, `code`, `boundary` and `summary`. Unknown headings use `generic`.

### Validation failures

The build fails with the module and article title when:

- an article is missing any required core section
- a required section is empty
- two articles in one module produce the same stable ID
- a `程序流程` section does not contain at least two ordered steps

The build does not fail for an optional unknown heading.
Unsafe or unsupported authored HTML is removed by the sanitizer; focused tests verify that it cannot reach generated JSON.

## Reader Rendering

### Main article

Each knowledge article renders as one continuous reading surface, not a stack of unrelated cards.

Visual hierarchy:

- article title: system Kai-style stack, approximately 36 to 38px on desktop
- article section heading: Kai-style stack, approximately 24 to 26px
- subsection heading: approximately 18 to 20px
- body: readable Song-style stack, approximately 16px with generous line height
- code: existing monospace stack

Preferred system stacks:

```css
--knowledge-heading-font: "Kaiti SC", STKaiti, KaiTi, "Songti SC", serif;
--knowledge-body-font: "Songti SC", STSong, "Noto Serif SC", Georgia, serif;
```

Existing site design tokens remain the source for production colors, borders and spacing. The visual prototype's literal colors are references, not new production tokens.

Required semantic treatments:

- definition: restrained green-tinted block with a top rule
- mechanism: numbered steps aligned inside the article content grid
- example: ordinary reading text plus trace or code where needed
- boundary: warm warning treatment without an oversized side border
- summary: compact concluding block

The numbered mechanism markers use a fixed marker column. They must not use negative margins or extend beyond the article's left reading edge.

### Process diagrams

A `程序流程` section authored as an ordered list renders as an accessible HTML/CSS process diagram:

- horizontal nodes and arrows on sufficiently wide screens
- vertical nodes and arrows on narrow screens
- original ordered-list semantics remain available to assistive technology
- long labels wrap inside stable node dimensions

Complex branching or architecture relationships may use a fenced Mermaid block. Mermaid is progressive enhancement: if rendering is unavailable, the sanitized source remains visible as a code block rather than leaving a blank region.

### Right annotation panel

The right panel follows the active knowledge article. Its contents come only from local annotations associated with that article.

Rules:

- entering an article with annotations shows those annotations
- entering an article without annotations clears the panel body
- leaving the knowledge section clears the article-specific panel body
- scrolling and clicking use the same active-article state
- deleted highlights may retain detached notes under the existing annotation behavior
- no article `body`, `sections` or legacy `groups` are copied into the panel

Annotations with written notes have a compact category menu with four values:

- `我的理解` (`understanding`)
- `待解决问题` (`question`)
- `反思` (`reflection`)
- `补充资料` (`resource`)

A selection with no written note remains a plain `高亮` and does not require a category. Existing saved annotations without a category default to `我的理解`, so the redesign does not discard local data or require a manual migration. Empty categories are not rendered.

### Learning records

`## 学习记录` is an optional ordinary module section rendered after `时间线`. It uses sanitized Markdown but does not create knowledge articles, search anchors below the article level or right-panel knowledge context. This gives `Interview Sprint` a place for daily cards without weakening the knowledge-article contract.

### Search

Search indexes both article titles and internal sections. A result label uses the form:

`Coding / 单调队列 / 核心机制`

Selecting a result opens the module and scrolls to the corresponding article section. Search continues to use the existing local substring matching and does not add a separate search service.

## Initial Content Migration

### Coding

Replace shallow Coding knowledge cards with two complete articles:

1. `deque、stack 与 queue`
2. `单调队列`

The articles incorporate the D1/D2 material that the user actually worked through: queue semantics, `append`/`appendleft`, `pop`/`popleft`, `list.pop(0)` versus `deque.popleft()`, candidate domination, candidate expiry and the sliding-window trace.

### Evals & Debugging

Replace the current shallow notes with two complete articles:

1. `Eval Case 的六层结构`
2. `Benchmark 与 Agent Behavior Eval`

The second article may include scope-specific freshness, latency sample versus percentile, positive and negative assertions and evidence consistency as optional sections. These concepts should not become several small cards.

### Interview Sprint

`D1 冲刺卡`, `D2 冲刺卡` and `冲刺卡格式` are learning records, not knowledge articles. Move them from `## 知识笔记` to a dedicated `## 学习记录` section.

The sprint page keeps training outcomes, evidence boundaries and retest dates. It does not duplicate the knowledge articles created in Coding or Evals & Debugging.

### Deferred topics

Remove shallow cards for topics not yet studied deeply from `## 知识笔记`, including Agent Runtime, Eval Harness, Trace Debugging, TypeScript and optional Rust. Preserve their roadmap coverage in `核心知识`, `任务` or the sprint schedule.

Cyrene-specific project narration remains in sprint records or `Behavioral / Strategy`. It may later become a general RAG & Memory article only after its project-specific decisions are connected to stable, reusable concepts.

Modules with no approved knowledge article omit the `知识笔记` section entirely rather than displaying an empty placeholder.

## Testing And Acceptance

### Build tests

- required article sections are enforced
- optional headings are accepted
- duplicate stable IDs fail
- fenced code language classes survive sanitization
- unsafe HTML and unsafe links are removed
- process steps produce the expected structured data
- search entries exist for article sections

### Reader tests

- article title and section hierarchy render from generated JSON
- semantic section classes match their `kind`
- the right panel is empty without local annotations
- the right panel does not duplicate article HTML
- active article changes consistently on click and scroll
- local highlights and notes persist after reload
- section-level search opens the correct anchor
- Mermaid failure leaves readable source

### Visual checks

Verify at minimum:

- desktop around 1440px wide
- mobile around 390px wide
- numbered steps remain inside the reading grid
- headings are visibly distinct from body text
- code scrolls without resizing the page
- process diagrams switch from horizontal to vertical without overlap
- right notes do not obscure the article
- typography falls back cleanly when Kai or Song system fonts are unavailable

### Content acceptance

Each migrated article must:

- be understandable without the original chat
- contain all five required core sections
- explain mechanisms rather than only naming terms
- include a worked trace, example or case
- separate known facts from project-specific observations where relevant
- avoid readiness language, interview scripts and redundant recap text

## Rollout Boundary

The first implementation ends after the renderer, annotation behavior, search anchors, migration of the four approved articles, sprint-record relocation and focused tests are complete. Additional knowledge articles are created in later study blocks at a target rate of one or two high-quality articles per block.
