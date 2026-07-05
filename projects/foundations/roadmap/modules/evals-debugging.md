---
id: evals-debugging
title: Evals & Debugging
status: in-progress
progress: 25
last_updated: 2026-07-05
priority: high
---

## 目标

能设计 Agent / LLM eval harness，并能用 trace debugging 定位 multi-step workflow failure。重点是 task set、grader、golden traces、adversarial cases、CI integration、thresholds、flaky eval 和 versioning。

## 当前状态

Eval and failure analysis 是 top lab signal 的关键维度。当前路线把 eval、trace 和 debugging 放在阅读之前，因为它们能直接提升 system design 和 project narrative 的可信度。

## 核心知识

### Eval And Debugging

必须会设计：

- task success eval
- regression eval
- tool-use correctness eval
- latency/cost metrics
- human review sampling
- trace-based debugging
- golden set and adversarial set
- failure taxonomy

## 任务

### Case 4: Design An Eval Harness For Agent Regressions

必须覆盖：

- task set
- graders
- golden traces
- adversarial cases
- CI integration
- pass/fail thresholds
- flaky eval handling
- model and prompt versioning

### Case 5: Design Trace Debugging For Multi-Step LLM Workflows

必须覆盖：

- trace schema
- span hierarchy
- prompt/tool/model events
- latency/cost aggregation
- redaction
- replay
- diff between runs

### Drill 4: Agent Trace Logger

Build：

- trace id
- spans for model call, tool call, retrieval
- latency and error fields
- redaction policy

Interview story：

- agents fail across steps; trace is the debugging primitive.

### Drill 5: Eval Harness

Build：

- test cases
- expected outcomes
- grader functions
- pass/fail summary

Interview story：

- agent regressions need evals tied to tasks, not only unit tests.

## 时间线

- Week 2：给 retrieval evaluator 加 trace log：query、retrieved docs、latency、score。
- Week 4：写一个 agent trace/debugging answer。
- Days 31-45：深入 eval harness：golden set、adversarial set、regression suite。
- Days 46-60：capstone extension 可以做 Agent eval and trace workbench。

## 资源

Research reading：

- Evals：OpenAI evals ideas、HELM-style thinking、agent eval discussions。Need to know：eval set、graders、contamination、regression。Interview use：设计 eval harness。

## 反思

Agent 失败通常不是单点 bug，而是 prompt、tool、retrieval、model、state、权限和 user goal 的组合问题。没有 trace，debugging 会变成猜测；没有 eval，修复会退化成 anecdote。

## 面试表达

可复用表达：

- “I would keep golden traces for known-good workflows, then compare prompt/tool/model events between runs.”
- “Agent regression evals need task-level outcomes and step-level diagnostics.”
- “A good eval harness needs versioning for model, prompt, tools and graders; otherwise pass/fail is not interpretable.”

## 验收标准

- 能设计 eval harness 的 task set、grader、threshold 和 CI integration。
- 能解释 golden traces 和 adversarial cases 的作用。
- 能实现 Agent Trace Logger 和 Eval Harness drills。
- 能从 trace schema 讲到 replay、diff、latency/cost aggregation 和 redaction。

## 下一步

- 给所有 drills 加 trace id 和 error field。
- 先做小型 Eval Harness，再考虑 capstone。
- 每次 mock design 后记录一个 failure taxonomy。
