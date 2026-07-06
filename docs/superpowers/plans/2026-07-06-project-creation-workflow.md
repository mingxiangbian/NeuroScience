# Project Creation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把通用项目创建工作流固化到当前 repo，让后续“创建新项目”请求可以按项目类型自动分流、生成默认结构并验证，而不是重新讨论基础目录和页面形态。

**Architecture:** 第一阶段采用 repo-local documentation + minimal template index，不写 CLI，不重构 Foundations runtime。新增一个 requirement test 锁定 workflow guide、`AGENTS.md` 指针和 `templates/project-creation/` 索引；`AGENTS.md` 只放短入口和关键分流规则，详细步骤放在 `docs/project-creation-workflow.md`。

**Tech Stack:** Markdown documentation, repo-local `AGENTS.md`, Node.js assertion-based requirement tests.

---

## File Structure

- Create: `tests/project-creation-workflow-requirements.mjs`
  - 静态验证项目创建 workflow 的 guide、AGENTS 指针和 template index 是否存在，并检查关键规则没有丢失。
- Create: `docs/project-creation-workflow.md`
  - 用户下次要求创建新项目时的执行指南：项目类型判断、默认目录、默认输出、追问边界、验证清单。
- Modify: `AGENTS.md`
  - 增加一个短 section，告诉未来 Codex 在“创建新项目”时先读 `docs/project-creation-workflow.md`，并保留最关键的类型分流。
- Create: `templates/project-creation/README.md`
  - 放轻量模板索引和各类项目的默认结构，供后续人工或 Codex 复制参考；不做生成器。

## Task 1: Add Workflow Guide And First Requirement Test

**Files:**
- Create: `tests/project-creation-workflow-requirements.mjs`
- Create: `docs/project-creation-workflow.md`

- [ ] **Step 1: Add failing workflow-guide requirements**

Create `tests/project-creation-workflow-requirements.mjs` with:

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
```

Expected: FAIL with:

```text
project creation workflow guide should exist
```

- [ ] **Step 3: Create the workflow guide**

Create `docs/project-creation-workflow.md` with:

````md
# Project Creation Workflow

This guide is the repo-local default for future "create a new project" requests. It turns a user's topic, content, and goal into a concrete project structure without re-litigating directories, page style, or basic validation.

Use this guide only inside the `NeuroScience` repo. It does not replace research protocols, paper review standards, or project-specific specs.

## Quick Start For New Projects

When the user asks to create a new project:

1. Infer the project type from the user's goal and content.
2. Pick the default location and output shape from the router below.
3. Ask only when the choice changes long-term organization, privacy, runtime, or overwrite risk.
4. Create the smallest durable project structure that satisfies the goal.
5. Add the project to the relevant directory page or manifest when it should be discoverable.
6. Run the verification checklist before reporting completion.

Do not ask the user to choose a structure when the content is enough to decide. Do not force engineering projects into the Foundations reader.

## Project Type Router

| Type | Trigger signals | Default location | Default presentation |
| --- | --- | --- | --- |
| knowledge / learning / roadmap | learning, prep, roadmap, knowledge base, review, module notes | `projects/{slug}/` | Foundations-style reader/dashboard |
| paper / topic reading | paper, reading notes, citation, method, evidence, limitations | `papers/{slug}/` | Paper reader or structured paper notes |
| engineering / tool / experiment | implement, app, tool, demo, agent, experiment system, runnable code | `projects/{slug}/` | README, spec, plan, source, tests, optional demo |
| research project | research question, hypothesis, mechanism, experiment design, staged conclusion | `projects/{slug}/` | README, research roadmap, hypotheses, linked questions and sources |
| hybrid project | mixes engineering, learning, paper reading, and research | `projects/{slug}/` for the main artifact | Split layers; project homepage links them |

## Directory Rules

- Project core belongs in `projects/{slug}/`.
- Paper-related learning material belongs in `papers/{slug}/`.
- Source maps belong in `sources/`, even when they support one project.
- Open questions belong in `questions/{slug}/`.
- Dated discussion records belong in `sessions/YYYY-MM-DD-{slug}.md`.
- Do not leave source maps or general open questions inside `projects/{slug}/` as the long-term home.

## Default Outputs

### Knowledge / Learning / Roadmap

Create:

- `projects/{slug}/index.html`
- `projects/{slug}/roadmap/modules/*.md`
- `projects/{slug}/roadmap/roadmap-data.json`
- `projects/{slug}/scripts/build-roadmap-data.mjs`
- A directory entry in `projects/manifest.json` or the current project directory page system

Defaults:

- Initial progress is `0` unless the user explicitly provides completed work.
- `Overview` is a dashboard, not a normal module.
- Main content is concept-centered; timeline is allowed but not the primary structure.
- Right-side notes are associated with knowledge cards; no associated note means blank.
- Reuse the current Foundations reader interaction pattern for search, navigation, local annotations, and collapsed section rail.

### Paper / Topic Reading

Create:

- A paper reader page or structured paper note under `papers/{slug}/`.
- Citation, research question, claim, method, key results, evidence strength, limitations, quality checks, takeaway, and open questions.
- `sources/{slug}-sources.md` when the work creates a source map.
- `questions/{slug}/open-questions.md` when the work creates durable questions.

Defaults:

- Separate literature claims, user hypotheses, and assistant synthesis.
- Use current sources for recent or contested claims.
- Keep PDFs, HTML exports, and notes organized under the paper topic directory when they are paper-specific.

### Engineering / Tool / Experiment

Create:

- `projects/{slug}/README.md`
- `projects/{slug}/docs/spec.md`
- `projects/{slug}/docs/plan.md`
- `projects/{slug}/src/`
- `projects/{slug}/tests/`

Defaults:

- Prioritize a runnable project over a decorative page.
- Add `index.html` only when a browser demo or public project page is part of the goal.
- State run commands, test commands, current limitations, and next engineering checkpoints.
- Do not hide source code behind a reader-style learning page.

### Research Project

Create:

- `projects/{slug}/README.md`
- `projects/{slug}/research-roadmap.md`
- `projects/{slug}/hypotheses.md`
- `questions/{slug}/open-questions.md` when durable questions exist
- `sources/{slug}-sources.md` when source maps exist

Defaults:

- Track evidence strength and claim type.
- Keep competing hypotheses explicit.
- Link sources and questions from the project README instead of moving them into the project folder.

### Hybrid Project

Create the main project under `projects/{slug}/`, then split supporting material by role:

```text
projects/{slug}/
  README.md
  docs/
  src/
  tests/
  learning/
questions/{slug}/open-questions.md
sources/{slug}-sources.md
```

Defaults:

- The main artifact controls the homepage.
- Learning pages, source maps, and open questions stay linked but separate.
- If the project includes both a runnable tool and a study roadmap, build the tool structure first and put the reader under `learning/`.

## Ask Only When

Ask a clarification question before creating files only when:

- The project could reasonably belong in both `projects/` and `papers/`, and the wrong location would harm long-term organization.
- The user asks for a public page but the content appears private, personal, or unsuitable for publishing.
- An engineering project requires a runtime choice that cannot be inferred from existing repo context.
- The requested outputs conflict, such as pure static GitHub Pages plus server-side persistence.
- The target directory already exists and would be overwritten.

## Verification Checklist

Always run the narrow checks relevant to the project type:

- Markdown or static-page hygiene: `git diff --check`
- New workflow rule coverage: `node tests/project-creation-workflow-requirements.mjs`
- Project directory coverage: `node tests/projects-requirements.mjs` when `projects/` changes
- Paper directory coverage: `node tests/papers-requirements.mjs` when `papers/` changes
- Reader syntax: `node --check path/to/reader.js` when a reader JS file changes
- Build script syntax: `node --check path/to/build-script.mjs` when a build script changes
- Generated data: run the project-specific build command when Markdown sources feed JSON
- Engineering project checks: run the project-specific lint/test/build command documented in its README

Report which files were created or updated, which commands passed, and any checks that were skipped because the project type did not require them.
````

- [ ] **Step 4: Run focused verification**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
git diff --check
```

Expected: both commands PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/project-creation-workflow-requirements.mjs docs/project-creation-workflow.md
git commit -m "Add project creation workflow guide"
```

## Task 2: Wire The Workflow Into AGENTS

**Files:**
- Modify: `tests/project-creation-workflow-requirements.mjs`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add failing AGENTS requirements**

In `tests/project-creation-workflow-requirements.mjs`, after the final guide assertion:

```js
assert.match(guide, /Verification Checklist/, "workflow guide should include a verification checklist");
```

add:

```js
assert.match(agents, /## Project Creation Workflow/, "AGENTS should expose the project creation workflow");
assert.match(agents, /docs\/project-creation-workflow\.md/, "AGENTS should point future workers to the workflow guide");
assert.match(agents, /Knowledge \/ learning \/ roadmap/, "AGENTS should include the knowledge project route");
assert.match(agents, /Engineering \/ tool \/ experiment/, "AGENTS should include the engineering project route");
assert.match(agents, /Do not force engineering projects into the Foundations reader/, "AGENTS should preserve the engineering project exception");
assert.match(agents, /Ask only when the location, privacy, runtime, conflict, or overwrite risk is unclear/, "AGENTS should define when clarification is needed");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
```

Expected: FAIL with:

```text
AGENTS should expose the project creation workflow
```

- [ ] **Step 3: Add the AGENTS workflow pointer**

In `AGENTS.md`, insert this section immediately before `## 语言规范（Language Policy）`:

```md
## Project Creation Workflow

当用户要求创建新项目时，先读取并遵守 `docs/project-creation-workflow.md`。目标是让用户只提供主题、内容和目标，助手就能按项目类型选择结构、页面形态和验证步骤。

默认分流：

- Knowledge / learning / roadmap：放入 `projects/{slug}/`，使用 Foundations 风格 reader/dashboard。
- Paper / topic reading：放入 `papers/{slug}/`，使用 paper reader 或结构化 paper note。
- Engineering / tool / experiment：放入 `projects/{slug}/`，优先 `README`、`docs/spec.md`、`docs/plan.md`、`src/`、`tests/` 和可运行验证。
- Research project：放入 `projects/{slug}/`，配套 `questions/{slug}/` 与 `sources/{slug}-sources.md`。
- Hybrid project：主项目放 `projects/{slug}/`，学习页、source map 和 open questions 按职责分层链接。

Do not force engineering projects into the Foundations reader. 只有当 location、privacy、runtime、目标冲突或 overwrite risk 不清楚时才先追问；其他情况按 workflow 默认值直接推进。
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
git diff --check
```

Expected: both commands PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/project-creation-workflow-requirements.mjs AGENTS.md
git commit -m "Document project creation workflow entrypoint"
```

## Task 3: Add Minimal Project-Creation Template Index

**Files:**
- Modify: `tests/project-creation-workflow-requirements.mjs`
- Create: `templates/project-creation/README.md`

- [ ] **Step 1: Add failing template-index requirements**

In `tests/project-creation-workflow-requirements.mjs`, after the AGENTS assertions, add:

```js
assert.equal(existsSync(templateIndexUrl), true, "project creation template index should exist");
assert.match(templateIndex, /# Project Creation Templates/, "template index should have a stable title");
assert.match(templateIndex, /Knowledge \/ Learning \/ Roadmap/, "template index should include knowledge project structure");
assert.match(templateIndex, /Paper \/ Topic Reading/, "template index should include paper project structure");
assert.match(templateIndex, /Engineering \/ Tool \/ Experiment/, "template index should include engineering project structure");
assert.match(templateIndex, /Research Project/, "template index should include research project structure");
assert.match(templateIndex, /Hybrid Project/, "template index should include hybrid project structure");
assert.match(templateIndex, /This is not a generator/, "template index should clarify that it is not a generator");
assert.match(templateIndex, /projects\/\\{slug\\}\/docs\/spec\.md/, "engineering template should include project-local spec path");
assert.match(templateIndex, /questions\/\\{slug\\}\/open-questions\.md/, "research template should link questions outside the project folder");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
```

Expected: FAIL with:

```text
project creation template index should exist
```

- [ ] **Step 3: Create the template index**

Create `templates/project-creation/README.md` with:

````md
# Project Creation Templates

This is not a generator. It is a compact reference for future Codex runs when the user asks to create a new project from natural-language content.

For the full decision rules, read `docs/project-creation-workflow.md` first.

## Knowledge / Learning / Roadmap

Use when the project is mainly a learning plan, interview prep system, knowledge base, or roadmap.

```text
projects/{slug}/
  index.html
  README.md
  roadmap/
    modules/
      overview.md
      module-name.md
    roadmap-data.json
    roadmap-reader.css
    roadmap-reader.js
  scripts/
    build-roadmap-data.mjs
```

Default page: Foundations-style reader/dashboard.

Required checks:

- `node --check projects/{slug}/roadmap/roadmap-reader.js`
- `node --check projects/{slug}/scripts/build-roadmap-data.mjs`
- Run the project-specific build script.
- `node tests/projects-requirements.mjs` when the project directory page or manifest changes.
- `git diff --check`

## Paper / Topic Reading

Use when the project is mainly a paper, paper cluster, or literature reading packet.

```text
papers/{slug}/
  index.html
  downloaded-papers.md
  notes-cn/
  pdfs/
  html/
sources/{slug}-sources.md
questions/{slug}/open-questions.md
```

Default page: paper reader or structured paper note.

Required checks:

- `node tests/papers-requirements.mjs`
- `node tests/paper-reader-requirements.mjs` when shared reader behavior changes.
- `git diff --check`

## Engineering / Tool / Experiment

Use when the project must run, test, or demonstrate a system.

```text
projects/{slug}/
  README.md
  docs/
    spec.md
    plan.md
  src/
  tests/
```

Default page: no reader unless the user asks for a demo or public project page.

Required checks:

- Project-specific lint/test/build commands from `README.md`.
- Smoke test for the runnable path.
- `node tests/projects-requirements.mjs` when the project directory page or manifest changes.
- `git diff --check`

## Research Project

Use when the project is mainly a durable research question, hypothesis system, mechanism map, or experiment design.

```text
projects/{slug}/
  README.md
  research-roadmap.md
  hypotheses.md
questions/{slug}/open-questions.md
sources/{slug}-sources.md
```

Default page: Markdown-first; add a reader/dashboard only when public navigation materially helps.

Required checks:

- Evidence strength and claim type are explicit.
- `questions/{slug}/open-questions.md` has status and next action.
- Source maps stay in `sources/`.
- `git diff --check`

## Hybrid Project

Use when the project mixes runnable engineering, learning notes, paper reading, and research questions.

```text
projects/{slug}/
  README.md
  docs/
  src/
  tests/
  learning/
questions/{slug}/open-questions.md
sources/{slug}-sources.md
```

Default page: the main artifact controls the homepage. Supporting materials are linked by role instead of merged into one large file.

Required checks:

- Run the checks for each active layer.
- Confirm the project homepage links to supporting learning, source, and question files.
- `git diff --check`
````

- [ ] **Step 4: Run focused verification**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
git diff --check
```

Expected: both commands PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/project-creation-workflow-requirements.mjs templates/project-creation/README.md
git commit -m "Add project creation template index"
```

## Task 4: Final Verification

**Files:**
- Verify only; no planned file changes.

- [ ] **Step 1: Run syntax check for the new test**

Run:

```bash
node --check tests/project-creation-workflow-requirements.mjs
```

Expected: PASS.

- [ ] **Step 2: Run focused workflow test**

Run:

```bash
node tests/project-creation-workflow-requirements.mjs
```

Expected: PASS.

- [ ] **Step 3: Run existing directory tests**

Run:

```bash
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
```

Expected: both commands PASS.

- [ ] **Step 4: Run repository whitespace check**

Run:

```bash
git diff --check
```

Expected: PASS with no output.

- [ ] **Step 5: Confirm git state**

Run:

```bash
git status --short
```

Expected: no output after the task commits above.

## Self-Review Checklist

- Spec coverage: the plan implements the repo-local guide, type router, clarification policy, project type defaults, minimal scaffold/index, and verification checks.
- Scope: no CLI, no shared runtime migration, no Foundations rewrite, no backend.
- Test coverage: new static requirement test guards the guide, AGENTS pointer, template index, directory boundaries, engineering-reader exception, and verification checklist.
- Execution boundary: this plan prepares the workflow for future project creation; it does not create a new user project itself.
