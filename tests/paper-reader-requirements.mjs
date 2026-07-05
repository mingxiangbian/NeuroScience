import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";

function getPngSize(fileUrl) {
  const buffer = readFileSync(fileUrl);
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  };
}

const projectId = "brain-memory-for-ai-agents";
const readerUrl = new URL(`../papers/${projectId}/index.html`, import.meta.url);
const sharedCssUrl = new URL("../papers/shared/reader.css", import.meta.url);
const sharedJsUrl = new URL("../papers/shared/reader.js", import.meta.url);
const manifestUrl = new URL("../papers/manifest.json", import.meta.url);
const forbiddenReaderRouteUrl = new URL("../papers/reader/", import.meta.url);

assert.equal(existsSync(readerUrl), true, "paper project should expose a static reader page");
assert.equal(existsSync(sharedCssUrl), true, "reader should use a shared CSS file for reusable project pages");
assert.equal(existsSync(sharedJsUrl), true, "reader should use a shared JS file for reusable project pages");
assert.equal(existsSync(forbiddenReaderRouteUrl), false, "reader should not add a global /papers/reader/ route");

const html = readFileSync(readerUrl, "utf8");
const css = readFileSync(sharedCssUrl, "utf8");
const js = readFileSync(sharedJsUrl, "utf8");
const manifest = JSON.parse(readFileSync(manifestUrl, "utf8"));
const project = manifest.find((entry) => entry.id === projectId);

assert.ok(project, "manifest should include the brain memory project");
assert.match(html, /<html lang="zh-CN">/, "project reader should use Chinese UI language");
assert.match(html, /data-page="paper-project-reader"/, "project page should identify itself as the project reader");
assert.match(html, /href="\.\.\/"[\s\S]*aria-label="返回文献阁"/, "project mark should link back to the 文献阁 directory");
assert.match(html, /class="title-x-mark"[\s\S]*viewBox="0 0 96 96"/, "project mark should reuse the existing double-arc logo");
assert.match(html, /href="\.\.\/shared\/reader\.css"/, "project reader should load shared reader CSS");
assert.match(html, /src="\.\.\/shared\/reader\.js"/, "project reader should load shared reader JS");
assert.match(html, /id="reader-toolbar"/, "reader should include the top toolbar");
assert.match(html, /id="paper-directory"/, "reader should include the left paper directory");
assert.doesNotMatch(html, /id="chunk-nav"/, "reader should not add a secondary chunk navigation control to the open paper directory");
assert.match(html, /id="section-rail"/, "reader should include the collapsed section line index");
assert.match(html, /id="reader-main"/, "reader should include the center chunk reader");
assert.match(html, /id="note-panel"/, "reader should include the right current-chunk note panel");
assert.match(html, /id="mobile-note-drawer"/, "reader should include the mobile note drawer");
assert.match(html, /id="global-search"/, "reader should include a global search input");
assert.match(html, /id="search-overlay"/, "reader should expose a stable search overlay click target");
assert.match(html, /placeholder="Search"/,
  "reader search placeholder should be the concise label Search");
assert.match(html, /class="search-spinner"[\s\S]*aria-hidden="true"/, "search should include a tiny loading spinner");
assert.match(html, /class="search-icon"[\s\S]*id="global-search"[\s\S]*class="search-shortcut">⌘ K<\/kbd>/, "search should include a magnifying glass icon and keyboard hint");
assert.match(html, /<div class="toolbar-right">[\s\S]*<div class="toolbar-search">[\s\S]*<\/div>\s*<div class="toolbar-controls">[\s\S]*id="toggle-theme"[\s\S]*id="toggle-note"/, "search should be visually decoupled from the right toolbar controls");
assert.doesNotMatch(html, /<\/div>\s*<div class="toolbar-search">[\s\S]*<\/div>\s*<div class="toolbar-right">/, "search should no longer be a center toolbar column");
const toolbarLeftMarkup = html.match(/<div class="toolbar-left">(?<body>[\s\S]*?)<\/div>/)?.groups?.body ?? "";
assert.doesNotMatch(toolbarLeftMarkup, /id="toggle-left"/, "paper directory collapse control should not live in the top-left toolbar island");
assert.match(toolbarLeftMarkup, /class="icon-button mobile-directory-toggle"[\s\S]*data-toggle-left/, "mobile layout should expose a visible toolbar control for opening the paper directory");
assert.match(html, /<div class="directory-header">[\s\S]*class="directory-title">记忆与智能体[\s\S]*id="toggle-left"/, "paper directory collapse control should live next to the project title");
assert.match(html, /class="icon-button directory-toggle"[\s\S]*id="toggle-left"[\s\S]*data-toggle-left/, "primary directory collapse control should use the shared left-toggle binding");
assert.match(html, /class="icon-button rail-toggle"[\s\S]*data-toggle-left/, "collapsed section rail should include a local restore control");
assert.equal((html.match(/id="toggle-left"/g) ?? []).length, 1, "reader should keep one primary left-toggle id");
assert.match(html, /id="toggle-left"/, "reader should include a left directory collapse control");
assert.match(html, /id="toggle-note"/, "reader should include a right note panel collapse control");
assert.match(html, /id="toggle-theme"/, "reader should include a night mode toggle");
assert.doesNotMatch(html, /id="paper-list"|class="paper-list"|本地 paper 列表/, "project page should no longer be a simple paper list");

assert.match(css, /data-theme="dark"/, "reader CSS should support night mode");
assert.match(css, /backdrop-filter:\s*blur\(/, "reader CSS should use glass surfaces");
assert.match(css, /--toolbar-offset/, "reader CSS should define a toolbar offset for fixed reader panels");
assert.match(css, /--reader-glass-highlight/, "reader CSS should define a glass edge highlight token");
assert.match(css, /--reader-glass-edge/, "reader CSS should define a glass border token");
assert.match(css, /--reader-glass:\s*rgba\(238,\s*247,\s*242,\s*0\.42\)/, "reader glass should use a cool white-green translucent base in light mode");
assert.match(css, /--reader-glass-strong:\s*rgba\(244,\s*249,\s*245,\s*0\.56\)/, "strong reader glass should stay cool and translucent");
assert.match(css, /--reader-glass-low:\s*rgba\(244,\s*249,\s*245,\s*0\.2\)/, "reader CSS should define a low-opacity glass wash for linear notes");
assert.match(css, /--reader-glass-shadow:\s*rgba\(19,\s*45,\s*42,\s*0\.16\)/, "glass shadow should use a cool ink wash instead of warm card shadow");
assert.match(css, /--toolbar-control-size:\s*42px/, "toolbar controls should share a common height token");
assert.match(css, /\.reader-shell\s*\{[\s\S]*grid-template-columns:/, "reader CSS should define a desktop three-column reader layout");
assert.match(css, /\.reader-shell\s*\{[\s\S]*align-items:\s*start/, "reader grid should align side panels to the start so sticky positioning is not defeated by stretching");
assert.match(css, /\.reader-shell\s*\{[\s\S]*height:\s*100dvh[\s\S]*overflow:\s*hidden/, "reader shell should stay as a viewport-height app frame");
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*display:\s*flex/, "toolbar should be a modular flex container, not a three-column monolithic bar");
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*background:\s*transparent/, "toolbar container should not render as one full-width glass bar");
assert.match(css, /\.toolbar-controls\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "toolbar control group should render as an independent glass island");
assert.match(css, /\.toolbar-right\s*\{[\s\S]*background:\s*transparent/, "right toolbar wrapper should not merge search and controls into one glass island");
assert.match(css, /\.toolbar-controls\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "right toolbar buttons should keep their own glass control island");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*width:\s*clamp\(190px,\s*20vw,\s*280px\)/, "search should be a compact right-side tool");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*height:\s*var\(--toolbar-control-size\)/, "search should use the shared toolbar height");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "search should render as its own glass input component");
assert.match(css, /\.toolbar-controls\s*\{[\s\S]*height:\s*var\(--toolbar-control-size\)/, "toolbar control island should use the shared toolbar height");
assert.match(css, /\.toolbar-controls \.icon-button\s*\{[\s\S]*width:\s*calc\(var\(--toolbar-control-size\) - 10px\)[\s\S]*height:\s*calc\(var\(--toolbar-control-size\) - 10px\)/, "toolbar buttons should align to the search height");
assert.match(css, /\.search-icon\s*\{[\s\S]*width:\s*16px/, "search input should include a compact magnifying glass icon");
assert.match(css, /\.search-shortcut\s*\{[\s\S]*font-size:\s*11px/, "search input should include a quiet keyboard shortcut hint");
assert.match(css, /\.search-spinner\s*\{[\s\S]*width:\s*14px[\s\S]*height:\s*14px/, "search spinner should stay tiny");
assert.match(css, /\.reader-shell\.is-search-loading \.search-spinner\s*\{[\s\S]*opacity:\s*1/, "search loading should reveal the spinner");
assert.match(css, /\.reader-shell\.is-searching \.search-focus-layer\s*\{[\s\S]*pointer-events:\s*auto/, "search overlay should accept outside-click dismissal");
assert.match(css, /\.reader-shell\.is-searching \.toolbar-search\s*\{[\s\S]*position:\s*fixed[\s\S]*width:\s*min\(760px,\s*calc\(100vw - 48px\)\)/, "active search should become a centered modal input");
assert.match(css, /\.reader-shell\.is-searching \.search-results\s*\{[\s\S]*position:\s*fixed[\s\S]*width:\s*min\(760px,\s*calc\(100vw - 48px\)\)/, "active search results should align with the modal search width");
assert.match(css, /\.reader-shell\.is-searching \.search-results\s*\{[\s\S]*border:\s*1px solid var\(--reader-glass-edge\)[\s\S]*box-shadow:\s*0 26px 64px var\(--reader-glass-shadow\)/, "search results should be one unified glass list");
assert.match(css, /\.result-item\s*\{[\s\S]*min-width:\s*0[\s\S]*grid-template-columns:\s*24px minmax\(0,\s*1fr\)/, "result rows should reserve icon space without horizontal overflow");
assert.match(css, /\.result-title,\s*\.result-snippet\s*\{[\s\S]*overflow:\s*hidden[\s\S]*text-overflow:\s*ellipsis/, "search result title and snippet should be clamped");
assert.match(css, /\.result-copy\s*\{[\s\S]*min-width:\s*0/, "result copy should be allowed to shrink inside rows");
assert.match(css, /\.result-icon\s*\{[\s\S]*width:\s*18px[\s\S]*height:\s*18px/, "result rows should include leading icons");
assert.match(css, /\.result-highlight\s*\{[\s\S]*background:\s*rgba\(166,\s*67,\s*56,\s*0\.16\)/, "search keyword highlights should be subtle");
assert.match(css, /\.result-empty\s*\{[\s\S]*font-size:\s*13px/, "empty search results should stay quiet");
assert.match(css, /body,\s*\.toolbar-search,\s*\.toolbar-controls,\s*\.search-results[\s\S]*transition:[\s\S]*color 240ms ease[\s\S]*background 240ms ease[\s\S]*border-color 240ms ease/, "theme changes should transition color, background, and borders");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*height:\s*calc\(100dvh - var\(--toolbar-offset\) - 12px\)/, "paper directory should remain in the desktop viewport while the center article scrolls");
assert.match(css, /\.reader-main\s*\{[\s\S]*overflow-y:\s*auto/, "center article should own vertical scrolling so side panels do not scroll away");
assert.match(css, /\.reader-main\s*\{[\s\S]*height:\s*calc\(100dvh - var\(--toolbar-offset\) - 12px\)/, "center article should fit inside the fixed reader frame");
assert.match(css, /\.note-panel\s*\{[\s\S]*height:\s*calc\(100dvh - var\(--toolbar-offset\) - 12px\)/, "parallel note panel should remain in the desktop viewport while the center article scrolls");
assert.match(css, /\.directory-surface\s*\{[\s\S]*max-height:\s*100%/, "paper directory should stay inside the fixed side panel height");
assert.match(css, /\.directory-surface\s*\{[\s\S]*height:\s*100%/, "paper directory surface should fill the fixed side panel height");
assert.match(css, /\.reader-shell\.is-left-collapsed \.section-rail\s*\{[\s\S]*display:\s*flex/, "section rail should only appear when the desktop left panel is collapsed");
assert.match(css, /@media \(max-width:\s*1100px\)[\s\S]*is-note-collapsed/, "reader CSS should prioritize the main reader on narrow desktop widths");
assert.match(css, /@media \(max-width:\s*860px\)/, "reader CSS should define a portrait/mobile reader layout");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.section-rail[\s\S]*display:\s*none/, "mobile layout should hide the collapsed section rail");
assert.match(css, /\.directory-header\s*\{[\s\S]*display:\s*flex/, "directory title and collapse action should share a local header row");
assert.match(css, /\.directory-title\s*\{[\s\S]*font-size:\s*16px[\s\S]*font-weight:\s*760/, "directory title should read as the parent category");
assert.match(css, /\.paper-nav-item\s*\{[\s\S]*font-size:\s*13px/, "paper titles should read as children under the project category");
assert.match(css, /\.paper-nav-item\[aria-current="true"\]/, "expanded paper directory should show selected rows with a pressed state");
assert.match(css, /\.paper-nav-item\[aria-current="true"\]::before\s*\{[\s\S]*background:\s*var\(--reader-red\)/, "active paper should use a dark red left accent");
assert.doesNotMatch(css, /\.chunk-nav/, "open paper directory should not include a separate chunk navigation list");
assert.match(css, /\.project-mark\s*\{[\s\S]*background:\s*transparent[\s\S]*box-shadow:\s*none/, "project logo should use a flat treatment without glass chrome");
assert.match(css, /\.mobile-directory-toggle\s*\{[\s\S]*display:\s*none/, "mobile directory opener should stay hidden on desktop");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.mobile-directory-toggle\s*\{[\s\S]*display:\s*inline-flex/, "mobile layout should show a directory opener in the toolbar");
assert.match(css, /\.section-line:hover/, "collapsed section index should support hover line focus");
assert.match(css, /\.section-line:hover\s*\+\s*\.section-line/, "collapsed section index should lengthen the next adjacent line on hover");
assert.match(css, /\.section-line:has\(\+\s*\.section-line:hover\)/, "collapsed section index should lengthen the previous adjacent line on hover");
assert.match(css, /--reader-section-line:\s*rgba\(255,\s*255,\s*255,\s*0\.88\)/, "dark mode collapsed section lines should use a white color");
assert.match(css, /--reader-section-line-hover:\s*rgba\(255,\s*255,\s*255,\s*1\)/, "dark mode hover section line should be fully white");
assert.match(css, /--reader-section-line-active:\s*rgba\(255,\s*255,\s*255,\s*1\)/, "dark mode active section line should be fully white");
assert.match(css, /--reader-section-line-glow:\s*rgba\(255,\s*255,\s*255,\s*0\.34\)/, "dark mode section lines should have a white visibility glow");
const sectionRailRule = css.match(/\.section-rail\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionLineRule = css.match(/\.section-line\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionLineHoverRule = css.match(/\.section-line:hover\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionNeighborRule = css.match(/\.section-line:hover\s*\+\s*\.section-line,\s*\n\.section-line:has\(\+\s*\.section-line:hover\)\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const sectionActiveRule = css.match(/\.section-line\.is-active\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
assert.doesNotMatch(sectionRailRule, /border:\s*1px solid var\(--reader-glass-edge\)/, "collapsed section rail should not keep a card border");
assert.doesNotMatch(sectionRailRule, /background:\s*var\(--reader-glass\)/, "collapsed section rail should sit directly on the page canvas");
assert.doesNotMatch(sectionRailRule, /box-shadow:/, "collapsed section rail should not render as a floating card");
assert.match(sectionRailRule, /background:\s*transparent/, "collapsed section rail should use a transparent base");
assert.match(sectionLineRule, /width:\s*18px/, "section lines should share a stable base length");
assert.match(sectionLineRule, /background:\s*var\(--reader-section-line\)/, "section lines should use theme-aware contrast tokens");
assert.match(sectionLineRule, /box-shadow:\s*0 0 0 1px var\(--reader-section-line-glow\)/, "section lines should use a subtle dark-mode visibility edge");
assert.match(sectionLineHoverRule, /width:\s*36px/, "hovered section line should lengthen");
assert.match(sectionLineHoverRule, /height:\s*3px/, "hovered section line should thicken");
assert.match(sectionLineHoverRule, /background:\s*var\(--reader-section-line-hover\)/, "hovered section line should use theme-aware contrast tokens");
assert.match(sectionNeighborRule, /width:\s*28px/, "adjacent section lines should lengthen only while another line is hovered");
assert.doesNotMatch(sectionNeighborRule, /background:/, "adjacent section lines should not darken");
assert.match(sectionActiveRule, /background:\s*var\(--reader-section-line-active\)/, "active section should use a theme-aware contrast token");
assert.doesNotMatch(sectionActiveRule, /width:|height:/, "active section should not lengthen in the static state");
assert.match(css, /\.chunk-source-card/, "English source text should render in a light chunk card");
assert.match(css, /\.chunk-explanation/, "Chinese explanation should render outside the source card");
assert.match(css, /\.chunk-title/, "reader CSS should style chunk short titles");
assert.match(css, /\.chunk-translation/, "reader CSS should style Chinese translation separately from explanation");
assert.match(css, /\.reading-focus/, "reader CSS should style Chinese reading focus metadata");
assert.match(css, /\.paper-header\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "paper header should use a readable ch-based width");
assert.match(css, /\.chunk-list\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "chunk list should use a readable ch-based width");
assert.match(css, /\.note-surface\s*\{[\s\S]*min-height:/, "note panel should stay as a continuous blank surface");
assert.match(css, /\.math-block/, "reader CSS should style LaTeX/math blocks");
assert.match(css, /\.math-render/, "reader CSS should style rendered LaTeX output");
assert.match(css, /\.math-fallback/, "reader CSS should keep a readable fallback when math rendering fails");
assert.match(css, /\.code-block/, "reader CSS should style code blocks");
assert.match(css, /\.table-block/, "reader CSS should style table blocks");
assert.match(css, /\.figure-frame/, "reader CSS should style figure references with constrained dimensions");
assert.match(css, /\.search-results\s+\.result-item\s*\+ \.result-item/, "search results should use line separators");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.reader-shell\.is-searching \.toolbar-search[\s\S]*width:\s*calc\(100vw - 28px\)/, "mobile search modal should stay near full width without overflow");
assert.match(css, /\.paper-actions\.is-fallback-only/, "source links should be available only in the no-chunk fallback state");
assert.match(css, /\.section-chip[\s\S]*background:\s*transparent/, "section anchors should be quiet ghost controls");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "reader shell should avoid oversized card radii");
assert.doesNotMatch(css, /emoji/i, "reader style should not depend on emoji as the main visual language");

const notePanelRule = css.match(/\.note-panel\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const noteSurfaceRule = css.match(/\.note-surface\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const resultItemRule = css.match(/\.result-item\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
assert.doesNotMatch(resultItemRule, /box-shadow:/, "result rows should not have a persistent card shadow");
assert.match(notePanelRule, /border-left:\s*1px solid var\(--reader-note-rule\)/, "note panel should use a left rule instead of a full card border");
assert.doesNotMatch(notePanelRule, /\bborder:\s*1px solid var\(--reader-glass-edge\)/, "note panel should not render as a full glass card");
assert.match(noteSurfaceRule, /border:\s*0/, "note surface should not be an inner card");
assert.match(noteSurfaceRule, /background:\s*transparent/, "note surface should stay visually continuous");
assert.match(css, /\.note-surface p\s*\{[\s\S]*padding:\s*0 0 15px/, "parallel note surface should render the active chunk note as the only visible note");
assert.doesNotMatch(css, /\.note-item/, "parallel notes should not render every chunk note at once");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.note-panel[\s\S]*display:\s*none/, "mobile layout should keep the desktop note line hidden by default");

assert.match(js, /const PROJECT_ID = "brain-memory-for-ai-agents"/, "reader JS should bind the current project id for this project instance");
assert.match(js, /const SEARCH_DEBOUNCE_MS = 260/, "search debounce duration should stay lightweight");
assert.match(js, /const SEMANTIC_SCORE_THRESHOLD = 0\.42/, "semantic-only results should use a hard threshold");
assert.match(js, /searchDebounceTimer:\s*null/, "reader state should track the search debounce timer");
assert.match(js, /searchOverlay:\s*document\.querySelector\("#search-overlay"\)/, "reader should bind the search overlay for outside-click dismissal");
assert.match(js, /fetchJson\("\.\.\/manifest\.json"\)/, "reader should load the parent papers manifest");
assert.match(js, /readings\/\$\{paper\.id\}\/paper\.json/, "reader should load per-paper paper.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/chunks\.json/, "reader should load per-paper chunks.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/notes\.json/, "reader should load per-paper notes.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/embeddings\.json/, "reader should load per-paper embeddings.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/figures\.json/, "reader should attempt optional figures.json data");
assert.match(js, /assetBasePath:\s*`readings\/\$\{paper\.id\}\/`/, "reader should store each reading package base path for local assets");
assert.match(js, /IntersectionObserver/, "reader should keep the note panel aligned to the visible chunk");
assert.match(js, /function renderPaperLinks/, "reader should isolate source links for fallback metadata only");
assert.match(js, /<div class="paper-actions"><\/div>/, "normal chunked paper headers should not render source action links");
assert.match(js, /actions\.classList\.add\("is-fallback-only"\)/, "no-chunk fallback should mark source links as fallback-only");
assert.match(js, /function renderNoteSurface/, "note panel should render through a stable root surface");
assert.match(js, /function updateNoteSurface/, "reader should update the right panel to the current chunk note");
assert.doesNotMatch(js, /function renderChunkNav|data-chunk-nav-id/, "reader should not render a left-side chunk index in the open paper directory");
assert.doesNotMatch(js, /function renderNoteSurfaces|data-note-chunk-id|function syncSidebarsToChunk/, "reader should not render all chunk notes in the right panel");
assert.match(js, /function syncResponsiveState/, "reader should synchronize desktop and mobile shell state by breakpoint");
assert.match(js, /function updateActiveSectionRail/, "section rail active state should be updated independently from hover state");
assert.match(js, /function getActiveChunkByViewport/, "reader should compute active chunk from viewport geometry");
assert.match(js, /getBoundingClientRect\(\)/, "scrollspy should measure chunk geometry");
assert.match(js, /els\.main\.getBoundingClientRect\(\)/, "scrollspy should measure the center reader viewport, not the browser window");
assert.match(js, /els\.main\.addEventListener\("scroll"[\s\S]*updateActiveChunkFromViewport/, "scrollspy should update when the center reader scrolls");
assert.match(js, /root:\s*els\.main/, "IntersectionObserver should observe chunks inside the center reader scroller");
assert.doesNotMatch(js, /markSectionNeighbors|is-neighbor/, "section rail should not store hover wave state in JS because stale classes can fake scroll progress");
assert.match(js, /querySelectorAll\("\[data-toggle-left\]"\)/, "reader should bind all local left-directory controls");
assert.match(js, /cosineSimilarity/, "reader should perform local vector ranking");
assert.match(js, /sourceText[\s\S]*zhTranslation[\s\S]*zhExplanation/, "reader search should use sourceText, zhTranslation, and zhExplanation");
assert.match(js, /chunk\.zhTranslation/, "reader should render Chinese translations from chunk data");
assert.match(js, /paperData\.categoryZh/, "reader should prefer Chinese paper category metadata");
assert.match(js, /paperData\.readingFocus/, "reader should render Chinese reading focus metadata");
assert.match(js, /function openSearchModal/, "reader should isolate opening the search modal");
assert.match(js, /function closeSearchModal/, "reader should isolate closing the search modal");
assert.match(js, /function getSearchSnippet/, "reader should build search snippets around query terms");
assert.match(js, /function highlightSearchTerms/, "reader should highlight matched search terms");
assert.match(js, /function setSearchLoading/, "reader should expose a small loading state");
assert.match(js, /function scheduleSearch/, "reader should debounce search input");
assert.match(js, /function getLexicalScore/, "reader should calculate lexical search scores");
assert.match(js, /function getSemanticScore/, "reader should isolate semantic score calculation");
assert.match(js, /function getHybridSearchResults/, "reader should combine lexical and semantic scores");
assert.match(js, /lexicalScore > 0 \|\| semanticScore >= SEMANTIC_SCORE_THRESHOLD/, "reader should filter low-relevance results");
assert.match(js, /lexicalScore \* 10 \+ semanticScore/, "reader should prioritize lexical matches in ranking");
assert.match(js, /result-icon result-icon--/, "search results should render typed leading icons");
assert.match(js, /class="result-title"[\s\S]*class="result-snippet"/, "search results should use a two-line result structure");
assert.match(js, /No results found/, "reader should use the requested no-result wording");
assert.doesNotMatch(js, /no found/, "reader should remove the old broken no found copy");
assert.match(js, /els\.searchOverlay\.addEventListener\("click"[\s\S]*closeSearchModal/, "overlay click should close the search modal");
assert.match(js, /if \(!trimmed\)[\s\S]*searchResults\.innerHTML = ""/, "empty modal search should show no hint text");
assert.match(js, /renderMathBlock/, "reader should render math blocks");
assert.match(html, /katex\.min\.css/, "reader should load KaTeX styles for math rendering");
assert.match(html, /katex\.min\.js/, "reader should load KaTeX runtime for math rendering");
assert.match(js, /function renderLatex/, "reader should isolate LaTeX rendering");
assert.match(js, /window\.katex\?\.renderToString/, "reader should use KaTeX instead of showing raw LaTeX as code");
assert.match(js, /throwOnError:\s*false/, "reader should keep the page usable when one formula cannot render");
assert.match(js, /class="math-fallback"/, "reader should retain a readable escaped fallback for unsupported LaTeX");
assert.match(js, /renderCodeBlock/, "reader should render code blocks");
assert.match(js, /renderTableBlock/, "reader should render table blocks");
assert.match(js, /function resolveReadingAssetPath\(path,\s*reading\)/, "reader should resolve figure assets relative to the active reading package");
assert.match(js, /figureRefs/, "reader should resolve cross-page figure references");
assert.match(js, /if \(!figure\?\.file\) return ""/, "reader should skip missing figure files instead of rendering empty placeholders");
assert.match(js, /renderNoChunkPaper/, "reader should render real metadata for papers without chunk packages");
assert.doesNotMatch(js, /\/api\/|localhost|127\.0\.0\.1|openai|anthropic|generateAnswer|chatCompletion|SurrealDB/i, "reader should stay static without backend, provider keys, AI answers, or hard SurrealDB dependency");

const readingPaperIds = project.papers.map((paper) => paper.id);

for (const paper of project.papers) {
  assert.equal(typeof paper.shortTitle, "string", `paper ${paper.id} should include shortTitle`);
  assert.ok(paper.shortTitle.length > 0 && paper.shortTitle.length <= 42, `paper ${paper.id} shortTitle should stay compact`);
  assert.equal(paper.hasReading, true, `paper ${paper.id} should expose a completed reading package`);
}

for (const paperId of readingPaperIds) {
  const readingBase = new URL(`../papers/${projectId}/readings/${paperId}/`, import.meta.url);
  const requiredFiles = ["paper.json", "chunks.json", "notes.json", "embeddings.json", "figures.json"];

  for (const file of requiredFiles) {
    const fileUrl = new URL(file, readingBase);
    assert.equal(existsSync(fileUrl), true, `${paperId} should include ${file}`);
    assert.ok(statSync(fileUrl).size > 0, `${paperId} ${file} should not be empty`);
  }

  const paperData = JSON.parse(readFileSync(new URL("paper.json", readingBase), "utf8"));
  const chunkData = JSON.parse(readFileSync(new URL("chunks.json", readingBase), "utf8"));
  const notesData = JSON.parse(readFileSync(new URL("notes.json", readingBase), "utf8"));
  const embeddingsData = JSON.parse(readFileSync(new URL("embeddings.json", readingBase), "utf8"));
  const figuresData = JSON.parse(readFileSync(new URL("figures.json", readingBase), "utf8"));

  assert.equal(paperData.id, paperId, `${paperId} paper.json should use the paper id`);
  assert.equal(typeof paperData.shortTitle, "string", `${paperId} paper.json should include shortTitle`);
  assert.ok(Array.isArray(paperData.sections) && paperData.sections.length >= 2, `${paperId} should include section metadata`);
  assert.equal(chunkData.paperId, paperId, `${paperId} chunks.json should use the paper id`);
  assert.ok(Array.isArray(chunkData.chunks) && chunkData.chunks.length >= 8, `${paperId} should include a substantive reading package`);
  assert.equal(notesData.paperId, paperId, `${paperId} notes.json should use the paper id`);
  assert.equal(embeddingsData.paperId, paperId, `${paperId} embeddings.json should use the paper id`);
  assert.deepEqual(embeddingsData.indexedFields, ["sourceText", "zhTranslation", "zhExplanation"], `${paperId} embeddings should index sourceText, zhTranslation, and zhExplanation`);
  assert.equal(figuresData.paperId, paperId, `${paperId} figures.json should use the paper id`);
  assert.ok(Array.isArray(figuresData.figures), `${paperId} figures.json should include a figures array`);

  const chunkIds = new Set();
  const noteChunkIds = new Set(notesData.notes.map((note) => note.chunkId));
  const embeddingChunkIds = new Set(embeddingsData.items.map((item) => item.chunkId));
  const figureIds = new Set(figuresData.figures.map((figure) => figure.id));
  const renderedFigures = figuresData.figures.filter((item) => item.file);
  const sourceFigures = renderedFigures.filter((figure) => /^(semantic-crop|source-figure|paper-extract)$/.test(figure.cropMode));

  assert.ok(sourceFigures.length >= 1, `${paperId} should include at least one real source figure before using redraw fallbacks`);

  for (const figure of renderedFigures) {
    assert.equal(existsSync(new URL(figure.file, readingBase)), true, `${paperId} figure file ${figure.file} should exist`);
    assert.match(figure.cropMode, /^(semantic-crop|source-figure|paper-extract|manual-redraw)$/, `${paperId} figure ${figure.id} should be source-backed or a documented redraw, not a page fallback`);
    assert.match(figure.status, /^(cropped|extracted|redrawn)$/, `${paperId} figure ${figure.id} should be marked ready for rendering`);
    if (/^(semantic-crop|source-figure|paper-extract)$/.test(figure.cropMode)) {
      assert.doesNotMatch(figure.file, /\.svg$/i, `${paperId} figure ${figure.id} should use a raster source image when it is marked as source-backed`);
      assert.ok(figure.sourceFigure || Number.isFinite(figure.sourcePage), `${paperId} figure ${figure.id} should identify the source figure or source page`);
    }
    if (figure.cropMode === "manual-redraw") {
      assert.equal(figure.redrawType, "reader-side-fallback", `${paperId} manual redraw ${figure.id} should declare itself as a fallback`);
      assert.equal(typeof figure.sourceBasis, "string", `${paperId} manual redraw ${figure.id} should explain the source basis`);
      assert.ok(figure.sourceBasis.length > 12, `${paperId} manual redraw ${figure.id} should have a meaningful source basis`);
    }
  }

  for (const [index, chunk] of chunkData.chunks.entries()) {
    assert.match(chunk.id, /^ch-\d{3}$/, `${paperId} chunk ${index} should use stable ch-000 ids`);
    assert.equal(chunkIds.has(chunk.id), false, `${paperId} chunk id ${chunk.id} should be unique`);
    chunkIds.add(chunk.id);
    assert.equal(typeof chunk.sourceText, "string", `${paperId} ${chunk.id} should include sourceText`);
    assert.ok(chunk.sourceText.trim().length > 40, `${paperId} ${chunk.id} sourceText should be substantive`);
    assert.equal(typeof chunk.zhTranslation, "string", `${paperId} ${chunk.id} should include zhTranslation`);
    assert.ok(chunk.zhTranslation.trim().length > 20, `${paperId} ${chunk.id} zhTranslation should be substantive`);
    assert.equal(typeof chunk.zhExplanation, "string", `${paperId} ${chunk.id} should include zhExplanation`);
    assert.ok(chunk.zhExplanation.trim().length > 20, `${paperId} ${chunk.id} zhExplanation should be substantive`);
    assert.equal(noteChunkIds.has(chunk.id), true, `${paperId} ${chunk.id} should have a parallel note entry, even if blank`);
    assert.equal(embeddingChunkIds.has(chunk.id), true, `${paperId} ${chunk.id} should have an embedding vector`);
    assert.ok(Array.isArray(chunk.keywords), `${paperId} ${chunk.id} should include keywords`);
    if (chunk.blocks) {
      assert.ok(Array.isArray(chunk.blocks), `${paperId} ${chunk.id} blocks should be an array`);
      for (const block of chunk.blocks) {
        assert.match(block.type, /^(paragraph|math|code|table|figure)$/, `${paperId} ${chunk.id} block type ${block.type} should be supported`);
      }
    }
    if (chunk.figureRefs) {
      for (const ref of chunk.figureRefs) {
        assert.equal(figureIds.has(ref.id), true, `${paperId} ${chunk.id} figureRef ${ref.id} should exist in figures.json`);
        assert.match(ref.relation, /^(near|supporting|deferred)$/, `${paperId} ${chunk.id} figureRef should use a supported relation`);
      }
    }
  }

  assert.ok(chunkData.chunks.some((chunk) => chunk.blocks?.some((block) => block.type === "math")), `${paperId} should include at least one math block for formula support`);
  assert.ok(chunkData.chunks.some((chunk) => chunk.blocks?.some((block) => block.type === "code" || block.type === "table")), `${paperId} should include code or table block coverage`);
  assert.ok(chunkData.chunks.some((chunk) => chunk.figureRefs?.some((ref) => ref.relation === "supporting" || ref.relation === "deferred")), `${paperId} should include cross-page/supporting figure references`);

  for (const item of embeddingsData.items) {
    assert.equal(chunkIds.has(item.chunkId), true, `${paperId} embedding item should point to a real chunk`);
    assert.ok(Array.isArray(item.vector), `${paperId} embedding item should include a vector`);
    assert.ok(item.vector.length >= 8, `${paperId} embedding vectors should be non-trivial`);
    assert.ok(item.vector.every((value) => typeof value === "number" && Number.isFinite(value)), `${paperId} embedding vectors should contain finite numbers`);
  }
}

const zhangBase = new URL(`../papers/${projectId}/readings/zhang-2024-memory-mechanism-llm-agents/`, import.meta.url);
const zhangPaper = JSON.parse(readFileSync(new URL("paper.json", zhangBase), "utf8"));
const zhangChunks = JSON.parse(readFileSync(new URL("chunks.json", zhangBase), "utf8")).chunks;
const zhangFigures = JSON.parse(readFileSync(new URL("figures.json", zhangBase), "utf8")).figures;

assert.ok(zhangChunks.length >= 18, "Zhang 2024 should be expanded beyond the demo chunk set");
assert.equal(typeof zhangPaper.categoryZh, "string", "Zhang 2024 should include Chinese category metadata");
assert.equal(typeof zhangPaper.relationZh, "string", "Zhang 2024 should include Chinese relation metadata");
assert.equal(typeof zhangPaper.descriptionZh, "string", "Zhang 2024 should include Chinese description metadata");
assert.ok(Array.isArray(zhangPaper.readingFocus) && zhangPaper.readingFocus.length >= 3, "Zhang 2024 should include Chinese reading focus items");

for (const chunk of zhangChunks) {
  assert.equal(typeof chunk.title, "string", `Zhang 2024 ${chunk.id} should include a Chinese short title`);
  assert.ok(chunk.title.trim().length >= 4, `Zhang 2024 ${chunk.id} title should be meaningful`);
  assert.ok(chunk.zhTranslation.trim().length > 40, `Zhang 2024 ${chunk.id} zhTranslation should be substantive`);
}

const zhangRenderedFigures = zhangFigures.filter((figure) => figure.file);
assert.ok(zhangRenderedFigures.length >= 2, "Zhang 2024 should render at least two real local figures");
for (const figure of zhangRenderedFigures) {
  assert.equal(existsSync(new URL(figure.file, zhangBase)), true, `Zhang 2024 figure file ${figure.file} should exist`);
  assert.equal(figure.cropMode, "semantic-crop", `Zhang 2024 ${figure.id} should use semantic-crop instead of page screenshot`);
  assert.equal(figure.status, "cropped", `Zhang 2024 ${figure.id} should be marked cropped`);
  assert.ok(figure.bbox && Number.isFinite(figure.bbox.x) && Number.isFinite(figure.bbox.y), `Zhang 2024 ${figure.id} should include crop bbox metadata`);
  const size = getPngSize(new URL(figure.file, zhangBase));
  assert.notDeepEqual(size, { width: 1020, height: 1320 }, `Zhang 2024 ${figure.id} should not be a full-page screenshot`);
  assert.ok(size.height < 900, `Zhang 2024 ${figure.id} should be cropped to the relevant information`);
}

assert.ok(zhangChunks.some((chunk) => chunk.blocks?.some((block) => block.type === "table")), "Zhang 2024 should include at least one table block");
assert.ok(zhangChunks.some((chunk) => chunk.blocks?.some((block) => block.type === "math")), "Zhang 2024 should include at least one math block");

const expandedReadingIds = [
  {
    id: "mcclelland-1995-complementary-learning-systems",
    label: "McClelland 1995"
  },
  {
    id: "yassa-stark-2011-pattern-separation",
    label: "Yassa and Stark 2011"
  }
];

for (const { id, label } of expandedReadingIds) {
  const readingBase = new URL(`../papers/${projectId}/readings/${id}/`, import.meta.url);
  const paperData = JSON.parse(readFileSync(new URL("paper.json", readingBase), "utf8"));
  const chunkData = JSON.parse(readFileSync(new URL("chunks.json", readingBase), "utf8")).chunks;
  const notesData = JSON.parse(readFileSync(new URL("notes.json", readingBase), "utf8")).notes;
  const embeddingsData = JSON.parse(readFileSync(new URL("embeddings.json", readingBase), "utf8")).items;
  const figuresData = JSON.parse(readFileSync(new URL("figures.json", readingBase), "utf8")).figures;

  assert.ok(chunkData.length >= 12, `${label} should be expanded beyond the demo chunk set`);
  assert.equal(typeof paperData.categoryZh, "string", `${label} should include Chinese category metadata`);
  assert.equal(typeof paperData.relationZh, "string", `${label} should include Chinese relation metadata`);
  assert.equal(typeof paperData.descriptionZh, "string", `${label} should include Chinese description metadata`);
  assert.ok(Array.isArray(paperData.readingFocus) && paperData.readingFocus.length >= 3, `${label} should include Chinese reading focus items`);
  assert.ok(paperData.sections.length >= 5, `${label} should include a useful section spine`);
  assert.equal(notesData.length, chunkData.length, `${label} should keep one parallel note row per chunk`);
  assert.equal(embeddingsData.length, chunkData.length, `${label} should keep one local search vector per chunk`);
  assert.ok(figuresData.filter((figure) => figure.file).length >= 2, `${label} should include local figure assets or manual redraws`);

  for (const figure of figuresData.filter((item) => item.file)) {
    assert.equal(existsSync(new URL(figure.file, readingBase)), true, `${label} figure file ${figure.file} should exist`);
    assert.match(figure.cropMode, /^(semantic-crop|source-figure|paper-extract|manual-redraw)$/, `${label} figure ${figure.id} should be cropped, extracted, or documented as a redraw`);
    assert.match(figure.status, /^(cropped|extracted|redrawn)$/, `${label} figure ${figure.id} should be marked ready for rendering`);
  }

  for (const chunk of chunkData) {
    assert.equal(typeof chunk.title, "string", `${label} ${chunk.id} should include a Chinese short title`);
    assert.ok(chunk.title.trim().length >= 4, `${label} ${chunk.id} title should be meaningful`);
    assert.ok(chunk.zhTranslation.trim().length > 40, `${label} ${chunk.id} zhTranslation should be substantive`);
  }
}

const projectReadingDirs = readdirSync(new URL(`../papers/${projectId}/readings/`, import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();
assert.deepEqual(projectReadingDirs, readingPaperIds.slice().sort(), "every project paper should have a matching reading package");
