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
  assert.match(moduleMarkdown, /status: (not-started|learning|review|done)/, `module ${id} should declare an allowed learning status`);
  assert.match(moduleMarkdown, /learning_progress: [0-9]+/, `module ${id} should declare learning progress`);
  assert.doesNotMatch(moduleMarkdown, /^progress: /m, `module ${id} should not use legacy progress`);
  assert.match(moduleMarkdown, /last_updated: 2026-07-05/, `module ${id} should declare a last updated date`);
  if (id === "overview") {
    assert.match(moduleMarkdown, /## Dashboard/, "overview should be a dashboard source");
    assert.match(moduleMarkdown, /## Interview Signal/, "overview should include interview signal calibration");
    assert.match(moduleMarkdown, /真实 baseline|Signal Rubric|当前最大风险/, "overview should track interview-readiness uncertainty");
    assert.doesNotMatch(moduleMarkdown, /## 验收标准|## 下一步/, "overview should not use ordinary-module closing sections");
  } else {
    assert.match(moduleMarkdown, /## 目标[\s\S]*## 当前状态[\s\S]*## 核心知识[\s\S]*## 任务[\s\S]*## 时间线[\s\S]*## 知识笔记/, `module ${id} should use the knowledge-base section contract`);
    assert.doesNotMatch(moduleMarkdown, /## 资源|## 反思|## 面试表达|## 验收标准|## 下一步/, `module ${id} should not keep old side-note or project-management sections`);
  }
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
assert.match(css, /\.learning-progress/, "roadmap CSS should style learning progress");
assert.match(css, /\.progress-ring/, "roadmap CSS should style a module progress ring");
assert.match(css, /\.overall-progress/, "roadmap CSS should label overall learning progress");
assert.match(css, /\.dashboard-grid/, "roadmap CSS should style the overview dashboard");
assert.match(css, /\.dashboard-module-list/, "roadmap CSS should style module dashboard rows");
assert.match(css, /\.knowledge-list/, "roadmap CSS should style knowledge-note lists");
assert.match(css, /\.knowledge-card/, "roadmap CSS should style concept-centric knowledge cards");
assert.match(css, /\.timeline-list/, "roadmap CSS should style timeline content as a visual list");
assert.match(css, /\.note-group-title/, "roadmap CSS should style explicit note group headings");
assert.match(css, /\.annotation-toolbar/, "roadmap CSS should style the local annotation selection toolbar");
assert.match(css, /\.knowledge-highlight/, "roadmap CSS should style knowledge-card highlights");
assert.match(css, /\.knowledge-highlight\.is-note/, "note-backed highlights should be visually distinguishable");
assert.match(css, /\.annotation-delete-popover/, "roadmap CSS should style the highlight delete popover");
assert.match(css, /\.local-annotation-list/, "right note panel should style local annotation groups");
assert.match(css, /\.local-annotation-quote/, "right note panel should style copied source excerpts");
assert.match(css, /\.local-annotation-editor/, "right note panel should style editable study notes");
assert.match(css, /\.local-annotation\.is-detached/, "right note panel should expose detached annotation state");
assert.match(css, /\.section-line:hover/, "roadmap CSS should style collapsed rail hover state");
assert.match(css, /\.section-line:hover \+ \.section-line/, "collapsed rail should grow neighboring lines on hover");
assert.match(css, /\.section-line\[aria-current="true"\]/, "roadmap CSS should expose active collapsed rail state");
assert.match(css, /\.section-line\[aria-current="true"\]:hover,\s*\.section-line\.is-active:hover\s*\{[\s\S]*background:\s*var\(--reader-section-line-hover\)/, "active collapsed rail line should show a distinct hover state");
const activeRailRule = css.match(/\.section-line\[aria-current="true"\],\s*\.section-line\.is-active\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
const activeRailHoverRule = css.match(/\.section-line\[aria-current="true"\]:hover,\s*\.section-line\.is-active:hover\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
assert.ok(activeRailRule, "active collapsed rail rule should be inspectable");
assert.ok(activeRailHoverRule, "active collapsed rail hover rule should be inspectable");
assert.doesNotMatch(activeRailRule, /width\s*:/, "active collapsed rail state should not lengthen the current line");
assert.match(activeRailHoverRule, /width:\s*36px/, "active collapsed rail hover state should lengthen the current line");
assert.match(css, /\.section-tooltip/, "collapsed rail should expose section tooltips");
assert.match(css, /\.result-meta/, "roadmap CSS should show module and section metadata in search results");
assert.match(css, /\.reader-shell\.is-searching \.reader-toolbar\s*\{[\s\S]*z-index:\s*4[0-9]/, "search toolbar and results should sit above the search overlay");
assert.match(css, /@media \(max-width:\s*860px\)/, "roadmap CSS should include mobile layout rules");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "roadmap reader should avoid oversized card radii");

assert.match(js, /fetchJson\("roadmap\/roadmap-data\.json"\)/, "roadmap JS should load generated JSON");
assert.match(js, /function renderModuleNav/, "roadmap JS should isolate module navigation rendering");
assert.match(js, /function renderCurrentModule/, "roadmap JS should isolate module content rendering");
assert.match(js, /function renderOverviewDashboard/, "roadmap JS should render overview as a dashboard");
assert.match(js, /function renderKnowledgeNotesSection/, "roadmap JS should render concept-centric knowledge notes");
assert.match(js, /function renderContextualNotePanel/, "roadmap JS should render context-aware right notes");
assert.match(js, /function setActiveKnowledgeContext/, "roadmap JS should sync right notes with active knowledge context");
assert.match(js, /function runSearch/, "roadmap JS should implement local keyword search");
assert.match(js, /function setTheme/, "roadmap JS should support theme switching");
assert.match(js, /function renderProgressSummary/, "roadmap JS should render labeled module and overall learning progress");
assert.match(js, /function renderTimelineSection/, "roadmap JS should render timeline as a visual component");
assert.match(js, /function renderSearchResults/, "roadmap JS should isolate section-level search rendering");
assert.match(js, /function hasSearchTerm/, "roadmap JS should avoid raw substring-only search matches");
assert.match(js, /function getSearchMatchLevel/, "roadmap JS should distinguish whole-word matches from partial matches");
assert.match(js, /function escapeSearchPattern/, "roadmap JS should escape user search terms before building regex patterns");
assert.match(js, /return getSearchMatchLevel\(text, term\) > 0;/, "hasSearchTerm should delegate to the shared match-level helper");
assert.match(js, /const moduleLevel = getSearchMatchLevel\(entry\.moduleTitle, term\);/, "search scoring should evaluate module title match levels");
assert.match(js, /moduleLevel === 2 \? 16 : moduleLevel === 1 \? 6 : 0/, "whole-word module matches should outrank partial module matches");
assert.match(js, /bodyLevel === 2 \? 4 : bodyLevel === 1 \? 1 : 0/, "body partial matches should remain a low-score fallback");
assert.match(js, /function getSearchScore/, "roadmap JS should rank search entries with explicit scoring");
assert.match(js, /function setActiveSection/, "roadmap JS should update collapsed rail active state dynamically");
assert.match(js, /function syncActiveSectionFromScroll/, "roadmap JS should actively sync rail state from reader scroll position");
assert.match(js, /addEventListener\("scroll", state\.sectionScrollHandler, \{ passive: true \}\)/, "reader scroll should drive collapsed rail active state");
assert.match(js, /els\.main\.clientHeight \* 0\.24/, "active rail state should switch near the upper reading anchor");
assert.doesNotMatch(js, /rootMargin:\s*"-16% 0px -68% 0px"/, "active rail state should not depend on the old narrow intersection band");
assert.match(js, /data-section-id/, "roadmap JS should render stable section targets for search and rail navigation");
assert.match(js, /section-tooltip/, "roadmap JS should render collapsed rail tooltips");
assert.doesNotMatch(js, /index === 0 \? " is-active" : ""/, "section rail should not hard-code the first line as active");
assert.doesNotMatch(js, /index === 0 \? "true" : "false"/, "section rail aria-current should not be hard-coded from initial index");
assert.match(js, /button\.className = "section-line";/, "section rail buttons should start inactive");
assert.match(js, /button\.setAttribute\("aria-current", "false"\);/, "section rail aria-current should be initialized as false");
assert.match(js, /knowledgeNotes/, "roadmap JS should consume generated knowledge notes");
assert.doesNotMatch(js, /资源", "反思", "面试表达"/, "right notes should not be hard-coded to old resource/reflection/interview groups");
assert.doesNotMatch(js, /if \(sectionId === getSectionId\(module, "知识笔记"\)\) return module\.knowledgeNotes\?\.\[0\];/, "knowledge note section should not default to the first note");
assert.doesNotMatch(js, /return getKnowledgeNoteById\(module, state\.activeKnowledgeNoteId\) \?\? module\.knowledgeNotes\?\.\[0\];/, "ordinary sections should not fall back to stale or first knowledge notes");
assert.match(js, /if \(sectionId !== getSectionId\(module, "知识笔记"\)\) return null;/, "ordinary sections should return an empty right panel when they have no explicit knowledge note");
assert.match(js, /const renderedNotes = note[\s\S]*: "";/, "right note panel should render an empty surface when no note is associated");
assert.match(js, /renderContextualNotePanel\(null\);/, "module switches should start with an empty right note panel");
assert.doesNotMatch(js, /renderContextualNotePanel\(nextModule\.knowledgeNotes\?\.\[0\]\);/, "module switches should not default the right panel to the first knowledge note");
assert.match(js, /ANNOTATION_STORAGE_KEY = "foundationsReader\.annotations\.v1"/, "Foundations reader should define a versioned local annotation storage key");
assert.match(js, /function createEmptyAnnotationStore/, "Foundations reader should create an empty annotation store");
assert.match(js, /function loadAnnotations/, "Foundations reader should load local annotations from localStorage");
assert.match(js, /function saveAnnotations/, "Foundations reader should save local annotations to localStorage");
assert.match(js, /function getAnnotationsForNote/, "Foundations reader should filter annotations by module and knowledge note");
assert.match(js, /function createAnnotationFromSelection/, "Foundations reader should create annotations from selected knowledge-card text");
assert.match(js, /function applyHighlights/, "Foundations reader should restore highlights inside knowledge cards");
assert.match(js, /function updateAnnotationNote/, "Foundations reader should update local study-note text");
assert.match(js, /function deleteAnnotation/, "Foundations reader should support deleting highlights and annotations");
assert.match(js, /\.knowledge-card/, "annotation selection should be scoped to knowledge cards");
assert.match(js, /data-note-id/, "annotations should anchor to stable knowledge note ids");
assert.match(js, /高亮/, "selection toolbar should expose a highlight action");
assert.match(js, /笔记/, "selection toolbar should expose a note action");
assert.match(js, /只删除高亮，保留笔记/, "delete confirmation should allow keeping the note");
assert.match(js, /高亮和笔记一起删除/, "delete confirmation should allow deleting both highlight and note");
assert.doesNotMatch(js, /PROJECT_ID = "brain-memory-for-ai-agents"|paperReader\.annotations\.v1/, "Foundations annotations should not reuse paper-reader project state");
assert.doesNotMatch(js, /githubToken|Authorization|contents\/|repos\/|gitHub|fetch\(\"\/api/i, "Foundations annotations should not write to GitHub or backend APIs");
assert.doesNotMatch(js, /embeddings\.json|cosineSimilarity|PROJECT_ID = "brain-memory-for-ai-agents"/, "Foundations reader JS should not reuse paper-specific semantic search state");

assert.equal(data.project.id, "foundations", "generated data should identify the Foundations project");
assert.equal(data.project.targetRole, "Agent / LLM Systems Engineer", "generated data should keep the target role");
assert.equal(data.project.dashboardModuleId, "overview", "generated data should identify overview as the dashboard");
assert.equal(typeof data.project.overallLearningProgress, "number", "generated data should include overall learning progress");
assert.equal(data.project.overallLearningProgress, 0, "initial overall learning progress should be zero");
assert.deepEqual(data.modules.map((module) => [module.id, module.title]), requiredModules, "generated data should include the required modules in navigation order");

for (const module of data.modules) {
  assert.equal(typeof module.status, "string", `${module.id} should include status`);
  assert.equal(typeof module.learningProgress, "number", `${module.id} should include numeric learning progress`);
  assert.ok(module.learningProgress >= 0 && module.learningProgress <= 100, `${module.id} learningProgress should be bounded`);
  assert.equal(Object.hasOwn(module, "progress"), false, `${module.id} should not expose legacy progress`);
  assert.equal(typeof module.lastUpdated, "string", `${module.id} should include lastUpdated`);
  assert.equal(typeof module.searchText, "string", `${module.id} should include search text`);
  assert.ok(module.searchText.length > 80, `${module.id} should have useful search text`);
  assert.ok(module.sections && typeof module.sections === "object", `${module.id} should include sections`);
  assert.equal(Object.hasOwn(module.sections, "验收标准"), false, `${module.id} should not render 验收标准 as a section`);
  assert.equal(Object.hasOwn(module.sections, "下一步"), false, `${module.id} should not render 下一步 as a section`);
  if (module.id !== "overview") {
    assert.equal(Object.hasOwn(module.sections, "时间线"), true, `${module.id} should preserve 时间线`);
    assert.equal(Object.hasOwn(module.sections, "知识笔记"), true, `${module.id} should include 知识笔记`);
  }
  assert.ok(Array.isArray(module.searchEntries), `${module.id} should include section-level search entries`);
  assert.ok(module.searchEntries.length > 0, `${module.id} should expose searchable sections`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should point back to the module`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.sectionTitle === "string" && entry.sectionTitle.length > 0), `${module.id} search entries should include section titles`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.text === "string" && entry.text.length > 20), `${module.id} search entries should include useful text`);
  assert.ok(Array.isArray(module.knowledgeNotes), `${module.id} should include knowledge notes`);
  assert.ok(module.knowledgeNotes.every((note) => typeof note.id === "string" && note.id.startsWith(module.id)), `${module.id} knowledge notes should have stable ids`);
  assert.ok(module.knowledgeNotes.every((note) => typeof note.title === "string" && note.title.length > 0), `${module.id} knowledge notes should include titles`);
  assert.ok(Array.isArray(module.timeline), `${module.id} should include a timeline array`);
}

const byId = Object.fromEntries(data.modules.map((module) => [module.id, module]));
assert.ok(byId["agent-design"].timeline.length >= 3, "agent design should expose timeline items for visual rendering");
assert.ok(byId["rag-memory"].knowledgeNotes.length >= 2, "RAG and memory should expose concept-centric notes");
assert.ok(byId["rag-memory"].knowledgeNotes.some((note) => note.title === "RAG evaluation"), "RAG and memory should include a RAG evaluation note");
assert.ok(byId["rag-memory"].searchEntries.some((entry) => entry.type === "knowledge-note"), "search should include knowledge-note entries");
assert.match(byId.overview.searchText, /30\/45\/60-Day Plan|Project Recommendations|Weekly Review Checklist/, "overview should preserve timeline and project recommendation content");
assert.match(byId.overview.searchText, /Interview Signal|真实 baseline|Agent system design mock/, "overview should preserve interview signal calibration content");
assert.match(byId.coding.searchText, /Coding Plan|Python Standards|TypeScript Standards|Optional Rust Log Parser/, "coding should preserve implementation training content");
assert.match(byId["llm-systems"].searchText, /LLM Systems|Transformer|post-training|LLM Fundamentals/, "LLM systems should preserve model and theory content");
assert.match(byId["agent-design"].searchText, /Agent Systems|Agent Runtime With Tool Calling|Safe Tool Execution Layer|Tool Router/, "agent design should preserve agent runtime content");
assert.match(byId["rag-memory"].searchText, /RAG And Memory|Production RAG System|Long-Term Memory|Retrieval Evaluator|Memory Store/, "RAG and memory should preserve retrieval and memory content");
assert.match(byId["evals-debugging"].searchText, /Eval And Debugging|Eval Harness|Trace Debugging|Agent Trace Logger/, "evals should preserve eval and trace content");
assert.match(byId["research-reading"].searchText, /Research Reading List|scaling laws|RLHF|RLAIF|RLVR/, "research reading should preserve reading list content");
assert.match(byId["behavioral-strategy"].searchText, /Behavioral And Project Deep Dive|Strategy Rubric|STAR|tradeoff/, "behavioral strategy should preserve interview strategy content");
assert.match(byId.logs.searchText, /Weekly Review|review checklist|复盘/, "logs should preserve review and reflection content");
