# SelfMem Reading Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SelfMem: Self-Optimizing Memory for AI Agents` to the `brain-memory-for-ai-agents` paper directory as a complete, bilingual, source-backed deep reading package.

**Architecture:** Reuse the existing static reader contract. Add one manifest item, one local PDF, and a self-contained `readings/yang-2026-selfmem/` package with paper metadata, 22 argument-level chunks, parallel blank notes, deterministic local search vectors, and five real PDF figure crops. No shared reader or backend code changes are planned.

**Tech Stack:** Static JSON, JavaScript contract tests, Node.js package validator, Poppler (`pdftocairo`/`pdftotext`) for source extraction and semantic PDF crops.

## Global Constraints

- Paper id is exactly `yang-2026-selfmem`; manifest id and reading directory must match.
- Source mode is `verbatim`; `sourceText` must come from arXiv PDF `2607.03726v1`.
- Save the PDF as `papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf`.
- Use exactly 22 stable chunk ids, `ch-001` through `ch-022`, each representing a complete argument unit.
- Every chunk has faithful Chinese translation, separate project explanation, one concise premise, one concise claim, and one to three evidence items.
- Deep-reading search fields are exactly `sourceText`, `zhTranslation`, `zhExplanation`, `premise`, `claim`, `evidence`.
- Include at least five real source crops and no full-page screenshots.
- Include the strategy-refinement protocol, final compact-memory policy, key prompts, and memory action space from the appendices.
- `notes.json` starts blank for all 22 chunks.
- Do not add SurrealDB, online embeddings, AI providers, API routes, or reader-specific UI.

---

### Task 1: Lock the SelfMem package contract

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`
- Modify: `tests/paper-import-standard-requirements.mjs`

**Interfaces:**
- Consumes: `papers/manifest.json` and generic reading-package file layout.
- Produces: focused assertions that fail until the SelfMem package is complete.

- [ ] **Step 1: Add the focused manifest and package assertions**

In `tests/paper-reader-requirements.mjs`, add `selfMemPaper` beside `workspacePaper`, then assert:

```js
const selfMemPaper = project.papers.find((paper) => paper.id === "yang-2026-selfmem");

assert.ok(selfMemPaper, "project manifest should register SelfMem");
assert.equal(selfMemPaper.title, "SelfMem: Self-Optimizing Memory for AI Agents", "SelfMem should use the source title");
assert.equal(selfMemPaper.shortTitle, "SelfMem", "SelfMem should use a compact reader title");
assert.equal(selfMemPaper.authors, "Yang et al.", "SelfMem should use compact author metadata");
assert.equal(selfMemPaper.year, 2026, "SelfMem should use the source year");
assert.equal(selfMemPaper.source, "https://arxiv.org/abs/2607.03726", "SelfMem should link to arXiv");
assert.equal(selfMemPaper.localFile, "pdfs/2026-yang-selfmem.pdf", "SelfMem should keep the source PDF locally");
assert.equal(selfMemPaper.hasReading, true, "SelfMem should expose a completed reading package");
```

Inside the per-paper loop, derive deep-reading expectations generically:

```js
const isDeepReading = Array.isArray(paperData.readingGroups);
const expectedIndexedFields = isDeepReading
  ? ["sourceText", "zhTranslation", "zhExplanation", "premise", "claim", "evidence"]
  : ["sourceText", "zhTranslation", "zhExplanation"];
assert.deepEqual(embeddingsData.indexedFields, expectedIndexedFields, `${paperId} embeddings should match its reading depth`);
```

Add SelfMem-specific checks:

```js
if (paperId === "yang-2026-selfmem") {
  assert.equal(paperData.sourceMode, "verbatim", "SelfMem should use verbatim PDF mode");
  assert.equal(paperData.license, "CC BY 4.0", "SelfMem should record its source license");
  assert.equal(paperData.readingGroups.length, 7, "SelfMem should define seven reading groups");
  assert.equal(chunkData.chunks.length, 22, "SelfMem should cover the main paper and implementation appendices in 22 chunks");
  assert.ok(figuresData.figures.filter((figure) => figure.file).length >= 5, "SelfMem should include five real source crops");
  assert.ok(figuresData.figures.every((figure) => figure.publicCropPolicy === "minimal-necessary"), "SelfMem figures should use minimal necessary crops");
}
```

- [ ] **Step 2: Update the package-count contract**

In `tests/paper-import-standard-requirements.mjs`, change the expected validator count from 10 to 11:

```js
assert.match(validatorOutput, /Validated 11 reading packages for brain-memory-for-ai-agents/, "validator should check every current reading package");
```

- [ ] **Step 3: Run tests and confirm the intended failure**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
```

Expected: both fail because `yang-2026-selfmem` is not yet present and the validator still finds 10 packages.

- [ ] **Step 4: Commit the failing contract**

```bash
git add tests/paper-reader-requirements.mjs tests/paper-import-standard-requirements.mjs
git commit -m "test: define SelfMem reading package contract"
```

### Task 2: Acquire the source PDF and create real figure crops

**Files:**
- Create: `papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures.json`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-2-selfmem-overview.png`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/table-1-beam-results.png`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-3-question-types.png`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-4-strategy-optimization.png`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/table-2-method-positioning.png`

**Interfaces:**
- Consumes: arXiv PDF `https://arxiv.org/pdf/2607.03726`.
- Produces: local source file plus figure ids `fig-001` through `fig-005` for `chunks.json`.

- [ ] **Step 1: Download and verify the paper**

```bash
mkdir -p papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures
curl -L --fail https://arxiv.org/pdf/2607.03726 -o papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf
pdfinfo papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf
```

Expected: title `SelfMem: Self-Optimizing Memory for AI Agents`, 16 pages, A4, unencrypted.

- [ ] **Step 2: Render semantic crops from the PDF**

Use `pdftocairo -png -singlefile -r 144` with page-specific crop coordinates. Coordinates are in the 144-DPI rendered page space (`1191 x 1684`) and may be tightened after visual inspection, but must not expand to a full page:

```bash
pdftocairo -png -singlefile -r 144 -f 2 -l 2 -x 135 -y 120 -W 925 -H 690 papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-2-selfmem-overview
pdftocairo -png -singlefile -r 144 -f 7 -l 7 -x 135 -y 120 -W 925 -H 850 papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/table-1-beam-results
pdftocairo -png -singlefile -r 144 -f 8 -l 8 -x 120 -y 100 -W 950 -H 535 papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-3-question-types
pdftocairo -png -singlefile -r 144 -f 8 -l 8 -x 120 -y 610 -W 950 -H 720 papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/figure-4-strategy-optimization
pdftocairo -png -singlefile -r 144 -f 12 -l 12 -x 120 -y 110 -W 950 -H 900 papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/table-2-method-positioning
```

- [ ] **Step 3: Inspect all five crops**

Open each PNG and verify the intended figure/table, caption or necessary legend is present; unrelated body text and page furniture are absent. Re-run only the affected crop command if a label, axis, row, or caption is clipped.

- [ ] **Step 4: Add `figures.json`**

Create five entries with ids and canonical sections:

```json
{
  "paperId": "yang-2026-selfmem",
  "figures": [
    { "id": "fig-001", "label": "Figure 2", "file": "figures/figure-2-selfmem-overview.png", "sourcePage": 2, "sourceFigure": "Figure 2", "cropMode": "semantic-crop", "publicCropPolicy": "minimal-necessary", "sourceUrl": "https://arxiv.org/abs/2607.03726", "sourceAnchor": "Figure 2", "bbox": { "x": 135, "y": 120, "width": 925, "height": 690 }, "canonicalSectionId": "sec-framework", "status": "cropped", "caption": "SelfMem keeps the raw transcript as an immutable source of truth while the agent inspects evidence, manages a memory workspace, reviews quality, and answers with retrieved support." },
    { "id": "fig-002", "label": "Table 1", "file": "figures/table-1-beam-results.png", "sourcePage": 7, "sourceFigure": "Table 1", "cropMode": "semantic-crop", "publicCropPolicy": "minimal-necessary", "sourceUrl": "https://arxiv.org/abs/2607.03726", "sourceAnchor": "Table 1", "bbox": { "x": 135, "y": 120, "width": 925, "height": 850 }, "canonicalSectionId": "sec-results", "status": "cropped", "caption": "Main BEAM results at 100K, 500K, and 1M conversation scales, including score, pass rate, cost, cache use, and request counts." },
    { "id": "fig-003", "label": "Figure 3", "file": "figures/figure-3-question-types.png", "sourcePage": 8, "sourceFigure": "Figure 3", "cropMode": "semantic-crop", "publicCropPolicy": "minimal-necessary", "sourceUrl": "https://arxiv.org/abs/2607.03726", "sourceAnchor": "Figure 3", "bbox": { "x": 120, "y": 100, "width": 950, "height": 535 }, "canonicalSectionId": "sec-results", "status": "cropped", "caption": "BEAM question-type results showing where SelfMem is strong and where its advantage is less consistent across scales." },
    { "id": "fig-004", "label": "Figure 4", "file": "figures/figure-4-strategy-optimization.png", "sourcePage": 8, "sourceFigure": "Figure 4", "cropMode": "semantic-crop", "publicCropPolicy": "minimal-necessary", "sourceUrl": "https://arxiv.org/abs/2607.03726", "sourceAnchor": "Figure 4", "bbox": { "x": 120, "y": 610, "width": 950, "height": 720 }, "canonicalSectionId": "sec-optimization", "status": "cropped", "caption": "Held-out score across optimizer iterations and training-set sizes; the best strategy appears at an intermediate point rather than the maximum search budget." },
    { "id": "fig-005", "label": "Table 2", "file": "figures/table-2-method-positioning.png", "sourcePage": 12, "sourceFigure": "Table 2", "cropMode": "semantic-crop", "publicCropPolicy": "minimal-necessary", "sourceUrl": "https://arxiv.org/abs/2607.03726", "sourceAnchor": "Table 2", "bbox": { "x": 120, "y": 110, "width": 950, "height": 900 }, "canonicalSectionId": "sec-positioning", "status": "cropped", "caption": "Author-side positioning of SelfMem against retrieval, compression, hierarchical memory, structured notes, and production memory systems." }
  ]
}
```

- [ ] **Step 5: Commit source assets**

```bash
git add papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures.json papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures
git commit -m "assets: add SelfMem paper and evidence figures"
```

### Task 3: Build the bilingual deep reading data

**Files:**
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/paper.json`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/chunks.json`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/notes.json`
- Create: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/embeddings.json`

**Interfaces:**
- Consumes: source PDF and figure ids `fig-001` through `fig-005`.
- Produces: the complete reading package consumed by `papers/shared/reader.js` and `scripts/validate-reading-packages.mjs`.

- [ ] **Step 1: Create `paper.json` with seven sections and seven reading groups**

Use these section ids:

```text
sec-introduction
sec-positioning
sec-framework
sec-memory-loop
sec-experiments
sec-results
sec-optimization
sec-implementation
sec-limitations
```

Use the seven group ids from the design: `group-problem`, `group-positioning`, `group-framework`, `group-loop`, `group-evaluation`, `group-optimization`, `group-implementation-limits`. Include five premises, seven narrative-spine entries bound one-to-one to groups, and four group-bound misreadings. Set `sourceFile` to `../../pdfs/2026-yang-selfmem.pdf`.

- [ ] **Step 2: Create 22 source-grounded chunks**

Use this stable id/title/section/group map:

```text
ch-001 固定记忆策略的问题           sec-introduction  group-problem
ch-002 从给鱼到教会捕鱼             sec-introduction  group-problem
ch-003 相关记忆系统的边界           sec-positioning   group-positioning
ch-004 自改进智能体的启发           sec-positioning   group-positioning
ch-005 SelfMem 的问题定义            sec-framework     group-framework
ch-006 transcript 是事实来源         sec-framework     group-framework
ch-007 memory workspace 与动作空间   sec-framework     group-framework
ch-008 多通道反馈而非单一奖励         sec-framework     group-framework
ch-009 构建与审查闭环                sec-memory-loop   group-loop
ch-010 记忆条件化回答                sec-memory-loop   group-loop
ch-011 BEAM 评估协议                 sec-experiments   group-evaluation
ch-012 baseline 与模型配置           sec-experiments   group-evaluation
ch-013 指标与成本口径                sec-experiments   group-evaluation
ch-014 三个规模上的主结果            sec-results       group-evaluation
ch-015 成本和请求数量                sec-results       group-evaluation
ch-016 不同问题类型的表现            sec-results       group-evaluation
ch-017 策略搜索的隔离规则            sec-optimization  group-optimization
ch-018 迭代次数不是越多越好          sec-optimization  group-optimization
ch-019 最终紧凑记忆策略              sec-implementation group-implementation-limits
ch-020 构建与回答 Prompt             sec-implementation group-implementation-limits
ch-021 repair、refinement 与工具表   sec-implementation group-implementation-limits
ch-022 局限与项目迁移                sec-limitations   group-implementation-limits
```

Add math blocks to `ch-005`, `ch-007`, `ch-008`, `ch-009`, and `ch-010`; table blocks to `ch-003`, `ch-013`, `ch-014`, and `ch-021`; code blocks to `ch-020` and `ch-021`. Link figures as follows:

```text
ch-003 -> fig-005 supporting
ch-007 -> fig-001 supporting
ch-014 -> fig-002 supporting
ch-016 -> fig-003 supporting
ch-018 -> fig-004 supporting
```

- [ ] **Step 3: Create blank parallel notes**

Create `notes.json` with `paperId: "yang-2026-selfmem"` and exactly 22 `{ "chunkId": "ch-NNN", "note": "" }` rows. Do not set `noteMode`.

- [ ] **Step 4: Create deterministic local search vectors**

Create `embeddings.json` with model `static-domain-keyword-v1`, the six deep-reading `indexedFields`, the existing 12 domain dimensions, and exactly one finite 12-number vector per chunk. Vectors should emphasize the relevant dimensions without claiming to be model-generated semantic embeddings.

- [ ] **Step 5: Run package validation without manifest registration**

Run direct JSON syntax checks:

```bash
node -e 'for (const f of process.argv.slice(1)) JSON.parse(require("node:fs").readFileSync(f, "utf8"))' papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/*.json
```

Expected: exit 0. The project validator still reports 10 packages because SelfMem is not registered yet.

- [ ] **Step 6: Commit reading data**

```bash
git add papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/paper.json papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/chunks.json papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/notes.json papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/embeddings.json
git commit -m "feat: add SelfMem deep reading data"
```

### Task 4: Register SelfMem and close the validation loop

**Files:**
- Modify: `papers/manifest.json`

**Interfaces:**
- Consumes: completed `yang-2026-selfmem` package.
- Produces: a visible directory item and reader route through the existing manifest-driven UI.

- [ ] **Step 1: Add the manifest item**

Insert after the existing LLM Agent Memory Survey entry:

```json
{
  "id": "yang-2026-selfmem",
  "title": "SelfMem: Self-Optimizing Memory for AI Agents",
  "shortTitle": "SelfMem",
  "hasReading": true,
  "authors": "Yang et al.",
  "year": 2026,
  "source": "https://arxiv.org/abs/2607.03726",
  "localFile": "pdfs/2026-yang-selfmem.pdf",
  "noteFile": "readings/yang-2026-selfmem/notes.json"
}
```

- [ ] **Step 2: Run focused validators**

```bash
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
```

Expected: validator reports `Validated 11 reading packages for brain-memory-for-ai-agents: 0 errors`; both tests pass.

- [ ] **Step 3: Run regression checks**

```bash
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit 0 with no whitespace errors.

- [ ] **Step 4: Verify the actual reader**

Serve the repository with the existing local server and open:

```text
http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/?paper=yang-2026-selfmem
```

At desktop and mobile widths, verify all 22 chunks render, the five crops are legible, math/code/table blocks do not overflow, search finds `immutable source of truth`, `strategy refinement`, and `leakage`, and the right note rail remains blank but continuous.

- [ ] **Step 5: Commit registration**

```bash
git add papers/manifest.json
git commit -m "feat: register SelfMem in memory papers"
```

### Task 5: Final content and evidence review

**Files:**
- Review only: all files created or modified in Tasks 1-4.

**Interfaces:**
- Consumes: complete package and passing tests.
- Produces: verified implementation ready for the user's next publish instruction.

- [ ] **Step 1: Check coverage against the PDF**

Confirm the reader covers Sections 1-6 and Appendices A-C, including the strategy loop, prompt constraints and tool table. Confirm references and the author disclosure appendix are not promoted into substantive chunks.

- [ ] **Step 2: Check claim strength**

Confirm `zhExplanation` labels the 100K strategy-refinement result as preliminary, keeps BEAM claims within the shared harness, and does not equate natural-language memory policy optimization with biological plasticity or parameter learning.

- [ ] **Step 3: Re-run the complete verification stack**

```bash
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
git status --short --branch
```

Expected: all tests pass, the validator reports 11 packages, and only intentional commits plus the analysis-only `tmp/` directory remain.
