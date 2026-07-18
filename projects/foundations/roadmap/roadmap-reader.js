import {
  ANNOTATION_CATEGORIES,
  ANNOTATION_STORE_VERSION,
  createAnnotationAnchor,
  getAnnotationArchiveNoteId,
  getAnnotationContextId,
  groupAnnotations,
  migrateLegacyAnnotations,
  parseStoredAnnotations,
  resolveAnnotationAnchor,
} from "./annotation-model.js";
import { enhanceCodeListings } from "./code-listing.js";
import {
  getDefaultNotePanelCollapsed,
  getFinanceReentryState,
  getReaderPanelStorageKey,
  getReaderThemeStorageKey,
  getRenderableSectionTitles,
  resolveInitialTheme,
} from "./reader-state-model.js";

const READER_SCRIPT = document.querySelector("script[data-source][src$='roadmap-reader.js']");
const PROJECT_ID = document.body.dataset.projectId ?? "foundations";
const ROADMAP_DATA_SOURCE = READER_SCRIPT?.dataset.source ?? "roadmap/roadmap-data.json";
const ANNOTATION_STORAGE_KEY = `${PROJECT_ID}Reader.annotations.v1`;
const TASK_STORAGE_KEY = `${PROJECT_ID}Reader.tasks.v1`;
const THEME_STORAGE_KEY = getReaderThemeStorageKey(PROJECT_ID);
const NOTE_PANEL_STORAGE_KEY = getReaderPanelStorageKey(PROJECT_ID, "notes");
const MERMAID_MODULE_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.esm.min.mjs";
const KEYBOARD_NAVIGATION_KEYS = new Set(["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "]);
const ANNOTATION_EXCLUDED_SELECTOR = [
  "[data-annotation-exclude]",
  "a[href]",
  "button",
  "input",
  "textarea",
  "select",
  "summary",
  "label",
  "[contenteditable]",
  ".knowledge-highlight",
  "[role='button']",
].join(", ");

const state = {
  data: null,
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  activeKnowledgeNoteId: "",
  moduleRenderVersion: 0,
  navigationVersion: 0,
  sectionScrollHandler: null,
  sectionScrollOwner: null,
  sectionScrollFrame: 0,
  annotations: { version: ANNOTATION_STORE_VERSION, items: [] },
  annotationPersistenceAllowed: true,
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null,
  annotationSelectionWarning: null,
  annotationReturnFocus: null,
  notePanelPreferenceCollapsed: getDefaultNotePanelCollapsed(PROJECT_ID),
  drawerReturnFocus: null,
  careerLastSettledUnitId: "",
  careerBoardView: "focus",
  financeGraphFocusId: "",
  financeGraphResizeFrame: 0,
  financeGraphResizeObserver: null,
};

const taskState = loadTaskState();

const els = {
  shell: document.querySelector("#reader-shell"),
  nav: document.querySelector("#module-nav"),
  sectionLines: document.querySelector("#section-lines"),
  moduleHeader: document.querySelector("#module-header"),
  sectionList: document.querySelector("#section-list"),
  noteLabel: document.querySelector("#note-label"),
  noteSurface: document.querySelector("#note-surface"),
  mobileNoteLabel: document.querySelector("#mobile-note-label"),
  mobileNoteSurface: document.querySelector("#mobile-note-surface"),
  searchInput: document.querySelector("#global-search"),
  searchResults: document.querySelector("#search-results"),
  searchOverlay: document.querySelector("#search-overlay"),
  toolbar: document.querySelector("#reader-toolbar"),
  sidebar: document.querySelector("#module-directory"),
  toggleTheme: document.querySelector("#toggle-theme"),
  toggleNote: document.querySelector("#toggle-note"),
  noteRailToggle: document.querySelector("#note-rail-toggle"),
  noteCount: document.querySelector("#note-count"),
  notePanelContent: document.querySelector("#note-panel-content"),
  mobileNoteDrawer: document.querySelector("#mobile-note-drawer"),
  closeMobileNote: document.querySelector("#close-mobile-note"),
  drawerBackdrop: document.querySelector("#drawer-backdrop"),
  announcer: document.querySelector("#reader-announcer"),
  toggleLeftControls: document.querySelectorAll("[data-toggle-left]"),
  main: document.querySelector("#reader-main"),
};

function resolveUrl(path) {
  return new URL(path, window.location.href);
}

async function fetchJson(path) {
  const response = await fetch(resolveUrl(path));
  if (!response.ok) throw new Error(`Unable to load ${path}`);
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createEmptyAnnotationStore() {
  return {
    version: ANNOTATION_STORE_VERSION,
    items: [],
  };
}

function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(ANNOTATION_STORAGE_KEY);
    return parseStoredAnnotations(raw, PROJECT_ID);
  } catch (error) {
    console.warn(`Unable to load ${PROJECT_ID} annotations`, error);
    return { store: createEmptyAnnotationStore(), canPersist: false };
  }
}

function saveAnnotations(annotations = state.annotations) {
  if (!state.annotationPersistenceAllowed) return;
  try {
    window.localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(annotations));
  } catch (error) {
    console.warn("Unable to save Foundations annotations", error);
  }
}

function loadTaskState() {
  try {
    const raw = window.localStorage.getItem(TASK_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (error) {
    console.warn("Unable to load task checklist state", error);
    return {};
  }
}

function saveTaskState(tasks = taskState) {
  try {
    window.localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
  } catch (error) {
    console.warn("Unable to save task checklist state", error);
  }
}

function readStorageValue(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn(`Unable to read ${PROJECT_ID} reader preference`, error);
    return null;
  }
}

function writeStorageValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch (error) {
    console.warn(`Unable to save ${PROJECT_ID} reader preference`, error);
    return false;
  }
}

function announce(message) {
  if (!els.announcer || !message) return;
  els.announcer.textContent = "";
  requestAnimationFrame(() => {
    els.announcer.textContent = message;
  });
}

function getAnnotationsForNote(moduleId, noteId) {
  return state.annotations.items.filter((item) => (
    item.moduleId === moduleId && getAnnotationContextId(item) === noteId
  ));
}

function getArchivedAnnotations(moduleId) {
  return getAnnotationsForNote(moduleId, getAnnotationArchiveNoteId(moduleId));
}

function getElementFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element ?? null;
}

function getKnowledgeArticleFromNode(node) {
  return getElementFromNode(node)?.closest?.(".knowledge-article") ?? null;
}

function isAllContentAnnotationScope() {
  return PROJECT_ID === "finance" && document.body.dataset.annotationScope === "all-content";
}

function getAnnotationContextFromNode(node) {
  const element = getElementFromNode(node);
  if (!element) return null;
  const context = isAllContentAnnotationScope()
    ? element.closest("[data-annotation-context]")
    : element.closest(".knowledge-article");
  return context && els.sectionList.contains(context) ? context : null;
}

function getAnnotationContextElement(contextId) {
  if (!contextId) return null;
  const context = els.sectionList.querySelector(
    `[data-annotation-context="${CSS.escape(contextId)}"]`,
  );
  if (isAllContentAnnotationScope()) return context;
  return context?.matches(".knowledge-article") ? context : null;
}

function getAnnotationContextTitle(context, fallback = "") {
  return context?.dataset.annotationTitle
    || context?.dataset.sectionTitle
    || context?.querySelector("h1, h2, h3, h4, h5, h6")?.textContent?.trim()
    || fallback;
}

function isAnnotationExcludedPosition(node) {
  return Boolean(getElementFromNode(node)?.closest(ANNOTATION_EXCLUDED_SELECTOR));
}

function selectionContainsExcludedContent(range) {
  const fragment = range.cloneContents();
  return Boolean(fragment.querySelector?.(ANNOTATION_EXCLUDED_SELECTOR));
}

function rangeContainsExcludedContent(range) {
  return isAnnotationExcludedPosition(range.startContainer)
    || isAnnotationExcludedPosition(range.endContainer)
    || selectionContainsExcludedContent(range);
}

function getAnnotationTextScope(node, context) {
  const scope = getElementFromNode(node)?.closest(
    "p, li, pre, td, th, blockquote, figcaption, h1, h2, h3, h4, h5, h6, .knowledge-article-intro",
  );
  return scope && context.contains(scope) ? scope : context;
}

function createSelectionError(code, message) {
  return { error: { code, message } };
}

function getSelectionAnnotationContext() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const rawSelectedText = selection.toString();
  const selectedText = rawSelectedText.trim();
  if (selectedText.length < 2) return null;
  if (rangeContainsExcludedContent(range)) {
    return createSelectionError("excluded-content", "这部分内容不支持批注，请选择正文文字。");
  }

  const startContext = getAnnotationContextFromNode(range.startContainer);
  const endContext = getAnnotationContextFromNode(range.endContainer);
  if (!startContext && !endContext) return null;
  if (!startContext || startContext !== endContext) {
    return createSelectionError("cross-context", "一次只能批注同一个内容区块中的文字。");
  }
  if (
    getAnnotationTextScope(range.startContainer, startContext)
    !== getAnnotationTextScope(range.endContainer, endContext)
  ) {
    return createSelectionError("cross-semantic-block", "请将选择范围限制在同一段、同一列表项或同一表格单元格内。");
  }

  const contextId = startContext.dataset.annotationContext || startContext.dataset.noteId;
  const noteId = startContext.dataset.noteId ?? "";
  const moduleId = state.currentModule?.id;
  if (!moduleId || !contextId) return null;

  const rangeStartOffset = getTextOffset(startContext, range.startContainer, range.startOffset);
  if (rangeStartOffset < 0) {
    return createSelectionError("unresolved-selection", "无法定位这段文字，请缩小选择范围后重试。");
  }
  const contextText = getTextNodes(startContext).map((node) => node.nodeValue).join("");
  const anchored = createAnnotationAnchor({
    contextId,
    contextText,
    selectedText: rawSelectedText,
    selectionStart: rangeStartOffset,
  });
  if (!anchored) {
    return createSelectionError("unresolved-selection", "无法稳定定位这段文字，请缩小选择范围后重试。");
  }

  return {
    moduleId,
    contextId: anchored.contextId,
    anchor: anchored.anchor,
    noteId,
    contextTitle: getAnnotationContextTitle(startContext),
    selectedText: anchored.anchor.selectedText,
    matchIndex: anchored.anchor.matchIndex,
    rect: range.getBoundingClientRect(),
  };
}

function hideAnnotationToolbar() {
  state.annotationToolbar?.remove();
  state.annotationToolbar = null;
  state.pendingAnnotation = null;
}

function hideAnnotationSelectionWarning() {
  state.annotationSelectionWarning?.remove();
  state.annotationSelectionWarning = null;
}

function showAnnotationSelectionWarning(message) {
  hideAnnotationSelectionWarning();
  if (!message) return;
  const warning = document.createElement("div");
  warning.className = "annotation-selection-warning";
  warning.setAttribute("role", "status");
  warning.textContent = message;
  document.body.append(warning);
  state.annotationSelectionWarning = warning;
  window.setTimeout(() => {
    if (state.annotationSelectionWarning === warning) hideAnnotationSelectionWarning();
  }, 2800);
}

function handleAnnotationSelection() {
  const result = getSelectionAnnotationContext();
  if (result?.error) {
    hideAnnotationToolbar();
    showAnnotationSelectionWarning(result.error.message);
    return;
  }
  hideAnnotationSelectionWarning();
  if (result) renderAnnotationToolbar(result);
  else hideAnnotationToolbar();
}

function renderAnnotationToolbar(context) {
  hideAnnotationToolbar();
  if (context?.error) return context;
  if (!context?.rect || !context?.contextId) return null;
  const toolbar = document.createElement("div");
  toolbar.className = "annotation-toolbar";
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute("aria-label", "批注操作");
  toolbar.innerHTML = `
    <button type="button" data-annotation-mode="highlight">高亮</button>
    <button type="button" data-annotation-mode="note">笔记</button>
  `;
  toolbar.style.position = "fixed";
  toolbar.querySelectorAll("[data-annotation-mode]").forEach((button) => {
    button.addEventListener("click", () => createAnnotationFromSelection(button.dataset.annotationMode));
  });
  document.body.append(toolbar);
  const viewportWidth = document.documentElement.clientWidth || window.innerWidth;
  const viewportHeight = document.documentElement.clientHeight || window.innerHeight;
  const toolbarRect = toolbar.getBoundingClientRect();
  const desiredLeft = context.rect.left + context.rect.width / 2 - toolbarRect.width / 2;
  const desiredTop = context.rect.top - toolbarRect.height - 8;
  const fallbackTop = context.rect.bottom + 8;
  toolbar.style.left = `${Math.min(
    Math.max(12, desiredLeft),
    Math.max(12, viewportWidth - toolbarRect.width - 12),
  )}px`;
  toolbar.style.top = `${Math.min(
    Math.max(12, desiredTop >= 12 ? desiredTop : fallbackTop),
    Math.max(12, viewportHeight - toolbarRect.height - 12),
  )}px`;
  state.annotationToolbar = toolbar;
  state.pendingAnnotation = context;
  return context;
}

function createAnnotationId() {
  return `${PROJECT_ID}-ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
  if (!context?.moduleId || !context?.contextId || !context?.anchor) return;
  const now = new Date().toISOString();
  const annotationMode = mode === "note" ? "note" : "highlight";
  const annotation = {
    id: createAnnotationId(),
    projectId: PROJECT_ID,
    moduleId: context.moduleId,
    contextId: context.contextId,
    ...(context.noteId ? { noteId: context.noteId } : {}),
    anchor: { ...context.anchor },
    selectedText: context.anchor.selectedText,
    matchIndex: context.anchor.matchIndex,
    mode: annotationMode,
    category: annotationMode === "note" ? "understanding" : "highlight",
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
  const createdMark = els.sectionList.querySelector(
    `.knowledge-highlight[data-annotation-id="${CSS.escape(annotation.id)}"]`,
  );
  setActiveKnowledgeContext(context.contextId);
  updateAnnotationCount();
  announce(annotationMode === "note" ? "已添加笔记批注" : "已添加高亮批注");
  if (annotationMode === "note") {
    openNotePanelForContext({ focusEditor: true, returnFocus: createdMark });
  }
}

function updateAnnotationNote(annotationId, value) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.note = value;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
}

function updateAnnotationCategory(annotationId, category, focusSurface) {
  if (!ANNOTATION_CATEGORIES.some((item) => item.id === category)) return;
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.category = category;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
  renderActiveContextualNotePanel();
  requestAnimationFrame(() => {
    focusSurface?.querySelector(
      `[data-annotation-category="${CSS.escape(annotationId)}"]`,
    )?.focus({ preventScroll: true });
  });
}

function deleteAnnotation(annotationId, behavior) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const returnState = state.annotationReturnFocus;
  const returnContext = returnState?.context;
  const returnSurface = returnState?.trigger?.closest?.(".note-surface");
  const returnSurfaceId = returnSurface?.id ?? "";
  const returnManageIndex = returnSurface
    ? [...returnSurface.querySelectorAll("[data-annotation-manage]")].indexOf(returnState.trigger)
    : -1;
  const keepNote = behavior === "highlight-only" && annotation.mode === "note";
  if (keepNote) {
    annotation.highlightActive = false;
    annotation.updatedAt = new Date().toISOString();
  } else {
    state.annotations.items = state.annotations.items.filter((item) => item.id !== annotationId);
  }
  saveAnnotations();
  hideAnnotationDeletePopover({ restoreFocus: false });
  applyHighlights();
  renderActiveContextualNotePanel();
  updateAnnotationCount();
  announce(keepNote ? "已删除原文高亮，笔记已保留" : "已删除批注");
  if (returnSurfaceId) {
    requestAnimationFrame(() => {
      const surface = document.getElementById(returnSurfaceId);
      const remainingManageButtons = [...(surface?.querySelectorAll("[data-annotation-manage]") ?? [])];
      const sameAnnotationButton = keepNote
        ? surface?.querySelector(`[data-annotation-manage="${CSS.escape(annotationId)}"]`)
        : null;
      const adjacentButton = remainingManageButtons[
        Math.min(Math.max(returnManageIndex, 0), Math.max(remainingManageButtons.length - 1, 0))
      ];
      const fallbackControl = els.shell.classList.contains("is-mobile-note-open")
        ? els.closeMobileNote
        : els.noteRailToggle ?? els.toggleNote;
      (sameAnnotationButton ?? adjacentButton ?? fallbackControl)?.focus({ preventScroll: true });
    });
    return;
  }
  if (returnContext?.isConnected) {
    if (!returnContext.hasAttribute("tabindex")) returnContext.setAttribute("tabindex", "-1");
    requestAnimationFrame(() => returnContext.focus({ preventScroll: true }));
  }
}

function hideAnnotationDeletePopover({ restoreFocus = true } = {}) {
  const returnTarget = state.annotationReturnFocus?.trigger;
  const wasMobileModalLayer = state.annotationDeletePopover?.dataset.mobileModalLayer === "true";
  state.annotationDeletePopover?.remove();
  state.annotationDeletePopover = null;
  state.annotationReturnFocus = null;
  if (wasMobileModalLayer && els.shell.classList.contains("is-mobile-note-open")) {
    els.mobileNoteDrawer?.setAttribute("aria-modal", "true");
  }
  if (restoreFocus && returnTarget?.isConnected) {
    requestAnimationFrame(() => returnTarget.focus({ preventScroll: true }));
  }
}

function showAnnotationDeletePopover(annotationId, rect, trigger = document.activeElement) {
  hideAnnotationDeletePopover({ restoreFocus: false });
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const context = getAnnotationContextElement(getAnnotationContextId(annotation));
  state.annotationReturnFocus = {
    trigger: trigger instanceof HTMLElement ? trigger : null,
    context,
  };
  const annotationContextId = getAnnotationContextId(annotation);
  if (annotationContextId && state.activeKnowledgeNoteId !== annotationContextId) {
    setActiveKnowledgeContext(annotationContextId);
  }
  const popover = document.createElement("div");
  popover.className = "annotation-delete-popover";
  popover.setAttribute("role", "dialog");
  popover.setAttribute("aria-label", "删除批注");
  const layeredOverMobileNote = els.shell.classList.contains("is-mobile-note-open")
    && Boolean(els.mobileNoteDrawer?.contains(trigger));
  if (layeredOverMobileNote) {
    popover.setAttribute("aria-modal", "true");
    popover.dataset.mobileModalLayer = "true";
    els.mobileNoteDrawer.removeAttribute("aria-modal");
  }
  const keepButton = annotation.mode === "note"
    ? `<button type="button" data-delete-behavior="highlight-only">只删除高亮，保留笔记</button>`
    : "";
  popover.innerHTML = `
    ${keepButton}
    <button type="button" data-delete-behavior="all">${annotation.mode === "note" ? "高亮和笔记一起删除" : "删除高亮"}</button>
    <button type="button" data-delete-behavior="cancel">取消</button>
  `;
  popover.style.position = "fixed";
  popover.style.maxWidth = "calc(100vw - 24px)";
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
  const viewportWidth = document.documentElement.clientWidth || window.innerWidth;
  const viewportHeight = document.documentElement.clientHeight || window.innerHeight;
  const popoverRect = popover.getBoundingClientRect();
  const desiredTop = rect.bottom + 8;
  const fallbackTop = rect.top - popoverRect.height - 8;
  popover.style.left = `${Math.min(
    Math.max(12, rect.left),
    Math.max(12, viewportWidth - popoverRect.width - 12),
  )}px`;
  popover.style.top = `${Math.min(
    Math.max(12, desiredTop + popoverRect.height <= viewportHeight - 12 ? desiredTop : fallbackTop),
    Math.max(12, viewportHeight - popoverRect.height - 12),
  )}px`;
  state.annotationDeletePopover = popover;
  requestAnimationFrame(() => popover.querySelector("button")?.focus());
}

function getTextNodes(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.parentElement?.closest("[data-annotation-exclude]")) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  return nodes;
}

function clearHighlights() {
  els.sectionList.querySelectorAll(".knowledge-highlight").forEach((mark) => {
    mark.replaceWith(...mark.childNodes);
  });
  els.sectionList.normalize();
}

function getTextOffset(root, targetNode, targetOffset) {
  let absoluteOffset = 0;
  for (const node of getTextNodes(root)) {
    if (node === targetNode) return absoluteOffset + targetOffset;
    absoluteOffset += node.nodeValue.length;
  }
  if (targetNode !== root && !root.contains(targetNode)) return -1;
  try {
    const prefixRange = document.createRange();
    prefixRange.selectNodeContents(root);
    prefixRange.setEnd(targetNode, targetOffset);
    const container = document.createElement("div");
    container.append(prefixRange.cloneContents());
    container.querySelectorAll("[data-annotation-exclude]").forEach((element) => element.remove());
    return container.textContent.length;
  } catch {
    return -1;
  }
}

function getTextPosition(nodes, absoluteOffset, bias) {
  let traversed = 0;
  for (const [index, node] of nodes.entries()) {
    const next = traversed + node.nodeValue.length;
    if (
      absoluteOffset < next
      || (absoluteOffset === next && (bias === "end" || index === nodes.length - 1))
    ) {
      return { node, offset: absoluteOffset - traversed };
    }
    traversed = next;
  }
  return null;
}

function findTextRange(root, annotationOrSelectedText, matchIndex = 0) {
  const nodes = getTextNodes(root);
  const combinedText = nodes.map((node) => node.nodeValue).join("");
  const annotation = typeof annotationOrSelectedText === "string"
    ? { selectedText: annotationOrSelectedText, matchIndex }
    : annotationOrSelectedText;
  const resolved = resolveAnnotationAnchor(combinedText, annotation);
  if (!resolved) return null;
  const startPosition = getTextPosition(nodes, resolved.startOffset, "start");
  const endPosition = getTextPosition(nodes, resolved.endOffset, "end");
  if (!startPosition || !endPosition) return null;
  const range = document.createRange();
  range.setStart(startPosition.node, startPosition.offset);
  range.setEnd(endPosition.node, endPosition.offset);
  return range;
}

function getRangeDocumentOrder(range) {
  const nodes = getTextNodes(els.sectionList);
  let order = 0;
  for (const node of nodes) {
    if (node === range.startContainer) return order + range.startOffset;
    order += node.nodeValue.length;
  }
  return 0;
}

function applyHighlights() {
  clearHighlights();
  if (!state.currentModule) return;
  const moduleId = state.currentModule.id;
  const activeAnnotations = state.annotations.items.filter((item) => (
    item.moduleId === moduleId && item.highlightActive
  ));
  const resolvedHighlights = [];
  for (const annotation of activeAnnotations) {
    const context = getAnnotationContextElement(getAnnotationContextId(annotation));
    if (!context) continue;
    const range = findTextRange(context, annotation);
    if (!range || rangeContainsExcludedContent(range)) continue;
    resolvedHighlights.push({
      annotation,
      range,
      order: getRangeDocumentOrder(range),
    });
  }
  resolvedHighlights.sort((left, right) => right.order - left.order);
  for (const { annotation, range } of resolvedHighlights) {
    const mark = document.createElement("mark");
    mark.className = `knowledge-highlight${annotation.mode === "note" ? " is-note" : ""}`;
    mark.dataset.annotationId = annotation.id;
    mark.tabIndex = 0;
    mark.setAttribute("role", "button");
    mark.setAttribute("aria-haspopup", "dialog");
    const selectedText = annotation.anchor?.selectedText ?? annotation.selectedText ?? "";
    const conciseText = selectedText.length > 48 ? `${selectedText.slice(0, 48)}…` : selectedText;
    mark.setAttribute("aria-label", `${annotation.mode === "note" ? "带笔记的高亮" : "高亮"}：${conciseText}。按回车管理批注`);
    mark.append(range.extractContents());
    mark.addEventListener("click", (event) => {
      event.stopPropagation();
      showAnnotationDeletePopover(annotation.id, mark.getBoundingClientRect(), mark);
    });
    mark.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      showAnnotationDeletePopover(annotation.id, mark.getBoundingClientRect(), mark);
    });
    range.insertNode(mark);
  }
}

function getInitialModuleId() {
  const url = new URL(window.location.href);
  const fromQuery = url.searchParams.get("module");
  const fromHash = url.hash.replace(/^#/, "");
  return fromQuery || fromHash || state.data?.project?.dashboardModuleId || "overview";
}

function getModuleById(moduleId) {
  return state.data?.modules.find((module) => module.id === moduleId);
}

function getSection(module, title) {
  return module.sections?.[title] ?? "";
}

function getSectionId(module, title) {
  return module.sectionIds?.[title] ?? `${module.id}-${title}`;
}

function clampProgress(value) {
  return Math.max(0, Math.min(100, Number(value) || 0));
}

function getLearningProgress(module) {
  return clampProgress(module?.learningProgress);
}

function getOverallLearningProgress() {
  return clampProgress(state.data?.project?.overallLearningProgress);
}

function getStatusLabel(status) {
  const labels = {
    "not-started": "未开始",
    "in-progress": "进行中",
    learning: "学习中",
    review: "复习中",
    done: "已完成",
  };
  return labels[status] ?? status;
}

function getModuleMeta(module, { includeDate = false } = {}) {
  const parts = PROJECT_ID === "foundations"
    ? module.planScope === "interview"
      ? ["临时面试", getStatusLabel(module.status)]
      : [module.goalRole || getStatusLabel(module.status)]
    : [getStatusLabel(module.status)];
  if (PROJECT_ID !== "finance" && PROJECT_ID !== "foundations" && module.priority) parts.push(module.priority);
  if (includeDate && module.lastUpdated) {
    parts.push(PROJECT_ID === "finance" ? `更新于 ${module.lastUpdated}` : `Updated ${module.lastUpdated}`);
  }
  return parts.join(" · ");
}

function renderThemeToggle(theme) {
  if (!els.toggleTheme) return;
  const isDark = theme === "dark";
  els.toggleTheme.setAttribute("aria-pressed", isDark ? "true" : "false");
  els.toggleTheme.setAttribute("aria-label", isDark ? "切换日间模式" : "切换夜间模式");
  const icon = els.toggleTheme.querySelector("svg");
  if (icon) {
    icon.innerHTML = isDark
      ? '<circle cx="12" cy="12" r="3.6" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 2.6v2M12 19.4v2M2.6 12h2M19.4 12h2M5.35 5.35l1.42 1.42M17.23 17.23l1.42 1.42M18.65 5.35l-1.42 1.42M6.77 17.23l-1.42 1.42" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
      : '<path d="M20 15.5A7.5 7.5 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />';
  }
}

function setTheme(theme, { persist = false } = {}) {
  const normalized = resolveInitialTheme({
    projectId: PROJECT_ID,
    storedTheme: theme,
    htmlTheme: document.body.dataset.theme,
  });
  document.body.dataset.theme = normalized;
  renderThemeToggle(normalized);
  if (persist) writeStorageValue(THEME_STORAGE_KEY, normalized);
}

function updateNotePanelControls() {
  const mobile = window.matchMedia("(max-width: 1100px)").matches;
  const mobileOpen = els.shell.classList.contains("is-mobile-note-open");
  const desktopExpanded = !els.shell.classList.contains("is-note-collapsed");
  const expanded = mobile ? mobileOpen : desktopExpanded;
  for (const control of [els.toggleNote, els.noteRailToggle]) {
    if (!control) continue;
    control.setAttribute("aria-expanded", expanded ? "true" : "false");
    control.setAttribute("aria-label", expanded ? "收起学习批注" : "展开学习批注");
  }
  els.mobileNoteDrawer?.setAttribute("aria-hidden", mobileOpen ? "false" : "true");
}

function updateDirectoryControls() {
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  const expanded = mobile
    ? els.shell.classList.contains("is-mobile-left-open")
    : !els.shell.classList.contains("is-left-collapsed");
  els.toggleLeftControls.forEach((control) => {
    control.setAttribute("aria-expanded", expanded ? "true" : "false");
    control.setAttribute(
      "aria-label",
      mobile
        ? expanded ? "关闭模块目录" : "打开模块目录"
        : expanded ? "收起模块目录" : "展开模块目录",
    );
  });
}

function refreshSizeDependentUi() {
  scheduleFinanceKnowledgeMapEdges();
  enhanceFinanceTables(els.sectionList);
}

function scheduleReaderLayoutRefresh() {
  requestAnimationFrame(refreshSizeDependentUi);
  window.setTimeout(refreshSizeDependentUi, 220);
}

function setDesktopNotePanelCollapsed(collapsed, { persist = false, peeking = false } = {}) {
  const shouldCollapse = Boolean(collapsed);
  els.shell.classList.toggle("is-note-collapsed", shouldCollapse);
  els.shell.classList.toggle("is-note-peeking", peeking && !shouldCollapse);
  if (persist) {
    state.notePanelPreferenceCollapsed = shouldCollapse;
    els.shell.classList.remove("is-note-peeking");
    writeStorageValue(NOTE_PANEL_STORAGE_KEY, shouldCollapse ? "collapsed" : "expanded");
  }
  updateNotePanelControls();
  scheduleReaderLayoutRefresh();
}

function restoreNotePanelPreference() {
  const savedPreference = readStorageValue(NOTE_PANEL_STORAGE_KEY);
  const collapsed = savedPreference === "collapsed"
    ? true
    : savedPreference === "expanded"
      ? false
      : getDefaultNotePanelCollapsed(PROJECT_ID);
  state.notePanelPreferenceCollapsed = collapsed;
  setDesktopNotePanelCollapsed(collapsed);
}

function updateMobileDrawerInert() {
  const noteOpen = els.shell.classList.contains("is-mobile-note-open")
    && Boolean(els.closeMobileNote);
  const directoryOpen = els.shell.classList.contains("is-mobile-left-open")
    && window.matchMedia("(max-width: 860px)").matches;
  if (els.toolbar) els.toolbar.inert = noteOpen || directoryOpen;
  if (els.sidebar) els.sidebar.inert = noteOpen;
  if (els.main) els.main.inert = noteOpen || directoryOpen;
  if (directoryOpen) {
    els.sidebar?.setAttribute("role", "dialog");
    els.sidebar?.setAttribute("aria-modal", "true");
  } else {
    els.sidebar?.removeAttribute("role");
    els.sidebar?.removeAttribute("aria-modal");
  }
}

function setMobileNoteOpen(open, returnFocus = document.activeElement) {
  const shouldOpen = Boolean(open);
  if (shouldOpen) {
    state.drawerReturnFocus = returnFocus instanceof HTMLElement ? returnFocus : els.toggleNote;
    els.shell.classList.remove("is-mobile-left-open");
  }
  els.shell.classList.toggle("is-mobile-note-open", shouldOpen);
  updateMobileDrawerInert();
  updateNotePanelControls();
  updateDirectoryControls();
  if (shouldOpen) {
    requestAnimationFrame(() => (els.closeMobileNote ?? els.mobileNoteDrawer)?.focus());
  } else {
    const focusTarget = state.drawerReturnFocus;
    state.drawerReturnFocus = null;
    if (focusTarget?.isConnected) requestAnimationFrame(() => focusTarget.focus());
  }
}

function setMobileDirectoryOpen(open, returnFocus = document.activeElement) {
  const shouldOpen = Boolean(open);
  if (shouldOpen) {
    state.drawerReturnFocus = returnFocus instanceof HTMLElement ? returnFocus : null;
    els.shell.classList.remove("is-mobile-note-open");
  }
  els.shell.classList.toggle("is-mobile-left-open", shouldOpen);
  updateMobileDrawerInert();
  updateNotePanelControls();
  updateDirectoryControls();
  if (shouldOpen) {
    requestAnimationFrame(() => els.nav.querySelector(".module-nav-item[aria-current='true']")?.focus());
  } else {
    const focusTarget = state.drawerReturnFocus;
    state.drawerReturnFocus = null;
    if (focusTarget?.isConnected) requestAnimationFrame(() => focusTarget.focus());
  }
}

function closeMobileDrawers({ restoreFocus = true } = {}) {
  const focusTarget = restoreFocus ? state.drawerReturnFocus : null;
  els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
  updateMobileDrawerInert();
  els.mobileNoteDrawer?.setAttribute("aria-hidden", "true");
  state.drawerReturnFocus = null;
  updateNotePanelControls();
  updateDirectoryControls();
  if (focusTarget?.isConnected) requestAnimationFrame(() => focusTarget.focus());
}

function openNotePanelForContext({ focusEditor = false, returnFocus = document.activeElement } = {}) {
  if (window.matchMedia("(max-width: 1100px)").matches) {
    setMobileNoteOpen(true, returnFocus);
    if (focusEditor) {
      requestAnimationFrame(() => els.mobileNoteSurface.querySelector("textarea")?.focus({ preventScroll: true }));
    }
    return;
  }
  if (state.notePanelPreferenceCollapsed) {
    setDesktopNotePanelCollapsed(false, { peeking: true });
  }
  if (focusEditor) {
    requestAnimationFrame(() => els.noteSurface.querySelector("textarea")?.focus({ preventScroll: true }));
  }
}

function updateAnnotationCount() {
  const count = state.annotations.items.filter((item) => item.projectId === PROJECT_ID).length;
  if (!els.noteCount) return;
  els.noteCount.textContent = String(count);
  els.noteCount.setAttribute("aria-label", `${count} 条批注`);
}

function getReaderScrollOwner() {
  if (window.matchMedia("(max-width: 860px)").matches) {
    return document.scrollingElement ?? document.documentElement;
  }
  return els.main;
}

function getReaderScrollEventTarget() {
  const owner = getReaderScrollOwner();
  return owner === document.scrollingElement || owner === document.documentElement || owner === document.body
    ? window
    : owner;
}

function scrollElementToTopImmediately(element) {
  if (!element) return;
  const previousScrollBehavior = element.style.scrollBehavior;
  element.style.scrollBehavior = "auto";
  element.scrollTo({ top: 0, left: 0, behavior: "auto" });
  element.scrollTop = 0;
  element.style.scrollBehavior = previousScrollBehavior;
}

function resetReaderScroll() {
  const owner = getReaderScrollOwner();
  const documentOwner = document.scrollingElement ?? document.documentElement;
  scrollElementToTopImmediately(owner);
  if (documentOwner !== owner) scrollElementToTopImmediately(documentOwner);
  if (els.main !== owner) scrollElementToTopImmediately(els.main);
}

function renderModuleNav() {
  els.nav.innerHTML = "";
  const createModuleButton = (module) => {
    const progress = getLearningProgress(module);
    const button = document.createElement("button");
    button.className = `module-nav-item${module.planScope ? ` is-${module.planScope}` : ""}`;
    button.type = "button";
    button.dataset.moduleId = module.id;
    button.setAttribute("aria-current", module.id === state.currentModule?.id ? "true" : "false");
    button.innerHTML = `
      <span class="module-nav-title">${escapeHtml(module.title)}</span>
      ${module.planScope === "interview" || PROJECT_ID === "finance" ? `<span class="module-nav-progress">${escapeHtml(String(progress))}%</span>` : ""}
      <span class="module-nav-meta">${escapeHtml(getModuleMeta(module))}</span>
    `;
    button.addEventListener("click", () => openModule(module.id));
    return button;
  };

  if (PROJECT_ID !== "foundations" || !state.data.project.navigationGroups?.length) {
    for (const module of state.data.modules) els.nav.append(createModuleButton(module));
    return;
  }

  const moduleById = new Map(state.data.modules.map((module) => [module.id, module]));
  for (const group of state.data.project.navigationGroups) {
    const wrapper = document.createElement("section");
    wrapper.className = `module-nav-group is-${group.scope}`;
    wrapper.setAttribute("aria-labelledby", `module-nav-group-${group.id}`);
    const heading = document.createElement("p");
    heading.className = "module-nav-group-title";
    heading.id = `module-nav-group-${group.id}`;
    heading.textContent = group.title;
    wrapper.append(heading);

    for (const item of group.items) {
      if (item.type === "module") {
        const module = moduleById.get(item.moduleId);
        if (module) wrapper.append(createModuleButton(module));
        continue;
      }
      const slot = document.createElement("div");
      slot.className = "module-nav-frozen-slot";
      slot.setAttribute("role", "note");
      slot.setAttribute("aria-label", `${item.title}，冻结插槽，${item.note}`);
      slot.innerHTML = `
        <span class="module-nav-frozen-id">${escapeHtml(item.subsystemId)}</span>
        <span class="module-nav-frozen-copy"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.note)}</small></span>
        <span aria-hidden="true">冻</span>
      `;
      wrapper.append(slot);
    }
    els.nav.append(wrapper);
  }
}

function getRailTargets(module) {
  const sectionTitles = PROJECT_ID === "foundations" && module.id === "career-roadmap"
    ? ["当前状态", "任务", "目标", "核心知识", "时间线"]
    : Object.keys(module.sections ?? {});
  const sectionTargets = sectionTitles.flatMap((sectionTitle) => [
    {
      id: getSectionId(module, sectionTitle),
      title: sectionTitle,
    },
    ...(module.id === "career-roadmap" && sectionTitle === "目标"
      ? [{ id: `${getSectionId(module, sectionTitle)}-evidence`, title: "能力证据" }]
      : []),
  ]);
  const noteTargets = (module.knowledgeNotes ?? []).map((note) => ({
    id: note.id,
    title: note.title,
  }));
  const archiveTargets = getArchivedAnnotations(module.id).length > 0
    ? [{ id: getAnnotationArchiveNoteId(module.id), title: "历史笔记" }]
    : [];
  return [...sectionTargets, ...noteTargets, ...archiveTargets];
}

function renderSectionRail(module) {
  els.sectionLines.innerHTML = "";
  getRailTargets(module).forEach((target) => {
    const button = document.createElement("button");
    button.className = "section-line";
    button.type = "button";
    button.dataset.sectionId = target.id;
    button.title = target.title;
    button.setAttribute("aria-label", target.title);
    button.setAttribute("aria-current", "false");
    button.innerHTML = `<span class="section-tooltip">${escapeHtml(target.title)}</span>`;
    button.addEventListener("click", () => {
      invalidateDeferredNavigation();
      document.querySelector(`#${CSS.escape(target.id)}`)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      setActiveSection(target.id);
    });
    els.sectionLines.append(button);
  });
}

function renderProgressSummary(module) {
  const progress = getLearningProgress(module);
  const overallProgress = getOverallLearningProgress();
  return `
    <div class="module-progress-summary learning-progress" aria-label="学习进度摘要">
      <div class="progress-ring" style="--progress: ${progress}" aria-label="本模块学习进度 ${progress}%">
        <span>${escapeHtml(String(progress))}%</span>
      </div>
      <div class="progress-copy">
        <p class="progress-label">本模块学习进度</p>
        <p class="progress-status">${escapeHtml(getModuleMeta(module))}</p>
      </div>
      <div class="overall-progress-card" aria-label="整体学习进度 ${overallProgress}%">
        <span class="overall-progress-tag">全部模块</span>
        <span class="overall-progress-value">${escapeHtml(String(overallProgress))}%</span>
      </div>
    </div>
  `;
}

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

function renderTaskSection(module, title) {
  const raw = getSection(module, title);
  if (!raw) return raw;

  const temp = document.createElement("div");
  temp.innerHTML = raw;

  const groups = [];
  let current = { heading: "", intro: [], items: [] };
  temp.childNodes.forEach((node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (node.tagName === "H3") {
      if (current.heading || current.intro.length || current.items.length) groups.push(current);
      current = { heading: node.textContent, intro: [], items: [] };
    } else if (node.tagName === "OL" || node.tagName === "UL") {
      node.querySelectorAll(":scope > li").forEach((li) => {
        current.items.push(li.innerHTML);
      });
    } else if (node.tagName === "P") {
      current.intro.push(node.innerHTML);
    }
  });
  if (current.heading || current.intro.length || current.items.length) groups.push(current);

  const hasCheckableItems = groups.some((group) => group.items.length > 0);
  if (!hasCheckableItems) return raw;

  return groups
    .map((group, groupIndex) => {
      const introHtml = group.intro.map((html) => `<p>${html}</p>`).join("");
      const itemsHtml = group.items
        .map((html, itemIndex) => {
          const taskId = `${module.id}__${title}__${groupIndex}__${itemIndex}`;
          const isDone = Boolean(taskState[taskId]);
          return `
            <li class="task-item${isDone ? " is-done" : ""}">
              <label>
                <input type="checkbox" data-task-id="${escapeHtml(taskId)}" ${isDone ? "checked" : ""} />
                <span>${html}</span>
              </label>
            </li>
          `;
        })
        .join("");
      return `
        ${group.heading ? `<h3>${escapeHtml(group.heading)}</h3>` : ""}
        ${introHtml}
        ${itemsHtml ? `<ul class="task-list">${itemsHtml}</ul>` : ""}
      `;
    })
    .join("");
}

function renderOverviewDashboard(module) {
  return renderFinanceOverviewDashboard(module);
}

function getCareerUnitRuntime(module) {
  const units = module.units ?? [];
  const firstOpenIndex = units.findIndex((unit) => !taskState[unit.taskId]);
  const settledCount = firstOpenIndex === -1 ? units.length : firstOpenIndex;
  const runtimeUnits = units.map((unit, index) => ({
    ...unit,
    runtimeStatus: index < settledCount
      ? "settled"
      : index === settledCount
        ? "active"
        : "frozen",
  }));
  return {
    units: runtimeUnits,
    settledCount,
    activeUnit: runtimeUnits.find((unit) => unit.runtimeStatus === "active") ?? null,
    frozenUnits: runtimeUnits.filter((unit) => unit.runtimeStatus === "frozen"),
  };
}

function getCareerSessionLabel(unit) {
  if (!unit?.sessions) return "";
  const { min, max } = unit.sessions;
  return `${min === max ? min : `${min}–${max}`} session${max === 1 ? "" : "s"}`;
}

function renderCareerWorkbench(module, runtime) {
  const sectionId = getSectionId(module, "当前状态");
  const unit = runtime.activeUnit;
  if (!unit) {
    return `
      <article class="career-workbench-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="当前状态">
        <h2 class="career-section-label">活动单元 · 单线程，只有这一件活</h2>
        <div class="career-empty-state">
          <strong>U1–U7 已全部结算</strong>
          <p>台账已经封存这段进展；下一单元应在一次事件触发校准后再定义。</p>
        </div>
      </article>
    `;
  }
  return `
    <article class="career-workbench-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="当前状态">
      <h2 class="career-section-label">活动单元 · 单线程，只有这一件活</h2>
      <div class="career-workbench">
        <div class="career-workbench-main">
          <div class="career-unit-tags">
            <span class="career-chip is-type">${escapeHtml(unit.type)}</span>
            <span class="career-chip">${escapeHtml(getCareerSessionLabel(unit))}</span>
          </div>
          <p class="career-unit-title">${escapeHtml(unit.id)} ${escapeHtml(unit.title)}</p>
          <p class="career-unit-next"><span>下一步</span>${escapeHtml(unit.nextAction)}</p>
          <div class="career-workbench-actions" aria-label="活动单元辅助动作">
            <button class="career-action" type="button" data-career-log-action="breakpoint">记断点</button>
            <button class="career-action is-quiet" type="button" data-career-log-action="wall">撞墙了</button>
          </div>
        </div>
        <div class="career-seal-slot">
          <button class="career-pending-seal-button" type="button" data-career-settle-unit="${escapeHtml(unit.id)}" aria-label="结算 ${escapeHtml(unit.id)} ${escapeHtml(unit.title)}并落印">
            <span class="career-pending-seal">${escapeHtml(unit.id)}</span>
            <span>结算落印</span>
          </button>
          <p class="career-seal-slot-note">产物与判据成立后再落印</p>
        </div>
      </div>
    </article>
  `;
}

function renderCareerLedger(module, runtime) {
  const sectionId = getSectionId(module, "任务");
  const seals = runtime.units.map((unit) => {
    const justSettled = unit.runtimeStatus === "settled" && state.careerLastSettledUnitId === unit.id;
    return `
      <div class="career-unit-seal is-${escapeHtml(unit.runtimeStatus)}${justSettled ? " is-just-settled" : ""}" data-career-unit-seal="${escapeHtml(unit.id)}" role="img" aria-label="${escapeHtml(unit.id)} ${escapeHtml(unit.title)}，${unit.runtimeStatus === "settled" ? "已结算" : unit.runtimeStatus === "active" ? "活动单元，待印" : "冻结"}">
        <span class="career-unit-seal-id">${escapeHtml(unit.id)}</span>
        <span class="career-unit-seal-title">${escapeHtml(unit.runtimeStatus === "active" ? "待印" : unit.title)}</span>
      </div>
    `;
  }).join("");
  const tickets = Math.floor(runtime.settledCount / 2);
  const untilNextTicket = 2 - (runtime.settledCount % 2);
  const nearby = runtime.frozenUnits.slice(0, 3);
  const distant = runtime.frozenUnits.slice(3);
  const nearbyCards = nearby.length > 0
    ? nearby.map((unit) => `
        <div class="career-frozen-card">
          <span class="career-frozen-id">${escapeHtml(unit.id)}</span>
          <span><strong>${escapeHtml(unit.title)}</strong> · ${escapeHtml(unit.type)} · ${escapeHtml(getCareerSessionLabel(unit))}</span>
          <span class="career-frozen-stamp" aria-hidden="true">冻</span>
        </div>
      `).join("")
    : '<p class="career-empty-state">近期队列已经清空。</p>';
  const distantText = distant.length > 0
    ? distant.map((unit) => `${unit.id} ${unit.title}`).join(" · ")
    : "记忆系统 · 实时语音 pipeline · 系统层源码笔记 · 跨子系统整合——到队头再定义";
  return `
    <article class="career-ledger-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="任务">
      <h2 class="career-section-label">台账 · 只涨不跌</h2>
      <div class="career-ledger-strip">
        <div class="career-ledger-seals">${seals}</div>
        <div class="career-ledger-meta">
          <p class="career-ledger-count"><strong>${escapeHtml(String(runtime.settledCount))}</strong><span>已结算</span></p>
          <p class="career-ticket">玩耍券 ×${escapeHtml(String(tickets))} · 再结算 ${escapeHtml(String(untilNextTicket))} 个解锁</p>
        </div>
      </div>
      <h3 class="career-section-label is-subsection">冻结队列 · 封存待取，不是欠债</h3>
      <div class="career-frozen-queue">${nearbyCards}</div>
      <p class="career-distant-queue">远期：${escapeHtml(distantText)}</p>
    </article>
  `;
}

function renderCareerGoalTrace(runtime) {
  const unit = runtime.activeUnit;
  if (!unit) {
    return `
      <div class="career-goal-trace-empty">
        <strong>这一批单元已经全部结算</strong>
        <p>下一条路径应在事件触发校准后再写入；主板不会替你自动生成新方向。</p>
      </div>
    `;
  }

  const mapping = unit.goalMapping ?? {};
  const subsystemById = new Map((state.data?.project?.subsystems ?? []).map((subsystem) => [subsystem.id, subsystem]));
  const mappedSubsystems = (mapping.subsystemIds ?? [])
    .map((subsystemId) => subsystemById.get(subsystemId))
    .filter(Boolean);
  const subsystemItems = mappedSubsystems.length > 0
    ? mappedSubsystems.map((subsystem) => `<li><span>${escapeHtml(subsystem.id)}</span>${escapeHtml(subsystem.title)}</li>`).join("")
    : "<li>尚未映射子系统</li>";
  const pathLabel = mapping.pathLabel || "等待路线图映射";
  const stageLabel = mapping.stageLabel || "当前阶段";
  const targetGoal = state.data?.project?.targetGoal || "长期目标";

  return `
    <div class="career-goal-trace" aria-label="当前单元通往长期目标的路径">
      <p class="career-goal-trace-lede"><strong>${escapeHtml(unit.id)} ${escapeHtml(unit.title)}</strong>现在承担的是“${escapeHtml(pathLabel)}”：它把当前实验接回长期系统目标。</p>
      <ol class="career-goal-trace-steps">
        <li class="career-goal-trace-step is-current">
          <span class="career-goal-trace-label">当前单元</span>
          <strong>${escapeHtml(unit.id)} ${escapeHtml(unit.title)}</strong>
          <small>${escapeHtml(unit.type)} · ${escapeHtml(getCareerSessionLabel(unit))}</small>
        </li>
        <li class="career-goal-trace-step">
          <span class="career-goal-trace-label">形成作用</span>
          <strong>${escapeHtml(pathLabel)}</strong>
          <small>来自“${escapeHtml(mapping.sourceSection || "行动映射")}”</small>
        </li>
        <li class="career-goal-trace-step is-systems">
          <span class="career-goal-trace-label">作用范围</span>
          <ul class="career-goal-trace-systems">${subsystemItems}</ul>
        </li>
        <li class="career-goal-trace-step">
          <span class="career-goal-trace-label">结果窗口</span>
          <strong>${escapeHtml(stageLabel)}</strong>
          <small>窗口提供远景坐标，不制造日历债</small>
        </li>
      </ol>
      <p class="career-goal-trace-north-star"><span>北极星</span><strong>${escapeHtml(targetGoal)}</strong></p>
      <p class="career-board-source">路径来自路线图的显式映射；它说明“为什么做”，不代表任何深度已经掌握。</p>
    </div>
  `;
}

function renderCareerBoard(module, runtime) {
  const sectionId = getSectionId(module, "目标");
  const focusSelected = state.careerBoardView !== "overview";
  return `
    <article class="career-board-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="目标">
      <div class="career-board-heading">
        <h2 class="career-section-label">贾维斯 0.x · 当前路径与系统总览</h2>
        <div class="career-board-view-switch" role="group" aria-label="主板视图">
          <button type="button" data-career-board-view="focus" aria-pressed="${focusSelected ? "true" : "false"}" aria-controls="career-board-focus">当前路径</button>
          <button type="button" data-career-board-view="overview" aria-pressed="${focusSelected ? "false" : "true"}" aria-controls="career-board-overview">系统总览</button>
        </div>
      </div>
      <div class="career-board-panel career-board-focus" id="career-board-focus" data-career-board-panel="focus"${focusSelected ? "" : " hidden"}>
        ${renderCareerGoalTrace(runtime)}
      </div>
      <div class="career-board-panel career-board-overview" id="career-board-overview" data-career-board-panel="overview"${focusSelected ? " hidden" : ""}>
        <div class="career-board-scroll" tabindex="0" aria-label="可横向滚动查看六子系统完整主板">
          <svg class="career-mainboard" viewBox="0 0 900 560" role="group" aria-labelledby="career-mainboard-title career-mainboard-description">
            <title id="career-mainboard-title">贾维斯 0.x 六子系统主板</title>
            <desc id="career-mainboard-description">六个子系统的长期能力地图。人格与情感、实时多模态是冻结插槽，其余插槽链接到现有学习模块。</desc>
            <rect class="career-board-outline" x="10" y="10" width="880" height="540" rx="16" />
            <rect class="career-board-inner-outline" x="20" y="20" width="860" height="520" rx="11" />
            <g class="career-board-mounts"><circle cx="34" cy="34" r="6"/><circle cx="866" cy="34" r="6"/><circle cx="34" cy="526" r="6"/><circle cx="866" cy="526" r="6"/></g>
            <text class="career-board-silkscreen is-title" x="105" y="52">JARVIS 0.x — MAINBOARD REV 0.1</text>
            <text class="career-board-silkscreen is-caption" x="105" y="70">SINGLE-THREAD ASSEMBLY · SETTLEMENT LEDGER · EST. 2026</text>
            <text class="career-board-silkscreen is-caption" x="450" y="84" text-anchor="middle">SIX-SYSTEM BACKPLANE</text>
            <path class="career-board-backplane" d="M452 148 V463 M428 148 H476 M428 308 H476 M428 463 H476" />
            <g class="career-board-backplane-nodes"><circle cx="452" cy="148" r="4"/><circle cx="452" cy="308" r="4"/><circle cx="452" cy="463" r="4"/></g>

            <a class="career-board-link" href="?module=llm-systems" data-career-module-id="llm-systems" aria-label="打开 LLM Systems：基座模型">
              <g class="career-board-slot is-supplied">
                <rect x="146" y="92" width="282" height="112" rx="8" />
                <text class="career-board-slot-code" x="166" y="124">① BASE MODEL</text>
                <text class="career-board-slot-title" x="166" y="150">基座模型 · 外部供货</text>
                <text class="career-board-slot-note" x="166" y="176">LLM Systems · 懂原理、边界与供给约束</text>
              </g>
            </a>

            <g class="career-board-slot is-frozen">
              <rect x="476" y="92" width="278" height="112" rx="8" />
              <text class="career-board-slot-code" x="496" y="124">② PERSONA</text>
              <text class="career-board-slot-title" x="496" y="150">人格与情感</text>
              <text class="career-board-slot-note" x="496" y="174">冻结 · U4–U6 到队头再定义</text>
            </g>

            <a class="career-board-link" href="?module=rag-memory" data-career-module-id="rag-memory" aria-label="打开 Lifelong Memory：终身记忆">
              <g class="career-board-slot">
                <rect x="146" y="252" width="282" height="112" rx="8" />
                <text class="career-board-slot-code" x="166" y="284">③ LIFELONG MEMORY</text>
                <text class="career-board-slot-title" x="166" y="310">终身记忆</text>
                <text class="career-board-slot-note" x="166" y="334">写入 · 整合 · 遗忘 · 反思</text>
              </g>
            </a>

            <g class="career-board-slot is-frozen">
              <rect x="476" y="252" width="278" height="112" rx="8" />
              <text class="career-board-slot-code" x="496" y="284">④ REALTIME MULTIMODAL</text>
              <text class="career-board-slot-title" x="496" y="310">实时多模态交互</text>
              <text class="career-board-slot-note" x="496" y="334">冻结 · 到相关单元再定义</text>
            </g>

            <a class="career-board-link" href="?module=agent-design" data-career-module-id="agent-design" aria-label="打开 Agent Runtime：Agent 执行">
              <g class="career-board-slot">
                <rect x="146" y="412" width="282" height="102" rx="8" />
                <text class="career-board-slot-code" x="166" y="442">⑤ AGENT EXEC</text>
                <text class="career-board-slot-title" x="166" y="468">Agent 执行 · 安全运行时</text>
                <rect class="career-board-chip is-archive" x="166" y="480" width="104" height="22" rx="3" />
                <text class="career-board-chip-text" x="218" y="495" text-anchor="middle">CYRENE 0.0</text>
                <rect class="career-board-chip is-socket" x="286" y="480" width="122" height="22" rx="3" />
                <text class="career-board-chip-text is-socket" x="347" y="495" text-anchor="middle">0.1 SOCKET · U7</text>
              </g>
            </a>

            <g class="career-board-slot">
              <rect x="476" y="412" width="278" height="102" rx="8" />
              <text class="career-board-slot-code" x="496" y="442">⑥ SYSTEM LAYER</text>
              <text class="career-board-slot-title" x="496" y="468">系统层 · 推理与工程地基</text>
              <a class="career-board-link is-inline" href="?module=llm-systems" data-career-module-id="llm-systems" aria-label="打开 LLM Systems 系统层内容"><text x="496" y="493">LLM Systems</text></a>
              <text class="career-board-slot-note" x="582" y="493">+</text>
              <a class="career-board-link is-inline" href="?module=coding" data-career-module-id="coding" aria-label="打开 Engineering Foundations"><text x="598" y="493">Engineering Foundations</text></a>
            </g>

            <g class="career-board-corner-seal"><rect x="806" y="44" width="48" height="48" rx="4"/><text x="830" y="75" text-anchor="middle">0.x</text></g>
          </svg>
        </div>
        <p class="career-board-note">这张总览只表达六个子系统及其现有模块入口；单元队列只保留在台账。②与④仍是冻结插槽。</p>
      </div>
    </article>
  `;
}

function renderCareerEvidenceMatrix(module, runtime) {
  const matrix = module.evidenceMatrix;
  if (!matrix?.depthLevels?.length || !matrix?.rows?.length) return "";
  const subsystemById = new Map((state.data?.project?.subsystems ?? []).map((subsystem) => [subsystem.id, subsystem]));
  const activeSubsystemIds = new Set(runtime.activeUnit?.goalMapping?.subsystemIds ?? []);
  const stateLabels = {
    unassessed: "未登记",
    observed: "观察中",
    supported: "有证据",
    revisit: "需复核",
  };
  const headerCells = matrix.depthLevels
    .map((level) => `<th scope="col">${escapeHtml(level.label)}</th>`)
    .join("");
  const rows = matrix.rows.map((row) => {
    const subsystem = subsystemById.get(row.subsystemId) ?? { id: row.subsystemId, title: `子系统 ${row.subsystemId}` };
    const cellsByLevel = new Map((row.cells ?? []).map((cell) => [cell.depthLevelId, cell]));
    const cells = matrix.depthLevels.map((level) => {
      const cell = cellsByLevel.get(level.id) ?? { state: "unassessed", evidenceRefs: [] };
      const cellState = stateLabels[cell.state] ? cell.state : "unassessed";
      const evidenceRefs = Array.isArray(cell.evidenceRefs) ? cell.evidenceRefs.filter(Boolean) : [];
      const evidenceText = evidenceRefs.length > 0 ? `；${evidenceRefs.join("；")}` : "";
      return `
        <td data-evidence-state="${escapeHtml(cellState)}" aria-label="${escapeHtml(subsystem.title)} · ${escapeHtml(level.label)}：${escapeHtml(stateLabels[cellState])}${escapeHtml(evidenceText)}">
          <span class="career-evidence-mark" aria-hidden="true"></span>
          <span class="career-evidence-state">${escapeHtml(stateLabels[cellState])}</span>
        </td>
      `;
    }).join("");
    return `
      <tr${activeSubsystemIds.has(row.subsystemId) ? ' class="is-current-path"' : ""}>
        <th scope="row"><span>${escapeHtml(subsystem.id)}</span><strong>${escapeHtml(subsystem.title)}</strong>${activeSubsystemIds.has(row.subsystemId) ? '<small>当前路径</small>' : ""}</th>
        ${cells}
      </tr>
    `;
  }).join("");
  return `
    <article class="career-evidence-section" id="${escapeHtml(`${getSectionId(module, "目标")}-evidence`)}" data-section-id="${escapeHtml(`${getSectionId(module, "目标")}-evidence`)}" data-section-title="能力证据" aria-labelledby="career-evidence-title">
      <div class="career-evidence-scroll" role="region" tabindex="0" aria-labelledby="career-evidence-title" aria-describedby="career-evidence-note">
        <table class="career-evidence-matrix">
          <caption id="career-evidence-title">
            <strong>能力证据矩阵 · 六系统 × 五深度</strong>
            <span>只登记结算或校准中明确指认的证据，不计算百分比。</span>
          </caption>
          <thead><tr><th scope="col">子系统</th>${headerCells}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="career-evidence-note" id="career-evidence-note">空心焊盘表示尚未登记证据，不等于不会。当前路径只标出这项工作作用于哪里，不会提前填入任何深度。</p>
    </article>
  `;
}

function renderCareerInsightAndReference(module, runtime) {
  const sectionId = getSectionId(module, "核心知识");
  const unit = runtime.activeUnit ?? runtime.units.at(-1);
  const insight = unit?.insight || "本单元尚未留下朱批；完成产物与结算问答后，再提炼真正改变判断的那一点。";
  return `
    <article class="career-annotation" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="核心知识">
      <h2 class="career-section-label">朱批 · 当前单元要带走的判断</h2>
      <div class="career-annotation-layout">
        <div class="career-annotation-body">
          <strong>${escapeHtml(unit?.id ?? "")} ${escapeHtml(unit?.title ?? "阶段结算")}</strong>
          ${unit?.bodyHtml ?? ""}
        </div>
        <aside class="career-annotation-aside">
          <span class="career-annotation-label">朱批</span>
          <p>${escapeHtml(insight)}</p>
        </aside>
      </div>
      <details class="career-reference">
        <summary>展开完整路线依据与运行规则</summary>
        <div class="career-reference-body">
          <section><h3>长期目标</h3>${getSection(module, "目标")}</section>
          <section><h3>结算、深度与校准</h3>${getSection(module, "核心知识")}</section>
        </div>
      </details>
    </article>
  `;
}

function renderCareerStages(module) {
  const sectionId = getSectionId(module, "时间线");
  const items = module.outcomeGates?.length
    ? module.outcomeGates
    : (module.timeline ?? []).map((item, index) => ({
        id: item.id,
        label: item.label,
        order: index + 1,
        status: item.status === "current" ? "current" : "planned",
        window: { label: "待校准", commitment: "flexible" },
        context: "长期阶段",
        outcome: item.text,
      }));
  const gates = items.map((item, index) => {
    const current = item.status === "current" || (index === 0 && !items.some((entry) => entry.status === "current"));
    return `
      <li class="career-gate${current ? " is-current" : " is-planned"}"${current ? ' aria-current="step"' : ""}>
        <span class="career-gate-marker" aria-hidden="true">${escapeHtml(String(item.order ?? index + 1))}</span>
        <div class="career-gate-window">
          <span>柔性时间窗</span>
          <strong>${escapeHtml(item.window?.label ?? "待校准")}</strong>
        </div>
        <div class="career-gate-copy">
          <p class="career-gate-title"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.context || "长期阶段")}</strong></p>
          <p class="career-gate-outcome"><span>结果闸门</span>${escapeHtml(item.outcome)}</p>
        </div>
      </li>
    `;
  }).join("");
  return `
    <article class="career-stage-track" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="时间线">
      <h2 class="career-section-label">四阶段 · 结果闸门</h2>
      <ol class="career-gate-list">${gates}</ol>
      <p class="career-gate-note">阶段由结果解锁，时间窗只提供远景坐标；日期不会自动制造进度或欠债。</p>
    </article>
  `;
}

function renderCareerRoadmap(module) {
  const runtime = getCareerUnitRuntime(module);
  return `
    <div class="career-dashboard">
      ${renderCareerWorkbench(module, runtime)}
      ${renderCareerLedger(module, runtime)}
      ${renderCareerBoard(module, runtime)}
      ${renderCareerEvidenceMatrix(module, runtime)}
      ${renderCareerInsightAndReference(module, runtime)}
      ${renderCareerStages(module)}
    </div>
  `;
}

function settleCareerUnit(module, unitId) {
  const runtime = getCareerUnitRuntime(module);
  if (!runtime.activeUnit || runtime.activeUnit.id !== unitId) return;
  taskState[runtime.activeUnit.taskId] = true;
  saveTaskState(taskState);
  state.careerLastSettledUnitId = unitId;
  state.moduleRenderVersion += 1;
  renderCurrentModule();
  renderSectionRail(module);
  observeSections();
  announce(`${unitId} ${runtime.activeUnit.title}已结算并落印，下一单元已解冻`);
  window.setTimeout(() => {
    els.sectionList.querySelector(`[data-career-unit-seal="${CSS.escape(unitId)}"]`)?.classList.remove("is-just-settled");
    if (state.careerLastSettledUnitId === unitId) state.careerLastSettledUnitId = "";
  }, 760);
}

function setCareerBoardView(view) {
  if (!["focus", "overview"].includes(view)) return;
  state.careerBoardView = view;
  els.sectionList.querySelectorAll("[data-career-board-view]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.careerBoardView === view));
  });
  els.sectionList.querySelectorAll("[data-career-board-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.careerBoardPanel !== view;
  });
  announce(view === "focus" ? "已显示当前单元路径" : "已显示六子系统总览");
}

function bindCareerRoadmap(module) {
  els.sectionList.querySelector("[data-career-settle-unit]")?.addEventListener("click", (event) => {
    settleCareerUnit(module, event.currentTarget.dataset.careerSettleUnit);
  });
  els.sectionList.querySelectorAll("[data-career-board-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setCareerBoardView(button.dataset.careerBoardView);
    });
  });
  els.sectionList.querySelectorAll("[data-career-log-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const logsModule = getModuleById("logs");
      openModule("logs", {
        targetSectionId: logsModule ? getSectionId(logsModule, "任务") : "",
      });
    });
  });
  els.sectionList.querySelectorAll("[data-career-module-id]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      openModule(link.dataset.careerModuleId);
    });
  });
}

function renderFinanceOverviewDashboard(module) {
  const dashboardModuleId = state.data.project.dashboardModuleId;
  const learningModules = state.data.modules.filter((item) => item.id !== dashboardModuleId);
  const financeReentry = getFinanceReentryState(learningModules);
  const { nextModule } = financeReentry;
  const graph = state.data.project.knowledgeGraph ?? { nodes: [], edges: [], topologicalOrder: [] };
  const graphNodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const moduleById = new Map(learningModules.map((item) => [item.id, item]));
  const conceptNodes = graph.nodes.filter((node) => node.graphRole !== "support");
  const supportNodes = graph.nodes.filter((node) => node.graphRole === "support");
  const layerById = new Map();
  for (const nodeId of graph.topologicalOrder) {
    const node = graphNodeById.get(nodeId);
    if (!node || node.graphRole === "support") continue;
    const layer = node.relations.length === 0
      ? 0
      : Math.max(...node.relations.map((relation) => (layerById.get(relation.prerequisiteId) ?? -1) + 1));
    layerById.set(nodeId, layer);
  }
  const layerCount = Math.max(1, ...layerById.values()) + 1;
  const layers = Array.from({ length: layerCount }, (_, layer) => (
    conceptNodes.filter((node) => layerById.get(node.id) === layer)
  ));
  const preferredFocusId = state.financeGraphFocusId
    && graphNodeById.has(state.financeGraphFocusId)
    ? state.financeGraphFocusId
    : nextModule?.id ?? conceptNodes[0]?.id ?? supportNodes[0]?.id ?? "";
  state.financeGraphFocusId = preferredFocusId;

  const renderGraphNode = (node) => {
    const learningModule = moduleById.get(node.id);
    const progress = getLearningProgress(learningModule);
    const current = node.id === preferredFocusId;
    return `
      <button
        class="finance-map-node${current ? " is-focused" : ""}"
        type="button"
        data-graph-module-id="${escapeHtml(node.id)}"
        data-graph-role="${escapeHtml(node.graphRole ?? "concept")}"
        data-module-status="${escapeHtml(learningModule?.status ?? "not-started")}"
        aria-current="${current ? "true" : "false"}"
        aria-describedby="finance-map-instructions"
        tabindex="${current ? "0" : "-1"}"
      >
        <span class="finance-map-node-label">${escapeHtml(node.title)}</span>
        <span class="finance-map-node-meta"><span>${escapeHtml(getStatusLabel(learningModule?.status))}</span><span>${escapeHtml(String(progress))}%</span></span>
      </button>
    `;
  };

  const relationItems = graph.edges.map((edge) => {
    const source = graphNodeById.get(edge.sourceId);
    const target = graphNodeById.get(edge.targetId);
    return `<li><strong>${escapeHtml(source?.title)}</strong><span aria-hidden="true"> → </span><strong>${escapeHtml(target?.title)}</strong>：${escapeHtml(edge.rationale)}</li>`;
  }).join("");
  const supportRelationItems = supportNodes.map((node) => (
    `<li><strong>${escapeHtml(node.title)}</strong>（学习支持）：${escapeHtml(node.decisionRole)}</li>`
  )).join("");

  const ledgerRows = graph.topologicalOrder.map((nodeId) => {
    const node = graphNodeById.get(nodeId);
    const learningModule = moduleById.get(nodeId);
    if (!node || !learningModule) return "";
    const prerequisites = node.relations.map((relation) => moduleById.get(relation.prerequisiteId)).filter(Boolean);
    const completedPrerequisites = prerequisites.filter((item) => item.status === "done").length;
    const prerequisiteLabel = node.graphRole === "support"
      ? "学习支持"
      : prerequisites.length === 0
        ? "无前置"
        : `${completedPrerequisites}/${prerequisites.length} 已完成`;
    const actionLabel = learningModule.status === "done"
      ? "复习"
      : learningModule.status === "not-started"
        ? "开始学习"
        : "继续学习";
    return `
      <tr data-status="${escapeHtml(learningModule.status)}">
        <th scope="row"><button class="finance-table-link" type="button" data-dashboard-module-id="${escapeHtml(node.id)}">${escapeHtml(node.title)}</button></th>
        <td><span class="finance-ledger-status">${escapeHtml(getStatusLabel(learningModule.status))}</span></td>
        <td>${escapeHtml(prerequisiteLabel)}</td>
        <td class="is-numeric">${escapeHtml(String(getLearningProgress(learningModule)))}%</td>
        <td>${escapeHtml(actionLabel)}</td>
      </tr>
    `;
  }).join("");

  const decisionSteps = ["认识资产", "控制风险", "分析企业", "估算价值", "执行交易", "复盘纪律"];

  return `
    <div class="finance-overview" data-annotation-exclude>
      <section class="finance-next-step" aria-label="下一步学习行动">
        <div>
          <span class="finance-next-step-label">下一步</span>
          <span class="finance-next-step-status">${escapeHtml(getStatusLabel(financeReentry.status))}</span>
          <strong>${escapeHtml(financeReentry.nextStepLabel)}</strong>
          <p>${escapeHtml(state.data.project.dashboardFocus ?? "从第一模块开始建立学习边界。")}</p>
        </div>
        ${nextModule ? `<button type="button" data-dashboard-module-id="${escapeHtml(nextModule.id)}">进入模块 <span aria-hidden="true">→</span></button>` : ""}
      </section>

      <section
        class="finance-knowledge-map"
        id="overview-学习导航"
        data-section-id="overview-学习导航"
        data-section-title="学习导航"
        aria-labelledby="finance-map-title"
      >
        <header class="finance-map-header">
          <div>
            <h2 id="finance-map-title">概念依赖图</h2>
            <p id="finance-map-instructions">方向键浏览节点，Enter 或空格进入模块。聚焦节点会显示前置、下游及其投资决策作用。</p>
          </div>
          <div class="finance-map-legend" aria-label="图例">
            <span><i data-legend="current"></i>当前</span>
            <span><i data-legend="dependency"></i>依赖</span>
            <span><i data-legend="support"></i>学习支持</span>
          </div>
        </header>
        <div class="finance-map-layout">
          <div class="finance-map-stage">
            <svg class="finance-map-edge-layer" aria-hidden="true" focusable="false"></svg>
            <div class="finance-map-node-layer" style="--finance-map-columns: ${layerCount}">
              ${layers.map((nodes, layerIndex) => `
                <div class="finance-map-layer" data-graph-layer="${layerIndex}">
                  <span class="finance-map-layer-label">L${layerIndex + 1}</span>
                  ${nodes.map(renderGraphNode).join("")}
                </div>
              `).join("")}
            </div>
            <div class="finance-map-support-rail" aria-label="学习支持模块">
              <span>学习支持</span>
              ${supportNodes.map(renderGraphNode).join("")}
            </div>
          </div>
          <aside class="finance-map-inspector" aria-live="polite"></aside>
        </div>
        <details class="finance-map-text-alternative">
          <summary>查看文字版依赖关系</summary>
          <ol>${relationItems}${supportRelationItems}</ol>
        </details>
      </section>

      <section
        class="finance-decision-sequence"
        id="overview-使用方式"
        data-section-id="overview-使用方式"
        data-section-title="使用方式"
        aria-labelledby="finance-decision-title"
      >
        <h2 id="finance-decision-title">一次投资决策如何调用这些知识</h2>
        <ol>${decisionSteps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
      </section>

      <section class="finance-ledger-section" aria-labelledby="finance-ledger-title">
        <div class="finance-ledger-heading">
          <div>
            <h2 id="finance-ledger-title">学习账表</h2>
            <p>用于精确查值；知识结构仍以上方依赖图为主。</p>
          </div>
          <span>${learningModules.length} 个模块 · 终端式密度</span>
        </div>
        <div class="finance-table-scroll">
          <table class="finance-data-table finance-module-ledger" data-density="terminal">
            <caption class="visually-hidden">投资学习模块状态</caption>
            <thead><tr><th scope="col">模块</th><th scope="col">状态</th><th scope="col">前置状态</th><th scope="col">进度</th><th scope="col">当前动作</th></tr></thead>
            <tbody>${ledgerRows}</tbody>
          </table>
        </div>
      </section>

      <section
        class="finance-overview-boundary"
        id="overview-学习边界"
        data-section-id="overview-学习边界"
        data-section-title="学习边界"
        aria-labelledby="finance-boundary-title"
      >
        <h2 id="finance-boundary-title">学习边界</h2>
        <div>${getSection(module, "学习边界")}</div>
      </section>
    </div>
  `;
}

function getFinanceGraphContext(moduleId) {
  const graph = state.data?.project?.knowledgeGraph;
  const node = graph?.nodes.find((item) => item.id === moduleId);
  if (!graph || !node) return null;
  const prerequisiteIds = graph.edges
    .filter((edge) => edge.targetId === moduleId)
    .map((edge) => edge.sourceId);
  const dependentIds = graph.edges
    .filter((edge) => edge.sourceId === moduleId)
    .map((edge) => edge.targetId);
  return { graph, node, prerequisiteIds, dependentIds };
}

function renderFinanceMapInspector(context) {
  const inspector = els.sectionList.querySelector(".finance-map-inspector");
  if (!inspector || !context) return;
  const moduleTitle = (moduleId) => context.graph.nodes.find((node) => node.id === moduleId)?.title ?? moduleId;
  const learningModule = getModuleById(context.node.id);
  const relationList = (ids, emptyLabel) => ids.length > 0
    ? `<ul>${ids.map((id) => `<li>${escapeHtml(moduleTitle(id))}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(emptyLabel)}</p>`;
  inspector.innerHTML = `
    <p class="finance-map-inspector-label">决策作用</p>
    <h3>${escapeHtml(context.node.title)}</h3>
    <p class="finance-map-inspector-role">${escapeHtml(context.node.decisionRole)}</p>
    <dl>
      <div><dt>学习状态</dt><dd>${escapeHtml(getStatusLabel(learningModule?.status))} · ${escapeHtml(String(getLearningProgress(learningModule)))}%</dd></div>
      <div><dt>直接前置</dt><dd>${relationList(context.prerequisiteIds, context.node.graphRole === "support" ? "学习支持节点，无强制前置" : "起点模块，无前置概念")}</dd></div>
      <div><dt>直接下游</dt><dd>${relationList(context.dependentIds, context.node.graphRole === "support" ? "跨模块提供查阅与练习支持" : "最终用于整合判断与复盘")}</dd></div>
    </dl>
    <button type="button" data-dashboard-module-id="${escapeHtml(context.node.id)}">进入「${escapeHtml(context.node.title)}」 <span aria-hidden="true">→</span></button>
  `;
  inspector.querySelector("[data-dashboard-module-id]")?.addEventListener("click", () => openModule(context.node.id));
}

function updateFinanceKnowledgeMapFocus(moduleId, { moveFocus = false } = {}) {
  const context = getFinanceGraphContext(moduleId);
  if (!context) return;
  state.financeGraphFocusId = moduleId;
  const relatedIds = new Set([moduleId, ...context.prerequisiteIds, ...context.dependentIds]);
  const nodes = [...els.sectionList.querySelectorAll(".finance-map-node")];
  for (const node of nodes) {
    const nodeId = node.dataset.graphModuleId;
    const focused = nodeId === moduleId;
    node.classList.toggle("is-focused", focused);
    node.classList.toggle("is-prerequisite", context.prerequisiteIds.includes(nodeId));
    node.classList.toggle("is-dependent", context.dependentIds.includes(nodeId));
    node.classList.toggle("is-dimmed", !relatedIds.has(nodeId));
    node.setAttribute("aria-current", focused ? "true" : "false");
    node.tabIndex = focused ? 0 : -1;
  }
  els.sectionList.querySelectorAll(".finance-map-edge").forEach((edge) => {
    const sourceId = edge.dataset.sourceId;
    const targetId = edge.dataset.targetId;
    edge.classList.toggle("is-related", sourceId === moduleId || targetId === moduleId);
    edge.classList.toggle("is-prerequisite-edge", targetId === moduleId);
    edge.classList.toggle("is-dependent-edge", sourceId === moduleId);
  });
  renderFinanceMapInspector(context);
  if (moveFocus) {
    els.sectionList.querySelector(`.finance-map-node[data-graph-module-id="${CSS.escape(moduleId)}"]`)?.focus();
  }
}

function drawFinanceKnowledgeMapEdges() {
  const stage = els.sectionList.querySelector(".finance-map-stage");
  const svg = stage?.querySelector(".finance-map-edge-layer");
  const graph = state.data?.project?.knowledgeGraph;
  if (!stage || !svg || !graph) return;
  const stageRect = stage.getBoundingClientRect();
  if (stageRect.width === 0 || stageRect.height === 0) return;
  svg.setAttribute("viewBox", `0 0 ${stageRect.width} ${stageRect.height}`);
  svg.setAttribute("width", String(stageRect.width));
  svg.setAttribute("height", String(stageRect.height));
  const paths = graph.edges.map((edge) => {
    const source = stage.querySelector(`.finance-map-node[data-graph-module-id="${CSS.escape(edge.sourceId)}"]`);
    const target = stage.querySelector(`.finance-map-node[data-graph-module-id="${CSS.escape(edge.targetId)}"]`);
    if (!source || !target) return "";
    const sourceRect = source.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const x1 = sourceRect.right - stageRect.left;
    const y1 = sourceRect.top + sourceRect.height / 2 - stageRect.top;
    const x2 = targetRect.left - stageRect.left;
    const y2 = targetRect.top + targetRect.height / 2 - stageRect.top;
    const bend = Math.max(28, Math.abs(x2 - x1) * 0.46);
    const path = `M ${x1.toFixed(1)} ${y1.toFixed(1)} C ${(x1 + bend).toFixed(1)} ${y1.toFixed(1)}, ${(x2 - bend).toFixed(1)} ${y2.toFixed(1)}, ${x2.toFixed(1)} ${y2.toFixed(1)}`;
    return `<path class="finance-map-edge" data-source-id="${escapeHtml(edge.sourceId)}" data-target-id="${escapeHtml(edge.targetId)}" d="${path}" marker-end="url(#finance-map-arrow)" />`;
  }).join("");
  svg.innerHTML = `
    <defs>
      <marker id="finance-map-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0 0 8 4 0 8Z" class="finance-map-arrow" />
      </marker>
    </defs>
    ${paths}
  `;
  updateFinanceKnowledgeMapFocus(state.financeGraphFocusId);
}

function scheduleFinanceKnowledgeMapEdges() {
  if (state.financeGraphResizeFrame) cancelAnimationFrame(state.financeGraphResizeFrame);
  state.financeGraphResizeFrame = requestAnimationFrame(() => {
    state.financeGraphResizeFrame = 0;
    drawFinanceKnowledgeMapEdges();
  });
}

function bindFinanceKnowledgeMap() {
  const nodes = [...els.sectionList.querySelectorAll(".finance-map-node")];
  if (nodes.length === 0) return;
  const getDirectionalNode = (currentNode, key) => {
    const currentRect = currentNode.getBoundingClientRect();
    const currentCenter = {
      x: currentRect.left + currentRect.width / 2,
      y: currentRect.top + currentRect.height / 2,
    };
    const horizontal = key === "ArrowLeft" || key === "ArrowRight";
    const direction = key === "ArrowLeft" || key === "ArrowUp" ? -1 : 1;
    return nodes
      .filter((candidate) => candidate !== currentNode)
      .map((candidate) => {
        const rect = candidate.getBoundingClientRect();
        const dx = rect.left + rect.width / 2 - currentCenter.x;
        const dy = rect.top + rect.height / 2 - currentCenter.y;
        const primary = horizontal ? dx : dy;
        const secondary = horizontal ? dy : dx;
        return { candidate, primary, score: Math.abs(primary) + Math.abs(secondary) * 0.42 };
      })
      .filter(({ primary }) => Math.sign(primary) === direction && Math.abs(primary) > 1)
      .sort((left, right) => left.score - right.score)[0]?.candidate ?? currentNode;
  };
  for (const node of nodes) {
    node.addEventListener("pointerenter", () => {
      if (document.activeElement?.closest?.(".finance-map-inspector")) return;
      updateFinanceKnowledgeMapFocus(node.dataset.graphModuleId);
    });
    node.addEventListener("focus", () => updateFinanceKnowledgeMapFocus(node.dataset.graphModuleId));
    node.addEventListener("click", () => openModule(node.dataset.graphModuleId));
    node.addEventListener("keydown", (event) => {
      if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        const target = getDirectionalNode(node, event.key);
        updateFinanceKnowledgeMapFocus(target.dataset.graphModuleId, { moveFocus: true });
      } else if (event.key === "Home") {
        event.preventDefault();
        updateFinanceKnowledgeMapFocus(nodes[0].dataset.graphModuleId, { moveFocus: true });
      } else if (event.key === "End") {
        event.preventDefault();
        updateFinanceKnowledgeMapFocus(nodes.at(-1).dataset.graphModuleId, { moveFocus: true });
      }
    });
  }
  updateFinanceKnowledgeMapFocus(state.financeGraphFocusId);
  state.financeGraphResizeObserver?.disconnect();
  if (typeof ResizeObserver === "function") {
    const stage = els.sectionList.querySelector(".finance-map-stage");
    state.financeGraphResizeObserver = new ResizeObserver(scheduleFinanceKnowledgeMapEdges);
    if (stage) state.financeGraphResizeObserver.observe(stage);
  }
  scheduleFinanceKnowledgeMapEdges();
}

function renderKnowledgeArticleSection(section) {
  return `
    <section class="knowledge-article-section is-${escapeHtml(section.kind)}" id="${escapeHtml(section.id)}" data-section-id="${escapeHtml(section.id)}" data-section-title="${escapeHtml(section.title)}">
      <h4>${escapeHtml(section.title)}</h4>
      <div class="knowledge-article-section-body">${section.body}</div>
    </section>
  `;
}

function renderKnowledgeNotesSection(module) {
  const notes = module.knowledgeNotes ?? [];
  if (notes.length === 0) return "";
  return `<div class="knowledge-articles">${notes.map((note) => `
    <article class="knowledge-article" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}" data-note-id="${escapeHtml(note.id)}" data-annotation-context="${escapeHtml(note.id)}" data-annotation-title="${escapeHtml(note.title)}">
      <header class="knowledge-article-header">
        <h3 class="knowledge-article-title">${escapeHtml(note.title)}</h3>
        <div class="knowledge-article-intro">${note.intro}</div>
      </header>
      ${note.sections.map(renderKnowledgeArticleSection).join("")}
    </article>
  `).join("")}</div>`;
}

function renderLegacyAnnotationArchive(module) {
  if (getArchivedAnnotations(module.id).length === 0) return "";
  const archiveId = getAnnotationArchiveNoteId(module.id);
  return `
    <article class="module-section legacy-annotation-archive" id="${escapeHtml(archiveId)}" data-section-id="${escapeHtml(archiveId)}" data-section-title="历史笔记" data-legacy-annotation-archive>
      <h2>历史笔记</h2>
      <p>旧版来源已变更，原文高亮无法恢复；选中文本与笔记已完整保留在右侧。</p>
    </article>
  `;
}

function renderCurrentModule() {
  const module = state.currentModule;
  state.financeGraphResizeObserver?.disconnect();
  state.financeGraphResizeObserver = null;
  const isFinanceOverview = PROJECT_ID === "finance" && module.id === state.data.project.dashboardModuleId;
  const isCareerRoadmap = PROJECT_ID === "foundations" && module.id === "career-roadmap";
  const isLongTermModule = PROJECT_ID === "foundations" && module.planScope === "long-term";
  const projectGoal = state.data.project.targetGoal ?? state.data.project.targetRole;
  els.main.classList.toggle("is-finance-overview", isFinanceOverview);
  els.main.classList.toggle("is-career-roadmap", isCareerRoadmap);
  els.moduleHeader.classList.toggle("is-compact", isFinanceOverview);
  els.moduleHeader.classList.toggle("is-career", isCareerRoadmap);
  els.moduleHeader.innerHTML = isFinanceOverview ? `
    <div class="finance-overview-header">
      <div>
        <p class="module-kicker">投资学习工作台 · 概念依赖与决策链</p>
        <h1 class="module-title" tabindex="-1">投资知识全景</h1>
        <p class="module-meta">先理解知识如何共同支持一次投资决策，再进入具体模块学习。</p>
      </div>
      <div class="finance-overall-progress" aria-label="整体学习进度 ${escapeHtml(String(getOverallLearningProgress()))}%">
        <span>整体进度</span>
        <strong>${escapeHtml(String(getOverallLearningProgress()))}%</strong>
      </div>
    </div>
  ` : isCareerRoadmap ? `
    <div class="career-header">
      <p class="career-header-kicker">${escapeHtml(state.data.project.title)} · CAREER ROADMAP · 结算制</p>
      <h1 class="career-header-title module-title" tabindex="-1">贾维斯 0.x 装配台</h1>
      <p class="career-header-meta">单线程 · 台账只涨不跌 · 空窗不记债</p>
      <p class="career-header-goal">长期目标：${escapeHtml(projectGoal)}</p>
    </div>
  ` : `
    <p class="module-kicker">${escapeHtml(state.data.project.title)} · ${escapeHtml(module.planScope === "interview" ? "临时面试突击 · 不改写长期路线" : projectGoal)}</p>
    <h1 class="module-title" tabindex="-1">${escapeHtml(module.title)}</h1>
    <p class="module-meta">${escapeHtml(getModuleMeta(module, { includeDate: true }))}</p>
    ${isLongTermModule ? `
      <div class="long-term-module-context">
        <span>在总路线中的职责</span>
        <strong>${escapeHtml(module.goalRole)}</strong>
        <p>长期模块不使用百分比；是否进入主线由 Career Roadmap 的活动单元决定。</p>
      </div>
    ` : renderProgressSummary(module)}
  `;

  if (isCareerRoadmap) {
    els.sectionList.innerHTML = renderCareerRoadmap(module);
    bindCareerRoadmap(module);
    return;
  }

  if (module.id === state.data.project.dashboardModuleId) {
    els.sectionList.innerHTML = renderOverviewDashboard(module);
    els.sectionList.querySelectorAll("[data-dashboard-module-id]").forEach((button) => {
      button.addEventListener("click", () => openModule(button.dataset.dashboardModuleId));
    });
    if (isFinanceOverview) bindFinanceKnowledgeMap();
    enhanceFinanceTables(els.sectionList);
    return;
  }

  const mainSections = getRenderableSectionTitles(module, PROJECT_ID);
  const blocks = mainSections
    .map((title) => {
      const body = title === "时间线"
        ? renderTimelineSection(module, title)
        : title === "知识笔记"
          ? renderKnowledgeNotesSection(module)
          : title === "任务"
            ? renderTaskSection(module, title)
            : getSection(module, title);
      if (!body) return "";
      const sectionId = getSectionId(module, title);
      return `
        <article class="module-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="${escapeHtml(title)}"${PROJECT_ID === "finance" ? ` data-annotation-context="${escapeHtml(sectionId)}" data-annotation-title="${escapeHtml(title)}"` : ""}>
          <h2>${escapeHtml(title)}</h2>
          <div class="section-body">${body}</div>
        </article>
      `;
    })
    .filter(Boolean)
    .join("");

  const archiveBlock = renderLegacyAnnotationArchive(module);
  const content = `${blocks}${archiveBlock}`;
  els.sectionList.innerHTML = content || `
    <article class="status-panel">
      <h2>${escapeHtml(module.title)}</h2>
      <p>这个模块还没有可展示内容。</p>
    </article>
  `;

  const annotationContextSelector = isAllContentAnnotationScope()
    ? "[data-annotation-context]"
    : ".knowledge-article";
  els.sectionList.querySelectorAll(annotationContextSelector).forEach((context) => {
    context.addEventListener("click", (event) => {
      if (event.target.closest(annotationContextSelector) !== context) return;
      setActiveKnowledgeContext(context.dataset.annotationContext || context.dataset.noteId);
    });
  });
  els.sectionList.querySelector("[data-legacy-annotation-archive]")?.addEventListener("click", (event) => {
    setActiveSection(event.currentTarget.dataset.sectionId);
  });

  els.sectionList.querySelectorAll("[data-task-id]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const taskId = checkbox.dataset.taskId;
      taskState[taskId] = checkbox.checked;
      saveTaskState(taskState);
      checkbox.closest(".task-item")?.classList.toggle("is-done", checkbox.checked);
    });
  });
  enhanceFinanceTables(els.sectionList);
}

function getFinanceTableLabel(table, fallback) {
  const section = table.closest("[data-section-title]");
  if (!section) return fallback;
  const walker = document.createTreeWalker(section, NodeFilter.SHOW_ELEMENT);
  let nearestHeading = "";
  while (walker.nextNode()) {
    const element = walker.currentNode;
    if (element === table) break;
    if (element.matches?.("h3, h4")) nearestHeading = element.textContent.trim();
  }
  return nearestHeading || section.dataset.sectionTitle || fallback;
}

function enhanceFinanceTables(root) {
  if (PROJECT_ID !== "finance") return;
  root.querySelectorAll("table").forEach((table) => {
    table.classList.add("finance-data-table");
    table.dataset.density ||= "terminal";
    const sectionTitle = getFinanceTableLabel(table, state.currentModule?.title ?? "数据表");
    if (!table.querySelector("caption")) {
      const caption = document.createElement("caption");
      caption.className = "visually-hidden";
      caption.textContent = sectionTitle;
      table.prepend(caption);
    }
    table.querySelectorAll("thead th").forEach((columnHeader) => {
      if (!columnHeader.hasAttribute("scope")) columnHeader.scope = "col";
    });
    table.querySelectorAll("tbody tr").forEach((row) => {
      const firstCell = row.firstElementChild;
      if (!firstCell?.matches("td")) return;
      const rowHeader = document.createElement("th");
      for (const attribute of firstCell.attributes) {
        rowHeader.setAttribute(attribute.name, attribute.value);
      }
      rowHeader.scope = "row";
      rowHeader.append(...firstCell.childNodes);
      firstCell.replaceWith(rowHeader);
    });
    table.querySelectorAll("tr").forEach((row) => {
      [...row.children].forEach((cell, index) => {
        if (index === 0) cell.classList.add("is-sticky-column");
        const text = cell.textContent.trim();
        if (/^[+−-]?[¥$€£]?\s*[\d,.]+(?:\.\d+)?%?$/.test(text)) cell.classList.add("is-numeric");
        if (/^\+/.test(text)) cell.dataset.polarity = "positive";
        if (/^[−-]/.test(text) && /\d/.test(text)) cell.dataset.polarity = "negative";
      });
    });
    let wrapper = table.closest(".finance-table-scroll");
    if (!wrapper) {
      wrapper = document.createElement("div");
      wrapper.className = "finance-table-scroll";
      table.before(wrapper);
      wrapper.append(table);
    }
    requestAnimationFrame(() => {
      const horizontalOverflow = wrapper.scrollWidth > wrapper.clientWidth + 1;
      const verticalOverflow = wrapper.scrollHeight > wrapper.clientHeight + 1;
      const overflows = horizontalOverflow || verticalOverflow;
      if (overflows) {
        const direction = horizontalOverflow && verticalOverflow
          ? "横向和纵向"
          : horizontalOverflow ? "横向" : "纵向";
        wrapper.tabIndex = 0;
        wrapper.setAttribute("role", "region");
        wrapper.setAttribute("aria-label", `${sectionTitle}，可${direction}滚动`);
      } else {
        wrapper.removeAttribute("tabindex");
        wrapper.removeAttribute("role");
        wrapper.removeAttribute("aria-label");
      }
    });
  });
}

function renderMathExpressions(root = els.sectionList) {
  const renderToString = window.katex?.renderToString;
  if (typeof renderToString !== "function") return;

  root.querySelectorAll(".math-display[data-latex], .math-inline[data-latex]").forEach((element) => {
    if (element.dataset.mathRendered === "true") return;
    try {
      const rendered = renderToString(element.dataset.latex ?? "", {
        displayMode: element.classList.contains("math-display"),
        throwOnError: false,
        strict: "ignore",
        trust: false,
      });
      element.innerHTML = rendered;
      element.dataset.mathRendered = "true";
    } catch (error) {
      console.warn(`Unable to render ${PROJECT_ID} formula`, error);
    }
  });
}

async function renderMermaidDiagrams(root = els.sectionList) {
  const blocks = [...root.querySelectorAll("pre code.language-mermaid")];
  if (blocks.length === 0) return;
  try {
    const { default: mermaid } = await import(MERMAID_MODULE_URL);
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
    for (const [index, code] of blocks.entries()) {
      try {
        const { svg } = await mermaid.render(`${PROJECT_ID}-mermaid-${Date.now()}-${index}`, code.textContent);
        const figure = document.createElement("figure");
        figure.className = "knowledge-diagram";
        figure.innerHTML = svg;
        code.closest("pre")?.replaceWith(figure);
      } catch (error) {
        console.warn(`Unable to render ${PROJECT_ID} Mermaid diagram`, error);
      }
    }
  } catch (error) {
    console.warn(`Unable to load ${PROJECT_ID} Mermaid renderer`, error);
  }
}

function getKnowledgeNoteById(module, noteId) {
  return (module.knowledgeNotes ?? []).find((note) => note.id === noteId);
}

function getKnowledgeArticleForTarget(module, targetId) {
  return (module.knowledgeNotes ?? []).find((note) => (
    note.id === targetId || note.sections?.some((section) => section.id === targetId)
  )) ?? null;
}

function renderLocalAnnotations(note, contextId = note?.id) {
  if (!state.currentModule || !contextId) return "";
  const annotations = getAnnotationsForNote(state.currentModule.id, contextId)
    .filter((annotation) => annotation.mode === "note" || annotation.note || annotation.highlightActive);
  return renderAnnotationList(annotations, "本地学习笔记");
}

function renderArchivedAnnotations(module) {
  return renderAnnotationList(getArchivedAnnotations(module.id), "历史笔记");
}

function isAnnotationAnchorResolved(annotation) {
  if (!annotation.highlightActive) return false;
  const context = getAnnotationContextElement(getAnnotationContextId(annotation));
  const range = context ? findTextRange(context, annotation) : null;
  return Boolean(range && !rangeContainsExcludedContent(range));
}

function renderAnnotationList(annotations, title) {
  if (annotations.length === 0) return "";
  const groups = groupAnnotations(annotations);

  return `
    <section class="note-block local-annotation-list">
      <h3 class="note-group-title">${escapeHtml(title)}</h3>
      ${groups.map((group) => `
        <section class="local-annotation-group" data-annotation-group="${escapeHtml(group.key)}">
          <h4 class="note-group-title">${escapeHtml(group.label)}</h4>
          ${group.items.map((annotation) => {
            const quote = annotation.anchor?.selectedText ?? annotation.selectedText ?? "";
            const conciseQuote = quote.length > 32 ? `${quote.slice(0, 32)}…` : quote;
            const resolved = isAnnotationAnchorResolved(annotation);
            const detached = !annotation.highlightActive;
            const anchorStatus = detached ? "detached" : resolved ? "resolved" : "unresolved";
            const status = !annotation.highlightActive
              ? "原文高亮已删除，批注仍保留。"
              : !resolved
                ? "原文位置已失效，批注仍保留。"
                : "";
            const annotationHead = `
              <div class="local-annotation-head">
                <p class="local-annotation-quote">${escapeHtml(quote)}</p>
                <button class="local-annotation-manage" type="button" data-annotation-manage="${escapeHtml(annotation.id)}" aria-label="管理批注：${escapeHtml(conciseQuote)}">管理</button>
              </div>
            `;
            if (group.key === "highlight") {
              return `
                <article class="local-annotation${detached ? " is-detached" : ""}" data-annotation-id="${escapeHtml(annotation.id)}" data-anchor-status="${anchorStatus}">
                  ${annotationHead}
                  ${status ? `<p class="local-annotation-status">${escapeHtml(status)}</p>` : ""}
                </article>
              `;
            }
            return `
              <article class="local-annotation${detached ? " is-detached" : ""}" data-annotation-id="${escapeHtml(annotation.id)}" data-anchor-status="${anchorStatus}">
                ${annotationHead}
                <select class="local-annotation-category" data-annotation-category="${escapeHtml(annotation.id)}" aria-label="笔记分类">
                  ${ANNOTATION_CATEGORIES.map((category) => `<option value="${escapeHtml(category.id)}"${annotation.category === category.id ? " selected" : ""}>${escapeHtml(category.label)}</option>`).join("")}
                </select>
                <textarea class="local-annotation-editor" rows="4" data-annotation-editor="${escapeHtml(annotation.id)}" placeholder="写下自己的理解、问题、反思或补充资料">${escapeHtml(annotation.note)}</textarea>
                ${status ? `<p class="local-annotation-status">${escapeHtml(status)}</p>` : ""}
              </article>
            `;
          }).join("")}
        </section>
      `).join("")}
    </section>
  `;
}

function renderContextualNotePanel(note, {
  archived = false,
  contextId = note?.id ?? "",
  contextTitle = note?.title ?? "",
} = {}) {
  const module = state.currentModule;
  const renderedNotes = archived ? renderArchivedAnnotations(module) : renderLocalAnnotations(note);
  const contextualNotes = renderedNotes || (!archived && !note
    ? renderLocalAnnotations(null, contextId)
    : "");
  const noteContent = contextualNotes || (PROJECT_ID === "finance"
    ? '<p class="note-empty-state">模块正文均可批注。选中文字即可添加本地高亮或笔记；批注只保存在当前浏览器。</p>'
    : "");

  const contextLabel = archived ? "" : contextTitle;
  const label = `${archived ? "历史笔记" : "学习过程记录"} · ${module.title}${contextLabel ? ` / ${contextLabel}` : ""}`;
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  els.noteSurface.innerHTML = noteContent;
  els.mobileNoteSurface.innerHTML = noteContent;
  updateAnnotationCount();
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.querySelectorAll("[data-annotation-category]").forEach((select) => {
      select.addEventListener("change", () => {
        updateAnnotationCategory(select.dataset.annotationCategory, select.value, surface);
      });
    });
    surface.querySelectorAll("[data-annotation-manage]").forEach((button) => {
      button.addEventListener("click", () => {
        const annotationId = button.dataset.annotationManage;
        showAnnotationDeletePopover(annotationId, button.getBoundingClientRect(), button);
      });
    });
    surface.querySelectorAll("[data-annotation-editor]").forEach((editor) => {
      editor.addEventListener("input", () => {
        const annotationId = editor.dataset.annotationEditor;
        const value = editor.value;
        for (const surfaceToSync of [els.noteSurface, els.mobileNoteSurface]) {
          surfaceToSync.querySelectorAll(`[data-annotation-editor="${CSS.escape(annotationId)}"]`).forEach((matchingEditor) => {
            if (matchingEditor !== editor) matchingEditor.value = value;
          });
        }
        updateAnnotationNote(annotationId, value);
      });
    });
  }
}

function renderActiveContextualNotePanel() {
  const module = state.currentModule;
  const archiveId = getAnnotationArchiveNoteId(module.id);
  const archived = state.activeKnowledgeNoteId === archiveId && getArchivedAnnotations(module.id).length > 0;
  const note = getKnowledgeNoteById(module, state.activeKnowledgeNoteId);
  const context = archived ? null : getAnnotationContextElement(state.activeKnowledgeNoteId);
  renderContextualNotePanel(note, {
    archived,
    contextId: archived ? archiveId : state.activeKnowledgeNoteId,
    contextTitle: getAnnotationContextTitle(context, note?.title),
  });
}

function setActiveKnowledgeContext(sectionId) {
  const module = state.currentModule;
  const note = getKnowledgeArticleForTarget(module, sectionId);
  const archiveId = getAnnotationArchiveNoteId(module.id);
  const archived = sectionId === archiveId && getArchivedAnnotations(module.id).length > 0;
  const directContext = isAllContentAnnotationScope() ? getAnnotationContextElement(sectionId) : null;
  const contextId = archived ? archiveId : note?.id ?? directContext?.dataset.annotationContext ?? "";
  state.activeKnowledgeNoteId = contextId;
  renderContextualNotePanel(note, {
    archived,
    contextId,
    contextTitle: getAnnotationContextTitle(directContext, note?.title),
  });
}

function updateUrl(moduleId) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", moduleId);
  url.hash = "";
  window.history.replaceState({}, "", url);
}

function setActiveSection(sectionId) {
  state.activeSectionId = sectionId;
  const article = getKnowledgeArticleForTarget(state.currentModule, sectionId);
  const railSectionId = article?.id ?? sectionId;
  els.sectionLines.querySelectorAll(".section-line").forEach((button) => {
    const isActive = button.dataset.sectionId === railSectionId;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-current", isActive ? "true" : "false");
  });
  setActiveKnowledgeContext(sectionId);
}

function getActiveSectionFromScroll(sections) {
  const owner = getReaderScrollOwner();
  const isDocumentOwner = owner === document.scrollingElement || owner === document.documentElement || owner === document.body;
  const clientHeight = isDocumentOwner ? window.innerHeight : owner.clientHeight;
  const remainingScroll = owner.scrollHeight - clientHeight - owner.scrollTop;
  if (remainingScroll <= 64) {
    return sections.at(-1);
  }
  const anchorTop = isDocumentOwner
    ? window.innerHeight * 0.24
    : owner.getBoundingClientRect().top + owner.clientHeight * 0.24;
  let activeSection = sections[0];
  for (const section of sections) {
    if (section.getBoundingClientRect().top <= anchorTop) {
      activeSection = section;
    } else {
      break;
    }
  }
  return activeSection;
}

function syncActiveSectionFromScroll(sections = [...els.sectionList.querySelectorAll("[data-section-id]")]) {
  const activeSection = getActiveSectionFromScroll(sections);
  const sectionId = activeSection?.dataset.sectionId;
  if (sectionId && sectionId !== state.activeSectionId) setActiveSection(sectionId);
}

function observeSections() {
  if (state.sectionScrollHandler) {
    state.sectionScrollOwner?.removeEventListener("scroll", state.sectionScrollHandler);
    state.sectionScrollHandler = null;
    state.sectionScrollOwner = null;
  }
  if (state.sectionScrollFrame) {
    cancelAnimationFrame(state.sectionScrollFrame);
    state.sectionScrollFrame = 0;
  }

  const sections = [...els.sectionList.querySelectorAll("[data-section-id]")];
  if (sections.length === 0) return;

  const scrollEventTarget = getReaderScrollEventTarget();
  state.sectionScrollOwner = scrollEventTarget;
  state.sectionScrollHandler = () => {
    if (state.sectionScrollFrame) return;
    state.sectionScrollFrame = requestAnimationFrame(() => {
      state.sectionScrollFrame = 0;
      syncActiveSectionFromScroll(sections);
    });
  };
  scrollEventTarget.addEventListener("scroll", state.sectionScrollHandler, { passive: true });
  syncActiveSectionFromScroll(sections);
}

function clearSearch() {
  state.searchQuery = "";
  els.searchInput.value = "";
  els.searchResults.hidden = true;
  els.searchResults.innerHTML = "";
}

function invalidateDeferredNavigation() {
  state.navigationVersion += 1;
}

function isTextEntryTarget(target) {
  return target instanceof Element
    && (target.matches("input, textarea, select") || target.isContentEditable);
}

function openModule(moduleId, { syncUrl = true, targetSectionId = "" } = {}) {
  const nextModule = getModuleById(moduleId) ?? state.data.modules[0];
  const moduleRenderVersion = ++state.moduleRenderVersion;
  const navigationVersion = ++state.navigationVersion;
  state.currentModule = nextModule;
  state.activeKnowledgeNoteId = "";
  hideAnnotationDeletePopover();
  hideAnnotationToolbar();
  if (syncUrl) updateUrl(nextModule.id);
  renderModuleNav();
  els.nav.querySelector(`.module-nav-item[data-module-id="${CSS.escape(nextModule.id)}"]`)?.scrollIntoView({ block: "nearest" });
  renderCurrentModule();
  if (!targetSectionId) resetReaderScroll();
  renderMathExpressions(els.sectionList);
  enhanceCodeListings(els.sectionList);
  void renderMermaidDiagrams().then(() => {
    if (state.moduleRenderVersion !== moduleRenderVersion) return;
    applyHighlights();
    observeSections();
    if (targetSectionId && state.navigationVersion === navigationVersion && state.activeSectionId === targetSectionId) {
      requestAnimationFrame(() => {
        if (
          state.moduleRenderVersion !== moduleRenderVersion
          || state.navigationVersion !== navigationVersion
          || state.activeSectionId !== targetSectionId
        ) return;
        document.querySelector(`#${CSS.escape(targetSectionId)}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
        setActiveSection(targetSectionId);
      });
    }
  });
  renderContextualNotePanel(null);
  renderSectionRail(nextModule);
  applyHighlights();
  observeSections();
  if (targetSectionId) {
    requestAnimationFrame(() => {
      if (state.moduleRenderVersion !== moduleRenderVersion) return;
      document.querySelector(`#${CSS.escape(targetSectionId)}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(targetSectionId);
    });
  }
  if (els.shell.classList.contains("is-mobile-left-open")) {
    closeMobileDrawers({ restoreFocus: false });
  } else {
    updateDirectoryControls();
  }
  announce(`已打开${nextModule.title}`);
  if (syncUrl && !targetSectionId) {
    requestAnimationFrame(() => els.moduleHeader.querySelector(".module-title")?.focus({ preventScroll: true }));
  }
}

function openSearchModal() {
  hideAnnotationDeletePopover();
  hideAnnotationToolbar();
  els.shell.classList.add("is-searching");
  els.searchResults.hidden = false;
}

function closeSearchModal() {
  els.shell.classList.remove("is-searching");
  els.searchResults.hidden = true;
}

function getSearchTerms(query) {
  return query.trim().split(/\s+/).filter(Boolean);
}

function isAsciiSearchTerm(term) {
  return /^[a-z0-9]+$/i.test(term);
}

function escapeSearchPattern(value) {
  return String(value ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getSearchMatchLevel(text, term) {
  const normalizedText = String(text ?? "").toLowerCase();
  const normalizedTerm = String(term ?? "").toLowerCase();
  if (!normalizedTerm) return 0;
  if (!normalizedText.includes(normalizedTerm)) return 0;
  if (!isAsciiSearchTerm(normalizedTerm)) return 2;
  const pattern = new RegExp(`(^|[^a-z0-9])${escapeSearchPattern(normalizedTerm)}([^a-z0-9]|$)`, "i");
  return pattern.test(normalizedText) ? 2 : 1;
}

function hasSearchTerm(text, term) {
  return getSearchMatchLevel(text, term) > 0;
}

function getSearchScore(entry, terms) {
  return terms.reduce((score, term) => {
    const moduleLevel = getSearchMatchLevel(entry.moduleTitle, term);
    const sectionLevel = getSearchMatchLevel(entry.sectionTitle, term);
    const bodyLevel = getSearchMatchLevel(entry.text, term);
    const moduleScore = moduleLevel === 2 ? 16 : moduleLevel === 1 ? 6 : 0;
    const sectionScore = sectionLevel === 2 ? 10 : sectionLevel === 1 ? 4 : 0;
    const bodyScore = bodyLevel === 2 ? 4 : bodyLevel === 1 ? 1 : 0;
    return score + moduleScore + sectionScore + bodyScore;
  }, 0);
}

function highlightTerms(text, query) {
  const terms = getSearchTerms(query).map(escapeSearchPattern);
  if (terms.length === 0) return escapeHtml(text);
  const pattern = new RegExp(`(${terms.join("|")})`, "gi");
  const exactPattern = new RegExp(`^(${terms.join("|")})$`, "i");
  return String(text ?? "")
    .split(pattern)
    .map((part) => exactPattern.test(part) ? `<mark class="result-highlight">${escapeHtml(part)}</mark>` : escapeHtml(part))
    .join("");
}

function getSnippet(module, query) {
  const searchText = module.searchText ?? "";
  const lower = searchText.toLowerCase();
  const term = getSearchTerms(query).find((item) => lower.includes(item.toLowerCase()));
  if (!term) return searchText.slice(0, 160);
  const index = lower.indexOf(term.toLowerCase());
  const start = Math.max(0, index - 56);
  const end = Math.min(searchText.length, index + term.length + 128);
  return `${start > 0 ? "..." : ""}${searchText.slice(start, end)}${end < searchText.length ? "..." : ""}`;
}

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

function getMatchedSection(module, query) {
  const terms = getSearchTerms(query).map((term) => term.toLowerCase());
  for (const [title, html] of Object.entries(module.sections ?? {})) {
    const haystack = `${title} ${html}`.toLowerCase();
    if (terms.some((term) => haystack.includes(term))) return title;
  }
  return "Module";
}

function renderSearchResults(results) {
  els.searchResults.hidden = false;
  if (results.length === 0) {
    const emptyMessage = PROJECT_ID === "finance" ? "未找到结果" : "No results found";
    els.searchResults.innerHTML = `<p class="result-empty">${emptyMessage}</p>`;
    return;
  }

  els.searchResults.innerHTML = results
    .map(({ module, entry }) => {
      const resultTitle = entry.articleTitle && entry.articleTitle !== entry.sectionTitle
        ? `${entry.articleTitle} / ${entry.sectionTitle}`
        : entry.sectionTitle;
      return `
      <button class="result-item" type="button" data-module-id="${escapeHtml(module.id)}" data-section-id="${escapeHtml(entry.id)}">
        <span>
          <span class="result-title">${highlightTerms(resultTitle, state.searchQuery)}</span>
          <span class="result-snippet">${highlightTerms(getEntrySnippet(entry, state.searchQuery), state.searchQuery)}</span>
        </span>
        <span class="result-meta">${escapeHtml(module.title)}</span>
      </button>
    `;
    })
    .join("");

  els.searchResults.querySelectorAll("[data-module-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const moduleId = button.dataset.moduleId;
      const sectionId = button.dataset.sectionId;
      clearSearch();
      closeSearchModal();
      openModule(moduleId, { targetSectionId: sectionId });
    });
  });
}

function runSearch(query) {
  state.searchQuery = query.trim();
  if (!state.searchQuery) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
    return;
  }

  const terms = getSearchTerms(state.searchQuery).map((term) => term.toLowerCase());
  const results = state.data.modules
    .flatMap((module) => module.searchEntries.map((entry) => ({ module, entry })))
    .map(({ module, entry }) => {
      const score = getSearchScore(entry, terms);
      return { module, entry, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.module.title.localeCompare(right.module.title))
    .slice(0, 8);

  renderSearchResults(results);
}

function toggleNotePanel(control) {
  if (window.matchMedia("(max-width: 1100px)").matches) {
    setMobileNoteOpen(!els.shell.classList.contains("is-mobile-note-open"), control);
    return;
  }
  setDesktopNotePanelCollapsed(!els.shell.classList.contains("is-note-collapsed"), { persist: true });
}

function getFocusableElements(root) {
  if (!root) return [];
  return [...root.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )].filter((element) => !element.hidden && element.getClientRects().length > 0);
}

function trapMobileDrawerFocus(event) {
  if (event.key !== "Tab") return;
  const noteOpen = Boolean(els.closeMobileNote)
    && els.shell.classList.contains("is-mobile-note-open");
  const directoryOpen = els.shell.classList.contains("is-mobile-left-open")
    && window.matchMedia("(max-width: 860px)").matches;
  const drawer = state.annotationDeletePopover
    ?? (noteOpen ? els.mobileNoteDrawer : directoryOpen ? els.sidebar : null);
  if (!drawer) return;
  const focusable = getFocusableElements(drawer);
  if (focusable.length === 0) {
    event.preventDefault();
    drawer.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  } else if (!drawer.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
  }
}

function bindEvents() {
  els.toggleTheme?.addEventListener("click", () => {
    setTheme(document.body.dataset.theme === "dark" ? "light" : "dark", { persist: true });
  });

  els.toggleNote?.addEventListener("click", () => toggleNotePanel(els.toggleNote));
  els.noteRailToggle?.addEventListener("click", () => toggleNotePanel(els.noteRailToggle));
  els.closeMobileNote?.addEventListener("click", () => setMobileNoteOpen(false));
  els.drawerBackdrop?.addEventListener("click", () => closeMobileDrawers());

  els.toggleLeftControls.forEach((button) => {
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 860px)").matches) {
        const shouldOpen = !els.shell.classList.contains("is-mobile-left-open");
        if (shouldOpen && els.shell.classList.contains("is-mobile-note-open")) {
          setMobileNoteOpen(false);
        }
        setMobileDirectoryOpen(shouldOpen, button);
        return;
      }
      els.shell.classList.toggle("is-left-collapsed");
      updateDirectoryControls();
      scheduleReaderLayoutRefresh();
    });
  });

  els.searchInput.addEventListener("focus", openSearchModal);
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchOverlay.addEventListener("click", closeSearchModal);

  els.main.addEventListener("pointerdown", invalidateDeferredNavigation);
  els.main.addEventListener("wheel", invalidateDeferredNavigation, { passive: true });
  els.main.addEventListener("touchstart", invalidateDeferredNavigation, { passive: true });

  els.main.addEventListener("pointerup", () => {
    requestAnimationFrame(handleAnnotationSelection);
  });

  els.main.addEventListener("keyup", handleAnnotationSelection);

  let annotationSelectionTimer = 0;
  document.addEventListener("selectionchange", () => {
    window.clearTimeout(annotationSelectionTimer);
    const selection = window.getSelection();
    const anchor = getElementFromNode(selection?.anchorNode);
    if (!selection || selection.isCollapsed || !anchor || !els.main.contains(anchor)) return;
    annotationSelectionTimer = window.setTimeout(handleAnnotationSelection, 180);
  });

  document.addEventListener("pointerdown", (event) => {
    const isDeletePopoverClick = state.annotationDeletePopover?.contains(event.target);
    if (state.annotationDeletePopover && !isDeletePopoverClick) {
      hideAnnotationDeletePopover({ restoreFocus: false });
    }
    if (isDeletePopoverClick) return;
    if (state.annotationToolbar?.contains(event.target)) return;
    if (!getAnnotationContextFromNode(event.target)) hideAnnotationToolbar();
  });

  window.addEventListener("keydown", (event) => {
    trapMobileDrawerFocus(event);
    if (KEYBOARD_NAVIGATION_KEYS.has(event.key) && !isTextEntryTarget(event.target)) {
      invalidateDeferredNavigation();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchModal();
      els.searchInput.focus();
    }
    if (event.key === "Escape") {
      const searching = els.shell.classList.contains("is-searching");
      const drawerOpen = els.shell.classList.contains("is-mobile-left-open")
        || els.shell.classList.contains("is-mobile-note-open");
      if (state.annotationDeletePopover) {
        event.preventDefault();
        hideAnnotationDeletePopover();
        return;
      }
      if (state.annotationToolbar || state.annotationSelectionWarning) {
        event.preventDefault();
        hideAnnotationToolbar();
        hideAnnotationSelectionWarning();
        return;
      }
      if (searching) {
        event.preventDefault();
        els.searchInput.blur();
        closeSearchModal();
        return;
      }
      if (drawerOpen) {
        event.preventDefault();
        closeMobileDrawers();
      }
    }
  });

  let resizeFrame = 0;
  window.addEventListener("resize", () => {
    if (resizeFrame) cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0;
      if (state.sectionScrollOwner && state.sectionScrollOwner !== getReaderScrollEventTarget()) {
        observeSections();
      }
      if (
        (!window.matchMedia("(max-width: 1100px)").matches && els.shell.classList.contains("is-mobile-note-open"))
        || (!window.matchMedia("(max-width: 860px)").matches && els.shell.classList.contains("is-mobile-left-open"))
      ) {
        closeMobileDrawers({ restoreFocus: false });
      }
      updateNotePanelControls();
      updateDirectoryControls();
      refreshSizeDependentUi();
    });
  });
}

async function init() {
  try {
    setTheme(resolveInitialTheme({
      projectId: PROJECT_ID,
      storedTheme: readStorageValue(THEME_STORAGE_KEY),
      htmlTheme: document.body.dataset.theme,
    }));
    restoreNotePanelPreference();
    updateNotePanelControls();
    updateDirectoryControls();
    state.data = await fetchJson(ROADMAP_DATA_SOURCE);
    const annotationLoad = loadAnnotations();
    const migratedAnnotations = migrateLegacyAnnotations(annotationLoad.store, state.data.modules);
    state.annotations = migratedAnnotations;
    state.annotationPersistenceAllowed = annotationLoad.canPersist;
    if (annotationLoad.canPersist) saveAnnotations(migratedAnnotations);
    updateAnnotationCount();
    bindEvents();
    openModule(getInitialModuleId(), { syncUrl: false });
  } catch (error) {
    els.sectionList.innerHTML = `
      <article class="status-panel">
        <h2>路线图加载失败</h2>
        <p>${escapeHtml(error.message)}</p>
      </article>
    `;
  }
}

init();
