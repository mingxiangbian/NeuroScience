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

## 知识笔记

### Research Reading List

核心理解：

- Transformer basics：Attention Is All You Need。Interview use：解释 LLM inference 和 context limits。
- Scaling：Kaplan scaling laws、Chinchilla。Need to know：data/model/compute tradeoff。
- Instruction tuning：InstructGPT。Interview use：解释 post-training 为什么重要。
- Preference optimization：DPO、PPO basics。Interview use：回答 RLHF / DPO 追问。
- Tool use：ReAct、Toolformer。Interview use：设计 tool-calling agents。
- RAG：Lewis RAG paper plus modern retrieval notes。Interview use：设计 production RAG。
- Agent memory：Generative Agents、MemGPT、LLM agent memory surveys。Interview use：设计 long-term memory。
- Evals：OpenAI evals ideas、HELM-style thinking、agent eval discussions。Interview use：设计 eval harness。

复习提示：

- 每篇 reading 只产出 5 行卡片，不写长综述。

### Post-training terms

核心理解：

- Post-training terms to connect：SFT、RLHF、RLAIF、RLVR、PPO、DPO、reward model、direct preference optimization。
- 需要能说明 RLHF、RLAIF、RLVR 和 Agent eval 的关系。

常见误区：

- 只背术语定义，不说明它们如何影响 system design、model behavior 或 eval。

面试转译：

- “The paper claims X. The mechanism is Y. The limitation is Z. This helps answer interview question Q. The system design implication is S.”

### Reading scope control

核心理解：

- Research Agent 的冲动是扩大 reading scope；Supervisor 的限制是：每组 reading 必须能转成 system design 或面试追问。
- 读完不能讲出面试用途，就不进入当前准备主线。

复习提示：

- 先做 4 张 high-signal cards：Attention、InstructGPT、ReAct、RAG；再补 memory 和 eval cards。
