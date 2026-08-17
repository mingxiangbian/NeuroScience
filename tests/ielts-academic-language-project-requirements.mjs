import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const exists = (path) => existsSync(new URL(path, import.meta.url));

const requiredFiles = [
  "../projects/language/README.md",
  "../projects/language/ielts-academic/README.md",
  "../projects/language/ielts-academic/plans/event-driven-study-system.md",
  "../projects/language/ielts-academic/plans/unit-ledger.json",
  "../projects/language/ielts-academic/plans/calibration-events.json",
  "../projects/language/ielts-academic/plans/exam-sprint.json",
  "../projects/language/ielts-academic/plans/mock-test-strategy.md",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/README.md",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/8-week-diagnostic-driven-plan.md",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/daily-flexible-training.md",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/checkpoint-rules.md",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/checkpoint-status.json",
  "../projects/language/ielts-academic/plans/archive/legacy-8-week/weekly-review-template.md",
  "../projects/language/ielts-academic/prompts/orchestrator.md",
  "../projects/language/ielts-academic/prompts/run-modes.md",
  "../projects/language/ielts-academic/prompts/interaction-protocol.md",
  "../projects/language/ielts-academic/prompts/output-contract.md",
  "../projects/language/ielts-academic/prompts/calibration-and-validation.md",
  "../projects/language/ielts-academic/prompts/agents/listening-specialist.md",
  "../projects/language/ielts-academic/prompts/agents/reading-specialist.md",
  "../projects/language/ielts-academic/prompts/agents/writing-task-1-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/writing-task-2-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/speaking-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/language-error-analyst.md",
  "../projects/language/ielts-academic/prompts/agents/diagnostic-score-profile-analyst.md",
  "../projects/language/ielts-academic/prompts/agents/study-load-execution-planner.md",
  "../projects/language/ielts-academic/diagnostics/diagnostic-input-template.md",
  "../projects/language/ielts-academic/diagnostics/score-profile-template.md",
  "../projects/language/ielts-academic/diagnostics/score-history-template.md",
  "../projects/language/ielts-academic/diagnostics/speaking-audio-self-assessment.md",
  "../projects/language/ielts-academic/diagnostics/error-log-template.md",
  "../projects/language/ielts-academic/diagnostics/score-profile.json",
  "../projects/language/ielts-academic/diagnostics/score-history.json",
  "../projects/language/ielts-academic/diagnostics/error-log.json",
  "../projects/language/ielts-academic/errors/regression-check-template.md",
  "../projects/language/ielts-academic/validation/output-contract-checklist.md",
  "../projects/language/ielts-academic/validation/dry-run-test-cases.md",
  "../projects/language/ielts-academic/validation/examiner-calibration-checklist.md",
  "../projects/language/ielts-academic/index.html",
  "../projects/language/ielts-academic/scripts/build-ielts-data.mjs",
  "../projects/language/ielts-academic/scripts/build-schema.mjs",
  "../projects/language/ielts-academic/scripts/build-references.mjs",
  "../projects/language/ielts-academic/site/ielts-data.json",
  "../projects/language/ielts-academic/site/ielts-reader.css",
  "../projects/language/ielts-academic/site/ielts-reader.js",
  "../projects/language/ielts-academic/site/reader-annotations.js",
  "../projects/language/ielts-academic/site/reader-modules.js",
  "../projects/language/ielts-academic/site/reader-references.js",
  "../projects/language/ielts-academic/site/reader-renderers.js",
  "../projects/language/ielts-academic/site/reader-state.js",
  "../projects/language/ielts-academic/site/reader-utils.js",
  "../projects/language/ielts-academic/notes/README.md",
  "../projects/language/ielts-academic/notes/speaking/2026-may-august-part-2-topic-clusters.md",
  "../projects/language/ielts-academic/notes/speaking/part-2-knowledge-bank.md",
  "../projects/language/ielts-academic/notes/speaking/part-2-review-bank.md",
  "../projects/language/ielts-academic/notes/writing/task-2-argument-development.md",
  "../projects/language/ielts-academic/journal/README.md",
  "../projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md",
];

for (const path of requiredFiles) assert.equal(exists(path), true, `${path} should exist`);

for (const path of [
  "../projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md",
  "../projects/language/ielts-academic/plans/daily-flexible-training.md",
  "../projects/language/ielts-academic/plans/checkpoint-rules.md",
  "../projects/language/ielts-academic/plans/checkpoint-status.json",
  "../projects/language/ielts-academic/plans/weekly-review-template.md",
  "../projects/language/ielts-academic/site/reader-tasks.js",
]) {
  assert.equal(exists(path), false, `${path} should exit the active runtime`);
}

const languageReadme = read("../projects/language/README.md");
const projectReadme = read("../projects/language/ielts-academic/README.md");
const eventSystem = read("../projects/language/ielts-academic/plans/event-driven-study-system.md");
const unitLedger = JSON.parse(read("../projects/language/ielts-academic/plans/unit-ledger.json"));
const calibrationEvents = JSON.parse(read("../projects/language/ielts-academic/plans/calibration-events.json"));
const sprintPlan = JSON.parse(read("../projects/language/ielts-academic/plans/exam-sprint.json"));
const scoreProfile = JSON.parse(read("../projects/language/ielts-academic/diagnostics/score-profile.json"));
const scoreHistory = JSON.parse(read("../projects/language/ielts-academic/diagnostics/score-history.json"));
const errorLog = JSON.parse(read("../projects/language/ielts-academic/diagnostics/error-log.json"));
const orchestrator = read("../projects/language/ielts-academic/prompts/orchestrator.md");
const outputContract = read("../projects/language/ielts-academic/prompts/output-contract.md");
const runModes = read("../projects/language/ielts-academic/prompts/run-modes.md");
const executionPlanner = read("../projects/language/ielts-academic/prompts/agents/study-load-execution-planner.md");
const calibration = read("../projects/language/ielts-academic/prompts/calibration-and-validation.md");
const speaking = read("../projects/language/ielts-academic/prompts/agents/speaking-examiner.md");
const dryRuns = read("../projects/language/ielts-academic/validation/dry-run-test-cases.md");
const part2Topics = read("../projects/language/ielts-academic/notes/speaking/2026-may-august-part-2-topic-clusters.md");
const part2Review = read("../projects/language/ielts-academic/notes/speaking/part-2-review-bank.md");
const projectIndex = read("../projects/language/ielts-academic/index.html");
const siteJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const renderers = read("../projects/language/ielts-academic/site/reader-renderers.js");
const references = read("../projects/language/ielts-academic/site/reader-references.js");
const readerState = read("../projects/language/ielts-academic/site/reader-state.js");
const buildScript = read("../projects/language/ielts-academic/scripts/build-ielts-data.mjs");
const buildSchema = read("../projects/language/ielts-academic/scripts/build-schema.mjs");
const buildReferences = read("../projects/language/ielts-academic/scripts/build-references.mjs");
const manifest = JSON.parse(read("../projects/manifest.json"));

assert.match(languageReadme, /IELTS Academic/);
assert.match(projectReadme, /Overall 7\.5/);
assert.match(projectReadme, /2026-08-22 to 2026-09-05/);
assert.match(projectReadme, /base day is 225 focused minutes/);
assert.match(projectReadme, /event-driven-study-system\.md/);
assert.doesNotMatch(projectReadme, /adaptive 8-week plan|daily flexible training|checkpoint-status\.json/i);

assert.match(eventSystem, /同时最多一个活动单元/);
assert.match(eventSystem, /连续 3 个独立新样本/);
assert.match(eventSystem, /当前学习状态只以 `unit-ledger\.json` 为准/);
assert.match(eventSystem, /普通日基础量为 225 分钟/);
assert.match(eventSystem, /每天先完成 P0 口语/);
assert.match(eventSystem, /Reading 作为 P2/);
assert.match(eventSystem, /口试前后 48 小时/);
assert.equal(unitLedger.schemaVersion, 2);
assert.equal(unitLedger.activeUnit === null || unitLedger.activeUnit.status === "active", true);
assert.equal(unitLedger.suggestedUnit === null || unitLedger.suggestedUnit.status === "suggested", true);
assert.equal(unitLedger.state === "active", unitLedger.activeUnit !== null);
assert.equal(Array.isArray(unitLedger.queue), true);
assert.equal(Array.isArray(unitLedger.settled), true);
const runtimeUnits = [
  unitLedger.activeUnit,
  unitLedger.suggestedUnit,
  ...unitLedger.queue,
  ...unitLedger.settled,
].filter(Boolean);
assert.equal(runtimeUnits.some((unit) => unit.id === "M1"), true);
assert.equal(calibrationEvents.schemaVersion, 2);
assert.deepEqual(calibrationEvents.events.map((event) => event.id), [
  "baseline-complete",
  "error-set-changed",
  "two-mocks-available",
  "regression-detected",
  "external-deadline-changed",
  "target-reached",
]);

assert.equal(scoreProfile.target.overall, 7.5);
assert.equal(scoreProfile.target.perSkillFloor, 6.5);
assert.equal(Object.hasOwn(scoreProfile.target, "timelineWeeks"), false);
assert.equal(Array.isArray(scoreHistory.entries), true);
assert.equal(scoreHistory.entries.some((entry) => entry.id === "2026-07-23-c19-test-1-baseline"), true);
assert.equal(
  scoreHistory.entries.some(
    (entry) => entry.id === "2026-08-11-c21-test-1-reading-passage-2" && /13\/13/.test(entry.notes),
  ),
  true,
);
assert.equal(Array.isArray(errorLog.errors), true);
assert.equal(
  errorLog.errors.some(
    (error) => error.id === "E008" && error.status === "improving" && error.consecutiveCleanSamples === 1,
  ),
  true,
);
assert.equal(sprintPlan.exam.speakingDate, null);
assert.equal(sprintPlan.exam.dayOneAvailableMinutes, 270);
assert.equal(sprintPlan.speakingContingency.readinessDeadline, "2026-08-21");
assert.equal(sprintPlan.prioritySystem.effectiveFrom, "2026-08-15");
assert.deepEqual(sprintPlan.prioritySystem.levels.map((level) => level.id), ["P0", "P1", "P2", "P3"]);
assert.match(sprintPlan.prioritySystem.carryPolicy, /不与原计划叠加/);
assert.equal(sprintPlan.dailyBudget.standardMinutes, 225);
assert.equal(sprintPlan.days.length, 20);
assert.equal(sprintPlan.days[0].template, "halfDay");
assert.equal(sprintPlan.dailyBudget.templateMinutes.mockSpeaking, 315);
assert.equal(sprintPlan.days.find((day) => day.day === 3).template, "mockSpeaking");
assert.match(sprintPlan.days.find((day) => day.day === 3).tasks.speaking, /8 道未见 Part 1/);
assert.equal(sprintPlan.days.find((day) => day.day === 6).date, "2026-08-15");
assert.equal(sprintPlan.days.find((day) => day.day === 6).template, "rollingStandard");
assert.match(sprintPlan.days.find((day) => day.day === 6).tasks.speaking, /Part 2/);
assert.equal(sprintPlan.days.find((day) => day.day === 12).template, "oralPriority");

assert.match(orchestrator, /Do not invent a personal weakness profile/);
assert.match(orchestrator, /Keep at most one active learning unit/);
assert.match(orchestrator, /Do not create a fixed week plan/);
assert.match(outputContract, /Settlement criteria/);
assert.match(outputContract, /Duration is required only for diagnostic units, mock units/);
assert.doesNotMatch(outputContract, /Adaptive 8-week plan|Weekly time allocation|Daily training tasks/);
assert.match(runModes, /only mode that supports real agent independence/);
assert.match(executionPlanner, /one executable, evidence-settled learning unit/);
assert.match(calibration, /LLM-generated band estimate is advisory/);
assert.match(speaking, /transcript alone cannot verify pronunciation/);
assert.match(dryRuns, /Fixed-error evidence dry run/);
assert.match(dryRuns, /activeUnit: null/);

const extractPart2Ids = (text) => [...new Set(text.match(/\b(?:PE|EV|OB|PL)\d{2}\b/g) ?? [])].sort();
const topicIds = extractPart2Ids(part2Topics);
const reviewIds = extractPart2Ids(part2Review);
assert.equal(topicIds.length, 55);
assert.deepEqual(reviewIds, topicIds);
assert.equal(part2Review.match(/^## R\d{2} -/gm)?.length, 23);
assert.match(part2Review, /PE11（应急卡）/);
assert.match(part2Review, /尚未完成两分钟口述验证/);
assert.match(part2Review, /persistent internal affective state/);
assert.match(part2Review, /完整循迹、避障和 PID 最终测试没有完全成功/);
assert.doesNotMatch(part2Review, /待补|Details to confirm later|Status: missing/i);
assert.doesNotMatch(part2Topics, /补齐 6 个事实缺口|帮助妹妹选大学/);

assert.match(projectIndex, /data-page="ielts-academic-reader"/);
assert.match(projectIndex, /id="reader-shell"/);
assert.match(projectIndex, /id="global-search"/);
assert.match(projectIndex, /id="note-panel"/);
assert.match(projectIndex, /data-source="site\/ielts-data\.json"/);

for (const title of ["现在", "单元", "错误", "证据", "结算", "档案", "系统"]) {
  assert.match(siteJs, new RegExp(`title: "${title}"`), `reader should expose ${title}`);
}
assert.doesNotMatch(siteJs, /title: "总览"|title: "8周计划"|title: "笔记"|title: "日志"|title: "提示词库"|title: "质量验证"/);
assert.doesNotMatch(siteJs, /reader-tasks|learningProgress|overallLearningProgress|renderProgressSummary/);
assert.doesNotMatch(renderers, /renderSwimlane|renderDailyTasks|renderCheckpointMilestones|WEEKS/);
assert.match(renderers, /function renderNow/);
assert.match(renderers, /function renderUnits/);
assert.match(renderers, /function renderEvidence/);
assert.match(renderers, /function renderSettlements/);
assert.match(references, /unit: getUnits/);
assert.match(references, /calibration:/);
assert.doesNotMatch(readerState, /TASK_STORAGE_KEY|loadTaskState|saveTaskState/);

assert.match(buildScript, /plans\/unit-ledger\.json/);
assert.match(buildScript, /plans\/calibration-events\.json/);
assert.match(buildScript, /plans\/exam-sprint\.json/);
assert.doesNotMatch(buildScript, /checkpoint-status\.json|checkpoints/);
assert.match(buildSchema, /insufficient_fix_evidence/);
assert.match(buildSchema, /deprecated_field/);
assert.match(buildSchema, /conditionalReserve/);
assert.match(buildReferences, /type, label, moduleId/);

const ieltsProject = manifest.find((project) => project.id === "ielts-academic");
assert.ok(ieltsProject);
assert.equal(ieltsProject.folder, "language/ielts-academic/");
assert.equal(ieltsProject.status, "active");
