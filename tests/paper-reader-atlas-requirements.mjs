import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";

const projectId = "brain-memory-for-ai-agents";
const projectUrl = new URL(`../papers/${projectId}/`, import.meta.url);
const atlasUrl = new URL("research-atlas.json", projectUrl);
const manifestUrl = new URL("../papers/manifest.json", import.meta.url);
const readerHtmlUrl = new URL("index.html", projectUrl);
const readerJsUrl = new URL("../papers/shared/reader.js", import.meta.url);
const readerCssUrl = new URL("../papers/shared/reader.css", import.meta.url);

const readJson = (url) => JSON.parse(readFileSync(url, "utf8"));
const sorted = (items) => [...items].sort();

assert.equal(existsSync(atlasUrl), true, "paper project should publish research-atlas.json");

const atlas = readJson(atlasUrl);
const manifest = readJson(manifestUrl);
const html = readFileSync(readerHtmlUrl, "utf8");
const js = readFileSync(readerJsUrl, "utf8");
const css = readFileSync(readerCssUrl, "utf8");
const project = manifest.find((entry) => entry.id === projectId);

assert.ok(project, "papers manifest should include the brain-memory project");
assert.equal(atlas.version, 1, "research atlas schema version should stay explicit");
assert.match(atlas.titleZh, /\S/, "atlas should have a Chinese title");
assert.match(atlas.titleEn, /not a citation graph/i, "atlas title should state that the view is not a citation graph");
assert.match(atlas.disclaimerZh, /不是引用图/, "Chinese disclaimer should reject a citation-graph interpretation");
assert.match(atlas.disclaimerZh, /不表示生物同构/, "Chinese disclaimer should reject biological-isomorphism claims");
assert.match(
  atlas.disclaimerEn,
  /not biological mechanism identity/i,
  "English disclaimer should separate engineering inspiration from biological mechanism identity"
);

const expectedLaneIds = ["agent", "brain", "workspace"];
const laneIds = atlas.lanes.map((lane) => lane.id);
assert.deepEqual(sorted(laneIds), expectedLaneIds, "atlas should keep the three evidence lanes distinct");
assert.equal(new Set(laneIds).size, laneIds.length, "atlas lane IDs should be unique");
for (const lane of atlas.lanes) {
  assert.match(lane.labelZh, /\S/, `${lane.id} lane should have a Chinese text label`);
  assert.match(lane.labelEn, /\S/, `${lane.id} lane should have an English text label`);
}

const readablePapers = project.papers.filter((paper) => paper.hasReading === true);
const manifestPaperById = new Map(readablePapers.map((paper) => [paper.id, paper]));
const nodeByPaperId = new Map(atlas.nodes.map((node) => [node.paperId, node]));
assert.equal(nodeByPaperId.size, atlas.nodes.length, "atlas paper nodes should be unique");
assert.deepEqual(
  sorted(nodeByPaperId.keys()),
  sorted(manifestPaperById.keys()),
  "atlas nodes should exactly track the manifest papers that have reading packages"
);

const expectedLaneMembership = {
  agent: [
    "packer-2023-memgpt",
    "park-2023-generative-agents",
    "yang-2026-selfmem",
    "zhang-2024-memory-mechanism-llm-agents"
  ],
  brain: [
    "guskjolen-cembrowski-2023-engram-neurons",
    "mcclelland-1995-complementary-learning-systems",
    "rasch-born-2013-sleep-memory",
    "squire-2004-memory-systems",
    "squire-dede-2015-conscious-unconscious-memory-systems",
    "yassa-stark-2011-pattern-separation"
  ],
  workspace: ["gurnee-2026-global-workspace-language-models"]
};

for (const [laneId, expectedPaperIds] of Object.entries(expectedLaneMembership)) {
  const actualPaperIds = atlas.nodes.filter((node) => node.lane === laneId).map((node) => node.paperId);
  assert.deepEqual(sorted(actualPaperIds), sorted(expectedPaperIds), `${laneId} lane should preserve its evidence boundary`);
}

const expectedPaperTypes = {
  "gurnee-2026-global-workspace-language-models": "source-linked-mechanism-study",
  "guskjolen-cembrowski-2023-engram-neurons": "lifecycle-review",
  "mcclelland-1995-complementary-learning-systems": "theory-simulation",
  "packer-2023-memgpt": "system-paper",
  "park-2023-generative-agents": "system-paper",
  "rasch-born-2013-sleep-memory": "review-consolidation",
  "squire-2004-memory-systems": "review-taxonomy",
  "squire-dede-2015-conscious-unconscious-memory-systems": "review-taxonomy",
  "yang-2026-selfmem": "arxiv-v1-preprint",
  "yassa-stark-2011-pattern-separation": "mechanism-review",
  "zhang-2024-memory-mechanism-llm-agents": "survey"
};

const readingByPaperId = new Map();
for (const paper of readablePapers) {
  const packageUrl = new URL(`readings/${paper.id}/`, projectUrl);
  const paperDataUrl = new URL("paper.json", packageUrl);
  const figuresDataUrl = new URL("figures.json", packageUrl);
  assert.equal(existsSync(paperDataUrl), true, `${paper.id} should have paper.json`);
  assert.equal(existsSync(figuresDataUrl), true, `${paper.id} should have figures.json`);

  const paperData = readJson(paperDataUrl);
  const figuresData = readJson(figuresDataUrl);
  assert.equal(paperData.id, paper.id, `${paper.id} reading metadata should preserve the manifest ID`);
  assert.equal(paperData.title, paper.title, `${paper.id} title should come from the canonical manifest metadata`);
  assert.equal(paperData.shortTitle, paper.shortTitle, `${paper.id} short title should match the manifest`);
  assert.equal(paperData.year, paper.year, `${paper.id} year should match the manifest`);
  assert.ok(Array.isArray(paperData.sections) && paperData.sections.length > 0, `${paper.id} should expose reading sections`);
  assert.equal(
    new Set(paperData.sections.map((section) => section.id)).size,
    paperData.sections.length,
    `${paper.id} section IDs should be unique`
  );
  assert.ok(Array.isArray(figuresData.figures), `${paper.id} figures.json should expose a figures array`);
  readingByPaperId.set(paper.id, {
    packageUrl,
    paperData,
    figureById: new Map(figuresData.figures.map((figure) => [figure.id, figure]))
  });
}

const allowedFigureStatuses = new Set(["cropped", "extracted"]);
const allowedCropModes = new Set(["semantic-crop", "source-figure", "web-screenshot-crop"]);

function assertRealLocalFigure(paperId, figureId, context) {
  const reading = readingByPaperId.get(paperId);
  assert.ok(reading, `${context} should reference an existing reading package: ${paperId}`);
  const figure = reading.figureById.get(figureId);
  assert.ok(figure, `${context} should resolve ${paperId}/${figureId} in figures.json`);
  assert.match(figure.file ?? "", /^figures\/.+\.(?:png|jpe?g|webp|svg)$/i, `${context} should use a local image asset`);
  assert.equal((figure.file ?? "").split("/").includes(".."), false, `${context} image path should stay inside its reading package`);
  assert.ok(allowedFigureStatuses.has(figure.status), `${context} should use an extracted or cropped source figure`);
  assert.ok(allowedCropModes.has(figure.cropMode), `${context} should record a source-backed crop mode`);
  assert.match(figure.caption ?? "", /\S/, `${context} should retain the paper figure caption`);
  assert.ok(
    figure.sourceUrl || figure.sourceFigure || figure.sourcePage,
    `${context} should retain source URL, source figure, or source page provenance`
  );
  const imageUrl = new URL(figure.file, reading.packageUrl);
  assert.equal(existsSync(imageUrl), true, `${context} local image file should exist`);
  assert.ok(statSync(imageUrl).size > 1024, `${context} local image should be a substantive source asset`);
  return figure;
}

for (const node of atlas.nodes) {
  assert.ok(expectedLaneIds.includes(node.lane), `${node.paperId} should use a declared evidence lane`);
  assert.equal(node.paperType, expectedPaperTypes[node.paperId], `${node.paperId} should keep its evidence-aware paper type`);
  assert.match(node.motifZh ?? "", /\S/, `${node.paperId} should have a Chinese mechanism motif`);
  assert.match(node.primaryFigureId ?? "", /^fig-\d+$/, `${node.paperId} should name a primary source figure`);
  for (const duplicatedField of ["title", "shortTitle", "year", "authors", "source", "localFile"]) {
    assert.equal(
      Object.hasOwn(node, duplicatedField),
      false,
      `${node.paperId} atlas node should not duplicate manifest field ${duplicatedField}`
    );
  }
  assertRealLocalFigure(node.paperId, node.primaryFigureId, `${node.paperId} atlas node`);
}

assert.equal(atlas.visualAbstract.paperId, "zhang-2024-memory-mechanism-llm-agents", "visual abstract should introduce the survey synthesis");
assert.equal(atlas.visualAbstract.figureId, "fig-004", "visual abstract should use the survey's real overview figure");
assert.equal(atlas.visualAbstract.plateNumber, "01", "visual abstract should keep its editorial plate number");
assertRealLocalFigure(atlas.visualAbstract.paperId, atlas.visualAbstract.figureId, "visual abstract");
const visualReading = readingByPaperId.get(atlas.visualAbstract.paperId);
const visualSectionIds = new Set(visualReading.paperData.sections.map((section) => section.id));
assert.ok(Array.isArray(atlas.visualAbstract.anchors) && atlas.visualAbstract.anchors.length >= 3, "visual abstract should expose reading anchors");
for (const anchor of atlas.visualAbstract.anchors) {
  assert.ok(visualSectionIds.has(anchor.sectionId), `visual abstract anchor should resolve section ${anchor.sectionId}`);
  assert.match(anchor.labelZh ?? "", /\S/, "visual abstract anchor should have a Chinese text label");
  assert.match(anchor.labelEn ?? "", /\S/, "visual abstract anchor should have an English text label");
}

assert.ok(Array.isArray(atlas.featuredPlates) && atlas.featuredPlates.length > 0, "atlas should define at least one evidence plate");
const featuredPlateKeys = new Set();
for (const plate of atlas.featuredPlates) {
  const plateKey = `${plate.paperId}/${plate.figureId}`;
  assert.equal(featuredPlateKeys.has(plateKey), false, `featured plate ${plateKey} should be unique`);
  featuredPlateKeys.add(plateKey);
  assertRealLocalFigure(plate.paperId, plate.figureId, `featured plate ${plateKey}`);
  assert.match(plate.plateNumber ?? "", /^\d+(?:\.\d+)?$/, `featured plate ${plateKey} should have an editorial number`);
  assert.ok(Array.isArray(plate.methods) && plate.methods.length > 0, `featured plate ${plateKey} should name its methods`);
  assert.ok(Array.isArray(plate.callouts) && plate.callouts.length >= 2, `featured plate ${plateKey} should include evidence callouts`);
  assert.equal(new Set(plate.callouts.map((callout) => callout.key)).size, plate.callouts.length, `featured plate ${plateKey} callout keys should be unique`);
  for (const callout of plate.callouts) {
    assert.match(callout.titleZh ?? "", /\S/, `featured plate ${plateKey} callout should have a title`);
    assert.match(callout.bodyZh ?? "", /\S/, `featured plate ${plateKey} callout should explain the evidence`);
  }
  for (const field of ["claimZh", "evidenceZh", "limitationZh", "synthesisZh"]) {
    assert.match(plate.analysis?.[field] ?? "", /\S/, `featured plate ${plateKey} should include ${field}`);
  }
}

const clsPlate = atlas.featuredPlates.find((plate) => (
  plate.paperId === "mcclelland-1995-complementary-learning-systems" && plate.figureId === "fig-002"
));
assert.ok(clsPlate, "CLS Figure 11 should remain the featured stability-plasticity evidence plate");
assert.match(clsPlate.analysis.limitationZh, /不是.*脑测量/, "CLS synthesis should not be presented as a direct brain measurement");
assert.match(clsPlate.analysis.limitationZh, /不是.*AI agent/i, "CLS synthesis should not be presented as an AI-agent benchmark");

const nodeLaneByPaperId = new Map(atlas.nodes.map((node) => [node.paperId, node.lane]));
const expectedRelationSignatures = [
  "mcclelland-1995-complementary-learning-systems|rasch-born-2013-sleep-memory|conceptual-continuity",
  "packer-2023-memgpt|yang-2026-selfmem|explicit-comparator",
  "squire-2004-memory-systems|squire-dede-2015-conscious-unconscious-memory-systems|taxonomy-refinement"
];
const relationSignatures = atlas.relations.map((relation) => `${relation.from}|${relation.to}|${relation.kind}`);
assert.deepEqual(sorted(relationSignatures), sorted(expectedRelationSignatures), "atlas should keep only the three evidence-safe paper relations");
assert.equal(new Set(relationSignatures).size, relationSignatures.length, "atlas relations should be unique");
for (const relation of atlas.relations) {
  assert.ok(nodeByPaperId.has(relation.from), `relation source should exist: ${relation.from}`);
  assert.ok(nodeByPaperId.has(relation.to), `relation target should exist: ${relation.to}`);
  assert.notEqual(relation.from, relation.to, "atlas should not create self-relations");
  assert.equal(
    nodeLaneByPaperId.get(relation.from),
    nodeLaneByPaperId.get(relation.to),
    `${relation.from} -> ${relation.to} should not imply a cross-domain paper relation`
  );
  assert.match(relation.label ?? "", /\S/, "every relation should have a text label, not color alone");
}

const relationEndpoints = new Set(atlas.relations.flatMap((relation) => [relation.from, relation.to]));
assert.equal(
  relationEndpoints.has("gurnee-2026-global-workspace-language-models"),
  false,
  "Global Workspace study should remain an independent branch, not a memory-mechanism equivalence claim"
);
assert.equal(
  atlas.relations.some((relation) => new Set([relation.from, relation.to]).has("park-2023-generative-agents")
    && new Set([relation.from, relation.to]).has("packer-2023-memgpt")),
  false,
  "Generative Agents and MemGPT should not receive an unsupported direct relation"
);

assert.ok(Array.isArray(atlas.bridgeQuestions) && atlas.bridgeQuestions.length === 4, "atlas should keep four explicit design questions");
for (const question of atlas.bridgeQuestions) {
  assert.match(question.labelZh ?? "", /\S/, "bridge question should have a visible text label");
  assert.ok(Array.isArray(question.sources) && question.sources.length > 0, "bridge question should name its evidence sources");
  assert.equal(new Set(question.sources).size, question.sources.length, "bridge question sources should be unique");
  assert.equal(Object.hasOwn(question, "to"), false, "design question should not masquerade as a directed paper relation");
  assert.equal(Object.hasOwn(question, "target"), false, "design question should not claim a biological-to-engineering target mapping");
  for (const source of question.sources) {
    assert.ok(nodeByPaperId.has(source), `bridge source should exist: ${source}`);
    assert.equal(nodeLaneByPaperId.get(source), "brain", `bridge source ${source} should remain brain evidence, not an engineering claim`);
  }
}

assert.match(html, /role="tablist"[^>]*aria-label="阅读视图"/, "reader should expose the paper/lineage view switch as a tablist");
assert.match(html, /id="view-lineage"[^>]*role="tab"[^>]*aria-selected="false"[^>]*data-reader-view="lineage"/, "reader should expose an accessible lineage tab");
assert.match(html, /id="lineage-controls"[^>]*aria-label="概念谱系筛选"[^>]*hidden/, "reader should reserve accessible lineage filters");
assert.match(html, /id="lineage-view"[^>]*aria-label="跨论文概念谱系"[^>]*hidden/, "reader should reserve a dedicated lineage view");

assert.match(js, /fetchJson\("research-atlas\.json"(?:,\s*\{\s*optional:\s*true\s*\})?\)/, "reader should load the project research atlas");
assert.match(js, /state\.atlas\s*=/, "reader should retain the loaded atlas in reader state");
assert.match(js, /viewControls[\s\S]*addEventListener\("click"[\s\S]*openLineage/, "lineage tab should be bound to the lineage view controller");
assert.match(js, /const requestedView = params\.get\("view"\)[^]*if \(requestedView === "lineage"\) openLineage\(\);/, "a lineage deep link should remain in lineage mode after reload");
assert.match(js, /function renderLineageView\(/, "reader should render the conceptual lineage view");
assert.match(js, /class="lineage-scroll" tabindex="0"[^>]*aria-label=/, "lineage timeline should be keyboard-focusable and horizontally scrollable");
assert.match(js, /<canvas class="lineage-connections" aria-hidden="true"><\/canvas>/, "decorative relation canvas should stay hidden from assistive technology");
assert.match(js, /data-lineage-node[^]*aria-pressed=/, "lineage nodes should be real selectable buttons");
assert.match(js, /class="lineage-legend"[^]*同领域概念连续性[^]*明确前作 \/ 比较关系[^]*项目级设计问题/, "lineage should provide a text legend instead of color-only meaning");
assert.match(js, /state\.atlas\.disclaimerZh/, "main lineage view should render the Chinese interpretation boundary");
assert.match(js, /state\.atlas\.disclaimerEn/, "lineage inspector should render the English interpretation boundary");
assert.match(js, /function renderVisualAbstract\(/, "reader should render the survey visual abstract");
assert.match(js, /resolveReadingAssetPath\(figure\.file, reading\)/, "visual treatments should resolve existing local reading-package assets");
assert.match(js, /function openFigureLightbox\(/, "reader should expose source figures in a full-size viewer");
assert.match(js, /data-figure-lightbox-src=/, "visual abstract and research plates should include full-size figure controls");
assert.match(js, /role="region" aria-label="可滚动的原始尺寸论文图"/, "full-size figures should expose an accessible scroll region");
assert.match(js, /typeof dialog\.showModal !== "function"[^]*window\.open\(/, "unsupported dialog browsers should fall back to the source image itself");
assert.match(js, /function renderFigure\([^]*class="figure-frame research-plate/, "paper figures should render as editorial research plates");
assert.match(js, /class="figure-caption plate-paper-caption"/, "research plates should retain the source paper caption");
assert.match(js, /class="plate-footer"[^]*Source stamp/, "research plates should expose source provenance");
assert.match(js, /function renderEvidencePanel\([^]*plate\.analysis\.claimZh[^]*plate\.analysis\.evidenceZh[^]*plate\.analysis\.limitationZh[^]*plate\.analysis\.synthesisZh/, "featured figures should expose claim, evidence, limitation, and synthesis separately");
assert.match(js, /prefers-reduced-motion:\s*reduce/, "reader motion should respect reduced-motion preferences");

assert.match(css, /\.lineage-view\b/, "reader CSS should style the lineage view");
assert.match(css, /\.lineage-scroll\s*\{[^}]*overflow-x:\s*auto/s, "lineage timeline should use explicit horizontal overflow");
assert.match(css, /\.lineage-node\b/, "reader CSS should style timeline nodes");
assert.match(css, /\.lineage-lane--brain\b/, "brain evidence lane should have a visual treatment");
assert.match(css, /\.lineage-lane--workspace\b/, "workspace branch should have a visual treatment");
assert.match(css, /\.lineage-lane--agent\b/, "agent engineering lane should have a visual treatment");
assert.match(css, /\.lineage-legend\b/, "reader CSS should style the textual relation legend");
assert.match(css, /\.visual-abstract\b/, "reader CSS should style the real-figure visual abstract");
assert.match(css, /\.research-plate\b/, "reader CSS should style editorial research plates");
assert.match(css, /\.figure-lightbox\s*\{/, "reader CSS should style the source-figure viewer");
assert.match(css, /\.figure-lightbox-viewport\s*\{[^}]*overflow:\s*auto/s, "full-size source figures should remain pannable on narrow screens");
assert.match(css, /\.lineage-relation-label\.is-muted\s*\{[^}]*opacity:\s*0/s, "unrelated lineage labels should not compete with the selected paper");
assert.match(css, /\.evidence-panel\b/, "reader CSS should style the evidence inspector");
assert.match(css, /@media \(max-width:\s*860px\)[^]*\.lineage-/i, "lineage visualization should adapt at the reader mobile breakpoint");

console.log("Paper reader research-atlas requirements passed.");
