import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";

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
assert.match(html, /id="section-rail"/, "reader should include the collapsed section line index");
assert.match(html, /id="reader-main"/, "reader should include the center chunk reader");
assert.match(html, /id="note-panel"/, "reader should include the right continuous note panel");
assert.match(html, /id="mobile-note-drawer"/, "reader should include the mobile note drawer");
assert.match(html, /id="global-search"/, "reader should include a global search input");
assert.match(html, /placeholder="Searching\.\.\."/,
  "reader search placeholder should be concise and international");
assert.match(html, /<div class="toolbar-right">[\s\S]*<div class="toolbar-search">[\s\S]*id="global-search"[\s\S]*id="toggle-theme"/, "search should live inside the right modular toolbar group");
assert.doesNotMatch(html, /<\/div>\s*<div class="toolbar-search">[\s\S]*<\/div>\s*<div class="toolbar-right">/, "search should no longer be a center toolbar column");
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
assert.match(css, /\.reader-shell\s*\{[\s\S]*grid-template-columns:/, "reader CSS should define a desktop three-column reader layout");
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*display:\s*flex/, "toolbar should be a modular flex container, not a three-column monolithic bar");
assert.match(css, /\.reader-toolbar\s*\{[\s\S]*background:\s*transparent/, "toolbar container should not render as one full-width glass bar");
assert.match(css, /\.toolbar-left,\s*\.toolbar-right\s*\{[\s\S]*backdrop-filter:\s*var\(--reader-panel-blur\)/, "toolbar groups should render as independent glass islands");
assert.match(css, /\.toolbar-search\s*\{[\s\S]*width:\s*clamp\(180px,\s*18vw,\s*260px\)/, "search should be a compact right-side tool");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*position:\s*sticky/, "paper directory should stay fixed in the viewport through sticky positioning");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*top:\s*calc\(var\(--toolbar-offset\) \+ 5vh\)/, "paper directory should stick as a floating card below the toolbar");
assert.match(css, /\.reader-sidebar\s*\{[\s\S]*height:\s*auto/, "paper directory wrapper should not be full-height");
assert.match(css, /\.note-panel\s*\{[\s\S]*position:\s*sticky/, "parallel note panel should stay fixed in the viewport through sticky positioning");
assert.match(css, /\.directory-surface,\s*\.section-rail\s*\{[\s\S]*border:\s*1px solid var\(--reader-glass-edge\)/, "directory and section rail should keep glass panel borders");
assert.match(css, /\.directory-surface\s*\{[\s\S]*max-height:\s*min\(76vh,\s*calc\(100vh - var\(--toolbar-offset\) - 36px\)\)/, "paper directory should use content-driven height with a viewport cap");
assert.match(css, /\.directory-surface\s*\{[\s\S]*height:\s*auto/, "paper directory surface should not fill the viewport");
assert.match(css, /\.reader-shell\.is-left-collapsed \.section-rail\s*\{[\s\S]*display:\s*flex/, "section rail should only appear when the desktop left panel is collapsed");
assert.match(css, /@media \(max-width:\s*1100px\)[\s\S]*is-note-collapsed/, "reader CSS should prioritize the main reader on narrow desktop widths");
assert.match(css, /@media \(max-width:\s*860px\)/, "reader CSS should define a portrait/mobile reader layout");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.section-rail[\s\S]*display:\s*none/, "mobile layout should hide the collapsed section rail");
assert.match(css, /\.paper-nav-item\[aria-current="true"\]/, "expanded paper directory should show selected rows with a pressed state");
assert.match(css, /\.paper-nav-item\[aria-current="true"\]::before\s*\{[\s\S]*background:\s*var\(--reader-red\)/, "active paper should use a dark red left accent");
assert.match(css, /\.section-line:hover/, "collapsed section index should support hover line focus");
assert.match(css, /\.section-line\.is-neighbor/, "collapsed section index should support adjacent line wave by length");
assert.match(css, /\.chunk-source-card/, "English source text should render in a light chunk card");
assert.match(css, /\.chunk-explanation/, "Chinese explanation should render outside the source card");
assert.match(css, /\.paper-header\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "paper header should use a readable ch-based width");
assert.match(css, /\.chunk-list\s*\{[\s\S]*max-width:\s*min\(75ch,\s*calc\(100vw - 40px\)\)/, "chunk list should use a readable ch-based width");
assert.match(css, /\.note-surface\s*\{[\s\S]*min-height:/, "note panel should stay as a continuous blank surface");
assert.match(css, /\.math-block/, "reader CSS should style LaTeX/math blocks");
assert.match(css, /\.code-block/, "reader CSS should style code blocks");
assert.match(css, /\.table-block/, "reader CSS should style table blocks");
assert.match(css, /\.figure-frame/, "reader CSS should style figure references with constrained dimensions");
assert.match(css, /\.search-results\s+\.result-item\s*\+ \.result-item/, "search results should use line separators");
assert.match(css, /\.paper-actions\.is-fallback-only/, "source links should be available only in the no-chunk fallback state");
assert.match(css, /\.section-chip[\s\S]*background:\s*transparent/, "section anchors should be quiet ghost controls");
assert.doesNotMatch(css, /border-radius:\s*24px|border-radius:\s*28px/, "reader shell should avoid oversized card radii");
assert.doesNotMatch(css, /emoji/i, "reader style should not depend on emoji as the main visual language");

const notePanelRule = css.match(/\.note-panel\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
const noteSurfaceRule = css.match(/\.note-surface\s*\{(?<body>[\s\S]*?)\n\}/)?.groups?.body ?? "";
assert.match(notePanelRule, /border-left:\s*1px solid var\(--reader-note-rule\)/, "note panel should use a left rule instead of a full card border");
assert.doesNotMatch(notePanelRule, /\bborder:\s*1px solid var\(--reader-glass-edge\)/, "note panel should not render as a full glass card");
assert.match(noteSurfaceRule, /border:\s*0/, "note surface should not be an inner card");
assert.match(noteSurfaceRule, /background:\s*transparent/, "note surface should stay visually continuous");
assert.match(css, /\.note-surface p \+ p\s*\{[\s\S]*border-top:\s*1px solid var\(--reader-note-rule\)/, "parallel notes should be separated by quiet horizontal rules");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.note-panel[\s\S]*display:\s*none/, "mobile layout should keep the desktop note line hidden by default");

assert.match(js, /const PROJECT_ID = "brain-memory-for-ai-agents"/, "reader JS should bind the current project id for this project instance");
assert.match(js, /fetchJson\("\.\.\/manifest\.json"\)/, "reader should load the parent papers manifest");
assert.match(js, /readings\/\$\{paper\.id\}\/paper\.json/, "reader should load per-paper paper.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/chunks\.json/, "reader should load per-paper chunks.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/notes\.json/, "reader should load per-paper notes.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/embeddings\.json/, "reader should load per-paper embeddings.json data");
assert.match(js, /readings\/\$\{paper\.id\}\/figures\.json/, "reader should attempt optional figures.json data");
assert.match(js, /IntersectionObserver/, "reader should keep the note panel aligned to the visible chunk");
assert.match(js, /function renderPaperLinks/, "reader should isolate source links for fallback metadata only");
assert.match(js, /<div class="paper-actions"><\/div>/, "normal chunked paper headers should not render source action links");
assert.match(js, /actions\.classList\.add\("is-fallback-only"\)/, "no-chunk fallback should mark source links as fallback-only");
assert.match(js, /function renderNoteSurface/, "note panel should render through a stable root surface");
assert.match(js, /function syncResponsiveState/, "reader should synchronize desktop and mobile shell state by breakpoint");
assert.match(js, /function updateActiveSectionRail/, "section rail active state should be updated independently from hover state");
assert.match(js, /cosineSimilarity/, "reader should perform local vector ranking");
assert.match(js, /sourceText[\s\S]*zhExplanation/, "reader search should use sourceText and zhExplanation");
assert.match(js, /no found/, "reader should show no found for empty search results");
assert.match(js, /renderMathBlock/, "reader should render math blocks");
assert.match(js, /renderCodeBlock/, "reader should render code blocks");
assert.match(js, /renderTableBlock/, "reader should render table blocks");
assert.match(js, /figureRefs/, "reader should resolve cross-page figure references");
assert.match(js, /hasFile \?[\s\S]*<img[\s\S]*: `[\s\S]*figure-placeholder/, "reader should not render broken images for figures without files");
assert.match(js, /renderNoChunkPaper/, "reader should render real metadata for papers without chunk packages");
assert.doesNotMatch(js, /\/api\/|localhost|127\.0\.0\.1|openai|anthropic|generateAnswer|chatCompletion|SurrealDB/i, "reader should stay static without backend, provider keys, AI answers, or hard SurrealDB dependency");

const readingPaperIds = [
  "zhang-2024-memory-mechanism-llm-agents",
  "mcclelland-1995-complementary-learning-systems",
  "yassa-stark-2011-pattern-separation",
];

for (const paper of project.papers) {
  assert.equal(typeof paper.shortTitle, "string", `paper ${paper.id} should include shortTitle`);
  assert.ok(paper.shortTitle.length > 0 && paper.shortTitle.length <= 42, `paper ${paper.id} shortTitle should stay compact`);
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
  assert.ok(Array.isArray(chunkData.chunks) && chunkData.chunks.length >= 4, `${paperId} should include at least four chunks`);
  assert.equal(notesData.paperId, paperId, `${paperId} notes.json should use the paper id`);
  assert.equal(embeddingsData.paperId, paperId, `${paperId} embeddings.json should use the paper id`);
  assert.deepEqual(embeddingsData.indexedFields, ["sourceText", "zhExplanation"], `${paperId} embeddings should index sourceText and zhExplanation`);
  assert.equal(figuresData.paperId, paperId, `${paperId} figures.json should use the paper id`);
  assert.ok(Array.isArray(figuresData.figures), `${paperId} figures.json should include a figures array`);

  const chunkIds = new Set();
  const noteChunkIds = new Set(notesData.notes.map((note) => note.chunkId));
  const embeddingChunkIds = new Set(embeddingsData.items.map((item) => item.chunkId));
  const figureIds = new Set(figuresData.figures.map((figure) => figure.id));

  for (const [index, chunk] of chunkData.chunks.entries()) {
    assert.match(chunk.id, /^ch-\d{3}$/, `${paperId} chunk ${index} should use stable ch-000 ids`);
    assert.equal(chunkIds.has(chunk.id), false, `${paperId} chunk id ${chunk.id} should be unique`);
    chunkIds.add(chunk.id);
    assert.equal(typeof chunk.sourceText, "string", `${paperId} ${chunk.id} should include sourceText`);
    assert.ok(chunk.sourceText.trim().length > 40, `${paperId} ${chunk.id} sourceText should be substantive`);
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

assert.equal(existsSync(new URL(`../papers/${projectId}/readings/park-2023-generative-agents/`, import.meta.url)), false, "non-first-batch papers should not need fake chunk packages");

const projectReadingDirs = readdirSync(new URL(`../papers/${projectId}/readings/`, import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();
assert.deepEqual(projectReadingDirs, readingPaperIds.slice().sort(), "first implementation should only create the confirmed three high-quality reading packages");
