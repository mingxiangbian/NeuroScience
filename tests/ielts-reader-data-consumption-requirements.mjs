import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const indexHtml = read("../projects/language/ielts-academic/index.html");
const entryJs = read("../projects/language/ielts-academic/site/ielts-reader.js");
const css = read("../projects/language/ielts-academic/site/ielts-reader.css");
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
assert.match(annotations, /定位失效|unresolved/i, "annotations should expose unresolved locator state");
assert.match(annotations, /本机临时阅读标注/, "annotation UI should state local temporary boundary");

assert.match(modules, /function renderModuleSafely/, "module rendering should have per-module error boundary");
assert.match(utils, /function getShortcutLabel/, "shortcut label should be platform-aware");
assert.match(renderers, /<table class="swimlane-table"/, "swimlane should expose table semantics");

assert.match(css, /\.score-history/, "CSS should style score history");
assert.match(css, /\.checkpoint-milestones/, "CSS should style checkpoint milestones");
assert.match(css, /\.reference-panel-action/, "CSS should style reference panel actions");
assert.match(css, /\.validation-issue/, "CSS should style validation issues");
assert.match(css, /\.annotation-draft/, "CSS should style annotation journal draft");
assert.match(css, /\.annotation-unresolved/, "CSS should style unresolved annotations");

assert.match(indexHtml, /site\/ielts-reader\.js/, "reader HTML should keep stable entrypoint");
assert.equal(Array.isArray(data.references.targets), true);
assert.equal(Array.isArray(data.build.validationIssues), true);
