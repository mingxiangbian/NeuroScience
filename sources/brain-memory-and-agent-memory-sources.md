# Sources: Brain Memory and Agent Memory

---
date: 2026-06-18
topic: brain memory mechanisms and AI agent memory
status: draft
tags: [memory, neuroscience, ai-agent, sources]
---

## Research Area

这个 source map 服务 `projects/brain-memory-for-ai-agents/`。它覆盖两类来源：

- Neuroscience: 大脑 memory 的 encoding, consolidation, retrieval, reconsolidation, forgetting。
- AI Agent: LLM-based Agent 的 long-term memory, memory module, reflection, update, evaluation, governance。

暂时不把任何来源写成项目结论。每个来源读完后再决定是否进入 `papers/` 或 `knowledge/`。

## Key Terms

| 中文 | English | Notes |
| --- | --- | --- |
| 记忆痕迹 | engram | 记忆的神经基底候选概念。 |
| 编码 | encoding | 经验如何被写入或改变系统状态。 |
| 巩固 | consolidation | 短期、脆弱记忆如何稳定和重组。 |
| 提取 | retrieval | 线索如何重新激活记忆。 |
| 再巩固 | reconsolidation | 被提取的记忆可能再次进入可修改状态。 |
| 遗忘 | forgetting | 存储丢失、访问失败、主动抑制或治理机制。 |
| 海马索引 | hippocampal indexing | 海马作为分布式皮层表示索引的理论。 |
| 模式补全 | pattern completion | 不完整线索补全完整记忆模式。 |
| 模式分离 | pattern separation | 区分相似经验，降低干扰。 |
| Agent memory | Agent memory | AI Agent 的持久化外部 memory system。 |
| 偏好记忆 | preference memory | 用户长期偏好和上下文倾向。 |
| 长期对话记忆 | long-term conversational memory | 跨 session 维持用户和任务上下文。 |

## Seed Sources: Neuroscience

| Source | Year | Type | Why it matters | Status |
| --- | --- | --- | --- | --- |
| Guskjolen & Cembrowski, "Engram neurons: Encoding, consolidation, retrieval, and forgetting of memory" | 2023 | peer-reviewed expert review | 直接覆盖 memory lifecycle: encoding, consolidation, retrieval, forgetting。 | located |
| Squire, "Memory systems of the brain: a brief history and current perspective" | 2004 | review | 记忆系统分型和历史框架。 | pending verification |
| Tulving, "Episodic and semantic memory" | 1972 | classic chapter | 区分 episodic memory 和 semantic memory。 | pending verification |
| Marr / hippocampal indexing related work | various | theory / review | 研究 hippocampus 作为 index、pattern separation / completion 的理论入口。 | pending verification |
| Reviews on memory reconsolidation | various | review | 支持 Agent memory update 类比的候选来源。 | pending search |
| Reviews on active forgetting | various | review | 支持 Agent forgetting / access control 设计的候选来源。 | pending search |

## Seed Sources: AI Agent Memory

| Source | Year | Type | Why it matters | Status |
| --- | --- | --- | --- | --- |
| Zhang et al., "A Survey on the Memory Mechanism of Large Language Model based Agents" | 2024 | arXiv survey | 系统整理 LLM-based Agent memory module 的设计和评估。 | located |
| Park et al., "Generative Agents: Interactive Simulacra of Human Behavior" | 2023 | arXiv / UIST paper | observation, reflection, planning 的经典 Agent memory 架构。 | located |
| Packer et al., "MemGPT: Towards LLMs as Operating Systems" | 2023 / 2024 revision | arXiv paper | memory tiers, virtual context management, multi-session chat。 | located |
| "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers" | 2026 | arXiv survey / preprint | 新近综述，覆盖 mechanisms, evaluation, emerging frontiers。 | located, needs quality check |
| "Preference-Aware Memory Update for Long-Term LLM Agents" | 2025 | arXiv preprint | 聚焦 preference memory update 和长期对话。 | located, needs quality check |
| Xu et al., "A-Mem: Agentic Memory for LLM Agents" | 2025 / 2026 modified | OpenReview / NeurIPS poster | 动态组织和更新 memory network 的代表方向。 | located, needs quality check |

## URLs

| Source | URL |
| --- | --- |
| A Survey on the Memory Mechanism of Large Language Model based Agents | https://arxiv.org/abs/2404.13501 |
| Generative Agents: Interactive Simulacra of Human Behavior | https://arxiv.org/abs/2304.03442 |
| MemGPT: Towards LLMs as Operating Systems | https://arxiv.org/abs/2310.08560 |
| Engram neurons: Encoding, consolidation, retrieval, and forgetting of memory | https://www.nature.com/articles/s41380-023-02137-5 |
| Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers | https://arxiv.org/html/2603.07670v1 |
| Preference-Aware Memory Update for Long-Term LLM Agents | https://arxiv.org/html/2510.09720v1 |
| A-Mem: Agentic Memory for LLM Agents | https://openreview.net/forum?id=FiM0M8gcct |

## Quality Checks to Apply

### Neuroscience

- 研究对象：人类、啮齿动物、体外模型还是计算模型？
- 方法测到什么：行为、神经活动、因果操控、转录组、连接、影像？
- 是否区分 encoding, consolidation, retrieval, forgetting？
- 是否能支持机制解释，还是只支持相关性？
- 是否能迁移到计算原则，还是只属于生物实现细节？

### AI Agent

- memory 具体指什么：raw log、summary、embedding、graph、profile、tool trace、world state？
- 是否支持 write / retrieve / update / delete / audit？
- eval 是否跨 session？
- 是否测错误纠正、偏好漂移、遗忘和隐私？
- baseline 是否合理？
- 是否有代码、数据、实现细节？

## Next Search Terms

- hippocampal indexing theory review
- hippocampus pattern completion pattern separation review
- encoding specificity principle review
- memory reconsolidation review
- active forgetting neuroscience review
- engram reactivation memory retrieval optogenetics review
- long-term conversational memory LLM benchmark
- LLM agent memory evaluation benchmark
- preference memory update LLM agent
- memory governance LLM agent
- agent memory deletion user control
