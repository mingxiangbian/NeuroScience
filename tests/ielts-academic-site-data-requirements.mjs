import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const buildScriptUrl = new URL("../projects/language/ielts-academic/scripts/build-ielts-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/language/ielts-academic/site/ielts-data.json", import.meta.url);
const jsUrl = new URL("../projects/language/ielts-academic/site/ielts-reader.js", import.meta.url);
const readerModuleUrls = [
  "../projects/language/ielts-academic/site/reader-modules.js",
  "../projects/language/ielts-academic/site/reader-state.js",
  "../projects/language/ielts-academic/site/reader-tasks.js",
  "../projects/language/ielts-academic/site/reader-utils.js",
].map((path) => new URL(path, import.meta.url));

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const data = JSON.parse(readFileSync(dataUrl, "utf8"));
const readerJs = readFileSync(jsUrl, "utf8");
const readerJsBundle = [
  readerJs,
  ...readerModuleUrls.map((url) => readFileSync(url, "utf8")),
].join("\n");

assert.equal(data.project.id, "ielts-academic");
assert.equal(data.project.target.overall, 8);
assert.equal(data.project.target.perSkillFloor, 7.5);
assert.equal(data.build.contentUpdatedAt, data.scoreProfile.lastUpdated);
assert.match(data.build.generatedAt, /^\d{4}-\d{2}-\d{2}$/);
assert.equal(Array.isArray(data.build.validationIssues), true);
assert.deepEqual(data.build.validationIssues.filter((issue) => issue.severity === "fatal"), []);
assert.ok(data.references);
assert.equal(Array.isArray(data.references.targets), true);
assert.ok(data.references.backlinks);
assert.equal(
  data.references.targets.some((target) => target.id === "note:writing/task-2-argument-development"),
  true,
);
assert.equal(
  data.references.targets.some((target) => target.id === "error:E001"),
  true,
);
assert.equal(
  data.references.backlinks["note:writing/task-2-argument-development"].some((link) => link.id.startsWith("journal:")),
  true,
);
assert.equal(
  data.notes.every((note) => typeof note.html === "string" && note.html.length > 0),
  true,
);
assert.equal(
  data.promptLibrary.every((prompt) => typeof prompt.html === "string" && prompt.html.length > 0),
  true,
);
assert.equal(
  data.validation.every((check) => typeof check.html === "string" && check.html.length > 0),
  true,
);
assert.equal(Array.isArray(data.sourceLinks), true);
assert.ok(data.scoreProfile);
assert.equal(Array.isArray(data.scoreProfile.skills), true);
assert.equal(Array.isArray(data.scoreHistory.entries), true);
assert.equal(Array.isArray(data.errorLog.errors), true);
assert.deepEqual(
  data.checkpoints.checkpoints.map((checkpoint) => checkpoint.week),
  [2, 4, 6, 8],
);
assert.equal(Array.isArray(data.notes), true);
assert.equal(
  data.notes.some((note) => note.id === "writing/task-2-argument-development"),
  true,
);
assert.equal(Array.isArray(data.journal), true);
assert.equal(
  data.journal.some((entry) => entry.path.endsWith("2026-07-06-initial-setup.md")),
  true,
);
assert.equal(Array.isArray(data.promptLibrary), true);
assert.equal(
  data.promptLibrary.some((prompt) => prompt.id === "prompts/orchestrator"),
  true,
);
assert.equal(
  data.promptLibrary.some((prompt) => prompt.id === "prompts/agents/writing-task-2-examiner"),
  true,
);
assert.equal(Array.isArray(data.validation), true);
assert.equal(
  data.validation.some((doc) => doc.id === "validation/dry-run-test-cases"),
  true,
);

const allowedStatuses = new Set(["active", "improving", "fixed", "regressed"]);
const allowedImpacts = new Set(["high", "medium", "low"]);
const errorIds = new Set(data.errorLog.errors.map((error) => error.id));
const noteIds = new Set(data.notes.map((note) => note.id));

for (const error of data.errorLog.errors) {
  assert.equal(allowedStatuses.has(error.status), true, `${error.id} should use an allowed status`);
  assert.equal(allowedImpacts.has(error.impact), true, `${error.id} should use an allowed impact`);
}

for (const note of data.notes) {
  for (const errorId of note.relatedErrors) {
    assert.equal(errorIds.has(errorId), true, `${note.id} should reference existing error ${errorId}`);
  }
}

for (const entry of data.journal) {
  for (const errorId of entry.relatedErrors) {
    assert.equal(errorIds.has(errorId), true, `${entry.id} should reference existing error ${errorId}`);
  }

  for (const noteId of entry.relatedNotes) {
    assert.equal(noteIds.has(noteId), true, `${entry.id} should reference existing note ${noteId}`);
  }
}

assert.deepEqual(data.build.referenceIssues, []);
assert.match(readerJs, /from "\.\/reader-state\.js"/, "reader entrypoint should import local state helpers");
assert.doesNotMatch(readerJsBundle, /githubToken|Authorization|contents\/|repos\/|fetch\("\/api/i);
assert.match(readerJsBundle, /ieltsReader\.annotations\.v1/, "reader JS should allow local annotation state only under the IELTS annotation key");
assert.match(readerJsBundle, /ieltsReader\.tasks\.v1/, "reader JS should allow local task state only under the IELTS task key");
assert.doesNotMatch(readerJsBundle, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint|localStorage\.setItem\(".*journal|localStorage\.setItem\(".*notes/i);
assert.doesNotMatch(readerJsBundle, /method:\s*["']POST["']|method:\s*["']PUT["']|method:\s*["']PATCH["']|method:\s*["']DELETE["']/i);
