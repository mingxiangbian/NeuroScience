# 项目证据台账：论坛文本情感识别

---
date: 2026-07-23
status: active
tags: [evidence-log, emotion-recognition, llm, application]
project: llm-forum-text-emotion-recognition
---

## Purpose

本文件是未来 CV、SOP、推荐信和项目答辩的事实来源。它记录“做了什么、由谁完成、如何验证、结果在哪里”，不记录无法核验的宣传性表述。

项目计划、正在进行的工作和已验证成果必须分开。只有带原始产物和复核方法的 `Verified` 条目，才能对外写成完成事实。

## Evidence Rules

### 最值得保留的申请证据

- 明确的研究问题及项目目标。
- 数据来源、规模、标签和合规性。
- 个人负责的具体部分。
- 采用的模型及有意义的基线。
- Macro-F1、各类别召回率等完整指标。
- 对照实验、鲁棒性测试或消融实验。
- 反讽、否定、网络用语、上下文依赖等失败案例分析。
- 可复现代码、实验配置、技术报告或演示。
- 使用 LLM 时记录模型版本、提示方式、成本、延迟及相对基线的真实收益。

录取委员会更看重“问题定义、实验、结果、反思”的完整闭环，而不是使用了多少模型。

### 应避免的问题

- 只汇报 accuracy。
- 没有基线比较。
- 数据泄漏，或训练集与测试集高度重复。
- 只调用一次 LLM API 便宣称完成 LLM 系统。
- 把计划中的功能写成已经完成。
- 为追求漂亮指标隐去失败实验。
- 在 CV 中写无法由代码、报告或导师验证的数字。
- 未处理论坛数据的隐私、授权和匿名化问题。

即使新方法没有超过基线，只要实验严谨、失败原因分析充分，仍然可以成为可信的申请项目。

## Status Vocabulary

| Status | 含义 | 可否对外写成成果 |
| --- | --- | --- |
| Planned | 仅为计划，尚未执行 | 否 |
| In Progress | 已开始，但结果尚未冻结 | 否 |
| Completed | 已产生产物，但尚未独立复核 | 只能写过程，不能写最终数字 |
| Verified | 产物、配置和复核方法齐全 | 是 |
| Rejected | 失败、无效或被证据否定 | 否，但应保留为研究反思 |

## Project Facts

| ID | Fact | Source | Status |
| --- | --- | --- | --- |
| FACT-001 | 题目为 Research and Implementation of Emotion Recognition System of Forum Text Based on LLM | [`../uestc-fyp-topics-2026-2027/topics.md`](../uestc-fyp-topics-2026-2027/topics.md) | Verified |
| FACT-002 | 项目属于 Artificial Intelligence Technology，类型为 Engineering Design | [`../uestc-fyp-topics-2026-2027/topics.md`](../uestc-fyp-topics-2026-2027/topics.md) | Verified |
| FACT-003 | 导师为王玉林，公示邮箱为 `wyl@uestc.edu.cn` | [`../uestc-fyp-topics-2026-2027/topics.md`](../uestc-fyp-topics-2026-2027/topics.md) | Verified |
| FACT-004 | 导师要求先查论文、复现代码、准备论坛文本数据并完成开题准备 | 用户转述的导师邮件；原始邮件由用户保留 | Completed |
| FACT-005 | 已建立 6 篇核心论文的本地阅读包和复现路线 | [`../../papers/llm-forum-text-emotion-recognition/reading-route.md`](../../papers/llm-forum-text-emotion-recognition/reading-route.md) | Verified |

## Evidence Register

每项可对外成果单独占一行。一个指标必须同时链接配置、日志和预测结果，不能只链接截图。

| Evidence ID | Date | Claim or result | Personal contribution | Artifact path | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EVID-001 | 2026-07-23 | 建立项目研究、证据、问题与来源记录结构 | 整理项目边界与证据规则 | `projects/llm-forum-text-emotion-recognition/` | 检查文件与交叉链接 | Completed |
| EVID-002 | 2026-07-17 | 建立 6 篇核心论文的结构化阅读包 | 论文筛选、结构化整理与复现路线设计 | `papers/llm-forum-text-emotion-recognition/` | 本地文件和阅读器可打开 | Verified |
| EVID-003 | 2026-07-29 | 使用固定 TweetEval emotion 训练集拟合 TF-IDF + Logistic Regression 基线；未执行验证集或测试集评估 | 固定配置、实现训练脚本并保存可复现元数据 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/` | 重新加载模型，核对训练文件哈希、类别和词表规模 | Completed |
| EVID-004 | 2026-07-29 | EXP-001 在固定 validation split 上得到 Macro-F1 0.493991、Accuracy 0.631016；测试集未读取 | 实现验证脚本，保存逐条预测、各类别指标和混淆矩阵 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-002-validation/` | 从保存的预测独立复算 374 条 gold label、概率和指标 | Completed |
| EVID-005 | 2026-07-29 | 在固定训练集上拟合仅将 `class_weight` 改为 `"balanced"` 的受控基线；未执行验证集或测试集评估 | 参数化训练脚本，预登记比较协议并保存模型元数据 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/` | 核对两次运行的训练哈希、词表、IDF 和非权重超参数一致 | Completed |
| EVID-006 | 2026-07-29 | Balanced 变体在固定 validation split 上得到 Macro-F1 0.565981、Accuracy 0.620321；相对未加权版本 Macro-F1 提高 0.071990 | 使用同一验证协议评估受控变体并比较类别 recall | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-004-balanced-validation/` | 从逐条预测独立复算指标，并核对两次 validation 文件哈希一致 | Completed |
| EVID-007 | 2026-07-29 | Word + character n-gram TF-IDF + Linear SVM 在固定 validation split 上得到 Macro-F1 0.611866、Accuracy 0.671123；相对 EXP-004 分别提高 0.045885 和 0.050802 | 预登记 paper-aligned 组合基线，实现训练、decision score 保存、完整评估和独立复算 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-005-word-char-linear-svm/` | 独立核对 374 条 gold/prediction、输入与产物哈希、各类别指标和混淆矩阵；test 未读取 | Completed |
| EVID-008 | 2026-07-29 | 训练集内 5 折选择并冻结的 Linear SVM 在一次 validation 确认中得到 Macro-F1 0.622678、Accuracy 0.676471；相对 EXP-005 分别提高 0.010812 和 0.005348 | 设计不读取 validation/test 的 30 候选网格，冻结配置哈希，再执行一次 Major validation 评估 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-007-tuned-linear-svm/` | 独立复算 374 条预测、完整指标、混淆矩阵、输入与产物哈希；EXP-006 记录仅访问 train，test 未读取 | Completed |
| EVID-009 | 2026-07-30 | EXP-011 RoBERTa-base 三随机种子微调在固定 validation split 上得到 Macro-F1 0.732804 +/- 0.005007、Accuracy 0.792335 +/- 0.004084；相对 EXP-007 平均 Macro-F1 提高 0.110126 | 预登记 Major 协议，固定模型 revision、环境、三种子和 checkpoint 选择规则；实现 MPS 训练、完整产物和独立复算 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/runs/exp-011-roberta-base-finetuning/` | `verification.json` 重算 1,122 条 validation 预测、三种子指标及输入、模型和产物哈希；test 未读取 | Completed |
| EVID-010 | 2026-07-30 | EXP-014 在冻结通用 RoBERTa-base 配置中加入 0.05 label smoothing 后，validation Macro-F1 为 0.740219 +/- 0.005381，较 EXP-011 提高 0.007415 | 先用 EXP-012/013 仅在训练集内筛选预处理、论文超参数和正则化，再预登记并执行三 seed validation 确认 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/runs/exp-014-optimized-roberta-validation/` | `verification.json` 独立复算 1,122 条 validation 预测、三 seed 指标、混淆矩阵、输入/模型/产物哈希；test 未读取 | Completed |
| EVID-011 | 2026-07-30 | EXP-015 Twitter 域预训练 RoBERTa-base 在固定下游协议上得到 validation Macro-F1 0.761755 +/- 0.010579、Accuracy 0.829768 +/- 0.012350；较 EXP-014 提高 0.021536，3/3 配对 seed 提高 | 固定数据、预处理、超参数和评估，仅替换 base encoder；记录逐类收益与 optimism 退化 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/runs/exp-015-twitter-roberta-base-validation/` | `verification.json` 独立复算 1,122 条 validation 预测、三 seed 指标、混淆矩阵、输入/模型/产物哈希；test 未读取 | Completed |
| EVID-012 | 2026-07-30 | EXP-016 一次性正式 test gate 中，EXP-015 获得 Macro-F1 0.809973 +/- 0.007038；相对 EXP-014 提高 0.017328，3/3 seed 提高；label smoothing 相对 EXP-011 未形成 test 改善 | 冻结十个评估单元及其哈希，实现统一离线推理、完整指标、配对比较、外部参照和独立复算 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/test-gate/` | `verification.json` 独立复算 14,210 条预测、类别指标、混淆矩阵、配对差值和产物哈希；归档提交 `f061ec9` | Verified |

## Data Register

在数据采集或下载前填写。未知项保持 `TBD`，不得用估计值代替。

| Field | Current value | Evidence path | Status |
| --- | --- | --- | --- |
| Target forum or domain | TBD | TBD | Planned |
| Language | TBD | TBD | Planned |
| Collection method | TBD | TBD | Planned |
| Terms or authorization basis | TBD | TBD | Planned |
| Raw sample count | TBD | TBD | Planned |
| Deduplicated sample count | TBD | TBD | Planned |
| Label set and definitions | TBD | TBD | Planned |
| Number of annotators | TBD | TBD | Planned |
| Inter-annotator agreement | TBD | TBD | Planned |
| Anonymization procedure | TBD | TBD | Planned |
| Train/dev/test split rule | 按 `thread_id` 划分是当前方案，尚待数据结构确认 | TBD | Planned |
| Redistribution boundary | TBD | TBD | Planned |

每次冻结数据版本时记录：

- 数据版本号与生成日期。
- 原始、清洗、去重和各划分样本数。
- 每类支持数及长尾分布。
- 去重方法、泄漏检查和异常样本处理。
- 可公开字段、受限字段和删除流程。

## Experiment Register

每次运行使用一个独立实验编号，并保存以下信息：

```text
Experiment ID:
Date:
Research question:
Status:
Code commit:
Dataset version and split:
Model and checkpoint:
Environment:
Random seed:
Hyperparameters:
Primary metric:
Per-class metrics:
Cost and latency:
Artifact paths:
Result:
Failure or caveat:
Reproduction command:
Verified by:
```

至少保留：

- 训练配置、命令、日志和 checkpoint 说明。
- 测试集预测文件，而非只有汇总分数。
- Macro-F1、每类 precision/recall/F1、support 和混淆矩阵。
- 多随机种子结果或重复调用波动。
- 与同一数据版本上基线的差值。

### EXP-001: TF-IDF + Logistic Regression Train Only

```text
Experiment ID: EXP-001
Date: 2026-07-29
Research question: 固定 TweetEval emotion 训练集能否完整拟合首个非神经网络基线并保存可复现产物？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official train split；3,257 samples
Model and checkpoint: word TF-IDF (1,2)-grams + Logistic Regression
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64
Random seed: 42
Hyperparameters: min_df=2；sublinear_tf=true；C=1.0；solver=lbfgs；max_iter=1000；class_weight=None
Primary metric: N/A；本阶段只训练，不评估
Per-class metrics: N/A
Cost and latency: local CPU；fit_seconds=0.173760
Artifact paths: experiments/tweeteval-emotion/tfidf-logreg/runs/exp-001-train-only/
Result: 模型成功拟合并可重新加载；9,886 TF-IDF features；classifier coefficient shape 4 x 9,886
Failure or caveat: 尚未读取 validation/test，不能报告或比较模型性能
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/train.py
Verified by: 待验证集评估与独立复核
```

### EXP-002: Fixed Validation Evaluation

```text
Experiment ID: EXP-002
Date: 2026-07-29
Research question: 首个固定 TF-IDF + Logistic Regression 基线在 TweetEval emotion validation split 上的类别平衡表现如何？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official validation split；374 samples
Model and checkpoint: EXP-001 model SHA-256 4e7a34db3599d3187a3f09310045edabb926ce156c5b6084633d41f9c8905e72
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64
Random seed: 42，继承自 EXP-001
Hyperparameters: 继承 EXP-001；本阶段未调参
Primary metric: validation Macro-F1=0.4939908442494706
Per-class metrics: anger F1=0.723192；joy F1=0.536913；optimism F1=0.129032；sadness F1=0.586826
Cost and latency: local CPU；evaluation_seconds=0.013783
Artifact paths: experiments/tweeteval-emotion/tfidf-logreg/runs/exp-002-validation/
Result: Accuracy=0.631016；optimism recall=0.071429；大量 joy、optimism 和 sadness 样本被预测为 anger
Failure or caveat: 这是模型选择阶段的 validation 结果，不是 test 结果；少数类表现很弱，不能只引用 accuracy
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/validate.py
Verified by: 已从 predictions.csv 独立复算 gold labels、概率和完整指标，代码已归档；未做第二环境复现，因此保留 Completed
```

### EXP-003: Balanced Controlled Variant Train Only

```text
Experiment ID: EXP-003
Date: 2026-07-29
Research question: 仅提高少数类训练损失权重，能否改善首个基线的类别平衡表现？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official train split；3,257 samples
Model and checkpoint: word TF-IDF (1,2)-grams + Logistic Regression；class_weight=balanced
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64
Random seed: 42
Hyperparameters: 与 EXP-001 相同，仅 class_weight 从 None 改为 balanced
Primary metric: N/A；本阶段只训练，不评估
Per-class metrics: N/A
Cost and latency: local CPU；fit_seconds=0.150382
Artifact paths: experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/
Result: 模型成功拟合并可重新加载；9,886 TF-IDF features；classifier coefficient shape 4 x 9,886
Failure or caveat: 尚未读取 validation/test，不能判断类别加权是否有效
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/train.py --class-weight balanced --output-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only
Verified by: 已核对 EXP-001 与 EXP-003 的训练文件哈希、样本数、词表、IDF 和全部非权重分类器设置一致
```

### EXP-004: Balanced Fixed Validation Evaluation

```text
Experiment ID: EXP-004
Date: 2026-07-29
Research question: 仅改变 class_weight 后，balanced 变体是否按预登记标准改善 validation Macro-F1 和少数类 recall？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official validation split；374 samples
Model and checkpoint: EXP-003 model SHA-256 110d42029c387bba87311b7fc2c3d39121d37f61b3cf0af6bd8168a363005372
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64
Random seed: 42，继承自 EXP-003
Hyperparameters: 继承 EXP-003；本阶段未调参
Primary metric: validation Macro-F1=0.565980574363182；较 EXP-002 +0.071989730114
Per-class metrics: anger F1=0.719243；joy F1=0.603352；optimism F1=0.361446；sadness F1=0.579882
Cost and latency: local CPU；evaluation_seconds=0.011521
Artifact paths: experiments/tweeteval-emotion/tfidf-logreg/runs/exp-004-balanced-validation/
Result: Accuracy=0.620321；joy recall=0.556701；optimism recall=0.535714；按预登记 Macro-F1 选择 balanced 版本
Failure or caveat: Accuracy 较 EXP-002 下降 0.010695；anger recall 下降 0.193750；optimism precision 仅 0.272727，存在明显 false positives；这是 validation 而非 test
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/validate.py --model projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/model.joblib --train-metadata projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/run.json --output-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-004-balanced-validation
Verified by: 已从 predictions.csv 独立复算 374 条 gold labels、概率、Macro-F1、Accuracy 和混淆矩阵，代码已归档；未做第二环境复现，因此保留 Completed
```

### EXP-005: Word + Character TF-IDF with Linear SVM

```text
Experiment ID: EXP-005
Tier: Major
RQ ID: RQ-B1
Date: 2026-07-29
Research question: 在同一 TweetEval emotion train/validation 划分上，word + character n-gram TF-IDF + Linear SVM 是否比当前 balanced word TF-IDF + Logistic Regression 基线更强？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907；运行时仓库为 dirty state
Dataset version and split: TweetEval upstream 4fbd22c；official train 3,257 samples + validation 374 samples
Model and checkpoint: word (1,2) + character (3,5) TF-IDF；LinearSVC C=1.0；70,639 combined features
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64；local CPU
Random seed: 42；该传统模型在冻结配置下只运行一次
Primary metric: validation Macro-F1=0.6118659622；较 EXP-004 +0.0458853878
Secondary metrics: Accuracy=0.6711229947，较 EXP-004 +0.0508021390；weighted F1=0.6640249255
Per-class F1: anger=0.741379；joy=0.624277；optimism=0.444444；sadness=0.637363
Cost and latency: API cost USD 0；fit_seconds=0.512108；evaluation_seconds=0.052692
Artifact paths: experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-005-word-char-linear-svm/
Result: 通过预登记的 +0.005 practical-improvement threshold，成为当前更强的传统 validation baseline
Failure or caveat: optimism recall 从 EXP-004 的 0.535714 降为 0.357143；本地 Macro-F1 比论文 SVM validation 0.638 低 0.026134；官方完整超参数未披露，因此不是严格复现；test 未读取
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/run_experiment.py
Verification command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/verify.py
Verified by: verification.json 已独立复算输入哈希、374 条预测、完整指标和混淆矩阵；代码与匿名产物已归档
Thesis destination: 结果章节的传统基线比较表，编号待定
```

### EXP-007: Train-CV-Selected Linear SVM

```text
Experiment ID: EXP-007
Tier: Major
RQ ID: RQ-B1
Date: 2026-07-29
Research question: 不读取 validation 进行选择的训练集 5 折最优配置，能否在一次冻结 validation 确认中超过 EXP-005？
Status: Completed
Code archive commit: f061ec9c91e925236d6d481c66efc9dcbbfce907；运行时仓库为 dirty state
Dataset version and split: EXP-006 仅使用 TweetEval official train 3,257 samples 进行 5-fold CV；EXP-007 使用 official train 3,257 + validation 374 samples
Model and checkpoint: word (1,2) + character (3,6) TF-IDF；LinearSVC C=0.25，class_weight=balanced；111,712 combined features
Selection: EXP-006 在 30 个候选、150 次 train-only CV fits 中按 mean Macro-F1 选择；冻结配置 SHA-256 8ddb3e3a479ebb53de8cee25401ff792acff770a6e5a4cc8823352f03f4f475e
Environment: Python 3.10.20；scikit-learn 1.7.2；macOS arm64；local CPU
Random seed: 42；EXP-007 冻结配置只运行一次
Primary metric: validation Macro-F1=0.6226779061；较 EXP-005 +0.0108119439
Secondary metrics: Accuracy=0.6764705882，较 EXP-005 +0.0053475936；weighted F1=0.6734402704
Train diagnostics: Accuracy=0.9858765735；Macro-F1=0.9847133788
Per-class F1: anger=0.759644；joy=0.636872；optimism=0.472727；sadness=0.621469
Cost and latency: API cost USD 0；EXP-006 total_seconds=101.625621；EXP-007 fit_seconds=0.563269，evaluation_seconds=0.069310
Artifact paths: experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-006-train-cv-tuning/；experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-007-tuned-linear-svm/
Result: 通过预登记的 +0.005 Macro-F1 practical-improvement threshold，成为当前最强的本地传统 validation baseline
Failure or caveat: sadness F1 较 EXP-005 下降 0.015894；前四名 train-CV Macro-F1 差值不足 0.005，不能断言某个 character range 独占优势；同时改变 C、class_weight 与 character n-gram range，不能把收益归因于单一超参数；train-CV 0.670851 高于 validation 0.622678，存在选择乐观偏差或 split variance；validation 已参与开发，不能作为最终泛化估计；test 未读取
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/run_tuned_validation.py
Verification command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/verify.py --run-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-007-tuned-linear-svm --expected-experiment-id EXP-007
Verified by: verification.json 已独立复算输入哈希、374 条预测、完整指标和混淆矩阵；代码与匿名产物已归档
Thesis destination: 结果章节的传统基线调优与模型比较表，编号待定
```

### EXP-009: Preserved Logger Failure

```text
Experiment ID: EXP-009
Tier: Major
RQ ID: RQ-B2
Date: 2026-07-30
Status: Rejected
Stage reached: environment、config、model manifest 与 comparison gate 通过；读取 train 3,257 + validation 374 后，在加载 seed-42 模型时停止
Result: 无模型性能结果；未完成 optimization step，未生成 validation prediction，test 未读取
Failure or caveat: 终端 Tee 缺少 isatty()，Transformers 加载报告触发 AttributeError
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-009-roberta-base-finetuning/
Preserved source SHA-256: 31adaeca66f8634c234299bfc269529298f44bb695437b07651fa3a9a8415fe8
Verified by: failure-note.md、run.json、stdout.log 与失败源码快照互相对应
```

### EXP-010: Preserved Restricted-Process Failure

```text
Experiment ID: EXP-010
Tier: Major
RQ ID: RQ-B2
Date: 2026-07-30
Status: Rejected
Stage reached: pre-data environment gate
Result: 无模型性能结果；未打开项目数据，未完成 optimization step，未生成 validation prediction，test 未读取
Failure or caveat: 受限执行进程未暴露 Apple MPS，环境门以 RuntimeError 停止
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-010-roberta-base-finetuning/
Preserved source SHA-256: f5ae5859fa56c0c21af5370b629670bd6418ae6d32f4db8f699bec5969fd89fd
Verified by: failure-note.md、run.json、stdout.log 与失败源码快照互相对应
```

### EXP-011: RoBERTa-Base Three-Seed Fine-Tuning

```text
Experiment ID: EXP-011
Tier: Major
RQ ID: RQ-B2
Date: 2026-07-30
Research question: 在同一 TweetEval emotion train/validation 划分上，标准微调的 RoBERTa-base 是否稳定超过 EXP-007？
Status: Completed；独立 verification status=Verified；代码与匿名产物已归档
Code commit: 运行时 commit c92b92db18dfe8ccd5368774532bb22019f7889a（dirty state）；归档 commit f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official train 3,257 + validation 374；明确允许 train/validation；test 未读取
Model and checkpoint: FacebookAI/roberta-base revision e2da8e2f811d1448a5b465c236feacd80ffbac7b；124,648,708 parameters；每个 seed 保留一个 validation Macro-F1 最佳 checkpoint
Environment: Python 3.10.20；PyTorch 2.9.1；Transformers 5.8.0；macOS arm64；Apple MPS；70-package isolated runtime lock
Random seeds: 42、43、44
Hyperparameters: max_length=128；epochs=5；train/eval batch=16/32；AdamW；learning_rate=2e-5；weight_decay=0.01；linear scheduler；warmup_ratio=0.1；max_grad_norm=1.0；无 class weights
Selection: 每个 seed 按 validation Macro-F1 选择最佳 epoch；seed 42/43/44 分别选择 epoch 4/3/5；三者均保留为未来 test 候选
Primary metric: validation Macro-F1=0.7328038562 +/- 0.0050069241
Secondary metrics: Accuracy=0.7923351159 +/- 0.0040842921；macro precision=0.7320299191 +/- 0.0119709033；macro recall=0.7392844043 +/- 0.0010029791；weighted F1=0.7946161973 +/- 0.0040863394
Per-class F1: anger=0.880407 +/- 0.005369；joy=0.765547 +/- 0.001818；optimism=0.529918 +/- 0.045122；sadness=0.755343 +/- 0.020474
Per-class recall: anger=0.866667 +/- 0.009547；joy=0.718213 +/- 0.015748；optimism=0.559524 +/- 0.020620；sadness=0.812734 +/- 0.023390
Train diagnostics: Macro-F1=0.956154 +/- 0.014429；Accuracy=0.961621 +/- 0.013520
Cost and latency: API cost USD 0；local MPS total_seconds=1,391.291949；每个 seed 训练约 439-442 seconds；本地 run 目录约 1.4 GiB
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-011-roberta-base-finetuning/
Result: 三个 seed 均超过 EXP-007；平均 Macro-F1 delta=+0.1101259501，通过预登记 +0.005 practical-improvement threshold
Failure or caveat: 结果来自开发用 validation，不是 test；不构成官方 benchmark 或统计显著性声明；train-validation gap 明显；optimism 仍是最弱且 seed variation 最大的类别；尚未完成冻结抽样的错误分析
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/train_finetune.py
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/verify_finetune.py
Verified by: verification.json 独立复算三组共 1,122 条预测、全部汇总指标、混淆矩阵、输入/模型/产物哈希和 split discipline
Target figure/table: 编码器与传统基线比较表；三 seed learning curves；类级 F1 图
Thesis destination: 方法章节的微调设置；结果章节的编码器基线与类别表现；附录的复现配置、哈希和失败运行
```

### EXP-012 and EXP-013: Train-Only Configuration Screening

```text
Experiment IDs: EXP-012、EXP-013
Tier: Minor
RQ ID: RQ-B2
Date: 2026-07-30
Status: Completed
Dataset version and split: TweetEval upstream 4fbd22c；只读取 official train 3,257 samples；按 random_state=20260730 分层切分 inner train 2,768 + inner validation 489；official validation/test 均未读取
Model and checkpoint: FacebookAI/roberta-base revision e2da8e2f811d1448a5b465c236feacd80ffbac7b；筛选 checkpoint 均不保留
Random seeds: 第一轮 seed 42；入围候选再使用 seeds 43、44
EXP-012 factors: 原始文本或 mention/URL 归一化；当前训练设置或 CardiffNLP 论文超参数组合
EXP-012 result: 当前训练设置 + 原始文本按登记规则胜出，inner-validation Macro-F1=0.792437 +/- 0.013076；名义归一化版本为 0.781106 +/- 0.014348，但归一化规则 changed_rows=0，不能把分差归因于预处理；论文超参数原始文本版本为 0.731747 +/- 0.034817
EXP-013 factors: weight decay 0.05、classifier dropout 0.2、label smoothing 0.05、inverse-sqrt class weights；均与当前设置做单因素比较
EXP-013 result: label smoothing 0.05 胜出，inner-validation Macro-F1=0.795601 +/- 0.003187，较 control +0.009129，3/3 配对 seed 提高；weight decay 0.05 为 0.789304 +/- 0.008837
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-012-train-only-screen/；experiments/tweeteval-emotion/roberta-base/runs/exp-013-regularization-screen/
Failure or caveat: 这些分数来自 official train 内部切分，只用于选择 EXP-014 配置，不是可与 EXP-011 直接比较的 validation 结果；归一化候选没有实际改变文本，不能形成预处理效果结论；Apple MPS 的同名 seed 重跑仍有约 0.005 波动，应保留为执行限制
Verified by: run.json 记录 split access、数据哈希、每个候选的逐条预测和选择规则；test_split_accessed=false
```

### EXP-014: Optimized Generic RoBERTa Validation

```text
Experiment ID: EXP-014
Tier: Major
RQ ID: RQ-B2
Date: 2026-07-30
Research question: 经 train-only 筛选选出的单因素正则化，能否在固定 official validation 上稳定改善 EXP-011？
Status: Completed；独立 verification status=Verified；代码与匿名产物已归档
Code commit: 运行时 commit c92b92db18dfe8ccd5368774532bb22019f7889a（dirty state）；归档 commit f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official train 3,257 + validation 374；test 未读取
Model and checkpoint: FacebookAI/roberta-base revision e2da8e2f811d1448a5b465c236feacd80ffbac7b；每个 seed 保留一个 validation Macro-F1 最佳 checkpoint
Environment: Python 3.10.20；PyTorch 2.9.1；Transformers 5.8.0；macOS arm64；Apple MPS
Random seeds: 42、43、44
Hyperparameters: 与 EXP-011 相同，仅增加 label_smoothing_factor=0.05；原始文本；max_length=128；epochs=5；train/eval batch=16/32；learning_rate=2e-5；weight_decay=0.01
Selection: 每个 seed 按 validation Macro-F1 选择最佳 epoch；seed 42/43/44 分别选择 epoch 3/4/5；不使用 test 选 seed
Primary metric: validation Macro-F1=0.7402186466 +/- 0.0053806830
Secondary metrics: Accuracy=0.7967914439 +/- 0.0026737968；macro precision=0.7473693113 +/- 0.0098678431；macro recall=0.7386609832 +/- 0.0178301512；weighted F1=0.7965506931 +/- 0.0058801497
Per-class F1: anger=0.874853 +/- 0.014608；joy=0.780481 +/- 0.009400；optimism=0.556824 +/- 0.014889；sadness=0.748717 +/- 0.007374
Train diagnostics: mean Macro-F1=0.955639；mean Accuracy=0.961007
Cost and latency: API cost USD 0；local MPS total_seconds=1,428.663726；retained checkpoints=3
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-014-optimized-roberta-validation/
Result: 相对 EXP-011 平均 Macro-F1 delta=+0.0074147904，通过 +0.005 practical-improvement threshold；seed 42/43/44 配对 delta 分别为 +0.011267、-0.004348、+0.015325，其中 seed 43 属于 practical tie
Failure or caveat: 收益幅度较小，只有 2/3 seed 明确提高；这是 validation 开发结果而非 test；train-validation gap 仍明显；不能将收益外推为统计显著或官方 benchmark 提升
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/controlled_runner.py --config projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/configs/exp-014-optimized-roberta-validation.json --output-dir <new-output-dir>
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/verify_controlled.py --run-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/runs/exp-014-optimized-roberta-validation
Verified by: verification.json 独立复算三组共 1,122 条 prediction、概率、完整指标、混淆矩阵、checkpoint、输入/模型/产物哈希和 split discipline
Target figure/table: 通用 RoBERTa 调优前后比较表；三 seed learning curves；类级 F1 图
Thesis destination: 方法章节的 train-only 配置选择；结果章节的正则化对照；附录的配置、哈希和运行命令
```

### EXP-015: Twitter-Domain RoBERTa Validation

```text
Experiment ID: EXP-015
Tier: Major
RQ ID: RQ-B3
Date: 2026-07-30
Research question: 在数据、预处理、训练与评估完全相同的条件下，Twitter 域预训练 base encoder 是否优于通用 RoBERTa-base？
Status: Completed；独立 verification status=Verified；代码与匿名产物已归档
Code commit: 运行时 commit c92b92db18dfe8ccd5368774532bb22019f7889a（dirty state）；归档 commit f061ec9c91e925236d6d481c66efc9dcbbfce907
Dataset version and split: TweetEval upstream 4fbd22c；official train 3,257 + validation 374；test 未读取
Model and checkpoint: cardiffnlp/twitter-roberta-base revision cbb417e9647b51504caf68cbe1af6bbf56da06b7；基础 masked-language model，不是 emotion fine-tuned checkpoint；每个 seed 保留一个最佳 checkpoint
Environment: Python 3.10.20；PyTorch 2.9.1；Transformers 5.8.0；macOS arm64；Apple MPS
Random seeds: 42、43、44
Hyperparameters: 与 EXP-014 完全相同；原始文本；label_smoothing_factor=0.05；max_length=128；epochs=5；train/eval batch=16/32；learning_rate=2e-5；weight_decay=0.01
Selection: 每个 seed 按 validation Macro-F1 选择最佳 epoch；seed 42/43/44 分别选择 epoch 3/5/3；不使用 test 选 seed
Primary metric: validation Macro-F1=0.7617550811 +/- 0.0105789631
Secondary metrics: Accuracy=0.8297682709 +/- 0.0123497384；macro precision=0.7762391373 +/- 0.0050814593；macro recall=0.7524307164 +/- 0.0184959562；weighted F1=0.8271186807 +/- 0.0146006398
Per-class F1: anger=0.891352 +/- 0.010946；joy=0.837945 +/- 0.016770；optimism=0.521836 +/- 0.014871；sadness=0.795888 +/- 0.030733
Train diagnostics: mean Macro-F1=0.952836；mean Accuracy=0.960291
Cost and latency: API cost USD 0；local MPS total_seconds=1,419.383575；retained checkpoints=3
Artifact paths: experiments/tweeteval-emotion/roberta-base/runs/exp-015-twitter-roberta-base-validation/
Result: 相对 EXP-014 平均 Macro-F1 delta=+0.0215364344，3/3 配对 seed 均提高；seed 42/43/44 delta 分别为 +0.023810、+0.035437、+0.005362
Class-level result: anger、joy、sadness F1 分别提高 0.016499、0.057464、0.047171；optimism F1 下降 0.034988。整体域预训练收益不能解释为所有情绪类别均受益
Failure or caveat: optimism 仍是最弱类别且相对通用 encoder 退化；validation 已参与模型开发，不能作为最终泛化估计；域预训练只证明与当前数据分布匹配相关，不能单独建立因果机制解释
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/controlled_runner.py --config projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/configs/exp-015-twitter-roberta-base-validation.json --output-dir <new-output-dir>
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/verify_controlled.py --run-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/runs/exp-015-twitter-roberta-base-validation
Verified by: verification.json 独立复算三组共 1,122 条 prediction、概率、完整指标、混淆矩阵、checkpoint、输入/模型/产物哈希和 split discipline
Target figure/table: 通用与 Twitter 域 encoder 的配对比较表；逐类 F1 差值图；optimism 错误分析表
Thesis destination: 方法章节的预训练域控制变量；结果章节的整体与逐类比较；讨论章节的 optimism 反例
```

### EXP-016: Frozen Formal Test Gate

```text
Experiment ID: EXP-016
Tier: Major
RQ IDs: RQ-B1、RQ-B2、RQ-B3
Date: 2026-07-30
Research questions: 冻结的传统基线、通用 RoBERTa、label-smoothing 变体与 Twitter 域 RoBERTa 在未用于选择的 official test 上表现如何？validation 中的正则化和域预训练收益能否泛化？
Status: Frozen and Verified
Code commit: 运行时 commit c92b92db18dfe8ccd5368774532bb22019f7889a（dirty state）；代码、匿名结果和验证记录归档于 f061ec9c91e925236d6d481c66efc9dcbbfce907
Registration: 用户明确批准后，先冻结 10 个评估单元、输入/模型/checkpoint 哈希、主辅指标、3-seed 汇总和配对比较；禁止重训、ensemble、test 选 seed 与结果后调参。用户于 2026-07-30 查看本地结果和官方参照后确认冻结；此后 TweetEval test 只用于描述性错误分析，不再用于开发决策
Dataset version and split: TweetEval upstream 4fbd22c；official test 1,421 samples；class support anger=558、joy=358、optimism=123、sadness=382；EXP-016 只读取 test
Frozen conditions: EXP-007 一个 fitted Linear SVM；EXP-011、EXP-014、EXP-015 各三个由 validation 预先选定的 seed 42/43/44 checkpoint
Environment: Python 3.10.20；scikit-learn 1.7.2；PyTorch 2.9.1；Transformers 5.8.0；macOS arm64；Linear SVM 使用 CPU，神经模型使用 Apple MPS；offline inference
Primary metric: test Macro-F1；EXP-007=0.6469979241；EXP-011=0.7957606214 +/- 0.0032980313；EXP-014=0.7926449006 +/- 0.0036583360；EXP-015=0.8099731965 +/- 0.0070382781
Secondary metrics: test Accuracy；EXP-007=0.7009148487；EXP-011=0.8198451795 +/- 0.0032248949；EXP-014=0.8207834858 +/- 0.0046856637；EXP-015=0.8400187661 +/- 0.0081259714
Weighted F1: EXP-007=0.6953830808；EXP-011=0.8201706268 +/- 0.0029738220；EXP-014=0.8200976195 +/- 0.0031209327；EXP-015=0.8388282546 +/- 0.0078768613
EXP-014 versus EXP-011: paired test Macro-F1 mean delta=-0.0031157208；seed 42/43/44 deltas=+0.001324、-0.001502、-0.009169；低于 0.005 practical threshold，且 2/3 seed 为负
EXP-015 versus EXP-014: paired test Macro-F1 mean delta=+0.0173282959；seed 42/43/44 deltas=+0.024422、+0.012330、+0.015233；超过 0.005 practical threshold，且 3/3 seed 为正
EXP-015 per-class F1: anger=0.873872 +/- 0.004904；joy=0.849487 +/- 0.012695；optimism=0.691421 +/- 0.003334；sadness=0.825112 +/- 0.012049
EXP-015 versus EXP-014 per-class F1 delta: anger=+0.014219；joy=+0.019390；optimism=+0.007331；sadness=+0.028374
External reference: pinned upstream README reports SVM=0.647、RoBERTa-Base=0.761、RoBERTa-Twitter=0.720、RoBERTa-Retrained=0.785；upstream bundled emotion predictions（SHA-256 16c6cf2b1c678bc739a738aa565e1f1bfb67e365cfc06fb413bfda9ddbaf88a0）经 upstream evaluation script（SHA-256 86c824e466ffba0cd407655fbbda759c6a9c09e541be4bfaaf547df8255d2793）评估为 0.798272。外部配置与本地实现不完全相同，单独列示
Cost and latency: API cost USD 0；完整 gate wall_time_seconds=113.288264；每个 neural checkpoint 推理约 11.2-11.8 seconds
Artifact paths: experiments/tweeteval-emotion/test-gate/configs/exp-016-frozen-test.json；experiments/tweeteval-emotion/test-gate/protocols/exp-016-frozen-test.md；experiments/tweeteval-emotion/test-gate/runs/exp-016-frozen-test/
Result: EXP-015 是冻结 test 上表现最强的本地条件，比 EXP-007 高 0.162975 Macro-F1；Twitter 域预训练相对 EXP-014 的收益在 test 上保持。label smoothing 的小幅 validation 收益没有泛化，不能再表述为已证明的改进
Failure or caveat: optimism 仍是最弱类别；其 validation 退化在 test 上反转为小幅提高，说明类别级结论受 split 影响；3 seeds 只量化训练波动，不构成充分统计显著性；上游 leaderboard 不是完全同配置对照；EXP-015 继承了 EXP-014 的 label smoothing，因此 EXP-015/014 只隔离 base encoder，不能回答 Twitter 模型去掉 label smoothing 是否更好；TweetEval test 已被正式消费，此后任何同 test 开发或新增模型评估必须标记 post-test，不能替代 EXP-016
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/test-gate/evaluate_frozen_test.py（正式 gate 已完成，不得再次执行）
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/test-gate/verify_frozen_test.py
Verified by: verification.json 从 14,210 条模型-样本预测记录独立复算完整指标、类别结果、混淆矩阵、3-seed 汇总、配对差值、排名、gold row order 和所有产物哈希
Target figure/table: 四条件正式 test 主结果表；label smoothing 与域预训练配对差值表；逐类 F1 图
Thesis destination: 方法章节的 test gate 与选择纪律；结果章节的主模型比较和消融；讨论章节的 validation/test 不一致、optimism 弱项与外部 benchmark 边界
```

## LLM Run Register

每种 LLM 配置都应视为一个可版本化实验：

```text
Provider and exact model version:
Access date:
Prompt template version:
System and user prompt:
Few-shot selection rule:
Decoding parameters:
Output schema and parser:
Retry and invalid-output policy:
Input and output token count:
Estimated or billed cost:
Median and tail latency:
Data handling and retention setting:
Baseline used for comparison:
Measured gain or loss:
```

“使用了某模型”不是结果。只有相对固定基线的可复核收益、代价和失败边界才构成证据。

## Controls, Ablations, and Robustness

| Test ID | Question | Control | Treatment | Metric | Artifact | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CTRL-001 | 回复上下文是否有效 | 无上下文 | 父回复或完整线程 | Macro-F1、上下文依赖子集 F1 | TBD | Planned |
| CTRL-002 | 检索示例是否有效 | 随机 few-shot | 语义检索 few-shot | Macro-F1、成本、延迟 | TBD | Planned |
| CTRL-003 | 领域适配是否有效 | 无微调 | 领域 fine-tuning 或 LoRA | Macro-F1、per-class recall | TBD | Planned |
| CTRL-004 | 预训练语料域匹配是否有效 | `FacebookAI/roberta-base` | `cardiffnlp/twitter-roberta-base` | Macro-F1、per-class F1 | EXP-014、EXP-015、EXP-016 | Completed and test-verified |
| ROB-001 | 模型是否依赖表面形式 | 原文本 | 否定、拼写、网络用语等受控扰动 | 性能下降幅度 | TBD | Planned |

## Failure Case Register

失败案例不能只挑有趣样本，应按预先定义的类型统计：

| Case ID | Type | Gold label | Prediction | Context used | Likely cause | Evidence path | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TBD | sarcasm / negation / slang / context / ambiguity / minority class | TBD | TBD | TBD | TBD | TBD | Planned |

每类至少记录代表性真阳性、假阳性和假阴性，并区分：

- 数据或标注问题。
- 模型能力问题。
- 上下文缺失。
- 提示或输出解析问题。
- 类别定义本身不稳定。

## Reproducibility and Deliverables

| Deliverable | Required evidence | Path | Status |
| --- | --- | --- | --- |
| Data card | 来源、许可、字段、规模、标签、匿名化、划分 | TBD | Planned |
| Baseline reproduction | 环境、命令、配置、日志、预测、指标 | `experiments/tweeteval-emotion/tfidf-logreg/`；`experiments/tweeteval-emotion/tfidf-linear-svm/`；`experiments/tweeteval-emotion/roberta-base/`；`experiments/tweeteval-emotion/test-gate/` | TweetEval Complete; forum pending |
| LLM comparison | 模型版本、提示、解析、成本、延迟、对照 | TBD | Planned |
| Robustness or ablation report | 预设问题、控制变量、完整结果 | TBD | Planned |
| Runnable demo | 启动说明、固定样例、限制说明 | TBD | Planned |
| Technical report or thesis | 问题、方法、实验、结果、失败与反思 | TBD | Planned |

## Application Claim Builder

对外表述先在此处审计，再进入 CV、SOP 或推荐信：

| Claim ID | Draft claim | Supporting evidence IDs | Verifiable by | Approved wording | Status |
| --- | --- | --- | --- | --- | --- |
| CLAIM-001 | TBD | TBD | code / report / supervisor | TBD | Planned |

写入外部材料前逐项确认：

- 动词是否准确区分 designed、implemented、evaluated 和 proposed。
- 数字是否对应固定数据版本、测试集和指标定义。
- 是否明确个人贡献，而不是把团队成果全部归为个人。
- 是否保留关键限制，避免把相关性、单次结果或演示夸大为稳健结论。
- 导师或复核者能否在合理时间内找到原始证据。

## Change Log

| Date | Change | Evidence impact |
| --- | --- | --- |
| 2026-07-23 | 创建项目证据台账并录入当前已确认事实 | 建立后续实验和申请表述的统一事实来源 |
| 2026-07-29 | 记录 EXP-001 训练脚本、固定配置和本地模型产物 | 可证明已完成训练阶段；尚不支持任何性能声明 |
| 2026-07-29 | 记录 EXP-002 validation 指标、逐条预测和混淆矩阵 | 建立首个内部性能基准；测试集仍保持未使用 |
| 2026-07-29 | 记录 EXP-003 balanced 受控变体的预登记协议与训练产物 | 建立单变量类别权重对照；尚不支持效果声明 |
| 2026-07-29 | 记录 EXP-004 balanced validation 结果并按预登记指标完成选择 | Balanced 版本成为当前 TF-IDF 基线；测试集仍保持未使用 |
| 2026-07-29 | 记录 EXP-005 word + character TF-IDF + Linear SVM 的预登记、训练、validation 结果与独立复算 | 当前传统基线的 validation Macro-F1 和 Accuracy 均提高；仍未读取 test，且不声称严格复现官方 SVM |
| 2026-07-29 | 记录 EXP-006 train-only 交叉验证调参与 EXP-007 一次性 validation 确认 | 更强正则化的冻结配置小幅提高 Macro-F1 与 Accuracy；test 仍未读取，结果状态为 Completed |
| 2026-07-30 | 将 EXP-007 的现有配置和模型哈希冻结为本地传统基线候选 | 停止在该实验编号下继续调参；等待编码器与 LLM 候选冻结后再进入统一 test gate |
| 2026-07-30 | 建立独立 RoBERTa 环境、固定上游模型 revision，并完成 EXP-008 离线 MPS 烟雾测试 | 证明编码器训练链路可运行；合成 loss 不构成模型性能证据，train/validation/test 均未读取 |
| 2026-07-30 | 保留 EXP-009 logger failure 与 EXP-010 restricted-process MPS failure 的源码、日志和元数据 | 两次失败均未产生性能结果，不从历史中删除，也不影响后续科学配置 |
| 2026-07-30 | 完成 EXP-011 RoBERTa-base 三 seed 微调与独立复算 | 建立当前编码器 validation 候选；平均 Macro-F1 比 EXP-007 高 0.110126，optimism 仍是主要弱项；test 未读取 |
| 2026-07-30 | 完成 EXP-012/013 train-only 配置筛选，并冻结原始文本 + 0.05 label smoothing | 避免使用 official validation 进行候选搜索；归一化规则未改变任何样本，不能解释候选分差；论文同款超参数未胜出 |
| 2026-07-30 | 完成 EXP-014 三 seed validation 确认与独立复算 | 通用 RoBERTa-base 相对 EXP-011 获得 0.007415 Macro-F1 小幅收益；test 未读取 |
| 2026-07-30 | 完成 EXP-015 Twitter 域预训练 base encoder 配对实验与独立复算 | 平均 Macro-F1 相对 EXP-014 提高 0.021536，3/3 seed 提高；同时保留 optimism F1 下降 0.034988 的反例；test 未读取 |
| 2026-07-30 | 预登记并完成 EXP-016 一次性冻结 test gate 与独立复算 | EXP-015 以 0.809973 +/- 0.007038 Macro-F1 成为最强冻结条件；域预训练 test delta=+0.017328 且 3/3 seed 为正；label smoothing test delta=-0.003116，validation 收益未泛化；TweetEval test 自此视为已消费 |
| 2026-07-30 | 用户确认冻结 TweetEval 基线，并将代码、匿名结果和验证记录归档至 `f061ec9` | EVID-012 晋升为 `Verified`；后续同一 test 仅允许描述性分析，不再用于调参、模型选择或替换 EXP-016 |
