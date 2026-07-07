# Global Workspace Deep Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把 `gurnee-2026-global-workspace-language-models` 升级成带前提、叙事主线、论点证据和本地裁剪图的 deep reading package，并把规则沉淀进通用导入标准和验证。

**Architecture:** 继续使用现有静态 Paper Representation reader。`paper.json` 承载 paper 级 `readingGroups / premises / narrativeSpine / misreadings`，`chunks.json` 承载 chunk 级 `groupId / premise / claim / evidence`，`figures.json` 承载本地裁剪图和来源元数据。`papers/shared/reader.js` 只做轻量渲染，不新增后端、数据库或 AI provider。

**Tech Stack:** 静态 HTML/CSS/vanilla JS、Node.js test scripts、JSON reading package、GitHub Pages。

---

## File Map

- Modify: `papers/PAPER_IMPORT_STANDARD.md`
  - 增加 `Deep Reading Package Standard`。
  - 写死字段长度、去重、group 绑定和公开页面最小必要裁剪准则。
- Modify: `tests/paper-import-standard-requirements.mjs`
  - 断言标准包含 deep reading 规则。
- Modify: `scripts/validate-reading-packages.mjs`
  - 验证 deep reading package 的 paper/chunk/figure 字段。
- Modify: `tests/paper-reader-requirements.mjs`
  - 断言 reader 渲染 deep reading 字段，Gurnee package 保留 22 个 chunk 并有本地裁剪图。
- Modify: `papers/shared/reader.js`
  - 渲染 paper 级 deep reading intro 和 chunk 级 premise/claim/evidence。
  - 把新增字段纳入本地搜索文本。
- Modify: `papers/shared/reader.css`
  - 为 deep reading intro、group divider、claim/evidence 轻量结构增加样式。
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/paper.json`
  - 增加 reading groups、premises、narrative spine、misreadings。
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/chunks.json`
  - 保留所有 22 个 `ch-xxx`，增加 `groupId / premise / claim / evidence`。
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/embeddings.json`
  - `indexedFields` 增加 `premise / claim / evidence`。
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures.json`
  - 关键图改为本地 `web-screenshot-crop`，保留来源元数据。
- Create: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures/*.png`
  - 至少 5 张本地裁剪图，覆盖 overview、method、workspace evidence、structure、auditing/training。

---

### Task 1: Deep Reading Standard And Validator

**Files:**
- Modify: `tests/paper-import-standard-requirements.mjs`
- Modify: `papers/PAPER_IMPORT_STANDARD.md`
- Modify: `scripts/validate-reading-packages.mjs`

- [x] **Step 1: Write failing standard assertions**

Add assertions equivalent to:

```js
assert.match(standard, /Deep Reading Package Standard/, "standard should define deep reading packages");
assert.match(standard, /readingGroups[\s\S]*premises[\s\S]*narrativeSpine[\s\S]*misreadings/, "standard should define paper-level deep reading fields");
assert.match(standard, /narrativeSpine[\s\S]*groupId[\s\S]*readingGroups/, "narrative spine should bind to reading groups");
assert.match(standard, /premise[\s\S]*claim[\s\S]*evidence/, "standard should define chunk-level deep reading fields");
assert.match(standard, /claim[\s\S]*zhExplanation[\s\S]*不能语义重复/, "standard should require claim and explanation de-duplication");
assert.match(standard, /最小必要裁剪[\s\S]*GitHub Pages/, "standard should define public-page screenshot crop boundaries");
```

- [x] **Step 2: Run the failing test**

Run:

```bash
node tests/paper-import-standard-requirements.mjs
```

Expected: FAIL because `PAPER_IMPORT_STANDARD.md` does not yet define the deep reading standard.

- [x] **Step 3: Update `PAPER_IMPORT_STANDARD.md`**

Add a `Deep Reading Package Standard` section that requires:

```text
readingGroups / premises / narrativeSpine / misreadings
premise / claim / evidence
narrativeSpine.groupId -> readingGroups[].id
premise and claim: one sentence each
evidence: at most 3 short items
claim and zhExplanation must not repeat the same job
public GitHub Pages screenshots follow minimal necessary crop
```

- [x] **Step 4: Add validator checks**

In `scripts/validate-reading-packages.mjs`, add helpers:

```js
function isDeepReadingPaper(paperData) {
  return Array.isArray(paperData?.readingGroups) || Array.isArray(paperData?.narrativeSpine);
}
```

Validate deep papers only, so older packages remain valid:

Validate these concrete rules for deep papers:

```text
readingGroups is an array with at least 3 unique ids
narrativeSpine is an array and every item.groupId exists in readingGroups
misreadings is an array and every item.groupId, when present, exists in readingGroups
every chunk.groupId exists in readingGroups
every chunk.premise and chunk.claim is a non-empty single sentence
every chunk.evidence is an array with 1 to 3 non-empty strings
embeddings.indexedFields includes premise, claim, and evidence
figures include at least 5 local files with publicCropPolicy: minimal-necessary
```

- [x] **Step 5: Run standard test again**

Run:

```bash
node tests/paper-import-standard-requirements.mjs
```

Expected: PASS.

---

### Task 2: Reader Rendering Contracts

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`
- Modify: `papers/shared/reader.js`
- Modify: `papers/shared/reader.css`

- [x] **Step 1: Write failing reader assertions**

Add assertions equivalent to:

```js
assert.match(js, /function renderDeepReadingIntro/, "reader should render paper-level deep reading intro");
assert.match(js, /function renderChunkDeepReading/, "reader should render chunk-level premise, claim, and evidence");
assert.match(js, /readingGroups/, "reader should consume reading groups from paper.json");
assert.match(js, /chunk\.premise/, "reader should render chunk premise");
assert.match(js, /chunk\.claim/, "reader should render chunk claim");
assert.match(js, /chunk\.evidence/, "reader should render chunk evidence");
assert.match(css, /\.deep-reading-intro/, "reader CSS should style deep reading intro");
assert.match(css, /\.chunk-evidence/, "reader CSS should style chunk evidence");
```

- [x] **Step 2: Run failing reader test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because reader does not render deep reading fields yet.

- [x] **Step 3: Implement reader rendering**

Add functions in `papers/shared/reader.js`:

```js
function renderDeepReadingIntro(paperData) {
  return [renderPremises(paperData), renderNarrativeSpine(paperData), renderMisreadings(paperData)].filter(Boolean).join("");
}

function renderChunkDeepReading(chunk, reading) {
  return [renderChunkGroup(chunk, reading), renderChunkPremise(chunk), renderChunkClaimEvidence(chunk)].filter(Boolean).join("");
}
```

Wire them into `renderPaperHeader()` and `renderChunk()`. Extend search text and lexical fields with:

```js
chunk.premise
chunk.claim
(chunk.evidence ?? []).join("\n")
```

- [x] **Step 4: Add CSS**

Add lightweight styles:

```css
.deep-reading-intro {}
.reading-spine {}
.chunk-deep-reading {}
.chunk-premise {}
.chunk-claim {}
.chunk-evidence {}
```

- [x] **Step 5: Run reader test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: reader structure assertions pass, Gurnee data assertions may still fail until Task 3.

---

### Task 3: Gurnee Deep Reading Data

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/paper.json`
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/chunks.json`
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/embeddings.json`
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Write failing Gurnee data assertions**

Assert:

```js
assert.ok(Array.isArray(paperData.readingGroups) && paperData.readingGroups.length === 7);
assert.ok(Array.isArray(paperData.premises) && paperData.premises.length >= 3);
assert.ok(Array.isArray(paperData.narrativeSpine) && paperData.narrativeSpine.every((item) => groupIds.has(item.groupId)));
assert.ok(Array.isArray(paperData.misreadings) && paperData.misreadings.some((item) => item.groupId === "group-workspace-evidence"));
assert.equal(chunkData.chunks.length, 22);
assert.ok(chunkData.chunks.every((chunk) => groupIds.has(chunk.groupId)));
assert.ok(chunkData.chunks.every((chunk) => typeof chunk.premise === "string" && typeof chunk.claim === "string" && Array.isArray(chunk.evidence)));
assert.deepEqual(embeddingsData.indexedFields, ["sourceText", "zhTranslation", "zhExplanation", "premise", "claim", "evidence"]);
```

- [x] **Step 2: Run failing Gurnee data test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because Gurnee data does not yet have deep reading fields.

- [x] **Step 3: Update `paper.json`**

Add 7 `readingGroups`, 3 to 6 `premises`, group-bound `narrativeSpine`, and group-bound `misreadings`.

- [x] **Step 4: Update `chunks.json`**

Keep all 22 existing chunk ids. Add `groupId`, one-sentence `premise`, one-sentence `claim`, and up to 3-item `evidence` to every chunk.

- [x] **Step 5: Update `embeddings.json`**

Update:

```json
"indexedFields": ["sourceText", "zhTranslation", "zhExplanation", "premise", "claim", "evidence"]
```

Do not change vector count or note count.

- [x] **Step 6: Run Gurnee data tests**

Run:

```bash
node tests/paper-reader-requirements.mjs
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
```

Expected: data assertions pass except local figure assertions that depend on Task 4.

---

### Task 4: Local Figure Crops

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures.json`
- Create: `papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures/*.png`

- [x] **Step 1: Write failing figure assertions**

Assert:

```js
const gurneeLocalFigures = figuresData.figures.filter((figure) => figure.file);
assert.ok(gurneeLocalFigures.length >= 5, "Gurnee 2026 should include key local cropped screenshots");
assert.ok(gurneeLocalFigures.every((figure) => figure.cropMode === "web-screenshot-crop"));
assert.ok(gurneeLocalFigures.every((figure) => figure.sourceUrl && figure.sourceAnchor && figure.bbox && figure.publicCropPolicy === "minimal-necessary"));
```

- [x] **Step 2: Run failing figure test**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because figures are source-linked only.

- [x] **Step 3: Capture selective source screenshots**

Use browser automation or source assets to produce at least these files:

```text
figures/fig-workspace-overview.png
figures/fig-jlens-method.png
figures/fig-jspace-method.png
figures/fig-workspace-evidence.png
figures/fig-structure-broadcast.png
figures/fig-auditing-reflection.png
```

Each image must crop only the relevant figure or evidence region, not a full page.

- [x] **Step 4: Update `figures.json`**

For each local crop, add:

```json
{
  "file": "figures/fig-workspace-overview.png",
  "cropMode": "web-screenshot-crop",
  "status": "cropped",
  "publicCropPolicy": "minimal-necessary",
  "bbox": {
    "description": "cropped to source figure region and nearest caption only"
  }
}
```

- [x] **Step 5: Run figure tests**

Run:

```bash
node tests/paper-reader-requirements.mjs
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
```

Expected: PASS.

---

### Task 5: Final Verification And Commit

**Files:**
- All modified files from Tasks 1-4.

- [x] **Step 1: Run full verification**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all pass.

- [x] **Step 2: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
```

Expected: only paper deep-reading, standard, tests, reader, figure assets, and plan/spec files are changed.

- [x] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-07-07-global-workspace-deep-reading-implementation.md \
  docs/superpowers/specs/2026-07-07-global-workspace-deep-reading-design.md \
  papers/PAPER_IMPORT_STANDARD.md \
  scripts/validate-reading-packages.mjs \
  tests/paper-import-standard-requirements.mjs \
  tests/paper-reader-requirements.mjs \
  papers/shared/reader.js \
  papers/shared/reader.css \
  papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/paper.json \
  papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/chunks.json \
  papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/embeddings.json \
  papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures.json \
  papers/brain-memory-for-ai-agents/readings/gurnee-2026-global-workspace-language-models/figures
git commit -m "Implement global workspace deep reading package"
```

Expected: commit succeeds.
