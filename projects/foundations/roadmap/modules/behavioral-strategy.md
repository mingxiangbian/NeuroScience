---
id: behavioral-strategy
title: Behavioral / Strategy
status: not-started
learning_progress: 0
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

## 知识笔记

### STAR and evidence

核心理解：

- STAR 可以用，但不要僵硬。Situation、Task、Action、Result、Reflection 都要有具体证据。
- Strong signal 是清楚地说出“我做了什么、为什么这样设计、怎么验证、哪里失败过、我如何改进”。
- Weak signal 是只说“我了解 RAG/Agent/RLHF”、只背论文名、只画组件不讲 failure recovery。

面试转译：

- “The strongest version of this story is not that the project was complex; it is the specific tradeoff I made and how I verified it.”

### Strategy Rubric

核心理解：

- Strategy Rubric 每周从 Coding correctness、Coding communication、LLM systems、Agent design、Research depth、Behavioral、Project evidence 七个维度打分。
- 目标不是包装，而是 being perceived as strong through evidence。
- 真正强信号来自可验证的行为：限时写代码、实现小组件、设计 eval、复盘失败、清楚表达取舍。

复习提示：

- 每次 mock 后记录“哪个回答听起来 vague”，再把它改成 evidence-backed answer。

### Project deep dive

核心理解：

- Project deep dive 模板：Problem and users、Constraints、Architecture、Hardest tradeoff、Failure mode、Eval or verification、What I would improve。
- 每个 mini drill 都要能讲成 project evidence。

面试转译：

- “I did not build a large demo first; I decomposed it into tool router, retrieval evaluator, memory store, trace logger, and eval harness because each maps to a measurable interview signal.”
