import { createReaderModule, makeKnowledgeNote, renderModuleSafely } from "./reader-modules.js";
import {
  applyHighlights as applyAnnotationHighlights,
  createJournalDraftMarkdown,
  getAnnotationContext as getAnnotationDraftContext,
  getReadableCardFromNode,
  getSelectionAnnotationContext as getSelectionAnnotationContextFromRuntime,
  hideAnnotationDeletePopover as hideAnnotationDeletePopoverFromRuntime,
  hideAnnotationToolbar as hideAnnotationToolbarFromRuntime,
  renderAnnotationToolbar as renderAnnotationToolbarFromRuntime,
  renderLocalAnnotations as renderLocalAnnotationsFromRuntime,
  updateAnnotationNote as updateAnnotationNoteFromRuntime,
} from "./reader-annotations.js";
import {
  buildDocumentNotes,
  buildErrorNotes,
  buildUnitNotes,
  formatTarget,
  renderErrors,
  renderEvidence,
  renderJournal,
  renderNotes,
  renderNow,
  renderPromptLibrary,
  renderSettlements,
  renderUnits,
  renderValidation,
} from "./reader-renderers.js";
import { getReferencePanelPayload, openReferenceTarget, renderReferencePanel } from "./reader-references.js";
import { loadAnnotations, loadUiState, saveAnnotations, saveUiState } from "./reader-state.js";
import { escapeHtml, getShortcutLabel, slugify, titleCase, toList } from "./reader-utils.js";

const readerScript = document.querySelector('script[src$="ielts-reader.js"]');

const state = {
  rawData: null,
  data: null,
  currentModule: null,
  searchQuery: "",
  activeSectionId: "",
  activeKnowledgeNoteId: "",
  sectionScrollHandler: null,
  sectionScrollFrame: 0,
  annotations: { version: 1, items: [] },
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null,
  ui: loadUiState(),
};

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

function getDataSource() {
  return readerScript?.dataset.source ?? "site/ielts-data.json";
}

function resolveUrl(path) {
  return new URL(path, window.location.href);
}

async function fetchJson(path) {
  const response = await fetch(resolveUrl(path));
  if (!response.ok) throw new Error(`无法加载 ${path}`);
  return response.json();
}

function getStatusLabel(status) {
  const labels = {
    active: "进行中",
    improving: "改善中",
    fixed: "已修复",
    regressed: "复发",
    "not-yet-run": "未运行",
    "not-started": "未开始",
    ready: "可执行",
    suggested: "建议",
    settled: "已结算",
  };
  return labels[status] ?? titleCase(status);
}

function getPriorityLabel(priority) {
  const labels = {
    "current action": "当前动作",
    "unit ledger": "单元账本",
    "high-impact repair": "高影响修复",
    "evidence profile": "证据档案",
    "settlement record": "结算记录",
    "learning archive": "学习档案",
    "system quality": "系统与质量",
  };
  return labels[priority] ?? titleCase(priority);
}

function buildReaderModules(data) {
  const target = data.project?.target ?? data.scoreProfile?.target ?? {};
  const lastUpdated = data.scoreProfile?.lastUpdated ?? data.build?.generatedAt ?? "";
  const hasErrors = toList(data.errorLog?.errors).length > 0;
  const hasEvidence = toList(data.scoreHistory?.entries).length > 0;
  const hasSettlements = toList(data.unitLedger?.settled).length > 0;

  const modules = [
    createReaderModule({
      id: "now",
      title: "现在",
      status: data.unitLedger?.activeUnit ? "active" : "not-started",
      priority: "current action",
      lastUpdated,
      sections: { 当前动作: renderModuleSafely("now", "当前动作", () => renderNow(data)) },
      knowledgeNotes: [makeKnowledgeNote("now-target", "目标与诊断边界", `<p>${escapeHtml(formatTarget(target))}</p>`)],
    }),
    createReaderModule({
      id: "units",
      title: "单元",
      status: data.unitLedger?.activeUnit ? "active" : data.unitLedger?.suggestedUnit ? "suggested" : "not-started",
      priority: "unit ledger",
      lastUpdated,
      sections: { 单元账本: renderModuleSafely("units", "单元账本", () => renderUnits(data)) },
      knowledgeNotes: buildUnitNotes(data),
    }),
    createReaderModule({
      id: "errors",
      title: "错误",
      status: hasErrors ? "active" : "not-started",
      priority: "high-impact repair",
      lastUpdated,
      sections: { 错误状态: renderModuleSafely("errors", "错误状态", () => renderErrors(data)) },
      knowledgeNotes: buildErrorNotes(data),
    }),
    createReaderModule({
      id: "evidence",
      title: "证据",
      status: hasEvidence ? "ready" : "not-started",
      priority: "evidence profile",
      lastUpdated,
      sections: { 成绩与证据: renderModuleSafely("evidence", "成绩与证据", () => renderEvidence(data)) },
    }),
    createReaderModule({
      id: "settlements",
      title: "结算",
      status: hasSettlements ? "settled" : "not-started",
      priority: "settlement record",
      lastUpdated,
      sections: { 结算与校准: renderModuleSafely("settlements", "结算与校准", () => renderSettlements(data)) },
    }),
    createReaderModule({
      id: "archive",
      title: "档案",
      status: toList(data.notes).length || toList(data.journal).length ? "ready" : "not-started",
      priority: "learning archive",
      lastUpdated,
      sections: {
        学习笔记: renderModuleSafely("archive", "学习笔记", () => renderNotes(data)),
        复盘记录: renderModuleSafely("archive", "复盘记录", () => renderJournal(data)),
      },
      knowledgeNotes: [...buildDocumentNotes(data.notes, "note"), ...buildDocumentNotes(data.journal, "journal")],
    }),
    createReaderModule({
      id: "system",
      title: "系统",
      status: "ready",
      priority: "system quality",
      lastUpdated,
      sections: {
        智能体提示词: renderModuleSafely("system", "智能体提示词", () => renderPromptLibrary(data)),
        质量校验: renderModuleSafely("system", "质量校验", () => renderValidation(data)),
      },
      knowledgeNotes: [...buildDocumentNotes(data.promptLibrary, "prompt"), ...buildDocumentNotes(data.validation, "validation")],
    }),
  ];

  return {
    project: {
      id: "ielts-academic",
      title: "语言",
      targetRole: `IELTS Academic · ${formatTarget(target)}`,
      dashboardModuleId: "now",
    },
    raw: data,
    modules,
  };
}

function setTheme(theme, options = {}) {
  const normalized = theme === "dark" ? "dark" : "light";
  state.ui.theme = normalized;
  document.body.dataset.theme = normalized;
  els.toggleTheme?.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
  if (options.persist !== false) saveUiState(state.ui);
}

function applyStoredShellState() {
  els.shell?.classList.toggle("is-left-collapsed", state.ui.leftCollapsed);
  els.shell?.classList.toggle("is-note-collapsed", state.ui.noteCollapsed);
  document.querySelectorAll("[data-shortcut-label]").forEach((shortcut) => {
    shortcut.textContent = getShortcutLabel();
  });
  setTheme(state.ui.theme, { persist: false });
}

function getAnnotationRuntime() {
  return {
    state,
    els,
    saveAnnotations,
    getKnowledgeNoteById,
    renderContextualNotePanel,
  };
}

function getSelectionAnnotationContext() {
  return getSelectionAnnotationContextFromRuntime(getAnnotationRuntime());
}

function hideAnnotationToolbar() {
  hideAnnotationToolbarFromRuntime(getAnnotationRuntime());
}

function hideAnnotationDeletePopover() {
  hideAnnotationDeletePopoverFromRuntime(getAnnotationRuntime());
}

function renderAnnotationToolbar(context) {
  renderAnnotationToolbarFromRuntime(getAnnotationRuntime(), context);
}

function applyHighlights() {
  applyAnnotationHighlights(getAnnotationRuntime());
}

function updateAnnotationNote(annotationId, value) {
  updateAnnotationNoteFromRuntime(getAnnotationRuntime(), annotationId, value);
}

function renderLocalAnnotations(note) {
  return renderLocalAnnotationsFromRuntime(getAnnotationRuntime(), note);
}

function refreshJournalDraftTextareas(annotationId) {
  if (!annotationId) return;
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const note = getKnowledgeNoteById(state.currentModule, annotation.noteId);
  const draft = createJournalDraftMarkdown(annotation, getAnnotationDraftContext(note));
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.querySelectorAll(`[data-journal-draft="${CSS.escape(annotationId)}"]`).forEach((textarea) => {
      textarea.value = draft;
    });
  }
}

async function copyJournalDraft(button, textarea) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(textarea.value);
      button.textContent = "已复制";
      return;
    }
    textarea.focus();
    textarea.select();
    button.textContent = "请手动复制";
  } catch {
    textarea.focus();
    textarea.select();
    button.textContent = "复制失败，请手动复制";
  }
}

function getInitialModuleId() {
  const url = new URL(window.location.href);
  const fromQuery = url.searchParams.get("module");
  const fromHash = url.hash.replace(/^#/, "");
  return fromQuery || fromHash || "now";
}

function getModuleById(moduleId) {
  return state.data?.modules.find((module) => module.id === moduleId);
}

function getSectionId(module, title) {
  return module.sectionIds?.[title] ?? `${module.id}-${slugify(title)}`;
}

function renderModuleNav() {
  els.nav.innerHTML = "";
  for (const module of state.data.modules) {
    const button = document.createElement("button");
    button.className = "module-nav-item";
    button.type = "button";
    button.dataset.moduleId = module.id;
    button.setAttribute("aria-current", module.id === state.currentModule?.id ? "true" : "false");
    button.innerHTML = `
      <span class="module-nav-title">${escapeHtml(module.title)}</span>
      <span class="module-nav-meta">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(getPriorityLabel(module.priority))}</span>
    `;
    button.addEventListener("click", () => openModule(module.id));
    els.nav.append(button);
  }
}

function getRailTargets(module) {
  return Object.keys(module.sections ?? {}).map((sectionTitle) => ({
    id: getSectionId(module, sectionTitle),
    title: sectionTitle,
  }));
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
      document.querySelector(`#${CSS.escape(target.id)}`)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      setActiveSection(target.id);
    });
    els.sectionLines.append(button);
  });
}

function renderCurrentModule() {
  const module = state.currentModule;
  els.moduleHeader.innerHTML = `
    <p class="module-kicker">${escapeHtml(state.data.project.title)} · ${escapeHtml(state.data.project.targetRole)}</p>
    <h1 class="module-title">${escapeHtml(module.title)}</h1>
    <p class="module-meta">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(getPriorityLabel(module.priority))} · 更新 ${escapeHtml(module.lastUpdated)}</p>
  `;

  const sectionBlocks = Object.entries(module.sections ?? {})
    .map(([title, body]) => {
      const sectionId = getSectionId(module, title);
      return `
        <article class="module-section" id="${escapeHtml(sectionId)}" data-section-id="${escapeHtml(sectionId)}" data-note-id="${escapeHtml(sectionId)}" data-section-title="${escapeHtml(title)}">
          <h2>${escapeHtml(title)}</h2>
          <div class="section-body">${body}</div>
        </article>
      `;
    })
    .join("");

  els.sectionList.innerHTML = sectionBlocks
    ? sectionBlocks
    : `
      <article class="status-panel">
        <h2>${escapeHtml(module.title)}</h2>
        <p>这个模块还没有可展示内容。</p>
      </article>
    `;

  bindSectionReferenceChips();
}

function getKnowledgeNoteById(module, noteId) {
  if (!module || !noteId) return null;
  return toList(module.knowledgeNotes).find((note) => note.id === noteId)
    ?? module.sectionNotes?.[noteId]
    ?? null;
}

function renderEmptyDetailPanel() {
  return `
    <article class="note-context detail-empty">
      <h3>上下文详情</h3>
      <p class="note-empty">点击引用，或选中正文后创建高亮/笔记，在这里查看具体对象。</p>
    </article>
  `;
}

function renderContextualNotePanel(note) {
  const noteGroups = note?.groups?.length
    ? note.groups.map((group) => `
      <section class="note-block" data-note-group="${escapeHtml(group.label)}">
        <h3 class="note-group-title">${escapeHtml(group.label)}</h3>
        <div class="note-group-body">${group.body}</div>
      </section>
    `).join("")
    : note?.body ? `<section class="note-block"><div class="note-group-body">${note.body}</div></section>` : "";
  const renderedNotes = note
    ? `<article class="note-context"><h3>${escapeHtml(note.title)}</h3>${noteGroups}${renderLocalAnnotations(note)}</article>`
    : renderEmptyDetailPanel();

  const label = note ? `详情 · ${note.title}` : "上下文详情";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  els.noteSurface.innerHTML = renderedNotes;
  els.mobileNoteSurface.innerHTML = renderedNotes;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
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
        refreshJournalDraftTextareas(annotationId);
      });
    });
    surface.querySelectorAll("[data-copy-journal-draft]").forEach((button) => {
      button.addEventListener("click", async () => {
        const textarea = button.closest(".annotation-draft")?.querySelector("textarea");
        if (!textarea) return;
        await copyJournalDraft(button, textarea);
      });
    });
    bindReferencePanelActions(surface);
  }
}

function bindReferencePanelActions(surface) {
  surface.querySelectorAll("[data-jump-reference]").forEach((button) => {
    button.addEventListener("click", () => {
      openReferenceTarget(state.data, button.dataset.jumpReference, openModule);
    });
  });
  surface.querySelectorAll("[data-reference-id]").forEach((button) => {
    button.addEventListener("click", () => renderReferenceContext(button.dataset.referenceId));
  });
}

function renderReferenceContext(referenceId) {
  const payload = getReferencePanelPayload(state.data, referenceId);
  const rendered = renderReferencePanel(payload);
  const label = payload ? `引用 · ${payload.title}` : "引用";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  els.noteSurface.innerHTML = rendered;
  els.mobileNoteSurface.innerHTML = rendered;
  bindReferencePanelActions(els.noteSurface);
  bindReferencePanelActions(els.mobileNoteSurface);
}

function bindSectionReferenceChips() {
  els.sectionList.querySelectorAll("[data-reference-id]").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      renderReferenceContext(chip.dataset.referenceId);
    });
  });
}

function setActiveKnowledgeContext(sectionId) {
  const note = getKnowledgeNoteById(state.currentModule, sectionId);
  state.activeKnowledgeNoteId = note?.id ?? "";
  renderContextualNotePanel(note);
}

function updateUrl(moduleId) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", moduleId);
  url.hash = "";
  window.history.replaceState({}, "", url);
}

function setActiveSection(sectionId) {
  state.activeSectionId = sectionId;
  els.sectionLines.querySelectorAll(".section-line").forEach((button) => {
    const isActive = button.dataset.sectionId === sectionId;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-current", isActive ? "true" : "false");
  });
}

function getActiveSectionFromScroll(sections) {
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

function openModule(moduleId, { syncUrl = true, targetSectionId = "" } = {}) {
  const nextModule = getModuleById(moduleId) ?? state.data.modules[0];
  state.currentModule = nextModule;
  state.activeKnowledgeNoteId = "";
  hideAnnotationDeletePopover();
  hideAnnotationToolbar();
  if (syncUrl) updateUrl(nextModule.id);
  renderModuleNav();
  renderCurrentModule();
  renderContextualNotePanel(null);
  renderSectionRail(nextModule);
  applyHighlights();
  els.main.scrollTop = 0;
  observeSections();
  if (targetSectionId) {
    requestAnimationFrame(() => {
      const target = document.querySelector(`#${CSS.escape(targetSectionId)}`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        setActiveSection(targetSectionId);
        return;
      }
      setActiveKnowledgeContext(targetSectionId);
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

function renderSearchResults(results) {
  els.searchResults.hidden = false;
  if (results.length === 0) {
    els.searchResults.innerHTML = `<p class="result-empty">没有找到结果</p>`;
    return;
  }

  els.searchResults.innerHTML = results
    .map(({ module, entry }) => `
      <button class="result-item" type="button" data-module-id="${escapeHtml(module.id)}" data-section-id="${escapeHtml(entry.id)}">
        <span>
          <span class="result-title">${highlightTerms(entry.sectionTitle, state.searchQuery)}</span>
          <span class="result-snippet">${highlightTerms(getEntrySnippet(entry, state.searchQuery), state.searchQuery)}</span>
        </span>
        <span class="result-meta">${escapeHtml(module.title)}</span>
      </button>
    `)
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
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-note-open");
      return;
    }
    state.ui.noteCollapsed = !state.ui.noteCollapsed;
    els.shell.classList.toggle("is-note-collapsed", state.ui.noteCollapsed);
    saveUiState(state.ui);
  });

  els.toggleLeftControls.forEach((button) => {
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 860px)").matches) {
        els.shell.classList.toggle("is-mobile-left-open");
        return;
      }
      state.ui.leftCollapsed = !state.ui.leftCollapsed;
      els.shell.classList.toggle("is-left-collapsed", state.ui.leftCollapsed);
      saveUiState(state.ui);
    });
  });

  els.searchInput.addEventListener("focus", openSearchModal);
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchOverlay.addEventListener("click", closeSearchModal);

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
    if (!getReadableCardFromNode(event.target)) hideAnnotationToolbar();
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
    state.rawData = await fetchJson(getDataSource());
    state.data = buildReaderModules(state.rawData);
    state.annotations = loadAnnotations();
    applyStoredShellState();
    bindEvents();
    openModule(getInitialModuleId(), { syncUrl: false });
  } catch (error) {
    els.sectionList.innerHTML = `
      <article class="status-panel">
        <h2>IELTS 阅读器加载失败</h2>
        <p>${escapeHtml(error.message)}</p>
      </article>
    `;
  }
}

init();
