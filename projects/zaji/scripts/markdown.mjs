import { Marked, Renderer } from "marked";
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

const allowedTags = [
  "a", "blockquote", "br", "code", "del", "div", "em", "h2", "h3", "h4", "h5", "h6",
  "hr", "img", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
];

const allowedAttributes = {
  a: ["href", "title", "rel"],
  code: ["class"],
  div: ["class", "data-latex"],
  h2: ["id"],
  h3: ["id"],
  h4: ["id"],
  h5: ["id"],
  h6: ["id"],
  img: ["src", "alt", "title", "loading", "decoding"],
  span: ["class", "data-latex"],
  td: ["align"],
  th: ["align"],
};

const allowedClasses = {
  code: ["hljs", /^language-[a-z0-9_+-]+$/],
  div: ["math-display"],
  span: ["math-inline", /^hljs-[a-z0-9_-]+$/],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function slugifyHeading(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/<[^>]*>/g, "")
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "") || "section";
}

function getDeclaredLanguage(lang) {
  const declared = String(lang ?? "").trim().split(/\s+/, 1)[0].toLowerCase();
  return /^[a-z0-9_+-]+$/.test(declared) ? declared : "";
}

function normalizeLocalImage(href, siteRoot) {
  const value = String(href ?? "").trim();
  if (/^https:\/\//i.test(value)) return value;
  if (!/^assets\/[a-z0-9][a-z0-9._/-]*$/i.test(value)) return "";
  if (value.includes("..") || value.includes("\\")) return "";
  return `${siteRoot}/${value}`;
}

function renderMathPlaceholder(tagName, className, latex) {
  const escapedLatex = escapeHtml(latex);
  return `<${tagName} class="${className}" data-latex="${escapedLatex}">${escapedLatex}</${tagName}>`;
}

const displayMathExtension = {
  name: "zajiDisplayMath",
  level: "block",
  start(source) {
    return source.match(/^ {0,3}\\\[[ \t]*$/m)?.index;
  },
  tokenizer(source) {
    const match = /^ {0,3}\\\[[ \t]*\r?\n([\s\S]*?)\r?\n {0,3}\\\][ \t]*(?:(?:\r?\n)+|$)/.exec(source);
    if (!match) return undefined;
    return { type: "zajiDisplayMath", raw: match[0], latex: match[1].trim() };
  },
  renderer(token) {
    return `${renderMathPlaceholder("div", "math-display", token.latex)}\n`;
  },
};

const inlineMathExtension = {
  name: "zajiInlineMath",
  level: "inline",
  start(source) {
    const index = source.indexOf("\\(");
    return index === -1 ? undefined : index;
  },
  tokenizer(source) {
    const match = /^\\\(([^\n]+?)\\\)/.exec(source);
    if (!match) return undefined;
    return { type: "zajiInlineMath", raw: match[0], latex: match[1] };
  },
  renderer(token) {
    return renderMathPlaceholder("span", "math-inline", token.latex);
  },
};

export function parseFrontmatter(markdownSource) {
  const source = String(markdownSource ?? "");
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { frontmatter: {}, body: source };

  const frontmatter = {};
  for (const [index, line] of match[1].split(/\r?\n/).entries()) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const parsed = line.match(/^([a-z][a-z0-9_]*):\s*(.*)$/i);
    if (!parsed) throw new Error(`Invalid frontmatter line ${index + 1}: ${line}`);
    const [, key, rawValue] = parsed;
    const value = rawValue.trim();
    if (value.startsWith("[") && value.endsWith("]")) {
      const inner = value.slice(1, -1).trim();
      frontmatter[key] = inner ? inner.split(",").map((item) => item.trim()).filter(Boolean) : [];
    } else if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      frontmatter[key] = value.slice(1, -1);
    } else {
      frontmatter[key] = value;
    }
  }

  return { frontmatter, body: source.slice(match[0].length) };
}

export function renderMarkdown(markdownSource, { siteRoot = "." } = {}) {
  const toc = [];
  const usedHeadingIds = new Map();
  const renderer = new Renderer();
  const renderPlainCode = renderer.code.bind(renderer);

  renderer.heading = function heading(token) {
    const baseId = slugifyHeading(token.text);
    const seen = usedHeadingIds.get(baseId) ?? 0;
    usedHeadingIds.set(baseId, seen + 1);
    const id = seen === 0 ? baseId : `${baseId}-${seen + 1}`;
    if (token.depth <= 4) toc.push({ depth: token.depth, id, title: token.text.trim() });
    return `<h${token.depth} id="${escapeHtml(id)}">${this.parser.parseInline(token.tokens)}</h${token.depth}>`;
  };

  renderer.code = (token) => {
    const language = getDeclaredLanguage(token.lang);
    if (!language || !hljs.getLanguage(language)) return renderPlainCode(token);
    const highlighted = hljs.highlight(token.text, { language, ignoreIllegals: true }).value;
    return `<pre><code class="hljs language-${language}">${highlighted}\n</code></pre>`;
  };

  renderer.image = (token) => {
    const src = normalizeLocalImage(token.href, siteRoot);
    const alt = String(token.text ?? "").trim();
    if (!src || !alt) return "";
    const title = token.title ? ` title="${escapeHtml(token.title)}"` : "";
    return `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"${title} loading="lazy" decoding="async">`;
  };

  const parser = new Marked({
    extensions: [displayMathExtension, inlineMathExtension],
    gfm: true,
    breaks: false,
    renderer,
  });
  const rawHtml = parser.parse(String(markdownSource ?? ""), { async: false });
  const html = sanitizeHtml(rawHtml, {
    allowedTags,
    allowedAttributes,
    allowedClasses,
    allowedSchemes: ["http", "https", "mailto"],
    allowedSchemesByTag: { img: ["https"] },
    allowProtocolRelative: false,
    transformTags: {
      a: (tagName, attribs) => ({
        tagName,
        attribs: { ...attribs, rel: "noopener noreferrer" },
      }),
    },
  });
  const text = sanitizeHtml(html, { allowedTags: [], allowedAttributes: {} })
    .replace(/\s+/g, " ")
    .trim();

  return {
    html,
    text,
    toc,
    hasMath: html.includes("data-latex="),
  };
}
