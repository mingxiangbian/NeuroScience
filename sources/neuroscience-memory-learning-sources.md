# Neuroscience Memory Learning Sources

---
date: 2026-06-19
status: draft
project: brain-memory-for-ai-agents
scope: neuroscience memory mechanisms before agent architecture
tags: [memory, neuroscience, sources, learning-route]
related:
  - ../projects/brain-memory-for-ai-agents/neuroscience-memory-learning-route.md
  - ../projects/brain-memory-for-ai-agents/open-questions.md
  - ../sources/brain-memory-and-agent-memory-sources.md
---

## Purpose

这份 source map 服务 `brain-memory-for-ai-agents` 的前期学习阶段。

这里的“找全”不是收集记忆研究领域的所有论文，而是覆盖当前学习路线中必须理解的机制模块：

- memory type taxonomy。
- encoding / consolidation / retrieval / reconsolidation / forgetting 生命周期。
- retrieval cue、partial activation、pattern completion / separation。
- hippocampal indexing、place/grid/time cells、episode-specific neurons。
- engram、dynamic engram、engram accessibility。
- systems consolidation、schema、semanticization。
- sleep、dream、replay、sharp-wave ripples。
- extinction、prediction error、memory update。
- active forgetting、interference、inhibitory control。
- emotional / motivated memory。
- computational neuroscience models。

当前阶段只做来源地图，不把这些来源结论晋升到 `knowledge/`。每篇论文只有在后续读完并完成质量检查后，才进入 `papers/` 或稳定知识笔记。

## How to Use

阅读顺序不要按年份，也不要按引用量。建议按学习路线分阶段读：

1. 每个阶段先读 1 篇综述，建立概念边界。
2. 再读 1-2 篇关键实验，看证据来自什么方法。
3. 前沿论文只作为 watch，不急于当成稳定结论。
4. 每读一篇都记录：研究对象、方法、核心主张、证据强度、局限、对应项目问题。

优先级说明：

- `core`: 学这个阶段必须读。
- `classic`: 历史或理论根基，后续概念会反复出现。
- `mechanism`: 关键实验或机制证据。
- `frontier`: 2023-2026 前沿方向，先跟踪，读时要更严格检查。
- `optional`: 有用但不是第一轮必须读。

## First-Round Reading Packet

第一轮不要超过这些。读完后再扩展。

| Order | Source | Why first |
| --- | --- | --- |
| 1 | Guskjolen & Cembrowski, 2023, "Engram neurons: Encoding, consolidation, retrieval, and forgetting of memory" | 用一篇综述建立 memory lifecycle 和 engram 语言。 |
| 2 | Squire & Dede, 2015, "Conscious and Unconscious Memory Systems" | 建立 memory systems 分类，避免把所有 memory 混成一种。 |
| 3 | Dudai, Karni & Born, 2015, "The Consolidation and Transformation of Memory" | 把 consolidation 理解为 transformation，而不是简单搬运。 |
| 4 | Teyler & Rudy, 2007, "The hippocampal indexing theory and episodic memory" | 学 hippocampal indexing 的现代入口。 |
| 5 | Yassa & Stark, 2011, "Pattern separation in the hippocampus" | 连接 DG / CA3 与 pattern separation / completion。 |
| 6 | Josselyn, Kohler & Frankland, 2015, "Finding the engram" | 学 engram 概念、证据和实验逻辑。 |
| 7 | Rasch & Born, 2013, "About Sleep's Role in Memory" | 学 sleep-dependent consolidation 的大框架。 |
| 8 | Nader & Hardt, 2009, "A single standard for memory: the case for reconsolidation" | 学 retrieval 如何让旧记忆变得可修改。 |
| 9 | Hardt, Nader & Nadel, 2013, "Decay happens: the role of active forgetting in memory" | 建立 active forgetting 不是被动失败的入口。 |
| 10 | McGaugh, 2004, "The amygdala modulates the consolidation of memories of emotionally arousing experiences" | 建立 emotional memory 的调制视角。 |
| 11 | McClelland, McNaughton & O'Reilly, 1995, "Why there are complementary learning systems..." | 学 CLS 这条从神经科学到计算模型的主线。 |
| 12 | Spens & Burgess, 2024, "A generative model of memory construction and consolidation" | 进入现代 computational memory construction。 |

## Stage 0. Memory Type Taxonomy

目标：先把 memory types 分开，尤其区分 declarative / nondeclarative、episodic / semantic、working memory、emotional memory。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Tulving, 1972, "Episodic and Semantic Memory" | classic chapter | episodic / semantic distinction 的源头。 |
| core | Tulving, 2002, "Episodic Memory: From Mind to Brain" | review | episodic memory 的认知和脑机制入口。 |
| core | Squire, 2004, "Memory systems of the brain: a brief history and current perspective" | review | 记忆系统分型和历史框架。 |
| core | Squire & Dede, 2015, "Conscious and Unconscious Memory Systems" | review | declarative / nondeclarative、working memory、implicit memory。 |
| core | Baddeley, 2012, "Working Memory: Theories, Models, and Controversies" | review | working memory 不等于 long-term memory。 |
| core | Phelps, 2004, "Human emotion and memory: interactions of the amygdala and hippocampal complex" | review | emotional memory 更像调制与交互，不是简单独立存储。 |
| optional | Renoult et al., 2012, "The semanticization of episodic memory" | review / theory | episode 如何变成 semantic / gist 的入口。 |

URLs:

- Tulving 1972: https://alicekim.ca/12.EpSem72.pdf
- Tulving 2002: https://www.annualreviews.org/doi/10.1146/annurev.psych.53.100901.135114
- Squire 2004: https://whoville.ucsd.edu/PDFs/384_Squire_%20NeurobiolLearnMem2004.pdf
- Squire & Dede 2015: https://pmc.ncbi.nlm.nih.gov/articles/PMC4355270/
- Baddeley 2012: https://www.annualreviews.org/content/journals/10.1146/annurev-psych-120710-100422
- Phelps 2004: https://pubmed.ncbi.nlm.nih.gov/15082325/

## Stage 1. Memory Lifecycle

目标：把 memory 看成动态生命周期，而不是静态存储。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| core | Guskjolen & Cembrowski, 2023, "Engram neurons: Encoding, consolidation, retrieval, and forgetting of memory" | review | lifecycle + engram 的主入口。 |
| core | Dudai, Karni & Born, 2015, "The Consolidation and Transformation of Memory" | review | consolidation 作为 transformation。 |
| core | Josselyn, Kohler & Frankland, 2015, "Finding the engram" | review | engram experimental criteria。 |
| mechanism | Josselyn & Tonegawa, 2020, "Memory engrams: Recalling the past and imagining the future" | review | engram cells、distributed ensembles、future imagination。 |
| optional | Kandel et al. / synaptic plasticity reviews | textbook / review | synaptic consolidation 背景，不作为第一轮重点。 |

URLs:

- Guskjolen & Cembrowski 2023: https://www.nature.com/articles/s41380-023-02137-5
- Dudai et al. 2015: https://pubmed.ncbi.nlm.nih.gov/26447570/
- Josselyn et al. 2015: https://doi.org/10.1038/nrn4000
- Josselyn & Tonegawa 2020: https://pubmed.ncbi.nlm.nih.gov/31896692/

## Stage 2. Retrieval, Cues, Partial Activation

目标：理解 retrieval 为什么不是“整条记忆查出来”，而是 cue-dependent reactivation、competition、completion 和 reconstruction。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Tulving & Thomson, 1973, "Encoding specificity and retrieval processes in episodic memory" | empirical / theory | encoding specificity 的源头。 |
| core | Rugg & Wilding, 2000 / Rugg & Johnson, 2015 retrieval reviews | review | human episodic retrieval 的 neuroimaging 入口。 |
| core | Johnson & Rugg, 2007, "Recollection and the reinstatement of encoding-related cortical activity" | original / fMRI | reinstatement 证据。 |
| core | Yonelinas, 2002, "The Nature of Recollection and Familiarity" | review | recollection / familiarity 区分。 |
| mechanism | Yassa & Stark, 2011, "Pattern separation in the hippocampus" | review | pattern separation 与类似记忆混淆。 |
| optional | Karpicke & Roediger retrieval practice literature | cognitive psychology | retrieval 会改变后续记忆表现，但不要直接等同 reconsolidation。 |

URLs:

- Tulving & Thomson 1973: https://doi.org/10.1037/h0020071
- Tulving & Thomson 1973 PDF: https://alicekim.ca/9.ESP73.pdf
- Johnson & Rugg 2007: https://pubmed.ncbi.nlm.nih.gov/17204822/
- Yonelinas 2002: https://doi.org/10.1006/jmla.2002.2864
- Yassa & Stark 2011: https://pmc.ncbi.nlm.nih.gov/articles/PMC3183227/

## Stage 3. Hippocampal Indexing and Hippocampal Computation

目标：理解 hippocampus 是 index、binding system、autoassociative memory，还是也存储内容；区分理论层和实验层。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Marr, 1971, "Simple memory: a theory for archicortex" | computational theory | hippocampal memory model 的早期理论源头。 |
| classic | Teyler & DiScenna, 1986, "The hippocampal memory indexing theory" | theory | hippocampus as index 的经典版本。 |
| core | Teyler & Rudy, 2007, "The hippocampal indexing theory and episodic memory" | review / theory | indexing theory 的现代入口。 |
| core | Yassa & Stark, 2011, "Pattern separation in the hippocampus" | review | DG / CA3 与 separation。 |
| core | Moser et al. / place-grid review, "Place Cells, Grid Cells, and Memory" | review | spatial map 与 memory 的关系。 |
| mechanism | Umbach et al., 2020, "Time cells in the human hippocampus and entorhinal cortex support episodic memory" | human single-neuron | time cells 与 episodic sequence。 |
| frontier | Kolibius et al., 2023, "Hippocampal neurons code individual episodic memories in humans" | human single-neuron | episode-specific neurons；样本和区域特异性要谨慎。 |
| frontier | Chandra et al., 2025, "Episodic and associative memory from spatial scaffolds in the hippocampus" | computational / original | spatial scaffold 解释 episodic / associative memory。 |

URLs:

- Marr 1971: https://pubmed.ncbi.nlm.nih.gov/4399412/
- Marr 1971 PDF: https://www.cs.cmu.edu/afs/cs/academic/class/15883-f17/readings/marr-1971.pdf
- Teyler & DiScenna 1986: https://pubmed.ncbi.nlm.nih.gov/3008780/
- Teyler & Rudy 2007: https://pubmed.ncbi.nlm.nih.gov/17696170/
- Place Cells, Grid Cells, and Memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC4315928/
- Time cells in humans: https://www.pnas.org/doi/10.1073/pnas.2013250117
- Episode-specific neurons: https://www.nature.com/articles/s41562-023-01706-6
- Spatial scaffolds: https://www.nature.com/articles/s41586-024-08392-y

## Stage 4. Engram and Dynamic Memory Traces

目标：理解 engram 从“固定痕迹”走向 dynamic ensemble、accessibility、competition、representational drift。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Josselyn, Kohler & Frankland, 2015, "Finding the engram" | review | engram 概念和实验标准。 |
| classic | Tonegawa et al., 2015, "Memory Engram Cells Have Come of Age" | review | optogenetics 之后的 engram 研究框架。 |
| mechanism | Liu et al., 2012, "Optogenetic stimulation of a hippocampal engram activates fear memory recall" | original / optogenetics | engram cell causality 的经典实验。 |
| mechanism | Ramirez et al., 2013, "Creating a false memory in the hippocampus" | original / optogenetics | engram manipulation 与 false memory。 |
| core | Guskjolen & Cembrowski, 2023 | review | engram lifecycle。 |
| core | "Memory engram stability and flexibility", 2024 | review | stable engram vs flexible engram。 |
| frontier | Tome et al., 2024, "Dynamic and selective engrams emerge with memory consolidation" | original / calcium imaging / optogenetics | engram turnover、inhibitory plasticity、selectivity。 |
| frontier | "Engram Synapses and Synapse Dynamics in Memory Processing", 2026 | review | synapse turnover 与 memory processing，后续 watch。 |

URLs:

- Finding the engram: https://doi.org/10.1038/nrn4000
- Memory Engram Cells Have Come of Age: https://doi.org/10.1016/j.neuron.2015.08.002
- Liu et al. 2012: https://doi.org/10.1038/nature11028
- Ramirez et al. 2013: https://doi.org/10.1126/science.1239073
- Engram lifecycle 2023: https://www.nature.com/articles/s41380-023-02137-5
- Engram stability and flexibility 2024: https://www.nature.com/articles/s41386-024-01979-z
- Dynamic and selective engrams 2024: https://www.nature.com/articles/s41593-023-01551-w
- Engram synapses 2026: https://onlinelibrary.wiley.com/doi/full/10.1111/jnc.70404

## Stage 5. Systems Consolidation, Schema, Gist, Semanticization

目标：理解记忆如何从具体经历变成更稳定、抽象、可泛化但可能失真的知识。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | McClelland, McNaughton & O'Reilly, 1995, "Why there are complementary learning systems..." | computational theory | hippocampus fast learning vs neocortex slow learning。 |
| core | Dudai, Karni & Born, 2015 | review | consolidation as transformation。 |
| core | Moscovitch et al. / Nadel et al., multiple trace and trace transformation reviews | theory / review | standard model vs MTT / TTT。 |
| core | Gilboa & Marlatte, 2017, "Neurobiology of Schemas and Schema-Mediated Memory" | review | schema、vmPFC、hippocampus-neocortex。 |
| mechanism | Tse et al., 2007, "Schemas and memory consolidation" | original / animal | schema 加速整合的经典实验。 |
| mechanism | Sommer, 2022, "Schemas provide a scaffold for neocortical integration of new memories" | original / human fMRI | schema scaffold 与 neocortical integration。 |
| frontier | Park & Kaang, 2026, "Role of the hippocampus in systems consolidation of remote fear memory" | review | remote memory 中 hippocampus 是否长期参与。 |
| frontier | Tarder-Stoll et al., 2026, "Adaptive episodic memory..." | review | multiple memory representations and adaptive behavior。 |

URLs:

- CLS 1995: https://pubmed.ncbi.nlm.nih.gov/7624455/
- CLS 1995 PDF: https://stanford.edu/~jlmcc/papers/McCMcNaughtonOReilly95.pdf
- Consolidation and transformation: https://pubmed.ncbi.nlm.nih.gov/26447570/
- Systems consolidation / transformation review: https://neuropsychologylab.psych.utoronto.ca/files/Systems%20consolidation%2C%20transformation%20and%20reorganization%20Multiple%20Trace%20Theory%2C%20Trace%20Transformation%20Theory%20and%20their%20Competitors.pdf
- Gilboa & Marlatte 2017: https://pubmed.ncbi.nlm.nih.gov/28551107/
- Tse et al. 2007: https://doi.org/10.1126/science.1135935
- Schema scaffold 2022: https://www.nature.com/articles/s41467-022-33517-0
- Park & Kaang 2026: https://www.nature.com/articles/s12276-026-01680-9
- Adaptive episodic memory 2026: https://pubmed.ncbi.nlm.nih.gov/41187993/

## Stage 6. Sleep, Dream, Replay

目标：区分 sleep-dependent consolidation、offline replay、dream，不把 dream 直接等同于 replay。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| core | Rasch & Born, 2013, "About Sleep's Role in Memory" | review | sleep and memory 的大综述。 |
| core | Klinzing, Niethard & Born, 2019, "Mechanisms of systems memory consolidation during sleep" | review | oscillations、slow waves、spindles、hippocampal replay。 |
| core | Joo & Frank, 2018, "The hippocampal sharp wave-ripple in memory retrieval for immediate use and consolidation" | review | SWR 与 retrieval / consolidation。 |
| core | "Replay and Ripples in Humans", 2025 | review | human replay / SPW-Rs 的近年前沿入口。 |
| mechanism | Wamsley & Stickgold, 2011, "Memory, Sleep and Dreaming: Experiencing Consolidation" | review | dream 与 memory consolidation 的证据边界。 |
| mechanism | "Sleep microstructure organizes memory replay", 2025 | original / Nature | sleep microstructure 与新旧 memory replay。 |
| frontier | "Parallel processing of past and future memories through reactivation and synaptic plasticity mechanisms during sleep", 2025 | original / Nature Communications | sleep 同时巩固旧记忆与准备未来学习。 |
| frontier | "Large sharp-wave ripples promote hippocampo-cortical memory consolidation", 2025 | original / watch | SWR size、reactivation、hippocampo-cortical consolidation。 |

URLs:

- Rasch & Born 2013: https://journals.physiology.org/doi/full/10.1152/physrev.00032.2012
- Rasch & Born 2013 PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC3768102/
- Klinzing et al. 2019: https://www.nature.com/articles/s41593-019-0467-3
- Joo & Frank 2018: https://doi.org/10.1038/s41583-018-0077-1
- Replay and Ripples in Humans 2025: https://www.annualreviews.org/content/journals/10.1146/annurev-neuro-112723-024516
- Memory, Sleep and Dreaming: https://pmc.ncbi.nlm.nih.gov/articles/PMC3079906/
- Dreaming and Offline Memory Consolidation: https://pmc.ncbi.nlm.nih.gov/articles/PMC4704085/
- Sleep microstructure 2025: https://www.nature.com/articles/s41586-024-08340-w
- Past/future sleep processing 2025: https://www.nature.com/articles/s41467-025-58860-w
- Large SWRs 2025: https://pubmed.ncbi.nlm.nih.gov/41205608/

## Stage 7. Reconsolidation, Update, Extinction

目标：理解 retrieval 何时让旧记忆进入可修改状态；区分 reconsolidation、extinction、new learning。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Nader, Schafe & LeDoux, 2000, "Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval" | original / animal | reconsolidation 现代经典实验。 |
| core | Nader & Hardt, 2009, "A single standard for memory: the case for reconsolidation" | review | reconsolidation 理论入口。 |
| core | Sara, 2000 / Dudai reconsolidation reviews | review | remembering as a biological process。 |
| core | "An update on memory reconsolidation updating", 2017 | review | reconsolidation-update and prediction error。 |
| mechanism | Sinclair & Barense, 2019, "Prediction Error and Memory Reactivation" | review / theory | incomplete reminders、prediction error、memory updating。 |
| classic | Bouton, 2004, "Context and Behavioral Processes in Extinction" | review | extinction 多数情况下不是删除旧记忆，而是 context-dependent new learning。 |
| core | Bouton et al., 2021, "Behavioral and neurobiological mechanisms of Pavlovian and instrumental extinction learning" | review | extinction 的行为与神经机制。 |
| mechanism | Clem & Huganir, 2010, "Calcium-permeable AMPA receptor dynamics mediate fear memory erasure" | original | erasure vs inhibitory learning 的重要对照。 |

URLs:

- Nader et al. 2000: https://www.nature.com/articles/35021052
- Nader & Hardt 2009: https://pubmed.ncbi.nlm.nih.gov/19229241/
- Reconsolidation and dynamic memory: https://pmc.ncbi.nlm.nih.gov/articles/PMC4588064/
- Reconsolidation updating 2017: https://pmc.ncbi.nlm.nih.gov/articles/PMC5605913/
- Prediction error and reactivation: https://barense.psych.utoronto.ca/wp-content/uploads/2019/11/2019_Sinclair_Barense_TINs.pdf
- Bouton 2004: https://learnmem.cshlp.org/content/11/5/485.full.pdf
- Extinction mechanisms 2021: https://journals.physiology.org/doi/abs/10.1152/physrev.00016.2020
- Clem & Huganir 2010: https://doi.org/10.1126/science.1195298

## Stage 8. Forgetting, Inhibition, Competition, Accessibility

目标：把 forgetting 拆成 passive decay、interference、retrieval failure、active forgetting、inhibitory control、engram accessibility、competition。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Anderson & Green, 2001, "Suppressing unwanted memories by executive control" | original / human cognitive neuroscience | motivated suppression / inhibitory control。 |
| core | Hardt, Nader & Nadel, 2013, "Decay happens: the role of active forgetting in memory" | review | active forgetting 入门。 |
| core | Richards & Frankland, 2017, "The Persistence and Transience of Memory" | perspective / review | forgetting as adaptive feature。 |
| core | Davis & Zhong, 2017, "The Biology of Forgetting" | review | molecular / cellular forgetting mechanisms。 |
| core | Anderson & Hulbert, 2021, "Active Forgetting: Adaptation of Memory by Prefrontal Control" | review | intentional suppression、retrieval-induced forgetting。 |
| core | Ryan & Frankland, 2022, "Forgetting as a form of adaptive engram cell plasticity" | review | adaptive engram plasticity。 |
| frontier | Berry, Guhle & Davis, 2024, "Active forgetting and neuropsychiatric diseases" | review | molecular、cellular、network forgetting mechanisms。 |
| frontier | Fawcett et al., 2024, "Active intentional and unintentional forgetting in the laboratory and everyday life" | review | human everyday forgetting and lab paradigms。 |
| frontier | "Natural forgetting reversibly modulates engram expression", 2024 | original | forgetting as reversible accessibility change。 |
| frontier | "The cost of remembering: engram competition as a flexible mechanism of forgetting", 2025 | review / perspective | engram competition 作为遗忘框架。 |

URLs:

- Anderson & Green 2001: https://doi.org/10.1038/35066572
- Hardt et al. 2013: https://pubmed.ncbi.nlm.nih.gov/23369831/
- Richards & Frankland 2017: https://pubmed.ncbi.nlm.nih.gov/28641107/
- The Biology of Forgetting: https://pmc.ncbi.nlm.nih.gov/articles/PMC5657245/
- Anderson & Hulbert 2021: https://www.annualreviews.org/content/journals/10.1146/annurev-psych-072720-094140
- Ryan & Frankland 2022: https://doi.org/10.1038/s41583-021-00548-3
- Active forgetting and neuropsychiatric diseases 2024: https://www.nature.com/articles/s41380-024-02521-9
- Active intentional and unintentional forgetting 2024: https://doi.org/10.1038/s44159-024-00352-7
- Natural forgetting 2024: https://elifesciences.org/articles/92860
- Engram competition 2025: https://www.cell.com/trends/neurosciences/fulltext/S0166-2236%2825%2900153-5

## Stage 9. Emotional and Motivated Memory

目标：理解 emotion / motivation 如何调制 encoding、consolidation、retrieval；区分 emotion as content 和 emotion as modulation。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| core | McGaugh, 2004, "The amygdala modulates the consolidation of memories of emotionally arousing experiences" | review | amygdala modulation 的经典入口。 |
| core | Phelps, 2004, "Human emotion and memory: interactions of the amygdala and hippocampal complex" | review | human emotional memory。 |
| mechanism | Dolcos et al., 2004, "Interaction between the amygdala and the medial temporal lobe memory system predicts better memory for emotional events" | original / fMRI | emotional encoding 中 amygdala-MTL interaction。 |
| core | Shohamy & Adcock, 2010, "Dopamine and adaptive memory" | review | dopamine、reward、adaptive memory。 |
| core | Mather et al., 2016 / Clewett et al., 2018 locus coeruleus-norepinephrine work | review / original | norepinephrine、arousal、priority memory。 |
| core | Poh & Adcock, 2026, "Motivation as Neural Context for Adaptive Learning and Memory Formation" | review | dopaminergic VTA vs noradrenergic LC 的最新综合模型。 |
| mechanism | Murty, LaBar & Adcock, 2012, "Threat of punishment motivates memory encoding via amygdala..." | original / fMRI | punishment / threat motivation 与 amygdala-MTL。 |
| frontier | Costa et al., 2025, "Human hippocampal reactivation of amygdala encoding-related gamma patterns during aversive memory retrieval" | human intracranial recording | aversive retrieval 的 amygdala-hippocampus gamma pattern。 |
| frontier | Sonkusare et al., 2026, "Adaptive shifts in amygdala-hippocampal theta coupling govern aversive learning and extinction" | human intracranial recording | learning/extinction 中 theta coupling 方向变化。 |

URLs:

- McGaugh 2004: https://pubmed.ncbi.nlm.nih.gov/15217324/
- Phelps 2004: https://pubmed.ncbi.nlm.nih.gov/15082325/
- Dolcos et al. 2004: https://doi.org/10.1038/nn1190
- Shohamy & Adcock 2010: https://www.cell.com/trends/cognitive-sciences/fulltext/S1364-6613%2810%2900186-5
- Emotional enhancement and norepinephrine: https://pmc.ncbi.nlm.nih.gov/articles/PMC2877027/
- Motivation as Neural Context 2026: https://www.annualreviews.org/content/journals/10.1146/annurev-psych-032525-031744
- Murty et al. 2012: https://www.jneurosci.org/content/32/26/8969
- Costa et al. 2025: https://www.nature.com/articles/s41467-025-61928-2
- Sonkusare et al. 2026: https://www.nature.com/articles/s41467-026-73967-4

## Stage 10. Computational Neuroscience Models

目标：学习神经科学中的计算模型，但暂时不转入 Agent 架构。

| Priority | Source | Type | Use |
| --- | --- | --- | --- |
| classic | Marr, 1971, "Simple memory: a theory for archicortex" | computational theory | hippocampus as memory system 的早期模型。 |
| classic | Hopfield, 1982, "Neural networks and physical systems with emergent collective computational abilities" | computational model | attractor / content-addressable memory。 |
| classic | McClelland, McNaughton & O'Reilly, 1995 | computational theory | CLS。 |
| core | Norman & O'Reilly, 2003, "Modeling hippocampal and neocortical contributions to recognition memory" | computational model | hippocampal pattern separation / completion in recognition。 |
| core | Kumaran, Hassabis & McClelland, 2016, "What learning systems do intelligent agents need?" | theory / review | CLS 更新版，注意这里是 cognitive science / AI bridge，不是架构建议。 |
| core | Whittington et al. / cognitive map models | computational neuroscience | hippocampal-entorhinal relational representation。 |
| frontier | Spens & Burgess, 2024, "A generative model of memory construction and consolidation" | computational model | generative reconstruction、schema distortion、replay。 |
| frontier | Chandra et al., 2025, "Episodic and associative memory from spatial scaffolds in the hippocampus" | computational / original | spatial scaffold and high-capacity associative memory。 |
| frontier | George et al., 2025, "Constructing future behavior in the hippocampal formation through composition and replay" | computational / original | composition、replay、future behavior。 |

URLs:

- Marr 1971: https://pubmed.ncbi.nlm.nih.gov/4399412/
- Hopfield 1982: https://www.pnas.org/doi/10.1073/pnas.79.8.2554
- CLS 1995: https://pubmed.ncbi.nlm.nih.gov/7624455/
- Norman & O'Reilly 2003 PDF: https://www.princeton.edu/~compmem/psyrev_inpress.pdf
- Kumaran et al. 2016: https://doi.org/10.1016/j.tics.2016.05.004
- Spens & Burgess 2024: https://www.nature.com/articles/s41562-023-01799-z
- Spatial scaffolds 2025: https://www.nature.com/articles/s41586-024-08392-y
- Composition and replay 2025: https://www.nature.com/articles/s41593-025-01908-3

## Frontier Watchlist

这些不是第一轮必读，但需要持续追踪。

| Topic | Sources | Why watch |
| --- | --- | --- |
| Dynamic engram | Tome et al. 2024; Memory engram stability and flexibility 2024; Engram synapses 2026 | engram 不再是固定痕迹，而是动态 ensemble / accessibility。 |
| Human intracranial memory evidence | Episode-specific neurons 2023; Replay and Ripples in Humans 2025; Costa et al. 2025; Sonkusare et al. 2026 | 补足 fMRI 时间分辨率不足，但样本和任务限制更明显。 |
| Hippocampus in remote memory | Park & Kaang 2026; systems reconsolidation work | 远期记忆是否仍依赖 hippocampus 仍有争议。 |
| Active forgetting | Berry et al. 2024; Natural forgetting 2024; Engram competition 2025 | forgetting increasingly treated as adaptive and mechanistic, not just failure。 |
| Sleep microstructure and replay | Sleep microstructure 2025; Past/future sleep processing 2025; Large SWRs 2025 | sleep replay 可能不只是巩固旧记忆，也涉及干扰控制和未来学习准备。 |
| Emotional memory in humans | Costa et al. 2025; Sonkusare et al. 2026 | human iEEG 正在给 emotional memory 提供更强时间尺度证据。 |
| Generative / constructive memory | Spens & Burgess 2024; adaptive episodic memory 2026 | memory retrieval as reconstruction / construction，而不是 replay as exact copy。 |

## Quality Checks

每篇来源至少检查：

- 研究对象：人类、啮齿动物、果蝇、体外模型、计算模型。
- 方法：fMRI、EEG/MEG、iEEG、单神经元、电生理、钙成像、光遗传、药理、行为、建模。
- 测到了什么：活动相关、行为相关、因果操控、模型拟合、还是概念论证。
- 不能推出什么：相关性不能推出机制；模型拟合不能证明生物实现。
- 证据强度：consensus、strong evidence、preliminary、disputed、speculative。
- claim type：literature claim、computational model、assistant synthesis、open question。

## Deliberately Excluded for Now

暂时不纳入第一轮：

- 纯 AI Agent memory 论文：已有 `brain-memory-and-agent-memory-sources.md` 跟踪，当前先学神经科学。
- 纯教育心理学学习法论文：retrieval practice 只作为辅助概念，不进入主线。
- 临床治疗细节：PTSD、焦虑、成瘾、阿尔茨海默病只在机制需要时引用。
- 分子通路细节：PKMzeta、Rac1、AMPAR trafficking、microglia 等先放在 forgetting / engram 机制下，不单独开阶段。
- 哲学记忆理论：除非影响 episodic / semantic / self / identity 的边界问题，否则暂不扩展。
