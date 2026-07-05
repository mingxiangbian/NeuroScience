# Foundations Roadmap Reader 设计

Date: 2026-07-05
Status: Approved design, awaiting implementation plan

## Summary

本 spec 设计 `projects/foundations/` 的 roadmap 网页化方案。目标是把现有 `llm-agent-engineer-roadmap.md` 做成类似 `papers/brain-memory-for-ai-agents/` 的三栏 reader，但语义从 paper reading 改为长期面试成长计划。

用户已确认的关键方向：

- `projects/foundations/index.html` 直接成为 roadmap reader。
- `README.md` 和 `multi-agent-planner.md` 保留为 Markdown 文件，但不作为首页主体验。
- 左侧导航按能力模块组织，而不是按周或日期组织。
- 页面第一版是纯静态展示，不做网页内勾选、不写 `localStorage`、不接后端。
- 内容源采用 Markdown + build script + generated JSON 的混合方案。
- 第一版完整迁移现有 `llm-agent-engineer-roadmap.md` 的关键信息，不只迁移骨架。

## Goals

- 把 `projects/foundations/` 从文档卡片页升级为可阅读、可搜索、可长期维护的 roadmap reader。
- 让用户日常维护时继续写 Markdown，而不是手写 JSON。
- 让网页读取结构化 JSON，避免浏览器运行时解析自由格式 Markdown。
- 将现有 672 行 roadmap 内容按能力模块完整拆分，保留知识地图、计划、coding、system design、reading、mock、drills、projects 和 strategy 信息。
- 保持 GitHub Pages 纯静态部署路径，不引入服务端依赖。
- 复用 paper reader 的视觉语言：左侧目录、中间主内容、右侧平行笔记、顶部搜索、主题切换、折叠侧栏。

## Non-Goals

- 不把 `README.md` 和 `multi-agent-planner.md` 转成 reader 模块。
- 不做在线编辑器、任务勾选保存、账号系统、后端、数据库或 AI provider。
- 不把每条任务状态存在浏览器里。
- 不把 roadmap 变成严格日历或打卡 app。
- 不重写 `papers/brain-memory-for-ai-agents/` 的 reader 数据模型。
- 不在第一版引入 embedding search、LLM search、Mermaid editor 或可视化技能树。
- 不重组 `projects/`、`papers/`、`sources/`、`questions/` 的长期目录边界。

## Reader Information Architecture

### Main Navigation

左侧导航使用稳定的能力模块，数量应长期保持有限：

1. `Overview`
2. `Coding`
3. `LLM Systems`
4. `Agent Design`
5. `RAG & Memory`
6. `Evals & Debugging`
7. `Research Reading`
8. `Behavioral / Strategy`
9. `Logs`

这个结构比时间轴更适合长期个人项目。时间会持续增长，但能力模块是稳定集合。用户后续第 20 周、第 30 周的记录应继续落入对应模块，而不是膨胀出大量周目录。

### Module Page Shape

每个模块的中间主内容包含：

- 当前状态
- 能力目标
- 核心知识
- 练习任务
- 时间线记录
- 验收标准
- 下一步

右侧平行笔记栏包含：

- 推荐资源
- 面试表达
- 常见坑
- 反思笔记
- 相关项目证据

### Dashboard And Logs

`Overview` 是总览页：

- 总目标：Agent / LLM Systems Engineer。
- 当前优先级。
- 各模块 progress。
- 近期动作。
- 30/45/60-day plan 的跨模块摘要。

`Logs` 是独立复盘页：

- 用于跨模块复盘。
- 用于暂时不知道归入哪个模块的想法。
- 按时间倒序或时间线顺序展示。
- 不承担主导航组织职责。

## Source Data Design

### File Structure

目标文件结构：

```text
projects/foundations/
  index.html
  README.md
  multi-agent-planner.md
  llm-agent-engineer-roadmap.md
  roadmap/
    modules/
      overview.md
      coding.md
      llm-systems.md
      agent-design.md
      rag-memory.md
      evals-debugging.md
      research-reading.md
      behavioral-strategy.md
      logs.md
    roadmap-data.json
  scripts/
    build-roadmap-data.mjs
```

`llm-agent-engineer-roadmap.md` 保留为原始完整路线图和历史参考。`roadmap/modules/*.md` 是后续日常维护入口。`roadmap/roadmap-data.json` 是 build 输出，页面只读取该 JSON。

### Module Markdown Contract

每个模块文件使用 frontmatter + 固定二级标题：

```md
---
id: coding
title: Coding
status: in-progress
progress: 35
last_updated: 2026-07-05
priority: high
---

## 目标

## 当前状态

## 核心知识

## 任务

## 时间线

## 资源

## 反思

## 面试表达

## 验收标准

## 下一步
```

允许某些模块没有所有标题，但 build script 必须输出空字符串或空数组，而不是让页面报错。

### Generated JSON Shape

`roadmap-data.json` 建议包含：

```json
{
  "generatedAt": "2026-07-05T00:00:00.000Z",
  "project": {
    "id": "foundations",
    "title": "基石",
    "targetRole": "Agent / LLM Systems Engineer"
  },
  "modules": [
    {
      "id": "coding",
      "title": "Coding",
      "status": "in-progress",
      "progress": 35,
      "lastUpdated": "2026-07-05",
      "priority": "high",
      "sections": {
        "目标": "<p>把 coding 能力转成可测量的面试信号。</p>",
        "当前状态": "<p>进行中，优先补强 Python 和 TypeScript 实现。</p>",
        "任务": "<ul><li>完成 graph、heap、DP 基础题组。</li></ul>",
        "时间线": "<ul><li>2026-07-05: 建立 Foundations roadmap reader 结构。</li></ul>",
        "资源": "<ul><li>LeetCode patterns and agent implementation drills.</li></ul>",
        "反思": "<p>记录卡住点和下一轮训练调整。</p>",
        "面试表达": "<p>用约束、tradeoff、failure mode 解释实现选择。</p>"
      },
      "searchText": "coding Python TypeScript graph heap DP implementation drills"
    }
  ]
}
```

页面不需要知道 Markdown 的原始结构，只消费 `modules` 和 `sections`。

## Content Migration Rules

第一版必须完整迁移现有 roadmap 的关键信息。允许轻微重排，但不应丢失原文中的主干内容。

### `overview.md`

承接：

- `Profile And Target`
- `Supervisor Synthesis`
- `30/45/60-Day Plan`
- `Project Recommendations`
- `Weekly Review Checklist`

用途：

- 总目标和整体节奏。
- 每个模块的高层优先级。
- 跨模块的 30/45/60 天安排。

### `coding.md`

承接：

- `Knowledge Map` 中的 `Coding Fundamentals`
- `Python / TypeScript Implementation`
- `Coding Plan`
- `Mock Interview Set` 中的 `Coding`
- `Mini Implementation Drills` 中偏 implementation 的题目
- optional Rust log parser 作为 extension

### `llm-systems.md`

承接：

- `Knowledge Map` 中的 `LLM Systems`
- `System Design Plan` 中通用 LLM production 部分
- `Research Reading List` 中服务、推理、post-training 相关内容
- `Mock Interview Set` 中的 `LLM Fundamentals`

### `agent-design.md`

承接：

- `Knowledge Map` 中的 `Agent Systems`
- `Case 2: Design An Agent Runtime With Tool Calling`
- `Case 6: Design A Safe Tool Execution Layer`
- `Tool Router`
- `TypeScript Agent Interface`
- `Streaming Wrapper`

### `rag-memory.md`

承接：

- `Knowledge Map` 中的 `RAG And Memory`
- `Case 1: Design A Production RAG System`
- `Case 3: Design Long-Term Memory For A Personal Assistant`
- `Retrieval Evaluator`
- `Memory Store`

### `evals-debugging.md`

承接：

- `Knowledge Map` 中的 `Eval And Debugging`
- `Case 4: Design An Eval Harness For Agent Regressions`
- `Case 5: Design Trace Debugging For Multi-Step LLM Workflows`
- `Agent Trace Logger`
- `Eval Harness`

### `research-reading.md`

承接：

- `Research Reading List`
- LLM theory、post-training、reasoning、agent/memory、evals 的论文和概念卡片
- 每篇阅读材料应附带“面试中怎么用”的短说明

### `behavioral-strategy.md`

承接：

- `Mock Interview Set` 中的 `Behavioral And Project Deep Dive`
- `Strategy Rubric`
- 项目叙事、失败案例、tradeoff 表达、resume signal

### `logs.md`

第一版可以从 `Weekly Review Checklist` 和现有计划中提炼初始条目。后续作为跨模块复盘和未归类想法入口。

## Build Script Design

`projects/foundations/scripts/build-roadmap-data.mjs` 职责：

- 读取 `projects/foundations/roadmap/modules/*.md`。
- 解析 frontmatter。
- 按 `## ` 二级标题切分正文。
- 将 Markdown section 转成安全 HTML。
- 生成 `roadmap/roadmap-data.json`。
- 生成 `searchText`，供页面关键词搜索使用。
- 对必需字段做校验：`id`、`title`、`status`、`progress`、`last_updated`。

实现可以优先使用 repo 可用的 Node 标准库和轻量自写解析逻辑。frontmatter 和二级标题格式固定，没必要引入大型 static-site generator。

### Build Validation

脚本失败条件：

- 模块文件缺少 frontmatter。
- `id` 与文件名预期不一致。
- `progress` 不是 0 到 100 的数字。
- `status` 不在允许集合：`not-started`、`in-progress`、`review`、`done`。
- 至少一个核心模块缺失。
- 生成 JSON 后无法 `JSON.parse`。

## Page Design

### HTML Entry

`projects/foundations/index.html` 替换当前文档卡片页，成为 reader shell。

页面可以复用 paper reader 的结构概念：

- `reader-shell`
- `reader-toolbar`
- `reader-sidebar`
- `reader-main`
- `note-panel`
- `mobile-note-drawer`

但不应直接复用 `papers/shared/reader.js` 的 paper-specific state，因为该脚本写死了 `PROJECT_ID = "brain-memory-for-ai-agents"`，并假设存在 paper/chunk/embedding 数据。

### CSS Strategy

推荐做法：

- 复用 paper reader 的视觉语言和 class 命名。
- 可新增 `projects/foundations/roadmap/roadmap-reader.css`，避免污染 `papers/shared/reader.css`。
- 如果抽出真正通用的 CSS，需要保持小范围，只抽 layout/token，不抽 paper-specific chunk 样式。

第一版更稳的边界是：Foundations reader 自己拥有 CSS 文件，视觉贴近 paper reader，但不和 paper reader 共用行为脚本。

### JS Strategy

新增 `projects/foundations/roadmap/roadmap-reader.js`：

- 加载 `roadmap/roadmap-data.json`。
- 渲染模块导航。
- 渲染当前模块主内容。
- 渲染右侧平行笔记。
- 支持 URL 参数或 hash：例如 `?module=coding` 或 `#coding`。
- 支持关键词搜索：title、section text、searchText。
- 支持 theme toggle。
- 支持左右栏折叠和移动端 drawer。

不做：

- embedding search。
- AI answer。
- runtime Markdown parsing。
- 保存状态。

## Search Design

第一版搜索是关键词搜索：

- 输入框仍用 `Search`。
- `⌘ K` 打开搜索。
- 结果按模块分组或列表展示。
- 点击结果切换到对应模块。
- 搜索范围来自 `searchText`。

搜索结果显示：

- 模块 title。
- 命中的 section 名称。
- 简短 snippet。

无结果状态保持轻量，不做大插图或推荐标签。

## Responsive Design

桌面：

- 三栏布局：左侧模块导航、中间模块内容、右侧资源/反思/面试表达。
- 左侧和右侧都可折叠。

移动端：

- 中间内容优先。
- 左侧模块导航用 drawer。
- 右侧笔记用 drawer 或底部面板。
- 搜索 modal 接近全宽。

文本必须在移动端不溢出，不使用 viewport-width 字体缩放。

## Testing Plan

扩展 `tests/projects-requirements.mjs` 或新增 `tests/foundations-roadmap-requirements.mjs`，断言：

- `projects/foundations/index.html` 存在 reader shell。
- 首页不再渲染 README/template 文档卡片作为主体验。
- `projects/foundations/roadmap/modules/*.md` 九个模块文件都存在。
- `projects/foundations/roadmap/roadmap-data.json` 存在。
- `roadmap-data.json` 包含 `Overview`、`Coding`、`LLM Systems`、`Agent Design`、`RAG & Memory`、`Evals & Debugging`、`Research Reading`、`Behavioral / Strategy`、`Logs`。
- JSON 中每个模块都有 `status`、`progress`、`lastUpdated`、`sections`、`searchText`。
- `Coding` 模块保留 coding plan 和 Python/TypeScript 内容。
- `Agent Design`、`RAG & Memory`、`Evals & Debugging` 保留对应 system design case 和 mini drill。
- `Overview` 保留 30/45/60-day plan。
- `Behavioral / Strategy` 保留 strategy rubric。
- build script 可运行并生成可解析 JSON。

视觉和行为验证：

- 本地 HTTP server 打开 `/projects/foundations/`。
- 桌面视口确认三栏布局、模块导航、右侧笔记。
- 移动视口确认内容不溢出，导航和笔记可访问。
- 搜索 `RAG`、`tool calling`、`Python`、`strategy` 能跳到相关模块。

## Acceptance Criteria

- `/projects/foundations/` 打开后直接呈现 roadmap reader，而不是文档列表。
- 原 `README.md`、`multi-agent-planner.md`、`llm-agent-engineer-roadmap.md` 仍可从仓库访问。
- 现有 roadmap 主干内容被完整迁移到模块 Markdown，不出现明显信息丢失。
- 页面只读取 generated JSON，不在浏览器中解析 Markdown。
- build script 是日常更新流程的一部分：编辑模块 Markdown 后运行脚本即可更新页面数据。
- GitHub Pages 可纯静态部署。
- `node tests/projects-requirements.mjs` 和新增/扩展的 Foundations 测试通过。
- `git diff --check` 通过。

## Risks And Mitigations

### Risk: 内容迁移时丢信息

Mitigation:

- 迁移后用 heading map 对照原 `llm-agent-engineer-roadmap.md`。
- 测试中检查关键章节短语。
- 保留原始 roadmap 文件作为审计来源。

### Risk: build script 太复杂

Mitigation:

- 只支持固定 frontmatter 和固定二级标题。
- 不支持任意 Markdown AST 特性。
- 复杂表格和 code block 可以先原样转成基本 HTML。

### Risk: 与 paper reader 共享脚本导致耦合

Mitigation:

- 不复用 `papers/shared/reader.js`。
- Foundations reader 使用独立 `roadmap-reader.js`。
- 只借鉴视觉结构和交互模式。

### Risk: 模块导航失去时间叙事

Mitigation:

- 每个模块内部保留 `时间线`。
- `Overview` 汇总 30/45/60-day plan。
- `Logs` 提供跨模块复盘入口。

## Implementation Boundary

本 spec 只定义设计。进入实现前需要单独写 implementation plan，按步骤处理：

1. 建立模块 Markdown 和 build script。
2. 完整迁移现有 roadmap 内容。
3. 生成 JSON。
4. 替换 `projects/foundations/index.html` 为 reader。
5. 增加 reader CSS/JS。
6. 更新测试。
7. 本地和线上验证。
