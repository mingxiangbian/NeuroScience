import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, cp, symlink, link, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync, spawnSync } from "node:child_process";
import vm from "node:vm";
import test from "node:test";
import { inspectHtml, minifySite } from "../scripts/minify-site.mjs";

const script = fileURLToPath(new URL("../scripts/minify-site.mjs", import.meta.url));
const sourceRoot = fileURLToPath(new URL("../", import.meta.url));

async function fixture(t, files) {
  const directory = await mkdtemp(path.join(tmpdir(), "site-minify-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const source = path.join(directory, "source");
  const stage = path.join(directory, "_site");
  for (const [name, contents] of Object.entries(files)) {
    await mkdir(path.dirname(path.join(source, name)), { recursive: true });
    await writeFile(path.join(source, name), contents);
  }
  await cp(source, stage, { recursive: true });
  return { directory, source, stage };
}

function outsideExecutableBodies(html) {
  let result = html;
  for (const block of inspectHtml(html).blocks.reverse()) {
    result = result.slice(0, block.start) + `[${block.loader}]` + result.slice(block.end);
  }
  return result;
}

test("staging-only minification preserves HTML, JSON, embedded examples and script behavior", async (t) => {
  const js = `/*! License stays */
    var publicName = "智能体";
    function retainedName(input) { return input + " & <tag>"; }
    globalThis.result = [retainedName(publicName), retainedName.name, eval("publicName"), /a b/.test("a b")];
  `;
  const css = `/*! CSS License stays */
    @import "./nested.css";
    .example > p { color: rgb(255, 0, 0); margin: 0.0px; }
    .example::after { content: "two  spaces 智能体"; --verbatim: "one  two"; }
  `;
  const html = `<!doctype html><html><head>
    <!-- <script>this is documentation, not valid JS</script> -->
    <script type="importmap">{ "imports": { "external": "https://example.org/x.js" } }</script>
    <script type="application/ld+json">{ "text": " Keep  spacing " }</script>
    <script src="">ignored content is not executable JavaScript</script>
    <style data-note=">"> p { color: rgb(255, 0, 0); } </style>
    <link rel="stylesheet" href="./THEME.CSS">
    </head><body><p> Keep   all \n text </p>
    <pre><code>&lt;script&gt; example   code &lt;/script&gt;</code></pre>
    <template><script>not valid JS  keep me</script><style>keep this too</style></template>
    <textarea><script>literal text in a textarea</script></textarea>
    <script data-marker=">">${js}</script>
    <script src="./main.js"></script>
    <script type="module"> import { value } from "./module.js"; globalThis.moduleValue = value; </script>
    <a href="nested/">Another page</a></body></html>`;
  const files = {
    "package.json": '{"type":"module"}',
    "index.html": html, "main.js": js, "THEME.CSS": css,
    "nested.css": "p { padding: 2px  4px; }\n",
    "module.js": 'export { value } from "./dependency.js"; import("./lazy.js");\n',
    "dependency.js": "export const value =  42;\n",
    "lazy.js": "export const lazy =  true;\n",
    "nested/index.html": "<p> A   second page </p><script> globalThis.nested =  3; </script>",
    "projects/manifest.json": '[{"folder":"declared/"}]',
    "projects/declared/index.html": "<script> globalThis.declared =  1; </script>",
    "projects/experiments/unused.js": "unreferenced Python-ish experiment code: [not JavaScript]\n",
    "papers/manifest.json": "[]"
  };
  const { source, stage } = await fixture(t, files);
  const totals = await minifySite(stage);
  assert.equal(totals.files, 9, "only entry pages and their browser asset dependencies are processed");
  assert.ok(totals.rawAfter < totals.rawBefore);
  assert.ok(totals.gzipAfter < totals.gzipBefore);
  for (const [name, original] of Object.entries(files)) assert.equal(await readFile(path.join(source, name), "utf8"), original);
  assert.equal(await readFile(path.join(stage, "projects/experiments/unused.js"), "utf8"), files["projects/experiments/unused.js"]);
  const output = await readFile(path.join(stage, "index.html"), "utf8");
  assert.equal(outsideExecutableBodies(output), outsideExecutableBodies(html));
  const before = vm.createContext({});
  const after = vm.createContext({});
  vm.runInContext(js, before);
  vm.runInContext(await readFile(path.join(stage, "main.js"), "utf8"), after);
  assert.equal(JSON.stringify(after.result), JSON.stringify(before.result));
  const classic = inspectHtml(output).blocks.find((block) => output.slice(block.start, block.end).includes("publicName"));
  vm.runInContext(output.slice(classic.start, classic.end), after);
  assert.equal(JSON.stringify(after.result), JSON.stringify(before.result));
  const module = await import(pathToFileURL(path.join(stage, "module.js")));
  assert.equal(module.value, 42);
  const outputCss = await readFile(path.join(stage, "THEME.CSS"), "utf8");
  assert.match(outputCss, /\/\*! CSS License stays \*\//);
  assert.match(outputCss, /color:rgb\(255,0,0\)/, "color syntax must not be approximated or replaced");
  assert.match(outputCss, /margin:0\.0px/, "syntax minification must remain disabled");
  assert.match(outputCss, /content:"two  spaces 智能体"/);
  assert.match(outputCss, /--verbatim: ?"one  two"/, "whitespace inside custom-property strings must survive");
  const secondPass = await minifySite(stage);
  assert.equal(secondPass.changed, 0, "minification should be idempotent");
});

test("inline script and style closing tags stay escaped without changing values or following HTML", async (t) => {
  const scripts = [
    String.raw`globalThis.value = "<\/ScRiPt>";`,
    'globalThis.value = `</scr` + `ipt>`;',
    'globalThis.value = String.raw`<\\/script>`;'
  ];
  for (const source of scripts) {
    const html = `<script>${source}</script><p id=tail> Keep  spacing </p>`;
    const { stage } = await fixture(t, { "index.html": html });
    await minifySite(stage);
    const output = await readFile(path.join(stage, "index.html"), "utf8");
    const [block] = inspectHtml(output).blocks;
    assert.equal(inspectHtml(output).blocks.length, 1);
    const body = output.slice(block.start, block.end);
    assert.doesNotMatch(body, /<\/script/i, "HTML must not see an unescaped closing tag inside JavaScript");
    const before = vm.createContext({});
    const after = vm.createContext({});
    vm.runInContext(source, before);
    vm.runInContext(body, after);
    assert.equal(after.value, before.value, source);
    assert.equal(outsideExecutableBodies(output), outsideExecutableBodies(html));
  }
  const css = String.raw`p::before { content: "<\/style>"; }`;
  const html = `<style>${css}</style><p id=tail> Keep  spacing </p>`;
  const { stage } = await fixture(t, { "index.html": html });
  await minifySite(stage);
  const output = await readFile(path.join(stage, "index.html"), "utf8");
  const [block] = inspectHtml(output).blocks;
  assert.equal(inspectHtml(output).blocks.length, 1);
  const body = output.slice(block.start, block.end);
  assert.doesNotMatch(body, /<\/style/i, "HTML must not see an unescaped closing tag inside CSS");
  assert.match(body, /content:"<\\\/style>"/);
  assert.equal(outsideExecutableBodies(output), outsideExecutableBodies(html));
});

test("the CLI reports raw and gzip bytes and rejects unsafe roots and arguments", async (t) => {
  const { source, stage } = await fixture(t, { "index.html": "<script> globalThis.test =  42; </script>" });
  const report = JSON.parse(execFileSync(process.execPath, [script, stage], { encoding: "utf8" }));
  assert.equal(report.files, 1);
  assert.ok(report.rawBefore > report.rawAfter);
  assert.ok(report.gzipBefore > 0 && report.gzipAfter > 0);
  for (const directory of [source, sourceRoot, path.join(sourceRoot, "projects")]) {
    const result = spawnSync(process.execPath, [script, directory], { encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /staging|source/i);
  }
  const extra = spawnSync(process.execPath, [script, stage, "extra"], { encoding: "utf8" });
  assert.notEqual(extra.status, 0);
  assert.match(extra.stderr, /Usage:/);
});

test("symlinks, hardlinks and parse errors cannot modify source or leave partial output", async (t) => {
  for (const variant of ["symlink", "parent-symlink", "hardlink", "parse-error"]) {
    const files = { "index.html": '<script>globalThis.ok =  true;</script><script src="bad.js"></script>', "original.js": "const original =  1;\n" };
    const { source, stage } = await fixture(t, files);
    const original = path.join(source, "original.js");
    if (variant === "symlink") await symlink(original, path.join(stage, "bad.js"));
    if (variant === "parent-symlink") {
      await symlink(source, path.join(stage, "linked"));
      await writeFile(path.join(stage, "index.html"), '<script src="linked/original.js"></script>');
      files["index.html"] = '<script src="linked/original.js"></script>';
    }
    if (variant === "hardlink") await link(original, path.join(stage, "bad.js"));
    if (variant === "parse-error") await writeFile(path.join(stage, "bad.js"), "this is invalid JS !");
    await assert.rejects(minifySite(stage));
    assert.equal(await readFile(original, "utf8"), files["original.js"]);
    assert.equal(await readFile(path.join(stage, "index.html"), "utf8"), files["index.html"]);
  }
});
