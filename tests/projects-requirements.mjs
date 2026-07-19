import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const projectsPageUrl = new URL("../projects/index.html", import.meta.url);
const manifestUrl = new URL("../projects/manifest.json", import.meta.url);
const topicPageUrl = new URL("../projects/brain-memory-for-ai-agents/index.html", import.meta.url);
const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const financePageUrl = new URL("../projects/finance/index.html", import.meta.url);
const zajiPageUrl = new URL("../projects/zaji/index.html", import.meta.url);
const foundationsReadmeUrl = new URL("../projects/foundations/README.md", import.meta.url);
const foundationsPlannerUrl = new URL("../projects/foundations/multi-agent-planner.md", import.meta.url);
const foundationsRoadmapUrl = new URL("../projects/foundations/llm-agent-engineer-roadmap.md", import.meta.url);
const fontSourcesUrl = new URL("../assets/fonts/README.md", import.meta.url);
const bookmarkFontUrl = new URL("../assets/fonts/ZhiMangXing-Bookmark.woff2", import.meta.url);

assert.equal(existsSync(projectsPageUrl), true, "projects/ should expose a static project homepage");
assert.equal(existsSync(manifestUrl), true, "projects/ should expose a manifest.json index for project modules");
assert.equal(existsSync(topicPageUrl), true, "brain-memory-for-ai-agents should expose a static topic page");
assert.equal(existsSync(foundationsPageUrl), true, "foundations should expose a static project page");
assert.equal(existsSync(financePageUrl), true, "finance should expose a static learning-reader page");
assert.equal(existsSync(zajiPageUrl), true, "zaji should expose a static public notebook homepage");
assert.equal(existsSync(foundationsReadmeUrl), true, "foundations should include a README");
assert.equal(existsSync(foundationsPlannerUrl), true, "foundations should include the reusable multi-agent planner");
assert.equal(existsSync(foundationsRoadmapUrl), true, "foundations should include the LLM/Agent engineer roadmap");
assert.equal(existsSync(fontSourcesUrl), true, "self-hosted font notes should exist");

const projectsHtml = readFileSync(projectsPageUrl, "utf8");
const manifest = JSON.parse(readFileSync(manifestUrl, "utf8"));
const topicHtml = readFileSync(topicPageUrl, "utf8");
const foundationsHtml = readFileSync(foundationsPageUrl, "utf8");
const foundationsRoadmap = readFileSync(foundationsRoadmapUrl, "utf8");
const fontSources = readFileSync(fontSourcesUrl, "utf8");
const bookmarkFontCmap = execFileSync("ttx", ["-q", "-t", "cmap", "-o", "-", fileURLToPath(bookmarkFontUrl)], {
  encoding: "utf8",
});

assert.match(projectsHtml, /<title>项目 \| NeuroScience x AI<\/title>/, "projects page should use the Chinese project directory page title");
assert.match(projectsHtml, /data-page="projects-homepage"/, "projects/ should identify itself as a homepage");
assert.match(projectsHtml, /href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"/, "projects page logo should link back to the main homepage");
assert.match(projectsHtml, /projects\/manifest\.json/, "projects homepage should load its project modules from projects/manifest.json");
assert.match(projectsHtml, /<h1 id="page-title"><span class="title-line">项目<\/span><\/h1>/, "visible projects page title should be 项目");
assert.match(projectsHtml, /font-family:\s*var\(--title-calligraphy-font\)/, "projects page title should use the shared self-hosted calligraphy font stack");
assert.match(projectsHtml, /data-title-script/, "projects page should tag project title script for bookmark layout");
assert.match(projectsHtml, /\.project-card\[data-title-script="latin"\] h2\s*\{[\s\S]*writing-mode:\s*horizontal-tb/, "latin project titles should render horizontally inside bookmarks");
assert.doesNotMatch(projectsHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "projects page should not send users to the GitHub folder listing");
assert.deepEqual(
  manifest.map((project) => project.title),
  ["基石", "语言", "记忆与智能体", "投资", "札记"],
  "projects bookmarks should include the registered project titles in display order",
);
assert.equal(manifest.find((project) => project.id === "finance")?.folder, "finance/", "finance should link to its reader page");
assert.equal(manifest.find((project) => project.id === "zaji")?.folder, "zaji/", "zaji should link to its public notebook page");
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.folder,
  "language/ielts-academic/",
  "IELTS Academic should be linked through the nested language project folder",
);
assert.equal(
  manifest.find((project) => project.id === "ielts-academic")?.title,
  "语言",
  "IELTS Academic should display as the Chinese language bookmark",
);
assert.match(fontSources, /ZhiMangXing-Regular\.ttf --text='记忆与智能体基石语言投资情感大模型札记'/, "bookmark font subset should include the Chinese project and paper directory titles");
for (const character of new Set(manifest.map((project) => project.title).join(""))) {
  const codePoint = character.codePointAt(0)?.toString(16);
  assert.match(
    bookmarkFontCmap,
    new RegExp(`code="0x${codePoint}"`, "i"),
    `bookmark font subset should contain the visible Chinese bookmark character ${character}`,
  );
}

assert.match(topicHtml, /<title>Brain Memory for AI Agents \| NeuroScience x AI<\/title>/, "topic page should use the project title");
assert.match(topicHtml, /data-page="project-topic"/, "project topic should identify itself as a topic page");
assert.match(topicHtml, /href="\.\.\/index\.html"[\s\S]*返回项目/, "topic page should link back to the local projects homepage");
for (const file of ["README.md", "research-roadmap.md", "hypotheses.md", "mechanism-to-agent-design.md"]) {
  const renderedUrl = `https://github.com/mingxiangbian/NeuroScience/blob/main/projects/brain-memory-for-ai-agents/${file}`;
  assert.ok(topicHtml.includes(`href="${renderedUrl}"`), `topic page should open ${file} in GitHub's rendered document view`);
}
assert.equal((topicHtml.match(/target="_blank" rel="noopener noreferrer"/g) ?? []).length, 4, "rendered project documents should open safely without replacing the study page");
assert.match(topicHtml, /href="\.\.\/\.\.\/papers\/brain-memory-for-ai-agents\/"/, "topic page should link to the matching local paper topic page");
assert.doesNotMatch(topicHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "topic page should not send users to the GitHub folder listing");

assert.match(foundationsHtml, /data-page="foundations-roadmap-reader"/, "foundations page should identify itself as the roadmap reader");
assert.match(foundationsHtml, /id="reader-shell"/, "foundations page should use the reader shell");
assert.match(foundationsHtml, /roadmap\/roadmap-data\.json/, "foundations reader should load generated roadmap data");
assert.doesNotMatch(foundationsHtml, /class="doc-grid"|class="doc-link"/, "foundations page should not remain a document-card homepage");
assert.match(foundationsRoadmap, /Agent \/ LLM Systems Engineer/, "foundations roadmap should target Agent / LLM Systems Engineer interviews");

const financeHtml = readFileSync(financePageUrl, "utf8");
assert.match(financeHtml, /<title>投资 \| NeuroScience x AI<\/title>/, "finance page should use the Chinese project title");
assert.match(financeHtml, /data-page="finance-roadmap-reader"/, "finance should identify itself as a roadmap reader");
assert.match(financeHtml, /data-project-id="finance"/, "finance reader state should remain isolated from Foundations");
assert.match(financeHtml, /data-source="roadmap\/roadmap-data\.json"/, "finance should load its generated roadmap data");
