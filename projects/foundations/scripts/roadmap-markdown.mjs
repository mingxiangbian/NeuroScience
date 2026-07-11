import { marked } from "marked";
import sanitizeHtml from "sanitize-html";

export const REQUIRED_KNOWLEDGE_SECTIONS = [
  "核心定义",
  "核心机制",
  "逐步示例",
  "边界与常见错误",
  "一句话总结",
];

const SECTION_KINDS = new Map([
  ["核心定义", "definition"],
  ["核心机制", "mechanism"],
  ["逐步示例", "example"],
  ["程序流程", "flow"],
  ["代码实现", "code"],
  ["复杂度分析", "complexity"],
  ["架构图", "diagram"],
  ["概念对比", "comparison"],
  ["指标与公式", "metrics"],
  ["参考资料", "resources"],
  ["边界与常见错误", "boundary"],
  ["一句话总结", "summary"],
]);

const allowedTags = [
  "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "h5", "h6",
  "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
];

const allowedAttributes = {
  a: ["href", "title", "rel"],
  code: ["class"],
  th: ["align"],
  td: ["align"],
};

export function markdownToSafeHtml(markdown) {
  const rawHtml = marked.parse(String(markdown ?? ""), { async: false, gfm: true, breaks: false });
  const html = sanitizeHtml(rawHtml, {
    allowedTags,
    allowedAttributes,
    allowedSchemes: ["http", "https", "mailto"],
    allowProtocolRelative: false,
    transformTags: {
      a: sanitizeHtml.simpleTransform("a", { rel: "noopener noreferrer" }),
    },
  });
  const text = sanitizeHtml(html, { allowedTags: [], allowedAttributes: {} })
    .replace(/\s+/g, " ")
    .trim();
  return { html, text };
}

function slugifyTitle(title) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function splitHeadingBlocks(markdown, level) {
  const marker = `${"#".repeat(level)} `;
  const blocks = [];
  let title = "";
  let lines = [];
  let inCode = false;
  const flush = () => {
    if (!title) return;
    blocks.push({ title, markdown: lines.join("\n").trim() });
    lines = [];
  };
  for (const line of String(markdown ?? "").split("\n")) {
    if (line.startsWith("```") ) inCode = !inCode;
    if (!inCode && line.startsWith(marker)) {
      flush();
      title = line.slice(marker.length).trim();
      continue;
    }
    if (title) lines.push(line);
  }
  flush();
  return blocks;
}

function splitArticleBody(markdown) {
  const lines = String(markdown ?? "").split("\n");
  let inCode = false;
  let firstSectionIndex = lines.length;
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].startsWith("```") ) inCode = !inCode;
    if (!inCode && lines[index].startsWith("#### ")) {
      firstSectionIndex = index;
      break;
    }
  }
  return {
    introMarkdown: lines.slice(0, firstSectionIndex).join("\n").trim(),
    sectionBlocks: splitHeadingBlocks(lines.slice(firstSectionIndex).join("\n"), 4),
  };
}

function countOrderedSteps(markdown) {
  return String(markdown ?? "").split("\n").filter((line) => /^\d+\.\s+/.test(line)).length;
}

export function parseKnowledgeArticles(moduleId, markdown) {
  const ids = new Set();
  return splitHeadingBlocks(markdown, 3).map((articleBlock) => {
    const id = `${moduleId}-${slugifyTitle(articleBlock.title) || "article"}`;
    if (ids.has(id)) throw new Error(`${moduleId}: duplicate knowledge article id ${id}`);
    ids.add(id);

    const { introMarkdown, sectionBlocks } = splitArticleBody(articleBlock.markdown);
    const sectionByTitle = new Map(sectionBlocks.map((section) => [section.title, section]));
    for (const requiredTitle of REQUIRED_KNOWLEDGE_SECTIONS) {
      const required = sectionByTitle.get(requiredTitle);
      if (!required || !required.markdown.trim()) {
        throw new Error(`${moduleId} / ${articleBlock.title} is missing required section ${requiredTitle}`);
      }
    }

    const sections = sectionBlocks.map((sectionBlock) => {
      const kind = SECTION_KINDS.get(sectionBlock.title) ?? "generic";
      if (kind === "flow" && countOrderedSteps(sectionBlock.markdown) < 2) {
        throw new Error(`${moduleId} / ${articleBlock.title} / 程序流程 requires at least two ordered steps`);
      }
      const rendered = markdownToSafeHtml(sectionBlock.markdown);
      return {
        id: `${id}-${slugifyTitle(sectionBlock.title) || "section"}`,
        kind,
        title: sectionBlock.title,
        body: rendered.html,
        text: rendered.text,
      };
    });
    const intro = markdownToSafeHtml(introMarkdown);
    return {
      id,
      title: articleBlock.title,
      intro: intro.html,
      introText: intro.text,
      sections,
      text: [intro.text, ...sections.map((section) => section.text)].filter(Boolean).join(" "),
    };
  });
}
