import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const buildScriptUrl = new URL("../projects/language/ielts-academic/scripts/build-ielts-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/language/ielts-academic/site/ielts-data.json", import.meta.url);
const jsUrl = new URL("../projects/language/ielts-academic/site/ielts-reader.js", import.meta.url);

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const data = JSON.parse(readFileSync(dataUrl, "utf8"));
const readerJs = readFileSync(jsUrl, "utf8");

assert.equal(data.project.id, "ielts-academic");
assert.equal(data.project.target.overall, 8);
assert.equal(data.project.target.perSkillFloor, 7.5);
assert.equal(
  data.build.generatedAt,
  data.scoreProfile.lastUpdated,
  "generated site data should be stable across repeated builds",
);
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
  data.promptLibrary.some((prompt) => prompt.id === "orchestrator"),
  true,
);
assert.equal(
  data.promptLibrary.some((prompt) => prompt.id === "agents/writing-task-2-examiner"),
  true,
);
assert.equal(Array.isArray(data.validation), true);
assert.equal(
  data.validation.some((doc) => doc.id === "dry-run-test-cases"),
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
assert.doesNotMatch(readerJs, /githubToken|Authorization|contents\/|repos\/|fetch\("\/api/i);
assert.match(readerJs, /ieltsReader\.annotations\.v1/, "reader JS should allow local annotation state only under the IELTS annotation key");
assert.match(readerJs, /ieltsReader\.tasks\.v1/, "reader JS should allow local task state only under the IELTS task key");
assert.doesNotMatch(readerJs, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint|localStorage\.setItem\(".*journal|localStorage\.setItem\(".*notes/i);
assert.doesNotMatch(readerJs, /method:\s*["']POST["']|method:\s*["']PUT["']|method:\s*["']PATCH["']|method:\s*["']DELETE["']/i);
