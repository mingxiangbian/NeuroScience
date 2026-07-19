import { makeKnowledgeNote } from "./reader-modules.js";
import { renderReferenceChips } from "./reader-references.js";
import { escapeHtml, titleCase, toList, truncateText } from "./reader-utils.js";

export const ERROR_STATUSES = ["active", "improving", "fixed", "regressed"];

const SKILL_LABELS = {
  listening: "听力",
  reading: "阅读",
  writing: "写作",
  speaking: "口语",
  general: "通用",
};

const CONFIDENCE_LABELS = {
  unverified: "未验证",
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
  if (!target || typeof target !== "object") return "总分 7.5 · 单项线待确认";
  const overallBand = getBandNumber(target.overall);
  const floorBand = getBandNumber(target.perSkillFloor);
  const overall = Number.isFinite(overallBand) ? overallBand.toFixed(1) : "7.5";
  const floor = Number.isFinite(floorBand) ? `单项 ${floorBand.toFixed(1)}+` : "单项线待确认";
  return `总分 ${overall} · ${floor}`;
}

function getSkillLabel(skill) {
  const id = typeof skill === "string" ? skill : skill?.id;
  const label = typeof skill === "object" ? skill?.label : "";
  return SKILL_LABELS[id] ?? label ?? titleCase(id ?? "general");
}

function getConfidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] ?? (confidence ? `${confidence} 置信度` : "未验证");
}

function getRiskLabel(risk) {
  return RISK_LABELS[risk] ?? (risk ? `风险 ${risk}` : "风险未知");
}

function getImpactLabel(impact) {
  return IMPACT_LABELS[impact] ?? (impact ? `${impact}影响` : "影响待定");
}

function getDimensionLabel(dimension) {
  return DIMENSION_LABELS[dimension] ?? dimension;
}

function getSeverityLabel(severity) {
  return { fatal: "致命", warning: "警告" }[severity] ?? severity;
}

export function getErrorStatusLabel(status) {
  return {
    active: "活跃",
    improving: "改善中",
    fixed: "已修复",
    regressed: "复发",
  }[status] ?? titleCase(status);
}

export function getUnitStatusLabel(status) {
  return {
    suggested: "建议",
    ready: "待开启",
    active: "进行中",
    settled: "已结算",
  }[status] ?? titleCase(status);
}

function getUnitTypeLabel(type) {
  return {
    diagnostic: "诊断单元",
    repair: "修复单元",
    mock: "模考单元",
    calibration: "校准单元",
  }[type] ?? type;
}

function getCalibrationStatusLabel(status) {
  return {
    waiting: "等待证据",
    triggered: "已触发",
    decided: "已决策",
  }[status] ?? status;
}

function getBodyPreview(item, maxLength = 150) {
  let preview = truncateText(item?.body ?? "", maxLength);
  const title = String(item?.title ?? "").trim();
  if (title && preview.toLowerCase().startsWith(title.toLowerCase())) {
    preview = preview.slice(title.length).replace(/^[:：.\s·|-]+/, "").trim();
  }
  return preview || title;
}

function getAllUnits(unitLedger) {
  return [
    unitLedger?.activeUnit,
    unitLedger?.suggestedUnit,
    ...toList(unitLedger?.queue),
    ...toList(unitLedger?.settled),
  ].filter(Boolean);
}

function renderUnitRecord(unit, options = {}) {
  if (!unit) return "";
  const { prominent = false } = options;
  return `
    <article class="unit-record${prominent ? " unit-record-prominent" : ""}" id="unit-${escapeHtml(unit.id)}" data-unit-status="${escapeHtml(unit.status)}">
      <div class="unit-record-heading">
        <p class="card-kicker">${escapeHtml(unit.id)} · ${escapeHtml(getUnitTypeLabel(unit.type))} · ${escapeHtml(getUnitStatusLabel(unit.status))}</p>
        <h3>${escapeHtml(unit.title)}</h3>
      </div>
      ${unit.reason ? `<p class="card-body unit-reason">${escapeHtml(unit.reason)}</p>` : ""}
      <dl class="unit-facts">
        <div><dt>第一步</dt><dd>${escapeHtml(unit.nextAction)}</dd></div>
        <div><dt>产物</dt><dd>${escapeHtml(unit.expectedArtifact)}</dd></div>
        <div><dt>复查</dt><dd>${escapeHtml(unit.reviewMethod)}</dd></div>
      </dl>
      <div class="settlement-criteria">
        <p class="card-kicker">结算判据</p>
        <ol>${toList(unit.settlementCriteria).map((criterion) => `<li>${escapeHtml(criterion)}</li>`).join("")}</ol>
      </div>
      ${renderReferenceChips([{ referenceId: `unit:${unit.id}`, label: "查看单元详情", sourcePath: "plans/unit-ledger.json" }], "unit")}
    </article>
  `;
}

export function renderNow(data) {
  const ledger = data.unitLedger ?? {};
  const activeUnit = ledger.activeUnit;
  const suggestedUnit = ledger.suggestedUnit;
  const currentTrigger = toList(data.calibrationEvents?.events).find((event) => event.id === data.derived?.currentTrigger);
  const hasStarted = Boolean(
    activeUnit
      || (ledger.state && ledger.state !== "not-started")
      || toList(ledger.settled).length
      || toList(data.scoreHistory?.entries).length,
  );
  const leadUnit = activeUnit ?? (!hasStarted ? suggestedUnit : null);
  const stateLabel = activeUnit ? "一个单元正在进行" : hasStarted ? "当前没有活动单元" : "学习尚未开始";
  const headline = activeUnit?.title ?? (hasStarted ? "等待下一份独立证据" : "先保留空白，不伪造进度");
  const nextAction = leadUnit?.nextAction
    ?? (hasStarted ? currentTrigger?.condition ?? "等待下一项校准事件触发。" : "等待真实诊断输入。");

  return `
    <div class="now-stack" data-learning-state="${escapeHtml(ledger.state ?? "not-started")}">
      <article class="current-action">
        <p class="card-kicker">现在 · ${escapeHtml(stateLabel)}</p>
        <h3>${escapeHtml(headline)}</h3>
        <div class="next-action-block">
          <span>第一步</span>
          <p>${escapeHtml(nextAction)}</p>
        </div>
        ${
          activeUnit
            ? renderReferenceChips([{ referenceId: `unit:${activeUnit.id}`, label: `活动单元 ${activeUnit.id}` }], "unit")
            : !hasStarted && suggestedUnit
              ? `<p class="current-action-note">${escapeHtml(suggestedUnit.id)} 只是建议诊断，不代表已经开始，也不代表写作已被判断为最弱项。</p>${renderReferenceChips([{ referenceId: `unit:${suggestedUnit.id}`, label: `建议单元 ${suggestedUnit.id}` }], "unit")}`
              : ""
        }
      </article>
      <dl class="now-ledger" aria-label="当前决策边界">
        <div><dt>目标</dt><dd>${escapeHtml(formatTarget(data.project?.target ?? data.scoreProfile?.target))}</dd></div>
        <div><dt>成绩证据</dt><dd>${toList(data.scoreHistory?.entries).length ? `${toList(data.scoreHistory.entries).length} 条事件` : "尚无真实记录"}</dd></div>
        <div><dt>真实错误</dt><dd>${toList(data.errorLog?.errors).length ? `${toList(data.errorLog.errors).length} 个` : "尚未识别"}</dd></div>
        <div><dt>下一触发器</dt><dd>${escapeHtml(currentTrigger?.label ?? "等待首份真实诊断证据")}</dd></div>
      </dl>
    </div>
  `;
}

export function renderUnits(data) {
  const ledger = data.unitLedger ?? {};
  const queue = toList(ledger.queue);
  const settled = toList(ledger.settled);
  return `
    <div class="unit-ledger-view">
      <section class="ledger-group">
        <div class="ledger-heading"><h3>活动单元</h3><span>${ledger.activeUnit ? "1" : "0"}</span></div>
        ${ledger.activeUnit ? renderUnitRecord(ledger.activeUnit, { prominent: true }) : '<p class="empty-state">当前没有活动单元。只有用户明确开始后，建议单元才会移入这里。</p>'}
      </section>
      <section class="ledger-group">
        <div class="ledger-heading"><h3>建议单元</h3><span>${ledger.suggestedUnit ? "1" : "0"}</span></div>
        ${ledger.suggestedUnit ? renderUnitRecord(ledger.suggestedUnit) : '<p class="empty-state">暂无建议单元。</p>'}
      </section>
      <section class="ledger-group ledger-compact">
        <div class="ledger-heading"><h3>候选队列</h3><span>${queue.length}</span></div>
        ${queue.length ? queue.map((unit) => renderUnitRecord(unit)).join("") : '<p class="empty-state">队列为空。队列不是债，不产生逾期。</p>'}
      </section>
      <section class="ledger-group ledger-compact">
        <div class="ledger-heading"><h3>已结算</h3><span>${settled.length}</span></div>
        ${settled.length ? settled.map((unit) => renderUnitRecord(unit)).join("") : '<p class="empty-state">还没有结算记录。</p>'}
      </section>
    </div>
  `;
}

function renderErrorCard(error) {
  return `
    <article class="error-card" id="error-${escapeHtml(error.id)}">
      <p class="card-kicker">${escapeHtml(error.id)} · ${escapeHtml(getSkillLabel(error.skill))} · ${escapeHtml(getImpactLabel(error.impact))}</p>
      <h3>${escapeHtml(getErrorStatusLabel(error.status))}</h3>
      <p class="card-body error-description">${escapeHtml(error.description)}</p>
      <dl class="error-evidence-meta">
        <div><dt>最后出现</dt><dd>${escapeHtml(error.lastSeenAt || "待记录")}</dd></div>
        <div><dt>连续无错</dt><dd>${escapeHtml(String(error.consecutiveCleanSamples ?? 0))} / 3</dd></div>
      </dl>
      ${renderReferenceChips([{ referenceId: `error:${error.id}`, label: "查看证据" }], "error")}
    </article>
  `;
}

export function renderErrors(data) {
  const allErrors = toList(data.errorLog?.errors);
  if (allErrors.length === 0) {
    return `
      <div class="error-empty-state">
        <h3>还没有真实错误记录</h3>
        <p>未验证维度不是错误。只有真实样本证明某个模式存在后，才会进入错误生命周期。</p>
        <div class="error-lifecycle" aria-label="错误生命周期">
          <span>活跃</span><span>改善中</span><span>已修复</span><span>复发</span>
        </div>
      </div>
    `;
  }

  return `
    <div class="error-status-board">
      ${ERROR_STATUSES.map((status) => {
        const errors = allErrors.filter((error) => error.status === status);
        return `
          <section class="error-status-group" data-error-status="${escapeHtml(status)}">
            <div class="ledger-heading"><h3>${escapeHtml(getErrorStatusLabel(status))}</h3><span>${errors.length}</span></div>
            ${errors.length ? errors.map(renderErrorCard).join("") : '<p class="empty-state">暂无记录。</p>'}
          </section>
        `;
      }).join("")}
    </div>
  `;
}

export function renderScoreHistory(scoreHistory) {
  const entries = toList(scoreHistory?.entries);
  if (entries.length === 0) return '<p class="empty-state score-history-empty">暂无真实成绩事件。完成诊断或模考并保留证据后再显示。</p>';
  return `
    <div class="score-history" aria-label="成绩证据事件">
      <table>
        <thead><tr><th>日期</th><th>事件</th><th>来源</th><th>听</th><th>读</th><th>写</th><th>说</th><th>总分</th><th>置信度</th></tr></thead>
        <tbody>
          ${entries.map((entry) => `
            <tr id="evidence-${escapeHtml(entry.id)}">
              <td>${escapeHtml(entry.date)}</td>
              <th scope="row">${escapeHtml(entry.eventType)}</th>
              <td>${escapeHtml(entry.sourceType)}</td>
              <td>${escapeHtml(formatBand(entry.skills?.listening))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.reading))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.writing))}</td>
              <td>${escapeHtml(formatBand(entry.skills?.speaking))}</td>
              <td>${escapeHtml(formatBand(entry.overall))}</td>
              <td>${escapeHtml(getConfidenceLabel(entry.confidence))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderSkillEvidence(skill) {
  return `
    <article class="skill-evidence-row">
      <div class="skill-evidence-heading">
        <h3>${escapeHtml(getSkillLabel(skill))}</h3>
        <strong>${escapeHtml(formatBand(skill.estimatedBand))}</strong>
        <span>${escapeHtml(getConfidenceLabel(skill.confidence))} · ${escapeHtml(getRiskLabel(skill.riskLevel))}</span>
      </div>
      <p>${escapeHtml(toList(skill.evidenceBasis).join(" ") || "尚无证据说明。")}</p>
      <div class="skill-gap-dimensions" aria-label="未验证维度">
        ${toList(skill.unverifiedDimensions).map((dimension) => `<span>${escapeHtml(getDimensionLabel(dimension))}</span>`).join("")}
      </div>
    </article>
  `;
}

export function renderEvidence(data) {
  const profile = data.scoreProfile ?? {};
  return `
    <div class="evidence-view">
      <article class="evidence-summary">
        <div><span>当前判断</span><strong>${escapeHtml(formatBand(profile.currentEstimate?.overall))}</strong></div>
        <p>${escapeHtml(profile.currentEstimate?.summary ?? "尚无真实诊断证据。")}</p>
        <p class="evidence-boundary">目标 ${escapeHtml(formatTarget(profile.target))}。LLM 评分仅作建议，未验证维度不折算成分数。</p>
      </article>
      <div class="skill-evidence-list">${toList(profile.skills).map(renderSkillEvidence).join("")}</div>
      <section class="evidence-events"><h3>成绩事件</h3>${renderScoreHistory(data.scoreHistory)}</section>
    </div>
  `;
}

export function renderSettlements(data) {
  const settledUnits = toList(data.unitLedger?.settled);
  const events = toList(data.calibrationEvents?.events);
  return `
    <div class="settlement-view">
      <section class="settled-units">
        <div class="ledger-heading"><h3>已通过判据的单元</h3><span>${settledUnits.length}</span></div>
        ${settledUnits.length ? settledUnits.map((unit) => renderUnitRecord(unit)).join("") : '<p class="empty-state">还没有单元通过结算判据。</p>'}
      </section>
      <section class="calibration-events">
        <div class="ledger-heading"><h3>事件触发校准</h3><span>${events.length}</span></div>
        ${events.map((event) => `
          <article class="calibration-event" id="calibration-${escapeHtml(event.id)}" data-calibration-status="${escapeHtml(event.status)}">
            <div>
              <p class="card-kicker">${escapeHtml(getCalibrationStatusLabel(event.status))}</p>
              <h3>${escapeHtml(event.label)}</h3>
              <p>${escapeHtml(event.condition)}</p>
            </div>
            <p class="calibration-decision">${escapeHtml(event.decision ?? "尚未触发，不作决定。")}</p>
            ${renderReferenceChips([{ referenceId: `calibration:${event.id}`, label: "查看触发条件" }], "calibration")}
          </article>
        `).join("")}
      </section>
    </div>
  `;
}

export function renderCompactDocumentCard(item, options = {}) {
  const { referencePrefix, kindLabel = "文档", meta = "", relatedErrors = [], relatedNotes = [] } = options;
  const referenceId = `${referencePrefix}:${item.id}`;
  return `
    <article class="compact-document-card" id="${escapeHtml(referencePrefix)}-${escapeHtml(item.id)}">
      <div class="compact-document-main">
        <p class="card-kicker">${escapeHtml(kindLabel)}${meta ? ` · ${escapeHtml(meta)}` : ""}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="compact-document-preview">${escapeHtml(getBodyPreview(item))}</p>
      </div>
      <div class="compact-document-actions">
        ${renderReferenceChips([{ referenceId, label: "查看详情", sourcePath: item.path }], "source")}
        ${renderReferenceChips(toList(relatedErrors).map((errorId) => ({ referenceId: `error:${errorId}`, label: errorId })), "error")}
        ${renderReferenceChips(toList(relatedNotes).map((noteId) => ({ referenceId: `note:${noteId}`, label: noteId })), "note")}
      </div>
    </article>
  `;
}

export function renderNotes(data) {
  const notes = toList(data.notes);
  if (notes.length === 0) return '<p class="empty-state">暂无已索引笔记。</p>';
  return `<div class="compact-document-grid">${notes.map((note) => renderCompactDocumentCard(note, {
    referencePrefix: "note",
    kindLabel: "笔记",
    meta: [note.skill ? getSkillLabel(note.skill) : "", note.topic ?? ""].filter(Boolean).join(" · "),
    relatedErrors: note.relatedErrors,
  })).join("")}</div>`;
}

export function renderJournal(data) {
  const entries = toList(data.journal);
  if (entries.length === 0) return '<p class="empty-state">暂无已索引复盘。</p>';
  return `<div class="compact-document-grid">${entries.map((entry) => renderCompactDocumentCard(entry, {
    referencePrefix: "journal",
    kindLabel: "复盘",
    meta: entry.date ?? "未注明日期",
    relatedErrors: entry.relatedErrors,
    relatedNotes: entry.relatedNotes,
  })).join("")}</div>`;
}

export function renderPromptLibrary(data) {
  const prompts = toList(data.promptLibrary);
  if (prompts.length === 0) return '<p class="empty-state">暂无提示词文档。</p>';
  return `<div class="compact-document-grid">${prompts.map((prompt) => renderCompactDocumentCard(prompt, {
    referencePrefix: "prompt",
    kindLabel: "提示词",
    meta: prompt.id ?? "",
  })).join("")}</div>`;
}

export function renderValidation(data) {
  const checks = toList(data.validation);
  const issues = toList(data.build?.validationIssues);
  return `
    <div class="validation-view">
      <section class="validation-issues" aria-label="构建验证问题">
        <div class="ledger-heading"><h3>构建验证</h3><span>${issues.length}</span></div>
        ${issues.length ? issues.map((validationIssue) => `
          <article class="validation-issue" data-severity="${escapeHtml(validationIssue.severity)}">
            <strong>${escapeHtml(getSeverityLabel(validationIssue.severity))} · ${escapeHtml(validationIssue.type)}</strong>
            <span>${escapeHtml(validationIssue.path)}</span>
            <p>${escapeHtml(validationIssue.message)}</p>
          </article>
        `).join("") : '<p class="empty-state">暂无构建验证问题。</p>'}
      </section>
      <div class="compact-document-grid">${checks.map((check) => renderCompactDocumentCard(check, {
        referencePrefix: "validation",
        kindLabel: "验证",
        meta: check.id ?? "",
      })).join("")}</div>
    </div>
  `;
}

export function buildUnitNotes(data) {
  return getAllUnits(data.unitLedger).map((unit) => makeKnowledgeNote(
    `unit-${unit.id}`,
    `${unit.id} · ${unit.title}`,
    `<p>${escapeHtml(unit.nextAction)}</p>`,
    [{ label: "结算判据", body: `<ol>${toList(unit.settlementCriteria).map((criterion) => `<li>${escapeHtml(criterion)}</li>`).join("")}</ol>` }],
  ));
}

export function buildErrorNotes(data) {
  return toList(data.errorLog?.errors).map((error) => makeKnowledgeNote(
    `error-${error.id}`,
    `${error.id} · ${error.description}`,
    `<p>${escapeHtml(error.description)}</p>${renderReferenceChips([{ referenceId: `error:${error.id}`, label: error.id }], "error")}`,
    [
      { label: "证据", body: `<ul>${toList(error.evidence).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` },
      { label: "复查方法", body: `<p>${escapeHtml(error.reviewMethod ?? "待定")}</p>` },
    ],
  ));
}

export function buildDocumentNotes(items, prefix) {
  return toList(items).map((item) => makeKnowledgeNote(
    `${prefix}-${item.id}`,
    item.title,
    item.html ?? `<p>${escapeHtml(item.body ?? "")}</p>`,
    [{ label: "来源", body: renderReferenceChips([{ referenceId: `${prefix}:${item.id}`, label: item.path, sourcePath: item.path }], "source") }],
  ));
}
