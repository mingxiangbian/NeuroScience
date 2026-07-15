import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
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

function parseKnowledgeRelations(raw, fileLabel) {
  let relations;
  try {
    relations = JSON.parse(raw ?? "[]");
  } catch (error) {
    throw new Error(`${fileLabel} has invalid knowledge_relations JSON: ${error.message}`);
  }

  if (!Array.isArray(relations)) {
    throw new Error(`${fileLabel} knowledge_relations must be an array`);
  }

  return relations.map((relation, index) => {
    const relationLabel = `${fileLabel} knowledge_relations[${index}]`;
    if (!relation || typeof relation !== "object" || Array.isArray(relation)) {
      throw new Error(`${relationLabel} must be an object`);
    }
    for (const field of ["prerequisiteId", "type", "rationale"]) {
      if (typeof relation[field] !== "string" || !relation[field].trim()) {
        throw new Error(`${relationLabel} is missing ${field}`);
      }
    }
    if (relation.type !== "prerequisite") {
      throw new Error(`${relationLabel} has unsupported type ${relation.type}`);
    }
    return {
      prerequisiteId: relation.prerequisiteId.trim(),
      type: relation.type,
      rationale: relation.rationale.trim(),
    };
  });
}

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

function renderSectionHtml(markdown) {
  const html = markdownToSafeHtml(markdown).html;
  return html.replace(/<(\/?)h1>/g, "<$1h3>");
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
    Object.entries(rawSections).map(([sectionTitle, markdown]) => [sectionTitle, renderSectionHtml(markdown)]),
  );
  const record = {
    id: parsed.data.id,
    title: parsed.data.title,
    status: parsed.data.status,
    learningProgress: Number(parsed.data.learning_progress),
    lastUpdated: parsed.data.last_updated,
    priority: parsed.data.priority ?? "medium",
    decisionRole: parsed.data.decision_role ?? "",
    graphRole: parsed.data.graph_role ?? "concept",
    knowledgeRelations: parseKnowledgeRelations(parsed.data.knowledge_relations, `${id}.md`),
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

export function buildKnowledgeGraph(modules, dashboardModuleId = "overview") {
  const seenModuleIds = new Set();
  for (const module of modules) {
    if (seenModuleIds.has(module.id)) {
      throw new Error(`knowledge graph has duplicate module id ${module.id}`);
    }
    seenModuleIds.add(module.id);
  }

  const learningModules = modules.filter((module) => module.id !== dashboardModuleId);
  const moduleIds = new Set(learningModules.map((module) => module.id));
  const orderIndex = new Map(learningModules.map((module, index) => [module.id, index]));
  const edges = [];

  const nodes = learningModules.map((module) => {
    if (typeof module.decisionRole !== "string" || !module.decisionRole.trim()) {
      throw new Error(`knowledge graph node ${module.id} is missing decisionRole`);
    }
    if (!new Set(["concept", "support"]).has(module.graphRole)) {
      throw new Error(`knowledge graph node ${module.id} has invalid graphRole ${module.graphRole}`);
    }
    if (!Array.isArray(module.knowledgeRelations)) {
      throw new Error(`knowledge graph node ${module.id} has invalid relations`);
    }
    if (module.graphRole === "support" && module.knowledgeRelations.length > 0) {
      throw new Error(`knowledge graph support node ${module.id} cannot declare prerequisites`);
    }

    const prerequisiteIds = new Set();
    const relations = module.knowledgeRelations.map((relation) => {
      const { prerequisiteId, type, rationale } = relation;
      if (!moduleIds.has(prerequisiteId)) {
        throw new Error(`knowledge graph node ${module.id} has unknown dependency ${prerequisiteId}`);
      }
      if (prerequisiteId === module.id) {
        throw new Error(`knowledge graph node ${module.id} cannot depend on itself`);
      }
      if (prerequisiteIds.has(prerequisiteId)) {
        throw new Error(`knowledge graph node ${module.id} has duplicate dependency ${prerequisiteId}`);
      }
      if (type !== "prerequisite" || typeof rationale !== "string" || !rationale.trim()) {
        throw new Error(`knowledge graph node ${module.id} has invalid relation metadata for ${prerequisiteId}`);
      }
      prerequisiteIds.add(prerequisiteId);
      const normalizedRelation = { prerequisiteId, type, rationale: rationale.trim() };
      edges.push({
        sourceId: prerequisiteId,
        targetId: module.id,
        type,
        rationale: normalizedRelation.rationale,
      });
      return normalizedRelation;
    });

    return {
      id: module.id,
      title: module.title,
      decisionRole: module.decisionRole.trim(),
      graphRole: module.graphRole,
      relations,
    };
  });

  const indegree = new Map(nodes.map((node) => [node.id, 0]));
  const dependents = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    indegree.set(edge.targetId, indegree.get(edge.targetId) + 1);
    dependents.get(edge.sourceId).push(edge.targetId);
  }

  const ready = nodes
    .filter((node) => indegree.get(node.id) === 0)
    .map((node) => node.id)
    .sort((left, right) => orderIndex.get(left) - orderIndex.get(right));
  const topologicalOrder = [];

  while (ready.length > 0) {
    const currentId = ready.shift();
    topologicalOrder.push(currentId);
    for (const dependentId of dependents.get(currentId)) {
      const nextIndegree = indegree.get(dependentId) - 1;
      indegree.set(dependentId, nextIndegree);
      if (nextIndegree === 0) {
        ready.push(dependentId);
        ready.sort((left, right) => orderIndex.get(left) - orderIndex.get(right));
      }
    }
  }

  if (topologicalOrder.length !== nodes.length) {
    const cyclicIds = nodes
      .filter((node) => indegree.get(node.id) > 0)
      .map((node) => node.id)
      .join(", ");
    throw new Error(`knowledge graph contains a dependency cycle involving ${cyclicIds}`);
  }

  return { version: 1, nodes, edges, topologicalOrder };
}

export function buildFinanceRoadmapData() {
  const moduleRecords = MODULES.map(buildModule);
  const knowledgeGraph = buildKnowledgeGraph(moduleRecords);
  const modules = moduleRecords.map(({ decisionRole, graphRole, knowledgeRelations, ...module }) => module);
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
      knowledgeGraph,
    },
    modules,
  };

  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
  return roadmapData;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  buildFinanceRoadmapData();
}
