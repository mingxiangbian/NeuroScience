# Brain Memory for AI Agents

---
date: 2026-06-18
status: active
tags: [memory, neuroscience, ai-agent, personal-assistant]
sources:
  - ../../sources/brain-memory-and-agent-memory-sources.md
---

## Project Question

人脑 memory 机制能为 AI Agent / personal assistant 的长期 memory system 提供哪些可迁移原则，哪些只是有用类比，哪些不能迁移？

## Motivation

一个没有长期 memory 的 Agent 更像一次性 tool：它可以回答问题、调用工具、执行任务，但很难形成连续关系、个人化偏好、长期项目上下文和跨 session 的经验积累。

这个项目从两个方向推进：

- 神经科学方向：理解大脑如何编码、巩固、提取、更新、遗忘记忆，以及这些过程有哪些机制证据。
- AI Agent 方向：研究一个 personal assistant 的 memory 应该如何被写入、检索、更新、压缩、删除、验证和解释。

核心目标不是证明 AI 像大脑，而是用神经科学机制帮助约束 Agent memory 设计。

## Scope

本项目覆盖：

- 记忆阶段：encoding, consolidation, retrieval, reconsolidation, forgetting。
- 记忆类型：episodic memory, semantic memory, procedural memory, preference memory, task memory。
- 神经层级：突触、engram、海马、皮层、前额叶、杏仁核、睡眠和状态依赖检索。
- 计算层级：索引、线索、模式补全、冲突解决、泛化、压缩、遗忘。
- Agent 层级：用户偏好、长期对话、任务历史、项目上下文、专业领域经验、游戏角色连续性。

## Non-goals

暂时不做：

- 把大脑机制直接等同于 LLM 机制。
- 写一套泛泛的 neuroscience 教材。
- 直接实现生产级 memory system。
- 在没有来源核查前把内容晋升为 `knowledge/` 稳定笔记。
- 把用户隐私、删除权、记忆治理问题当作次要细节。

## Working Distinctions

| 概念 | 说明 | 在 Agent 中的对应问题 |
| --- | --- | --- |
| 参数化知识 | 模型训练后写入参数的世界知识 | 难以个人化、难以删除、难以追踪来源 |
| 上下文记忆 | 当前窗口内可见内容 | 容量有限，跨 session 不稳定 |
| 外部长期 memory | 持久化记录、索引、摘要或结构化状态 | personal assistant 的主要设计对象 |
| 情景记忆 | 与具体事件、时间、对象、上下文绑定 | 用户经历、项目历史、对话事件 |
| 语义记忆 | 从经验中抽象出的稳定知识 | 用户长期偏好、概念图谱、专业知识 |
| 程序性记忆 | 如何做某类任务 | 工作流、tool 使用习惯、自动化策略 |

## Current View

当前初步判断：

- Agent memory 不能只等于向量库检索。
- 有用的长期 memory 至少需要生命周期管理：encoding, consolidation, retrieval, update, forgetting。
- 大脑机制对 Agent 设计的价值主要在计算原则层，而不是生物实现层。
- 最危险的误区是把“能检索旧文本”误认为“拥有可用记忆”。

这些判断目前是 assistant synthesis / user hypothesis，需要通过文献和实验继续验证。

## Core Files

- `research-roadmap.md`: 分阶段研究路线。
- `../../questions/brain-memory-for-ai-agents/open-questions.md`: 开放问题和拆解。
- `hypotheses.md`: 当前假设库。
- `mechanism-to-agent-design.md`: 大脑机制到 Agent memory 设计的映射表。
- `../../papers/brain-memory-for-ai-agents/neuroscience-memory-learning-route.md`: 神经科学记忆机制学习路线。
- `../../sources/neuroscience-memory-learning-sources.md`: 神经科学记忆机制文献学习来源地图。
- `../../sessions/2026-06-18-memory-retrieval-mechanism.md`: seed session。
- `../../sources/brain-memory-and-agent-memory-sources.md`: 来源地图。

## Next Action

1. 核查 seed sources，优先读综述和代表性 Agent memory 论文。
2. 把“记忆检索不是完整调用，而是部分激活到模式补全”的问题整理成第一张机制图。
3. 在 `mechanism-to-agent-design.md` 中继续填充证据强度和工程风险。
4. 选择一个最小 Agent memory use case，例如 personal assistant 的长期偏好记忆，作为后续架构 spec 的落点。
