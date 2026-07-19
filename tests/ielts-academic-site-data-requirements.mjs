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
assert.deepEqual(data.project.target, { overall: 7.5, perSkillFloor: null });
assert.equal(data.build.contentUpdatedAt, data.scoreProfile.lastUpdated);
assert.match(data.build.generatedAt, /^\d{4}-\d{2}-\d{2}$/);
assert.deepEqual(data.build.validationIssues, []);
assert.deepEqual(data.build.referenceIssues, []);

assert.equal("checkpoints" in data, false);
assert.equal("timelineWeeks" in data.project.target, false);
assert.equal(data.scoreProfile.schemaVersion, 2);
assert.equal(data.scoreProfile.state, "not-started");
assert.equal(data.scoreProfile.currentEstimate.overall, null);
assert.equal(Array.isArray(data.scoreProfile.skills), true);
assert.deepEqual(data.scoreHistory.entries, []);
assert.deepEqual(data.errorLog.errors, []);

assert.equal(data.unitLedger.schemaVersion, 2);
assert.equal(data.unitLedger.activeUnit, null);
assert.equal(data.unitLedger.suggestedUnit.id, "D1");
assert.equal(data.unitLedger.suggestedUnit.status, "suggested");
assert.equal(data.unitLedger.suggestedUnit.settlementCriteria.length, 3);
assert.deepEqual(data.unitLedger.queue, []);
assert.deepEqual(data.unitLedger.settled, []);

assert.equal(data.calibrationEvents.events.length, 6);
assert.equal(data.calibrationEvents.events.every((event) => event.status === "waiting"), true);
assert.deepEqual(data.derived, {
  learningState: "not-started",
  errorCounts: { active: 0, improving: 0, fixed: 0, regressed: 0 },
  settledUnitCount: 0,
  evidenceEventCount: 0,
  currentTrigger: "baseline-complete",
});

assert.equal(Array.isArray(data.references.targets), true);
assert.ok(data.references.backlinks);
assert.equal(data.references.targets.some((target) => target.id === "unit:D1" && target.moduleId === "units"), true);
assert.equal(data.references.targets.some((target) => target.id === "calibration:baseline-complete" && target.moduleId === "settlements"), true);
assert.equal(data.references.targets.some((target) => target.id === "note:writing/task-2-argument-development" && target.moduleId === "archive"), true);
assert.equal(data.references.targets.some((target) => target.id === "error:E001"), false);
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
