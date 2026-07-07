import { escapeHtml, toList, truncateText } from "./reader-utils.js";

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

export function makeReferenceChipFromTarget(target, kind = target?.type ?? "reference") {
  if (!target) return "";
  return renderReferenceChips([{ referenceId: target.id, label: target.label, sourcePath: target.sourcePath }], kind);
}

export function getReferencePanelPayload(data, referenceId) {
  const target = getReferenceTarget(data, referenceId);
  if (!target) return null;
  const raw = data.raw ?? data;
  const collections = {
    error: raw.errorLog?.errors ?? [],
    note: raw.notes ?? [],
    journal: raw.journal ?? [],
    prompt: raw.promptLibrary ?? [],
    validation: raw.validation ?? [],
  };
  const record = toList(collections[target.type]).find((item) => item.id === target.rawId) ?? {};
  const relatedObjects = [
    ...toList(record.relatedErrors).map((id) => ({ referenceId: `error:${id}`, label: id, type: "error" })),
    ...toList(record.relatedNotes).map((id) => ({ referenceId: `note:${id}`, label: id, type: "note" })),
  ];
  return {
    target,
    record,
    backlinks: getBacklinks(data, referenceId),
    relatedObjects,
    title: target.label,
    status: record.status ?? record.impact ?? "",
    skill: record.skill ?? "",
    date: record.date ?? "",
    summary: record.summary ?? record.description ?? record.body ?? "",
    body: record.html ?? `<p>${escapeHtml(truncateText(record.body ?? record.description ?? ""))}</p>`,
  };
}

export function renderReferencePanel(payload) {
  if (!payload) return '<p class="note-empty">引用对象不存在。</p>';
  const sourceLink = payload.target.sourcePath
    ? `<a class="reference-panel-action" href="${escapeHtml(payload.target.sourcePath)}">查看源文件</a>`
    : "";
  return `
    <article class="note-context reference-panel" data-reference-panel="${escapeHtml(payload.target.id)}">
      <p class="card-kicker">${escapeHtml(payload.target.type)} · ${escapeHtml(payload.target.sourcePath ?? "")}</p>
      <h3>${escapeHtml(payload.title)}</h3>
      <dl class="reference-panel-meta">
        <div><dt>Type</dt><dd>${escapeHtml(payload.target.type)}</dd></div>
        <div><dt>Status</dt><dd>${escapeHtml(payload.status || "n/a")}</dd></div>
        <div><dt>Skill</dt><dd>${escapeHtml(payload.skill || "n/a")}</dd></div>
        <div><dt>Date</dt><dd>${escapeHtml(payload.date || "n/a")}</dd></div>
        <div><dt>Source</dt><dd>${escapeHtml(payload.target.sourcePath || "generated data")}</dd></div>
      </dl>
      <p class="card-body">${escapeHtml(truncateText(payload.summary))}</p>
      <div class="note-group-body">${payload.body}</div>
      <div class="reference-panel-actions">
        <button class="reference-panel-action" type="button" data-jump-reference="${escapeHtml(payload.target.id)}">跳转到模块位置</button>
        ${sourceLink}
      </div>
      <section class="note-block">
        <h3 class="note-group-title">Related objects</h3>
        ${
          payload.relatedObjects.length
            ? renderReferenceChips(payload.relatedObjects, "related")
            : '<p class="note-empty">暂无关联对象。</p>'
        }
      </section>
      <section class="note-block">
        <h3 class="note-group-title">Backlinks</h3>
        ${
          payload.backlinks.length
            ? renderReferenceChips(payload.backlinks.map((link) => ({ referenceId: link.id, label: link.label })), "backlink")
            : '<p class="note-empty">暂无反向引用。</p>'
        }
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
