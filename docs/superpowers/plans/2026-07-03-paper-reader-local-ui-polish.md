# Paper Reader Local UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留现有水墨 floating reader layout，只修正搜索框粘连、左侧目录层级倒置、折叠按钮位置和左上 logo 玻璃感。

**Architecture:** `papers/brain-memory-for-ai-agents/index.html` 做轻量结构调整：搜索框保留在右上区域但成为独立组件，目录折叠按钮移动到目录标题旁，折叠后的章节细线区保留一个本地恢复按钮。`papers/shared/reader.css` 负责视觉解耦、父子层级、logo 扁平化和移动端适配。`papers/shared/reader.js` 只把目录收放绑定从单个按钮扩展为同一类本地按钮，不改 reader 数据、chunk、embedding 或搜索算法。`tests/paper-reader-requirements.mjs` 锁定结构与样式。

**Tech Stack:** Static HTML/CSS/JS, inline SVG icons, Node.js assertion tests, GitHub Pages static runtime.

---

## File Structure

- Modify: `tests/paper-reader-requirements.mjs`
  - 增加断言：placeholder 为 `Search`，搜索框包含放大镜和 `⌘ K`，搜索框不再和主题/笔记按钮共享同一玻璃岛。
  - 增加断言：`#toggle-left` 位于目录标题行，不在 `.toolbar-left`。
  - 增加断言：目录标题比论文项更强，logo 使用 flat treatment。
- Modify: `papers/brain-memory-for-ai-agents/index.html`
  - 从 `.toolbar-left` 移除 `#toggle-left`。
  - 在 `.directory-surface` 内新增 `.directory-header`，放置 `.directory-title` 和 `#toggle-left`。
  - 在 `.toolbar-search` 中加入 inline magnifying-glass SVG 和 `<kbd>⌘ K</kbd>`。
  - 将 placeholder 改为 `Search`。
  - 将 `.toolbar-right` 分成独立 `.toolbar-search` 和 `.toolbar-controls`。
- Modify: `papers/shared/reader.css`
  - `.toolbar-right` 成为透明 wrapper，不再自身显示玻璃岛。
  - `.toolbar-search` 成为独立 input component。
  - `.toolbar-controls` 承载主题/笔记按钮的玻璃岛。
  - `.project-mark` flat 化，hover 只改变透明度/颜色，不出现玻璃背景。
  - `.directory-header` 做父级标题行，`.directory-title` 增大加粗，`.directory-toggle` 保持就近控制。
- Modify: `papers/shared/reader.js`
  - 将左侧目录收放事件从 `#toggle-left` 扩展为 `[data-toggle-left]`，保证目录折叠后仍可在章节细线区恢复。

## Task 1: Lock Local UI Polish Requirements In Tests

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Add failing assertions**

Add assertions near the existing toolbar and search checks:

```js
assert.match(html, /placeholder="Search"/, "reader search placeholder should be the concise label Search");
assert.match(html, /class="search-icon"[\s\S]*id="global-search"[\s\S]*class="search-shortcut">⌘ K<\/kbd>/, "search should include a magnifying glass icon and keyboard hint");
assert.match(html, /<div class="toolbar-right">[\s\S]*<div class="toolbar-search">[\s\S]*<\/div>\s*<div class="toolbar-controls">[\s\S]*id="toggle-theme"[\s\S]*id="toggle-note"/, "search should be visually decoupled from the right toolbar controls");
const toolbarLeftMarkup = html.match(/<div class="toolbar-left">(?<body>[\s\S]*?)<\/div>/)?.groups?.body ?? "";
assert.doesNotMatch(toolbarLeftMarkup, /id="toggle-left"/, "paper directory collapse control should not live in the top-left toolbar island");
assert.match(html, /<div class="directory-header">[\s\S]*class="directory-title">记忆与智能体[\s\S]*id="toggle-left"/, "paper directory collapse control should live next to the project title");
assert.match(html, /class="icon-button rail-toggle"[\s\S]*data-toggle-left/, "collapsed section rail should include a local restore control");
assert.match(js, /querySelectorAll\("\[data-toggle-left\]"\)/, "reader should bind all local left-directory controls");
```

Add assertions near the existing CSS toolbar/directory checks:

```js
assert.match(css, /\.toolbar-right\s*\{[\s\S]*background:\s*transparent/, "right toolbar wrapper should not merge search and controls into one glass island");
assert.match(css, /\.toolbar-controls\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "right toolbar buttons should keep their own glass control island");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "search should render as its own glass input component");
assert.match(css, /\.search-icon\s*\{[\s\S]*width:\s*16px/, "search input should include a compact magnifying glass icon");
assert.match(css, /\.search-shortcut\s*\{[\s\S]*font-size:\s*11px/, "search input should include a quiet keyboard shortcut hint");
assert.match(css, /\.directory-header\s*\{[\s\S]*display:\s*flex/, "directory title and collapse action should share a local header row");
assert.match(css, /\.directory-title\s*\{[\s\S]*font-size:\s*16px[\s\S]*font-weight:\s*760/, "directory title should read as the parent category");
assert.match(css, /\.paper-nav-item\s*\{[\s\S]*font-size:\s*13px/, "paper titles should read as children under the project category");
assert.match(css, /\.project-mark\s*\{[\s\S]*background:\s*transparent[\s\S]*box-shadow:\s*none/, "project logo should use a flat treatment without glass chrome");
```

- [x] **Step 2: Run test to verify RED**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because placeholder is still `Searching...`, search has no icon/kbd, collapse button is still in the top-left toolbar, and CSS has not added the local directory header rules.

## Task 2: Implement Structure Changes

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`

- [x] **Step 1: Move left collapse button into the directory header**

Replace the top-left toolbar content with only the project mark:

```html
<div class="toolbar-left">
  <a class="project-mark" href="../" aria-label="返回文献阁">
    ...
  </a>
</div>
```

Replace the directory title with a local header row:

```html
<div class="directory-header">
  <p class="directory-title">记忆与智能体</p>
  <button class="icon-button directory-toggle" id="toggle-left" type="button" aria-label="收放论文目录" data-toggle-left>
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</div>
```

Add a restore control inside the collapsed section rail:

```html
<button class="icon-button rail-toggle" type="button" aria-label="展开论文目录" data-toggle-left>
  ...
</button>
```

- [x] **Step 2: Make search its own component**

Change right toolbar markup to:

```html
<div class="toolbar-right">
  <div class="toolbar-search">
    <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m21 21-4.2-4.2M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
    <input id="global-search" type="search" autocomplete="off" placeholder="Search" aria-label="全局语义搜索" />
    <kbd class="search-shortcut">⌘ K</kbd>
    <div class="search-results" id="search-results" hidden></div>
  </div>
  <div class="toolbar-controls">
    ...
  </div>
</div>
```

- [x] **Step 3: Run requirement test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL until CSS styles are implemented.

## Task 3: Implement Visual Treatment

**Files:**
- Modify: `papers/shared/reader.css`
- Modify: `papers/shared/reader.js`

- [x] **Step 1: Decouple search and right controls**

Change `.toolbar-right` to a transparent wrapper:

```css
.toolbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  background: transparent;
  padding: 0;
  border: 0;
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}
```

Add `.toolbar-controls` as the glass button island:

```css
.toolbar-controls {
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
}
```

- [x] **Step 2: Style independent search input**

Update `.toolbar-search` and children:

```css
.toolbar-search {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  width: clamp(190px, 20vw, 280px);
  border: 1px solid var(--reader-glass-edge);
  border-radius: 999px;
  background: var(--reader-glass);
  padding: 7px 10px;
  backdrop-filter: var(--reader-panel-blur);
  -webkit-backdrop-filter: var(--reader-panel-blur);
  box-shadow:
    inset 0 1px 0 var(--reader-glass-highlight),
    0 14px 40px var(--reader-glass-shadow);
}

.search-icon {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  color: var(--reader-ink-muted);
}

.toolbar-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  background: transparent;
  padding: 2px 0;
}

.search-shortcut {
  flex: 0 0 auto;
  color: var(--reader-ink-muted);
  font-size: 11px;
}
```

- [x] **Step 3: Strengthen directory hierarchy**

Add:

```css
.directory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.directory-title {
  margin: 0;
  color: var(--reader-ink);
  font-size: 16px;
  font-weight: 760;
}

.directory-toggle {
  width: 32px;
  height: 32px;
}

.paper-nav-item {
  font-size: 13px;
}
```

- [x] **Step 4: Flatten project mark**

Update `.project-mark` so it has no glass chrome:

```css
.project-mark {
  border-color: transparent;
  background: transparent;
  box-shadow: none;
}

.project-mark:hover {
  border-color: transparent;
  background: transparent;
  opacity: 0.72;
}
```

- [x] **Step 5: Update mobile spacing**

In the mobile media query, set:

```css
.toolbar-right {
  gap: 8px;
}

.toolbar-controls {
  gap: 6px;
  padding: 5px;
}

.toolbar-search {
  width: clamp(142px, 40vw, 190px);
  padding: 6px 9px;
}

.search-shortcut {
  display: none;
}
```

- [x] **Step 6: Bind all local left-directory controls**

In `reader.js`, query all `[data-toggle-left]` controls and bind the existing left-panel toggle behavior to each one.

- [x] **Step 7: Run requirement test and verify GREEN**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: PASS.

## Task 4: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-07-03-paper-reader-local-ui-polish.md`

- [x] **Step 1: Run static verification**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit 0.

- [x] **Step 2: Run local preview check**

Run:

```bash
curl -I --max-time 3 http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/
```

Expected: HTTP 200. If the server is unavailable, start the existing static preview server and retry.

- [x] **Step 3: Run browser smoke check**

Use Playwright with system Chrome to verify:

- desktop `1280x800`: no horizontal overflow, search and controls do not overlap, search width is at most `280px`, `#toggle-left` is inside `.directory-header`.
- mobile `390x844`: no horizontal overflow, search and controls do not overlap, `.search-shortcut` is hidden, left sidebar remains hidden by default.

- [x] **Step 4: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-07-03-paper-reader-local-ui-polish.md papers/brain-memory-for-ai-agents/index.html papers/shared/reader.css papers/shared/reader.js tests/paper-reader-requirements.mjs
git commit -m "Polish paper reader local controls"
```

Expected: commit succeeds and unrelated untracked files remain unstaged.
