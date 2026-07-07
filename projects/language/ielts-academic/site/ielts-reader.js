import { createReaderModule, makeKnowledgeNote, renderModuleSafely } from "./reader-modules.js";
import { loadAnnotations, loadTaskState, loadUiState, saveAnnotations, saveTaskState, saveUiState } from "./reader-state.js";
import { renderTaskChecklist } from "./reader-tasks.js";
import { escapeHtml, getShortcutLabel, slugify, titleCase, toList, truncateText } from "./reader-utils.js";

const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8];
const LANES = ["Listening", "Reading", "Writing", "Speaking", "Errors"];
const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];

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

function getDataSource() {
  return readerScript?.dataset.source ?? "site/ielts-data.json";
}

function resolveUrl(path) {
  return new URL(path, window.location.href);
}

async function fetchJson(path) {
  const response = await fetch(resolveUrl(path));
  if (!response.ok) throw new Error(`Unable to load ${path}`);
  return response.json();
}

function formatBand(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "Unverified";
}

function formatTarget(target) {
  if (!target || typeof target !== "object") return "Overall 8.0 / each skill 7.5+";
  const overall = Number.isFinite(Number(target.overall)) ? Number(target.overall).toFixed(1) : "8.0";
  const floor = Number.isFinite(Number(target.perSkillFloor)) ? Number(target.perSkillFloor).toFixed(1) : "7.5";
  const weeks = Number.isFinite(Number(target.timelineWeeks)) ? `${Number(target.timelineWeeks)} weeks` : "8 weeks";
  return `Overall ${overall} / each skill ${floor}+ / ${weeks}`;
}

function getStatusLabel(status) {
  const labels = {
    active: "进行中",
    improving: "改善中",
    fixed: "已修复",
    regressed: "复发",
    template: "模板态",
    "not-yet-run": "未运行",
    "not-started": "未开始",
    ready: "可执行",
  };
  return labels[status] ?? titleCase(status);
}

function renderReferenceChips(items, kind = "reference") {
  const chips = toList(items).filter(Boolean);
  if (chips.length === 0) return "";

  return `
    <div class="reference-chip-list">
      ${chips
        .map((item) => {
          const label = typeof item === "string" ? item : item.label;
          const href = typeof item === "string" ? "" : item.href;
          const safeKind = escapeHtml(kind);
          const safeLabel = escapeHtml(label);
          if (href) {
            return `<a class="reference-chip" data-kind="${safeKind}" href="${escapeHtml(href)}">${safeLabel}</a>`;
          }
          return `<span class="reference-chip" data-kind="${safeKind}">${safeLabel}</span>`;
        })
        .join("")}
    </div>
  `;
}

function renderMarkdownPreview(markdown) {
  const lines = String(markdown ?? "").split(/\r?\n/);
  const blocks = [];
  let listItems = [];

  const flushList = () => {
    if (listItems.length === 0) return;
    blocks.push(`<ul>${listItems.map((item) => `<li>${item}</li>`).join("")}</ul>`);
    listItems = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    const listMatch = line.match(/^[-*]\s+(.+)$/);
    if (listMatch) {
      listItems.push(escapeHtml(listMatch[1]));
      continue;
    }
    flushList();
    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      blocks.push(`<h3>${escapeHtml(headingMatch[2])}</h3>`);
      continue;
    }
    blocks.push(`<p>${escapeHtml(line)}</p>`);
  }
  flushList();

  return blocks.join("") || '<p class="empty-state">No content.</p>';
}

function renderSkillGapBars(skills, target) {
  const floor = Number.isFinite(Number(target?.perSkillFloor)) ? Number(target.perSkillFloor) : 7.5;
  const safeSkills = toList(skills);

  if (safeSkills.length === 0) {
    return '<p class="empty-state">No skill profile has been generated yet.</p>';
  }

  return `
    <div class="skill-gap-stack">
      ${safeSkills
        .map((skill) => {
          const estimate = Number(skill.estimatedBand);
          const hasEstimate = Number.isFinite(estimate);
          const fill = hasEstimate ? Math.max(0, Math.min(100, (estimate / floor) * 100)) : 0;
          const gap = hasEstimate ? Math.max(0, floor - estimate).toFixed(1) : "diagnostic needed";
          return `
            <article class="skill-gap">
              <div class="skill-gap-header">
                <div>
                  <p class="skill-gap-label">${escapeHtml(skill.label ?? titleCase(skill.id))}</p>
                  <p class="skill-gap-meta">Band ${escapeHtml(formatBand(skill.estimatedBand))} | Gap: ${escapeHtml(gap)}</p>
                </div>
                <p class="skill-gap-meta">${escapeHtml(skill.confidence ?? "low")} confidence</p>
              </div>
              <div class="skill-gap-bar" aria-hidden="true">
                <div class="skill-gap-fill" style="width: ${fill.toFixed(0)}%;"></div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderMetricGrid(metrics) {
  return `
    <div class="metric-grid">
      ${metrics
        .map((metric) => `
          <article class="metric-card">
            <p class="metric-label">${escapeHtml(metric.label)}</p>
            <p class="metric-value">${escapeHtml(metric.value)}</p>
          </article>
        `)
        .join("")}
    </div>
  `;
}

function renderDashboard(data) {
  const target = data.project?.target ?? data.scoreProfile?.target ?? {};
  const profile = data.scoreProfile ?? {};
  const referenceIssueCount = toList(data.build?.referenceIssues).length;

  return `
    <div class="dashboard-stack">
      ${renderMetricGrid([
        { label: "Target", value: formatTarget(target) },
        { label: "Run mode", value: profile.runMode ?? "not-yet-run" },
        { label: "State", value: profile.state ?? "template" },
        { label: "Reference issues", value: String(referenceIssueCount) },
      ])}
      <article class="content-card">
        <h3>Skill gaps</h3>
        ${renderSkillGapBars(profile.skills, target)}
      </article>
      <div class="dashboard-grid" aria-label="IELTS dashboard">
        <section class="dashboard-card">
          <p class="dashboard-card-label">Current estimate</p>
          <strong>${escapeHtml(formatBand(profile.currentEstimate?.overall))}</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">Confidence</p>
          <strong>${escapeHtml(profile.currentEstimate?.confidence ?? "low")}</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">Open risks</p>
          <strong>${escapeHtml(String(toList(profile.risks).length))}</strong>
        </section>
      </div>
    </div>
  `;
}

function renderCheckpointMarker(checkpoint) {
  return `
    <article class="checkpoint-marker">
      <strong>${escapeHtml(checkpoint.name ?? `Week ${checkpoint.week} checkpoint`)}</strong>
      <span>${escapeHtml(checkpoint.status ?? "not-started")}</span>
      <span>${escapeHtml(checkpoint.decision ?? checkpoint.purpose ?? "")}</span>
    </article>
  `;
}

function laneText(label, week) {
  if (label === "Errors") return "Log and review";
  if (week === 1) return "Diagnostic evidence";
  if (week === 2) return "Baseline check";
  if (week <= 4) return "Focused repair";
  if (week <= 6) return "Regression control";
  return "Mock and lock-in";
}

function renderSwimlane(data) {
  const checkpointByWeek = new Map(toList(data.checkpoints?.checkpoints).map((checkpoint) => [Number(checkpoint.week), checkpoint]));
  const header = `
    <div class="swimlane-heading">Skill</div>
    ${WEEKS.map((week) => `<div class="swimlane-heading">Week ${week}</div>`).join("")}
  `;

  const rows = LANES.map((label) => {
    const cells = WEEKS.map((week) => {
      const checkpoint = label === "Errors" ? checkpointByWeek.get(week) : null;
      return `
        <div class="swimlane-cell">
          ${checkpoint ? renderCheckpointMarker(checkpoint) : `<span>${escapeHtml(laneText(label, week))}</span>`}
        </div>
      `;
    }).join("");
    return `<div class="swimlane-row-label">${escapeHtml(label)}</div>${cells}`;
  }).join("");

  return `<div class="swimlane-scroll"><div class="swimlane-grid">${header}${rows}</div></div>`;
}

function renderCheckpointList(data) {
  const checkpoints = toList(data.checkpoints?.checkpoints);
  if (checkpoints.length === 0) return '<p class="empty-state">No checkpoints found.</p>';
  return `
    <div class="stack">
      ${checkpoints
        .map((checkpoint) => `
          <article class="content-card">
            <p class="card-kicker">Week ${escapeHtml(checkpoint.week)} | ${escapeHtml(checkpoint.status ?? "not-started")}</p>
            <h3>${escapeHtml(checkpoint.name)}</h3>
            <p class="card-body">${escapeHtml(checkpoint.purpose)}</p>
            <p class="card-body">${escapeHtml(checkpoint.decision)}</p>
          </article>
        `)
        .join("")}
    </div>
  `;
}

function renderDailyTasks(data, moduleId) {
  const errors = toList(data.errorLog?.errors).map((error) => `${error.id}: ${error.reviewMethod ?? error.description}`);
  const baseTasks = [
    "Log actual focused study minutes before changing the weekly allocation.",
    "Run one diagnostic or review task before adding new theory.",
    "Update confidence and unverified dimensions only after evidence changes.",
  ];
  return renderTaskChecklist({
    sourceId: `${moduleId}:daily-training`,
    fieldName: "dailyTask",
    items: [...baseTasks, ...errors],
    taskState,
  });
}

function renderErrorCard(error) {
  return `
    <article class="error-card">
      <p class="card-kicker">${escapeHtml(error.id)} | ${escapeHtml(error.skill)} | ${escapeHtml(error.impact)}</p>
      <h3>${escapeHtml(error.description)}</h3>
      <p class="error-priority">${escapeHtml(error.nextReview ?? "Next review pending")}</p>
      <p class="card-body">${escapeHtml(error.reviewMethod ?? "")}</p>
      ${renderReferenceChips([error.id], "error")}
    </article>
  `;
}

function renderErrors(data) {
  const allErrors = toList(data.errorLog?.errors);
  const columns = ERROR_STATUSES.map((status) => {
    const statusErrors = allErrors.filter((error) => error.status === status);
    return `
      <section class="error-column" aria-label="${escapeHtml(titleCase(status))} errors">
        <h3>${escapeHtml(titleCase(status))}</h3>
        ${
          statusErrors.length > 0
            ? statusErrors.map(renderErrorCard).join("")
            : '<p class="empty-state">No matching errors.</p>'
        }
      </section>
    `;
  }).join("");

  return `<div class="error-board">${columns}</div>`;
}

function renderNotes(data) {
  const notes = toList(data.notes);
  if (notes.length === 0) return '<p class="empty-state">No notes have been indexed.</p>';

  return `
    <div class="stack">
      ${notes
        .map((note) => `
          <article class="note-card">
            <p class="card-kicker">${escapeHtml(note.skill ?? "general")} | ${escapeHtml(note.topic ?? "untagged")}</p>
            <h3>${escapeHtml(note.title)}</h3>
            <p class="card-body">${escapeHtml(truncateText(note.body))}</p>
            ${renderReferenceChips([{ label: note.path, href: note.path }], "source")}
            ${renderReferenceChips(note.relatedErrors, "error")}
          </article>
        `)
        .join("")}
    </div>
  `;
}

function renderJournal(data) {
  const entries = toList(data.journal);
  if (entries.length === 0) return '<p class="empty-state">No journal entries have been indexed.</p>';

  return `
    <div class="stack">
      ${entries
        .map((entry) => `
          <article class="journal-card">
            <p class="card-kicker">${escapeHtml(entry.date ?? "undated")}</p>
            <h3>${escapeHtml(entry.title)}</h3>
            <p class="card-body">${escapeHtml(truncateText(entry.body))}</p>
            ${renderReferenceChips([{ label: entry.path, href: entry.path }], "source")}
            ${renderReferenceChips(entry.relatedErrors, "error")}
            ${renderReferenceChips(toList(entry.relatedNotes).map((note) => `note: ${note}`), "note")}
          </article>
        `)
        .join("")}
    </div>
  `;
}

function renderPromptLibrary(data) {
  const prompts = toList(data.promptLibrary);
  if (prompts.length === 0) return '<p class="empty-state">No prompt documents found.</p>';

  return `
    <div class="stack">
      ${prompts
        .map((prompt) => `
          <article class="content-card">
            <p class="card-kicker">${escapeHtml(prompt.id ?? "prompt")}</p>
            <h3>${escapeHtml(prompt.title)}</h3>
            <p class="card-body">${escapeHtml(truncateText(prompt.body))}</p>
            ${renderReferenceChips([{ label: prompt.path, href: prompt.path }], "source")}
          </article>
        `)
        .join("")}
    </div>
  `;
}

function renderValidation(data) {
  const checks = toList(data.validation);
  if (checks.length === 0) return '<p class="empty-state">No validation documents found.</p>';

  return `
    <div class="stack">
      ${checks
        .map((check) => `
          <article class="content-card">
            <p class="card-kicker">${escapeHtml(check.id ?? "validation")}</p>
            <h3>${escapeHtml(check.title)}</h3>
            <p class="card-body">${escapeHtml(truncateText(check.body))}</p>
            ${renderReferenceChips([{ label: check.path, href: check.path }], "source")}
          </article>
        `)
        .join("")}
    </div>
  `;
}

function buildErrorNotes(data) {
  return toList(data.errorLog?.errors).map((error) => makeKnowledgeNote(
    `error-${error.id}`,
    `${error.id} · ${error.description}`,
    `
      <p>${escapeHtml(error.description)}</p>
      <p>${escapeHtml(error.reviewMethod ?? "")}</p>
      ${renderReferenceChips([error.id], "error")}
    `,
    [
      {
        label: "Evidence",
        body: `<ul>${toList(error.evidence).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`,
      },
      {
        label: "Next review",
        body: `<p>${escapeHtml(error.nextReview ?? "Pending")}</p>`,
      },
    ],
  ));
}

function buildDocumentNotes(items, prefix) {
  return toList(items).map((item) => makeKnowledgeNote(
    `${prefix}-${item.id}`,
    item.title,
    renderMarkdownPreview(item.body),
    [
      {
        label: "Source",
        body: renderReferenceChips([{ label: item.path, href: item.path }], "source"),
      },
    ],
  ));
}

function buildReaderModules(data) {
  const target = data.project?.target ?? data.scoreProfile?.target ?? {};
  const lastUpdated = data.scoreProfile?.lastUpdated ?? data.build?.generatedAt ?? "";
  const dashboardSections = {
    Dashboard: renderModuleSafely("dashboard", "Dashboard", () => renderDashboard(data)),
    "Score profile": renderModuleSafely("dashboard", "Score profile", () => `
      <p>${escapeHtml(data.scoreProfile?.currentEstimate?.summary ?? "Diagnostic evidence has not been collected yet.")}</p>
      ${renderReferenceChips(toList(data.scoreProfile?.risks), "risk")}
    `),
    "Daily training tasks": renderModuleSafely("dashboard", "Daily training tasks", () => renderDailyTasks(data, "dashboard")),
  };

  const swimlaneSections = {
    "8-week swimlane": renderModuleSafely("swimlane", "8-week swimlane", () => renderSwimlane(data)),
    "Checkpoint rules": renderModuleSafely("swimlane", "Checkpoint rules", () => renderCheckpointList(data)),
    "Daily training tasks": renderModuleSafely("swimlane", "Daily training tasks", () => renderDailyTasks(data, "swimlane")),
  };

  const errorSections = {
    Errors: renderModuleSafely("errors", "Errors", () => renderErrors(data)),
    "Regression control": renderModuleSafely("errors", "Regression control", () => renderTaskChecklist({
      sourceId: "errors:regression-control",
      fieldName: "reviewMethod",
      items: toList(data.errorLog?.errors).map((error) => `${error.id}: verify whether this error is fixed repeatedly or regressed.`),
      taskState,
    })),
  };

  const noteSections = {
    Notes: renderModuleSafely("notes", "Notes", () => renderNotes(data)),
    "Indexed note bodies": renderModuleSafely("notes", "Indexed note bodies", () => `
      <div class="knowledge-list">
        ${buildDocumentNotes(data.notes, "note")
          .map((note) => `
            <article class="knowledge-card" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-note-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}">
              <h3>${escapeHtml(note.title)}</h3>
              <div class="knowledge-card-body">${note.body}</div>
            </article>
          `)
          .join("")}
      </div>
    `),
  };

  const journalSections = {
    Journal: renderModuleSafely("journal", "Journal", () => renderJournal(data)),
    "Session bodies": renderModuleSafely("journal", "Session bodies", () => `
      <div class="knowledge-list">
        ${buildDocumentNotes(data.journal, "journal")
          .map((note) => `
            <article class="knowledge-card" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-note-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}">
              <h3>${escapeHtml(note.title)}</h3>
              <div class="knowledge-card-body">${note.body}</div>
            </article>
          `)
          .join("")}
      </div>
    `),
  };

  const promptSections = {
    "Prompt library": renderModuleSafely("prompt-library", "Prompt library", () => renderPromptLibrary(data)),
    "Prompt bodies": renderModuleSafely("prompt-library", "Prompt bodies", () => `
      <div class="knowledge-list">
        ${buildDocumentNotes(data.promptLibrary, "prompt")
          .map((note) => `
            <article class="knowledge-card" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-note-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}">
              <h3>${escapeHtml(note.title)}</h3>
              <div class="knowledge-card-body">${note.body}</div>
            </article>
          `)
          .join("")}
      </div>
    `),
  };

  const validationSections = {
    Validation: renderModuleSafely("validation", "Validation", () => renderValidation(data)),
    "Validation bodies": renderModuleSafely("validation", "Validation bodies", () => `
      <div class="knowledge-list">
        ${buildDocumentNotes(data.validation, "validation")
          .map((note) => `
            <article class="knowledge-card" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-note-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}">
              <h3>${escapeHtml(note.title)}</h3>
              <div class="knowledge-card-body">${note.body}</div>
            </article>
          `)
          .join("")}
      </div>
    `),
  };

  const modules = [
    createReaderModule({
      id: "dashboard",
      title: "Dashboard",
      status: data.scoreProfile?.state ?? "template",
      priority: "score profile",
      learningProgress: data.scoreProfile?.state === "template" ? 10 : 45,
      lastUpdated,
      sections: dashboardSections,
      knowledgeNotes: [
        makeKnowledgeNote("dashboard-target", "Target and diagnosis boundary", `<p>${escapeHtml(formatTarget(target))}</p>`),
      ],
    }),
    createReaderModule({
      id: "swimlane",
      title: "8-week swimlane",
      status: "ready",
      priority: "weekly execution",
      learningProgress: 15,
      lastUpdated,
      sections: swimlaneSections,
      knowledgeNotes: toList(data.checkpoints?.checkpoints).map((checkpoint) => makeKnowledgeNote(
        `checkpoint-week-${checkpoint.week}`,
        checkpoint.name,
        `<p>${escapeHtml(checkpoint.purpose)}</p><p>${escapeHtml(checkpoint.decision)}</p>`,
      )),
    }),
    createReaderModule({
      id: "errors",
      title: "Errors",
      status: toList(data.errorLog?.errors).length ? "active" : "not-started",
      priority: "high-impact repair",
      learningProgress: 20,
      lastUpdated,
      sections: errorSections,
      knowledgeNotes: buildErrorNotes(data),
    }),
    createReaderModule({
      id: "notes",
      title: "Notes",
      status: toList(data.notes).length ? "ready" : "not-started",
      priority: "study memory",
      learningProgress: toList(data.notes).length ? 20 : 0,
      lastUpdated,
      sections: noteSections,
      knowledgeNotes: buildDocumentNotes(data.notes, "note"),
    }),
    createReaderModule({
      id: "journal",
      title: "Journal",
      status: toList(data.journal).length ? "ready" : "not-started",
      priority: "weekly review",
      learningProgress: toList(data.journal).length ? 20 : 0,
      lastUpdated,
      sections: journalSections,
      knowledgeNotes: buildDocumentNotes(data.journal, "journal"),
    }),
    createReaderModule({
      id: "prompt-library",
      title: "Prompt library",
      status: "ready",
      priority: "agent operation",
      learningProgress: 40,
      lastUpdated,
      sections: promptSections,
      knowledgeNotes: buildDocumentNotes(data.promptLibrary, "prompt"),
    }),
    createReaderModule({
      id: "validation",
      title: "Validation",
      status: "ready",
      priority: "quality gate",
      learningProgress: 35,
      lastUpdated,
      sections: validationSections,
      knowledgeNotes: buildDocumentNotes(data.validation, "validation"),
    }),
  ];

  return {
    project: {
      id: "ielts-academic",
      title: "语言",
      targetRole: `IELTS Academic · ${formatTarget(target)}`,
      dashboardModuleId: "dashboard",
      overallLearningProgress: Math.round(modules.reduce((sum, module) => sum + module.learningProgress, 0) / modules.length),
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
  document.querySelectorAll(".search-shortcut").forEach((shortcut) => {
    shortcut.textContent = getShortcutLabel();
  });
  setTheme(state.ui.theme, { persist: false });
}

function getAnnotationsForNote(moduleId, noteId) {
  return state.annotations.items.filter((item) => item.moduleId === moduleId && item.noteId === noteId);
}

function getReadableCardFromNode(node) {
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

function getSelectionAnnotationContext() {
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
  return `ielts-ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
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
    createdAt: now,
    updatedAt: now,
  };
  state.annotations.items.push(annotation);
  saveAnnotations(state.annotations);
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
  saveAnnotations(state.annotations);
}

function hideAnnotationDeletePopover() {
  state.annotationDeletePopover?.remove();
  state.annotationDeletePopover = null;
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
  saveAnnotations(state.annotations);
  hideAnnotationDeletePopover();
  applyHighlights();
  renderContextualNotePanel(getKnowledgeNoteById(state.currentModule, annotation.noteId));
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
    const card = els.sectionList.querySelector(`[data-note-id="${CSS.escape(annotation.noteId)}"], [data-section-id="${CSS.escape(annotation.noteId)}"]`);
    if (!card) continue;
    const range = findTextRange(card, annotation.selectedText, annotation.matchIndex);
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
  return fromQuery || fromHash || "dashboard";
}

function getModuleById(moduleId) {
  return state.data?.modules.find((module) => module.id === moduleId);
}

function getSectionId(module, title) {
  return module.sectionIds?.[title] ?? `${module.id}-${slugify(title)}`;
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
  const noteTargets = toList(module.knowledgeNotes).map((note) => ({
    id: note.id,
    title: note.title,
  }));
  return [...sectionTargets, ...noteTargets];
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

function renderProgressSummary(module) {
  const progress = getLearningProgress(module);
  const overallProgress = getOverallLearningProgress();
  return `
    <div class="module-progress-summary" aria-label="阅读进度摘要">
      <div class="progress-ring" style="--progress: ${progress}" aria-label="本模块进度 ${progress}%">
        <span>${escapeHtml(String(progress))}%</span>
      </div>
      <div>
        <p class="progress-label">本模块进度</p>
        <p class="progress-status">${escapeHtml(getStatusLabel(module.status))} · ${escapeHtml(module.priority)}</p>
      </div>
      <div class="overall-progress-card" aria-label="整体进度 ${overallProgress}%">
        <span class="overall-progress-tag">全部模块</span>
        <span class="overall-progress-value">${escapeHtml(String(overallProgress))}%</span>
      </div>
    </div>
  `;
}

function renderKnowledgeNotesSection(module) {
  const notes = toList(module.knowledgeNotes);
  if (notes.length === 0) return "";
  return `
    <article class="module-section" id="${escapeHtml(module.id)}-parallel-notes" data-section-id="${escapeHtml(module.id)}-parallel-notes" data-note-id="${escapeHtml(module.id)}-parallel-notes" data-section-title="Parallel notes">
      <h2>Parallel notes</h2>
      <div class="section-body knowledge-list">
        ${notes.map((note) => `
          <article class="knowledge-card" id="${escapeHtml(note.id)}" data-section-id="${escapeHtml(note.id)}" data-section-title="${escapeHtml(note.title)}" data-note-id="${escapeHtml(note.id)}">
            <h3>${escapeHtml(note.title)}</h3>
            <div class="knowledge-card-body">${note.body}</div>
          </article>
        `).join("")}
      </div>
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
  const noteBlocks = renderKnowledgeNotesSection(module);

  els.sectionList.innerHTML = sectionBlocks || noteBlocks
    ? `${sectionBlocks}${noteBlocks}`
    : `
      <article class="status-panel">
        <h2>${escapeHtml(module.title)}</h2>
        <p>这个模块还没有可展示内容。</p>
      </article>
    `;

  els.sectionList.querySelectorAll("[data-section-id], [data-note-id]").forEach((card) => {
    card.addEventListener("click", () => {
      setActiveKnowledgeContext(card.dataset.noteId || card.dataset.sectionId);
    });
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

function getKnowledgeNoteById(module, noteId) {
  if (!module || !noteId) return null;
  return toList(module.knowledgeNotes).find((note) => note.id === noteId)
    ?? module.sectionNotes?.[noteId]
    ?? null;
}

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
          <textarea class="local-annotation-editor" rows="4" data-annotation-editor="${escapeHtml(annotation.id)}" placeholder="写下理解、反思或备考动作">${escapeHtml(annotation.note)}</textarea>
          ${annotation.highlightActive ? "" : `<p class="local-annotation-status">原文高亮已删除，笔记仍保留。</p>`}
        </article>
      `).join("")}
    </section>
  `;
}

function renderContextualNotePanel(note) {
  const module = state.currentModule;
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
    : `<p class="note-empty">选择正文区块或选中文本后，可在这里查看上下文和本地批注。</p>`;

  const label = `Parallel note · ${module.title}`;
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
      });
    });
  }
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
  setActiveKnowledgeContext(sectionId);
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
    els.searchResults.innerHTML = `<p class="result-empty">No results found</p>`;
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
        <h2>IELTS reader 加载失败</h2>
        <p>${escapeHtml(error.message)}</p>
      </article>
    `;
  }
}

init();
