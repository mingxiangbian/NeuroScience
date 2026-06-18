# Session: World Model and Cognitive Memory

---
date: 2026-06-19
topic: world model and cognitive memory
status: brainstorm
tags: [memory, world-model, cognitive-memory, ai-agent, reward]
sources:
  - https://chatgpt.com/share/6a341b42-defc-83ea-ae32-7c6fb5716fda
  - ../projects/brain-memory-for-ai-agents/README.md
---

## User Question

用户提供了一条关于“世界模型与大模型区别”的 shared ChatGPT conversation，希望判断是否需要整理。该记录实际讨论的核心不是普通概念区分，而是 human memory、AI memory、world model、persistent cognitive agent 和 memory architecture 的关系。

## Short Answer

这条记录值得作为 brainstorm session 保存，但暂时不应晋升为 `knowledge/`。它提出了一个重要分叉：如果 AI memory 只优化 task success 或 prediction accuracy，可能会得到 engineering memory / task memory；如果目标是构建更接近长期个人助手或 persistent agent 的 memory，则还需要考虑 identity continuity、emotional salience、social modeling、grounding、adaptation 和可更新性。

更准确的项目问题不是“world model 是否等于 cognitive memory”，而是：

> 一个 persistent cognitive agent 需要怎样的 memory objective、architecture 和 reward，才能超出短期任务工具的范围？

## Key Concepts

| 中文 | English | 说明 |
| --- | --- | --- |
| 世界模型 | world model | 系统对外部环境状态、动态和后果的内部模型；最低定义不要求人类式认知记忆。 |
| 认知记忆 | cognitive memory | 不只服务任务准确率，还涉及情绪权重、身份连续性、社会建模、偏好和经历。 |
| 持续智能体 | persistent agent | 跨 session 保持状态、目标、记忆和行为连续性的 Agent。 |
| 工程记忆 | engineering memory | 主要优化 task success、prediction accuracy、loss minimization 的记忆设计。 |
| 目标函数错配 | objective mismatch | 训练或优化目标与目标认知功能不一致。 |
| 情绪显著性 | emotional salience | 影响记忆写入、检索优先级和长期可访问性的候选门控信号。 |
| 身份连续性 | identity continuity | Agent 或人类主体在时间中的偏好、经历、自我叙事和行为稳定性。 |
| 混合认知记忆 | hybrid cognitive memory | 由 episodic trace、graph / semantic memory、latent state 等组成的候选架构。 |

## Evidence Used

| 来源 | 类型 | 作用 |
| --- | --- | --- |
| ChatGPT shared conversation: 世界模型与大模型区别 | prior conversation | 作为 brainstorm seed 和待验证假设来源，不作为科学证据。 |
| `projects/brain-memory-for-ai-agents/` | project context | 将讨论放入长期 memory 项目，而不是单独散落。 |

## Claims

| Claim | Evidence strength | Claim type | Notes |
| --- | --- | --- | --- |
| `self-supervised learning` 不等于 human memory。 | speculative | assistant synthesis | 方向合理，但需要具体化：不等于哪一类 human memory，在哪些任务上不同。 |
| human memory 不只服务 prediction accuracy，也服务 survival、emotional salience、social modeling、identity continuity。 | preliminary / speculative | assistant synthesis | 听起来合理，但记录中没有文献证据；后续需要分项验证。 |
| 如果 AI memory 只优化 task success，可能更像工具记忆，而不是 cognitive memory。 | speculative | user hypothesis / assistant synthesis | 是项目值得保留的核心假设。 |
| `world model` 不等于 human-like cognitive system。 | preliminary | assistant synthesis | 这是重要澄清：world model 的最低定义可以比 cognitive memory 更窄。 |
| persistent cognitive agent 可能比 world model 更高一层，因为它还包含长期记忆、身份连续性和行动稳定性。 | speculative | assistant synthesis | 适合作为开放问题，而不是结论。 |
| emotion 可以被工程化理解为 memory write / retrieval policy 的一类 gate。 | speculative | assistant synthesis | 这个点很有价值，但必须避免说 AI 有生物情绪。 |
| hybrid cognitive memory 可以由 latent state、graph memory 和 episodic trace 组成。 | speculative | assistant synthesis | 是架构 brainstorm，不是已验证方案。 |
| memory reward 不应只包含 task utility，还应包含 consistency、compression、grounding、adaptation 等目标。 | speculative | assistant synthesis | 值得进入项目假设库和后续 eval 设计。 |

## Design Notes

这条记录里最值得保留的设计方向是：

```text
Frozen reasoning model
+ learned cognitive memory controller
+ hybrid graph / episodic / latent state
+ multi-objective reward
```

这比纯 RAG 更接近 memory system，也比端到端训练整个大模型更现实。但它仍然只是一个工程假设，需要拆成可验证模块。

## Important Distinctions

### World Model vs Cognitive Memory

`world model` 的最低定义是系统能表示环境状态、预测状态变化和支持行动选择。它不必拥有情绪记忆、身份记忆或丰富情景记忆。

`cognitive memory` 更强调主体连续性和经历组织。它可能包含 world model，但不等于 world model。

### Task Agent vs Persistent Agent

`task agent` 可以只用工程记忆，优化任务完成率、检索效率和上下文复用。

`persistent agent` 需要更强的长期 memory：它要维持偏好、项目历史、社会关系、身份连续性、可纠错历史和长期适应。

### Memory Objective vs Memory Mechanism

记录里最有价值的点是把目标函数拉出来讨论。memory architecture 不能只问“存在哪里、怎么检索”，还要问：

- memory 应该优化什么？
- 哪些 memory 应该被保留，即使它们不直接提高当前任务得分？
- 什么样的 memory 会让 Agent 更稳定、更可纠正、更像长期助手？

## Candidate Reward Dimensions

| Reward / Loss | 问题 | 风险 |
| --- | --- | --- |
| Task Utility | memory 是否提高任务完成率？ | 会把系统推向纯工具记忆。 |
| Consistency | memory 是否让 Agent 跨时间行为更稳定？ | 可能固化旧偏好。 |
| Compression | memory 是否足够简洁但不丢关键状态？ | 摘要漂移或丢失证据。 |
| Grounding | memory 是否保留来源和证据？ | 存储成本和检索复杂度上升。 |
| Adaptation | memory 是否能随新证据更新？ | 过度更新会破坏稳定性。 |
| Identity Stability | memory 是否维持长期主体/助手连续性？ | 容易滑向人格化过度解释。 |

## Uncertainties and Disagreements

- “human memory 不是 optimization system”这句话需要降级。更稳妥的说法是：human memory 不是以单一 task accuracy 或 prediction loss 为目标的系统。
- `cognitive memory` 是否应该成为 AI Agent 的目标，取决于产品目标；并非所有 Agent 都需要。
- 情绪记忆不能直接迁移到 AI；工程上只能讨论 salience、priority、risk、self-relevance 等门控变量。
- `world model` 和 `cognitive memory` 的边界需要继续澄清，避免把 world model 定义得过宽。
- 多目标 reward 可能引入冲突，例如 consistency 与 adaptation、compression 与 grounding 之间存在张力。

## Follow-up Questions

- Agent memory 的 objective function 应该包含哪些项？
- 什么任务必须使用 cognitive memory，而不是 engineering memory？
- `emotion = memory write policy` 这个类比能否落成 salience gating？
- `identity continuity` 对 personal assistant 是必要条件、可选体验，还是风险？
- hybrid cognitive memory 的最小实现应该包含哪些状态：episodic trace、semantic graph、latent state、preference profile、audit trail？
- 如何评估 memory 是否让 Agent 更像长期助手，而不是只提高单次任务表现？

## Files Updated

- `../projects/brain-memory-for-ai-agents/open-questions.md`
- `../projects/brain-memory-for-ai-agents/hypotheses.md`
