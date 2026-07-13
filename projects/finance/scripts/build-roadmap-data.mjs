import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  markdownToSafeHtml,
  parseKnowledgeArticles,
} from "../../foundations/scripts/roadmap-markdown.mjs";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const financeDir = dirname(scriptDir);
const modulesDir = join(financeDir, "roadmap", "modules");
const outputPath = join(financeDir, "roadmap", "roadmap-data.json");

const MODULES = [
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

const VALID_STATUSES = new Set(["not-started", "in-progress", "learning", "review", "done"]);

function parseFrontmatter(markdown, fileLabel) {
  const match = markdown.match(/^---\n(?<body>[\s\S]*?)\n---\n(?<content>[\s\S]*)$/);
  if (!match?.groups) throw new Error(`${fileLabel} is missing frontmatter`);
  const data = {};
  for (const line of match.groups.body.split("\n")) {
    const separator = line.indexOf(":");
    if (separator === -1) continue;
    data[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
  }
  return { data, content: match.groups.content.trim() };
}

function splitSections(content) {
  const sections = {};
  const matches = [];
  let activeFence = null;
  let offset = 0;

  for (const line of content.split("\n")) {
    const fenceMatch = line.match(/^[ \t]{0,3}(`{3,}|~{3,})(.*)$/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (!activeFence) {
        activeFence = { character: marker[0], length: marker.length };
      } else if (
        marker[0] === activeFence.character
        && marker.length >= activeFence.length
        && fenceMatch[2].trim() === ""
      ) {
        activeFence = null;
      }
    } else if (!activeFence) {
      const headingMatch = line.match(/^## (.+)$/);
      if (headingMatch) matches.push({ index: offset, length: line.length, title: headingMatch[1].trim() });
    }
    offset += line.length + 1;
  }

  for (const [index, current] of matches.entries()) {
    const next = matches[index + 1];
    const start = current.index + current.length;
    sections[current.title] = content.slice(start, next?.index ?? content.length).trim();
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
      const labelMatch = text.match(/^([^：:]{1,24})[：:]\s*(.+)$/);
      return {
        id: `timeline-${index + 1}`,
        label: labelMatch?.[1] ?? `步骤 ${index + 1}`,
        text: labelMatch?.[2] ?? text,
        status: "open",
      };
    });
}

function buildSearchEntries(id, title, rawSections, knowledgeNotes) {
  const sectionEntries = Object.entries(rawSections)
    .filter(([sectionTitle]) => sectionTitle !== "知识笔记")
    .map(([sectionTitle, markdown]) => {
      const rendered = markdownToSafeHtml(markdown);
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
  ]).filter((entry) => entry.text.length > 20);

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
  const markdown = readFileSync(join(modulesDir, `${id}.md`), "utf8");
  const parsed = parseFrontmatter(markdown, `${id}.md`);
  const rawSections = splitSections(parsed.content);
  const sections = Object.fromEntries(
    Object.entries(rawSections).map(([sectionTitle, markdown]) => [sectionTitle, markdownToSafeHtml(markdown).html]),
  );
  const record = {
    id: parsed.data.id,
    title: parsed.data.title,
    status: parsed.data.status,
    learningProgress: Number(parsed.data.learning_progress),
    lastUpdated: parsed.data.last_updated,
    priority: parsed.data.priority ?? "medium",
    sections,
    sectionIds: Object.fromEntries(
      Object.keys(rawSections).map((sectionTitle) => [sectionTitle, `${id}-${slugifySection(sectionTitle) || "section"}`]),
    ),
    knowledgeNotes: parseKnowledgeArticles(id, rawSections["知识笔记"] ?? ""),
    timeline: extractTimelineItems(rawSections["时间线"] ?? ""),
    searchText: `${title} ${stripMarkdown(parsed.content)}`,
  };
  record.searchEntries = buildSearchEntries(id, title, rawSections, record.knowledgeNotes);
  validateModule(record, id, title);
  return record;
}

const modules = MODULES.map(buildModule);
const learningModules = modules.filter((module) => module.id !== "overview");
const latestDate = modules.map((module) => module.lastUpdated).sort().at(-1);

const roadmapData = {
  generatedAt: `${latestDate}T00:00:00.000Z`,
  project: {
    id: "finance",
    title: "投资",
    targetRole: "长期投资学习",
    dashboardModuleId: "overview",
    glossaryModuleId: "terms-further-reading",
    dashboardFocus: "从第 1 周开始：确认个人财务安全边界，再学习收益、风险与复利。",
    overallLearningProgress: Math.round(
      learningModules.reduce((sum, module) => sum + module.learningProgress, 0) / learningModules.length,
    ),
  },
  modules,
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
