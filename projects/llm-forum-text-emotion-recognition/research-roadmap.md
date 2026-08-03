# Research Roadmap: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
status: draft
tags: [emotion-recognition, forum-text, llm, roadmap]
---

## Success Criteria

项目成功不以“用了多少模型”为标准，而以是否形成可复核闭环为标准：

```text
明确研究问题 -> 合规数据 -> 公平基线 -> 对照实验 -> 完整指标 -> 失败分析 -> 可复现产物
```

最低通过条件：

- 数据来源、规模、标签、匿名化和划分方法可说明。
- 简单基线、编码器基线与 LLM 方法只能在相同数据集、任务定义、split 和评估
  代码下比较。
- 报告 Macro-F1、各类别 precision/recall/F1 和混淆矩阵。
- 至少完成一组对照、消融或鲁棒性实验。
- 所有外部成果表述均能追溯到 [`evidence-log.md`](evidence-log.md) 中的 `Verified` 证据。

## Dependency Order

```text
TweetEval process validation（completed）
传统分类器 -> 通用 RoBERTa -> Twitter-domain RoBERTa
    |
    v
GoEmotions supervised baselines（dev conditions completed）
简单多标签基线 -> BERT-base / RoBERTa
    |
    v
GoEmotions local LLM behavioral comparison（dev 2x2 verified）
Qwen3-1.7B Instruct zero/few-shot + decoder ablation
    +
matched Base/Instruct frozen probes
    |
    v
Instruct LoRA -> optional matched 1.7B/4B scale control
    |
    v
Error analysis -> test gate -> context -> SAE
```

TweetEval emotion 的四分类单标签分数只回答 TweetEval 内部的模型比较问题。
GoEmotions 的 28 标签多标签结果只在 GoEmotions 内比较。任何实验都不得用
TweetEval 的 RoBERTa 分数作为 GoEmotions LLM 的性能对照。

## Research Question Registry

| RQ ID | Question | Expected contribution | Major experiments | Thesis destination | Status |
| --- | --- | --- | --- | --- | --- |
| RQ-B1 | 在固定 TweetEval emotion 数据上，word + character n-gram Linear SVM 是否比 balanced word TF-IDF + Logistic Regression 更强，且训练集内调参能否进一步改善泛化？ | 建立进入编码器实验前更可信的传统非神经网络下界；量化增加字符特征、更换分类器和受控调参的收益与边界 | EXP-005、EXP-007（由 Minor EXP-006 选择配置）、EXP-016 test gate | 结果章节的传统基线与调优比较表，编号待定 | 阶段性解决：EXP-007 test Macro-F1=0.646998、Accuracy=0.700915；与上游 SVM 的三位小数结果一致，逐条预测已独立复算 |
| RQ-B2 | 在相同 TweetEval emotion 数据上，标准微调的 RoBERTa-base 是否稳定优于 EXP-007，且 label smoothing 的 validation 收益能否泛化到冻结 test？ | 建立可复现的强编码器基线，量化三随机种子波动，并区分开发集改善与真正的测试集泛化 | EXP-009（首个优化步前实现失败）；EXP-010（数据读取前环境失败）；EXP-011（正式控制）；EXP-014（由 Minor EXP-012/013 选择配置）；EXP-016 test gate；EXP-017 error analysis | 结果章节的编码器基线、调优与传统方法比较表；讨论章节的稳定错误与 validation/test 不一致，编号待定 | 阶段性解决：EXP-011 test Macro-F1=0.795761 +/- 0.003298；EXP-014 为 0.792645 +/- 0.003658，配对 delta=-0.003116；EXP-017 中正确 seed 数增加/减少的样本为 80/82，且无 0/3 与 3/3 直接翻转，label smoothing 未建立 test 改善 |
| RQ-B3 | 在相同数据、预处理和冻结微调协议下，Twitter 域预训练的 RoBERTa-base 是否比通用 RoBERTa-base 获得更高的 Macro-F1，并泛化到冻结 test？ | 将“域预训练收益”与超参数调优分离，检验论坛/社交媒体语言分布匹配是否改善情绪分类，尤其是 optimism 等困难类别 | EXP-015（与 EXP-014 配对比较）、EXP-016 test gate、EXP-017 error analysis | 结果章节的预训练域消融与逐类别比较表；讨论章节的共享错误、域恢复/回退与 optimism 弱项，编号待定 | 阶段性解决：EXP-015 test Macro-F1=0.809973 +/- 0.007038，较 EXP-014 +0.017328，3/3 seed 提高；EXP-017 观察到 21 个稳定恢复与 11 个稳定回退，但 optimism 无完整 0/3-to-3/3 翻转，仍是稳定错误率最高的类别 |
| RQ-G1 | 在固定 GoEmotions 28 标签多标签任务上，BERT-base/RoBERTa 监督微调相对简单多标签基线增加了多少有效性能？ | 建立后续 LLM 比较所需的同数据集监督下界与强编码器基线，并记录类别不平衡、多标签阈值和细粒度标签的困难 | EXP-018 simple baseline；EXP-019 BERT smoke；EXP-020 BERT-base-cased Major；EXP-030 cross-model error analysis | 结果章节的 GoEmotions 监督基线与多标签错误结构表，编号待定 | 阶段性解决：EXP-020 dev Macro-F1=`0.489435 +/- 0.011063`，较 EXP-018 提高 `0.285791`；EXP-030 显示 BERT 在 878 条多标签样本上的 subset accuracy 约 `0.179`，高于 LoRA 的约 `0.043`。GoEmotions test 未获取，RoBERTa alternative 未执行 |
| RQ-G2 | 在相同 GoEmotions 数据、标签和评估协议上，本地 post-trained LLM 相对冻结 BERT 增加了什么；Base、post-trained 与 task-LoRA 三个适配阶段又如何改变情绪标签的行为表现和线性可解码性？ | 一条实用性能证据链比较 zero/few-shot、LoRA、性能、格式、成本与延迟；一条配对控制证据链先用 constrained/unconstrained 2x2 分离 decoder 影响，再使用同规模 Base/Instruct 的相同 frozen probe 隔离后训练影响，不把提示遵循误写为情绪机制 | EXP-021 Minor 环境与来源 smoke；EXP-022/023 parser failures；EXP-024 constrained-decoding gate；EXP-025 full-dev constrained zero/few-shot Major；EXP-026 matched unconstrained decoder Major；EXP-027 matched hidden-state smoke；EXP-028 matched frozen probe（资源门失败）；EXP-029 Instruct LoRA 三 seed Major；EXP-030 cross-model error analysis；EXP-031 neutral ontology inference ablation | 结果章节的同数据集 LLM 2x2、LoRA、编码器与错误结构比较；Table-G2-4 的 ontology 推理消融；讨论章节的表征和 ontology 边界 | 行为线阶段性解决：EXP-029 选定 zero-shot dev Macro-F1=`0.451374 +/- 0.019212`，较 EXP-025 `+0.210209`、较 EXP-020 `-0.038061`；EXP-030 发现 LoRA 平均预测标签数仅 `1.034`，且 174 条 `neutral+emotion` gold 对 closed ontology 结构性不可达；EXP-031 中 decoder-only 预测完全不变，aligned inference 的 Macro-F1 仅 `+0.001682`、neutral 共现切片 Samples-F1 `-0.009132`，未产生 neutral 共现预测。EXP-025/026/029/030/031 均 Verified，test 未获取；target-aligned retraining 待新编号。表征线仍开放：EXP-028 为 Failed，正式 probe 待新编号 |

## Phase 0: Scope and Opening

Status: in progress

目标：

- 与导师确认任务语言、论坛领域、标签粒度、数据获取方式和系统交付边界。
- 把“论坛文本情感识别”区分为单条文本分类与会话情感识别（Emotion Recognition in Conversation, ERC）。
- 将研究问题压缩为一条主线和不超过两条扩展问题。

通过条件：

- 项目 README 中不再存在会改变主线的关键未知项。
- 开题报告中的任务定义、数据计划、基线和评估指标彼此一致。

## Phase 1: Literature and Baseline Reproduction

Status: in progress; GoEmotions `DATA-GOE-V1`、EXP-018 与 EXP-020 dev baselines verified, test pending

目标：

- 先用 TweetEval emotion 的 Logistic Regression、Linear SVM、通用
  RoBERTa 和 Twitter-domain RoBERTa 验证训练、评估和 test gate 链路。
- 再在 GoEmotions 上先建立简单多标签基线，再复现或现代化实现
  BERT-base/RoBERTa 编码器基线。
- 记录原论文环境与现代实现之间的差异。

当前进展：

- TweetEval emotion 的传统方法、编码器、冻结 test 和错误分析已完成。
- GoEmotions 已建立并行实验目录并冻结
  [`DATA-GOE-V1`](experiments/goemotions/protocols/data-protocol-v1.md)：
  使用官方 agreement-filtered split、完整 28 标签和多标签任务。
- GoEmotions train、dev 和 `emotions.txt` 已从固定 revision 获取并校验；
  数据质量检查已记录于 `data/goemotions/manifest.json`。test 未获取，
  test gate 仍关闭。
- EXP-018 已在固定 train/dev 上完成并独立验证：word TF-IDF + 28 个
  One-vs-Rest Logistic Regression 的 dev Macro-F1 为 `0.203644`，Micro-F1
  为 `0.377639`。
- EXP-019 已完成离线模型哈希、MPS 三步训练与 28 标签合成推理烟雾测试；
  不构成任务性能证据。
- EXP-020 已按冻结的 BERT-base-cased 条件完成三随机种子训练与独立验证：
  dev Macro-F1 为 `0.489435 +/- 0.011063`，Micro-F1 为
  `0.586671 +/- 0.002928`。三个 seed 的 5,426 x 28 概率矩阵、指标、模型与
  输入哈希已复核，最大数值差异为 0；GoEmotions test 仍未获取。
- GoEmotions 论文报告的 full-taxonomy BERT Macro-F1 `0.46` 来自 test。
  EXP-020 是现代 PyTorch/Transformers/MPS 的 dev 复现，不能作同 split 的
  直接差值或声称逐位复现原 TensorFlow Estimator。

必须保留：

- 代码仓库版本或 commit。
- Python、PyTorch、Transformers、CUDA 与硬件信息。
- 数据版本、划分、随机种子、配置、训练日志和预测文件。
- 原论文结果、当前复现结果及差异说明。

通过条件：

- 从干净环境可重复运行。
- 评估脚本使用固定测试集，并能生成按类别指标。
- 未达到论文数值时仍保留结果和原因分析。

## Phase 2: Forum Data Protocol

Status: blocked by scope confirmation

目标：

- 确定平台条款、授权边界、隐私处理和可再分发范围。
- 冻结最小字段、标签说明、`unclear/other` 规则和标注流程。
- 先做小规模双人标注试验，再决定单标签或多标签主线。

最低字段：

```text
post_id, thread_id, parent_id, author_hash, created_at,
title, body, reply_depth, forum_section, source_url, labels
```

通过条件：

- 原始身份信息不进入公开训练数据。
- 按 `thread_id` 划分 train/dev/test，避免同一线程跨集合泄漏。
- 记录样本量、类别分布、重复率、标注者与一致性指标。
- 数据说明中明确允许和不允许的使用方式。

## Phase 3: Reproducible Supervised Baselines

Status: TweetEval gate completed; GoEmotions simple and BERT dev baselines verified, test pending

目标：

- 将 EXP-018 固定为 GoEmotions 简单多标签 sanity baseline。
- 在相同 GoEmotions 数据和标签空间上建立 BERT-base 或 RoBERTa 编码器基线。
- 编码器冻结后，才允许登记 GoEmotions LLM 对照。
- 自建论坛数据确定后，再按其标注协议建立独立基线，不沿用跨任务分数。

主要指标：

- Macro-F1。
- 每类 precision、recall 和 F1。
- Weighted-F1 或 Micro-F1，仅作为补充。
- 混淆矩阵、类别支持数和置信区间或多随机种子波动。

通过条件：

- 所有方法使用相同数据版本和测试集。
- 完成重复样本、同线程泄漏和预处理差异检查。
- 至少保存一个可直接复核的预测文件。

## Phase 4: Local LLM Comparison and Post-training Control

Status: EXP-025/026 prompt x decoder 2x2, EXP-029 three-seed LoRA, EXP-030 error analysis and EXP-031 inference ablation completed and independently verified; target-aligned retraining and test pending

目标：

- 只在与冻结 GoEmotions 监督基线相同的数据、标签和评估协议上比较。
- 以本地 Qwen3-1.7B 为第一研究规模，不默认从 4B 开始。
- 实用性能线先比较 post-trained Instruct 的 zero-shot 与 few-shot，再在资源门
  通过后进行 Instruct LoRA。
- 后训练控制线使用同规模 Base 与 Instruct、相同精度、输入、层/池化和线性
  probe；不得用 Base 的聊天提示失败证明其没有情绪表征。
- Base/Instruct frozen probe 只支持标签线性可解码性比较，不直接支持机制结论。
- 只有 1.7B 出现预先定义的容量证据时才加入 4B；规模实验必须匹配量化和提示
  条件，不能把 BF16 1.7B 与 4-bit 4B 的差异归因于参数规模。

当前进展：

- EXP-021 已下载固定 revision 的 `Qwen/Qwen3-1.7B` 与
  `Qwen/Qwen3-1.7B-Base`，在同一 MLX-LM 环境转换为未量化 BF16，并分别通过
  合成输入生成检查。
- 两份 upstream、两份 MLX BF16 转换及逐文件 SHA-256 已写入 manifest；本地
  总占用为 `14,437,414,837` bytes。
- 独立复核确认模型 revision、文件哈希、依赖版本与 Git ignore 边界；本阶段读取
  项目数据 0 行，未访问 train/dev/test。
- EXP-022 使用 32 条匿名 train 文本完成 64 次资源测量；资源、时间和截断门通过，
  zero-shot/few-shot 完整 dev 线性估计约为 `1.25`/`1.48` 小时，峰值 MLX memory
  为 `3.65` GB。
- EXP-022 总门因 few-shot strict-parser 有效率 `87.5%` 未达到 95% 而失败；
  zero-shot 为 `96.875%`。没有读取 gold label、dev/test 或计算分类性能。
- EXP-023 的数字 label-ID 修复使 zero-shot/few-shot 有效率降至
  `50.0%`/`65.625%`，作为负结果保留。
- EXP-024 回到 EXP-022 标签名 prompt，并增加有限状态 token mask；两条件均为
  `32/32 = 100%` 严格有效，完整 dev 线性估计约 `1.08`/`1.46` 小时，峰值
  `3.65` GB，全部门通过并独立复核。该格式率是约束解码属性，不是分类性能证据。
- EXP-025 constrained full-dev 已完成并验证：zero-shot/few-shot Macro-F1 为
  `0.222998`/`0.241164`，parser 有效率为 `99.9631%`/`100%`；配对 bootstrap 支持按
  冻结规则选择 few-shot，但它仍显著低于 EXP-020 的全部三个 BERT seed。
- EXP-026 matched unconstrained ablation 已完成并验证：zero-shot/few-shot Macro-F1 为
  `0.228700`/`0.236465`，parser 有效率为 `95.9823%`/`90.7298%`。
- 联合 2x2 表明 few-shot 约束主要恢复 503 个无效输出，双方有效的 4,923 条标签集合
  全部一致；zero-shot 双方有效的 5,206 条中有 1,259 条标签集合不同。约束对
  Macro-F1 的影响较小且方向不一致，但对输出行为和格式有效率不可忽略。
- 两次独立 verifier 均返回 `Passed`、最大数值差异 0，公开产物不含原文或 comment
  ID，GoEmotions test 仍未获取。
- EXP-027 已用六条合成文本验证 matched hidden-state 路径：token ID 完全一致，
  `6 x 2048` pooled vectors 数值有限，未读取项目 split。
- EXP-028 已按冻结条件完成四份特征与 8 个探针，但 fitting/evaluation 用时
  `344.288` 分钟，超过 240 分钟资源门，正式状态为 `Failed`。失败产物审计重算
  概率、指标和 bootstrap 均一致；Base/post-trained 诊断 Macro-F1 为
  `0.310534`/`0.306373`，配对差值 `-0.004161`、95% CI
  `[-0.013156, 0.004711]`，但这些值不是 Verified 证据。该表征支线必须使用新的
  实验编号恢复，不能用当前失败运行推断机制。
- EXP-029 已在不使用 EXP-028 诊断值选择标签、prompt 或 LoRA 配置的前提下，完成
  三个 seed 的监督 LoRA 和 zero/few-shot 全量 dev 评估。冻结规则选择 zero-shot，
  Macro-F1 为 `0.451374 +/- 0.019212`，较 EXP-025 选定条件提高 `0.210209`，但仍比
  EXP-020 BERT 均值低 `0.038061`；few-shot 为 `0.425265 +/- 0.004858`。
- EXP-029 三个 seed 均通过独立 verifier、资源门和隐私检查；训练峰值内存不超过
  `7.208` GB，API 成本为 USD 0，GoEmotions test 仍未获取。该结果支持 LoRA 增加
  任务能力，不支持内部情绪机制或人类认知结论。
- EXP-030 在读原文前冻结跨模型抽样规则，并复算 EXP-020、EXP-025 与 EXP-029 的
  7 份 dev 预测。LoRA subset accuracy 为 `0.508293`、高于 BERT 的 `0.440963`，
  但 Macro-F1 低 `0.038061`；差异主要表现为 LoRA 平均预测 `1.034` 个标签，在
  多标签样本上的 exact-match 明显较弱。当前 Qwen ontology 还使 174 条
  `neutral+emotion` gold 结构性不可达。48 条冻结匿名案例和 5,426 条 gold 已由
  verifier 复算，公开原文泄漏为 0，test 未获取。
- EXP-031 复用 EXP-029 三个冻结 adapter，对 closed decoder、仅开放 decoder 和
  prompt/decoder 同时对齐三种推理策略做全量 dev 配对消融。仅开放 decoder 时
  16,278 条 seed-row 预测完全不变；aligned inference 的 Macro-F1 平均只提高
  `0.001682`，Samples-F1、exact match 和 neutral 共现切片 Samples-F1 分别变化
  `-0.003240`、`-0.005529` 和 `-0.009132`，且没有生成任何 neutral 共现预测。
  三 seed 与聚合 verifier 均通过，正式结论为 `no_material_inference_improvement`。
  该结果只排除 inference-only correction 足够的解释；target-aligned retraining
  必须作为新 Major 单独检验，GoEmotions test 继续关闭。

除分类指标外必须记录：

- 模型提供方、精确版本与访问日期。
- 完整提示模板、示例选择规则和解码参数。
- 格式有效率、失败重试规则、成本和延迟。
- 相对简单基线与编码器基线的真实收益。
- Base、Instruct 与 LoRA 的适配阶段，以及 probe 和生成式分类读出的区别。
- 精度与量化条件；行为实验和内部表征实验若使用不同精度，必须分别命名。

通过条件：

- LLM 输出经过确定性的标签解析和异常处理。
- 不使用测试标签选择提示、示例或阈值。
- 能回答“更复杂的方法增加了什么，以及代价是什么”。
- Base/Instruct 的后训练比较使用相同 supervised readout，并包含 label-shuffle
  或等价泄漏控制。
- 不引用 TweetEval RoBERTa 分数作为 GoEmotions LLM 的性能对照。

## Phase 5: Context, Robustness, and Failure Analysis

Status: partial; TweetEval failure analysis completed, context and robustness pending

目标：

- 比较无上下文、父回复上下文和完整线程上下文。
- 检查反讽、否定、网络用语、拼写噪声、长文本和少数类。
- 对关键模块做消融，例如移除检索示例、标签定义或上下文。

通过条件：

- 至少一组控制实验或消融实验。
- 至少一组扰动、跨域或类别不平衡鲁棒性测试。
- 失败案例按类型整理，并说明哪些结论不能从当前结果推出。

当前进展：

- EXP-017 已完成 TweetEval 冻结 test 的全量 seed 稳定性、混淆、模型
  overlap 和 42 条预注册定性复核。
- 该结果只完成 failure analysis，不等于完成 context 或 robustness；
  后两者必须在新的 validation 或 forum holdout 上预登记，不能使用已阅读
  的 TweetEval test 案例开发。

## Phase 6: System, Thesis, and Archive

Status: not started

目标：

- 将已验证模型封装为可运行演示。
- 完成论文、技术报告、实验配置和复现说明。
- 将最终可对外表述绑定到证据编号。

通过条件：

- 演示不替代离线评估，且展示的功能均已实现。
- 代码、数据说明、配置、结果表和失败实验能够互相对应。
- 导师可以从仓库或交付包复核核心数字和个人贡献。

## Stop Conditions

出现以下情况时停止扩大模型规模，先修复研究设计：

- 数据授权或匿名化尚未明确。
- 训练集与测试集存在同线程、重复文本或标签泄漏。
- 简单基线尚未稳定复现。
- 只有 accuracy，或没有按类别指标。
- LLM 的模型版本、提示、成本或解析规则无法追溯。
- 新方法看似更好，但比较使用了不同数据、不同划分或不同评估脚本。
