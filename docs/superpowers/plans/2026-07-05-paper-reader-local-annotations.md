# Paper Reader Local Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Paper Representation 阅读器中实现浏览器本地保存的英文原文高亮和右侧平行批注。

**Architecture:** 继续使用静态 GitHub Pages 前端，不新增后端和仓库写回。`reader.js` 增加一个 localStorage-backed annotation runtime，选区浮层负责创建高亮/批注，右侧现有 note surface 负责展示当前 chunk 的原始 note 和本地 annotation。

**Tech Stack:** Static HTML/CSS/JS, `localStorage`, DOM Selection/Range API, existing `node` requirement tests.

---

## File Structure

- Modify: `tests/paper-reader-requirements.mjs`
  - 增加 annotation runtime、CSS、删除确认、无后端写回的静态断言。
- Modify: `papers/shared/reader.js`
  - 增加 annotation state、storage helpers、selection toolbar、highlight restoration、note editor、delete popover。
- Modify: `papers/shared/reader.css`
  - 增加 source highlight、annotation toolbar、右侧引用/批注编辑区、detached 状态样式。
- Modify: `papers/PAPER_IMPORT_STANDARD.md`
  - 增加 runtime local annotations 说明，明确它不属于 reading package 源文件。

## Task 1: Add Failing Annotation Requirements

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [ ] **Step 1: Add reader JS assertions**

Add assertions near the existing reader JS behavior checks:

```js
assert.match(js, /ANNOTATION_STORAGE_PREFIX = "paperReader\.annotations\.v1"/, "reader should define a versioned local annotation storage prefix");
assert.match(js, /function getAnnotationStorageKey/, "reader should isolate local annotation storage keys");
assert.match(js, /function loadAnnotations/, "reader should load local annotations from localStorage");
assert.match(js, /function saveAnnotations/, "reader should save local annotations to localStorage");
assert.match(js, /function getAnnotationsForChunk/, "reader should filter annotations by active paper and chunk");
assert.match(js, /function createAnnotationFromSelection/, "reader should create annotations from selected source text");
assert.match(js, /function applyHighlights/, "reader should restore source highlights after render");
assert.match(js, /function updateAnnotationNote/, "reader should update annotation notes live");
assert.match(js, /function deleteAnnotation/, "reader should support deleting highlights and annotations");
assert.match(js, /\.chunk-source-card/, "annotation selection should be scoped to English source cards");
assert.match(js, /Highlight/, "selection toolbar should expose a Highlight action");
assert.match(js, /Note/, "selection toolbar should expose a Note action");
assert.match(js, /只删除高亮，保留笔记/, "delete confirmation should allow keeping the note");
assert.match(js, /高亮和批注一起删除/, "delete confirmation should allow deleting both highlight and note");
assert.doesNotMatch(js, /githubToken|Authorization|contents\/|repos\/|gitHub/i, "local annotations should not write to GitHub");
```

- [ ] **Step 2: Add reader CSS assertions**

Add assertions near note and chunk CSS checks:

```js
assert.match(css, /\.annotation-toolbar/, "reader CSS should style the selection annotation toolbar");
assert.match(css, /\.source-highlight/, "reader CSS should style source text highlights");
assert.match(css, /\.source-highlight\.is-note/, "note-backed highlights should be visually distinguishable");
assert.match(css, /\.annotation-delete-popover/, "reader CSS should style the highlight delete confirmation popover");
assert.match(css, /\.note-annotation/, "reader CSS should style local annotation notes");
assert.match(css, /\.note-annotation-quote/, "right-side copied source quotes should use a distinct quote style");
assert.match(css, /\.note-annotation-editor/, "right-side annotation notes should be editable");
assert.match(css, /\.note-annotation\.is-detached/, "notes retained after highlight deletion should show detached state");
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL on the first missing annotation assertion.

## Task 2: Implement Local Annotation Runtime

**Files:**
- Modify: `papers/shared/reader.js`

- [ ] **Step 1: Add annotation constants and state**

Add near the top of `reader.js`:

```js
const ANNOTATION_STORAGE_PREFIX = "paperReader.annotations.v1";
```

Extend `state`:

```js
annotations: { version: 1, projectId: PROJECT_ID, items: [] },
pendingAnnotation: null,
annotationToolbar: null,
annotationDeletePopover: null
```

- [ ] **Step 2: Add storage helpers**

Add helper functions after `escapeRegExp`:

```js
function getAnnotationStorageKey() {
  return `${ANNOTATION_STORAGE_PREFIX}.${PROJECT_ID}`;
}

function createEmptyAnnotationStore() {
  return {
    version: 1,
    projectId: PROJECT_ID,
    items: []
  };
}

function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(getAnnotationStorageKey());
    if (!raw) return createEmptyAnnotationStore();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.items)) return createEmptyAnnotationStore();
    return {
      version: 1,
      projectId: PROJECT_ID,
      items: parsed.items.filter((item) => item && item.projectId === PROJECT_ID)
    };
  } catch (error) {
    console.warn("Unable to load local annotations", error);
    return createEmptyAnnotationStore();
  }
}

function saveAnnotations(annotations = state.annotations) {
  try {
    window.localStorage.setItem(getAnnotationStorageKey(), JSON.stringify(annotations));
  } catch (error) {
    console.warn("Unable to save local annotations", error);
  }
}

function getAnnotationsForChunk(paperId, chunkId) {
  return state.annotations.items.filter((item) => item.paperId === paperId && item.chunkId === chunkId);
}
```

- [ ] **Step 3: Add selection context helpers**

Add functions that only accept selections inside one `.source-paragraph` in one `.chunk-source-card`:

```js
function getSourceParagraphFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".source-paragraph") ?? null;
}

function countTextOccurrences(text, needle) {
  if (!needle) return 0;
  let count = 0;
  let index = text.indexOf(needle);
  while (index !== -1) {
    count += 1;
    index = text.indexOf(needle, index + needle.length);
  }
  return count;
}

function getSelectionAnnotationContext() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const selectedText = selection.toString().trim();
  if (selectedText.length < 2) return null;

  const startParagraph = getSourceParagraphFromNode(range.startContainer);
  const endParagraph = getSourceParagraphFromNode(range.endContainer);
  if (!startParagraph || startParagraph !== endParagraph) return null;

  const sourceCard = startParagraph.closest(".chunk-source-card");
  const chunk = startParagraph.closest(".chunk");
  if (!sourceCard || !chunk || !sourceCard.contains(startParagraph)) return null;

  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(sourceCard);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const matchIndex = countTextOccurrences(beforeRange.toString(), selectedText);
  const rect = range.getBoundingClientRect();

  return {
    selectedText,
    matchIndex,
    paperId: state.currentPaper?.id,
    chunkId: chunk.dataset.chunkId,
    rect
  };
}
```

- [ ] **Step 4: Add create/update/delete helpers**

Add functions:

```js
function createAnnotationId() {
  return `ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
  if (!context?.paperId || !context?.chunkId) return;
  const now = new Date().toISOString();
  state.annotations.items.push({
    id: createAnnotationId(),
    projectId: PROJECT_ID,
    paperId: context.paperId,
    chunkId: context.chunkId,
    selectedText: context.selectedText,
    matchIndex: context.matchIndex,
    mode,
    note: "",
    highlightActive: true,
    createdAt: now,
    updatedAt: now
  });
  saveAnnotations();
  state.pendingAnnotation = null;
  window.getSelection()?.removeAllRanges();
  hideAnnotationToolbar();
  applyHighlights(state.currentReading);
  updateActiveChunkFromViewport(state.currentReading);
}

function updateAnnotationNote(annotationId, value) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.note = value;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
}

function deleteAnnotation(annotationId, behavior) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  if (behavior === "highlight-only" && annotation.mode === "note") {
    annotation.highlightActive = false;
    annotation.updatedAt = new Date().toISOString();
  } else {
    state.annotations.items = state.annotations.items.filter((item) => item.id !== annotationId);
  }
  saveAnnotations();
  hideAnnotationDeletePopover();
  applyHighlights(state.currentReading);
  updateActiveChunkFromViewport(state.currentReading);
}
```

- [ ] **Step 5: Add highlight restoration**

Add text-node based restoration:

```js
function clearHighlights() {
  document.querySelectorAll(".source-highlight").forEach((mark) => {
    mark.replaceWith(document.createTextNode(mark.textContent ?? ""));
  });
}

function getSourceTextNodes(chunkElement) {
  const nodes = [];
  chunkElement.querySelectorAll(".source-paragraph").forEach((paragraph) => {
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      nodes.push(node);
      node = walker.nextNode();
    }
  });
  return nodes;
}

function findTextRangeInNodes(nodes, selectedText, matchIndex) {
  const fullText = nodes.map((node) => node.textContent ?? "").join("");
  let startIndex = -1;
  let searchFrom = 0;
  for (let count = 0; count <= matchIndex; count += 1) {
    startIndex = fullText.indexOf(selectedText, searchFrom);
    if (startIndex === -1) return null;
    searchFrom = startIndex + selectedText.length;
  }
  const endIndex = startIndex + selectedText.length;
  let offset = 0;
  let startNode = null;
  let endNode = null;
  let startOffset = 0;
  let endOffset = 0;
  for (const node of nodes) {
    const text = node.textContent ?? "";
    const nextOffset = offset + text.length;
    if (!startNode && startIndex >= offset && startIndex <= nextOffset) {
      startNode = node;
      startOffset = startIndex - offset;
    }
    if (!endNode && endIndex >= offset && endIndex <= nextOffset) {
      endNode = node;
      endOffset = endIndex - offset;
      break;
    }
    offset = nextOffset;
  }
  if (!startNode || !endNode) return null;
  return { startNode, startOffset, endNode, endOffset };
}

function applyHighlight(annotation) {
  if (!annotation.highlightActive) return;
  const chunkElement = document.querySelector(`.chunk[data-chunk-id="${CSS.escape(annotation.chunkId)}"]`);
  if (!chunkElement) return;
  const rangeParts = findTextRangeInNodes(getSourceTextNodes(chunkElement), annotation.selectedText, annotation.matchIndex ?? 0);
  if (!rangeParts) return;
  const range = document.createRange();
  range.setStart(rangeParts.startNode, rangeParts.startOffset);
  range.setEnd(rangeParts.endNode, rangeParts.endOffset);
  const mark = document.createElement("mark");
  mark.className = `source-highlight${annotation.mode === "note" ? " is-note" : ""}`;
  mark.dataset.annotationId = annotation.id;
  range.surroundContents(mark);
}

function applyHighlights(reading) {
  clearHighlights();
  if (!reading || !state.currentPaper) return;
  state.annotations.items
    .filter((item) => item.paperId === state.currentPaper.id)
    .forEach((annotation) => applyHighlight(annotation));
}
```

- [ ] **Step 6: Run reader test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: still FAIL until CSS and note rendering are complete, but annotation function assertions should now pass.

## Task 3: Wire Annotation UI And Note Surface

**Files:**
- Modify: `papers/shared/reader.js`

- [ ] **Step 1: Add toolbar and delete popover rendering**

Add:

```js
function ensureAnnotationToolbar() {
  if (state.annotationToolbar) return state.annotationToolbar;
  const toolbar = document.createElement("div");
  toolbar.className = "annotation-toolbar";
  toolbar.hidden = true;
  toolbar.innerHTML = `
    <button type="button" data-annotation-action="highlight">Highlight</button>
    <button type="button" data-annotation-action="note">Note</button>
  `;
  toolbar.addEventListener("click", (event) => {
    const button = event.target.closest("[data-annotation-action]");
    if (!button) return;
    createAnnotationFromSelection(button.dataset.annotationAction);
  });
  document.body.append(toolbar);
  state.annotationToolbar = toolbar;
  return toolbar;
}

function hideAnnotationToolbar() {
  if (state.annotationToolbar) state.annotationToolbar.hidden = true;
}

function renderAnnotationToolbar() {
  const context = getSelectionAnnotationContext();
  if (!context) {
    state.pendingAnnotation = null;
    hideAnnotationToolbar();
    return;
  }
  state.pendingAnnotation = context;
  const toolbar = ensureAnnotationToolbar();
  toolbar.hidden = false;
  toolbar.style.left = `${Math.min(window.innerWidth - 170, Math.max(12, context.rect.left + context.rect.width / 2 - 76))}px`;
  toolbar.style.top = `${Math.max(12, context.rect.top - 48)}px`;
}

function ensureAnnotationDeletePopover() {
  if (state.annotationDeletePopover) return state.annotationDeletePopover;
  const popover = document.createElement("div");
  popover.className = "annotation-delete-popover";
  popover.hidden = true;
  popover.innerHTML = `
    <button type="button" data-delete-behavior="highlight-only">只删除高亮，保留笔记</button>
    <button type="button" data-delete-behavior="all">高亮和批注一起删除</button>
    <button type="button" data-delete-behavior="cancel">取消</button>
  `;
  popover.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-behavior]");
    if (!button) return;
    const annotationId = popover.dataset.annotationId;
    if (button.dataset.deleteBehavior !== "cancel") {
      deleteAnnotation(annotationId, button.dataset.deleteBehavior);
    }
    hideAnnotationDeletePopover();
  });
  document.body.append(popover);
  state.annotationDeletePopover = popover;
  return popover;
}

function hideAnnotationDeletePopover() {
  if (state.annotationDeletePopover) state.annotationDeletePopover.hidden = true;
}

function showAnnotationDeletePopover(annotationId, rect) {
  const popover = ensureAnnotationDeletePopover();
  popover.dataset.annotationId = annotationId;
  popover.hidden = false;
  popover.style.left = `${Math.min(window.innerWidth - 250, Math.max(12, rect.left))}px`;
  popover.style.top = `${Math.min(window.innerHeight - 130, Math.max(12, rect.bottom + 8))}px`;
}
```

- [ ] **Step 2: Update note surface rendering**

Replace `renderNoteSurface(surface, note)` with:

```js
function renderNoteSurface(surface, note, annotations = []) {
  const baseNote = note ? `<p>${escapeHtml(note)}</p>` : "";
  const annotationMarkup = annotations
    .filter((annotation) => annotation.mode === "note")
    .map((annotation) => `
      <article class="note-annotation${annotation.highlightActive ? "" : " is-detached"}" data-note-annotation-id="${escapeHtml(annotation.id)}">
        <blockquote class="note-annotation-quote">${escapeHtml(annotation.selectedText)}</blockquote>
        <textarea class="note-annotation-editor" data-annotation-note-id="${escapeHtml(annotation.id)}" placeholder="写批注...">${escapeHtml(annotation.note ?? "")}</textarea>
      </article>
    `)
    .join("");
  surface.innerHTML = `${baseNote}${annotationMarkup}`;
  surface.classList.remove("is-changing");
  surface.querySelectorAll(".note-annotation-editor").forEach((editor) => {
    editor.addEventListener("input", () => updateAnnotationNote(editor.dataset.annotationNoteId, editor.value));
  });
}
```

Update `updateNoteSurface(chunkId, note)` so it passes annotations:

```js
const annotations = state.currentPaper && chunkId
  ? getAnnotationsForChunk(state.currentPaper.id, chunkId)
  : [];
window.setTimeout(() => renderNoteSurface(surface, note, annotations), 90);
```

- [ ] **Step 3: Bind annotation controls**

Add:

```js
function bindAnnotationControls() {
  els.chunkList.addEventListener("mouseup", () => window.setTimeout(renderAnnotationToolbar, 0));
  els.chunkList.addEventListener("keyup", () => window.setTimeout(renderAnnotationToolbar, 0));
  els.chunkList.addEventListener("click", (event) => {
    const highlight = event.target.closest(".source-highlight");
    if (!highlight) return;
    showAnnotationDeletePopover(highlight.dataset.annotationId, highlight.getBoundingClientRect());
  });
  document.addEventListener("mousedown", (event) => {
    if (state.annotationToolbar?.contains(event.target) || state.annotationDeletePopover?.contains(event.target)) return;
    if (!event.target.closest(".source-highlight")) hideAnnotationDeletePopover();
    if (!event.target.closest(".chunk-source-card")) hideAnnotationToolbar();
  });
}
```

Call `bindAnnotationControls()` from `bindControls()`.

- [ ] **Step 4: Apply highlights after chunk render**

Update `renderChunks(reading)`:

```js
els.chunkList.innerHTML = reading.chunks.map((chunk) => renderChunk(chunk, reading)).join("");
applyHighlights(reading);
observeChunks(reading);
```

Initialize annotations in `initReader()` before opening a paper:

```js
state.annotations = loadAnnotations();
```

- [ ] **Step 5: Run reader test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL only on missing CSS or standard docs assertions.

## Task 4: Add Annotation Styling

**Files:**
- Modify: `papers/shared/reader.css`

- [ ] **Step 1: Add source highlight and toolbar CSS**

Add near chunk source styles:

```css
.source-highlight {
  border-radius: 4px;
  background: rgba(166, 67, 56, 0.16);
  box-shadow: 0 0 0 1px rgba(166, 67, 56, 0.08);
  cursor: pointer;
}

.source-highlight.is-note {
  background: rgba(183, 142, 64, 0.22);
}

.source-highlight:hover {
  background: rgba(166, 67, 56, 0.24);
}

.annotation-toolbar,
.annotation-delete-popover {
  position: fixed;
  z-index: 80;
  display: flex;
  gap: 6px;
  border: 1px solid var(--reader-glass-edge);
  border-radius: 14px;
  background: var(--reader-glass-strong);
  padding: 6px;
  backdrop-filter: var(--reader-panel-blur);
  -webkit-backdrop-filter: var(--reader-panel-blur);
  box-shadow:
    inset 0 1px 0 var(--reader-glass-highlight),
    0 18px 44px var(--reader-glass-shadow);
}

.annotation-toolbar button,
.annotation-delete-popover button {
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--reader-ink);
  padding: 6px 9px;
  font-size: 12px;
  cursor: pointer;
}

.annotation-toolbar button:hover,
.annotation-delete-popover button:hover {
  background: rgba(255, 255, 255, 0.28);
}

.annotation-delete-popover {
  flex-direction: column;
  min-width: 220px;
}
```

- [ ] **Step 2: Add right note annotation CSS**

Add near `.note-surface` styles:

```css
.note-annotation {
  margin: 0 0 18px;
  padding: 0 0 16px 12px;
  border-left: 1px solid rgba(24, 60, 73, 0.28);
}

.note-annotation.is-detached {
  opacity: 0.72;
}

.note-annotation-quote {
  margin: 0 0 9px;
  color: var(--reader-blue);
  font-family: var(--reader-serif);
  font-size: 13px;
  line-height: 1.58;
}

.note-annotation-editor {
  display: block;
  width: 100%;
  min-height: 84px;
  resize: vertical;
  border: 0;
  border-bottom: 1px solid var(--reader-line);
  background: transparent;
  color: var(--reader-ink);
  padding: 0 0 8px;
  outline: none;
  font: inherit;
  line-height: 1.72;
}

.note-annotation-editor:focus {
  border-bottom-color: var(--reader-red);
}
```

- [ ] **Step 3: Run reader test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: PASS or fail only on import standard documentation.

## Task 5: Document Runtime Annotation Boundary

**Files:**
- Modify: `papers/PAPER_IMPORT_STANDARD.md`

- [ ] **Step 1: Add local annotation note**

After the `notes.json Contract` rules, add:

```md
## Runtime Local Annotations

本地高亮和批注是 reader runtime 的个人层，不属于 reading package 源文件。

- 前端可以用 `localStorage` 保存 `paperReader.annotations.v1.<projectId>`。
- annotation 可以记录 `paperId`、`chunkId`、`selectedText`、`matchIndex`、`mode`、`note` 和 `highlightActive`。
- `Highlight` 只恢复原文高亮；`Note` 同时把选中原文作为引用放入右侧平行笔记区。
- 本地 annotation 不写回 `notes.json`，也不要求进入 GitHub commit。
- 如果需要长期沉淀，后续应通过单独导出/导入或人工整理流程完成。
```

- [ ] **Step 2: Run standard test**

Run:

```bash
node tests/paper-import-standard-requirements.mjs
```

Expected: PASS.

## Task 6: Final Verification And Commit

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run full checks**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Inspect diff**

Run:

```bash
git diff --stat
git status --short
```

Expected: only the plan, reader JS/CSS, import standard, and reader requirements test are changed.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add docs/superpowers/plans/2026-07-05-paper-reader-local-annotations.md \
  tests/paper-reader-requirements.mjs \
  papers/shared/reader.js \
  papers/shared/reader.css \
  papers/PAPER_IMPORT_STANDARD.md
git commit -m "Add local paper reader annotations"
```

Expected: commit succeeds on `codex/paper-reader-local-annotations`.

## Self-Review

- Spec coverage: covers localStorage persistence, source-only selection, Highlight/Note actions, right note reuse, distinct quote styling, deletion popover, no export/import, no backend.
- Placeholder scan: no `TBD`, `TODO`, or deferred implementation placeholders.
- Type consistency: function names in tests match JS tasks; CSS class names in tests match style tasks.
