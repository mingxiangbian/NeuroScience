---
id: research-reading
title: Research Reading
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: medium
---

## 目标

只读能转化为面试答案的材料。每篇 reading 必须输出 claim、mechanism、limitation、interview question 和 system design implication。

## 当前状态

Research reading 是第六优先级，不能挤掉 coding、implementation、system design 和 mock expression。阅读要服务 Agent / LLM Systems Engineer 面试，而不是扩成论文综述。

## 核心知识

阅读覆盖：

- Transformer basics
- Scaling laws
- Instruction tuning
- Preference optimization
- Tool use
- RAG
- Agent memory
- Evals

## 任务

每篇 reading 的输出只要 5 行：

1. paper claim
2. mechanism
3. limitation
4. interview question it helps answer
5. one system design implication

## 时间线

- Week 1：只读一个 Agent 系统概念，服务 tool calling answer。
- Week 2：读 RAG / retrieval 相关材料，服务 production RAG。
- Week 3：读 agent memory 相关材料，服务 long-term memory。
- Week 4：整理成 mock interview 可用的 short cards。
- Days 31-45：读 post-training / RLHF / DPO / RLVR，并解释它们和 Agent eval 的关系。
- Days 46-60：练 research-engineering discussion：如何把 ambiguous failure 转成 experiment。
