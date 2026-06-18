# Research Roadmap: Brain Memory for AI Agents

---
date: 2026-06-18
status: draft
tags: [memory, roadmap, ai-agent]
---

## Success Criteria

这个项目第一阶段成功，不是因为读完很多论文，而是因为能形成一个可检验的框架：

```text
brain mechanism -> computational principle -> agent memory design -> evidence strength -> risk
```

每条映射都要标明它是 literature claim、assistant synthesis、user hypothesis 还是 open question。

## Phase 0: Project Setup

状态：进行中。

目标：

- 建立项目入口和记录结构。
- 保存之前关于“人脑记忆机制”的 seed session。
- 建立 source map，区分已定位来源和待核查来源。

产物：

- `README.md`
- `open-questions.md`
- `hypotheses.md`
- `mechanism-to-agent-design.md`
- `../../sessions/2026-06-18-memory-retrieval-mechanism.md`
- `../../sources/brain-memory-and-agent-memory-sources.md`

## Phase 1: Concept Map

目标：

- 建立记忆机制的最小概念图。
- 区分 encoding, consolidation, retrieval, reconsolidation, forgetting。
- 区分 episodic memory, semantic memory, procedural memory, working memory, preference memory。
- 明确这些概念在 Agent 设计中可能对应什么，不对应什么。

重点问题：

- retrieval 是“查库”还是线索驱动的部分激活和模式补全？
- hippocampal indexing 可以怎样启发 Agent memory index？
- forgetting 是缺陷、压缩、访问失败，还是主动治理机制？

验证方式：

- 每个概念至少有一个可靠 neuroscience 来源。
- 每个 AI 类比都标注类比层级，不写成生物事实。

## Phase 2: Neuroscience Mechanisms

目标：

- 阅读记忆机制综述和代表性实验。
- 建立可复用的 `knowledge/` 候选内容，但先不晋升。

主题：

- engram: encoding, consolidation, retrieval, forgetting。
- hippocampus: indexing, pattern separation, pattern completion。
- cortex and mPFC: systems consolidation, gist-like memory, top-down control。
- amygdala: emotional salience and memory modulation。
- sleep and offline replay: consolidation and memory reorganization。
- reconsolidation: retrieved memories can become modifiable。

验证方式：

- 方法层面说明测到了什么，不能推出什么。
- 区分相关性、预测能力、因果操控和机制解释。

## Phase 3: Agent Memory Literature

目标：

- 建立 LLM Agent memory 的设计空间。
- 比较 storage, retrieval, reflection, update, compression, deletion, eval。

主题：

- memory module survey。
- Generative Agents 的 observation, reflection, planning。
- MemGPT 的 memory tiers 和 context management。
- long-term dialogue memory evaluation。
- preference memory update。
- dynamic / agentic memory organization。

验证方式：

- 检查 baseline 是否合理。
- 检查 eval 是否真的测 memory，而不是只测短上下文复述。
- 检查是否有跨 session、长期一致性、错误纠正和遗忘能力。

## Phase 4: Mechanism-to-Design Mapping

目标：

- 把神经机制转成 Agent memory design constraints。
- 明确哪些迁移只是类比，哪些有计算意义。

产物：

- `mechanism-to-agent-design.md` 的完整表格。
- 第一版 `Agent Memory Architecture Spec` 草案。

候选设计维度：

- write policy: 什么时候写入 memory？
- retrieval policy: 用什么线索触发检索？
- consolidation policy: 什么时候摘要、归并、强化或降权？
- update policy: 新信息如何修改旧 memory？
- forgetting policy: 如何遗忘、过期、删除或降低可访问性？
- audit policy: 用户如何查看、纠错和撤回 memory？

## Phase 5: Minimal Prototype or Design Spec

目标：

- 选择一个最小场景，把研究转成可测试设计。

候选场景：

- personal assistant 长期偏好记忆。
- 游戏 NPC 角色连续性。
- 专业领域研究助手的项目上下文 memory。
- 多 session 写作或研究协作助手。

产物：

- `Agent Memory Architecture Spec`
- memory schema
- memory lifecycle
- eval checklist
- failure modes

## Stop Conditions

如果出现以下情况，暂停写结论，回到来源核查：

- 只剩类比，没有机制证据。
- Agent 设计结论无法被 eval。
- 把检索增强、长上下文和长期 memory 混为一谈。
- 把用户偏好写成不可质疑的永久事实。
