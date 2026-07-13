import assert from "node:assert/strict";
import { markdownToSafeHtml } from "../projects/foundations/scripts/roadmap-markdown.mjs";

const displayMath = markdownToSafeHtml(String.raw`收益公式：

\[
R=\frac{P_1-P_0+D}{P_0}
\]`);

assert.match(displayMath.html, /class="math-display"[^>]*data-latex=/, "display math should survive Markdown as a renderable placeholder");
assert.doesNotMatch(displayMath.html, /<h1>/, "display math equals signs should not become Setext headings");
assert.match(displayMath.text, /R=\\frac/, "display math should remain searchable and available as a fallback");

const inlineMath = markdownToSafeHtml(String.raw`组合下跌 \(30\%\) 时仍按计划执行。`);
assert.match(inlineMath.html, /class="math-inline"[^>]*data-latex=/, "inline math should survive Markdown as a renderable placeholder");
assert.match(inlineMath.text, /30\\%/, "inline math should remain searchable and available as a fallback");

const fencedMath = markdownToSafeHtml([
  "```markdown",
  String.raw`\[not a formula\]`,
  String.raw`\(still code\)`,
  "```",
].join("\n"));
assert.doesNotMatch(fencedMath.html, /class="math-(?:display|inline)"/, "math delimiters inside fenced code should remain code");
assert.match(fencedMath.html, /<pre><code class="hljs language-markdown">/, "fenced math examples should retain code rendering");

const inlineCodeMath = markdownToSafeHtml('Use `\\(not a formula\\)` as a literal example.');
assert.doesNotMatch(inlineCodeMath.html, /class="math-(?:display|inline)"/, "math delimiters inside inline code should remain code");
assert.match(inlineCodeMath.html, /<code>\\\(not a formula\\\)<\/code>/, "inline math examples should retain code rendering");

const unsafeMath = markdownToSafeHtml(String.raw`\(x <img src=x onerror=alert(1)>\)`);
assert.doesNotMatch(unsafeMath.html, /<img\b|<script\b/i, "math placeholders should not introduce executable HTML");
assert.match(unsafeMath.html, /&lt;img/, "unsafe formula text should remain visible only as escaped fallback content");

console.log("roadmap Markdown math contract passed");
