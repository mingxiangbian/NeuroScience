# Foundations Roadmap Reader UI Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `projects/foundations/` roadmap reader 从“有框架但展示弱”的状态修到真实可用：右栏有明确分类，搜索可跳转到模块章节，收缩 rail 跟随滚动，高层进度标签明确，`时间线` 以视觉 timeline 展示。

**Architecture:** 保持当前静态架构：Markdown 是写作源，`build-roadmap-data.mjs` 输出结构化 JSON，`roadmap-reader.js` 只负责渲染和交互。新增数据字段不引入后端、不引入 browser storage、不引入搜索库；个人项目规模使用 section-level substring search。CSS 继续沿用 reader shell 三栏布局，只加强当前页面的可读性和状态反馈。

**Tech Stack:** Static HTML/CSS/JavaScript, Node.js build script, Markdown source files, GitHub Pages.

---

## 文件结构

- Modify: `tests/foundations-roadmap-requirements.mjs`
  - 增加需求断言：section-level search index、note 分组标题、进度环和整体进度标签、timeline class、scroll active observer、collapsed rail hover。
- Modify: `projects/foundations/scripts/build-roadmap-data.mjs`
  - 增加 `overallProgress`、`searchEntries`、`noteGroups`、`timeline` 字段。
  - 保持 `generatedAt` 确定性。
- Modify: `projects/foundations/roadmap/roadmap-data.json`
  - 由构建脚本生成，不手写。
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
  - 使用结构化字段渲染右栏、搜索结果、进度、timeline 和 rail active。
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
  - 增加进度环、整体进度、note group、timeline、search result、collapsed rail hover/active 样式。

---

### Task 1: Strengthen Requirements Tests

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`

- [ ] **Step 1: Add failing assertions for generated data shape**

In `tests/foundations-roadmap-requirements.mjs`, after the existing loop that checks each module includes `sections`, add:

```js
assert.equal(typeof data.project.overallProgress, "number", "generated data should include overall progress");
assert.ok(data.project.overallProgress > 0, "overall progress should be greater than zero");
assert.ok(data.project.overallProgress <= 100, "overall progress should not exceed 100");

for (const module of data.modules) {
  assert.ok(Array.isArray(module.searchEntries), `${module.id} should include section-level search entries`);
  assert.ok(module.searchEntries.length > 0, `${module.id} should expose searchable sections`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should point back to the module`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.sectionTitle === "string" && entry.sectionTitle.length > 0), `${module.id} search entries should include section titles`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.text === "string" && entry.text.length > 20), `${module.id} search entries should include useful text`);
  assert.ok(Array.isArray(module.noteGroups), `${module.id} should include note groups`);
  assert.ok(module.noteGroups.every((group) => ["资源", "反思", "面试表达"].includes(group.title)), `${module.id} note groups should use known categories`);
  assert.ok(Array.isArray(module.timeline), `${module.id} should include a timeline array`);
}

assert.ok(byId["agent-design"].timeline.length >= 3, "agent design should expose timeline items for visual rendering");
```

- [ ] **Step 2: Add failing assertions for reader JS behavior**

In the JS assertions section, add:

```js
assert.match(js, /function renderProgressSummary/, "roadmap JS should render labeled module and overall progress");
assert.match(js, /function renderTimelineSection/, "roadmap JS should render timeline as a visual component");
assert.match(js, /function renderSearchResults/, "roadmap JS should isolate section-level search rendering");
assert.match(js, /function setActiveSection/, "roadmap JS should update collapsed rail active state dynamically");
assert.match(js, /IntersectionObserver/, "roadmap JS should observe visible sections for active rail state");
assert.match(js, /data-section-id/, "roadmap JS should render stable section targets for search and rail navigation");
```

- [ ] **Step 3: Add failing assertions for CSS classes**

In the CSS assertions section, add:

```js
assert.match(css, /\.progress-ring/, "roadmap CSS should style a module progress ring");
assert.match(css, /\.overall-progress/, "roadmap CSS should label overall roadmap progress");
assert.match(css, /\.timeline-list/, "roadmap CSS should style timeline content as a visual list");
assert.match(css, /\.note-group-title/, "roadmap CSS should style explicit note group headings");
assert.match(css, /\.section-line:hover/, "roadmap CSS should style collapsed rail hover state");
assert.match(css, /\.section-line\[aria-current="true"\]/, "roadmap CSS should expose active collapsed rail state");
assert.match(css, /\.result-meta/, "roadmap CSS should show module and section metadata in search results");
```

- [ ] **Step 4: Run requirements test and verify RED**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL with an assertion such as `generated data should include overall progress`, `roadmap JS should render labeled module and overall progress`, or `roadmap CSS should style a module progress ring`.

- [ ] **Step 5: Commit failing requirements**

Run:

```bash
git add tests/foundations-roadmap-requirements.mjs
git commit -m "Add foundations roadmap UI data requirements"
```

---

### Task 2: Generate Structured Roadmap Data

**Files:**
- Modify: `projects/foundations/scripts/build-roadmap-data.mjs`
- Modify generated: `projects/foundations/roadmap/roadmap-data.json`

- [ ] **Step 1: Add plain-text helpers**

In `build-roadmap-data.mjs`, after `stripMarkdown`, add:

```js
function stripHtml(html) {
  return String(html ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function slugifySection(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
```

- [ ] **Step 2: Add timeline extraction**

After `slugifySection`, add:

```js
function extractTimelineItems(markdown) {
  return String(markdown ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^- /.test(line))
    .map((line, index) => {
      const text = line.replace(/^- /, "").trim();
      const labelMatch = text.match(/^(Week \d+|Days \d+-\d+|Day \d+\+|Days \d+\+|[^：:]{1,18})[：:]\s*(.+)$/);
      return {
        id: `timeline-${index + 1}`,
        label: labelMatch?.[1] ?? `Step ${index + 1}`,
        text: labelMatch?.[2] ?? text,
        status: /进行中|current|in-progress/i.test(text) ? "current" : index < 2 ? "done" : "open",
      };
    });
}
```

- [ ] **Step 3: Add search and note builders**

After `extractTimelineItems`, add:

```js
function buildSearchEntries(id, title, rawSections) {
  return Object.entries(rawSections).map(([sectionTitle, sectionMarkdown]) => ({
    id: `${id}-${slugifySection(sectionTitle) || "section"}`,
    moduleId: id,
    moduleTitle: title,
    sectionTitle,
    text: stripMarkdown(sectionMarkdown),
  }));
}

function buildNoteGroups(sections) {
  return ["资源", "反思", "面试表达"]
    .map((title) => ({
      title,
      body: sections[title] ?? "",
      text: stripHtml(sections[title] ?? ""),
    }))
    .filter((group) => group.body);
}
```

- [ ] **Step 4: Extend module records**

In `buildModule`, add `sectionIds`, `searchEntries`, `noteGroups`, and `timeline`:

```js
const sectionIds = Object.fromEntries(
  Object.keys(rawSections).map((sectionTitle) => [sectionTitle, `${id}-${slugifySection(sectionTitle) || "section"}`]),
);
const record = {
  id: parsed.data.id,
  title: parsed.data.title,
  status: parsed.data.status,
  progress: Number(parsed.data.progress),
  lastUpdated: parsed.data.last_updated,
  priority: parsed.data.priority ?? "medium",
  sections,
  sectionIds,
  searchEntries: buildSearchEntries(id, title, rawSections),
  noteGroups: buildNoteGroups(sections),
  timeline: extractTimelineItems(rawSections["时间线"] ?? ""),
  searchText: `${title} ${stripMarkdown(parsed.content)}`,
};
```

- [ ] **Step 5: Extend validation and project metadata**

In `validateModule`, add:

```js
if (!Array.isArray(record.searchEntries) || record.searchEntries.length === 0) throw new Error(`${expectedId} has no search entries`);
if (!Array.isArray(record.noteGroups)) throw new Error(`${expectedId} has invalid note groups`);
if (!Array.isArray(record.timeline)) throw new Error(`${expectedId} has invalid timeline`);
```

Before `roadmapData`, add:

```js
const overallProgress = Math.round(
  modules.reduce((sum, module) => sum + module.progress, 0) / modules.length,
);
```

Inside `project`, add:

```js
overallProgress,
```

- [ ] **Step 6: Generate data and verify tests move forward**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL, but now at JS or CSS assertions rather than generated data assertions.

---

### Task 3: Render Real UI States

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add active section state and observer cleanup**

Update top-level `state`:

```js
const state = {
  data: null,
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  sectionObserver: null,
};
```

- [ ] **Step 2: Add section id helper**

After `getSection`, add:

```js
function getSectionId(module, title) {
  return module.sectionIds?.[title] ?? `${module.id}-${title}`;
}
```

- [ ] **Step 3: Add labeled progress renderer**

After `renderSectionRail`, add:

```js
function renderProgressSummary(module, progress) {
  const overallProgress = Math.max(0, Math.min(100, Number(state.data.project.overallProgress) || 0));
  return `
    <div class="module-progress-summary" aria-label="进度摘要">
      <div class="progress-ring" style="--progress: ${progress}" aria-label="本模块进度 ${progress}%">
        <span>${escapeHtml(String(progress))}%</span>
      </div>
      <div class="progress-copy">
        <p class="progress-label">本模块进度</p>
        <p class="progress-status">${escapeHtml(module.status)} · ${escapeHtml(module.priority)}</p>
      </div>
      <p class="overall-progress">整体进度 ${escapeHtml(String(overallProgress))}%</p>
    </div>
  `;
}
```

- [ ] **Step 4: Add timeline renderer**

After `renderProgressSummary`, add:

```js
function renderTimelineSection(module, title) {
  if (!module.timeline?.length) return getSection(module, title);
  const items = module.timeline
    .map((item) => `
      <li class="timeline-item" data-status="${escapeHtml(item.status)}">
        <span class="timeline-dot" aria-hidden="true"></span>
        <div>
          <p class="timeline-label">${escapeHtml(item.label)}</p>
          <p class="timeline-text">${escapeHtml(item.text)}</p>
        </div>
      </li>
    `)
    .join("");
  return `<ol class="timeline-list">${items}</ol>`;
}
```

- [ ] **Step 5: Update module header and section rendering**

In `renderCurrentModule`, replace the old `.progress-meter` header block with:

```js
${renderProgressSummary(module, progress)}
```

When rendering each `.module-section`, compute section id and timeline body:

```js
const sectionId = getSectionId(module, title);
const body = title === "时间线" ? renderTimelineSection(module, title) : getSection(module, title);
```

Set the article id and data attributes:

```html
<article class="module-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="${escapeHtml(title)}">
```

- [ ] **Step 6: Update note panel rendering**

Replace the note section map in `renderNotePanel` with:

```js
const noteBlocks = module.noteGroups
  .map((group) => `
    <section class="note-block" data-note-group="${escapeHtml(group.title)}">
      <h3 class="note-group-title">${escapeHtml(group.title)}</h3>
      <div class="note-group-body">${group.body}</div>
    </section>
  `)
  .join("");
```

Use a fallback only when there are no groups:

```js
const renderedNotes = noteBlocks || `<p class="note-empty">这个模块还没有资源、反思或面试表达。</p>`;
els.noteSurface.innerHTML = renderedNotes;
els.mobileNoteSurface.innerHTML = renderedNotes;
```

- [ ] **Step 7: Add active section sync**

After `updateUrl`, add:

```js
function setActiveSection(sectionId) {
  state.activeSectionId = sectionId;
  els.sectionLines.querySelectorAll(".section-line").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.sectionId === sectionId);
    button.setAttribute("aria-current", button.dataset.sectionId === sectionId ? "true" : "false");
  });
}

function observeSections() {
  state.sectionObserver?.disconnect();
  const sections = [...els.sectionList.querySelectorAll("[data-section-id]")];
  if (sections.length === 0) return;
  state.sectionObserver = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((left, right) => Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top))[0];
    if (visible?.target?.dataset.sectionId) setActiveSection(visible.target.dataset.sectionId);
  }, {
    root: els.main,
    threshold: [0.2, 0.5, 0.8],
    rootMargin: "-16% 0px -68% 0px",
  });
  sections.forEach((section) => state.sectionObserver.observe(section));
  setActiveSection(sections[0].dataset.sectionId);
}
```

- [ ] **Step 8: Update rail rendering**

In `renderSectionRail`, use `sectionId` and `aria-current`:

```js
const sectionId = getSectionId(module, sectionTitle);
button.dataset.sectionId = sectionId;
button.title = sectionTitle;
button.setAttribute("aria-current", index === 0 ? "true" : "false");
button.addEventListener("click", () => {
  document.querySelector(`#${CSS.escape(sectionId)}`)?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
  setActiveSection(sectionId);
});
```

- [ ] **Step 9: Render section-level search results**

Replace `runSearch` result mapping with section entries:

```js
const results = state.data.modules
  .flatMap((module) => module.searchEntries.map((entry) => ({ module, entry })))
  .map(({ module, entry }) => {
    const text = `${entry.moduleTitle} ${entry.sectionTitle} ${entry.text}`.toLowerCase();
    const score = terms.reduce((sum, term) => sum + (text.includes(term) ? 1 : 0), 0);
    return { module, entry, score };
  })
  .filter((item) => item.score > 0)
  .sort((left, right) => right.score - left.score || left.module.title.localeCompare(right.module.title))
  .slice(0, 8);

renderSearchResults(results);
```

Add `renderSearchResults` before `runSearch`:

```js
function renderSearchResults(results) {
  els.searchResults.hidden = false;
  if (results.length === 0) {
    els.searchResults.innerHTML = `<p class="result-empty">No results found</p>`;
    return;
  }

  els.searchResults.innerHTML = results
    .map(({ module, entry }) => `
      <button class="result-item" type="button" data-module-id="${escapeHtml(module.id)}" data-section-id="${escapeHtml(entry.id)}">
        <span>
          <span class="result-title">${highlightTerms(entry.sectionTitle, state.searchQuery)}</span>
          <span class="result-snippet">${highlightTerms(getEntrySnippet(entry, state.searchQuery), state.searchQuery)}</span>
        </span>
        <span class="result-meta">${escapeHtml(module.title)}</span>
      </button>
    `)
    .join("");

  els.searchResults.querySelectorAll("[data-module-id]").forEach((button) => {
    button.addEventListener("click", () => {
      openModule(button.dataset.moduleId, { targetSectionId: button.dataset.sectionId });
      closeSearchModal();
    });
  });
}
```

Add `getEntrySnippet` next to `getSnippet`:

```js
function getEntrySnippet(entry, query) {
  const searchText = entry.text ?? "";
  const lower = searchText.toLowerCase();
  const term = getSearchTerms(query).find((item) => lower.includes(item.toLowerCase()));
  if (!term) return searchText.slice(0, 160);
  const index = lower.indexOf(term.toLowerCase());
  const start = Math.max(0, index - 56);
  const end = Math.min(searchText.length, index + term.length + 128);
  return `${start > 0 ? "..." : ""}${searchText.slice(start, end)}${end < searchText.length ? "..." : ""}`;
}
```

- [ ] **Step 10: Support opening target section**

Update `openModule` signature:

```js
function openModule(moduleId, { syncUrl = true, targetSectionId = "" } = {}) {
```

After `renderSectionRail(nextModule);`, call:

```js
observeSections();
if (targetSectionId) {
  requestAnimationFrame(() => {
    document.querySelector(`#${CSS.escape(targetSectionId)}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(targetSectionId);
  });
}
```

- [ ] **Step 11: Verify GREEN for JS/data shape**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL only if CSS assertions are not implemented yet.

---

### Task 4: Style The Real UI

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.css`

- [ ] **Step 1: Replace simple progress meter styles with labeled progress styles**

Add after `.module-title` styles:

```css
.module-progress-summary {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  margin-top: 18px;
  border-top: 1px solid var(--reader-line);
  padding-top: 18px;
}

.progress-ring {
  --progress: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background:
    radial-gradient(circle at center, var(--reader-paper-strong) 0 56%, transparent 57%),
    conic-gradient(var(--reader-blue) calc(var(--progress) * 1%), rgba(31, 39, 36, 0.12) 0);
  color: var(--reader-ink);
  font-family: var(--reader-mono);
  font-size: 15px;
  font-weight: 760;
}

.progress-label,
.progress-status,
.overall-progress {
  margin: 0;
}

.progress-label {
  font-size: 14px;
  font-weight: 760;
}

.progress-status,
.overall-progress {
  color: var(--reader-ink-muted);
  font-size: 12px;
}

.overall-progress {
  justify-self: end;
  font-weight: 720;
}
```

- [ ] **Step 2: Add timeline styles**

Add after `.section-body pre`:

```css
.timeline-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline-item {
  position: relative;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 16px;
  padding: 0 0 22px;
}

.timeline-item::before {
  position: absolute;
  top: 20px;
  bottom: 0;
  left: 7px;
  width: 1px;
  background: var(--reader-line);
  content: "";
}

.timeline-item:last-child::before {
  display: none;
}

.timeline-dot {
  position: relative;
  z-index: 1;
  width: 15px;
  height: 15px;
  margin-top: 5px;
  border: 2px solid var(--reader-blue);
  border-radius: 50%;
  background: var(--reader-paper-strong);
}

.timeline-item[data-status="current"] .timeline-dot {
  border-color: var(--reader-red);
  box-shadow: 0 0 0 4px rgba(166, 67, 56, 0.1);
}

.timeline-label,
.timeline-text {
  margin: 0;
}

.timeline-label {
  color: var(--reader-ink-muted);
  font-size: 13px;
  font-weight: 720;
}

.timeline-text {
  margin-top: 3px;
  font-size: 16px;
  line-height: 1.7;
}
```

- [ ] **Step 3: Add note group styles**

Replace `.note-block h3` with:

```css
.note-group-title {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 8px;
  color: var(--reader-blue);
  font-size: 14px;
  font-weight: 760;
}

.note-group-title::before {
  width: 8px;
  height: 8px;
  border: 1px solid currentColor;
  border-radius: 50%;
  content: "";
}

.note-group-body {
  border-left: 1px solid var(--reader-line);
  padding-left: 14px;
}

.note-empty {
  margin: 0;
  color: var(--reader-ink-muted);
}
```

- [ ] **Step 4: Update collapsed rail active and hover styles**

Change `.section-line.is-active` to:

```css
.section-line[aria-current="true"],
.section-line.is-active {
  width: 32px;
  height: 3px;
  background: var(--reader-section-line-active);
}
```

Keep `.section-line:hover` as the hover rule.

- [ ] **Step 5: Update search result metadata selector**

Add:

```css
.result-meta {
  color: var(--reader-ink-muted);
  font-family: var(--reader-mono);
  font-size: 11px;
  white-space: nowrap;
}
```

- [ ] **Step 6: Add mobile progress fallback**

Inside `@media (max-width: 860px)`, add:

```css
.module-progress-summary {
  grid-template-columns: 72px minmax(0, 1fr);
}

.overall-progress {
  grid-column: 1 / -1;
  justify-self: start;
}
```

- [ ] **Step 7: Verify GREEN**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
git diff --check
```

Expected: PASS and no whitespace errors.

---

### Task 5: Browser And Pages Verification

**Files:**
- No source file changes expected.

- [ ] **Step 1: Run full local regression**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
node projects/foundations/scripts/build-roadmap-data.mjs
git status --short --branch
```

Expected: tests pass and `git status` shows only intended changed files before commit.

- [ ] **Step 2: Start local server**

Run:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Expected: server prints `Serving HTTP on 127.0.0.1 port 8765`.

- [ ] **Step 3: Verify local page with Chrome connector or CLI fallback**

Use the Chrome connector if available. Verify:

- `data-page="foundations-roadmap-reader"` exists.
- `project.overallProgress` is shown as `整体进度`.
- Default module renders a `.progress-ring`.
- `#search-results` returns section-level results for `RAG`.
- Clicking a result opens the target module and section.
- `.note-group-title` appears for `资源 / 反思 / 面试表达` when those sections exist.
- Console has no error logs.

If Chrome connector fails, use `curl` and static tests as fallback:

```bash
curl -fsSL http://127.0.0.1:8765/projects/foundations/ | rg -n "foundations-roadmap-reader|roadmap-reader.js|roadmap-reader.css"
curl -fsSL http://127.0.0.1:8765/projects/foundations/roadmap/roadmap-data.json | rg -n "\"overallProgress\"|\"searchEntries\"|\"noteGroups\"|\"timeline\""
```

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add tests/foundations-roadmap-requirements.mjs projects/foundations/scripts/build-roadmap-data.mjs projects/foundations/roadmap/roadmap-data.json projects/foundations/roadmap/roadmap-reader.js projects/foundations/roadmap/roadmap-reader.css
git commit -m "Connect foundations roadmap UI data"
```

- [ ] **Step 5: Push and verify Pages**

Run:

```bash
git push origin main
gh run list --repo mingxiangbian/NeuroScience --branch main --limit 5
gh run watch <latest-run-id> --repo mingxiangbian/NeuroScience --exit-status
curl --retry 3 --retry-delay 2 -fsSL https://mingxiangbian.github.io/NeuroScience/projects/foundations/ | rg -n "foundations-roadmap-reader|roadmap-reader.js|roadmap-reader.css"
curl --retry 3 --retry-delay 2 -fsSL https://mingxiangbian.github.io/NeuroScience/projects/foundations/roadmap/roadmap-data.json | rg -n "\"overallProgress\"|\"searchEntries\"|\"noteGroups\"|\"timeline\""
```

Expected: push succeeds, Pages workflow succeeds, deployed HTML and JSON include the new UI/data fields.

---

## Self-Review

- Spec coverage: right note labels, search logic, collapsed rail active/hover, progress labeling, visual timeline, and verification are covered by Tasks 1-5.
- Placeholder scan: no unfinished markers or vague testing instructions remain.
- Type consistency: `overallProgress`, `searchEntries`, `noteGroups`, `timeline`, `sectionIds`, `renderProgressSummary`, `renderTimelineSection`, `renderSearchResults`, and `setActiveSection` are consistently named across data, JS, CSS, and tests.
