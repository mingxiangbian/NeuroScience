import {
  ANNOTATION_CATEGORIES,
  getAnnotationArchiveNoteId,
  groupAnnotations,
  migrateLegacyAnnotations,
  parseStoredAnnotations,
} from "./annotation-model.js";

const ANNOTATION_STORAGE_KEY = "foundationsReader.annotations.v1";
const TASK_STORAGE_KEY = "foundationsReader.tasks.v1";
const MERMAID_MODULE_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.esm.min.mjs";

const state = {
  data: null,
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  activeKnowledgeNoteId: "",
  moduleRenderVersion: 0,
  navigationVersion: 0,
  sectionScrollHandler: null,
  sectionScrollFrame: 0,
  annotations: { version: 1, items: [] },
  annotationPersistenceAllowed: true,
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null,
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
  toggleTheme: document.querySelector("#toggle-theme"),
  toggleNote: document.querySelector("#toggle-note"),
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
    version: 1,
    items: [],
  };
}

function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(ANNOTATION_STORAGE_KEY);
    return parseStoredAnnotations(raw);
  } catch (error) {
    console.warn("Unable to load Foundations annotations", error);
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

function getAnnotationsForNote(moduleId, noteId) {
  return state.annotations.items.filter((item) => item.moduleId === moduleId && item.noteId === noteId);
}

function getArchivedAnnotations(moduleId) {
  return getAnnotationsForNote(moduleId, getAnnotationArchiveNoteId(moduleId));
}

function getKnowledgeArticleFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".knowledge-article") ?? null;
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
  if (range.startContainer !== range.endContainer) return null;

  const startArticle = getKnowledgeArticleFromNode(range.startContainer);
  const endArticle = getKnowledgeArticleFromNode(range.endContainer);
  if (!startArticle || startArticle !== endArticle) return null;

  const noteId = startArticle.dataset.noteId;
  const moduleId = state.currentModule?.id;
  if (!moduleId || !noteId) return null;

  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(startArticle);
  beforeRange.setEnd(range.startContainer, range.startOffset);

  return {
    moduleId,
    noteId,
    selectedText,
    matchIndex: countTextOccurrences(beforeRange.toString(), selectedText),
    rect: range.getBoundingClientRect(),
  };
}

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
  toolbar.style.position = "fixed";
  toolbar.style.left = `${Math.max(12, context.rect.left + context.rect.width / 2)}px`;
  toolbar.style.top = `${Math.max(12, context.rect.top - 46)}px`;
  toolbar.querySelectorAll("[data-annotation-mode]").forEach((button) => {
    button.addEventListener("click", () => createAnnotationFromSelection(button.dataset.annotationMode));
  });
  document.body.append(toolbar);
  state.annotationToolbar = toolbar;
  state.pendingAnnotation = context;
}

function createAnnotationId() {
  return `foundation-ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
  if (!context?.moduleId || !context?.noteId) return;
  const now = new Date().toISOString();
  const annotationMode = mode === "note" ? "note" : "highlight";
  const annotation = {
    id: createAnnotationId(),
    projectId: "foundations",
    moduleId: context.moduleId,
    noteId: context.noteId,
    selectedText: context.selectedText,
    matchIndex: context.matchIndex,
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
  renderContextualNotePanel(getKnowledgeNoteById(state.currentModule, context.noteId));
}

function updateAnnotationNote(annotationId, value) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.note = value;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
}

function updateAnnotationCategory(annotationId, category) {
  if (!ANNOTATION_CATEGORIES.some((item) => item.id === category)) return;
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.category = category;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
  renderActiveContextualNotePanel();
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
  renderActiveContextualNotePanel();
}

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
  popover.style.position = "fixed";
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
    const article = els.sectionList.querySelector(`.knowledge-article[data-note-id="${CSS.escape(annotation.noteId)}"]`);
    if (!article) continue;
    const range = findTextRange(article, annotation.selectedText, annotation.matchIndex);
    if (!range) continue;
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
    mark.append(range.extractContents());
    mark.addEventListener("click", (event) => {
      event.stopPropagation();
      showAnnotationDeletePopover(annotation.id, mark.getBoundingClientRect());
    });
    range.insertNode(mark);
  }
}

function getInitialModuleId() {
  const url = new URL(window.location.href);
  const fromQuery = url.searchParams.get("module");
  const fromHash = url.hash.replace(/^#/, "");
  return fromQuery || fromHash || "overview";
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

function setTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.body.dataset.theme = normalized;
  els.toggleTheme?.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
}

function renderModuleNav() {
  els.nav.innerHTML = "";
  for (const module of state.data.modules) {
    const progress = getLearningProgress(module);
    const button = document.createElement("button");
    button.className = "module-nav-item";
    button.type = "button";
    button.dataset.moduleId = module.id;
    button.setAttribute("aria-current", module.id === state.currentModule?.id ? "true" : "false");
    button.innerHTML = `
      <span class="module-nav-title">${escapeHtml(module.title)}</span>
      <span class="module-nav-progress">${escapeHtml(String(progress))}%</span>
      <span class="module-nav-meta">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(module.priority)}</span>
    `;
    button.addEventListener("click", () => openModule(module.id));
    els.nav.append(button);
  }
}

function getRailTargets(module) {
  const sectionTargets = Object.keys(module.sections ?? {}).map((sectionTitle) => ({
    id: getSectionId(module, sectionTitle),
    title: sectionTitle,
  }));
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
        <p class="progress-status">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(module.priority)}</p>
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
  const dashboardModuleId = state.data.project.dashboardModuleId;
  const learningModules = state.data.modules.filter((item) => item.id !== dashboardModuleId);
  const stableModules = learningModules.filter((item) => item.id !== "interview-sprint");
  const nextModule = learningModules.find((item) => item.status !== "complete") ?? learningModules[0];
  const moduleRows = learningModules
    .map((item) => `
      <button class="dashboard-module-row" type="button" data-dashboard-module-id="${escapeHtml(item.id)}">
        <span>
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(getStatusLabel(item.status))} · ${escapeHtml(item.priority)}</small>
        </span>
        <span class="dashboard-module-progress">${escapeHtml(String(getLearningProgress(item)))}%</span>
      </button>
    `)
    .join("");

  const blocks = [
    ["Dashboard", `
      <div class="route-ledger" aria-label="Foundations route ledger">
        <div class="route-ledger-row">
          <span class="route-ledger-label">下一次打开</span>
          ${nextModule ? `
            <button class="route-ledger-target" type="button" data-dashboard-module-id="${escapeHtml(nextModule.id)}">
              <strong>${escapeHtml(nextModule.title)}</strong>
              <span>${escapeHtml(nextModule.priority)}</span>
            </button>
          ` : "<strong>暂无下一模块</strong>"}
        </div>
        <div class="route-ledger-row">
          <span class="route-ledger-label">当前缺口</span>
          <strong>先校准 coding / system design baseline，再扩展项目。</strong>
        </div>
      </div>
      ${getSection(module, "Dashboard")}
      <div class="dashboard-grid" aria-label="Foundations dashboard">
        <section class="dashboard-card">
          <p class="dashboard-card-label">整体学习进度</p>
          <strong>${escapeHtml(String(getOverallLearningProgress()))}%</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">主线模块</p>
          <strong>${escapeHtml(String(stableModules.length))}</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">当前状态</p>
          <strong>未开始</strong>
        </section>
      </div>
    `],
    ["Interview Signal", getSection(module, "Interview Signal")],
    ["模块总览", `
      ${getSection(module, "模块总览")}
      <div class="dashboard-module-list" aria-label="模块学习状态">
        ${moduleRows}
      </div>
    `],
    ["计划节奏", getSection(module, "计划节奏")],
    ["待补知识", getSection(module, "待补知识")],
  ];

  return blocks
    .map(([title, body]) => {
      if (!body) return "";
      const sectionId = getSectionId(module, title);
      return `
        <article class="module-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="${escapeHtml(title)}">
          <h2>${escapeHtml(title)}</h2>
          <div class="section-body">${body}</div>
        </article>
      `;
    })
    .filter(Boolean)
    .join("");
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
    <article class="knowledge-article" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}" data-note-id="${escapeHtml(note.id)}">
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
  els.moduleHeader.innerHTML = `
    <p class="module-kicker">${escapeHtml(state.data.project.title)} · ${escapeHtml(state.data.project.targetRole)}</p>
    <h1 class="module-title">${escapeHtml(module.title)}</h1>
    <p class="module-meta">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(module.priority)} · Updated ${escapeHtml(module.lastUpdated)}</p>
    ${renderProgressSummary(module)}
  `;

  if (module.id === state.data.project.dashboardModuleId) {
    els.sectionList.innerHTML = renderOverviewDashboard(module);
    els.sectionList.querySelectorAll("[data-dashboard-module-id]").forEach((button) => {
      button.addEventListener("click", () => openModule(button.dataset.dashboardModuleId));
    });
    return;
  }

  const mainSections = ["目标", "当前状态", "核心知识", "任务", "时间线", "学习记录", "知识笔记"];
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
        <article class="module-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-section-title="${escapeHtml(title)}">
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

  els.sectionList.querySelectorAll(".knowledge-article").forEach((article) => {
    article.addEventListener("click", () => setActiveKnowledgeContext(article.dataset.noteId));
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
}

async function renderMermaidDiagrams(root = els.sectionList) {
  const blocks = [...root.querySelectorAll("pre code.language-mermaid")];
  if (blocks.length === 0) return;
  try {
    const { default: mermaid } = await import(MERMAID_MODULE_URL);
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
    for (const [index, code] of blocks.entries()) {
      try {
        const { svg } = await mermaid.render(`foundations-mermaid-${Date.now()}-${index}`, code.textContent);
        const figure = document.createElement("figure");
        figure.className = "knowledge-diagram";
        figure.innerHTML = svg;
        code.closest("pre")?.replaceWith(figure);
      } catch (error) {
        console.warn("Unable to render Foundations Mermaid diagram", error);
      }
    }
  } catch (error) {
    console.warn("Unable to load Foundations Mermaid renderer", error);
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

function renderLocalAnnotations(note) {
  if (!state.currentModule || !note) return "";
  const annotations = getAnnotationsForNote(state.currentModule.id, note.id)
    .filter((annotation) => annotation.mode === "note" || annotation.note || annotation.highlightActive);
  return renderAnnotationList(annotations, "本地学习笔记");
}

function renderArchivedAnnotations(module) {
  return renderAnnotationList(getArchivedAnnotations(module.id), "历史笔记");
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
            if (group.key === "highlight") {
              return `
                <article class="local-annotation" data-annotation-id="${escapeHtml(annotation.id)}">
                  <p class="local-annotation-quote">${escapeHtml(annotation.selectedText)}</p>
                </article>
              `;
            }
            return `
              <article class="local-annotation${annotation.highlightActive ? "" : " is-detached"}" data-annotation-id="${escapeHtml(annotation.id)}">
                <p class="local-annotation-quote">${escapeHtml(annotation.selectedText)}</p>
                <select class="local-annotation-category" data-annotation-category="${escapeHtml(annotation.id)}" aria-label="笔记分类">
                  ${ANNOTATION_CATEGORIES.map((category) => `<option value="${escapeHtml(category.id)}"${annotation.category === category.id ? " selected" : ""}>${escapeHtml(category.label)}</option>`).join("")}
                </select>
                <textarea class="local-annotation-editor" rows="4" data-annotation-editor="${escapeHtml(annotation.id)}" placeholder="写下自己的理解、问题、反思或补充资料">${escapeHtml(annotation.note)}</textarea>
                ${annotation.highlightActive ? "" : `<p class="local-annotation-status">原文高亮已删除，笔记仍保留。</p>`}
              </article>
            `;
          }).join("")}
        </section>
      `).join("")}
    </section>
  `;
}

function renderContextualNotePanel(note, { archived = false } = {}) {
  const module = state.currentModule;
  const renderedNotes = archived ? renderArchivedAnnotations(module) : renderLocalAnnotations(note);

  const label = `${archived ? "历史笔记" : "学习过程记录"} · ${module.title}`;
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  els.noteSurface.innerHTML = renderedNotes;
  els.mobileNoteSurface.innerHTML = renderedNotes;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.querySelectorAll("[data-annotation-category]").forEach((select) => {
      select.addEventListener("change", () => {
        updateAnnotationCategory(select.dataset.annotationCategory, select.value);
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
  renderContextualNotePanel(note, { archived });
}

function setActiveKnowledgeContext(sectionId) {
  const module = state.currentModule;
  const note = getKnowledgeArticleForTarget(module, sectionId);
  const archiveId = getAnnotationArchiveNoteId(module.id);
  const archived = sectionId === archiveId && getArchivedAnnotations(module.id).length > 0;
  state.activeKnowledgeNoteId = archived ? archiveId : note?.id ?? "";
  renderContextualNotePanel(note, { archived });
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
  const remainingScroll = els.main.scrollHeight - els.main.clientHeight - els.main.scrollTop;
  if (remainingScroll <= 64) {
    return sections.at(-1);
  }
  const anchorTop = els.main.getBoundingClientRect().top + els.main.clientHeight * 0.24;
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
    els.main.removeEventListener("scroll", state.sectionScrollHandler);
    state.sectionScrollHandler = null;
  }
  if (state.sectionScrollFrame) {
    cancelAnimationFrame(state.sectionScrollFrame);
    state.sectionScrollFrame = 0;
  }

  const sections = [...els.sectionList.querySelectorAll("[data-section-id]")];
  if (sections.length === 0) return;

  state.sectionScrollHandler = () => {
    if (state.sectionScrollFrame) return;
    state.sectionScrollFrame = requestAnimationFrame(() => {
      state.sectionScrollFrame = 0;
      syncActiveSectionFromScroll(sections);
    });
  };
  els.main.addEventListener("scroll", state.sectionScrollHandler, { passive: true });
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
  renderCurrentModule();
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
  els.main.scrollTop = 0;
  observeSections();
  if (targetSectionId) {
    requestAnimationFrame(() => {
      if (state.moduleRenderVersion !== moduleRenderVersion) return;
      document.querySelector(`#${CSS.escape(targetSectionId)}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(targetSectionId);
    });
  }
  els.shell.classList.remove("is-mobile-left-open");
}

function openSearchModal() {
  hideAnnotationDeletePopover();
  hideAnnotationToolbar();
  els.shell.classList.add("is-searching");
  els.searchResults.hidden = false;
}

function closeSearchModal() {
  els.shell.classList.remove("is-searching");
  if (!state.searchQuery) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
  }
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
    els.searchResults.innerHTML = `<p class="result-empty">No results found</p>`;
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

function bindEvents() {
  els.toggleTheme.addEventListener("click", () => {
    setTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
  });

  els.toggleNote.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 1100px)").matches) {
      els.shell.classList.toggle("is-mobile-note-open");
      return;
    }
    els.shell.classList.toggle("is-note-collapsed");
  });

  els.toggleLeftControls.forEach((button) => {
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 860px)").matches) {
        els.shell.classList.toggle("is-mobile-left-open");
        return;
      }
      els.shell.classList.toggle("is-left-collapsed");
    });
  });

  els.searchInput.addEventListener("focus", openSearchModal);
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchOverlay.addEventListener("click", closeSearchModal);

  els.main.addEventListener("pointerdown", invalidateDeferredNavigation);
  els.main.addEventListener("wheel", invalidateDeferredNavigation, { passive: true });
  els.main.addEventListener("touchstart", invalidateDeferredNavigation, { passive: true });

  els.main.addEventListener("mouseup", () => {
    requestAnimationFrame(() => {
      const context = getSelectionAnnotationContext();
      if (context) renderAnnotationToolbar(context);
      else hideAnnotationToolbar();
    });
  });

  els.main.addEventListener("keyup", () => {
    const context = getSelectionAnnotationContext();
    if (context) renderAnnotationToolbar(context);
    else hideAnnotationToolbar();
  });

  document.addEventListener("mousedown", (event) => {
    const isDeletePopoverClick = state.annotationDeletePopover?.contains(event.target);
    if (state.annotationDeletePopover && !isDeletePopoverClick) hideAnnotationDeletePopover();
    if (isDeletePopoverClick) return;
    if (state.annotationToolbar?.contains(event.target)) return;
    if (!getKnowledgeArticleFromNode(event.target)) hideAnnotationToolbar();
  });

  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchModal();
      els.searchInput.focus();
    }
    if (event.key === "Escape") {
      hideAnnotationDeletePopover();
      hideAnnotationToolbar();
      closeSearchModal();
      els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
    }
  });
}

async function init() {
  try {
    state.data = await fetchJson("roadmap/roadmap-data.json");
    const annotationLoad = loadAnnotations();
    const migratedAnnotations = migrateLegacyAnnotations(annotationLoad.store, state.data.modules);
    state.annotations = migratedAnnotations;
    state.annotationPersistenceAllowed = annotationLoad.canPersist;
    if (annotationLoad.canPersist) saveAnnotations(migratedAnnotations);
    bindEvents();
    setTheme("light");
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
