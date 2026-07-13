# Finance Gold Theme Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Finance reader's inherited green presentation with an isolated, accessible “古金纸墨” theme while fixing the confirmed narrow-screen, search-close, empty-state, copy, and all-complete re-entry defects.

**Architecture:** Keep the maintained Foundations reader as the shared behavior and layout implementation. Add one Finance-only CSS layer after the shared stylesheet, keep Finance content in Markdown → JSON, and extract the shared `status !== "done"` selector plus Finance re-entry copy into a pure state model. Both builders define `done` as the completed status, so the shared selector replaces Foundations’ obsolete `complete` check while the Finance view state makes the all-complete copy directly unit-testable without a DOM.

**Tech Stack:** Static HTML, CSS with scoped OKLCH tokens, vanilla ES modules, Markdown-to-JSON builder, Node.js `node:assert` contract tests, in-app browser visual verification.

## Global Constraints

- Finance selectors must be scoped under `body[data-page="finance-roadmap-reader"]`; Foundations must retain its current palette.
- Use the approved restrained palette: neutral rice-paper and deep ink carry about 90% of visual weight; gold is limited to state, progress, focus, and key actions.
- Light body text contrast must be at least 4.5:1; large text and UI graphics must be at least 3:1.
- At `<= 480px`, the toolbar becomes two rows and primary controls expose 44px touch targets.
- Do not copy the shared reader stylesheet or add a frontend dependency.
- Keep `overview` as the route/module id while changing the Finance-visible title to `学习总览` and section title to `学习导航`.
- Treat `done` as the completed module status in both Finance and Foundations; `complete` is not a valid builder status.
- Closing search with Escape must hide the result list even when the query remains populated; refocusing search may reveal the preserved results.
- Use this exact Finance note empty-state copy: `进入任一概念模块底部的「知识笔记」，选中文字即可添加本地批注。批注只保存在当前浏览器。`
- Preserve public-site privacy: no holdings, transactions, account details, personal finances, or investment decisions.
- Preserve all unrelated dirty-worktree files and stage only the files named by each task.

## File Map

- Create `projects/finance/finance-theme.css`: Finance-only palette, interaction, focus, and mobile-toolbar overrides.
- Create `projects/finance/README.md`: project use, content pipeline, annotation boundary, and privacy contract.
- Modify `projects/finance/index.html`: load the Finance theme after the shared reader CSS.
- Modify `projects/finance/roadmap/modules/overview.md`: Chinese visible title and section heading.
- Modify `projects/finance/scripts/build-roadmap-data.mjs`: enforce the Chinese overview title.
- Regenerate `projects/finance/roadmap/roadmap-data.json`: compiled content consumed by the page.
- Create `projects/foundations/roadmap/reader-state-model.js`: shared next-incomplete selector and Finance re-entry view state.
- Modify `projects/foundations/roadmap/roadmap-reader.js`: consume the state model, close search results reliably, hide Finance priority noise, and render the accurate Finance note empty state.
- Modify `tests/finance-learning-reader-requirements.mjs`: Finance theme, docs, copy, and shared-reader integration contracts.
- Create `tests/foundations-reader-state-model.mjs`: pure state-decision regression tests.
- Modify `tests/foundations-roadmap-requirements.mjs`: require the shared state test and reject the obsolete `complete` lookup.
- Modify `package.json`: include the new focused model test in `test:foundations`.
- Modify `docs/superpowers/specs/2026-07-13-finance-learning-reader-design.md`: mark the refinement verified only after final QA passes.

---

### Task 0: Capture the Verified Initial Finance Reader Baseline

**Files:**
- Stage only the already-built Finance reader files listed below; do not stage the unrelated `papers/`, `tmp/`, Gurnee script, or Gurnee test changes.

**Interfaces:**
- Consumes: the uncommitted initial Finance reader that already passes `npm run test:all`.
- Produces: one reviewed baseline commit so the gold refinement commits contain only their own deltas.

- [ ] **Step 1: Re-run the current baseline tests**

```bash
node projects/finance/scripts/build-roadmap-data.mjs
npm run test:all
git diff --check
```

Expected: all commands exit 0 before anything is staged.

- [ ] **Step 2: Stage exactly the initial Finance reader scope**

```bash
git add \
  assets/fonts/README.md \
  assets/fonts/ZhiMangXing-Bookmark.woff2 \
  docs/superpowers/plans/2026-07-13-finance-learning-reader.md \
  package.json \
  projects/finance/index.html \
  projects/finance/roadmap/modules/asset-classes.md \
  projects/finance/roadmap/modules/behavior-process.md \
  projects/finance/roadmap/modules/fund-company-analysis.md \
  projects/finance/roadmap/modules/investment-basics.md \
  projects/finance/roadmap/modules/overview.md \
  projects/finance/roadmap/modules/risk-allocation.md \
  projects/finance/roadmap/modules/study-plan-tools.md \
  projects/finance/roadmap/modules/terms-further-reading.md \
  projects/finance/roadmap/modules/trading-execution.md \
  projects/finance/roadmap/modules/valuation.md \
  projects/finance/roadmap/roadmap-data.json \
  projects/finance/scripts/build-roadmap-data.mjs \
  projects/foundations/index.html \
  projects/foundations/roadmap/annotation-model.js \
  projects/foundations/roadmap/roadmap-reader.js \
  projects/manifest.json \
  tests/finance-learning-reader-requirements.mjs \
  tests/foundations-annotation-model.mjs \
  tests/foundations-roadmap-requirements.mjs \
  tests/projects-requirements.mjs
```

Inspect the staged names:

```bash
git diff --cached --name-only
```

Expected: only the paths above. No path under `papers/`, `tmp/`, `scripts/.tmp-*`, or `tests/gurnee-*` may appear.

- [ ] **Step 3: Commit the baseline**

```bash
git diff --cached --check
git commit -m "feat: add finance learning reader"
```

Expected: the commit succeeds and unrelated work remains unstaged.

---

### Task 1: Finance Theme, Responsive Toolbar, Documentation, and Chinese Overview

**Files:**
- Create: `projects/finance/finance-theme.css`
- Create: `projects/finance/README.md`
- Modify: `projects/finance/index.html`
- Modify: `projects/finance/roadmap/modules/overview.md`
- Modify: `projects/finance/scripts/build-roadmap-data.mjs`
- Regenerate: `projects/finance/roadmap/roadmap-data.json`
- Test: `tests/finance-learning-reader-requirements.mjs`

**Interfaces:**
- Consumes: shared CSS variables and DOM classes from `projects/foundations/roadmap/roadmap-reader.css`.
- Produces: a scoped theme loaded after shared CSS and generated Finance data whose overview title is `学习总览`.

- [ ] **Step 1: Write the failing Finance theme and content contracts**

Add these URL declarations after `financePageUrl`:

```js
const financeThemeUrl = new URL("../projects/finance/finance-theme.css", import.meta.url);
const financeReadmeUrl = new URL("../projects/finance/README.md", import.meta.url);
```

Change the first expected module tuple and load the two files:

```js
const expectedModules = [
  ["overview", "学习总览"],
  ["investment-basics", "投资的本质与前提"],
  ["asset-classes", "资产类别"],
  ["risk-allocation", "风险与配置"],
  ["fund-company-analysis", "基金与公司分析"],
  ["valuation", "估值"],
  ["trading-execution", "交易与执行"],
  ["behavior-process", "行为与流程"],
  ["study-plan-tools", "学习计划与工具"],
  ["terms-further-reading", "术语速查与延伸"],
];

assert.equal(existsSync(financeThemeUrl), true, "finance should expose a project-scoped gold theme");
assert.equal(existsSync(financeReadmeUrl), true, "finance should document its use and privacy boundary");

const financeTheme = readFileSync(financeThemeUrl, "utf8");
const financeReadme = readFileSync(financeReadmeUrl, "utf8");
```

Add these assertions after the existing HTML checks:

```js
const sharedCssIndex = financeHtml.indexOf('../foundations/roadmap/roadmap-reader.css');
const financeThemeIndex = financeHtml.indexOf('finance-theme.css');
assert.ok(sharedCssIndex >= 0 && financeThemeIndex > sharedCssIndex, "finance theme should load after shared reader CSS");
assert.match(financeHtml, /class="directory-kicker">学习路径<\/p>/, "finance directory chrome should use Chinese copy");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]/, "finance theme should be page-scoped");
assert.match(financeTheme, /oklch\(/, "finance theme should use the approved perceptual color space");
assert.match(financeTheme, /body\[data-page="finance-roadmap-reader"\]\[data-theme="dark"\]\s+\.route-ledger-label\s*\{\s*color:\s*var\(--reader-ink\);\s*\}/, "dark finance ledger labels should use dedicated high-contrast text");
assert.match(financeTheme, /--reader-panel-blur:\s*blur\(18px\)/, "finance should reduce the inherited glass blur");
assert.match(financeTheme, /\.toolbar-search:focus-within/, "finance search should expose a visible focus state");
assert.match(financeTheme, /@media \(max-width:\s*480px\)/, "finance should have a narrow-toolbar layout");
assert.match(financeTheme, /grid-template-rows:\s*auto auto/, "narrow finance toolbar should use two rows");
assert.match(financeTheme, /width:\s*44px[\s\S]*height:\s*44px/, "narrow finance controls should expose 44px targets");
assert.doesNotMatch(financeTheme, /#2e704d|rgba\(46,\s*112,\s*77|rgba\(152,\s*217,\s*166/, "finance theme should not retain the inherited visible green palette");
assert.match(financeReadme, /本地批注只保存在当前浏览器/, "README should explain annotation persistence");
assert.match(financeReadme, /不保存持仓、交易、账户或个人财务信息/, "README should preserve the public privacy boundary");
assert.ok(data.modules[0].sections["学习导航"], "finance overview should expose the Chinese navigation section");
assert.equal(data.modules[0].sections.Dashboard, undefined, "finance should not retain the visible Dashboard heading");
```

- [ ] **Step 2: Run the Finance test and verify it fails for missing theme/docs**

Run:

```bash
npm run test:finance
```

Expected: FAIL at `finance should expose a project-scoped gold theme` because `finance-theme.css` does not exist.

- [ ] **Step 3: Create the scoped Finance theme**

Create `projects/finance/finance-theme.css` with this complete structure and values:

```css
body[data-page="finance-roadmap-reader"] {
  --reader-ink: oklch(24% 0.018 72);
  --reader-ink-muted: oklch(43% 0.025 75);
  --reader-paper: oklch(96% 0.012 92);
  --reader-paper-soft: oklch(97% 0.01 92 / 0.88);
  --reader-paper-strong: oklch(98% 0.006 92 / 0.96);
  --reader-line: oklch(35% 0.025 75 / 0.16);
  --reader-line-strong: oklch(35% 0.025 75 / 0.36);
  --reader-glass: oklch(97% 0.012 92 / 0.78);
  --reader-glass-strong: oklch(98% 0.008 92 / 0.92);
  --reader-glass-highlight: oklch(100% 0 0 / 0.72);
  --reader-glass-edge: oklch(64% 0.05 82 / 0.34);
  --reader-glass-shadow: oklch(28% 0.035 72 / 0.12);
  --reader-note-rule: oklch(52% 0.11 80 / 0.28);
  --reader-section-line: oklch(35% 0.025 75 / 0.2);
  --reader-section-line-hover: oklch(42% 0.085 78);
  --reader-section-line-active: oklch(52% 0.11 80);
  --reader-blue: oklch(52% 0.11 80);
  --reader-red: oklch(42% 0.085 78);
  --reader-shadow: oklch(28% 0.035 72 / 0.12);
  --reader-code-surface: oklch(94% 0.014 88 / 0.9);
  --reader-code-header: oklch(42% 0.04 76 / 0.06);
  --reader-code-border: oklch(42% 0.04 76 / 0.24);
  --reader-code-inline: oklch(52% 0.11 80 / 0.1);
  --reader-code-ink: oklch(28% 0.02 72);
  --reader-code-gutter: oklch(43% 0.025 75 / 0.68);
  --reader-code-keyword: oklch(42% 0.085 78);
  --reader-code-literal: oklch(45% 0.08 52);
  --reader-code-comment: oklch(43% 0.025 75 / 0.78);
  --reader-code-type: oklch(40% 0.06 235);
  --reader-code-function: oklch(44% 0.08 82);
  --reader-code-error: oklch(46% 0.12 28);
  --reader-panel-blur: blur(18px) saturate(1.08);
  --finance-gold-text: oklch(42% 0.085 78);
  --finance-gold-graphic: oklch(52% 0.11 80);
  --finance-gold-wash: oklch(91% 0.035 84);
  --finance-hover: oklch(91% 0.035 84 / 0.48);
  --finance-selected: oklch(91% 0.035 84 / 0.68);
  --finance-focus-ring: oklch(52% 0.11 80 / 0.24);
  background:
    radial-gradient(circle at 14% 10%, oklch(78% 0.08 82 / 0.18), transparent 25%),
    radial-gradient(circle at 86% 26%, oklch(87% 0.045 88 / 0.2), transparent 34%),
    linear-gradient(145deg, oklch(98% 0.006 92), var(--reader-paper) 62%, oklch(92% 0.022 88));
}

body[data-page="finance-roadmap-reader"][data-theme="dark"] {
  --reader-ink: oklch(93% 0.012 88);
  --reader-ink-muted: oklch(76% 0.022 84);
  --reader-paper: oklch(16% 0.015 75);
  --reader-paper-soft: oklch(18% 0.017 75 / 0.88);
  --reader-paper-strong: oklch(20% 0.018 75 / 0.96);
  --reader-line: oklch(90% 0.015 84 / 0.14);
  --reader-line-strong: oklch(90% 0.015 84 / 0.34);
  --reader-glass: oklch(19% 0.018 75 / 0.82);
  --reader-glass-strong: oklch(22% 0.02 75 / 0.94);
  --reader-glass-highlight: oklch(100% 0 0 / 0.12);
  --reader-glass-edge: oklch(78% 0.06 83 / 0.24);
  --reader-glass-shadow: oklch(6% 0.01 75 / 0.42);
  --reader-note-rule: oklch(78% 0.11 83 / 0.28);
  --reader-section-line: oklch(93% 0.012 88 / 0.28);
  --reader-section-line-hover: oklch(86% 0.08 83);
  --reader-section-line-active: oklch(78% 0.11 83);
  --reader-blue: oklch(78% 0.11 83);
  --reader-red: oklch(78% 0.11 83);
  --reader-shadow: oklch(6% 0.01 75 / 0.36);
  --reader-code-surface: oklch(18% 0.017 75 / 0.94);
  --reader-code-header: oklch(93% 0.012 88 / 0.06);
  --reader-code-border: oklch(93% 0.012 88 / 0.2);
  --reader-code-inline: oklch(78% 0.11 83 / 0.12);
  --reader-code-ink: oklch(90% 0.012 88);
  --reader-code-gutter: oklch(76% 0.022 84 / 0.66);
  --reader-code-keyword: oklch(82% 0.09 83);
  --reader-code-literal: oklch(76% 0.09 55);
  --reader-code-comment: oklch(70% 0.02 82 / 0.72);
  --reader-code-type: oklch(75% 0.06 235);
  --reader-code-function: oklch(80% 0.08 82);
  --reader-code-error: oklch(72% 0.12 28);
  --finance-gold-text: oklch(82% 0.09 83);
  --finance-gold-graphic: oklch(78% 0.11 83);
  --finance-gold-wash: oklch(34% 0.045 78);
  --finance-hover: oklch(34% 0.045 78 / 0.42);
  --finance-selected: oklch(34% 0.045 78 / 0.58);
  --finance-focus-ring: oklch(78% 0.11 83 / 0.28);
  background:
    radial-gradient(circle at 16% 14%, oklch(48% 0.07 80 / 0.2), transparent 27%),
    radial-gradient(circle at 86% 28%, oklch(38% 0.045 80 / 0.18), transparent 35%),
    linear-gradient(145deg, oklch(14% 0.013 75), var(--reader-paper) 64%, oklch(20% 0.02 76));
}

body[data-page="finance-roadmap-reader"][data-theme="dark"] .route-ledger-label {
  color: var(--reader-ink);
}

body[data-page="finance-roadmap-reader"]::before {
  background:
    linear-gradient(102deg, transparent 0 34%, oklch(52% 0.11 80 / 0.035) 34.2%, transparent 35%),
    linear-gradient(17deg, transparent 0 56%, oklch(42% 0.085 78 / 0.03) 56.2%, transparent 57%),
    radial-gradient(ellipse at 18% 30%, oklch(100% 0 0 / 0.28), transparent 40%);
}

body[data-page="finance-roadmap-reader"] :is(a, button, select, textarea):focus-visible {
  outline: 2px solid var(--finance-gold-text);
  outline-offset: 2px;
}

body[data-page="finance-roadmap-reader"] .toolbar-search:focus-within {
  border-color: var(--finance-gold-text);
  box-shadow: 0 0 0 3px var(--finance-focus-ring);
}

body[data-page="finance-roadmap-reader"] .toolbar-search input:focus-visible {
  outline: 0;
}

body[data-page="finance-roadmap-reader"] :is(.toolbar-controls, .toolbar-search) {
  box-shadow:
    inset 0 1px 0 var(--reader-glass-highlight),
    inset 0 -1px 0 oklch(35% 0.025 75 / 0.08),
    0 14px 36px var(--reader-glass-shadow);
}

body[data-page="finance-roadmap-reader"] .module-nav-item[aria-current="true"] {
  grid-template-columns: minmax(0, 1fr) auto;
  border-color: var(--finance-gold-text);
  background: var(--finance-selected);
}

body[data-page="finance-roadmap-reader"] .module-nav-item[aria-current="true"]::before {
  content: none;
}

body[data-page="finance-roadmap-reader"] :is(.icon-button:hover, .module-nav-item:hover, .dashboard-module-row:hover, .result-item:hover) {
  background: var(--finance-hover);
}

body[data-page="finance-roadmap-reader"] .progress-fill {
  background: var(--finance-gold-graphic);
}

body[data-page="finance-roadmap-reader"] .progress-ring {
  background:
    radial-gradient(circle at center, var(--reader-paper-strong) 0 56%, transparent 57%),
    conic-gradient(var(--finance-gold-graphic) calc(var(--progress) * 1%), oklch(35% 0.015 75 / 0.12) 0);
}

body[data-page="finance-roadmap-reader"] .result-highlight {
  background: var(--finance-selected);
}

body[data-page="finance-roadmap-reader"] .knowledge-highlight {
  background: var(--finance-hover);
}

body[data-page="finance-roadmap-reader"] .knowledge-highlight.is-note {
  background: var(--finance-selected);
  box-shadow: inset 0 -1px 0 var(--finance-gold-text);
}

body[data-page="finance-roadmap-reader"] .knowledge-highlight:hover,
body[data-page="finance-roadmap-reader"] .knowledge-highlight.is-note:hover {
  background: var(--finance-gold-wash);
}

body[data-page="finance-roadmap-reader"] .note-empty-state {
  margin: 0;
  max-width: 28ch;
  color: var(--reader-ink-muted);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 480px) {
  body[data-page="finance-roadmap-reader"] .reader-toolbar {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    gap: 8px;
  }

  body[data-page="finance-roadmap-reader"] .toolbar-left {
    grid-row: 1;
    grid-column: 1;
  }

  body[data-page="finance-roadmap-reader"] .toolbar-right {
    display: contents;
  }

  body[data-page="finance-roadmap-reader"] .toolbar-controls {
    grid-row: 1;
    grid-column: 2;
    justify-self: end;
    height: 52px;
    padding: 4px;
  }

  body[data-page="finance-roadmap-reader"] .toolbar-search {
    grid-row: 2;
    grid-column: 1 / -1;
    width: 100%;
    height: 44px;
  }

  body[data-page="finance-roadmap-reader"] :is(.project-mark, .icon-button) {
    width: 44px;
    height: 44px;
  }

  body[data-page="finance-roadmap-reader"] .search-shortcut {
    display: none;
  }

  body[data-page="finance-roadmap-reader"] .reader-shell.is-searching .toolbar-search {
    top: 120px;
    width: calc(100vw - 28px);
  }

  body[data-page="finance-roadmap-reader"] .reader-shell.is-searching .search-results {
    top: 174px;
    width: calc(100vw - 28px);
  }

  body[data-page="finance-roadmap-reader"] .reader-shell.is-mobile-left-open .reader-sidebar {
    inset: 124px 14px auto;
  }
}
```

- [ ] **Step 4: Load the theme and add the project README**

Add this line immediately after the shared stylesheet in `projects/finance/index.html`:

```html
<link rel="stylesheet" href="finance-theme.css" />
```

In the same file, localize the visible directory kicker:

```html
<p class="directory-kicker">学习路径</p>
```

Create `projects/finance/README.md`:

```markdown
# 投资学习

这是公开的长期投资学习阅读器，用于学习概念、恢复进度、搜索术语和整理可公开的知识笔记。

## 使用方式

1. 从「学习总览」查看下一模块和整体进度。
2. 按模块阅读；能够解释和复述后，再更新模块 Markdown 的状态与进度。
3. 使用全文搜索查找术语、公式和案例。
4. 进入任一概念模块底部的「知识笔记」，选中文字即可添加本地批注；本地批注只保存在当前浏览器。需要长期保留的理解应写回对应 Markdown 模块。

## 内容与构建

- 内容源：`roadmap/modules/*.md`
- 构建命令：`node scripts/build-roadmap-data.mjs`
- 页面数据：`roadmap/roadmap-data.json`

## 隐私边界

这是公开站点，不保存持仓、交易、账户或个人财务信息，也不记录真实投资决策。页面内容只用于学习，不构成个性化投资建议。
```

- [ ] **Step 5: Localize the overview source and builder contract**

Change `projects/finance/roadmap/modules/overview.md`:

```markdown
title: 学习总览
```

and:

```markdown
## 学习导航
```

Change the first `MODULES` tuple in `projects/finance/scripts/build-roadmap-data.mjs`:

```js
["overview", "学习总览"],
```

Run:

```bash
node projects/finance/scripts/build-roadmap-data.mjs
npm run test:finance
```

Expected: both commands exit 0 and the Finance contract prints `finance reader contract passed`.

- [ ] **Step 6: Commit the theme/content slice**

```bash
git add projects/finance/index.html projects/finance/finance-theme.css projects/finance/README.md projects/finance/roadmap/modules/overview.md projects/finance/scripts/build-roadmap-data.mjs projects/finance/roadmap/roadmap-data.json tests/finance-learning-reader-requirements.mjs
git commit -m "feat: add finance antique gold theme"
```

---

### Task 2: Re-entry State, Search Close, Finance Metadata, and Note Empty State

**Files:**
- Create: `projects/foundations/roadmap/reader-state-model.js`
- Create: `tests/foundations-reader-state-model.mjs`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `tests/finance-learning-reader-requirements.mjs`
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: `getNextIncompleteModule(modules): object | null` using the builders’ shared `done` status vocabulary.
- Produces: `getFinanceReentryState(modules): { nextModule: object | null, nextStepLabel: string, status: string }`.
- Consumes: Finance and Foundations module records with `status` values including `done`; both dashboards handle a `null` all-complete result, and Finance gets explicit completed-state copy from the view state.

- [ ] **Step 1: Write the failing pure state-model test**

Create `tests/foundations-reader-state-model.mjs`:

```js
import assert from "node:assert/strict";
import {
  getFinanceReentryState,
  getNextIncompleteModule,
} from "../projects/foundations/roadmap/reader-state-model.js";

const modules = [
  { id: "one", title: "第一模块", status: "done" },
  { id: "two", title: "第二模块", status: "in-progress" },
  { id: "three", title: "第三模块", status: "not-started" },
];

assert.equal(getNextIncompleteModule(modules)?.id, "two", "reader should select the first unfinished module");
assert.equal(getNextIncompleteModule(modules.map((module) => ({ ...module, status: "done" }))), null, "reader should return null when every module is complete");
assert.equal(getNextIncompleteModule([]), null, "reader should handle an empty module list");

const activeReentry = getFinanceReentryState(modules);
assert.equal(activeReentry.nextModule?.id, "two", "finance re-entry should expose the next unfinished module");
assert.equal(activeReentry.nextStepLabel, "第二模块", "finance should expose the active next-step title");
assert.equal(activeReentry.status, "in-progress", "finance re-entry should expose the active module status");

const completeReentry = getFinanceReentryState(modules.map((module) => ({ ...module, status: "done" })));
assert.deepEqual(completeReentry, {
  nextModule: null,
  nextStepLabel: "全部模块已完成",
  status: "done",
}, "finance should expose directly testable all-complete copy and status");
```

Insert the test before `foundations-roadmap-requirements.mjs` in the `test:foundations` package script:

```json
"test:foundations": "node tests/foundations-annotation-model.mjs && node tests/foundations-code-listing-model.mjs && node tests/foundations-knowledge-article-parser.mjs && node tests/foundations-knowledge-content-requirements.mjs && node tests/foundations-reader-state-model.mjs && node tests/foundations-roadmap-requirements.mjs && git diff --exit-code -- projects/foundations/roadmap/roadmap-data.json"
```

Add `"foundations-reader-state-model.mjs"` to the focused-test filename array in `tests/foundations-roadmap-requirements.mjs` so Pages CI cannot silently drop the new test.

Run:

```bash
node tests/foundations-reader-state-model.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `reader-state-model.js`.

- [ ] **Step 2: Implement the selector and Finance re-entry view state**

Create `projects/foundations/roadmap/reader-state-model.js`:

```js
export function getNextIncompleteModule(modules = []) {
  return modules.find((module) => module.status !== "done") ?? null;
}

export function getFinanceReentryState(modules = []) {
  const nextModule = getNextIncompleteModule(modules);
  return {
    nextModule,
    nextStepLabel: nextModule?.title ?? "全部模块已完成",
    status: nextModule?.status ?? "done",
  };
}
```

Run:

```bash
node tests/foundations-reader-state-model.mjs
```

Expected: exit 0 with no assertion failure.

- [ ] **Step 3: Add failing Finance reader behavior contracts**

Load the shared reader source in `tests/finance-learning-reader-requirements.mjs`:

```js
const sharedReaderUrl = new URL("../projects/foundations/roadmap/roadmap-reader.js", import.meta.url);
const sharedReader = readFileSync(sharedReaderUrl, "utf8");
```

Add:

```js
const closeSearchSource = sharedReader.match(/function closeSearchModal\(\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
const escapeKeySource = sharedReader.match(/if \(event\.key === "Escape"\) \{([\s\S]*?)\n    \}/)?.[1] ?? "";

assert.match(sharedReader, /function renderFinanceOverviewDashboard\(module\)[\s\S]*?getFinanceReentryState\(learningModules\)/, "finance dashboard should consume the tested re-entry view state");
assert.match(sharedReader, /financeReentry\.nextStepLabel/, "finance dashboard should render the tested all-complete copy");
assert.match(sharedReader, /getStatusLabel\(financeReentry\.status\)/, "finance dashboard should render the tested re-entry status");
assert.match(sharedReader, /PROJECT_ID\s*!==\s*"finance"/, "finance metadata should hide redundant raw priority");
assert.match(sharedReader, /PROJECT_ID === "finance" \? "未找到结果" : "No results found"/, "finance empty search results should use Chinese copy");
assert.match(sharedReader, /进入任一概念模块底部的「知识笔记」，选中文字即可添加本地批注。批注只保存在当前浏览器。/, "empty note panels should explain the actual annotation boundary");
assert.match(closeSearchSource, /els\.searchResults\.hidden = true;/, "closing search should always hide results");
assert.doesNotMatch(closeSearchSource, /if \(!state\.searchQuery\)/, "closing search should not depend on an empty query");
assert.match(escapeKeySource, /if \(els\.shell\.classList\.contains\("is-searching"\)\) event\.preventDefault\(\);[\s\S]*closeSearchModal\(\);/, "Escape should prevent the native search-input default only while search is open, before preserving and hiding results");
assert.match(escapeKeySource, /if \(els\.shell\.classList\.contains\("is-searching"\)\) els\.searchInput\.blur\(\);[\s\S]*closeSearchModal\(\);/, "Escape should blur the search input only while search is open so one click can restore preserved results");
assert.doesNotMatch(sharedReader, /status !== "(?:done|complete)"\) \?\? learningModules\[0\]/, "completed dashboards should not fall back to their first module");
```

Also add these shared-reader assertions beside the other `roadmap-reader.js` contracts in `tests/foundations-roadmap-requirements.mjs`:

```js
assert.match(js, /getNextIncompleteModule\(learningModules\)/, "Foundations overview should use the tested done-status selector");
assert.doesNotMatch(js, /status !== "complete"/, "Foundations should not use a status rejected by its builder");
```

Run:

```bash
npm run test:finance
npm run test:foundations
```

Expected: both commands FAIL because the shared reader has not imported the state model or fixed `closeSearchModal` yet.

- [ ] **Step 4: Integrate the state model and remove Finance priority noise**

Add this import beside the existing local imports in `roadmap-reader.js`:

```js
import {
  getFinanceReentryState,
  getNextIncompleteModule,
} from "./reader-state-model.js";
```

Add after `getStatusLabel`:

```js
function getModuleMeta(module, { includeDate = false } = {}) {
  const parts = [getStatusLabel(module.status)];
  if (PROJECT_ID !== "finance" && module.priority) parts.push(module.priority);
  if (includeDate && module.lastUpdated) {
    parts.push(PROJECT_ID === "finance" ? `更新于 ${module.lastUpdated}` : `Updated ${module.lastUpdated}`);
  }
  return parts.join(" · ");
}
```

Replace the nav metadata with:

```js
<span class="module-nav-meta">${escapeHtml(getModuleMeta(module))}</span>
```

Replace the progress summary metadata with:

```js
<p class="progress-status">${escapeHtml(getModuleMeta(module))}</p>
```

Replace the Foundations and Finance dashboard row metadata with:

```js
<small>${escapeHtml(getModuleMeta(item))}</small>
```

Replace the module header metadata with:

```js
<p class="module-meta">${escapeHtml(getModuleMeta(module, { includeDate: true }))}</p>
```

In `renderOverviewDashboard`, replace the obsolete `complete` lookup and fallback with:

```js
const nextModule = getNextIncompleteModule(learningModules);
```

In `renderFinanceOverviewDashboard`, replace the inline lookup and fallback with:

```js
const financeReentry = getFinanceReentryState(learningModules);
const { nextModule } = financeReentry;
```

Change the first Finance block key and source lookup, remove the raw priority `<span>`, and use the tested view-state labels:

```js
["学习导航", `
  <div class="route-ledger" aria-label="投资学习导航">
    <div class="route-ledger-row">
      <span class="route-ledger-label">下一步</span>
      ${nextModule ? `
        <button class="route-ledger-target" type="button" data-dashboard-module-id="${escapeHtml(nextModule.id)}">
          <strong>${escapeHtml(financeReentry.nextStepLabel)}</strong>
        </button>
      ` : `<strong>${escapeHtml(financeReentry.nextStepLabel)}</strong>`}
    </div>
    <div class="route-ledger-row">
      <span class="route-ledger-label">当前计划</span>
      <strong>${escapeHtml(state.data.project.dashboardFocus ?? "从第一模块开始建立学习边界。")}</strong>
    </div>
    ${glossaryModule ? `
      <div class="route-ledger-row">
        <span class="route-ledger-label">快速查阅</span>
        <button class="route-ledger-target" type="button" data-dashboard-module-id="${escapeHtml(glossaryModule.id)}">
          <strong>${escapeHtml(glossaryModule.title)}</strong>
          <span>术语</span>
        </button>
      </div>
    ` : ""}
  </div>
  ${getSection(module, "学习导航")}
  <div class="dashboard-grid" aria-label="投资学习进度">
    <section class="dashboard-card">
      <p class="dashboard-card-label">整体学习进度</p>
      <strong>${escapeHtml(String(getOverallLearningProgress()))}%</strong>
    </section>
    <section class="dashboard-card">
      <p class="dashboard-card-label">概念模块</p>
      <strong>${escapeHtml(String(learningModules.length))}</strong>
    </section>
    <section class="dashboard-card">
      <p class="dashboard-card-label">当前状态</p>
      <strong>${escapeHtml(getStatusLabel(financeReentry.status))}</strong>
    </section>
  </div>
`]
```

- [ ] **Step 5: Make search closing unconditional and localize its empty result**

Replace `closeSearchModal` with:

```js
function closeSearchModal() {
  els.shell.classList.remove("is-searching");
  els.searchResults.hidden = true;
}
```

Do not clear `state.searchQuery`, the input value, or `searchResults.innerHTML`: reopening the still-populated input should reveal the preserved result set.

In the global `keydown` handler, guard the native Escape interception with the open-search state, prevent the browser's native `<input type="search">` clearing, and blur before closing:

```js
if (event.key === "Escape") {
  if (els.shell.classList.contains("is-searching")) event.preventDefault();
  if (els.shell.classList.contains("is-searching")) els.searchInput.blur();
  hideAnnotationDeletePopover();
  hideAnnotationToolbar();
  closeSearchModal();
  els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
}
```

Regression expectation: with search open and `估值` populated, Escape must leave `state.searchQuery`, the input value, and `searchResults.innerHTML` intact while hiding the overlay and result list. Refocusing search must reveal the same retained results. When search is not open, Escape must not suppress the browser default solely because the handler exists.

In the empty branch of `renderSearchResults`, replace the hard-coded English sentence with:

```js
const emptyMessage = PROJECT_ID === "finance" ? "未找到结果" : "No results found";
els.searchResults.innerHTML = `<p class="result-empty">${emptyMessage}</p>`;
```

- [ ] **Step 6: Render the Finance-only explanatory note empty state**

In `renderContextualNotePanel`, add:

```js
const noteContent = renderedNotes || (PROJECT_ID === "finance"
  ? '<p class="note-empty-state">进入任一概念模块底部的「知识笔记」，选中文字即可添加本地批注。批注只保存在当前浏览器。</p>'
  : "");
```

The project guard preserves Foundations’ current empty-panel behavior; only Finance receives the newly approved copy and scoped styling.

and assign `noteContent` to both surfaces:

```js
els.noteSurface.innerHTML = noteContent;
els.mobileNoteSurface.innerHTML = noteContent;
```

- [ ] **Step 7: Run focused and shared regressions**

Run:

```bash
node --check projects/foundations/roadmap/reader-state-model.js
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-reader-state-model.mjs
npm run test:finance
npm run test:foundations
```

Expected: every command exits 0; Foundations generated JSON remains unchanged.

- [ ] **Step 8: Commit the behavior slice**

```bash
git add projects/foundations/roadmap/reader-state-model.js projects/foundations/roadmap/roadmap-reader.js tests/foundations-reader-state-model.mjs tests/foundations-roadmap-requirements.mjs tests/finance-learning-reader-requirements.mjs package.json
git commit -m "fix: harden finance reader interactions"
```

---

### Task 3: Full Verification and Delivery Status

**Files:**
- Modify after successful QA: `docs/superpowers/specs/2026-07-13-finance-learning-reader-design.md`

**Interfaces:**
- Consumes: Tasks 1-2 complete implementation.
- Produces: verified desktop/mobile/light/dark delivery and an accurate design status.

- [ ] **Step 1: Rebuild and run the complete automated suite**

Run:

```bash
node projects/finance/scripts/build-roadmap-data.mjs
npm run test:all
git diff --check
```

Expected: all commands exit 0; Finance prints its contract pass line and Foundations reports no generated-data diff.

- [ ] **Step 2: Run the design-system detector on the changed UI files**

Run:

```bash
node .agents/skills/impeccable/scripts/detect.mjs --json projects/finance/index.html projects/finance/finance-theme.css projects/foundations/roadmap/roadmap-reader.js
```

Expected: no high-severity side-stripe, gradient-text, oversized-radius, or unscoped Finance color finding. Review advisory literal-color findings against the approved spec rather than suppressing them automatically.

- [ ] **Step 3: Verify the page in a local browser at four states**

Serve the repository root and inspect `http://localhost:4173/projects/finance/`:

```bash
python3 -m http.server 4173 --directory .
```

Verify:

- Desktop 1280×720 light: no visible green background; gold is restrained; note panel accurately points to the concept modules’ 「知识笔记」 section.
- Desktop dark: charcoal paper, legible text, muted gold emphasis, no bright yellow-on-black luxury styling.
- Mobile 390×844 light: toolbar uses two rows, directory opens below it, search and note controls remain reachable. Type `估值`, press Escape, confirm the input still contains `估值` and the retained result DOM remains intact while both the overlay and result list hide, then refocus and confirm the same preserved results reappear. Replace the query with `zzzz-no-match` and confirm the empty result reads `未找到结果`.
- Mobile 320×700 light: search input width is at least 44px, all primary toolbar controls are 44×44px, and `document.documentElement.scrollWidth === document.documentElement.clientWidth`.
- Keyboard: tab focus is visible on return, directory, theme, note, search, module, and dashboard controls.
- Completion behavior remains covered by the pure all-`done` Finance re-entry view-state test and the shared-reader rendering contract; do not mutate generated project data during visual QA.

- [ ] **Step 4: Verify computed contrast**

Use the browser's computed colors for `.section-body`, `.module-meta`, `.route-ledger-label`, `.module-nav-item[aria-current="true"]`, and focused toolbar controls. Confirm body/small text ≥4.5:1 and non-text focus/active boundaries ≥3:1 in both themes. If a value misses, adjust only the corresponding Finance token toward higher contrast and rerun `npm run test:finance` plus this check.

- [ ] **Step 5: Mark the design verified and commit delivery metadata**

Change the design status line to:

```markdown
- 状态：初版与「古金纸墨」改进均已实现并通过桌面、390px、320px、亮色与暗色验证
```

Then run and commit:

```bash
git diff --check
git add docs/superpowers/specs/2026-07-13-finance-learning-reader-design.md docs/superpowers/plans/2026-07-13-finance-gold-theme.md
git commit -m "docs: record verified finance theme delivery"
```

Expected: the commit includes only the approved plan and verified spec status; unrelated worktree files remain unstaged.

---

### Task 4: Close Final Whole-Branch Review Regressions

**Files:**
- Modify: `package.json`
- Modify: `projects/finance/index.html`
- Modify: `projects/finance/roadmap/roadmap-data.json`
- Modify: `projects/foundations/roadmap/reader-state-model.js`
- Modify: `projects/foundations/roadmap/roadmap-reader.css`
- Modify: `projects/foundations/roadmap/roadmap-reader.js`
- Modify: `projects/foundations/scripts/roadmap-markdown.mjs`
- Modify: `tests/finance-learning-reader-requirements.mjs`
- Modify: `tests/foundations-reader-state-model.mjs`
- Modify: `tests/foundations-roadmap-requirements.mjs`
- Create: `tests/foundations-roadmap-markdown-math.mjs`

**Interfaces:**
- Consumes: canonical Finance Markdown modules and the shared Foundations reader.
- Produces: complete Finance section rendering, safe searchable math placeholders enhanced by KaTeX, and a deterministic generated-data freshness gate.

- [ ] **Step 1: Prove the missing-section and malformed-formula regressions**

Add focused tests that require Finance to return every generated section title in source order while Foundations keeps its curated seven-title contract. Add Markdown tests for display and inline math, fenced and inline code, escaped unsafe input, searchable fallback text, and the Setext-heading regression.

Expected: the new tests fail against the reviewed branch before implementation.

- [ ] **Step 2: Select renderable sections per project**

Move the established Foundations title list into `reader-state-model.js` and expose `getRenderableSectionTitles(module, projectId)`. Return every generated section key for Finance and the existing curated subset for other projects. Use the selector from `renderCurrentModule` without changing dashboard or special section renderers.

Expected: every Finance rail/search section ID has a rendered DOM target; Foundations ordering stays unchanged.

- [ ] **Step 3: Preserve and progressively render roadmap formulas**

Use an independent `Marked` instance with block `\\[...\\]` and inline `\\(...\\)` extensions. Emit escaped `math-display` or `math-inline` placeholders whose `data-latex` and visible fallback text survive sanitization and search extraction. Do not transform fenced or inline code.

Load KaTeX 0.16.11 only on the Finance page, before the shared reader. After module HTML mounts, render placeholders with `trust: false`, retain fallback text when KaTeX is unavailable, and constrain wide display formulas to an internal horizontal scroller so they cannot widen the document.

- [ ] **Step 4: Make Finance generated data self-checking**

Change `test:finance` to run:

```bash
node projects/finance/scripts/build-roadmap-data.mjs
node tests/finance-learning-reader-requirements.mjs
git diff --exit-code -- projects/finance/roadmap/roadmap-data.json
```

Extend the Finance contract to compare source formulas with generated placeholders, reject formula-created Setext headings, verify KaTeX load order and safe runtime options, and require every non-dashboard section to expose a unique renderable ID.

- [ ] **Step 5: Verify representative content and narrow-screen containment**

Run:

```bash
node projects/finance/scripts/build-roadmap-data.mjs
npm run test:all
git diff --check
```

At `?module=valuation`, confirm a previously omitted numbered section is visible, every formula placeholder renders without a KaTeX error, and the document has no horizontal overflow at 1280px, 390px, or 320px. At 320px, confirm an intentionally wide formula scrolls inside its own container.

- [ ] **Step 6: Preserve the reader heading hierarchy**

Add a Finance contract that rejects `<h1>` inside generated section bodies and requires a representative authored chapter heading to survive as `<h3>`. Because the reader owns the page `<h1>` and each module section heading is `<h2>`, normalize sanitized Finance section-body `<h1>` elements to `<h3>` during the Finance build. Keep headings shown inside fenced Markdown templates as code.

Rebuild and confirm generated Finance data contains no `<h1>`, the complete suite passes, and browser inspection reports no page-level headings inside `.section-body`.
