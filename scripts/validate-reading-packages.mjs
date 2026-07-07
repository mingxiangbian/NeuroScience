#!/usr/bin/env node
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = join(repoRoot, "papers", "manifest.json");
const projectFilter = process.argv[2] ?? null;
const errors = [];
let packageCount = 0;

function readJson(path, label) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    errors.push(`${label}: cannot read valid JSON (${error.message})`);
    return null;
  }
}

function fail(label, message) {
  errors.push(`${label}: ${message}`);
}

function assert(condition, label, message) {
  if (!condition) fail(label, message);
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value, minLength = 1) {
  return typeof value === "string" && value.trim().length >= minLength;
}

function isDeepReadingPaper(paperData) {
  return Array.isArray(paperData?.readingGroups) || Array.isArray(paperData?.narrativeSpine);
}

function isHttpUrl(value) {
  if (!isNonEmptyString(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function relativeExists(baseDir, relativePath) {
  if (!isNonEmptyString(relativePath)) return false;
  const pathWithoutHash = relativePath.split("#")[0];
  return existsSync(join(baseDir, pathWithoutHash));
}

function isSafeRelativePath(path) {
  if (!isNonEmptyString(path)) return false;
  const normalized = normalize(path);
  return !normalized.startsWith("..") && !resolve(path).startsWith(path);
}

function validateRequiredFiles(readingDir, label) {
  for (const file of ["paper.json", "chunks.json", "notes.json", "embeddings.json", "figures.json"]) {
    const filePath = join(readingDir, file);
    assert(existsSync(filePath), label, `missing ${file}`);
    if (existsSync(filePath)) {
      assert(statSync(filePath).size > 0, label, `${file} is empty`);
    }
  }
}

function validatePaperData(paperData, manifestPaper, label) {
  assert(isObject(paperData), label, "paper.json must be an object");
  if (!isObject(paperData)) return { sectionIds: new Set() };

  assert(paperData.id === manifestPaper.id, label, "paper.json id must match manifest paper id");
  assert(paperData.title === manifestPaper.title, label, "paper.json title should match manifest title");
  assert(isNonEmptyString(paperData.shortTitle) && paperData.shortTitle.length <= 42, label, "paper.json shortTitle must be compact");
  assert(isNonEmptyString(paperData.categoryZh, 4), label, "paper.json must include categoryZh");
  assert(isNonEmptyString(paperData.relationZh, 10), label, "paper.json must include relationZh");
  assert(isNonEmptyString(paperData.descriptionZh, 20), label, "paper.json must include descriptionZh");
  assert(Array.isArray(paperData.readingFocus) && paperData.readingFocus.length >= 3, label, "paper.json readingFocus must include at least 3 Chinese reading prompts");
  assert(Array.isArray(paperData.sections) && paperData.sections.length >= 2, label, "paper.json sections must include at least 2 sections");
  assert(!paperData.sourceMode || /^(verbatim|source-linked)$/.test(paperData.sourceMode), label, "paper.json sourceMode must be verbatim or source-linked");
  if (paperData.sourceMode === "source-linked") {
    assert(isHttpUrl(paperData.source), label, "source-linked paper.json must include an http source URL");
  }

  const sectionIds = new Set();
  for (const [index, section] of (paperData.sections ?? []).entries()) {
    const sectionLabel = `${label} sections[${index}]`;
    assert(isNonEmptyString(section?.id), sectionLabel, "section id is required");
    assert(!sectionIds.has(section?.id), sectionLabel, "section id must be unique");
    sectionIds.add(section?.id);
    assert(isNonEmptyString(section?.title), sectionLabel, "section title is required");
    assert(isNonEmptyString(section?.titleZh), sectionLabel, "section titleZh is required");
  }

  return { sectionIds };
}

function validateFigures(figuresData, readingDir, sectionIds, label, { sourceLinked = false } = {}) {
  assert(isObject(figuresData), label, "figures.json must be an object");
  assert(Array.isArray(figuresData?.figures), label, "figures.json must include figures array");

  const figureIds = new Set();
  const renderedFigures = [];
  const sourceBackedModes = new Set(["source-figure", "semantic-crop", "paper-extract", "web-screenshot-crop"]);
  const sourceLinkedFigures = [];

  for (const [index, figure] of (figuresData?.figures ?? []).entries()) {
    const figureLabel = `${label} figures[${index}]`;
    assert(isNonEmptyString(figure?.id), figureLabel, "figure id is required");
    assert(!figureIds.has(figure?.id), figureLabel, "figure id must be unique");
    figureIds.add(figure?.id);
    assert(isNonEmptyString(figure?.label), figureLabel, "figure label is required");
    assert(isNonEmptyString(figure?.caption, 8), figureLabel, "figure caption is required");
    assert(!figure?.file || isSafeRelativePath(figure.file), figureLabel, "figure file must be a safe relative path");
    assert(!figure?.canonicalSectionId || sectionIds.has(figure.canonicalSectionId), figureLabel, "canonicalSectionId must point to a paper section");

    if (!figure?.file && figure?.cropMode === "source-linked") {
      sourceLinkedFigures.push(figure);
      assert(sourceLinked, figureLabel, "source-linked figure metadata is only allowed in source-linked packages");
      assert(figure.status === "source-linked", figureLabel, "source-linked figure status must be source-linked");
      assert(isHttpUrl(figure.sourceUrl), figureLabel, "source-linked figures need sourceUrl");
      assert(isNonEmptyString(figure.sourceAnchor, 4), figureLabel, "source-linked figures need sourceAnchor");
      assert(isNonEmptyString(figure.sourceFigure, 4), figureLabel, "source-linked figures need sourceFigure");
      continue;
    }

    if (figure?.file) {
      renderedFigures.push(figure);
      assert(existsSync(join(readingDir, figure.file)), figureLabel, `figure file does not exist: ${figure.file}`);
      assert(/^(source-figure|semantic-crop|paper-extract|web-screenshot-crop|manual-redraw)$/.test(figure.cropMode), figureLabel, "rendered figure must not use page-fallback crop mode");
      assert(/^(cropped|extracted|redrawn)$/.test(figure.status), figureLabel, "rendered figure status must be cropped, extracted, or redrawn");

      if (figure.cropMode === "semantic-crop") {
        assert(isObject(figure.bbox), figureLabel, "semantic-crop figures must include bbox");
        for (const field of ["x", "y", "width", "height"]) {
          assert(Number.isFinite(figure.bbox?.[field]), figureLabel, `bbox.${field} must be finite`);
        }
        assert(figure.bbox?.width > 0 && figure.bbox?.height > 0, figureLabel, "bbox width and height must be positive");
      }

      if (figure.cropMode === "web-screenshot-crop") {
        assert(figure.publicCropPolicy === "minimal-necessary", figureLabel, "web screenshot crops must declare minimal-necessary publicCropPolicy");
        assert(isObject(figure.bbox), figureLabel, "web screenshot crops must include bbox metadata");
        assert(isHttpUrl(figure.sourceUrl), figureLabel, "web screenshot crops need sourceUrl");
        assert(isNonEmptyString(figure.sourceAnchor, 4), figureLabel, "web screenshot crops need sourceAnchor");
      }

      if (sourceBackedModes.has(figure.cropMode)) {
        assert(isNonEmptyString(figure.sourceFigure) || Number.isFinite(figure.sourcePage), figureLabel, "source-backed figures need sourceFigure or sourcePage");
      }

      if (figure.cropMode === "manual-redraw") {
        assert(figure.redrawType === "reader-side-fallback", figureLabel, "manual redraw must declare reader-side-fallback");
        assert(isNonEmptyString(figure.sourceBasis, 20), figureLabel, "manual redraw must explain sourceBasis");
      }
    }
  }

  if (sourceLinked) {
    assert(renderedFigures.length + sourceLinkedFigures.length >= 1, label, "source-linked reading package should include at least one figure reference");
    assert(sourceLinkedFigures.length >= 1 || renderedFigures.some((figure) => sourceBackedModes.has(figure.cropMode)), label, "source-linked reading package should include source-linked or source-backed figures");
  } else {
    assert(renderedFigures.length >= 1, label, "reading package should render at least one figure");
    assert(renderedFigures.some((figure) => sourceBackedModes.has(figure.cropMode)), label, "reading package should include at least one source-backed figure");
  }

  return { figureIds };
}

function validateChunks(chunksData, paperId, sectionIds, figureIds, label, { sourceLinked = false, sourceBase = "" } = {}) {
  assert(isObject(chunksData), label, "chunks.json must be an object");
  assert(chunksData?.paperId === paperId, label, "chunks.json paperId must match paper id");
  assert(Array.isArray(chunksData?.chunks) && chunksData.chunks.length >= 8, label, "chunks.json must include at least 8 substantive chunks");

  const chunkIds = new Set();
  const usedSectionIds = new Set();
  let hasMath = false;
  let hasStructuredBlock = false;
  let hasFigureRef = false;

  for (const [index, chunk] of (chunksData?.chunks ?? []).entries()) {
    const chunkLabel = `${label} ${chunk?.id ?? `chunks[${index}]`}`;
    assert(/^ch-\d{3}$/.test(chunk?.id ?? ""), chunkLabel, "chunk id must use ch-000 format");
    assert(!chunkIds.has(chunk?.id), chunkLabel, "chunk id must be unique");
    chunkIds.add(chunk?.id);
    assert(sectionIds.has(chunk?.sectionId), chunkLabel, "sectionId must point to paper.json sections");
    usedSectionIds.add(chunk?.sectionId);
    assert(Number.isInteger(chunk?.order) && chunk.order >= 1, chunkLabel, "order must be a positive integer");
    assert(isNonEmptyString(chunk?.title, 4), chunkLabel, "chunk title must be a meaningful Chinese short title");
    assert(isNonEmptyString(chunk?.sourceText, 80), chunkLabel, "sourceText must contain substantive paper source text");
    assert(isNonEmptyString(chunk?.zhTranslation, 40), chunkLabel, "zhTranslation must contain faithful Chinese translation");
    assert(isNonEmptyString(chunk?.zhExplanation, 20), chunkLabel, "zhExplanation must contain project reading explanation");
    assert(Array.isArray(chunk?.keywords) && chunk.keywords.length >= 2, chunkLabel, "keywords must include at least 2 terms");
    assert(Array.isArray(chunk?.blocks) && chunk.blocks.length >= 1, chunkLabel, "blocks must preserve display structure");
    if (sourceLinked) {
      assert(chunk?.sourceMode === "source-linked", chunkLabel, "source-linked chunks must declare sourceMode");
      assert(isNonEmptyString(chunk?.sourceAnchor, 4), chunkLabel, "source-linked chunks must include sourceAnchor");
      assert(isNonEmptyString(chunk?.sourceSection, 4), chunkLabel, "source-linked chunks must include sourceSection");
      assert(isHttpUrl(chunk?.sourceUrl), chunkLabel, "source-linked chunks must include sourceUrl");
      assert(chunk.sourceUrl.startsWith(sourceBase) && chunk.sourceUrl.includes("#"), chunkLabel, "source-linked sourceUrl must point to an anchored source section");
    }

    for (const [blockIndex, block] of (chunk?.blocks ?? []).entries()) {
      const blockLabel = `${chunkLabel} blocks[${blockIndex}]`;
      assert(/^(paragraph|math|code|table|figure)$/.test(block?.type ?? ""), blockLabel, "block type is unsupported");
      if (block?.type === "paragraph") {
        assert(isNonEmptyString(block.text, 20), blockLabel, "paragraph block needs text");
      }
      if (block?.type === "math") {
        hasMath = true;
        assert(isNonEmptyString(block.latex, 3), blockLabel, "math block needs latex");
        assert(!/^\$\$?|\$\$?$/.test(block.latex.trim()), blockLabel, "math latex should omit $ delimiters");
      }
      if (block?.type === "code") {
        hasStructuredBlock = true;
        assert(isNonEmptyString(block.code, 8), blockLabel, "code block needs code");
      }
      if (block?.type === "table") {
        hasStructuredBlock = true;
        assert(Array.isArray(block.columns) && block.columns.length >= 2, blockLabel, "table block needs columns");
        assert(Array.isArray(block.rows) && block.rows.length >= 1, blockLabel, "table block needs rows");
      }
      if (block?.type === "figure") {
        hasFigureRef = true;
        assert(figureIds.has(block.id), blockLabel, "figure block id must exist in figures.json");
      }
    }

    for (const [refIndex, ref] of (chunk?.figureRefs ?? []).entries()) {
      const refLabel = `${chunkLabel} figureRefs[${refIndex}]`;
      hasFigureRef = true;
      assert(figureIds.has(ref?.id), refLabel, "figureRef id must exist in figures.json");
      assert(/^(near|supporting|deferred)$/.test(ref?.relation ?? ""), refLabel, "figureRef relation must be near, supporting, or deferred");
    }
  }

  for (const sectionId of sectionIds) {
    assert(usedSectionIds.has(sectionId), label, `section ${sectionId} has no chunk coverage`);
  }

  assert(hasMath, label, "reading package should include at least one math block");
  assert(hasStructuredBlock, label, "reading package should include at least one code or table block");
  assert(hasFigureRef, label, "reading package should include figure references");

  return { chunkIds };
}

function validateDeepReadingPaperData(paperData, label) {
  if (!isDeepReadingPaper(paperData)) return { groupIds: new Set(), enabled: false };

  assert(Array.isArray(paperData.readingGroups) && paperData.readingGroups.length >= 3, label, "deep reading papers need at least 3 readingGroups");
  const groupIds = new Set();
  for (const [index, group] of (paperData.readingGroups ?? []).entries()) {
    const groupLabel = `${label} readingGroups[${index}]`;
    assert(isNonEmptyString(group?.id), groupLabel, "group id is required");
    assert(!groupIds.has(group?.id), groupLabel, "group id must be unique");
    groupIds.add(group?.id);
    assert(isNonEmptyString(group?.title, 4), groupLabel, "group title is required");
    assert(isNonEmptyString(group?.summary, 10), groupLabel, "group summary is required");
  }

  assert(Array.isArray(paperData.premises) && paperData.premises.length >= 3 && paperData.premises.length <= 6, label, "deep reading papers need 3 to 6 premises");
  for (const [index, premise] of (paperData.premises ?? []).entries()) {
    const premiseLabel = `${label} premises[${index}]`;
    assert(isNonEmptyString(premise?.title, 4), premiseLabel, "premise title is required");
    assert(isNonEmptyString(premise?.body, 12), premiseLabel, "premise body is required");
  }

  assert(Array.isArray(paperData.narrativeSpine) && paperData.narrativeSpine.length >= 3, label, "deep reading papers need a narrativeSpine");
  for (const [index, item] of (paperData.narrativeSpine ?? []).entries()) {
    const spineLabel = `${label} narrativeSpine[${index}]`;
    assert(groupIds.has(item?.groupId), spineLabel, "narrativeSpine groupId must point to readingGroups");
    assert(isNonEmptyString(item?.summary, 8), spineLabel, "narrativeSpine summary is required");
  }

  assert(Array.isArray(paperData.misreadings) && paperData.misreadings.length >= 2, label, "deep reading papers need misreadings");
  for (const [index, item] of (paperData.misreadings ?? []).entries()) {
    const misreadingLabel = `${label} misreadings[${index}]`;
    assert(isNonEmptyString(item?.text, 8), misreadingLabel, "misreading text is required");
    if (item?.groupId) {
      assert(groupIds.has(item.groupId), misreadingLabel, "misreading groupId must point to readingGroups");
    }
  }

  return { groupIds, enabled: true };
}

function validateDeepReadingChunks(chunksData, groupIds, label, { enabled = false } = {}) {
  if (!enabled) return;
  for (const [index, chunk] of (chunksData?.chunks ?? []).entries()) {
    const chunkLabel = `${label} ${chunk?.id ?? `chunks[${index}]`}`;
    assert(groupIds.has(chunk?.groupId), chunkLabel, "deep reading chunk groupId must point to readingGroups");
    assert(isNonEmptyString(chunk?.premise, 8), chunkLabel, "deep reading chunk needs premise");
    assert(chunk.premise.length <= 80, chunkLabel, "premise should stay concise");
    assert(isNonEmptyString(chunk?.claim, 8), chunkLabel, "deep reading chunk needs claim");
    assert(chunk.claim.length <= 95, chunkLabel, "claim should stay concise");
    assert(chunk.claim.trim() !== chunk.zhExplanation?.trim(), chunkLabel, "claim must not duplicate zhExplanation");
    assert(Array.isArray(chunk?.evidence) && chunk.evidence.length >= 1 && chunk.evidence.length <= 3, chunkLabel, "evidence must include 1 to 3 items");
    for (const [evidenceIndex, evidence] of chunk.evidence.entries()) {
      assert(isNonEmptyString(evidence, 4), `${chunkLabel} evidence[${evidenceIndex}]`, "evidence item is required");
      assert(evidence.length <= 80, `${chunkLabel} evidence[${evidenceIndex}]`, "evidence item should stay concise");
    }
  }
}

function validateDeepReadingFigures(figuresData, label, { enabled = false } = {}) {
  if (!enabled) return;
  const localFigures = (figuresData?.figures ?? []).filter((figure) => figure.file);
  assert(localFigures.length >= 5, label, "deep reading package should include at least 5 local cropped figures");
  for (const [index, figure] of localFigures.entries()) {
    const figureLabel = `${label} deep figures[${index}]`;
    assert(figure.publicCropPolicy === "minimal-necessary", figureLabel, "local public figures must declare minimal-necessary crop policy");
    assert(isHttpUrl(figure.sourceUrl), figureLabel, "local public figures need sourceUrl");
    assert(isNonEmptyString(figure.sourceAnchor, 4), figureLabel, "local public figures need sourceAnchor");
    assert(isObject(figure.bbox), figureLabel, "local public figures need bbox metadata");
  }
}

function validateNotes(notesData, paperId, chunkIds, label) {
  assert(isObject(notesData), label, "notes.json must be an object");
  assert(notesData?.paperId === paperId, label, "notes.json paperId must match paper id");
  assert(Array.isArray(notesData?.notes), label, "notes.json must include notes array");
  assert(notesData?.notes?.length === chunkIds.size, label, "notes.json must include one note row per chunk");
  if (notesData?.noteMode) {
    assert(notesData.noteMode === "public", label, "notes.json noteMode must be public when set");
  }
  const publicNotes = notesData?.noteMode === "public";
  if (publicNotes) {
    assert((notesData.notes ?? []).some((note) => typeof note?.note === "string" && note.note.trim().length > 0), label, "public notes should include at least one non-empty note");
  }

  const noteChunkIds = new Set();
  for (const [index, note] of (notesData?.notes ?? []).entries()) {
    const noteLabel = `${label} notes[${index}]`;
    assert(chunkIds.has(note?.chunkId), noteLabel, "note chunkId must point to a real chunk");
    assert(!noteChunkIds.has(note?.chunkId), noteLabel, "note chunkId must be unique");
    noteChunkIds.add(note?.chunkId);
    if (publicNotes) {
      assert(typeof note?.note === "string", noteLabel, "public note must be a string");
    } else {
      assert(note?.note === "", noteLabel, "source notes should start as empty strings; personal notes live in localStorage");
    }
  }
}

function validateEmbeddings(embeddingsData, paperId, chunkIds, label, { deepReading = false } = {}) {
  assert(isObject(embeddingsData), label, "embeddings.json must be an object");
  assert(embeddingsData?.paperId === paperId, label, "embeddings.json paperId must match paper id");
  assert(Array.isArray(embeddingsData?.indexedFields), label, "embeddings.json must include indexedFields");
  for (const field of ["sourceText", "zhTranslation", "zhExplanation"]) {
    assert(embeddingsData?.indexedFields?.includes(field), label, `indexedFields must include ${field}`);
  }
  if (deepReading) {
    for (const field of ["premise", "claim", "evidence"]) {
      assert(embeddingsData?.indexedFields?.includes(field), label, `deep reading indexedFields must include ${field}`);
    }
  }
  assert(Array.isArray(embeddingsData?.items), label, "embeddings.json must include items");
  assert(embeddingsData?.items?.length === chunkIds.size, label, "embeddings.json must include one vector per chunk");

  const embeddingChunkIds = new Set();
  for (const [index, item] of (embeddingsData?.items ?? []).entries()) {
    const itemLabel = `${label} embeddings[${index}]`;
    assert(chunkIds.has(item?.chunkId), itemLabel, "embedding chunkId must point to a real chunk");
    assert(!embeddingChunkIds.has(item?.chunkId), itemLabel, "embedding chunkId must be unique");
    embeddingChunkIds.add(item?.chunkId);
    assert(Array.isArray(item?.vector) && item.vector.length >= 8, itemLabel, "vector must be a non-trivial array");
    assert((item?.vector ?? []).every((value) => typeof value === "number" && Number.isFinite(value)), itemLabel, "vector must contain finite numbers");
  }
}

function validateReadingPackage(project, manifestPaper) {
  const projectDir = join(repoRoot, "papers", project.id);
  const readingDir = join(projectDir, "readings", manifestPaper.id);
  const label = `${project.id}/${manifestPaper.id}`;

  validateRequiredFiles(readingDir, label);

  const paperData = readJson(join(readingDir, "paper.json"), `${label}/paper.json`);
  const chunksData = readJson(join(readingDir, "chunks.json"), `${label}/chunks.json`);
  const notesData = readJson(join(readingDir, "notes.json"), `${label}/notes.json`);
  const embeddingsData = readJson(join(readingDir, "embeddings.json"), `${label}/embeddings.json`);
  const figuresData = readJson(join(readingDir, "figures.json"), `${label}/figures.json`);

  const { sectionIds } = validatePaperData(paperData, manifestPaper, label);
  const deepReading = validateDeepReadingPaperData(paperData, label);
  const isSourceLinked = paperData?.sourceMode === "source-linked";
  if (isSourceLinked) {
    assert(isHttpUrl(manifestPaper.source), label, "source-linked manifest paper must include a source URL");
    assert(!manifestPaper.localFile, label, "source-linked manifest paper should not pretend to have a local full source file");
  } else {
    assert(relativeExists(projectDir, manifestPaper.localFile), label, "manifest localFile must point to an existing project file");
    assert(relativeExists(projectDir, manifestPaper.noteFile), label, "manifest noteFile must point to an existing project file");
    assert(!paperData?.sourceFile || relativeExists(readingDir, paperData.sourceFile), label, "paper.json sourceFile must exist");
    assert(!paperData?.noteFile || relativeExists(readingDir, paperData.noteFile), label, "paper.json noteFile must exist");
  }

  const { figureIds } = validateFigures(figuresData, readingDir, sectionIds, label, { sourceLinked: isSourceLinked });
  const { chunkIds } = validateChunks(chunksData, manifestPaper.id, sectionIds, figureIds, label, {
    sourceLinked: isSourceLinked,
    sourceBase: paperData?.source ?? manifestPaper.source ?? ""
  });
  validateDeepReadingChunks(chunksData, deepReading.groupIds, label, { enabled: deepReading.enabled });
  validateDeepReadingFigures(figuresData, label, { enabled: deepReading.enabled });
  validateNotes(notesData, manifestPaper.id, chunkIds, label);
  validateEmbeddings(embeddingsData, manifestPaper.id, chunkIds, label, { deepReading: deepReading.enabled });

  packageCount += 1;
}

const manifest = readJson(manifestPath, "papers/manifest.json");
assert(Array.isArray(manifest), "papers/manifest.json", "manifest must be a project array");

for (const project of manifest ?? []) {
  if (projectFilter && project.id !== projectFilter) continue;
  const projectLabel = project?.id ?? "unknown-project";
  assert(isNonEmptyString(project?.id), projectLabel, "project id is required");
  assert(Array.isArray(project?.papers), projectLabel, "project papers must be an array");

  const readingPapers = (project?.papers ?? []).filter((paper) => paper.hasReading);
  for (const paper of readingPapers) {
    validateReadingPackage(project, paper);
  }
}

if (projectFilter && packageCount === 0) {
  fail(projectFilter, "no reading packages matched the requested project");
}

if (errors.length > 0) {
  console.error(`Reading package validation failed with ${errors.length} errors:`);
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exitCode = 1;
} else {
  const scope = projectFilter ?? "all projects";
  console.log(`Validated ${packageCount} reading packages for ${scope}: 0 errors`);
}
