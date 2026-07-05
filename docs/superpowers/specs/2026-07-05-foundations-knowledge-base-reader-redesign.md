# Foundations Knowledge Base Reader 改造设计

Date: 2026-07-05
Status: Draft spec, awaiting user review

## Summary

本 spec 设计 `projects/foundations/` 的第二轮信息架构改造。当前页面已经具备三栏 reader、模块导航、搜索和静态数据构建，但它仍然偏“roadmap 展示页”：进度语义不准、Overview 像普通模块、右栏内容有固定填充感、折叠后的横线章节导航没有完全对齐参考页。

本轮目标是把 Foundations 从“面试计划页面”推进为长期面试知识库：左侧负责导航，中间负责模块知识正文，右侧负责跟随当前 section 的知识旁注。学习沉淀不按日期写成流水账，而按知识概念组织成可复习的 `知识笔记`。

## Goals

- 将页面主语义从 `roadmap progress` 改为 `learning progress`，用户未开始学习时进度从 `0%` 开始。
- 将 `Overview` 改为 dashboard，不再按普通模块展示 `任务 / 时间线 / 验收标准 / 下一步`。
- 保留每个普通模块的 `时间线`，用于计划节奏和阶段安排。
- 删除普通模块中的 `验收标准` 和 `下一步` section，避免项目管理模板感。
- 用按概念组织的 `知识笔记` 替代固定 `资源 / 反思 / 面试表达` 三段。
- 右侧栏根据当前正文 section 或当前知识点展示相关资料、易错点、面试转译和复习提示；没有内容的分组不显示。
- 折叠左栏后的横线章节导航对齐 `papers/shared` 的交互：居中、tooltip、active、hover 邻近线联动。
- 保持纯静态 GitHub Pages 架构：Markdown source -> build script -> JSON -> browser render。

## Non-Goals

- 不引入网页内编辑器、数据库、账号系统、后端或 browser storage。
- 不把学习记录设计成按日期倒序的日记系统。
- 不删除现有 `时间线` 内容。
- 不重组 `projects/`、`papers/`、`sources/`、`questions/`、`sessions/` 的长期目录边界。
- 不在本轮加入 embedding search、LLM search、技能树或图数据库。
- 不把 `Foundations` 拆出 `projects/`，它仍然是项目核心页面。

## Current Problems

### Progress Mislabeling

当前 frontmatter 中的 `progress` 值来自路线图整理程度或主观准备估计，但页面文案显示为“本模块进度”。这会误导用户以为已经学完一部分。对于尚未系统学习的模块，真实学习进度应为 `0%`。

### Overview Is Treated Like A Module

当前 `overview.md` 包含普通模块的 `任务 / 时间线 / 验收标准 / 下一步`。这会让 Overview 像一个大模块，而不是总览和 dashboard。Overview 应负责聚合状态，而不承载模块级学习内容。

### Right Panel Is Too Rigid

当前右栏固定显示 `资源 / 反思 / 面试表达`。问题是：

- `资源` 里混入了阅读目的和面试用途。
- `反思` 在用户尚未学习时不真实，更像“易错点”或“提醒”。
- `面试表达` 有价值，但不应该强制每个模块都显示。
- 固定三段会造成“为了放而放”的感觉。

### Knowledge Notes Need Concept Structure

用户明确希望学习沉淀以知识形式记录，而不是时间形式记录。因此不应设计 `2026-07-05 学了什么` 这样的主结构。更合适的是按概念建卡片，例如 `RAG evaluation`、`memory write policy`、`tool calling failure recovery`。

### Collapsed Rail Does Not Match Reference Reader

当前折叠左栏后的横线导航是简化版。参考页 `papers/shared` 的 rail 包含居中布局、tooltip、hover 邻近线联动和更克制的 active 状态。Foundations 应复用同一交互语言。

## Considered Approaches

### Approach A: Minimal Copy Fix

只把 `progress` 改成 `0`，重命名右栏标题，补 tooltip。

优点：改动最小。

缺点：没有解决 Overview 和右栏数据模型问题，后续继续维护时仍会出现内容硬塞。

### Approach B: Timeline-Centric Learning Log

把每次学习追加为日期日志，右栏显示最近学习记录。

优点：容易写，适合记录过程。

缺点：用户已明确不希望按时间记录知识；长期复习时需要在日期堆里找概念，不适合作为知识库。

### Approach C: Concept-Centric Knowledge Base

保留模块与时间线，但新增按概念组织的 `知识笔记`。右栏从知识笔记中抽取旁注，Overview 改 dashboard。

优点：符合长期复习和面试准备；结构稳定；不会丢掉原来的计划节奏。

缺点：需要调整 Markdown contract、build script 和 reader rendering。

选择：采用 Approach C。

## Information Architecture

### Left Expanded Navigation

展开状态左栏仍按稳定能力模块导航：

1. `Overview`
2. `Coding`
3. `LLM Systems`
4. `Agent Design`
5. `RAG & Memory`
6. `Evals & Debugging`
7. `Research Reading`
8. `Behavioral / Strategy`
9. `Logs`

左栏不再承担主要进度展示职责。模块名和当前选中态足够；详细进度放在 Overview dashboard 和模块 header。

### Left Collapsed Rail

收起状态显示当前模块的 section rail，而不是模块列表。

行为要求：

- rail 垂直居中，视觉对齐 `papers/shared/reader.css`。
- 每条横线对应当前模块的一个主 section。
- hover 当前线时当前线变长，相邻线轻微变长。
- hover 显示 tooltip，内容为 section title。
- active 状态只做颜色高亮，不强行变粗成“进度条”。
- JS 渲染 `<span class="section-tooltip">section title</span>`，而不是只依赖 `title` attribute。

### Center Content

普通模块的中间正文结构：

```md
## 目标

## 当前状态

## 核心知识

## 任务

## 时间线

## 知识笔记
```

保留 `时间线`，因为它负责计划节奏。删除 `验收标准` 和 `下一步`，因为它们和 `任务 / 时间线 / 知识笔记` 重复，并让页面像项目管理模板。

### Knowledge Notes

`知识笔记` 按概念组织，不按日期组织。

推荐 Markdown 结构：

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

- 能否解释 bad retrieval、bad generation 和 bad citation 的区别？
```

每个 `###` 概念就是一个 knowledge card。build script 应把它解析为结构化 `knowledgeNotes`，供正文和右栏同时使用。

### Right Note Panel

右栏不再固定渲染 `资源 / 反思 / 面试表达` 三组。它改为当前 section 的旁注区。

数据来源优先级：

1. 如果当前 section 是 `知识笔记` 中的某个 concept，右栏显示该 concept 的旁注。
2. 如果当前 section 不是 concept，但存在与 section title 匹配的 note card，显示匹配 card。
3. 如果没有匹配 card，显示模块级精选旁注。
4. 如果仍没有内容，右栏显示空状态，不硬造分类。

右栏允许的分组：

- `相关资料`
- `关键提醒`
- `面试转译`
- `复习提示`

分组为空时不显示。`关键提醒` 取代当前不真实的 `反思`，因为它可以包含易错点、判断标准和陷阱，但不假装用户已经学过。

## Overview Dashboard

`Overview` 是特殊页面，不使用普通模块 section contract。

它展示：

- 目标岗位：`Agent / LLM Systems Engineer`。
- 准备策略：coding、implementation、system design、eval、interview expression 的优先级。
- 总体学习进度：从所有模块 `learning_progress` 聚合，初始为 `0%`。
- 模块状态表：模块名、学习进度、状态、当前重点。
- 当前优先模块：例如 `Coding`、`Agent Design`、`RAG & Memory`、`Evals & Debugging`。
- 计划节奏：保留原 30/45/60-day plan 的摘要。
- 待补知识：从各模块 `知识笔记` 或空白处汇总出的缺口。

Overview 不显示普通模块的 `验收标准` 和 `下一步`。

## Data Model

### Frontmatter

普通模块 frontmatter 改为：

```yaml
---
id: rag-memory
title: RAG & Memory
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: high
---
```

字段语义：

- `learning_progress`: 用户真实学习完成度，初始为 `0`。
- `status`: `not-started`、`learning`、`review`、`done`。
- `priority`: 面试准备优先级，不等于学习状态。

不再使用 `progress` 表示学习进度。如果 implementation 需要兼容旧数据，可在 build script 中临时把缺失的 `learning_progress` 视为 `0`，但页面文案只显示新语义。

### Generated JSON

模块 JSON 需要包含：

```json
{
  "id": "rag-memory",
  "title": "RAG & Memory",
  "status": "not-started",
  "learningProgress": 0,
  "priority": "high",
  "sections": {
    "目标": "...",
    "当前状态": "...",
    "核心知识": "...",
    "任务": "...",
    "时间线": "...",
    "知识笔记": "..."
  },
  "knowledgeNotes": [
    {
      "id": "rag-memory-rag-evaluation",
      "title": "RAG evaluation",
      "summary": "retrieval quality 要先于 generation quality 单独评估。",
      "resources": ["Lewis et al. RAG"],
      "reminders": ["只看最终答案正确率会掩盖 retrieval failure。"],
      "interview": ["I would evaluate retrieval before generation..."],
      "reviewPrompts": ["能否解释 bad retrieval、bad generation 和 bad citation 的区别？"]
    }
  ],
  "searchEntries": []
}
```

`searchEntries` 应覆盖普通 section 和 knowledge note。搜索结果点击 knowledge note 时，应跳转到中间正文对应 concept，并同步右栏。

## Content Migration Rules

### Ordinary Modules

对 `coding.md`、`llm-systems.md`、`agent-design.md`、`rag-memory.md`、`evals-debugging.md`、`research-reading.md`、`behavioral-strategy.md`、`logs.md`：

- 保留 `目标`、`当前状态`、`核心知识`、`任务`、`时间线`。
- 删除 `验收标准` 和 `下一步` section。
- 把原 `资源`、`反思`、`面试表达` 合并整理进 `知识笔记`。
- 合并时按概念组织，不按原标题机械拼接。
- 若某个模块暂时没有真实学习内容，也可以先放少量“关键提醒”和“面试转译”，但不使用“反思”这个标题。

### Overview

`overview.md` 改为 dashboard source。原来的岗位信号、Supervisor synthesis、30/45/60-day plan 应保留，但呈现为总览，而不是普通 section。

Overview 可以保留计划节奏，但不保留普通模块式 `任务 / 验收标准 / 下一步`。

### Timeline

所有已有 `时间线` 内容保留。它继续代表计划节奏，不代表知识沉淀。

## Rendering Behavior

### Module Header

模块 header 显示：

- module title
- status
- priority
- learning progress

文案必须明确为“学习进度”。初始为 `0%` 时不应显得异常。

### Timeline Rendering

`时间线` 继续渲染为 visual timeline。它不参与 learning progress 自动计算。

### Knowledge Notes Rendering

中间正文中的 `知识笔记` 应以 concept cards 或 compact sections 呈现。每个 card 需要稳定 anchor，用于搜索结果、rail 和右栏同步。

### Right Panel Sync

滚动到某个 knowledge card 或点击搜索结果后：

- 中间正文定位到该 card。
- 左侧 collapsed rail active 状态更新。
- 右栏展示该 card 的 `相关资料 / 关键提醒 / 面试转译 / 复习提示`。

如果当前 section 不是 knowledge card，右栏显示模块级旁注或空状态。

## Build Script Requirements

`projects/foundations/scripts/build-roadmap-data.mjs` 需要：

- 读取 `learning_progress`，并校验为 `0-100` 的数字。
- 接受 `status` 为 `not-started / learning / review / done`。
- 不再要求每个模块有 `验收标准` 和 `下一步`。
- 解析 `## 知识笔记` 下的 `### concept`。
- 从 concept 中识别 `核心理解`、`常见误区`、`相关资料`、`面试转译`、`复习提示`。
- 为每个 concept 生成稳定 `id`。
- 将普通 section 和 concept 都纳入 search index。

## Testing And Verification

更新 `tests/foundations-roadmap-requirements.mjs`，覆盖：

- 所有普通模块使用 `learning_progress`，初始可为 `0`。
- 不再要求 `验收标准` 和 `下一步`。
- `时间线` 仍存在。
- 至少一个模块生成 `knowledgeNotes`。
- 右栏渲染不再依赖固定 `资源 / 反思 / 面试表达`。
- Overview 被标记为 dashboard 或能生成 dashboard 数据。
- collapsed rail 生成 `.section-tooltip`。
- CSS 包含参考页式 rail 行为：居中、tooltip、hover 邻近线、active 高亮。
- 搜索能返回 knowledge note 级别结果。

手动验证：

- 打开 `projects/foundations/`。
- Overview 第一屏像 dashboard，而不是普通文章。
- 普通模块显示 `学习进度 0%`。
- `时间线` 仍显示。
- `验收标准` 和 `下一步` 不再出现在普通模块正文。
- 滚动或点击 knowledge note 时，右栏内容跟随变化。
- 左栏收起后横线导航视觉接近 `papers/brain-memory-for-ai-agents/`。

## Implementation Boundaries

本 spec 只要求改 `projects/foundations/` 及其测试：

- `projects/foundations/roadmap/modules/*.md`
- `projects/foundations/scripts/build-roadmap-data.mjs`
- `projects/foundations/roadmap/roadmap-data.json`
- `projects/foundations/roadmap/roadmap-reader.js`
- `projects/foundations/roadmap/roadmap-reader.css`
- `tests/foundations-roadmap-requirements.mjs`

不修改 `papers/shared/reader.*`，只参考其 rail behavior。

## Acceptance Criteria

- 页面语义上是长期知识库，而不是单纯计划表。
- 用户看到的进度从真实学习进度出发，未学习模块为 `0%`。
- Overview 是 dashboard。
- 普通模块保留 `时间线`，删除 `验收标准` 和 `下一步`。
- `知识笔记` 按概念组织，支持长期复习。
- 右栏不是固定填充，而是当前知识点旁注。
- collapsed rail 与参考 reader 的交互语言一致。
- 全部改动保持纯静态部署和现有 repo 目录边界。
