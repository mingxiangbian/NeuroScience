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

const VALID_STATUSES = new Set(["not-started", "in-progress", "review", "done"]);

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

function validateModule(record, expectedId, expectedTitle) {
  if (record.id !== expectedId) throw new Error(`${expectedId} has id ${record.id}`);
  if (record.title !== expectedTitle) throw new Error(`${expectedId} has title ${record.title}`);
  if (!VALID_STATUSES.has(record.status)) throw new Error(`${expectedId} has invalid status ${record.status}`);
  if (!Number.isFinite(record.progress) || record.progress < 0 || record.progress > 100) {
    throw new Error(`${expectedId} has invalid progress ${record.progress}`);
  }
  if (!record.lastUpdated) throw new Error(`${expectedId} is missing lastUpdated`);
  if (Object.keys(record.sections).length === 0) throw new Error(`${expectedId} has no sections`);
}

function buildModule([id, title]) {
  const markdownPath = join(modulesDir, `${id}.md`);
  const markdown = readFileSync(markdownPath, "utf8");
  const parsed = parseFrontmatter(markdown, `${id}.md`);
  const rawSections = splitSections(parsed.content);
  const sections = Object.fromEntries(
    Object.entries(rawSections).map(([sectionTitle, sectionMarkdown]) => [sectionTitle, renderMarkdown(sectionMarkdown)]),
  );
  const record = {
    id: parsed.data.id,
    title: parsed.data.title,
    status: parsed.data.status,
    progress: Number(parsed.data.progress),
    lastUpdated: parsed.data.last_updated,
    priority: parsed.data.priority ?? "medium",
    sections,
    searchText: `${title} ${stripMarkdown(parsed.content)}`,
  };
  validateModule(record, id, title);
  return record;
}

const roadmapData = {
  generatedAt: new Date().toISOString(),
  project: {
    id: "foundations",
    title: "基石",
    targetRole: "Agent / LLM Systems Engineer",
  },
  modules: MODULES.map(buildModule),
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(roadmapData, null, 2)}\n`);
