import { escapeHtml, toList, truncateText } from "./reader-utils.js";

function getUnits(raw) {
  return [
    raw.unitLedger?.activeUnit,
    raw.unitLedger?.suggestedUnit,
    ...toList(raw.unitLedger?.queue),
    ...toList(raw.unitLedger?.settled),
  ].filter(Boolean);
}

export function getReferenceTarget(data, referenceId) {
  return toList(data?.raw?.references?.targets ?? data?.references?.targets)
    .find((target) => target.id === referenceId) ?? null;
}

export function getBacklinks(data, referenceId) {
  return toList((data?.raw?.references?.backlinks ?? data?.references?.backlinks ?? {})[referenceId]);
}

export function renderReferenceChips(items, kind = "reference") {
  const chips = toList(items).filter(Boolean);
  if (chips.length === 0) return "";
  return `
    <div class="reference-chip-list">
      ${chips.map((item) => {
        const referenceId = typeof item === "string" ? item : item.referenceId;
        const label = typeof item === "string" ? item : item.label;
        const sourcePath = typeof item === "string" ? "" : item.sourcePath;
        return `
          <button class="reference-chip" type="button" data-kind="${escapeHtml(kind)}" data-reference-id="${escapeHtml(referenceId)}" data-source-path="${escapeHtml(sourcePath)}">
            ${escapeHtml(label ?? referenceId)}
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function getReferenceTypeLabel(type) {
  return {
    unit: "单元",
    error: "错误",
    evidence: "证据",
    calibration: "校准",
    note: "笔记",
    journal: "复盘",
    prompt: "提示词",
    validation: "验证",
    reference: "引用",
  }[type] ?? type;
}

function getRecordCollection(raw, type) {
  return {
    unit: getUnits(raw),
    error: raw.errorLog?.errors ?? [],
    evidence: raw.scoreHistory?.entries ?? [],
    calibration: raw.calibrationEvents?.events ?? [],
    note: raw.notes ?? [],
    journal: raw.journal ?? [],
    prompt: raw.promptLibrary ?? [],
    validation: raw.validation ?? [],
  }[type] ?? [];
}

function toReferenceObject(referenceId, type = "reference") {
  if (!referenceId) return null;
  return { referenceId, label: referenceId.replace(/^[^:]+:/, ""), type: referenceId.split(":")[0] || type };
}

function getRelatedObjects(record) {
  return [
    ...toList(record.relatedErrors).map((id) => ({ referenceId: `error:${id}`, label: id, type: "error" })),
    ...toList(record.relatedNotes).map((id) => ({ referenceId: `note:${id}`, label: id, type: "note" })),
    ...toList(record.errorRefs).map((id) => ({ referenceId: `error:${id}`, label: id, type: "error" })),
    ...toList(record.evidenceRefs).map((id) => toReferenceObject(id, "evidence")),
    ...toList(record.fixedEvidence).map((id) => toReferenceObject(id, "evidence")),
    record.repairUnitId ? { referenceId: `unit:${record.repairUnitId}`, label: record.repairUnitId, type: "unit" } : null,
  ].filter(Boolean);
}

function renderRecordBody(target, record) {
  if (target.type === "unit") {
    return `
      <dl class="reference-panel-meta">
        <div><dt>第一步</dt><dd>${escapeHtml(record.nextAction ?? "待定")}</dd></div>
        <div><dt>产物</dt><dd>${escapeHtml(record.expectedArtifact ?? "待定")}</dd></div>
        <div><dt>复查</dt><dd>${escapeHtml(record.reviewMethod ?? "待定")}</dd></div>
      </dl>
      <h4>结算判据</h4>
      <ol>${toList(record.settlementCriteria).map((criterion) => `<li>${escapeHtml(criterion)}</li>`).join("")}</ol>
    `;
  }
  if (target.type === "calibration") {
    return `<p>${escapeHtml(record.condition ?? "")}</p><p><strong>决定：</strong>${escapeHtml(record.decision ?? "尚未触发，不作决定。")}</p>`;
  }
  if (target.type === "evidence") {
    return `<p>${escapeHtml(record.notes ?? "成绩证据事件")}</p><p>置信度：${escapeHtml(record.confidence ?? "未验证")}</p>`;
  }
  return record.html ?? `<p>${escapeHtml(truncateText(record.body ?? record.description ?? ""))}</p>`;
}

export function getReferencePanelPayload(data, referenceId) {
  const target = getReferenceTarget(data, referenceId);
  if (!target) return null;
  const raw = data.raw ?? data;
  const record = toList(getRecordCollection(raw, target.type)).find((item) => item.id === target.rawId) ?? {};
  return {
    target,
    record,
    backlinks: getBacklinks(data, referenceId),
    relatedObjects: getRelatedObjects(record),
    title: target.label,
    status: record.status ?? record.impact ?? "",
    skill: record.skill ?? "",
    date: record.date ?? record.openedAt ?? record.settledAt ?? record.decidedAt ?? "",
    summary: record.summary ?? record.reason ?? record.description ?? record.condition ?? record.body ?? record.nextAction ?? "",
    body: renderRecordBody(target, record),
  };
}

export function renderReferencePanel(payload) {
  if (!payload) return '<p class="note-empty">引用对象不存在。</p>';
  const sourceLink = payload.target.sourcePath
    ? `<a class="reference-panel-action" href="${escapeHtml(payload.target.sourcePath)}">查看源文件</a>`
    : "";
  return `
    <article class="note-context reference-panel" data-reference-panel="${escapeHtml(payload.target.id)}">
      <p class="card-kicker">${escapeHtml(getReferenceTypeLabel(payload.target.type))}</p>
      <h3>${escapeHtml(payload.title)}</h3>
      <dl class="reference-panel-meta">
        <div><dt>类型</dt><dd>${escapeHtml(getReferenceTypeLabel(payload.target.type))}</dd></div>
        <div><dt>状态</dt><dd>${escapeHtml(payload.status || "无")}</dd></div>
        <div><dt>技能</dt><dd>${escapeHtml(payload.skill || "无")}</dd></div>
        <div><dt>日期</dt><dd>${escapeHtml(payload.date || "无")}</dd></div>
      </dl>
      ${payload.summary ? `<p class="card-body">${escapeHtml(truncateText(payload.summary))}</p>` : ""}
      <div class="note-group-body">${payload.body}</div>
      <div class="reference-panel-actions">
        <button class="reference-panel-action" type="button" data-jump-reference="${escapeHtml(payload.target.id)}">跳转到对应位置</button>
        ${sourceLink}
      </div>
      <section class="note-block">
        <h3 class="note-group-title">关联对象</h3>
        ${payload.relatedObjects.length ? renderReferenceChips(payload.relatedObjects, "related") : '<p class="note-empty">暂无关联对象。</p>'}
      </section>
      <section class="note-block">
        <h3 class="note-group-title">反向引用</h3>
        ${payload.backlinks.length ? renderReferenceChips(payload.backlinks.map((link) => ({ referenceId: link.id, label: link.label })), "backlink") : '<p class="note-empty">暂无反向引用。</p>'}
      </section>
    </article>
  `;
}

export function openReferenceTarget(data, referenceId, openModule) {
  const target = getReferenceTarget(data, referenceId);
  if (!target) return false;
  openModule(target.moduleId, { targetSectionId: target.sectionId });
  return true;
}
