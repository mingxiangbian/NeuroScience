---
id: research-reading
title: Research Reading
status: in-progress
progress: 25
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

## 资源

### Research Reading List

- Transformer basics：Attention Is All You Need。Need to know：attention、positional encoding、encoder/decoder intuition。Interview use：解释 LLM inference 和 context limits。
- Scaling：Kaplan scaling laws、Chinchilla。Need to know：data/model/compute tradeoff。Interview use：讨论模型能力和成本边界。
- Instruction tuning：InstructGPT。Need to know：SFT、RLHF、human preference。Interview use：解释 post-training 为什么重要。
- Preference optimization：DPO、PPO basics。Need to know：reward model vs direct preference optimization。Interview use：回答 RLHF / DPO 追问。
- Tool use：ReAct、Toolformer。Need to know：reasoning + acting、tool selection。Interview use：设计 tool-calling agents。
- RAG：Lewis RAG paper plus modern retrieval notes。Need to know：retrieval、generation、faithfulness。Interview use：设计 production RAG。
- Agent memory：Generative Agents、MemGPT、LLM agent memory surveys。Need to know：memory write/read、reflection、context management。Interview use：设计 long-term memory。
- Evals：OpenAI evals ideas、HELM-style thinking、agent eval discussions。Need to know：eval set、graders、contamination、regression。Interview use：设计 eval harness。

Post-training terms to connect:

- SFT
- RLHF
- RLAIF
- RLVR
- PPO
- DPO
- reward model
- direct preference optimization

## 反思

Research Agent 的冲动是扩大 reading scope；Supervisor 的限制是：每组 reading 必须能转成 system design 或面试追问。读完不能讲出面试用途，就不进入当前准备主线。

## 面试表达

阅读卡片回答模板：

- “The paper claims X.”
- “The mechanism is Y.”
- “The limitation is Z.”
- “This helps answer interview question Q.”
- “The system design implication is S.”

## 验收标准

- 每篇 reading 只产出 5 行卡片，不写长综述。
- 能把 Transformer、scaling laws、RLHF、DPO、RAG、agent memory、evals 连接到具体 system design。
- 能说明 paper claim 和自己的 system implication 之间的区别。
- 能解释 RLHF、RLAIF、RLVR 和 Agent eval 的关系。

## 下一步

- 先做 4 张 high-signal cards：Attention、InstructGPT、ReAct、RAG。
- 再补 memory 和 eval cards。
- 每张 card 都要关联一个 mock interview question。
