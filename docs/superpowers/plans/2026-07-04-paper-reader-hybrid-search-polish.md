# Paper Reader Hybrid Search Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 paper reader 搜索优化为克制的 hybrid search 体验，修复结果溢出、视觉噪音、顶部控件尺寸不齐和低相关结果误返回。

**Architecture:** 保持现有静态 reader：`index.html` 只补充 spinner 容器，`reader.css` 处理统一控件和搜索结果样式，`reader.js` 在本地 `state.searchItems` 上计算 lexical score + semantic score。实现不改 reading 数据、不接后端、不引入 provider。

**Tech Stack:** 静态 HTML、CSS、vanilla JS、Node.js assertion tests、Playwright local visual check。

---

## File Structure

- Modify: `tests/paper-reader-requirements.mjs`
  - 增加 hybrid search、debounce、spinner、leading icon、统一列表、无常驻 item shadow 和 toolbar sizing 断言。
- Modify: `papers/brain-memory-for-ai-agents/index.html`
  - 在 search input 旁增加微型 spinner。
- Modify: `papers/shared/reader.css`
  - 引入 toolbar size token、统一顶部控件高度。
  - 将 `#search-results` 改成统一玻璃列表容器，单条结果去掉常驻阴影。
  - 增加 leading icon、spinner、theme transition 和 overflow 防护样式。
- Modify: `papers/shared/reader.js`
  - 增加 debounce timer、loading state。
  - 增加 lexical score、semantic score、hard threshold 和 result type。
  - 渲染 result icon，并保持无结果状态克制。

## Task 1: 更新需求测试

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: 写入失败测试**

新增断言目标：

```js
assert.match(html, /class="search-spinner"[\s\S]*aria-hidden="true"/, "search should include a tiny loading spinner");
assert.match(css, /--toolbar-control-size:\s*42px/, "toolbar controls should share a common height token");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*height:\s*var\(--toolbar-control-size\)/, "search should use the shared toolbar height");
assert.match(css, /\.toolbar-controls\s*\{[\s\S]*height:\s*var\(--toolbar-control-size\)/, "toolbar control island should use the shared toolbar height");
assert.match(css, /\.toolbar-controls \.icon-button\s*\{[\s\S]*width:\s*calc\(var\(--toolbar-control-size\) - 10px\)[\s\S]*height:\s*calc\(var\(--toolbar-control-size\) - 10px\)/, "toolbar buttons should align to the search height");
assert.match(css, /\.search-results\s*\{[\s\S]*border:\s*1px solid var\(--reader-glass-edge\)[\s\S]*box-shadow:\s*0 26px 64px var\(--reader-glass-shadow\)/, "search results should be one unified glass list");
assert.match(css, /\.result-item\s*\{[\s\S]*min-width:\s*0[\s\S]*grid-template-columns:\s*24px minmax\(0,\s*1fr\)/, "result rows should reserve icon space without horizontal overflow");
assert.doesNotMatch(css.match(/\.result-item\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "", /box-shadow:/, "result rows should not have a persistent card shadow");
assert.match(css, /\.result-icon\s*\{[\s\S]*width:\s*18px[\s\S]*height:\s*18px/, "result rows should include leading icons");
assert.match(css, /\.reader-shell\.is-search-loading \.search-spinner\s*\{[\s\S]*opacity:\s*1/, "search loading should reveal the spinner");
assert.match(css, /body,\s*\.toolbar-search,\s*\.toolbar-controls,\s*\.search-results[\s\S]*transition:[\s\S]*color 240ms ease[\s\S]*background 240ms ease[\s\S]*border-color 240ms ease/, "theme changes should transition color, background, and borders");
assert.match(js, /searchDebounceTimer:\s*null/, "reader state should track the search debounce timer");
assert.match(js, /const SEARCH_DEBOUNCE_MS = 260/, "search debounce duration should stay lightweight");
assert.match(js, /const SEMANTIC_SCORE_THRESHOLD = 0\.42/, "semantic-only results should use a hard threshold");
assert.match(js, /function getLexicalScore/, "reader should calculate lexical search scores");
assert.match(js, /function getSemanticScore/, "reader should isolate semantic score calculation");
assert.match(js, /function getHybridSearchResults/, "reader should combine lexical and semantic scores");
assert.match(js, /lexicalScore > 0 \|\| semanticScore >= SEMANTIC_SCORE_THRESHOLD/, "reader should filter low-relevance results");
assert.match(js, /function scheduleSearch/, "reader should debounce search input");
assert.match(js, /function setSearchLoading/, "reader should expose a small loading state");
assert.match(js, /result-icon result-icon--/, "search results should render typed leading icons");
```

- [x] **Step 2: 运行测试确认失败**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL，失败点来自新 spinner、toolbar token、hybrid search helper 或 persistent shadow 断言。

## Task 2: HTML 和 CSS 视觉实现

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`
- Modify: `papers/shared/reader.css`

- [x] **Step 1: 增加 search spinner markup**

在 `<input id="global-search"...>` 与 `<kbd class="search-shortcut">` 之间加入：

```html
<span class="search-spinner" aria-hidden="true"></span>
```

- [x] **Step 2: 统一 toolbar sizing**

在 `:root` 增加：

```css
--toolbar-control-size: 42px;
```

将 `.toolbar-search` 和 `.toolbar-controls` 高度对齐到该 token；`.toolbar-controls .icon-button` 使用 `calc(var(--toolbar-control-size) - 10px)`。

- [x] **Step 3: 搜索结果改为统一玻璃列表**

关键 CSS：

```css
.reader-shell.is-searching .search-results {
  display: block;
  overflow: hidden auto;
  border: 1px solid var(--reader-glass-edge);
  border-radius: 18px;
  background: var(--reader-glass-strong);
  box-shadow: 0 26px 64px var(--reader-glass-shadow);
}

.result-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  min-width: 0;
  width: 100%;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 12px 14px;
}
```

`.result-item` 静默状态不写 `box-shadow`，hover 才允许轻微背景变化。

- [x] **Step 4: leading icon 和 spinner 样式**

新增：

```css
.result-icon {
  width: 18px;
  height: 18px;
}

.search-spinner {
  width: 14px;
  height: 14px;
  opacity: 0;
}

.reader-shell.is-search-loading .search-spinner {
  opacity: 1;
}
```

- [x] **Step 5: theme transition**

只对颜色相关属性加 transition，不使用 `transition: all`。

## Task 3: JS hybrid search 实现

**Files:**
- Modify: `papers/shared/reader.js`

- [x] **Step 1: 增加状态和常量**

新增：

```js
const SEARCH_DEBOUNCE_MS = 260;
const SEMANTIC_SCORE_THRESHOLD = 0.42;

const state = {
  ...
  searchDebounceTimer: null
};
```

- [x] **Step 2: 增加 loading 和 debounce**

新增：

```js
function setSearchLoading(loading) {
  els.shell.classList.toggle("is-search-loading", loading);
}

function scheduleSearch(query) {
  window.clearTimeout(state.searchDebounceTimer);
  const trimmed = query.trim();
  if (!trimmed) {
    setSearchLoading(false);
    runSearch("");
    return;
  }
  setSearchLoading(true);
  state.searchDebounceTimer = window.setTimeout(() => {
    runSearch(trimmed);
    setSearchLoading(false);
  }, SEARCH_DEBOUNCE_MS);
}
```

关闭 modal 时清理 timer。

- [x] **Step 3: 增加 lexical + semantic score**

新增：

```js
function getLexicalScore(item, query) {
  const terms = getSearchTerms(query).map((term) => term.toLowerCase());
  const sectionTitle = getSectionTitle(item.reading, item.chunk.sectionId);
  const weightedFields = [
    [item.paper.title, 5],
    [item.paper.shortTitle, 5],
    [sectionTitle, 4],
    [item.chunk.sourceText, 2],
    [item.chunk.zhExplanation, 2],
    [(item.chunk.keywords ?? []).join(" "), 3]
  ];
  let score = 0;
  for (const [field, weight] of weightedFields) {
    const lower = String(field ?? "").toLowerCase();
    for (const term of terms) {
      if (term && lower.includes(term)) score += weight;
    }
  }
  return score;
}

function getSemanticScore(item, queryVector) {
  return cosineSimilarity(queryVector, item.vector);
}
```

- [x] **Step 4: 替换 runSearch 排序过滤**

新增 `getHybridSearchResults(query)`，过滤条件：

```js
lexicalScore > 0 || semanticScore >= SEMANTIC_SCORE_THRESHOLD
```

排序使用 `lexicalScore * 10 + semanticScore`，再取 `top 8`。

- [x] **Step 5: 渲染 typed leading icon**

结果按钮结构：

```html
<span class="result-icon result-icon--chunk" aria-hidden="true">...</span>
<span class="result-copy">
  <span class="result-title">...</span>
  <span class="result-snippet">...</span>
</span>
```

当前论文结果用 `chunk`，跨论文结果用 `paper`。

## Task 4: 验证

**Files:**
- Test: `tests/paper-reader-requirements.mjs`
- Test: `tests/papers-requirements.mjs`
- Test: `tests/homepage-requirements.mjs`

- [x] **Step 1: 运行测试**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: 四个命令 exit 0。

- [x] **Step 2: 浏览器视觉检查**

用本地预览检查：

- desktop `1280x800`：搜索结果无水平滚动条，item 没有独立阴影堆叠。
- mobile `390x844`：结果 icon 不挤压标题和 snippet，无横向溢出。
- 随便输入无关词：显示小号 `No results found`，不吐噪音结果。

- [x] **Step 3: 整理状态**

确认 `git status --short --branch` 只显示本轮目标文件和既有无关未跟踪目录。
