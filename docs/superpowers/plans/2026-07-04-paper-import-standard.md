# Paper Import Standard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `papers/` 下所有子项目阅读器建立统一的 paper 导入标准，避免后续 chunk、翻译、图表、笔记和 embedding 字段各写各的。

**Architecture:** 新增一个全局标准文档 `papers/PAPER_IMPORT_STANDARD.md`，作为所有 `papers/<project-id>/readings/<paper-id>/` reading package 的契约。新增测试 `tests/paper-import-standard-requirements.mjs`，只锁住标准必须覆盖的字段、质量边界和静态页面限制，不改变现有 reader runtime。

**Tech Stack:** Markdown 文档、Node.js 断言测试、现有静态 JSON reading package。

---

### Task 1: 标准测试

**Files:**
- Create: `tests/paper-import-standard-requirements.mjs`
- Read: `papers/PAPER_IMPORT_STANDARD.md`

- [ ] **Step 1: Write the failing test**

```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const standardUrl = new URL("../papers/PAPER_IMPORT_STANDARD.md", import.meta.url);

assert.equal(existsSync(standardUrl), true, "paper import standard should exist at papers/PAPER_IMPORT_STANDARD.md");

const standard = readFileSync(standardUrl, "utf8");

assert.match(standard, /^# Paper Import Standard/m, "standard should have a stable title");
assert.match(standard, /papers\/<project-id>\/readings\/<paper-id>\//, "standard should define the reading package path");
assert.match(standard, /paper\.json[\s\S]*chunks\.json[\s\S]*notes\.json[\s\S]*embeddings\.json[\s\S]*figures\.json/, "standard should list all required reading package files");
assert.match(standard, /sourceText[\s\S]*论文原文/, "standard should define sourceText as paper source text, not a summary");
assert.match(standard, /zhTranslation[\s\S]*忠实翻译/, "standard should define zhTranslation as faithful translation");
assert.match(standard, /zhExplanation[\s\S]*解释/, "standard should separate explanation from translation");
assert.match(standard, /blocks[\s\S]*paragraph[\s\S]*math[\s\S]*code[\s\S]*table[\s\S]*figure/, "standard should define supported block types");
assert.match(standard, /figureRefs[\s\S]*near[\s\S]*supporting[\s\S]*deferred/, "standard should define cross-page figure references");
assert.match(standard, /notes\.json[\s\S]*空字符串/, "standard should allow empty notes without visible placeholder text");
assert.match(standard, /indexedFields[\s\S]*sourceText[\s\S]*zhTranslation[\s\S]*zhExplanation/, "standard should define searchable fields");
assert.match(standard, /不引入[\s\S]*\/api\/[\s\S]*provider key[\s\S]*SurrealDB/, "standard should keep the reader static and backend-free");
assert.match(standard, /Import Checklist/, "standard should include an import checklist for future agents");
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node tests/paper-import-standard-requirements.mjs`

Expected: FAIL because `papers/PAPER_IMPORT_STANDARD.md` does not exist yet.

### Task 2: 标准文档

**Files:**
- Create: `papers/PAPER_IMPORT_STANDARD.md`

- [ ] **Step 1: Write the standard**

Create `papers/PAPER_IMPORT_STANDARD.md` with:

```md
# Paper Import Standard

...
```

The document must define:
- global scope for every `papers/<project-id>/` reader page
- required reading package files
- `paper.json` metadata contract
- `chunks.json` chunk contract
- block types for paragraph, LaTeX math, code, table, and figure
- cross-page figure references
- parallel note rules
- static embedding index rules
- import checklist

- [ ] **Step 2: Run the standard test**

Run: `node tests/paper-import-standard-requirements.mjs`

Expected: PASS.

### Task 3: Regression Verification

**Files:**
- Verify: `tests/paper-reader-requirements.mjs`
- Verify: `tests/homepage-requirements.mjs`
- Verify: `tests/paper-import-standard-requirements.mjs`

- [ ] **Step 1: Run all relevant checks**

Run:

```bash
node tests/paper-import-standard-requirements.mjs
node tests/paper-reader-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-07-04-paper-import-standard.md papers/PAPER_IMPORT_STANDARD.md tests/paper-import-standard-requirements.mjs
git commit -m "Add paper import standard"
```

Expected: one new commit on the current `codex/zhang-2024-complete-reader-sample` branch.
