import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const root = new URL("../projects/language/ielts-academic/", import.meta.url);
const languageReadmeUrl = new URL("../projects/language/README.md", import.meta.url);

const requiredFiles = [
  "../projects/language/README.md",
  "../projects/language/ielts-academic/README.md",
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
  "../projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md",
  "../projects/language/ielts-academic/plans/daily-flexible-training.md",
  "../projects/language/ielts-academic/plans/checkpoint-rules.md",
  "../projects/language/ielts-academic/plans/weekly-review-template.md",
  "../projects/language/ielts-academic/plans/mock-test-strategy.md",
  "../projects/language/ielts-academic/errors/error-priority-map.md",
  "../projects/language/ielts-academic/errors/band-6-to-8-language-map.md",
  "../projects/language/ielts-academic/errors/regression-check-template.md",
  "../projects/language/ielts-academic/validation/output-contract-checklist.md",
  "../projects/language/ielts-academic/validation/dry-run-test-cases.md",
  "../projects/language/ielts-academic/validation/examiner-calibration-checklist.md",
];

for (const path of requiredFiles) {
  assert.equal(existsSync(new URL(path, import.meta.url)), true, `${path} should exist`);
}

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const languageReadme = read("../projects/language/README.md");
const projectReadme = read("../projects/language/ielts-academic/README.md");
const orchestrator = read("../projects/language/ielts-academic/prompts/orchestrator.md");
const runModes = read("../projects/language/ielts-academic/prompts/run-modes.md");
const outputContract = read("../projects/language/ielts-academic/prompts/output-contract.md");
const calibration = read("../projects/language/ielts-academic/prompts/calibration-and-validation.md");
const speaking = read("../projects/language/ielts-academic/prompts/agents/speaking-examiner.md");
const scoreProfile = read("../projects/language/ielts-academic/diagnostics/score-profile-template.md");
const eightWeekPlan = read("../projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md");
const checkpoints = read("../projects/language/ielts-academic/plans/checkpoint-rules.md");
const regression = read("../projects/language/ielts-academic/errors/regression-check-template.md");
const dryRuns = read("../projects/language/ielts-academic/validation/dry-run-test-cases.md");

assert.match(languageReadme, /IELTS Academic/, "language README should link to IELTS Academic");
assert.match(projectReadme, /Overall 8\.0/, "project README should state the aggressive overall target");
assert.match(projectReadme, /each skill 7\.5\+/, "project README should state the per-skill floor");
assert.match(projectReadme, /manual multi-session mode/, "project README should explain independent run mode");
assert.match(projectReadme, /single-session simulation mode/, "project README should explain simulation mode");

assert.match(orchestrator, /Do not invent a personal weakness profile/, "orchestrator should refuse unsupported diagnosis");
assert.match(orchestrator, /Run mode used and independence level/, "orchestrator should report run mode and independence level");
assert.match(orchestrator, /duration, material type, expected output, and review method/, "orchestrator should enforce task fields");

assert.match(runModes, /This is the only mode that supports real agent independence/, "run modes should define true independence");
assert.match(runModes, /not independent/, "run modes should label single-session simulation as not independent");

assert.match(outputContract, /Score confidence and unverified dimensions/, "output contract should require confidence and unverified dimensions");
assert.match(outputContract, /Weekly time allocation by skill/, "output contract should require adaptive allocation");
assert.match(outputContract, /Regression checks/, "output contract should require regression checks");

assert.match(calibration, /https:\/\/ielts\.org\/take-a-test\/your-results\/ielts-scoring-in-detail/, "calibration should cite IELTS scoring detail");
assert.match(calibration, /LLM-generated band estimate is advisory/, "calibration should mark LLM scores as advisory");
assert.match(calibration, /more than 0\.5 band/, "calibration should define examiner drift threshold");

assert.match(speaking, /transcript alone cannot verify pronunciation/, "speaking examiner should state transcript limitation");
assert.match(speaking, /score range with confidence/, "speaking examiner should avoid exact transcript-only scores");

assert.match(scoreProfile, /Evidence basis/, "score profile should record evidence basis");
assert.match(scoreProfile, /Confidence/, "score profile should record confidence");
assert.match(scoreProfile, /Unverified dimensions/, "score profile should record unverified dimensions");

assert.match(eightWeekPlan, /diagnosis-weighted/, "8-week plan should be adaptive");
assert.match(eightWeekPlan, /Critical gap/, "8-week plan should define critical gaps");
assert.match(eightWeekPlan, /Maintenance skill/, "8-week plan should preserve maintenance allocation");

assert.match(checkpoints, /Week 2 feasibility check/, "checkpoint rules should include Week 2");
assert.match(checkpoints, /Week 6 correction checkpoint/, "checkpoint rules should include Week 6");
assert.match(checkpoints, /Week 8 readiness check/, "checkpoint rules should include Week 8");
assert.match(checkpoints, /6 focused hours per week/, "checkpoint rules should include the workload floor");

assert.match(regression, /fixed repeatedly/, "regression template should track repeated fixes");
assert.match(regression, /regressed/, "regression template should track regressions");

assert.match(dryRuns, /Missing-information dry run/, "dry runs should test missing input behavior");
assert.match(dryRuns, /Partial-input dry run/, "dry runs should test partial input handling");
assert.match(dryRuns, /Low-workload dry run/, "dry runs should test workload feasibility");
assert.match(dryRuns, /Single-session mode dry run/, "dry runs should test simulation labeling");

assert.equal(root.pathname.endsWith("/projects/language/ielts-academic/"), true);
assert.equal(languageReadmeUrl.pathname.endsWith("/projects/language/README.md"), true);
