# Foundations Roadmap Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `projects/foundations/` 从文档卡片页升级成纯静态 roadmap reader，并完整迁移现有 `llm-agent-engineer-roadmap.md` 的主干内容。

**Architecture:** 用户继续维护 Markdown 模块文件；本地 build script 将模块 Markdown 编译成 `roadmap/roadmap-data.json`；`projects/foundations/index.html` 只读取 generated JSON 并渲染三栏 reader。Foundations reader 视觉贴近 paper reader，但使用独立 CSS/JS，避免复用 paper-specific `papers/shared/reader.js`。

**Tech Stack:** Static HTML, CSS, vanilla JavaScript modules, Node.js build script, Markdown source files, GitHub Pages.

---

## File Structure

Create:

- `tests/foundations-roadmap-requirements.mjs`：Foundations reader 专用结构、数据和内容保留测试。
- `projects/foundations/scripts/build-roadmap-data.mjs`：从模块 Markdown 生成 `roadmap/roadmap-data.json`。
- `projects/foundations/roadmap/modules/overview.md`
- `projects/foundations/roadmap/modules/coding.md`
- `projects/foundations/roadmap/modules/llm-systems.md`
- `projects/foundations/roadmap/modules/agent-design.md`
- `projects/foundations/roadmap/modules/rag-memory.md`
- `projects/foundations/roadmap/modules/evals-debugging.md`
- `projects/foundations/roadmap/modules/research-reading.md`
- `projects/foundations/roadmap/modules/behavioral-strategy.md`
- `projects/foundations/roadmap/modules/logs.md`
- `projects/foundations/roadmap/roadmap-reader.css`
- `projects/foundations/roadmap/roadmap-reader.js`
- `projects/foundations/roadmap/roadmap-data.json`

Modify:

- `projects/foundations/index.html`：替换当前 README/template/roadmap 卡片页，改成 reader shell。
- `tests/projects-requirements.mjs`：保留 Foundations README/planner/roadmap 文件存在性检查；移除“首页必须链接 README/template/roadmap 卡片”的旧断言；补充 reader shell 入口断言。

Read-only reference:

- `docs/superpowers/specs/2026-07-05-foundations-roadmap-reader-design.md`
- `projects/foundations/llm-agent-engineer-roadmap.md`
- `papers/brain-memory-for-ai-agents/index.html`
- `papers/shared/reader.css`
- `papers/shared/reader.js`

---

## Task 1: Add Failing Foundations Reader Tests

**Files:**

- Create: `tests/foundations-roadmap-requirements.mjs`
- Modify: `tests/projects-requirements.mjs`

- [ ] **Step 1: Create Foundations-specific failing test**

Create `tests/foundations-roadmap-requirements.mjs` with these checks:

```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const buildScriptUrl = new URL("../projects/foundations/scripts/build-roadmap-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/foundations/roadmap/roadmap-data.json", import.meta.url);
const cssUrl = new URL("../projects/foundations/roadmap/roadmap-reader.css", import.meta.url);
const jsUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);
const modulesDirUrl = new URL("../projects/foundations/roadmap/modules/", import.meta.url);

const requiredModules = [
  ["overview", "Overview"],
  ["coding", "Coding"],
  ["llm-systems", "LLM Systems"],
  ["agent-design", "Agent Design"],
  ["rag-memory", "RAG & Memory"],
  ["evals-debugging", "Evals & Debugging"],
  ["research-reading", "Research Reading"],
  ["behavioral-strategy", "Behavioral / Strategy"],
  ["logs", "Logs"]
];

assert.equal(existsSync(foundationsPageUrl), true, "Foundations should expose a static reader page");
assert.equal(existsSync(buildScriptUrl), true, "Foundations should include a roadmap data build script");
assert.equal(existsSync(dataUrl), true, "Foundations should include generated roadmap data");
assert.equal(existsSync(cssUrl), true, "Foundations should include dedicated roadmap reader CSS");
assert.equal(existsSync(jsUrl), true, "Foundations should include dedicated roadmap reader JS");

for (const [id] of requiredModules) {
  const moduleUrl = new URL(`${id}.md`, modulesDirUrl);
  assert.equal(existsSync(moduleUrl), true, `module ${id} should exist`);
  const moduleMarkdown = readFileSync(moduleUrl, "utf8");
  assert.match(moduleMarkdown, new RegExp(`id: ${id}`), `module ${id} should declare its id`);
  assert.match(moduleMarkdown, /status: (not-started|in-progress|review|done)/, `module ${id} should declare an allowed status`);
  assert.match(moduleMarkdown, /progress: [0-9]+/, `module ${id} should declare progress`);
  assert.match(moduleMarkdown, /last_updated: 2026-07-05/, `module ${id} should declare a last updated date`);
  assert.match(moduleMarkdown, /## 目标|## 当前状态|## 时间线|## 资源|## 面试表达|## 验收标准/, `module ${id} should use fixed second-level sections`);
}

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const html = readFileSync(foundationsPageUrl, "utf8");
const css = readFileSync(cssUrl, "utf8");
const js = readFileSync(jsUrl, "utf8");
const data = JSON.parse(readFileSync(dataUrl, "utf8"));

assert.match(html, /data-page="foundations-roadmap-reader"/, "Foundations page should identify itself as the roadmap reader");
assert.match(html, /id="reader-shell"/, "Foundations page should include a reader shell");
assert.match(html, /id="module-directory"/, "Foundations page should include a left module directory");
assert.match(html, /id="reader-main"/, "Foundations page should include a center reader area");
assert.match(html, /id="note-panel"/, "Foundations page should include a right note panel");
assert.match(html, /id="global-search"/, "Foundations page should include global search");
assert.match(html, /href="roadmap\/roadmap-reader\.css"/, "Foundations page should load dedicated reader CSS");
assert.match(html, /src="roadmap\/roadmap-reader\.js"/, "Foundations page should load dedicated reader JS");
assert.doesNotMatch(html, /class="doc-grid"|class="doc-link"/, "Foundations page should no longer render the document-card homepage as the main experience");
assert.doesNotMatch(html, /href="README\.md"[\s\S]*href="multi-agent-planner\.md"[\s\S]*href="llm-agent-engineer-roadmap\.md"/, "Foundations homepage should not be a README/template/roadmap card list");

assert.match(css, /\.reader-shell\s*\{[\s\S]*grid-template-columns:/, "roadmap CSS should define a three-column reader shell");
assert.match(css, /data-theme="dark"/, "roadmap CSS should support dark mode");
assert.match(css, /\.module-nav-item\[aria-current="true"\]/, "roadmap CSS should style the active module");
assert.match(css, /\.progress-meter/, "roadmap CSS should style module progress");
assert.match(css, /@media \(max-width:\s*860px\)/, "roadmap CSS should include mobile layout rules");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "roadmap reader should avoid oversized card radii");

assert.match(js, /fetchJson\("roadmap\/roadmap-data\.json"\)/, "roadmap JS should load generated JSON");
assert.match(js, /function renderModuleNav/, "roadmap JS should isolate module navigation rendering");
assert.match(js, /function renderCurrentModule/, "roadmap JS should isolate module content rendering");
assert.match(js, /function renderNotePanel/, "roadmap JS should isolate right-note rendering");
assert.match(js, /function runSearch/, "roadmap JS should implement local keyword search");
assert.match(js, /function setTheme/, "roadmap JS should support theme switching");
assert.doesNotMatch(js, /localStorage|sessionStorage/, "first version should not persist state in browser storage");
assert.doesNotMatch(js, /embeddings\.json|cosineSimilarity|PROJECT_ID = "brain-memory-for-ai-agents"/, "Foundations reader JS should not reuse paper-specific semantic search state");

assert.equal(data.project.id, "foundations", "generated data should identify the Foundations project");
assert.equal(data.project.targetRole, "Agent / LLM Systems Engineer", "generated data should keep the target role");
assert.deepEqual(data.modules.map((module) => [module.id, module.title]), requiredModules, "generated data should include the required modules in navigation order");

for (const module of data.modules) {
  assert.equal(typeof module.status, "string", `${module.id} should include status`);
  assert.equal(typeof module.progress, "number", `${module.id} should include numeric progress`);
  assert.equal(typeof module.lastUpdated, "string", `${module.id} should include lastUpdated`);
  assert.equal(typeof module.searchText, "string", `${module.id} should include search text`);
  assert.ok(module.searchText.length > 80, `${module.id} should have useful search text`);
  assert.ok(module.sections && typeof module.sections === "object", `${module.id} should include sections`);
}

const byId = Object.fromEntries(data.modules.map((module) => [module.id, module]));
assert.match(byId.overview.searchText, /30\/45\/60-Day Plan|Project Recommendations|Weekly Review Checklist/, "overview should preserve timeline and project recommendation content");
assert.match(byId.coding.searchText, /Coding Plan|Python Standards|TypeScript Standards|Optional Rust Log Parser/, "coding should preserve implementation training content");
assert.match(byId["llm-systems"].searchText, /LLM Systems|Transformer|post-training|LLM Fundamentals/, "LLM systems should preserve model and theory content");
assert.match(byId["agent-design"].searchText, /Agent Systems|Agent Runtime With Tool Calling|Safe Tool Execution Layer|Tool Router/, "agent design should preserve agent runtime content");
assert.match(byId["rag-memory"].searchText, /RAG And Memory|Production RAG System|Long-Term Memory|Retrieval Evaluator|Memory Store/, "RAG and memory should preserve retrieval and memory content");
assert.match(byId["evals-debugging"].searchText, /Eval And Debugging|Eval Harness|Trace Debugging|Agent Trace Logger/, "evals should preserve eval and trace content");
assert.match(byId["research-reading"].searchText, /Research Reading List|scaling laws|RLHF|RLAIF|RLVR/, "research reading should preserve reading list content");
assert.match(byId["behavioral-strategy"].searchText, /Behavioral And Project Deep Dive|Strategy Rubric|STAR|tradeoff/, "behavioral strategy should preserve interview strategy content");
assert.match(byId.logs.searchText, /Weekly Review|review checklist|复盘/, "logs should preserve review and reflection content");
```

- [ ] **Step 2: Update project homepage test expectations**

In `tests/projects-requirements.mjs`, replace the old Foundations page-card checks:

```js
assert.match(foundationsHtml, /href="README\.md"/, "foundations page should link to the project README");
assert.match(foundationsHtml, /href="multi-agent-planner\.md"/, "foundations page should link to the reusable planner");
assert.match(foundationsHtml, /href="llm-agent-engineer-roadmap\.md"/, "foundations page should link to the roadmap");
```

with reader checks:

```js
assert.match(foundationsHtml, /data-page="foundations-roadmap-reader"/, "foundations page should identify itself as the roadmap reader");
assert.match(foundationsHtml, /id="reader-shell"/, "foundations page should use the reader shell");
assert.match(foundationsHtml, /roadmap\/roadmap-data\.json/, "foundations reader should load generated roadmap data");
assert.doesNotMatch(foundationsHtml, /class="doc-grid"|class="doc-link"/, "foundations page should not remain a document-card homepage");
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL because `projects/foundations/scripts/build-roadmap-data.mjs` and the roadmap reader files do not exist yet.

- [ ] **Step 4: Commit failing tests**

Run:

```bash
git add tests/foundations-roadmap-requirements.mjs tests/projects-requirements.mjs
git commit -m "Add foundations roadmap reader requirements"
```

---

## Task 2: Add Module Markdown Sources

**Files:**

- Create: `projects/foundations/roadmap/modules/*.md`
- Reference: `projects/foundations/llm-agent-engineer-roadmap.md`

- [ ] **Step 1: Create module files with frontmatter**

Create nine module files using these frontmatter values:

```yaml
id: overview
title: Overview
status: in-progress
progress: 45
last_updated: 2026-07-05
priority: high
```

```yaml
id: coding
title: Coding
status: in-progress
progress: 35
last_updated: 2026-07-05
priority: high
```

```yaml
id: llm-systems
title: LLM Systems
status: in-progress
progress: 30
last_updated: 2026-07-05
priority: high
```

```yaml
id: agent-design
title: Agent Design
status: in-progress
progress: 35
last_updated: 2026-07-05
priority: high
```

```yaml
id: rag-memory
title: RAG & Memory
status: in-progress
progress: 30
last_updated: 2026-07-05
priority: high
```

```yaml
id: evals-debugging
title: Evals & Debugging
status: in-progress
progress: 25
last_updated: 2026-07-05
priority: high
```

```yaml
id: research-reading
title: Research Reading
status: in-progress
progress: 25
last_updated: 2026-07-05
priority: medium
```

```yaml
id: behavioral-strategy
title: Behavioral / Strategy
status: in-progress
progress: 30
last_updated: 2026-07-05
priority: high
```

```yaml
id: logs
title: Logs
status: in-progress
progress: 20
last_updated: 2026-07-05
priority: medium
```

- [ ] **Step 2: Populate fixed sections**

Each module should use these section headings when relevant:

```md
## 目标
## 当前状态
## 核心知识
## 任务
## 时间线
## 资源
## 反思
## 面试表达
## 验收标准
## 下一步
```

Content mapping must follow the spec:

- `overview.md`: Profile And Target, Supervisor Synthesis, 30/45/60-Day Plan, Project Recommendations, Weekly Review Checklist.
- `coding.md`: Coding Fundamentals, Python / TypeScript Implementation, Coding Plan, Coding mock questions, implementation drills, optional Rust.
- `llm-systems.md`: LLM Systems, transformer/inference/post-training reading, LLM Fundamentals mock questions.
- `agent-design.md`: Agent Systems, agent runtime, safe tool execution, tool router, TypeScript agent interface, streaming wrapper.
- `rag-memory.md`: RAG And Memory, production RAG, long-term memory, retrieval evaluator, memory store.
- `evals-debugging.md`: Eval And Debugging, eval harness, trace debugging, agent trace logger.
- `research-reading.md`: Research Reading List with interview-use notes.
- `behavioral-strategy.md`: Behavioral mock set, Strategy Rubric, project storytelling and tradeoff expression.
- `logs.md`: Weekly review checklist and initial reflection log.

- [ ] **Step 3: Verify module content coverage**

Run:

```bash
rg -n "30/45/60-Day Plan|Coding Plan|Python Standards|TypeScript Standards|Agent Runtime With Tool Calling|Production RAG System|Eval Harness|Research Reading List|Strategy Rubric|Weekly Review" projects/foundations/roadmap/modules
```

Expected: Each phrase appears in at least one module file.

- [ ] **Step 4: Commit module sources**

Run:

```bash
git add projects/foundations/roadmap/modules
git commit -m "Add foundations roadmap module sources"
```

---

## Task 3: Add Markdown-To-JSON Build Script

**Files:**

- Create: `projects/foundations/scripts/build-roadmap-data.mjs`
- Create: `projects/foundations/roadmap/roadmap-data.json`

- [ ] **Step 1: Implement build script**

Create `projects/foundations/scripts/build-roadmap-data.mjs` with these responsibilities:

```js
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const foundationsDir = dirname(scriptDir);
const modulesDir = join(foundationsDir, "roadmap", "modules");
const outputPath = join(foundationsDir, "roadmap", "roadmap-data.json");

const MODULES = [
  ["overview", "Overview"],
  ["coding", "Coding"],
  ["llm-systems", "LLM Systems"],
  ["agent-design", "Agent Design"],
  ["rag-memory", "RAG & Memory"],
  ["evals-debugging", "Evals & Debugging"],
  ["research-reading", "Research Reading"],
  ["behavioral-strategy", "Behavioral / Strategy"],
  ["logs", "Logs"]
];

const VALID_STATUSES = new Set(["not-started", "in-progress", "review", "done"]);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseFrontmatter(markdown, fileLabel) {
  const match = markdown.match(/^---\n(?<body>[\s\S]*?)\n---\n(?<content>[\s\S]*)$/);
  if (!match?.groups) throw new Error(`${fileLabel} is missing frontmatter`);
  const data = {};
  for (const line of match.groups.body.split("\n")) {
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    data[key] = value;
  }
  return { data, content: match.groups.content.trim() };
}

function splitSections(content) {
  const sections = {};
  const matches = Array.from(content.matchAll(/^## (.+)$/gm));
  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const next = matches[index + 1];
    const title = current[1].trim();
    const start = current.index + current[0].length;
    const end = next?.index ?? content.length;
    sections[title] = content.slice(start, end).trim();
  }
  return sections;
}

function renderInline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function renderMarkdown(markdown) {
  const lines = String(markdown ?? "").split("\n");
  const blocks = [];
  let paragraph = [];
  let list = [];
  let inCode = false;
  let codeLines = [];
  let codeLanguage = "";

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (list.length === 0) return;
    blocks.push(`<ul>${list.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ul>`);
    list = [];
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        blocks.push(`<pre><code data-language="${escapeHtml(codeLanguage)}">${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        inCode = false;
        codeLines = [];
        codeLanguage = "";
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeLanguage = line.slice(3).trim();
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    if (/^### /.test(line)) {
      flushParagraph();
      flushList();
      blocks.push(`<h3>${renderInline(line.replace(/^### /, ""))}</h3>`);
      continue;
    }

    const listMatch = line.match(/^- \[( |x)\] (.+)$/i) ?? line.match(/^- (.+)$/);
    if (listMatch) {
      flushParagraph();
      list.push(listMatch[2] ?? listMatch[1]);
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }

    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  return blocks.join("\n");
}

function stripMarkdown(markdown) {
  return String(markdown ?? "")
    .replace(/^---[\s\S]*?---/, "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#>*_`\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function validateModule(record, expectedId, expectedTitle) {
  if (record.id !== expectedId) throw new Error(`${expectedId} has id ${record.id}`);
  if (record.title !== expectedTitle) throw new Error(`${expectedId} has title ${record.title}`);
  if (!VALID_STATUSES.has(record.status)) throw new Error(`${expectedId} has invalid status ${record.status}`);
  if (!Number.isFinite(record.progress) || record.progress < 0 || record.progress > 100) {
    throw new Error(`${expectedId} has invalid progress ${record.progress}`);
  }
  if (!record.lastUpdated) throw new Error(`${expectedId} is missing lastUpdated`);
}

function buildModule([id, title]) {
  const markdownPath = join(modulesDir, `${id}.md`);
  const markdown = readFileSync(markdownPath, "utf8");
  const parsed = parseFrontmatter(markdown, `${id}.md`);
  const rawSections = splitSections(parsed.content);
  const sections = Object.fromEntries(
    Object.entries(rawSections).map(([sectionTitle, sectionMarkdown]) => [sectionTitle, renderMarkdown(sectionMarkdown)])
  );
  const record = {
    id: parsed.data.id,
    title: parsed.data.title,
    status: parsed.data.status,
    progress: Number(parsed.data.progress),
    lastUpdated: parsed.data.last_updated,
    priority: parsed.data.priority ?? "medium",
    sections,
    searchText: `${title} ${stripMarkdown(parsed.content)}`
  };
  validateModule(record, id, title);
  return record;
}

const roadmapData = {
  generatedAt: new Date().toISOString(),
  project: {
    id: "foundations",
    title: "基石",
    targetRole: "Agent / LLM Systems Engineer"
  },
  modules: MODULES.map(buildModule)
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
```

- [ ] **Step 2: Run script**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
```

Expected: `projects/foundations/roadmap/roadmap-data.json` is created and parseable.

- [ ] **Step 3: Run Foundations test and verify progress**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL because `index.html`, CSS, and JS are not implemented yet.

- [ ] **Step 4: Commit build script and generated data**

Run:

```bash
git add projects/foundations/scripts/build-roadmap-data.mjs projects/foundations/roadmap/roadmap-data.json
git commit -m "Build foundations roadmap data"
```

---

## Task 4: Replace Foundations Homepage With Reader Shell

**Files:**

- Modify: `projects/foundations/index.html`
- Create: `projects/foundations/roadmap/roadmap-reader.css`
- Create: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Replace HTML with reader shell**

`projects/foundations/index.html` should include:

- `<body data-page="foundations-roadmap-reader" data-theme="light">`
- `#reader-shell`
- `#search-overlay`
- `#reader-toolbar`
- `#module-directory`
- `#module-nav`
- `#section-lines`
- `#reader-main`
- `#module-header`
- `#section-list`
- `#note-panel`
- `#mobile-note-drawer`
- `#global-search`
- CSS link `roadmap/roadmap-reader.css`
- module script `roadmap/roadmap-reader.js`

- [ ] **Step 2: Add dedicated CSS**

`roadmap-reader.css` should define:

- reader tokens matching the paper reader tone.
- three-column `.reader-shell`.
- `.reader-shell.is-left-collapsed`, `.reader-shell.is-note-collapsed`, `.reader-shell.is-searching`.
- toolbar search modal.
- `.module-nav-item[aria-current="true"]`.
- `.progress-meter`.
- `.module-section`.
- `.note-panel` as a continuous right note surface.
- mobile layout under `@media (max-width: 860px)`.

- [ ] **Step 3: Add reader JS**

`roadmap-reader.js` should implement:

- `fetchJson("roadmap/roadmap-data.json")`.
- `renderModuleNav()`.
- `renderCurrentModule()`.
- `renderNotePanel()`.
- `renderSectionRail()`.
- `runSearch()`.
- `setTheme()`.
- `openSearchModal()` and `closeSearchModal()`.
- URL state using `?module=<id>`.
- left and right panel toggles.

The JS must not use `localStorage`, `sessionStorage`, paper embeddings, or `PROJECT_ID = "brain-memory-for-ai-agents"`.

- [ ] **Step 4: Run reader tests**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
node tests/projects-requirements.mjs
```

Expected: both PASS.

- [ ] **Step 5: Commit reader page**

Run:

```bash
git add projects/foundations/index.html projects/foundations/roadmap/roadmap-reader.css projects/foundations/roadmap/roadmap-reader.js tests/projects-requirements.mjs
git commit -m "Add foundations roadmap reader"
```

---

## Task 5: Verify Browser Behavior And Existing Pages

**Files:**

- No planned file changes unless verification exposes a bug.

- [ ] **Step 1: Run full local tests**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 2: Start local HTTP server**

Run:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Expected: server starts and serves the repository root.

- [ ] **Step 3: Verify desktop reader DOM**

Use a browser or bundled Playwright with installed Chrome to open:

```text
http://127.0.0.1:8765/projects/foundations/
```

Expected DOM:

- title contains `基石`
- `.module-nav-item` count is 9
- active module defaults to `Overview`
- `#reader-main` contains 30/45/60-day plan content
- search for `RAG` returns `RAG & Memory`
- switching to `?module=coding` renders Coding content

- [ ] **Step 4: Verify mobile reader DOM**

Open the same URL at a narrow viewport.

Expected:

- content width does not overflow viewport
- mobile directory toggle exists
- note drawer exists
- search modal width stays within viewport

- [ ] **Step 5: Stop local HTTP server**

Stop the server process after browser verification finishes.

---

## Task 6: Finalize And Push

**Files:**

- No planned file changes unless final verification exposes a bug.

- [ ] **Step 1: Confirm clean status**

Run:

```bash
git status --short --branch
```

Expected: branch is ahead of `origin/main` with no unstaged changes.

- [ ] **Step 2: Push main**

Run:

```bash
git push origin main
```

Expected: push succeeds.

- [ ] **Step 3: Watch GitHub Pages**

Run:

```bash
gh run list --repo mingxiangbian/NeuroScience --branch main --limit 5
gh run watch <latest-run-id> --repo mingxiangbian/NeuroScience --exit-status
```

Expected: latest `Deploy GitHub Pages` run completes successfully.

- [ ] **Step 4: Verify live Pages**

Run:

```bash
curl -fsSL https://mingxiangbian.github.io/NeuroScience/projects/foundations/ | rg -n "foundations-roadmap-reader|roadmap-reader.js|roadmap-reader.css"
curl -fsSL https://mingxiangbian.github.io/NeuroScience/projects/foundations/roadmap/roadmap-data.json | rg -n "\"title\": \"Coding\"|\"title\": \"RAG & Memory\"|\"targetRole\": \"Agent / LLM Systems Engineer\""
```

Expected: both commands find the expected live content.
