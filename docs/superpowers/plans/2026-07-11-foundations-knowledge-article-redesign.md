# Foundations Knowledge Article Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace shallow Foundations knowledge cards with four self-contained knowledge articles, a structured build contract, article-level learning annotations, and a responsive reading layout.

**Architecture:** Module Markdown remains the only authored source. A focused build-time parser converts `###` articles and `####` semantic sections into sanitized JSON; the static browser reader renders continuous articles, section-level search anchors, progressive Mermaid diagrams, and local annotation categories without a backend.

**Tech Stack:** Node.js ESM, `marked@18.0.5`, `sanitize-html@2.17.5`, vanilla HTML/CSS/JavaScript, browser `localStorage`, pinned Mermaid ESM `11.12.2`, Node assertion tests, Chrome headless visual verification.

## Global Constraints

- Every published article requires `核心定义`, `核心机制`, `逐步示例`, `边界与常见错误`, and `一句话总结`.
- Center-column articles contain stable knowledge only; readiness, interview scripts, scoring, and retest reminders stay outside knowledge articles.
- The right panel contains only article-linked local highlights and user notes; no article body or legacy note group is copied there.
- Markdown is the only authored source; `roadmap-data.json` is generated and never edited manually.
- Modules without an approved article omit the `知识笔记` section rather than showing a placeholder.
- Use system font stacks only: Kai-style headings, Song-style reading text, and the existing monospace code stack.
- Do not change learning progress as a side effect of migrating or styling content.
- Keep `knowledgeNotes` and `foundationsReader.annotations.v1` for compatibility.
- Keep the pinned Mermaid URL exact: `https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.esm.min.mjs`.
- Synchronize `projects/foundations/roadmap/modules/interview-sprint.md` with `projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md`.

---

## File Map

- Create `projects/foundations/scripts/roadmap-markdown.mjs`: safe Markdown rendering, heading-aware article parsing, semantic section validation.
- Create `projects/foundations/roadmap/annotation-model.js`: pure annotation normalization, categories, and grouping.
- Modify `projects/foundations/scripts/build-roadmap-data.mjs`: consume structured articles and emit article-section search entries.
- Modify `projects/foundations/roadmap/roadmap-reader.js`: render continuous articles, section anchors, Mermaid, and annotation-only side panels.
- Modify `projects/foundations/roadmap/roadmap-reader.css`: article typography, semantic blocks, flow diagrams, and annotation controls.
- Modify `projects/foundations/roadmap/modules/*.md`: publish four learned articles, remove unlearned shallow cards, and relocate sprint cards.
- Modify `projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md`: keep the backup sprint source aligned.
- Regenerate `projects/foundations/roadmap/roadmap-data.json` from Markdown.
- Create `tests/foundations-knowledge-article-parser.mjs`: parser, sanitizer, required-section, duplicate-ID, and flow validation.
- Create `tests/foundations-knowledge-content-requirements.mjs`: exact first-batch article and learning-record contract.
- Create `tests/foundations-annotation-model.mjs`: legacy annotation migration and category grouping.
- Modify `tests/foundations-roadmap-requirements.mjs`: generated article schema, reader contract, search, CSS, and optional-section expectations.

---

### Task 1: Safe Knowledge Article Parser

**Files:**
- Create: `projects/foundations/scripts/roadmap-markdown.mjs`
- Create: `tests/foundations-knowledge-article-parser.mjs`

**Interfaces:**
- Produces: `markdownToSafeHtml(markdown) -> { html, text }`
- Produces: `parseKnowledgeArticles(moduleId, markdown) -> KnowledgeArticle[]`
- Produces article shape: `{ id, title, intro, introText, sections, text }`
- Produces section shape: `{ id, kind, title, body, text }`
- Depends on: `marked`, `sanitize-html`

- [ ] **Step 1: Write the failing parser test**

Create `tests/foundations-knowledge-article-parser.mjs` with complete positive and negative cases:

```js
import assert from "node:assert/strict";
import {
  markdownToSafeHtml,
  parseKnowledgeArticles,
} from "../projects/foundations/scripts/roadmap-markdown.mjs";

const completeArticle = `### 单调队列

> 维护仍可能成为最大值的候选。

\`deque\` · \`O(n)\`

#### 核心定义
队列保存候选索引。

#### 核心机制
1. 删除被支配候选
2. 加入新索引

#### 程序流程
1. 新索引进入窗口
2. 删除队尾候选
3. 清理过期队首

#### 逐步示例
在 \`[3, 5, 2, 4]\` 中，5 淘汰 3。

#### 代码实现
\`\`\`python
queue.popleft()
\`\`\`

#### 边界与常见错误
\`pop()\` 处理支配，\`popleft()\` 处理过期。

#### 一句话总结
每个索引最多入队和出队一次。`;

const articles = parseKnowledgeArticles("coding", completeArticle);
assert.equal(articles.length, 1);
assert.equal(articles[0].id, "coding-单调队列");
assert.match(articles[0].intro, /<blockquote>/);
assert.deepEqual(
  articles[0].sections.map(({ title, kind }) => [title, kind]),
  [
    ["核心定义", "definition"],
    ["核心机制", "mechanism"],
    ["程序流程", "flow"],
    ["逐步示例", "example"],
    ["代码实现", "code"],
    ["边界与常见错误", "boundary"],
    ["一句话总结", "summary"],
  ],
);
assert.match(articles[0].sections[4].body, /class="language-python"/);
assert.match(articles[0].text, /每个索引最多入队和出队一次/);

const articleWithUnknownSection = parseKnowledgeArticles(
  "coding",
  completeArticle.replace(
    "#### 一句话总结",
    "#### 延伸理解\n这是一段允许保留的自定义扩展。\n\n#### 一句话总结",
  ),
)[0];
assert.equal(
  articleWithUnknownSection.sections.find((section) => section.title === "延伸理解")?.kind,
  "generic",
);

const safe = markdownToSafeHtml(`> lead

| A | B |
| - | - |
| 1 | 2 |

<script>alert(1)</script>
[unsafe](javascript:alert(1))`);
assert.match(safe.html, /<blockquote>/);
assert.match(safe.html, /<table>/);
assert.doesNotMatch(safe.html, /<script|javascript:/i);

assert.throws(
  () => parseKnowledgeArticles("coding", completeArticle.replace("#### 一句话总结", "#### 结论")),
  /coding.*单调队列.*一句话总结/,
);
assert.throws(
  () => parseKnowledgeArticles("coding", `${completeArticle}\n\n${completeArticle}`),
  /duplicate knowledge article id/i,
);
assert.throws(
  () => parseKnowledgeArticles("coding", completeArticle.replace(
    "1. 新索引进入窗口\n2. 删除队尾候选\n3. 清理过期队首",
    "1. 新索引进入窗口",
  )),
  /程序流程.*at least two ordered steps/i,
);
```

- [ ] **Step 2: Run the test and verify the module is missing**

Run:

```bash
node tests/foundations-knowledge-article-parser.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `roadmap-markdown.mjs`.

- [ ] **Step 3: Implement the focused parser module**

Create `projects/foundations/scripts/roadmap-markdown.mjs` with these exact public constants and functions:

```js
import { marked } from "marked";
import sanitizeHtml from "sanitize-html";

export const REQUIRED_KNOWLEDGE_SECTIONS = [
  "核心定义",
  "核心机制",
  "逐步示例",
  "边界与常见错误",
  "一句话总结",
];

const SECTION_KINDS = new Map([
  ["核心定义", "definition"],
  ["核心机制", "mechanism"],
  ["逐步示例", "example"],
  ["程序流程", "flow"],
  ["代码实现", "code"],
  ["复杂度分析", "complexity"],
  ["架构图", "diagram"],
  ["概念对比", "comparison"],
  ["指标与公式", "metrics"],
  ["参考资料", "resources"],
  ["边界与常见错误", "boundary"],
  ["一句话总结", "summary"],
]);

const allowedTags = [
  "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "h5", "h6",
  "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
];

const allowedAttributes = {
  a: ["href", "title", "rel"],
  code: ["class"],
  th: ["align"],
  td: ["align"],
};

export function markdownToSafeHtml(markdown) {
  const rawHtml = marked.parse(String(markdown ?? ""), { async: false, gfm: true, breaks: false });
  const html = sanitizeHtml(rawHtml, {
    allowedTags,
    allowedAttributes,
    allowedSchemes: ["http", "https", "mailto"],
    allowProtocolRelative: false,
    transformTags: {
      a: sanitizeHtml.simpleTransform("a", { rel: "noopener noreferrer" }),
    },
  });
  const text = sanitizeHtml(html, { allowedTags: [], allowedAttributes: {} })
    .replace(/\s+/g, " ")
    .trim();
  return { html, text };
}

function slugifyTitle(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function splitHeadingBlocks(markdown, level) {
  const marker = `${"#".repeat(level)} `;
  const blocks = [];
  let title = "";
  let lines = [];
  let inCode = false;
  const flush = () => {
    if (!title) return;
    blocks.push({ title, markdown: lines.join("\n").trim() });
    lines = [];
  };
  for (const line of String(markdown ?? "").split("\n")) {
    if (line.startsWith("```")) inCode = !inCode;
    if (!inCode && line.startsWith(marker)) {
      flush();
      title = line.slice(marker.length).trim();
      continue;
    }
    if (title) lines.push(line);
  }
  flush();
  return blocks;
}

function splitArticleBody(markdown) {
  const lines = String(markdown ?? "").split("\n");
  let inCode = false;
  let firstSectionIndex = lines.length;
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].startsWith("```")) inCode = !inCode;
    if (!inCode && lines[index].startsWith("#### ")) {
      firstSectionIndex = index;
      break;
    }
  }
  return {
    introMarkdown: lines.slice(0, firstSectionIndex).join("\n").trim(),
    sectionBlocks: splitHeadingBlocks(lines.slice(firstSectionIndex).join("\n"), 4),
  };
}

function countOrderedSteps(markdown) {
  return String(markdown ?? "").split("\n").filter((line) => /^\d+\.\s+/.test(line)).length;
}

export function parseKnowledgeArticles(moduleId, markdown) {
  const ids = new Set();
  return splitHeadingBlocks(markdown, 3).map((articleBlock) => {
    const id = `${moduleId}-${slugifyTitle(articleBlock.title) || "article"}`;
    if (ids.has(id)) throw new Error(`${moduleId}: duplicate knowledge article id ${id}`);
    ids.add(id);

    const { introMarkdown, sectionBlocks } = splitArticleBody(articleBlock.markdown);
    const sectionByTitle = new Map(sectionBlocks.map((section) => [section.title, section]));
    for (const requiredTitle of REQUIRED_KNOWLEDGE_SECTIONS) {
      const required = sectionByTitle.get(requiredTitle);
      if (!required || !required.markdown.trim()) {
        throw new Error(`${moduleId} / ${articleBlock.title} is missing required section ${requiredTitle}`);
      }
    }

    const sections = sectionBlocks.map((sectionBlock) => {
      const kind = SECTION_KINDS.get(sectionBlock.title) ?? "generic";
      if (kind === "flow" && countOrderedSteps(sectionBlock.markdown) < 2) {
        throw new Error(`${moduleId} / ${articleBlock.title} / 程序流程 requires at least two ordered steps`);
      }
      const rendered = markdownToSafeHtml(sectionBlock.markdown);
      return {
        id: `${id}-${slugifyTitle(sectionBlock.title) || "section"}`,
        kind,
        title: sectionBlock.title,
        body: rendered.html,
        text: rendered.text,
      };
    });
    const intro = markdownToSafeHtml(introMarkdown);
    return {
      id,
      title: articleBlock.title,
      intro: intro.html,
      introText: intro.text,
      sections,
      text: [intro.text, ...sections.map((section) => section.text)].filter(Boolean).join(" "),
    };
  });
}
```

- [ ] **Step 4: Run the parser test**

Run:

```bash
node tests/foundations-knowledge-article-parser.mjs
```

Expected: exit 0 with no assertion output.

- [ ] **Step 5: Commit the parser**

```bash
git add projects/foundations/scripts/roadmap-markdown.mjs tests/foundations-knowledge-article-parser.mjs
git commit -m "feat: add foundations knowledge article parser"
```

---

### Task 2: Migrate Learned Content And Sprint Records

**Files:**
- Create: `tests/foundations-knowledge-content-requirements.mjs`
- Modify: `projects/foundations/roadmap/modules/coding.md`
- Modify: `projects/foundations/roadmap/modules/evals-debugging.md`
- Modify: `projects/foundations/roadmap/modules/interview-sprint.md`
- Modify: `projects/foundations/roadmap/modules/agent-design.md`
- Modify: `projects/foundations/roadmap/modules/llm-systems.md`
- Modify: `projects/foundations/roadmap/modules/rag-memory.md`
- Modify: `projects/foundations/roadmap/modules/research-reading.md`
- Modify: `projects/foundations/roadmap/modules/behavioral-strategy.md`
- Modify: `projects/foundations/roadmap/modules/logs.md`
- Modify: `projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md`

**Interfaces:**
- Produces exactly two Coding articles: `deque、stack 与 queue`, `单调队列`.
- Produces exactly two Evals articles: `Eval Case 的六层结构`, `Benchmark 与 Agent Behavior Eval`.
- Produces `## 学习记录` in Interview Sprint and no `## 知识笔记` there.
- Leaves no `## 知识笔记` in unlearned modules.

- [ ] **Step 1: Write the failing content-contract test**

Create `tests/foundations-knowledge-content-requirements.mjs`:

```js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const modulesDir = new URL("../projects/foundations/roadmap/modules/", import.meta.url);
const readModule = (id) => readFileSync(new URL(`${id}.md`, modulesDir), "utf8");
const requiredHeadings = ["核心定义", "核心机制", "逐步示例", "边界与常见错误", "一句话总结"];

function articleTitles(markdown) {
  const knowledge = markdown.split("## 知识笔记\n")[1] ?? "";
  return [...knowledge.matchAll(/^### (.+)$/gm)].map((match) => match[1]);
}

function assertCompleteArticles(markdown, expectedTitles) {
  assert.deepEqual(articleTitles(markdown), expectedTitles);
  const knowledge = markdown.split("## 知识笔记\n")[1] ?? "";
  const blocks = knowledge.split(/^### /m).slice(1);
  for (const block of blocks) {
    for (const heading of requiredHeadings) {
      assert.match(block, new RegExp(`^#### ${heading}$`, "m"), `${block.split("\n")[0]} should include ${heading}`);
    }
    assert.doesNotMatch(block, /^面试转译[：:]$/m);
    assert.doesNotMatch(block, /^复习提示[：:]$/m);
    assert.doesNotMatch(block, /\breadiness\b|hard gate/i);
  }
}

assertCompleteArticles(readModule("coding"), ["deque、stack 与 queue", "单调队列"]);
assertCompleteArticles(readModule("evals-debugging"), ["Eval Case 的六层结构", "Benchmark 与 Agent Behavior Eval"]);

const sprint = readModule("interview-sprint");
assert.match(sprint, /^## 学习记录$/m);
assert.doesNotMatch(sprint, /^## 知识笔记$/m);
assert.match(sprint, /^### D1 冲刺卡$/m);
assert.match(sprint, /^### D2 冲刺卡$/m);

for (const id of ["agent-design", "llm-systems", "rag-memory", "research-reading", "behavioral-strategy", "logs"]) {
  assert.doesNotMatch(readModule(id), /^## 知识笔记$/m, `${id} should not publish an unlearned knowledge article`);
}

const backup = readFileSync(new URL("../projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md", import.meta.url), "utf8");
assert.match(backup, /## 学习记录/);
assert.doesNotMatch(backup, /## 知识笔记/);
```

- [ ] **Step 2: Run the content test and confirm the old cards fail**

Run:

```bash
node tests/foundations-knowledge-content-requirements.mjs
```

Expected: FAIL because Coding and Evals still use old titles and Sprint still has `## 知识笔记`.

- [ ] **Step 3: Rewrite Coding as two complete articles**

Replace Coding's current `## 知识笔记` body with this exact authored content:

````markdown
## 知识笔记

### deque、stack 与 queue

> Stack、queue 和 deque 的区别不在于“装了哪些值”，而在于允许从哪一端加入和取出，以及这个操作需要付出什么代价。

`list` · `collections.deque` · `LIFO` · `FIFO`

#### 核心定义

- **Stack（栈）**遵循后进先出（Last In, First Out, LIFO）。最后加入的元素最先离开。Python 中通常用 `list.append()` 入栈、`list.pop()` 出栈。
- **Queue（队列）**遵循先进先出（First In, First Out, FIFO）。最早加入的元素最先离开。Python 中通常用 `deque.append()` 入队、`deque.popleft()` 出队。
- **Deque（双端队列）**允许从左右两端加入或删除元素。它既能实现 stack，也能实现 queue，还能支持需要同时维护两端的算法。

| 需求 | 推荐操作 | 典型复杂度 |
| --- | --- | --- |
| 栈顶加入 / 删除 | `list.append()` / `list.pop()` | 摊销 `O(1)` / `O(1)` |
| 队尾加入、队首删除 | `deque.append()` / `deque.popleft()` | `O(1)` / `O(1)` |
| 双端加入 / 删除 | `deque.appendleft()`、`append()`、`popleft()`、`pop()` | `O(1)` |
| 删除 list 第一个元素 | `list.pop(0)` | `O(n)` |

#### 核心机制

Python `list` 是按连续位置组织的动态数组。执行 `list.pop(0)` 后，为了继续让第一个有效元素位于索引 0，后续元素都要向左移动一个位置。删除本身只发生一次，但移动量与列表长度成正比，因此是 `O(n)`。

`collections.deque` 针对两端操作设计。`popleft()` 更新左端边界并返回元素，不需要把剩余元素整体搬动，因此是 `O(1)`。从使用者视角看，剩余元素的**逻辑索引**仍会变小；但这不等于底层把每个元素都复制到前一个物理位置。

这也解释了一个容易混淆的点：复杂度描述的是操作量如何随输入规模增长，而不是 Python 表面上有没有重新编号。

#### 程序流程

1. 根据规则确定新元素从左端还是右端进入。
2. 根据服务顺序确定元素从哪一端离开。
3. 如果不同优先级内部仍要求 FIFO，为每个优先级维护独立队列。
4. 总是先清空高优先级队列，再处理普通队列。

#### 逐步示例

考虑事件：

```python
events = [
    ("normal", "A"),
    ("urgent", "C"),
    ("normal", "B"),
    ("urgent", "D"),
]
```

如果紧急任务也要求先到先得，就不能把紧急任务不断 `appendleft()` 到同一个队列，因为后来的 `D` 会跑到先来的 `C` 前面。使用两个 FIFO 队列时：

| 读入事件 | urgent_queue | normal_queue |
| --- | --- | --- |
| `normal A` | `[]` | `[A]` |
| `urgent C` | `[C]` | `[A]` |
| `normal B` | `[C]` | `[A, B]` |
| `urgent D` | `[C, D]` | `[A, B]` |

最终服务顺序是 `C → D → A → B`：优先级之间是“紧急优先”，同一优先级内部仍然是 FIFO。

#### 代码实现

```python
from collections import deque


def service_order(events):
    urgent_queue = deque()
    normal_queue = deque()
    served = []

    for typ, person in events:
        if typ == "urgent":
            urgent_queue.append(person)
        else:
            normal_queue.append(person)

    while urgent_queue or normal_queue:
        if urgent_queue:
            served.append(urgent_queue.popleft())
        else:
            served.append(normal_queue.popleft())

    return served
```

#### 复杂度分析

设一共有 `n` 个事件。每个人只进入一次队列、离开一次队列，所以总时间复杂度是 `O(n)`。两个队列和结果列表最多保存 `n` 个名字，额外空间复杂度是 `O(n)`。

如果对普通 `list` 连续执行 `pop(0)`，移动次数约为 `(n-1) + (n-2) + ... + 1`，总时间会增长到 `O(n²)`。

#### 边界与常见错误

- `deque.popleft()` 是从左端删除；`deque.pop()` 是从右端删除。两者都是 `O(1)`，但表达的顺序规则不同。
- `appendleft()` 会让后来元素先被 `popleft()` 取出；它适合“插队即反转顺序”的规则，不自动保证同优先级 FIFO。
- `deque` 不适合频繁随机访问中间位置。需要按索引反复读取时，`list` 通常更合适。
- 说“索引减一”不足以解释复杂度。要继续追问：是逻辑编号变化，还是底层元素发生了线性搬移？

#### 一句话总结

Stack 和 queue 定义取出顺序，deque 提供两端 `O(1)` 操作；选择容器时要同时匹配语义和复杂度。

### 单调队列

> 单调队列不保存窗口中的全部元素，也不只保存最大值和次大值；它保存所有仍可能在未来成为答案的候选索引。

`deque` · `sliding window` · `monotonic invariant` · `O(n)`

#### 核心定义

求滑动窗口最大值时，单调队列（monotonic deque）通常保存**索引**，并维持两个不变量：

1. 索引从队首到队尾递增，因此可以从左端判断候选是否已经离开窗口。
2. 对应的值从队首到队尾单调不增，因此队首始终是当前窗口最大值。

队列里可能有两个、三个甚至更多候选。例如严格递减序列 `[9, 7, 5, 3]` 中，没有较新的值能支配较旧的值，四个索引都需要暂时保留。

#### 核心机制

**右端 `pop()` 处理值支配。** 当新值大于或等于队尾候选时，新值更大、出现得又更晚。只要新值还在窗口，旧候选就不可能先于它成为最大值，因此旧候选可以永久删除。

**左端 `popleft()` 处理位置过期。** 当队首索引小于窗口左边界时，它已经不属于当前窗口。即使它的值最大，也必须删除。

这两个删除条件彼此独立：右端比较“谁更有竞争力”，左端判断“谁还在窗口内”。不能把 `pop()` 和 `popleft()` 简化成“都在删左边的旧数字”。

#### 程序流程

1. 读取右端新元素。
2. 从队尾删除所有值不大于新值的候选。
3. 把新元素的索引加入队尾。
4. 从队首删除已经小于窗口左边界的索引。
5. 当窗口形成后，从队首读取当前最大值。

#### 逐步示例

对 `values = [3, 5, 2, 4]`、窗口大小 `k = 3`：

| right | 新值 | 队列变化（索引） | 候选值 | 当前输出 |
| --- | ---: | --- | --- | ---: |
| 0 | 3 | `[] → [0]` | `[3]` | 窗口未形成 |
| 1 | 5 | `[0] → [] → [1]` | `[5]` | 窗口未形成 |
| 2 | 2 | `[1] → [1, 2]` | `[5, 2]` | 5 |
| 3 | 4 | `[1, 2] → [1] → [1, 3]` | `[5, 4]` | 5 |

在 `right = 1` 时，5 从右端淘汰 3；在 `right = 3` 时，4 从右端淘汰 2，但不能淘汰更大的 5。

过期是另一件事。若窗口为 `[5, 3, 4]` 后继续右移到 `[3, 4, 2]`，值 5 的索引已经越过左边界，此时才从队首 `popleft()`。

#### 代码实现

```python
from collections import deque


def sliding_window_max(values, k):
    if k <= 0 or k > len(values):
        return []

    candidates = deque()
    answer = []

    for right, value in enumerate(values):
        while candidates and values[candidates[-1]] <= value:
            candidates.pop()
        candidates.append(right)

        left = right - k + 1
        if candidates[0] < left:
            candidates.popleft()

        if left >= 0:
            answer.append(values[candidates[0]])

    return answer
```

#### 复杂度分析

虽然代码里有嵌套 `while`，总复杂度仍是 `O(n)`。每个索引只会进入队列一次，并且最多因为“被支配”或“过期”离开一次。所有 `pop()` 和 `popleft()` 的总次数不会超过 `n`。

队列最多保存一个窗口内的候选，空间复杂度是 `O(k)`。

#### 边界与常见错误

- 队列保存索引而不是只保存值，否则无法判断元素是否已经离开窗口。
- 使用 `<` 还是 `<=` 取决于是否保留相等值。用 `<=` 会保留更新的相等候选，通常更容易处理过期。
- 队首是当前最大值；队列其余元素是按优先级排列的未来候选，不等于严格意义上的“第二大、第三大”。
- 右端 `pop()` 的触发条件是新值支配旧候选；左端 `popleft()` 的触发条件是索引过期。
- 看到嵌套循环不能直接判断为 `O(n²)`，要计算每个元素在所有循环中总共被处理几次。

#### 一句话总结

单调队列用右端删除被支配候选、用左端删除过期候选，使每个索引只进出一次并在线性时间内维护窗口最大值。
````

- [ ] **Step 4: Rewrite Evals as two complete articles**

Replace Evals' current `## 知识笔记` body with this exact authored content:

````markdown
## 知识笔记

### Eval Case 的六层结构

> 一个可信的 Eval case 不只是“输入加断言”，而是一条从测试条件、行为契约、真实观测到可复核证据的完整因果链。

`input` · `expected` · `actual` · `assertion` · `metric` · `evidence`

#### 核心定义

| 层 | 回答的问题 | 典型内容 |
| --- | --- | --- |
| Input | 运行前给了系统什么？ | fixture、请求、模式、配置、工具状态 |
| Expected | 系统应该或不应该做什么？ | 必须返回的内容、禁止泄露的内容、允许的动作 |
| Actual | 系统实际上做了什么？ | 返回文本、tool call、trace、状态变化、错误 |
| Assertion | 如何机械判断 actual 是否符合 expected？ | 相等、包含、不包含、schema、顺序或阈值检查 |
| Metric | 如何量化表现？ | success、leakage、latency sample、token count |
| Evidence | 人如何复核结论？ | 原始输出片段、trace ID、计时样本、失败原因 |

六层的关键边界是：`input` 是条件，`actual` 是观测。Fixture 里存在某条 Active Memory，只能证明测试准备了它，不能证明系统真的返回或使用了它。

#### 核心机制

一个 case 的可信度来自层与层之间的引用关系：

1. `expected` 必须由产品 Policy 或行为契约导出，不能由当前实现反推。
2. `assertion` 必须直接检查 `actual`，而不是检查 fixture 或测试名称。
3. `metric` 必须由同一组 actual observations 计算。
4. `evidence` 必须展示断言真正读取的事实，不能单独硬编码一套解释。

行为边界通常同时需要**正向断言**和**负向断言**。正向断言验证必须出现的行为；负向断言验证禁止行为没有发生。只有负向断言时，一个什么都不返回的系统也可能通过。

#### 程序流程

1. 固定 fixture、请求、模式和 Policy。
2. 从 Policy 写出 expected 的允许项与禁止项。
3. 运行系统并保存原始 actual output 与 trace。
4. 对同一 actual 执行正向和负向 assertions。
5. 从同一观测计算 metrics，并附上可定位 evidence。
6. 报告 pass、fail 与 case 本身尚未覆盖的边界。

#### 逐步示例

假设一个读取模式的 Policy 明确要求：返回 Active Memory，不返回 Pending Memory，也不返回 Fast Summary。

```python
case_input = {
    "mode": "balanced",
    "active_memory": "Prefer concise answers",
    "pending_memory": "Expose draft candidates",
    "fast_summary": "Temporary session summary",
}

actual = {
    "text": "User preference: Prefer concise answers",
    "latency_ms": 22,
}
```

Expected 可写成：

- `active_memory` 必须出现在返回文本中。
- `pending_memory` 不得出现在返回文本中。
- `fast_summary` 不得出现在返回文本中。

Assertions 直接读取 `actual["text"]`：

```python
text = actual["text"]

assert case_input["active_memory"] in text
assert case_input["pending_memory"] not in text
assert case_input["fast_summary"] not in text
```

Metrics 可以记录 `active_recall = 1`、`pending_leakage = 0`、`fast_summary_leakage = 0` 和 `latency_sample_ms = 22`。Evidence 则保存实际返回文本、三项布尔观测和本次计时。因为这里只运行一次，22 ms 只能叫 latency sample，不能叫 P95。

#### 概念对比

| 容易混淆的两项 | 区别 |
| --- | --- |
| Expected vs Assertion | Expected 是行为契约；Assertion 是把契约变成可执行判断的方法 |
| Actual vs Evidence | Actual 是原始观测；Evidence 是便于人复核该观测与结论的呈现 |
| Fixture presence vs Retrieval success | Fixture 只证明输入存在；retrieval success 必须在输出或 trace 中被观察到 |
| Metric vs Conclusion | Metric 是数值；结论还需要说明样本、阈值和覆盖范围 |

#### 边界与常见错误

- 测试名写着 `FAST` 或 `BALANCED`，不代表断言真的覆盖了对应 Policy。
- `not required` 不自动等于 `forbidden`；禁止项必须来自明确契约。
- Evidence 不能由单个条件触发后把其他指标全部写成 0，否则报告可能与 assertion 结果矛盾。
- 一条 case 的通过只能说明该 fixture 下的契约成立，不能外推成整个系统的准确率。
- 断言实现本身也可能有 bug，因此失败报告应保留 raw actual 和 trace，方便反向审计 evaluator。

#### 一句话总结

Eval case 的六层结构把输入条件、行为契约、真实观测、机器判断、数值指标和人工证据连成一条可审计链。

### Benchmark 与 Agent Behavior Eval

> Benchmark 衡量系统“跑得怎样”，Agent Behavior Eval 判断系统“做得对不对”；两者可以共享一次运行，但不能互相替代。

`latency` · `cost` · `percentile` · `behavior correctness` · `regression`

#### 核心定义

**System performance benchmark** 关注速度、成本和容量，例如 latency、throughput、token usage、memory footprint、并发能力。

**Agent Behavior Eval** 关注行为正确性与安全边界，例如是否选择正确工具、参数是否正确、是否完成目标、失败后是否恢复、是否泄露不应使用的 memory。

**Regression suite** 用固定 cases 检查已知行为是否被后续修改破坏。它证明的是“这些 case 在这个版本和配置下的结果”，不是生产流量上的总体准确率。

#### 核心机制

两类评估应共享同一批可重放运行，但分别回答问题：

1. 性能层记录每次运行的耗时、token、成本、资源和吞吐。
2. 行为层从 output、tool call、trace 和状态变化判断成功、错误与泄露。
3. 聚合层分别报告分布指标和行为通过率，并保留 case 级明细。
4. 结论层写清 workload、样本量、环境、scope 和未覆盖风险。

单次计时是 sample。P95 是一组可比较样本的第 95 百分位，需要重复运行、稳定环境以及明确的 warm-up 和异常值处理。把一次 22 ms 命名为 `p95`，不会让它自动获得分布意义。

字符数除以四可以作为粗略 token estimate，用于早期相对回归；它不能替代目标模型 tokenizer 的真实 token count，也不能直接当作账单成本。

#### 概念对比

| 问题 | Performance benchmark | Agent Behavior Eval |
| --- | --- | --- |
| 核心问题 | 多快、多贵、能承载多少 | 是否做对、是否越界 |
| 主要观测 | 时间、token、资源、吞吐 | output、tool call、trace、state |
| 常见聚合 | P50/P95、均值、QPS、成本 | success rate、error taxonomy、leakage |
| 典型失败 | 尾延迟、成本膨胀、容量不足 | 错工具、错参数、无恢复、信息泄露 |
| 能否互相替代 | 不能 | 不能 |

#### 逐步示例

比较“每轮回答后同步 summarization hook”和“周期性 maintenance”时，应回放同一组对话，而不是分别凭使用感受给出数字：

1. 固定对话、模型、配置、机器和缓存策略。
2. 每种方案先 warm up，再重复运行足够次数。
3. 记录前台新增 latency、总 token、调用次数和费用。
4. 分 scope 测量 time-to-availability：项目偏好可能按日维护，全局记忆可能按周或更长周期维护。
5. 用标注集测 Memory Precision、Recall、错误记忆泄露和下游任务成功率。
6. 同时报告性能分布、行为结果和 freshness tradeoff，而不是只挑一个有利指标。

同步 hook 的可能收益是 freshness 高，代价是把总结调用放进用户等待的关键路径。周期维护会移除这段同步等待和调用，但会引入记忆可用延迟。是否值得，必须由目标 scope 的 freshness 要求与完整测量共同决定。

#### 指标与公式

对 `n` 次可比较运行：

- `latency_samples = [t1, t2, ..., tn]`
- `P95 = latency_samples` 的 95% 分位值，而不是其中任意一次调用
- `behavior_success_rate = passed_behavior_cases / executed_behavior_cases`
- `memory_precision = retrieved_relevant / retrieved_total`
- `memory_recall = retrieved_relevant / relevant_expected`

Skipped case 不应放进 passed 的分母，也不应被当作成功。估算 token 时必须使用带 `estimated` 的字段名；只有 tokenizer 实算值才能使用 `token_count`。

#### 项目案例

Cyrene 的归档 deterministic full profile 为 67 cases：59 passed、8 skipped、0 failed。这个数字只描述该 regression suite 的归档结果，不代表生产准确率，也不代表每个 case 都已由项目负责人逐项审计。

从每轮同步 summarization hook 改为周期维护，依据是实际使用中观察到回答变慢和 token 消耗增加；没有保留改造前后的量化对照。因此可信表述是“改变了关键路径，并观察到定性问题”，而不是声称延迟或成本下降了某个百分比。

#### 边界与常见错误

- 用行为通过率回答 latency 问题，或用低 latency 证明行为正确，都是指标错位。
- 样本量为 1 时不能报告 P95；样本环境不同也不能直接比较分位数。
- `59/8/0` 必须同时带上 profile、总 case 数和 skipped 含义，不能简化成“准确率 100%”。
- 架构上移除同步调用可以说明关键路径发生变化，但没有 before/after 数据时不能虚构改善幅度。
- Freshness 必须按 scope 定义。项目级与全局级 memory 使用同一个可用时间阈值，会掩盖真实设计目标。

#### 一句话总结

可信评估把性能分布、行为正确性、数据 scope 和证据边界分开报告，再用同一批可重放运行解释它们之间的取舍。
````

- [ ] **Step 5: Move sprint cards and remove unlearned cards**

- Rename Sprint `## 知识笔记` to `## 学习记录` in both live and backup sources.
- Keep D1, D2, and the sprint-card format under `学习记录`; rename their internal labels from `核心理解` and `复习提示` to `完成记录` and `后续检查` so they are visibly records.
- Remove `## 知识笔记` and its body from Agent Design, LLM Systems, RAG & Memory, Research Reading, Behavioral / Strategy, and Logs.
- Preserve their topic names and roadmap coverage in the existing `核心知识`, `任务`, and `时间线` sections; do not change `learning_progress`.

- [ ] **Step 6: Run the content contract**

Run:

```bash
node tests/foundations-knowledge-content-requirements.mjs
```

Expected: exit 0.

- [ ] **Step 7: Commit the content migration**

```bash
git add tests/foundations-knowledge-content-requirements.mjs projects/foundations/roadmap/modules projects/foundations/interview_prep_2026-07-09/08_sprint_module_for_website.md
git commit -m "content: promote foundations knowledge articles"
```

---

### Task 3: Generate Structured Articles And Section Search Entries

**Files:**
- Modify: `projects/foundations/scripts/build-roadmap-data.mjs`
- Modify: `projects/foundations/roadmap/roadmap-data.json`
- Modify: `tests/foundations-roadmap-requirements.mjs`

**Interfaces:**
- Consumes: `markdownToSafeHtml`, `parseKnowledgeArticles` from Task 1.
- Produces: `module.knowledgeNotes[]` with `intro`, `introText`, `sections`, and `text`.
- Produces: article search entries with `type: "knowledge-note"`.
- Produces: internal search entries with `type: "knowledge-section"`, `articleTitle`, and stable section IDs.

- [ ] **Step 1: Replace old generated-data expectations with failing article assertions**

Update `tests/foundations-roadmap-requirements.mjs` so it requires:

```js
assert.deepEqual(byId.coding.knowledgeNotes.map((note) => note.title), ["deque、stack 与 queue", "单调队列"]);
assert.deepEqual(byId["evals-debugging"].knowledgeNotes.map((note) => note.title), [
  "Eval Case 的六层结构",
  "Benchmark 与 Agent Behavior Eval",
]);
for (const id of ["interview-sprint", "agent-design", "llm-systems", "rag-memory", "research-reading", "behavioral-strategy", "logs"]) {
  assert.equal(byId[id].knowledgeNotes.length, 0, `${id} should not expose shallow knowledge notes`);
}
for (const id of ["coding", "evals-debugging"]) {
  for (const article of byId[id].knowledgeNotes) {
    assert.equal(typeof article.intro, "string");
    assert.ok(Array.isArray(article.sections));
    assert.deepEqual(
      article.sections.filter((section) => ["definition", "mechanism", "example", "boundary", "summary"].includes(section.kind)).map((section) => section.kind),
      ["definition", "mechanism", "example", "boundary", "summary"],
    );
  }
}
assert.equal(Object.hasOwn(byId["interview-sprint"].sections, "学习记录"), true);
assert.equal(Object.hasOwn(byId["interview-sprint"].sections, "知识笔记"), false);
assert.ok(byId.coding.searchEntries.some((entry) => (
  entry.type === "knowledge-section" && entry.articleTitle === "单调队列" && entry.sectionTitle === "核心机制"
)));
```

Remove assertions requiring every non-overview module to expose `知识笔记`, old `groups`, old card titles, or RAG knowledge notes. Keep assertions that their roadmap topics remain in `searchText`.

- [ ] **Step 2: Run the Foundations test and verify the old generator fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL because generated `knowledgeNotes` still contain `body` and `groups` instead of structured sections.

- [ ] **Step 3: Replace handwritten Markdown rendering in the builder**

In `build-roadmap-data.mjs`:

```js
import {
  markdownToSafeHtml,
  parseKnowledgeArticles,
} from "./roadmap-markdown.mjs";
```

- Delete the local `escapeHtml`, `renderInline`, `renderMarkdown`, `splitSubsections`, `splitNoteGroups`, `NOTE_GROUP_LABELS`, and `buildKnowledgeNotes` implementations.
- Render ordinary module sections with `markdownToSafeHtml(sectionMarkdown).html`.
- Build knowledge articles with `parseKnowledgeArticles(id, rawSections["知识笔记"] ?? "")`.
- Keep `stripMarkdown` only for the module-wide `searchText` field. Timeline extraction continues to consume raw Markdown directly.

- [ ] **Step 4: Emit article and internal-section search entries**

Replace the note portion of `buildSearchEntries` with:

```js
const noteEntries = knowledgeNotes.flatMap((note) => [
  {
    id: note.id,
    type: "knowledge-note",
    moduleId: id,
    moduleTitle: title,
    articleTitle: note.title,
    sectionTitle: note.title,
    text: note.text,
  },
  ...note.sections.map((section) => ({
    id: section.id,
    type: "knowledge-section",
    moduleId: id,
    moduleTitle: title,
    articleTitle: note.title,
    sectionTitle: section.title,
    text: section.text,
  })),
]).filter((entry) => entry.text.length > 20);
```

Ensure ordinary section entries use `articleTitle: ""` for a consistent data shape.

- [ ] **Step 5: Regenerate JSON and run data tests**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
node tests/foundations-knowledge-article-parser.mjs
node tests/foundations-knowledge-content-requirements.mjs
node tests/foundations-roadmap-requirements.mjs
```

Expected: all four commands exit 0.

- [ ] **Step 6: Commit the structured data pipeline**

```bash
git add projects/foundations/scripts/build-roadmap-data.mjs projects/foundations/roadmap/roadmap-data.json tests/foundations-roadmap-requirements.mjs
git commit -m "feat: generate structured foundations knowledge data"
```

---

### Task 4: Render Continuous Articles, Search Anchors, And Mermaid

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `tests/foundations-roadmap-requirements.mjs`

**Interfaces:**
- Consumes: `knowledgeNotes[].intro`, `knowledgeNotes[].sections[]`, section `kind` and section IDs.
- Produces DOM: `.knowledge-article`, `.knowledge-article-title`, `.knowledge-article-section.is-{kind}`.
- Produces: `renderMermaidDiagrams(root) -> Promise<void>` with readable-code fallback.
- Search uses internal section IDs and maps them back to the parent article for the right-panel context.

- [ ] **Step 1: Write failing reader source-contract assertions**

Add assertions requiring these functions and removing old card/group behavior:

```js
assert.match(js, /function renderKnowledgeArticleSection/);
assert.match(js, /class="knowledge-article"/);
assert.match(js, /knowledge-article-title/);
assert.match(js, /knowledge-article-section is-\$\{escapeHtml\(section\.kind\)\}/);
assert.match(js, /const mainSections = \["目标", "当前状态", "核心知识", "任务", "时间线", "学习记录", "知识笔记"\]/);
assert.match(js, /function getKnowledgeArticleForTarget/);
assert.match(js, /entry\.articleTitle/);
assert.match(js, /MERMAID_MODULE_URL = "https:\/\/cdn\.jsdelivr\.net\/npm\/mermaid@11\.12\.2\/dist\/mermaid\.esm\.min\.mjs"/);
assert.match(js, /async function renderMermaidDiagrams/);
assert.doesNotMatch(js, /note\?\.groups/);
assert.doesNotMatch(js, /note\?\.body/);
assert.doesNotMatch(js, /这个模块还没有知识笔记/);
```

- [ ] **Step 2: Run the reader contract and verify failure**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL on `renderKnowledgeArticleSection`.

- [ ] **Step 3: Implement continuous article rendering**

Add:

```js
function renderKnowledgeArticleSection(section) {
  return `
    <section class="knowledge-article-section is-${escapeHtml(section.kind)}" id="${escapeHtml(section.id)}" data-section-id="${escapeHtml(section.id)}" data-section-title="${escapeHtml(section.title)}">
      <h4>${escapeHtml(section.title)}</h4>
      <div class="knowledge-article-section-body">${section.body}</div>
    </section>
  `;
}

function renderKnowledgeNotesSection(module) {
  const notes = module.knowledgeNotes ?? [];
  if (notes.length === 0) return "";
  return `<div class="knowledge-articles">${notes.map((note) => `
    <article class="knowledge-article" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}" data-note-id="${escapeHtml(note.id)}">
      <header class="knowledge-article-header">
        <h3 class="knowledge-article-title">${escapeHtml(note.title)}</h3>
        <div class="knowledge-article-intro">${note.intro}</div>
      </header>
      ${note.sections.map(renderKnowledgeArticleSection).join("")}
    </article>
  `).join("")}</div>`;
}
```

Add `学习记录` before `知识笔记` in `mainSections`. Skip `知识笔记` when `renderKnowledgeNotesSection` returns an empty string.

- [ ] **Step 4: Map internal anchors to their parent article**

Implement:

```js
function getKnowledgeArticleForTarget(module, targetId) {
  return (module.knowledgeNotes ?? []).find((note) => (
    note.id === targetId || note.sections?.some((section) => section.id === targetId)
  )) ?? null;
}
```

Use it in `setActiveKnowledgeContext` and when computing the rail-active ID, so scrolling within one article keeps that article's rail marker active while search can still jump to a specific internal section.

- [ ] **Step 5: Render section-level search labels**

In `renderSearchResults`, compute:

```js
const resultTitle = entry.articleTitle && entry.articleTitle !== entry.sectionTitle
  ? `${entry.articleTitle} / ${entry.sectionTitle}`
  : entry.sectionTitle;
```

Render `resultTitle` in `.result-title`. Keep the module title in `.result-meta`.

- [ ] **Step 6: Add pinned progressive Mermaid rendering**

Add:

```js
const MERMAID_MODULE_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.esm.min.mjs";

async function renderMermaidDiagrams(root = els.sectionList) {
  const blocks = [...root.querySelectorAll("pre code.language-mermaid")];
  if (blocks.length === 0) return;
  try {
    const { default: mermaid } = await import(MERMAID_MODULE_URL);
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
    for (const [index, code] of blocks.entries()) {
      try {
        const { svg } = await mermaid.render(`foundations-mermaid-${Date.now()}-${index}`, code.textContent);
        const figure = document.createElement("figure");
        figure.className = "knowledge-diagram";
        figure.innerHTML = svg;
        code.closest("pre")?.replaceWith(figure);
      } catch (error) {
        console.warn("Unable to render Foundations Mermaid diagram", error);
      }
    }
  } catch (error) {
    console.warn("Unable to load Foundations Mermaid renderer", error);
  }
}
```

Call `renderMermaidDiagrams()` after module content is inserted and before final active-section synchronization. Do not replace the source `<pre>` unless rendering succeeds.

- [ ] **Step 7: Run the reader contract**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: exit 0.

- [ ] **Step 8: Commit article rendering**

```bash
git add projects/foundations/roadmap/roadmap-reader.js tests/foundations-roadmap-requirements.mjs
git commit -m "feat: render foundations knowledge articles"
```

---

### Task 5: Categorize Local Learning Notes Without Duplicating Articles

**Files:**
- Create: `projects/foundations/roadmap/annotation-model.js`
- Create: `tests/foundations-annotation-model.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `tests/foundations-roadmap-requirements.mjs`

**Interfaces:**
- Produces: `ANNOTATION_CATEGORIES` with `understanding`, `question`, `reflection`, `resource`.
- Produces: `normalizeAnnotation(annotation) -> annotation` with legacy default `understanding` for note annotations.
- Produces: `groupAnnotations(annotations) -> [{ key, label, items }]`, including plain `highlight`.
- Reader produces: `updateAnnotationCategory(annotationId, category)`.

- [ ] **Step 1: Write the failing pure-model test**

Create `tests/foundations-annotation-model.mjs`:

```js
import assert from "node:assert/strict";
import {
  ANNOTATION_CATEGORIES,
  groupAnnotations,
  normalizeAnnotation,
} from "../projects/foundations/roadmap/annotation-model.js";

assert.deepEqual(ANNOTATION_CATEGORIES.map((item) => item.id), [
  "understanding",
  "question",
  "reflection",
  "resource",
]);

const legacyNote = normalizeAnnotation({ id: "n1", mode: "note", note: "旧笔记" });
assert.equal(legacyNote.category, "understanding");

const pureHighlight = normalizeAnnotation({ id: "h1", mode: "highlight", note: "" });
assert.equal(pureHighlight.category, "highlight");

const groups = groupAnnotations([
  pureHighlight,
  legacyNote,
  normalizeAnnotation({ id: "q1", mode: "note", note: "为什么？", category: "question" }),
]);
assert.deepEqual(groups.map(({ key, label }) => [key, label]), [
  ["highlight", "高亮"],
  ["understanding", "我的理解"],
  ["question", "待解决问题"],
]);
```

- [ ] **Step 2: Run the test and verify the model is missing**

Run:

```bash
node tests/foundations-annotation-model.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement the pure annotation model**

Create `projects/foundations/roadmap/annotation-model.js`:

```js
export const ANNOTATION_CATEGORIES = [
  { id: "understanding", label: "我的理解" },
  { id: "question", label: "待解决问题" },
  { id: "reflection", label: "反思" },
  { id: "resource", label: "补充资料" },
];

const CATEGORY_LABELS = new Map([
  ["highlight", "高亮"],
  ...ANNOTATION_CATEGORIES.map((item) => [item.id, item.label]),
]);

export function normalizeAnnotation(annotation) {
  const source = annotation && typeof annotation === "object" ? annotation : {};
  const validCategory = ANNOTATION_CATEGORIES.some((item) => item.id === source.category);
  const category = source.mode === "highlight" && !source.note
    ? "highlight"
    : validCategory ? source.category : "understanding";
  return { ...source, category };
}

export function groupAnnotations(annotations) {
  const normalized = annotations.map(normalizeAnnotation);
  const orderedKeys = ["highlight", ...ANNOTATION_CATEGORIES.map((item) => item.id)];
  return orderedKeys
    .map((key) => ({
      key,
      label: CATEGORY_LABELS.get(key),
      items: normalized.filter((item) => item.category === key),
    }))
    .filter((group) => group.items.length > 0);
}
```

- [ ] **Step 4: Normalize stored annotations and render real groups**

In `roadmap-reader.js`:

```js
import {
  ANNOTATION_CATEGORIES,
  groupAnnotations,
  normalizeAnnotation,
} from "./annotation-model.js";
```

- Apply `normalizeAnnotation` inside `loadAnnotations` while preserving the v1 key.
- Set `category: mode === "note" ? "understanding" : "highlight"` for new annotations.
- Add `updateAnnotationCategory(annotationId, category)` with allow-list validation against `ANNOTATION_CATEGORIES`.
- Replace `renderLocalAnnotations` with grouped rendering. Pure highlights render their source quote only; note groups render a category `<select>` and textarea.
- Remove `noteGroups` and any fallback rendering of `note.body` from `renderContextualNotePanel`.
- Keep both desktop and mobile editors synchronized by annotation ID.
- Change the textarea placeholder to `写下自己的理解、问题、反思或补充资料`.

- [ ] **Step 5: Add failing and then passing reader assertions**

Require:

```js
assert.match(js, /from "\.\/annotation-model\.js"/);
assert.match(js, /function updateAnnotationCategory/);
assert.match(js, /data-annotation-category/);
assert.match(js, /groupAnnotations\(annotations\)/);
assert.doesNotMatch(js, /noteGroups/);
assert.doesNotMatch(js, /note\?\.body/);
assert.doesNotMatch(js, /面试表达/);
```

- [ ] **Step 6: Run annotation and reader tests**

Run:

```bash
node tests/foundations-annotation-model.mjs
node tests/foundations-roadmap-requirements.mjs
```

Expected: both exit 0.

- [ ] **Step 7: Commit annotation categories**

```bash
git add projects/foundations/roadmap/annotation-model.js projects/foundations/roadmap/roadmap-reader.js tests/foundations-annotation-model.mjs tests/foundations-roadmap-requirements.mjs
git commit -m "feat: categorize foundations learning notes"
```

---

### Task 6: Apply The Approved Article Visual System And Verify The Site

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
- Modify: `tests/foundations-roadmap-requirements.mjs`

**Interfaces:**
- Consumes DOM classes from Task 4 and annotation controls from Task 5.
- Produces responsive typography and semantic visual treatments using existing reader color tokens.
- Produces horizontal process diagrams above 860px and vertical diagrams at or below 860px.

- [ ] **Step 1: Write failing CSS contract assertions**

Add:

```js
assert.match(css, /--knowledge-heading-font:\s*"Kaiti SC",\s*STKaiti,\s*KaiTi/);
assert.match(css, /--knowledge-body-font:\s*"Songti SC",\s*STSong/);
assert.match(css, /\.knowledge-article-title\s*\{[\s\S]*font-size:\s*38px/);
assert.match(css, /\.knowledge-article-section\.is-definition/);
assert.match(css, /\.knowledge-article-section\.is-mechanism\s+ol/);
assert.match(css, /grid-template-columns:\s*42px minmax\(0,\s*1fr\)/);
assert.match(css, /\.knowledge-article-section\.is-flow\s+ol/);
assert.match(css, /\.annotation-category-select/);
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.knowledge-article-section\.is-flow\s+ol/);
assert.doesNotMatch(css, /\.knowledge-card\s*\{/);
```

- [ ] **Step 2: Run the Foundations test and verify old card CSS fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL on the first knowledge-font assertion.

- [ ] **Step 3: Replace card styles with continuous article typography**

Add to `:root`:

```css
--knowledge-heading-font: "Kaiti SC", STKaiti, KaiTi, "Songti SC", serif;
--knowledge-body-font: "Songti SC", STSong, "Noto Serif SC", Georgia, serif;
```

Replace `.knowledge-list`, `.knowledge-card`, and `.knowledge-card-body` with:

```css
.knowledge-articles {
  display: grid;
  gap: 48px;
}

.knowledge-article {
  min-width: 0;
  border-top: 1px solid var(--reader-line);
  padding: 30px 0 10px;
  font-family: var(--knowledge-body-font);
}

.knowledge-article:first-child {
  border-top: 0;
  padding-top: 4px;
}

.knowledge-article-title {
  margin: 0;
  color: var(--reader-ink);
  font-family: var(--knowledge-heading-font);
  font-size: 38px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0;
}

.knowledge-article-intro {
  margin-top: 14px;
  color: var(--reader-ink-muted);
  font-size: 17px;
  line-height: 1.85;
}

.knowledge-article-section {
  margin-top: 34px;
}

.knowledge-article-section > h4 {
  margin: 0 0 12px;
  border-bottom: 1px solid var(--reader-line);
  padding-bottom: 8px;
  color: var(--reader-blue);
  font-family: var(--knowledge-heading-font);
  font-size: 25px;
  line-height: 1.35;
  letter-spacing: 0;
}

.knowledge-article-section-body {
  font-size: 16px;
  line-height: 1.85;
}
```

Use existing `--reader-blue`, `--reader-red`, `--reader-line`, `--reader-glass-highlight`, and `--reader-ink-muted` for definition, boundary, summary, and code treatments. Do not copy literal prototype colors into production CSS.

- [ ] **Step 4: Style mechanism steps and process diagrams**

- `.is-mechanism ol` uses a counter, no default padding, and rows with `grid-template-columns: 42px minmax(0, 1fr)`.
- Its `li::before` is a fixed 34px circular marker inside the grid; do not use negative margins.
- `.is-flow ol` uses grid columns with stable `minmax(120px, 1fr)` nodes.
- `.is-flow li::after` supplies an arrow between nodes except on the last item.
- At `max-width: 860px`, `.is-flow ol` becomes one column and arrows rotate downward.
- At `max-width: 860px`, `.knowledge-article-title` uses `font-size: 32px`; font sizes never scale continuously with viewport width.
- Code blocks retain horizontal scrolling and never change article width.

- [ ] **Step 5: Style annotation categories and mobile notes**

- `.annotation-category-select` is a compact menu, not a text pill.
- Group headings use restrained color differences for highlight, understanding, question, reflection, and resource.
- Textareas and selects fit the right panel at 240px width and the mobile drawer without horizontal overflow.
- Empty right panels retain no filler copy.

- [ ] **Step 6: Run all automated checks**

Run:

```bash
node tests/foundations-knowledge-article-parser.mjs
node tests/foundations-knowledge-content-requirements.mjs
node tests/foundations-annotation-model.mjs
node tests/foundations-roadmap-requirements.mjs
npm run test:projects
npm run test:all
git diff --check
```

Expected: every command exits 0; Node assertion tests print no failures.

- [ ] **Step 7: Start the static site and capture desktop/mobile screenshots**

Run from the repository root:

```bash
python3 -m http.server 4173
```

In a second terminal, capture:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,1600 --screenshot=/tmp/foundations-knowledge-desktop.png "http://localhost:4173/projects/foundations/?module=coding"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --window-size=390,844 --screenshot=/tmp/foundations-knowledge-mobile.png "http://localhost:4173/projects/foundations/?module=coding"
```

Inspect both images and verify:

- title, h4, and body sizes are visibly distinct
- numbered markers remain inside the article edge
- process flow is horizontal on desktop and vertical on mobile
- code does not force horizontal page overflow
- right notes do not overlap the article
- mobile text wraps without clipping
- Kai/Song fallback produces readable Chinese text

- [ ] **Step 8: Commit visual and responsive work**

```bash
git add projects/foundations/roadmap/roadmap-reader.css tests/foundations-roadmap-requirements.mjs
git commit -m "style: refine foundations knowledge articles"
```

- [ ] **Step 9: Run final branch verification**

Run:

```bash
git status --short
git log --oneline --decorate -8
node projects/foundations/scripts/build-roadmap-data.mjs
node tests/foundations-roadmap-requirements.mjs
npm run test:all
git diff --check
```

Expected: clean worktree, generated JSON unchanged after rebuilding, all tests exit 0, and six feature commits follow the plan commit.
