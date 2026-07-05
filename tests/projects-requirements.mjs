import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const projectsPageUrl = new URL("../projects/index.html", import.meta.url);
const manifestUrl = new URL("../projects/manifest.json", import.meta.url);
const topicPageUrl = new URL("../projects/brain-memory-for-ai-agents/index.html", import.meta.url);
const foundationsPageUrl = new URL("../projects/foundations/index.html", import.meta.url);
const foundationsReadmeUrl = new URL("../projects/foundations/README.md", import.meta.url);
const foundationsPlannerUrl = new URL("../projects/foundations/multi-agent-planner.md", import.meta.url);
const foundationsRoadmapUrl = new URL("../projects/foundations/llm-agent-engineer-roadmap.md", import.meta.url);
const fontSourcesUrl = new URL("../assets/fonts/README.md", import.meta.url);

assert.equal(existsSync(projectsPageUrl), true, "projects/ should expose a static project homepage");
assert.equal(existsSync(manifestUrl), true, "projects/ should expose a manifest.json index for project modules");
assert.equal(existsSync(topicPageUrl), true, "brain-memory-for-ai-agents should expose a static topic page");
assert.equal(existsSync(foundationsPageUrl), true, "foundations should expose a static project page");
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

assert.match(projectsHtml, /<title>项目 \| NeuroScience x AI<\/title>/, "projects page should use the Chinese project directory page title");
assert.match(projectsHtml, /data-page="projects-homepage"/, "projects/ should identify itself as a homepage");
assert.match(projectsHtml, /href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"/, "projects page logo should link back to the main homepage");
assert.match(projectsHtml, /projects\/manifest\.json/, "projects homepage should load its project modules from projects/manifest.json");
assert.match(projectsHtml, /<h1 id="page-title"><span class="title-line">项目<\/span><\/h1>/, "visible projects page title should be 项目");
assert.match(projectsHtml, /font-family:\s*var\(--title-calligraphy-font\)/, "projects page title should use the shared self-hosted calligraphy font stack");
assert.doesNotMatch(projectsHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "projects page should not send users to the GitHub folder listing");
assert.deepEqual(
  manifest.map((project) => project.title),
  ["基石", "记忆与智能体"],
  "projects bookmarks should include the registered Chinese project titles in display order",
);
assert.match(fontSources, /ZhiMangXing-Regular\.ttf --text='记忆与智能体基石'/, "bookmark font subset should include both project bookmark titles");

assert.match(topicHtml, /<title>Brain Memory for AI Agents \| NeuroScience x AI<\/title>/, "topic page should use the project title");
assert.match(topicHtml, /data-page="project-topic"/, "project topic should identify itself as a topic page");
assert.match(topicHtml, /href="\.\.\/index\.html"[\s\S]*返回项目/, "topic page should link back to the local projects homepage");
assert.match(topicHtml, /README\.md/, "topic page should link to the existing project README");
assert.match(topicHtml, /research-roadmap\.md/, "topic page should link to the existing project roadmap");
assert.match(topicHtml, /hypotheses\.md/, "topic page should link to the existing project hypotheses");
assert.match(topicHtml, /mechanism-to-agent-design\.md/, "topic page should link to the existing mechanism mapping");
assert.match(topicHtml, /href="\.\.\/\.\.\/papers\/brain-memory-for-ai-agents\/"/, "topic page should link to the matching local paper topic page");
assert.doesNotMatch(topicHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "topic page should not send users to the GitHub folder listing");

assert.match(foundationsHtml, /data-page="foundations-roadmap-reader"/, "foundations page should identify itself as the roadmap reader");
assert.match(foundationsHtml, /id="reader-shell"/, "foundations page should use the reader shell");
assert.match(foundationsHtml, /roadmap\/roadmap-data\.json/, "foundations reader should load generated roadmap data");
assert.doesNotMatch(foundationsHtml, /class="doc-grid"|class="doc-link"/, "foundations page should not remain a document-card homepage");
assert.match(foundationsRoadmap, /Agent \/ LLM Systems Engineer/, "foundations roadmap should target Agent / LLM Systems Engineer interviews");
