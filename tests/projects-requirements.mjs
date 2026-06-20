import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const projectsPageUrl = new URL("../projects/index.html", import.meta.url);
const topicPageUrl = new URL("../projects/brain-memory-for-ai-agents/index.html", import.meta.url);

assert.equal(existsSync(projectsPageUrl), true, "projects/ should expose a static project homepage");
assert.equal(existsSync(topicPageUrl), true, "brain-memory-for-ai-agents should expose a static topic page");

const projectsHtml = readFileSync(projectsPageUrl, "utf8");
const topicHtml = readFileSync(topicPageUrl, "utf8");

assert.match(projectsHtml, /<title>Research Projects \| NeuroScience x AI<\/title>/, "projects page should use a project homepage title");
assert.match(projectsHtml, /data-page="projects-homepage"/, "projects/ should identify itself as a homepage");
assert.match(projectsHtml, /href="\.\.\/index\.html" aria-label="Back to NeuroScience x AI homepage"/, "projects page logo should link back to the main homepage");
assert.match(projectsHtml, /href="brain-memory-for-ai-agents\/"[\s\S]*Brain Memory for AI Agents/, "projects page should link to the Brain Memory for AI Agents topic page");
assert.doesNotMatch(projectsHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "projects page should not send users to the GitHub folder listing");

assert.match(topicHtml, /<title>Brain Memory for AI Agents \| NeuroScience x AI<\/title>/, "topic page should use the project title");
assert.match(topicHtml, /data-page="project-topic"/, "project topic should identify itself as a topic page");
assert.match(topicHtml, /href="\.\.\/index\.html"[\s\S]*Research Projects/, "topic page should link back to the local projects homepage");
assert.match(topicHtml, /README\.md/, "topic page should link to the existing project README");
assert.match(topicHtml, /research-roadmap\.md/, "topic page should link to the existing project roadmap");
assert.match(topicHtml, /hypotheses\.md/, "topic page should link to the existing project hypotheses");
assert.match(topicHtml, /mechanism-to-agent-design\.md/, "topic page should link to the existing mechanism mapping");
assert.match(topicHtml, /href="\.\.\/\.\.\/papers\/brain-memory-for-ai-agents\/"/, "topic page should link to the matching local paper topic page");
assert.doesNotMatch(topicHtml, /github\.com\/mingxiangbian\/NeuroScience\/tree\/main\/projects/i, "topic page should not send users to the GitHub folder listing");
