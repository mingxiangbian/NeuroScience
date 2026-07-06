import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(scriptDir, "..");
const outputPath = resolve(projectDir, "site/ielts-data.json");

const allowedErrorStatuses = new Set(["active", "improving", "fixed", "regressed"]);
const allowedErrorImpacts = new Set(["high", "medium", "low"]);

const promptSources = [
  ["orchestrator", "prompts/orchestrator.md"],
  ["run-modes", "prompts/run-modes.md"],
  ["interaction-protocol", "prompts/interaction-protocol.md"],
  ["output-contract", "prompts/output-contract.md"],
  ["calibration-and-validation", "prompts/calibration-and-validation.md"],
  ["agents/listening-specialist", "prompts/agents/listening-specialist.md"],
  ["agents/reading-specialist", "prompts/agents/reading-specialist.md"],
  ["agents/writing-task-1-examiner", "prompts/agents/writing-task-1-examiner.md"],
  ["agents/writing-task-2-examiner", "prompts/agents/writing-task-2-examiner.md"],
  ["agents/speaking-examiner", "prompts/agents/speaking-examiner.md"],
  ["agents/language-error-analyst", "prompts/agents/language-error-analyst.md"],
  ["agents/diagnostic-score-profile-analyst", "prompts/agents/diagnostic-score-profile-analyst.md"],
  ["agents/study-load-execution-planner", "prompts/agents/study-load-execution-planner.md"],
];

const validationSources = [
  ["output-contract-checklist", "validation/output-contract-checklist.md"],
  ["dry-run-test-cases", "validation/dry-run-test-cases.md"],
  ["examiner-calibration-checklist", "validation/examiner-calibration-checklist.md"],
];

function parseFrontmatter(markdown) {
  const match = markdown.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { frontmatter: {}, body: markdown };

  const frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const parsed = line.match(/^([^:]+):\s*(.*)$/);
    if (!parsed) continue;
    frontmatter[parsed[1].trim()] = parseYamlValue(parsed[2].trim());
  }

  return {
    frontmatter,
    body: markdown.slice(match[0].length),
  };
}

function validateReferences({ errorLog, notes, journal }) {
  const issues = [];
  const errorIds = new Set((errorLog.errors ?? []).map((error) => error.id));
  const noteIds = new Set(notes.map((note) => note.id));

  for (const error of errorLog.errors ?? []) {
    if (!allowedErrorStatuses.has(error.status)) {
      issues.push({
        type: "invalid_error_status",
        errorId: error.id,
        value: error.status,
        expected: [...allowedErrorStatuses],
      });
    }

    if (!allowedErrorImpacts.has(error.impact)) {
      issues.push({
        type: "invalid_error_impact",
        errorId: error.id,
        value: error.impact,
        expected: [...allowedErrorImpacts],
      });
    }
  }

  for (const note of notes) {
    for (const errorId of note.relatedErrors) {
      if (!errorIds.has(errorId)) {
        issues.push({
          type: "missing_related_error",
          sourceType: "note",
          sourceId: note.id,
          relatedError: errorId,
        });
      }
    }
  }

  for (const entry of journal) {
    for (const errorId of entry.relatedErrors) {
      if (!errorIds.has(errorId)) {
        issues.push({
          type: "missing_related_error",
          sourceType: "journal",
          sourceId: entry.id,
          relatedError: errorId,
        });
      }
    }

    for (const noteId of entry.relatedNotes) {
      if (!noteIds.has(noteId)) {
        issues.push({
          type: "missing_related_note",
          sourceType: "journal",
          sourceId: entry.id,
          relatedNote: noteId,
        });
      }
    }
  }

  return issues;
}

function parseYamlValue(value) {
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((item) => parseYamlScalar(item.trim()));
  }

  return parseYamlScalar(value);
}

function parseYamlScalar(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }

  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null") return null;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

function readJson(path) {
  return JSON.parse(readFileSync(resolve(projectDir, path), "utf8"));
}

function readMarkdownDoc(id, path) {
  const markdown = readFileSync(resolve(projectDir, path), "utf8");
  const { frontmatter, body } = parseFrontmatter(markdown);

  return {
    id,
    path,
    title: extractTitle(body, id),
    body: body.trim(),
    frontmatter,
  };
}

function indexNotes() {
  return findMarkdownFiles(resolve(projectDir, "notes"))
    .filter((path) => path.split(sep).at(-1) !== "README.md")
    .map((filePath) => {
      const path = toProjectPath(filePath);
      const idFromPath = path.replace(/^notes\//, "").replace(/\.md$/, "");
      const { frontmatter, body } = parseFrontmatter(readFileSync(filePath, "utf8"));

      return {
        id: String(frontmatter.id ?? idFromPath),
        path,
        title: extractTitle(body, idFromPath),
        body: body.trim(),
        frontmatter,
        skill: frontmatter.skill ?? null,
        topic: frontmatter.topic ?? null,
        date: frontmatter.date ?? null,
        relatedErrors: toArray(frontmatter.related_errors),
      };
    })
    .sort((a, b) => a.path.localeCompare(b.path));
}

function indexJournal() {
  const entriesDir = resolve(projectDir, "journal/entries");
  if (!existsSync(entriesDir)) return [];

  return findMarkdownFiles(entriesDir)
    .map((filePath) => {
      const path = toProjectPath(filePath);
      const id = path.replace(/^journal\/entries\//, "").replace(/\.md$/, "");
      const { frontmatter, body } = parseFrontmatter(readFileSync(filePath, "utf8"));

      return {
        id,
        path,
        title: extractTitle(body, id),
        body: body.trim(),
        frontmatter,
        date: frontmatter.date ?? extractDateFromId(id),
        relatedErrors: toArray(frontmatter.related_errors),
        relatedNotes: toArray(frontmatter.related_notes),
      };
    })
    .sort((a, b) => String(b.date ?? "").localeCompare(String(a.date ?? "")) || b.path.localeCompare(a.path));
}

function findMarkdownFiles(dir) {
  const files = [];

  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(path));
    } else if (entry.isFile() && extname(entry.name) === ".md") {
      files.push(path);
    }
  }

  return files.sort((a, b) => a.localeCompare(b));
}

function toProjectPath(path) {
  return relative(projectDir, path).split(sep).join("/");
}

function extractTitle(markdown, fallback) {
  const match = markdown.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallback;
}

function extractDateFromId(id) {
  const match = id.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

function toArray(value) {
  if (Array.isArray(value)) return value.map(String);
  if (value === undefined || value === null || value === "") return [];
  return [String(value)];
}

const scoreProfile = readJson("diagnostics/score-profile.json");
const scoreHistory = readJson("diagnostics/score-history.json");
const errorLog = readJson("diagnostics/error-log.json");
const checkpoints = readJson("plans/checkpoint-status.json");
const notes = indexNotes();
const journal = indexJournal();
const promptLibrary = promptSources.map(([id, path]) => readMarkdownDoc(id, path));
const validation = validationSources.map(([id, path]) => readMarkdownDoc(id, path));
const referenceIssues = validateReferences({ errorLog, notes, journal });

const data = {
  project: {
    id: "ielts-academic",
    title: "IELTS Academic",
    target: scoreProfile.target,
  },
  build: {
    generatedAt: new Date().toISOString(),
    referenceIssues,
  },
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

if (referenceIssues.length > 0) {
  process.exitCode = 1;
}
