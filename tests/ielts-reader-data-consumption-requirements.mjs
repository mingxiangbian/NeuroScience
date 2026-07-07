import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const indexHtml = read("../projects/language/ielts-academic/index.html");
const entryJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const css = read("../projects/language/ielts-academic/site/ielts-reader.css");
const workflow = read("../.github/workflows/pages.yml");
const data = JSON.parse(read("../projects/language/ielts-academic/site/ielts-data.json"));

assert.match(entryJs, /from "\.\/reader-renderers\.js"/, "entrypoint should import renderer module");
assert.match(entryJs, /from "\.\/reader-modules\.js"/, "entrypoint should import module builder");
assert.match(entryJs, /from "\.\/reader-references\.js"/, "entrypoint should import reference module");
assert.match(entryJs, /from "\.\/reader-annotations\.js"/, "entrypoint should import annotation module");
assert.match(entryJs, /from "\.\/reader-tasks\.js"/, "entrypoint should import task module");

const renderers = read("../projects/language/ielts-academic/site/reader-renderers.js");
const references = read("../projects/language/ielts-academic/site/reader-references.js");
const annotations = read("../projects/language/ielts-academic/site/reader-annotations.js");
const tasks = read("../projects/language/ielts-academic/site/reader-tasks.js");
const utils = read("../projects/language/ielts-academic/site/reader-utils.js");
const modules = read("../projects/language/ielts-academic/site/reader-modules.js");

assert.doesNotMatch(renderers, /function laneText/, "swimlane should not use static laneText");
assert.match(renderers, /function renderScoreHistory/, "dashboard should render score history");
assert.match(renderers, /function getSkillWeekFocus/, "swimlane should derive per-skill weekly focus");
assert.match(renderers, /function renderCheckpointMilestones/, "checkpoint milestones should be global");
assert.match(renderers, /scoreProfile\.skills/, "swimlane should consume skill profile data");
assert.match(renderers, /errorLog\?\.errors/, "swimlane should consume error data");
assert.match(renderers, /scoreHistory\?\.entries/, "dashboard should consume score history data");

assert.match(references, /function renderReferenceChips/, "reference chips should live in reference module");
assert.match(references, /data-reference-id/, "reference chips should bind internal target ids");
assert.match(references, /function getReferencePanelPayload/, "right panel should render reference payloads");
assert.match(references, /relatedObjects/, "right panel payload should expose forward related objects");
assert.match(references, /payload\.status/, "right panel should expose object status metadata");
assert.match(references, /payload\.skill/, "right panel should expose object skill metadata");
assert.match(references, /payload\.date/, "right panel should expose object date metadata");
assert.match(references, /payload\.summary/, "right panel should expose object summary metadata");
assert.match(references, /function openReferenceTarget/, "references should support internal navigation");
assert.doesNotMatch(references, /href="\$\{escapeHtml\(item\.path\)\}"/, "source path should not be the primary chip navigation");

assert.match(tasks, /function createStableTaskId/, "task module should create stable task ids");
assert.doesNotMatch(tasks, /__\$\{index\}/, "task ids should not use array index");

assert.match(annotations, /function createJournalDraftMarkdown/, "annotations should support journal draft export");
assert.match(annotations, /data-journal-draft/, "annotation journal draft should have a refresh target");
assert.match(annotations, /定位失效|unresolved/i, "annotations should expose unresolved locator state");
assert.match(annotations, /本机临时阅读标注/, "annotation UI should state local temporary boundary");
assert.match(entryJs, /function refreshJournalDraftTextareas/, "annotation editor should refresh adjacent journal drafts");
assert.match(entryJs, /navigator\.clipboard\?\.writeText/, "journal draft copy should handle unavailable clipboard APIs");
assert.match(entryJs, /请手动复制|复制失败/, "journal draft copy should expose a manual fallback state");
assert.match(entryJs, /function renderEmptyDetailPanel/, "right panel should default to an empty detail state");
assert.match(entryJs, /function getPriorityLabel/, "module priority labels should be localized");
assert.match(entryJs, /成绩档案/, "module priority labels should be Chinese-facing");
assert.doesNotMatch(entryJs, /"Session bodies"/, "journal module should not render duplicate full session bodies by default");
assert.doesNotMatch(entryJs, /renderKnowledgeNotesSection/, "main content should not auto-render parallel notes");
assert.doesNotMatch(
  entryJs,
  /querySelectorAll\("\[data-section-id\], \[data-note-id\]"\)/,
  "clicking normal main sections should not mirror content into the right panel",
);
const setActiveSectionBlock = entryJs.slice(
  entryJs.indexOf("function setActiveSection"),
  entryJs.indexOf("function getActiveSectionFromScroll"),
);
assert.doesNotMatch(setActiveSectionBlock, /setActiveKnowledgeContext/, "scroll sync should not populate the right panel");

assert.match(modules, /function renderModuleSafely/, "module rendering should have per-module error boundary");
assert.match(utils, /function getShortcutLabel/, "shortcut label should be platform-aware");
assert.match(utils, /function renderExamMark/, "utility module should render the exam mark component");
assert.match(renderers, /renderExamMark/, "dashboard and checkpoint renderers should use exam marks");
assert.match(entryJs, /renderExamMark/, "entrypoint progress summary should use exam marks");
assert.match(renderers, /<table class="swimlane-table"/, "swimlane should expose table semantics");
assert.match(renderers, /function getCheckpointDisplayName/, "checkpoint titles should remove duplicate week prefixes");
assert.doesNotMatch(
  renderers,
  /Week \$\{escapeHtml\(checkpoint\.week\)\} · \$\{escapeHtml\(checkpoint\.name\)\}/,
  "checkpoint marker should not duplicate week text from data names",
);
assert.match(renderers, /function getCompactWeekFocusLabel/, "swimlane cells should have compact labels");
assert.match(renderers, /class="swimlane-chip"/, "swimlane cells should render compact chips");
assert.doesNotMatch(renderers, /<h3>\$\{escapeHtml\(error\.description\)\}<\/h3>/, "error cards should not use long descriptions as headings");
assert.match(renderers, /error-description/, "error cards should demote descriptions to compact body text");

assert.match(css, /\.score-history/, "CSS should style score history");
assert.match(css, /\.checkpoint-milestones/, "CSS should style checkpoint milestones");
assert.match(css, /\.reference-panel-action/, "CSS should style reference panel actions");
assert.match(css, /\.validation-issue/, "CSS should style validation issues");
assert.match(css, /\.annotation-draft/, "CSS should style annotation journal draft");
assert.match(css, /\.annotation-unresolved/, "CSS should style unresolved annotations");
assert.match(css, /\.swimlane-chip/, "CSS should style compact swimlane chips");
assert.match(css, /\.error-description/, "CSS should clamp compact error descriptions");
assert.match(css, /--reader-marker: var\(--reader-red\);/, "CSS should expose the IELTS marker token");
assert.match(css, /--text-display: clamp\(36px, 5vw, 56px\);/, "CSS should expose display type scale token");
assert.match(css, /--sp-16: 64px;/, "CSS should expose spacing scale tokens");
assert.match(css, /--radius-pill: 999px;/, "CSS should expose radius scale tokens");
assert.match(css, /\.exam-mark/, "CSS should style the exam mark component");
assert.doesNotMatch(css, /progress-ring/, "reader progress should no longer use progress rings");
assert.doesNotMatch(
  css,
  /--reader-glass|--reader-panel-blur|backdrop-filter|-webkit-backdrop-filter/,
  "reader should not use frosted glass tokens or filters",
);

assert.match(indexHtml, /site\/ielts-reader\.js/, "reader HTML should keep stable entrypoint");
assert.match(indexHtml, /data-shortcut-label/, "shortcut hint should be platform-aware");
assert.match(workflow, /actions\/setup-node@v5/, "Pages workflow should setup Node before deploy");
assert.match(workflow, /npm ci/, "Pages workflow should install dependencies");
assert.match(workflow, /fonttools\[woff\]==4\.63\.0/, "Pages workflow should install WOFF font validation tools");
assert.match(workflow, /npm run build:ielts/, "Pages workflow should build IELTS data before deploy");
assert.match(workflow, /npm run test:all/, "Pages workflow should run static site tests before deploy");
assert.equal(Array.isArray(data.references.targets), true);
assert.equal(Array.isArray(data.build.validationIssues), true);
