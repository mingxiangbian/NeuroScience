export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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
