# Paper Reader Shell Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将 `papers/<project-id>/` 阅读器从卡片化三栏工作台修成更省空间、更稳定的文档阅读器壳层。

**Architecture:** 保留现有 `papers/shared/reader.css` 和 `papers/shared/reader.js` 复用边界，不新增路由、不新增后端。先用 `tests/paper-reader-requirements.mjs` 锁定新布局、竖屏规则、搜索、笔记稳定性和无破图行为，再以最小改动更新 shared reader。

**Tech Stack:** Static HTML, CSS, browser ES modules, Node.js assertion tests, Playwright/browser smoke checks.

---

## File Map

- Modify: `tests/paper-reader-requirements.mjs`
  - 负责结构和静态契约测试：搜索 placeholder、header 链接隐藏、竖屏不显示 section rail、玻璃层级、无破图、无后端依赖。
- Modify: `papers/brain-memory-for-ai-agents/index.html`
  - 只改搜索 placeholder 和必要的 aria/结构 class，不改变页面层级。
- Modify: `papers/shared/reader.css`
  - 负责 full-width reader shell、固定玻璃目录、固定笔记 panel、响应式断点、正文去卡片化、section rail 桌面限定。
- Modify: `papers/shared/reader.js`
  - 负责 note panel 稳定状态、header 链接只在 fallback 显示、figure 无文件时不渲染 broken image、断点控制逻辑。
- Verify only: `tests/papers-requirements.mjs`
- Verify only: `tests/homepage-requirements.mjs`

## Task 1: 更新 reader shell 需求测试

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`
- Read: `docs/superpowers/specs/2026-07-03-paper-reader-shell-refinement-design.md`

- [x] **Step 1: Add failing static assertions**

Update `tests/paper-reader-requirements.mjs` with assertions equivalent to:

```js
assert.match(html, /placeholder="Searching\.\.\."/);
assert.match(js, /function renderPaperLinks/);
assert.match(js, /<div class="paper-actions"><\/div>/);
assert.match(js, /actions\.classList\.add\("is-fallback-only"\)/);
assert.match(js, /function renderNoteSurface/);
assert.match(js, /function syncResponsiveState/);
assert.match(js, /function updateActiveSectionRail/);
assert.match(js, /hasFile \?[\s\S]*<img[\s\S]*: `[\s\S]*figure-placeholder/);
assert.match(css, /--toolbar-offset/);
assert.match(css, /--reader-glass-highlight/);
assert.match(css, /--reader-glass-edge/);
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*position:\s*sticky/);
assert.match(css, /\.note-panel\s*\{[\s\S]*position:\s*sticky/);
assert.match(css, /\.reader-shell\.is-left-collapsed \.section-rail\s*\{[\s\S]*display:\s*flex/);
assert.match(css, /@media \(max-width:\s*1100px\)[\s\S]*is-note-collapsed/);
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.section-rail\s*\{[\s\S]*display:\s*none/);
assert.match(css, /\.paper-actions\.is-fallback-only/);
assert.match(css, /\.section-chip[\s\S]*background:\s*transparent/);
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/);
```

- [x] **Step 2: Run the targeted test and confirm it fails**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL on the new shell refinement assertions, because current implementation still uses old placeholder, old header links, old breakpoint behavior, and weaker layout rules.

## Task 2: Update HTML shell contract

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`
- Test: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Change search placeholder**

Replace:

```html
placeholder="搜索 paper chunk"
```

with:

```html
placeholder="Searching..."
```

- [x] **Step 2: Keep existing project and panel structure**

Do not remove these ids:

```html
id="reader-toolbar"
id="paper-directory"
id="section-rail"
id="reader-main"
id="note-panel"
id="mobile-note-drawer"
id="global-search"
```

The test still depends on this static contract.

## Task 3: Rework CSS layout and visual system

**Files:**
- Modify: `papers/shared/reader.css`
- Test: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Add glass/layout variables**

Add root variables:

```css
--toolbar-offset: 86px;
--reader-glass-highlight: rgba(255, 255, 255, 0.72);
--reader-glass-edge: rgba(255, 255, 255, 0.46);
--reader-panel-blur: blur(30px) saturate(1.24);
```

Add dark overrides with lower highlight opacity:

```css
--reader-glass-highlight: rgba(255, 255, 255, 0.18);
--reader-glass-edge: rgba(255, 255, 255, 0.16);
```

- [x] **Step 2: Convert shell to tighter full-width reader**

Update `.reader-shell` to:

```css
.reader-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr;
  grid-template-columns: minmax(198px, 238px) minmax(0, 1fr) minmax(230px, 290px);
  grid-template-areas:
    "toolbar toolbar toolbar"
    "directory main notes";
  column-gap: clamp(8px, 1.2vw, 14px);
  row-gap: 10px;
  padding: 10px clamp(8px, 1.4vw, 16px) 0;
  transition: grid-template-columns 180ms ease;
}
```

Keep collapsed variants, but reduce collapsed rail width to `52px`.

- [x] **Step 3: Strengthen toolbar/sidebar/note glass**

Make `.reader-toolbar`, `.directory-surface`, `.section-rail`, `.note-panel`, and `.mobile-note-drawer` use:

```css
border: 1px solid var(--reader-glass-edge);
background: var(--reader-glass);
backdrop-filter: var(--reader-panel-blur);
-webkit-backdrop-filter: var(--reader-panel-blur);
box-shadow:
  inset 0 1px 0 var(--reader-glass-highlight),
  inset 0 0 24px rgba(255, 255, 255, 0.1),
  0 18px 48px var(--reader-shadow);
```

- [x] **Step 4: Make side panels fixed-in-viewport via sticky**

Update:

```css
.reader-sidebar {
  grid-area: directory;
  position: sticky;
  top: var(--toolbar-offset);
  align-self: start;
  min-width: 0;
  height: calc(100vh - var(--toolbar-offset) - 12px);
}

.directory-surface,
.section-rail,
.note-panel {
  height: calc(100vh - var(--toolbar-offset) - 12px);
  overflow: auto;
}

.note-panel {
  grid-area: notes;
  position: sticky;
  top: var(--toolbar-offset);
  align-self: start;
}
```

- [x] **Step 5: De-card the main reader**

Update:

```css
.reader-main {
  grid-area: main;
  min-width: 0;
  padding: 6px 0 72px;
}

.paper-header,
.chunk-list {
  max-width: min(920px, calc(100vw - 40px));
}

.paper-title {
  font-size: clamp(30px, 4.2vw, 58px);
}

.paper-meta {
  color: rgba(31, 39, 36, 0.74);
}

.section-chip {
  border: 1px solid var(--reader-line);
  background: transparent;
  color: var(--reader-ink-muted);
  padding: 5px 8px;
  font-size: 12px;
}
```

- [x] **Step 6: Keep fallback links visually available only in fallback state**

Add:

```css
.paper-actions.is-fallback-only {
  display: flex;
}

.paper-actions:empty {
  display: none;
}
```

- [x] **Step 7: Add responsive breakpoints**

Add `max-width: 1100px` behavior:

```css
@media (max-width: 1100px) {
  .reader-shell {
    grid-template-columns: minmax(184px, 210px) minmax(0, 1fr) 0;
  }

  .reader-shell:not(.is-mobile-note-open) .note-panel {
    opacity: 0;
    pointer-events: none;
    transform: translateX(10px);
  }
}
```

Replace mobile breakpoint with `max-width: 860px`, and ensure:

```css
@media (max-width: 860px) {
  .reader-shell,
  .reader-shell.is-left-collapsed,
  .reader-shell.is-note-collapsed,
  .reader-shell.is-left-collapsed.is-note-collapsed {
    display: block;
    padding: 8px;
  }

  .reader-sidebar,
  .note-panel,
  .section-rail,
  .reader-shell.is-left-collapsed .section-rail {
    display: none;
  }

  .reader-shell.is-mobile-left-open .reader-sidebar {
    display: block;
    position: fixed;
    left: 8px;
    right: 8px;
    top: 72px;
    z-index: 45;
    height: min(68vh, 560px);
  }

  .reader-shell.is-mobile-left-open .directory-surface {
    height: 100%;
  }
}
```

## Task 4: Update JS rendering and state behavior

**Files:**
- Modify: `papers/shared/reader.js`
- Test: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Extract fallback-only link renderer**

Add:

```js
function renderPaperLinks(paperData) {
  return [
    paperData.sourceFile || state.currentPaper.localFile
      ? `<a href="${escapeHtml(paperData.sourceFile ?? state.currentPaper.localFile)}">原文</a>`
      : "",
    paperData.noteFile || state.currentPaper.noteFile
      ? `<a href="${escapeHtml(paperData.noteFile ?? state.currentPaper.noteFile)}">中文精读</a>`
      : "",
    paperData.source || state.currentPaper.source
      ? `<a href="${escapeHtml(paperData.source ?? state.currentPaper.source)}">来源</a>`
      : ""
  ].filter(Boolean).join("");
}
```

- [x] **Step 2: Remove normal header actions**

Change `renderPaperHeader(reading)` so normal chunked reading renders:

```js
<div class="paper-actions"></div>
```

and does not include `原文` / `中文精读` / `来源`.

- [x] **Step 3: Keep links in no-chunk fallback**

In `renderNoChunkPaper()`, after `renderPaperHeader(null)`, populate:

```js
const actions = els.paperHeader.querySelector(".paper-actions");
if (actions) {
  actions.classList.add("is-fallback-only");
  actions.innerHTML = renderPaperLinks(state.currentPaper);
}
```

- [x] **Step 4: Make note rendering stable**

Replace `updateNoteSurface` with a root-stable function pair:

```js
function renderNoteSurface(surface, note) {
  surface.textContent = note ?? "";
  surface.classList.remove("is-changing");
}

function updateNoteSurface(chunkId, note) {
  const label = chunkId ? `Parallel note · ${chunkId}` : "Parallel note";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.classList.add("is-changing");
    window.setTimeout(() => renderNoteSurface(surface, note), 90);
  }
}
```

- [x] **Step 5: Track active section separately from hover**

Add:

```js
function updateActiveSectionRail(sectionId) {
  for (const line of els.sectionLines.children) {
    line.classList.toggle("is-active", line.dataset.sectionId === sectionId);
  }
}
```

Then update `setActiveChunk` to call `updateActiveSectionRail(chunk?.sectionId)` instead of inlining section line toggles.

- [x] **Step 6: Avoid broken figure images**

Keep `renderFigure` using `hasFile` and ensure the `img` branch only renders when `Boolean(figure.file)` is true. The fallback branch must use `.figure-placeholder`, not an empty image.

- [x] **Step 7: Add responsive state sync**

Add:

```js
function syncResponsiveState() {
  const narrow = window.matchMedia("(max-width: 1100px)").matches;
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  els.shell.classList.toggle("is-note-collapsed", narrow && !mobile);
  if (!mobile) {
    els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
  }
}
```

Call `syncResponsiveState()` in `bindControls()` and on `resize`.

- [x] **Step 8: Update toolbar button breakpoints**

Change mobile detection in click handlers from `max-width: 760px` to `max-width: 860px`.

Left toggle behavior:

```js
if (window.matchMedia("(max-width: 860px)").matches) {
  els.shell.classList.toggle("is-mobile-left-open");
  els.shell.classList.remove("is-left-collapsed");
  return;
}
els.shell.classList.toggle("is-left-collapsed");
```

Right toggle behavior:

```js
if (window.matchMedia("(max-width: 860px)").matches) {
  els.shell.classList.toggle("is-mobile-note-open");
  return;
}
els.shell.classList.toggle("is-note-collapsed");
```

## Task 5: Verify behavior

**Files:**
- Verify: `tests/paper-reader-requirements.mjs`
- Verify: `tests/papers-requirements.mjs`
- Verify: `tests/homepage-requirements.mjs`

- [x] **Step 1: Run static tests**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit `0`.

- [x] **Step 2: Start or reuse local preview**

Run a local static server if none is already serving port `4173`:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Expected: `http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/` serves the reader page.

- [x] **Step 3: Browser smoke check**

Use browser automation to verify:

```js
{
  desktop: {
    url: "http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/",
    viewport: "1280x820",
    expected: [
      "no horizontal overflow",
      "paper directory visible",
      "note panel visible",
      "search placeholder is Searching...",
      "normal header has no 原文/中文精读/来源 links",
      "note panel root remains visible with blank note"
    ]
  },
  mobile: {
    viewport: "390x844",
    expected: [
      "paper directory hidden by default",
      "note panel hidden by default",
      "section rail hidden",
      "left toggle opens paper directory list, not section rail",
      "body width equals viewport width"
    ]
  }
}
```

Expected: all smoke checks pass without console errors.

## Task 6: Commit implementation

**Files:**
- Stage only:
  - `docs/superpowers/plans/2026-07-03-paper-reader-shell-refinement.md`
  - `papers/brain-memory-for-ai-agents/index.html`
  - `papers/shared/reader.css`
  - `papers/shared/reader.js`
  - `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Review intended diff**

Run:

```bash
git status --short
git diff -- docs/superpowers/plans/2026-07-03-paper-reader-shell-refinement.md papers/brain-memory-for-ai-agents/index.html papers/shared/reader.css papers/shared/reader.js tests/paper-reader-requirements.mjs
```

Expected: only the planned files are modified or added, plus unrelated untracked `projects/uestc-fyp-topics-2026-2027/` remains untouched.

- [x] **Step 2: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-07-03-paper-reader-shell-refinement.md papers/brain-memory-for-ai-agents/index.html papers/shared/reader.css papers/shared/reader.js tests/paper-reader-requirements.mjs
git commit -m "Refine paper reader shell"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: layout, toolbar, glass visual system, note stability, section rail, responsive controls, content chrome, figures, and tests are covered by Tasks 1-5.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation step remains.
- Scope check: this plan stays within reader shell refinement and does not rewrite paper chunk content.
