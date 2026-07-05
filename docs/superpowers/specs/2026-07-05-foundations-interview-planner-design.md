# Foundations 面试准备 Planner 设计

Date: 2026-07-05
Status: Approved design, awaiting implementation plan

## Summary

本 spec 设计 `projects/foundations/` 下的面试准备系统。目标不是做一个大型 demo 项目，而是建立一套面向顶尖 AI Lab 的 **Agent / LLM Systems Engineer** 面试准备包。

当前用户选择：

- 产物模式：先生成一版可用计划，再沉淀成 `projects/foundations/` 的长期模板。
- 时间形态：核心 30 天冲刺，可延展到 45/60 天。
- 目标岗位：Agent / LLM Systems Engineer。
- 难度对齐：OpenAI / Anthropic / DeepMind / xAI 这类顶尖 AI Lab / AGI 团队。
- 当前短板：coding 和实现能力优先，其次是面试表达；LLM/Agent 系统知识已有一点基础，但需要深入。
- 技术栈：Python + TypeScript 为主，Rust 只作为 optional depth add-on。
- 项目策略：面试优先，不做大项目；用小型 implementation drills 和 system design casebook 提供面试证据。

## Goals

- 给出一份可直接执行的 30/45/60 天准备路线。
- 把用户提供的 6-agent prompt 整理成可复用 planner 模板。
- 输出面试有用的知识地图、coding 训练、system design casebook、reading list、mock interview set 和 mini drills。
- 优先提升候选人在面试中的可感知强度：能写、能设计、能解释 tradeoff、能讨论失败模式和 eval。

## Non-Goals

- 不把 Foundations 做成通用课程网站。
- 不做大型 full-stack demo 项目。
- 不把路线写成论文综述或泛泛 reading list。
- 不追求 AGI 理论完整性，除非它直接服务 Agent / LLM Systems Engineer 面试。
- 不引入后端、数据库、AI provider、自动生成工具或交互式 planner。
- 不重组 `projects/`、`papers/`、`sources/`、`questions/` 的既有目录边界。

## Target User Profile

计划默认用户当前处于从 0 到 1 系统化准备阶段：

- 需要建立稳定 coding 训练节奏。
- 需要把 Python / TypeScript 实现能力转成面试可展示信号。
- 需要把 LLM/Agent 概念从“知道一些”推进到“能做系统设计和故障分析”。
- 需要练习结构化表达，避免回答散、浅、只背概念。

## Agent Model

最终文档使用用户给定的 6-agent 框架，但输出必须由 Supervisor 收敛，不能变成六份重复意见。

### CTO Agent

关注 production LLM systems：

- scalable LLM serving
- RAG, memory, tool calling
- agent runtime, tracing, observability
- latency, cost, reliability, safety guardrails

主要贡献：system design casebook 的工程现实、tradeoff、failure modes。

### Research Agent

关注 LLM/AGI 相关理论：

- transformer, attention
- scaling laws
- reasoning models
- memory and world models
- RLHF / RLVR / post-training

主要贡献：少量高影响 reading list 和面试中会被追问的 conceptual framework。

### Coding Interview Agent

关注可测量 coding 能力：

- LeetCode patterns
- Python implementation
- TypeScript service/interface implementation
- agent component drills

主要贡献：每日/每周 coding 训练结构和小型实现题。

### Product / Agent Design Agent

关注 AI product and agent UX：

- tool orchestration
- multi-agent workflow
- memory UX
- human-in-the-loop
- failure recovery

主要贡献：让 system design 不停留在后端组件图，而能解释真实用户场景、交互和产品风险。

### Interview Strategy Agent

关注面试信号最大化：

- resume and project framing
- behavioral stories
- answer structure
- mock interview scoring rubric

主要贡献：把准备内容转化成面试可被识别的强信号。

### Supervisor Agent

负责收敛：

- 消除重复。
- 明确冲突。
- 平衡 theory / engineering / coding / expression。
- 输出最终路线和优先级。

Supervisor 的默认判定规则：

1. 面试相关性优先于学术完整性。
2. coding 和表达训练不能被 reading 挤掉。
3. 每个 system design 主题都要能落到 implementation drill 或 failure analysis。
4. 只做少量 high-signal papers，不做论文堆积。

## Output Files

第一版只创建三个核心文件，避免目录膨胀：

```text
projects/foundations/
  README.md
  multi-agent-planner.md
  llm-agent-engineer-roadmap.md
```

### `README.md`

项目入口，包含：

- Foundations 的目标。
- 推荐使用方式。
- 当前路线定位。
- 指向 planner 和 roadmap 的链接。

### `multi-agent-planner.md`

可复用 planner 模板，包含：

- 6-agent roles。
- 输入字段：target role、timeline、skill baseline、constraints、language stack、project preference。
- Step 1 parallel generation。
- Step 2 adversarial debate。
- Step 3 conflict extraction。
- Step 4 scoring。
- Step 5 final synthesis。
- 输出格式模板。

### `llm-agent-engineer-roadmap.md`

这次为用户生成的实际路线，包含：

- Knowledge Map。
- 30/45/60 天弹性计划。
- Coding Plan。
- System Design Plan。
- Research Reading List。
- Mock Interview Set。
- Mini Implementation Drills。
- Project Recommendations。
- Strategy Rubric。

## Roadmap Shape

路线采用 milestone 结构，而不是死板日历。

### Core 30 Days

目标：从分散准备进入可面试状态。

每周都有：

- coding pattern practice
- implementation drill
- LLM/Agent system design case
- research concept review
- mock answer practice

### Extension To 45 Days

目标：补强系统设计和 mock 表达。

重点：

- 更复杂的 RAG / memory / tool-use case。
- 端到端 failure analysis。
- 简历项目叙事。
- mock interview iteration。

### Extension To 60 Days

目标：冲击顶尖团队的更高信号。

重点：

- eval harness depth。
- post-training / reasoning / agent failures 的研究型追问。
- optional Rust systems-depth module。
- project-style capstone only if time permits。

## Task Intensity Model

由于用户每天时间不固定，每周任务分三层：

- `minimum`：当天很忙也要完成，通常是 30-45 分钟。
- `standard`：推荐完成量，通常覆盖 coding + design + expression。
- `stretch`：有额外时间时做，用于 high-signal 区分。

任何一天中断时，不补偿性堆积任务；下一天回到当周 `minimum` 和 `standard`。

## Knowledge Map Requirements

知识地图必须分层，而不是平铺概念：

- Coding fundamentals
  - arrays, hash maps, two pointers
  - trees, graphs, BFS/DFS
  - heap, intervals, greedy
  - DP basics
  - Python/TypeScript implementation habits
- LLM systems
  - tokenization, attention, transformer inference basics
  - batching, caching, streaming
  - latency/cost tradeoff
- Agent systems
  - tool calling
  - planning vs reactive loops
  - memory write/read/update/delete
  - trace and observability
  - eval and regression testing
- RAG and memory
  - chunking
  - embedding retrieval
  - reranking
  - context assembly
  - freshness and privacy
- Interview expression
  - clarify requirements
  - state assumptions
  - compare tradeoffs
  - identify failure modes
  - propose evals

## Coding Plan Requirements

Coding 计划必须可测量：

- 每周指定 patterns。
- 每天有题量或实现目标。
- Python 是主面试语言。
- TypeScript 用于 service/API/interface style drills。
- Rust 只放在 45/60 天 extension 的 optional module。

Coding 输出不只做 LeetCode，还要包括 Agent/LLM implementation drills：

- tool router
- memory store
- retrieval evaluator
- trace logger
- streaming response wrapper
- retry and timeout controller

## System Design Casebook Requirements

casebook 应覆盖：

- Design a production RAG system。
- Design an agent runtime with tool calling。
- Design a long-term memory system for a personal assistant。
- Design an eval harness for Agent regressions。
- Design a trace/debugging system for multi-step LLM workflows。
- Design a safe tool execution layer。

每个 case 必须包含：

- problem framing
- assumptions
- architecture
- data flow
- tradeoffs
- failure modes
- eval plan
- likely interviewer follow-ups

## Research Reading Requirements

reading list 控制在 high-signal 少量材料：

- Transformer / attention basics。
- scaling laws。
- RLHF / post-training。
- RAG and retrieval。
- tool use / function calling。
- agent memory。
- evals and benchmark pitfalls。

每篇或每组 reading 都必须回答：

- 面试为什么会用到。
- 需要掌握到什么深度。
- 可以怎样转成 system design 或 research discussion 答案。

## Mock Interview Requirements

mock set 按类别组织：

- Coding。
- Python/TypeScript implementation。
- LLM fundamentals。
- Agent system design。
- RAG/memory/eval。
- Behavioral and project deep dive。

每道题附：

- expected signal
- strong answer outline
- common weak answer
- follow-up questions

## Conflict Resolution Rules

预期冲突及解决：

- Research Agent 想扩大 reading 范围时，Supervisor 限制为面试高频和能转化为设计答案的内容。
- CTO Agent 强调 production 约束时，Product Agent 补充用户场景和 workflow，不让设计变成纯 infra。
- Coding Agent 要求可量化训练，因此每天必须有可执行练习，不能只阅读。
- Strategy Agent 可以调整表达顺序，但不能牺牲事实准确性或工程合理性。

## Quality Bar

最终 roadmap 必须满足：

- 能让用户当天开始执行。
- 每周任务有明确产出。
- 不使用空泛表述，例如“多学习基础知识”。
- 不把顶尖 AI Lab 面试简化成普通 CRUD 系统设计。
- 不把 AGI/LLM 内容堆成论文清单。
- 每个核心模块都能对应面试题或可展示 drill。

## Verification

实施完成后应验证：

- `projects/foundations/README.md` 存在并链接到 planner 和 roadmap。
- `multi-agent-planner.md` 包含 6-agent roles、debate、scoring 和 final synthesis。
- `llm-agent-engineer-roadmap.md` 包含指定 7 类输出。
- 文档中没有占位符、空 section 或互相矛盾的时间线。
- `git diff --check` 通过。

如果需要自动化测试，可新增轻量 Node 脚本检查文件存在和关键标题；第一版可以先用人工 review 加 `rg`/`git diff --check` 验证。
