import { readFile, writeFile, realpath, lstat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { build } from "esbuild";
import { Parser } from "htmlparser2";

const repository = await realpath(fileURLToPath(new URL("../", import.meta.url)));
const siteUrl = new URL("https://site.invalid/NeuroScience/");
const executableTypes = new Set(["", "module", "text/javascript", "application/javascript"]);
const inertTags = new Set(["pre", "code", "template", "textarea", "title", "noscript"]);
const inside = (root, file) => file.startsWith(`${root}${path.sep}`);

// Source ranges let us preserve every HTML byte outside executable script/style bodies.
export function inspectHtml(source) {
  const stack = [];
  const blocks = [];
  const references = [];
  let parser;
  parser = new Parser({
    onopentag(name, attributes) {
      const inert = stack.some((entry) => inertTags.has(entry.name));
      const entry = { name, start: parser.endIndex + 1 };
      if (!inert) {
        if (name === "script" && executableTypes.has((attributes.type ?? "").trim().toLowerCase())) {
          if (Object.hasOwn(attributes, "src")) references.push(attributes.src);
          else entry.loader = "js";
        } else if (name === "style" && ["", "text/css"].includes((attributes.type ?? "").trim().toLowerCase())) {
          entry.loader = "css";
        } else if (name === "link" && (attributes.rel ?? "").toLowerCase().split(/\s+/).includes("stylesheet")) {
          references.push(attributes.href);
        } else if (name === "a" || name === "iframe") {
          const reference = attributes.href ?? attributes.src;
          if (reference && /(?:\.html?(?:[?#]|$)|\/(?:[?#]|$))/.test(reference)) references.push(reference);
        }
      }
      stack.push(entry);
    },
    onclosetag(name, implied) {
      const entry = stack.pop();
      if (entry?.name === name && entry.loader && !implied) {
        blocks.push({ start: entry.start, end: parser.startIndex, loader: entry.loader });
      }
    }
  }, { decodeEntities: true });
  parser.end(source);
  return { blocks, references };
}

async function compress(source, loader, sourcefile) {
  // No bundling, renaming, syntax minification, target lowering, or tree shaking.
  // Metadata lists imports without resolving or reading unrelated source files.
  const result = await build({
    stdin: { contents: source, loader, sourcefile },
    bundle: false, write: false, metafile: true,
    minifyWhitespace: true, minifyIdentifiers: false, minifySyntax: false,
    treeShaking: false, charset: "utf8", legalComments: "inline", logLevel: "silent"
  });
  if (result.warnings.length) throw new Error(`${sourcefile}: ${result.warnings.map((warning) => warning.text).join("; ")}`);
  return {
    code: result.outputFiles[0].text,
    imports: Object.values(result.metafile.outputs).flatMap((output) => output.imports.map((entry) => entry.path))
  };
}

export async function minifySite(directory = "_site") {
  const requested = path.resolve(directory);
  const root = await realpath(requested);
  if ((await lstat(requested)).isSymbolicLink() || path.basename(root) !== "_site"
    || root === repository || inside(root, repository)
    || (inside(repository, root) && root !== path.join(repository, "_site"))) {
    throw new Error("Only a separate _site staging directory may be minified; source directories are forbidden.");
  }
  const pending = new Set(["index.html", "papers/index.html", "projects/index.html"]);
  const visited = new Set();
  const changes = [];
  const totals = { files: 0, changed: 0, rawBefore: 0, rawAfter: 0, gzipBefore: 0, gzipAfter: 0 };

  async function safeFile(relative) {
    const file = path.resolve(root, relative);
    if (!inside(root, file)) throw new Error(`Asset escapes staging directory: ${relative}`);
    let stat;
    try { stat = await lstat(file); } catch (error) { if (error.code === "ENOENT") return null; throw error; }
    if (!stat.isFile() || stat.nlink !== 1 || await realpath(file) !== file) {
      throw new Error(`Asset must be an independent regular staging file: ${relative}`);
    }
    return file;
  }

  function enqueue(reference, from) {
    if (!reference || reference.startsWith("#")) return;
    const url = new URL(reference, new URL(from, siteUrl));
    if (url.origin !== siteUrl.origin || !url.pathname.startsWith(siteUrl.pathname)) return;
    let relative = decodeURIComponent(url.pathname.slice(siteUrl.pathname.length));
    if (relative.endsWith("/")) relative += "index.html";
    if (/\.(?:html?|m?js|css)$/i.test(relative)) pending.add(relative);
  }

  if (!await safeFile("index.html")) throw new Error("Staging directory must contain index.html.");
  for (const section of ["papers", "projects"]) {
    const manifest = await safeFile(`${section}/manifest.json`);
    if (manifest) {
      for (const entry of JSON.parse(await readFile(manifest, "utf8"))) {
        if (entry.folder) enqueue(entry.folder, `${section}/manifest.json`);
      }
    }
  }

  // Follow only public page links and browser asset imports, never walk projects/.
  for (const relative of pending) {
    if (visited.has(relative)) continue;
    visited.add(relative);
    const file = await safeFile(relative);
    if (!file) continue;
    const original = await readFile(file, "utf8");
    let output;
    if (/\.html?$/i.test(relative)) {
      const { blocks, references } = inspectHtml(original);
      references.forEach((reference) => enqueue(reference, relative));
      output = original;
      for (const block of blocks.reverse()) {
        const result = await compress(original.slice(block.start, block.end), block.loader, relative);
        result.imports.forEach((reference) => enqueue(reference, relative));
        output = output.slice(0, block.start) + result.code + output.slice(block.end);
      }
    } else {
      const result = await compress(original, /\.css$/i.test(relative) ? "css" : "js", relative);
      result.imports.forEach((reference) => enqueue(reference, relative));
      output = result.code;
    }
    totals.files += 1;
    totals.rawBefore += Buffer.byteLength(original);
    totals.rawAfter += Buffer.byteLength(output);
    totals.gzipBefore += gzipSync(original).length;
    totals.gzipAfter += gzipSync(output).length;
    if (output !== original) changes.push({ file, output });
  }
  // Validate every input before writing any output; a failure also stops CI upload.
  for (const { file, output } of changes) await writeFile(file, output);
  totals.changed = changes.length;
  return totals;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length > 3) throw new Error("Usage: node scripts/minify-site.mjs [staging/_site]");
    console.log(JSON.stringify(await minifySite(process.argv[2]), null, 2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
