import { readdirSync, readFileSync } from "node:fs";
import { extname, relative, resolve, sep } from "node:path";

export function parseYamlScalar(value) {
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null") return null;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

export function parseYamlValue(value) {
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((item) => parseYamlScalar(item.trim()));
  }
  return parseYamlScalar(value);
}

export function parseFrontmatter(markdown) {
  const match = String(markdown ?? "").match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { frontmatter: {}, body: String(markdown ?? "") };
  const frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const parsed = line.match(/^([^:]+):\s*(.*)$/);
    if (parsed) frontmatter[parsed[1].trim()] = parseYamlValue(parsed[2].trim());
  }
  return { frontmatter, body: String(markdown ?? "").slice(match[0].length) };
}

export function toArray(value) {
  if (Array.isArray(value)) return value.map(String);
  if (value === undefined || value === null || value === "") return [];
  return [String(value)];
}

export function findMarkdownFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) files.push(...findMarkdownFiles(path));
    else if (entry.isFile() && extname(entry.name) === ".md") files.push(path);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

export function toProjectPath(path, projectDir) {
  return relative(projectDir, path).split(sep).join("/");
}

export function extractTitle(markdown, fallback) {
  const match = String(markdown ?? "").match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallback;
}

export function findMarkdownDocuments(rootDir, projectDir, options = {}) {
  const stripPrefix = options.stripPrefix ?? "";
  return findMarkdownFiles(rootDir)
    .filter((filePath) => options.includeReadme === true || !filePath.endsWith(`${sep}README.md`))
    .map((filePath) => {
      const path = toProjectPath(filePath, projectDir);
      const id = path.replace(new RegExp(`^${stripPrefix}`), "").replace(/\.md$/, "");
      const markdown = readFileSync(filePath, "utf8");
      const { frontmatter, body } = parseFrontmatter(markdown);
      return {
        id,
        path,
        title: extractTitle(body, id),
        markdown,
        body: body.trim(),
        frontmatter,
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}
