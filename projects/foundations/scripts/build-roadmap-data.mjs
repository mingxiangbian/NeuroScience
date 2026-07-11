import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  markdownToSafeHtml,
  parseKnowledgeArticles,
} from "./roadmap-markdown.mjs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const foundationsDir = dirname(scriptDir);
const modulesDir = join(foundationsDir, "roadmap", "modules");
const outputPath = join(foundationsDir, "roadmap", "roadmap-data.json");

const MODULES = [
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

const VALID_STATUSES = new Set(["not-started", "in-progress", "learning", "review", "done"]);

function parseFrontmatter(markdown, fileLabel) {
  const match = markdown.match(/^---\n(?<body>[\s\S]*?)\n---\n(?<content>[\s\S]*)$/);
  if (!match?.groups) throw new Error(`${fileLabel} is missing frontmatter`);
  const data = {};
  for (const line of match.groups.body.split("\n")) {
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    data[key] = value;
  }
  return { data, content: match.groups.content.trim() };
}

function splitSections(content) {
  const sections = {};
  const matches = Array.from(content.matchAll(/^## (.+)$/gm));
  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const next = matches[index + 1];
    const title = current[1].trim();
    const start = current.index + current[0].length;
    const end = next?.index ?? content.length;
    sections[title] = content.slice(start, end).trim();
  }
  return sections;
}

function stripMarkdown(markdown) {
  return String(markdown ?? "")
    .replace(/^---[\s\S]*?---/, "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#>*_`\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function slugifySection(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function extractTimelineItems(markdown) {
  return String(markdown ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^- /.test(line))
    .map((line, index) => {
      const text = line.replace(/^- /, "").trim();
      const labelMatch = text.match(/^(Week \d+|Days \d+-\d+|Day \d+\+|Days \d+\+|[^：:]{1,18})[：:]\s*(.+)$/);
      const itemText = labelMatch?.[2] ?? text;
      return {
        id: `timeline-${index + 1}`,
        label: labelMatch?.[1] ?? `Step ${index + 1}`,
        text: itemText,
        status: /^(?:已完成|done)(?:[；;:\s]|$)/i.test(itemText)
          ? "done"
          : /^(?:进行中|current|in-progress)(?:[；;:\s]|$)/i.test(itemText)
            ? "current"
            : /^(?:未开始|pending|open)(?:[；;:\s]|$)/i.test(itemText)
              ? "open"
              : index < 2
                ? "done"
                : "open",
      };
    });
}

function buildSearchEntries(id, title, rawSections, knowledgeNotes) {
  const sectionEntries = Object.entries(rawSections)
    .map(([sectionTitle, sectionMarkdown]) => {
      const rendered = markdownToSafeHtml(sectionMarkdown);
      return {
        id: `${id}-${slugifySection(sectionTitle) || "section"}`,
        type: "section",
        moduleId: id,
        moduleTitle: title,
        articleTitle: "",
        sectionTitle,
        text: rendered.text,
      };
    })
    .filter((entry) => entry.text.length > 20);

  const noteEntries = knowledgeNotes.flatMap((note) => [
    {
      id: note.id,
      type: "knowledge-note",
      moduleId: id,
      moduleTitle: title,
      articleTitle: note.title,
      sectionTitle: note.title,
      text: note.text,
    },
    ...note.sections.map((section) => ({
      id: section.id,
      type: "knowledge-section",
      moduleId: id,
      moduleTitle: title,
      articleTitle: note.title,
      sectionTitle: section.title,
      text: section.text,
    })),
  ])
    .filter((entry) => entry.text.length > 20);

  return [...sectionEntries, ...noteEntries];
}

function validateModule(record, expectedId, expectedTitle) {
  if (record.id !== expectedId) throw new Error(`${expectedId} has id ${record.id}`);
  if (record.title !== expectedTitle) throw new Error(`${expectedId} has title ${record.title}`);
  if (!VALID_STATUSES.has(record.status)) throw new Error(`${expectedId} has invalid status ${record.status}`);
  if (!Number.isFinite(record.learningProgress) || record.learningProgress < 0 || record.learningProgress > 100) {
    throw new Error(`${expectedId} has invalid learning progress ${record.learningProgress}`);
  }
  if (!record.lastUpdated) throw new Error(`${expectedId} is missing lastUpdated`);
  if (Object.keys(record.sections).length === 0) throw new Error(`${expectedId} has no sections`);
  if (!Array.isArray(record.searchEntries) || record.searchEntries.length === 0) throw new Error(`${expectedId} has no search entries`);
  if (!Array.isArray(record.knowledgeNotes)) throw new Error(`${expectedId} has invalid knowledge notes`);
  if (!Array.isArray(record.timeline)) throw new Error(`${expectedId} has invalid timeline`);
}

function buildModule([id, title]) {
  const markdownPath = join(modulesDir, `${id}.md`);
  const markdown = readFileSync(markdownPath, "utf8");
  const parsed = parseFrontmatter(markdown, `${id}.md`);
  const rawSections = splitSections(parsed.content);
  const sections = Object.fromEntries(
    Object.entries(rawSections).map(([sectionTitle, sectionMarkdown]) => [sectionTitle, markdownToSafeHtml(sectionMarkdown).html]),
  );
  const sectionIds = Object.fromEntries(
    Object.keys(rawSections).map((sectionTitle) => [sectionTitle, `${id}-${slugifySection(sectionTitle) || "section"}`]),
  );
  const record = {
    id: parsed.data.id,
    title: parsed.data.title,
    status: parsed.data.status,
    learningProgress: Number(parsed.data.learning_progress),
    lastUpdated: parsed.data.last_updated,
    priority: parsed.data.priority ?? "medium",
    sections,
    sectionIds,
    knowledgeNotes: parseKnowledgeArticles(id, rawSections["知识笔记"] ?? ""),
    timeline: extractTimelineItems(rawSections["时间线"] ?? ""),
    searchText: `${title} ${stripMarkdown(parsed.content)}`,
  };
  record.searchEntries = buildSearchEntries(id, title, rawSections, record.knowledgeNotes);
  validateModule(record, id, title);
  return record;
}

const modules = MODULES.map(buildModule);
const latestDate = modules.map((module) => module.lastUpdated).sort().at(-1);
const dashboardModuleId = "overview";
const learningModules = modules.filter((module) => module.id !== dashboardModuleId);
const overallLearningProgress = Math.round(
  learningModules.reduce((sum, module) => sum + module.learningProgress, 0) / learningModules.length,
);

const roadmapData = {
  generatedAt: `${latestDate}T00:00:00.000Z`,
  project: {
    id: "foundations",
    title: "基石",
    targetRole: "Agent / LLM Systems Engineer",
    dashboardModuleId,
    overallLearningProgress,
  },
  modules,
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
