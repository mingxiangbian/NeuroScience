# IELTS Reader Foundations Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 IELTS 项目书签改为中文“语言”，并把 IELTS static reader 改造成与 Foundations reader 基本一致的视觉和交互体验。

**Architecture:** `projects/language/ielts-academic/` 继续作为 source of truth；`site/ielts-data.json` 仍由 build script 生成。Reader 前端改为 Foundations-style shell，并在客户端把 IELTS 数据适配成 Dashboard、Swimlane、Errors、Notes、Journal、Prompt Library、Validation 七个 reader modules。浏览器只允许保存 UI、annotations 和 task state 到 IELTS 专属 `localStorage` keys，不写回 repo。

**Tech Stack:** Plain HTML/CSS/JavaScript, Node.js standard-library tests, GitHub Pages static files, localStorage.

---

## File Map

- Modify: `projects/manifest.json`
  将 IELTS bookmark title 从 `IELTS Academic` 改成 `语言`。
- Modify: `projects/index.html`
  保持中文书签默认字体路径；移除或调整 IELTS Latin title 特判，确保 `语言` 使用中文 calligraphy bookmark style。
- Modify: `projects/language/ielts-academic/index.html`
  将现有 sidebar/dashboard shell 改成 Foundations-style reader shell。
- Modify: `projects/language/ielts-academic/site/ielts-reader.css`
  用 Foundations-style reader tokens、layout、toolbar、directory、main content、note panel、dark theme、mobile drawer 样式替换当前 SaaS dashboard 风格。
- Modify: `projects/language/ielts-academic/site/ielts-reader.js`
  把现有 IELTS rendering 适配到 module reader；迁移 theme、collapse、search、annotation、task state 交互。
- Modify: `tests/projects-requirements.mjs`
  更新 bookmark title/font subset 断言。
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
  更新 reader shell、CSS、JS、localStorage 和 no-write-back contract 断言。
- Modify: `tests/ielts-academic-site-data-requirements.mjs`
  补充 allowed localStorage key/no source-data localStorage 检查。

---

### Task 1: Bookmark Title Contract

**Files:**
- Modify: `tests/projects-requirements.mjs`
- Modify: `projects/manifest.json`
- Modify: `projects/index.html`

- [ ] **Step 1: Update the failing project bookmark test**

In `tests/projects-requirements.mjs`, replace the manifest title assertion with:

```js
assert.deepEqual(
  manifest.map((project) => project.title),
  ["基石", "语言", "记忆与智能体"],
  "projects bookmarks should include the registered project titles in display order",
);
```

Replace the font subset assertion with:

```js
assert.match(fontSources, /ZhiMangXing-Regular\.ttf --text='记忆与智能体基石语言'/, "bookmark font subset should include the Chinese project bookmark titles");
```

Add this assertion after the manifest folder assertion:

```js
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.title,
  "语言",
  "IELTS Academic should display as the Chinese language bookmark",
);
```

- [ ] **Step 2: Run the bookmark test and verify red**

Run:

```bash
node tests/projects-requirements.mjs
```

Expected: FAIL because manifest still contains `IELTS Academic` and the font subset notes still omit `语言`.

- [ ] **Step 3: Change the manifest title**

In `projects/manifest.json`, change only the IELTS entry title:

```json
{
  "id": "ielts-academic",
  "title": "语言",
  "folder": "language/ielts-academic/",
  "summary": "Diagnostic-driven IELTS Academic preparation with multi-agent prompts, adaptive planning, notes, journal, and validation dashboards.",
  "status": "active"
}
```

- [ ] **Step 4: Ensure project card script detection treats the title as Chinese**

In `projects/index.html`, keep the existing script-detection behavior for Latin titles, but the IELTS card should now receive the default non-Latin path because its manifest title is `语言`.

If the implementation currently has an IELTS-specific override such as:

```js
project.id === "ielts-academic" ? "latin" : ...
```

replace it with content-based detection:

```js
const titleScript = /[A-Za-z]/.test(project.title) ? "latin" : "cjk";
```

Do not remove the Latin CSS path entirely; future English project titles can still use it.

- [ ] **Step 5: Update font subset notes if needed**

If `assets/fonts/README.md` contains the bookmark subset command:

```text
ZhiMangXing-Regular.ttf --text='记忆与智能体基石'
```

change it to:

```text
ZhiMangXing-Regular.ttf --text='记忆与智能体基石语言'
```

Only update this note if the file has the exact subset command. Do not regenerate font files unless current tests require it.

- [ ] **Step 6: Verify green and commit**

Run:

```bash
node tests/projects-requirements.mjs
git diff --check
```

Expected: PASS.

Commit:

```bash
git add tests/projects-requirements.mjs projects/manifest.json projects/index.html assets/fonts/README.md
git commit -m "fix: localize IELTS project bookmark"
```

If `projects/index.html` or `assets/fonts/README.md` did not change, omit them from `git add`.

---

### Task 2: Foundations-Style IELTS Reader Shell Contract

**Files:**
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
- Modify: `projects/language/ielts-academic/index.html`

- [ ] **Step 1: Replace old reader shell assertions with Foundations-style shell assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, keep the existing file existence checks and static data checks, but replace the old HTML region assertions:

```js
assert.match(projectIndex, /id="dashboard"/, "IELTS reader should include a dashboard region");
assert.match(projectIndex, /id="swimlane"/, "IELTS reader should include a swimlane region");
assert.match(projectIndex, /id="errors"/, "IELTS reader should include an errors region");
assert.match(projectIndex, /id="notes"/, "IELTS reader should include a notes region");
assert.match(projectIndex, /id="journal"/, "IELTS reader should include a journal region");
assert.match(projectIndex, /id="prompt-library"/, "IELTS reader should include a prompt library region");
assert.match(projectIndex, /id="validation"/, "IELTS reader should include a validation region");
```

with:

```js
assert.match(projectIndex, /data-page="ielts-academic-reader"/, "IELTS project should expose a dedicated reader page");
assert.match(projectIndex, /data-theme="light"/, "IELTS reader should start with the light reader theme");
assert.match(projectIndex, /id="reader-shell"/, "IELTS reader should use the Foundations-style reader shell");
assert.match(projectIndex, /id="reader-toolbar"/, "IELTS reader should include a top toolbar");
assert.match(projectIndex, /id="global-search"/, "IELTS reader should include global search");
assert.match(projectIndex, /id="module-directory"/, "IELTS reader should include a module directory");
assert.match(projectIndex, /id="section-rail"/, "IELTS reader should include a section rail");
assert.match(projectIndex, /id="module-header"/, "IELTS reader should include a module header");
assert.match(projectIndex, /id="section-list"/, "IELTS reader should include a section list");
assert.match(projectIndex, /id="note-panel"/, "IELTS reader should include a right note panel");
assert.match(projectIndex, /id="mobile-note-drawer"/, "IELTS reader should include a mobile note drawer");
assert.match(projectIndex, /data-source="site\/ielts-data\.json"/, "IELTS reader should load generated site data through a data-source attribute");
```

- [ ] **Step 2: Run the IELTS test and verify red**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL because the current IELTS page still uses `.ielts-shell`, old sidebar regions and no `reader-shell` / toolbar / note panel.

- [ ] **Step 3: Replace the IELTS HTML shell**

Replace `projects/language/ielts-academic/index.html` with a Foundations-style shell adapted for IELTS:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>语言 | IELTS Academic Reader</title>
    <link rel="stylesheet" href="site/ielts-reader.css" />
  </head>
  <body data-page="ielts-academic-reader" data-theme="light">
    <div class="reader-shell" id="reader-shell">
      <div class="search-focus-layer" id="search-overlay" aria-hidden="true"></div>

      <header class="reader-toolbar" id="reader-toolbar">
        <div class="toolbar-left">
          <a class="project-mark" href="../../" aria-label="返回项目">
            <svg class="title-x-mark" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
              <path class="title-x-left-bleed" d="M39 10 C22 19 13 34 13 49 C13 66 23 81 41 88 C32 73 29 59 34 48 C29 38 31 24 39 10 Z" />
              <path class="title-x-left-core" d="M41 13 C26 22 18 35 18 49 C18 63 27 76 41 83 C35 71 33 59 38 48 C33 38 35 25 41 13 Z" />
              <path class="title-x-right-core" d="M55 13 C70 22 78 35 78 49 C78 63 69 76 55 83 C61 71 63 59 58 48 C63 38 61 25 55 13 Z" />
            </svg>
          </a>
          <button class="icon-button mobile-directory-toggle" type="button" aria-label="打开模块目录" data-toggle-left>
            <svg width="21" height="21" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 5h16v14H4V5Z M9 5v14 M12 9h5 M12 13h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>

        <div class="toolbar-right">
          <div class="toolbar-search">
            <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="m21 21-4.2-4.2M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
            </svg>
            <input id="global-search" type="search" autocomplete="off" placeholder="Search" aria-label="全局搜索" />
            <kbd class="search-shortcut">⌘ K</kbd>
          </div>
          <div class="toolbar-controls">
            <button class="icon-button" id="toggle-theme" type="button" aria-label="切换夜间模式" aria-pressed="false">
              <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 15.5A7.5 7.5 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
              </svg>
            </button>
            <button class="icon-button" id="toggle-note" type="button" aria-label="收放平行笔记">
              <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 5H4M20 12H8M20 19H4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
            </button>
          </div>
          <div class="search-results" id="search-results" hidden></div>
        </div>
      </header>

      <aside class="reader-sidebar" id="module-directory" aria-label="IELTS reader modules">
        <div class="directory-surface">
          <div class="directory-header">
            <div>
              <p class="directory-kicker">IELTS Academic</p>
              <p class="directory-title">语言</p>
            </div>
            <button class="icon-button directory-toggle" id="toggle-left" type="button" aria-label="收放模块目录" data-toggle-left>
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
          <nav class="module-nav" id="module-nav" aria-label="IELTS modules"></nav>
        </div>
        <div class="section-rail" id="section-rail" aria-label="章节索引">
          <button class="icon-button rail-toggle" type="button" aria-label="展开模块目录" data-toggle-left>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <div class="section-lines" id="section-lines"></div>
        </div>
      </aside>

      <main class="reader-main" id="reader-main">
        <section class="module-header" id="module-header" aria-label="模块信息"></section>
        <section class="section-list" id="section-list" aria-label="模块正文">
          <article class="status-panel">
            <h2>正在加载 IELTS reader</h2>
            <p>读取 site/ielts-data.json。</p>
          </article>
        </section>
      </main>

      <aside class="note-panel" id="note-panel" aria-label="平行笔记">
        <p class="note-label" id="note-label">Parallel note</p>
        <div class="note-surface" id="note-surface"></div>
      </aside>

      <aside class="mobile-note-drawer" id="mobile-note-drawer" aria-label="移动端平行笔记">
        <p class="note-label" id="mobile-note-label">Parallel note</p>
        <div class="note-surface" id="mobile-note-surface"></div>
      </aside>
    </div>

    <script type="module" src="site/ielts-reader.js" data-source="site/ielts-data.json"></script>
  </body>
</html>
```

- [ ] **Step 4: Verify green for HTML contract and commit**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
git diff --check
```

Expected: the HTML assertions pass. Task 3 will replace the CSS/JS assertions and should create the next red tests.

Commit:

```bash
git add tests/ielts-academic-language-project-requirements.mjs projects/language/ielts-academic/index.html
git commit -m "feat: adopt IELTS reader shell"
```

---

### Task 3: Reader Style And Interaction Contract

**Files:**
- Modify: `tests/ielts-academic-language-project-requirements.mjs`
- Modify: `tests/ielts-academic-site-data-requirements.mjs`
- Modify: `projects/language/ielts-academic/site/ielts-reader.css`
- Modify: `projects/language/ielts-academic/site/ielts-reader.js`

- [ ] **Step 1: Add CSS parity assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, replace old CSS selectors:

```js
assert.match(siteCss, /\.ielts-shell/, "IELTS CSS should style the reader shell");
assert.match(siteCss, /\.swimlane-grid/, "IELTS CSS should style the 8-week swimlane");
assert.match(siteCss, /\.error-board/, "IELTS CSS should style the error board");
assert.match(siteCss, /@media \(max-width:\s*860px\)/, "IELTS CSS should include responsive rules");
assert.match(siteCss, /\.skill-gap/, "IELTS CSS should style skill gap bars");
assert.match(siteCss, /\.checkpoint-marker/, "IELTS CSS should style checkpoint markers");
assert.match(siteCss, /\.reference-chip/, "IELTS CSS should style reference chips");
assert.match(siteCss, /\.reader-search/, "IELTS CSS should style reader search");
```

with:

```js
assert.match(siteCss, /\.reader-shell/, "IELTS CSS should style the Foundations-style reader shell");
assert.match(siteCss, /\.reader-toolbar/, "IELTS CSS should style the reader toolbar");
assert.match(siteCss, /\.toolbar-search/, "IELTS CSS should style global search");
assert.match(siteCss, /\.reader-sidebar/, "IELTS CSS should style the module directory");
assert.match(siteCss, /\.module-section/, "IELTS CSS should style reader module sections");
assert.match(siteCss, /\.note-panel/, "IELTS CSS should style the right note panel");
assert.match(siteCss, /\.mobile-note-drawer/, "IELTS CSS should style the mobile note drawer");
assert.match(siteCss, /\[data-theme="dark"\]/, "IELTS CSS should include dark theme tokens");
assert.match(siteCss, /\.annotation-toolbar/, "IELTS CSS should style annotation controls");
assert.match(siteCss, /\.task-list/, "IELTS CSS should style task checklist state");
assert.match(siteCss, /@media \(max-width:\s*860px\)/, "IELTS CSS should include mobile drawer responsive rules");
```

Keep:

```js
assert.doesNotMatch(siteCss, /border-radius:\s*24px|border-radius:\s*28px/, "IELTS reader should avoid oversized card radii");
```

- [ ] **Step 2: Add JS parity assertions**

In `tests/ielts-academic-language-project-requirements.mjs`, replace old JS function assertions with:

```js
assert.match(siteJs, /const ANNOTATION_STORAGE_KEY = "ieltsReader\.annotations\.v1"/, "IELTS JS should use an IELTS annotation localStorage key");
assert.match(siteJs, /const TASK_STORAGE_KEY = "ieltsReader\.tasks\.v1"/, "IELTS JS should use an IELTS task localStorage key");
assert.match(siteJs, /const UI_STATE_KEY = "ieltsReader\.ui\.v1"/, "IELTS JS should use an IELTS UI localStorage key");
assert.match(siteJs, /function buildReaderModules/, "IELTS JS should adapt IELTS site data into reader modules");
assert.match(siteJs, /function renderModuleNav/, "IELTS JS should render module navigation");
assert.match(siteJs, /function renderCurrentModule/, "IELTS JS should render the active module");
assert.match(siteJs, /function renderSectionRail/, "IELTS JS should render a section rail");
assert.match(siteJs, /function renderContextualNotePanel/, "IELTS JS should render contextual notes");
assert.match(siteJs, /function runSearch/, "IELTS JS should support Foundations-style global search");
assert.match(siteJs, /function createAnnotationFromSelection/, "IELTS JS should support local annotations");
assert.match(siteJs, /function saveTaskState/, "IELTS JS should persist local task state");
assert.match(siteJs, /function setTheme/, "IELTS JS should support theme switching");
assert.match(siteJs, /fetchJson\(getDataSource\(\)\)/, "IELTS JS should load generated data from the script data-source attribute");
assert.match(siteJs, /Dashboard/, "IELTS modules should keep the Dashboard content");
assert.match(siteJs, /8-week swimlane/, "IELTS modules should keep the swimlane content");
assert.match(siteJs, /Errors/, "IELTS modules should keep the Errors content");
assert.match(siteJs, /Notes/, "IELTS modules should keep the Notes content");
assert.match(siteJs, /Journal/, "IELTS modules should keep the Journal content");
assert.match(siteJs, /Prompt library/, "IELTS modules should keep the Prompt library content");
assert.match(siteJs, /Validation/, "IELTS modules should keep the Validation content");
assert.doesNotMatch(siteJs, /githubToken|Authorization|contents\/|repos\/|fetch\("\/api/i, "IELTS JS should not include backend or GitHub write-back signals");
assert.doesNotMatch(siteJs, /localStorage\.setItem\("(?!ieltsReader\.(ui|annotations|tasks)\.v1")/, "IELTS JS should only write allowed IELTS localStorage keys");
assert.doesNotMatch(siteJs, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint/i, "IELTS JS should not store score, error, or checkpoint source data in localStorage");
```

Keep older content rendering assertions only if they remain meaningful. Do not require old function names such as `renderDashboard` if the new implementation renders Dashboard through modules.

- [ ] **Step 3: Add site-data no-write-back assertion**

In `tests/ielts-academic-site-data-requirements.mjs`, add after the existing no-write-back assertion:

```js
assert.match(readerJs, /ieltsReader\.annotations\.v1/, "reader JS should allow local annotation state only under the IELTS annotation key");
assert.match(readerJs, /ieltsReader\.tasks\.v1/, "reader JS should allow local task state only under the IELTS task key");
assert.doesNotMatch(readerJs, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint|localStorage\.setItem\(".*journal|localStorage\.setItem\(".*notes/i);
assert.doesNotMatch(readerJs, /method:\s*["']POST["']|method:\s*["']PUT["']|method:\s*["']PATCH["']|method:\s*["']DELETE["']/i);
```

- [ ] **Step 4: Run tests and verify red**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
```

Expected: FAIL because CSS and JS are still the old IELTS dashboard reader.

- [ ] **Step 5: Replace CSS with Foundations-style IELTS reader CSS**

Replace `projects/language/ielts-academic/site/ielts-reader.css` with a CSS file based on `projects/foundations/roadmap/roadmap-reader.css`, adapted to IELTS. Required selectors:

```css
:root {
  color-scheme: light;
  --reader-ink: #1f2724;
  --reader-ink-muted: rgba(31, 39, 36, 0.64);
  --reader-paper: #f4efe3;
  --reader-paper-soft: rgba(251, 248, 239, 0.78);
  --reader-paper-strong: rgba(255, 252, 244, 0.9);
  --reader-line: rgba(31, 39, 36, 0.13);
  --reader-glass: rgba(238, 247, 242, 0.42);
  --reader-glass-strong: rgba(244, 249, 245, 0.56);
  --reader-glass-highlight: rgba(255, 255, 255, 0.82);
  --reader-glass-edge: rgba(226, 239, 235, 0.72);
  --reader-glass-shadow: rgba(19, 45, 42, 0.16);
  --reader-blue: #183c49;
  --reader-red: #a64338;
  --reader-panel-blur: blur(34px) saturate(1.3);
  --toolbar-control-size: 42px;
  font-family: "Inter", "SF Pro Text", "PingFang SC", "Noto Sans SC", system-ui, sans-serif;
}

[data-theme="dark"] {
  color-scheme: dark;
  --reader-ink: #eef0e7;
  --reader-ink-muted: rgba(238, 240, 231, 0.66);
  --reader-paper: #111615;
  --reader-paper-soft: rgba(28, 34, 32, 0.78);
  --reader-paper-strong: rgba(35, 42, 39, 0.9);
  --reader-line: rgba(238, 240, 231, 0.14);
  --reader-glass: rgba(24, 34, 32, 0.58);
  --reader-glass-strong: rgba(30, 42, 39, 0.68);
  --reader-glass-highlight: rgba(255, 255, 255, 0.18);
  --reader-glass-edge: rgba(255, 255, 255, 0.16);
  --reader-glass-shadow: rgba(0, 0, 0, 0.36);
  --reader-blue: #9cc9cf;
  --reader-red: #ca6a60;
}
```

The final CSS must include these selector families:

```css
.reader-shell {}
.reader-toolbar {}
.toolbar-search {}
.toolbar-controls {}
.reader-sidebar {}
.directory-surface {}
.module-nav {}
.section-rail {}
.reader-main {}
.module-header {}
.section-list {}
.module-section {}
.dashboard-grid {}
.error-board {}
.note-panel {}
.mobile-note-drawer {}
.annotation-toolbar {}
.annotation-delete-popover {}
.knowledge-highlight {}
.task-list {}
@media (max-width: 860px) {}
```

Do not use 24px or 28px border radii. Large shell/panel effects can use 16px only if copied from toolbar controls; repeated cards should stay at 8px or less.

- [ ] **Step 6: Replace JS with IELTS module reader**

Rewrite `projects/language/ielts-academic/site/ielts-reader.js` around these top-level constants and state:

```js
const UI_STATE_KEY = "ieltsReader.ui.v1";
const ANNOTATION_STORAGE_KEY = "ieltsReader.annotations.v1";
const TASK_STORAGE_KEY = "ieltsReader.tasks.v1";
const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8];
const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];

const state = {
  data: null,
  modules: [],
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  activeKnowledgeNoteId: "",
  sectionScrollHandler: null,
  sectionScrollFrame: 0,
  annotations: { version: 1, items: [] },
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null,
  ui: { theme: "light", leftCollapsed: false, noteCollapsed: false },
};

const taskState = loadTaskState();
```

The implementation must define these functions because tests assert them:

```js
function getDataSource() {
  return document.currentScript?.dataset.source ?? "site/ielts-data.json";
}

async function fetchJson(path) {
  const response = await fetch(new URL(path, window.location.href));
  if (!response.ok) throw new Error(`Unable to load ${path}`);
  return response.json();
}

function buildReaderModules(data) {
  return [
    buildDashboardModule(data),
    buildSwimlaneModule(data),
    buildErrorsModule(data),
    buildNotesModule(data),
    buildJournalModule(data),
    buildPromptLibraryModule(data),
    buildValidationModule(data),
  ];
}
```

Required module IDs and titles:

```js
[
  ["dashboard", "Dashboard"],
  ["swimlane", "8-week swimlane"],
  ["errors", "Errors"],
  ["notes", "Notes"],
  ["journal", "Journal"],
  ["prompt-library", "Prompt library"],
  ["validation", "Validation"],
]
```

Each module object should have:

```js
{
  id: "dashboard",
  title: "Dashboard",
  kicker: "Current state",
  summary: "...",
  status: "template",
  priority: "high",
  lastUpdated: "...",
  sections: [
    { id: "dashboard-overview", title: "Overview", body: "<div>...</div>" },
  ],
  note: {
    id: "dashboard-note",
    title: "Dashboard",
    body: "<p>...</p>",
  },
  searchEntries: [],
}
```

Keep the existing escaping helpers and IELTS-specific display helpers such as band formatting, target formatting, reference chips, skill gap bars, checkpoint markers and error columns. They can be renamed, but the rendered modules must still expose Dashboard, Swimlane, Errors, Notes, Journal, Prompt Library and Validation content.

- [ ] **Step 7: Add local annotation and task state**

Port the local-only interaction pattern from Foundations with IELTS-specific keys:

```js
function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(ANNOTATION_STORAGE_KEY);
    if (!raw) return { version: 1, items: [] };
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) return { version: 1, items: [] };
    return {
      version: 1,
      items: parsed.items.filter((item) => item && item.projectId === "ielts-academic"),
    };
  } catch {
    return { version: 1, items: [] };
  }
}

function saveAnnotations(annotations = state.annotations) {
  window.localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(annotations));
}

function loadTaskState() {
  try {
    const raw = window.localStorage.getItem(TASK_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function saveTaskState(tasks = taskState) {
  window.localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
}
```

Task checkboxes should only be rendered for action-like source fields such as error `reviewMethod`, checkpoint `evidenceRequired`, or explicit validation/checklist content. Do not add checkboxes to every static informational card.

- [ ] **Step 8: Add theme and panel state**

Implement:

```js
function loadUiState() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(UI_STATE_KEY) ?? "{}");
    state.ui = {
      theme: parsed.theme === "dark" ? "dark" : "light",
      leftCollapsed: Boolean(parsed.leftCollapsed),
      noteCollapsed: Boolean(parsed.noteCollapsed),
    };
  } catch {
    state.ui = { theme: "light", leftCollapsed: false, noteCollapsed: false };
  }
}

function saveUiState() {
  window.localStorage.setItem(UI_STATE_KEY, JSON.stringify(state.ui));
}

function setTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  state.ui.theme = normalized;
  document.body.dataset.theme = normalized;
  document.querySelector("#toggle-theme")?.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
  saveUiState();
}
```

Bind `#toggle-theme`, `#toggle-note`, and `[data-toggle-left]` to update shell classes and UI state.

- [ ] **Step 9: Add global search**

Implement `runSearch(query)` so it searches `module.searchEntries`, sorts by title/body relevance, renders `.search-results`, and clicking a result calls:

```js
openModule(moduleId, { targetSectionId: sectionId });
```

Search should include data from notes, journal, errors, prompts and validation.

- [ ] **Step 10: Verify green and commit**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node --check projects/language/ielts-academic/site/ielts-reader.js
git diff --check
```

Expected: PASS.

Commit:

```bash
git add tests/ielts-academic-language-project-requirements.mjs tests/ielts-academic-site-data-requirements.mjs projects/language/ielts-academic/site/ielts-reader.css projects/language/ielts-academic/site/ielts-reader.js
git commit -m "feat: align IELTS reader with Foundations interactions"
```

---

### Task 4: Browser Verification And Final Cleanup

**Files:**
- Modify only if verification reveals a narrow issue:
  - `projects/language/ielts-academic/index.html`
  - `projects/language/ielts-academic/site/ielts-reader.css`
  - `projects/language/ielts-academic/site/ielts-reader.js`
  - relevant tests

- [ ] **Step 1: Run full repository verification**

Run:

```bash
node tests/projects-requirements.mjs
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
git diff --exit-code -- projects/language/ielts-academic/site/ielts-data.json
git diff --check
```

Expected: PASS.

- [ ] **Step 2: Start local static server**

Run:

```bash
python3 -m http.server 8765
```

from repo root. Keep it running for browser checks.

- [ ] **Step 3: Browser-check the project bookmark page**

Open:

```text
http://127.0.0.1:8765/projects/
```

Verify:

- The second bookmark title is `语言`.
- It uses the same vertical Chinese calligraphy visual path as `基石` and `记忆与智能体`.
- There is no obvious title clipping on desktop or 390px mobile.

- [ ] **Step 4: Browser-check the IELTS reader**

Open:

```text
http://127.0.0.1:8765/projects/language/ielts-academic/
```

Verify:

- No console errors.
- Dashboard, 8-week swimlane, Errors, Notes, Journal, Prompt library and Validation are reachable from the directory.
- Theme toggle changes light/dark state and persists after reload.
- Directory collapse works on desktop and mobile.
- Note panel collapse works on desktop and mobile.
- Search finds an IELTS-specific term such as `Writing` or `Task 2`.
- Highlight/annotation can be created inside a main content card and persists after reload.
- Task checkbox state, where rendered, persists after reload.
- 390px mobile viewport has no full-page horizontal overflow or incoherent overlap.

- [ ] **Step 5: Fix any browser-only issue narrowly**

If browser verification finds layout or runtime issues, fix only the affected file and rerun:

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node --check projects/language/ielts-academic/site/ielts-reader.js
git diff --check
```

- [ ] **Step 6: Commit browser cleanup if needed**

If Step 5 changed files:

```bash
git add projects/language/ielts-academic/index.html projects/language/ielts-academic/site/ielts-reader.css projects/language/ielts-academic/site/ielts-reader.js tests/ielts-academic-language-project-requirements.mjs tests/ielts-academic-site-data-requirements.mjs
git commit -m "fix: polish IELTS reader parity"
```

- [ ] **Step 7: Final status**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: clean feature branch with only intended commits.

## Final Completion Checklist

- [ ] Bookmark page displays IELTS project as `语言`.
- [ ] IELTS bookmark uses the Chinese bookmark font path.
- [ ] IELTS reader uses a Foundations-style reader shell.
- [ ] Theme toggle, directory collapse, note panel collapse, search, annotations and task state work.
- [ ] Browser state is limited to `ieltsReader.ui.v1`, `ieltsReader.annotations.v1`, and `ieltsReader.tasks.v1`.
- [ ] No GitHub/API/repo write-back path exists.
- [ ] Existing IELTS source content semantics are unchanged.
- [ ] `site/ielts-data.json` remains deterministic.
- [ ] All required Node and git verification commands pass.
- [ ] Browser check passes on desktop and 390px mobile.
