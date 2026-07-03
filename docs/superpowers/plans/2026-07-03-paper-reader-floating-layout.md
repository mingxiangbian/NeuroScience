# Paper Reader Floating Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `papers/brain-memory-for-ai-agents/` 阅读器改为 floating reader layout：左侧目录是 sticky floating card，顶部是模块化功能岛，搜索缩短放到右侧工具组，正文排版更适合长文阅读。

**Architecture:** 只改静态 reader 外壳，不改数据和搜索逻辑。`papers/brain-memory-for-ai-agents/index.html` 只移动搜索框到右侧工具组；`papers/shared/reader.css` 负责布局、视觉和响应式；`tests/paper-reader-requirements.mjs` 锁定需求。

**Tech Stack:** Static HTML/CSS/JS, Node.js assertion tests, GitHub Pages static runtime.

---

## File Structure

- Modify: `papers/brain-memory-for-ai-agents/index.html`
  - 将 `.toolbar-search` 从 toolbar 中间独立区域移动进 `.toolbar-right`，让搜索成为右侧工具组的一部分。
- Modify: `papers/shared/reader.css`
  - `.reader-toolbar` 从整条玻璃栏改为透明 flex 容器。
  - `.toolbar-left` 和 `.toolbar-right` 变成独立 modular navigation islands。
  - `.toolbar-search` 缩短到 `clamp(180px, 18vw, 260px)`。
  - `.reader-sidebar` 和 `.directory-surface` 改为 sticky floating card，内容驱动高度，最大 `76vh`。
  - `.paper-nav-item[aria-current="true"]` 增加暗红左边条。
  - `.paper-header`、`.chunk-list`、`.chunk` 使用 `ch` 限制阅读行宽。
- Modify: `tests/paper-reader-requirements.mjs`
  - 增加断言：搜索属于右侧工具组、toolbar 是 modular、目录是 floating card、正文 max-width 使用 `ch`、active state 有暗红边条。

## Task 1: Lock Floating Layout Requirements In Tests

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Add failing HTML and CSS assertions**

Add these assertions after the existing toolbar/search assertions:

```js
assert.match(html, /<div class="toolbar-right">[\s\S]*<div class="toolbar-search">[\s\S]*id="global-search"[\s\S]*id="toggle-theme"/, "search should live inside the right modular toolbar group");
assert.doesNotMatch(html, /<\/div>\s*<div class="toolbar-search">[\s\S]*<\/div>\s*<div class="toolbar-right">/, "search should no longer be a center toolbar column");
```

Add these assertions after the existing CSS glass/layout assertions:

```js
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*display:\s*flex/, "toolbar should be a modular flex container, not a three-column monolithic bar");
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*background:\s*transparent/, "toolbar container should not render as one full-width glass bar");
assert.match(css, /\.toolbar-left,\s*\.toolbar-right\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "toolbar groups should render as independent glass islands");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*width:\s*clamp\(180px,\s*18vw,\s*260px\)/, "search should be a compact right-side tool");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*top:\s*calc\(var\(--toolbar-offset\) \+ 5vh\)/, "paper directory should stick as a floating card below the toolbar");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*height:\s*auto/, "paper directory wrapper should not be full-height");
assert.match(css, /\.directory-surface\s*\{[\s\S]*max-height:\s*min\(76vh,\s*calc\(100vh - var\(--toolbar-offset\) - 36px\)\)/, "paper directory should use content-driven height with a viewport cap");
assert.match(css, /\.directory-surface\s*\{[\s\S]*height:\s*auto/, "paper directory surface should not fill the viewport");
assert.match(css, /\.paper-nav-item\[aria-current="true"\]::before\s*\{[\s\S]*background:\s*var\(--reader-red\)/, "active paper should use a dark red left accent");
assert.match(css, /\.paper-header\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "paper header should use a readable ch-based width");
assert.match(css, /\.chunk-list\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "chunk list should use a readable ch-based width");
```

- [x] **Step 2: Run the requirement test and verify RED**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because search is still centered, toolbar is still a full glass bar, and left directory still fills the viewport.

## Task 2: Implement Modular Toolbar And Compact Search

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`
- Modify: `papers/shared/reader.css`

- [x] **Step 1: Move search into the right toolbar group**

Change toolbar structure from:

```html
<div class="toolbar-search">
  <input id="global-search" type="search" autocomplete="off" placeholder="Searching..." aria-label="全局语义搜索" />
  <div class="search-results" id="search-results" hidden></div>
</div>

<div class="toolbar-right">
```

to:

```html
<div class="toolbar-right">
  <div class="toolbar-search">
    <input id="global-search" type="search" autocomplete="off" placeholder="Searching..." aria-label="全局语义搜索" />
    <div class="search-results" id="search-results" hidden></div>
  </div>
```

- [x] **Step 2: Replace full toolbar bar with modular islands**

Change `.reader-toolbar` to:

```css
.reader-toolbar {
  grid-area: toolbar;
  position: sticky;
  top: 10px;
  z-index: 30;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  background: transparent;
  padding: 0;
  pointer-events: none;
}
```

Change `.toolbar-left, .toolbar-right` to include island visuals:

```css
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--reader-glass-edge);
  border-radius: 16px;
  background: var(--reader-glass);
  padding: 7px;
  backdrop-filter: var(--reader-panel-blur);
  -webkit-backdrop-filter: var(--reader-panel-blur);
  box-shadow:
    inset 0 1px 0 var(--reader-glass-highlight),
    inset 0 -1px 0 rgba(19, 45, 42, 0.05),
    inset 0 0 26px rgba(255, 255, 255, 0.12),
    0 14px 40px var(--reader-glass-shadow);
  pointer-events: auto;
}
```

Keep `.toolbar-right { justify-content: flex-end; }`.

- [x] **Step 3: Compact the search field**

Change `.toolbar-search` to:

```css
.toolbar-search {
  position: relative;
  width: clamp(180px, 18vw, 260px);
}
```

Reduce search input padding:

```css
padding: 9px 14px;
```

- [x] **Step 4: Run requirement test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL if floating directory and typography are not implemented yet; toolbar/search assertions should now pass.

## Task 3: Implement Floating Directory And Reading Typography

**Files:**
- Modify: `papers/shared/reader.css`

- [x] **Step 1: Convert reader sidebar to floating card positioning**

Change `.reader-sidebar` to:

```css
.reader-sidebar {
  grid-area: directory;
  position: sticky;
  top: calc(var(--toolbar-offset) + 5vh);
  align-self: start;
  min-width: 0;
  height: auto;
}
```

Change `.directory-surface, .section-rail` shared block from fixed `height` to:

```css
max-height: min(76vh, calc(100vh - var(--toolbar-offset) - 36px));
overflow: auto;
```

Then set `.directory-surface` to:

```css
.directory-surface {
  height: auto;
  padding: 14px;
}
```

Set `.section-rail` to:

```css
.section-rail {
  display: none;
  height: min(58vh, calc(100vh - var(--toolbar-offset) - 70px));
  align-items: center;
  justify-content: center;
}
```

- [x] **Step 2: Add active paper left accent**

Add:

```css
.paper-nav-item {
  position: relative;
}

.paper-nav-item[aria-current="true"] {
  color: var(--reader-ink);
  border-color: rgba(166, 67, 56, 0.18);
  background: rgba(255, 255, 255, 0.28);
  padding-left: 16px;
  box-shadow:
    inset 0 2px 9px rgba(42, 35, 25, 0.1),
    inset 0 0 0 1px rgba(255, 255, 255, 0.22);
}

.paper-nav-item[aria-current="true"]::before {
  position: absolute;
  left: 7px;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 999px;
  background: var(--reader-red);
  content: "";
}
```

- [x] **Step 3: Set readable ch-based content widths**

Change:

```css
.paper-header {
  margin: 6px auto 22px;
  max-width: min(75ch, calc(100vw - 40px));
}

.chunk-list {
  display: grid;
  gap: 28px;
  min-width: 0;
  max-width: min(75ch, calc(100vw - 40px));
  margin: 0 auto;
}
```

Change `.paper-title` font size to:

```css
font-size: clamp(28px, 3.4vw, 48px);
line-height: 1.12;
```

Keep `.source-paragraph` line-height in the `1.7-1.82` range and `.chunk-explanation` line-height in the `1.8-1.9` range.

- [x] **Step 4: Run requirement test and verify GREEN**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: PASS.

## Task 4: Responsive Adjustments And Verification

**Files:**
- Modify: `papers/shared/reader.css`
- Modify: `docs/superpowers/plans/2026-07-03-paper-reader-floating-layout.md`

- [x] **Step 1: Update narrow and mobile CSS**

In `@media (max-width: 1100px)`, keep the sidebar floating but reduce width via existing grid columns.

In `@media (max-width: 860px)`, keep:

```css
.reader-sidebar,
.note-panel,
.section-rail,
.reader-shell.is-left-collapsed .section-rail {
  display: none;
}
```

Update mobile toolbar:

```css
.reader-toolbar {
  gap: 8px;
  top: 8px;
}

.toolbar-left,
.toolbar-right {
  gap: 6px;
  padding: 5px;
}

.toolbar-search {
  width: clamp(132px, 38vw, 190px);
}
```

- [x] **Step 2: Run full static verification**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit 0.

- [x] **Step 3: Run local preview check**

Run:

```bash
curl -I --max-time 3 http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/
```

Expected: HTTP 200. If the server is not running, start the existing static preview server and retry.

- [x] **Step 4: Run browser smoke check**

Use Playwright with system Chrome to verify:

- desktop `1280x800`: no horizontal overflow, `.directory-surface` computed height is below viewport full height, `.reader-toolbar` background is transparent, `.toolbar-search` width is at most `260px`.
- tablet `760x800`: no horizontal overflow.
- mobile `390x844`: `.reader-sidebar`, `.note-panel`, `.section-rail` are hidden by default; `.reader-toolbar` controls do not overlap.

- [x] **Step 5: Mark completed checkboxes**

After each step is completed, change its checkbox in this plan from `- [ ]` to `- [x]`.

- [x] **Step 6: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-07-03-paper-reader-floating-layout.md papers/brain-memory-for-ai-agents/index.html papers/shared/reader.css tests/paper-reader-requirements.mjs
git commit -m "Refine paper reader floating layout"
```

Expected: commit succeeds and unrelated untracked files remain unstaged.
