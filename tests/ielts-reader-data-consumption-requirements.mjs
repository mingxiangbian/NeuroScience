import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  formatTarget,
  getSprintDay,
  renderNow,
  renderSprintPlan,
} from "../projects/language/ielts-academic/site/reader-renderers.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const indexHtml = read("../projects/language/ielts-academic/index.html");
const entryJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const renderers = read("../projects/language/ielts-academic/site/reader-renderers.js");
const references = read("../projects/language/ielts-academic/site/reader-references.js");
const annotations = read("../projects/language/ielts-academic/site/reader-annotations.js");
const modules = read("../projects/language/ielts-academic/site/reader-modules.js");
const state = read("../projects/language/ielts-academic/site/reader-state.js");
const utils = read("../projects/language/ielts-academic/site/reader-utils.js");
const css = read("../projects/language/ielts-academic/site/ielts-reader.css");
const workflow = read("../.github/workflows/pages.yml");
const data = JSON.parse(read("../projects/language/ielts-academic/site/ielts-data.json"));

assert.match(entryJs, /from "\.\/reader-renderers\.js"/);
assert.match(entryJs, /from "\.\/reader-modules\.js"/);
assert.match(entryJs, /from "\.\/reader-references\.js"/);
assert.match(entryJs, /from "\.\/reader-annotations\.js"/);
assert.match(entryJs, /from "\.\/reader-state\.js"/);
assert.doesNotMatch(entryJs, /reader-tasks/);

for (const title of ["现在", "单元", "错误", "证据", "结算", "档案", "系统"]) {
  assert.match(entryJs, new RegExp(`title: "${title}"`), `reader should expose ${title}`);
}
assert.match(entryJs, /dashboardModuleId: "now"/);
assert.match(entryJs, /return fromQuery \|\| fromHash \|\| "now"/);
assert.match(entryJs, /function renderModuleNav/);
assert.match(entryJs, /function renderCurrentModule/);
assert.match(entryJs, /function renderSectionRail/);
assert.match(entryJs, /function runSearch/);
assert.match(entryJs, /function renderEmptyDetailPanel/);
assert.match(entryJs, /点击引用，或选中正文/);
assert.doesNotMatch(entryJs, /learningProgress|overallLearningProgress|renderProgressSummary|module-nav-progress/);
assert.doesNotMatch(entryJs, /data-task-id|taskState|saveTaskState|loadTaskState/);

assert.match(renderers, /function renderNow/);
assert.match(renderers, /data-learning-state/);
assert.match(renderers, /学习尚未开始/);
assert.match(renderers, /只是建议诊断，不代表已经开始/);
assert.match(renderers, /function renderUnits/);
assert.match(renderers, /当前没有活动单元/);
assert.match(renderers, /队列不是债，不产生逾期/);
assert.match(renderers, /function renderErrors/);
assert.match(renderers, /未验证维度不是错误/);
assert.match(renderers, /function renderEvidence/);
assert.match(renderers, /scoreHistory\?\.entries/);
assert.match(renderers, /function renderSettlements/);
assert.match(renderers, /事件触发校准/);
assert.match(renderers, /function renderSprintPlan/);
assert.match(renderers, /口试排程/);
assert.match(renderers, /conditionalReserve/);
assert.match(renderers, /function renderCompactDocumentCard/);
assert.match(renderers, /compact-document-grid/);
assert.doesNotMatch(renderers, /WEEKS|renderSwimlane|renderDailyTasks|renderCheckpointMilestones|\.week\b/);
assert.doesNotMatch(renderers, /0\.0.*Gap|完成第 1 周诊断/);

assert.match(references, /function renderReferenceChips/);
assert.match(references, /data-reference-id/);
assert.match(references, /function getReferencePanelPayload/);
assert.match(references, /unit: getUnits/);
assert.match(references, /evidence: raw\.scoreHistory/);
assert.match(references, /calibration: raw\.calibrationEvents/);
assert.match(references, /relatedObjects/);
assert.match(references, /function openReferenceTarget/);

assert.match(annotations, /function createJournalDraftMarkdown/);
assert.match(annotations, /定位失效|unresolved/i);
assert.match(annotations, /本机临时阅读标注/);
assert.match(entryJs, /function refreshJournalDraftTextareas/);
assert.match(entryJs, /navigator\.clipboard\?\.writeText/);
assert.match(entryJs, /请手动复制|复制失败/);
assert.doesNotMatch(entryJs, /querySelectorAll\("\[data-section-id\], \[data-note-id\]"\)/);
const setActiveSectionBlock = entryJs.slice(entryJs.indexOf("function setActiveSection"), entryJs.indexOf("function getActiveSectionFromScroll"));
assert.doesNotMatch(setActiveSectionBlock, /setActiveKnowledgeContext/);

assert.match(modules, /function renderModuleSafely/);
assert.doesNotMatch(modules, /learningProgress/);
assert.match(state, /ieltsReader\.ui\.v1/);
assert.match(state, /ieltsReader\.annotations\.v1/);
assert.doesNotMatch(state, /ieltsReader\.tasks\.v1|TASK_STORAGE_KEY/);
assert.match(utils, /function getShortcutLabel/);

assert.match(css, /\.reader-shell/);
assert.match(css, /\.reader-toolbar/);
assert.match(css, /\.reader-sidebar/);
assert.match(css, /\.module-section/);
assert.match(css, /\.note-panel/);
assert.match(css, /\.mobile-note-drawer/);
assert.match(css, /\[data-theme="dark"\]/);
assert.match(css, /\.annotation-toolbar/);
assert.match(css, /@media \(max-width:\s*860px\)/);
assert.doesNotMatch(css, /--reader-glass|--reader-panel-blur|backdrop-filter|-webkit-backdrop-filter/);
assert.match(css, /--reader-paper:\s*#eee9dc/);
assert.match(css, /--reader-surface:\s*#faf7ef/);
assert.match(css, /--reader-red:\s*#a33e35/);
assert.match(css, /\.current-action::before/);
assert.match(css, /\.unit-record::before/);
assert.match(css, /\.sprint-speaking-window/);
assert.match(css, /\.sprint-task-row/);
assert.match(css, /\.sprint-reserve/);
assert.doesNotMatch(css, /radial-gradient|linear-gradient/);
assert.doesNotMatch(css, /\.task-list|\.swimlane|\.dashboard-grid|\.module-progress-summary/);

assert.match(indexHtml, /site\/ielts-reader\.js/);
assert.match(indexHtml, /data-shortcut-label/);
assert.match(indexHtml, /id="note-panel"/);
assert.match(workflow, /npm run build:ielts/);
assert.match(workflow, /npm run test:all/);

assert.equal(data.derived.learningState, data.unitLedger.state);
assert.equal(
  data.derived.currentTrigger,
  data.calibrationEvents.events.find((event) => event.status !== "decided")?.id ?? null,
);
const runtimeUnits = [
  data.unitLedger.activeUnit,
  data.unitLedger.suggestedUnit,
  ...data.unitLedger.queue,
  ...data.unitLedger.settled,
].filter(Boolean);
for (const unit of runtimeUnits) {
  assert.equal(data.references.targets.some((target) => target.id === `unit:${unit.id}`), true);
}
assert.equal(Array.isArray(data.references.targets), true);
assert.equal(Array.isArray(data.build.validationIssues), true);
assert.equal(getSprintDay(data.sprintPlan, "2026-08-09").template, "halfDay");
assert.equal(getSprintDay(data.sprintPlan, "2026-08-09").day, 1);
assert.equal(getSprintDay(data.sprintPlan, "2026-09-06"), null);
const sprintHtml = renderSprintPlan(data);
assert.match(sprintHtml, /口试排程/);
assert.match(sprintHtml, /4\.5 小时/);
assert.match(sprintHtml, /条件加练/);
assert.match(sprintHtml, /8月25–26日/);
assert.doesNotMatch(sprintHtml, /undefined|null/);
assert.equal(formatTarget({ overall: 7.5, perSkillFloor: null }), "总分 7.5 · 单项线待确认");
assert.equal(formatTarget({ overall: 8, perSkillFloor: 7.5 }), "总分 8.0 · 单项 7.5+");

const settledNow = renderNow({
  unitLedger: {
    state: "waiting-evidence",
    activeUnit: null,
    suggestedUnit: null,
    settled: [{ id: "R3" }],
  },
  calibrationEvents: {
    events: [{ id: "two-mocks-available", label: "两次可比模考可用", condition: "等待下一次模考。" }],
  },
  derived: { currentTrigger: "two-mocks-available" },
  scoreHistory: { entries: [{ id: "EV1" }] },
  errorLog: { errors: [] },
  project: { target: { overall: 7.5, perSkillFloor: null } },
});
assert.match(settledNow, /当前没有活动单元/);
assert.match(settledNow, /等待下一份独立证据/);
assert.doesNotMatch(settledNow, /学习尚未开始/);
