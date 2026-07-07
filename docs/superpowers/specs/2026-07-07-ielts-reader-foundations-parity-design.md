# IELTS Reader Foundations Parity Design

Date: 2026-07-07
Status: awaiting user review before implementation planning

## Context

`projects/language/ielts-academic/` 已经完成 v2：它有结构化 JSON 数据、`notes/`、`journal/`、build script、`site/ielts-data.json` 和一个只读 static reader。当前 reader 更像 SaaS dashboard：左侧 sidebar + 多个 dashboard sections。

用户现在希望做两件事：

- 项目书签页中 `IELTS Academic` 改成中文 **“语言”**，并使用和 `基石`、`记忆与智能体` 相同的中文书签字体。
- IELTS reader 的内容不改，但视觉和交互要基本复用 `projects/foundations/` 的 reader 体验。用户明确选择完整迁移：夜间模式、目录折叠、右侧笔记折叠、全局搜索、右侧平行笔记、高亮/批注、任务勾选状态都要加。

已确认 `projects/foundations/roadmap/roadmap-reader.js` 没有 repo 写回路径。它读取静态 JSON，并把 annotations / tasks 存在浏览器 `localStorage`。IELTS reader 也应保持同样边界：可以存 UI state、annotations 和 task state，但不能写回 Markdown、JSON、GitHub API 或 backend。

## Goals

- 将 `projects/manifest.json` 中 IELTS 项目的展示 title 改为 `语言`，让项目书签页使用中文竖排书签字体。
- 保留 IELTS 项目的 folder、source files、structured data 和学习内容，不改诊断数据、notes、journal、prompts、validation 的语义内容。
- 将 IELTS reader 改造成接近 `Foundations` reader 的页面壳：
  - 顶部 toolbar。
  - 左侧目录 / section rail。
  - 主内容阅读区。
  - 右侧平行笔记面板。
  - 移动端目录和笔记 drawer。
- 在 IELTS reader 中完整迁移 Foundations 的核心交互：
  - theme toggle。
  - left directory collapse。
  - note panel collapse。
  - global search and search overlay。
  - right-side contextual note panel。
  - text highlight / annotation。
  - task checkbox state。
- 保持 `projects/language/ielts-academic/site/ielts-data.json` 仍由 build script 生成，并保持 deterministic build。
- 扩展测试，覆盖书签 title、中文字体路径、reader shell parity、localStorage 边界和无 write-back signals。

## Non-Goals

- 不重写 IELTS 学习内容，不改变 `score-profile.json`、`error-log.json`、`notes/`、`journal/` 的内容含义。
- 不引入 backend、database、GitHub API 写回、token、authenticated write path。
- 不把 browser annotations / tasks 当成 repo source of truth。
- 不抽象出跨项目 shared reader framework；本次优先让 IELTS 复用 Foundations 的体验，不改 Foundations reader 行为。
- 不把 IELTS 数据模型改成 Foundations roadmap 数据模型；只做 reader adaptation。
- 不新增外部 package dependency 或 bundler。
- 不改变 GitHub Pages 的静态部署方式。

## Assumptions

- Repo 根目录是 `/Users/phoenix/Assistant/NeuroScience`。
- `projects/foundations/` 是视觉和交互参考，但不是要被重构的共享组件。
- IELTS reader 仍从 `projects/language/ielts-academic/site/ielts-data.json` 读取数据。
- Browser localStorage 允许保存用户端临时学习交互：
  - `ieltsReader.ui.v1`
  - `ieltsReader.annotations.v1`
  - `ieltsReader.tasks.v1`
- 上述 localStorage 数据只代表当前浏览器状态，不需要同步到 repo。

## Design

### 1. Project Bookmark

`projects/manifest.json` 中 IELTS entry 的 `title` 改为：

```json
"title": "语言"
```

`id` 仍为 `ielts-academic`，`folder` 仍为 `language/ielts-academic/`，`summary` 可以继续说明它是 IELTS Academic 项目。

`projects/index.html` 当前根据 title script 对 Latin 标题使用横排 sans 字体。改成中文 title 后，IELTS bookmark 应自然进入默认中文竖排路径：

- 使用 `--bookmark-calligraphy-font`。
- `writing-mode: vertical-rl`。
- `text-orientation: upright`。
- 字体子集需要覆盖 `语言`。

实现时应更新 `tests/projects-requirements.mjs`，不再期待 `IELTS Academic` 卡片标题，而是期待 `语言`。字体子集断言也要包含 `语言`。

### 2. Reader Shell

`projects/language/ielts-academic/index.html` 改成 Foundations-style shell，保留 IELTS 数据入口：

```html
<body data-page="ielts-academic-reader" data-theme="light">
  <div class="reader-shell" id="reader-shell">
    <div class="search-focus-layer" id="search-overlay" aria-hidden="true"></div>
    <header class="reader-toolbar" id="reader-toolbar">...</header>
    <aside class="reader-sidebar" id="module-directory">...</aside>
    <main class="reader-main" id="reader-main">...</main>
    <aside class="note-panel" id="note-panel">...</aside>
    <aside class="mobile-note-drawer" id="mobile-note-drawer">...</aside>
  </div>
  <script type="module" src="site/ielts-reader.js" data-source="site/ielts-data.json"></script>
</body>
```

The page should keep IELTS identity in labels, but use the same reader composition as Foundations. The visible content should still represent the existing IELTS sections:

- Dashboard
- 8-week swimlane
- Errors
- Notes
- Journal
- Prompt library
- Validation

### 3. Data Mapping

The implementation should adapt existing IELTS data to reader modules without changing source content.

Recommended module mapping:

| Reader module | Source data |
| --- | --- |
| Dashboard | `data.scoreProfile`, `data.scoreHistory`, `data.project.target` |
| 8-week swimlane | `data.checkpoints`, existing weekly plan data in `site/ielts-data.json` |
| Errors | `data.errorLog.errors` |
| Notes | `data.notes` |
| Journal | `data.journal` |
| Prompt library | `data.promptLibrary` |
| Validation | `data.validation`, `data.build.referenceIssues` |

The reader may reshape these into display cards at runtime, but it must not mutate the loaded data as source state.

### 4. Interaction Model

IELTS reader should migrate these Foundations-style interactions:

- **Theme toggle:** store visual theme in `ieltsReader.ui.v1`.
- **Directory collapse:** store collapsed state in `ieltsReader.ui.v1`.
- **Note panel collapse:** store collapsed state in `ieltsReader.ui.v1`.
- **Global search:** search across rendered IELTS module titles, descriptions, notes, journal entries, prompt docs, validation docs and errors. Search results should navigate to the relevant module/card.
- **Contextual note panel:** right panel shows details for the selected module/card. It should not edit repo source data.
- **Highlight / annotation:** text selection inside eligible content cards creates annotations in `ieltsReader.annotations.v1`.
- **Task checkbox state:** checklist-style items, if rendered, can persist checked state in `ieltsReader.tasks.v1`.

The `localStorage` boundary is explicit:

- Allowed: `ieltsReader.ui.v1`, `ieltsReader.annotations.v1`, `ieltsReader.tasks.v1`.
- Not allowed: localStorage keys or data structures that replace `scoreProfile`, `errorLog`, `checkpoints`, `notes`, `journal`, `promptLibrary` or `validation` source files.
- Not allowed: `fetch` with non-GET write intent, GitHub `contents/`, `repos/`, `Authorization`, `githubToken`, `/api` write paths.

### 5. CSS Strategy

`projects/language/ielts-academic/site/ielts-reader.css` should move away from the current SaaS dashboard style and toward Foundations reader tokens and layout:

- Paper texture / subtle grid background.
- `reader-shell` grid with toolbar, directory, main and notes areas.
- Glass controls and small icon buttons.
- Reader sections/cards with compact 8px-or-less radii where card surfaces are used.
- Dark theme token overrides.
- Mobile layout with drawer behavior and no horizontal page overflow.

The implementation can copy relevant selectors from `projects/foundations/roadmap/roadmap-reader.css`, but should rename or adapt only where needed for IELTS. It should not import Foundations CSS directly unless the implementation plan explicitly proves this will not regress Foundations.

### 6. JavaScript Strategy

`projects/language/ielts-academic/site/ielts-reader.js` should keep existing IELTS-specific rendering logic where useful, but reorganize around Foundations reader state and event patterns:

- `state.data`
- `state.currentModule`
- `state.searchQuery`
- `state.activeSectionId`
- `state.activeKnowledgeNoteId` or IELTS equivalent
- `state.annotations`
- `taskState`

The implementation can port Foundations helper functions for:

- `fetchJson`
- `escapeHtml`
- theme / panel state
- search rendering
- annotation storage and rendering
- task state loading/saving
- mobile drawer behavior

IELTS-specific rendering should remain explicit. It should not pretend IELTS modules are Foundations roadmap modules if that creates confusing names or fragile data assumptions.

### 7. Accessibility And Responsive Behavior

- Toolbar buttons must have `aria-label`.
- Collapsible controls must expose `aria-pressed` or equivalent state where meaningful.
- Search input must have accessible label.
- Main content should remain keyboard reachable.
- Mobile layout must preserve access to directory and note panel.
- No important text should be clipped or overlap at 390px mobile width.

## Files In Scope

Expected implementation files:

- `projects/manifest.json`
- `projects/index.html`
- `projects/language/ielts-academic/index.html`
- `projects/language/ielts-academic/site/ielts-reader.css`
- `projects/language/ielts-academic/site/ielts-reader.js`
- `tests/projects-requirements.mjs`
- `tests/ielts-academic-language-project-requirements.mjs`
- `tests/ielts-academic-site-data-requirements.mjs` if additional no-write-back assertions belong there

Optional, only if the implementation needs documentation updates:

- `projects/language/README.md`
- `projects/language/ielts-academic/README.md`

Out of scope:

- `projects/foundations/**`
- IELTS source content under `prompts/`, `diagnostics/*.json`, `notes/`, `journal/`, `validation/`, unless tests reveal a broken reference caused by the visual migration.

## Testing And Verification

Implementation plan should include these verification gates:

```bash
node tests/projects-requirements.mjs
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
git diff --exit-code -- projects/language/ielts-academic/site/ielts-data.json
git diff --check
```

Frontend verification should also include a local static server check:

```bash
python3 -m http.server 8765
```

Then inspect:

```text
http://127.0.0.1:8765/projects/
http://127.0.0.1:8765/projects/language/ielts-academic/
```

Required manual/browser checks:

- Project bookmark shows `语言` in the same visual style as `基石` and `记忆与智能体`.
- IELTS reader loads data from `site/ielts-data.json` without console errors.
- Dashboard, swimlane, errors, notes, journal, prompt library and validation are visible.
- Theme toggle works.
- Directory collapse works.
- Note panel collapse works.
- Search returns relevant IELTS results and navigates to content.
- Highlight / annotation can be created and persists after reload.
- Task checkbox state, where rendered, persists after reload.
- No repo write-back, GitHub token, API write path or source-data localStorage path exists.
- Desktop and 390px mobile have no incoherent overlap or full-page horizontal overflow.

## Acceptance Criteria

- `projects/manifest.json` shows IELTS bookmark title as `语言`.
- `projects/index.html` renders the IELTS bookmark with the Chinese calligraphy bookmark font, not the Latin fallback.
- IELTS reader uses Foundations-style shell and interaction model.
- IELTS source content remains semantically unchanged.
- `site/ielts-data.json` remains build-generated and deterministic.
- Browser localStorage is limited to UI, annotations and task state.
- All listed verification commands pass.
- Feature branch receives code review before merge.

## Risks

- Copying too much Foundations JS can accidentally import Foundations-specific assumptions such as module IDs, note IDs or project IDs. The implementation must use IELTS-specific IDs and localStorage keys.
- Adding annotations and task state increases JS complexity. The plan should keep the first implementation focused on parity, not on a generalized shared reader framework.
- A full reader shell migration can break existing dashboard contract tests if the tests only search for old function names/selectors. Tests should be updated to enforce behavior and reader contract, not stale layout implementation details.
- Direct `file://` opening can fail because the reader fetches JSON. README guidance should continue to recommend GitHub Pages or local static server.

## Implementation Defaults

- IELTS task checkbox state should appear only where the source item naturally represents a task, review action, checklist item or follow-up action. Do not add checkboxes to every informational card.
- Annotation UI should apply inside main content cards. Do not enable selection annotations on navigation controls, toolbar controls, sidebar buttons or search result controls.
