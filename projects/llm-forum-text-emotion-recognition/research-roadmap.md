# Research Roadmap: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
last_updated: 2026-08-13
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
传统分类器 -> 通用 RoBERTa -> Twitter-domain RoBERTa -> frozen test
    |
    v
GoEmotions public-task reproduction（completed）
简单多标签基线 -> BERT-base -> Qwen direct generation -> Qwen LoRA -> frozen test
    |
    v
IAC 2.0 forum-data pilot（closed as exploratory diagnosis）
清洗/去重 -> 标注试验 -> stance-emotion 与 ontology mismatch
    |
    v
Weibo task protocol and split（completed; verified）
EClass rows -> single-label ontology -> group-disjoint split -> leakage/dedup audit
    |
    v
Environment/model/parser/LoRA preflight（completed; verified）
    |
    v
M0/M1/M2 same-dataset baselines（completed; verified）
majority/TF-IDF -> Chinese encoder
    |
    v
Frozen Qwen context x reasoning 2x2 on dev（completed; verified）
CurCL / PrevCL+CurCL x reasoning off/on
    |
    v
Generative LoRA + frozen dev error analysis（completed; verified）
    |
    v
TEST-READY -> one-time held-out test（completed; verified; consumed）
    |
    +--> read-only post-test analysis -> system/thesis archive
    +--> optional matched representation analysis -> optional SAE/intervention
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
| RQ-F1 | 在冻结的 Weibo EClass 单标签任务上，传统文本分类器、中文 encoder 与本地 Qwen 的性能、稳定性和成本有何差异？ | 在同一任务、split 和评估脚本上建立论坛式中文社交文本的直接证据链；若 Qwen 不优于 encoder，负结果仍能界定其系统成本与适用边界 | DATA-WEIBO-TASK-V1；EXP-041 model-stack preflight；EXP-042 M0/M1/M2 Major；EXP-043 frozen Qwen 2x2；EXP-044 LoRA cost preflight；EXP-046 runtime-equivalence gate；EXP-047 generative LoRA Major；EXP-048 frozen dev error analysis；EXP-049 frozen test gate | 方法章节的数据与任务定义；结果章节的同任务模型主表与错误结构表 | 阶段性解决：EXP-049 test 上 encoder/LoRA/matched Qwen reference Macro-F1=`0.649621 +/- 0.007365`/`0.636612 +/- 0.021429`/`0.316921`。LoRA-reference delta=`+0.319691`，95% CI `[+0.274779,+0.362068]`；LoRA-encoder delta=`-0.013009`，CI `[-0.045671,+0.024011]`，点估计触发冻结退化规则但区间跨 0，不支持确定的 encoder 优势。test 已消费，不再用于调参或模型选择 |
| RQ-F2 | 对同一 target，固定局部前文和 reasoning-mode inference 是否分别改善 Qwen 的最终单标签预测，两者是否存在交互？ | 用 `CurCL`/`PrevCL+CurCL` x reasoning off/on 的配对 2x2 分离上下文、推理模式及其交互；若无稳定收益，也能排除“增加上下文或生成推理必然更好” | EXP-041 train-only preflight；EXP-043 Qwen 2x2 Major；EXP-046 runtime-equivalence gate；必要时 correct-vs-shuffled-context control | 结果章节的 2x2 主表与交互图；讨论章节的 context/reasoning 与 runtime 边界 | 阶段性解决：观测 context contrast=`-0.021512`、CI 排除 0；平均 reasoning contrast=`+0.030825`、CI 排除 0；interaction CI 跨 0。EXP-046 显示固定 batch 可重放但共同批次重排仅 `14/16` 标签一致，因此后续 reasoning-on 正式评估冻结 singleton；context 未通过 shuffled-control 门 |
| RQ-F3 | 在 Weibo 直接基线冻结后，同语料辅助任务或外部中文 ERC 迁移是否比 Weibo-only 训练增加可复现收益？ | 区分目标任务监督与迁移监督的增量价值；负结果可说明语言、领域或 ontology mismatch 抵消了迁移收益 | Conditional same-corpus ECause auxiliary；可选 T / S-U->T / S-C->T / S-R->T transfer Major，EXP 编号待登记 | 可选结果/消融章节；不作为最低毕设闭环 | 条件性扩展；只有 RQ-F1/RQ-F2 的 dev 证据完成后才决定是否启动 |
| RQ-F4 | 行为上已验证的 Qwen 中，情绪标签和上下文条件是否在不同层呈现稳定的线性可解码信息，post-training/LoRA 是否改变这种结构？ | 将性能结果连接到受控的表征相关性证据；无稳定 probe 结果时如实形成负结果，不阻塞系统论文 | Matched layer-wise probes；label-shuffle/control tasks；可选 SAE、patching/ablation，EXP 编号待登记 | 可选表征分析章节 | 后置扩展；必须在行为模型与分析层/池化规则冻结后启动 |

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

## Phase 2: Forum Data Protocol and Dataset Selection

Status: IAC 2.0 exploratory branch closed after diagnosing stance-emotion and ontology mismatch; Weibo EClass task/split protocol completed and verified

目标：

- 确定每个候选来源的许可、隐私、保存和再分发边界。
- 用 IAC 2.0 小规模 human calibration 检查自建标签方案；该分支只作数据诊断，不继续
  扩大标注或裁决为正式 gold。
- 对 Weibo EClass 另行冻结单标签 ontology、输入字段、分组划分、去重和泄漏规则；不能
  沿用 IAC2 或 GoEmotions 的标签协议。

IAC2 探索性清洗候选的最低字段：

```text
sample_uid, thread_uid, parent_uid, target_uid,
discussion_title, direct_parent_body,
target_quote_blocks, target_body, target_full_with_quotes,
target_only_decision, contextual_decision
```

通过条件：

- 原始身份信息不进入公开训练数据。
- 按来源中真正承载依赖关系的 group 划分：IAC2 使用 `thread_id`，Weibo 使用
  multi-user group；同一依赖组不得跨 split。
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
  书面确认历史覆盖前，直接恢复 GoEmotions parents 为 `NO-GO`，历史方案中的
  GoEmotions Dataset A/B 构建保持 `BLOCKED`。

2026-08-05 IAC 2.0 cleaning：

- 4forums 已在条件性、非商业本地研究边界下作为论坛上下文候选源；原文、派生文本、标签和
  checkpoint 均不公开。
- [`DATA-FCTX-CLEAN-V2`](experiments/forum-context/dataset-construction/protocols/data-cleaning-quality-filter-v2.md)
  对 414,453 帖生成 403,374 个 parent-target 候选，403,336 个通过保守 hard filter。
- 539,658 条 quote 全部完成层级重建核对：537,778 条顶层、1,880 条嵌套 offset 有效，
  missing parent、out-of-bounds 和 cycle 均为 0。
- 独立验证器通过 40 项检查且 mismatch 为 0；清洗产物尚未进行情绪标注、样本抽取、
  去重或 thread-disjoint split。

2026-08-05 IAC 2.0 deduplication：

- [`DATA-FCTX-DEDUP-V2`](experiments/forum-context/dataset-construction/deduplication/protocols/data-deduplication-v2.md)
  对 403,336 个 eligible parent-target pairs 执行精确、词法近似与语义近似检测。
- 仅精确重复与纯格式差异允许自动折叠：保留 403,183 条，自动去除 153 条；每个删除
  均有指向最终保留项的直接证据边，semantic-only 自动删除为 0。
- 68,552 条 review-only 近邻边组成 249 个簇、涉及 1,308 条候选；这些簇尚未人工裁决，
  后续抽样协议必须将其作为分组或排除约束。
- HNSW 的冻结 128-query audit 得到 mean recall@64=0.992554，超过 0.98 门槛，且
  `k=512` 时饱和查询为 0；独立 verifier 69 项检查全部通过。
- V1 因 mean recall@64=0.975464 未达门槛且 token 长度统计错误而保留为 `Failed`；
  V2 未复用其边或决策。

2026-08-05 label calibration and annotation view：

- [`DATA-FCTX-LABEL-V1`](experiments/forum-context/protocols/data-label-calibration-view-v1.md)
  冻结 10 种不合并的原子情绪候选加 `neutral`，采用 single-primary-label calibration；
  `other_emotion` 和 `unclear` 不直接作为最终训练类别，强度不采集。
- 标注固定为两阶段：先锁定 target-only decision，再展示 discussion title、direct parent、
  target quote blocks 和 target full 得到 contextual decision；未来回复和完整祖先链不进入 V1。
- sarcasm 作为独立修辞属性，不自动映射为 cynicism；mixed emotion 只作诊断 flag，V1
  不收集 secondary label。
- 私有文本 view 与 sidecar annotation record 使用独立 JSON Schema；真实记录只能写入
  gitignored `data/iac2/annotations/`。最终训练 ontology 和 split 仍待 pilot 结果与后续
  正式数据协议。
- [`DATA-FCTX-SAMPLE-V1`](experiments/forum-context/protocols/data-annotation-sampling-pilot-v1.md)
  冻结 80 个受约束随机案例、四组各 10 个 diagnostic cases、24 个 blind repeats、固定
  seed、每 thread/review cluster 至多一例、reserve 替换和一致性/context review gates。
  sampler preflight 通过前不得导出真实标注 view。

2026-08-06 sampling preflight：

- metadata-only sampler 从 403,183 条候选中确定性选择 120 条主样本与 60 条备用样本；
  180 条样本和 thread 均全局唯一，非空 review cluster 也满足至多一例约束。
- 四个 diagnostic pool 容量分别为 sarcasm 662、hostility-affect 1,153、short-context
  1,757 和 distinct-quote 37,233，均超过冻结配额。
- 独立 verifier 重放 hash ranking、lane eligibility、顺序与全局约束，45 项检查全部通过，
  mismatch 为 0。私有 manifest 权限为 `0600` 且受 Git ignore 保护；公开报告无论坛文本、
  源 ID、HMAC ID 或逐样本记录。
- 24 条 blind repeats 尚未生成，需等 120 条样本完成 `unusable` 替换后再按 72 小时 washout
  规则物化。下一门是私有 staged-view exporter 的 schema、allowlist 与隐私验证。

2026-08-06 private staged-view export：

- 按冻结 annotation order 为 120 条主样本生成 `0001.json` 至 `0120.json`；私有目录权限
  `0700`、全部文件权限 `0600`，并继续受 Git ignore 保护。
- 89 条样本包含 target quote，共 164 个顶层引用块：direct parent 123、same-thread other
  29、external or unknown 12。该结构统计不包含情绪标签，也不用于更换样本。
- 独立 verifier 从 cleaning/dedup SQLite 逐份重建并比较内容，34 项 hash、Schema、顺序、
  allowlist、权限和隐私检查全部通过；mismatch、schema problem、隐藏 sampling/source
  metadata 和公开 payload violation 均为 0。
- Stage A 必须先提交并锁定、Stage B 才能揭示的边界已在全部 120 条 Human Pass 1
  记录中执行；repeat manifest 未生成。

2026-08-07 human pass and direct comparison：

- Human Pass 1 完成 120/120 条 Stage A 与 Stage B，原始记录以只读 checkpoint 固定；
  人工在查看模型标签前记录了 stance 主导、话题集中、长引用和 post-level 多片段问题。
- 因 IAC2 很可能不是最终训练集，项目作者预先登记 amendment，取消 24 条延迟盲重标，
  将 pilot 改为探索性数据诊断。由此不再报告人工时间稳定性或 inter-annotator agreement。
- 三方 Stage B 精确一致为 21/120；Human/Model 1、Human/Model 2、Model 1/Model 2 的精确
  一致率分别为 25.83%、24.17% 和 58.33%。这些是来源比较，不定义 gold。
- Human Stage B 的 30 个 `other_emotion` 提议中有 18 个 `disapproval`、11 个 `approval`
  和 1 个 `regret`，说明当前数据和协议把论坛立场与情绪识别混在了一起。
- 106 条至少存在一次 Stage A 或 Stage B 分歧的记录已写入私有 sidecar；公开报告无
  论坛文本、ID 或逐样本标签。该 pilot 已完成诊断作用，当前不继续扩大标注。

2026-08-08 public candidate viability audit：

- 在读取任何候选样本前冻结
  [`DATA-FCTX-PUBLIC-AUDIT-V1`](experiments/forum-context/protocols/data-public-candidate-viability-audit-v1.md)，
  只审计 KOTE train/validation、Hotter and Colder CLARIN 发布包和 Weibo Emotion Cause
  Corpus 固定版本；未下载 KOTE test、未执行 hydration、未训练模型。
- KOTE 的 40,000 train 与 5,000 validation 均为三列 C0 多标签数据，跨 split ID 和精确文本
  overlap 均为 0。平均 7.91 个正标签与论文的五人投票、样本内 min-max 和 `> 0.2`
  二值化一致；它通过 training/control 候选门，但仍需单独冻结 ontology mapping。
- Hotter 发布包实测 19,828 行标注、12,675 个 URL/时间目标键，但没有目标或上下文文本；
  hydration 脚本实时请求网页、无 timeout、默认只处理 50 行并拼接签名。0 个目标拥有完整
  8 情绪标注，README 与实际标签 schema 也不一致，因此状态为 `blocked_pending_review`。
- Weibo 两个 TSV 含 quoted embedded newlines，分别解析为 12,586 与 23,127 条逻辑记录；
  后者混合 12,052 条 cause scaffold 和 11,075 条 emotion clause，且与独立 cause 文件仅
  120 条记录完全相同。它只通过 C1 emotion-cause auxiliary 门，不能按行 join 或替代主任务。
- 独立 verifier 重解析原始快照、复算关键统计与哈希，并核对 test/hydration/Git-ignore
  边界，35/35 项通过。下一门是数据采用决策，而非训练：确认 KOTE C0、Weibo auxiliary
  与 IAC2 challenge 的有限角色后，才冻结映射、group-disjoint split 和模型/test 协议。
- 2026-08-08 审计后决策：排除 Hotter and Colder。其冻结审计结论和本地忽略快照仅用于
  追溯；不执行 hydration，也不用于训练、模型选择、评估或论文主张。后续数据采用门只
  需决定 KOTE、Weibo、IAC2 的有限角色以及上下文主数据来源。

2026-08-08 Weibo 后续任务结构检查与暂定决策：

- 前述 `eligible_auxiliary` 是公开候选广度审计在当时问题边界内的结论，不被改写。后续
  检查进一步确认 `emotion_classification.tsv` 内存在可独立定义的 EClass 单标签子任务，
  因而将其升级为**有条件的下一阶段主任务候选**；该升级仍需新协议和 verifier 才能成为
  `Verified` 数据采用证据。
- 当前解析得到 11,075 条 emotion-clause 候选，属于 3,386 个 multi-user groups；11,073 条
  同时具备可解析的 `PrevCL`、`CurCL` 与 `SufCL` 字段，7,688 条具有非空前一 clause。
  这些数字是下一协议的待复核输入，不是已冻结训练集规模。
- 主输入定义为 `CurCL`，固定可部署上下文定义为 `PrevCL + CurCL`。`PrevCL` 是组内前一
  clause，不保证是 direct reply 或 parent；因此论文应称其为 fixed local discourse context，
  不能写成完整 thread context。`SufCL` 含未来信息，只能作为可选离线消融，不能进入主系统。
- EClass 没有官方 train/dev/test split。必须按 multi-user group 分组划分，并在划分前处理
  跨组精确/近似重复，防止同一文本或相邻 clause 通过 target/context 角色跨 split 泄漏。
- KOTE 保留为低优先级 C0 多标签控制，IAC2 只保留 challenge/数据失败案例，Hotter and
  Colder 已排除；三者都不阻塞 Weibo task protocol。

2026-08-08 `DATA-WEIBO-TASK-V1` execution：

- 从 11,075 条 EClass 逻辑记录中按冻结规则保留 8,540 条七分类样本；结构损坏 group、
  `fear` 和 composite/unknown labels 按协议排除。
- 同 target-label 折叠 2,422 条；117 个多标签 target 的 295 条记录保留，但绑定在同一
  leakage component。冻结词法近重复审计命中 0 对，不据此声称语义等价。
- group/target/duplicate-disjoint split 为 train 5,995、validation 1,272、sealed test
  1,273；6,138 条有 `PrevCL`，2,402 条无前文。两个输入视图逐条配对。
- 独立 verifier 通过 33/33 项检查；标签最大分配误差 0.005882，context/ambiguity 切片
  最大分配误差 0.022315。test labels 已密封且 Git ignored。
- 该证据只验证数据构建与采用，不产生模型结果，也不授权训练代码读取 test labels。

## Phase 3: Reproducible Supervised Baselines

Status: TweetEval and GoEmotions frozen test gates completed and verified; Weibo Stage 3 same-task baselines completed and verified

目标：

- 将 EXP-018 固定为 GoEmotions 简单多标签 sanity baseline。
- 在相同 GoEmotions 数据和标签空间上建立 BERT-base 或 RoBERTa 编码器基线。
- 编码器冻结后，才允许登记 GoEmotions LLM 对照。
- Weibo 协议通过后，从 majority、word/character TF-IDF 线性模型开始，再训练中文
  BERT/RoBERTa encoder；所有方法使用同一 EClass 单标签任务和 group-disjoint split。
- BERT/RoBERTa 只作同任务强基线，不作为教师生成伪标签，也不参与 Qwen 系统推理。
- 只有简单基线和 encoder 的 dev 结果可复算后，才启动 Qwen direct/LoRA 主比较。

主要指标：

- Macro-F1。
- 每类 precision、recall 和 F1。
- Accuracy 和 Weighted-F1，仅作为补充；多标签专用的 Samples-F1 不用于 Weibo EClass。
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

## Phase 5: Context, Reasoning, Robustness, and Failure Analysis

Status: partial; TweetEval and GoEmotions error/annotation analysis completed, forum context and robustness pending

目标：

- 在同一 Weibo target 上比较 `CurCL` 与 `PrevCL + CurCL`，不把 `PrevCL` 误写为 parent。
- 对同一冻结 Qwen checkpoint 交叉比较 reasoning off/on，只评估最终标签、格式、成本、
  延迟和重复稳定性，不把生成的 reasoning text 当作 gold 或忠实机制。
- 若正确上下文出现收益，增加 matched shuffled-`PrevCL` 控制，检查收益来自语义相关性
  还是仅来自更多 token。
- 检查隐含情绪、否定、反讽、网络用语、长文本、首 clause 无上下文和少数类。

通过条件：

- 完成 context x reasoning 的配对 2x2，并报告主效应与交互。
- 至少完成一组 shuffled-context、类别不平衡或输出随机性控制。
- 失败案例按类型整理，并说明哪些结论不能从当前结果推出。

当前进展：

- EXP-017 已完成 TweetEval 冻结 test 的全量 seed 稳定性、混淆、模型
  overlap 和 42 条预注册定性复核。
- EXP-030、EXP-035 至 EXP-037 已完成 GoEmotions 的跨模型错误结构、逐标注者聚合
  与完整 dev 分歧感知诊断；EXP-038 正式 test 已验证并消费。
- 该结果只完成 failure analysis，不等于完成 context 或 robustness；
  后两者必须在新的 validation 或 forum holdout 上预登记，不能使用已消费的
  TweetEval 或 GoEmotions test 开发。

## Next-Stage Experimental Plan: Weibo Single-Label Context and Reasoning

Status: `DATA-WEIBO-TASK-V1` and train-only Stage 2 preflight verified on
2026-08-08; no dev Major or test access is authorized by this section

本节取代 2026-08-04 的 GoEmotions parent-recovery 方案，作为后续实验的当前设计稿。
它不改写 TweetEval、GoEmotions 或 IAC2 的历史证据，也不把尚未登记的实验写成已完成。

### Scope Decision

论文题目保持为：

- 中文：基于大模型的论坛文本情感识别。
- 英文：Research and Implementation of Emotion Recognition System of Forum Text Based on LLM。

下一阶段的核心经验任务冻结为 Weibo EClass 单标签分类。Weibo 是中文微博多用户讨论
语料，可作为 forum-like social discussion 的可执行代理，但不是一般论坛的完整代表。
除非后续增加跨域验证，论文结论必须限定在该语料、该标签体系和 fixed local context，
不能声称已经证明所有论坛或完整回复树上的泛化能力。

最低毕设闭环为：

1. 冻结并验证 Weibo EClass 任务、标签、group-disjoint split 和两个输入视图。
2. 在同一数据上完成简单基线、中文 encoder 与本地 Qwen 对照。
3. 完成 `context x reasoning` 配对 2x2，只以最终标签衡量 reasoning-mode 的实际收益。
4. 在 dev 冻结配置后一次性评估 test，完成错误分析和可运行系统。

迁移学习、Base/Instruct 表征比较、layer probe、SAE 和内部干预均为后置扩展，不阻塞
最低闭环。TweetEval 与 GoEmotions 只证明此前的实验流程和公开任务复现，不作为 Weibo
的训练数据、教师标签或跨任务数值对照。中文数据不因语言本身降级；语言只在迁移实验
涉及跨语言来源时成为需要控制的变量。

### Task and Input Definition

- 预测单位：一条 EClass emotion-clause 的 `CurCL`。
- 主任务：从冻结 ontology 中预测 `CurCL` 按上游标注所表达的一个且仅一个
  `primary_emotion`；不推断作者不可观察的真实心理状态。
- Target-only 输入：`CurCL`。
- Context 输入：`PrevCL + CurCL`，并用稳定边界标记区分上下文与待分类 target。
- `PrevCL` 只是同一 multi-user group 中的前一 clause，不保证是 direct reply、parent 或
  同一作者发言。系统和论文必须使用“固定局部前文”或 local discourse context 的表述。
- `SufCL` 含 target 之后的信息，不进入主训练、主评估或最终系统；若以后使用，只能作为
  明确标记为 offline/non-deployable 的未来信息消融。
- 在最终 8,540 条任务记录中，2,402 条 `PrevCL` 为空，6,138 条可提供局部前文。完整
  split 用于系统总体表现；context-available
  paired slice 用于估计上下文本身的效应，首 clause slice 单独报告。

本阶段使用上游已有人工标签，不重新人工标注 11,075 条数据，也不让 BERT 或外部 LLM
生成主任务 gold。若以后引入无标签论坛数据，伪标签、人工复核和数据权利必须另建协议。

### Label Ontology Gate

Weibo 原始标签混合细粒度情绪、粗粒度 sentiment、`neutral`、`No_emotion`、极少数
`fear` 和 45 条 composite labels。它不是可以直接送入训练器的干净 ontology。正式数据
协议已在读取模型结果前冻结以下主方案：

- Frozen paper-comparable set：`joy`、`sadness`、`anger`、`positive`、
  `negative`、`neutral` 和 `No_emotion`。
- `fear`：因样本极少且原论文主实验忽略该类，不并入主比较；保留聚合计数。
- 45 条 composite rows：不拆分、不把组合字符串当作新单类，不用于主训练；保留在公开
  聚合统计和私有诊断清单中。
- `positive`/`negative` 虽比 `joy`/`anger` 粗，仍为上游有效标签；主复现中不得按直觉合并。
- `neutral` 与 `No_emotion` 保持不同，除非上游文献提供可核验的等价定义；不得为了提高
  分数把多数类重新映射。

由于 `No_emotion` 占多数，Accuracy 不能作为主模型选择指标。任何 class weighting、
resampling 或 focal loss 都是后续受控消融，不能在第一个 encoder/LLM 结果出来后无记录地
改变主任务。

### Data Construction and Split Gate

`DATA-WEIBO-TASK-V1` 已完成以下数据构建要求，且未启动模型训练：

1. 用 TSV parser 处理 quoted embedded newlines，过滤 12,052 条 `Y/N` cause scaffold，
   只保留满足 EClass schema 的 emotion-clause rows。
2. 从模型输入中剔除 gold emotion、cause judgment、结构答案标记和任何可直接泄漏标签的
   字段；只保留允许的自然语言 clause 与匿名 group/row ID。
3. 在划分前完成 exact、normalized-exact 和近似语义重复审计。跨 group 重复要么折叠，
   要么绑定到同一 split；自动删除只允许有可复核证据的精确/格式重复。
4. 按 multi-user group 做固定的 stratified group split。精确比例、seed 和不可行时的
   fallback algorithm 在 protocol 中预注册；同一 group、重复簇和相邻 clause 不得跨 split。
5. 对 train 拟合所有词表、IDF、class weights 和采样规则；dev 用于模型、prompt、parser、
   checkpoint 和 reasoning policy；test 在 `TEST-READY` 前不可读取。
6. 同时导出 `CurCL` 与 `PrevCL + CurCL` 两个可配对视图，并验证 target 文本、label、ID、
   split 和样本顺序一一对应。上下文截断必须优先保留完整 target。
7. 保存数据卡、上游 revision、license、原始/派生 hashes、逻辑行数、过滤原因、标签分布、
   context coverage、重复统计和重建命令。

Weibo 没有官方 split；原论文若报告 5-fold cross-validation，只能作为文献参照。当前
group-disjoint held-out 结果不得与论文数值直接作百分点差值，除非另做严格匹配的复现条件。
原始文本继续留在 gitignored 数据目录；公开 Git 只保存协议、代码、哈希和聚合统计。

### Data Adoption Pass Signal

Status: `Passed`. Construction and independent verification evidence is recorded
under `EVID-033`; model training and test access remain separate later gates.

只有以下条件同时满足，Weibo 才从 provisional candidate 变为 adopted task：

- 主标签规则、排除规则和 raw-to-task 映射可由 verifier 重放。
- group、duplicate cluster 和 target/context 角色均无跨 split 泄漏。
- 两个输入视图逐条配对，且 `SufCL`、gold 字段和未来信息不进入主输入。
- train/dev/test 的类分布和 context-available coverage 可接受，少数类没有被划分算法清空。
- 数据许可、存储与公开边界已在数据卡中明确。

### Stage 2 Model-Stack Pass Signal

Status: `Passed` under `EXP-041` and `EVID-034`.

- M1 word/character TF-IDF + LinearSVC 与 M2 Chinese RoBERTa 的 train-only
  fit/update 路径通过；未报告分类性能。
- Qwen3-4B BF16 的 paired prompt、thinking on/off 和严格 JSON parser 完成 42 次
  smoke，37/42 可解析；5 个失败均为 thinking 输出达到 1024-token 上限。
- 精确 LoRA 方案在 blocks 20-35 的 112 个目标模块上完成两步更新、保存和重载，峰值
  内存 8.65 GB；本机资源门通过。
- `AUDIT-EXP-041-V1` 独立复算 16/16 项、0 mismatch。EXP-039、EXP-040 和原 verifier
  failure 均保留，不被成功重跑覆盖。
- 全程只读 train；validation/test 未访问。解析率是格式可用性，不是情绪识别准确率。

### Baseline and Model Matrix

模型扩展按信息价值而不是参数量排序：

| ID | Model/readout | Required input conditions | Purpose | Status |
| --- | --- | --- | --- | --- |
| M0 | Majority class | `CurCL` | 检查类不平衡下 Accuracy 的虚高 | 必须 |
| M1 | Word + character TF-IDF + Linear SVM 或 Logistic Regression | `CurCL`; `PrevCL + CurCL` | 可复现的传统文本下界与简单 context 对照 | 必须，分类器在 protocol 前二选一 |
| M2 | Chinese BERT/RoBERTa + softmax + CrossEntropy | 两个配对输入视图 | 同任务强 encoder baseline | 必须，精确 checkpoint 待冻结 |
| M3 | Qwen post-trained/Instruct direct generation | 2x2 四条件 | 开箱即用 LLM 的标签、格式、成本和 reasoning/context 效应 | 必须 |
| M4 | 同一 Qwen Instruct + generative LoRA | 由 dev 冻结的主输入/推理条件；必要时做 post-LoRA diagnostic | 主要 LLM system，检验任务适配收益 | EXP-047/048 dev 链已验证；EXP-049 正式 test 已验证并消费 |
| M5 | Matched Qwen Base/Instruct/LoRA hidden states + probe | 冻结行为样本和输入 | 表征相关性分析 | 可选后置 |

主 LLM 路线是**生成式单标签任务**，不是 BERT 辅助，也不是“LLM hidden state 后接一个
分类器”作为系统主结果。M2 是公平强基线；M5 的 linear probe 只回答表征可解码性，不能
代替 M3/M4 的实际系统输出，也不能和 softmax classifier 的数值混成同一模型条件。

M1/M2 的 target-only 与 context 分数来自两套 matched training runs：保持 split、seed、
训练预算、模型选择规则和评估代码一致，只改变冻结的输入视图。它们回答“模型在对应输入上
训练后能达到什么性能”，不等同于 M3 在同一冻结 checkpoint 上做的 inference-time 2x2。

Qwen 默认候选为资源可承受的 4B post-trained/Instruct 模型；精确模型名、revision、chat
template、precision 和 license 必须在 GPU preflight 后冻结。此前 GoEmotions 使用的 1.7B
只保留为历史证据，不能把跨数据集分数当作“4B 必然更好”的依据。8B、Llama、Gemma 和
full fine-tuning 不进入主矩阵，除非 4B 结果暴露出预注册的容量问题且新增实验能改变结论。

### LLM Preflight Gate

在昂贵训练前，先用 train-derived 小样本和 dev 的受限 diagnostic slice 完成 Minor
preflight；不得读取 test。通过条件至少包括：

- reasoning off/on 均能稳定输出冻结标签，strict parser 有效率达到 protocol 门槛。
- prompt 在 `CurCL` 与 `PrevCL + CurCL` 下只改变允许的输入字段，target 边界明确。
- thinking token、final-answer token 和 parser 边界可区分；无效输出和多标签输出有唯一处理。
- 最大长度、target-preserving truncation、batch、precision、显存、吞吐和预计总成本可接受。
- reasoning on/off 的 public prompt 部分、system message、label definitions 和解码参数除开关
  外保持一致；若框架不能做到等价，必须把差异写入 protocol 而不是称为单因素实验。
- 训练前使用极小 train-only subset 做 forward/backward、label mapping、loss 下降、LoRA
  参数更新和 checkpoint reload 检查，避免再次为接口或 ontology 错误付出完整训练成本。

### Context x Reasoning 2x2

M3 在同一冻结 Instruct checkpoint、同一 dev targets 和同一 final-label parser 上运行：

| Condition | Input | Reasoning mode | Primary contrast |
| --- | --- | --- | --- |
| A | `CurCL` | off | reference |
| B | `CurCL` | on | `B - A`: reasoning without context |
| C | `PrevCL + CurCL` | off | `C - A`: context without reasoning |
| D | `PrevCL + CurCL` | on | `D - C`: reasoning with context |

交互量为 `(D - C) - (B - A)`。四条件必须使用相同 label ontology、target set、模型权重、
输出 schema、max input budget 和评估代码。全量 dev 报告系统总体表现；上下文主效应只在
`PrevCL` 非空的 paired slice 上解释，同时单列首 clause 结果。

Reasoning on 允许模型先生成过程文本再给最终标签；off 要求直接给最终标签。研究不比较
推理链措辞、不拟合所谓“标准推理链”，也不把链的一致性当作主指标。过程文本默认只进入
gitignored 诊断日志，正式预测文件保留匿名 ID、最终标签、解析状态、token、延迟和必要的
hash。主解码尽量确定性；若 reasoning mode 必须采样，则预注册重复次数，并报告标签一致率、
Macro-F1 mean +/- variation 和额外成本。

若 `C - A` 或 `D - B` 显示实际上下文收益，再对同一 target 加入长度/位置匹配的 shuffled
`PrevCL`。正确前文必须优于 shuffled 前文，才能把收益主要归因于上下文语义；否则只能说
增加了输入或改变了 prompt condition。

### LoRA Training Boundary

M4 只在 M0-M3 与 2x2 dev 结果可复算后登记。它采用生成式 SFT/LoRA，训练目标是可解析的
最终单标签；不引入人工 rationale gold。训练前必须选择并冻结一种输入策略：

- **Recommended primary**：用 2x2 在 dev 选出的可部署输入与 reasoning policy 训练一个
  system adapter，回答“最佳冻结策略经任务适配后能达到什么性能”。
- **Optional matched attribution**：若论文必须判断 LoRA 后的 context effect，再训练
  target-only 与 context 两个 matched adapters，保持 seed、步数、数据量和预算一致。
  不得把单一 context-trained adapter 上的 target-only 反事实输入当成严格的训练期消融。

若 reasoning-on 在 M3 胜出，M4 启动前还必须验证训练模板、loss mask 与 thinking/final
通道的兼容性。没有人工 rationale gold 时不得默认合成推理链或把 synthetic rationale
混入主训练；若只能做 label-only SFT，则 reasoning-on 的 M3 结论与 M4 训练收益分开报告。

核心随机训练至少 3 个 seeds。LoRA 必须记录 rank、alpha、dropout、target modules、可训练
参数、optimizer、scheduler、sequence length、batch/accumulation、precision/quantization 和
checkpoint 选择。若使用 QLoRA，行为结果可以作为系统证据，但后续 hidden-state 分析必须
单独说明量化对 activation distribution 的影响。

### Evaluation

主模型选择指标为 Macro-F1。所有正式 dev/test 还需报告：

- Accuracy、macro precision/recall、Weighted-F1。
- 每类 precision、recall、F1、support 和明确方向的 confusion matrix。
- full split、context-available paired slice、first-clause slice 的分层结果。
- LLM strict-format validity、invalid/multiple-label rate、token 数、吞吐、median/tail latency
  和显存/费用。
- 对可获得可靠概率的 classifier 报告校准；生成式模型若没有可比 label probability，
  不伪造 confidence，改报解析稳定性和重复调用标签一致率。

2x2 采用以 group 为重采样单位的 paired bootstrap，避免把同组 clause 当作独立样本。
随机训练报告至少 3 seeds 的 mean +/- std，并保留逐 seed 预测。默认 Macro-F1 绝对差
小于 `0.005` 视为 practical tie；若正式 protocol 使用其他阈值，必须在结果前登记。

模型选择、prompt、few-shot examples、reasoning policy、checkpoint 和任何 threshold 只能
使用 train/dev。最终 test gate 一次性包含所有需要进入主表的冻结配置，避免看完一个模型
的 test 后再决定是否加入另一个模型。

### Error Analysis Protocol

dev 阶段先冻结抽样规则，再检查：

- `No_emotion` 与有情绪类别的双向混淆。
- `positive/negative` 与 `joy/sad/anger` 的 ontology 重叠。
- 少数类、短 clause、长 context、否定、反讽、隐含情绪和网络符号。
- A/B/C/D 中因加入正确上下文而修复、恶化或保持不变的配对样本。
- reasoning on/off 的稳定翻转、无效输出和“解释很长但最终标签不变”的成本案例。
- encoder 与 Qwen 的共享错误和各自特有错误。

定性案例只能从预先冻结的分层清单抽取，公开记录用匿名 ID 和聚合类型。test 后可以做
一次只读错误分析用于论文讨论，但不得据此改 prompt、标签、模型或再读取同一 test。

### Representation Claim Boundary

表征支线只在 M3/M4 形成稳定行为结果后启动，并优先分析一个冻结主模型，而不是同时扩展
多尺寸、多家族和多种解释方法。第一步是 matched layer-wise linear probe：

- 使用同一 Weibo split、标签、输入文本、precision、pooling 和 probe architecture。
- Base/Instruct/LoRA 比较前先验证 tokenizer、模板和 token-position alignment；无法等价时
  明确把模板差异列为混杂变量，不强行作因果归因。
- probe 训练只读 train，层/池化选择只读 dev，最终结果遵守新的 test gate；加入
  label-shuffle、长度/词汇控制或等价的泄漏控制。
- reasoning on/off 若生成了不同长度的 token trajectory，只比较预注册的对齐位置，例如
  pre-generation target representation；不把任意“最后 token”差异写成 reasoning 机制。

Layer probe 只能说明情绪或上下文信息具有线性可解码性。输入替换能支持“上下文变化导致
行为/表征变化”，但不证明模型采用人类情绪机制，也不证明生成 rationale 忠实反映内部
计算。只有 activation patching、ablation 或 steering 等内部干预和充分控制，才可能提出
更强的因果表征证据。

Sparse Autoencoder（SAE）只在 probe 找到跨 seed 稳定候选层、行为现象明确且资源预算允许
时登记。SAE 失败或不执行不影响最低毕设闭环。

### Conditional Transfer Gate

迁移训练不在 Weibo 直接基线之前发生。只有 M0-M3 和 2x2 dev 结果完成，且迁移能回答
明确问题时，才在 test 前作一次 go/no-go 决策。

优先级如下：

1. **Same-corpus auxiliary first**：将独立 ECause release 作为先行辅助任务，再回到 EClass
   目标训练。两个 TSV 已证实不能按行 join，因此只能按各自 task schema 顺序训练或多任务
   训练，不能伪造一一对应样本。
2. **Chinese ERC source second**：若同语料辅助无效且仍需验证迁移，最多选择一个有明确
   上下文和许可的中文 ERC 数据集，例如待审计的 MPDD candidate。
3. English EmotionLines/EmotionPush 不作第一迁移源，因为语言、对话体裁和标签 ontology
   同时变化，会让正负结果难以归因。

跨数据集迁移的最低对照为：

```text
T        = Weibo-only target training
S-U -> T = source utterance-only training, then Weibo target training
S-C -> T = source correct-context training, then Weibo target training
S-R -> T = source shuffled-context training, then Weibo target training
```

四条件必须使用相同 Weibo fine-tuning budget 和 test-free 模型选择。若 source/target 标签
空间不同，生成式模型使用显式 task-specific label schema；分类器必须重置 target head，
不能把不同 label IDs 当成共享语义。若 `S-C` 不优于 `S-R`、Macro-F1 增益小于 `0.005`、
收益只来自多数类，或 ontology mapping 无法辩护，则停止迁移扩展并保留负结果。

### Execution Order

```text
Stage 0  TweetEval + GoEmotions reproduction/test（completed）
         IAC2 cleaning/annotation diagnosis（closed; no more labeling）
    |
Stage 1  Register and verify Weibo task/data protocol（completed）
         ontology -> parser -> dedup -> group split -> paired views -> verifier
    |
Stage 2  Environment/model/parser/LoRA preflight（completed; train only）
    |
Stage 3  M0 majority + M1 TF-IDF + M2 Chinese encoder on dev（completed; EXP-042 Verified）
    |
Stage 4  M3 frozen Qwen context x reasoning 2x2 on dev（completed; EXP-043 Verified）
         -> context gain did not appear; shuffled-context control not triggered
    |
Stage 4.5  M4 local LoRA cost preflight（completed; EXP-044 Verified; train only）
           -> technically feasible; 2 epochs x 3 seeds ~=21.72 h with safety
    |
Stage 4.6  reasoning-on runtime-equivalence gate（completed; EXP-046 Verified; train only）
           -> freeze singleton; repeat after each adapter before dev access
    |
Stage 5  M4 generative LoRA, 3 seeds, matched singleton dev comparison
         (completed; EXP-047 matched validation Verified)
    |
Stage 6  Frozen dev error analysis and bounded ablations
         (completed; EXP-048 Verified; no new tuning or transfer triggered)
    |
Stage 7  Freeze model/prompt/parser/metrics/slices -> TEST-READY -> user approval
         (completed; frozen contract verified before test access)
    |
Stage 8  One-time held-out test for all frozen main-table configurations
         (completed; EXP-049 Verified; test consumed)
    |
Stage 9  Post-test read-only error analysis -> demo -> thesis evidence archive（next）
    |
Optional  Matched probes -> controlled intervention -> SAE
```

每个 Major 训练或评估仍需在 `experiments/` 下建立独立 protocol 和单调递增 EXP ID。
本节规定依赖和停止门，不授权读取 test 或启动训练。若 dev 错误分析导致任务、prompt 或
模型改变，必须回到对应开发阶段登记新实验；不能在 test 后继续同一主结果的开发循环。

### System Deliverable

最终 demo 接收可选的 previous local clause 和必填 target clause，输出一个冻结标签以及
可核验时的置信度/不确定性。界面应能切换 target-only 与 context 输入，并记录模型版本、
reasoning mode、解析状态和推理延迟。若展示生成 explanation，必须标记为模型输出而非
忠实内部理由，且不用于替代最终标签评估。

系统不得读取 `SufCL` 或未来回复，不把输出表述为作者真实心理诊断，也不在本阶段扩展为
社区趋势、舆情聚合或自动管理决策系统。

### Current Risks and Pending Decisions

当前风险优先级为：

1. Weibo 是微博多用户 clause 数据，不是标准论坛 thread；论文题目与外部效度必须收敛。
2. `PrevCL` 不保证是 parent，context claim 只能落在 fixed local discourse context。
3. `No_emotion` 占多数，且 emotion/sentiment/neutral ontology 混合，容易出现 Accuracy
   虚高和类别定义重叠。
4. 没有官方 split，当前 held-out group split 与原论文交叉验证数值不能直接比较。
5. EXP-043 的 332 条 first-clause prompt 哈希完全一致，但 reasoning-on 两次批处理只有
   273 个最终标签一致。EXP-046 已确认固定顺序 batch 8 可重放，而改变共同批次后最终标签
   仅 `14/16` 一致；D-C 不能全部解释为语义 context effect。Stage 5 reasoning-on 正式评估
   冻结 singleton，并要求每个 adapter 训练后、读取 dev 前重复同一 train-only replay。
6. EXP-047 已选择当前唯一通过等价性门的本机 MLX BF16 路线；seeds 42/43/44 的 2-epoch
   正式 train-only 运行分别耗时 `20,577.547 s`/`20,548.721 s`/`20,415.953 s`，峰值分别为
   `8.804 GB`/`8.804 GB`/`8.805 GB`，adapter load-forward 与两次 singleton replay 均已
   独立验证。seed 43 首次受限启动在第一个训练
   iteration 前因 Metal 不可用停止，失败记录保留，attempt 2 使用新目录完整重跑。原 2 epochs
   x 3 seeds 训练安全投影为 `21.72 h`，三次成功训练实际合计约 `17.095 h`；
   matched validation 实际四条件命令耗时 `87,122.823 s`，其中无 adapter reference 占
   `79,098.411 s`；峰值内存 `8.498 GB`。LoRA 三 seed Macro-F1 为
   `0.552028`/`0.548289`/`0.587096`，均值 `0.562471 +/- 0.021408`，相对 matched reference
   提高 `+0.228873`，但仍比 EXP-042 M2 target-only 低 `0.032454`。租 GPU 会更换训练/推理
   后端，若未来迁移仍必须追加 correction、获得私有数据传输批准并通过新的 train-only
   backend-equivalence Minor。
7. LoRA 同时把 parser-valid 从 reference 的 `90.8805%` 提高到三个 seed 的 `100%`，并把
   平均生成长度从 `525.37` tokens 降到约 `10.45` tokens。EXP-048 的 Accuracy 加性分解显示，
   116 条 reference output-failure slice 贡献 `+0.070755`，另外 1,156 条 reference 有效输出
   贡献 `+0.486111`；因此收益不只是格式恢复。LoRA 与 encoder 的 Accuracy 仅差
   `-0.013103`，但 Macro-F1 仍差 `-0.032454`，主要弱项为 sadness、neutral、anger、positive
   及 no_emotion/极性/具体情绪边界；LoRA seed 一致率也较低。以上仍只支持行为解释，不能
   解释为忠实推理或内部机制。
8. hidden-state、probe 或 SAE 只能形成表征层证据，不能回答人类情绪产生机制。

数据协议、Stage 2 模型栈、Stage 3 M0/M1/M2、Stage 4 frozen Qwen 2x2、EXP-044
本地成本门和 EXP-046 runtime-equivalence gate 已经冻结并验证。EXP-047 Stage 5
generative LoRA Major 冻结 label-only target、target-only + reasoning-on、三 seed、固定
epoch-2 checkpoint、matched singleton reference、post-adapter replay、本机 MLX 和 116 小时
资源上限。seeds 42/43/44 的 train-only、adapter load-forward、双次 singleton replay、
matched validation 与 EXP-048 dev 错误分析均已完成并通过独立 verifier。EXP-049 随后按
TEST-READY 合同一次性评估 9 个冻结单元：encoder/LoRA/matched reference test Macro-F1
分别为 `0.649621 +/- 0.007365`、`0.636612 +/- 0.021429` 和 `0.316921`。LoRA 明确改善
matched Qwen，但相对 encoder 的 `-0.013009` 差值区间跨 0。test 已消费，后续不得调参、
挑选最佳 test seed 或重跑候选；下一步仅做只读错误分析、系统演示与论文证据归档。除这些
明确 gate 外，不再恢复
GoEmotions parents、不继续 IAC2 正式标注、不执行 Hotter hydration，也不把 KOTE 加入主线。

### Review Questions Before Model Protocol Freeze

交给外部模型或导师审查时，优先要求其回答：

1. 七类 primary ontology 与 `fear`/composite 排除是否忠实于 EClass 原始研究，而非事后方便？
2. group-disjoint split、跨组去重和 target/context 角色检查是否足以控制泄漏？
3. A/B/C/D 是否真正只改变 context 和 reasoning mode；chat template 或解码是否仍有混杂？
4. “冻结模型 2x2 -> 选择可部署条件 -> generative LoRA”的顺序能否分别回答因果对照与
   最佳系统性能，而不会把二者混写？
5. same-corpus auxiliary 或跨数据集迁移是否有足够增量信息，还是应直接跳过？
6. 在不增加额外数据集和模型家族的前提下，最低闭环是否足以支撑题目中的 LLM-based
   与 forum text 两个关键词？

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
- Weibo ontology、raw-to-task parser 或 data-adoption verifier 尚未通过。
- 训练集与测试集存在同 group、重复文本、target/context 角色或标签字段泄漏。
- 简单基线尚未稳定复现。
- 只有 accuracy，或没有按类别指标。
- LLM 的模型版本、提示、成本或解析规则无法追溯。
- reasoning on/off 除开关外还存在无法控制的 prompt/parser 差异，却仍被当作单因素比较。
- 已读取 test 后仍试图用其结果改标签、prompt、checkpoint 或迁移方案。
- 新方法看似更好，但比较使用了不同数据、不同划分或不同评估脚本。
