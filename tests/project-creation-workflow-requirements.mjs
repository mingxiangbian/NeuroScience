import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const guideUrl = new URL("../docs/project-creation-workflow.md", import.meta.url);
const agentsUrl = new URL("../AGENTS.md", import.meta.url);
const templateIndexUrl = new URL("../templates/project-creation/README.md", import.meta.url);

assert.equal(existsSync(guideUrl), true, "project creation workflow guide should exist");

const guide = readFileSync(guideUrl, "utf8");
const agents = existsSync(agentsUrl) ? readFileSync(agentsUrl, "utf8") : "";
const templateIndex = existsSync(templateIndexUrl) ? readFileSync(templateIndexUrl, "utf8") : "";

assert.match(guide, /# Project Creation Workflow/, "workflow guide should have a stable title");
assert.match(guide, /## Quick Start For New Projects/, "workflow guide should include a quick-start section");
assert.match(guide, /## Project Type Router/, "workflow guide should define the project type router");
assert.match(guide, /knowledge \/ learning \/ roadmap/i, "workflow guide should cover knowledge-style projects");
assert.match(guide, /paper \/ topic reading/i, "workflow guide should cover paper-reading projects");
assert.match(guide, /engineering \/ tool \/ experiment/i, "workflow guide should cover engineering projects");
assert.match(guide, /research project/i, "workflow guide should cover research projects");
assert.match(guide, /hybrid project/i, "workflow guide should cover hybrid projects");
assert.match(guide, /Do not force engineering projects into the Foundations reader/, "workflow guide should protect engineering projects from reader overuse");
assert.match(guide, /source maps belong in `sources\/`/, "workflow guide should keep source maps in sources/");
assert.match(guide, /open questions belong in `questions\/\{slug\}\/`/, "workflow guide should keep open questions in questions/{slug}/");
assert.match(guide, /Ask only when/, "workflow guide should define the clarification boundary");
assert.match(guide, /Verification Checklist/, "workflow guide should include a verification checklist");
assert.match(agents, /## Project Creation Workflow/, "AGENTS should expose the project creation workflow");
assert.match(agents, /docs\/project-creation-workflow\.md/, "AGENTS should point future workers to the workflow guide");
assert.match(agents, /Knowledge \/ learning \/ roadmap/, "AGENTS should include the knowledge project route");
assert.match(agents, /Engineering \/ tool \/ experiment/, "AGENTS should include the engineering project route");
assert.match(agents, /Do not force engineering projects into the Foundations reader/, "AGENTS should preserve the engineering project exception");
assert.match(agents, /Ask only when the location, privacy, runtime, conflict, or overwrite risk is unclear/, "AGENTS should define when clarification is needed");
assert.equal(existsSync(templateIndexUrl), true, "project creation template index should exist");
assert.match(templateIndex, /# Project Creation Templates/, "template index should have a stable title");
assert.match(templateIndex, /Knowledge \/ Learning \/ Roadmap/, "template index should include knowledge project structure");
assert.match(templateIndex, /Paper \/ Topic Reading/, "template index should include paper project structure");
assert.match(templateIndex, /Engineering \/ Tool \/ Experiment/, "template index should include engineering project structure");
assert.match(templateIndex, /Research Project/, "template index should include research project structure");
assert.match(templateIndex, /Hybrid Project/, "template index should include hybrid project structure");
assert.match(templateIndex, /This is not a generator/, "template index should clarify that it is not a generator");
assert.match(templateIndex, /projects\/\{slug\}\/\n(?:  .+\n)*  docs\/\n(?:    .+\n)*    spec\.md/, "engineering template should include project-local spec path");
assert.match(templateIndex, /questions\/\{slug\}\/open-questions\.md/, "research template should link questions outside the project folder");
