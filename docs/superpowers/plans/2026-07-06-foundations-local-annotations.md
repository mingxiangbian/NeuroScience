# Foundations Local Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `projects/foundations/` 基石知识库 reader 中增加浏览器本地高亮和学习笔记批注。

**Architecture:** 继续保持 GitHub Pages 纯静态架构，不新增后端、不写回 Markdown、不改 `roadmap-data.json` schema。annotation runtime 只挂在 `knowledge-card` 知识卡片上，以 `moduleId + noteId` 定位本地记录；右侧学习记录面板继续跟随当前知识卡，并在原有知识分组下方渲染本地摘录和笔记。

**Tech Stack:** Vanilla HTML/CSS/JS, DOM Selection/Range API, `localStorage`, existing Node requirement tests, static GitHub Pages.

---

## File Structure

- Modify: `tests/foundations-roadmap-requirements.mjs`
  - 更新 contract：第一版不再禁止 browser storage；新增 local annotation runtime、知识卡选区、右侧学习记录、无后端写回等断言。
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
  - 新增 annotation state、storage helpers、选区 toolbar、高亮恢复、右侧本地笔记渲染、删除逻辑。
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
  - 新增知识高亮、选区浮层、删除 popover、右侧本地笔记样式。
- Do not modify: `projects/foundations/roadmap/roadmap-data.json`
  - 本地 annotation 是 runtime 个人层，不进入生成数据。
- Do not modify: `papers/shared/reader.js` or `papers/shared/reader.css`
  - 论文阅读器已完成，本计划不触碰。

## Task 1: Add Failing Foundations Annotation Requirements

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`

- [ ] **Step 1: Replace the old no-storage assertion**

Find:

```js
assert.doesNotMatch(js, /localStorage|sessionStorage/, "first version should not persist state in browser storage");
```

Replace it with:

```js
assert.match(js, /ANNOTATION_STORAGE_KEY = "foundationsReader\.annotations\.v1"/, "Foundations reader should define a versioned local annotation storage key");
assert.match(js, /function createEmptyAnnotationStore/, "Foundations reader should create an empty annotation store");
assert.match(js, /function loadAnnotations/, "Foundations reader should load local annotations from localStorage");
assert.match(js, /function saveAnnotations/, "Foundations reader should save local annotations to localStorage");
assert.match(js, /function getAnnotationsForNote/, "Foundations reader should filter annotations by module and knowledge note");
assert.match(js, /function createAnnotationFromSelection/, "Foundations reader should create annotations from selected knowledge-card text");
assert.match(js, /function applyHighlights/, "Foundations reader should restore highlights inside knowledge cards");
assert.match(js, /function updateAnnotationNote/, "Foundations reader should update local study-note text");
assert.match(js, /function deleteAnnotation/, "Foundations reader should support deleting highlights and annotations");
assert.match(js, /\.knowledge-card/, "annotation selection should be scoped to knowledge cards");
assert.match(js, /data-note-id/, "annotations should anchor to stable knowledge note ids");
assert.match(js, /高亮/, "selection toolbar should expose a highlight action");
assert.match(js, /笔记/, "selection toolbar should expose a note action");
assert.match(js, /只删除高亮，保留笔记/, "delete confirmation should allow keeping the note");
assert.match(js, /高亮和笔记一起删除/, "delete confirmation should allow deleting both highlight and note");
assert.doesNotMatch(js, /PROJECT_ID = "brain-memory-for-ai-agents"|paperReader\.annotations\.v1/, "Foundations annotations should not reuse paper-reader project state");
assert.doesNotMatch(js, /githubToken|Authorization|contents\/|repos\/|gitHub|fetch\(\"\/api/i, "Foundations annotations should not write to GitHub or backend APIs");
```

- [ ] **Step 2: Add CSS assertions**

Add near the existing `.knowledge-card` and `.note-group-title` CSS assertions:

```js
assert.match(css, /\.annotation-toolbar/, "roadmap CSS should style the local annotation selection toolbar");
assert.match(css, /\.knowledge-highlight/, "roadmap CSS should style knowledge-card highlights");
assert.match(css, /\.knowledge-highlight\.is-note/, "note-backed highlights should be visually distinguishable");
assert.match(css, /\.annotation-delete-popover/, "roadmap CSS should style the highlight delete popover");
assert.match(css, /\.local-annotation-list/, "right note panel should style local annotation groups");
assert.match(css, /\.local-annotation-quote/, "right note panel should style copied source excerpts");
assert.match(css, /\.local-annotation-editor/, "right note panel should style editable study notes");
assert.match(css, /\.local-annotation\.is-detached/, "right note panel should expose detached annotation state");
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL on the first missing annotation assertion, most likely `ANNOTATION_STORAGE_KEY`.

## Task 2: Add Annotation State And Storage Helpers

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add constants and state**

Add above `const state = {`:

```js
const ANNOTATION_STORAGE_KEY = "foundationsReader.annotations.v1";
```

Extend `state`:

```js
const state = {
  data: null,
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  activeKnowledgeNoteId: "",
  sectionObserver: null,
  annotations: { version: 1, items: [] },
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null,
};
```

- [ ] **Step 2: Add storage helpers**

Add after `escapeHtml`:

```js
function createEmptyAnnotationStore() {
  return {
    version: 1,
    items: [],
  };
}

function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(ANNOTATION_STORAGE_KEY);
    if (!raw) return createEmptyAnnotationStore();
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) return createEmptyAnnotationStore();
    return {
      version: 1,
      items: parsed.items.filter((item) => item && item.projectId === "foundations"),
    };
  } catch (error) {
    console.warn("Unable to load Foundations annotations", error);
    return createEmptyAnnotationStore();
  }
}

function saveAnnotations(annotations = state.annotations) {
  try {
    window.localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(annotations));
  } catch (error) {
    console.warn("Unable to save Foundations annotations", error);
  }
}

function getAnnotationsForNote(moduleId, noteId) {
  return state.annotations.items.filter((item) => item.moduleId === moduleId && item.noteId === noteId);
}
```

- [ ] **Step 3: Load annotations during init**

In `init()`, after `state.data = await fetchJson("roadmap/roadmap-data.json");`, add:

```js
state.annotations = loadAnnotations();
```

- [ ] **Step 4: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL on missing selection/highlight functions.

## Task 3: Implement Knowledge-Card Selection And Toolbar

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add selection context helpers**

Add after `getAnnotationsForNote`:

```js
function getKnowledgeCardFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".knowledge-card") ?? null;
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

  const startCard = getKnowledgeCardFromNode(range.startContainer);
  const endCard = getKnowledgeCardFromNode(range.endContainer);
  if (!startCard || startCard !== endCard) return null;

  const noteId = startCard.dataset.noteId;
  const moduleId = state.currentModule?.id;
  if (!moduleId || !noteId) return null;

  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(startCard);
  beforeRange.setEnd(range.startContainer, range.startOffset);

  return {
    moduleId,
    noteId,
    selectedText,
    matchIndex: countTextOccurrences(beforeRange.toString(), selectedText),
    rect: range.getBoundingClientRect(),
  };
}
```

- [ ] **Step 2: Add toolbar rendering**

Add after selection context helpers:

```js
function hideAnnotationToolbar() {
  state.annotationToolbar?.remove();
  state.annotationToolbar = null;
  state.pendingAnnotation = null;
}

function renderAnnotationToolbar(context) {
  hideAnnotationToolbar();
  const toolbar = document.createElement("div");
  toolbar.className = "annotation-toolbar";
  toolbar.innerHTML = `
    <button type="button" data-annotation-mode="highlight">高亮</button>
    <button type="button" data-annotation-mode="note">笔记</button>
  `;
  toolbar.style.left = `${Math.max(12, context.rect.left + context.rect.width / 2)}px`;
  toolbar.style.top = `${Math.max(12, context.rect.top - 46)}px`;
  toolbar.querySelectorAll("[data-annotation-mode]").forEach((button) => {
    button.addEventListener("click", () => createAnnotationFromSelection(button.dataset.annotationMode));
  });
  document.body.append(toolbar);
  state.annotationToolbar = toolbar;
  state.pendingAnnotation = context;
}
```

- [ ] **Step 3: Bind selection events**

In `bindEvents()`, before the `window.addEventListener("keydown", ...)` block, add:

```js
els.main.addEventListener("mouseup", () => {
  requestAnimationFrame(() => {
    const context = getSelectionAnnotationContext();
    if (context) renderAnnotationToolbar(context);
  });
});

els.main.addEventListener("keyup", () => {
  const context = getSelectionAnnotationContext();
  if (context) renderAnnotationToolbar(context);
});

document.addEventListener("mousedown", (event) => {
  if (state.annotationToolbar?.contains(event.target)) return;
  if (state.annotationDeletePopover?.contains(event.target)) return;
  if (!getKnowledgeCardFromNode(event.target)) hideAnnotationToolbar();
});
```

- [ ] **Step 4: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL on missing `createAnnotationFromSelection`, `applyHighlights`, `deleteAnnotation`, and CSS classes.

## Task 4: Create, Update, Delete Annotation Records

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add record mutation helpers**

Add after `renderAnnotationToolbar`:

```js
function createAnnotationId() {
  return `foundation-ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
  if (!context?.moduleId || !context?.noteId) return;
  const now = new Date().toISOString();
  const annotation = {
    id: createAnnotationId(),
    projectId: "foundations",
    moduleId: context.moduleId,
    noteId: context.noteId,
    selectedText: context.selectedText,
    matchIndex: context.matchIndex,
    mode: mode === "note" ? "note" : "highlight",
    note: "",
    highlightActive: true,
    createdAt: now,
    updatedAt: now,
  };
  state.annotations.items.push(annotation);
  saveAnnotations();
  window.getSelection()?.removeAllRanges();
  hideAnnotationToolbar();
  applyHighlights();
  renderContextualNotePanel(getKnowledgeNoteById(state.currentModule, context.noteId));
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
  applyHighlights();
  renderContextualNotePanel(getKnowledgeNoteById(state.currentModule, annotation.noteId));
}
```

- [ ] **Step 2: Add delete popover helpers**

Add after `deleteAnnotation`:

```js
function hideAnnotationDeletePopover() {
  state.annotationDeletePopover?.remove();
  state.annotationDeletePopover = null;
}

function showAnnotationDeletePopover(annotationId, rect) {
  hideAnnotationDeletePopover();
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const popover = document.createElement("div");
  popover.className = "annotation-delete-popover";
  const keepButton = annotation.mode === "note"
    ? `<button type="button" data-delete-behavior="highlight-only">只删除高亮，保留笔记</button>`
    : "";
  popover.innerHTML = `
    ${keepButton}
    <button type="button" data-delete-behavior="all">高亮和笔记一起删除</button>
    <button type="button" data-delete-behavior="cancel">取消</button>
  `;
  popover.style.left = `${Math.max(12, rect.left)}px`;
  popover.style.top = `${Math.max(12, rect.bottom + 8)}px`;
  popover.querySelectorAll("[data-delete-behavior]").forEach((button) => {
    button.addEventListener("click", () => {
      const behavior = button.dataset.deleteBehavior;
      if (behavior === "cancel") {
        hideAnnotationDeletePopover();
        return;
      }
      deleteAnnotation(annotationId, behavior);
    });
  });
  document.body.append(popover);
  state.annotationDeletePopover = popover;
}
```

- [ ] **Step 3: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL on missing highlight restoration and CSS classes.

## Task 5: Restore Highlights Inside Knowledge Cards

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add text matching helpers**

Add after `showAnnotationDeletePopover`:

```js
function getTextNodes(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      if (node.parentElement?.closest(".knowledge-highlight")) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  return nodes;
}

function clearHighlights() {
  els.sectionList.querySelectorAll(".knowledge-highlight").forEach((mark) => {
    mark.replaceWith(document.createTextNode(mark.textContent));
  });
  els.sectionList.normalize();
}

function findTextRange(root, selectedText, matchIndex) {
  const nodes = getTextNodes(root);
  let occurrence = 0;
  for (const node of nodes) {
    const index = node.nodeValue.indexOf(selectedText);
    if (index === -1) continue;
    if (occurrence === matchIndex) {
      const range = document.createRange();
      range.setStart(node, index);
      range.setEnd(node, index + selectedText.length);
      return range;
    }
    occurrence += 1;
  }
  return null;
}
```

- [ ] **Step 2: Add `applyHighlights`**

Add after `findTextRange`:

```js
function applyHighlights() {
  clearHighlights();
  if (!state.currentModule) return;
  const moduleId = state.currentModule.id;
  const activeAnnotations = state.annotations.items.filter((item) => (
    item.moduleId === moduleId && item.highlightActive
  ));
  for (const annotation of activeAnnotations) {
    const card = els.sectionList.querySelector(`.knowledge-card[data-note-id="${CSS.escape(annotation.noteId)}"]`);
    if (!card) continue;
    const range = findTextRange(card, annotation.selectedText, annotation.matchIndex);
    if (!range) continue;
    const mark = document.createElement("mark");
    mark.className = `knowledge-highlight${annotation.mode === "note" ? " is-note" : ""}`;
    mark.dataset.annotationId = annotation.id;
    mark.append(range.extractContents());
    mark.addEventListener("click", (event) => {
      event.stopPropagation();
      showAnnotationDeletePopover(annotation.id, mark.getBoundingClientRect());
    });
    range.insertNode(mark);
  }
}
```

- [ ] **Step 3: Call highlight restoration after module render**

In `openModule()`, after `renderSectionRail(nextModule);`, add:

```js
applyHighlights();
```

In `renderCurrentModule()`, after assigning `els.sectionList.innerHTML = blocks || ...`, do not call `applyHighlights()` there. Keep the call in `openModule()` so overview and ordinary modules have a single restoration path.

- [ ] **Step 4: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: still FAIL on CSS classes and possibly right-panel local annotation rendering.

## Task 6: Render Local Notes In The Right Learning Panel

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add local annotation renderer**

Add before `renderContextualNotePanel(note)`:

```js
function renderLocalAnnotations(note) {
  if (!state.currentModule || !note) return "";
  const annotations = getAnnotationsForNote(state.currentModule.id, note.id)
    .filter((annotation) => annotation.mode === "note" || annotation.note || !annotation.highlightActive);
  if (annotations.length === 0) return "";

  return `
    <section class="note-block local-annotation-list">
      <h3 class="note-group-title">本地学习笔记</h3>
      ${annotations.map((annotation) => `
        <article class="local-annotation${annotation.highlightActive ? "" : " is-detached"}" data-annotation-id="${escapeHtml(annotation.id)}">
          <p class="local-annotation-quote">${escapeHtml(annotation.selectedText)}</p>
          <textarea class="local-annotation-editor" rows="4" data-annotation-editor="${escapeHtml(annotation.id)}" placeholder="写下理解、反思或面试表达">${escapeHtml(annotation.note)}</textarea>
          ${annotation.highlightActive ? "" : `<p class="local-annotation-status">原文高亮已删除，笔记仍保留。</p>`}
        </article>
      `).join("")}
    </section>
  `;
}
```

- [ ] **Step 2: Append local annotations to the existing right panel**

In `renderContextualNotePanel(note)`, replace:

```js
const renderedNotes = note
  ? `<article class="note-context"><h3>${escapeHtml(note.title)}</h3>${noteGroups}</article>`
  : `<p class="note-empty">这个模块没有独立知识笔记；选择具体能力模块后，右栏会同步显示当前知识卡。</p>`;
```

With:

```js
const renderedNotes = note
  ? `<article class="note-context"><h3>${escapeHtml(note.title)}</h3>${noteGroups}${renderLocalAnnotations(note)}</article>`
  : `<p class="note-empty">这个模块没有独立知识笔记；选择具体能力模块后，右栏会同步显示当前知识卡。</p>`;
```

- [ ] **Step 3: Bind local annotation editors**

Still inside `renderContextualNotePanel(note)`, after:

```js
els.mobileNoteSurface.innerHTML = renderedNotes;
```

Add:

```js
for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
  surface.querySelectorAll("[data-annotation-editor]").forEach((editor) => {
    editor.addEventListener("input", () => {
      updateAnnotationNote(editor.dataset.annotationEditor, editor.value);
    });
  });
}
```

- [ ] **Step 4: Ensure active note context updates on card click**

After `renderCurrentModule()` completes ordinary module rendering, add this before the function returns:

```js
els.sectionList.querySelectorAll(".knowledge-card").forEach((card) => {
  card.addEventListener("click", () => setActiveKnowledgeContext(card.dataset.noteId));
});
```

Do not add this to the overview dashboard branch.

- [ ] **Step 5: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL only on missing CSS classes.

## Task 7: Add Annotation Styles

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.css`

- [ ] **Step 1: Add highlight and toolbar styles**

Add after the `.knowledge-card-body` block:

```css
.knowledge-highlight {
  border-radius: 3px;
  background: rgba(166, 67, 56, 0.18);
  color: inherit;
  cursor: pointer;
}

.knowledge-highlight.is-note {
  background: rgba(24, 60, 73, 0.2);
  box-shadow: inset 0 -1px 0 rgba(24, 60, 73, 0.28);
}

.knowledge-highlight:hover {
  background: rgba(166, 67, 56, 0.28);
}

.knowledge-highlight.is-note:hover {
  background: rgba(24, 60, 73, 0.3);
}

.annotation-toolbar,
.annotation-delete-popover {
  position: fixed;
  z-index: 60;
  display: flex;
  gap: 6px;
  border: 1px solid var(--reader-glass-edge);
  border-radius: 12px;
  background: var(--reader-glass-strong);
  backdrop-filter: var(--reader-panel-blur);
  -webkit-backdrop-filter: var(--reader-panel-blur);
  box-shadow: 0 18px 42px var(--reader-glass-shadow);
  padding: 6px;
}

.annotation-toolbar button,
.annotation-delete-popover button {
  border: 0;
  border-radius: 8px;
  color: var(--reader-ink);
  background: transparent;
  padding: 7px 9px;
  font-size: 12px;
  cursor: pointer;
}

.annotation-toolbar button:hover,
.annotation-delete-popover button:hover {
  background: var(--reader-glass-highlight);
}

.annotation-delete-popover {
  flex-direction: column;
  align-items: stretch;
  min-width: 176px;
}
```

- [ ] **Step 2: Add right-panel local note styles**

Add after `.note-group-body`:

```css
.local-annotation-list {
  border-top: 1px solid var(--reader-line);
  margin-top: 4px;
  padding-top: 16px;
}

.local-annotation {
  display: grid;
  gap: 8px;
  border-left: 1px solid var(--reader-line);
  padding: 0 0 18px 14px;
}

.local-annotation + .local-annotation {
  margin-top: 12px;
}

.local-annotation.is-detached {
  opacity: 0.72;
}

.local-annotation-quote {
  margin: 0;
  color: var(--reader-ink-muted);
  font-size: 12px;
  line-height: 1.62;
}

.local-annotation-editor {
  width: 100%;
  min-height: 86px;
  resize: vertical;
  border: 1px solid var(--reader-line);
  border-radius: 8px;
  color: var(--reader-ink);
  background: rgba(255, 255, 255, 0.2);
  padding: 9px 10px;
  font: inherit;
  line-height: 1.6;
}

.local-annotation-editor:focus {
  outline: 1px solid var(--reader-blue);
  border-color: var(--reader-blue);
}

.local-annotation-status {
  margin: 0;
  color: var(--reader-ink-muted);
  font-size: 12px;
}
```

- [ ] **Step 3: Run the test**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: PASS.

## Task 8: Verification And Commit

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `projects/foundations/roadmap/roadmap-reader.css`

- [ ] **Step 1: Run focused Foundations verification**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: PASS.

- [ ] **Step 2: Run adjacent project/page tests**

Run:

```bash
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
```

Expected: all PASS. This confirms the Foundations change did not touch the projects index or paper reader contracts.

- [ ] **Step 3: Run whitespace hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Review the diff**

Run:

```bash
git diff -- tests/foundations-roadmap-requirements.mjs projects/foundations/roadmap/roadmap-reader.js projects/foundations/roadmap/roadmap-reader.css
```

Expected: diff only contains local annotation tests/runtime/styles. No edits to `papers/shared/*`, no generated `roadmap-data.json` churn, no unrelated formatting.

- [ ] **Step 5: Commit**

Run:

```bash
git add tests/foundations-roadmap-requirements.mjs projects/foundations/roadmap/roadmap-reader.js projects/foundations/roadmap/roadmap-reader.css
git commit -m "Add local annotations to foundations reader"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: plan covers local-only storage, `knowledge-card`-scoped selection, `moduleId + noteId` anchoring, highlight-only and note-backed records, right-panel learning notes, deletion behavior, detached-note state, no backend/GitHub writeback, and no paper-reader changes.
- Placeholder scan: no blocked placeholder patterns or undefined task references are left in executable steps.
- Type consistency: annotation fields are consistent across tasks: `id`, `projectId`, `moduleId`, `noteId`, `selectedText`, `matchIndex`, `mode`, `note`, `highlightActive`, `createdAt`, `updatedAt`.
- Scope check: this is one subsystem only: Foundations runtime annotations. It does not modify Markdown source generation, paper-reader annotations, or cloud sync.
