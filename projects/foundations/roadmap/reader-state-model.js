const CURATED_SECTION_TITLES = [
  "目标",
  "当前状态",
  "核心知识",
  "任务",
  "时间线",
  "学习记录",
  "知识笔记",
];

const VALID_THEMES = new Set(["light", "dark"]);

function normalizeProjectId(projectId) {
  const normalized = String(projectId ?? "foundations").trim();
  return normalized || "foundations";
}

export function getReaderThemeStorageKey(projectId) {
  return `${normalizeProjectId(projectId)}Reader.theme.v1`;
}

export function getReaderPanelStorageKey(projectId, panelId) {
  const normalizedPanelId = String(panelId ?? "panel").trim() || "panel";
  return `${normalizeProjectId(projectId)}Reader.${normalizedPanelId}.v1`;
}

export function getDefaultNotePanelCollapsed(projectId) {
  return normalizeProjectId(projectId) === "finance";
}

export function resolveInitialTheme({ projectId, storedTheme, htmlTheme } = {}) {
  if (VALID_THEMES.has(storedTheme)) return storedTheme;
  if (VALID_THEMES.has(htmlTheme)) return htmlTheme;
  return normalizeProjectId(projectId) === "finance" ? "dark" : "light";
}

export function getNextIncompleteModule(modules = []) {
  return modules.find((module) => module.status !== "done") ?? null;
}

export function getFinanceReentryState(modules = []) {
  const nextModule = getNextIncompleteModule(modules);
  return {
    nextModule,
    nextStepLabel: nextModule?.title ?? "全部模块已完成",
    status: nextModule?.status ?? "done",
  };
}

export function getRenderableSectionTitles(module, projectId) {
  const generatedTitles = Object.keys(module?.sections ?? {});
  if (projectId === "finance") return generatedTitles;
  if (module?.id === "overview") return generatedTitles;
  return CURATED_SECTION_TITLES.filter((title) => generatedTitles.includes(title));
}
