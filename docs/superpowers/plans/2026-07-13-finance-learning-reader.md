# Finance Learning Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved investment guide into a public, module-based Finance learning reader with progress, retrieval, and local annotations.

**Architecture:** Keep the approved Markdown-to-JSON pipeline under `projects/finance/`. Reuse the existing Foundations reader surface, making its data source and local persistence project-scoped so Finance remains an independent learning space without duplicating the reader implementation.

**Tech Stack:** Static HTML, browser ES modules, Node.js build/test scripts, existing `marked` and `sanitize-html` Markdown pipeline.

## Global Constraints

- Keep the project public and learning-only: no holdings, trading logs, or personal financial records.
- Use exactly nine concept-centred learning modules plus the Overview dashboard.
- Treat `roadmap/modules/*.md` as the only Finance content source; delete the original monolithic guide after migration.
- Start all module progress at `0` and retain local-only annotations.
- Keep the existing Foundations reader functional while making its storage keys and JSON source project-scoped.
- Update the project manifest and the bookmark-font subset for the visible title `投资`.

---

### Task 1: Lock the Finance reader contract with a failing test

**Files:**
- Create: `tests/finance-learning-reader-requirements.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: generated `projects/finance/roadmap/roadmap-data.json`.
- Produces: `npm run test:finance`, which checks source layout, reader wiring, data shape, nine modules, initial progress, search records, and public-content boundaries.

- [ ] **Step 1: Write the failing test**

```js
assert.equal(existsSync(financePageUrl), true);
assert.deepEqual(data.modules.map((module) => module.id), [
  "overview", "investment-basics", "asset-classes", "risk-allocation",
  "fund-company-analysis", "valuation", "trading-execution",
  "behavior-process", "study-plan-tools", "terms-further-reading",
]);
assert.equal(data.project.id, "finance");
assert.ok(data.modules.every((module) => module.learningProgress === 0));
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/finance-learning-reader-requirements.mjs`

Expected: `AssertionError` because Finance has neither a reader page nor generated data.

- [ ] **Step 3: Register the focused test command**

```json
"test:finance": "node tests/finance-learning-reader-requirements.mjs"
```

- [ ] **Step 4: Re-run the test**

Run: `npm run test:finance`

Expected: still fails on missing implementation, proving the command exercises the new contract.

### Task 2: Create the module-only Finance content pipeline

**Files:**
- Create: `projects/finance/scripts/build-roadmap-data.mjs`
- Create: `projects/finance/roadmap/modules/overview.md`
- Create: `projects/finance/roadmap/modules/{investment-basics,asset-classes,risk-allocation,fund-company-analysis,valuation,trading-execution,behavior-process,study-plan-tools,terms-further-reading}.md`
- Create: `projects/finance/roadmap/roadmap-data.json`
- Delete: `projects/finance/investment_beginner_guide_zh.md`

**Interfaces:**
- Consumes: frontmatter fields `id`, `title`, `status`, `learning_progress`, `last_updated`, and `priority`, plus Markdown sections.
- Produces: `{ project, modules }` JSON compatible with the shared reader. Each module includes rendered `sections`, stable `sectionIds`, `knowledgeNotes`, `timeline`, `searchText`, and section-level `searchEntries`.

- [ ] **Step 1: Implement a strict Finance builder**

```js
const MODULES = [["overview", "Overview"], ["investment-basics", "投资的本质与前提"] /* … */];
const parsed = parseFrontmatter(markdown, `${id}.md`);
if (parsed.data.id !== id || parsed.data.title !== title) throw new Error(`${id} metadata mismatch`);
if (!VALID_STATUSES.has(parsed.data.status)) throw new Error(`${id} has invalid status`);
```

Import the established Markdown parser from `../../foundations/scripts/roadmap-markdown.mjs`; do not introduce another parser or dependency.

- [ ] **Step 2: Split the approved guide into nine concept modules**

Use `目标` / `核心知识` / `学习记录` / `知识笔记` and, where applicable, `任务` or `时间线` sections. Put the 12-week plan in `study-plan-tools.md`, and the complete glossary and further-reading material in `terms-further-reading.md`. Keep content educational and preserve warnings that examples are not personal investment advice.

- [ ] **Step 3: Build the data and verify it is readable**

Run: `node projects/finance/scripts/build-roadmap-data.mjs && node -e 'JSON.parse(require("node:fs").readFileSync("projects/finance/roadmap/roadmap-data.json", "utf8"))'`

Expected: the build creates a parseable JSON artifact before the contract test validates its contents.

### Task 3: Generalize only the shared reader seams needed by Finance

**Files:**
- Modify: `projects/foundations/roadmap/annotation-model.js`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

**Interfaces:**
- Consumes: `body[data-project-id]` and the loading script’s `data-source` value.
- Produces: project-specific local-storage keys (`${projectId}Reader.annotations.v1`, `${projectId}Reader.tasks.v1`), annotations tagged with the active project, and dashboard options from `data.project`.

- [ ] **Step 1: Make annotation parsing accept the active project**

```js
export function parseStoredAnnotations(raw, projectId = "foundations") {
  // …
  items: parsed.items.filter((item) => item && item.projectId === projectId)
}
```

- [ ] **Step 2: Read the page configuration before reader initialization**

```js
const readerScript = document.querySelector("script[data-source][src$='roadmap-reader.js']");
const PROJECT_ID = document.body.dataset.projectId ?? "foundations";
const ROADMAP_DATA_SOURCE = readerScript?.dataset.source ?? "roadmap/roadmap-data.json";
const ANNOTATION_STORAGE_KEY = `${PROJECT_ID}Reader.annotations.v1`;
```

Use `PROJECT_ID` for annotation IDs, records, parser filtering, diagnostics, and Mermaid diagram IDs. Use `ROADMAP_DATA_SOURCE` in `init()`.

- [ ] **Step 3: Make the Overview dashboard data-driven**

```js
const nextModule = learningModules.find((item) => item.status !== "done") ?? learningModules[0];
const glossaryModule = getModuleById(state.data.project.glossaryModuleId);
```

Retain the existing Foundations overview content. For Finance, consume the explicit project fields `dashboardFocus` (the Week 1 re-entry action) and `glossaryModuleId` (`terms-further-reading`) to render the current-plan label and glossary shortcut. Do not alter the existing reader’s keyboard navigation, search, code listings, or annotation UI contract.

- [ ] **Step 4: Verify the shared reader stays syntactically valid**

Run: `node --check projects/foundations/roadmap/annotation-model.js && node --check projects/foundations/roadmap/roadmap-reader.js && npm run test:foundations`

Expected: all existing Foundations checks pass.

### Task 4: Add the Finance reader page and project discovery

**Files:**
- Create: `projects/finance/index.html`
- Modify: `projects/manifest.json`
- Modify: `tests/projects-requirements.mjs`
- Modify: `assets/fonts/README.md`
- Modify: `assets/fonts/ZhiMangXing-Bookmark.woff2`

**Interfaces:**
- Consumes: shared reader assets in `../foundations/roadmap/` and Finance `roadmap/roadmap-data.json`.
- Produces: `data-page="finance-roadmap-reader"`, `data-project-id="finance"`, a Finance heading/navigation label, and a discoverable `投资` bookmark.

- [ ] **Step 1: Create the static Finance page shell**

```html
<body data-page="finance-roadmap-reader" data-project-id="finance" data-theme="light">
  <!-- same reader shell IDs as Foundations -->
  <script type="module" src="../foundations/roadmap/roadmap-reader.js" data-source="roadmap/roadmap-data.json"></script>
</body>
```

Set the document title to `投资 | NeuroScience x AI`, link the project mark to `../index.html`, and label the sidebar `Finance` / `投资`.

- [ ] **Step 2: Register the manifest entry and test it**

```json
{
  "id": "finance",
  "title": "投资",
  "folder": "finance/",
  "summary": "Concept-centred investment learning with a modular reader, progress dashboard, glossary, and local annotations.",
  "status": "active"
}
```

Add assertions for the Finance page and title sequence in `tests/projects-requirements.mjs`.

- [ ] **Step 3: Regenerate the bookmark font subset**

Run: `curl -L https://github.com/google/fonts/raw/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf -o /tmp/ZhiMangXing-Regular.ttf && pyftsubset /tmp/ZhiMangXing-Regular.ttf --text='记忆与智能体基石语言投资' --flavor=woff2 --output-file=assets/fonts/ZhiMangXing-Bookmark.woff2`

Update the documented generation command and let the existing cmap assertion verify `投` and `资`.

### Task 5: Run the full acceptance suite and inspect the rendered reader

**Files:**
- Verify: `projects/finance/**`, `projects/foundations/roadmap/{annotation-model.js,roadmap-reader.js}`, `projects/manifest.json`, `tests/**`, `assets/fonts/**`

- [ ] **Step 1: Run focused verification**

Run: `npm run test:finance && npm run test:projects && npm run test:foundations && git diff --check`

Expected: each command exits `0`.

- [ ] **Step 2: Serve and inspect the page at desktop and mobile widths**

Run: `python3 -m http.server 4173 --directory .`

Open: `http://localhost:4173/projects/finance/`

Check: Overview opens first; progress is 0%; “投资的本质与前提” is the next module; the glossary shortcut navigates to “术语速查与延伸”; search returns section-level results; theme, side rails, local annotations, and the narrow mobile drawer work.

- [ ] **Step 3: Record exact verification evidence before handoff**

Report only fresh command results, created/modified files, and any intentionally skipped check.
