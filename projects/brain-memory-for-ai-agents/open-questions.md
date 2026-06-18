# Open Questions: Brain Memory for AI Agents

---
date: 2026-06-18
status: active
tags: [memory, open-questions, ai-agent]
sources:
  - ../../sources/brain-memory-and-agent-memory-sources.md
---

## Primary Question

人脑 memory 机制能为 AI Agent / personal assistant 的长期 memory system 提供哪些可迁移原则，哪些只是类比，哪些不能迁移？

Status: reading-not-started

## Neuroscience Questions

### Q1. 记忆 retrieval 是怎样从线索进入部分激活，再进入模式补全和显性回忆的？

Why it matters: 这关系到 Agent memory 是否应该由明确命令触发，还是由当前上下文线索自动触发候选 memory。

Scope: circuit / systems / cognitive / computational

Current view: 初步假设是 retrieval 不是一次性“查库”，而是线索驱动的动态过程；需要用 hippocampus, engram, encoding specificity 相关文献验证。

Next action:

- 查 `encoding specificity principle`, `hippocampal indexing`, `pattern completion`, `engram reactivation`。

### Q2. hippocampus 的 indexing 理论能否转成 Agent memory index 的计算原则？

Why it matters: Agent memory 需要通过有限线索重新定位分布式历史上下文。

Scope: systems / computational / AI-model

Current view: 可能有启发意义，但不能直接等同。大脑 index 指向分布式神经活动，Agent index 指向文本、事件、向量、图谱或状态。

Next action:

- 阅读 hippocampal indexing theory 和 systems consolidation 综述。

### Q3. forgetting 在大脑中是存储丢失、检索失败、主动抑制，还是多种机制？

Why it matters: Agent memory 也需要遗忘，但遗忘可能是隐私、压缩、冲突解决和性能控制的一部分。

Scope: synaptic / circuit / systems / cognitive / AI-model

Current view: 不应把 forgetting 只看作 bug。需要区分不可用、不可访问、被抑制和被更新。

Next action:

- 查 `active forgetting`, `memory accessibility`, `engram forgetting`, `retrieval failure`。

### Q4. reconsolidation 对 Agent memory update 有什么启发？

Why it matters: 旧 memory 被重新提取后可能需要修改，而不是简单追加新记录。

Scope: cellular / systems / cognitive / AI-model

Current view: 这是 Agent memory update 的强候选类比，但需要核查证据边界。

Next action:

- 查 `memory reconsolidation review`, `retrieval-induced plasticity`。

## Agent Design Questions

### Q5. 一个 personal assistant 应该记住什么，不该记住什么？

Why it matters: 记忆越多不等于越好。错误、敏感、过时或未经确认的 memory 会降低信任。

Scope: AI-model / product / eval

Current view: 需要 write policy，区分事实、偏好、任务状态、长期目标、临时上下文和敏感信息。

Next action:

- 建立 memory type taxonomy。

### Q6. Agent memory 应该如何从 episode 变成 stable preference 或 semantic knowledge？

Why it matters: 一次对话不应该轻易变成永久偏好；多次重复可能需要 consolidation。

Scope: AI-model / computational

Current view: 需要类似 consolidation 的证据累积机制，不能只按最近一次用户表达覆盖旧记忆。

Next action:

- 对比 reflection, summarization, preference update, exponential moving average 等机制。

### Q7. Agent memory 如何处理冲突、过时和错误？

Why it matters: 长期助手必须能修正自己，而不是固化旧结论。

Scope: AI-model / eval / governance

Current view: 需要 conflict resolution 和 audit trail。旧 memory 不一定删除，可能降权、标记过期或保留版本。

Next action:

- 查 memory update, preference drift, user correction, memory governance。

### Q8. Agent memory eval 应该测什么？

Why it matters: 很多系统只测是否能找回旧文本，但 personal assistant 需要测长期一致性、适时检索、不过度检索、纠错和删除。

Scope: AI-model / eval

Current view: eval 至少要覆盖 recall, precision, update, privacy, deletion, over-personalization。

Next action:

- 查 LoCoMo, long-term conversational memory eval, MemoryBench, MemoryArena。

## Bridge Questions

### Q9. 从大脑机制迁移到 Agent 设计时，哪些层级可以比较？

Why it matters: 防止把“AI 像大脑”写成无约束类比。

Scope: computational / AI-model / neuroscience

Current view: 只能在目标、计算原则、表征、动态、行为和数据对应层分别比较。

Next action:

- 在 `mechanism-to-agent-design.md` 增加 `claim type` 和 `risk` 字段。

### Q10. memory 和 world model 的边界在哪里？

Why it matters: 用户之前的讨论已经触及这个问题。Agent 需要既能记住“发生过什么”，也能推断“通常会怎样”。

Scope: cognitive / computational / AI-model

Current view: episodic memory 更接近具体经历证据，world model 更接近压缩后的规律和预测结构；两者会互相影响。

Next action:

- 查 episodic memory, semantic memory, schema, predictive processing, world model。

### Q11. Agent memory 的 objective function 应该是什么？

Why it matters: 如果 memory 只优化 task success 或 prediction accuracy，系统可能更像高效工具，而不是长期个人助手或 persistent agent。

Scope: computational / AI-model / eval / product

Current view: objective 可能至少包含 task utility, consistency, compression, grounding, adaptation, privacy 和 user correction。不同 Agent 不一定需要同一种 objective。

Next action:

- 从 `sessions/2026-06-19-world-model-and-cognitive-memory.md` 抽取候选 reward 维度，并和 Agent memory eval 文献对照。

### Q12. world model、cognitive memory 和 persistent agent 是什么关系？

Why it matters: 如果把 world model 定义得太宽，会把环境预测、长期记忆、情绪权重、身份连续性混在一起，导致架构目标不清。

Scope: cognitive / computational / AI-model

Current view: world model 的最低定义不要求 human-like cognitive memory；persistent agent 可能需要 world model 加长期 cognitive memory 和行动连续性。

Next action:

- 定义三者的最小必要条件：`world model`, `cognitive memory`, `persistent agent`。
