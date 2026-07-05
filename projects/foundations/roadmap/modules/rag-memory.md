---
id: rag-memory
title: RAG & Memory
status: in-progress
progress: 30
last_updated: 2026-07-05
priority: high
---

## 目标

能设计 production RAG 和 long-term memory，并能解释 retrieval quality、context assembly、provenance、freshness、privacy、write policy、conflict resolution 和 deletion。

## 当前状态

RAG & Memory 是 Agent / LLM 系统面试高频交叉点。准备重点是把“检索 + 生成”拆成可验证组件，不把“上下文窗口更长”误当作 memory。

## 核心知识

### RAG And Memory

必须会解释：

- chunking strategy
- embedding retrieval
- reranking
- metadata filtering
- context assembly
- citation and provenance
- freshness
- deletion and privacy
- memory write policy
- memory conflict resolution

## 任务

### Case 1: Design A Production RAG System

必须覆盖：

- ingestion pipeline
- chunking and metadata
- embedding and index
- retrieval and reranking
- context assembly
- citations
- freshness
- prompt injection defense
- eval: recall@k, answer faithfulness, latency, cost

### Case 3: Design Long-Term Memory For A Personal Assistant

必须覆盖：

- what should be remembered
- write policy
- retrieval policy
- update/delete policy
- privacy and user control
- conflict resolution
- stale memory detection
- eval: precision of memory use, harmful memory rate

### Drill 2: Retrieval Evaluator

Build：

- document list
- query set
- expected relevant ids
- recall@k and failure report

Interview story：

- RAG quality is measured before generation, not only by final answer.

### Drill 3: Memory Store

Build：

- write/read/update/delete
- metadata tags
- conflict detection
- deletion test

Interview story：

- long-term memory requires write policy, user control, and stale memory handling.

## 时间线

- Week 2：画 RAG data flow；写 mini retrieval evaluator；练 `Design a production RAG system`。
- Week 2 stretch：给 retrieval evaluator 加 TypeScript API wrapper；加 trace log：query、retrieved docs、latency、score。
- Week 3：实现 JSON-backed memory store：write、retrieve、update、delete；练 `Design long-term memory for a personal assistant`。
- Week 3 stretch：给 memory store 加 conflict resolution；加 eval：memory 是否应该写入、是否应该删除。

## 资源

Research reading：

- RAG：Lewis RAG paper plus modern retrieval notes。Need to know：retrieval、generation、faithfulness。Interview use：设计 production RAG。
- Agent memory：Generative Agents、MemGPT、LLM agent memory surveys。Need to know：memory write/read、reflection、context management。Interview use：设计 long-term memory。

## 反思

RAG 和 memory 的共同陷阱是“存得多”不等于“记得好”。强回答要覆盖 retrieval precision、write policy、delete policy、privacy、stale memory 和 harmful memory rate。

## 面试表达

可复用表达：

- “I would evaluate retrieval before generation with recall@k and failure reports, then separately evaluate answer faithfulness.”
- “Memory write should be a policy decision, not an automatic append of every interaction.”
- “Deletion and user control are part of memory quality, especially for personal assistants.”

## 验收标准

- 能设计 production RAG pipeline 并给出 recall@k、faithfulness、latency、cost eval。
- 能解释 long-term memory 的 write/retrieve/update/delete policy。
- 能实现 retrieval evaluator 和 memory store 两个 drills。
- 能讲清 freshness、privacy 和 prompt injection defense。

## 下一步

- 先做 Retrieval Evaluator。
- 再做 Memory Store。
- 每个实现都配一个 failure report，避免只写 happy path。
