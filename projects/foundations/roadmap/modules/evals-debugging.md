---
id: evals-debugging
title: Evals & Debugging
status: learning
learning_progress: 0
last_updated: 2026-07-11
priority: high
---

## 目标

能设计 Agent / LLM eval harness，并能用 trace debugging 定位 multi-step workflow failure。重点是 task set、grader、golden traces、adversarial cases、CI integration、thresholds、flaky eval 和 versioning。

## 当前状态

Eval and failure analysis 是 top lab signal 的关键维度。D2 已完成第一份 coached case audit：用六部分拆解 Cyrene `T0-MODE-FAST`，并对 Balanced Mode 做近迁移。当前仍是 coached readiness 1；D5 才进行未见 case 的独立审计。

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

### Eval Case Anatomy — D2

核心理解：

- 一个可审计的 Eval case 包含六部分：input 是运行前的 fixture 和请求；expected 是行为契约；actual 是运行后观察结果；assertion 是比较 actual 与 expected 的可执行规则；metric 是数值度量；evidence 是供人复核的事实。
- system performance benchmark 回答“多快、多贵、多大”，Agent behavior eval 回答“是否做了正确的事、是否做了不该做的事”。同一 case 可以同时包含两类信号，但不能用延迟或 token 数替代行为正确性。
- 正向断言验证必须出现的行为，负向断言验证禁止行为没有出现。只有负向断言时，系统可能什么都不返回却仍然通过。
- Assertion 和 Evidence 应共用同一组实际观测。Evidence 不能由一个条件触发后硬编码其余结论，否则报告可能一边 `failed`，一边声称没有泄漏。
- 单次调用耗时只能叫 latency sample，不能叫 P95；字符数除以四只能用于近似 token regression，不能冒充真实 tokenizer 或计费结果。
- Context freshness 要按 scope 测量：项目偏好和全局记忆具有不同维护周期，不能共用一个 time-to-availability threshold。

常见误区：

- 把 fixture 中存在 Active Memory 当作系统已经成功返回 Active Memory；Eval 必须检查 actual output。
- 把 `not required` 自动解释成 `forbidden`，或忽略真实 Policy 对模式互斥的要求。
- 把单 case 的 `modeAccuracy = 1` 说成系统准确率 100%，把一次 `22ms` 说成 P95。
- 用“架构上移除了同步调用”替代前后效果数据；可以说明关键路径变化，但不能虚构延迟或成本降幅。

面试转译：

- “I separate the fixture, expected behavior, observed output, executable assertions, metrics, and evidence. I also require positive assertions for required behavior, because absence-only checks can pass when the system returns nothing.”
- “For the Cyrene fast-mode case, the archived regression proves several exclusion boundaries, but it does not prove active-memory retrieval, and its latency and token fields are estimates rather than production distribution metrics.”

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
