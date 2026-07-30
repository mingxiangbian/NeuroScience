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

## Scope

第一阶段覆盖：

- 英文论坛或社交媒体文本情绪识别。
- 单条文本与回复上下文两种输入设定。
- 粗粒度单标签任务，并根据标注一致性决定是否扩展到细粒度多标签。
- TF-IDF + Logistic Regression、BERT/RoBERTa 与 zero-shot/few-shot LLM 对比。
- 在资源允许且基线稳定后，再评估 LoRA、检索示例或上下文建模。
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

### 尚未完成

- 目标论坛、文本语言、授权范围和数据再分发边界尚未确认。
- 标签体系、标注者、标注协议和一致性指标尚未确定。
- 已有传统基线、通用 RoBERTa 和 Twitter 域预训练 RoBERTa 的训练、validation 与一次性正式 test 证据；但尚未完成自建数据集、LLM 对照、完整错误分析或可运行系统。

## Evidence Standard

[`evidence-log.md`](evidence-log.md) 是本项目面向 CV、SOP 和推荐信的事实来源。只有状态为 `Verified`，且能由代码、日志、数据说明、报告或导师材料复核的条目，才能写成对外成果。

即使新方法没有超过基线，只要问题定义清楚、实验严谨、失败原因分析充分，仍可形成可信的申请项目。

## Core Files

- [`opening-report.md`](opening-report.md): 开题报告研究内容草案、技术路线、创新点与范围控制。
- [`research-roadmap.md`](research-roadmap.md): 从开题到论文交付的阶段路线和通过条件。
- [`hypotheses.md`](hypotheses.md): 当前待验证假设、反证条件和对应实验。
- [`evidence-log.md`](evidence-log.md): 项目事实、实验产物和申请证据台账。
- [`experiments/tweeteval-emotion/test-gate/README.md`](experiments/tweeteval-emotion/test-gate/README.md): EXP-016 一次性正式 test 结果、受控比较、外部参照与复算入口。
- [`../../questions/llm-forum-text-emotion-recognition/open-questions.md`](../../questions/llm-forum-text-emotion-recognition/open-questions.md): 会改变项目主线的开放问题。
- [`../../sources/llm-forum-text-emotion-recognition-sources.md`](../../sources/llm-forum-text-emotion-recognition-sources.md): 论文、代码、数据与合规来源地图。
- [`../../papers/llm-forum-text-emotion-recognition/reading-route.md`](../../papers/llm-forum-text-emotion-recognition/reading-route.md): 论文阅读器与复现建议。

## Next Action

1. 向导师确认目标论坛、语言、标签粒度、数据获取方式和预期交付物。
2. 不再围绕 TweetEval test 调参；先冻结错误案例抽样规则，再比较 EXP-007、EXP-011、EXP-014 与 EXP-015 的共享错误、特有错误、optimism 弱项以及 validation/test 方向不一致的案例。
3. 明确首个 LLM 对照的模型、prompt、成本预算和数据处理边界。若后续读取同一 TweetEval test，必须标记为 post-test evaluation；更强的最终证据应来自新冻结的论坛 holdout。
4. 在采集前完成数据合规检查和小规模双人标注试验。
