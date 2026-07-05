---
id: behavioral-strategy
title: Behavioral / Strategy
status: in-progress
progress: 30
last_updated: 2026-07-05
priority: high
---

## 目标

把准备内容转成面试官能识别的强信号：结构化表达、清楚 tradeoff、真实 failure story、可验证 project evidence。

## 当前状态

第二优先级是面试表达。coding 和 system design 内容必须最终转成可讲述的故事，否则准备会停留在“做过一些练习”。

## 核心知识

表达训练重点：

- clarify requirements
- state assumptions
- compare tradeoffs
- identify failure modes
- propose evals
- tell evidence-backed stories
- avoid vague claims

## 任务

### Behavioral And Project Deep Dive

1. Tell me about a project where requirements were ambiguous。
2. Tell me about a time you debugged a difficult issue。
3. Tell me about a tradeoff you made between speed and correctness。
4. Tell me about a time you changed your mind after evidence。
5. Walk me through a system you built and what you would improve。

### Strategy Rubric

Score yourself weekly from 1 to 5:

- Coding correctness：1 = Cannot finish medium；3 = Finishes with hints；5 = Finishes cleanly and explains。
- Coding communication：1 = Silent or scattered；3 = Explains main idea；5 = Clarifies, narrates, tests。
- LLM systems：1 = Knows terms；3 = Explains components；5 = Designs with tradeoffs and evals。
- Agent design：1 = Generic loop；3 = Names tools/memory；5 = Handles safety, trace, failure。
- Research depth：1 = Name-drops papers；3 = Explains claims；5 = Connects papers to systems。
- Behavioral：1 = Vague stories；3 = STAR-ish；5 = Crisp, evidence-backed, reflective。
- Project evidence：1 = No artifacts；3 = Small scripts；5 = Drills tied to interview stories。

Weekly target：

- Week 1：average 2.5
- Week 2：average 3
- Week 3：average 3.5
- Week 4：average 4
- Day 45+：push weakest two dimensions toward 4
- Day 60+：one standout dimension should reach 5

## 时间线

- Week 1：练一个 2 分钟 tool-calling agent 设计回答。
- Week 3：写 1 个 behavioral story：如何在 ambiguity 下做取舍。
- Week 4：整理 5 个 behavioral stories；做 2 次 system design mock；做一轮 full loop mock。
- Days 31-45：简历项目叙事和 mock interview iteration。
- Days 46-60：3 次 full mock，并按 rubric 复盘。

## 资源

Strong signal：

- 清楚地说出“我做了什么、为什么这样设计、怎么验证、哪里失败过、我如何改进”。
- 所有 drills 都要能对应一个 interview story。
- 每个 system design 都要包含 success metrics、failure modes、evals and monitoring。

Weak signal：

- 只说“我了解 RAG/Agent/RLHF”。
- 只背论文名。
- 只画组件，不讲 failure recovery。
- 只说项目很复杂，不给 evidence。

## 反思

Strategy 的重点是“being perceived as strong”，但这不等于包装。真正强信号来自可验证的行为：限时写代码、实现小组件、设计 eval、复盘失败、清楚表达取舍。

## 面试表达

STAR-ish 但不要僵硬：

- Situation：背景和约束。
- Task：你要解决什么。
- Action：你具体做了什么。
- Result：结果、证据、指标。
- Reflection：如果重做会改什么。

Project deep dive 模板：

1. Problem and users。
2. Constraints。
3. Architecture。
4. Hardest tradeoff。
5. Failure mode。
6. Eval or verification。
7. What I would improve。

## 验收标准

- 至少 5 个 behavioral stories。
- 每个 story 都有 evidence，而不是抽象形容。
- 每个 mini drill 都能讲成 project evidence。
- Strategy Rubric 每周更新一次。
- 至少一个维度到 Day 60 能达到 5。

## 下一步

- 先为 Tool Router、Retrieval Evaluator、Memory Store、Trace Logger 各写 3 句 interview story。
- 每周按 Strategy Rubric 自评。
- mock 后记录“哪个回答听起来 vague”。
