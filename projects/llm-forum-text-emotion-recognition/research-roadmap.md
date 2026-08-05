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
Instruct LoRA -> frozen GoEmotions test gate
    |
    v
Forum data protocol -> context -> optional matched probe / SAE
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
| RQ-G1 | 在固定 GoEmotions 28 标签多标签任务上，BERT-base/RoBERTa 监督微调相对简单多标签基线增加了多少有效性能？ | 建立后续 LLM 比较所需的同数据集监督下界与强编码器基线，并记录类别不平衡、多标签阈值和细粒度标签的困难 | EXP-018 simple baseline；EXP-019 BERT smoke；EXP-020 BERT-base-cased Major；EXP-030 cross-model error analysis；EXP-038 frozen test gate | 结果章节的 GoEmotions 监督基线、多标签错误结构与正式测试表 | 阶段性解决：EXP-020 test Macro-F1=`0.488328 +/- 0.008771`，较 EXP-018 高 `0.292132`，较论文 test 参照 `0.46` 高 `0.028328`；EXP-030 的 dev 错误结构保留。GoEmotions test 已消费，RoBERTa alternative 不作为当前阶段关闭条件 |
| RQ-G2 | 在相同 GoEmotions 数据、标签和评估协议上，本地 post-trained LLM 相对冻结 BERT 增加了什么；Base、post-trained 与 task-LoRA 三个适配阶段又如何改变情绪标签的行为表现和线性可解码性？ | 一条实用性能证据链比较 zero/few-shot、LoRA、性能、格式、成本与延迟；一条配对控制证据链分离 decoder、训练目标与标注聚合影响，再使用同规模 Base/Instruct 的相同 frozen probe 隔离后训练影响，不把提示遵循或聚合标签复现误写为情绪机制 | EXP-021 Minor 环境与来源 smoke；EXP-022/023 parser failures；EXP-024 constrained-decoding gate；EXP-025 full-dev constrained zero/few-shot Major；EXP-026 matched unconstrained decoder Major；EXP-027 matched hidden-state smoke；EXP-028 matched frozen probe（资源门失败）；EXP-029 Instruct LoRA 三 seed Major；EXP-030 cross-model error analysis；EXP-031 neutral ontology inference ablation；EXP-032 acceleration preflight Minor；EXP-033 target-aligned LoRA Major；EXP-034 train neutral-cooccurrence diagnostic Minor；EXP-035 neutral co-occurrence annotation audit Major；EXP-036 dev rater-aware diagnostic Major；EXP-037 full-dev rater-aware diagnostic Major；EXP-038 frozen test gate | 结果章节的同数据集 LLM 2x2、LoRA、编码器与错误结构比较；Table-G2-4 至 Table-G2-10 的 ontology、标注与正式测试证据；讨论章节的表征、ontology 和 aggregated supervision 边界 | 行为线阶段性解决：EXP-038 test 上，历史 EXP-029 Macro-F1=`0.450652 +/- 0.032175`，target-aligned EXP-033 seed 42=`0.444675`，均低于 BERT `0.488328 +/- 0.008771`；EXP-029 仍标记 ontology-misaligned，EXP-033 是主要 aligned LLM 结果。此前 EXP-030 至 EXP-037 的近单标签偏向、聚合标注和 rater-aware 结论保持不变。test 已消费，EXP-033 seeds 43/44 不补跑；表征线仍开放，EXP-028 为 Failed，正式 probe 待新编号 |

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

Status: completed for public behavioral reproduction; GoEmotions EXP-038 test verified and consumed

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
- GoEmotions train、dev、test 和 `emotions.txt` 已从固定 revision 获取并校验；
  数据质量检查已记录于 `data/goemotions/manifest.json`，EXP-038 已完成一次性 test gate。
- EXP-018 已在固定 train/dev 上完成并独立验证：word TF-IDF + 28 个
  One-vs-Rest Logistic Regression 的 dev Macro-F1 为 `0.203644`，Micro-F1
  为 `0.377639`。
- EXP-019 已完成离线模型哈希、MPS 三步训练与 28 标签合成推理烟雾测试；
  不构成任务性能证据。
- EXP-020 已按冻结的 BERT-base-cased 条件完成三随机种子训练、dev 与正式 test 独立验证：
  dev Macro-F1 为 `0.489435 +/- 0.011063`，Micro-F1 为
  `0.586671 +/- 0.002928`。三个 seed 的 5,426 x 28 概率矩阵、指标、模型与
  输入哈希已复核，最大数值差异为 0；test Macro-F1 为
  `0.488328 +/- 0.008771`。
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

Status: metadata preflight completed; blocked by source authorization and historical coverage

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

2026-08-04 preflight：

- 已登记
  [`DATA-FCTX-PR-V1`](experiments/forum-context/protocols/data-source-parent-recovery-pilot-v1.md)，
  并仅从现有 manifest 确认 train/dev 共保留 48,836 个互异 comment IDs；未读取 test、
  下载 raw CSV、调用 Reddit API 或获取 parent text。
- GoEmotions 官方 raw schema 包含 `id` 和 `parent_id`，但当前 Reddit 官方政策要求
  学术研究通过获批的 RFR 项目，且 ML/AI training 需要明确同意。
- RFR 当前公开范围为最近五年历史，而 GoEmotions 来源截至 2019 年 1 月；在 Reddit
  书面确认历史覆盖前，直接恢复 GoEmotions parents 为 `NO-GO`，Dataset A/B 构建保持
  `BLOCKED`。

## Phase 3: Reproducible Supervised Baselines

Status: TweetEval and GoEmotions frozen test gates completed and verified

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

Status: behavioral line completed through EXP-038 frozen test and independently verified; EXP-033 seeds 43/44 remain unrun by design; representation line remains open after EXP-028 Failed

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
- EXP-032 在 train-only Minor 中固定比较 `batch2-grad5` 与 `batch5-grad2`。后者稳态
  rows/s 只有前者的 `0.981853`，峰值内存从 `5.179` GB 增至 `7.312` GB，故正式
  重训保留原 batch 配置。公共前缀 KV cache 虽有 `1.275726x` 端到端速度，但固定
  32 条训练样本只有 `31/32` 逐 token 一致，故拒绝缓存路径并保留完整 prompt。
  verifier 已复算通过；该预检不含 validation/test 性能证据。
- EXP-033 已作为 target-aligned LoRA Major 登记。其独立 runner 没有数据制备或
  dev/test 命令，逐字段继承 EXP-029 的模型、训练、资源和 repetition gate，只消费
  保留全部官方标签的冻结 train JSONL。当前 V3 将 protocol、runner、独立 verifier
  和 canonical MLX runtime contract 全部绑定到哈希；no-model dry-run、独立复算和
  PRE-EXP-033 V3 重放已确认 43,410 条 target、1,396 条 `neutral+emotion`、完整
  模型/MLX-LM 哈希和两份 train-only runtime config。V3 还通过关闭 stdout/stderr 后
  挂起的假进程验证 EOF 后剩余 wall-time 门。一次显式授权的 50-iteration train-only
  smoke 已完成并独立验证：10 次 optimizer update、`7.208` GB 峰值内存、`8.109`
  小时正式训练投影，224 个 LoRA 张量中的 112 个 `lora_b` 均非零；未读取 dev/test。
  随后的 formal V2 gate 与 seed-42 授权完成 4,341 次 optimizer update，训练约
  `7.49` 小时，峰值 `7.208` GB，独立 load/forward verifier 为 `Passed`。完整 dev
  validation Macro-F1=`0.427959`，较匹配的 seed-42 aligned-open 参考低 `0.012678`，
  paired 95% CI=`[-0.026938,+0.001434]`，故 improvement gate 未通过。全量预测标签
  cardinality 为 `1.058054`；174 条 neutral 共现样本仍没有目标共现预测。该负结果已
  独立复算，test 未获取；seeds 43/44 未授权。
- EXP-034 作为 Minor 直接回放冻结的 EXP-033 seed-42 adapter，在其训练时见过的全部
  1,396 条 `neutral+emotion` 样本上进行一次 greedy 推理。目标共现预测仍为
  `0/1,396`，预测 cardinality 为 `1.019341`，与 validation 切片的 `1.017241` 几乎
  相同；1,370 条输出只有一个标签，另有 26 条多标签输出，但没有一条包含 neutral。
  独立 verifier 重建训练切片并复算全部指标后返回 `Passed`，dev/test 未读取。该结果
  排除了“主要只是 held-out 泛化失败”的简单解释，但尚不能区分 exposure、token-level
  objective、标签顺序、优化/LoRA 容量或模型规模；原样运行 seeds 43/44 的信息价值下降。
- EXP-035 作为 Major 审计了相同 1,396 条 train target 的逐标注者原始投票。全部
  `1,396/1,396` 条都是不同标注者判断经 `>=2` 阈值聚合而成，同一标注者直接共选
  `neutral+emotion` 为 `0`，官方 simplified labels 全部精确复现。48 条冻结目的性
  文本复核中 6 条被编码为可能需要上下文，但不能外推到总体。该证据把数据聚合确认为
  异常结构的首要解释，不再要求模型无条件复现语义上冲突的 target。
- EXP-036 进一步冻结 174 条对应 dev allowlist、7 份既有预测与逐标注者评分语义。
  174/174 条仍为 aggregation-only，866 行 raw annotations 经官方 `>=2` 票规则全部
  精确复现。EXP-029 与 BERT 的 clear-rater expected set-F1 为
  `0.363250 +/- 0.017685` 与 `0.362531 +/- 0.002371`，family delta=`+0.000720`、
  95% CI=`[-0.018463,+0.019903]`，属于局部 practical tie。Qwen 的 official exact
  match 为 0，但 clear-rater expected/any-rater exact 为 `0.341284/0.852490`；这证明
  aggregate-union exact match 与个体标注一致度是不同问题。该 174-row 结果不能外推到
  完整 dev，也不能推翻 EXP-020 与 EXP-029 的 full-dev Macro-F1 差距。
- EXP-037 把相同证据边界扩展到完整 5,426 条 dev，复算 19,440 行逐标注者记录和
  7 份冻结预测。BERT/EXP-029 的 clear-rater soft Macro-F1 为 `0.383471/0.347253`；
  EXP-029 - BERT soft delta=`-0.036218`、95% CI=`[-0.043834,-0.029494]`，相对 official
  delta 的 shift=`+0.001843`、95% CI=`[-0.006779,+0.011015]`。expected individual-rater
  set-F1 delta 也为 `-0.010390`、CI 不跨 0。结论为 `gap_remains`：标注聚合会改变局部
  评分语义，但不足以解释总体性能差距，因此不默认登记 vote-distribution/soft-target
  重训。
- EXP-038 已执行一次性 official test gate。EXP-018/020/025/029/033 的 Macro-F1 为
  `0.196197`、`0.488328 +/- 0.008771`、`0.233653`、
  `0.450652 +/- 0.032175` 和 `0.444675`。9 个冻结单元均独立复算通过，test 已消费。
  下一决策门转为冻结论坛数据与上下文协议，或为表征支线登记资源可行的新 probe。

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

Status: partial; TweetEval and GoEmotions error/annotation analysis completed, forum context and robustness pending

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
- EXP-030、EXP-035 至 EXP-037 已完成 GoEmotions 的跨模型错误结构、逐标注者聚合
  与完整 dev 分歧感知诊断；EXP-038 正式 test 已验证并消费。
- 该结果只完成 failure analysis，不等于完成 context 或 robustness；
  后两者必须在新的 validation 或 forum holdout 上预登记，不能使用已消费的
  TweetEval 或 GoEmotions test 开发。

## Next-Stage Plan: Context-Aware Forum Emotion Recognition

Status: discussion draft recorded on 2026-08-04; not yet an experiment protocol

本节记录 GoEmotions 公开行为复现结束后形成的下一阶段方案。它整理的是当前已经
讨论过的研究设计，不分配新的 EXP 编号，也不提前决定数据来源、最终样本量、模型
revision、超参数或测试门。若本节与前文 Phase 2/5 的早期占位描述冲突，下一阶段以
本节为准；已经完成并验证的 TweetEval 和 GoEmotions 实验不受影响。

### Research Objective

论文题目保持为：

- 中文：基于大模型的论坛文本情感识别。
- 英文：Research and Implementation of Emotion Recognition System of Forum Text Based on LLM。

研究目标不是证明 LLM 一定超过 BERT，而是研究论坛回复上下文是否改变情绪识别，
比较不同模型状态的行为与内部表征，并完成一个可运行的识别系统。

当前研究问题为：

1. 正确的父回复上下文是否能帮助模型识别 target comment 的情绪？
2. BERT、Qwen Base、Qwen post-trained 和 Qwen LoRA 在上下文收益、多标签预测及
   失败模式上有何差异？
3. 情绪标签和上下文条件是否能从不同层的 hidden state 中被线性解码？
4. 预训练、后训练和任务 LoRA 是否改变情绪相关表征及其上下文敏感性？

### Evidence Structure

下一阶段采用两个用途不同的数据集，不能把二者的结论混写。

#### Dataset A: GoEmotions Context Augmentation Dataset

在能够合规恢复父回复的前提下，为 GoEmotions target comment 增加上下文。标签仍是
原始的 target-only GoEmotions 标签，用于较大规模地测试模型行为与上下文稳定性。

固定比较三种输入：

```text
A. target only
B. correct parent + target
C. matched random parent + target
```

随机 parent 应尽量匹配论坛版块、文本长度和时间范围，排除同一 thread，并固定抽样
规则和随机种子。Dataset A 可以回答“附加上下文是否帮助模型恢复原始标签”以及
“正确上下文是否优于等量随机上下文”，但不能单独支持“模型更符合上下文中的人类
情绪判断”。

#### Dataset B: Context-Aware Emotion Annotation Subset

Dataset B 是上下文结论的主要证据。相同类型的论坛 target 分别在以下条件下由人类
标注：

```text
Condition 1: target only
Condition 2: parent + target
```

它用于比较人类在有无上下文时对 target 情绪的判断，并为模型的上下文识别能力提供
与任务定义一致的 gold labels。Dataset A 是规模与稳定性实验，Dataset B 才承担
context-aware emotion recognition 的主要结论。

### Data and Compliance Gate

Closed-corpus preflight completed on 2026-08-04 under
[`DATA-FCTX-CJ-V1`](experiments/forum-context/protocols/data-closed-corpus-parent-coverage-v1.md).
All 48,836 train/dev targets matched official raw metadata, but only 157 (0.3215%)
had parent-comment text available inside the official release. Parent text was
missing for 48,679 targets: 19,987 parents were submissions not represented in
the comment corpus, and 28,692 were comment IDs absent from the raw release.

This is missing **parent text**, not missing `parent_id`: every audited target had
a parent identifier. Because the raw release is unpartitioned, the 157 available
pairs are not automatically split-safe. The official-release-only route is
therefore insufficient for the planned large-scale Dataset A and does not advance
to annotation or model training.

执行顺序必须是：

```text
确认来源、授权和使用边界
-> 仅用现有标识检查元数据可行性
-> 小规模 parent recovery pilot
-> 恢复率、缺失和偏差审计
-> 通过后才构建 Dataset A 与 Dataset B
```

在确认允许的研究用途、文本保存方式、再分发范围和删除处理前，不开始批量恢复
parent text。pilot 至少记录成功恢复、deleted/removed、无法恢复及 parent 类型；并
比较可恢复与不可恢复样本的原始情绪分布、target 长度、论坛版块和时间等可用属性，
避免最终数据只代表“容易恢复的样本”。

若来源不允许使用、恢复率不足或缺失具有明显系统性偏差，则停止该数据构造路线，
改用授权更明确的上下文论坛数据或重新准备合规数据，不以技术手段绕过来源限制。

原始文本、原始用户标识和可逆映射不得进入公开 Git；公开产物只保留协议、统计、
哈希、匿名化样例和允许再分发的处理结果。

### Annotation Pilot

人工标注先做约 200--300 条 pilot，再依据一致性、上下文导致的标签变化比例和实际
成本决定是否扩大。抽样同时保留：

- 代表总体分布的随机样本，用于估计上下文变化的实际比例。
- 可能依赖上下文的样本，例如短回复、反讽、否定、代词指代、隐含情绪和歧义文本，
  用于提高诊断能力；该部分必须与随机样本分层报告。

标注遵循以下原则：

- 标注 target 表达或暗示的情绪，不标注 parent 的情绪，也不推断作者的真实心理状态。
- 使用 GoEmotions 28 标签多标签体系以保持可比性；只做一次细粒度标注，粗粒度结果
  由事先冻结的映射派生，不要求标注者重复标两套标签。
- `unclear` 单独记录，不能与 `neutral` 合并。
- 同一标注者不能看到同一 target 的两个条件，以免记忆污染；不同 target 的条件应
  随机、平衡分配。
- 目标是每条样本、每个条件至少获得 3 份独立判断；最终人数和工作量在 pilot 后确认。

一致性至少从两个层面报告：逐标签二元一致性，以及样本标签集合的 Jaccard 或 set-F1。
若使用 kappa 或 Krippendorff's alpha，必须明确其多标签编码和距离定义，不能用一个
未经说明的总体 kappa 代替多标签一致性。最终 gold label 的投票、阈值、`unclear`
处理和 adjudication 规则需在正式标注前单独冻结。

### Split and Input Rules

- 所有 train/dev/test 按 `thread_id` 分组划分，同一 thread 不得跨 split。
- Dataset B 建立新的 held-out test；只允许在模型、阈值和分析方案冻结后消费一次。
- target-only、correct-parent 和 random-parent 条件使用相同 target 集合与评估代码。
- 输入格式、最大长度、截断方向和 target 保留规则必须一致；上下文实验不使用 target
  之后的回复，避免引入未来信息。
- 已消费的 TweetEval 和 GoEmotions test 不得用于选择本阶段的数据规则、模型、层、
  pooling、prompt、阈值或超参数。

### Model Matrix

性能与表征实验使用以下主模型：

| Model state | Training/readout | Purpose |
| --- | --- | --- |
| BERT-base | BCE multi-label fine-tuning | 传统 encoder 强基线 |
| Qwen3-4B-Base | frozen hidden state + linear classifier | 检查预训练表征中的线性可解码信息 |
| Qwen3-4B post-trained | frozen hidden state + 相同 linear classifier | 隔离 post-training 的影响 |
| Qwen3-4B post-trained + LoRA | classification LoRA + BCE | 检查任务适配后的性能与表征变化 |

Qwen 的候选配对为 `Qwen/Qwen3-4B-Base` 与 `Qwen/Qwen3-4B`；精确 revision 必须在
正式 protocol 中固定。此前口头讨论中的 “Instruct” 指这里的 post-trained 模型，
不能用名称不同但预训练谱系不匹配的模型代替。

Base、post-trained 和 LoRA 的表征比较必须固定输入序列、token IDs、最大长度、
pooling、精度、数据 split 和 probe 架构，并先通过 tokenization equivalence preflight。
LoRA 后进行表征比较时，应冻结适配后的 backbone，再训练一份新的相同 linear probe；
不能把 LoRA 训练时的任务分类头直接当作 probe 证据。

主表征实验使用 BF16 或 FP16 的非量化模型。若租用 GPU 后仍需采用 QLoRA，必须将
量化条件作为独立实验变量记录，不能与非量化 hidden state 结果直接归因比较。
thinking/reasoning 关闭只约束生成式实验；hidden-state forward 的输入路径仍需单独固定。

### Generation and Classification Boundary

主路线是 hidden-state multi-label classification。Qwen post-trained 直接根据 prompt
生成 emotion labels 只作为辅助的“开箱即用”能力实验，单独记录 parser、格式率、
成本和延迟，不与 BCE classifier 的分数混成同一模型条件。

Classification LoRA 是主任务适配路线；Generative LoRA 暂不进入主实验，因为现有
GoEmotions 复现已显示生成式读取容易出现单标签偏向和格式问题。

### Evaluation

主指标为 Macro-F1，同时报告：

- Micro-F1 和 Samples-F1。
- 每类 precision、recall、F1 和 support。
- 平均预测标签数及 gold label cardinality。
- subset accuracy 作为补充，不作为唯一结论。
- 概率输出的校准指标。
- 代表性样本与 context-likely 样本的分层结果。

阈值只能在 dev 上选择并冻结。核心随机训练至少运行 3 个 seeds，报告 mean +/- std。
A/B/C 同 target 比较采用 paired bootstrap；实际显著性判定和 practical-tie 阈值在正式
protocol 中登记。

### Representation Claim Boundary

Layer-wise linear probe 只能说明某层的情绪或上下文信息具有线性可解码性，不能直接
证明模型采用了人类情绪机制。保持 target 不变、替换 correct/random/语义相反 context
属于输入干预，可以支持“上下文变化导致预测或表征变化”，但仍不能据此声称发现了
emotion neuron。

只有后续加入 activation patching、ablation 或 steering 等内部干预，才可能提出更强
的因果表征证据。Sparse Autoencoder（SAE）放在 layer probe 确定候选层和现象之后，
属于可选扩展，不是毕设完成条件。

### Execution Order

```text
Phase 0  TweetEval + GoEmotions 公开行为复现（已完成）
    |
Phase 1  数据来源、合规边界与 parent recovery pilot
    |
Phase 2  Dataset A 构造 + Dataset B 人工标注 pilot
    |
Phase 3  thread-level split、数据卡与正式标注协议冻结
    |
Phase 4  BERT-base context baseline（A/B/C）
    |
Phase 5  Qwen Base/post-trained frozen linear classifiers（A/B/C）
    |
Phase 6  Qwen post-trained classification LoRA
    |
Phase 7  layer-wise probes + controlled context intervention
    |
Phase 8  one-time held-out test + demo + thesis evidence archive
    |
Optional SAE / activation intervention
```

每个正式训练或评估阶段仍需在 `experiments/` 下建立独立 protocol 和实验编号；本节
只规定研究依赖顺序，不授权下载数据、读取新 test 或启动训练。

### System Deliverable

最终 demo 至少接收 parent 和 target，输出多标签情绪及置信度，并能够并列显示
target-only 与 parent+target 的预测变化。界面记录所用模型版本和推理延迟，并在低
置信度或条件变化较大时提示人工复核。系统输出是文本情绪识别结果，不应表述为对
作者真实心理状态的诊断。

### Current Risks and Pending Decisions

当前风险优先级为：

1. parent 数据来源、恢复许可和样本缺失偏差。
2. context-aware 标注的一致性及上下文真正改变判断的比例。
3. Base/post-trained/LoRA 模型配对和输入路径是否公平。
4. LoRA 是否产生稳定收益。
5. layer probe、内部干预和 SAE 是否能形成额外解释证据。

正式开始前仍待确认：数据来源与授权文本、parent recovery 方案、pilot 后的正式样本量、
标注聚合规则、Qwen 精确 revision、GPU 环境、最大上下文长度、pooling 与选取层。当前
不扩展到 8B/更大模型、Llama/Gemma 横向比较、完整 reply path、full fine-tuning 或把
SAE 设为必做项。

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
