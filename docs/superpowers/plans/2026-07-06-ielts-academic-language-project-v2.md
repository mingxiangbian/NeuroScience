# IELTS Academic Language Project v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 IELTS Academic v1 Markdown 项目包扩展为完整 v2：结构化数据、notes / journal、build script、GitHub Pages 静态 reader、项目目录入口和验证测试。

**Architecture:** `projects/language/ielts-academic/` 保持唯一 source of truth；`scripts/build-ielts-data.mjs` 从 Markdown、JSON 和 frontmatter 生成 `site/ielts-data.json`；`index.html` 和 `site/ielts-reader.js` 只读渲染 dashboard、swimlane、errors、notes、journal、prompt library 和 validation。页面不写回 repo，不使用 backend、token 或 GitHub API。

**Tech Stack:** Markdown, JSON, plain HTML/CSS/JavaScript, Node.js standard library tests, GitHub Pages static files.

---

## File Map

- Modify: `tests/ielts-academic-language-project-requirements.mjs`
  扩展 v1 项目包测试，覆盖 v2 文件存在性、页面资源、README 入口和 manifest entry。
- Create: `tests/ielts-academic-site-data-requirements.mjs`
  运行 build script，校验 `site/ielts-data.json` schema、cross-reference integrity、allowlist 和无写回逻辑。
- Modify: `tests/projects-requirements.mjs`
  更新项目目录 manifest 断言，让 IELTS Academic 出现在项目书签列表中。
- Create: `projects/language/ielts-academic/diagnostics/score-profile.json`
  Dashboard 当前 score profile 数据；初始状态必须标记为 template / initial，不能伪造成绩。
- Create: `projects/language/ielts-academic/diagnostics/score-history.json`
  Week-by-week score history starter data。
- Create: `projects/language/ielts-academic/diagnostics/error-log.json`
  Error board source data，包含 starter error IDs 供 cross-reference 验证。
- Create: `projects/language/ielts-academic/plans/checkpoint-status.json`
  Week 2 / 4 / 6 / 8 checkpoint 状态数据。
- Create: `projects/language/ielts-academic/notes/README.md`
  Notes 系统入口和 frontmatter contract。
- Create: `projects/language/ielts-academic/notes/{listening,reading,writing,speaking,vocabulary,grammar}/`
  技能笔记目录；每个目录可用 `.gitkeep` 保留。
- Create: `projects/language/ielts-academic/notes/writing/task-2-argument-development.md`
  Starter note，用于验证 `related_errors` 和 notes rendering。
- Create: `projects/language/ielts-academic/journal/README.md`
  Journal 系统入口和 frontmatter contract。
- Create: `projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md`
  Starter journal entry，用于验证 `related_notes` 和 `related_errors`。
- Create: `projects/language/ielts-academic/scripts/build-ielts-data.mjs`
  读取 source files、解析 frontmatter、校验 references、生成 site data。
- Create: `projects/language/ielts-academic/site/ielts-data.json`
  Build output，由脚本生成并提交，方便 GitHub Pages 直接读取。
- Create: `projects/language/ielts-academic/site/ielts-reader.css`
  IELTS reader 样式。
- Create: `projects/language/ielts-academic/site/ielts-reader.js`
  IELTS reader 渲染、搜索、过滤和 section navigation。
- Create: `projects/language/ielts-academic/index.html`
  GitHub Pages static reader shell。
- Modify: `projects/language/README.md`
  增加页面入口、data workflow、notes / journal 提示。
- Modify: `projects/language/ielts-academic/README.md`
  增加 v2 usage flow、static reader、structured data 和 build command。
- Modify: `projects/manifest.json`
  注册 IELTS Academic 项目。

---

### Task 1: V2 Structural Contract And Project Entry

**Files:**
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
- Modify: `tests/projects-requirements.mjs`
- Create: `projects/language/ielts-academic/index.html`
- Create: `projects/language/ielts-academic/site/ielts-reader.css`
- Create: `projects/language/ielts-academic/site/ielts-reader.js`
- Create: `projects/language/ielts-academic/scripts/build-ielts-data.mjs`
- Modify: `projects/manifest.json`

- [ ] **Step 1: Extend the IELTS project requirements test**

In `tests/ielts-academic-language-project-requirements.mjs`, add these paths to `requiredFiles` after the current validation checklist entries:

```js
  "../projects/language/ielts-academic/index.html",
  "../projects/language/ielts-academic/scripts/build-ielts-data.mjs",
  "../projects/language/ielts-academic/site/ielts-data.json",
  "../projects/language/ielts-academic/site/ielts-reader.css",
  "../projects/language/ielts-academic/site/ielts-reader.js",
```

Add these reads after `const dryRuns = ...`:

```js
const projectIndex = read("../projects/language/ielts-academic/index.html");
const siteJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const siteCss = read("../projects/language/ielts-academic/site/ielts-reader.css");
const buildScript = read("../projects/language/ielts-academic/scripts/build-ielts-data.mjs");
const manifest = JSON.parse(read("../projects/manifest.json"));
```

Add these assertions before the final pathname assertions:

```js
assert.match(projectIndex, /data-page="ielts-academic-reader"/, "IELTS project should expose a dedicated reader page");
assert.match(projectIndex, /site\/ielts-reader\.css/, "IELTS reader should load dedicated CSS");
assert.match(projectIndex, /site\/ielts-reader\.js/, "IELTS reader should load dedicated JS");
assert.match(projectIndex, /id="dashboard"/, "IELTS reader should include a dashboard region");
assert.match(projectIndex, /id="swimlane"/, "IELTS reader should include a swimlane region");
assert.match(projectIndex, /id="errors"/, "IELTS reader should include an errors region");
assert.match(projectIndex, /id="notes"/, "IELTS reader should include a notes region");
assert.match(projectIndex, /id="journal"/, "IELTS reader should include a journal region");
assert.match(projectIndex, /id="prompt-library"/, "IELTS reader should include a prompt library region");
assert.match(projectIndex, /id="validation"/, "IELTS reader should include a validation region");

assert.match(siteCss, /\.ielts-shell/, "IELTS CSS should style the reader shell");
assert.match(siteCss, /\.swimlane-grid/, "IELTS CSS should style the 8-week swimlane");
assert.match(siteCss, /\.error-board/, "IELTS CSS should style the error board");
assert.match(siteCss, /@media \(max-width:\s*860px\)/, "IELTS CSS should include responsive rules");

assert.match(siteJs, /fetchJson\("site\/ielts-data\.json"\)/, "IELTS JS should load generated site data");
assert.match(siteJs, /function renderDashboard/, "IELTS JS should render dashboard");
assert.match(siteJs, /function renderSwimlane/, "IELTS JS should render swimlane");
assert.match(siteJs, /function renderErrors/, "IELTS JS should render errors");
assert.match(siteJs, /function renderNotes/, "IELTS JS should render notes");
assert.match(siteJs, /function renderJournal/, "IELTS JS should render journal");
assert.match(siteJs, /function renderPromptLibrary/, "IELTS JS should render prompt library");
assert.match(siteJs, /function renderValidation/, "IELTS JS should render validation");
assert.doesNotMatch(siteJs, /githubToken|Authorization|contents\/|repos\/|fetch\(\"\/api/i, "IELTS JS should not include backend or GitHub write-back signals");

assert.match(buildScript, /function parseFrontmatter/, "build script should parse frontmatter");
assert.match(buildScript, /function validateReferences/, "build script should validate cross references");

const ieltsProject = manifest.find((project) => project.id === "ielts-academic");
assert.ok(ieltsProject, "projects manifest should include IELTS Academic");
assert.equal(ieltsProject.folder, "language/ielts-academic/", "IELTS manifest folder should point to the nested language project");
assert.equal(ieltsProject.status, "active", "IELTS manifest entry should be active");
```

- [ ] **Step 2: Update the project directory requirements test**

In `tests/projects-requirements.mjs`, replace the manifest title assertion:

```js
assert.deepEqual(
  manifest.map((project) => project.title),
  ["基石", "IELTS Academic", "记忆与智能体"],
  "projects bookmarks should include the registered project titles in display order",
);
```

Replace the font subset assertion with:

```js
assert.match(fontSources, /ZhiMangXing-Regular\.ttf --text='记忆与智能体基石'/, "bookmark font subset should include the Chinese project bookmark titles");
```

Add this assertion after the manifest title assertion:

```js
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.folder,
  "language/ielts-academic/",
  "IELTS Academic should be linked through the nested language project folder",
);
```

- [ ] **Step 3: Run the structural tests and confirm failure**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL with a missing file assertion for `../projects/language/ielts-academic/index.html` or one of the new v2 files.

Run:

```bash
node tests/projects-requirements.mjs
```

Expected: FAIL because `projects/manifest.json` does not yet contain `IELTS Academic`.

- [ ] **Step 4: Add the minimal structural files required by the test**

Create `projects/language/ielts-academic/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>IELTS Academic | Language</title>
    <link rel="stylesheet" href="site/ielts-reader.css" />
  </head>
  <body data-page="ielts-academic-reader">
    <div class="ielts-shell">
      <aside class="reader-sidebar" aria-label="IELTS project sections">
        <a href="../README.md">Language</a>
        <button type="button" data-section-target="dashboard">Dashboard</button>
        <button type="button" data-section-target="swimlane">8-Week Plan</button>
        <button type="button" data-section-target="errors">Errors</button>
        <button type="button" data-section-target="notes">Notes</button>
        <button type="button" data-section-target="journal">Journal</button>
        <button type="button" data-section-target="prompt-library">Prompt Library</button>
        <button type="button" data-section-target="validation">Validation</button>
      </aside>
      <main class="reader-main">
        <section id="dashboard" class="reader-section"></section>
        <section id="swimlane" class="reader-section"></section>
        <section id="errors" class="reader-section"></section>
        <section id="notes" class="reader-section"></section>
        <section id="journal" class="reader-section"></section>
        <section id="prompt-library" class="reader-section"></section>
        <section id="validation" class="reader-section"></section>
      </main>
    </div>
    <script src="site/ielts-reader.js" defer></script>
  </body>
</html>
```

Create `projects/language/ielts-academic/site/ielts-reader.css`:

```css
:root {
  color-scheme: light;
  --ielts-ink: #202522;
  --ielts-muted: rgba(32, 37, 34, 0.68);
  --ielts-paper: #f7f4ea;
  --ielts-panel: #fffdf7;
  --ielts-line: rgba(32, 37, 34, 0.16);
  --ielts-accent: #2f6f68;
  --ielts-risk: #b94b42;
  --ielts-ready: #4d7b56;
  font-family: "Inter", "SF Pro Display", "PingFang SC", system-ui, sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  color: var(--ielts-ink);
  background: var(--ielts-paper);
}

.ielts-shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: 100vh;
}

.reader-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 24px;
  border-right: 1px solid var(--ielts-line);
  background: rgba(255, 253, 247, 0.82);
}

.reader-sidebar a,
.reader-sidebar button {
  display: block;
  width: 100%;
  margin: 0 0 8px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  text-decoration: none;
  font: inherit;
  cursor: pointer;
}

.reader-main {
  padding: 32px;
}

.reader-section {
  margin: 0 0 32px;
}

.swimlane-grid {
  display: grid;
  grid-template-columns: 120px repeat(8, minmax(88px, 1fr));
  gap: 1px;
  overflow-x: auto;
  border: 1px solid var(--ielts-line);
}

.error-board {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 12px;
}

.chip {
  display: inline-flex;
  align-items: center;
  margin: 0 6px 6px 0;
  padding: 4px 8px;
  border: 1px solid var(--ielts-line);
  border-radius: 999px;
  color: var(--ielts-muted);
}

@media (max-width: 860px) {
  .ielts-shell {
    grid-template-columns: 1fr;
  }

  .reader-sidebar {
    position: static;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--ielts-line);
  }

  .reader-main {
    padding: 20px;
  }

  .error-board {
    grid-template-columns: 1fr;
  }
}
```

Create `projects/language/ielts-academic/site/ielts-reader.js`:

```js
async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}: ${response.status}`);
  return response.json();
}

function setText(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html;
}

function renderDashboard(data) {
  setText("dashboard", `<h1>IELTS Academic Dashboard</h1><p>Target: Overall ${data.scoreProfile.target.overall}, each skill ${data.scoreProfile.target.perSkillFloor}+.</p>`);
}

function renderSwimlane(data) {
  setText("swimlane", `<h2>8-Week Swimlane</h2><div class="swimlane-grid">${data.checkpoints.checkpoints.map((checkpoint) => `<div>Week ${checkpoint.week}</div><div>${checkpoint.name}</div>`).join("")}</div>`);
}

function renderErrors(data) {
  setText("errors", `<h2>Errors</h2><div class="error-board">${data.errorLog.errors.map((error) => `<article><h3>${error.id}</h3><p>${error.description}</p></article>`).join("")}</div>`);
}

function renderNotes(data) {
  setText("notes", `<h2>Notes</h2>${data.notes.map((note) => `<article><h3>${note.title}</h3><p>${note.skill}</p></article>`).join("")}`);
}

function renderJournal(data) {
  setText("journal", `<h2>Journal</h2>${data.journal.map((entry) => `<article><h3>${entry.title}</h3><p>${entry.date}</p></article>`).join("")}`);
}

function renderPromptLibrary(data) {
  setText("prompt-library", `<h2>Prompt Library</h2>${data.promptLibrary.map((prompt) => `<article><h3>${prompt.title}</h3></article>`).join("")}`);
}

function renderValidation(data) {
  setText("validation", `<h2>Validation</h2>${data.validation.map((item) => `<article><h3>${item.title}</h3></article>`).join("")}`);
}

async function init() {
  const data = await fetchJson("site/ielts-data.json");
  renderDashboard(data);
  renderSwimlane(data);
  renderErrors(data);
  renderNotes(data);
  renderJournal(data);
  renderPromptLibrary(data);
  renderValidation(data);
}

init().catch((error) => {
  setText("dashboard", `<h1>IELTS Academic Dashboard</h1><p>${error.message}</p>`);
});
```

Create `projects/language/ielts-academic/scripts/build-ielts-data.mjs` as a temporary working script that will be replaced in Task 3:

```js
import { mkdirSync, writeFileSync } from "node:fs";

function parseFrontmatter(markdown) {
  return { data: {}, body: markdown };
}

function validateReferences() {
  return [];
}

const output = new URL("../site/ielts-data.json", import.meta.url);
mkdirSync(new URL("../site/", import.meta.url), { recursive: true });
writeFileSync(
  output,
  JSON.stringify(
    {
      build: { generatedAt: "2026-07-06", referenceIssues: [] },
      scoreProfile: { target: { overall: 8, perSkillFloor: 7.5 }, skills: [] },
      scoreHistory: { entries: [] },
      errorLog: { errors: [] },
      checkpoints: { checkpoints: [] },
      notes: [],
      journal: [],
      promptLibrary: [],
      validation: [],
    },
    null,
    2,
  ),
);
```

Create `projects/language/ielts-academic/site/ielts-data.json` by running:

```bash
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
```

- [ ] **Step 5: Register IELTS Academic in the project manifest**

Edit `projects/manifest.json` so it becomes:

```json
[
  {
    "id": "foundations",
    "title": "基石",
    "folder": "foundations/",
    "summary": "Interview preparation foundations for AI, agents, architectures, AGI, and embodied intelligence.",
    "status": "active"
  },
  {
    "id": "ielts-academic",
    "title": "IELTS Academic",
    "folder": "language/ielts-academic/",
    "summary": "Diagnostic-driven IELTS Academic preparation with multi-agent prompts, adaptive planning, notes, journal, and validation dashboards.",
    "status": "active"
  },
  {
    "id": "brain-memory-for-ai-agents",
    "title": "记忆与智能体",
    "folder": "brain-memory-for-ai-agents/",
    "summary": "Neuroscience memory mechanisms as a foundation for later agent-memory research.",
    "status": "active"
  }
]
```

- [ ] **Step 6: Run tests for the structural contract**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/projects-requirements.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit the structural contract**

Run:

```bash
git add tests/ielts-academic-language-project-requirements.mjs tests/projects-requirements.mjs projects/manifest.json projects/language/ielts-academic/index.html projects/language/ielts-academic/site/ielts-reader.css projects/language/ielts-academic/site/ielts-reader.js projects/language/ielts-academic/site/ielts-data.json projects/language/ielts-academic/scripts/build-ielts-data.mjs
git commit -m "test: add IELTS v2 structural contract"
```

---

### Task 2: Structured Source Data, Notes, And Journal

**Files:**
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
- Create: `projects/language/ielts-academic/diagnostics/score-profile.json`
- Create: `projects/language/ielts-academic/diagnostics/score-history.json`
- Create: `projects/language/ielts-academic/diagnostics/error-log.json`
- Create: `projects/language/ielts-academic/plans/checkpoint-status.json`
- Create: `projects/language/ielts-academic/notes/README.md`
- Create: `projects/language/ielts-academic/notes/listening/.gitkeep`
- Create: `projects/language/ielts-academic/notes/reading/.gitkeep`
- Create: `projects/language/ielts-academic/notes/writing/task-2-argument-development.md`
- Create: `projects/language/ielts-academic/notes/speaking/.gitkeep`
- Create: `projects/language/ielts-academic/notes/vocabulary/.gitkeep`
- Create: `projects/language/ielts-academic/notes/grammar/.gitkeep`
- Create: `projects/language/ielts-academic/journal/README.md`
- Create: `projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md`

- [ ] **Step 1: Extend the source content assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, add these paths to `requiredFiles` after the site files added in Task 1:

```js
  "../projects/language/ielts-academic/diagnostics/score-profile.json",
  "../projects/language/ielts-academic/diagnostics/score-history.json",
  "../projects/language/ielts-academic/diagnostics/error-log.json",
  "../projects/language/ielts-academic/plans/checkpoint-status.json",
  "../projects/language/ielts-academic/notes/README.md",
  "../projects/language/ielts-academic/notes/listening/.gitkeep",
  "../projects/language/ielts-academic/notes/reading/.gitkeep",
  "../projects/language/ielts-academic/notes/writing/task-2-argument-development.md",
  "../projects/language/ielts-academic/notes/speaking/.gitkeep",
  "../projects/language/ielts-academic/notes/vocabulary/.gitkeep",
  "../projects/language/ielts-academic/notes/grammar/.gitkeep",
  "../projects/language/ielts-academic/journal/README.md",
  "../projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md",
```

Add these reads after `const manifest = ...`:

```js
const notesReadme = read("../projects/language/ielts-academic/notes/README.md");
const journalReadme = read("../projects/language/ielts-academic/journal/README.md");
```

Add these assertions before the final pathname assertions:

```js
assert.match(notesReadme, /related_errors/, "notes README should document related_errors");
assert.match(journalReadme, /related_notes/, "journal README should document related_notes");
```

- [ ] **Step 2: Run the source content test and confirm failure**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL with a missing file assertion for `../projects/language/ielts-academic/diagnostics/score-profile.json`.

- [ ] **Step 3: Create `score-profile.json`**

Create `projects/language/ielts-academic/diagnostics/score-profile.json`:

```json
{
  "schemaVersion": 1,
  "state": "template",
  "lastUpdated": "2026-07-06",
  "runMode": "not-yet-run",
  "target": {
    "overall": 8,
    "perSkillFloor": 7.5,
    "timelineWeeks": 8
  },
  "currentEstimate": {
    "overall": null,
    "confidence": "low",
    "summary": "Initial template state. Replace after Week 1 diagnostic evidence is collected."
  },
  "skills": [
    {
      "id": "listening",
      "label": "Listening",
      "estimatedBand": null,
      "confidence": "low",
      "evidenceBasis": ["No timed Listening diagnostic has been recorded in this JSON file yet."],
      "unverifiedDimensions": ["spelling", "synonym recognition", "section 4 academic comprehension", "speed tracking"],
      "riskLevel": "unknown"
    },
    {
      "id": "reading",
      "label": "Reading",
      "estimatedBand": null,
      "confidence": "low",
      "evidenceBasis": ["No timed Reading diagnostic has been recorded in this JSON file yet."],
      "unverifiedDimensions": ["TFNG", "matching headings", "multiple choice", "time allocation"],
      "riskLevel": "unknown"
    },
    {
      "id": "writing",
      "label": "Writing",
      "estimatedBand": null,
      "confidence": "low",
      "evidenceBasis": ["No scored Task 1 or Task 2 sample has been recorded in this JSON file yet."],
      "unverifiedDimensions": ["Task 1 overview", "Task 2 argument development", "grammar accuracy", "lexical control"],
      "riskLevel": "unknown"
    },
    {
      "id": "speaking",
      "label": "Speaking",
      "estimatedBand": null,
      "confidence": "low",
      "evidenceBasis": ["No recorded Speaking diagnostic has been recorded in this JSON file yet."],
      "unverifiedDimensions": ["pronunciation", "real-time fluency", "Part 2 expansion", "Part 3 abstraction"],
      "riskLevel": "unknown"
    }
  ],
  "risks": [
    "Overall 8.0 is not a realistic operating target until Week 1 diagnostic evidence exists.",
    "Speaking pronunciation and real-time fluency remain unverified without audio evidence."
  ]
}
```

- [ ] **Step 4: Create `score-history.json`**

Create `projects/language/ielts-academic/diagnostics/score-history.json`:

```json
{
  "schemaVersion": 1,
  "entries": [
    {
      "date": "2026-07-06",
      "week": 0,
      "state": "template",
      "runMode": "not-yet-run",
      "skills": {
        "listening": null,
        "reading": null,
        "writing": null,
        "speaking": null
      },
      "notes": "Starter entry only. Replace with Week 1 diagnostic results before using this history for allocation decisions."
    }
  ]
}
```

- [ ] **Step 5: Create `error-log.json`**

Create `projects/language/ielts-academic/diagnostics/error-log.json`:

```json
{
  "schemaVersion": 1,
  "errors": [
    {
      "id": "E001",
      "skill": "writing",
      "impact": "high",
      "status": "active",
      "description": "Task 2 argument development needs evidence from a real diagnostic essay before it can be scored.",
      "evidence": ["Starter error used to demonstrate cross-reference behavior."],
      "nextReview": "Week 1 diagnostic review",
      "reviewMethod": "Write one timed Task 2 essay, score against descriptor categories, and update this entry with real evidence."
    },
    {
      "id": "E002",
      "skill": "speaking",
      "impact": "high",
      "status": "active",
      "description": "Speaking pronunciation and real-time fluency are unverified without audio.",
      "evidence": ["Starter error used to keep audio evidence visible in the dashboard."],
      "nextReview": "First recorded Part 2 and Part 3 sample",
      "reviewMethod": "Record answers, complete speaking-audio-self-assessment.md, then update the Speaking score confidence."
    }
  ]
}
```

- [ ] **Step 6: Create `checkpoint-status.json`**

Create `projects/language/ielts-academic/plans/checkpoint-status.json`:

```json
{
  "schemaVersion": 1,
  "checkpoints": [
    {
      "week": 2,
      "name": "Week 2 Data Quality Check",
      "purpose": "Confirm the Week 1 diagnostic produced enough evidence before committing Weeks 3-4 allocation.",
      "status": "not-started",
      "decision": "Pending diagnostic evidence.",
      "evidenceRequired": ["At least one scored sample per available skill", "Confidence label for each skill", "Initial error log entries"]
    },
    {
      "week": 4,
      "name": "Week 4 Target Feasibility Check",
      "purpose": "Decide whether the 8-week operating target remains Overall 8.0 / each skill 7.5+.",
      "status": "not-started",
      "decision": "Pending Week 4 score profile.",
      "evidenceRequired": ["Updated score profile", "Writing Task 1 and Task 2 evidence", "Speaking audio self-assessment if available"]
    },
    {
      "week": 6,
      "name": "Week 6 Trajectory And Allocation Check",
      "purpose": "Compare Week 4 and Week 6 progress and reallocate time toward stalled skills.",
      "status": "not-started",
      "decision": "Pending Week 6 trajectory evidence.",
      "evidenceRequired": ["Score history comparison", "Regression check results", "Actual weekly study hours"]
    },
    {
      "week": 8,
      "name": "Week 8 Final Lock-in",
      "purpose": "Finalize exam readiness, risk flags, and per-skill exam-day tactics.",
      "status": "not-started",
      "decision": "Pending final mock-test evidence.",
      "evidenceRequired": ["Final mock results", "Risk-flagged skills", "Exam-day time management plan"]
    }
  ]
}
```

- [ ] **Step 7: Create notes README and starter note**

Create `projects/language/ielts-academic/notes/README.md`:

````markdown
# IELTS Notes

These notes capture personal IELTS learning insights by skill. They are not the Orchestrator's planning input; structured files such as `diagnostics/score-profile.json`, `diagnostics/error-log.json`, and `plans/checkpoint-status.json` remain the decision inputs.

## Categories

- `listening/`
- `reading/`
- `writing/`
- `speaking/`
- `vocabulary/`
- `grammar/`

## Frontmatter Contract

```yaml
---
id: writing/task-2-argument-development
skill: writing
topic: task-2-argument-development
date: 2026-07-06
related_errors: [E001]
---
```

`related_errors` must point to IDs in `diagnostics/error-log.json`.
````

Create `.gitkeep` files with `apply_patch`:

```diff
*** Begin Patch
*** Add File: projects/language/ielts-academic/notes/listening/.gitkeep
+tracked directory marker
*** Add File: projects/language/ielts-academic/notes/reading/.gitkeep
+tracked directory marker
*** Add File: projects/language/ielts-academic/notes/speaking/.gitkeep
+tracked directory marker
*** Add File: projects/language/ielts-academic/notes/vocabulary/.gitkeep
+tracked directory marker
*** Add File: projects/language/ielts-academic/notes/grammar/.gitkeep
+tracked directory marker
*** End Patch
```

Create `projects/language/ielts-academic/notes/writing/task-2-argument-development.md`:

```markdown
---
id: writing/task-2-argument-development
skill: writing
topic: task-2-argument-development
date: 2026-07-06
related_errors: [E001]
---

# Task 2 Argument Development

This starter note records what should be checked after the first diagnostic Task 2 essay.

The key question is not whether the essay uses advanced vocabulary. The first check is whether each body paragraph makes one claim, explains the claim, and supports it with a relevant example.

Update this note after the first scored Task 2 sample.
```

- [ ] **Step 8: Create journal README and starter entry**

Create `projects/language/ielts-academic/journal/README.md`:

````markdown
# IELTS Journal

The journal is for dated reflection: workload, confidence, friction, breakthroughs, and exam-readiness concerns. It is separate from `plans/weekly-review-template.md`.

Journal entries do not feed Orchestrator planning decisions unless the same information is copied into the structured review files.

## Frontmatter Contract

```yaml
---
date: 2026-07-06
related_errors: [E001]
related_notes: [writing/task-2-argument-development]
---
```

`related_errors` must point to IDs in `diagnostics/error-log.json`. `related_notes` must point to note IDs under `notes/`.
````

Create `projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md`:

```markdown
---
date: 2026-07-06
related_errors: [E001, E002]
related_notes: [writing/task-2-argument-development]
---

# Initial Setup

The IELTS Academic project is being expanded from a prompt-and-plan package into a full learning repository.

This entry is starter content for validating the journal index and cross-reference flow. Replace or extend it after the first real study session.
```

- [ ] **Step 9: Run the structural test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: PASS.

- [ ] **Step 10: Commit structured source content**

Run:

```bash
git add tests/ielts-academic-language-project-requirements.mjs projects/language/ielts-academic/diagnostics/score-profile.json projects/language/ielts-academic/diagnostics/score-history.json projects/language/ielts-academic/diagnostics/error-log.json projects/language/ielts-academic/plans/checkpoint-status.json projects/language/ielts-academic/notes projects/language/ielts-academic/journal
git commit -m "docs: add IELTS v2 source data and learning logs"
```

---

### Task 3: Site Data Build Script And Data Contract Test

**Files:**
- Create: `tests/ielts-academic-site-data-requirements.mjs`
- Modify: `projects/language/ielts-academic/scripts/build-ielts-data.mjs`
- Modify generated: `projects/language/ielts-academic/site/ielts-data.json`

- [ ] **Step 1: Add the site data requirements test**

Create `tests/ielts-academic-site-data-requirements.mjs`:

```js
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const buildScriptUrl = new URL("../projects/language/ielts-academic/scripts/build-ielts-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/language/ielts-academic/site/ielts-data.json", import.meta.url);
const jsUrl = new URL("../projects/language/ielts-academic/site/ielts-reader.js", import.meta.url);

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const data = JSON.parse(readFileSync(dataUrl, "utf8"));
const js = readFileSync(jsUrl, "utf8");

assert.equal(data.project.id, "ielts-academic", "site data should identify the IELTS project");
assert.equal(data.project.target.overall, 8, "site data should keep the Overall 8.0 target");
assert.equal(data.project.target.perSkillFloor, 7.5, "site data should keep the per-skill 7.5 target");

assert.ok(data.scoreProfile, "site data should include scoreProfile");
assert.ok(Array.isArray(data.scoreProfile.skills), "scoreProfile should include skills");
assert.ok(data.scoreHistory, "site data should include scoreHistory");
assert.ok(Array.isArray(data.scoreHistory.entries), "scoreHistory should include entries");
assert.ok(data.errorLog, "site data should include errorLog");
assert.ok(Array.isArray(data.errorLog.errors), "errorLog should include errors");
assert.ok(data.checkpoints, "site data should include checkpoints");
assert.ok(Array.isArray(data.checkpoints.checkpoints), "checkpoints should include checkpoint array");
assert.deepEqual(
  data.checkpoints.checkpoints.map((checkpoint) => checkpoint.week),
  [2, 4, 6, 8],
  "checkpoint data should include Weeks 2, 4, 6, and 8",
);

assert.ok(Array.isArray(data.notes), "site data should include notes");
assert.ok(data.notes.some((note) => note.id === "writing/task-2-argument-development"), "starter writing note should be indexed");
assert.ok(Array.isArray(data.journal), "site data should include journal entries");
assert.ok(data.journal.some((entry) => entry.path.endsWith("2026-07-06-initial-setup.md")), "starter journal entry should be indexed");
assert.ok(Array.isArray(data.promptLibrary), "site data should include promptLibrary");
assert.ok(data.promptLibrary.some((item) => item.id === "orchestrator"), "prompt library should include orchestrator");
assert.ok(data.promptLibrary.some((item) => item.id === "agents/writing-task-2-examiner"), "prompt library should include Writing Task 2 examiner");
assert.ok(Array.isArray(data.validation), "site data should include validation docs");
assert.ok(data.validation.some((item) => item.id === "dry-run-test-cases"), "validation should include dry-run test cases");

const allowedStatuses = new Set(["active", "improving", "fixed", "regressed"]);
const allowedImpacts = new Set(["high", "medium", "low"]);
for (const error of data.errorLog.errors) {
  assert.ok(allowedStatuses.has(error.status), `${error.id} should use an allowed status`);
  assert.ok(allowedImpacts.has(error.impact), `${error.id} should use an allowed impact`);
}

const errorIds = new Set(data.errorLog.errors.map((error) => error.id));
const noteIds = new Set(data.notes.map((note) => note.id));
for (const note of data.notes) {
  for (const errorId of note.relatedErrors) {
    assert.ok(errorIds.has(errorId), `${note.id} should reference an existing error ${errorId}`);
  }
}
for (const entry of data.journal) {
  for (const errorId of entry.relatedErrors) {
    assert.ok(errorIds.has(errorId), `${entry.path} should reference an existing error ${errorId}`);
  }
  for (const noteId of entry.relatedNotes) {
    assert.ok(noteIds.has(noteId), `${entry.path} should reference an existing note ${noteId}`);
  }
}

assert.deepEqual(data.build.referenceIssues, [], "build should report no reference issues");
assert.doesNotMatch(js, /githubToken|Authorization|contents\/|repos\/|fetch\(\"\/api/i, "reader JS should not contain backend or GitHub write-back signals");
```

- [ ] **Step 2: Run the new test and confirm failure**

Run:

```bash
node tests/ielts-academic-site-data-requirements.mjs
```

Expected: FAIL because the current build script does not yet index notes, journal, prompts, validation, or cross-reference data.

- [ ] **Step 3: Replace the build script with the full standard-library implementation**

Replace `projects/language/ielts-academic/scripts/build-ielts-data.mjs` with:

```js
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const siteDir = path.join(projectRoot, "site");
const outputPath = path.join(siteDir, "ielts-data.json");

const markdownTitle = (body, fallback) => {
  const match = body.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallback;
};

const slugFromFile = (filePath, baseDir) =>
  path.relative(baseDir, filePath).replace(/\\/g, "/").replace(/\.md$/, "");

const readJson = (relativePath) => {
  const filePath = path.join(projectRoot, relativePath);
  return JSON.parse(readFileSync(filePath, "utf8"));
};

function parseScalar(value) {
  const trimmed = value.trim();
  if (trimmed === "[]") return [];
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    const inner = trimmed.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((item) => item.trim().replace(/^["']|["']$/g, ""));
  }
  return trimmed.replace(/^["']|["']$/g, "");
}

function parseFrontmatter(markdown) {
  if (!markdown.startsWith("---\n")) {
    return { data: {}, body: markdown };
  }
  const end = markdown.indexOf("\n---", 4);
  if (end === -1) {
    return { data: {}, body: markdown };
  }
  const raw = markdown.slice(4, end).trim();
  const body = markdown.slice(end + 4).replace(/^\n/, "");
  const data = {};
  for (const line of raw.split("\n")) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (match) {
      data[match[1]] = parseScalar(match[2]);
    }
  }
  return { data, body };
}

function walkMarkdown(dir) {
  if (!existsSync(dir)) return [];
  const entries = readdirSync(dir).sort();
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...walkMarkdown(fullPath));
    } else if (entry.endsWith(".md")) {
      files.push(fullPath);
    }
  }
  return files;
}

function readMarkdownItem(filePath, baseDir) {
  const markdown = readFileSync(filePath, "utf8");
  const { data, body } = parseFrontmatter(markdown);
  const id = data.id || slugFromFile(filePath, baseDir);
  return {
    id,
    path: slugFromFile(filePath, projectRoot) + ".md",
    title: markdownTitle(body, id),
    body,
    frontmatter: data,
  };
}

function readNotes() {
  const notesDir = path.join(projectRoot, "notes");
  return walkMarkdown(notesDir)
    .filter((filePath) => path.basename(filePath) !== "README.md")
    .map((filePath) => {
      const item = readMarkdownItem(filePath, notesDir);
      return {
        ...item,
        skill: item.frontmatter.skill || "general",
        topic: item.frontmatter.topic || item.id,
        date: item.frontmatter.date || "",
        relatedErrors: item.frontmatter.related_errors || [],
      };
    });
}

function readJournal() {
  const journalDir = path.join(projectRoot, "journal", "entries");
  return walkMarkdown(journalDir).map((filePath) => {
    const item = readMarkdownItem(filePath, journalDir);
    return {
      ...item,
      date: item.frontmatter.date || "",
      relatedErrors: item.frontmatter.related_errors || [],
      relatedNotes: item.frontmatter.related_notes || [],
    };
  }).sort((a, b) => b.date.localeCompare(a.date));
}

function readPromptLibrary() {
  const promptFiles = [
    ["orchestrator", "Orchestrator", "prompts/orchestrator.md"],
    ["run-modes", "Run Modes", "prompts/run-modes.md"],
    ["interaction-protocol", "Interaction Protocol", "prompts/interaction-protocol.md"],
    ["output-contract", "Output Contract", "prompts/output-contract.md"],
    ["calibration-and-validation", "Calibration And Validation", "prompts/calibration-and-validation.md"],
    ["agents/listening-specialist", "Listening Specialist", "prompts/agents/listening-specialist.md"],
    ["agents/reading-specialist", "Reading Specialist", "prompts/agents/reading-specialist.md"],
    ["agents/writing-task-1-examiner", "Writing Task 1 Examiner", "prompts/agents/writing-task-1-examiner.md"],
    ["agents/writing-task-2-examiner", "Writing Task 2 Examiner", "prompts/agents/writing-task-2-examiner.md"],
    ["agents/speaking-examiner", "Speaking Examiner", "prompts/agents/speaking-examiner.md"],
    ["agents/language-error-analyst", "Language Error Analyst", "prompts/agents/language-error-analyst.md"],
    ["agents/diagnostic-score-profile-analyst", "Diagnostic Score Profile Analyst", "prompts/agents/diagnostic-score-profile-analyst.md"],
    ["agents/study-load-execution-planner", "Study Load Execution Planner", "prompts/agents/study-load-execution-planner.md"],
  ];
  return promptFiles.map(([id, title, relativePath]) => ({
    id,
    title,
    path: relativePath,
    body: readFileSync(path.join(projectRoot, relativePath), "utf8"),
  }));
}

function readValidationDocs() {
  const validationFiles = [
    ["output-contract-checklist", "Output Contract Checklist", "validation/output-contract-checklist.md"],
    ["dry-run-test-cases", "Dry-run Test Cases", "validation/dry-run-test-cases.md"],
    ["examiner-calibration-checklist", "Examiner Calibration Checklist", "validation/examiner-calibration-checklist.md"],
  ];
  return validationFiles.map(([id, title, relativePath]) => ({
    id,
    title,
    path: relativePath,
    body: readFileSync(path.join(projectRoot, relativePath), "utf8"),
  }));
}

function validateReferences({ errorLog, notes, journal }) {
  const issues = [];
  const errorIds = new Set(errorLog.errors.map((error) => error.id));
  const noteIds = new Set(notes.map((note) => note.id));
  for (const note of notes) {
    for (const errorId of note.relatedErrors) {
      if (!errorIds.has(errorId)) issues.push(`${note.id} references missing error ${errorId}`);
    }
  }
  for (const entry of journal) {
    for (const errorId of entry.relatedErrors) {
      if (!errorIds.has(errorId)) issues.push(`${entry.path} references missing error ${errorId}`);
    }
    for (const noteId of entry.relatedNotes) {
      if (!noteIds.has(noteId)) issues.push(`${entry.path} references missing note ${noteId}`);
    }
  }
  return issues;
}

function validateAllowlists(errorLog) {
  const issues = [];
  const statuses = new Set(["active", "improving", "fixed", "regressed"]);
  const impacts = new Set(["high", "medium", "low"]);
  for (const error of errorLog.errors) {
    if (!statuses.has(error.status)) issues.push(`${error.id} has invalid status ${error.status}`);
    if (!impacts.has(error.impact)) issues.push(`${error.id} has invalid impact ${error.impact}`);
  }
  return issues;
}

const scoreProfile = readJson("diagnostics/score-profile.json");
const scoreHistory = readJson("diagnostics/score-history.json");
const errorLog = readJson("diagnostics/error-log.json");
const checkpoints = readJson("plans/checkpoint-status.json");
const notes = readNotes();
const journal = readJournal();
const promptLibrary = readPromptLibrary();
const validation = readValidationDocs();
const referenceIssues = [
  ...validateAllowlists(errorLog),
  ...validateReferences({ errorLog, notes, journal }),
];

const siteData = {
  project: {
    id: "ielts-academic",
    title: "IELTS Academic",
    target: scoreProfile.target,
  },
  build: {
    generatedAt: new Date().toISOString(),
    referenceIssues,
  },
  scoreProfile,
  scoreHistory,
  errorLog,
  checkpoints,
  notes,
  journal,
  promptLibrary,
  validation,
};

mkdirSync(siteDir, { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(siteData, null, 2)}\n`);

if (referenceIssues.length > 0) {
  console.error(referenceIssues.join("\n"));
  process.exitCode = 1;
}
```

- [ ] **Step 4: Run the build script and the data test**

Run:

```bash
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
node tests/ielts-academic-site-data-requirements.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit the build script and data test**

Run:

```bash
git add tests/ielts-academic-site-data-requirements.mjs projects/language/ielts-academic/scripts/build-ielts-data.mjs projects/language/ielts-academic/site/ielts-data.json
git commit -m "test: add IELTS site data build contract"
```

---

### Task 4: Static IELTS Reader Rendering

**Files:**
- Modify: `projects/language/ielts-academic/index.html`
- Modify: `projects/language/ielts-academic/site/ielts-reader.css`
- Modify: `projects/language/ielts-academic/site/ielts-reader.js`
- Modify: `tests/ielts-academic-language-project-requirements.mjs`

- [ ] **Step 1: Add reader behavior assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, add these assertions near the existing `siteJs` assertions:

```js
assert.match(siteJs, /function renderSkillGapBars/, "IELTS JS should render skill gap bars");
assert.match(siteJs, /function renderCheckpointMarker/, "IELTS JS should render checkpoint markers");
assert.match(siteJs, /function filterErrors/, "IELTS JS should filter errors");
assert.match(siteJs, /function runReaderSearch/, "IELTS JS should support reader search");
assert.match(siteJs, /function renderReferenceChips/, "IELTS JS should render cross-reference chips");
assert.match(siteJs, /localStorage\.setItem\("ieltsReader\.ui\.v1"/, "IELTS JS may persist only non-critical UI state");
assert.doesNotMatch(siteJs, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint/i, "IELTS JS should not store score, error, or checkpoint source data in localStorage");

assert.match(siteCss, /\.skill-gap/, "IELTS CSS should style skill gap bars");
assert.match(siteCss, /\.checkpoint-marker/, "IELTS CSS should style checkpoint markers");
assert.match(siteCss, /\.reference-chip/, "IELTS CSS should style reference chips");
assert.match(siteCss, /\.reader-search/, "IELTS CSS should style reader search");
assert.doesNotMatch(siteCss, /border-radius:\s*24px|border-radius:\s*28px/, "IELTS reader should avoid oversized card radii");
```

- [ ] **Step 2: Run the reader requirements test and confirm failure**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL because `renderSkillGapBars`, `runReaderSearch`, reference chip rendering, and full CSS classes do not exist yet.

- [ ] **Step 3: Expand `index.html` into the final reader shell**

Keep the same file path and replace the body with this structure:

```html
<body data-page="ielts-academic-reader">
  <div class="ielts-shell">
    <aside class="reader-sidebar" aria-label="IELTS project sections">
      <a class="project-backlink" href="../README.md">Language</a>
      <h1>IELTS Academic</h1>
      <p>Overall 8.0 / each skill 7.5+</p>
      <label class="reader-search">
        <span>Search</span>
        <input id="reader-search" type="search" autocomplete="off" />
      </label>
      <nav>
        <button type="button" data-section-target="dashboard">Dashboard</button>
        <button type="button" data-section-target="swimlane">8-Week Plan</button>
        <button type="button" data-section-target="errors">Errors</button>
        <button type="button" data-section-target="notes">Notes</button>
        <button type="button" data-section-target="journal">Journal</button>
        <button type="button" data-section-target="prompt-library">Prompt Library</button>
        <button type="button" data-section-target="validation">Validation</button>
      </nav>
    </aside>
    <main class="reader-main">
      <section id="dashboard" class="reader-section" aria-labelledby="dashboard-title"></section>
      <section id="swimlane" class="reader-section" aria-labelledby="swimlane-title"></section>
      <section id="errors" class="reader-section" aria-labelledby="errors-title"></section>
      <section id="notes" class="reader-section" aria-labelledby="notes-title"></section>
      <section id="journal" class="reader-section" aria-labelledby="journal-title"></section>
      <section id="prompt-library" class="reader-section" aria-labelledby="prompt-library-title"></section>
      <section id="validation" class="reader-section" aria-labelledby="validation-title"></section>
    </main>
  </div>
  <script src="site/ielts-reader.js" defer></script>
</body>
```

- [ ] **Step 4: Expand the reader CSS**

In `projects/language/ielts-academic/site/ielts-reader.css`, keep the Task 1 base and add styles for these selectors:

```css
.section-title {
  margin: 0 0 10px;
  font-size: clamp(24px, 3vw, 38px);
  letter-spacing: 0;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 12px;
}

.metric-card,
.content-card,
.error-card,
.note-card,
.journal-card {
  border: 1px solid var(--ielts-line);
  border-radius: 8px;
  background: var(--ielts-panel);
  padding: 14px;
}

.skill-gap {
  display: grid;
  gap: 6px;
}

.skill-gap-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(32, 37, 34, 0.12);
}

.skill-gap-fill {
  height: 100%;
  background: var(--ielts-accent);
}

.checkpoint-marker {
  border-left: 3px solid var(--ielts-accent);
  padding-left: 8px;
}

.swimlane-cell {
  min-height: 88px;
  padding: 10px;
  background: var(--ielts-panel);
}

.error-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
}

.error-column {
  min-width: 0;
}

.reference-chip {
  display: inline-flex;
  align-items: center;
  margin: 0 6px 6px 0;
  padding: 4px 8px;
  border: 1px solid var(--ielts-line);
  border-radius: 999px;
  color: var(--ielts-muted);
  background: rgba(47, 111, 104, 0.08);
}

.reader-search {
  display: grid;
  gap: 6px;
  margin: 18px 0;
}

.reader-search input,
.error-controls select {
  width: 100%;
  border: 1px solid var(--ielts-line);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--ielts-panel);
  color: inherit;
  font: inherit;
}

.is-hidden {
  display: none;
}
```

- [ ] **Step 5: Replace `ielts-reader.js` with section rendering logic**

Replace `projects/language/ielts-academic/site/ielts-reader.js` with a focused implementation containing these functions:

```js
const UI_STORAGE_KEY = "ieltsReader.ui.v1";
let state = { data: null, searchTerm: "", errorSkill: "all", errorImpact: "all" };

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}: ${response.status}`);
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[char]);
}

function setHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html;
}

function renderReferenceChips(values, prefix) {
  return values.map((value) => `<span class="reference-chip">${escapeHtml(prefix)} ${escapeHtml(value)}</span>`).join("");
}

function renderSkillGapBars(skills, floor) {
  return skills.map((skill) => {
    const band = typeof skill.estimatedBand === "number" ? skill.estimatedBand : 0;
    const percent = Math.max(0, Math.min(100, (band / floor) * 100));
    const gap = typeof skill.estimatedBand === "number" ? Math.max(0, floor - skill.estimatedBand).toFixed(1) : "unverified";
    return `<article class="metric-card skill-gap">
      <h3>${escapeHtml(skill.label)}</h3>
      <div class="skill-gap-bar"><div class="skill-gap-fill" style="width: ${percent}%"></div></div>
      <p>Gap: ${escapeHtml(gap)}</p>
      <p>${escapeHtml(skill.confidence)} confidence</p>
    </article>`;
  }).join("");
}

function renderDashboard(data) {
  setHtml("dashboard", `<h2 id="dashboard-title" class="section-title">Dashboard</h2>
    <div class="metric-grid">
      <article class="metric-card"><h3>Target</h3><p>Overall ${data.project.target.overall}, each skill ${data.project.target.perSkillFloor}+</p></article>
      <article class="metric-card"><h3>Run Mode</h3><p>${escapeHtml(data.scoreProfile.runMode)}</p></article>
      <article class="metric-card"><h3>State</h3><p>${escapeHtml(data.scoreProfile.state)}</p></article>
      <article class="metric-card"><h3>Reference Issues</h3><p>${data.build.referenceIssues.length}</p></article>
    </div>
    <div class="metric-grid">${renderSkillGapBars(data.scoreProfile.skills, data.project.target.perSkillFloor)}</div>`);
}

function renderCheckpointMarker(checkpoint) {
  return `<div class="checkpoint-marker">
    <strong>${escapeHtml(checkpoint.name)}</strong>
    <p>${escapeHtml(checkpoint.purpose)}</p>
    <p>${escapeHtml(checkpoint.decision)}</p>
  </div>`;
}

function renderSwimlane(data) {
  const weeks = Array.from({ length: 8 }, (_, index) => index + 1);
  const rows = ["Listening", "Reading", "Writing", "Speaking", "Errors"];
  const checkpoints = new Map(data.checkpoints.checkpoints.map((checkpoint) => [checkpoint.week, checkpoint]));
  const cells = [`<div class="swimlane-cell"><strong>Skill</strong></div>`, ...weeks.map((week) => `<div class="swimlane-cell"><strong>Week ${week}</strong></div>`)];
  for (const row of rows) {
    cells.push(`<div class="swimlane-cell"><strong>${row}</strong></div>`);
    for (const week of weeks) {
      cells.push(`<div class="swimlane-cell">${checkpoints.has(week) ? renderCheckpointMarker(checkpoints.get(week)) : "Training block"}</div>`);
    }
  }
  setHtml("swimlane", `<h2 id="swimlane-title" class="section-title">8-Week Swimlane</h2><div class="swimlane-grid">${cells.join("")}</div>`);
}

function filterErrors(errors) {
  return errors.filter((error) => {
    const skillOk = state.errorSkill === "all" || error.skill === state.errorSkill;
    const impactOk = state.errorImpact === "all" || error.impact === state.errorImpact;
    const searchOk = !state.searchTerm || `${error.id} ${error.description} ${error.evidence.join(" ")}`.toLowerCase().includes(state.searchTerm);
    return skillOk && impactOk && searchOk;
  });
}

function renderErrors(data) {
  const statuses = ["active", "improving", "fixed", "regressed"];
  const filtered = filterErrors(data.errorLog.errors);
  const columns = statuses.map((status) => `<section class="error-column"><h3>${status}</h3>${filtered.filter((error) => error.status === status).map((error) => `<article class="error-card"><h4>${escapeHtml(error.id)}</h4><p>${escapeHtml(error.description)}</p><p>${escapeHtml(error.impact)} impact · ${escapeHtml(error.skill)}</p><p>${escapeHtml(error.reviewMethod)}</p></article>`).join("")}</section>`).join("");
  setHtml("errors", `<h2 id="errors-title" class="section-title">Errors</h2>
    <div class="error-controls">
      <select id="error-skill"><option value="all">All skills</option><option value="listening">Listening</option><option value="reading">Reading</option><option value="writing">Writing</option><option value="speaking">Speaking</option></select>
      <select id="error-impact"><option value="all">All impacts</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
    </div>
    <div class="error-board">${columns}</div>`);
  document.getElementById("error-skill").value = state.errorSkill;
  document.getElementById("error-impact").value = state.errorImpact;
  document.getElementById("error-skill").addEventListener("change", (event) => {
    state.errorSkill = event.target.value;
    saveUiState();
    renderErrors(state.data);
  });
  document.getElementById("error-impact").addEventListener("change", (event) => {
    state.errorImpact = event.target.value;
    saveUiState();
    renderErrors(state.data);
  });
}

function renderNotes(data) {
  const notes = data.notes.filter((note) => !state.searchTerm || `${note.title} ${note.body}`.toLowerCase().includes(state.searchTerm));
  setHtml("notes", `<h2 id="notes-title" class="section-title">Notes</h2>${notes.map((note) => `<article class="note-card"><h3>${escapeHtml(note.title)}</h3><p>${escapeHtml(note.skill)} · ${escapeHtml(note.topic)}</p>${renderReferenceChips(note.relatedErrors, "Error")}</article>`).join("")}`);
}

function renderJournal(data) {
  const entries = data.journal.filter((entry) => !state.searchTerm || `${entry.title} ${entry.body}`.toLowerCase().includes(state.searchTerm));
  setHtml("journal", `<h2 id="journal-title" class="section-title">Journal</h2>${entries.map((entry) => `<article class="journal-card"><h3>${escapeHtml(entry.title)}</h3><p>${escapeHtml(entry.date)}</p>${renderReferenceChips(entry.relatedErrors, "Error")}${renderReferenceChips(entry.relatedNotes, "Note")}</article>`).join("")}`);
}

function renderPromptLibrary(data) {
  setHtml("prompt-library", `<h2 id="prompt-library-title" class="section-title">Prompt Library</h2>${data.promptLibrary.map((prompt) => `<article class="content-card"><h3>${escapeHtml(prompt.title)}</h3><p>${escapeHtml(prompt.path)}</p></article>`).join("")}`);
}

function renderValidation(data) {
  setHtml("validation", `<h2 id="validation-title" class="section-title">Validation</h2>${data.validation.map((item) => `<article class="content-card"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.path)}</p></article>`).join("")}`);
}

function runReaderSearch(term) {
  state.searchTerm = term.trim().toLowerCase();
  saveUiState();
  renderErrors(state.data);
  renderNotes(state.data);
  renderJournal(state.data);
}

function saveUiState() {
  localStorage.setItem("ieltsReader.ui.v1", JSON.stringify({
    searchTerm: state.searchTerm,
    errorSkill: state.errorSkill,
    errorImpact: state.errorImpact,
  }));
}

function loadUiState() {
  try {
    const saved = JSON.parse(localStorage.getItem(UI_STORAGE_KEY) || "{}");
    state = { ...state, ...saved };
  } catch {
    state = { ...state, searchTerm: "", errorSkill: "all", errorImpact: "all" };
  }
}

function renderAll(data) {
  renderDashboard(data);
  renderSwimlane(data);
  renderErrors(data);
  renderNotes(data);
  renderJournal(data);
  renderPromptLibrary(data);
  renderValidation(data);
}

async function init() {
  loadUiState();
  state.data = await fetchJson("site/ielts-data.json");
  renderAll(state.data);
  const search = document.getElementById("reader-search");
  search.value = state.searchTerm;
  search.addEventListener("input", (event) => runReaderSearch(event.target.value));
  document.querySelectorAll("[data-section-target]").forEach((button) => {
    button.addEventListener("click", () => document.getElementById(button.dataset.sectionTarget)?.scrollIntoView({ behavior: "smooth" }));
  });
}

init().catch((error) => {
  setHtml("dashboard", `<h2 id="dashboard-title" class="section-title">Dashboard</h2><p>${escapeHtml(error.message)}</p>`);
});
```

- [ ] **Step 6: Run reader tests**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
```

Expected: PASS.

- [ ] **Step 7: Commit the static reader**

Run:

```bash
git add tests/ielts-academic-language-project-requirements.mjs projects/language/ielts-academic/index.html projects/language/ielts-academic/site/ielts-reader.css projects/language/ielts-academic/site/ielts-reader.js
git commit -m "feat: add IELTS Academic static reader"
```

---

### Task 5: README Workflow Integration And Final Verification

**Files:**
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
- Modify: `projects/language/README.md`
- Modify: `projects/language/ielts-academic/README.md`
- Modify generated: `projects/language/ielts-academic/site/ielts-data.json`

- [ ] **Step 1: Add README workflow assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, add these assertions near the existing README assertions:

```js
assert.match(projectReadme, /static reader|GitHub Pages|site\/ielts-data\.json/i, "project README should describe the v2 static reader workflow");
assert.match(projectReadme, /notes\/|journal\//, "project README should link to notes and journal");
assert.match(languageReadme, /ielts-academic\/index\.html/, "language README should link to the IELTS static reader");
```

- [ ] **Step 2: Run the README workflow test and confirm failure**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL because the READMEs do not yet describe `static reader`, `site/ielts-data.json`, `notes/`, `journal/`, and `ielts-academic/index.html`.

- [ ] **Step 3: Update `projects/language/README.md`**

Replace the IELTS project bullet with:

```markdown
- [IELTS Academic](ielts-academic/) - a diagnostic-driven IELTS Academic project built around reusable multi-agent prompts, adaptive 8-week planning, error regression checks, notes, journal entries, and a [static reader](ielts-academic/index.html).
```

Add this section before `## Boundary`:

````markdown
## Workflow

For the IELTS Academic project, edit the Markdown and JSON source files in `ielts-academic/`, then run:

```bash
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
```

The generated `ielts-academic/site/ielts-data.json` powers the static reader. The browser is read-only; do not store score, error, checkpoint, notes, or journal source data only in local browser state.
````

- [ ] **Step 4: Update `projects/language/ielts-academic/README.md`**

Add this section after the opening two-layer description:

```markdown
## Static Reader

Open `index.html` to browse the v2 project reader. It renders:

- Dashboard
- 8-week swimlane
- Errors board
- Notes
- Journal
- Prompt library
- Validation status

The reader uses `site/ielts-data.json`, generated from the repository source files. It does not write back to GitHub, local files, or any backend.
```

Replace the Recommended Flow list with:

```markdown
1. Start with `diagnostics/diagnostic-input-template.md`.
2. Choose a run mode in `prompts/run-modes.md`.
3. Use `prompts/orchestrator.md` to coordinate subagent outputs.
4. Fill the human templates and update the structured counterparts: `diagnostics/score-profile.json`, `diagnostics/score-history.json`, `diagnostics/error-log.json`, and `plans/checkpoint-status.json`.
5. Follow `plans/8-week-diagnostic-driven-plan.md`, adjusting weekly allocation through `plans/checkpoint-rules.md`.
6. Track recurring issues in `diagnostics/error-log-template.md`, `diagnostics/error-log.json`, and `errors/regression-check-template.md`.
7. Record durable learning insights in `notes/` and freeform dated reflection in `journal/`.
8. Run `node projects/language/ielts-academic/scripts/build-ielts-data.mjs` before reviewing the static reader or committing weekly updates.
```

Add these bullets to `## Key Files`:

```markdown
- `diagnostics/score-profile.json`
- `diagnostics/score-history.json`
- `diagnostics/error-log.json`
- `plans/checkpoint-status.json`
- `notes/README.md`
- `journal/README.md`
- `scripts/build-ielts-data.mjs`
- `site/ielts-data.json`
- `index.html`
```

- [ ] **Step 5: Regenerate site data**

Run:

```bash
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
```

Expected: PASS with no stderr output and an updated `projects/language/ielts-academic/site/ielts-data.json`.

- [ ] **Step 6: Run full narrow verification**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
node tests/projects-requirements.mjs
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 7: Inspect git status**

Run:

```bash
git status --short
```

Expected: only files from this v2 implementation are modified or created.

- [ ] **Step 8: Commit README integration and generated data**

Run:

```bash
git add tests/ielts-academic-language-project-requirements.mjs projects/language/README.md projects/language/ielts-academic/README.md projects/language/ielts-academic/site/ielts-data.json
git commit -m "docs: document IELTS v2 reader workflow"
```

---

## Final Completion Checklist

- [ ] `node tests/ielts-academic-language-project-requirements.mjs` passes.
- [ ] `node tests/ielts-academic-site-data-requirements.mjs` passes.
- [ ] `node projects/language/ielts-academic/scripts/build-ielts-data.mjs` passes.
- [ ] `node tests/projects-requirements.mjs` passes.
- [ ] `git diff --check` passes.
- [ ] `projects/language/ielts-academic/index.html` contains no write-back path.
- [ ] `projects/language/ielts-academic/site/ielts-data.json` is generated from repository source files.
- [ ] `projects/manifest.json` includes `ielts-academic`.
- [ ] No score, error, checkpoint, note, or journal source data is stored only in browser state.

## Execution Notes

- If using subagents, create a fresh worker per task and review the diff before starting the next task.
- If executing inline, use a feature worktree before editing because `main` is currently ahead of `origin/main` with the spec commit.
- Keep commits task-sized. Do not merge or push until the final completion checklist passes.
