---
id: llm-systems
title: LLM Systems
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: high
---

## 目标

把 LLM 概念推进到“能设计、能实现、能解释 tradeoff、能被追问”的程度。重点是 inference behavior、context budgeting、structured outputs、post-training intuition 和 production constraints。

## 当前状态

LLM/Agent 系统知识已有基础，但需要从术语级理解推进到系统级回答。这个模块服务 system design、research discussion 和 LLM Fundamentals mock。

## 核心知识

### LLM Systems

核心概念：

- tokenization and context windows
- attention and KV cache intuition
- batching, streaming, rate limits
- latency and cost tradeoff
- prompt assembly and context budgeting
- model selection and fallback
- structured outputs and schema validation

需要能解释：

- 为什么 long context 不等于 memory。
- 为什么 KV cache 影响 latency 和 serving design。
- 为什么 structured output 需要 schema validation 和 retry。
- 为什么 benchmark scores 会误导 production system choices。

## 任务

### System Design Answer Template

每个 LLM system design case 用同一套结构：

1. Clarify requirements。
2. Define success metrics。
3. State assumptions。
4. Draw components。
5. Explain data flow。
6. Identify failure modes。
7. Propose evals and monitoring。
8. Discuss tradeoffs and follow-ups。

### LLM Fundamentals Mock

1. Explain attention and why KV cache matters。
2. Explain why long context is not the same as memory。
3. Explain SFT vs RLHF vs DPO。
4. Explain why benchmark scores can mislead。
5. Explain temperature, sampling, and structured outputs。

## 时间线

- Week 1：读一个 Agent/LLM 系统概念并练 2 分钟口头回答。
- Week 2：把 RAG data flow 和 prompt/context budgeting 讲清楚。
- Week 3：把 long-term memory 和 long context 的差别讲清楚。
- Week 4：整理 LLM Fundamentals mock questions。
- Days 31-45：读 post-training / RLHF / DPO / RLVR 概念，并解释它们和 Agent eval 的关系。
- Days 46-60：练 research-engineering discussion：如何把 ambiguous failure 转成 experiment。

## 知识笔记

### Transformer and KV cache

核心理解：

- Transformer basics 要能解释 attention、positional encoding、context limits 和 inference behavior。
- KV cache 不是实现细节；它改变 serving latency、batching strategy、streaming behavior 和 cost tradeoff。

常见误区：

- 只说“attention lets tokens attend to each other”不够，需要落到 inference 和系统约束。
- Long context expands what the model can attend to, but memory requires write policy、retrieval policy、update/delete policy and user control。

面试转译：

- “KV cache is not just an implementation detail; it changes serving latency, batching strategy, streaming behavior and cost tradeoff.”

### Post-training and structured outputs

核心理解：

- Post-training 需要区分 SFT、RLHF、DPO、RLVR 的作用。
- Structured outputs 不能只靠 prompt instruction，需要 schema validation、retry policy 和 trace logging。
- Model selection 要讲 latency、cost、reliability、eval 和 fallback，而不是“哪个模型更强”。

常见误区：

- 把 benchmark score 直接等同于 production choice。
- 把 structured output failure 当作 prompt wording 问题，而不是 runtime 和 validation 问题。

面试转译：

- “For structured outputs, prompt instruction is not enough. I would add schema validation, retry policy and trace logging.”

### Research Reading List

核心理解：

- Transformer basics：Attention Is All You Need。Interview use：解释 LLM inference 和 context limits。
- Scaling：Kaplan scaling laws、Chinchilla。Interview use：讨论模型能力和成本边界。
- Instruction tuning：InstructGPT。Interview use：解释 post-training 为什么重要。
- Preference optimization：DPO、PPO basics。Interview use：回答 RLHF / DPO 追问。

复习提示：

- 每篇 reading 只写 5 行：paper claim、mechanism、limitation、interview question、system design implication。
