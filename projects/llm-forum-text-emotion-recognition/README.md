# 基于大模型的论坛文本情感识别

---
date: 2026-07-23
status: opening-preparation
tags: [emotion-recognition, forum-text, llm, nlp, final-year-project]
sources:
  - ../../sources/llm-forum-text-emotion-recognition-sources.md
papers:
  - ../../papers/llm-forum-text-emotion-recognition/reading-route.md
---

## Project Identity

- English title: Research and Implementation of Emotion Recognition System of Forum Text Based on LLM
- Project area: Artificial Intelligence Technology
- Project type: Engineering Design
- Ownership: 中方
- Supervisor: 王玉林
- Supervisor email: `wyl@uestc.edu.cn`
- Current stage: 开题准备
- Supervisor's current instruction, as relayed by the user: 查阅情感识别相关论文，复现公开代码，自行准备论坛文本数据，并完成开题准备。

题目与导师信息来自已保存的毕设题目公示记录。导师指示来自用户转述的邮件回复；原始邮件应由用户另行保留，项目仓库只记录任务摘要。

## Project Question

在合规取得并可靠标注的论坛文本上，传统机器学习、预训练编码器与大语言模型（Large Language Model, LLM）方法在情绪识别的准确性、稳健性、成本和上下文利用能力方面有何差异？

## Working Objective

项目目标不是只做一个调用 LLM API 的界面，而是形成完整、可复核的研究闭环：

```text
问题定义 -> 数据与标注 -> 可复现基线 -> LLM 对照 -> 鲁棒性与失败分析 -> 可运行演示 -> 论文与证据归档
```

最终成果应同时包含：

- 一个边界明确的论坛文本情绪识别任务。
- 一套来源、授权、匿名化和数据划分均可说明的数据集。
- 至少一个简单基线和一个有竞争力的编码器基线。
- 与 LLM 方法的公平比较，而不是只展示单次模型输出。
- Macro-F1、各类别指标、混淆矩阵及失败案例分析。
- 可复现代码、环境、配置、预测结果和技术报告。
- 在研究结论支撑下形成的可运行演示。

## Experiment Route and Comparison Boundary

模型路线按数据集和依赖关系分为四段：

```text
TweetEval（已完成）
TF-IDF + Logistic Regression
-> TF-IDF + Linear SVM
-> 通用 RoBERTa
-> Twitter-domain RoBERTa
-> 验证训练、评估、test gate 和错误分析流程

GoEmotions（当前阶段）
简单多标签基线
-> BERT-base / RoBERTa 监督微调
-> 建立同一数据集上的冻结编码器基线

GoEmotions 本地 LLM 对照（当前阶段）
Qwen3-1.7B Instruct zero-shot / few-shot
+ Qwen3-1.7B Base / Instruct matched frozen probes
-> 区分实用分类表现与 post-training 对表征可解码性的影响

任务适配
Instruct LoRA
-> 与冻结的简单基线和 BERT 比较性能、稳定性、成本和延迟
-> 只有出现明确容量证据时才做 matched 1.7B / 4B scale control

后续
冻结错误分析（EXP-030 已完成） -> neutral ontology 推理消融（EXP-031 已完成）
-> target-aligned retraining 候选 -> test gate -> 上下文 -> 内部表征 -> SAE
```

LLM 是后续新增的第三类模型路线，不替代 TweetEval 已完成的传统分类器与
RoBERTa 比较。模型分数只能在相同数据集、任务定义、split 和评估代码下作正式
比较。TweetEval emotion 是四分类单标签任务，GoEmotions 是 28 标签多标签任务，
两者的分数不能直接横向比较。

如果最终完全取消 LLM 路线，本项目仍可退化为普通情绪分类研究，但题目、开题报告
和研究动机必须同步调整，不能继续声称完成“基于大模型”的比较。

## Scope

项目范围分阶段覆盖：

- 英文论坛或社交媒体文本情绪识别。
- 单条文本与回复上下文两种输入设定。
- GoEmotions 保持官方 28 标签多标签任务；自建论坛数据先做粗粒度单标签标注
  试验，再根据一致性决定是否扩展。
- 在 GoEmotions 上依次建立简单多标签基线、BERT/RoBERTa 监督基线和
  zero-shot/few-shot LLM 对照。
- 先以本地 1.7B Base/Instruct 配对模型建立 prompting 与后训练控制，再在资源
  允许时评估 LoRA、检索示例或上下文建模。
- 反讽、否定、网络用语、类别不平衡和上下文依赖等失败模式。

## Non-goals

当前不把以下内容视为项目成果：

- 只调用一次 LLM API 并展示几个样例。
- 只报告 accuracy。
- 没有固定数据划分、基线或可复现配置的模型比较。
- 在未确认平台条款、授权和匿名化方案前大规模采集论坛数据。
- 把计划中的模型、功能、指标或实验写成已经完成。
- 为追求复杂度而直接从 7B 级模型完整复现开始。

## Current State

### 已确认

- 毕设题目、项目类型、导师及导师当前准备要求已经记录。
- 已建立 6 篇核心论文的本地阅读包与复现路线。
- 已提出初始实验矩阵、最低数据字段和开题研究问题。
- 已使用固定 TweetEval emotion 训练集拟合首个 TF-IDF + Logistic Regression 基线，并完成固定验证集评估；测试集尚未读取。
- 已在其余配置不变的条件下拟合并评估 `class_weight="balanced"` 受控变体；按预先登记的 validation Macro-F1，balanced 版本暂选为后续 TF-IDF 基线。
- 已完成 paper-aligned word + character n-gram TF-IDF + Linear SVM 基线；EXP-005 的 validation Macro-F1 和 Accuracy 均高于 balanced Logistic Regression，成为当前更强的传统基线；测试集仍未读取。
- 已在不读取 validation/test 的条件下完成 EXP-006 训练集 5 折调参，并用冻结配置执行一次 EXP-007 validation 确认；Macro-F1 从 0.611866 提高到 0.622678，Accuracy 从 0.671123 提高到 0.676471，成为当前最强的本地传统基线；测试集仍未读取。
- 已建立独立的 `emotion-roberta` 环境并固定 `FacebookAI/roberta-base` 上游 revision；EXP-008 已通过离线模型哈希校验、MPS 单步训练和合成推理检查，未读取任何项目数据。
- 已完成 EXP-011 RoBERTa-base 三随机种子正式微调；validation Macro-F1 为 `0.732804 +/- 0.005007`，Accuracy 为 `0.792335 +/- 0.004084`，相对 EXP-007 的平均 Macro-F1 提高 `0.110126`。逐条预测、类级指标、训练曲线、checkpoint 哈希和独立复算均已保存；测试集仍未读取。
- 已通过 EXP-012 与 EXP-013 两轮仅使用训练集的 Minor 筛选确定正式调优配置：保留原始文本，加入 `label_smoothing_factor=0.05`。Tweet 归一化规则未改变当前数据中的任何样本，因此不能从分差判断其效果；论文同款超参数组合未在当前受控设置下胜出。
- 已完成 EXP-014 通用 RoBERTa-base 优化配置的三随机种子验证；validation Macro-F1 为 `0.740219 +/- 0.005381`，相对 EXP-011 提高 `0.007415`。两个 seed 明确提高，一个 seed 与 EXP-011 属于 practical tie；独立复算已通过，测试集仍未读取。
- 已完成 EXP-015 Twitter 域预训练 RoBERTa-base 的配对比较；validation Macro-F1 为 `0.761755 +/- 0.010579`，Accuracy 为 `0.829768 +/- 0.012350`，相对 EXP-014 的 Macro-F1 提高 `0.021536`，三个配对 seed 均提高。收益主要来自 joy、sadness 和 anger；optimism F1 反而从 `0.556824` 降至 `0.521836`，不能把整体收益解释为所有类别均受益。独立复算已通过，测试集仍未读取。
- 已完成并由用户确认冻结一次性测试门 EXP-016。test Macro-F1 分别为 EXP-007 `0.646998`、EXP-011 `0.795761 +/- 0.003298`、EXP-014 `0.792645 +/- 0.003658`、EXP-015 `0.809973 +/- 0.007038`。EXP-014 相对 EXP-011 的配对均值为 `-0.003116`，说明 label smoothing 的小幅 validation 收益没有泛化；EXP-015 相对 EXP-014 为 `+0.017328`，且 3/3 seed 提高，支持 Twitter 域预训练收益。14,210 条模型-样本预测的指标、类别结果、混淆矩阵和哈希已独立复算通过，并归档于提交 `f061ec9`；此后不得再用该 test 调参。
- 已完成 EXP-017 冻结错误分析。EXP-015 在 1,421 条 test 中有 155 条 3/3 seed 稳定错误和 147 条 seed 结果不稳定样本；optimism 的稳定错误率为 `26.02%`，明显高于 anger `6.63%`、joy `8.94%` 和 sadness `14.14%`。87 条样本被传统基线和全部神经模型 seed 共同判错。按读原文前冻结的五组规则复核 42 条匿名案例，并将原文隔离在 gitignored 本地目录；独立验证确认 14,210 条预测、抽样身份、定性编码、聚合表和公开隐私边界一致。
- 已创建与 TweetEval 并行的 GoEmotions 数据与实验分支，并冻结 `DATA-GOE-V1`：官方 agreement-filtered split、完整 27 类情绪加 `neutral`、多标签单评论任务、固定标签顺序和独立 test gate。train、dev 和 `emotions.txt` 已从固定 revision 获取并校验；官方 train/dev 的 41 个 exact-text overlap 已审阅记录，comment ID overlap 为 0，test 仍未获取。
- 已完成并独立验证 EXP-018 GoEmotions 简单多标签基线：word TF-IDF + 28 个独立 Logistic Regression 在固定 dev 上得到 Macro-F1 `0.203644`、Micro-F1 `0.377639` 和 subset accuracy `0.246959`。固定阈值 0.5 下有 3,261/5,426 条空预测，disappointment、grief、nervousness、pride 和 relief 的 recall 为 0；test 未获取或读取。
- 已通过 EXP-019 完成 BERT-base-cased 离线模型、MPS 训练与 28 标签推理烟雾测试，并完成 EXP-020 三随机种子正式微调。EXP-020 固定 dev 的 Macro-F1 为 `0.489435 +/- 0.011063`，Micro-F1 为 `0.586671 +/- 0.002928`，相对 EXP-018 的 Macro-F1 提高 `0.285791`。三个 seed 的 5,426 x 28 概率、完整指标、模型和输入哈希均已独立复算，最大数值差异为 0；test 未获取或读取。
- 已完成并独立验证 EXP-021：从 Qwen 官方仓库下载固定 revision 的 Qwen3-1.7B post-trained/Base 配对模型，在同一 MLX-LM 环境转换为未量化 BF16，并分别通过合成输入生成检查。四份模型副本共 `14,437,414,837` bytes，逐文件 SHA-256 与来源 manifest 已保存；本阶段未读取任何 GoEmotions split，也不构成情绪识别性能证据。
- 已完成并独立验证 EXP-022 本地成本与 strict-parser 试跑：32 条匿名 train 文本共 64 次测量，未读取 gold label、dev 或 test。资源门全部通过，zero-shot/few-shot 完整 dev 线性估计约 `1.25`/`1.48` 小时，峰值 MLX memory `3.65` GB；但 few-shot 严格 JSON 有效率为 `87.5%`，低于预注册的 95%，因此总门失败，尚不能进入 full-dev。
- 已完成并独立验证 EXP-023 数字 label-ID 修复负结果：zero-shot/few-shot 严格有效率降为 `50.0%`/`65.625%`，说明数字接口没有修复格式门。
- 已完成并独立验证 EXP-024 constrained label-name JSON 修复：复用 EXP-022 prompt 与同一批 32 条匿名 train 文本，两条件均为 `32/32 = 100%` 严格有效，64 次均正常结束；完整 dev 线性估计约 `1.08`/`1.46` 小时，峰值 MLX memory `3.65` GB，全部门通过。该格式率由解码约束保证，不是分类性能证据。
- 已完成并独立验证 EXP-025 constrained full-dev zero/few-shot Major。Macro-F1 为
  `0.222998`/`0.241164`，parser 有效率为 `99.9631%`/`100%`；few-shot 相对
  zero-shot 的配对差值为 `+0.018166`，按冻结规则成为当前 constrained Qwen dev
  条件，但仍比 EXP-020 BERT 三 seed 均值低 `0.248271`。
- 已完成并独立验证 EXP-026 matched unconstrained decoder ablation。Macro-F1 为
  `0.228700`/`0.236465`，parser 有效率为 `95.9823%`/`90.7298%`。联合 2x2 显示：
  few-shot 中双方有效的 4,923 条标签集合完全一致，约束主要救回 503 个无效输出；
  zero-shot 中双方有效的 5,206 条只有 `75.8164%` 标签集合完全一致，finite-state
  mask 不能笼统视为 label-neutral。两个 verifier 的最大数值差异均为 0，test 未获取。
- 已完成并独立验证 EXP-027 合成 hidden-state smoke：Base 与 post-trained 使用相同
  token ID，均得到有限的 `6 x 2048` final-layer mean-pooled 表征，未读取 train/dev/test。
  EXP-028 matched frozen probe 的零数据 preflight `28/28` 通过，四份特征与 8 个探针
  均完成，但 fitting/evaluation 用时 `344.288` 分钟，超过冻结的 240 分钟资源上限，
  因而正式状态为 `Failed`。失败产物审计的概率、指标与 bootstrap 复算差异均为 0；
  Base/post-trained 的诊断 Macro-F1 为 `0.310534`/`0.306373`，但不能写入 Verified 证据。
- 已完成并独立验证 EXP-029 Qwen3-1.7B 监督 LoRA 三随机种子实验。冻结规则选择
  zero-shot 条件，其 dev Macro-F1 为 `0.451374 +/- 0.019212`，较 EXP-025 选定的
  frozen few-shot 提高 `0.210209`，但仍比 EXP-020 BERT 均值低 `0.038061`。
  few-shot-synthetic-3 为 `0.425265 +/- 0.004858`，没有在 LoRA 后继续提供收益；
  三个 seed 均通过独立复算和资源门，test 未获取或读取。
- 已完成并独立验证 EXP-030 冻结跨模型 dev 错误分析。LoRA 的 subset accuracy 为
  `0.508293`，高于 BERT 的 `0.440963`，但其 Macro-F1 低 `0.038061`；LoRA 平均
  只输出 `1.034` 个标签，在 878 条多标签样本上的 subset accuracy 约 `0.043`，
  明显低于 BERT 的约 `0.179`。当前 Qwen ontology 使 174 条 `neutral+emotion`
  gold 在结构上无法 exact-match。7 份预测、5,426 条 gold、48 条冻结匿名案例和
  隐私边界均已复算通过，公开原文泄漏为 0；test 仍未获取。
- 已完成并独立验证 EXP-031 三随机种子推理消融。仅放开 decoder 时，三个 seed 的
  预测与冻结 closed condition 完全一致；同时对齐 prompt 与 decoder 后，Macro-F1
  从 `0.451374 +/- 0.019213` 变为 `0.453056 +/- 0.014757`，平均差值仅
  `+0.001682`，低于 `0.005` practical threshold。Samples-F1 与 exact match 分别
  下降 `0.003240` 和 `0.005529`，174 条 neutral co-occurrence 切片 Samples-F1
  下降 `0.009132`，所有条件均产生 0 条 `neutral+emotion` 预测。正式分类为
  `no_material_inference_improvement`；这只说明推理时修正不足以改变当前冻结 adapter，
  不能替代 target-aligned retraining，也不支持内部机制结论。test 仍未获取。

### 尚未完成

- 目标论坛、文本语言、授权范围和数据再分发边界尚未确认。
- 标签体系、标注者、标注协议和一致性指标尚未确定。
- 已有传统基线、编码器、一次性正式 test、冻结错误分析和 GoEmotions 本地 LLM
  prompt/decoder 2x2、LoRA 与跨模型错误结构证据；Base/post-trained probe 的首次
  正式运行触发资源门，尚无 Verified 表征结论。尚未完成自建数据集、广义鲁棒性
  实验或可运行系统。
- GoEmotions 的 BERT-base-cased dev 基线已经冻结；正式 test 尚未获取，
  RoBERTa alternative 尚未执行。EXP-018 与 EXP-020 不再事后调参，后续阈值、
  类别权重或模型变体必须使用新实验编号。
- Qwen3-1.7B Base/post-trained 本地环境、资源试跑、parser 修复门和 EXP-025/026
  full-dev 2x2 已完成并验证；EXP-027 probe smoke 已通过，EXP-028 正式 matched probe
  因 wall-time 门失败并保留。EXP-029 三 seed LoRA、EXP-030 错误分析与 EXP-031
  推理消融已完成并验证；target-aligned retraining 与新的正式 probe 尚未执行。

## Evidence Standard

[`evidence-log.md`](evidence-log.md) 是本项目面向 CV、SOP 和推荐信的事实来源。只有状态为 `Verified`，且能由代码、日志、数据说明、报告或导师材料复核的条目，才能写成对外成果。

即使新方法没有超过基线，只要问题定义清楚、实验严谨、失败原因分析充分，仍可形成可信的申请项目。

## Core Files

- [`opening-report.md`](opening-report.md): 开题报告研究内容草案、技术路线、创新点与范围控制。
- [`research-roadmap.md`](research-roadmap.md): 从开题到论文交付的阶段路线和通过条件。
- [`hypotheses.md`](hypotheses.md): 当前待验证假设、反证条件和对应实验。
- [`evidence-log.md`](evidence-log.md): 项目事实、实验产物和申请证据台账。
- [`experiments/tweeteval-emotion/test-gate/README.md`](experiments/tweeteval-emotion/test-gate/README.md): EXP-016 一次性正式 test 结果、受控比较、外部参照与复算入口。
- [`experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/REPORT.md`](experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/REPORT.md): EXP-017 全量稳定性、共享错误、受控转移和匿名定性分析。
- [`experiments/goemotions/protocols/data-protocol-v1.md`](experiments/goemotions/protocols/data-protocol-v1.md): GoEmotions 官方多标签数据来源、标签顺序、split 纪律和 test gate。
- [`data/goemotions/manifest.json`](data/goemotions/manifest.json): GoEmotions train/dev 固定快照的来源 revision、SHA-256、规模和数据质量检查。
- [`experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/REPORT.md`](experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/REPORT.md): EXP-018 简单多标签基线结果、类别诊断和独立验证说明。
- [`experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/REPORT.md`](experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/REPORT.md): EXP-020 BERT-base-cased 三随机种子 dev 复现、逐类诊断、论文边界和独立验证说明。
- [`experiments/goemotions/qwen3-1.7b/README.md`](experiments/goemotions/qwen3-1.7b/README.md): Qwen3-1.7B 配对模型来源、EXP-021 至 EXP-031 的行为实验、probe 门和后续 LLM 实验顺序。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md): EXP-028 资源门失败、诊断结果、独立产物审计和证据边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/REPORT.md): EXP-029 三随机种子 LoRA dev 结果、冻结比较、资源记录和证据边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/REPORT.md): EXP-031 三随机种子 neutral ontology 推理消融、冻结判定与 target-aligned retraining 边界。
- [`experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/REPORT.md`](experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/REPORT.md): EXP-030 跨 BERT、冻结 Qwen 与 LoRA 的 dev 错误结构、匿名定性复核和官方结果边界。
- [`../../questions/llm-forum-text-emotion-recognition/open-questions.md`](../../questions/llm-forum-text-emotion-recognition/open-questions.md): 会改变项目主线的开放问题。
- [`../../sources/llm-forum-text-emotion-recognition-sources.md`](../../sources/llm-forum-text-emotion-recognition-sources.md): 论文、代码、数据与合规来源地图。
- [`../../papers/llm-forum-text-emotion-recognition/reading-route.md`](../../papers/llm-forum-text-emotion-recognition/reading-route.md): 论文阅读器与复现建议。

## Next Action

1. 保持 EXP-020、EXP-025、EXP-029、EXP-030 和 EXP-031 冻结。EXP-031 已排除
   “仅在推理时放开 neutral ontology 就能实质改善”的解释；下一步先讨论并预登记
   一个新的 target-aligned retraining Major，在训练目标、prompt 和 decoder 三处都
   保持官方 `neutral+emotion` 标签，而不在 EXP-029/031 上事后调参。
2. 保留 EXP-028 的 `Failed` 状态；表征支线若继续，必须使用新的 matched-probe
   实验编号、现实资源门和透明恢复政策，不得用其诊断值反向修改标签或读出规则。
3. 并行向导师确认 GoEmotions 能否作为主要论坛数据，以及是否必须另行采集、
   标注或加入线程上下文。
4. GoEmotions test 继续关闭；只有候选模型、错误分析和论坛数据范围冻结后，才登记
   一次性 test gate。在新的 validation 或 forum holdout 上开发上下文和鲁棒性方案。
