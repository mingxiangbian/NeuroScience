import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { buildKnowledgeGraph } from "../projects/finance/scripts/build-roadmap-data.mjs";
import { getRenderableSectionTitles } from "../projects/foundations/roadmap/reader-state-model.js";

const financePageUrl = new URL("../projects/finance/index.html", import.meta.url);
const financeThemeUrl = new URL("../projects/finance/finance-theme.css", import.meta.url);
const financeReadmeUrl = new URL("../projects/finance/README.md", import.meta.url);
const financeBuildUrl = new URL("../projects/finance/scripts/build-roadmap-data.mjs", import.meta.url);
const financeDataUrl = new URL("../projects/finance/roadmap/roadmap-data.json", import.meta.url);
const financeModulesUrl = new URL("../projects/finance/roadmap/modules/", import.meta.url);
const originalGuideUrl = new URL("../projects/finance/investment_beginner_guide_zh.md", import.meta.url);
const sharedReaderUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);
const packageUrl = new URL("../package.json", import.meta.url);

const expectedModules = [
  ["overview", "学习总览"],
  ["investment-basics", "投资的本质与前提"],
  ["asset-classes", "资产类别"],
  ["risk-allocation", "风险与配置"],
  ["fund-company-analysis", "基金与公司分析"],
  ["valuation", "估值"],
  ["trading-execution", "交易与执行"],
  ["behavior-process", "行为与流程"],
  ["study-plan-tools", "学习计划与工具"],
  ["terms-further-reading", "术语速查与延伸"],
];

assert.equal(existsSync(financePageUrl), true, "finance should expose a static reader page");
assert.equal(existsSync(financeBuildUrl), true, "finance should expose a roadmap data builder");
assert.equal(existsSync(financeDataUrl), true, "finance should expose generated roadmap data");
assert.equal(existsSync(originalGuideUrl), false, "the monolithic guide should be replaced by modules");
assert.equal(existsSync(financeThemeUrl), true, "finance should expose a project-scoped gold theme");
assert.equal(existsSync(financeReadmeUrl), true, "finance should document its use and privacy boundary");

let sourceDisplayMathCount = 0;
let sourceInlineMathCount = 0;
for (const [id] of expectedModules) {
  const moduleUrl = new URL(`${id}.md`, financeModulesUrl);
  assert.equal(existsSync(moduleUrl), true, `finance should keep ${id}.md as source content`);
  const source = readFileSync(moduleUrl, "utf8");
  sourceDisplayMathCount += [...source.matchAll(/\\\[[\s\S]*?\\\]/g)].length;
  sourceInlineMathCount += [...source.matchAll(/\\\([^\n]*?\\\)/g)].length;
}

const financeHtml = readFileSync(financePageUrl, "utf8");
const financeTheme = readFileSync(financeThemeUrl, "utf8");
const financeReadme = readFileSync(financeReadmeUrl, "utf8");
const builder = readFileSync(financeBuildUrl, "utf8");
const data = JSON.parse(readFileSync(financeDataUrl, "utf8"));
const sharedReader = readFileSync(sharedReaderUrl, "utf8");
const packageJson = JSON.parse(readFileSync(packageUrl, "utf8"));
const closeSearchSource = sharedReader.match(/function closeSearchModal\(\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
const sourceBetween = (startMarker, endMarker) => {
  const start = sharedReader.indexOf(startMarker);
  const end = sharedReader.indexOf(endMarker, start + startMarker.length);
  return start >= 0 && end > start ? sharedReader.slice(start, end) : "";
};
const financeOverviewSource = sourceBetween("function renderFinanceOverviewDashboard", "function getFinanceGraphContext");
const tableEnhancementSource = sourceBetween("function enhanceFinanceTables", "function renderMathExpressions");
const openModuleSource = sourceBetween("function openModule", "function openSearchModal");
const mobileNoteSource = sourceBetween("function setMobileNoteOpen", "function setMobileDirectoryOpen");
const mobileDirectorySource = sourceBetween("function setMobileDirectoryOpen", "function closeMobileDrawers");
const mobileFocusTrapSource = sourceBetween("function trapMobileDrawerFocus", "function bindEvents");
const escapeKeySource = sharedReader.slice(
  sharedReader.indexOf('if (event.key === "Escape")'),
  sharedReader.indexOf("\n  });", sharedReader.indexOf('if (event.key === "Escape")')),
);
const renderedSectionHtml = data.modules.flatMap((module) => Object.values(module.sections ?? {})).join("\n");

assert.equal(
  packageJson.scripts["test:finance"],
  "node projects/finance/scripts/build-roadmap-data.mjs && node tests/finance-learning-reader-requirements.mjs && git diff --exit-code -- projects/finance/roadmap/roadmap-data.json",
  "Finance tests should rebuild canonical Markdown data before validation and reject stale generated JSON afterward",
);
assert.match(packageJson.scripts["test:all"], /npm run test:finance/, "the complete suite should retain the Finance freshness gate");

assert.match(financeHtml, /<title>投资 \| NeuroScience x AI<\/title>/, "finance page should use the project title");
assert.match(financeHtml, /data-page="finance-roadmap-reader"/, "finance page should identify the reader");
assert.match(financeHtml, /data-project-id="finance"/, "finance annotations should be project-scoped");
assert.match(financeHtml, /data-theme="dark"/, "finance should default to the approved dark research cockpit");
assert.match(financeHtml, /data-annotation-scope="all-content"/, "finance should allow annotations throughout module content");
assert.match(financeHtml, /localStorage\.getItem\("financeReader\.theme\.v1"\)/, "finance should restore its own theme before first paint");
assert.match(financeHtml, /src="\.\.\/foundations\/roadmap\/roadmap-reader\.js"/, "finance should reuse the maintained reader");
assert.match(financeHtml, /data-source="roadmap\/roadmap-data\.json"/, "finance reader should load finance-generated data");
assert.match(financeHtml, /katex@0\.16\.11\/dist\/katex\.min\.css/, "finance should load the established KaTeX stylesheet");
assert.match(financeHtml, /katex@0\.16\.11\/dist\/katex\.min\.js/, "finance should load the established KaTeX renderer before the shared reader");
assert.match(financeHtml, /href="\.\.\/index\.html" aria-label="返回项目"/, "finance should return to the project directory");
const sharedCssIndex = financeHtml.indexOf('../foundations/roadmap/roadmap-reader.css');
const financeThemeIndex = financeHtml.indexOf('finance-theme.css');
assert.ok(sharedCssIndex >= 0 && financeThemeIndex > sharedCssIndex, "finance theme should load after shared reader CSS");
assert.match(financeHtml, /class="directory-kicker">学习路径<\/p>/, "finance directory chrome should use Chinese copy");
assert.match(financeHtml, /id="note-rail-toggle"/, "finance should expose the compact desktop annotation rail");
assert.match(financeHtml, /id="note-count"[^>]*aria-label="0 条批注"/, "finance annotation rail should expose an accessible count");
assert.match(financeHtml, /id="mobile-note-drawer"[^>]*role="dialog"[^>]*aria-modal="true"/, "finance should expose a modal mobile annotation drawer");
assert.match(sharedReader, /popover\.setAttribute\("aria-modal", "true"\)/, "mobile annotation deletion should become the top modal layer");
assert.match(sharedReader, /els\.mobileNoteDrawer\.removeAttribute\("aria-modal"\)/, "mobile annotation deletion should suspend the underlying drawer modal semantics");
assert.match(sharedReader, /wasMobileModalLayer[\s\S]*mobileNoteDrawer\?\.setAttribute\("aria-modal", "true"\)/, "closing annotation deletion should restore the drawer modal semantics");
assert.match(financeHtml, /id="close-mobile-note"/, "finance mobile annotation drawer should have an explicit close control");
assert.match(financeHtml, /id="drawer-backdrop"/, "finance mobile drawers should expose a dismissible backdrop");
assert.match(financeHtml, /id="reader-announcer"[^>]*aria-live="polite"/, "finance interactions should expose a polite live region");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]/, "finance theme should be page-scoped");
assert.match(financeTheme, /oklch\(/, "finance theme should use the approved perceptual color space");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]\[data-theme="dark"\]\s*\{[\s\S]*--fin-current-text:\s*var\(--fin-gold-light\);[\s\S]*--fin-info:\s*var\(--fin-steel-light\);[\s\S]*--fin-gain:\s*var\(--fin-gain-light\);[\s\S]*--fin-loss:\s*var\(--fin-loss-light\);/, "dark finance theme should reserve brass, steel, green, and red for their approved semantics");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]\[data-theme="light"\]\s*\{[\s\S]*--fin-current-text:\s*var\(--fin-gold-deep\);[\s\S]*--fin-info:\s*var\(--fin-steel-deep\);[\s\S]*--fin-gain:\s*var\(--fin-gain-deep\);[\s\S]*--fin-loss:\s*var\(--fin-loss-deep\);/, "light finance theme should retain the same semantic color roles on ink-white surfaces");
assert.match(financeTheme, /--reader-panel-blur:\s*none/, "finance should use solid surfaces instead of inherited glass blur");
assert.doesNotMatch(financeTheme, /(?:linear|radial|conic)-gradient\(/, "finance luxury styling should not depend on decorative gradients");
assert.deepEqual(
  [...financeTheme.matchAll(/(?:^|\s)(?:-webkit-)?backdrop-filter:\s*([^;\n]+)/gm)]
    .map((match) => match[1].trim())
    .filter((value) => value !== "none"),
  [],
  "finance should not use active glass blur",
);
assert.match(financeTheme, /::selection\s*\{[\s\S]*background:\s*var\(--fin-selection-bg\)/, "finance should explicitly theme browser text selection");
assert.match(financeTheme, /::-moz-selection\s*\{[\s\S]*background:\s*var\(--fin-selection-bg\)/, "finance should theme text selection in Firefox as well");
assert.match(financeTheme, /\.toolbar-search:focus-within/, "finance search should expose a visible focus state");
assert.match(financeTheme, /\.reader-shell\.is-note-collapsed\s*\{[\s\S]*grid-template-columns:\s*228px minmax\(0, 1fr\) 48px/, "finance desktop should collapse annotations to a 48px rail");
assert.match(financeTheme, /\.finance-knowledge-map/, "finance should style the primary concept dependency map");
assert.match(financeTheme, /\.finance-map-stage\s*\{[\s\S]*position:\s*relative/, "finance map stage should anchor its SVG overlay");
assert.match(financeTheme, /\.finance-map-edge-layer\s*\{[\s\S]*position:\s*absolute/, "finance dependency edges should overlay the node layout");
assert.match(financeTheme, /\.finance-map-inspector/, "finance should style the fixed decision-use inspector");
assert.match(financeTheme, /\.finance-data-table\s*\{[\s\S]*min-width:\s*680px/, "finance data tables should retain terminal-like desktop density");
assert.match(financeTheme, /\.finance-table-scroll\s*\{[\s\S]*overflow:\s*auto/, "finance tables should own overflow locally");
assert.match(financeTheme, /@media \(max-width:\s*1100px\)/, "finance should adapt its note panel and map before tablet widths");
assert.match(financeTheme, /@media \(max-width:\s*860px\)/, "finance should switch to the mobile reading shell at the shared breakpoint");
assert.match(financeTheme, /@media \(max-width:\s*480px\)/, "finance should have a narrow-toolbar layout");
assert.match(financeTheme, /grid-template-rows:\s*auto auto/, "narrow finance toolbar should use two rows");
assert.match(financeTheme, /width:\s*44px[\s\S]*height:\s*44px/, "narrow finance controls should expose 44px targets");
assert.doesNotMatch(financeTheme, /#2e704d|rgba\(46,\s*112,\s*77|rgba\(152,\s*217,\s*166/, "finance theme should not retain the inherited visible green palette");
assert.match(financeReadme, /本地批注只保存在当前浏览器/, "README should explain annotation persistence");
assert.match(financeReadme, /不保存持仓、交易、账户或个人财务信息/, "README should preserve the public privacy boundary");
assert.ok(data.modules[0].sections["学习导航"], "finance overview should expose the Chinese navigation section");
assert.equal(data.modules[0].sections.Dashboard, undefined, "finance should not retain the visible Dashboard heading");
assert.match(builder, /throw new Error/, "finance builder should reject malformed modules");
assert.match(sharedReader, /function renderFinanceOverviewDashboard\(module\)[\s\S]*?getFinanceReentryState\(learningModules\)/, "finance dashboard should consume the tested re-entry view state");
assert.match(sharedReader, /financeReentry\.nextStepLabel/, "finance dashboard should render the tested all-complete copy");
assert.match(sharedReader, /getStatusLabel\(financeReentry\.status\)/, "finance dashboard should render the tested re-entry status");
assert.match(sharedReader, /PROJECT_ID\s*!==\s*"finance"/, "finance metadata should hide redundant raw priority");
assert.match(sharedReader, /PROJECT_ID === "finance" \? "未找到结果" : "No results found"/, "finance empty search results should use Chinese copy");
assert.match(sharedReader, /模块正文均可批注。选中文字即可添加本地高亮或笔记；批注只保存在当前浏览器。/, "empty note panels should explain the all-content annotation boundary");
assert.match(sharedReader, /data-annotation-context=/, "finance module sections should expose stable annotation contexts");
const overviewModule = data.modules.find((module) => module.id === data.project.dashboardModuleId);
for (const overviewSectionId of Object.values(overviewModule.sectionIds)) {
  assert.match(financeOverviewSource, new RegExp(`id="${overviewSectionId}"[\\s\\S]*data-section-id="${overviewSectionId}"`), `${overviewSectionId} should remain a real rail and search target`);
}
assert.match(sharedReader, /function handleAnnotationSelection\(\)[\s\S]*showAnnotationSelectionWarning\(result\.error\.message\)/, "invalid annotation selections should surface a useful warning");
assert.match(sharedReader, /addEventListener\("pointerup"[\s\S]*handleAnnotationSelection/, "pointer selections should open the annotation toolbar");
assert.match(sharedReader, /document\.addEventListener\("selectionchange"/, "long-press and non-mouse selections should be observed");
assert.match(sharedReader, /const ANNOTATION_EXCLUDED_SELECTOR = \[[\s\S]*"a\[href\]"[\s\S]*"label"[\s\S]*"\.knowledge-highlight"/, "annotations should reject links, form labels, and existing interactive highlights");
assert.match(sharedReader, /function rangeContainsExcludedContent\(range\)[\s\S]*selectionContainsExcludedContent\(range\)/, "annotation validation should reject selections that span interactive descendants");
assert.match(sharedReader, /function applyHighlights\(\)[\s\S]*rangeContainsExcludedContent\(range\)/, "restored annotations should never wrap newly interactive content");
assert.match(sharedReader, /data-annotation-manage=/, "every retained annotation should remain manageable from the note panel");
assert.match(sharedReader, /data-anchor-status="\$\{anchorStatus\}"/, "the note panel should expose whether each source anchor still resolves");
assert.match(sharedReader, /原文位置已失效，批注仍保留。/, "unresolved source anchors should remain visible and explain their state");
assert.match(sharedReader, /function deleteAnnotation[\s\S]*returnSurfaceId[\s\S]*remainingManageButtons[\s\S]*els\.closeMobileNote/, "deleting from a note drawer should restore focus inside the remaining active surface");
assert.match(sharedReader, /function updateAnnotationCategory\(annotationId, category, focusSurface\)[\s\S]*focus\(\{ preventScroll: true \}\)/, "changing annotation categories should restore focus after rerendering both note surfaces");
assert.match(sharedReader, /function getReaderScrollOwner/, "finance should resolve the real scrolling container at each breakpoint");
assert.match(sharedReader, /function scrollElementToTopImmediately\(element\)[\s\S]*element\.style\.scrollBehavior = "auto";[\s\S]*element\.scrollTop = 0;/, "module switches should temporarily bypass inherited smooth scrolling");
assert.match(sharedReader, /function resetReaderScroll\(\)[\s\S]*scrollElementToTopImmediately\(owner\);[\s\S]*scrollElementToTopImmediately\(documentOwner\)/, "finance module switches should reset both the real scroll owner and the document owner");
const renderIndex = openModuleSource.indexOf("renderCurrentModule();");
const resetIndex = openModuleSource.indexOf("if (!targetSectionId) resetReaderScroll();");
const mermaidIndex = openModuleSource.indexOf("void renderMermaidDiagrams()");
assert.ok(renderIndex >= 0 && resetIndex > renderIndex && resetIndex < mermaidIndex, "module navigation should reset synchronously before deferred rendering");
assert.match(sharedReader, /setTheme\(document\.body\.dataset\.theme === "dark" \? "light" : "dark", \{ persist: true \}\)/, "theme toggles should persist independently per project");
assert.match(sharedReader, /restoreNotePanelPreference\(\)/, "finance should restore its desktop note-rail preference");
assert.match(sharedReader, /function updateMobileDrawerInert\(\)/, "mobile drawers should share one inert-state coordinator");
assert.match(mobileNoteSource, /classList\.remove\("is-mobile-left-open"\)/, "opening mobile notes should close the directory drawer");
assert.match(mobileDirectorySource, /classList\.remove\("is-mobile-note-open"\)/, "opening the mobile directory should close the note drawer");
assert.match(mobileFocusTrapSource, /state\.annotationDeletePopover[\s\S]*els\.mobileNoteDrawer[\s\S]*els\.sidebar/, "mobile focus trapping should prioritize nested annotation dialogs and cover both drawers");
assert.match(mobileFocusTrapSource, /event\.shiftKey && document\.activeElement === first[\s\S]*document\.activeElement === last/, "mobile drawer focus should loop in both keyboard directions");
assert.match(sharedReader, /new ResizeObserver\(scheduleFinanceKnowledgeMapEdges\)/, "finance dependency edges should redraw when the graph layout changes");
assert.match(sharedReader, /document\.activeElement\?\.closest\?\.\("\.finance-map-inspector"\)/, "pointer hover should not replace an inspector while its action owns focus");
assert.match(sharedReader, /function enhanceFinanceTables\(root\)/, "finance should progressively enhance authored tables");
assert.match(sharedReader, /function getFinanceTableLabel\(table, fallback\)/, "finance tables should derive specific captions from nearby authored headings");
assert.match(tableEnhancementSource, /table\.querySelectorAll\("thead th"\)[\s\S]*columnHeader\.scope = "col";/, "finance table headers should expose column scope");
assert.match(tableEnhancementSource, /table\.querySelectorAll\("tbody tr"\)[\s\S]*document\.createElement\("th"\)[\s\S]*rowHeader\.scope = "row";/, "finance tables should promote the first body cell to an accessible row header");
assert.match(tableEnhancementSource, /const horizontalOverflow = wrapper\.scrollWidth > wrapper\.clientWidth \+ 1;[\s\S]*const verticalOverflow = wrapper\.scrollHeight > wrapper\.clientHeight \+ 1;[\s\S]*horizontalOverflow \|\| verticalOverflow/, "either table overflow axis should expose a keyboard-scrollable region");
assert.match(financeTheme, /@media \(max-width:\s*860px\)[\s\S]*\.finance-table-scroll\s*\{[\s\S]*max-height:\s*none;[\s\S]*overscroll-behavior-block:\s*auto;/, "mobile tables should grow vertically while containing only horizontal overscroll");
assert.match(sharedReader, /function renderMathExpressions\(root = els\.sectionList\)/, "the shared reader should expose a graceful math rendering pass");
assert.match(sharedReader, /window\.katex\?\.renderToString/, "the math rendering pass should reuse the established KaTeX runtime when available");
assert.match(sharedReader, /trust:\s*false/, "KaTeX rendering should reject trusted HTML commands from formula source");
assert.match(sharedReader, /renderCurrentModule\(\);[\s\S]*renderMathExpressions\(els\.sectionList\);/, "math should render after module HTML is mounted");
assert.match(closeSearchSource, /els\.searchResults\.hidden = true;/, "closing search should always hide results");
assert.doesNotMatch(closeSearchSource, /if \(!state\.searchQuery\)/, "closing search should not depend on an empty query");
assert.match(escapeKeySource, /if \(state\.annotationDeletePopover\)[\s\S]*hideAnnotationDeletePopover\(\);[\s\S]*return;/, "Escape should dismiss only the topmost annotation dialog first");
assert.match(escapeKeySource, /if \(searching\)[\s\S]*els\.searchInput\.blur\(\);[\s\S]*closeSearchModal\(\);[\s\S]*return;/, "Escape should blur the search input only while search is open so one click can restore preserved results");
assert.ok(escapeKeySource.indexOf("if (state.annotationDeletePopover)") < escapeKeySource.indexOf("if (drawerOpen)"), "nested annotation dialogs should close before their mobile drawer");
assert.doesNotMatch(sharedReader, /status !== "(?:done|complete)"\) \?\? learningModules\[0\]/, "completed dashboards should not fall back to their first module");

assert.equal(data.project.id, "finance", "generated data should identify the finance project");
assert.equal(data.project.title, "投资", "generated data should use the visible project title");
assert.equal(data.project.dashboardModuleId, "overview", "overview should be the dashboard");
assert.equal(data.project.glossaryModuleId, "terms-further-reading", "dashboard should expose the glossary module");
assert.equal(typeof data.project.dashboardFocus, "string", "dashboard should have a re-entry action");
assert.equal(data.project.overallLearningProgress, 0, "initial finance progress should be zero");
assert.deepEqual(data.modules.map((module) => [module.id, module.title]), expectedModules, "finance modules should follow the approved concept order");

const knowledgeGraph = data.project.knowledgeGraph;
const graphNodeIds = knowledgeGraph.nodes.map((node) => node.id);
const graphOrderIndex = new Map(knowledgeGraph.topologicalOrder.map((id, index) => [id, index]));
assert.equal(knowledgeGraph.version, 1, "finance knowledge graph should expose a versioned contract");
assert.equal(knowledgeGraph.nodes.length, 9, "finance knowledge graph should contain the nine learning modules");
assert.equal(graphNodeIds.includes(data.project.dashboardModuleId), false, "finance knowledge graph should exclude overview");
assert.equal(new Set(graphNodeIds).size, graphNodeIds.length, "finance knowledge graph node ids should be unique");
assert.equal(knowledgeGraph.topologicalOrder.length, graphNodeIds.length, "finance knowledge graph should order every node");
assert.equal(new Set(knowledgeGraph.topologicalOrder).size, graphNodeIds.length, "finance topological order should not repeat nodes");
assert.deepEqual(new Set(knowledgeGraph.topologicalOrder), new Set(graphNodeIds), "finance topological order should contain exactly the graph nodes");
assert.equal(
  knowledgeGraph.edges.length,
  knowledgeGraph.nodes.reduce((sum, node) => sum + node.relations.length, 0),
  "finance knowledge graph should materialize every node relationship as an edge",
);
for (const node of knowledgeGraph.nodes) {
  assert.equal(typeof node.decisionRole, "string", `${node.id} should explain its decision role`);
  assert.ok(node.decisionRole.length > 0, `${node.id} should explain its decision role`);
  assert.ok(["concept", "support"].includes(node.graphRole), `${node.id} should expose a valid graph role`);
  assert.ok(Array.isArray(node.relations), `${node.id} should expose relationship metadata`);
  for (const relation of node.relations) {
    assert.ok(graphNodeIds.includes(relation.prerequisiteId), `${node.id} should reference a known prerequisite`);
    assert.equal(relation.type, "prerequisite", `${node.id} should type its prerequisite relationship`);
    assert.ok(relation.rationale, `${node.id} should explain why its prerequisite is required`);
  }
}
assert.deepEqual(
  knowledgeGraph.nodes.filter((node) => node.graphRole === "support").map((node) => node.id),
  ["study-plan-tools", "terms-further-reading"],
  "learning support nodes should remain outside the concept prerequisite chain",
);
assert.deepEqual(
  Object.fromEntries(knowledgeGraph.nodes.map((node) => [node.id, node.relations.map((relation) => relation.prerequisiteId)])),
  {
    "investment-basics": [],
    "asset-classes": ["investment-basics"],
    "risk-allocation": ["investment-basics", "asset-classes"],
    "fund-company-analysis": ["asset-classes"],
    valuation: ["risk-allocation", "fund-company-analysis"],
    "trading-execution": ["risk-allocation", "valuation"],
    "behavior-process": ["risk-allocation", "fund-company-analysis", "valuation", "trading-execution"],
    "study-plan-tools": [],
    "terms-further-reading": [],
  },
  "finance knowledge graph should retain the user-approved direct prerequisite topology",
);
for (const edge of knowledgeGraph.edges) {
  assert.ok(graphOrderIndex.get(edge.sourceId) < graphOrderIndex.get(edge.targetId), `${edge.sourceId} should precede ${edge.targetId}`);
  const targetNode = knowledgeGraph.nodes.find((node) => node.id === edge.targetId);
  assert.ok(
    targetNode.relations.some((relation) => relation.prerequisiteId === edge.sourceId
      && relation.type === edge.type
      && relation.rationale === edge.rationale),
    `${edge.sourceId} -> ${edge.targetId} should retain its node relationship metadata`,
  );
}

const graphFixtureNode = (id, prerequisiteIds = [], graphRole = "concept") => ({
  id,
  title: id,
  decisionRole: `${id} decision`,
  graphRole,
  knowledgeRelations: prerequisiteIds.map((prerequisiteId) => ({
    prerequisiteId,
    type: "prerequisite",
    rationale: `${prerequisiteId} before ${id}`,
  })),
});
assert.throws(
  () => buildKnowledgeGraph([graphFixtureNode("a", ["missing"])]),
  /unknown dependency missing/,
  "finance knowledge graph should fail loudly on unknown dependencies",
);
assert.throws(
  () => buildKnowledgeGraph([graphFixtureNode("a"), graphFixtureNode("a")]),
  /duplicate module id a/,
  "finance knowledge graph should fail loudly on duplicate ids",
);
assert.throws(
  () => buildKnowledgeGraph([graphFixtureNode("a", ["b"]), graphFixtureNode("b", ["a"])]),
  /dependency cycle/,
  "finance knowledge graph should fail loudly on cycles",
);
assert.throws(
  () => buildKnowledgeGraph([graphFixtureNode("a"), graphFixtureNode("support", ["a"], "support")]),
  /support node support cannot declare prerequisites/,
  "finance support nodes should not masquerade as concept prerequisites",
);

assert.equal((renderedSectionHtml.match(/class="math-display"/g) ?? []).length, sourceDisplayMathCount, "every display formula should survive generated HTML exactly once");
assert.equal((renderedSectionHtml.match(/class="math-inline"/g) ?? []).length, sourceInlineMathCount, "every inline formula should survive generated HTML exactly once");
assert.doesNotMatch(renderedSectionHtml, /<h1>\s*\[/, "Finance display formulas should not be corrupted into Setext headings");
assert.doesNotMatch(renderedSectionHtml, /<h1(?:\s|>)/, "Finance section body headings should remain below the reader's module h2");
assert.match(renderedSectionHtml, /<h3>1\. 投资究竟是什么？<\/h3>/, "authored Finance chapter headings should be retained at the nested h3 level");

for (const module of data.modules) {
  assert.equal(module.learningProgress, 0, `${module.id} should start with zero progress`);
  assert.ok(module.sections && Object.keys(module.sections).length > 0, `${module.id} should render Markdown sections`);
  assert.ok(Array.isArray(module.searchEntries) && module.searchEntries.length > 0, `${module.id} should expose section-level search`);
  assert.ok(module.searchEntries.every((entry) => entry.moduleId === module.id), `${module.id} search entries should retain their module`);
  assert.ok(Array.isArray(module.knowledgeNotes), `${module.id} should expose knowledge articles for local annotations`);
  const renderableTitles = getRenderableSectionTitles(module, data.project.id);
  assert.deepEqual(renderableTitles, Object.keys(module.sections), `${module.id} should render every generated section in source order`);
  const renderableIds = renderableTitles.map((title) => module.sectionIds[title]);
  assert.ok(renderableIds.every(Boolean), `${module.id} should expose a DOM id for every renderable section`);
  assert.equal(new Set(renderableIds).size, renderableIds.length, `${module.id} section DOM ids should be unique`);
}

const termsModule = data.modules.find((module) => module.id === "terms-further-reading");
assert.match(termsModule.searchText, /市盈率|P\/E/, "the glossary module should retain investment terminology");
assert.match(termsModule.searchText, /延伸学习资料/, "the glossary module should retain further-reading material");

const studyPlanModule = data.modules.find((module) => module.id === "study-plan-tools");
const targetSection = studyPlanModule.sections["目标"] ?? "";
const policyTemplateSection = studyPlanModule.sections["21.1 投资政策声明模板"] ?? "";
assert.deepEqual(
  {
    targetRetainsIntendedProse: /按 12 周节奏完成概念练习/.test(targetSection),
    targetExcludesTemplateFields: !/长期目标|目标日期|预计投入频率/.test(targetSection),
    fencedHeadingStaysOutOfSectionKeys: !Object.hasOwn(studyPlanModule.sections, "财务安全"),
    policyTemplateRetainsFencedContent: /<pre><code class="hljs language-markdown">[\s\S]*我的投资政策声明[\s\S]*财务安全[\s\S]*<\/code><\/pre>/.test(policyTemplateSection),
  },
  {
    targetRetainsIntendedProse: true,
    targetExcludesTemplateFields: true,
    fencedHeadingStaysOutOfSectionKeys: true,
    policyTemplateRetainsFencedContent: true,
  },
  "fenced Markdown template headings should not split or overwrite Finance module sections",
);

console.log(`finance reader contract passed for ${fileURLToPath(financeDataUrl)}`);
