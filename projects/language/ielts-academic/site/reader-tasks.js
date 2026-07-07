import { escapeHtml, stableHash, toList } from "./reader-utils.js";

export function createStableTaskId(sourceId, fieldName, text) {
  return `${sourceId}:${fieldName}:${stableHash(text)}`;
}

export function renderTaskChecklist({ sourceId, fieldName, items, taskState }) {
  const rows = toList(items).filter(Boolean);
  if (rows.length === 0) return "";

  return `
    <ul class="task-list">
      ${rows
        .map((item) => {
          const taskId = createStableTaskId(sourceId, fieldName, item);
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
        .join("")}
    </ul>
  `;
}
