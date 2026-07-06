import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(scriptDir, "..");
const outputPath = resolve(projectDir, "site/ielts-data.json");

function parseFrontmatter(markdown) {
  const match = markdown.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) return { attributes: {}, body: markdown };

  const attributes = Object.fromEntries(
    match[1]
      .split("\n")
      .map((line) => line.match(/^([^:]+):\s*(.*)$/))
      .filter(Boolean)
      .map((parts) => [parts[1].trim(), parts[2].trim()]),
  );

  return {
    attributes,
    body: markdown.slice(match[0].length),
  };
}

function validateReferences(data) {
  const requiredKeys = [
    "build",
    "scoreProfile",
    "scoreHistory",
    "errorLog",
    "checkpoints",
    "notes",
    "journal",
    "promptLibrary",
    "validation",
  ];

  for (const key of requiredKeys) {
    if (!(key in data)) throw new Error(`Missing IELTS data key: ${key}`);
  }

  for (const prompt of data.promptLibrary) {
    if (!prompt.path.startsWith("prompts/")) throw new Error(`Unexpected prompt path: ${prompt.path}`);
  }
}

async function readOptionalMarkdown(path) {
  try {
    const markdown = await readFile(resolve(projectDir, path), "utf8");
    return parseFrontmatter(markdown);
  } catch {
    return { attributes: {}, body: "" };
  }
}

async function buildData() {
  const readme = await readOptionalMarkdown("README.md");

  const data = {
    build: {
      generatedAt: "2026-07-06",
      source: "projects/language/ielts-academic/scripts/build-ielts-data.mjs",
    },
    scoreProfile: {
      target: "Overall 8.0",
      evidenceBasis: "Pending diagnostic input",
      confidence: "Low",
      unverifiedDimensions: ["pronunciation", "timed writing", "listening accuracy"],
    },
    scoreHistory: [
      {
        label: "Initial placeholder",
        overall: "Unverified",
      },
    ],
    errorLog: [
      {
        skill: "Writing",
        pattern: "Error log not populated yet",
        priority: "Pending diagnosis",
        nextAction: "Run the diagnostic input template before prioritizing errors.",
      },
    ],
    checkpoints: [
      {
        week: "Week 2",
        title: "Feasibility check",
        focus: "Confirm weekly workload and first diagnostic signal.",
      },
      {
        week: "Week 6",
        title: "Correction checkpoint",
        focus: "Rebalance plan against persistent error patterns.",
      },
      {
        week: "Week 8",
        title: "Readiness check",
        focus: "Validate exam readiness with calibrated mocks.",
      },
    ],
    notes: [
      {
        source: "README.md",
        title: readme.attributes.title || "Project entry",
        body: "Use the existing Markdown materials as source of truth until later data extraction tasks expand this reader.",
      },
    ],
    journal: [
      {
        date: "TBD",
        title: "First diagnostic session",
        body: "Record diagnostic results before making claims about personal weaknesses.",
      },
    ],
    promptLibrary: [
      {
        mode: "orchestrator",
        title: "IELTS Academic orchestrator",
        path: "prompts/orchestrator.md",
      },
      {
        mode: "run modes",
        title: "Run modes",
        path: "prompts/run-modes.md",
      },
      {
        mode: "validation",
        title: "Output contract",
        path: "prompts/output-contract.md",
      },
    ],
    validation: [
      {
        type: "contract",
        title: "Output contract checklist",
        status: "Structural reader entry only; later tasks can bind full checklist data.",
      },
    ],
  };

  validateReferences(data);
  return data;
}

const data = await buildData();
await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(data, null, 2)}\n`);
