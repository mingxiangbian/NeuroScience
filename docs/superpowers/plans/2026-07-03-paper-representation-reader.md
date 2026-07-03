# Paper Representation Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn `papers/brain-memory-for-ai-agents/` into a spec-compliant Paper Representation reader with chunk reading, offline semantic search, parallel notes, and reusable project-level standards.

**Architecture:** Keep `papers/` as the 文献阁 directory and implement the reader at `papers/brain-memory-for-ai-agents/index.html`. Put reusable reader styling and behavior in `papers/shared/reader.css` and `papers/shared/reader.js`, and put per-paper data in `papers/brain-memory-for-ai-agents/readings/<paper-id>/`. Use static JSON and local vector math, not a backend or AI answer service.

**Tech Stack:** Static HTML/CSS/JavaScript, JSON reading packages, Node-based requirement tests, GitHub Pages-compatible assets.

---

### Task 1: Requirement Tests

**Files:**
- Modify: `tests/papers-requirements.mjs`
- Create: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Extend homepage manifest assertions**

Add checks that project papers include `shortTitle`, and that existing 文献阁 homepage constraints still hold.

- [x] **Step 2: Add reader requirement tests**

Create `tests/paper-reader-requirements.mjs` with checks for:

- `papers/brain-memory-for-ai-agents/index.html` is a project reader, not a paper list.
- No `/papers/reader/` route exists.
- The project mark links to `../`.
- Shared reader CSS and JS exist.
- Toolbar, paper directory, center chunk reader, right note panel, global search, night mode, and collapse controls exist.
- CSS supports water-ink paper styling, glass toolbar/sidebar/note panel, mobile center-only layout, pressed selected paper rows, section-line collapsed index, chunk cards, blank note surface, math/code/table/figure rendering, and night mode.
- JS loads `../manifest.json`, `readings/<paper-id>/paper.json`, `chunks.json`, `notes.json`, `embeddings.json`, and optional `figures.json`.
- JS implements local vector search over `sourceText + zhExplanation`, returns ranked chunks, shows `no found`, and does not use `/api/`, localhost, OpenAI, Anthropic, or AI answer generation.
- First content batch has data packages for Zhang 2024, McClelland 1995, and Yassa & Stark 2011.

- [x] **Step 3: Run the new reader test and confirm it fails before implementation**

Run: `node tests/paper-reader-requirements.mjs`

Expected: FAIL because shared reader files and reading packages do not exist yet.

### Task 2: Reading Data Packages

**Files:**
- Modify: `papers/manifest.json`
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/paper.json`
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/chunks.json`
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/notes.json`
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/figures.json`
- Create: `papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/embeddings.json`
- Create equivalent files for `mcclelland-1995-complementary-learning-systems`
- Create equivalent files for `yassa-stark-2011-pattern-separation`

- [x] **Step 1: Add `shortTitle` to every manifest paper**

Use short, one-line titles for the left directory. Keep full `title`, source links, and existing local files.

- [x] **Step 2: Create three reading packages**

Each package includes:

- `paper.json` with metadata, sections, category, relation, description, source file, and note file.
- `chunks.json` with 4-5 high-quality chunks, `sourceText`, optional `blocks`, `zhExplanation`, `figureRefs`, and keywords.
- `notes.json` with matching `chunkId` entries. Some notes intentionally remain blank to verify continuous blank note behavior.
- `figures.json` with at least one referenced figure metadata item. It can point to a future figure path but must be structurally valid.
- `embeddings.json` with deterministic static vectors generated from `sourceText + zhExplanation` using the local helper added in Task 3.

- [x] **Step 3: Validate data schema**

Run: `node tests/paper-reader-requirements.mjs`

Expected: still FAIL until reader files are implemented, but data package checks should pass.

### Task 3: Shared Reader CSS And JavaScript

**Files:**
- Create: `papers/shared/reader.css`
- Create: `papers/shared/reader.js`

- [x] **Step 1: Implement reusable reader styling**

`reader.css` must define:

- 宣纸/grid background and ink wash.
- Glass toolbar, sidebar, note panel, and global search focus state.
- Desktop four-area reader layout.
- Mobile layout that defaults to center reader only.
- Pressed selected paper row.
- Collapsed section-line index and hover wave.
- English chunk card and Chinese explanation outside the card.
- Math, code, table, figure, and fallback rendering styles.
- Right blank continuous note surface.
- Night mode via `data-theme="dark"`.

- [x] **Step 2: Implement reusable reader behavior**

`reader.js` must:

- Load the current project from `../manifest.json`.
- Render all manifest papers by `shortTitle`.
- Open `?paper=<id>` when present, otherwise the first paper with a reading package.
- Load `paper.json`, `chunks.json`, `notes.json`, `embeddings.json`, and optional `figures.json`.
- Render metadata, section index, chunks, rich blocks, figures, and blank-safe notes.
- Render no-chunk papers as metadata plus original/source/note links only.
- Use IntersectionObserver to keep the right note panel aligned to the current chunk.
- Toggle left directory, right note panel, global search focus, and night mode.
- Run local vector search over the static embeddings and display line-separated results.
- Avoid backend, localhost, provider key, and AI answer-generation dependencies.

- [x] **Step 3: Verify reader tests**

Run: `node tests/paper-reader-requirements.mjs`

Expected: PASS after Task 4 connects the page.

### Task 4: Project Reader Page

**Files:**
- Replace: `papers/brain-memory-for-ai-agents/index.html`

- [x] **Step 1: Replace the paper-list page with a reader shell**

The shell must include:

- `data-page="paper-project-reader"`
- Top toolbar
- Project logo link to `../`
- Left collapse button
- Center global search
- Night mode button
- Right note panel toggle
- Left paper directory
- Collapsed section index
- Center paper header and chunk stream
- Right continuous note panel
- Mobile note drawer
- Links to `../shared/reader.css` and `../shared/reader.js`

- [x] **Step 2: Verify reader loads under a static server**

Run a local static server and request:

- `http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/`
- `http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/readings/zhang-2024-memory-mechanism-llm-agents/chunks.json`

Expected: both return 200.

### Task 5: Final Verification And Completion Audit

**Files:**
- Modify as needed: requirement tests only if they reveal an actual spec gap.

- [x] **Step 1: Run project tests**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all pass.

- [x] **Step 2: Audit against the spec**

Read `docs/superpowers/specs/2026-07-03-paper-representation-design.md` and verify every requirement has current evidence in files or command output.

- [x] **Step 3: Inspect dirty worktree**

Run: `git status --short --branch`

Expected: changed files are relevant to paper downloads, manifest, reader implementation, tests, and plans/specs. Unrelated `projects/uestc-fyp-topics-2026-2027/` remains unstaged and untouched.

- [x] **Step 4: Commit implementation**

Stage relevant paper reader files, data packages, tests, and plan/spec files. Do not stage `projects/uestc-fyp-topics-2026-2027/`.

Commit message:

```text
Add paper representation reader
```

