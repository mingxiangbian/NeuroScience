import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { markdownToSafeHtml } from "./build-markdown.mjs";
import { buildReferenceIndex } from "./build-references.mjs";
import { findMarkdownDocuments, toArray } from "./build-sources.mjs";
import { validateSiteDataInputs } from "./build-schema.mjs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(scriptDir, "..");
const outputPath = resolve(projectDir, "site/ielts-data.json");

function readJson(path) {
  return JSON.parse(readFileSync(resolve(projectDir, path), "utf8"));
}

function extractDateFromId(id) {
  const match = id.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

function getGeneratedAt(scoreProfile) {
  return process.env.IELTS_BUILD_DATE || scoreProfile.lastUpdated || new Date().toISOString().slice(0, 10);
}

function enrichMarkdownDoc(doc) {
  const rendered = markdownToSafeHtml(doc.body);
  return {
    ...doc,
    html: rendered.html,
    text: rendered.text,
  };
}

function indexNotes() {
  return findMarkdownDocuments(resolve(projectDir, "notes"), projectDir)
    .filter((doc) => doc.path !== "notes/README.md")
    .map((doc) => {
      const rendered = markdownToSafeHtml(doc.body);
      return {
        ...doc,
        id: String(doc.frontmatter.id ?? doc.id.replace(/^notes\//, "")),
        html: rendered.html,
        text: rendered.text,
        skill: doc.frontmatter.skill ?? null,
        topic: doc.frontmatter.topic ?? null,
        date: doc.frontmatter.date ?? null,
        relatedErrors: toArray(doc.frontmatter.related_errors),
      };
    });
}

function indexJournal() {
  return findMarkdownDocuments(resolve(projectDir, "journal/entries"), projectDir, { stripPrefix: "journal/entries/" })
    .map((doc) => {
      const rendered = markdownToSafeHtml(doc.body);
      return {
        ...doc,
        id: doc.id,
        html: rendered.html,
        text: rendered.text,
        date: doc.frontmatter.date ?? extractDateFromId(doc.id),
        relatedErrors: toArray(doc.frontmatter.related_errors),
        relatedNotes: toArray(doc.frontmatter.related_notes),
      };
    })
    .sort((a, b) => String(b.date ?? "").localeCompare(String(a.date ?? "")) || b.path.localeCompare(a.path));
}

const scoreProfile = readJson("diagnostics/score-profile.json");
const scoreHistory = readJson("diagnostics/score-history.json");
const errorLog = readJson("diagnostics/error-log.json");
const checkpoints = readJson("plans/checkpoint-status.json");
const notes = indexNotes();
const journal = indexJournal();
const promptLibrary = findMarkdownDocuments(resolve(projectDir, "prompts"), projectDir, { includeReadme: false }).map(enrichMarkdownDoc);
const validation = findMarkdownDocuments(resolve(projectDir, "validation"), projectDir, { includeReadme: false }).map(enrichMarkdownDoc);

const validationResult = validateSiteDataInputs({
  scoreProfile,
  scoreHistory,
  errorLog,
  checkpoints,
  notes,
  journal,
  promptLibrary,
  validation,
});
const references = buildReferenceIndex({ errorLog, notes, journal, promptLibrary, validation });
const sourceLinks = references.targets
  .filter((target) => target.sourcePath)
  .map((target) => ({ id: target.id, label: target.label, path: target.sourcePath }));

const data = {
  project: {
    id: "ielts-academic",
    title: "IELTS Academic",
    target: scoreProfile.target,
  },
  build: {
    contentUpdatedAt: scoreProfile.lastUpdated,
    generatedAt: getGeneratedAt(scoreProfile),
    validationIssues: [...validationResult.fatalIssues, ...validationResult.warningIssues],
    referenceIssues: validationResult.fatalIssues.filter((issue) => issue.type === "missing_reference"),
  },
  references,
  sourceLinks,
  scoreProfile,
  scoreHistory,
  errorLog,
  checkpoints,
  notes,
  journal,
  promptLibrary,
  validation,
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(data, null, 2)}\n`);

if (validationResult.fatalIssues.length > 0) {
  for (const issue of validationResult.fatalIssues) {
    console.error(`${issue.path}: ${issue.message}`);
  }
  process.exitCode = 1;
}
