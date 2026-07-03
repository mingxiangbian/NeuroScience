# Paper Reader Search And Scrollspy Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 paper reader 的折叠章节索引、滚动 active 状态和全局搜索 modal 体验。

**Architecture:** 保持现有静态 reader 架构：`index.html` 提供结构，`reader.css` 负责响应式视觉，`reader.js` 负责本地搜索和 scrollspy。数据仍来自现有 `manifest.json`、`paper.json`、`chunks.json`、`notes.json`、`embeddings.json`，不新增后端或 schema。

**Tech Stack:** 静态 HTML、CSS、vanilla JS、Node.js 断言测试。

---

## File Structure

- Modify: `tests/paper-reader-requirements.mjs`
  - 将旧的“折叠目录仍是玻璃卡片”和 `no found` 断言改成新搜索/scrollspy 目标。
- Modify: `papers/brain-memory-for-ai-agents/index.html`
  - 给搜索遮罩补充稳定 id，方便 JS 绑定点击关闭。
- Modify: `papers/shared/reader.css`
  - 去掉折叠 section rail 卡片感。
  - 增加 centered search modal、统一结果条、关键词高亮和移动端宽度规则。
- Modify: `papers/shared/reader.js`
  - 增加 search modal open/close helper。
  - 增加 viewport geometry scrollspy。
  - 增加 query snippet 和 highlight helper。

## Task 1: 更新需求测试

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: 写入失败测试**

将旧断言替换为以下行为目标：

```js
const sectionRailRule = css.match(/\.section-rail\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionLineRule = css.match(/\.section-line\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionLineHoverRule = css.match(/\.section-line:hover\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionNeighborRule = css.match(/\.section-line\.is-neighbor\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionActiveRule = css.match(/\.section-line\.is-active\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";

assert.match(html, /id="search-overlay"/, "search overlay should expose a stable click target");
assert.doesNotMatch(sectionRailRule, /border:\s*1px solid var\(--reader-glass-edge\)/, "collapsed section rail should not keep a card border");
assert.match(sectionRailRule, /background:\s*transparent/, "collapsed section rail should sit directly on the page canvas");
assert.doesNotMatch(sectionRailRule, /box-shadow:/, "collapsed section rail should not render as a floating card");
assert.match(sectionLineRule, /width:\s*18px/, "section lines should share a stable base length");
assert.match(sectionLineHoverRule, /width:\s*36px/, "hovered section line should lengthen");
assert.match(sectionNeighborRule, /width:\s*28px/, "neighbor section lines should lengthen only on hover ripple");
assert.doesNotMatch(sectionNeighborRule, /background:/, "neighbor section lines should not darken");
assert.match(sectionActiveRule, /background:\s*rgba\(24,\s*60,\s*73,\s*0\.62\)/, "active section should darken");
assert.doesNotMatch(sectionActiveRule, /width:|height:/, "active section should not lengthen in the static state");
```

新增搜索 modal 和 scrollspy 断言：

```js
assert.match(css, /\.reader-shell\.is-searching \.search-focus-layer\s*\{[\s\S]*pointer-events:\s*auto/, "search overlay should accept outside-click dismissal");
assert.match(css, /\.reader-shell\.is-searching \.toolbar-search\s*\{[\s\S]*position:\s*fixed[\s\S]*width:\s*min\(760px,\s*calc\(100vw - 48px\)\)/, "active search should become a centered modal input");
assert.match(css, /\.reader-shell\.is-searching \.search-results\s*\{[\s\S]*position:\s*fixed[\s\S]*width:\s*min\(760px,\s*calc\(100vw - 48px\)\)/, "active search results should align with the modal search width");
assert.match(css, /\.result-title,\s*\.result-snippet\s*\{[\s\S]*overflow:\s*hidden[\s\S]*text-overflow:\s*ellipsis/, "search result title and snippet should be clamped");
assert.match(css, /\.result-highlight\s*\{[\s\S]*background:\s*rgba\(166,\s*67,\s*56,\s*0\.16\)/, "search keyword highlights should be subtle");
assert.match(js, /searchOverlay:\s*document\.querySelector\("#search-overlay"\)/, "reader should bind the search overlay for outside-click dismissal");
assert.match(js, /function openSearchModal/, "reader should isolate opening the search modal");
assert.match(js, /function closeSearchModal/, "reader should isolate closing the search modal");
assert.match(js, /function getActiveChunkByViewport/, "reader should compute active chunk from viewport geometry");
assert.match(js, /getBoundingClientRect\(\)[\s\S]*window\.innerHeight \/ 2/, "scrollspy should use viewport geometry");
assert.match(js, /function getSearchSnippet/, "reader should build search snippets around query terms");
assert.match(js, /function highlightSearchTerms/, "reader should highlight matched search terms");
assert.match(js, /No results found/, "reader should use the requested no-result wording");
assert.doesNotMatch(js, /no found/, "reader should remove the old broken no found copy");
```

- [x] **Step 2: 运行测试确认失败**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL，失败点来自新断言要求的 `search-overlay`、modal CSS、scrollspy helper 或 `No results found`。

## Task 2: HTML 和 CSS 视觉实现

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`
- Modify: `papers/shared/reader.css`

- [x] **Step 1: 补充搜索 overlay id**

在 reader shell 内将遮罩改成：

```html
<div class="search-focus-layer" id="search-overlay" aria-hidden="true"></div>
```

- [x] **Step 2: 去掉 section rail 卡片感**

将 `.directory-surface, .section-rail` 拆开：`.directory-surface` 保留玻璃卡片；`.section-rail` 使用透明背景、无边框、无大阴影。

关键 CSS：

```css
.section-rail {
  display: none;
  height: min(58vh, calc(100vh - var(--toolbar-offset) - 70px));
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 14px;
  padding: 10px 6px;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.section-line.is-active {
  background: rgba(24, 60, 73, 0.62);
}
```

- [x] **Step 3: 增加全局搜索 modal 样式**

保留普通状态下右侧紧凑 search，给 `.reader-shell.is-searching` 增加 fixed centered 样式。

关键 CSS：

```css
.reader-shell.is-searching .search-focus-layer {
  opacity: 1;
  pointer-events: auto;
}

.reader-shell.is-searching .toolbar-search {
  position: fixed;
  left: 50%;
  top: clamp(72px, 12vh, 112px);
  z-index: 45;
  width: min(760px, calc(100vw - 48px));
  transform: translateX(-50%);
}

.reader-shell.is-searching .search-results {
  position: fixed;
  left: 50%;
  top: calc(clamp(72px, 12vh, 112px) + 62px);
  width: min(760px, calc(100vw - 48px));
  transform: translateX(-50%);
}
```

移动端添加：

```css
@media (max-width: 860px) {
  .reader-shell.is-searching .toolbar-search,
  .reader-shell.is-searching .search-results {
    width: calc(100vw - 28px);
  }
}
```

## Task 3: JS 交互实现

**Files:**
- Modify: `papers/shared/reader.js`

- [x] **Step 1: 绑定 overlay 和 search helper**

在 `els` 增加：

```js
searchOverlay: document.querySelector("#search-overlay"),
```

新增：

```js
function openSearchModal() {
  els.shell.classList.add("is-searching");
}

function closeSearchModal() {
  els.searchResults.hidden = true;
  els.shell.classList.remove("is-searching");
}
```

- [x] **Step 2: 实现 viewport geometry scrollspy**

新增：

```js
function getActiveChunkByViewport() {
  const chunks = [...document.querySelectorAll(".chunk")];
  const viewportCenter = window.innerHeight / 2;
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const chunk of chunks) {
    const rect = chunk.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
    const distance = rect.top <= viewportCenter && rect.bottom >= viewportCenter
      ? 0
      : Math.min(Math.abs(rect.top - viewportCenter), Math.abs(rect.bottom - viewportCenter));
    if (distance < bestDistance) {
      best = chunk;
      bestDistance = distance;
    }
  }
  return best?.dataset.chunkId ?? chunks[0]?.dataset.chunkId;
}

function updateActiveChunkFromViewport(reading) {
  const chunkId = getActiveChunkByViewport();
  if (chunkId) setActiveChunk(reading, chunkId);
}
```

`observeChunks(reading)` 中继续保留 `IntersectionObserver`，但 active 更新改为调用 `updateActiveChunkFromViewport(reading)`，并绑定 `scroll`/`resize`。

- [x] **Step 3: 实现搜索结果片段和高亮**

新增：

```js
function getSearchSnippet(item, query) {
  const fields = [item.chunk.zhExplanation, item.chunk.sourceText].filter(Boolean);
  const lowerQuery = query.toLowerCase();
  for (const field of fields) {
    const lowerField = field.toLowerCase();
    const index = lowerField.indexOf(lowerQuery);
    if (index >= 0) {
      const start = Math.max(0, index - 60);
      const end = Math.min(field.length, index + lowerQuery.length + 120);
      return `${start > 0 ? "..." : ""}${field.slice(start, end)}${end < field.length ? "..." : ""}`;
    }
  }
  return fields[0]?.slice(0, 180) ?? "";
}

function highlightSearchTerms(text, query) {
  const escaped = escapeHtml(text);
  const terms = query.trim().split(/\s+/).filter(Boolean).map(escapeRegExp);
  if (terms.length === 0) return escaped;
  return escaped.replace(new RegExp(`(${terms.join("|")})`, "gi"), `<mark class="result-highlight">$1</mark>`);
}
```

并在 `runSearch()` 中改成：

```js
if (!trimmed) {
  els.searchResults.hidden = true;
  els.searchResults.innerHTML = "";
  return;
}

if (results.length === 0) {
  els.searchResults.innerHTML = `<div class="result-empty">No results found</div>`;
  return;
}
```

## Task 4: 验证和整理

**Files:**
- Test: `tests/paper-reader-requirements.mjs`
- Test: `tests/papers-requirements.mjs`
- Test: `tests/homepage-requirements.mjs`

- [x] **Step 1: 运行需求测试**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: 四个命令 exit 0。

- [x] **Step 2: 本地视觉检查**

Run:

```bash
node -e "console.log('Use existing preview at http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/')"
```

Expected: 用户当前预览页面可刷新检查。桌面搜索居中，移动端无横向溢出，折叠横线不再像卡片。

- [x] **Step 3: 汇报范围**

Final response 用中文说明：

- 已写入 plan。
- 已实现搜索 modal、scrollspy 和折叠目录线视觉。
- 列出运行过的验证命令。
- 明确未触碰 manifest、reading 数据、后端和 Papers 首页。
