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
  ["career-roadmap", "Career Roadmap"],
  ["llm-systems", "LLM Systems"],
  ["rag-memory", "Lifelong Memory"],
  ["agent-design", "Agent Runtime"],
  ["coding", "Engineering Foundations"],
  ["evals-debugging", "Evals & Diagnostics"],
  ["research-reading", "Research Reading"],
  ["logs", "Ledger & Calibration"],
  ["interview-sprint", "Interview Sprint"],
  ["behavioral-strategy", "Behavioral / Strategy"],
  ["overview", "Interview Overview"],
];

const VALID_STATUSES = new Set(["not-started", "in-progress", "learning", "review", "done"]);
const VALID_PLAN_SCOPES = new Set(["long-term", "interview"]);
const VALID_NAVIGATION_GROUPS = new Set(["north-star", "systems", "practice", "interview"]);
const VALID_MODULE_ROLES = new Set(["control", "domain", "support", "record", "interview"]);
const UNIT_GROUP_STATUSES = new Map([
  ["活动单元", "active"],
  ["近期队列", "frozen"],
]);

const NAVIGATION_GROUPS = [
  {
    id: "north-star",
    title: "长期总控",
    scope: "long-term",
    items: [{ type: "module", moduleId: "career-roadmap" }],
  },
  {
    id: "systems",
    title: "贾维斯子系统",
    scope: "long-term",
    items: [
      { type: "module", moduleId: "llm-systems" },
      { type: "slot", subsystemId: "2", title: "人格与情感", status: "frozen", note: "U4–U6 到队头再定义" },
      { type: "module", moduleId: "rag-memory" },
      { type: "slot", subsystemId: "4", title: "实时多模态交互", status: "frozen", note: "到相关单元再定义" },
      { type: "module", moduleId: "agent-design" },
    ],
  },
  {
    id: "practice",
    title: "构建与验证",
    scope: "long-term",
    items: [
      { type: "module", moduleId: "coding" },
      { type: "module", moduleId: "evals-debugging" },
      { type: "module", moduleId: "research-reading" },
      { type: "module", moduleId: "logs" },
    ],
  },
  {
    id: "interview",
    title: "临时面试突击",
    scope: "interview",
    items: [
      { type: "module", moduleId: "interview-sprint" },
      { type: "module", moduleId: "behavioral-strategy" },
      { type: "module", moduleId: "overview" },
    ],
  },
];

const JARVIS_SUBSYSTEMS = [
  { id: "1", key: "base-model", title: "基座模型", englishTitle: "BASE MODEL", status: "mapped", moduleIds: ["llm-systems"], note: "懂原理、边界与供给约束" },
  { id: "2", key: "persona", title: "人格与情感", englishTitle: "PERSONA", status: "frozen", moduleIds: [], note: "U4–U6 到队头再定义" },
  { id: "3", key: "memory", title: "终身记忆", englishTitle: "LIFELONG MEMORY", status: "mapped", moduleIds: ["rag-memory"], note: "写入、整合、遗忘与反思" },
  { id: "4", key: "multimodal", title: "实时多模态交互", englishTitle: "REALTIME MULTIMODAL", status: "frozen", moduleIds: [], note: "到相关单元再定义" },
  { id: "5", key: "agent-runtime", title: "Agent 执行", englishTitle: "AGENT EXEC", status: "mapped", moduleIds: ["agent-design"], note: "工具、规划、沙箱与恢复" },
  { id: "6", key: "system-layer", title: "系统层", englishTitle: "SYSTEM LAYER", status: "mapped", moduleIds: ["llm-systems", "coding"], note: "推理、延迟、成本与工程地基" },
];

const DEPTH_LEVEL_IDS = new Map([
  ["理解", "understand"],
  ["实现", "implement"],
  ["验证", "verify"],
  ["诊断", "diagnose"],
  ["综合/创新", "integrate-innovate"],
]);
const CIRCLED_SUBSYSTEM_IDS = new Map([
  ["①", "1"],
  ["②", "2"],
  ["③", "3"],
  ["④", "4"],
  ["⑤", "5"],
  ["⑥", "6"],
]);
const STAGE_NUMBERS = new Map([
  ["一", 1],
  ["二", 2],
  ["三", 3],
  ["四", 4],
]);

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

function parseList(value) {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugifySection(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function extractSubsection(markdown, subsectionTitle) {
  const source = String(markdown ?? "");
  const subsections = Array.from(source.matchAll(/^### (.+)$/gm));
  const index = subsections.findIndex((match) => match[1].trim() === subsectionTitle);
  if (index === -1) return "";
  const current = subsections[index];
  const next = subsections[index + 1];
  const start = current.index + current[0].length;
  return source.slice(start, next?.index ?? source.length).trim();
}

function extractUnitGoalMappings(markdown) {
  const sourceSection = "行动 → 子系统 → 阶段映射";
  const source = extractSubsection(markdown, sourceSection);
  const mappings = new Map();
  const lines = source.split("\n").map((line) => line.trim()).filter((line) => line.startsWith("- U"));

  for (const line of lines) {
    const match = line.match(/^- U(\d+)[–—-]U(\d+)[（(](.+?)[）)]\s*→\s*(.+?)\s*→\s*(.+?)[。.]?$/);
    if (!match) continue;
    const start = Number(match[1]);
    const end = Number(match[2]);
    const actionSequence = match[3].trim();
    const targetText = match[4].trim();
    const subsystemIds = targetText.startsWith("全部")
      ? JARVIS_SUBSYSTEMS.map((subsystem) => subsystem.id)
      : Array.from(targetText.matchAll(/[①②③④⑤⑥]/g), (item) => CIRCLED_SUBSYSTEM_IDS.get(item[0]));
    const pathLabel = targetText.match(/[（(](.+?)[）)]/)?.[1].trim() ?? actionSequence;

    if (subsystemIds.length === 0) throw new Error(`Career unit mapping has no subsystem ids: ${line}`);
    for (let number = start; number <= end; number += 1) {
      mappings.set(`U${number}`, {
        subsystemIds,
        pathLabel,
        stageLabel: match[5].trim(),
        sourceSection,
      });
    }
  }

  return mappings;
}

function extractDepthLevels(markdown) {
  const sourceSection = "深度阶梯（候选专长的定向仪）";
  const source = extractSubsection(markdown, sourceSection);
  const match = source.match(/统一五层：\*\*(.+?)\*\*/);
  if (!match) throw new Error("Career Roadmap is missing its five depth levels");

  return match[1].split("→").map((label, index) => {
    const normalizedLabel = label.trim();
    const id = DEPTH_LEVEL_IDS.get(normalizedLabel);
    if (!id) throw new Error(`Unsupported Career Roadmap depth level: ${normalizedLabel}`);
    return {
      id,
      label: normalizedLabel,
      order: index + 1,
    };
  });
}

function buildEvidenceMatrix(depthLevels) {
  return {
    basis: "explicit-evidence-only",
    sourceSection: "深度阶梯（候选专长的定向仪）",
    depthLevels,
    rows: JARVIS_SUBSYSTEMS.map((subsystem) => ({
      subsystemId: subsystem.id,
      cells: depthLevels.map((level) => ({
        depthLevelId: level.id,
        state: "unassessed",
        evidenceRefs: [],
      })),
    })),
  };
}

function extractCareerOutcomeGates(markdown) {
  return String(markdown ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^- 阶段[一二三四]\s*·/.test(line))
    .map((line) => {
      const match = line.match(/^- 阶段([一二三四])\s*·\s*([^：:]+)[：:]\s*(.+)$/);
      if (!match) throw new Error(`Unsupported Career Roadmap outcome gate: ${line}`);
      const order = STAGE_NUMBERS.get(match[1]);
      const rawOutcome = match[3].trim();
      const sourceStatus = rawOutcome.match(/^(进行中|未开始)[；;]\s*/)?.[1];
      const withoutStatus = rawOutcome.replace(/^(进行中|未开始)[；;]\s*/, "");
      const contextMatch = withoutStatus.match(/^([^：:]+)[：:]\s*(.+)$/);
      return {
        id: `stage-${order}`,
        label: `阶段${match[1]}`,
        order,
        status: sourceStatus === "进行中" ? "current" : "planned",
        window: {
          label: match[2].trim(),
          commitment: "flexible",
        },
        context: contextMatch?.[1].trim() ?? "",
        outcome: contextMatch?.[2].trim() ?? withoutStatus,
        sourceSection: "时间线",
      };
    });
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

function extractSettlementUnits(markdown, goalMappings) {
  const source = String(markdown ?? "");
  const subsections = Array.from(source.matchAll(/^### (.+)$/gm));
  const units = [];

  for (let index = 0; index < subsections.length; index += 1) {
    const current = subsections[index];
    const next = subsections[index + 1];
    const sectionTitle = current[1].trim();
    const start = current.index + current[0].length;
    const end = next?.index ?? source.length;
    const sectionBody = source.slice(start, end);
    const unitMatches = Array.from(sectionBody.matchAll(
      /^\d+\.\s+\*\*(U\d+)\s+(.+?)\*\*\s*[（(](\d+)(?:\s*[–—-]\s*(\d+))?\s+sessions?\s*[，,]\s*([^）)]+)[）)]\s*[：:]\s*(.+)$/gm,
    ));

    if (unitMatches.length === 0) continue;

    const groupName = Array.from(UNIT_GROUP_STATUSES.keys()).find((name) => sectionTitle.startsWith(name));
    if (!groupName) throw new Error(`Unsupported settlement unit group: ${sectionTitle}`);

    for (const match of unitMatches) {
      const minSessions = Number(match[3]);
      const rawDescription = match[6].trim();
      const normalizedDescription = rawDescription.replaceAll("**", "");
      const renderedDescription = markdownToSafeHtml(normalizedDescription);
      const description = renderedDescription.text;
      const expectedResult = rawDescription.match(/\*\*(预期结果：.+?)\*\*/)?.[1];
      const insightSentence = description
        .split(/[。！？]/)
        .map((sentence) => sentence.trim())
        .find((sentence) => sentence.includes("顿悟点"));
      const firstAction = description.split(/[；。]/).map((sentence) => sentence.trim()).find(Boolean) ?? description;
      const goalMapping = goalMappings.get(match[1]);
      if (!goalMapping) throw new Error(`Career settlement unit ${match[1]} has no explicit subsystem mapping`);
      units.push({
        id: match[1],
        title: match[2].trim(),
        type: match[5].trim(),
        sessions: {
          min: minSessions,
          max: Number(match[4] ?? minSessions),
        },
        status: UNIT_GROUP_STATUSES.get(groupName),
        taskId: `career-roadmap__unit__${match[1]}`,
        description,
        bodyHtml: renderedDescription.html,
        nextAction: firstAction.replace(/^顺序关键[—-]+/, ""),
        insight: expectedResult ?? insightSentence ?? "",
        goalMapping,
      });
    }
  }

  return units;
}

function buildSearchEntries(id, title, rawSections, knowledgeNotes) {
  const sectionEntries = Object.entries(rawSections)
    .filter(([sectionTitle]) => sectionTitle !== "知识笔记")
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
  if (!VALID_PLAN_SCOPES.has(record.planScope)) throw new Error(`${expectedId} has invalid plan scope ${record.planScope}`);
  if (!VALID_NAVIGATION_GROUPS.has(record.navigationGroup)) throw new Error(`${expectedId} has invalid navigation group ${record.navigationGroup}`);
  if (!VALID_MODULE_ROLES.has(record.moduleRole)) throw new Error(`${expectedId} has invalid module role ${record.moduleRole}`);
  if (!record.goalRole) throw new Error(`${expectedId} is missing goal role`);
  if (!Array.isArray(record.subsystems)) throw new Error(`${expectedId} has invalid subsystems`);
  if (expectedId === "career-roadmap") {
    if (!Array.isArray(record.units) || record.units.length === 0) throw new Error(`${expectedId} has no settlement units`);
    if (new Set(record.units.map((unit) => unit.id)).size !== record.units.length) throw new Error(`${expectedId} has duplicate settlement unit ids`);
    if (record.units.filter((unit) => unit.status === "active").length !== 1) throw new Error(`${expectedId} must have exactly one active settlement unit`);
    if (record.units.some((unit) => !Array.isArray(unit.goalMapping?.subsystemIds) || unit.goalMapping.subsystemIds.length === 0)) {
      throw new Error(`${expectedId} has a settlement unit without an explicit subsystem mapping`);
    }
    if (record.evidenceMatrix?.basis !== "explicit-evidence-only") throw new Error(`${expectedId} has an invalid evidence basis`);
    if (record.evidenceMatrix.depthLevels.length !== 5) throw new Error(`${expectedId} must define five depth levels`);
    if (record.evidenceMatrix.rows.length !== JARVIS_SUBSYSTEMS.length) throw new Error(`${expectedId} must define one evidence row per subsystem`);
    for (const row of record.evidenceMatrix.rows) {
      if (row.cells.length !== record.evidenceMatrix.depthLevels.length) throw new Error(`${expectedId} has an incomplete evidence row for subsystem ${row.subsystemId}`);
      if (row.cells.some((cell) => cell.state !== "unassessed" || cell.evidenceRefs.length !== 0)) {
        throw new Error(`${expectedId} must not infer evidence states from roadmap prose or unit status`);
      }
    }
    if (record.outcomeGates.length !== 4) throw new Error(`${expectedId} must define four outcome gates`);
    if (record.outcomeGates.some((gate) => gate.window.commitment !== "flexible" || !gate.outcome)) {
      throw new Error(`${expectedId} has an invalid flexible outcome gate`);
    }
  }
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
    planScope: parsed.data.plan_scope,
    navigationGroup: parsed.data.navigation_group,
    moduleRole: parsed.data.module_role,
    goalRole: parsed.data.goal_role,
    subsystems: parseList(parsed.data.subsystems),
    sections,
    sectionIds,
    knowledgeNotes: parseKnowledgeArticles(id, rawSections["知识笔记"] ?? ""),
    timeline: extractTimelineItems(rawSections["时间线"] ?? ""),
    searchText: `${title} ${stripMarkdown(parsed.content)}`,
  };
  if (id === "career-roadmap") {
    const unitGoalMappings = extractUnitGoalMappings(rawSections["核心知识"] ?? "");
    const depthLevels = extractDepthLevels(rawSections["核心知识"] ?? "");
    record.units = extractSettlementUnits(rawSections["任务"] ?? "", unitGoalMappings);
    record.evidenceMatrix = buildEvidenceMatrix(depthLevels);
    record.outcomeGates = extractCareerOutcomeGates(rawSections["时间线"] ?? "");
  }
  record.searchEntries = buildSearchEntries(id, title, rawSections, record.knowledgeNotes);
  validateModule(record, id, title);
  return record;
}

const modules = MODULES.map(buildModule);
const latestDate = modules.map((module) => module.lastUpdated).sort().at(-1);
const dashboardModuleId = "career-roadmap";
const learningModules = modules.filter((module) => (
  module.planScope === "long-term" && !["control", "record"].includes(module.moduleRole)
));
const overallLearningProgress = Math.round(
  learningModules.reduce((sum, module) => sum + module.learningProgress, 0) / learningModules.length,
);

const roadmapData = {
  generatedAt: `${latestDate}T00:00:00.000Z`,
  project: {
    id: "foundations",
    title: "基石",
    targetGoal: "贾维斯式智能陪伴系统",
    dashboardModuleId,
    overallLearningProgress,
    navigationGroups: NAVIGATION_GROUPS,
    subsystems: JARVIS_SUBSYSTEMS,
  },
  modules,
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
