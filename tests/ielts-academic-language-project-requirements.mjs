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
  "../projects/language/ielts-academic/index.html",
  "../projects/language/ielts-academic/scripts/build-ielts-data.mjs",
  "../projects/language/ielts-academic/site/ielts-data.json",
  "../projects/language/ielts-academic/site/ielts-reader.css",
  "../projects/language/ielts-academic/site/ielts-reader.js",
  "../projects/language/ielts-academic/site/reader-modules.js",
  "../projects/language/ielts-academic/site/reader-references.js",
  "../projects/language/ielts-academic/site/reader-renderers.js",
  "../projects/language/ielts-academic/site/reader-state.js",
  "../projects/language/ielts-academic/site/reader-tasks.js",
  "../projects/language/ielts-academic/site/reader-utils.js",
  "../projects/language/ielts-academic/diagnostics/score-profile.json",
  "../projects/language/ielts-academic/diagnostics/score-history.json",
  "../projects/language/ielts-academic/diagnostics/error-log.json",
  "../projects/language/ielts-academic/plans/checkpoint-status.json",
  "../projects/language/ielts-academic/notes/README.md",
  "../projects/language/ielts-academic/notes/listening/.gitkeep",
  "../projects/language/ielts-academic/notes/reading/.gitkeep",
  "../projects/language/ielts-academic/notes/writing/task-2-argument-development.md",
  "../projects/language/ielts-academic/notes/speaking/.gitkeep",
  "../projects/language/ielts-academic/notes/vocabulary/.gitkeep",
  "../projects/language/ielts-academic/notes/grammar/.gitkeep",
  "../projects/language/ielts-academic/journal/README.md",
  "../projects/language/ielts-academic/journal/entries/2026-07-06-initial-setup.md",
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
const projectIndex = read("../projects/language/ielts-academic/index.html");
const siteJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const readerModulesJs = read("../projects/language/ielts-academic/site/reader-modules.js");
const readerReferencesJs = read("../projects/language/ielts-academic/site/reader-references.js");
const readerRenderersJs = read("../projects/language/ielts-academic/site/reader-renderers.js");
const readerStateJs = read("../projects/language/ielts-academic/site/reader-state.js");
const readerTasksJs = read("../projects/language/ielts-academic/site/reader-tasks.js");
const readerUtilsJs = read("../projects/language/ielts-academic/site/reader-utils.js");
const readerJsBundle = [siteJs, readerModulesJs, readerReferencesJs, readerRenderersJs, readerStateJs, readerTasksJs, readerUtilsJs].join("\n");
const siteCss = read("../projects/language/ielts-academic/site/ielts-reader.css");
const buildScript = read("../projects/language/ielts-academic/scripts/build-ielts-data.mjs");
const buildSources = read("../projects/language/ielts-academic/scripts/build-sources.mjs");
const buildSchema = read("../projects/language/ielts-academic/scripts/build-schema.mjs");
const buildReferences = read("../projects/language/ielts-academic/scripts/build-references.mjs");
const buildMarkdown = read("../projects/language/ielts-academic/scripts/build-markdown.mjs");
const manifest = JSON.parse(read("../projects/manifest.json"));
const notesReadme = read("../projects/language/ielts-academic/notes/README.md");
const journalReadme = read("../projects/language/ielts-academic/journal/README.md");

assert.match(languageReadme, /IELTS Academic/, "language README should link to IELTS Academic");
assert.match(projectReadme, /Overall 8\.0/, "project README should state the aggressive overall target");
assert.match(projectReadme, /each skill 7\.5\+/, "project README should state the per-skill floor");
assert.match(projectReadme, /manual multi-session mode/, "project README should explain independent run mode");
assert.match(projectReadme, /single-session simulation mode/, "project README should explain simulation mode");
assert.match(projectReadme, /Static Reader/, "project README should describe the v2 static reader workflow");
assert.match(projectReadme, /GitHub Pages/, "project README should mention GitHub Pages launch guidance");
assert.match(projectReadme, /local static server/, "project README should mention local static server launch guidance");
assert.match(projectReadme, /site\/ielts-data\.json/, "project README should mention the static reader data file");
assert.match(projectReadme, /notes\//, "project README should link to notes");
assert.match(projectReadme, /journal\//, "project README should link to journal");
assert.match(languageReadme, /ielts-academic\/index\.html/, "language README should link to the IELTS static reader");

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

assert.match(projectIndex, /data-page="ielts-academic-reader"/, "IELTS project should expose a dedicated reader page");
assert.match(projectIndex, /data-theme="light"/, "IELTS reader should start with the light reader theme");
assert.match(projectIndex, /site\/ielts-reader\.css/, "IELTS reader should load dedicated CSS");
assert.match(projectIndex, /site\/ielts-reader\.js/, "IELTS reader should load dedicated JS");
assert.match(projectIndex, /id="reader-shell"/, "IELTS reader should use the Foundations-style reader shell");
assert.match(projectIndex, /id="reader-toolbar"/, "IELTS reader should include a top toolbar");
assert.match(projectIndex, /id="global-search"/, "IELTS reader should include global search");
assert.match(projectIndex, /id="module-directory"/, "IELTS reader should include a module directory");
assert.match(projectIndex, /id="section-rail"/, "IELTS reader should include a section rail");
assert.match(projectIndex, /id="module-header"/, "IELTS reader should include a module header");
assert.match(projectIndex, /id="section-list"/, "IELTS reader should include a section list");
assert.match(projectIndex, /id="note-panel"/, "IELTS reader should include a right note panel");
assert.match(projectIndex, /id="mobile-note-drawer"/, "IELTS reader should include a mobile note drawer");
assert.match(projectIndex, /data-source="site\/ielts-data\.json"/, "IELTS reader should load generated site data through a data-source attribute");

assert.match(siteCss, /\.reader-shell/, "IELTS CSS should style the Foundations-style reader shell");
assert.match(siteCss, /\.reader-toolbar/, "IELTS CSS should style the reader toolbar");
assert.match(siteCss, /\.toolbar-search/, "IELTS CSS should style global search");
assert.match(siteCss, /\.reader-sidebar/, "IELTS CSS should style the module directory");
assert.match(siteCss, /\.module-section/, "IELTS CSS should style reader module sections");
assert.match(siteCss, /\.note-panel/, "IELTS CSS should style the right note panel");
assert.match(siteCss, /\.mobile-note-drawer/, "IELTS CSS should style the mobile note drawer");
assert.match(siteCss, /\[data-theme="dark"\]/, "IELTS CSS should include dark theme tokens");
assert.match(siteCss, /\.annotation-toolbar/, "IELTS CSS should style annotation controls");
assert.match(siteCss, /\.task-list/, "IELTS CSS should style task checklist state");
assert.match(siteCss, /@media \(max-width:\s*860px\)/, "IELTS CSS should include mobile drawer responsive rules");
assert.doesNotMatch(siteCss, /border-radius:\s*24px|border-radius:\s*28px/, "IELTS reader should avoid oversized card radii");

assert.match(readerJsBundle, /const ANNOTATION_STORAGE_KEY = "ieltsReader\.annotations\.v1"/, "IELTS JS should use an IELTS annotation localStorage key");
assert.match(readerJsBundle, /const TASK_STORAGE_KEY = "ieltsReader\.tasks\.v1"/, "IELTS JS should use an IELTS task localStorage key");
assert.match(readerJsBundle, /const UI_STATE_KEY = "ieltsReader\.ui\.v1"/, "IELTS JS should use an IELTS UI localStorage key");
assert.match(siteJs, /from "\.\/reader-modules\.js"/, "IELTS reader entry should import module helpers");
assert.match(siteJs, /from "\.\/reader-references\.js"/, "IELTS reader entry should import reference helpers");
assert.match(siteJs, /from "\.\/reader-renderers\.js"/, "IELTS reader entry should import renderer helpers");
assert.match(siteJs, /from "\.\/reader-state\.js"/, "IELTS reader entry should import state helpers");
assert.match(siteJs, /from "\.\/reader-tasks\.js"/, "IELTS reader entry should import task helpers");
assert.match(siteJs, /from "\.\/reader-utils\.js"/, "IELTS reader entry should import utility helpers");
assert.match(readerRenderersJs, /value === null \|\| value === undefined/, "IELTS renderer should not format missing bands as numeric scores");
assert.match(readerRenderersJs, /entry\.date/, "IELTS score history should expose diagnostic dates");
assert.match(readerRenderersJs, /skill\.riskLevel/, "IELTS skill gaps should expose risk levels");
assert.match(readerRenderersJs, /skill\.unverifiedDimensions/, "IELTS skill gaps should expose unverified dimensions");
assert.match(readerRenderersJs, /\["high", "medium"\]/, "IELTS swimlane should consider high and medium impact errors");
assert.match(readerRenderersJs, /checkpoint\.evidenceRequired/, "IELTS checkpoint milestones should expose evidence requirements");
assert.match(siteJs, /function buildReaderModules/, "IELTS JS should adapt IELTS site data into reader modules");
assert.match(siteJs, /function renderModuleNav/, "IELTS JS should render module navigation");
assert.match(siteJs, /function renderCurrentModule/, "IELTS JS should render the active module");
assert.match(siteJs, /function renderSectionRail/, "IELTS JS should render a section rail");
assert.match(siteJs, /function renderContextualNotePanel/, "IELTS JS should render contextual notes");
assert.match(siteJs, /function runSearch/, "IELTS JS should support Foundations-style global search");
assert.match(siteJs, /function createAnnotationFromSelection/, "IELTS JS should support local annotations");
assert.match(readerJsBundle, /function saveTaskState/, "IELTS JS should persist local task state");
assert.match(readerTasksJs, /legacyIds/, "IELTS task helper should migrate legacy checklist IDs");
assert.match(siteJs, /createLegacyTaskIds/, "IELTS reader should supply legacy checklist IDs during migration");
assert.match(siteJs, /function setTheme/, "IELTS JS should support theme switching");
assert.match(siteJs, /fetchJson\(getDataSource\(\)\)/, "IELTS JS should load generated data from the script data-source attribute");
assert.match(siteJs, /Dashboard/, "IELTS modules should keep the Dashboard content");
assert.match(siteJs, /8-week swimlane/, "IELTS modules should keep the swimlane content");
assert.match(siteJs, /Errors/, "IELTS modules should keep the Errors content");
assert.match(siteJs, /Notes/, "IELTS modules should keep the Notes content");
assert.match(siteJs, /Journal/, "IELTS modules should keep the Journal content");
assert.match(siteJs, /Prompt library/, "IELTS modules should keep the Prompt library content");
assert.match(siteJs, /Validation/, "IELTS modules should keep the Validation content");
assert.doesNotMatch(readerJsBundle, /localStorage\.setItem\(".*score|localStorage\.setItem\(".*error|localStorage\.setItem\(".*checkpoint/i, "IELTS JS should not store score, error, or checkpoint source data in localStorage");
assert.doesNotMatch(readerJsBundle, /localStorage\.setItem\("(?!ieltsReader\.(ui|annotations|tasks)\.v1")/, "IELTS JS should only write allowed IELTS localStorage keys");
assert.doesNotMatch(siteJs, /githubToken|Authorization|contents\/|repos\/|fetch\("\/api/i, "IELTS JS should not include backend or GitHub write-back signals");

assert.match(buildScript, /from "\.\/build-sources\.mjs"/, "build script should use source helper module");
assert.match(buildScript, /from "\.\/build-schema\.mjs"/, "build script should use schema helper module");
assert.match(buildScript, /from "\.\/build-references\.mjs"/, "build script should use reference helper module");
assert.match(buildScript, /from "\.\/build-markdown\.mjs"/, "build script should use markdown helper module");
assert.match(buildSources, /function parseFrontmatter/, "source helper should parse frontmatter");
assert.match(buildSchema, /function validateSiteDataInputs/, "schema helper should validate site data inputs");
assert.match(buildReferences, /function buildReferenceIndex/, "reference helper should build cross-reference index");
assert.match(buildMarkdown, /function markdownToSafeHtml/, "markdown helper should render safe HTML");

const ieltsProject = manifest.find((project) => project.id === "ielts-academic");
assert.ok(ieltsProject, "projects manifest should include IELTS Academic");
assert.equal(ieltsProject.folder, "language/ielts-academic/", "IELTS manifest folder should point to the nested language project");
assert.equal(ieltsProject.status, "active", "IELTS manifest entry should be active");

assert.match(notesReadme, /related_errors/, "notes README should document related_errors");
assert.match(journalReadme, /related_notes/, "journal README should document related_notes");

assert.equal(root.pathname.endsWith("/projects/language/ielts-academic/"), true);
assert.equal(languageReadmeUrl.pathname.endsWith("/projects/language/README.md"), true);
