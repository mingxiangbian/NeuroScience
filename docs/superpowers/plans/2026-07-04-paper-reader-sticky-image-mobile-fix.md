# Paper Reader Sticky Image Mobile Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reader's visible regressions: desktop paper directory remains sticky, local figures resolve from each reading package, and mobile has a visible directory opener.

**Architecture:** Keep the static GitHub Pages reader architecture. Add assertions to the existing reader requirement test, then make minimal HTML/CSS/JS changes without touching section rail hover-wave logic or adding backend dependencies.

**Tech Stack:** Static HTML, shared CSS, browser JavaScript, Node assertion tests.

---

### Task 1: Reader Requirements

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [ ] **Step 1: Write failing assertions**

Add checks that:
- `.reader-shell` aligns grid items to the start so sticky side panels are not stretched.
- the toolbar contains a mobile-only `data-toggle-left` control without adding another `id="toggle-left"`.
- mobile CSS shows `.mobile-directory-toggle`.
- figure rendering resolves paths through the current reading package.

- [ ] **Step 2: Run reader test to verify failure**

Run: `node tests/paper-reader-requirements.mjs`
Expected: fail before implementation because these requirements are not present.

### Task 2: Minimal Reader Fix

**Files:**
- Modify: `papers/brain-memory-for-ai-agents/index.html`
- Modify: `papers/shared/reader.css`
- Modify: `papers/shared/reader.js`

- [ ] **Step 1: Add mobile directory control**

Add one toolbar button with `class="icon-button mobile-directory-toggle"` and `data-toggle-left`. Do not add a second `id="toggle-left"`.

- [ ] **Step 2: Stabilize sticky layout**

Add `align-items: start` to `.reader-shell`; keep `.reader-sidebar` as sticky and keep `.section-rail` hover rules unchanged.

- [ ] **Step 3: Resolve figure asset paths**

Store `assetBasePath: readings/${paper.id}/` in each loaded reading package and render figure `src` with that base path unless the figure path is already absolute.

### Task 3: Verification

**Files:**
- Test: `tests/paper-reader-requirements.mjs`
- Test: `tests/homepage-requirements.mjs`

- [ ] **Step 1: Run verification**

Run:
```bash
node tests/paper-reader-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all pass.
