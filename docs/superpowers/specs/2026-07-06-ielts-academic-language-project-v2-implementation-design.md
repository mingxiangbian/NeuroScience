# IELTS Academic Language Project v2 Implementation Design

Date: 2026-07-06
Status: awaiting user review before implementation planning

## Context

`projects/language/ielts-academic/` 已经存在 v1：它是一个以 Markdown 为主的 IELTS Academic prompt 与学习计划项目包，包含 Orchestrator、8 个 subagent prompt、诊断模板、8 周计划、error system 和 validation checklist。

用户提供了 v2 设计文档：`/Users/phoenix/Downloads/2026-07-06-ielts-academic-language-project-design-v2.md`。v2 的变化不是小修，而是把当前项目扩成一个完整的个人学习 repository：

- 保留 prompt system 和诊断驱动学习包。
- 新增结构化 `.json` 数据层，用于 score profile、score history、error log 和 checkpoint 状态。
- 新增 `notes/` 与 `journal/`，让技能笔记和自由反思成为一等内容。
- 新增 GitHub Pages 静态网站，把项目渲染成只读 dashboard / reader。
- 新增构建与校验脚本，检查 JSON、frontmatter 和 cross-reference 完整性。

用户选择实现方案 **A：完整 v2 一次落地**。因此本 spec 的目标是定义一次性实现完整 v2 的边界、架构、文件结构、数据流和验证方式。下一步必须先写 implementation plan，再执行具体改动。

## Goals

- 在现有 v1 基础上完整落地 v2，不删除或重组已有 prompt / plan / validation 文档。
- 补齐 v2 指定的 structured data files：`score-profile.json`、`score-history.json`、`error-log.json`、`checkpoint-status.json`。
- 建立 `notes/` 和 `journal/` 系统，并让它们通过 lightweight frontmatter 支持 cross-reference。
- 新增静态网站 `projects/language/ielts-academic/index.html`，通过 GitHub Pages 只读展示 IELTS 项目。
- 新增 build script，将 Markdown、JSON 和 frontmatter 聚合为 `site/ielts-data.json`。
- 新增或扩展测试，覆盖 v2 文件存在性、JSON schema、cross-reference integrity、页面资源、无写回逻辑。
- 将 IELTS Academic 项目加入 `projects/manifest.json`，让项目目录页面可发现它。

## Non-Goals

- 不构建 backend、database、authenticated write path 或 GitHub API 写回。
- 不自动运行多智能体 dispatch，不把 prompt system 变成 runnable orchestration app。
- 不把浏览器 localStorage 用作 score、error、checkpoint 或 journal 的 source of truth。
- 不做 bi-directional link graph engine；只使用 frontmatter fields 和 build-time/client-side index。
- 不把 notes 或 journal 内容作为 Orchestrator 的 planning decision input。
- 不重写现有 Foundations reader，也不抽象出跨项目通用 framework。
- 不承诺 8 周内 guaranteed Overall 8.0；页面和数据仍要显示 target risk。

## Assumptions

- Repo 根目录是 `/Users/phoenix/Assistant/NeuroScience`。
- GitHub Pages 仍从 repo 静态文件直接服务，不需要 bundler。
- IELTS 项目仍位于 `/Users/phoenix/Assistant/NeuroScience/projects/language/ielts-academic/`。
- 现有 v1 文档内容保留为主要 human-authored source。
- `.json` 文件是 rendering-friendly structured counterpart，但不得与 Markdown template 语义冲突。
- 页面可以使用 plain HTML / CSS / JavaScript，与现有 repo 的静态页面风格一致。

## Architecture

实现分三层。

### 1. Content Source Layer

`projects/language/ielts-academic/` 是唯一 source of truth。该层包含：

- 已有 prompt / diagnostics / plans / errors / validation Markdown。
- 新增 structured data：
  - `diagnostics/score-profile.json`
  - `diagnostics/score-history.json`
  - `diagnostics/error-log.json`
  - `plans/checkpoint-status.json`
- 新增 personal learning content：
  - `notes/README.md`
  - `notes/listening/`
  - `notes/reading/`
  - `notes/writing/`
  - `notes/speaking/`
  - `notes/vocabulary/`
  - `notes/grammar/`
  - `journal/README.md`
  - `journal/entries/`

Notes 和 journal 可以包含示例条目，但示例必须明显是 starter content，不伪造用户真实学习记录。

### 2. Build And Validation Layer

新增：

```text
projects/language/ielts-academic/scripts/build-ielts-data.mjs
```

脚本职责：

- 读取 required JSON data files。
- 扫描 `notes/**/*.md` 和 `journal/entries/*.md`。
- 解析 lightweight YAML frontmatter。
- 聚合 prompt library、validation docs、plan metadata 和 structured data。
- 校验 `related_errors` 指向 `diagnostics/error-log.json` 中存在的 error ID。
- 校验 `related_notes` 指向真实 note path 或 stable note ID。
- 校验 error status 只允许 `active`、`improving`、`fixed`、`regressed`。
- 生成：

```text
projects/language/ielts-academic/site/ielts-data.json
```

脚本应使用 Node.js standard library，不引入 package dependency。

### 3. Static Website Layer

新增：

```text
projects/language/ielts-academic/index.html
projects/language/ielts-academic/site/ielts-reader.css
projects/language/ielts-academic/site/ielts-reader.js
projects/language/ielts-academic/site/ielts-data.json
```

页面是 read-only rendering layer。数据流是：

```text
Markdown / JSON source files
  -> scripts/build-ielts-data.mjs
  -> site/ielts-data.json
  -> index.html + site/ielts-reader.js
```

浏览器不写回 repo，不请求 GitHub write API，不持有 token。

## File Structure

目标结构是在现有 v1 上补齐这些新增文件和目录：

```text
projects/language/ielts-academic/
  index.html
  diagnostics/
    score-profile.json
    score-history.json
    error-log.json
  plans/
    checkpoint-status.json
  notes/
    README.md
    listening/
    reading/
    writing/
    speaking/
    vocabulary/
    grammar/
  journal/
    README.md
    entries/
  scripts/
    build-ielts-data.mjs
  site/
    ielts-data.json
    ielts-reader.css
    ielts-reader.js
```

`projects/language/README.md` 和 `projects/language/ielts-academic/README.md` 需要更新入口链接，指向新静态页面和新的 notes / journal / data workflow。

`projects/manifest.json` 需要新增 IELTS Academic 项目 entry，除非实现时发现项目目录页面有其他显式排除规则。

## Data Model

### `score-profile.json`

用途：渲染 Dashboard 和 target gap。

最低字段：

- `target.overall`
- `target.perSkillFloor`
- `currentEstimate.overall`
- `skills[].id`
- `skills[].label`
- `skills[].estimatedBand`
- `skills[].confidence`
- `skills[].evidenceBasis`
- `skills[].unverifiedDimensions`
- `runMode`
- `lastUpdated`

如果某技能证据不足，`estimatedBand` 可以为 `null`，但必须有 `confidence: "low"` 和明确的 `unverifiedDimensions`。

### `score-history.json`

用途：展示 band 变化曲线和 Week 4/6 trajectory check。

最低字段：

- `entries[].date`
- `entries[].week`
- `entries[].runMode`
- `entries[].skills`
- `entries[].notes`

初始文件可以只包含 baseline starter entry，但必须明确是 template / initial state，不伪造真实 mock-test 成绩。

### `error-log.json`

用途：渲染 Errors Board 和 cross-reference resolver。

最低字段：

- `errors[].id`
- `errors[].skill`
- `errors[].impact`
- `errors[].status`
- `errors[].description`
- `errors[].evidence`
- `errors[].nextReview`
- `errors[].reviewMethod`

允许的 `impact`：`high`、`medium`、`low`。

允许的 `status`：`active`、`improving`、`fixed`、`regressed`。

### `checkpoint-status.json`

用途：渲染 8-week swimlane checkpoint markers。

最低字段：

- `checkpoints[].week`
- `checkpoints[].name`
- `checkpoints[].purpose`
- `checkpoints[].status`
- `checkpoints[].decision`
- `checkpoints[].evidenceRequired`

Week 2、4、6、8 必须全部存在。

### Notes Frontmatter

Notes 使用 lightweight frontmatter：

```yaml
---
id: writing/task-2-argument-development
skill: writing
topic: task-2-argument-development
date: 2026-07-06
related_errors: [E001]
---
```

`id` 应稳定，推荐等于相对 path 去掉 `.md`。`related_errors` 可以为空数组。

### Journal Frontmatter

Journal 使用 lightweight frontmatter：

```yaml
---
date: 2026-07-06
related_errors: [E001]
related_notes: [writing/task-2-argument-development]
---
```

Journal 不影响 Orchestrator planning，只作为 reflection layer。

## Website Sections

`index.html` 应包含一个可直接打开的 IELTS project reader，不做 marketing landing page。

### Dashboard

展示：

- Target：Overall 8.0 / each skill 7.5+。
- Current estimated score profile。
- 每个 skill 到 target 的 gap。
- 下一个 checkpoint。
- 当前 high-risk skills。
- Run mode 和 score confidence 提示。

### 8-Week Swimlane

展示 Weeks 1-8。行至少包括：

- Listening
- Reading
- Writing
- Speaking
- Errors

Week 2、4、6、8 显示 checkpoint marker，并可展开 purpose / decision / evidence required。

### Errors Board

按 status 分组：

- active
- improving
- fixed
- regressed

支持按 skill 和 impact 过滤。每个 error card 显示 ID、impact、evidence、next review 和 review method。

### Notes

按 skill 分类展示 notes，支持关键词搜索。Note 中的 `related_errors` 渲染为 chips，能定位到 Errors Board 中对应 error。

### Journal

倒序展示 journal entries。`related_notes` 和 `related_errors` 渲染为 chips，能定位到相关 note / error。

### Prompt Library

只读展示：

- Orchestrator
- Run modes
- Interaction protocol
- Output contract
- Calibration and validation
- 8 个 agent prompts

### Validation

展示：

- Output contract checklist
- Dry-run test cases
- Examiner calibration checklist
- Build-time cross-reference integrity status

Validation 页面不需要执行测试，只显示 repository 中的 validation content 和 build summary。

## UI Constraints

- 复用 repo 已有 minimalist academic 静态页面气质，但 IELTS 页面不需要复制 Foundations 的全部交互。
- 页面以实用 dashboard / reader 为主，不做宣传页。
- 需要响应式布局，至少桌面和窄屏都能阅读。
- 使用文本、表格、chips、simple bars、swimlane grid 即可，不引入 charting library。
- CSS 避免大面积单一色系，避免过度装饰。
- 关键 UI 文案使用中文，IELTS terms、file paths、prompt names 保持英文。

## Testing And Verification

实现计划应先写或扩展测试，再实现。

### Existing Test Extension

扩展：

```text
tests/ielts-academic-language-project-requirements.mjs
```

覆盖：

- v2 新增 files / directories 存在。
- target 仍明确为 Overall 8.0 / each skill 7.5+。
- `notes/`、`journal/`、`scripts/`、`site/` 均有入口。
- `index.html` 加载 `site/ielts-reader.css` 和 `site/ielts-reader.js`。
- `projects/manifest.json` 包含 IELTS Academic entry。

### New Data Test

新增：

```text
tests/ielts-academic-site-data-requirements.mjs
```

覆盖：

- 运行 `node projects/language/ielts-academic/scripts/build-ielts-data.mjs`。
- `site/ielts-data.json` 可解析。
- `scoreProfile`、`scoreHistory`、`errorLog`、`checkpoints`、`notes`、`journal`、`promptLibrary`、`validation` 都存在。
- notes / journal cross-reference 全部可解析。
- error status 和 impact 值在 allowlist 内。
- page JS 不包含 `githubToken`、`Authorization`、`contents/`、`repos/`、`fetch("/api` 等写回或 backend API 信号。

### Final Verification Commands

实现完成后至少运行：

```bash
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
git diff --check
```

如果修改 `projects/manifest.json`，还要运行：

```bash
node tests/projects-requirements.mjs
```

## Implementation Order

后续 implementation plan 应按此顺序展开：

1. 写失败测试，锁定 v2 文件、页面和数据契约。
2. 补 structured JSON files 和 notes / journal 骨架。
3. 写 `build-ielts-data.mjs`，生成 `site/ielts-data.json`。
4. 写 `index.html`、`ielts-reader.css`、`ielts-reader.js`。
5. 更新 `README.md` 入口和 `projects/manifest.json`。
6. 跑全部 narrow verification。
7. 提交实现分支并准备 merge / push。

## Risks And Mitigations

- **Scope risk:** v2 同时包含内容层、数据层和页面层。Mitigation：测试先行，按文件层分 commit，避免一次大 diff 难以 review。
- **Data truth conflict:** Markdown template 和 JSON 可能语义分叉。Mitigation：README 明确 JSON 是 rendering counterpart；weekly review 时同步更新。
- **False personal data risk:** starter JSON 可能看起来像真实分数。Mitigation：初始数据必须标记为 `initial` 或 `template`，confidence 低，避免伪造真实成绩。
- **Static site overreach:** 页面可能变成复杂 app。Mitigation：不引入 backend、framework、write path 或 link graph engine。
- **Cross-reference fragility:** note IDs 和 paths 可能漂移。Mitigation：build script 每次校验 references，失败时阻止把数据视为有效。

## Success Criteria

- 用户打开 `/Users/phoenix/Assistant/NeuroScience/projects/language/ielts-academic/README.md` 能理解 v2 项目如何使用。
- 用户打开 `/Users/phoenix/Assistant/NeuroScience/projects/language/ielts-academic/index.html` 能浏览 Dashboard、8-week swimlane、errors、notes、journal、prompt library 和 validation。
- `site/ielts-data.json` 完全由 repo 中 Markdown / JSON source 生成。
- Notes 和 journal 能被搜索、分类、交叉引用。
- Error board 能按 status / skill / impact 展示。
- 页面没有 score/error/checkpoint 写回逻辑。
- 所有指定 verification commands 通过。
