# Foundations LaTeX Code Listings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken numbered mechanism layout and turn Foundations fenced code into a reusable LaTeX Listings-style reading component with local IBM Plex Mono, deterministic syntax highlighting, copy feedback, conditional line numbers, and annotation-safe text.

**Architecture:** Markdown remains the authored source. `roadmap-markdown.mjs` highlights declared languages at build time with a restricted `highlight.js` core, while a focused browser module wraps sanitized `pre > code` nodes with listing chrome at render time. CSS owns the list-flow repair and visual system; annotation traversal excludes listing chrome and resolves selections across syntax-highlight spans.

**Tech Stack:** Node.js ESM, `marked@18.0.5`, `sanitize-html@2.17.5`, `highlight.js@11.11.1`, vanilla HTML/CSS/JavaScript, local WOFF2 assets from `@fontsource/ibm-plex-mono@5.2.7`, Node assertion tests, local browser visual verification.

## Global Constraints

- `核心机制` list content stays in normal text flow; numbered markers use absolute positioning inside reserved left padding.
- Inline code has IBM Plex Mono, no border, no pure-white background, and never stretches to row width.
- Fenced code has exactly one outer frame, a language label, an icon-only Copy control, and no nested `pre > code` frame.
- Line numbers appear only for four or more logical lines; one trailing Markdown newline does not add a line number.
- Copy output excludes language labels and line numbers.
- Syntax highlighting runs at build time only and never uses automatic language detection.
- Explicitly registered languages are Python, JavaScript, TypeScript, Rust, JSON, Bash, YAML, and Markdown.
- Mermaid fences remain available to the existing Mermaid renderer and are not wrapped as code listings.
- IBM Plex Mono loads from committed local WOFF2 files with `font-display: swap`; no font CDN is used.
- Listing controls and line numbers are excluded from local annotation text; selections across highlight spans remain restorable.
- Markdown files remain unchanged unless verification exposes malformed source.
- `roadmap-data.json` is generated, never edited manually.

---

## File Map

- Create `projects/foundations/roadmap/code-listing.js`: pure listing model, clipboard helper, DOM enhancement, icon-state feedback.
- Create `projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2`: local Latin regular font.
- Create `projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2`: local Latin medium font.
- Create `projects/foundations/assets/fonts/ibm-plex-mono/LICENSE`: upstream SIL OFL text from Fontsource package.
- Create `projects/foundations/assets/fonts/ibm-plex-mono/README.md`: source package, version, selected files, and purpose.
- Create `tests/foundations-code-listing-model.mjs`: line threshold, language label, copy-source, and clipboard behavior.
- Modify `package.json` and `package-lock.json`: pin `highlight.js@11.11.1`.
- Modify `projects/foundations/scripts/roadmap-markdown.mjs`: explicit build-time highlighting and sanitizer class allowlist.
- Modify `projects/foundations/roadmap/roadmap-reader.js`: listing enhancement order and annotation-safe cross-node ranges.
- Modify `projects/foundations/roadmap/roadmap-reader.css`: font faces, code tokens, mechanism-list repair, inline code, listing component, syntax palette, themes, and mobile behavior.
- Modify `projects/foundations/roadmap/roadmap-data.json`: regenerate highlighted HTML.
- Modify `tests/foundations-knowledge-article-parser.mjs`: build-time highlighter and sanitizer assertions.
- Modify `tests/foundations-roadmap-requirements.mjs`: font, CSS, runtime integration, and annotation contracts.

---

### Task 1: Deterministic Build-Time Syntax Highlighting

**Files:**
- Modify: `tests/foundations-knowledge-article-parser.mjs`
- Modify: `projects/foundations/scripts/roadmap-markdown.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`

**Interfaces:**
- Preserves: `markdownToSafeHtml(markdown) -> { html, text }`
- Adds internal: `renderCodeFence({ text, lang, escaped }) -> string`
- Produces: `<code class="hljs language-python"><span class="hljs-keyword">...</span></code>` for supported declared languages
- Produces: escaped plain `<code class="language-unknown">...</code>` for unsupported or missing languages

- [ ] **Step 1: Add failing parser assertions**

Extend the code sample in `tests/foundations-knowledge-article-parser.mjs` so the Python fence contains a keyword and string, then add:

```js
const highlightedCode = articles[0].sections.find((section) => section.kind === "code").body;
assert.match(highlightedCode, /class="hljs language-python"/);
assert.match(highlightedCode, /class="hljs-keyword">while<\/span>/);
assert.match(highlightedCode, /class="hljs-string">"ready"<\/span>/);
assert.doesNotMatch(highlightedCode, /<script|onclick=/i);

const unsupported = markdownToSafeHtml("```unknown\n<unsafe>\n```");
assert.match(unsupported.html, /class="language-unknown"/);
assert.match(unsupported.html, /&lt;unsafe&gt;/);
assert.doesNotMatch(unsupported.html, /class="hljs /);

const authoredHighlightClass = markdownToSafeHtml('<span class="hljs-keyword evil">fake</span>');
assert.doesNotMatch(authoredHighlightClass.html, /\bevil\b/);
```

- [ ] **Step 2: Run the parser test and verify RED**

Run:

```bash
node tests/foundations-knowledge-article-parser.mjs
```

Expected: FAIL because generated code has `language-python` but no `hljs` or `hljs-keyword` spans.

- [ ] **Step 3: Pin the highlighter dependency**

Run:

```bash
npm install --save-exact highlight.js@11.11.1
```

Expected: `package.json` and `package-lock.json` include exact version `11.11.1`.

- [ ] **Step 4: Add the explicit highlighter renderer**

In `projects/foundations/scripts/roadmap-markdown.mjs`, import `Renderer`, the core highlighter, and the eight language modules. Register each grammar once:

```js
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
  if (!language || !hljs.getLanguage(language) || language === "mermaid") {
    return renderPlainCode(token);
  }
  const highlighted = hljs.highlight(token.text, {
    language,
    ignoreIllegals: true,
  }).value;
  return `<pre><code class="hljs language-${language}">${highlighted}\n</code></pre>`;
};
```

Add `span` and restricted class patterns to the sanitizer, then pass the renderer to `marked.parse`:

```js
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

const rawHtml = marked.parse(String(markdown ?? ""), {
  async: false,
  gfm: true,
  breaks: false,
  renderer: markdownRenderer,
});
```

Pass `allowedClasses` to `sanitizeHtml`. Mermaid remains plain `language-mermaid` so the existing runtime renderer can find it.

- [ ] **Step 5: Verify GREEN and regenerate data**

Run:

```bash
node tests/foundations-knowledge-article-parser.mjs
node projects/foundations/scripts/build-roadmap-data.mjs
node tests/foundations-knowledge-content-requirements.mjs
```

Expected: all commands exit 0; generated Python HTML contains restricted `hljs-*` spans and content requirements remain unchanged.

- [ ] **Step 6: Commit Task 1**

```bash
git add package.json package-lock.json projects/foundations/scripts/roadmap-markdown.mjs projects/foundations/roadmap/roadmap-data.json tests/foundations-knowledge-article-parser.mjs
git commit -m "feat: highlight foundations code at build time"
```

---

### Task 2: Listing Model, Conditional Lines, And Copy State

**Files:**
- Create: `projects/foundations/roadmap/code-listing.js`
- Create: `tests/foundations-code-listing-model.mjs`

**Interfaces:**
- Produces: `createCodeListingModel(text, className) -> { source, language, label, lineCount, lineNumbers }`
- Produces: `copyCodeListingSource(source, clipboard) -> Promise<void>`
- Produces: `enhanceCodeListings(root, options?) -> void`
- DOM contract: `.code-listing`, `.code-listing-header`, `.code-listing-language`, `.code-listing-copy`, `.code-listing-body`, `.code-listing-gutter`

- [ ] **Step 1: Write the failing model test**

Create `tests/foundations-code-listing-model.mjs`:

```js
import assert from "node:assert/strict";
import {
  copyCodeListingSource,
  createCodeListingModel,
} from "../projects/foundations/roadmap/code-listing.js";

assert.deepEqual(
  createCodeListingModel("one\ntwo\nthree\n", "language-python hljs"),
  {
    source: "one\ntwo\nthree",
    language: "python",
    label: "PYTHON",
    lineCount: 3,
    lineNumbers: [],
  },
);

assert.deepEqual(
  createCodeListingModel("one\ntwo\nthree\nfour\n", "hljs language-typescript"),
  {
    source: "one\ntwo\nthree\nfour",
    language: "typescript",
    label: "TYPESCRIPT",
    lineCount: 4,
    lineNumbers: [1, 2, 3, 4],
  },
);

assert.equal(createCodeListingModel("value", "").label, "CODE");
assert.equal(createCodeListingModel("", "language-json").lineCount, 0);

let copied = "";
await copyCodeListingSource("print('ok')", {
  async writeText(value) {
    copied = value;
  },
});
assert.equal(copied, "print('ok')");

await assert.rejects(
  copyCodeListingSource("value", null),
  /Clipboard API is unavailable/,
);
```

- [ ] **Step 2: Run the model test and verify RED**

Run:

```bash
node tests/foundations-code-listing-model.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `code-listing.js`.

- [ ] **Step 3: Implement pure model and clipboard helper**

Create `projects/foundations/roadmap/code-listing.js` with these public functions:

```js
const LANGUAGE_CLASS_PATTERN = /(?:^|\s)language-([a-z0-9_+-]+)(?:\s|$)/i;

export function createCodeListingModel(text, className = "") {
  const source = String(text ?? "").replace(/\n$/, "");
  const language = className.match(LANGUAGE_CLASS_PATTERN)?.[1]?.toLowerCase() ?? "";
  const lineCount = source ? source.split("\n").length : 0;
  return {
    source,
    language,
    label: language ? language.toUpperCase() : "CODE",
    lineCount,
    lineNumbers: lineCount >= 4
      ? Array.from({ length: lineCount }, (_, index) => index + 1)
      : [],
  };
}

export async function copyCodeListingSource(source, clipboard) {
  if (typeof clipboard?.writeText !== "function") {
    throw new Error("Clipboard API is unavailable");
  }
  await clipboard.writeText(source);
}
```

- [ ] **Step 4: Implement idempotent DOM enhancement**

Add private `renderCopyIcon`, `renderCheckIcon`, `setCopyButtonState`, and exported `enhanceCodeListings`. The enhancer must:

```js
export function enhanceCodeListings(root, {
  clipboard = globalThis.navigator?.clipboard,
  schedule = globalThis.setTimeout,
} = {}) {
  root.querySelectorAll("pre > code").forEach((code) => {
    if (code.classList.contains("language-mermaid")) return;
    const pre = code.parentElement;
    if (!pre || pre.closest(".code-listing")) return;

    const model = createCodeListingModel(code.textContent, code.className);
    const listing = document.createElement("figure");
    listing.className = "code-listing";

    const header = document.createElement("figcaption");
    header.className = "code-listing-header";
    header.dataset.annotationExclude = "true";

    const label = document.createElement("span");
    label.className = "code-listing-language";
    label.textContent = model.label;

    const copyButton = document.createElement("button");
    copyButton.className = "code-listing-copy";
    copyButton.type = "button";
    copyButton.setAttribute("aria-label", "复制代码");
    copyButton.innerHTML = renderCopyIcon();
    copyButton.addEventListener("click", async () => {
      try {
        await copyCodeListingSource(model.source, clipboard);
        setCopyButtonState(copyButton, "success");
        schedule(() => setCopyButtonState(copyButton, "idle"), 1500);
      } catch {
        setCopyButtonState(copyButton, "error");
        schedule(() => setCopyButtonState(copyButton, "idle"), 1500);
      }
    });

    header.append(label, copyButton);

    const body = document.createElement("div");
    body.className = "code-listing-body";
    if (model.lineNumbers.length > 0) {
      const gutter = document.createElement("ol");
      gutter.className = "code-listing-gutter";
      gutter.dataset.annotationExclude = "true";
      gutter.setAttribute("aria-hidden", "true");
      for (const lineNumber of model.lineNumbers) {
        const item = document.createElement("li");
        item.textContent = String(lineNumber);
        gutter.append(item);
      }
      body.append(gutter);
    }

    pre.replaceWith(listing);
    body.append(pre);
    listing.append(header, body);
  });
}
```

Use embedded Lucide Copy and Check SVG paths. `setCopyButtonState` keeps the button dimensions stable and sets labels to `复制代码`, `已复制`, or `复制失败`.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
node tests/foundations-code-listing-model.mjs
node --check projects/foundations/roadmap/code-listing.js
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit Task 2**

```bash
git add projects/foundations/roadmap/code-listing.js tests/foundations-code-listing-model.mjs
git commit -m "feat: add foundations code listing model"
```

---

### Task 3: Mechanism Flow Repair, Local Font, And Listing Styles

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
- Create: `projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2`
- Create: `projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2`
- Create: `projects/foundations/assets/fonts/ibm-plex-mono/LICENSE`
- Create: `projects/foundations/assets/fonts/ibm-plex-mono/README.md`

**Interfaces:**
- Adds CSS tokens: `--reader-code-*`
- Replaces Grid mechanism item layout with positioned marker and normal text flow
- Styles runtime DOM contract from Task 2

- [ ] **Step 1: Replace the obsolete CSS contract with failing assertions**

In `tests/foundations-roadmap-requirements.mjs`, remove the assertion requiring `grid-template-columns: 42px minmax(0, 1fr)` and add assertions that inspect the exact mechanism, inline-code, and listing rules:

```js
const mechanismItemRule = css.match(/\.knowledge-article-section\.is-mechanism li\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
const mechanismMarkerRule = css.match(/\.knowledge-article-section\.is-mechanism li::before\s*\{(?<body>[\s\S]*?)\}/)?.groups.body ?? "";
assert.match(mechanismItemRule, /position:\s*relative/);
assert.match(mechanismItemRule, /padding-inline-start:\s*54px/);
assert.doesNotMatch(mechanismItemRule, /display:\s*(grid|flex)|grid-template-columns/);
assert.match(mechanismMarkerRule, /position:\s*absolute/);
assert.match(mechanismMarkerRule, /inset-inline-start:\s*0/);

assert.match(css, /@font-face\s*\{[\s\S]*font-family:\s*"IBM Plex Mono"/);
assert.match(css, /\.knowledge-article-section-body code:not\(pre code\)/);
assert.match(css, /\.code-listing\s*\{/);
assert.match(css, /\.code-listing-header\s*\{/);
assert.match(css, /\.code-listing-gutter\s*\{/);
assert.match(css, /\.code-listing pre > code\s*\{[\s\S]*border:\s*0;[\s\S]*background:\s*transparent/);
assert.match(css, /\.hljs-keyword/);
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.code-listing-copy/);
```

Add `existsSync` checks for both WOFF2 files and the local license.

- [ ] **Step 2: Run the roadmap contract and verify RED**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL because mechanism items still use Grid and listing/font selectors do not exist.

- [ ] **Step 3: Vendor the two local font files and license**

Use the verified Fontsource package without adding it as a runtime dependency:

```bash
tmpdir="$(mktemp -d)"
npm pack --pack-destination "$tmpdir" @fontsource/ibm-plex-mono@5.2.7
tar -xzf "$tmpdir/fontsource-ibm-plex-mono-5.2.7.tgz" -C "$tmpdir"
mkdir -p projects/foundations/assets/fonts/ibm-plex-mono
cp "$tmpdir/package/files/ibm-plex-mono-latin-400-normal.woff2" projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2
cp "$tmpdir/package/files/ibm-plex-mono-latin-500-normal.woff2" projects/foundations/assets/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2
cp "$tmpdir/package/LICENSE" projects/foundations/assets/fonts/ibm-plex-mono/LICENSE
rm -rf "$tmpdir"
```

Create `README.md` recording package `@fontsource/ibm-plex-mono@5.2.7`, the two copied files, SIL Open Font License, and that Chinese glyphs use the CSS fallback stack.

- [ ] **Step 4: Add font faces and theme tokens**

At the top of `roadmap-reader.css`, add Regular and Medium `@font-face` declarations with URLs relative to the CSS file:

```css
@font-face {
  font-family: "IBM Plex Mono";
  src: url("../assets/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2") format("woff2");
  font-style: normal;
  font-weight: 400;
  font-display: swap;
}

@font-face {
  font-family: "IBM Plex Mono";
  src: url("../assets/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2") format("woff2");
  font-style: normal;
  font-weight: 500;
  font-display: swap;
}
```

Add light and dark code tokens for surface, header, border, inline tint, gutter, keyword, literal, comment, and type/function roles. Values must derive from the current ink, green, and ochre palette and must not use pure white or black.

- [ ] **Step 5: Repair mechanism list flow and separate inline code**

Replace the Grid `li` rule with:

```css
.knowledge-article-section.is-mechanism li {
  position: relative;
  min-width: 0;
  margin: 0;
  padding-inline-start: 54px;
}

.knowledge-article-section.is-mechanism li::before {
  position: absolute;
  top: 0.12em;
  inset-inline-start: 0;
  display: grid;
  place-items: center;
  width: 34px;
  aspect-ratio: 1;
  border: 1px solid var(--reader-blue);
  border-radius: 50%;
  color: var(--reader-blue);
  background: var(--reader-paper-soft);
  font-family: var(--reader-code-font);
  font-size: 12px;
  content: counter(knowledge-mechanism-step, decimal-leading-zero);
  counter-increment: knowledge-mechanism-step;
}
```

Replace the generic `code` rule with inline-only selectors using `code:not(pre code)`. Remove its border and pure-white background while keeping compact padding, a maximum 3px radius, medium IBM Plex Mono, and the inline code token.

- [ ] **Step 6: Add the complete listing component and syntax palette**

Implement all Task 2 DOM selectors. The essential layout is:

```css
.code-listing {
  max-width: 100%;
  margin: 0 0 16px;
  overflow: hidden;
  border: 1px solid var(--reader-code-border);
  border-radius: 6px;
  background: var(--reader-code-surface);
}

.code-listing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 40px;
  border-bottom: 1px solid var(--reader-code-border);
  background: var(--reader-code-header);
  padding-inline-start: 14px;
}

.code-listing-body {
  display: flex;
  min-width: 0;
}

.code-listing-gutter {
  flex: 0 0 auto;
  margin: 0;
  border-inline-end: 1px solid var(--reader-code-border);
  padding: 16px 10px;
  color: var(--reader-code-gutter);
  font-family: var(--reader-code-font);
  font-size: 13px;
  line-height: 1.65;
  list-style: none;
  text-align: end;
  user-select: none;
}

.code-listing pre {
  min-width: 0;
  flex: 1 1 auto;
  margin: 0;
  overflow-x: auto;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 16px;
}

.code-listing pre > code {
  display: block;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
  color: var(--reader-code-ink);
  font-family: var(--reader-code-font);
  font-size: 13.5px;
  font-weight: 400;
  line-height: 1.65;
  white-space: pre;
}
```

Add stable 40px copy-button dimensions, visible focus, success/error state colors, restrained `.hljs-*` rules, dark-theme tokens, and mobile reductions for code padding and gutter width. Do not add shadows.

- [ ] **Step 7: Verify GREEN**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
node tests/foundations-code-listing-model.mjs
git diff --check
```

Expected: all commands exit 0 and both font files are present.

- [ ] **Step 8: Commit Task 3**

```bash
git add projects/foundations/assets/fonts/ibm-plex-mono projects/foundations/roadmap/roadmap-reader.css tests/foundations-roadmap-requirements.mjs
git commit -m "style: add foundations latex code listings"
```

---

### Task 4: Reader Integration And Annotation-Safe Highlight Spans

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

**Interfaces:**
- Consumes: `enhanceCodeListings(root)` from Task 2
- Preserves: `getSelectionAnnotationContext`, `findTextRange`, `applyHighlights`
- Adds internal: `getTextOffset(root, targetNode, targetOffset) -> number`
- Adds internal: `getTextPosition(nodes, absoluteOffset) -> { node, offset } | null`

- [ ] **Step 1: Add failing reader integration assertions**

Add these source-contract checks to `tests/foundations-roadmap-requirements.mjs`:

```js
assert.match(js, /import \{ enhanceCodeListings \} from "\.\/code-listing\.js"/);
assert.match(js, /renderCurrentModule\(\);[\s\S]*enhanceCodeListings\(els\.sectionList\);[\s\S]*renderMermaidDiagrams/);
assert.match(js, /closest\("\[data-annotation-exclude\]"\)/);
assert.doesNotMatch(js, /range\.startContainer !== range\.endContainer/);
assert.match(js, /function getTextOffset/);
assert.match(js, /function getTextPosition/);
assert.match(js, /const combinedText = nodes\.map/);
assert.match(js, /mark\.replaceWith\(\.\.\.mark\.childNodes\)/);
```

Also assert that `code-listing.js` exists and contains the Mermaid skip, `dataAnnotationExclude`, the four-line threshold, and the 1500ms reset.

- [ ] **Step 2: Run the roadmap test and verify RED**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL because the reader does not import or invoke the listing enhancer and still rejects cross-node selections.

- [ ] **Step 3: Integrate listing enhancement before Mermaid**

Import the enhancer at the top of `roadmap-reader.js`:

```js
import { enhanceCodeListings } from "./code-listing.js";
```

In `openModule`, call it immediately after `renderCurrentModule()` and before `renderMermaidDiagrams()`. The enhancer skips `language-mermaid`, so the existing Mermaid query and fallback remain valid.

- [ ] **Step 4: Exclude listing chrome from annotation selection**

Add a helper that checks whether a text position is inside `[data-annotation-exclude]`. Reject selection contexts whose start or end is excluded. Update `getTextNodes` to retain meaningful whitespace nodes but reject every node inside listing chrome.

- [ ] **Step 5: Resolve annotations across syntax-highlight spans**

Remove the same-node restriction. Flatten accepted text nodes and map absolute offsets back to DOM positions:

```js
function getTextOffset(root, targetNode, targetOffset) {
  let absoluteOffset = 0;
  for (const node of getTextNodes(root)) {
    if (node === targetNode) return absoluteOffset + targetOffset;
    absoluteOffset += node.nodeValue.length;
  }
  return -1;
}

function getTextPosition(nodes, absoluteOffset) {
  let traversed = 0;
  for (const node of nodes) {
    const next = traversed + node.nodeValue.length;
    if (absoluteOffset <= next) {
      return { node, offset: absoluteOffset - traversed };
    }
    traversed = next;
  }
  return null;
}

function findTextRange(root, selectedText, matchIndex) {
  if (!selectedText) return null;
  const nodes = getTextNodes(root);
  const combinedText = nodes.map((node) => node.nodeValue).join("");
  let occurrence = 0;
  let start = combinedText.indexOf(selectedText);
  while (start !== -1 && occurrence < matchIndex) {
    occurrence += 1;
    start = combinedText.indexOf(selectedText, start + selectedText.length);
  }
  if (start === -1) return null;
  const startPosition = getTextPosition(nodes, start);
  const endPosition = getTextPosition(nodes, start + selectedText.length);
  if (!startPosition || !endPosition) return null;
  const range = document.createRange();
  range.setStart(startPosition.node, startPosition.offset);
  range.setEnd(endPosition.node, endPosition.offset);
  return range;
}
```

Calculate `matchIndex` from accepted article text before the selected start position, not from listing header or gutter text. Change `clearHighlights` to unwrap mark children with `mark.replaceWith(...mark.childNodes)` before normalizing, preserving highlighter spans.

- [ ] **Step 6: Verify GREEN and all focused tests**

Run:

```bash
node tests/foundations-code-listing-model.mjs
node tests/foundations-knowledge-article-parser.mjs
node tests/foundations-annotation-model.mjs
node tests/foundations-roadmap-requirements.mjs
node --check projects/foundations/roadmap/roadmap-reader.js
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit Task 4**

```bash
git add projects/foundations/roadmap/roadmap-reader.js projects/foundations/roadmap/code-listing.js tests/foundations-roadmap-requirements.mjs
git commit -m "feat: integrate foundations code listings"
```

---

### Task 5: Full Regression And Visual Verification

**Files:**
- Verify only unless a failing check requires a scoped fix.

**Interfaces:**
- Validates the complete generated-data, reader, copy, annotation, theme, and responsive contract.

- [ ] **Step 1: Rebuild and prove generated data is stable**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
git diff --exit-code -- projects/foundations/roadmap/roadmap-data.json
```

Expected: build exits 0 and the second command reports no uncommitted generated-data drift.

- [ ] **Step 2: Run the complete repository test suite**

Run:

```bash
node tests/foundations-code-listing-model.mjs
node tests/foundations-knowledge-article-parser.mjs
node tests/foundations-knowledge-content-requirements.mjs
node tests/foundations-annotation-model.mjs
node tests/foundations-roadmap-requirements.mjs
npm run test:projects
npm run test:all
git diff --check
```

Expected: every command exits 0 with no assertion failures or whitespace errors.

- [ ] **Step 3: Start a local static server**

Run from the repository root:

```bash
python3 -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173/projects/foundations/?module=evals-debugging
```

- [ ] **Step 4: Verify desktop behavior around 1440px**

Check and capture evidence that:

- `核心机制` shows `01 expected 必须由...` in normal horizontal text flow.
- Inline `expected`, `assertion`, and `actual` tokens are compact and have no white input-style frame.
- Python blocks have one frame, `PYTHON`, and one Copy icon.
- Four-or-more-line blocks show aligned line numbers; short blocks do not.
- Copy places only source code on the clipboard and changes Copy to Check without layout shift.
- Code can be selected and highlighted; the highlight survives a reload.
- Light and dark themes preserve contrast and component structure.

- [ ] **Step 5: Verify mobile behavior around 390px**

Check and capture evidence that:

- mechanism text never collapses into one-character columns.
- long code scrolls within the listing and does not create page-level horizontal overflow.
- the language label and Copy control do not overlap.
- the copy control retains a usable touch target.
- the line gutter remains aligned while code scrolls.

- [ ] **Step 6: Final repository audit**

Run:

```bash
git status --short --branch
git log --oneline --decorate -6
```

Expected: only intentional committed changes exist on the feature branch; no server process is left running before completion.
