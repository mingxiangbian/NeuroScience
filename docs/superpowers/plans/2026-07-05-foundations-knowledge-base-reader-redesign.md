# Foundations Knowledge Base Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将 `projects/foundations/` 从 roadmap 展示页改造成以概念为核心的长期面试知识库 reader。

**Architecture:** 继续采用纯静态架构：`roadmap/modules/*.md` 是维护入口，`build-roadmap-data.mjs` 解析 Markdown 并生成 `roadmap-data.json`，`roadmap-reader.js` 消费 JSON 渲染 dashboard、模块正文、knowledge notes、右栏旁注和搜索结果。视觉层只改 Foundations reader，不改 `papers/shared`。

**Tech Stack:** Markdown frontmatter, Node.js ESM build script, vanilla HTML/CSS/JS, existing Node requirement tests, GitHub Pages static hosting.

---

### Task 1: 更新需求测试为新信息架构

**Files:**
- Modify: `tests/foundations-roadmap-requirements.mjs`

- [x] **Step 1: 写 failing test**

在现有测试中替换旧 contract 断言，新增这些行为断言：

```js
assert.match(css, /\.section-tooltip/, "collapsed rail should expose section tooltips");
assert.match(css, /\.section-line:hover \+ \.section-line/, "collapsed rail should grow neighboring lines on hover");
assert.match(css, /\.reader-shell\.is-left-collapsed \.section-rail\s*\{[\s\S]*display:\s*flex/, "collapsed rail should render in left-collapsed state");
assert.match(css, /\.note-group-title/, "right note panel should still style grouped note headings");

assert.match(js, /function renderOverviewDashboard/, "roadmap JS should render overview as a dashboard");
assert.match(js, /function renderKnowledgeNotesSection/, "roadmap JS should render concept-centric knowledge notes");
assert.match(js, /function renderContextualNotePanel/, "roadmap JS should render right notes from current section context");
assert.match(js, /function setActiveKnowledgeContext/, "roadmap JS should sync right notes with active knowledge context");
assert.match(js, /section-tooltip/, "roadmap JS should render collapsed rail tooltips");
assert.match(js, /knowledgeNotes/, "roadmap JS should consume generated knowledge notes");
assert.doesNotMatch(js, /资源", "反思", "面试表达"/, "right notes should not be hard-coded to old resource/reflection/interview groups");

assert.equal(typeof data.project.overallLearningProgress, "number", "generated data should include overall learning progress");
assert.equal(data.project.overallLearningProgress, 0, "initial overall learning progress should be zero");
assert.equal(data.project.dashboardModuleId, "overview", "overview should be identified as dashboard module");

for (const module of data.modules) {
  assert.equal(typeof module.learningProgress, "number", `${module.id} should include learningProgress`);
  assert.ok(module.learningProgress >= 0 && module.learningProgress <= 100, `${module.id} learningProgress should be bounded`);
  assert.ok(Array.isArray(module.knowledgeNotes), `${module.id} should include knowledgeNotes`);
  assert.ok(!Object.hasOwn(module.sections, "验收标准"), `${module.id} should not render 验收标准 as a section`);
  assert.ok(!Object.hasOwn(module.sections, "下一步"), `${module.id} should not render 下一步 as a section`);
  if (module.id !== "overview") {
    assert.ok(Object.hasOwn(module.sections, "时间线"), `${module.id} should preserve 时间线`);
    assert.ok(Object.hasOwn(module.sections, "知识笔记"), `${module.id} should include 知识笔记`);
  }
}

assert.ok(byId["rag-memory"].knowledgeNotes.length >= 2, "RAG & Memory should expose concept-centric notes");
assert.ok(byId["rag-memory"].knowledgeNotes.some((note) => note.title === "RAG evaluation"), "RAG & Memory should include RAG evaluation note");
assert.ok(byId["rag-memory"].searchEntries.some((entry) => entry.type === "knowledge-note"), "search should include knowledge-note entries");
```

- [x] **Step 2: 运行测试确认红灯**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: FAIL，至少命中 `learningProgress`、`knowledgeNotes`、`renderOverviewDashboard` 或 `.section-tooltip` 缺失。

### Task 2: 迁移模块 Markdown contract

**Files:**
- Modify: `projects/foundations/roadmap/modules/overview.md`
- Modify: `projects/foundations/roadmap/modules/coding.md`
- Modify: `projects/foundations/roadmap/modules/llm-systems.md`
- Modify: `projects/foundations/roadmap/modules/agent-design.md`
- Modify: `projects/foundations/roadmap/modules/rag-memory.md`
- Modify: `projects/foundations/roadmap/modules/evals-debugging.md`
- Modify: `projects/foundations/roadmap/modules/research-reading.md`
- Modify: `projects/foundations/roadmap/modules/behavioral-strategy.md`
- Modify: `projects/foundations/roadmap/modules/logs.md`

- [x] **Step 1: 更新 frontmatter**

每个模块将：

```yaml
status: in-progress
progress: 30
```

替换为：

```yaml
status: not-started
learning_progress: 0
```

保留 `priority`、`id`、`title`、`last_updated`。

- [x] **Step 2: 普通模块删除旧尾部 section**

对非 `overview.md` 模块：

- 保留 `## 目标`
- 保留 `## 当前状态`
- 保留 `## 核心知识`
- 保留 `## 任务`
- 保留 `## 时间线`
- 删除 `## 验收标准`
- 删除 `## 下一步`
- 将 `## 资源`、`## 反思`、`## 面试表达` 重写为 `## 知识笔记`

示例结构：

```md
## 知识笔记

### RAG evaluation

核心理解：

- retrieval quality 要先于 generation quality 单独评估。

常见误区：

- 只看最终答案正确率会掩盖 retrieval failure。

相关资料：

- Lewis et al. RAG

面试转译：

- “I would evaluate retrieval before generation with recall@k and failure reports, then separately evaluate answer faithfulness.”

复习提示：

- 能否解释 retrieval failure、generation hallucination 和 citation failure 的区别？
```

- [x] **Step 3: Overview 改为 dashboard source**

`overview.md` 保留目标岗位、策略、模块地图和 30/45/60-day plan，但 section 改为：

```md
## Dashboard

## 模块总览

## 计划节奏

## 待补知识
```

不要保留普通模块式 `## 验收标准` 或 `## 下一步`。

### Task 3: 更新 build script 数据模型

**Files:**
- Modify: `projects/foundations/scripts/build-roadmap-data.mjs`
- Generated: `projects/foundations/roadmap/roadmap-data.json`

- [x] **Step 1: 修改 status 和 progress 解析**

将允许状态更新为：

```js
const VALID_STATUSES = new Set(["not-started", "learning", "review", "done"]);
```

生成字段使用：

```js
const learningProgress = Number.parseInt(frontmatter.learning_progress ?? "0", 10);
```

并校验 `0 <= learningProgress <= 100`。

- [x] **Step 2: 新增 `extractKnowledgeNotes`**

实现解析 `## 知识笔记` 下 `### concept` 的函数，输出：

```js
{
  id: `${moduleId}-${slugifySection(title)}`,
  moduleId,
  title,
  summary,
  resources,
  reminders,
  interview,
  reviewPrompts,
  html
}
```

识别中文标签：

- `核心理解：` -> `summary` 和正文展示
- `常见误区：` -> `reminders`
- `关键提醒：` -> `reminders`
- `相关资料：` -> `resources`
- `面试转译：` -> `interview`
- `复习提示：` -> `reviewPrompts`

- [x] **Step 3: 更新 `buildSearchEntries`**

搜索条目包含普通 section 和 knowledge note：

```js
{
  id: note.id,
  type: "knowledge-note",
  moduleId,
  moduleTitle,
  sectionTitle: note.title,
  text: [note.summary, note.resources, note.reminders, note.interview, note.reviewPrompts].flat().join(" ")
}
```

- [x] **Step 4: 生成 dashboard project 字段**

`project` 中包含：

```js
overallLearningProgress,
dashboardModuleId: "overview"
```

`overallLearningProgress` 是非 Overview 模块 `learningProgress` 的平均值；初始应为 `0`。

- [x] **Step 5: 运行 build script**

Run:

```bash
node projects/foundations/scripts/build-roadmap-data.mjs
```

Expected: `roadmap-data.json` 更新并包含 `learningProgress`、`knowledgeNotes`、`overallLearningProgress`。

### Task 4: 更新 reader JS 渲染逻辑

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.js`

- [x] **Step 1: 引入 learning progress 文案**

将所有 `module.progress` 读法替换为 `module.learningProgress`，页面文案使用“学习进度”。

- [x] **Step 2: 新增 `renderOverviewDashboard`**

当 `module.id === "overview"` 时，用 dashboard 结构渲染：

- total learning progress
- module status grid
- current priority modules
- plan cadence sections

不要走普通模块的固定 section 渲染。

- [x] **Step 3: 新增 `renderKnowledgeNotesSection`**

把 `module.knowledgeNotes` 渲染成可定位 cards：

```html
<article class="knowledge-card" id="rag-memory-rag-evaluation" data-section-id="rag-memory-rag-evaluation" data-note-id="rag-memory-rag-evaluation">
  <h3>RAG evaluation</h3>
  ...
</article>
```

- [x] **Step 4: 新增 contextual note panel**

用 `renderContextualNotePanel(note)` 替代旧 `renderNotePanel` 的固定三组逻辑。

右栏分组：

- `相关资料`
- `关键提醒`
- `面试转译`
- `复习提示`

空数组不渲染。

- [x] **Step 5: active section 同步右栏**

`setActiveSection(sectionId)` 在更新 rail 后调用 `setActiveKnowledgeContext(sectionId)`。如果 section id 对应 knowledge note，右栏显示该 note；否则显示模块默认 note 或空状态。

- [x] **Step 6: collapsed rail 渲染 tooltip**

`renderSectionRail` 中每个 button 增加：

```js
button.innerHTML = `<span class="section-tooltip">${escapeHtml(sectionTitle)}</span>`;
```

knowledge note card 需要进入 rail 或至少可被搜索定位；普通 section rail 继续显示主 section。

### Task 5: 更新 CSS 视觉和布局

**Files:**
- Modify: `projects/foundations/roadmap/roadmap-reader.css`

- [x] **Step 1: 对齐 collapsed rail**

将 `.section-rail`、`.section-lines`、`.section-line`、`.section-tooltip` 对齐 `papers/shared/reader.css` 的行为：

- `height: min(58vh, calc(100vh - var(--toolbar-offset) - 70px))`
- `justify-content: center`
- `.section-lines { width: 38px; gap: 13px; }`
- `.section-line { position: relative; justify-self: center; }`
- `.section-line:hover + .section-line`
- `.section-line:has(+ .section-line:hover)`
- `.section-tooltip`

- [x] **Step 2: 更新 progress 和 dashboard 样式**

新增或调整：

- `.dashboard-grid`
- `.dashboard-card`
- `.dashboard-module-list`
- `.learning-progress`
- `.module-status-pill`

- [x] **Step 3: 增加 knowledge card 样式**

新增：

- `.knowledge-list`
- `.knowledge-card`
- `.knowledge-card h3`
- `.knowledge-note-group`
- `.knowledge-note-label`

保持 8px 或以下常规 radius，避免嵌套卡片。

### Task 6: 验证、提交、可选推送

**Files:**
- All files above

- [x] **Step 1: 跑 focused tests**

Run:

```bash
node tests/foundations-roadmap-requirements.mjs
```

Expected: PASS.

- [x] **Step 2: 跑相关回归**

Run:

```bash
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
git diff --check
```

Expected: all PASS / clean.

- [x] **Step 3: 本地静态预览**

Run:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/projects/foundations/` and verify:

- Overview 是 dashboard。
- 普通模块显示 `学习进度 0%`。
- `时间线` 保留。
- `验收标准` 和 `下一步` 不显示。
- `知识笔记` 按概念卡片展示。
- 右栏随 knowledge note 同步。
- 收起左栏后的横线导航有 tooltip 和 hover 邻近线。

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-05-foundations-knowledge-base-reader-redesign.md \
  tests/foundations-roadmap-requirements.mjs \
  projects/foundations/roadmap/modules/*.md \
  projects/foundations/scripts/build-roadmap-data.mjs \
  projects/foundations/roadmap/roadmap-data.json \
  projects/foundations/roadmap/roadmap-reader.js \
  projects/foundations/roadmap/roadmap-reader.css
git commit -m "Redesign foundations as knowledge base reader"
```

Expected: one implementation commit on `codex/foundations-knowledge-base-reader`.

## Self-Review

- Spec coverage: covers progress semantics, Overview dashboard, concept-centric notes, right panel sync, collapsed rail, tests, static build.
- Scope: focused on `projects/foundations/` and one test file; no repo taxonomy changes.
- TDD: Task 1 creates failing requirements before production changes.
- Risk: migrating all modules manually can produce uneven content. The implementation should preserve the existing core content while moving `资源 / 反思 / 面试表达` into `知识笔记`.
