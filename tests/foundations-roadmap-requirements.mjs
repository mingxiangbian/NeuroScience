import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const buildScriptUrl = new URL("../projects/foundations/scripts/build-roadmap-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/foundations/roadmap/roadmap-data.json", import.meta.url);
const cssUrl = new URL("../projects/foundations/roadmap/roadmap-reader.css", import.meta.url);
const jsUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);
const modulesDirUrl = new URL("../projects/foundations/roadmap/modules/", import.meta.url);

const requiredModules = [
  ["overview", "Overview"],
  ["coding", "Coding"],
  ["llm-systems", "LLM Systems"],
  ["agent-design", "Agent Design"],
  ["rag-memory", "RAG & Memory"],
  ["evals-debugging", "Evals & Debugging"],
  ["research-reading", "Research Reading"],
  ["behavioral-strategy", "Behavioral / Strategy"],
  ["logs", "Logs"],
];

assert.equal(existsSync(foundationsPageUrl), true, "Foundations should expose a static reader page");
assert.equal(existsSync(buildScriptUrl), true, "Foundations should include a roadmap data build script");
assert.equal(existsSync(dataUrl), true, "Foundations should include generated roadmap data");
assert.equal(existsSync(cssUrl), true, "Foundations should include dedicated roadmap reader CSS");
assert.equal(existsSync(jsUrl), true, "Foundations should include dedicated roadmap reader JS");

for (const [id] of requiredModules) {
  const moduleUrl = new URL(`${id}.md`, modulesDirUrl);
  assert.equal(existsSync(moduleUrl), true, `module ${id} should exist`);
  const moduleMarkdown = readFileSync(moduleUrl, "utf8");
  assert.match(moduleMarkdown, new RegExp(`id: ${id}`), `module ${id} should declare its id`);
  assert.match(moduleMarkdown, /status: (not-started|in-progress|review|done)/, `module ${id} should declare an allowed status`);
  assert.match(moduleMarkdown, /progress: [0-9]+/, `module ${id} should declare progress`);
  assert.match(moduleMarkdown, /last_updated: 2026-07-05/, `module ${id} should declare a last updated date`);
  assert.match(moduleMarkdown, /## 目标|## 当前状态|## 时间线|## 资源|## 面试表达|## 验收标准/, `module ${id} should use fixed second-level sections`);
}

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const html = readFileSync(foundationsPageUrl, "utf8");
const css = readFileSync(cssUrl, "utf8");
const js = readFileSync(jsUrl, "utf8");
const data = JSON.parse(readFileSync(dataUrl, "utf8"));

assert.match(html, /data-page="foundations-roadmap-reader"/, "Foundations page should identify itself as the roadmap reader");
assert.match(html, /id="reader-shell"/, "Foundations page should include a reader shell");
assert.match(html, /id="module-directory"/, "Foundations page should include a left module directory");
assert.match(html, /id="reader-main"/, "Foundations page should include a center reader area");
assert.match(html, /id="note-panel"/, "Foundations page should include a right note panel");
assert.match(html, /id="global-search"/, "Foundations page should include global search");
assert.match(html, /href="roadmap\/roadmap-reader\.css"/, "Foundations page should load dedicated reader CSS");
assert.match(html, /src="roadmap\/roadmap-reader\.js"/, "Foundations page should load dedicated reader JS");
assert.doesNotMatch(html, /class="doc-grid"|class="doc-link"/, "Foundations page should no longer render the document-card homepage as the main experience");
assert.doesNotMatch(html, /href="README\.md"[\s\S]*href="multi-agent-planner\.md"[\s\S]*href="llm-agent-engineer-roadmap\.md"/, "Foundations homepage should not be a README/template/roadmap card list");

assert.match(css, /\.reader-shell\s*\{[\s\S]*grid-template-columns:/, "roadmap CSS should define a three-column reader shell");
assert.match(css, /data-theme="dark"/, "roadmap CSS should support dark mode");
assert.match(css, /\.module-nav-item\[aria-current="true"\]/, "roadmap CSS should style the active module");
assert.match(css, /\.progress-meter/, "roadmap CSS should style module progress");
assert.match(css, /\.progress-ring/, "roadmap CSS should style a module progress ring");
assert.match(css, /\.overall-progress/, "roadmap CSS should label overall roadmap progress");
assert.match(css, /\.timeline-list/, "roadmap CSS should style timeline content as a visual list");
assert.match(css, /\.note-group-title/, "roadmap CSS should style explicit note group headings");
assert.match(css, /\.section-line:hover/, "roadmap CSS should style collapsed rail hover state");
assert.match(css, /\.section-line\[aria-current="true"\]/, "roadmap CSS should expose active collapsed rail state");
assert.match(css, /\.result-meta/, "roadmap CSS should show module and section metadata in search results");
assert.match(css, /\.reader-shell\.is-searching \.reader-toolbar\s*\{[\s\S]*z-index:\s*4[0-9]/, "search toolbar and results should sit above the search overlay");
assert.match(css, /@media \(max-width:\s*860px\)/, "roadmap CSS should include mobile layout rules");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "roadmap reader should avoid oversized card radii");

assert.match(js, /fetchJson\("roadmap\/roadmap-data\.json"\)/, "roadmap JS should load generated JSON");
assert.match(js, /function renderModuleNav/, "roadmap JS should isolate module navigation rendering");
assert.match(js, /function renderCurrentModule/, "roadmap JS should isolate module content rendering");
assert.match(js, /function renderNotePanel/, "roadmap JS should isolate right-note rendering");
assert.match(js, /function runSearch/, "roadmap JS should implement local keyword search");
assert.match(js, /function setTheme/, "roadmap JS should support theme switching");
assert.match(js, /function renderProgressSummary/, "roadmap JS should render labeled module and overall progress");
assert.match(js, /function renderTimelineSection/, "roadmap JS should render timeline as a visual component");
assert.match(js, /function renderSearchResults/, "roadmap JS should isolate section-level search rendering");
assert.match(js, /function hasSearchTerm/, "roadmap JS should avoid raw substring-only search matches");
assert.match(js, /function getSearchScore/, "roadmap JS should rank search entries with explicit scoring");
assert.match(js, /function setActiveSection/, "roadmap JS should update collapsed rail active state dynamically");
assert.match(js, /IntersectionObserver/, "roadmap JS should observe visible sections for active rail state");
assert.match(js, /data-section-id/, "roadmap JS should render stable section targets for search and rail navigation");
assert.doesNotMatch(js, /localStorage|sessionStorage/, "first version should not persist state in browser storage");
assert.doesNotMatch(js, /embeddings\.json|cosineSimilarity|PROJECT_ID = "brain-memory-for-ai-agents"/, "Foundations reader JS should not reuse paper-specific semantic search state");

assert.equal(data.project.id, "foundations", "generated data should identify the Foundations project");
assert.equal(data.project.targetRole, "Agent / LLM Systems Engineer", "generated data should keep the target role");
assert.equal(typeof data.project.overallProgress, "number", "generated data should include overall progress");
assert.ok(data.project.overallProgress > 0, "overall progress should be greater than zero");
assert.ok(data.project.overallProgress <= 100, "overall progress should not exceed 100");
assert.deepEqual(data.modules.map((module) => [module.id, module.title]), requiredModules, "generated data should include the required modules in navigation order");

for (const module of data.modules) {
  assert.equal(typeof module.status, "string", `${module.id} should include status`);
  assert.equal(typeof module.progress, "number", `${module.id} should include numeric progress`);
  assert.equal(typeof module.lastUpdated, "string", `${module.id} should include lastUpdated`);
  assert.equal(typeof module.searchText, "string", `${module.id} should include search text`);
  assert.ok(module.searchText.length > 80, `${module.id} should have useful search text`);
  assert.ok(module.sections && typeof module.sections === "object", `${module.id} should include sections`);
  assert.ok(Array.isArray(module.searchEntries), `${module.id} should include section-level search entries`);
  assert.ok(module.searchEntries.length > 0, `${module.id} should expose searchable sections`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should point back to the module`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.sectionTitle === "string" && entry.sectionTitle.length > 0), `${module.id} search entries should include section titles`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.text === "string" && entry.text.length > 20), `${module.id} search entries should include useful text`);
  assert.ok(Array.isArray(module.noteGroups), `${module.id} should include note groups`);
  assert.ok(module.noteGroups.every((group) => ["资源", "反思", "面试表达"].includes(group.title)), `${module.id} note groups should use known categories`);
  assert.ok(Array.isArray(module.timeline), `${module.id} should include a timeline array`);
}

const byId = Object.fromEntries(data.modules.map((module) => [module.id, module]));
assert.ok(byId["agent-design"].timeline.length >= 3, "agent design should expose timeline items for visual rendering");
assert.match(byId.overview.searchText, /30\/45\/60-Day Plan|Project Recommendations|Weekly Review Checklist/, "overview should preserve timeline and project recommendation content");
assert.match(byId.coding.searchText, /Coding Plan|Python Standards|TypeScript Standards|Optional Rust Log Parser/, "coding should preserve implementation training content");
assert.match(byId["llm-systems"].searchText, /LLM Systems|Transformer|post-training|LLM Fundamentals/, "LLM systems should preserve model and theory content");
assert.match(byId["agent-design"].searchText, /Agent Systems|Agent Runtime With Tool Calling|Safe Tool Execution Layer|Tool Router/, "agent design should preserve agent runtime content");
assert.match(byId["rag-memory"].searchText, /RAG And Memory|Production RAG System|Long-Term Memory|Retrieval Evaluator|Memory Store/, "RAG and memory should preserve retrieval and memory content");
assert.match(byId["evals-debugging"].searchText, /Eval And Debugging|Eval Harness|Trace Debugging|Agent Trace Logger/, "evals should preserve eval and trace content");
assert.match(byId["research-reading"].searchText, /Research Reading List|scaling laws|RLHF|RLAIF|RLVR/, "research reading should preserve reading list content");
assert.match(byId["behavioral-strategy"].searchText, /Behavioral And Project Deep Dive|Strategy Rubric|STAR|tradeoff/, "behavioral strategy should preserve interview strategy content");
assert.match(byId.logs.searchText, /Weekly Review|review checklist|复盘/, "logs should preserve review and reflection content");
