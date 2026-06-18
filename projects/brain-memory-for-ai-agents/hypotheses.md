# Hypotheses: Brain Memory for AI Agents

---
date: 2026-06-18
status: draft
tags: [memory, hypotheses, ai-agent]
sources:
  - ../../sources/brain-memory-and-agent-memory-sources.md
---

## H1. Agent memory 不能只等于向量库检索

Status: draft
Confidence: medium-low
Claim type: assistant synthesis

### Hypothesis

一个可用的 personal assistant memory system 至少需要 write, retrieval, consolidation, update, forgetting, audit 六个环节。向量库只覆盖 retrieval 的一部分。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| LLM Agent memory survey | 把 memory module 的设计和评估作为系统问题，而不是单一检索问题 | preliminary |
| Generative Agents | 使用 observation, reflection, planning，而不是只存取原始片段 | preliminary |
| MemGPT | 把 context 管理和 memory tiers 当作系统设计问题 | preliminary |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 待核查 RAG / long-context 系统 | 对某些任务，检索或长上下文可能已经足够 | open |

### Crucial Uncertainty

哪些任务必须依赖完整 lifecycle，哪些任务只需要短期上下文或 retrieval？

### What Would Change the Conclusion

如果高质量 eval 显示简单 retrieval 在长期个人化、纠错、删除、偏好漂移场景中足够稳定，这个假设需要降级。

### Next Action

- 查 long-term conversational memory eval。
- 设计 personal assistant memory 的最小 eval matrix。

## H2. 大脑记忆机制对 Agent 设计的主要价值在计算原则层，不在生物实现层

Status: draft
Confidence: medium
Claim type: assistant synthesis

### Hypothesis

hippocampus, engram, synaptic plasticity 等机制不能直接移植到 LLM Agent；但 encoding specificity, indexing, pattern completion, consolidation, reconsolidation, forgetting 可以作为计算设计约束。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| Engram review | 记忆跨 encoding, consolidation, retrieval, forgetting 变化 | strong for neuroscience, speculative for AI transfer |
| hippocampal indexing 相关综述 | index 和 reinstatement 提供可比较的计算框架 | preliminary for transfer |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 待核查 AI memory literature | 工程系统可能不需要生物启发也能达到目标 | open |

### Crucial Uncertainty

哪些脑机制只是解释生物系统的细节，哪些能抽象成通用 memory design principle？

### What Would Change the Conclusion

如果某些脑机制无法转成可测试的 Agent 设计约束，应从架构 spec 中移除，只保留在背景笔记。

### Next Action

- 在 `mechanism-to-agent-design.md` 中逐条标注 transfer risk。

## H3. Agent 需要主动遗忘机制，而不是无限积累 memory

Status: draft
Confidence: medium-low
Claim type: user hypothesis / assistant synthesis

### Hypothesis

长期 personal assistant 如果只积累不遗忘，会产生隐私风险、过时偏好、检索噪声、过度个人化和行为僵化。遗忘应被设计为治理机制。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| Engram review | forgetting 可被视为 memory lifecycle 的组成部分 | strong for neuroscience |
| Agent memory governance / update 文献 | 长期 memory 需要动态更新和治理 | preliminary |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 待核查完整审计存储方案 | 可以保留全部 raw log，同时只调节可访问性 | open |

### Crucial Uncertainty

Agent 的 forgetting 应该是物理删除、访问降权、摘要压缩、过期标记，还是多层组合？

### What Would Change the Conclusion

如果有强证据显示完整保存加可控检索优于删除或降权，假设需要改为“访问治理优先于删除”。

### Next Action

- 比较 deletion, decay, summarization, archival, access gating。

## H4. 用户偏好记忆需要证据累积，而不能由单次表达永久写入

Status: draft
Confidence: medium
Claim type: assistant synthesis

### Hypothesis

一次用户表达更适合作为 episode 或 weak preference；只有重复出现、明确确认或高置信情境下，才应 consolidation 为 stable preference。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| Preference-aware memory update 文献 | 用户偏好会随时间和上下文变化，需要动态更新 | preliminary |
| personal assistant 设计需求 | 单次误记会造成长期体验问题 | speculative |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 明确用户指令 | 有些偏好应立即写入，不需要多次观察 | consensus for product behavior |

### Crucial Uncertainty

如何区分“用户明确长期偏好”和“当前任务中的临时选择”？

### What Would Change the Conclusion

如果用户明确说“以后都这样做”，系统应允许快速写入，但仍需可查看和可撤回。

### Next Action

- 定义 preference memory 的 write policy。

## H5. 只优化 task success 的 memory 会收敛成工具记忆，而不是 cognitive memory

Status: draft
Confidence: low
Claim type: user hypothesis / assistant synthesis

### Hypothesis

如果 AI Agent memory 的主要目标只是 task success、prediction accuracy 或 loss minimization，它可能会学出 engineering memory：高效、简洁、任务相关，但缺少 emotional salience、identity continuity、social modeling、grounded episodic trace 和长期自我纠错能力。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| `sessions/2026-06-19-world-model-and-cognitive-memory.md` | brainstorm 中明确区分 engineering memory 和 cognitive memory | speculative |
| personal assistant 设计需求 | 长期助手需要跨 session 稳定性、偏好连续性和可纠错历史 | speculative |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 待核查 Agent memory eval | 对很多任务，task success 可能已经是足够好的目标 | open |
| 产品边界 | 并非所有 Agent 都需要 cognitive memory；很多工具型 Agent 应避免人格化长期记忆 | open |

### Crucial Uncertainty

哪些 Agent 场景必须超出 task memory？personal assistant、游戏角色、专业研究伙伴和通用工具的 memory objective 是否应不同？

### What Would Change the Conclusion

如果长期 personal assistant eval 显示 task utility objective 同时能带来稳定偏好、可纠错历史、来源可信和用户信任，这个假设需要降级。

### Next Action

- 设计 memory objective matrix：task utility, consistency, compression, grounding, adaptation, privacy, user control。

## H6. Hybrid cognitive memory 可能比纯 RAG 更接近长期 Agent memory 的最小实现

Status: draft
Confidence: low
Claim type: assistant synthesis

### Hypothesis

一个现实的长期 Agent memory 原型可以先采用 frozen reasoning model 加 learned / rule-based memory controller，再组合 episodic trace、semantic graph、latent state 和 audit trail，而不是直接端到端训练大模型。

### Supporting Evidence

| 来源 | 支持点 | 证据强度 |
| --- | --- | --- |
| `sessions/2026-06-19-world-model-and-cognitive-memory.md` | 提出 `latent state + graph memory + episodic trace` 的 hybrid 架构 | speculative |
| 现有 Agent memory 方向 | Generative Agents、MemGPT、agent memory survey 都显示 memory 可作为外部系统模块实现 | preliminary |

### Opposing Evidence

| 来源 | 反对点 | 证据强度 |
| --- | --- | --- |
| 待核查端到端 memory model | 端到端训练可能在长期一致性或隐式状态更新上更强 | open |
| 简单 RAG baseline | 对短期任务或事实回忆，hybrid 架构可能过度复杂 | open |

### Crucial Uncertainty

哪些 memory 状态必须显式存在？`episodic trace`、`semantic graph`、`latent state`、`preference profile` 和 `audit trail` 是否都必要？

### What Would Change the Conclusion

如果纯 RAG 或 long-context baseline 在长期个性化、冲突更新、来源追踪和遗忘控制上表现足够好，hybrid 架构需要简化。

### Next Action

- 在 `mechanism-to-agent-design.md` 中增加 `memory objective / reward` 设计约束。
