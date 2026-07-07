import { escapeHtml, stableHash, toList } from "./reader-utils.js";

export function createStableTaskId(sourceId, fieldName, text) {
  return `${sourceId}:${fieldName}:${stableHash(text)}`;
}

function normalizeLegacyIds(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  return value ? [value] : [];
}

export function renderTaskChecklist({
  sourceId,
  fieldName,
  items,
  taskState = {},
  legacyIds = [],
  onTaskStateMigrated,
}) {
  const rows = toList(items).filter(Boolean);
  if (rows.length === 0) return "";
  let didMigrate = false;
  const renderedRows = rows
    .map((item, index) => {
      const taskId = createStableTaskId(sourceId, fieldName, item);
      const legacyTaskIds = normalizeLegacyIds(legacyIds[index]);
      const hasLegacyState = legacyTaskIds.some((legacyId) => Boolean(taskState[legacyId]));
      if (hasLegacyState && !taskState[taskId]) {
        taskState[taskId] = true;
        didMigrate = true;
      }
      const isDone = Boolean(taskState[taskId]);
      return `
        <li class="task-item${isDone ? " is-done" : ""}">
          <label>
            <input type="checkbox" data-task-id="${escapeHtml(taskId)}" ${isDone ? "checked" : ""} />
            <span>${escapeHtml(item)}</span>
          </label>
        </li>
      `;
    })
    .join("");

  if (didMigrate && typeof onTaskStateMigrated === "function") {
    onTaskStateMigrated(taskState);
  }

  return `
    <ul class="task-list">
      ${renderedRows}
    </ul>
  `;
}
