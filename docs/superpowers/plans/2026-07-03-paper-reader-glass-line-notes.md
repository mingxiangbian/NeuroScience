# Paper Reader Glass Line Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 paper reader 的玻璃层改为冷白青灰质感，并把右侧平行笔记从卡片容器改成线性文档边栏。

**Architecture:** 只修改静态 reader 的共享 CSS 和需求测试。`papers/shared/reader.css` 负责视觉实现，`tests/paper-reader-requirements.mjs` 负责锁定冷色玻璃、右侧线性边栏、移动端隐藏和无后端依赖。

**Tech Stack:** Static HTML/CSS/JS, Node.js assertion tests, GitHub Pages static runtime.

---

## File Structure

- Modify: `tests/paper-reader-requirements.mjs`
  - 增加需求断言：冷白青灰玻璃变量、玻璃层高光/暗边、右侧 `.note-panel` 线性边栏、`.note-surface` 去卡片边框、笔记分隔线、移动端保持隐藏。
- Modify: `papers/shared/reader.css`
  - 调整 `--reader-glass*`、`--reader-shadow`、玻璃面板阴影。
  - 拆分 `.directory-surface`、`.note-panel`、`.section-rail` 共享卡片规则，避免右侧笔记继承完整卡片边框。
  - 把 `.note-panel` 改为透明/极弱底色 + 左竖线 + 横线分隔。
  - 保留移动端 `.note-panel` 默认隐藏、`.mobile-note-drawer` 玻璃样式。

## Task 1: Lock Visual Requirements In Tests

**Files:**
- Modify: `tests/paper-reader-requirements.mjs`

- [x] **Step 1: Add failing visual assertions**

Add assertions after the existing glass token checks:

```js
assert.match(css, /--reader-glass:\s*rgba\(238,\s*247,\s*242,\s*0\.42\)/, "reader glass should use a cool white-green translucent base in light mode");
assert.match(css, /--reader-glass-strong:\s*rgba\(244,\s*249,\s*245,\s*0\.56\)/, "strong reader glass should stay cool and translucent");
assert.match(css, /--reader-glass-low:\s*rgba\(244,\s*249,\s*245,\s*0\.2\)/, "reader CSS should define a low-opacity glass wash for linear notes");
assert.match(css, /--reader-glass-shadow:\s*rgba\(19,\s*45,\s*42,\s*0\.16\)/, "glass shadow should use a cool ink wash instead of warm card shadow");
```

Add assertions near the `.note-panel` checks:

```js
assert.match(css, /\.directory-surface,\s*\.section-rail\s*\{[\s\S]*border:\s*1px solid var\(--reader-glass-edge\)/, "directory and section rail should keep glass panel borders");
assert.match(css, /\.note-panel\s*\{[\s\S]*border-left:\s*1px solid var\(--reader-note-rule\)/, "note panel should use a left rule instead of a full card border");
assert.doesNotMatch(css, /\.note-panel\s*\{[\s\S]*border:\s*1px solid var\(--reader-glass-edge\)/, "note panel should not render as a full glass card");
assert.match(css, /\.note-surface\s*\{[\s\S]*border:\s*0/, "note surface should not be an inner card");
assert.match(css, /\.note-surface\s*\{[\s\S]*background:\s*transparent/, "note surface should stay visually continuous");
assert.match(css, /\.note-surface p \+ p\s*\{[\s\S]*border-top:\s*1px solid var\(--reader-note-rule\)/, "parallel notes should be separated by quiet horizontal rules");
assert.match(css, /@media \(max-width:\s*860px\)[\s\S]*\.note-panel[\s\S]*display:\s*none/, "mobile layout should keep the desktop note line hidden by default");
```

- [x] **Step 2: Run the requirement test and verify RED**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: FAIL because the CSS still uses warm glass variables and `.note-panel` still inherits full glass card styling.

## Task 2: Implement Cool Glass And Linear Notes

**Files:**
- Modify: `papers/shared/reader.css`

- [x] **Step 1: Update glass design tokens**

Change the light root tokens to:

```css
--reader-glass: rgba(238, 247, 242, 0.42);
--reader-glass-strong: rgba(244, 249, 245, 0.56);
--reader-glass-low: rgba(244, 249, 245, 0.2);
--reader-glass-highlight: rgba(255, 255, 255, 0.82);
--reader-glass-edge: rgba(226, 239, 235, 0.72);
--reader-glass-shadow: rgba(19, 45, 42, 0.16);
--reader-note-rule: rgba(24, 60, 73, 0.18);
--reader-panel-blur: blur(34px) saturate(1.3);
--reader-shadow: rgba(30, 42, 38, 0.13);
```

Add dark-mode equivalents:

```css
--reader-glass-low: rgba(28, 38, 36, 0.2);
--reader-glass-shadow: rgba(0, 0, 0, 0.36);
--reader-note-rule: rgba(156, 201, 207, 0.2);
```

- [x] **Step 2: Keep glass cards only on toolbar, directory, section rail, and mobile drawer**

Change the shared block from:

```css
.directory-surface,
.note-panel,
.section-rail {
```

to:

```css
.directory-surface,
.section-rail {
```

Use a cooler shadow stack:

```css
box-shadow:
  inset 0 1px 0 var(--reader-glass-highlight),
  inset 0 -1px 0 rgba(19, 45, 42, 0.05),
  inset 0 0 26px rgba(255, 255, 255, 0.12),
  0 18px 50px var(--reader-glass-shadow);
```

Apply the same cooler shadow to `.reader-toolbar` and `.mobile-note-drawer`.

- [x] **Step 3: Convert the right note panel to a linear rail**

Replace the `.note-panel` and `.note-surface` visual rules with:

```css
.note-panel {
  grid-area: notes;
  position: sticky;
  top: var(--toolbar-offset);
  align-self: start;
  height: calc(100vh - var(--toolbar-offset) - 12px);
  overflow: auto;
  border-left: 1px solid var(--reader-note-rule);
  background:
    linear-gradient(90deg, var(--reader-glass-low), transparent 64%);
  padding: 10px 0 10px 18px;
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.note-surface {
  min-height: calc(100vh - 160px);
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0 8px 0 0;
  line-height: 1.82;
  transition: opacity 140ms ease;
}

.note-surface p {
  margin: 0;
  padding: 0 0 15px;
}

.note-surface p + p {
  border-top: 1px solid var(--reader-note-rule);
  margin-top: 15px;
  padding-top: 15px;
}
```

Keep `.note-surface.is-changing` unchanged.

- [x] **Step 4: Run requirement tests and verify GREEN**

Run:

```bash
node tests/paper-reader-requirements.mjs
```

Expected: PASS.

## Task 3: Regression Verification And Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-07-03-paper-reader-glass-line-notes.md`

- [x] **Step 1: Run full verification**

Run:

```bash
node tests/paper-reader-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Expected: all commands exit 0.

- [x] **Step 2: Preview the local reader**

Check:

```bash
curl -I --max-time 3 http://127.0.0.1:4173/papers/brain-memory-for-ai-agents/
```

Expected: HTTP 200 if the local preview server is still running. If it is not running, start the existing static preview server and retry.

- [x] **Step 3: Mark completed plan checkboxes**

Change each task checkbox in this plan from `- [ ]` to `- [x]` only after its command or edit is complete.

- [x] **Step 4: Commit the implementation**

Run:

```bash
git add docs/superpowers/plans/2026-07-03-paper-reader-glass-line-notes.md tests/paper-reader-requirements.mjs papers/shared/reader.css
git commit -m "Refine reader glass and note rail"
```

Expected: commit succeeds and unrelated untracked files remain unstaged.
