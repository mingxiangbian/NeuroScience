import { makeKnowledgeNote } from "./reader-modules.js";
import { renderTaskChecklist } from "./reader-tasks.js";
import { escapeHtml, slugify, titleCase, toList, truncateText } from "./reader-utils.js";

export const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8];
export const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];

function getBandNumber(value) {
  if (value === null || value === undefined) return NaN;
  if (typeof value === "string" && value.trim() === "") return NaN;
  return Number(value);
}

export function formatBand(value) {
  const band = getBandNumber(value);
  return Number.isFinite(band) ? band.toFixed(1) : "Unverified";
}

export function formatTarget(target) {
  if (!target || typeof target !== "object") return "Overall 8.0 / each skill 7.5+";
  const overall = Number.isFinite(Number(target.overall)) ? Number(target.overall).toFixed(1) : "8.0";
  const floor = Number.isFinite(Number(target.perSkillFloor)) ? Number(target.perSkillFloor).toFixed(1) : "7.5";
  const weeks = Number.isFinite(Number(target.timelineWeeks)) ? `${Number(target.timelineWeeks)} weeks` : "8 weeks";
  return `Overall ${overall} / each skill ${floor}+ / ${weeks}`;
}

export function renderReferenceChips(items, kind = "reference") {
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
    <div class="skill-gap-stack">
      ${safeSkills
        .map((skill) => {
          const estimate = getBandNumber(skill.estimatedBand);
          const hasEstimate = Number.isFinite(estimate);
          const fill = hasEstimate ? Math.max(0, Math.min(100, (estimate / floor) * 100)) : 0;
          const gap = hasEstimate ? Math.max(0, floor - estimate).toFixed(1) : "diagnostic needed";
          const dimensions = toList(skill.unverifiedDimensions);
          return `
            <article class="skill-gap">
              <div class="skill-gap-header">
                <div>
                  <p class="skill-gap-label">${escapeHtml(skill.label ?? titleCase(skill.id))}</p>
                  <p class="skill-gap-meta">Band ${escapeHtml(formatBand(skill.estimatedBand))} | Gap: ${escapeHtml(gap)} | Risk: ${escapeHtml(skill.riskLevel ?? "unknown")}</p>
                </div>
                <p class="skill-gap-meta">${escapeHtml(skill.confidence ?? "low")} confidence</p>
              </div>
              ${
                dimensions.length
                  ? `<p class="skill-gap-meta">Unverified: ${escapeHtml(dimensions.join(" / "))}</p>`
                  : ""
              }
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

export function renderScoreHistory(scoreHistory) {
  const entries = toList(scoreHistory?.entries);
  const realEntries = entries.filter((entry) => entry.state !== "template" && Number(entry.week) > 0);
  if (realEntries.length === 0) {
    return '<p class="empty-state score-history-empty">暂无真实诊断轨迹。Week 1 diagnostic 后再显示趋势。</p>';
  }
  return `
    <div class="score-history" aria-label="Score history">
      <table>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Week</th>
            <th scope="col">Listening</th>
            <th scope="col">Reading</th>
            <th scope="col">Writing</th>
            <th scope="col">Speaking</th>
            <th scope="col">Overall</th>
          </tr>
        </thead>
        <tbody>
          ${realEntries.map((entry) => `
            <tr>
              <td>${escapeHtml(entry.date ?? "undated")}</td>
              <th scope="row">Week ${escapeHtml(entry.week)}</th>
              <td>${escapeHtml(formatBand(entry.skills?.listening))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.reading))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.writing))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.speaking))}</td>
              <td>${escapeHtml(formatBand(entry.overall))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderDashboard(data) {
  const target = data.project?.target ?? data.scoreProfile?.target ?? {};
  const profile = data.scoreProfile ?? {};
  const referenceIssueCount = toList(data.build?.referenceIssues).length;
  const validationIssues = toList(data.build?.validationIssues);
  const fatalCount = validationIssues.filter((issue) => issue.severity === "fatal").length;
  const warningCount = validationIssues.filter((issue) => issue.severity === "warning").length;

  return `
    <div class="dashboard-stack">
      ${renderMetricGrid([
        { label: "Target", value: formatTarget(target) },
        { label: "Run mode", value: profile.runMode ?? "not-yet-run" },
        { label: "State", value: profile.state ?? "template" },
        { label: "Reference issues", value: String(referenceIssueCount) },
        { label: "Validation", value: `${fatalCount} fatal / ${warningCount} warning` },
      ])}
      <article class="content-card">
        <h3>Skill gaps</h3>
        ${renderSkillGapBars(profile.skills, target)}
      </article>
      <article class="content-card">
        <h3>Score history</h3>
        ${renderScoreHistory(data.scoreHistory)}
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

export function getSkillWeekFocus({ skill, week, errors, checkpoints, state }) {
  const label = skill.label ?? titleCase(skill.id);
  const risk = skill.riskLevel ? `risk ${skill.riskLevel}` : "risk unknown";
  if (state === "template" || state === "not-yet-run") {
    return `诊断前模板态：收集 ${label} 证据 (${risk})`;
  }
  const skillErrors = toList(errors).filter((error) => error.skill === skill.id);
  const repairErrors = skillErrors.filter((error) => (
    ["high", "medium"].includes(error.impact) && error.status !== "fixed"
  ));
  const dimensions = toList(skill.unverifiedDimensions).slice(0, 2).join(" / ");
  const checkpoint = toList(checkpoints).find((item) => Number(item.week) === Number(week));
  if (checkpoint) return `${checkpoint.name}: ${toList(checkpoint.evidenceRequired).slice(0, 1).join("")}`;
  if (repairErrors.length > 0) return `${label}: repair ${repairErrors[0].id} (${repairErrors[0].impact})`;
  if (dimensions) return `${label}: verify ${dimensions} (${risk})`;
  return `${label}: maintain and review (${risk})`;
}

export function renderCheckpointMilestones(checkpoints) {
  const rows = toList(checkpoints);
  if (rows.length === 0) return "";
  return `
    <div class="checkpoint-milestones" aria-label="Global checkpoint milestones">
      ${rows.map((checkpoint) => `
        <article class="checkpoint-marker" data-week="${escapeHtml(checkpoint.week)}">
          <strong>Week ${escapeHtml(checkpoint.week)} · ${escapeHtml(checkpoint.name)}</strong>
          <span>${escapeHtml(checkpoint.status ?? "not-started")}</span>
          <span>${escapeHtml(checkpoint.decision ?? checkpoint.purpose ?? "")}</span>
          <span>${escapeHtml(toList(checkpoint.evidenceRequired).join(" / "))}</span>
        </article>
      `).join("")}
    </div>
  `;
}

export function renderSwimlane(data) {
  const scoreProfile = data.scoreProfile ?? {};
  const skills = toList(scoreProfile.skills);
  const checkpoints = toList(data.checkpoints?.checkpoints);
  const errors = toList(data.errorLog?.errors);
  if (skills.length === 0) return '<p class="empty-state">No skill profile has been generated yet.</p>';
  return `
    ${renderCheckpointMilestones(checkpoints)}
    <div class="swimlane-scroll">
      <table class="swimlane-table">
        <thead>
          <tr>
            <th scope="col">Skill</th>
            ${WEEKS.map((week) => `<th scope="col">Week ${week}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${skills.map((skill) => `
            <tr>
              <th scope="row">${escapeHtml(skill.label ?? titleCase(skill.id))}</th>
              ${WEEKS.map((week) => `
                <td>${escapeHtml(getSkillWeekFocus({ skill, week, errors, checkpoints, state: scoreProfile.state }))}</td>
              `).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderCheckpointList(data) {
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

export function createLegacyTaskIds(moduleId, sectionTitle, count) {
  const slug = slugify(sectionTitle);
  return Array.from({ length: count }, (_, index) => `${moduleId}__${slug}__${index}`);
}

export function renderDailyTasks(data, moduleId, taskState, onTaskStateMigrated) {
  const errors = toList(data.errorLog?.errors).map((error) => `${error.id}: ${error.reviewMethod ?? error.description}`);
  const baseTasks = [
    "Log actual focused study minutes before changing the weekly allocation.",
    "Run one diagnostic or review task before adding new theory.",
    "Update confidence and unverified dimensions only after evidence changes.",
  ];
  const items = [...baseTasks, ...errors];
  return renderTaskChecklist({
    sourceId: `${moduleId}:daily-training`,
    fieldName: "dailyTask",
    items,
    taskState,
    legacyIds: createLegacyTaskIds(moduleId, "Daily training tasks", items.length),
    onTaskStateMigrated,
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

export function renderErrors(data) {
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

export function renderNotes(data) {
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

export function renderJournal(data) {
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

export function renderPromptLibrary(data) {
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

export function renderValidation(data) {
  const checks = toList(data.validation);
  if (checks.length === 0) return '<p class="empty-state">No validation documents found.</p>';

  return `
    <div class="stack">
      ${checks
        .map((check) => `
          <article class="content-card validation-issue">
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

export function buildErrorNotes(data) {
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

export function buildDocumentNotes(items, prefix) {
  return toList(items).map((item) => makeKnowledgeNote(
    `${prefix}-${item.id}`,
    item.title,
    item.html ?? `<p>${escapeHtml(item.body ?? "")}</p>`,
    [
      {
        label: "Source",
        body: renderReferenceChips([{ label: item.path, href: item.path }], "source"),
      },
    ],
  ));
}
