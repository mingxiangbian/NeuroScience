# Project Creation Workflow 设计

Date: 2026-07-06
Status: Approved design, awaiting implementation plan

## Summary

本 spec 设计一个通用的项目创建工作流。目标不是把所有项目都套进同一个网页模板，而是让用户以后创建新项目时，只需要提供主题、内容和目标，Codex 就能按项目类型自动选择目录结构、文档结构、网页呈现方式和验证步骤。

用户已确认的关键方向：

- 需求不只覆盖学习项目，也覆盖工程项目、研究项目、论文阅读项目和混合项目。
- 下次用户输入内容时，不应再从零讨论目录、导航、页面展示和基础交互。
- Foundations 已经调好的 reader 体验可以作为知识型项目的默认呈现方式，但不能强行套到所有项目。
- 工程项目应优先保证可运行、可测试、可迭代，而不是优先做 reader 网页。
- 新项目应遵守当前 `NeuroScience` 仓库的目录职责：`projects/`、`papers/`、`sources/`、`questions/`、`sessions/` 分工不混用。

## Goals

- 建立一套默认项目分流规则：用户只给内容时，Codex 能判断项目属于学习型、论文型、工程型、研究型还是混合型。
- 为每类项目定义默认目录结构、首页职责、文档职责和验证标准。
- 把 Foundations reader 作为知识型项目的默认网页样式，避免后续同类项目重复微调 UI。
- 为工程项目定义不同的默认结构，强调 `README`、`spec`、`plan`、源码、测试和可运行 demo。
- 明确哪些情况需要追问用户，哪些情况可以直接采用默认值。
- 保持纯静态 GitHub Pages 友好；只有工程项目自身确实需要 runtime 时，才引入额外工具链。

## Non-Goals

- 不在本 spec 中实现 CLI、代码生成器或新的 scaffold 脚本。
- 不把现有 Foundations 页面迁移成共享 runtime。
- 不要求所有项目都有网页 reader。
- 不把 `sources/`、`questions/` 或 `sessions/` 的内容塞进项目本体目录。
- 不引入后端、数据库、账号系统或跨设备同步。
- 不把这套规则写成全局 Codex 行为；它只服务当前 `NeuroScience` 仓库。

## Project Type Router

当用户要求“创建一个新项目”但没有指定类型时，Codex 按以下规则判断。

### 1. 知识 / 学习 / 路线图项目

触发信号：

- 用户说“学习”“准备”“路线图”“知识库”“复习”“成长计划”“模块化记录”。
- 内容主体是知识点、资源、任务、阶段、笔记或长期复盘。

默认位置：

```text
projects/{slug}/
```

默认呈现：

- 使用 Foundations 风格的 reader/dashboard 网页。
- `Overview` 只做 dashboard，不承载普通模块的任务、时间线、验证标准或下一步。
- 模块正文以知识结构为主，时间线可以保留但不是主轴。
- 右侧栏显示与当前知识卡关联的学习笔记；没有关联时保持空白。
- 初始学习进度默认 `0`，除非用户明确提供已完成内容。

### 2. 论文 / 专题阅读项目

触发信号：

- 用户说“论文”“paper”“reading notes”“文献阅读”“专题阅读”。
- 内容主体是论文、作者、方法、结果、局限、open questions。

默认位置：

```text
papers/{slug}/
```

默认呈现：

- 使用 paper reader 风格。
- 页面重点是 citation、claim、method、evidence、limitations、takeaway 和 open questions。
- 若该专题产生 source map，放入 `sources/`。
- 若产生长期问题或假设，放入 `questions/{slug}/`。

### 3. 工程 / 工具 / 实验项目

触发信号：

- 用户说“实现”“工具”“app”“agent”“demo”“实验系统”“工程项目”“做一个可以运行的东西”。
- 内容主体是功能、接口、代码、测试、运行方式或实验验证。

默认位置：

```text
projects/{slug}/
```

默认结构：

```text
projects/{slug}/
  README.md
  docs/
    spec.md
    plan.md
  src/
  tests/
```

默认呈现：

- 首页优先是项目说明和运行入口，不默认套 reader。
- 如果需要 GitHub Pages 展示，再增加 `index.html` 或轻量 demo 页面。
- 如果项目同时需要学习笔记，学习页面作为附属文档或独立 reader，不与源码结构混在一起。

默认验证：

- 至少提供可运行命令、测试命令和当前限制。
- 修改后优先跑对应语言或框架的 lint/test/build。

### 4. 研究型项目

触发信号：

- 用户说“研究问题”“假设”“机制”“实验设计”“长期课题”“阶段性结论”。
- 内容主体是问题拆解、证据、竞争假设、实验路径或结论演化。

默认位置：

```text
projects/{slug}/
```

默认结构：

```text
projects/{slug}/
  README.md
  research-roadmap.md
  hypotheses.md
```

配套目录：

- 开放问题放 `questions/{slug}/open-questions.md`。
- 来源地图、书目和链接放 `sources/{slug}-sources.md`。
- 有日期的研究对话放 `sessions/YYYY-MM-DD-{slug}.md`。

默认呈现：

- 如果项目需要公开阅读体验，可以增加 dashboard 或 reader。
- 如果项目主要是内部研究推进，不默认做网页。

### 5. 混合项目

触发信号：

- 用户同时要求工程实现、学习沉淀、论文阅读或研究假设。

默认规则：

- 主体目标决定 `projects/{slug}/` 的首页。
- 工程代码、学习笔记、论文阅读和 open questions 分层放置。
- 项目首页负责互相链接，不把所有内容堆进一个文件或一个页面。

例子：

```text
projects/agent-eval-lab/
  README.md
  docs/spec.md
  docs/plan.md
  src/
  tests/
  learning/
    index.html
    roadmap/
questions/agent-eval-lab/open-questions.md
sources/agent-eval-lab-sources.md
```

## Default User Input Contract

用户下次创建项目时，可以只提供自然语言内容，例如：

```text
创建一个新项目：主题是 RAG eval lab。目标是做一个可以测试 retrieval 和 generation failure 的小工具。下面是我目前的想法……
```

Codex 默认从输入中抽取：

- `title`：项目显示名称。
- `slug`：URL 和目录名。
- `projectType`：知识型、论文型、工程型、研究型或混合型。
- `goal`：项目目标。
- `audience`：自己复习、公开展示、面试作品、研究沉淀或工程使用。
- `sourceContent`：用户给出的原始内容。
- `mustHaveOutputs`：必须生成的页面、文档、代码或测试。

如果用户没有给 `slug`，Codex 用英文短横线命名。中文标题保留在页面和 README 中。

## Clarification Policy

默认少问问题，能根据内容判断就直接执行。只有以下情况需要先追问：

- 项目可能放 `projects/` 或 `papers/`，且放错会影响长期组织。
- 用户要求公开网页，但内容包含不适合公开的信息。
- 工程项目缺少关键 runtime 选择，例如必须在 Python、Node、Rust 中选一个。
- 项目目标互相冲突，例如既要求纯静态 GitHub Pages，又要求服务端持久化数据库。
- 用户明确要求覆盖已有目录，存在覆盖风险。

不需要追问的默认值：

- 知识型项目初始进度为 `0`。
- 新项目默认加入对应目录页。
- 纯展示页面默认使用相对路径，保证 GitHub Pages 可用。
- 不明确是否需要后端时，默认不引入后端。
- 不明确是否需要漂亮首页时，工程项目默认先做可运行项目，不做营销式页面。

## Output Standards By Project Type

### 知识型项目

必须生成：

- 项目目录。
- reader 首页。
- Markdown source。
- generated JSON。
- build script。
- 目录页入口。

必须验证：

- build script 能生成 JSON。
- reader JS 通过 syntax check。
- 目录页包含新项目入口。
- 搜索、模块导航和右侧笔记使用 Foundations 当前交互标准。

### 论文型项目

必须生成：

- paper reader 页面或论文笔记 Markdown。
- citation 和来源链接。
- claim、method、evidence、limitations、takeaway。
- 必要时生成 `questions/` 和 `sources/` 文件。

必须验证：

- 引用链接可追踪。
- 页面路径和 query 参数在 GitHub Pages 下可访问。
- 论文作者结论、用户假设和 Codex 综合判断分开写。

### 工程型项目

必须生成：

- `README.md`：目标、运行方式、测试方式、当前限制。
- `docs/spec.md`：需求和设计。
- `docs/plan.md`：实现步骤。
- 源码和测试目录，除非用户明确只要设计文档。

必须验证：

- 能运行最小 demo 或 smoke test。
- 有明确失败边界和后续工作。
- 不为了展示而牺牲工程结构。

### 研究型项目

必须生成：

- 项目 README 或 research roadmap。
- 假设或问题拆解文件。
- 必要时配套 `questions/`、`sources/`、`sessions/`。

必须验证：

- 证据强度和 claim type 被区分。
- open questions 有 status 和 next action。
- source map 不留在 `projects/` 里。

## Page And UI Defaults

当项目需要网页展示时，默认遵守以下规则：

- 知识型项目使用 Foundations reader 的当前交互：三栏 reader、模块导航、搜索、高亮笔记、右侧关联笔记、折叠横线导航。
- 论文型项目使用 paper reader 的阅读结构。
- 工程项目只在需要 demo 或作品展示时生成网页；网页应直接展示可用体验，不做空泛 landing page。
- 不为所有项目统一添加卡片堆叠、hero 或装饰背景。
- 新页面必须优先保证内容真实、路径稳定、移动端不重叠。

## Implementation Boundary For Future Plan

后续 implementation plan 可以选择两层落地：

1. 文档层：把本工作流固化为 repo-local 指南，让 Codex 下次按此执行。
2. scaffold 层：在 `templates/` 或 `scripts/` 中提供可复用生成器，减少重复复制。

第一阶段推荐先做文档层和最小 scaffold，避免为了通用模板重构现有 Foundations runtime。

## Acceptance Criteria

- 用户下次只给主题和内容时，Codex 能按本 spec 自动判断项目类型。
- 知识型项目默认复用 Foundations 当前 reader 体验，不再反复微调基础 UI。
- 工程项目不会被强行做成知识 reader，而是优先具备可运行结构。
- 论文型、研究型项目遵守 `papers/`、`sources/`、`questions/` 的目录职责。
- 只有高风险或目标冲突时才追问用户。
- 本 spec 没有未决占位符、互相矛盾的要求或超出当前仓库边界的假设。
