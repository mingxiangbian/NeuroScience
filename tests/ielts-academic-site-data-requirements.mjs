import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const buildScriptUrl = new URL("../projects/language/ielts-academic/scripts/build-ielts-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/language/ielts-academic/site/ielts-data.json", import.meta.url);
const readerPaths = [
  "../projects/language/ielts-academic/site/ielts-reader.js",
  "../projects/language/ielts-academic/site/reader-annotations.js",
  "../projects/language/ielts-academic/site/reader-modules.js",
  "../projects/language/ielts-academic/site/reader-references.js",
  "../projects/language/ielts-academic/site/reader-renderers.js",
  "../projects/language/ielts-academic/site/reader-state.js",
  "../projects/language/ielts-academic/site/reader-utils.js",
];

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const data = JSON.parse(readFileSync(dataUrl, "utf8"));
const readerJsBundle = readerPaths.map((path) => readFileSync(new URL(path, import.meta.url), "utf8")).join("\n");

assert.equal(data.project.id, "ielts-academic");
assert.deepEqual(data.project.target, { overall: 7.5, perSkillFloor: 6.5 });
assert.equal(data.build.contentUpdatedAt, data.scoreProfile.lastUpdated);
assert.match(data.build.generatedAt, /^\d{4}-\d{2}-\d{2}$/);
assert.deepEqual(data.build.validationIssues, []);
assert.deepEqual(data.build.referenceIssues, []);

assert.equal("checkpoints" in data, false);
assert.equal("timelineWeeks" in data.project.target, false);
assert.equal(data.scoreProfile.schemaVersion, 2);
assert.equal(Array.isArray(data.scoreProfile.skills), true);
assert.equal(Array.isArray(data.scoreHistory.entries), true);
assert.equal(data.scoreHistory.entries.some((entry) => entry.id === "2026-07-23-c19-test-1-baseline"), true);
assert.equal(Array.isArray(data.errorLog.errors), true);
assert.equal(data.errorLog.errors.some((error) => error.id === "E015" && error.skill === "speaking"), true);
assert.equal(data.scoreHistory.entries.some((entry) => entry.id === "2026-08-09-planning-baseline"), true);

assert.equal(data.sprintPlan.schemaVersion, 1);
assert.equal(data.sprintPlan.exam.date, "2026-08-29");
assert.equal(data.sprintPlan.exam.speakingDate, null);
assert.deepEqual(data.sprintPlan.exam.usualSpeakingWindow, {
  startDate: "2026-08-22",
  endDate: "2026-09-05",
  source: "2026-08-09 NEEA registration email",
  boundary: "邮件说明口试通常安排在笔试前后 7 天，特殊情况下可能超出该区间；具体时间以准考证为准。",
});
assert.equal(data.sprintPlan.speakingContingency.readinessDeadline, "2026-08-20");
assert.equal(data.sprintPlan.days.length, 20);
assert.equal(data.sprintPlan.days[0].template, "halfDay");
assert.equal(data.sprintPlan.dailyBudget.templateMinutes.halfDay, 270);
assert.equal(data.sprintPlan.days.find((day) => day.day === 12).template, "mock");
assert.equal(data.sprintPlan.checkpoints.find((checkpoint) => checkpoint.id === "CP4").label.includes("8月25–26日"), true);

assert.equal(data.unitLedger.schemaVersion, 2);
assert.equal(data.unitLedger.activeUnit === null || data.unitLedger.activeUnit.status === "active", true);
assert.equal(data.unitLedger.suggestedUnit === null || data.unitLedger.suggestedUnit.status === "suggested", true);
assert.equal(data.unitLedger.state === "active", data.unitLedger.activeUnit !== null);
assert.equal(Array.isArray(data.unitLedger.queue), true);
assert.equal(Array.isArray(data.unitLedger.settled), true);
const runtimeUnits = [
  data.unitLedger.activeUnit,
  data.unitLedger.suggestedUnit,
  ...data.unitLedger.queue,
  ...data.unitLedger.settled,
].filter(Boolean);
assert.equal(runtimeUnits.some((unit) => unit.id === "M1"), true);

assert.equal(data.calibrationEvents.events.length, 6);
assert.equal(data.calibrationEvents.events.every((event) => ["waiting", "triggered", "decided"].includes(event.status)), true);
const expectedErrorCounts = { active: 0, improving: 0, fixed: 0, regressed: 0 };
for (const error of data.errorLog.errors) expectedErrorCounts[error.status] += 1;
assert.equal(data.derived.learningState, data.unitLedger.state);
assert.deepEqual(data.derived.errorCounts, expectedErrorCounts);
assert.equal(data.derived.settledUnitCount, data.unitLedger.settled.length);
assert.equal(data.derived.evidenceEventCount, data.scoreHistory.entries.length);
assert.equal(
  data.derived.currentTrigger,
  data.calibrationEvents.events.find((event) => event.status !== "decided")?.id ?? null,
);

assert.equal(Array.isArray(data.references.targets), true);
assert.ok(data.references.backlinks);
assert.equal(data.references.targets.some((target) => target.id === "unit:M1" && target.moduleId === "units"), true);
assert.equal(data.references.targets.some((target) => target.id === "calibration:baseline-complete" && target.moduleId === "settlements"), true);
assert.equal(data.references.targets.some((target) => target.id === "note:writing/task-2-argument-development" && target.moduleId === "archive"), true);
for (const error of data.errorLog.errors) {
  assert.equal(data.references.targets.some((target) => target.id === `error:${error.id}`), true);
}
assert.equal(data.references.backlinks["note:writing/task-2-argument-development"].some((link) => link.id.startsWith("journal:")), true);

assert.equal(data.notes.every((note) => typeof note.html === "string" && note.html.length > 0), true);
assert.equal(data.promptLibrary.every((prompt) => typeof prompt.html === "string" && prompt.html.length > 0), true);
assert.equal(data.validation.every((check) => typeof check.html === "string" && check.html.length > 0), true);
assert.equal(data.promptLibrary.some((prompt) => prompt.id === "prompts/orchestrator"), true);
assert.equal(data.promptLibrary.some((prompt) => /Keep at most one active learning unit/.test(prompt.text)), true);
assert.equal(data.validation.some((doc) => doc.id === "validation/dry-run-test-cases"), true);

const errorIds = new Set(data.errorLog.errors.map((error) => error.id));
const noteIds = new Set(data.notes.map((note) => note.id));
for (const note of data.notes) {
  for (const errorId of note.relatedErrors) assert.equal(errorIds.has(errorId), true);
}
for (const entry of data.journal) {
  for (const errorId of entry.relatedErrors) assert.equal(errorIds.has(errorId), true);
  for (const noteId of entry.relatedNotes) assert.equal(noteIds.has(noteId), true);
}

assert.doesNotMatch(readerJsBundle, /githubToken|Authorization|contents\/|repos\/|fetch\("\/api/i);
assert.match(readerJsBundle, /ieltsReader\.annotations\.v1/);
assert.match(readerJsBundle, /ieltsReader\.ui\.v1/);
assert.doesNotMatch(readerJsBundle, /ieltsReader\.tasks\.v1|data-task-id|reader-tasks/);
assert.doesNotMatch(readerJsBundle, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*unit|localStorage\.setItem\(".*calibration/i);
assert.doesNotMatch(readerJsBundle, /method:\s*["']POST["']|method:\s*["']PUT["']|method:\s*["']PATCH["']|method:\s*["']DELETE["']/i);
