import { marked } from "marked";
import sanitizeHtml from "sanitize-html";

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
