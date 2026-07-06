const UI_STATE_KEY = "ieltsReader.ui.v1";
const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8];
const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];
const LANE_LABELS = ["Listening", "Reading", "Writing", "Speaking", "Errors"];

const roots = {
  dashboard: document.querySelector('[data-render="dashboard"]'),
  swimlane: document.querySelector('[data-render="swimlane"]'),
  errors: document.querySelector('[data-render="errors"]'),
  notes: document.querySelector('[data-render="notes"]'),
  journal: document.querySelector('[data-render="journal"]'),
  promptLibrary: document.querySelector('[data-render="prompt-library"]'),
  validation: document.querySelector('[data-render="validation"]'),
};

const state = {
  searchTerm: "",
  errorSkill: "all",
  errorImpact: "all",
};

let readerData = null;

async function fetchJson(path) {
  const response = await fetch(new URL(path, window.location.href));
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

function setHtml(root, html) {
  if (root) root.innerHTML = html;
}

function toList(value) {
  return Array.isArray(value) ? value : [];
}

function toSearchText(value) {
  if (Array.isArray(value)) return value.map(toSearchText).join(" ");
  if (value && typeof value === "object") return Object.values(value).map(toSearchText).join(" ");
  return String(value ?? "").toLowerCase();
}

function matchesSearch(item) {
  const term = state.searchTerm.trim().toLowerCase();
  if (!term) return true;
  return toSearchText(item).includes(term);
}

function truncateText(value, maxLength = 220) {
  const text = String(value ?? "")
    .replace(/[#*_`>]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

function formatTarget(target) {
  if (!target || typeof target !== "object") return "Overall 8.0 / each skill 7.5+";
  const overall = Number.isFinite(Number(target.overall)) ? Number(target.overall).toFixed(1) : "8.0";
  const floor = Number.isFinite(Number(target.perSkillFloor)) ? Number(target.perSkillFloor).toFixed(1) : "7.5";
  const weeks = Number.isFinite(Number(target.timelineWeeks)) ? `${Number(target.timelineWeeks)} weeks` : "8 weeks";
  return `Overall ${overall} / each skill ${floor}+ / ${weeks}`;
}

function formatBand(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "Unverified";
}

function titleCase(value) {
  return String(value ?? "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function renderSkillGapBars(skills, target) {
  const floor = Number.isFinite(Number(target?.perSkillFloor)) ? Number(target.perSkillFloor) : 7.5;
  const safeSkills = toList(skills);

  if (safeSkills.length === 0) {
    return '<p class="empty-state">No skill profile has been generated yet.</p>';
  }

  return `
    <div class="stack">
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

function renderDashboard(data) {
  const target = data.project?.target ?? data.scoreProfile?.target ?? {};
  const profile = data.scoreProfile ?? {};
  const referenceIssueCount = toList(data.build?.referenceIssues).length;

  setHtml(
    roots.dashboard,
    `
      <div class="dashboard-stack">
        <div class="metric-grid">
          <article class="metric-card">
            <p class="metric-label">Target</p>
            <p class="metric-value">${escapeHtml(formatTarget(target))}</p>
          </article>
          <article class="metric-card">
            <p class="metric-label">Run mode</p>
            <p class="metric-value">${escapeHtml(profile.runMode ?? "not-yet-run")}</p>
          </article>
          <article class="metric-card">
            <p class="metric-label">State</p>
            <p class="metric-value">${escapeHtml(profile.state ?? "template")}</p>
          </article>
          <article class="metric-card">
            <p class="metric-label">Reference issues</p>
            <p class="metric-value">${escapeHtml(referenceIssueCount)}</p>
          </article>
        </div>
        <article class="content-card">
          <h3>Skill gaps</h3>
          ${renderSkillGapBars(profile.skills, target)}
        </article>
      </div>
    `,
  );
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

  const rows = LANE_LABELS.map((label) => {
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

  setHtml(roots.swimlane, `<div class="swimlane-grid">${header}${rows}</div>`);
}

function filterErrors(errors) {
  return toList(errors).filter((error) => {
    const skillMatch = state.errorSkill === "all" || error.skill === state.errorSkill;
    const impactMatch = state.errorImpact === "all" || error.impact === state.errorImpact;
    return skillMatch && impactMatch && matchesSearch(error);
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

function renderSelectOptions(values, activeValue, fallbackLabel) {
  return [
    `<option value="all"${activeValue === "all" ? " selected" : ""}>${escapeHtml(fallbackLabel)}</option>`,
    ...values.map((value) => `<option value="${escapeHtml(value)}"${activeValue === value ? " selected" : ""}>${escapeHtml(titleCase(value))}</option>`),
  ].join("");
}

function bindErrorControls(data) {
  const skillSelect = roots.errors?.querySelector('[data-error-filter="skill"]');
  const impactSelect = roots.errors?.querySelector('[data-error-filter="impact"]');

  skillSelect?.addEventListener("change", () => {
    state.errorSkill = skillSelect.value;
    saveUiState();
    renderErrors(data);
  });

  impactSelect?.addEventListener("change", () => {
    state.errorImpact = impactSelect.value;
    saveUiState();
    renderErrors(data);
  });
}

function renderErrors(data) {
  const allErrors = toList(data.errorLog?.errors);
  const skills = Array.from(new Set(allErrors.map((error) => error.skill).filter(Boolean))).sort();
  const impacts = Array.from(new Set(allErrors.map((error) => error.impact).filter(Boolean))).sort();
  const filteredErrors = filterErrors(allErrors);

  const columns = ERROR_STATUSES.map((status) => {
    const statusErrors = filteredErrors.filter((error) => error.status === status);
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

  setHtml(
    roots.errors,
    `
      <div class="error-controls">
        <label>
          Skill
          <select data-error-filter="skill">
            ${renderSelectOptions(skills, state.errorSkill, "All skills")}
          </select>
        </label>
        <label>
          Impact
          <select data-error-filter="impact">
            ${renderSelectOptions(impacts, state.errorImpact, "All impacts")}
          </select>
        </label>
      </div>
      <div class="error-board">${columns}</div>
    `,
  );
  bindErrorControls(data);
}

function renderNotes(data) {
  const notes = toList(data.notes).filter(matchesSearch);
  if (notes.length === 0) {
    setHtml(roots.notes, '<p class="empty-state">No notes match the current search.</p>');
    return;
  }

  setHtml(
    roots.notes,
    `
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
    `,
  );
}

function renderJournal(data) {
  const entries = toList(data.journal).filter(matchesSearch);
  if (entries.length === 0) {
    setHtml(roots.journal, '<p class="empty-state">No journal entries match the current search.</p>');
    return;
  }

  setHtml(
    roots.journal,
    `
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
    `,
  );
}

function renderPromptLibrary(data) {
  const prompts = toList(data.promptLibrary);
  if (prompts.length === 0) {
    setHtml(roots.promptLibrary, '<p class="empty-state">No prompt documents found.</p>');
    return;
  }

  setHtml(
    roots.promptLibrary,
    `
      <div class="stack">
        ${prompts
          .map((prompt) => `
            <article class="content-card">
              <p class="card-kicker">${escapeHtml(prompt.id ?? "prompt")}</p>
              <h3>${escapeHtml(prompt.title)}</h3>
              ${renderReferenceChips([{ label: prompt.path, href: prompt.path }], "source")}
            </article>
          `)
          .join("")}
      </div>
    `,
  );
}

function renderValidation(data) {
  const checks = toList(data.validation);
  if (checks.length === 0) {
    setHtml(roots.validation, '<p class="empty-state">No validation documents found.</p>');
    return;
  }

  setHtml(
    roots.validation,
    `
      <div class="stack">
        ${checks
          .map((check) => `
            <article class="content-card">
              <p class="card-kicker">${escapeHtml(check.id ?? "validation")}</p>
              <h3>${escapeHtml(check.title)}</h3>
              ${renderReferenceChips([{ label: check.path, href: check.path }], "source")}
            </article>
          `)
          .join("")}
      </div>
    `,
  );
}

function runReaderSearch(term = state.searchTerm) {
  state.searchTerm = String(term ?? "");
  const input = document.querySelector("#reader-search");
  if (input && input.value !== state.searchTerm) input.value = state.searchTerm;
  saveUiState();

  if (!readerData) return;
  renderErrors(readerData);
  renderNotes(readerData);
  renderJournal(readerData);
}

function saveUiState() {
  const payload = {
    searchTerm: state.searchTerm,
    errorSkill: state.errorSkill,
    errorImpact: state.errorImpact,
  };

  try {
    localStorage.setItem("ieltsReader.ui.v1", JSON.stringify(payload));
  } catch {
    return;
  }
}

function loadUiState() {
  try {
    const saved = JSON.parse(localStorage.getItem(UI_STATE_KEY) ?? "{}");
    state.searchTerm = typeof saved.searchTerm === "string" ? saved.searchTerm : "";
    state.errorSkill = typeof saved.errorSkill === "string" ? saved.errorSkill : "all";
    state.errorImpact = typeof saved.errorImpact === "string" ? saved.errorImpact : "all";
  } catch {
    state.searchTerm = "";
    state.errorSkill = "all";
    state.errorImpact = "all";
  }
}

function renderAll(data) {
  renderDashboard(data);
  renderSwimlane(data);
  renderErrors(data);
  renderNotes(data);
  renderJournal(data);
  renderPromptLibrary(data);
  renderValidation(data);
}

function bindNavigation() {
  document.querySelectorAll("[data-section-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.sectionTarget);
      if (!target) return;
      document.querySelectorAll("[data-section-target]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      target.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  });
}

function init() {
  loadUiState();
  bindNavigation();

  const searchInput = document.querySelector("#reader-search");
  if (searchInput) {
    searchInput.value = state.searchTerm;
    searchInput.addEventListener("input", () => runReaderSearch(searchInput.value));
  }

  fetchJson("site/ielts-data.json")
    .then((data) => {
      readerData = data;
      renderAll(data);
    })
    .catch((error) => {
      setHtml(roots.dashboard, `<p class="empty-state">${escapeHtml(error.message)}</p>`);
    });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
