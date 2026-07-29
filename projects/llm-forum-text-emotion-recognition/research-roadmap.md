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
- 简单基线、编码器基线与 LLM 方法在同一测试集上比较。
- 报告 Macro-F1、各类别 precision/recall/F1 和混淆矩阵。
- 至少完成一组对照、消融或鲁棒性实验。
- 所有外部成果表述均能追溯到 [`evidence-log.md`](evidence-log.md) 中的 `Verified` 证据。

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

Status: not started

目标：

- 先复现 TweetEval emotion 子任务，验证环境、数据划分、训练和评估链路。
- 再复现或现代化实现 GoEmotions 编码器基线。
- 记录原论文环境与现代实现之间的差异。

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

## Phase 3: Reproducible Baselines

Status: not started

目标：

- 建立 TF-IDF + Logistic Regression sanity baseline。
- 建立 BERT 或 RoBERTa 编码器基线。
- 根据标注协议决定是否增加普通 BCE 多标签基线与 SpanEmo。

主要指标：

- Macro-F1。
- 每类 precision、recall 和 F1。
- Weighted-F1 或 Micro-F1，仅作为补充。
- 混淆矩阵、类别支持数和置信区间或多随机种子波动。

通过条件：

- 所有方法使用相同数据版本和测试集。
- 完成重复样本、同线程泄漏和预处理差异检查。
- 至少保存一个可直接复核的预测文件。

## Phase 4: LLM Comparison

Status: not started

目标：

- 先比较 zero-shot 与 few-shot prompting。
- 再比较随机 few-shot 与语义检索示例。
- 只有前述比较有明确价值且资源允许时，才进行 LoRA 或其他参数高效微调。

除分类指标外必须记录：

- 模型提供方、精确版本与访问日期。
- 完整提示模板、示例选择规则和解码参数。
- 格式有效率、失败重试规则、成本和延迟。
- 相对简单基线与编码器基线的真实收益。

通过条件：

- LLM 输出经过确定性的标签解析和异常处理。
- 不使用测试标签选择提示、示例或阈值。
- 能回答“更复杂的方法增加了什么，以及代价是什么”。

## Phase 5: Context, Robustness, and Failure Analysis

Status: not started

目标：

- 比较无上下文、父回复上下文和完整线程上下文。
- 检查反讽、否定、网络用语、拼写噪声、长文本和少数类。
- 对关键模块做消融，例如移除检索示例、标签定义或上下文。

通过条件：

- 至少一组控制实验或消融实验。
- 至少一组扰动、跨域或类别不平衡鲁棒性测试。
- 失败案例按类型整理，并说明哪些结论不能从当前结果推出。

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
