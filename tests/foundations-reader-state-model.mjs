import assert from "node:assert/strict";
import {
  getFinanceReentryState,
  getNextIncompleteModule,
  getRenderableSectionTitles,
} from "../projects/foundations/roadmap/reader-state-model.js";

const modules = [
  { id: "one", title: "第一模块", status: "done" },
  { id: "two", title: "第二模块", status: "in-progress" },
  { id: "three", title: "第三模块", status: "not-started" },
];

assert.equal(getNextIncompleteModule(modules)?.id, "two", "reader should select the first unfinished module");
assert.equal(getNextIncompleteModule(modules.map((module) => ({ ...module, status: "done" }))), null, "reader should return null when every module is complete");
assert.equal(getNextIncompleteModule([]), null, "reader should handle an empty module list");

const activeReentry = getFinanceReentryState(modules);
assert.equal(activeReentry.nextModule?.id, "two", "finance re-entry should expose the next unfinished module");
assert.equal(activeReentry.nextStepLabel, "第二模块", "finance should expose the active next-step title");
assert.equal(activeReentry.status, "in-progress", "finance re-entry should expose the active module status");

const completeReentry = getFinanceReentryState(modules.map((module) => ({ ...module, status: "done" })));
assert.deepEqual(completeReentry, {
  nextModule: null,
  nextStepLabel: "全部模块已完成",
  status: "done",
}, "finance should expose directly testable all-complete copy and status");

const sectionModule = {
  sections: {
    目标: "goal",
    "13.1 P/E：市盈率": "pe",
    "13.2 PEG：把增长加入 P/E": "peg",
    知识笔记: "notes",
  },
};

assert.deepEqual(
  getRenderableSectionTitles(sectionModule, "finance"),
  Object.keys(sectionModule.sections),
  "finance should render every generated section in source order",
);
assert.deepEqual(
  getRenderableSectionTitles(sectionModule, "foundations"),
  ["目标", "知识笔记"],
  "Foundations should keep its curated section contract",
);
