const CURATED_SECTION_TITLES = [
  "目标",
  "当前状态",
  "核心知识",
  "任务",
  "时间线",
  "学习记录",
  "知识笔记",
];

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
  return CURATED_SECTION_TITLES.filter((title) => generatedTitles.includes(title));
}
