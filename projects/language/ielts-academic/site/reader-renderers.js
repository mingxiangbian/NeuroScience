import { makeKnowledgeNote } from "./reader-modules.js";
import { renderReferenceChips } from "./reader-references.js";
import { renderTaskChecklist } from "./reader-tasks.js";
import { escapeHtml, renderExamMark, slugify, titleCase, toList, truncateText } from "./reader-utils.js";

export const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8];
export const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];

const SKILL_LABELS = {
  listening: "听力",
  reading: "阅读",
  writing: "写作",
  speaking: "口语",
  general: "通用",
};

const CONFIDENCE_LABELS = {
  low: "低置信度",
  medium: "中等置信度",
  high: "高置信度",
};

const RISK_LABELS = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  unknown: "风险未知",
};

const IMPACT_LABELS = {
  low: "低影响",
  medium: "中影响",
  high: "高影响",
};

const DIMENSION_LABELS = {
  spelling: "拼写",
  "synonym recognition": "同义替换识别",
  "section 4 academic comprehension": "第 4 部分学术理解",
  "speed tracking": "语速跟踪",
  TFNG: "判断题",
  "matching headings": "标题匹配",
  "multiple choice": "选择题",
  "time allocation": "时间分配",
  "Task 1 overview": "Task 1 概览",
  "Task 2 argument development": "Task 2 论证展开",
  "grammar accuracy": "语法准确性",
  "lexical control": "词汇控制",
  pronunciation: "发音",
  "real-time fluency": "实时流利度",
  "Part 2 expansion": "Part 2 展开",
  "Part 3 abstraction": "Part 3 抽象讨论",
};

const CHECKPOINT_LABELS = {
  "Data Quality Check": "数据质量检查",
  "Target Feasibility Check": "目标可行性检查",
  "Trajectory And Allocation Check": "进度与分配检查",
  "Final Lock-in": "最终锁定",
};

function getBandNumber(value) {
  if (value === null || value === undefined) return NaN;
  if (typeof value === "string" && value.trim() === "") return NaN;
  return Number(value);
}

export function formatBand(value) {
  const band = getBandNumber(value);
  return Number.isFinite(band) ? band.toFixed(1) : "未验证";
}

export function formatTarget(target) {
  if (!target || typeof target !== "object") return "总分 8.0 / 单项 7.5+";
  const overall = Number.isFinite(Number(target.overall)) ? Number(target.overall).toFixed(1) : "8.0";
  const floor = Number.isFinite(Number(target.perSkillFloor)) ? Number(target.perSkillFloor).toFixed(1) : "7.5";
  const weeks = Number.isFinite(Number(target.timelineWeeks)) ? `${Number(target.timelineWeeks)}周` : "8周";
  return `总分 ${overall} / 单项 ${floor}+ / ${weeks}`;
}

function getCheckpointDisplayName(checkpoint) {
  const name = String(checkpoint?.name ?? "").trim();
  const week = String(checkpoint?.week ?? "").trim();
  if (!name) return week ? `检查点 ${week}` : "检查点";
  const pattern = new RegExp(`^Week\\s*${week}\\s*[·:|\\-–—]?\\s*`, "i");
  const displayName = name.replace(pattern, "").trim() || name;
  return CHECKPOINT_LABELS[displayName] ?? displayName;
}

function getSkillLabel(skill) {
  const id = typeof skill === "string" ? skill : skill?.id;
  const label = typeof skill === "object" ? skill?.label : "";
  return SKILL_LABELS[id] ?? label ?? titleCase(id ?? "general");
}

function getConfidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] ?? (confidence ? `${confidence} 置信度` : "低置信度");
}

function getRiskLabel(risk) {
  return RISK_LABELS[risk] ?? (risk ? `风险 ${risk}` : "风险未知");
}

function getImpactLabel(impact) {
  return IMPACT_LABELS[impact] ?? (impact ? `${impact} 影响` : "影响待定");
}

function getDimensionLabel(dimension) {
  return DIMENSION_LABELS[dimension] ?? dimension;
}

function getSeverityLabel(severity) {
  const labels = {
    fatal: "致命",
    warning: "警告",
  };
  return labels[severity] ?? severity;
}

export function getErrorStatusLabel(status) {
  const labels = {
    active: "活跃",
    improving: "改善中",
    fixed: "已修复",
    regressed: "复发",
  };
  return labels[status] ?? titleCase(status);
}

function getCheckpointStatusLabel(status) {
  const labels = {
    complete: "已完成",
    ready: "可执行",
    "not-started": "未开始",
    "not-yet-run": "未运行",
    template: "模板态",
  };
  return labels[status] ?? (status ? titleCase(status) : "未开始");
}

function getCompactWeekFocusLabel(focus) {
  if (/^诊断前模板态/.test(focus)) return "待诊断";
  if (/Data Quality|Target Feasibility|Trajectory|Final Lock-in|Check/i.test(focus)) return "检查点";
  if (/repair|修复/i.test(focus)) return "修复";
  if (/verify|验证/i.test(focus)) return "验证";
  if (/maintain|保持/i.test(focus)) return "保持";
  return truncateText(focus, 12);
}

function getBodyPreview(item, maxLength = 220) {
  let preview = truncateText(item?.body ?? "", maxLength);
  const title = String(item?.title ?? "").trim();
  if (title && preview.toLowerCase().startsWith(title.toLowerCase())) {
    preview = preview.slice(title.length).replace(/^[:：.\s·|-]+/, "").trim();
  }
  return preview || title;
}

function renderSkillGapBars(skills, target) {
  const floor = Number.isFinite(Number(target?.perSkillFloor)) ? Number(target.perSkillFloor) : 7.5;
  const safeSkills = toList(skills);

  if (safeSkills.length === 0) {
    return '<p class="empty-state">暂无技能画像。</p>';
  }

  return `
    <div class="skill-gap-list">
      ${safeSkills
        .map((skill) => {
          const estimate = getBandNumber(skill.estimatedBand);
          const hasEstimate = Number.isFinite(estimate);
          const fill = hasEstimate ? Math.max(0, Math.min(100, (estimate / floor) * 100)) : 0;
          const gap = hasEstimate ? Math.max(0, floor - estimate).toFixed(1) : "待诊断";
          const dimensions = toList(skill.unverifiedDimensions);
          return `
            <article class="skill-gap-row">
              <div class="skill-gap-header">
                ${renderExamMark(hasEstimate ? formatBand(skill.estimatedBand) : "–", { size: 38, pending: !hasEstimate })}
                <div class="skill-gap-copy">
                  <p class="skill-gap-label">${escapeHtml(getSkillLabel(skill))}</p>
                  <p class="skill-gap-meta">分数 ${escapeHtml(formatBand(skill.estimatedBand))} · 差距 ${escapeHtml(gap)} · ${escapeHtml(getRiskLabel(skill.riskLevel))}</p>
                </div>
                <p class="skill-gap-meta skill-gap-confidence">${escapeHtml(getConfidenceLabel(skill.confidence))}</p>
              </div>
              ${
                dimensions.length
                  ? `<div class="skill-gap-dimensions" aria-label="未验证维度">${dimensions.map((dimension) => `<span>${escapeHtml(getDimensionLabel(dimension))}</span>`).join("")}</div>`
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
    return '<p class="empty-state score-history-empty">暂无真实诊断轨迹。完成第 1 周诊断后再显示趋势。</p>';
  }
  return `
    <div class="score-history" aria-label="成绩轨迹">
      <table>
        <thead>
          <tr>
            <th scope="col">日期</th>
            <th scope="col">周次</th>
            <th scope="col">听力</th>
            <th scope="col">阅读</th>
            <th scope="col">写作</th>
            <th scope="col">口语</th>
            <th scope="col">总分</th>
          </tr>
        </thead>
        <tbody>
          ${realEntries.map((entry) => `
            <tr>
              <td>${escapeHtml(entry.date ?? "未注明日期")}</td>
              <th scope="row">第 ${escapeHtml(entry.week)} 周</th>
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
  const profileState = profile.state ?? "template";
  const isTemplateState = ["template", "not-yet-run"].includes(profileState);
  const checkpoints = toList(data.checkpoints?.checkpoints);
  const nextCheckpoint = checkpoints.find((checkpoint) => checkpoint.status !== "complete") ?? checkpoints[0];
  const skills = toList(profile.skills);
  const focusSkill = skills.find((skill) => skill.riskLevel === "high") ?? skills[0];
  const referenceIssueCount = toList(data.build?.referenceIssues).length;
  const validationIssues = toList(data.build?.validationIssues);
  const fatalCount = validationIssues.filter((issue) => issue.severity === "fatal").length;
  const warningCount = validationIssues.filter((issue) => issue.severity === "warning").length;

  return `
    <div class="dashboard-stack">
      <article class="evidence-ledger" data-state="${escapeHtml(profileState)}">
        <div class="evidence-ledger-copy">
          <p>证据账本</p>
          <h3>${isTemplateState ? "诊断证据还没落地" : "围绕最高风险技能修正"}</h3>
        </div>
        <dl class="evidence-ledger-list" aria-label="下一步 IELTS 训练动作">
          <div>
            <dt>下一步</dt>
            <dd>${isTemplateState ? "完成第 1 周诊断" : "修复活跃错误"}</dd>
          </div>
          <div>
            <dt>检查点</dt>
            <dd>${escapeHtml(nextCheckpoint?.name ? getCheckpointDisplayName(nextCheckpoint) : "第 1 周诊断")}</dd>
          </div>
          <div>
            <dt>重点技能</dt>
            <dd>${escapeHtml(focusSkill ? getSkillLabel(focusSkill) : "先补证据")}</dd>
          </div>
        </dl>
      </article>
      ${renderMetricGrid([
        { label: "目标", value: formatTarget(target) },
        { label: "运行模式", value: profile.runMode === "not-yet-run" ? "尚未运行" : profile.runMode ?? "尚未运行" },
        { label: "状态", value: isTemplateState ? "证据缺失" : profileState },
        { label: "引用问题", value: String(referenceIssueCount) },
        { label: "验证", value: `${fatalCount} 致命 / ${warningCount} 警告` },
      ])}
      <article class="content-card">
        <h3>技能差距</h3>
        ${renderSkillGapBars(profile.skills, target)}
      </article>
      <article class="content-card">
        <h3>成绩轨迹</h3>
        ${renderScoreHistory(data.scoreHistory)}
      </article>
      <div class="dashboard-grid" aria-label="IELTS 总览">
        <section class="dashboard-card">
          <p class="dashboard-card-label">当前估计</p>
          <strong>${escapeHtml(formatBand(profile.currentEstimate?.overall))}</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">置信度</p>
          <strong>${escapeHtml(getConfidenceLabel(profile.currentEstimate?.confidence ?? "low"))}</strong>
        </section>
        <section class="dashboard-card">
          <p class="dashboard-card-label">开放风险</p>
          <strong>${escapeHtml(String(toList(profile.risks).length))}</strong>
        </section>
      </div>
    </div>
  `;
}

export function getSkillWeekFocus({ skill, week, errors, checkpoints, state }) {
  const label = getSkillLabel(skill);
  const risk = getRiskLabel(skill.riskLevel);
  if (state === "template" || state === "not-yet-run") {
    return `诊断前模板态：收集 ${label} 证据（${risk}）`;
  }
  const skillErrors = toList(errors).filter((error) => error.skill === skill.id);
  const repairErrors = skillErrors.filter((error) => (
    ["high", "medium"].includes(error.impact) && error.status !== "fixed"
  ));
  const dimensions = toList(skill.unverifiedDimensions).slice(0, 2).map(getDimensionLabel).join(" / ");
  const checkpoint = toList(checkpoints).find((item) => Number(item.week) === Number(week));
  if (checkpoint) return `${getCheckpointDisplayName(checkpoint)}：${toList(checkpoint.evidenceRequired).slice(0, 1).join("")}`;
  if (repairErrors.length > 0) return `${label}: 修复 ${repairErrors[0].id}（${getImpactLabel(repairErrors[0].impact)}）`;
  if (dimensions) return `${label}: 验证 ${dimensions}（${risk}）`;
  return `${label}: 保持并复盘（${risk}）`;
}

export function renderCheckpointMilestones(checkpoints) {
  const rows = toList(checkpoints);
  if (rows.length === 0) return "";
  return `
    <div class="checkpoint-milestones" aria-label="全局检查点">
      ${rows.map((checkpoint) => `
        <article class="checkpoint-marker" data-week="${escapeHtml(checkpoint.week)}">
          ${renderExamMark(`W${checkpoint.week}`, { size: 40, pending: checkpoint.status !== "complete" })}
          <div class="checkpoint-copy">
            <strong>${escapeHtml(getCheckpointDisplayName(checkpoint))}</strong>
            <span>${escapeHtml(getCheckpointStatusLabel(checkpoint.status))}</span>
            <span>${escapeHtml(toList(checkpoint.evidenceRequired).length ? `${toList(checkpoint.evidenceRequired).length} 项证据` : "证据待定")}</span>
          </div>
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
  if (skills.length === 0) return '<p class="empty-state">暂无技能画像。</p>';
  return `
    ${renderCheckpointMilestones(checkpoints)}
    <div class="swimlane-scroll">
      <table class="swimlane-table">
        <thead>
          <tr>
            <th scope="col">技能</th>
            ${WEEKS.map((week) => `<th scope="col">第 ${week} 周</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${skills.map((skill) => `
            <tr>
              <th scope="row">${escapeHtml(getSkillLabel(skill))}</th>
              ${WEEKS.map((week) => {
                const focus = getSkillWeekFocus({ skill, week, errors, checkpoints, state: scoreProfile.state });
                return `
                  <td>
                    <span class="swimlane-chip" title="${escapeHtml(focus)}">${escapeHtml(getCompactWeekFocusLabel(focus))}</span>
                  </td>
                `;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderCheckpointList(data) {
  const checkpoints = toList(data.checkpoints?.checkpoints);
  if (checkpoints.length === 0) return '<p class="empty-state">暂无检查点。</p>';
  return `
    <div class="stack">
      ${checkpoints
        .map((checkpoint) => `
          <article class="content-card">
            <p class="card-kicker">第 ${escapeHtml(checkpoint.week)} 周 · ${escapeHtml(getCheckpointStatusLabel(checkpoint.status))}</p>
            <h3>${escapeHtml(getCheckpointDisplayName(checkpoint))}</h3>
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
    "记录今天实际专注学习分钟数，再调整周分配。",
    "先完成一个诊断或复盘任务，再补新理论。",
    "只有证据变化后才更新置信度和未验证维度。",
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
  const skillLabel = getSkillLabel(error.skill ?? "general");
  return `
    <article class="error-card">
      <p class="card-kicker">${escapeHtml(getImpactLabel(error.impact))} · ${escapeHtml(getErrorStatusLabel(error.status ?? "active"))}</p>
      <h3>${escapeHtml(`${error.id} · ${skillLabel}`)}</h3>
      <p class="card-body error-description">${escapeHtml(error.description)}</p>
      <p class="error-priority">${escapeHtml(error.nextReview ? `下次复查：${error.nextReview}` : "下次复查待定")}</p>
      <p class="card-body error-review">${escapeHtml(error.reviewMethod ?? "")}</p>
      ${renderReferenceChips([{ referenceId: `error:${error.id}`, label: error.id }], "error")}
    </article>
  `;
}

export function renderErrors(data) {
  const allErrors = toList(data.errorLog?.errors);
  const activeErrors = allErrors.filter((error) => (error.status ?? "active") === "active");
  const statusSummaries = ERROR_STATUSES.filter((status) => status !== "active").map((status) => {
    const statusErrors = allErrors.filter((error) => error.status === status);
    return `
      <section class="error-status-pill" aria-label="${escapeHtml(getErrorStatusLabel(status))}">
        <div>
          <h3>${escapeHtml(getErrorStatusLabel(status))}</h3>
          <p>${statusErrors.length ? `${statusErrors.length} 个错误` : "暂无匹配错误"}</p>
        </div>
        ${
          statusErrors.length
            ? `<div class="error-status-items">${statusErrors.map((error) => `
                <button class="error-status-item reference-chip" type="button" data-kind="error" data-reference-id="${escapeHtml(`error:${error.id}`)}">
                  ${escapeHtml(error.id)}
                </button>
              `).join("")}</div>`
            : ""
        }
      </section>
    `;
  }).join("");

  return `
    <div class="error-board">
      <section class="error-active-list" aria-label="活跃错误">
        <div class="error-column-heading">
          <h3>活跃错误</h3>
          <span>${escapeHtml(String(activeErrors.length))}</span>
        </div>
        <div class="error-card-stack">
          ${
            activeErrors.length > 0
              ? activeErrors.map(renderErrorCard).join("")
              : '<p class="empty-state">暂无匹配错误。</p>'
          }
        </div>
      </section>
      <aside class="error-status-strip" aria-label="其他错误状态">
        ${statusSummaries}
      </aside>
    </div>
  `;
}

export function renderCompactDocumentCard(item, options = {}) {
  const {
    referencePrefix,
    kindLabel = "文档",
    meta = "",
    relatedErrors = [],
    relatedNotes = [],
  } = options;
  const referenceId = `${referencePrefix}:${item.id}`;
  const sourceLabel = item.path ? "查看详情" : "查看内容";
  return `
    <article class="compact-document-card">
      <div class="compact-document-main">
        <p class="card-kicker">${escapeHtml(kindLabel)}${meta ? ` · ${escapeHtml(meta)}` : ""}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="compact-document-preview">${escapeHtml(getBodyPreview(item, 150))}</p>
      </div>
      <div class="compact-document-actions">
        ${renderReferenceChips([{ referenceId, label: sourceLabel, sourcePath: item.path }], "source")}
        ${renderReferenceChips(toList(relatedErrors).map((errorId) => ({
          referenceId: `error:${errorId}`,
          label: errorId,
        })), "error")}
        ${renderReferenceChips(toList(relatedNotes).map((noteId) => ({
          referenceId: `note:${noteId}`,
          label: noteId,
        })), "note")}
      </div>
    </article>
  `;
}

export function renderNotes(data) {
  const notes = toList(data.notes);
  if (notes.length === 0) return '<p class="empty-state">暂无已索引笔记。</p>';

  return `
    <div class="compact-document-grid">
      ${notes
        .map((note) => renderCompactDocumentCard(note, {
          referencePrefix: "note",
          kindLabel: "笔记",
          meta: [note.skill ? getSkillLabel(note.skill) : "", note.topic ?? ""].filter(Boolean).join(" · "),
          relatedErrors: note.relatedErrors,
        }))
        .join("")}
    </div>
  `;
}

export function renderJournal(data) {
  const entries = toList(data.journal);
  if (entries.length === 0) return '<p class="empty-state">暂无已索引日志。</p>';

  return `
    <div class="stack">
      ${entries
        .map((entry) => `
          <article class="journal-card">
            <p class="card-kicker">${escapeHtml(entry.date ?? "未注明日期")}</p>
            <h3>${escapeHtml(entry.title)}</h3>
            <p class="card-body">${escapeHtml(getBodyPreview(entry))}</p>
            ${renderReferenceChips([{ referenceId: `journal:${entry.id}`, label: entry.path, sourcePath: entry.path }], "source")}
            ${renderReferenceChips(toList(entry.relatedErrors).map((errorId) => ({
              referenceId: `error:${errorId}`,
              label: errorId,
            })), "error")}
            ${renderReferenceChips(toList(entry.relatedNotes).map((noteId) => ({
              referenceId: `note:${noteId}`,
              label: noteId,
            })), "note")}
          </article>
        `)
        .join("")}
    </div>
  `;
}

export function renderPromptLibrary(data) {
  const prompts = toList(data.promptLibrary);
  if (prompts.length === 0) return '<p class="empty-state">暂无提示词文档。</p>';

  return `
    <div class="compact-document-grid">
      ${prompts
        .map((prompt) => renderCompactDocumentCard(prompt, {
          referencePrefix: "prompt",
          kindLabel: "提示词",
          meta: prompt.id ?? "",
        }))
        .join("")}
    </div>
  `;
}

export function renderValidation(data) {
  const checks = toList(data.validation);
  const issues = toList(data.build?.validationIssues);
  const issuePanel = `
    <section class="validation-issues" aria-label="构建验证问题">
      <h3>构建验证</h3>
      ${
        issues.length
          ? issues.map((issue) => `
            <article class="validation-issue" data-severity="${escapeHtml(issue.severity)}">
              <strong>${escapeHtml(getSeverityLabel(issue.severity))} · ${escapeHtml(issue.type)}</strong>
              <span>${escapeHtml(issue.path)}</span>
              <p>${escapeHtml(issue.message)}</p>
            </article>
          `).join("")
          : '<p class="empty-state">暂无构建验证问题。</p>'
      }
    </section>
  `;
  if (checks.length === 0) return issuePanel;

  return `
    <div class="stack">
      ${issuePanel}
      <div class="compact-document-grid">
        ${checks
          .map((check) => renderCompactDocumentCard(check, {
            referencePrefix: "validation",
            kindLabel: "验证",
            meta: check.id ?? "",
          }))
          .join("")}
      </div>
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
      ${renderReferenceChips([{ referenceId: `error:${error.id}`, label: error.id }], "error")}
    `,
    [
      {
        label: "证据",
        body: `<ul>${toList(error.evidence).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`,
      },
      {
        label: "下次复查",
        body: `<p>${escapeHtml(error.nextReview ?? "待定")}</p>`,
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
        label: "来源",
        body: renderReferenceChips([{ referenceId: `${prefix}:${item.id}`, label: item.path, sourcePath: item.path }], "source"),
      },
    ],
  ));
}
