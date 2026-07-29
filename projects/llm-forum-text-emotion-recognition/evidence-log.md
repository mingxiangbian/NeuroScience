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

尚无已完成实验。每次运行使用一个独立实验编号，并保存以下信息：

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
| Baseline reproduction | 环境、命令、配置、日志、预测、指标 | TBD | Planned |
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
