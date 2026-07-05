import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const foundationsDir = dirname(scriptDir);
const modulesDir = join(foundationsDir, "roadmap", "modules");
const outputPath = join(foundationsDir, "roadmap", "roadmap-data.json");

const MODULES = [
  ["overview", "Overview"],
  ["coding", "Coding"],
  ["llm-systems", "LLM Systems"],
  ["agent-design", "Agent Design"],
  ["rag-memory", "RAG & Memory"],
  ["evals-debugging", "Evals & Debugging"],
  ["research-reading", "Research Reading"],
  ["behavioral-strategy", "Behavioral / Strategy"],
  ["logs", "Logs"],
];

const VALID_STATUSES = new Set(["not-started", "learning", "review", "done"]);
const NOTE_GROUP_LABELS = new Set(["核心理解", "常见误区", "关键提醒", "相关资料", "面试转译", "复习提示"]);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

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

function splitSubsections(markdown) {
  const blocks = [];
  let currentTitle = "";
  let currentLines = [];
  let inCode = false;

  function flush() {
    if (!currentTitle) return;
    blocks.push({
      title: currentTitle,
      markdown: currentLines.join("\n").trim(),
    });
    currentLines = [];
  }

  for (const line of String(markdown ?? "").split("\n")) {
    if (line.startsWith("```")) inCode = !inCode;
    if (!inCode && line.startsWith("### ")) {
      flush();
      currentTitle = line.replace(/^### /, "").trim();
      continue;
    }
    if (currentTitle) currentLines.push(line);
  }

  flush();
  return blocks;
}

function renderInline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function renderMarkdown(markdown) {
  const lines = String(markdown ?? "").split("\n");
  const blocks = [];
  let paragraph = [];
  let list = [];
  let orderedList = [];
  let inCode = false;
  let codeLines = [];
  let codeLanguage = "";

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (list.length > 0) {
      blocks.push(`<ul>${list.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ul>`);
      list = [];
    }
    if (orderedList.length > 0) {
      blocks.push(`<ol>${orderedList.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ol>`);
      orderedList = [];
    }
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) {
        blocks.push(`<pre><code data-language="${escapeHtml(codeLanguage)}">${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        inCode = false;
        codeLines = [];
        codeLanguage = "";
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeLanguage = line.slice(3).trim();
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    if (/^### /.test(line)) {
      flushParagraph();
      flushList();
      blocks.push(`<h3>${renderInline(line.replace(/^### /, ""))}</h3>`);
      continue;
    }

    const taskMatch = line.match(/^- \[( |x)\] (.+)$/i);
    const listMatch = line.match(/^- (.+)$/);
    const orderedMatch = line.match(/^\d+\. (.+)$/);
    if (taskMatch) {
      flushParagraph();
      orderedList = [];
      list.push(`${taskMatch[1].toLowerCase() === "x" ? "Done: " : "Open: "}${taskMatch[2]}`);
      continue;
    }
    if (listMatch) {
      flushParagraph();
      orderedList = [];
      list.push(listMatch[1]);
      continue;
    }
    if (orderedMatch) {
      flushParagraph();
      list = [];
      orderedList.push(orderedMatch[1]);
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }

    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();
  return blocks.join("\n");
}

function stripMarkdown(markdown) {
  return String(markdown ?? "")
    .replace(/^---[\s\S]*?---/, "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[#>*_`\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function stripHtml(html) {
  return String(html ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
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
      return {
        id: `timeline-${index + 1}`,
        label: labelMatch?.[1] ?? `Step ${index + 1}`,
        text: labelMatch?.[2] ?? text,
        status: /进行中|current|in-progress/i.test(text) ? "current" : index < 2 ? "done" : "open",
      };
    });
}

function splitNoteGroups(markdown) {
  const groups = [];
  let currentLabel = "";
  let currentLines = [];
  let inCode = false;

  function flush() {
    if (!currentLabel) return;
    const markdownBody = currentLines.join("\n").trim();
    groups.push({
      label: currentLabel,
      body: renderMarkdown(markdownBody),
      text: stripMarkdown(markdownBody),
    });
    currentLines = [];
  }

  for (const line of String(markdown ?? "").split("\n")) {
    if (line.startsWith("```")) inCode = !inCode;
    const labelMatch = !inCode ? line.match(/^([^：:]{2,12})[：:]$/) : null;
    if (labelMatch && NOTE_GROUP_LABELS.has(labelMatch[1])) {
      flush();
      currentLabel = labelMatch[1];
      continue;
    }
    if (currentLabel) currentLines.push(line);
  }

  flush();
  return groups;
}

function buildKnowledgeNotes(moduleId, knowledgeMarkdown) {
  return splitSubsections(knowledgeMarkdown).map((block) => {
    const text = stripMarkdown(block.markdown);
    return {
      id: `${moduleId}-${slugifySection(block.title) || "note"}`,
      title: block.title,
      body: renderMarkdown(block.markdown),
      text,
      groups: splitNoteGroups(block.markdown),
    };
  });
}

function buildSearchEntries(id, title, rawSections, knowledgeNotes) {
  const sectionEntries = Object.entries(rawSections)
    .map(([sectionTitle, sectionMarkdown]) => ({
      id: `${id}-${slugifySection(sectionTitle) || "section"}`,
      type: "section",
      moduleId: id,
      moduleTitle: title,
      sectionTitle,
      text: stripMarkdown(sectionMarkdown),
    }))
    .filter((entry) => entry.text.length > 20);

  const noteEntries = knowledgeNotes
    .map((note) => ({
      id: note.id,
      type: "knowledge-note",
      moduleId: id,
      moduleTitle: title,
      sectionTitle: note.title,
      text: note.text,
    }))
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
    Object.entries(rawSections).map(([sectionTitle, sectionMarkdown]) => [sectionTitle, renderMarkdown(sectionMarkdown)]),
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
    knowledgeNotes: buildKnowledgeNotes(id, rawSections["知识笔记"] ?? ""),
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
