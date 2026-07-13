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
