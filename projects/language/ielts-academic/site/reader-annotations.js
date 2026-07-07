import { escapeHtml } from "./reader-utils.js";

export function createJournalDraftMarkdown(annotation, context = {}) {
  const date = new Date().toISOString().slice(0, 10);
  const relatedNotes = context.noteReferenceId?.startsWith("note:")
    ? `[${context.noteReferenceId.replace(/^note:/, "")}]`
    : "[]";
  const relatedErrors = context.errorReferenceId?.startsWith("error:")
    ? `[${context.errorReferenceId.replace(/^error:/, "")}]`
    : "[]";
  return `---
date: ${date}
related_notes: ${relatedNotes}
related_errors: ${relatedErrors}
source_anchor: ${annotation.moduleId}/${annotation.noteId}
---

# Reader annotation ${date}

Source: ${context.sourceLabel ?? annotation.noteId}

> ${annotation.selectedText}

${annotation.note || "Write the durable reflection here before saving this as a journal entry."}
`;
}

export function renderAnnotationDraft(annotation, context) {
  const draft = createJournalDraftMarkdown(annotation, context);
  return `
    <details class="annotation-draft">
      <summary>复制为 journal 草稿</summary>
      <p>本机临时阅读标注不会写回 repo。需要长期保留时，把下面草稿保存到 journal/entries/。</p>
      <textarea readonly rows="10">${escapeHtml(draft)}</textarea>
      <button type="button" data-copy-journal-draft="${escapeHtml(annotation.id)}">复制草稿</button>
    </details>
  `;
}

export function getReadableCardFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".knowledge-card, .module-section") ?? null;
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

export function getSelectionAnnotationContext(runtime) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const selectedText = selection.toString().trim();
  if (selectedText.length < 2) return null;
  if (range.startContainer !== range.endContainer) return null;

  const startCard = getReadableCardFromNode(range.startContainer);
  const endCard = getReadableCardFromNode(range.endContainer);
  if (!startCard || startCard !== endCard) return null;

  const noteId = startCard.dataset.noteId || startCard.dataset.sectionId;
  const moduleId = runtime.state.currentModule?.id;
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

export function hideAnnotationToolbar(runtime) {
  runtime.state.annotationToolbar?.remove();
  runtime.state.annotationToolbar = null;
  runtime.state.pendingAnnotation = null;
}

export function renderAnnotationToolbar(runtime, context) {
  hideAnnotationToolbar(runtime);
  const toolbar = document.createElement("div");
  toolbar.className = "annotation-toolbar";
  toolbar.innerHTML = `
    <button type="button" data-annotation-mode="highlight">高亮</button>
    <button type="button" data-annotation-mode="note">笔记</button>
  `;
  toolbar.style.position = "fixed";
  toolbar.style.left = `${Math.max(12, context.rect.left + context.rect.width / 2)}px`;
  toolbar.style.top = `${Math.max(12, context.rect.top - 46)}px`;
  toolbar.querySelectorAll("[data-annotation-mode]").forEach((button) => {
    button.addEventListener("click", () => createAnnotationFromSelection(runtime, button.dataset.annotationMode));
  });
  document.body.append(toolbar);
  runtime.state.annotationToolbar = toolbar;
  runtime.state.pendingAnnotation = context;
}

function createAnnotationId() {
  return `ielts-ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function createAnnotationFromSelection(runtime, mode) {
  const context = runtime.state.pendingAnnotation;
  if (!context?.moduleId || !context?.noteId) return;
  const now = new Date().toISOString();
  const annotation = {
    id: createAnnotationId(),
    projectId: "ielts-academic",
    moduleId: context.moduleId,
    noteId: context.noteId,
    selectedText: context.selectedText,
    matchIndex: context.matchIndex,
    mode: mode === "note" ? "note" : "highlight",
    note: "",
    highlightActive: true,
    unresolved: false,
    createdAt: now,
    updatedAt: now,
  };
  runtime.state.annotations.items.push(annotation);
  runtime.saveAnnotations(runtime.state.annotations);
  window.getSelection()?.removeAllRanges();
  hideAnnotationToolbar(runtime);
  applyHighlights(runtime);
  runtime.renderContextualNotePanel(runtime.getKnowledgeNoteById(runtime.state.currentModule, context.noteId));
}

export function updateAnnotationNote(runtime, annotationId, value) {
  const annotation = runtime.state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.note = value;
  annotation.updatedAt = new Date().toISOString();
  runtime.saveAnnotations(runtime.state.annotations);
}

export function hideAnnotationDeletePopover(runtime) {
  runtime.state.annotationDeletePopover?.remove();
  runtime.state.annotationDeletePopover = null;
}

export function deleteAnnotation(runtime, annotationId, behavior) {
  const annotation = runtime.state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  if (behavior === "highlight-only" && annotation.mode === "note") {
    annotation.highlightActive = false;
    annotation.updatedAt = new Date().toISOString();
  } else {
    runtime.state.annotations.items = runtime.state.annotations.items.filter((item) => item.id !== annotationId);
  }
  runtime.saveAnnotations(runtime.state.annotations);
  hideAnnotationDeletePopover(runtime);
  applyHighlights(runtime);
  runtime.renderContextualNotePanel(runtime.getKnowledgeNoteById(runtime.state.currentModule, annotation.noteId));
}

function showAnnotationDeletePopover(runtime, annotationId, rect) {
  hideAnnotationDeletePopover(runtime);
  const annotation = runtime.state.annotations.items.find((item) => item.id === annotationId);
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
  popover.style.position = "fixed";
  popover.style.left = `${Math.max(12, rect.left)}px`;
  popover.style.top = `${Math.max(12, rect.bottom + 8)}px`;
  popover.querySelectorAll("[data-delete-behavior]").forEach((button) => {
    button.addEventListener("click", () => {
      const behavior = button.dataset.deleteBehavior;
      if (behavior === "cancel") {
        hideAnnotationDeletePopover(runtime);
        return;
      }
      deleteAnnotation(runtime, annotationId, behavior);
    });
  });
  document.body.append(popover);
  runtime.state.annotationDeletePopover = popover;
}

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

function clearHighlights(runtime) {
  runtime.els.sectionList.querySelectorAll(".knowledge-highlight").forEach((mark) => {
    mark.replaceWith(document.createTextNode(mark.textContent));
  });
  runtime.els.sectionList.normalize();
}

function findTextRange(root, selectedText, matchIndex) {
  if (!selectedText) return null;
  const nodes = getTextNodes(root);
  let occurrence = 0;
  for (const node of nodes) {
    let index = node.nodeValue.indexOf(selectedText);
    while (index !== -1) {
      if (occurrence === matchIndex) {
        const range = document.createRange();
        range.setStart(node, index);
        range.setEnd(node, index + selectedText.length);
        return range;
      }
      occurrence += 1;
      index = node.nodeValue.indexOf(selectedText, index + selectedText.length);
    }
  }
  return null;
}

function getRangeDocumentOrder(runtime, range) {
  const nodes = getTextNodes(runtime.els.sectionList);
  let order = 0;
  for (const node of nodes) {
    if (node === range.startContainer) return order + range.startOffset;
    order += node.nodeValue.length;
  }
  return 0;
}

export function applyHighlights(runtime) {
  clearHighlights(runtime);
  if (!runtime.state.currentModule) return;
  const moduleId = runtime.state.currentModule.id;
  const activeAnnotations = runtime.state.annotations.items.filter((item) => (
    item.moduleId === moduleId && item.highlightActive
  ));
  const resolvedHighlights = [];
  let changed = false;
  for (const annotation of activeAnnotations) {
    const card = runtime.els.sectionList.querySelector(`[data-note-id="${CSS.escape(annotation.noteId)}"], [data-section-id="${CSS.escape(annotation.noteId)}"]`);
    const range = card ? findTextRange(card, annotation.selectedText, annotation.matchIndex) : null;
    if (!range) {
      if (!annotation.unresolved) {
        annotation.unresolved = true;
        annotation.updatedAt = new Date().toISOString();
        changed = true;
      }
      continue;
    }
    if (annotation.unresolved) {
      annotation.unresolved = false;
      annotation.updatedAt = new Date().toISOString();
      changed = true;
    }
    resolvedHighlights.push({
      annotation,
      range,
      order: getRangeDocumentOrder(runtime, range),
    });
  }
  if (changed) runtime.saveAnnotations(runtime.state.annotations);
  resolvedHighlights.sort((left, right) => right.order - left.order);
  for (const { annotation, range } of resolvedHighlights) {
    const mark = document.createElement("mark");
    mark.className = `knowledge-highlight${annotation.mode === "note" ? " is-note" : ""}`;
    mark.dataset.annotationId = annotation.id;
    mark.append(range.extractContents());
    mark.addEventListener("click", (event) => {
      event.stopPropagation();
      showAnnotationDeletePopover(runtime, annotation.id, mark.getBoundingClientRect());
    });
    range.insertNode(mark);
  }
}

function getAnnotationContext(note) {
  const noteReferenceId = note?.id?.startsWith("note-") ? `note:${note.id.slice(5)}` : "";
  const errorReferenceId = note?.id?.startsWith("error-") ? `error:${note.id.slice(6)}` : "";
  return {
    sourceLabel: note?.title,
    noteReferenceId,
    errorReferenceId,
  };
}

export function renderLocalAnnotations(runtime, note) {
  if (!runtime.state.currentModule || !note) return "";
  const context = getAnnotationContext(note);
  const annotations = runtime.state.annotations.items
    .filter((item) => item.moduleId === runtime.state.currentModule.id && item.noteId === note.id)
    .filter((annotation) => annotation.mode === "note" || annotation.note || !annotation.highlightActive || annotation.unresolved);
  if (annotations.length === 0) return "";

  return `
    <section class="note-block local-annotation-list">
      <h3 class="note-group-title">本地学习笔记</h3>
      <p class="local-annotation-boundary">本机临时阅读标注，不写回 repo，不替代 journal。</p>
      ${annotations.map((annotation) => `
        <article class="local-annotation${annotation.highlightActive ? "" : " is-detached"}" data-annotation-id="${escapeHtml(annotation.id)}">
          <p class="local-annotation-quote">${escapeHtml(annotation.selectedText)}</p>
          <textarea class="local-annotation-editor" rows="4" data-annotation-editor="${escapeHtml(annotation.id)}" placeholder="写下理解、反思或备考动作">${escapeHtml(annotation.note)}</textarea>
          ${annotation.highlightActive ? "" : `<p class="local-annotation-status">原文高亮已删除，笔记仍保留。</p>`}
          ${annotation.unresolved ? `<p class="annotation-unresolved">定位失效：原文可能已修改，保留笔记内容。</p>` : ""}
          ${renderAnnotationDraft(annotation, context)}
        </article>
      `).join("")}
    </section>
  `;
}
