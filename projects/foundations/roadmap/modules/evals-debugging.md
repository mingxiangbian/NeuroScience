---
id: evals-debugging
title: Evals & Debugging
status: not-started
learning_progress: 0
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

## 知识笔记

### Eval Harness

核心理解：

- Eval Harness 要覆盖 task set、graders、golden traces、adversarial cases、CI integration、pass/fail thresholds、flaky eval handling、model/prompt versioning。
- Agent regression evals need task-level outcomes and step-level diagnostics。

常见误区：

- 只写 unit tests，但没有 task-level outcomes。
- pass/fail 没有绑定 model、prompt、tools、graders 的版本，导致结果不可解释。

面试转译：

- “A good eval harness needs versioning for model, prompt, tools and graders; otherwise pass/fail is not interpretable.”

### Trace Debugging

核心理解：

- Trace Debugging 覆盖 trace schema、span hierarchy、prompt/tool/model events、latency/cost aggregation、redaction、replay、diff between runs。
- Agent 失败通常不是单点 bug，而是 prompt、tool、retrieval、model、state、权限和 user goal 的组合问题。

常见误区：

- 没有 trace 时，debugging 会变成猜测；没有 eval 时，修复会退化成 anecdote。

面试转译：

- “I would keep golden traces for known-good workflows, then compare prompt/tool/model events between runs.”

### Agent Trace Logger

核心理解：

- Agent Trace Logger drill 包含 trace id、model/tool/retrieval spans、latency and error fields、redaction policy。
- Eval And Debugging 的强信号来自能把 failure taxonomy 转成 regression suite。

相关资料：

- Evals：OpenAI evals ideas、HELM-style thinking、agent eval discussions。Need to know：eval set、graders、contamination、regression。
