import { marked, Renderer } from "marked";
import sanitizeHtml from "sanitize-html";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import typescript from "highlight.js/lib/languages/typescript";
import yaml from "highlight.js/lib/languages/yaml";

for (const [name, grammar] of Object.entries({
  bash,
  javascript,
  json,
  markdown,
  python,
  rust,
  typescript,
  yaml,
})) {
  hljs.registerLanguage(name, grammar);
}

const markdownRenderer = new Renderer();
const renderPlainCode = markdownRenderer.code.bind(markdownRenderer);

function getDeclaredLanguage(lang) {
  const declared = String(lang ?? "").trim().split(/\s+/, 1)[0].toLowerCase();
  return /^[a-z0-9_+-]+$/.test(declared) ? declared : "";
}

markdownRenderer.code = (token) => {
  const language = getDeclaredLanguage(token.lang);
  if (!language || language === "mermaid" || !hljs.getLanguage(language)) {
    return renderPlainCode(token);
  }
  const highlighted = hljs.highlight(token.text, {
    language,
    ignoreIllegals: true,
  }).value;
  return `<pre><code class="hljs language-${language}">${highlighted}\n</code></pre>`;
};

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
  "hr", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
];

const allowedAttributes = {
  a: ["href", "title", "rel"],
  code: ["class"],
  span: ["class"],
  th: ["align"],
  td: ["align"],
};

const allowedClasses = {
  code: ["hljs", /^language-[a-z0-9_+-]+$/],
  span: [/^hljs-[a-z0-9_-]+$/],
};

export function markdownToSafeHtml(markdown) {
  const rawHtml = marked.parse(String(markdown ?? ""), {
    async: false,
    gfm: true,
    breaks: false,
    renderer: markdownRenderer,
  });
  const html = sanitizeHtml(rawHtml, {
    allowedTags,
    allowedAttributes,
    allowedClasses,
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

function tokensToMarkdown(tokens) {
  return tokens.map((token) => token.raw ?? "").join("").trim();
}

function splitHeadingBlocks(tokens, level) {
  const blocks = [];
  let title = "";
  let contentTokens = [];
  const flush = () => {
    if (!title) return;
    blocks.push({ title, markdown: tokensToMarkdown(contentTokens), tokens: contentTokens });
    contentTokens = [];
  };
  for (const token of tokens) {
    if (token.type === "heading" && token.depth === level) {
      flush();
      title = token.text.trim();
      continue;
    }
    if (title) contentTokens.push(token);
  }
  flush();
  return blocks;
}

function splitArticleBody(tokens) {
  const firstSectionIndex = tokens.findIndex((token) => token.type === "heading" && token.depth === 4);
  return {
    introMarkdown: tokensToMarkdown(tokens.slice(0, firstSectionIndex === -1 ? tokens.length : firstSectionIndex)),
    sectionBlocks: splitHeadingBlocks(tokens.slice(firstSectionIndex === -1 ? tokens.length : firstSectionIndex), 4),
  };
}

function countOrderedSteps(tokens) {
  return tokens
    .filter((token) => token.type === "list" && token.ordered)
    .reduce((count, token) => count + token.items.length, 0);
}

export function parseKnowledgeArticles(moduleId, markdown) {
  const ids = new Set();
  return splitHeadingBlocks(marked.lexer(String(markdown ?? "")), 3).map((articleBlock) => {
    const id = `${moduleId}-${slugifyTitle(articleBlock.title) || "article"}`;
    if (ids.has(id)) throw new Error(`${moduleId}: duplicate knowledge article id ${id}`);
    ids.add(id);

    const { introMarkdown, sectionBlocks } = splitArticleBody(articleBlock.tokens);
    const sectionByTitle = new Map(sectionBlocks.map((section) => [section.title, section]));
    for (const requiredTitle of REQUIRED_KNOWLEDGE_SECTIONS) {
      const required = sectionByTitle.get(requiredTitle);
      const rendered = required ? markdownToSafeHtml(required.markdown) : null;
      if (!required || !rendered?.text) {
        throw new Error(`${moduleId} / ${articleBlock.title} is missing required section ${requiredTitle}`);
      }
    }

    const sections = sectionBlocks.map((sectionBlock) => {
      const kind = SECTION_KINDS.get(sectionBlock.title) ?? "generic";
      if (kind === "flow" && countOrderedSteps(sectionBlock.tokens) < 2) {
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
