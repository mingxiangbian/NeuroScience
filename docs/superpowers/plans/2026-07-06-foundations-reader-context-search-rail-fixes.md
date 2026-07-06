# Foundations Reader Context Search Rail Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `projects/foundations/` roadmap reader 的右栏错误 fallback、搜索整词限制、以及收起横线导航 active hover 问题。

**Architecture:** 保持现有静态 reader 架构不变，只修改 `roadmap-reader.js` 的状态选择和搜索评分、`roadmap-reader.css` 的横线 hover 样式，以及 `tests/foundations-roadmap-requirements.mjs` 的回归断言。不新增数据字段、不改 Markdown 内容、不触碰 `papers/` reader。

**Tech Stack:** Vanilla JavaScript ES modules, static JSON reader, CSS, Node.js assertion-based requirement tests.

---

## File Structure

- Modify: `tests/foundations-roadmap-requirements.mjs`
  - 增加三个行为的静态回归约束：右栏严格关联、搜索完整词优先加子串兜底、横线导航 active/hover。
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
  - 修改 `getKnowledgeNoteForSection()`、`renderContextualNotePanel()`、`openModule()`、搜索匹配 helper、`getSearchScore()`、`highlightTerms()`、`renderSectionRail()`。
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
  - 增加 active 横线 hover 明确规则，避免 `.is-active` 覆盖 hover。

## Task 1: 右侧笔记栏严格关联

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add failing right-panel requirements**

In `tests/foundations-roadmap-requirements.mjs`, after this existing assertion:

```js
assert.doesNotMatch(js, /资源", "反思", "面试表达"/, "right notes should not be hard-coded to old resource/reflection/interview groups");
```

add:

```js
assert.doesNotMatch(js, /if \(sectionId === getSectionId\(module, "知识笔记"\)\) return module\.knowledgeNotes\?\.\[0\];/, "knowledge note section should not default to the first note");
assert.doesNotMatch(js, /return getKnowledgeNoteById\(module, state\.activeKnowledgeNoteId\) \?\? module\.knowledgeNotes\?\.\[0\];/, "ordinary sections should not fall back to stale or first knowledge notes");
assert.match(js, /if \(sectionId !== getSectionId\(module, "知识笔记"\)\) return null;/, "ordinary sections should return an empty right panel when they have no explicit knowledge note");
assert.match(js, /const renderedNotes = note[\s\S]*: "";/, "right note panel should render an empty surface when no note is associated");
assert.match(js, /renderContextualNotePanel\(null\);/, "module switches should start with an empty right note panel");
assert.doesNotMatch(js, /renderContextualNotePanel\(nextModule\.knowledgeNotes\?\.\[0\]\);/, "module switches should not default the right panel to the first knowledge note");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL with at least one of:

```text
knowledge note section should not default to the first note
ordinary sections should not fall back to stale or first knowledge notes
module switches should start with an empty right note panel
```

- [ ] **Step 3: Replace note association logic**

In `projects/foundations/roadmap/roadmap-reader.js`, replace the whole `getKnowledgeNoteForSection()` function with:

```js
function getKnowledgeNoteForSection(module, sectionId) {
  const directNote = getKnowledgeNoteById(module, sectionId);
  if (directNote) return directNote;
  if (sectionId !== getSectionId(module, "知识笔记")) return null;
  return getKnowledgeNoteById(module, state.activeKnowledgeNoteId) ?? null;
}
```

- [ ] **Step 4: Render an empty right surface when note is null**

In `renderContextualNotePanel(note)`, replace the `renderedNotes` ternary with:

```js
  const renderedNotes = note
    ? `<article class="note-context"><h3>${escapeHtml(note.title)}</h3>${noteGroups}${renderLocalAnnotations(note)}</article>`
    : "";
```

Keep the `label`, `noteSurface`, `mobileNoteSurface`, and editor-sync code unchanged.

- [ ] **Step 5: Stop defaulting module switches to the first note**

In `openModule()`, replace:

```js
  renderContextualNotePanel(nextModule.knowledgeNotes?.[0]);
```

with:

```js
  renderContextualNotePanel(null);
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-roadmap-requirements.mjs
```

Expected: both commands PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/foundations-roadmap-requirements.mjs projects/foundations/roadmap/roadmap-reader.js
git commit -m "Fix foundations right note context"
```

## Task 2: 搜索改为完整词优先加子串兜底

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [ ] **Step 1: Add failing hybrid-search requirements**

In `tests/foundations-roadmap-requirements.mjs`, after this existing assertion:

```js
assert.match(js, /function hasSearchTerm/, "roadmap JS should avoid raw substring-only search matches");
```

add:

```js
assert.match(js, /function getSearchMatchLevel/, "roadmap JS should distinguish whole-word matches from partial matches");
assert.match(js, /function escapeSearchPattern/, "roadmap JS should escape user search terms before building regex patterns");
assert.match(js, /return getSearchMatchLevel\(text, term\) > 0;/, "hasSearchTerm should delegate to the shared match-level helper");
assert.match(js, /const moduleLevel = getSearchMatchLevel\(entry\.moduleTitle, term\);/, "search scoring should evaluate module title match levels");
assert.match(js, /moduleLevel === 2 \? 16 : moduleLevel === 1 \? 6 : 0/, "whole-word module matches should outrank partial module matches");
assert.match(js, /bodyLevel === 2 \? 4 : bodyLevel === 1 \? 1 : 0/, "body partial matches should remain a low-score fallback");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL with:

```text
roadmap JS should distinguish whole-word matches from partial matches
```

- [ ] **Step 3: Add shared search match helpers**

In `projects/foundations/roadmap/roadmap-reader.js`, after `isAsciiSearchTerm(term)`, replace the existing `hasSearchTerm(text, term)` function with this block:

```js
function escapeSearchPattern(value) {
  return String(value ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getSearchMatchLevel(text, term) {
  const normalizedText = String(text ?? "").toLowerCase();
  const normalizedTerm = String(term ?? "").toLowerCase();
  if (!normalizedTerm) return 0;
  if (!normalizedText.includes(normalizedTerm)) return 0;
  if (!isAsciiSearchTerm(normalizedTerm)) return 2;
  const pattern = new RegExp(`(^|[^a-z0-9])${escapeSearchPattern(normalizedTerm)}([^a-z0-9]|$)`, "i");
  return pattern.test(normalizedText) ? 2 : 1;
}

function hasSearchTerm(text, term) {
  return getSearchMatchLevel(text, term) > 0;
}
```

- [ ] **Step 4: Replace search scoring**

Replace the whole `getSearchScore(entry, terms)` function with:

```js
function getSearchScore(entry, terms) {
  return terms.reduce((score, term) => {
    const moduleLevel = getSearchMatchLevel(entry.moduleTitle, term);
    const sectionLevel = getSearchMatchLevel(entry.sectionTitle, term);
    const bodyLevel = getSearchMatchLevel(entry.text, term);
    const moduleScore = moduleLevel === 2 ? 16 : moduleLevel === 1 ? 6 : 0;
    const sectionScore = sectionLevel === 2 ? 10 : sectionLevel === 1 ? 4 : 0;
    const bodyScore = bodyLevel === 2 ? 4 : bodyLevel === 1 ? 1 : 0;
    return score + moduleScore + sectionScore + bodyScore;
  }, 0);
}
```

- [ ] **Step 5: Reuse the escaping helper in highlighting**

In `highlightTerms(text, query)`, replace:

```js
  const terms = getSearchTerms(query).map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
```

with:

```js
  const terms = getSearchTerms(query).map(escapeSearchPattern);
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-roadmap-requirements.mjs
```

Expected: both commands PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/foundations-roadmap-requirements.mjs projects/foundations/roadmap/roadmap-reader.js
git commit -m "Improve foundations roadmap search matching"
```

## Task 3: 横线导航移除硬编码 active 并修复 active hover

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `projects/foundations/roadmap/roadmap-reader.css`

- [ ] **Step 1: Add failing rail requirements**

In `tests/foundations-roadmap-requirements.mjs`, after this existing assertion:

```js
assert.match(css, /\.section-line\[aria-current="true"\]/, "roadmap CSS should expose active collapsed rail state");
```

add:

```js
assert.match(css, /\.section-line\[aria-current="true"\]:hover,\s*\.section-line\.is-active:hover\s*\{[\s\S]*background:\s*var\(--reader-section-line-hover\)/, "active collapsed rail line should show a distinct hover state");
```

After this existing assertion:

```js
assert.match(js, /section-tooltip/, "roadmap JS should render collapsed rail tooltips");
```

add:

```js
assert.doesNotMatch(js, /index === 0 \? " is-active" : ""/, "section rail should not hard-code the first line as active");
assert.doesNotMatch(js, /index === 0 \? "true" : "false"/, "section rail aria-current should not be hard-coded from initial index");
assert.match(js, /button\.className = "section-line";/, "section rail buttons should start inactive");
assert.match(js, /button\.setAttribute\("aria-current", "false"\);/, "section rail aria-current should be initialized as false");
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL with at least one of:

```text
active collapsed rail line should show a distinct hover state
section rail should not hard-code the first line as active
```

- [ ] **Step 3: Remove hard-coded active from renderSectionRail**

In `projects/foundations/roadmap/roadmap-reader.js`, replace the `renderSectionRail(module)` function with:

```js
function renderSectionRail(module) {
  els.sectionLines.innerHTML = "";
  getRailTargets(module).forEach((target) => {
    const button = document.createElement("button");
    button.className = "section-line";
    button.type = "button";
    button.dataset.sectionId = target.id;
    button.title = target.title;
    button.setAttribute("aria-label", target.title);
    button.setAttribute("aria-current", "false");
    button.innerHTML = `<span class="section-tooltip">${escapeHtml(target.title)}</span>`;
    button.addEventListener("click", () => {
      document.querySelector(`#${CSS.escape(target.id)}`)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      setActiveSection(target.id);
    });
    els.sectionLines.append(button);
  });
}
```

- [ ] **Step 4: Add explicit active hover CSS**

In `projects/foundations/roadmap/roadmap-reader.css`, immediately after the existing active rule:

```css
.section-line[aria-current="true"],
.section-line.is-active {
  width: 32px;
  height: 3px;
  background: var(--reader-section-line-active);
}
```

add:

```css
.section-line[aria-current="true"]:hover,
.section-line.is-active:hover {
  width: 36px;
  height: 3px;
  background: var(--reader-section-line-hover);
}
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-roadmap-requirements.mjs
```

Expected: both commands PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/foundations-roadmap-requirements.mjs projects/foundations/roadmap/roadmap-reader.js projects/foundations/roadmap/roadmap-reader.css
git commit -m "Fix foundations section rail state"
```

## Task 4: Final Verification And Manual Smoke Check

**Files:**
- Read: `projects/foundations/index.html`
- Read: `projects/foundations/roadmap/roadmap-reader.js`
- Read: `projects/foundations/roadmap/roadmap-reader.css`
- Read: `tests/foundations-roadmap-requirements.mjs`

- [ ] **Step 1: Run full automated verification**

Run:

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-roadmap-requirements.mjs
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 2: Start a static local server**

Run:

```bash
python3 -m http.server 8765
```

Expected: server starts and prints:

```text
Serving HTTP on :: port 8765
```

If port `8765` is already in use, use:

```bash
python3 -m http.server 8766
```

- [ ] **Step 3: Manual browser smoke checks**

Open:

```text
http://127.0.0.1:8765/projects/foundations/
```

Check:

- Opening a module starts with an empty right note surface for ordinary sections.
- Clicking a `.knowledge-card` shows that card's note groups and local annotation notes in the right panel.
- Searching `Trans` returns entries containing `Transformer`.
- Searching the full word `Transformer` returns relevant entries at least as prominently as `Trans`.
- Hovering the current active collapsed rail line visibly changes width or color.

- [ ] **Step 4: Stop the static server**

In the server terminal, press:

```text
Ctrl-C
```

Expected: the server exits and no long-running session remains.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short --branch
```

Expected: clean worktree on the implementation branch, with only committed changes.

## Plan Self-Review

- Spec coverage: Task 1 covers strict right-panel association and empty surface; Task 2 covers hybrid search scoring; Task 3 covers rail hard-coded active and active hover; Task 4 covers full verification and browser smoke checks.
- Placeholder scan: no unresolved markers or unspecified test steps remain.
- Type consistency: helper names are fixed as `escapeSearchPattern`, `getSearchMatchLevel`, `hasSearchTerm`, `getSearchScore`, `renderContextualNotePanel`, and `renderSectionRail`.
- Scope check: plan only touches the three approved Foundations reader files plus the Foundations requirement test.
