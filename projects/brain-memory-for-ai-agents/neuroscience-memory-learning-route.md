# Neuroscience Memory Learning Route

---
date: 2026-06-19
status: draft
project: brain-memory-for-ai-agents
tags: [memory, neuroscience, learning-route, ai-agent]
related:
  - README.md
  - research-roadmap.md
  - open-questions.md
  - hypotheses.md
  - mechanism-to-agent-design.md
---

## Purpose

这个文件记录当前阶段的学习路线。目标不是提出 Agent memory architecture，而是先建立神经科学层面的记忆机制地图，为后续判断哪些机制能成为计算原则提供基础。

当前对应项目阶段：

- `research-roadmap.md` Phase 1: Concept Map。
- `research-roadmap.md` Phase 2: Neuroscience Mechanisms。
- `open-questions.md` Q1-Q4：retrieval、hippocampal indexing、forgetting、reconsolidation。
- `open-questions.md` Q10-Q12：memory、world model、cognitive memory、persistent agent 的边界问题。

## Boundaries

本路线暂时不做：

- 不设计 Agent memory 架构。
- 不写 `Agent Memory Architecture Spec`。
- 不把 brainstorm 内容晋升到 `knowledge/`。
- 不把脑机制直接等同于 LLM 或 Agent 机制。

本路线只回答：

- 人脑记忆有哪些关键机制？
- 这些机制分别处在什么层级：突触、细胞、engram、环路、系统、认知、行为？
- 哪些结论是共识，哪些是强证据，哪些仍有争议或只是计算模型？
- 哪些概念需要先学清楚，之后才适合谈 Agent memory？

## Learning Order

### Stage 0. 建立基础分类

目标：先避免把所有 memory 混成一种东西。

要学的概念：

- 情景记忆（episodic memory）。
- 语义记忆（semantic memory）。
- 程序性记忆（procedural memory）。
- 工作记忆（working memory）。
- 情绪记忆（emotional memory）。
- schema、gist、world model 的区别。

关键问题：

- 一次具体经历如何同时留下细节型表征和抽象型表征？
- 情景记忆和语义记忆是串行转化，还是并行存在？
- 情绪记忆是否是独立系统，还是对其他记忆系统的调制？

阶段产物：

- 一张 memory type taxonomy。
- 每种 memory type 对应的主要脑区和证据强度。

### Stage 1. 记忆生命周期

目标：把 memory 看成动态生命周期，而不是静态存储。

要学的概念：

- 编码（encoding）。
- 突触巩固（synaptic consolidation）。
- 系统巩固（systems consolidation）。
- 提取（retrieval）。
- 再巩固（reconsolidation）。
- 遗忘（forgetting）。

关键问题：

- 什么改变发生在突触和细胞层级？
- 什么改变发生在海马、皮层、杏仁核、前额叶之间？
- retrieval 是否会改变原记忆？
- forgetting 是存储丢失、检索失败、主动抑制，还是多机制组合？

阶段产物：

- 一张 `encoding -> consolidation -> retrieval -> reconsolidation / forgetting` 生命周期图。
- 每个阶段至少对应一个可靠 neuroscience source。

### Stage 2. Retrieval: 线索、部分激活和模式补全

目标：回答项目 Q1：retrieval 是否更像线索驱动的部分激活，而不是简单查库。

要学的概念：

- 编码特异性（encoding specificity）。
- 线索依赖检索（cue-dependent retrieval）。
- 重新激活 / 恢复（reactivation / reinstatement）。
- 模式补全（pattern completion）。
- 模式分离（pattern separation）。
- 熟悉感（familiarity）和回想（recollection）。

关键问题：

- 当前线索如何触发部分记忆痕迹？
- hippocampus 如何支持不完整线索下的模式补全？
- 相似经历如何避免互相干扰？
- 为什么 retrieval 可能产生 false memory 或过度泛化？

阶段产物：

- 一张 retrieval 机制图：cue -> partial activation -> competition -> completion -> explicit recall / failure。
- 区分 `reinstatement`、`reconstruction`、`recognition`、`recall`。

### Stage 3. Hippocampal indexing 和海马计算

目标：回答项目 Q2：hippocampal indexing theory 到底说了什么，证据边界在哪里。

要学的概念：

- 海马索引理论（hippocampal indexing theory）。
- 齿状回（dentate gyrus, DG）。
- CA3 autoassociative network。
- CA1 output / comparator。
- entorhinal cortex。
- cognitive map。
- place cells、grid cells、time cells、episode-specific neurons。

关键问题：

- 海马 index 是指向分布式皮层表征的 pointer，还是自身也存储记忆内容？
- DG / CA3 / CA1 在 pattern separation、completion、输出中分别扮演什么角色？
- 人类单神经元研究能支持到什么程度？
- spatial memory 和 episodic memory 是两套系统，还是共享 scaffold？

阶段产物：

- 一张 hippocampus subfield 功能表。
- 一张 `index / binding / separation / completion` 概念关系图。

### Stage 4. Engram: 记忆痕迹的动态性

目标：理解当前前沿为什么不再把 engram 视为固定痕迹。

要学的概念：

- 记忆痕迹（engram）。
- engram cell。
- engram allocation。
- engram reactivation。
- engram competition。
- engram accessibility。
- representational drift。
- inhibitory plasticity。

关键问题：

- 哪些细胞会进入某个 engram？
- engram 是稳定集合，还是随时间和经验变化的动态集合？
- 记忆稳定性和灵活性如何同时存在？
- forgetting 是否可能是 engram 可访问性变化，而不是痕迹消失？

阶段产物：

- 一张 dynamic engram 概念图。
- 对 `stable trace` 和 `dynamic engram` 两种观点做证据对比。

### Stage 5. Consolidation、schema 和语义化

目标：理解记忆如何从细节经历转成更稳定、更抽象、更可泛化的知识。

要学的概念：

- systems consolidation。
- multiple trace theory。
- trace transformation theory。
- schema。
- gist memory。
- semanticization。
- hippocampus-neocortex interaction。
- medial prefrontal cortex (mPFC)。

关键问题：

- 远期记忆是否真的不再需要海马？
- 细节型记忆和 gist 型记忆是否同时存在？
- schema 如何加速新信息整合？
- 语义化会带来什么代价：细节丢失、过度泛化、false memory？

阶段产物：

- 一张 systems consolidation 理论对照表。
- 一张 `episode -> schema / gist / semantic memory` 的证据边界图。

### Stage 6. Sleep、dream 和 replay

目标：理解睡眠、休息和 replay 在 memory consolidation 中的作用。

要学的概念：

- hippocampal replay。
- sharp-wave ripples (SPW-Rs)。
- slow oscillations。
- sleep spindles。
- hippocampal-cortical coupling。
- awake replay。
- offline learning。

关键问题：

- replay 是重复过去经验，还是重组经验？
- sleep replay 如何影响 consolidation、generalization 和 forgetting？
- dream 与 memory replay 的关系是否有强证据，还是仍偏推测？
- 人类 replay 研究和啮齿动物 replay 研究的证据差异是什么？

阶段产物：

- 一张 sleep / replay 机制图。
- 区分 `sleep-dependent consolidation`、`offline replay`、`dream` 三个概念。

### Stage 7. Reconsolidation、update 和 extinction

目标：回答项目 Q4：被提取的旧记忆是否会进入可修改状态。

要学的概念：

- memory reconsolidation。
- memory destabilization。
- memory updating。
- extinction。
- inhibitory learning。
- prediction error。
- event representation update。

关键问题：

- retrieval 什么时候会触发 reconsolidation？
- reconsolidation 是覆盖旧记忆，还是整合新信息？
- extinction 是删除旧关联，还是学习一个抑制旧反应的新关联？
- prediction error 在 memory update 中扮演什么角色？

阶段产物：

- 一张 `retrieval -> destabilization -> update / restabilization` 流程图。
- 区分 reconsolidation、extinction、new learning。

### Stage 8. Forgetting: 主动遗忘、竞争和可访问性

目标：回答项目 Q3：forgetting 不是单一失败模式。

要学的概念：

- active forgetting。
- retrieval failure。
- interference。
- inhibitory control。
- engram accessibility。
- engram competition。
- decay。
- suppression。
- representational drift。

关键问题：

- 遗忘是痕迹消失，还是访问失败？
- 哪些遗忘是适应性的？
- 新记忆如何竞争旧记忆的表达？
- 过度稳定的记忆为什么可能变成问题？

阶段产物：

- 一张 forgetting taxonomy。
- 一张 `storage loss / accessibility loss / inhibition / competition / updating` 对照表。

### Stage 9. Emotional and motivated memory

目标：理解情绪和动机如何改变 encoding、consolidation 和 retrieval。

要学的概念：

- amygdala-hippocampus interaction。
- emotional salience。
- aversive memory。
- reward modulation。
- dopamine。
- norepinephrine。
- locus coeruleus。
- ventral tegmental area (VTA)。
- neuromodulation。

关键问题：

- 杏仁核是否存储情景记忆，还是主要调制海马记忆？
- 情绪为什么会增强某些记忆，同时也可能损害细节分辨？
- reward / motivation 如何影响什么被写入长期记忆？
- 情绪记忆和恐惧消退的前沿证据来自哪些方法？

阶段产物：

- 一张 emotional memory modulation 图。
- 区分 `emotion as content` 和 `emotion as modulation`。

### Stage 10. Computational neuroscience models

目标：只学习神经科学中的计算模型，不转入 Agent 架构。

要学的模型：

- attractor network。
- complementary learning systems (CLS)。
- hippocampal replay model。
- generative model of memory construction。
- spatial scaffold model。
- predictive processing / prediction error。
- cognitive map and planning model。

关键问题：

- 哪些模型解释 biological data？
- 哪些模型只是 formal analogy？
- 模型解释的是 encoding、retrieval、consolidation、forgetting，还是 behavior？
- 模型是否有可检验预测？

阶段产物：

- 一张 computational model 对照表。
- 每个模型标注 claim type：literature claim、computational model、assistant synthesis、open question。

## Frontier Watchlist

当前最值得持续追踪的前沿方向：

1. Dynamic engram
   重点从“记忆存在哪里”转向“engram 如何随时间、经验、抑制性可塑性和检索状态变化”。

2. Human intracranial recordings
   人类单神经元、iEEG、theta/gamma coupling、sharp-wave ripples 正在补足 fMRI 时间分辨率不足的问题。

3. Hippocampus in remote memory
   远期记忆是否仍依赖海马仍有争议。最新综述强调海马可能长期参与细节保留、再巩固和皮层交互。

4. Active forgetting and accessibility
   遗忘越来越被看作适应性机制，可能涉及 engram 可访问性、竞争、抑制和重塑。

5. Non-neuronal and inhibitory mechanisms
   microglia、astrocytes、interneurons、axon initial segment plasticity 等正在进入记忆更新和消退研究。

6. Sleep / replay / offline cognition
   replay 不只服务巩固，也可能服务泛化、未来情境构造和结构化知识重组。

7. Emotional and motivated memory
   杏仁核-海马动态耦合、dopamine / norepinephrine 等 neuromodulatory systems 是理解 salience gating 的关键。

## Initial Source List

这些来源先作为学习入口，不直接作为最终结论。

| Topic | Source | Type | Status |
| --- | --- | --- | --- |
| Engram lifecycle | Guskjolen & Cembrowski, "Engram neurons: Encoding, consolidation, retrieval, and forgetting of memory", Molecular Psychiatry, 2023 | review | priority |
| Engram flexibility | "Memory engram stability and flexibility", Neuropsychopharmacology, 2024 | review | priority |
| Systems consolidation | Park & Kaang, "Role of the hippocampus in systems consolidation of remote fear memory", Experimental & Molecular Medicine, 2026 | review | priority |
| Human replay | "Replay and Ripples in Humans", Annual Review of Neuroscience, 2025 | review | priority |
| Motivated memory | "Motivation as Neural Context for Adaptive Learning and Memory Formation", Annual Review of Psychology, 2026 | review | priority |
| Emotional retrieval | Costa et al., "Human hippocampal reactivation of amygdala encoding-related gamma patterns during aversive memory retrieval", Nature Communications, 2025 | original research | priority |
| Emotional learning and extinction | Sonkusare et al., "Adaptive shifts in amygdala-hippocampal theta coupling govern aversive learning and extinction", Nature Communications, 2026 | original research | watch |
| Natural forgetting | "Natural forgetting reversibly modulates engram expression", eLife, 2024 | original research | priority |
| Engram competition | "The cost of remembering: engram competition as a flexible mechanism of forgetting", Trends in Neurosciences, 2025 | perspective / review | priority |
| Memory construction | Spens & Burgess, "A generative model of memory construction and consolidation", Nature Human Behaviour, 2024 | computational model | priority |
| Spatial scaffold | "Episodic and associative memory from spatial scaffolds in the hippocampus", Nature, 2025 | computational / original research | watch |
| Adaptive episodic memory | "Adaptive episodic memory: how multiple memory representations drive behavior in humans and nonhumans", Physiological Reviews, 2026 | review | priority |

## Reading Rules

每读一个来源时记录：

- 论文或综述回答了什么问题。
- 研究对象是人类、啮齿动物、体外模型还是计算模型。
- 方法测到了什么，不能推出什么。
- 结论属于哪个层级：分子、突触、细胞、engram、环路、系统、认知、行为、计算模型。
- 证据强度：consensus、strong evidence、preliminary evidence、disputed、speculative。
- 是否能支持项目中的某个 open question。

## First Three Reading Targets

优先顺序：

1. Guskjolen & Cembrowski 2023
   用来建立 memory lifecycle 和 engram 基础图。

2. Park & Kaang 2026
   用来理解 systems consolidation 的最新争议，尤其是远期记忆中海马是否仍参与。

3. "Replay and Ripples in Humans" 2025
   用来连接 sleep、replay、offline learning 和 human evidence。

完成这三篇后，再进入 forgetting / reconsolidation / emotional memory。

## Temporary Synthesis Constraint

在完成第一轮阅读前，只允许形成以下类型的输出：

- session note。
- source map。
- open question update。
- hypothesis update。
- mechanism concept map draft。

暂时不输出：

- Agent memory architecture。
- production memory schema。
- eval checklist。
- `knowledge/` 稳定知识条目。
