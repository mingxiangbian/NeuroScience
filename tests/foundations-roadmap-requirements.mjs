import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const buildScriptUrl = new URL("../projects/foundations/scripts/build-roadmap-data.mjs", import.meta.url);
const dataUrl = new URL("../projects/foundations/roadmap/roadmap-data.json", import.meta.url);
const cssUrl = new URL("../projects/foundations/roadmap/roadmap-reader.css", import.meta.url);
const jsUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);
const codeListingJsUrl = new URL("../projects/foundations/roadmap/code-listing.js", import.meta.url);
const regularCodeFontUrl = new URL("../projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2", import.meta.url);
const mediumCodeFontUrl = new URL("../projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2", import.meta.url);
const codeFontLicenseUrl = new URL("../projects/foundations/assets/fonts/ibm-plex-mono/LICENSE", import.meta.url);
const modulesDirUrl = new URL("../projects/foundations/roadmap/modules/", import.meta.url);
const packageJsonUrl = new URL("../package.json", import.meta.url);

const requiredModules = [
  ["overview", "Overview"],
  ["interview-sprint", "Interview Sprint"],
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
assert.equal(existsSync(codeListingJsUrl), true, "Foundations should include the code listing enhancer");
assert.equal(existsSync(regularCodeFontUrl), true, "Foundations should vendor IBM Plex Mono Regular");
assert.equal(existsSync(mediumCodeFontUrl), true, "Foundations should vendor IBM Plex Mono Medium");
assert.equal(existsSync(codeFontLicenseUrl), true, "Foundations should retain the local code font license");

for (const [id] of requiredModules) {
  const moduleUrl = new URL(`${id}.md`, modulesDirUrl);
  assert.equal(existsSync(moduleUrl), true, `module ${id} should exist`);
  const moduleMarkdown = readFileSync(moduleUrl, "utf8");
  assert.match(moduleMarkdown, new RegExp(`id: ${id}`), `module ${id} should declare its id`);
  assert.match(moduleMarkdown, /status: (not-started|in-progress|learning|review|done)/, `module ${id} should declare an allowed learning status`);
  assert.match(moduleMarkdown, /learning_progress: [0-9]+/, `module ${id} should declare learning progress`);
  assert.doesNotMatch(moduleMarkdown, /^progress: /m, `module ${id} should not use legacy progress`);
  const expectedLastUpdated = {
    "interview-sprint": "2026-07-11",
    "evals-debugging": "2026-07-11",
    "agent-design": "2026-07-10",
    "behavioral-strategy": "2026-07-10",
  }[id] ?? "2026-07-05";
  assert.match(moduleMarkdown, new RegExp(`last_updated: ${expectedLastUpdated}`), `module ${id} should declare a last updated date`);
  if (id === "overview") {
    assert.match(moduleMarkdown, /## Dashboard/, "overview should be a dashboard source");
    assert.match(moduleMarkdown, /## Interview Signal/, "overview should include interview signal calibration");
    assert.match(moduleMarkdown, /真实 baseline|Signal Rubric|当前最大风险/, "overview should track interview-readiness uncertainty");
    assert.doesNotMatch(moduleMarkdown, /## 验收标准|## 下一步/, "overview should not use ordinary-module closing sections");
  } else if (id === "interview-sprint") {
    assert.match(moduleMarkdown, /时间驾驶舱|D1（2026-07-10）|D7（2026-07-16）/, "interview sprint should stay a seven-day cockpit module");
    assert.match(moduleMarkdown, /知识本体一律沉淀到对应能力模块/, "interview sprint should not duplicate knowledge modules");
    assert.match(moduleMarkdown, /两个必修 90 分钟块/, "interview sprint should expose its two core learning blocks");
    assert.match(moduleMarkdown, /增加第三个 90 分钟块/, "interview sprint should expose its optional third learning block");
    assert.match(moduleMarkdown, /盲测基线/, "interview sprint should start with an unseen baseline");
    assert.match(moduleMarkdown, /learning_progress: 0[\s\S]*D1 冲刺卡/, "interview sprint should record D1 without inflating mastery progress");
    assert.match(moduleMarkdown, /D2（2026-07-11）：已完成 coached 学习[\s\S]*D2 冲刺卡/, "interview sprint should record the completed D2 coached blocks");
    assert.doesNotMatch(moduleMarkdown, /标准日 180 分钟|重日 210 分钟/, "interview sprint should not keep the superseded standard/heavy-day contract");
    assert.match(moduleMarkdown, /## 目标[\s\S]*## 当前状态[\s\S]*## 核心知识[\s\S]*## 任务[\s\S]*## 时间线[\s\S]*## 学习记录/, "interview sprint should retain its sprint learning record");
    assert.doesNotMatch(moduleMarkdown, /^## 知识笔记$/m, "interview sprint should not publish knowledge articles");
  } else {
    assert.match(moduleMarkdown, /## 目标[\s\S]*## 当前状态[\s\S]*## 核心知识[\s\S]*## 任务[\s\S]*## 时间线/, `module ${id} should preserve the core roadmap sections`);
    assert.doesNotMatch(moduleMarkdown, /## 资源|## 反思|## 面试表达|## 验收标准|## 下一步/, `module ${id} should not keep old side-note or project-management sections`);
  }
  if (id === "agent-design") {
    assert.match(moduleMarkdown, /status: learning[\s\S]*learning_progress: 0/, "agent design should be learning without claiming completion");
    assert.match(moduleMarkdown, /Production Agent Architecture Layers/, "agent design should record the four-layer architecture gap");
  }
  if (id === "behavioral-strategy") {
    assert.match(moduleMarkdown, /status: learning[\s\S]*learning_progress: 0/, "behavioral strategy should be learning without claiming independent readiness");
  }
  if (id === "evals-debugging") {
    assert.match(moduleMarkdown, /status: learning[\s\S]*learning_progress: 0/, "evals should be learning without claiming independent readiness");
    assert.match(moduleMarkdown, /input[\s\S]*expected[\s\S]*actual[\s\S]*assertion[\s\S]*metric[\s\S]*evidence/, "the D2 eval note should retain the six-part case anatomy");
  }
}

execFileSync(process.execPath, [buildScriptUrl.pathname], { stdio: "pipe" });

const html = readFileSync(foundationsPageUrl, "utf8");
const css = readFileSync(cssUrl, "utf8");
const js = readFileSync(jsUrl, "utf8");
const codeListingJs = readFileSync(codeListingJsUrl, "utf8");
const data = JSON.parse(readFileSync(dataUrl, "utf8"));
const packageJson = JSON.parse(readFileSync(packageJsonUrl, "utf8"));

const foundationsTestScript = packageJson.scripts?.["test:foundations"] ?? "";
for (const testFile of [
  "foundations-annotation-model.mjs",
  "foundations-code-listing-model.mjs",
  "foundations-knowledge-article-parser.mjs",
  "foundations-knowledge-content-requirements.mjs",
  "foundations-roadmap-requirements.mjs",
]) {
  assert.match(foundationsTestScript, new RegExp(testFile.replaceAll(".", "\\.")), `Pages CI should run ${testFile}`);
}
assert.match(foundationsTestScript, /git diff --exit-code -- projects\/foundations\/roadmap\/roadmap-data\.json/, "Foundations tests should reject stale generated roadmap data");
assert.match(packageJson.scripts?.["test:all"] ?? "", /npm run test:foundations/, "the Pages test entrypoint should include Foundations tests");

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
assert.match(css, /--knowledge-heading-font:\s*"Kaiti SC",\s*STKaiti,\s*KaiTi/, "knowledge articles should use the approved heading font stack");
assert.match(css, /--knowledge-body-font:\s*"Songti SC",\s*STSong/, "knowledge articles should use the approved body font stack");
assert.match(css, /\.knowledge-article-title\s*\{[\s\S]*font-size:\s*38px/, "knowledge articles should use the fixed desktop title size");
assert.match(css, /\.module-section\s+\.knowledge-article-title\s*\{[\s\S]*font-size:\s*38px/, "knowledge article titles should outrank generic module h3 styling on desktop");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.module-section\s+\.knowledge-article-title\s*\{[\s\S]*font-size:\s*32px/, "knowledge article titles should retain the fixed mobile title size");
assert.match(css, /\.knowledge-article-section\.is-definition/, "knowledge articles should style definition sections");
assert.match(css, /\.knowledge-article-section\.is-mechanism\s+ol/, "knowledge articles should style mechanism steps");
const mechanismItemRule = css.match(/\.knowledge-article-section\.is-mechanism li\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
const mechanismMarkerRule = css.match(/\.knowledge-article-section\.is-mechanism li::before\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
assert.match(mechanismItemRule, /position:\s*relative/, "mechanism text should retain normal document flow");
assert.match(mechanismItemRule, /padding-inline-start:\s*54px/, "mechanism steps should reserve marker space with padding");
assert.doesNotMatch(mechanismItemRule, /display:\s*(grid|flex)|grid-template-columns/, "mechanism text should not become a second grid column");
assert.match(mechanismMarkerRule, /position:\s*absolute/, "mechanism markers should not participate in text layout");
assert.match(mechanismMarkerRule, /inset-inline-start:\s*0/, "mechanism markers should remain at the start edge");
assert.match(css, /@font-face\s*\{[\s\S]*font-family:\s*"IBM Plex Mono"/, "code should use a locally declared IBM Plex Mono face");
assert.match(css, /\.knowledge-article-section-body code:not\(pre code\)/, "inline code should be styled separately from fenced code");
assert.match(css, /\.code-listing\s*\{/, "fenced code should render as one listing frame");
assert.match(css, /\.code-listing-header\s*\{/, "code listings should expose a compact header");
assert.match(css, /\.code-listing-gutter\s*\{/, "long code listings should support a line-number gutter");
const listingCodeRule = css.match(/\.code-listing pre > code\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
assert.match(listingCodeRule, /border:\s*0/, "code content should not add a second frame");
assert.match(listingCodeRule, /background:\s*transparent/, "code content should inherit the listing surface");
assert.match(css, /\.hljs-keyword/, "code listings should expose restrained syntax roles");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.code-listing-copy/, "copy controls should retain a mobile rule");
assert.match(css, /\.knowledge-article-section\.is-flow\s+ol/, "knowledge articles should style process flows");
const desktopFlowRule = css.match(/\.knowledge-article-section\.is-flow\s+ol\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
assert.match(desktopFlowRule, /grid-auto-flow:\s*column/, "desktop knowledge flows should keep every step in one row");
assert.match(desktopFlowRule, /grid-auto-columns:\s*minmax\(120px,\s*1fr\)/, "desktop knowledge flow steps should retain stable minimum widths");
assert.doesNotMatch(desktopFlowRule, /auto-fit|auto-fill/, "desktop knowledge flows should not wrap with auto-fit grids");
assert.match(css, /\.annotation-category-select/, "knowledge articles should preserve the annotation category selector contract");
assert.match(css, /\.local-annotation-category/, "knowledge articles should style the Task 5 annotation category select");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.knowledge-article-section\.is-flow\s+ol/, "knowledge process flows should stack on mobile");
assert.doesNotMatch(css, /\.knowledge-card\s*\{/, "roadmap CSS should not retain legacy knowledge cards");
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
assert.match(css, /\.legacy-annotation-archive\s*\{[\s\S]*padding:\s*14px 0 0/, "legacy annotation archive should remain a compact module section");
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
const tabletMediaStart = css.indexOf("@media (max-width: 1100px)");
const mobileMediaStart = css.indexOf("@media (max-width: 860px)", tabletMediaStart);
const tabletMediaRules = css.slice(tabletMediaStart, mobileMediaStart);
assert.ok(tabletMediaStart >= 0 && mobileMediaStart > tabletMediaStart, "tablet and mobile breakpoints should remain distinct");
assert.match(tabletMediaRules, /\.mobile-note-drawer\s*\{[\s\S]*position:\s*fixed/, "tablet rules should activate the note drawer without changing the main shell breakpoint");
assert.match(tabletMediaRules, /\.reader-shell\.is-mobile-note-open \.mobile-note-drawer\s*\{[\s\S]*display:\s*block/, "tablet rules should expose the opened note drawer");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "roadmap reader should avoid oversized card radii");

assert.match(js, /fetchJson\(ROADMAP_DATA_SOURCE\)/, "shared reader should load the generated JSON source supplied by its page");
assert.match(js, /function renderModuleNav/, "roadmap JS should isolate module navigation rendering");
assert.match(js, /function renderCurrentModule/, "roadmap JS should isolate module content rendering");
assert.match(js, /import \{ enhanceCodeListings \} from "\.\/code-listing\.js"/, "roadmap JS should import the code listing enhancer");
assert.match(js, /renderCurrentModule\(\);[\s\S]*enhanceCodeListings\(els\.sectionList\);[\s\S]*renderMermaidDiagrams/, "code listings should enhance before Mermaid starts");
assert.match(js, /closest\("\[data-annotation-exclude\]"\)/, "annotation text should exclude listing controls and line numbers");
assert.doesNotMatch(js, /range\.startContainer !== range\.endContainer/, "annotations should support selections across syntax spans");
assert.match(js, /function getTextOffset/, "annotation selection should resolve absolute text offsets");
assert.match(js, /function getTextPosition/, "annotation restoration should map offsets back to text nodes");
assert.match(js, /const combinedText = nodes\.map/, "annotation restoration should search across syntax nodes");
assert.match(js, /mark\.replaceWith\(\.\.\.mark\.childNodes\)/, "clearing a highlight should preserve nested syntax spans");
assert.match(codeListingJs, /classList\.contains\("language-mermaid"\)/, "the listing enhancer should leave Mermaid blocks untouched");
assert.match(codeListingJs, /dataset\.annotationExclude = "true"/, "listing chrome should stay outside annotation text");
assert.match(codeListingJs, /lineCount >= 4/, "line numbers should start at the four-line threshold");
assert.match(codeListingJs, /COPY_RESET_DELAY_MS = 1500/, "copy feedback should reset without changing button geometry");
assert.match(codeListingJs, /cancelSchedule = globalThis\.clearTimeout/, "copy feedback should support cancelling an earlier reset");
assert.match(codeListingJs, /const copyAttempt = \+\+copyAttemptVersion/, "copy feedback should let the latest activation own the visible state");
assert.match(codeListingJs, /cancelSchedule\(resetTimerId\)/, "copy feedback should cancel an earlier reset before starting a new attempt");
assert.match(js, /function renderOverviewDashboard/, "roadmap JS should render overview as a dashboard");
assert.match(js, /\["Interview Signal",\s*getSection\(module, "Interview Signal"\)\]/, "overview dashboard should render the interview signal section");
assert.match(js, /stableModules = learningModules\.filter\(\(item\) => item\.id !== "interview-sprint"\)/, "overview dashboard should keep sprint out of the stable module count");
assert.match(js, /String\(stableModules\.length\)/, "overview dashboard should count stable modules instead of temporary sprint modules");
assert.match(js, /function renderKnowledgeNotesSection/, "roadmap JS should render concept-centric knowledge notes");
assert.match(js, /function renderKnowledgeArticleSection/);
assert.match(js, /class="knowledge-article"/);
assert.match(js, /knowledge-article-title/);
assert.match(js, /knowledge-article-section is-\$\{escapeHtml\(section\.kind\)\}/);
assert.match(js, /const mainSections = \["目标", "当前状态", "核心知识", "任务", "时间线", "学习记录", "知识笔记"\]/);
assert.match(js, /function getKnowledgeArticleForTarget/);
assert.match(js, /entry\.articleTitle/);
assert.match(js, /MERMAID_MODULE_URL = "https:\/\/cdn\.jsdelivr\.net\/npm\/mermaid@11\.12\.2\/dist\/mermaid\.esm\.min\.mjs"/);
assert.match(js, /async function renderMermaidDiagrams/);
assert.match(js, /moduleRenderVersion:\s*0,/, "reader state should initialize a monotonically increasing module render version");
assert.match(js, /navigationVersion:\s*0,/, "reader state should track same-module navigation intent separately from rendering");
assert.match(js, /const moduleRenderVersion = \+\+state\.moduleRenderVersion;/, "each module open should capture a new render version");
assert.match(js, /const navigationVersion = \+\+state\.navigationVersion;/, "each module open should establish a fresh navigation intent");
assert.match(js, /renderMermaidDiagrams\(\)\.then\(\(\) => \{[\s\S]*if \(state\.moduleRenderVersion !== moduleRenderVersion\) return;[\s\S]*applyHighlights\(\);[\s\S]*observeSections\(\);[\s\S]*if \(targetSectionId\)/, "Mermaid completion should accept only its exact module render version");
assert.match(js, /state\.navigationVersion !== navigationVersion/, "Mermaid completion should not restore a target after later same-module navigation");
assert.match(js, /state\.activeSectionId === targetSectionId/, "Mermaid completion should only restore the still-active target");
assert.match(js, /function invalidateDeferredNavigation/, "reader interactions should invalidate delayed navigation restoration");
assert.match(js, /const KEYBOARD_NAVIGATION_KEYS = new Set/, "reader should define keyboard scrolling inputs that cancel delayed navigation");
assert.match(js, /KEYBOARD_NAVIGATION_KEYS\.has\(event\.key\) && !isTextEntryTarget\(event\.target\)/, "keyboard scrolling should cancel delayed navigation without intercepting text entry");
assert.doesNotMatch(js, /openedModuleId|state\.currentModule\?\.id !== openedModuleId/, "Mermaid completion should not rely on module identity alone");
assert.doesNotMatch(js, /note\?\.groups/);
assert.doesNotMatch(js, /note\?\.body/);
assert.doesNotMatch(js, /这个模块还没有知识笔记/);
assert.match(js, /function renderContextualNotePanel/, "roadmap JS should render context-aware right notes");
assert.match(js, /function setActiveKnowledgeContext/, "roadmap JS should sync right notes with active knowledge context");
assert.match(js, /function renderLegacyAnnotationArchive/, "roadmap JS should render a concise center archive explanation");
assert.match(js, /原文高亮无法恢复/, "legacy archive copy should explain the lost source highlighting explicitly");
assert.match(js, /选中文本与笔记已完整保留/, "legacy archive copy should confirm preserved annotation content");
assert.match(js, /function getArchivedAnnotations/, "roadmap JS should identify archived records per module");
assert.match(js, /getArchivedAnnotations\(module\.id\)\.length > 0/, "archive sections should only appear for modules with archived annotations");
assert.match(js, /title:\s*"历史笔记"/, "modules with archived records should expose a section-rail target");
assert.match(js, /function renderArchivedAnnotations/, "the right panel should render archived highlights as well as written notes");
assert.match(js, /function renderActiveContextualNotePanel/, "annotation edits should preserve the active article or archive panel");
assert.match(js, /function updateAnnotationCategory[\s\S]*renderActiveContextualNotePanel\(\);/, "category changes should keep archived annotations visible");
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
assert.match(js, /const remainingScroll = els\.main\.scrollHeight - els\.main\.clientHeight - els\.main\.scrollTop;[\s\S]*remainingScroll <= 64/, "the final short section should become active near the reader bottom despite browser scroll rounding");
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
assert.match(js, /const note = getKnowledgeArticleForTarget\(module, sectionId\);/, "knowledge article sections should map back to their parent article");
assert.match(js, /const renderedNotes = archived \? renderArchivedAnnotations\(module\) : renderLocalAnnotations\(note\);/, "right note panel should render local annotations only for an explicit article or archive target");
assert.match(js, /const railSectionId = article\?\.id \?\? sectionId;/, "nested article sections should keep the parent article active in the rail");
assert.match(js, /renderContextualNotePanel\(null\);/, "module switches should start with an empty right note panel");
assert.doesNotMatch(js, /renderContextualNotePanel\(nextModule\.knowledgeNotes\?\.\[0\]\);/, "module switches should not default the right panel to the first knowledge note");
assert.match(html, /data-project-id="foundations"/, "Foundations should identify its local reader state");
assert.match(js, /const PROJECT_ID = document\.body\.dataset\.projectId \?\? "foundations";/, "shared reader should default to the Foundations project id");
assert.match(js, /const ANNOTATION_STORAGE_KEY = `\$\{PROJECT_ID\}Reader\.annotations\.v1`;/, "shared reader should define project-scoped annotation storage");
assert.match(js, /const ROADMAP_DATA_SOURCE = READER_SCRIPT\?\.dataset\.source \?\? "roadmap\/roadmap-data\.json";/, "shared reader should accept the page data source");
assert.match(js, /function createEmptyAnnotationStore/, "Foundations reader should create an empty annotation store");
assert.match(js, /function loadAnnotations/, "Foundations reader should load local annotations from localStorage");
assert.match(js, /function saveAnnotations/, "Foundations reader should save local annotations to localStorage");
assert.match(js, /annotationPersistenceAllowed:\s*true,/, "reader state should track whether annotation writes are safe");
assert.match(js, /function saveAnnotations[\s\S]*if \(!state\.annotationPersistenceAllowed\) return;/, "every annotation write should honor recovery mode, not only initialization");
assert.match(js, /function getAnnotationsForNote/, "Foundations reader should filter annotations by module and knowledge note");
assert.match(js, /function createAnnotationFromSelection/, "Foundations reader should create annotations from selected knowledge-article text");
assert.match(js, /function applyHighlights/, "Foundations reader should restore highlights inside knowledge articles");
assert.match(js, /function updateAnnotationNote/, "Foundations reader should update local study-note text");
assert.match(js, /function deleteAnnotation/, "Foundations reader should support deleting highlights and annotations");
assert.match(js, /from "\.\/annotation-model\.js"/, "Foundations reader should import the annotation model");
assert.match(js, /const annotationLoad = loadAnnotations\(\);[\s\S]*migrateLegacyAnnotations\(annotationLoad\.store, state\.data\.modules\)/, "reader init should migrate annotations after current article data loads");
assert.match(js, /state\.annotations = migratedAnnotations;[\s\S]*saveAnnotations\(migratedAnnotations\);/, "reader init should persist migrated records to the same v1 store");
assert.match(js, /if \(annotationLoad\.canPersist\) saveAnnotations\(migratedAnnotations\);/, "reader init should not overwrite malformed or unreadable local annotation data");
assert.match(js, /state\.annotationPersistenceAllowed = annotationLoad\.canPersist;/, "reader init should keep failed-load persistence disabled for later edits");
assert.match(js, /function updateAnnotationCategory/, "Foundations reader should update annotation categories");
assert.match(js, /data-annotation-category/, "Foundations reader should render annotation category controls");
assert.match(js, /groupAnnotations\(annotations\)/, "Foundations reader should group active local annotations");
assert.doesNotMatch(js, /noteGroups/, "Foundations reader should not render legacy note groups");
assert.doesNotMatch(js, /note\?\.body/, "Foundations reader should not render fallback article copy");
assert.doesNotMatch(js, /面试表达/, "Foundations reader should not render legacy interview-expression copy");
assert.match(js, /\.knowledge-article/, "annotation selection should be scoped to knowledge articles");
assert.doesNotMatch(js, /knowledge-card/, "roadmap JS should not retain legacy knowledge-card selectors");
assert.match(js, /data-note-id/, "annotations should anchor to stable knowledge note ids");
assert.match(js, /高亮/, "selection toolbar should expose a highlight action");
assert.match(js, /笔记/, "selection toolbar should expose a note action");
assert.match(js, /只删除高亮，保留笔记/, "delete confirmation should allow keeping the note");
assert.match(js, /高亮和笔记一起删除/, "delete confirmation should allow deleting both highlight and note");
assert.doesNotMatch(js, /PROJECT_ID = "brain-memory-for-ai-agents"|paperReader\.annotations\.v1/, "Foundations annotations should not reuse paper-reader project state");
assert.doesNotMatch(js, /githubToken|Authorization|contents\/|repos\/|gitHub|fetch\(\"\/api/i, "Foundations annotations should not write to GitHub or backend APIs");
assert.doesNotMatch(js, /embeddings\.json|cosineSimilarity|PROJECT_ID = "brain-memory-for-ai-agents"/, "Foundations reader JS should not reuse paper-specific semantic search state");
assert.match(js, /els\.toggleNote\.addEventListener\("click", \(\) => \{[\s\S]*matchMedia\("\(max-width: 1100px\)"\)/, "note-toggle JS should use the same tablet breakpoint as the drawer CSS");
assert.match(js, /els\.toggleLeftControls\.forEach\([\s\S]*matchMedia\("\(max-width: 860px\)"\)/, "left navigation should keep the one-column mobile breakpoint at 860px");

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
  }
  assert.ok(Array.isArray(module.searchEntries), `${module.id} should include section-level search entries`);
  assert.ok(module.searchEntries.length > 0, `${module.id} should expose searchable sections`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should point back to the module`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.sectionTitle === "string" && entry.sectionTitle.length > 0), `${module.id} search entries should include section titles`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.articleTitle === "string"), `${module.id} search entries should include article titles`);
  assert.ok(module.searchEntries.filter((entry) => entry.type === "section").every((entry) => entry.articleTitle === ""), `${module.id} ordinary section entries should have no article title`);
  assert.ok(module.searchEntries.every((entry) => typeof entry.text === "string" && entry.text.length > 20), `${module.id} search entries should include useful text`);
  assert.ok(Array.isArray(module.knowledgeNotes), `${module.id} should include knowledge notes`);
  assert.ok(module.knowledgeNotes.every((note) => typeof note.id === "string" && note.id.startsWith(module.id)), `${module.id} knowledge notes should have stable ids`);
  assert.ok(module.knowledgeNotes.every((note) => typeof note.title === "string" && note.title.length > 0), `${module.id} knowledge notes should include titles`);
  assert.ok(Array.isArray(module.timeline), `${module.id} should include a timeline array`);
}

const byId = Object.fromEntries(data.modules.map((module) => [module.id, module]));
assert.ok(byId["agent-design"].timeline.length >= 3, "agent design should expose timeline items for visual rendering");
assert.equal(byId["interview-sprint"].status, "in-progress", "interview sprint should be marked as the active seven-day sprint");
assert.equal(byId["interview-sprint"].timeline.length, 7, "interview sprint should expose a D1-D7 cockpit timeline");
assert.equal(byId["interview-sprint"].timeline[0].status, "done", "interview sprint should mark D1 as completed");
assert.equal(byId["interview-sprint"].timeline[1].status, "done", "interview sprint should mark D2 coached learning as completed");
assert.ok(byId["interview-sprint"].timeline.slice(2).every((item) => item.status === "open"), "interview sprint should keep D3-D7 open after D2");
assert.match(byId["interview-sprint"].searchText, /Agent Eval|Python 容器|Context Engineering|parallel post-test/, "interview sprint should preserve the reprioritized seven-day schedule");
assert.deepEqual(byId.coding.knowledgeNotes.map((note) => note.title), ["deque、stack 与 queue", "单调队列"]);
assert.deepEqual(byId["evals-debugging"].knowledgeNotes.map((note) => note.title), [
  "Eval Case 的六层结构",
  "Benchmark 与 Agent Behavior Eval",
]);
for (const id of ["interview-sprint", "agent-design", "llm-systems", "rag-memory", "research-reading", "behavioral-strategy", "logs"]) {
  assert.equal(byId[id].knowledgeNotes.length, 0, `${id} should not expose shallow knowledge notes`);
}
for (const id of ["coding", "evals-debugging"]) {
  for (const article of byId[id].knowledgeNotes) {
    assert.equal(typeof article.intro, "string");
    assert.ok(Array.isArray(article.sections));
    assert.deepEqual(
      article.sections.filter((section) => ["definition", "mechanism", "example", "boundary", "summary"].includes(section.kind)).map((section) => section.kind),
      ["definition", "mechanism", "example", "boundary", "summary"],
    );
  }
}
assert.equal(Object.hasOwn(byId["interview-sprint"].sections, "学习记录"), true);
assert.equal(Object.hasOwn(byId["interview-sprint"].sections, "知识笔记"), false);
assert.ok(byId.coding.searchEntries.some((entry) => (
  entry.type === "knowledge-section" && entry.articleTitle === "单调队列" && entry.sectionTitle === "核心机制"
)));
assert.match(byId.overview.searchText, /30\/45\/60-Day Plan|Project Recommendations|Weekly Review Checklist/, "overview should preserve timeline and project recommendation content");
assert.match(byId.overview.searchText, /Interview Signal|真实 baseline|Agent system design mock/, "overview should preserve interview signal calibration content");
assert.match(byId.coding.searchText, /Coding Plan|Python Standards|TypeScript Standards|Optional Rust Log Parser/, "coding should preserve implementation training content");
assert.match(byId["llm-systems"].searchText, /LLM Systems|Transformer|post-training|LLM Fundamentals/, "LLM systems should preserve model and theory content");
assert.match(byId["agent-design"].searchText, /Agent Systems|Agent Runtime With Tool Calling|Safe Tool Execution Layer|Tool Router/, "agent design should preserve agent runtime content");
assert.match(byId["rag-memory"].searchText, /RAG And Memory|Production RAG System|Long-Term Memory|Retrieval Evaluator|Memory Store/, "RAG and memory should preserve retrieval and memory content");
assert.match(byId["evals-debugging"].searchText, /Eval And Debugging|Eval Harness|Trace Debugging|Agent Trace Logger/, "evals should preserve eval and trace content");
assert.match(byId["evals-debugging"].searchText, /Eval Case Anatomy|positive assertions|P95|time-to-availability/, "evals should expose the D2 coached case-audit knowledge");
assert.match(byId["research-reading"].searchText, /Research Reading List|scaling laws|RLHF|RLAIF|RLVR/, "research reading should preserve reading list content");
assert.match(byId["behavioral-strategy"].searchText, /Behavioral And Project Deep Dive|Strategy Rubric|STAR|tradeoff/, "behavioral strategy should preserve interview strategy content");
assert.match(byId.logs.searchText, /Weekly Review|review checklist|复盘/, "logs should preserve review and reflection content");
