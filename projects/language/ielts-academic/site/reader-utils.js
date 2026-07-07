export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderExamMark(label, { size = 56, pending = false } = {}) {
  const strokeColor = pending ? "var(--reader-ink-muted)" : "var(--reader-marker)";
  const dash = pending ? ' stroke-dasharray="4 3"' : "";
  return `
    <span class="exam-mark" style="--mark-size: ${size}px;">
      <svg viewBox="0 0 56 56" aria-hidden="true">
        <path d="M28 4C45 4 52 17 49 31C46 46 32 52 18 49C5 46 2 32 6 18C9 9 16 4 28 4Z" fill="none" stroke="${strokeColor}" stroke-width="2.5"${dash} />
      </svg>
      <span class="exam-mark-label">${escapeHtml(label)}</span>
    </span>
  `;
}

export function toList(value) {
  return Array.isArray(value) ? value : [];
}

export function titleCase(value) {
  return String(value ?? "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function slugify(value) {
  const slug = String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "section";
}

export function stableHash(value) {
  let hash = 0;
  for (const char of String(value ?? "")) {
    hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
  }
  return Math.abs(hash).toString(36).slice(0, 8);
}

export function stripHtml(value) {
  const temp = document.createElement("div");
  temp.innerHTML = String(value ?? "");
  return temp.textContent?.replace(/\s+/g, " ").trim() ?? "";
}

export function truncateText(value, maxLength = 220) {
  const text = String(value ?? "")
    .replace(/[#*_`>]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trim()}...`;
}

export function getShortcutLabel() {
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform) ? "⌘ K" : "Ctrl K";
}
