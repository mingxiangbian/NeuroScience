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
| EVID-013 | 2026-07-30 | EXP-017 中 EXP-015 有 155 条 3/3 seed 稳定错误，optimism 稳定错误率为 26.02%；87 条被传统基线与全部神经 seed 共同判错；域 encoder 有 21 个稳定恢复和 11 个稳定回退 | 在读原文前冻结五组、最多 48 条的抽样协议；全量复算稳定性、混淆、转移和 overlap，并对实际满足规则的 42 条案例做匿名定性编码 | `projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/` | `verification.json` 复核 14,210 条预测、1,421 个 gold、确定性抽样、42 条编码、聚合表和隐私边界；公开原文泄漏 0 | Verified |
| EVID-014 | 2026-07-31 | EXP-018 固定 GoEmotions dev Macro-F1 0.203644、Micro-F1 0.377639、subset accuracy 0.246959；3,261/5,426 条预测为空，5 个标签 recall 为 0；test 未获取或读取 | 在读取 dev 结果前冻结 TF-IDF + 28 个独立 Logistic Regression 的 Major 协议；实现训练、概率输出、逐标签指标、混淆矩阵和独立验证 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/` | `verification.json` 从固定 dev 标签和保存概率重建 5,426 x 28 矩阵，所有指标差异为 0，输入与产物哈希一致，模型被 Git 忽略，test 不存在 | Verified |
| EVID-015 | 2026-07-31 | EXP-020 BERT-base-cased 三随机种子在固定 GoEmotions dev 上得到 Macro-F1 0.489435 +/- 0.011063、Micro-F1 0.586671 +/- 0.002928；相对 EXP-018 Macro-F1 提高 0.285791；test 未获取或读取 | 固定模型 revision、论文对齐配置、最终 epoch 和三随机种子；实现 MPS 微调、概率与逐类指标保存、模型哈希和独立验证 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/` | `verification.json` 重建三个 seed 的 5,426 x 28 概率与预测矩阵，复算全部指标、逐类结果和 epoch 汇总，最大数值差异为 0；输入、模型和产物哈希一致，模型被 Git 忽略，test 不存在 | Verified |
| EVID-016 | 2026-07-31 | EXP-025 冻结 Qwen3-1.7B constrained zero/few-shot 在 GoEmotions dev 的 Macro-F1 为 0.222998/0.241164；few-shot 配对提高 0.018166，但仍比 EXP-020 均值低 0.248271；test 未获取 | 在 dev 访问前固定模型、prompt、有限状态 decoder、失败计分、完整指标、资源记录、10,000 次 paired bootstrap 和选择规则；实现匿名逐条产物及独立 verifier | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-025-full-dev-zero-few-shot/` | `verification.json` 重建两组 5,426 x 28 矩阵，复算指标、bootstrap、parser、资源与哈希；最大数值差异 0，test 不存在，公开原文泄漏 0 | Verified |
| EVID-017 | 2026-07-31 | EXP-026 matched decoder ablation 显示约束并非普遍 label-neutral：few-shot 双方有效的 4,923 条标签集合全同，zero-shot 双方有效的 5,206 条仅 75.8164% 全同；decoder 的 Macro-F1 影响较小且方向不一致 | 在任何正式 dev 访问前登记 2x2，只移除 token mask；固定 strict parser、invalid-as-empty、联合一致性诊断和 bootstrap，完整执行无约束两条件 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-026-unconstrained-decoder-ablation/` | `verification.json` 独立复算 10,852 条输出及 EXP-025/026 联合分析，最大数值差异 0；来源/产物哈希与隐私边界通过，test 不存在 | Verified |
| EVID-018 | 2026-08-02 | EXP-029 Qwen3-1.7B 监督 LoRA 三 seed 在 GoEmotions dev 的选定 zero-shot Macro-F1 为 0.451374 +/- 0.019212；较 EXP-025 选定条件提高 0.210209，但仍比 EXP-020 均值低 0.038061；test 未获取 | 在训练前冻结 LoRA 位置、训练配置、三 seed 资源门、zero/few-shot 选择规则和 same-dataset 对照；实现训练、双条件全量生成、匿名预测、完整指标、bootstrap 与独立 verifier | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/` | 三个 seed 的 `verification.json` 与 `multi-seed-verification.json` 均通过；复算 32,556 条 condition-row 评估、指标、资源和哈希，确认 private adapters 被忽略、公开原文泄漏 0、test 不存在 | Verified |
| EVID-019 | 2026-08-02 | EXP-030 显示 GoEmotions dev 上 LoRA subset accuracy 0.508293 高于 BERT 的 0.440963，但 Macro-F1 低 0.038061；LoRA 在多标签样本上约 0.043 exact-match，低于 BERT 的约 0.179；当前 Qwen ontology 使 174 条 neutral+emotion gold 结构性不可达 | 在读取错误原文前冻结 6 个抽样角色、最多 48 条案例与可能来源编码；复算 BERT、frozen Qwen 和 LoRA 共 7 份预测的总体、切片、逐类、转移与稳定性，并隔离私有原文 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/` | `verification.json` 复核 5,426 条 gold、7 份预测、48 条定性编码、8 个 CSV、3 个 JSON、确定性抽样和公开隐私边界；最大数值差异 0、公开原文泄漏 0、test 不存在 | Verified |
| EVID-020 | 2026-08-03 | EXP-031 三 seed 推理消融中，old-prompt/open-decoder 与 closed condition 的预测完全一致；aligned-prompt/open-decoder 的 Macro-F1 仅提高 0.001682，Samples-F1、exact match 和 neutral 共现切片 Samples-F1 分别下降 0.003240、0.005529 和 0.009132，所有条件均未产生 neutral+emotion 预测 | 在读取新 dev 结果前冻结三条件、三个 seed、资源门、切片、paired bootstrap 和判定规则；复用冻结 EXP-029 adapters，只改变推理 prompt 与 decoder，并实现匿名全量产物和独立 verifier | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/` | 三个 seed verification 与 `multi-seed-verification.json` 均通过；closed 条件精确复现 EXP-029，所有指标、切片、bootstrap、哈希、资源和隐私检查通过，test 不存在 | Verified |
| EVID-021 | 2026-08-03 | EXP-033 seed-42 target-aligned LoRA 在 GoEmotions dev 的 Macro-F1 为 0.427959，较匹配的 EXP-029 seed-42 aligned-open 参考低 0.012678，paired 95% CI=[-0.026938,+0.001434]；174 条 neutral+emotion gold 仍无目标共现预测 | 修复训练 target 的 neutral ontology 失配；冻结并审计训练、模型、运行时、资源和 validation 合同，完成正式训练与匿名全量 dev 评估 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-033-target-aligned-lora/` | formal training 与 validation verifier 均为 `Passed`；独立复算 adapter、训练轨迹、5,426 条预测、切片、bootstrap、资源、隐私和哈希，test 不存在 | Verified |
| EVID-022 | 2026-08-04 | EXP-034 在 EXP-033 seed-42 adapter 见过的全部 1,396 条 neutral+emotion 训练样本上仍产生 0 条目标共现预测；predicted cardinality=1.019341，而 gold=2.044413 | 将冻结 adapter 回放到预登记的完整训练共现切片，区分“训练目标未学会”与“只在 held-out 数据上不泛化”；实现匿名产物和独立复算 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/runs/exp-034-train-neutral-cooccurrence-diagnostic/` | `verification.json` 从官方 train TSV 与冻结 target 重建 1,396 条 gold，重新解析输出并复算指标、cardinality、共现计数、哈希和隐私边界；test 不存在，状态 `Passed` | Verified |
| EVID-023 | 2026-08-04 | EXP-035 发现冻结 train 的 1,396/1,396 条 neutral+emotion target 都由不同标注者投票聚合形成，同一标注者共选为 0；39 条含 unclear 投票，48 条目的性复核中 6 条被编码为可能需要上下文 | 在读取原文前冻结完整 train allowlist、逐标注者聚合复现、48 条分层抽样和编码词表；流式核对官方 raw annotations，只持久化命中记录 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/annotation-audit/runs/exp-035-neutral-cooccurrence-annotation-audit/` | `verification.json` 独立重建 1,396 条 target、复算 6,936 行逐标注者记录、全部投票/抽样/定性汇总、报告与隐私边界；官方 `>=2` 聚合 mismatch=0，公开原文和上游 ID 泄漏=0，test 不存在 | Verified |
| EVID-024 | 2026-08-04 | EXP-036 在 174 条 dev neutral+emotion 上发现 EXP-029 与 BERT 的 clear-rater expected set-F1 为 0.363250 与 0.362531，三 seed family delta=+0.000720、95% CI=[-0.018463,+0.019903]，属于 practical tie；Qwen 的 official exact match 为 0，但 expected/any-clear-rater exact match 为 0.341284/0.852490 | 在读取 dev raw votes 前冻结 174 条 allowlist、7 份既有预测、逐标注者评分语义、三组比较与 10,000 次 paired bootstrap；不训练、不推理、不选择模型 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/runs/exp-036-dev-rater-aware-diagnostic/` | `verification.json` 不导入 runner，独立复算 866 行逐标注者记录、1,218 条样本级分数、全部 CSV/JSON、三组 bootstrap、artifact hash 与隐私边界；174/174 官方聚合精确复现，test 不存在 | Verified |
| EVID-025 | 2026-08-04 | EXP-037 在完整 5,426 条 GoEmotions dev 上发现 EXP-029/BERT 的 official Macro-F1 为 0.451374/0.489435，clear-rater soft Macro-F1 为 0.347253/0.383471；soft delta=-0.036218、95% CI=[-0.043834,-0.029494]，相对 official delta 的 shift=+0.001843、CI 跨 0，整体差距仍存在 | 冻结全部 dev 行、7 份既有预测、clear-rater vote-fraction soft labels、逐标注者 set-F1、2,000 次 Macro-F1 bootstrap 与 10,000 次样本级 bootstrap；不训练、不推理、不选择模型 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/runs/exp-037-full-dev-rater-aware-diagnostic/` | 修正版 V2 verifier 独立复算 19,440 行逐标注者记录、5,426 行结构、588 行逐标签指标、3 组比较和全部公开产物；最大数值差异 5.12e-13，公开文本/上游 ID/raw rater ID 泄漏为 0，test 不存在 | Verified |
| EVID-026 | 2026-08-04 | EXP-038 一次性 GoEmotions test gate 中，EXP-020 BERT、EXP-029 历史 LoRA 和 EXP-033 target-aligned LoRA 的 Macro-F1 分别为 0.488328 +/- 0.008771、0.450652 +/- 0.032175 和 0.444675；BERT 比论文 test 参照 0.46 高 0.028328 | 在 test 获取前冻结 9 个单元、模型与配置哈希、dev 重放门、指标、资源上限和禁止 test 后选择规则；完成本地推理、匿名逐条产物、聚合与独立复算 | `projects/llm-forum-text-emotion-recognition/experiments/goemotions/test-gate/` | V2 verifier 重建 9 个 5,427 x 28 预测矩阵，复算完整指标和混淆矩阵并核对产物哈希；修正仅把生成标签 ID 从有序比较改为已验证唯一集合比较，未改变预测、指标或冻结配置 | Verified |
| EVID-027 | 2026-08-05 | `DATA-FCTX-CLEAN-V2` 从 IAC 2.0 4forums 的 414,453 帖构建 403,374 个 parent-target 候选，其中 403,336 个通过保守 hard filter；539,658 条 quote 全部完成层级和 offset 核对 | 冻结确定性清洗、隐私、quote 重建和质量标记协议；实现流式 SQL 解析、私有 SQLite、HMAC ID、聚合报告、合成测试与独立 verifier；保留并纠正失败 V1 | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/dataset-construction/` | 独立验证器复算 source/database/report hash、40 项数据库/计数/quote/重复/HMAC/隐私检查，mismatch=0；私有文本、源 ID、key 与数据库受 Git ignore 保护 | Verified |
| EVID-028 | 2026-08-05 | `DATA-FCTX-DEDUP-V2` 在 403,336 个 eligible parent-target pairs 上保留 403,183 条，自动去除 139 条精确重复和 14 条纯格式差异；68,552 条 review-only 近邻边形成 249 个簇、涉及 1,308 条候选，semantic-only 自动删除为 0 | 冻结 pair-level 精确、词法与 MiniLM 语义近邻协议；实现本地 embedding、FAISS HNSW、直接代表项、隐私产物和独立 verifier；V1 未达召回门槛后保留失败证据，V2 仅复用哈希验证的向量与图并重算全部边和决策 | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/dataset-construction/deduplication/` | 独立验证器通过 69 项 hash、SQLite、规则、分数、重放、隐私和检索检查，mismatch=0；mean recall@64=0.992554，门槛 0.98，`k=512` 饱和查询=0；私有文本、ID、向量与索引受 Git ignore 保护 | Verified |
| EVID-029 | 2026-08-06 | `DATA-FCTX-SAMPLE-V1` 从 403,183 条候选中确定性选择 120 条 calibration 主样本和 60 条备用样本；180 条样本与 thread 均全局唯一，四个 diagnostic pool 容量均满足冻结配额 | 冻结 hash ranking、lane quota、thread/review-cluster 全局唯一性、reserve 与 blind-repeat 顺序；实现 metadata-only sampler、私有 HMAC manifest、聚合报告、合成测试和独立重放 verifier | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/` | 独立 verifier 通过 45 项输入 hash、候选重建、配额、顺序、lane eligibility、唯一性、文件权限、Git ignore 和公开隐私检查，mismatch=0；公开报告无论坛文本、源/HMAC ID 或逐样本记录，24 条 blind repeats 尚未生成 | Verified |
| EVID-030 | 2026-08-06 | 冻结的 120 条 calibration 主样本已按 annotation order 导出为私有 staged views；89 条含 target quote，共 164 个顶层引用块 | 从 V2 cleaning/dedup SQLite 只重建 title、direct parent、target body/full 与引用来源；输出 `0001.json` 至 `0120.json`，不写 sampling lane、IAC 弱标签、源 ID、人工标签或 repeat | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/` | 独立 verifier 从数据库逐份重建并通过 34 项 hash、Schema、顺序、allowlist、权限、Git ignore 与公开隐私检查；mismatch、schema problem、hidden-metadata violation 均为 0，`records/` 与 repeat manifest 均不存在 | Verified |
| EVID-031 | 2026-08-07 | 120 条 Human Pass 1 完成后，按预登记 amendment 直接比较 Human、Model 1 和 Model 2；Stage B 三方精确一致为 21/120，Human/Model 一致率约 25%，106 条至少有一次阶段分歧；结果暴露 stance 与 emotion 的任务错位 | 完成人工两阶段标注并固定只读 checkpoint；在语义检查前登记取消盲重标的影响边界；实现封存 hash、逐行身份和决策契约核验、聚合比较、私有分歧 sidecar、隐私扫描与公开诊断报告 | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/reports/three-source-comparison-v1.md` | 比较脚本重验四份模型输出 hash 和 120 行映射，34 项标注测试通过，公开隐私违规为 0；尚无独立统计重算器，不生成 gold、不报告 IAA 或人工时间稳定性 | Completed |
| EVID-032 | 2026-08-08 | `DATA-FCTX-PUBLIC-AUDIT-V1` 判定 KOTE 仅可作 C0 训练/控制候选，Weibo Emotion Cause Corpus 仅可作 C1 辅助，Hotter and Colder 因无打包文本、实时 hydration 与 schema 风险阻塞；三者均未被采用为最终数据集 | 在样本读取前冻结获取和审计边界；固定来源 revision 与 hashes，解析真实 schema、逻辑记录、标签、上下文覆盖和跨文件关系，做不留原文的确定性样本质量复核，并修正物理行数与逻辑记录混淆 | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/public-candidate-audit/` | 独立 verifier 不导入生成器，重解析三份快照并复算关键计数、overlap、checksum、test/hydration 边界和全部 raw Git ignore；35/35 项通过，公开报告无行级文本、ID 或 URL | Verified |
| EVID-033 | 2026-08-08 | `DATA-WEIBO-TASK-V1` 从 11,075 条 EClass 记录中冻结 8,540 条七分类样本；group/target/duplicate-disjoint split 为 train 5,995、validation 1,272、sealed test 1,273，6,138 条有局部前文 | 冻结 ontology、结构解析、隐私处理、canonicalization、泄漏 component、split 容差、paired views 与 test gate；实现确定性构建器、私有 HMAC 数据、公开聚合报告、合成测试和独立 verifier，并保留被替代的 pre-balance 版本 | `projects/llm-forum-text-emotion-recognition/experiments/forum-context/weibo-eclass/` | 独立 verifier 不导入构建器，重解析固定 source 并通过 33/33 项结构、计数、标签、去重、split、泄漏、视图、隐私和密封检查；10/10 单元测试通过，test labels Git ignored，未训练或评估模型 | Verified |
| EVID-034 | 2026-08-08 | EXP-041 完成 Weibo Stage 2 train-only 模型栈预检：M1/M2 执行路径通过，Qwen3-4B 严格格式有效率 37/42，精确 16-block LoRA 两步更新与重载通过，峰值内存 8.65 GB | 冻结模型 revision、BF16 精度、paired prompt、thinking on/off、严格 parser、token budget、LoRA 插入位置和资源门；保留 EXP-039 target-rendering failure、EXP-040 384-token truncation failure 及原 verifier self-match failure | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-2-preflight/` | `AUDIT-EXP-041-V1` 不导入 runner/parser，重构 56 条选择、独立解析 42 条输出并核验模型清单、112 个 LoRA 插入、224 个 adapter tensors 与公私边界；16/16 检查、0 mismatch，validation/test 未访问，未计算性能指标 | Verified |
| EVID-035 | 2026-08-08 | EXP-042 在冻结 Weibo validation 上得到 M0 Macro-F1/Accuracy=`0.116913`/`0.692610`；M1 target/context Macro-F1=`0.338267`/`0.271504`；M2 target/context 三 seed Macro-F1=`0.594925 +/- 0.012919`/`0.594219 +/- 0.012046`，配对 context delta=`-0.000706 +/- 0.024737`，按实际并列规则冻结 target-only | 预注册 Major；同一 train/dev、两个冻结视图、M2 三 seed、final epoch 3、unweighted cross-entropy；row-level predictions 与六个 checkpoint 私有保留，sealed test 未读取 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/` | 独立 verifier 从私有预测重建全部 full/slice metrics、逐类表、混淆矩阵和 M2 aggregate，并核验 checkpoint、隐私与 split access；8/8 检查、0 mismatch | Verified |
| EVID-036 | 2026-08-09 | EXP-043 在冻结 Weibo validation 完成 Qwen3-4B context x reasoning 2x2；A/B/C/D Macro-F1=`0.308684`/`0.281480`/`0.333818`/`0.317997`，按冻结主指标选择 C；观测 context contrast=`-0.021512`、95% CI=`[-0.037515,-0.006905]`，平均 reasoning contrast=`+0.030825`、95% CI=`[+0.007225,+0.057146]`，interaction CI 跨 0；C 比 EXP-042 M2 target-only 低 `0.261107` | 预注册 Major；同一 1,272 条 validation、四个固定条件、greedy batch inference、严格 parser、2,000 次配对 bootstrap、无 retry/repair；5,088 次正式生成、API cost USD 0，row-level prompt/output/prediction 私有保留，sealed test 未读取 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/` | 独立 verifier 重新解析全部 raw output 并重建四条件指标、切片、factorial effects、选择、资源和隐私边界；10/10 检查、0 mismatch。reasoning on 的 Accuracy/Weighted-F1/格式有效率未同步改善；相同 first-clause prompts 只有 273/332 个 reasoning-on 标签一致，因此 D-C 不解释为纯语义 context effect | Verified |
| EVID-037 | 2026-08-09 | EXP-044 在 train-only 代表性 200-step 预检中确认本机可运行 Qwen3-4B BF16 LoRA：耗时 `355.254 s`、稳态中位 `0.575 step/s`、峰值 `8.679 GB`；按 1.25 安全系数，2/3 epochs x 3 seeds 顺序训练投影为 `21.72`/`32.58 h`，不含 validation 生成与分析 | 登记 Minor 资源门；按标签比例和标签内 token 长度分位点确定性抽取 200 条 train，核对空 `<think>` wrapper + JSON 的 supervision mask，运行精确 112-point LoRA，保存数值 history、私有 adapter 和成本投影；validation/test 未访问 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-cost-preflight/runs/exp-044-local-lora-cost-preflight/` | 独立 verifier 不导入 runner，重算输入哈希、完整 train 抽样、mask、runtime、20 行训练轨迹、224 个 adapter tensors、112 个非零 `lora_b`、成本和隐私边界；13/13 检查通过。该证据只支持技术与资源可行性，不支持分类性能 | Verified |
| EVID-038 | 2026-08-09 | EXP-046 在 16 条 train-derived prompt 上确认 reasoning-on 输出依赖共同批次：singleton 与固定顺序 batch 8 的新进程重放均为 final label/parser/raw `16/16` 一致；改变 batch 8 共同成员后分别为 `14/16`、`14/16`、`5/16`，因此按预注册规则冻结 singleton | 保留 EXP-045 的 `BatchEncoding` 初始化失败并在模型推理前停止；EXP-046 显式校验整数 token IDs，执行五个新进程模式共 80 次生成，只比较 raw output、parser state 和 final label，不用 gold 计算性能 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-batch-equivalence-v2/runs/exp-046-batch-equivalence-v2/` | 独立 verifier 不导入 runner，重建 5,995 条 train tokenization 与 16 条抽样，重算 strict parser、五模式摘要、四组一致性、资源和隐私边界；12/12 检查通过，峰值 `9.532 GB`，总记录墙钟 `2432.088 s`，validation/test 未访问 | Verified |
| EVID-039 | 2026-08-10 | EXP-047 seed 42 按冻结合同完成 Qwen3-4B BF16 generative LoRA train-only：2 epochs、`11,990` micro-iterations、`160,736` trained tokens、耗时 `20,577.547 s`、峰值 `8.804 GB`；epoch-2 adapter 的 224 tensors、112/112 非零 `lora_b` tensors、7,340,032 个可训练参数和独立 load-forward 均通过。随后两次全新进程、16 条 singleton replay 的 final label/parser/raw 均为 `16/16` 一致 | 正式授权仅覆盖 seed 42 train split；保存 epoch-1/epoch-2 checkpoints、数值 history 和私有 raw replay。训练与回放各自的 V1 verifier 都暴露阶段状态缺陷：前者把预期 adapter 误判为 dry-run 私有根污染，后者把自身新写入的 verification 文件计入源文件数；均以 post-run amendment 和独立 V2 verifier 修正，没有重训或重跑推理 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/` | 训练 V2 重算合同、环境、数据、history、adapter 哈希/权限并执行独立 load-forward；回放 V2 重新 tokenization、解析私有 raw output、核对两个 pass 与 4 个公开源文件且公开 raw 泄漏为 0。两者均为 `Passed`；validation/test 未访问，seeds 43/44 未授权，不支持 LoRA 分类性能结论 | Verified |
| EVID-040 | 2026-08-10 | EXP-047 seed 43 按独立授权完成 Qwen3-4B BF16 generative LoRA train-only：attempt 2 为 2 epochs、`11,990` micro-iterations、`160,736` trained tokens、耗时 `20,548.721 s`、峰值 `8.804 GB`；epoch-2 adapter 的 224 tensors、112/112 非零 `lora_b` tensors、7,340,032 个可训练参数和独立 load-forward 均通过。随后两次全新进程、16 条 singleton replay 的 final label/parser/raw 均为 `16/16` 一致，parser-valid 也均为 `16/16` | 首次受限启动因无 Metal device 以 `-6` 退出，发生在第一个 training iteration 之前；失败 run/stdout 与空 adapter 目录原样保留。correction 将 attempt 2 输出改到全新追加式目录，重新通过 gate 后从头训练，没有覆盖、恢复或续训；正式访问仅覆盖 train split，保存 epoch-1/epoch-2 checkpoints、数值 history 和私有 raw replay | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/` | attempt 2 训练 verifier 重算合同、授权、环境、数据、history、adapter 哈希/权限并执行独立 load-forward；回放 verifier 重新 tokenization、解析私有 raw output、核对两个 pass 与 4 个公开源文件且公开 raw 泄漏为 0；两者及各自 `--check` 均为 `Passed`。validation/test 未访问，seed 44 未授权，不支持 LoRA 分类性能结论 | Verified |
| EVID-041 | 2026-08-11 | EXP-047 seed 44 按独立授权完成 Qwen3-4B BF16 generative LoRA train-only：2 epochs、`11,990` micro-iterations、`160,736` trained tokens、耗时 `20,415.953 s`、峰值 `8.805 GB`；epoch-2 adapter 的 224 tensors、112/112 非零 `lora_b` tensors、7,340,032 个可训练参数和独立 load-forward 均通过。随后两次全新进程、16 条 singleton replay 的 final label/parser/raw 均为 `16/16` 一致，parser-valid 也均为 `16/16` | 授权、runtime、数据选择、实现源码和输出目录在训练前冻结并做哈希绑定；正式访问仅覆盖 train split，保存 epoch-1/epoch-2 checkpoints、数值 history 和私有 raw replay。回放合同在最终 adapter 与训练 verification 落盘后冻结，两遍分别使用全新进程 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/` | 训练 verifier 重算合同、授权、环境、数据、history、adapter 哈希/权限并执行独立 load-forward；回放 verifier 重新 tokenization、解析私有 raw output、核对两个 pass 与 4 个公开源文件且公开 raw 泄漏为 0；两者及各自 `--check` 均为 `Passed`。validation/test 未访问，三 seed 门现已全部通过；仍不支持 LoRA 分类性能结论，下一步为 matched validation 授权门 | Verified |
| EVID-042 | 2026-08-12 | EXP-047 在冻结的 1,272 条 Weibo EClass validation 上完成 matched singleton 比较：无 adapter reference Macro-F1=`0.333598`；LoRA seeds 42/43/44 为 `0.552028`/`0.548289`/`0.587096`，均值 `0.562471 +/- 0.021408`，按预注册规则相对 reference 提高 `+0.228873`，判定为 `material_improvement` | 显式授权只覆盖 validation；四个条件均使用同一 Qwen3-4B BF16、target-only、reasoning-on、singleton、greedy decoder、prompt/parser 和 1,272 行顺序。三 adapter 的 Accuracy 为 `0.768082`/`0.786164`/`0.783805`，parser-valid 均为 100%；reference 为 Accuracy `0.222484`、parser-valid `90.8805%`，其中 116 条可能因 1,024-token 上限截断 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/` | 独立 verifier 重建 5,088 次生成的 prompt、token、strict parser、预测、全量/切片指标、混淆矩阵和 2,000 次 group-level paired bootstrap，10 类检查、0 mismatch；三个 seed 相对 reference 的 Macro-F1 bootstrap 95% CI 均完全高于 0。LoRA 均值仍比 EXP-042 M2 target-only `0.594925` 低 `0.032454`，该跨架构差值仅作描述；sealed test 未访问 | Verified |
| EVID-043 | 2026-08-12 | EXP-048 对 EXP-042/047 的 7 份冻结 validation 预测完成错误分析：LoRA 相对 reference 的 Accuracy 增益 `+0.556866` 中，116 条 reference output-failure slice 贡献 `+0.070755`，1,156 条 reference 有效输出贡献 `+0.486111`；因此改善不只是格式恢复。LoRA 相对 encoder 的 Macro-F1/Accuracy 差为 `-0.032454`/`-0.013103`，最大逐类 F1 劣势为 sadness `-0.084593`、neutral `-0.065775`、anger `-0.039949` 和 positive `-0.029494` | 在读取原文前冻结 Major 协议、六类目的性抽样和定性代码；只读取 validation 及既有预测，不重训、不重新推理、不调参。LoRA 三 seed 有 904 条 3/3 正确、201 条 0/3 错误和 167 条不稳定，最终标签两两一致率均值 `0.884`，低于 encoder 的 `0.943`；48 条匿名案例主要出现标签/数据不确定性、ontology 重叠、隐含情绪和 no_emotion 边界 | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/` | 独立 verifier 复算 1,272 行、7 份预测、9 份 CSV、3 份 JSON 和 48 条人工编码，最大数值差为 0；私有原文文件为 mode 0600、Git ignored，公开 raw-text 泄漏为 0；目的性样本计数不作总体 prevalence 推断，sealed test 未访问 | Verified |
| EVID-044 | 2026-08-13 | EXP-049 按冻结 TEST-READY 合同完成 Weibo EClass 一次性正式 test：encoder/LoRA/matched no-adapter Qwen Macro-F1=`0.649621 +/- 0.007365`/`0.636612 +/- 0.021429`/`0.316921`；LoRA-reference delta=`+0.319691`，95% group-bootstrap CI=`[+0.274779,+0.362068]`；LoRA-encoder delta=`-0.013009`，CI=`[-0.045671,+0.024011]` | 在标签访问前冻结 M0、M1、encoder 三 seed、Qwen reference、LoRA 三 seed，共九个单元，以及 checkpoint、prompt、parser、指标、切片、bootstrap 和停止规则；先为每个单元生成 1,273 条预测，再只打开一次标签；不按 test 选最佳 seed | `projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/` | 独立 verifier 重建 9 个预测文件、11,457 条逐行预测、全部总体/切片/逐类指标及 2,000 次 group bootstrap，10 类检查、0 mismatch；10 个私有文件均 Git ignored 且未跟踪，公开 raw text/source ID 泄漏为 0。首次 finalizer 在指标落盘后因 null parser 的报告渲染错误停止；仅执行 report-only recovery，未重开标签、未重跑模型或指标 | Verified |
| EVID-045 | 2026-08-13 | `DATA-SO-TASK-V1` 从 pinned Stack Overflow Emotion Gold XLSX 重建 4,800 行六标签 gold，六个 sheet 逐行对齐且三位 rater 多数票复算 0 mismatch；4,681 个 duplicate components 被固定划分为 train/validation/test `3,360/720/720` 行、`3,277/702/702` 个组件，`surprise` 支持为 `31/7/7` | 来源 revision=`d6a679f39a198fdb0657a6116d35dd7b92496898`、XLSX SHA-256=`29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`、seed=`20260813`；exact/NFKC-casefold-whitespace duplicate components 不跨 split，26 个冲突组件原样绑定为 `18/4/4`；最大标签与 balance-slice 分配误差为 `0.011111`/`0.007692` | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json` | 独立 verifier 通过 53/53 项，synthetic unit tests 通过 11/11；raw text、逐行标签、rater votes 与 test gold 均在 mode 0700/0600 的 Git-ignored 私有层，公开 split index 不含文本、标签或上游坐标。test 为 sealed、未授权、未被模型消费；本条只支持数据构建结论，不支持模型性能结论 | Verified |
| EVID-046 | 2026-08-13 | EXP-050 在 24 条确定性 train-only 样本上验证 Stack Overflow M1-M4 共享执行链：M1/M2 六维 BCE 更新、M2/M3 matched head 与 zero-step logits、M3/M4 matched LoRA 初始化、112 个固定 LoRA 插入点、assistant-only loss 和 strict invalid-as-zero parser 均通过；成功链合计 44.18 s，Qwen 峰值 8.91 GB | 在正式性能实验前冻结 EXP-051 至 EXP-054 protocols、共享 config/prompt/parser、模型 revision、pooling、head、LoRA、checkpoint/threshold 顺序和数据访问边界；实现分阶段 runner、独立 verifier 与合成单元测试，并保留首个 digest-scope 失败尝试及 correction | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-050-shared-model-preflight/` | 独立 verifier 通过 77/77 项，model-preflight unit tests 通过 7/7；成功运行五个 stage 均为 Passed，只读取 train，validation/test 均未访问，未计算任何性能指标。M4 两步 smoke 的 0/4 canonical-valid 只证明 invalid 被确定性处理，不支持模型性能结论；正式 EXP-051 至 EXP-054 尚未执行 | Verified |
| EVID-047 | 2026-08-13 | EXP-051 seed 42 在 Stack Overflow C0 validation 上选中 epoch 4；固定 0.5 Macro-F1=`0.598759`，共享阈值 `0.25` 下 Macro-F1=`0.604619`、Micro-F1=`0.764645`、strict subset accuracy=`0.740278`，component-bootstrap 95% CI=`[0.559703,0.638948]` | 在性能结果前冻结 runner、独立 verifier、checkpoint/threshold 规则和 seed-42-only 授权；保留 epoch 1 内 MPS OOM 失败，完成 10-step train-only CPU recovery preflight 后，以未改变的科学配置从头训练 5 epochs，并隔离 checkpoint 与逐行 prediction | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/` | 独立 verifier 重放 selected checkpoint，复算概率、阈值、完整指标、逐类结果、2,000 次 component bootstrap、哈希、资源、隐私与 split access，67/67 项通过；test 未访问。`surprise` 仅 7 个正例且 F1=`0`，五标签敏感性 Macro-F1=`0.725543`；本条只支持单 seed 完整性门，不构成 M1 三 seed 结论 | Verified |
| EVID-048 | 2026-08-13 | EXP-051 seed 43 在同一 Stack Overflow C0 validation 上选中 epoch 4；固定 0.5 Macro-F1=`0.601329`，共享阈值 `0.30` 下 Macro-F1=`0.625341`、Micro-F1=`0.774869`、strict subset accuracy=`0.758333`，component-bootstrap 95% CI=`[0.580438,0.661573]` | 以独立 amendment 只授权 seed 43 的 train + validation，要求 seed-42 run/verification 哈希和 67/67 状态不变；科学配置与 seed 42 相同，在 CPU 从初始化运行 5 epochs，耗时 1,933.45 s、峰值 RSS 5.24 GB；seed 44 与 test 不授权 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/` | 独立 verifier 重放 selected checkpoint 并复算五轮概率、阈值、完整指标、逐类结果、2,000 次 component bootstrap、哈希、资源、隐私与 split access，72/72 项通过且 checkpoint replay 最大误差为 0；`surprise` 再次 F1=`0`。seeds 42/43 的共享阈值 Macro-F1 描述性均值为 `0.614980 +/- 0.014652`，不构成三 seed M1 结论 | Verified |
| EVID-049 | 2026-08-14 | EXP-051 seed 44 在同一 Stack Overflow C0 validation 上选中 epoch 5，固定与共享阈值 0.50 Macro-F1 均为 `0.621803`；三 seed M1 聚合的固定/共享阈值 Macro-F1 为 `0.607297 +/- 0.012628`/`0.617254 +/- 0.011084`，对应 strict subset accuracy 为 `0.773611 +/- 0.011369`/`0.760648 +/- 0.021621` | 在结果产生前以独立 amendment 只授权 seed 44 train + validation，并冻结三 seed arithmetic mean + sample std 聚合；要求 seed-43 run/verification 哈希和 72/72 状态不变。相同科学配置在 CPU 从初始化运行 5 epochs，耗时 1,856.63 s、峰值 RSS 5.36 GB；聚合不拼接逐行预测 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-three-seed-validation/` | Seed-44 verifier 重放 checkpoint 并复算五轮概率、选择、指标、bootstrap、哈希、资源、隐私与 split access，72/72 通过且最大误差为 0；独立 aggregate verifier 绑定三组 run/verification 哈希并以独立公式复算，53/53 通过。三个 seed 的 `surprise` F1 均为 0；test 未访问，EXP-052 未授权，不支持 M1-M2 或 test 结论 | Verified |
| EVID-050 | 2026-08-14 | EXP-052 seed 42 在同一 Stack Overflow C0 validation 上完成 frozen Qwen + `Linear(2560,6)`：epoch 2 被选中，固定 0.5 Macro-F1=`0.183391`；共享阈值 `0.25` 下 Macro-F1=`0.324929`、Micro-F1=`0.509700`、strict subset accuracy=`0.477778`，component-bootstrap 95% CI=`[0.282747,0.370449]` | 只授权 seed 42 train + validation；先修正 formal dry-run 强制门、失败 verifier 结构化报告、全源码 split audit 与成本投影，再以新 attempt 完成 24 条 train-only dry-run。正式 Qwen 全冻结、15,366 参数 head、2 epochs、6,720 steps、无序列截断；40.00 min、峰值 MLX 8.23 GB、API cost 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/` | 修正后的 dry-run 通过 51/51，真实 MLX head checkpoint smoke 在 11/11 测试内通过；正式 verifier 重算 token/order、特征、batch、head replay、checkpoint、阈值、完整指标、2,000 次 bootstrap、隐私和 split access，70/70 通过，head replay 最大误差 0。`surprise` F1=0，五标签 Macro-F1=`0.389915`；同 seed M1-M2 共享阈值差 `-0.279691` 仅为描述性单 seed 结果；test、seeds 43/44、M3/M4 未访问或授权 | Verified |
| EVID-051 | 2026-08-14 | EXP-052 seed-42 train/validation frozen-Qwen feature cache 被冻结为 seeds 43/44 的候选只读输入；该 gate 不产生性能结果 | 绑定 seed-42 run/verification、共享数据/模型/prompt/pooling 合同，以及 train/validation cache 的 SHA-256、shape、dtype、sample order 与 token stream；consumer 必须用 `mmap_mode=r` 并在使用前后复核 hash，且重新生成 seed-specific head、batch order、checkpoint 与 prediction | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/` | 独立 verifier 通过 74/74：两个 cache 均为 float32、有限值、只读 mmap、Git ignored，source seed 42 保持 70/70 verified 且 test 未访问；gate 未加载 Qwen、未训练、未计算性能。该授权不包含 seeds 43/44 训练，且明确禁止 EXP-053/054、context、router 与 test 复用 | Verified |
| EVID-052 | 2026-08-14 | EXP-052 seed 43 只读复用已验证的 train/validation frozen-Qwen cache 并训练全新 `Linear(2560,6)` head：epoch 2 被选中，固定 0.5 Macro-F1=`0.133610`；共享阈值 `0.20` 下 Macro-F1=`0.353593`、Micro-F1=`0.537969`、strict subset accuracy=`0.470833`，component-bootstrap 95% CI=`[0.315104,0.392166]` | 独立授权只覆盖 seed 43；cache 以 `mmap_mode=r` 读取并在运行前后复核 SHA-256，head 初始化、PCG64 batch order、optimizer、checkpoint、probability 和 bootstrap 全部按 seed 重建。2 epochs、6,720 steps；总耗时 4.23 s、峰值 MLX 0.000611 GB，Qwen load/forward/feature extraction 和 API cost 均为 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/` | 首次 preflight 因扁平 artifact 接口假设错误在训练前停止且未产生性能；修复后的新 attempt 通过 73/73。正式 verifier 绑定授权、cache gate、源码、配置和输出，复算 batch/head/checkpoint/threshold/metrics/bootstrap/privacy/split，99/99 通过；EXP-052 回归测试 26/26 通过。相对 seed 42，固定 Macro-F1 `-0.049782`、共享 Macro-F1 `+0.028664`；相对同 seed M1 的共享 Macro-F1 为 `-0.271748`。当前只支持 frozen-linear 弱表现与 seed/calibration 敏感性警告；test、seed 44、M3/M4 未访问或授权 | Verified |
| EVID-053 | 2026-08-14 | EXP-052 seed 44 只读复用同一 train/validation frozen-Qwen cache 并训练全新 `Linear(2560,6)` head：epoch 2 被选中，固定 0.5 Macro-F1=`0.137657`；共享阈值 `0.25` 下 Macro-F1=`0.278145`、Micro-F1=`0.494538`、strict subset accuracy=`0.523611`，component-bootstrap 95% CI=`[0.240756,0.314903]` | 独立授权只覆盖 seed 44，且以前一 seed 已完成并 99/99 verified 的 run/verification 哈希为前置门；cache 以 `mmap_mode=r` 读取并在运行前后复核 SHA-256，head 初始化、PCG64 batch order、optimizer、checkpoint、probability 和 bootstrap 全部按 seed 重建。2 epochs、6,720 steps；总耗时 4.79 s、peak MLX 0.000611 GB，Qwen load/forward/feature extraction 和 API cost 均为 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/` | Consumer preflight 78/78、正式 verifier 104/104、EXP-052 回归测试 28/28 通过；selected-head replay、阈值、完整指标、2,000 次 bootstrap、cache hash、隐私和 split access 均独立复核。共享阈值 Macro-F1 比 seeds 42/43 低 `0.046783`/`0.075447`，比同 seed M1 低 `0.343658`；`joy` 与 `surprise` F1 均为 0，五标签敏感性 Macro-F1=`0.333774`。本条完成第三个单 seed 结果，但不授权或替代 M2 三 seed aggregate；test、M3/M4 未访问或授权 | Verified |
| EVID-054 | 2026-08-14 | EXP-052 M2 三 seed validation aggregate：固定 0.5 Macro-F1=`0.151553 +/- 0.027647`；per-seed 共享阈值 Macro-F1=`0.318889 +/- 0.038085`、Micro-F1=`0.514069 +/- 0.022042`、strict subset accuracy=`0.490741 +/- 0.028678`、hamming loss=`0.121142 +/- 0.006565` | 在读取聚合结果前冻结 seeds 42/43/44、算术平均、sample std (`ddof=1`)、完整指标与逐类汇总；不拼接逐行预测。以同 seed、同条件计算 M2-M1 descriptive paired delta，不对 `n=3` 做显著性检验。Seed 42 含 Qwen feature extraction、43/44 为 cache-only，因此资源只逐 seed 保留，不计算 family 平均成本 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/` | 独立 verifier 通过 85/85，完整 EXP-052 tests 36/36。固定/共享阈值 M2-M1 Macro-F1 配对差值分别为 `-0.455744 +/- 0.035919`/`-0.298365 +/- 0.039425`，六个逐 seed 差值均为负；校准提高 Macro-F1 但降低 subset accuracy 并提高 hamming loss。`surprise` 三 seed F1 均为 0，`joy` 明显不稳定。结论仅覆盖 final-layer last-input-token pooling + 线性 head，不外推到其他读出、LoRA 或 Qwen 是否含情绪信息；test、M3/M4 未访问或授权 | Verified |
| EVID-055 | 2026-08-14 | EXP-053 M3 Classification LoRA 的 train-only 资源门通过：32/32 个更新 loss 有限，112 个 `lora_b` 全部非零，7,340,032 个 LoRA 参数与 15,366 参数 head 均更新且冻结 base sentinel 不变；checkpoint 重载 logits 最大误差为 0。训练/回放阶段峰值分别为 `8.674`/`8.376 GB`；按 `1.5x` 安全系数投影每 seed `4.436 h`、三 seed 顺序执行 `13.308 h` | 只读取并 tokenization 3,360 条 train，确定性抽取覆盖六标签、neutral、双标签与长短文本范围的 32 条；head 初始 hash 与 M2 seed 42 完全一致，LoRA 初始 logit delta 严格为 0，head/LoRA 使用独立 AdamW。Attempt 1 因训练引用未释放便重载第二份 Qwen，使进程总峰值误触 13 GB 门；保留失败记录后以 amendment 仅修正顺序阶段内存释放和计量，未放宽资源门或改变科学合同 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/` | EXP-053 专项 tests 12/12；独立 verifier 不导入 runner，重新加载 Qwen、重算完整 train tokenization/采样、head hash、zero delta、112-point insertion、private checkpoint tensors/digests/replay、时间投影、Git 隔离与 split access，102/102 通过。Validation/test 均未访问，无性能指标；本条只支持本机实现、资源与恢复可行性，不授权正式 seed 42、seeds 43/44 或 EXP-054 | Verified |
| EVID-056 | 2026-08-14 | EXP-053 M3 formal seed 42 选中 epoch 2：固定 0.5 Macro-F1=`0.602846`，共享阈值 `0.40` 下 Macro-F1=`0.637786`、Micro-F1=`0.758315`、strict subset accuracy=`0.755556`、hamming loss=`0.050463`，component-bootstrap 95% CI=`[0.548975,0.709997]`；五标签敏感性 Macro-F1=`0.692616`，`surprise` F1=`0.363636` 但仅 7 个正例且 CI 从 0 开始 | 只授权 seed 42 的 train + validation；与 M2 seed 42 匹配同一 head 初始化、prompt、pooling、batch-order RNG、2 epochs/6,720 steps 与评估制度。训练 7,340,032 个 LoRA 参数和 15,366 参数 head，base sentinel 保持不变；总耗时 `13,756.811 s` (`3.821 h`)、峰值 MLX `8.702 GB`、API cost 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-42/` | 相对 matched M2，固定/共享阈值 Macro-F1 delta=`+0.419455`/`+0.312857`，配对 component-bootstrap 95% CI=`[+0.326063,+0.497920]`/`[+0.223280,+0.388544]`。第一次独立 verifier 完整回放后仅因资源验证记录旧字段名保留为 Failed (`135/136`，概率误差 0)；schema-only amendment 后再次完整回放通过 `148/148`，概率误差 0、test 未访问。该条只支持单 seed 的 classification-interface LoRA 适配收益；在该 gate 完成时 seeds 43/44、M3 family、EXP-054 与 test 未授权 | Verified |
| EVID-057 | 2026-08-15 | EXP-053 M3 formal seed 43 选中 epoch 2：固定 0.5 Macro-F1=`0.659318`，共享阈值 `0.35` 下 Macro-F1=`0.663515`、Micro-F1=`0.756696`、weighted F1=`0.758532`、strict subset accuracy=`0.754167`、hamming loss=`0.050463`，component-bootstrap 95% CI=`[0.570351,0.732537]`；五标签敏感性 Macro-F1=`0.707329`，`surprise` F1=`0.444444` 但仅 7 个正例且 95% CI=`[0,0.8]` | 第二份独立授权只覆盖 seed 43 的 train + validation；与 M2 seed 43 匹配同一 head 初始化、prompt、pooling、batch-order RNG、2 epochs/6,720 steps 与评估制度。训练 7,340,032 个 LoRA 参数和 15,366 参数 head，base sentinel 保持不变；总耗时 `12,759.608 s` (`3.544 h`)、峰值 MLX `8.699 GB`、API cost 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-43/` | 相对 matched M2，固定/共享阈值 Macro-F1 delta=`+0.525708`/`+0.309922`，配对 component-bootstrap 95% CI=`[+0.432380,+0.598715]`/`[+0.208105,+0.390880]`。独立 verifier 完整重放 720 条 validation、复算 checkpoint/threshold/metrics/bootstrap/privacy/split，`143/143 Passed`，概率最大误差 0、test 未访问。Seeds 42/43 的共享阈值 Macro-F1 描述性均值为 `0.650650 +/- 0.018194`；在该 gate 完成时两 seed 仍不构成 M3 family，seed 44、EXP-054 与 test 未授权 | Verified |
| EVID-058 | 2026-08-15 | EXP-053 M3 formal seed 44 选中 epoch 2：固定 0.5 Macro-F1=`0.598812`，共享阈值 `0.25` 下 Macro-F1=`0.660795`、Micro-F1=`0.763713`、weighted F1=`0.756752`、strict subset accuracy=`0.741667`、hamming loss=`0.051852`，component-bootstrap 95% CI=`[0.584731,0.727760]`；五标签敏感性 Macro-F1=`0.720227`，`surprise` F1=`0.363636` 但仅 7 个正例且 95% CI=`[0,0.705882]` | 第三份独立授权只覆盖 seed 44 的 train + validation，并冻结 seeds 42/43 为前置证据；与 M2 seed 44 匹配同一 head 初始化、prompt、pooling、batch-order RNG、2 epochs/6,720 steps 与评估制度。训练 7,340,032 个 LoRA 参数和 15,366 参数 head，base sentinel 保持不变；总耗时 `12,065.663 s` (`3.352 h`)、峰值 MLX `8.702 GB`、API cost 0 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-44/` | 相对 matched M2，固定/共享阈值 Macro-F1 delta=`+0.461155`/`+0.382650`，配对 component-bootstrap 95% CI=`[+0.374006,+0.536410]`/`[+0.298126,+0.455866]`。独立 verifier 完整重放 720 条 validation、复算 checkpoint/threshold/metrics/bootstrap/privacy/split，`148/148 Passed`，概率最大误差 0、test 未访问；seed42/43/44 回归测试 `47/47`。三个单 seed均已验证，但本条未授权 M3 aggregate、EXP-054 或 test，不能提前报告 family mean/std | Verified |
| EVID-059 | 2026-08-15 | EXP-053 M3 三 seed validation aggregate：固定 0.5 Macro-F1=`0.620325 +/- 0.033829`；per-seed 共享阈值 Macro-F1=`0.654032 +/- 0.014135`、Micro-F1=`0.759575 +/- 0.003674`、weighted F1=`0.755704 +/- 0.003472`、strict subset accuracy=`0.750463 +/- 0.007649`、hamming loss=`0.050926 +/- 0.000802` | 在读取聚合结果前冻结 seeds 42/43/44、算术平均、sample std (`ddof=1`)、完整指标、逐类结果、matched M3-M2/M1 descriptive delta 与资源汇总；不读取或拼接逐行预测，不对 `n=3` 做显著性检验。绑定 seed 42 的修正版 verifier、seed 44 correction 及 M1/M2 aggregate 哈希 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/` | 独立 aggregate verifier 通过 `124/124`。共享阈值 M3-M2 Macro-F1 delta=`+0.335143 +/- 0.041168` 且 3/3 seed 为正，支持 LoRA 相对 matched frozen-Qwen linear head 的稳定任务适配收益。相对 M1 的共享六标签 Macro-F1 delta=`+0.036778 +/- 0.003154`，但去除仅 7 个正例的 `surprise` 后为 `-0.033981 +/- 0.008620`，Micro-F1 与 weighted F1 也分别为负，不能声称 M3 全面优于 encoder。Test、EXP-054 与错误分析均未访问或授权 | Verified |
| EVID-060 | 2026-08-15 | EXP-055 M1/M3 validation 错误分析：M1/M3 shared-threshold Macro-F1=`0.617254 +/- 0.011084`/`0.654032 +/- 0.014135`，去除 `surprise` 后为 `0.740705 +/- 0.013301`/`0.706724 +/- 0.013816`；M1-only/M3-only exact-correct 为 `42/53/73` 与 `53/50/43`。Whole-vector oracle 平均选择 M3 `8.33% +/- 0.77%`，相对 M1 的六标签/五标签 Macro-F1 上界为 `+0.136394 +/- 0.009058`/`+0.074784 +/- 0.010869`，五项 router headroom gate 全部通过 | 在读取逐行预测和原文前冻结 validation-only 协议；绑定 M1/M3 三 seed verified run/config/protocol 哈希，复算 720 条 validation、702 个 duplicate components、shared/fixed threshold、逐类指标、空预测、neutral FP、exact 转移、seed 稳定性和 2,000 次 component bootstrap。按冻结优先级确定性抽取最多 48 条，单一 reviewer 实际编码 45 条；原文和 source ID 仅存于 mode 0600、gitignored private 目录 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/error-analysis/runs/exp-055-m1-m3-validation-error-analysis/` | 定性样本主要标记 ontology overlap、weak-emotion/neutral boundary、implicit emotion 和 model/representation limitation，但目的性单人复核不能代表总体比例、因果或模型 reasoning。第一次临时 verifier 预检仅因 Markdown 空白的字面断言通过 208/209；科学产物未改变，attempt-2 只归一化空白并通过 `220/220`，专项测试 `16/16`。未训练、未推理、未访问 test 或 EXP-054；oracle 只授权另行登记 train-OOF router feasibility，不证明可部署收益 | Verified |
| EVID-061 | 2026-08-15 | EXP-054 M4 Qwen Generative LoRA 三 seed validation：seeds 42/43/44 均选中 epoch 2，Macro-F1=`0.589699`/`0.658405`/`0.597443`，聚合为 `0.615182 +/- 0.037632`；Micro-F1=`0.755144 +/- 0.009373`、weighted F1=`0.745278 +/- 0.016138`、strict subset accuracy=`0.776389 +/- 0.013679`、hamming loss=`0.050849 +/- 0.003706`，strict parser-valid rate=`1.000000 +/- 0.000000` | 使用冻结的 Qwen3-4B BF16 revision、同一 3,360/720 train/validation、seeds 42/43/44、rank-8 LoRA、assistant-only next-token CE、compact JSON、greedy decoding 和 invalid-as-zero parser；每 seed 2 epochs/6,720 optimizer steps。首次 train-only preflight 因 runner 在 adapter 重载时仍保留首个模型引用触发 Metal OOM，失败记录保留；仅修正对象生命周期后 attempt 2 完成全量 train 渲染、两步更新、adapter 重载和 4 条生成，并通过 `26/26` 独立检查 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-054-m4-generative-lora-three-seed-validation/` | 三个 seed verifier 均通过 `92/92`，每 seed 两个全新进程 replay 各为 `60/60` raw-output 一致；aggregate verifier 通过 `33/33`，专项 unit tests `10/10`。M4-M3 Macro-F1 delta=`-0.038850 +/- 0.030200` 且 3/3 seed 为负；五标签 delta=`-0.005542 +/- 0.036548`，subset accuracy delta=`+0.025926 +/- 0.017859`。结果支持端到端 formulation 比较，不隔离 generation 的因果效应；平均 wall time=`3.553 h/seed`、峰值 MLX=`9.300 GB`、API cost 0。Test 未访问，仍需单独冻结统一 TEST-READY 合同 | Verified |
| EVID-062 | 2026-08-15 | EXP-056 将 Stack Overflow C0 的 M1-M4 冻结为统一 TEST-READY：四个 family x seeds 42/43/44，共 12 个正式评估单元；固定各 seed 已选 checkpoint/adapter/head、M1-M3 validation 阈值、M4 strict parser、六标签主指标、五标签敏感性、五组 matched contrasts 与 2,000 次 duplicate-component bootstrap | 机器合同以 SHA-256 绑定全部上游 run/verification、模型产物、实现、prompt 和协议；runner 强制 `initialize -> predict-family -> seal-predictions -> score`，所有预测哈希封存前不能打开标签。EXP-055 oracle、未通过 train-OOF gate 的 router、ensemble、best-seed 和 test-time calibration 均排除 | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/test-gate/` | Final contract SHA-256=`bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966`；readiness verifier `89/89 Passed`，专项测试 `6/6`；冻结时 authorization 不存在、test inputs/labels opened 均为 `false`、正式公私输出目录均不存在。该条只证明 TEST-READY，不含任何 test 性能结果；test 仍 sealed、未授权、未消费 | Verified TEST-READY |
| EVID-063 | 2026-08-16 | EXP-056 按冻结合同完成 Stack Overflow C0 一次性正式 test：M1/M2/M3/M4 三 seed Macro-F1=`0.567459 +/- 0.007814`/`0.295226 +/- 0.020587`/`0.613804 +/- 0.025733`/`0.547823 +/- 0.015312`；M3-M2 delta=`+0.318578`、95% component-bootstrap CI=`[+0.254425,+0.369327]`；M3-M1 delta=`+0.046345`、CI=`[-0.008674,+0.089730]`；M4-M3 delta=`-0.065981`、CI=`[-0.107869,-0.011312]` | 用户授权绑定最终合同 SHA；依次完成四个 family 共 12 个单元，在任何标签访问前 hash-seal 全部预测，再一次性打开 720 条 test 标签评分。没有 test 后 checkpoint、seed、阈值、prompt、parser 或模型选择；M4 2,160 条生成全部 strict-parser-valid | `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/` | Post-score verifier `29/29 Passed`，不重开 sealed label source；results SHA-256=`d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd`。M3 相对 M2 的适配收益成立，但相对 M1 的六标签与五标签 CI 均跨 0；`surprise` 只有 7 个 test 正例。M4 主指标低于 M3，虽 subset accuracy 最高也不能改写主结论。首次 M2 受限启动因无 Metal 在推理前停止，无产物且未开标签；相同冻结命令获批后从头完成。test 自此已消费 | Verified |

## Data Register

在数据采集或下载前填写。未知项保持 `TBD`，不得用估计值代替。

| Field | Current value | Evidence path | Status |
| --- | --- | --- | --- |
| Target forum or domain | Stack Overflow Emotion Gold C0 is the frozen current main task; Weibo EClass remains a completed historical proxy, IAC2 a closed challenge diagnosis, KOTE an unused candidate, and Hotter is excluded | `experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md` | Current main task verified |
| Language | English for the current Stack Overflow task; the historical Weibo stage remains Chinese | `experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md` | Verified |
| Collection method | Pinned official repository workbook only; no live Stack Overflow scraping or inferred thread recovery in C0 | `data/stack-overflow-emotion-gold/task-v1.manifest.json` | Verified |
| Terms or authorization basis | Upstream README requests citation, but the repository contains no standard `LICENSE`; current use is restricted to private research, and this is not a legal determination | `experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md` | Verified conservative boundary |
| Raw sample count | 4,800 aligned workbook rows across six label sheets | `experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json` | Verified |
| Deduplicated sample count | No row is deleted or label-merged: all 4,800 rows are retained in 4,681 exact/normalized duplicate components; 26 conflicting components covering 52 rows remain bound within split | `experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json` | Verified component binding |
| Calibration sample | No new manual calibration is part of C0; the 120-case IAC2 calibration remains a closed historical diagnostic and is not evidence for Stack Overflow label quality | `experiments/forum-context/annotation/reports/three-source-comparison-v1.md` | Historical only |
| Private annotation views | No new annotation views are created; row text, upstream rater votes, derived labels and sealed test gold remain private | `data/stack-overflow-emotion-gold/README.md` | Verified storage boundary |
| Label set and definitions | Six independent labels in fixed order: love, joy, surprise, anger, sadness and fear; `neutral=true` only when all six are zero, not a seventh softmax class | `experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md` | Verified |
| Number of annotators | Three upstream rater marks per row and label; gold is positive at two or more votes | `experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json` | Verified reconstruction |
| Inter-annotator agreement | DATA-SO-TASK-V1 verifies exact majority-gold reconstruction but does not report a new IAA coefficient; majority agreement must not be presented as IAA | `experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md` | Not computed in this protocol |
| Anonymization procedure | Public identifiers are deterministic truncated SHA-256 IDs derived from protocol/source/row inputs; public artifacts omit text, upstream coordinates, row labels and rater votes | `experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json` | Verified public allowlist |
| Train/dev/test split rule | Exact plus NFKC/casefold/whitespace duplicate-component-disjoint multi-label stratification: 3,360/720/720 rows with seed `20260813`; test labels were opened once only after all 12 frozen prediction files were hash-sealed under EXP-056 | `data/stack-overflow-emotion-gold/task-v1.manifest.json` | Verified, test consumed |
| Redistribution boundary | Source XLSX and all row-level derived artifacts remain in mode 0700/0600 Git-ignored private directories; public files contain code, protocol, hashes, aggregate statistics and opaque split IDs only | `experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json` | Verified conservative boundary |

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

### EXP-017: Frozen Test Error Analysis

```text
Experiment ID: EXP-017
Tier: Major
RQ IDs: RQ-B2、RQ-B3
Date: 2026-07-30
Research questions: 冻结模型的错误在类别、随机种子和模型之间如何分布？Twitter 域 encoder 的整体收益对应哪些稳定恢复与回退？固定定性样本中有哪些可能的语言、上下文或标签因素？
Status: Verified；仅作已消费 test 的描述性分析，不构成新的开发或模型选择依据
Code commit: 分析运行时 HEAD 0fec243e5b96c04f2ad23382f430d3fe986b888b（dirty state）；新增分析代码和匿名产物尚待归档提交
Registration: 在读取任何错误原文前，固定五组角色、优先级、seed=20260730、每类配额、去重顺序、underfill 规则和最多 48 条预算；实际严格满足并入选 42 条，不以其他案例补足
Dataset and inputs: TweetEval upstream 4fbd22c；official test 1,421 rows；复用 EXP-016 十个已冻结 prediction artifacts，不执行新模型推理；EXP-016 run/verification 和 test text/label 哈希均固定
Full-split result: EXP-015 3/3 seed 稳定正确 1,119 条（78.75%）、稳定错误 155 条（10.91%）、mixed outcome 147 条（10.34%）
Class stability: EXP-015 稳定错误率 anger=6.63%、joy=8.94%、optimism=26.02%、sadness=14.14%；optimism 同时有最高 mixed rate 17.07%
Confusion result: 369 个 optimism seed-sample 中，62 个预测为 anger、42 个为 joy、25 个为 sadness；sadness 到 anger 为 129/1,146
Label-smoothing transition: EXP-011 到 EXP-014 有 80 条增加 correct seeds、82 条减少、1,259 条不变；不存在 0/3-to-3/3 稳定恢复或 3/3-to-0/3 稳定回退
Domain-encoder transition: EXP-014 到 EXP-015 有 129 条增加 correct seeds、90 条减少；21 条稳定恢复、11 条稳定回退；optimism 没有完整稳定恢复或回退
Error overlap: 87 条（test 的 6.12%、EXP-015 稳定错误的 56.13%）被 EXP-007 和 EXP-011/014/015 全部 seed 共同判错；只有 12 条仅 EXP-015 处于 stable-wrong 状态，但其他模型仍可能是 mixed 而非全对
Qualitative sample: 16 条高置信错误、6 条域恢复、4 条域回退、8 条共享错误、8 条普通错误，共 42 条；重叠 flags 中 lexical-cue conflict=32、mixed emotion=27、possible context dependency=18、annotation ambiguity=16、slang/noise=16、implicit emotion=14、sarcasm/irony=13、negation=7
Primary possible source: ontology overlap=14、model/representation limitation=12、annotation/data uncertainty=7、surface-form noise=5、missing context=4；这是单人定性判断，不是重新标注的真值
Privacy: 原文只保存在 gitignored private/selected_text.private.jsonl；公开 CSV、JSON、报告和台账仅含匿名 row ID、类别、模型输出、编码类型与聚合数；verification 检查 raw-text leak count=0
Cost and latency: API cost USD 0；新模型推理 0；42-case 单人复核；自动分析与复算为本地 CPU 秒级运行
Artifact paths: experiments/tweeteval-emotion/error-analysis/configs/exp-017-frozen-error-analysis.json；protocols/exp-017-frozen-error-analysis.md；runs/exp-017-frozen-error-analysis/
Result: 域预训练收益伴随稳定错误减少和更有利的 seed-count 转移；optimism 的弱项同时包含持久错误和初始化敏感性；超过一半 EXP-015 稳定错误属于所有条件共享的任务困难子集
Failure or caveat: 42 条为目的性分层样本，其比例不能外推为 test prevalence；只有一名 reviewer，无一致性指标；孤立 Tweet 无法验证上下文依赖；定性 flags 不是因果机制、心理学结论或新 gold label；任何后续方案必须在新 validation/forum holdout 上开发
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/error-analysis/analyze_frozen_errors.py --config <copy-with-new-output-dir>
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/error-analysis/verify_error_analysis.py
Verified by: verification.json 重建 1,421 条 aligned records 和 14,210 条 prediction rows，复算稳定性、混淆、转移、overlap、确定性抽样与定性聚合，并检查 private 文件未跟踪和公开 raw-text leak count=0
Target figure/table: 模型 seed 稳定性表；EXP-015 类级 stable/mixed 表；受控转移表；共享错误 overlap 表；定性因素计数表
Thesis destination: 方法章节的预注册错误抽样与隐私边界；结果章节的类别/seed/overlap；讨论章节的 optimism、类别重叠、上下文和域预训练边界
```

### EXP-018: GoEmotions TF-IDF + One-vs-Rest Logistic Regression

```text
Experiment ID: EXP-018
Tier: Major
RQ ID: RQ-G1
Date: 2026-07-31
Research question: 在固定 GoEmotions 28 标签多标签任务上，简单词法监督方法能达到什么水平，并暴露哪些类别不平衡和固定阈值问题？
Status: Verified；完成 RQ-G1 的 simple-baseline 条件；配对编码器条件由 EXP-020 完成
Code commit: 运行时 HEAD 0fec243e5b96c04f2ad23382f430d3fe986b888b（dirty state）；protocol SHA-256 2127acd5658a79c218f51dcefa9898ee6ef32558bb5cf79efeb2d9235e0f2a71；implementation SHA-256 cd305e231f54f4d9e0b40d7ed42f9c4c61be15cbda85b05682e79bc638b23e8d
Registration: 在查看 dev 结果前冻结 word TF-IDF、One-vs-Rest Logistic Regression、全局阈值 0.5、主辅指标和无事后调参规则
Dataset version and split: DATA-GOE-V1；Google Research agreement-filtered train 43,410 rows、dev 5,426 rows、28 labels；source revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0；test 未获取
Model: lowercase word TF-IDF，1-2 grams，min_df=2，max_features=100,000，sublinear_tf=true，58,338 features；28 个独立 LogisticRegression，C=1.0，L2，liblinear，class_weight=None，max_iter=1000；全局 threshold=0.5；不强制非空预测，不抑制 neutral
Environment: Python 3.10.20；scikit-learn 1.7.2；NumPy 2.2.6；SciPy 1.15.3；joblib 1.5.3；macOS arm64；CPU
Seed: 42
Primary metric: dev Macro-F1=0.2036443096；macro precision=0.5556100083；macro recall=0.1447543743
Secondary metrics: Micro-F1=0.3776385989；Weighted-F1=0.3328093951；Samples-F1=0.2781791375；subset/exact-match accuracy=0.2469590859；Hamming loss=0.0353193618
Prediction diagnostics: gold label cardinality mean=1.175820；predicted mean=0.413196；empty predictions=3,261/5,426（60.10%）；neutral co-predictions=2
Per-label result: gratitude F1=0.860248、love=0.614657、amusement=0.547461、admiration=0.499295、neutral=0.484634；disappointment、grief、nervousness、pride、relief 的 recall/F1 为 0，其中 disappointment 有 163 个 dev positives
Cost and latency: API cost USD 0；本地 CPU total=3.407991 seconds，fit=1.808585 seconds
Artifact paths: experiments/goemotions/tfidf-ovr-logreg/protocols/exp-018-tfidf-ovr-logreg.md；experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/
Result: 模型无 convergence warning，但在固定 0.5 阈值下明显低召回、低预测标签基数，构成可复现的保守词法下界；这不是优化器失败的证据
Failure or caveat: dev 只用于开发证据；未测试 class weighting、阈值调优、resampling 或 top-1 fallback，不能声称这些方法会改善 held-out；官方 train/dev 保留已审阅的 41 个 exact-text overlap；不得与 TweetEval 四分类分数直接比较
Reproduction command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/tfidf-ovr-logreg/train_and_evaluate.py
Verification command: /Users/phoenix/miniconda3/envs/llm/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/tfidf-ovr-logreg/verify.py（已完成；verification.json 为单次写入证据，不覆盖）
Verified by: verification.json 独立读取固定 dev 标签与保存概率，重建 5,426 x 28 gold/prediction 矩阵；聚合指标、逐标签指标、混淆矩阵和哈希全部一致，max metric diff=0；test 不存在且未访问
Target figure/table: GoEmotions 简单基线与编码器基线主结果表；预测标签基数和零召回标签诊断表
Thesis destination: 方法章节的多标签任务、固定阈值和评估协议；结果章节的 GoEmotions 监督基线表；讨论章节的类别不平衡、低召回和简单词法方法边界
```

### EXP-020: GoEmotions BERT-Base-Cased Three-Seed Fine-Tuning

```text
Experiment ID: EXP-020
Tier: Major
RQ ID: RQ-G1
Date: 2026-07-31
Research question: 在固定 GoEmotions 28 标签多标签任务、官方论文对齐超参数和相同 dev 评估协议下，BERT-base-cased 相对 EXP-018 简单词法基线增加多少有效性能？
Status: Verified；BERT dev 条件完成并冻结；GoEmotions test 未获取，RoBERTa alternative 未执行
Code commit: 运行时 HEAD 0fec243e5b96c04f2ad23382f430d3fe986b888b（dirty state）；protocol SHA-256 c406f9765f9e733e4adfa05712403bf149d50fddeca712b41c95eb0ab067c81d；config SHA-256 8ec432ddecc8e400bed2e676bcfb36649f1f1a48ce8b9c811ebde60f525277d5；implementation SHA-256 672f3085344f3046cea8c23225e90998bfaec21334584c411b15e914ebf9cfc7
Registration: 在查看正式 dev 结果前固定 BERT revision、三 seed、4 epochs、最后一轮作为冻结模型、全局阈值 0.3、主辅指标和无事后调参规则；EXP-019 仅验证环境
Dataset version and split: DATA-GOE-V1；Google Research agreement-filtered train 43,410 rows、dev 5,426 rows、28 labels；source revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0；test 未获取
Model: bert-base-cased snapshot revision cd5ef92a9fb2f889e972770a36d4ed042daf221e；model manifest SHA-256 795076f67146a80a2bd875d198305dcd663c84feccdf314b7b426354a1b6d75b；28-logit sigmoid multi-label head；BCEWithLogitsLoss；dropout=0.1
Training: max_length=50；batch_size=16；learning_rate=5e-5；epochs=4；warmup_ratio=0.1；weight_decay=0；每 seed 10,852 optimizer steps；最终 epoch 固定，不根据 dev 选择 checkpoint
Environment: Python 3.10.20；PyTorch/Transformers 环境锁 SHA-256 123e455840fb9e5e9230cd3eb7feda625a8819c4cd3dbf82b91068a7d60797fd；macOS arm64；Apple MPS
Seeds: 42、43、44
Primary metric: dev Macro-F1=0.4894350234 +/- 0.0110632106；macro precision=0.5081921896 +/- 0.0139948879；macro recall=0.5036522659 +/- 0.0088809844
Secondary metrics: Micro-F1=0.5866712266 +/- 0.0029280492；Weighted-F1=0.5828207287 +/- 0.0027126613；Samples-F1=0.5959360867 +/- 0.0031587150；subset accuracy=0.4409632633 +/- 0.0039627604；Hamming loss=0.0361925825 +/- 0.0002851131
Prediction diagnostics: gold label cardinality mean=1.175820；predicted mean=1.275955 +/- 0.004188；empty predictions=91.67 +/- 10.07；threshold=0.3
Seed results: seed 42 Macro-F1=0.478753、seed 43=0.488709、seed 44=0.500843；三个最终模型 SHA-256 分别为 f141c4b1b55e8828ef34148d640796c506e8385bee1f02b26e5c36791358fa5d、533ea076ac8d8affcb05a26b77f400647fda5210df8a327924c2fb2b617c7485、56b9fd21e5cc8e0a8820f2d47b3a1e4dcf3b47802deeeed271e1bed2afc0b526
Per-label result: gratitude F1=0.901493、amusement=0.793396、love=0.783643、remorse=0.728241、admiration=0.721486；grief=0（support 13）、relief=0.035088（support 18）、realization=0.254477、disappointment=0.303140；pride 的三 seed 波动为 0.349828 +/- 0.243638（support 15）
Epoch diagnostics: mean dev Macro-F1 从 epoch 1 的 0.392417 升至 epoch 3 的 0.489754，epoch 4 为 0.489435；epoch 4 相对 epoch 3 近似持平，但 dev loss 0.086722 -> 0.093219、Micro-F1 0.597161 -> 0.586671，提示指标相关的轻度过拟合；仍按预登记保留 epoch 4
Cost and latency: API cost USD 0；本地 MPS total=13,048.695 seconds（3h37m28.7s）
Artifact paths: experiments/goemotions/bert-base/protocols/exp-020-bert-base-cased.md；experiments/goemotions/bert-base/configs/exp-020-bert-base-cased.json；experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/
Result: BERT-base-cased 在同一 DATA-GOE-V1 dev 上提高 Macro-F1、Micro-F1 和预测标签覆盖，建立后续 LLM 对照所需的监督编码器基线；EXP-018 与 EXP-020 的阈值分别为 0.5 和 0.3，故差值不是纯模型架构消融
Paper boundary: GoEmotions 论文 full-taxonomy BERT Macro-F1=0.46 来自 test；EXP-020 来自 dev，且使用现代 PyTorch/Transformers/MPS，而非原 TensorFlow Estimator，不能把 0.489435 与 0.46 作同 split 差值或声称逐位复现
Failure or caveat: test 不存在且未访问；稀有类的均值和 seed 波动不稳定；频率只能解释部分困难，不能从 support 单独推出因果归因；没有执行阈值搜索、class weighting、early stopping 或 RoBERTa 替换
Reproduction command: PIP_USER=0 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/bert-base/train_and_evaluate.py
Verification command: PIP_USER=0 PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/bert-base/verify.py（已完成；verification.json 为单次写入证据，不覆盖）
Verified by: verification.json 独立读取保存概率，重建三个 seed 各 5,426 x 28 的 gold/prediction 矩阵；聚合、逐标签和 epoch 指标差异均为 0；输入、模型和产物哈希全部一致；预测文件不含原文或 comment ID；test 不存在且未访问
Target figure/table: GoEmotions 简单基线与 BERT 编码器主结果表；三 seed learning curves；逐类 F1 与 support 图；预测标签基数表
Thesis destination: 方法章节的 BERT 多标签微调与冻结协议；结果章节的 GoEmotions 监督基线和类别表现；讨论章节的阈值边界、稀有类波动、轻度过拟合与现代复现限制
```

## LLM Run Register

每种 LLM 配置都应视为一个可版本化实验：

GoEmotions 的简单多标签与 BERT dev 监督基线已经冻结，因此 LLM 对照可以登记
独立 Major protocol，但 test gate 继续关闭。TweetEval 的四分类单标签结果不得
作为 GoEmotions LLM 的性能对照。

### EXP-025: Constrained Qwen3-1.7B Zero/Few-Shot

```text
Experiment ID: EXP-025
Tier / RQ: Major / RQ-G2
Status: Verified；constrained few-shot 按冻结 dev 规则选定；test 未获取
Dataset and protocol: DATA-GOE-V1；official agreement-filtered dev；5,426 rows；28 labels
Provider and exact model: Qwen/Qwen3-1.7B revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e；本地未量化 MLX BF16
Prompt template: exp-022-resource-v1.json SHA-256 2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c；zero-shot 与固定三条 synthetic few-shot
Decoding: greedy；temperature=0；finite-state label-name JSON token mask；strict parser；无 synonym mapping、retry 或 post-hoc repair
Invalid policy: invalid 或 length-terminated 输出计为空预测；zero-shot 2 条，few-shot 0 条
Primary metric: constrained zero-shot/few-shot dev Macro-F1=0.222998/0.241164
Secondary metrics: Micro-F1=0.235917/0.250627；subset accuracy=0.179137/0.105234；predicted label cardinality=1.1896/1.9112
Selection: few-shot - zero-shot Macro-F1=+0.018166；paired bootstrap 95% CI=[+0.002977,+0.034469]；超过 0.005 practical threshold
Baseline comparison: 相对 EXP-018 为 +0.019353/+0.037520；相对 EXP-020 三 seed 均值为 -0.266437/-0.248271
Format and intervention: parser=99.9631%/100%；mask blocked unrestricted argmax on 5,426/503 rows；最终标签影响由 EXP-026 确定
Tokens and latency: prompt tokens=932,344/1,540,056；generated tokens=45,605/52,264；median generation=0.7499/0.9690 s
Resource and cost: local Apple M3；total=10,000.27 s；peak MLX memory=3.6600 GB；API cost USD 0
Artifacts: experiments/goemotions/qwen3-1.7b/protocols/exp-025-full-dev-zero-few-shot.md；configs/exp-025-full-dev-zero-few-shot.json；runs/exp-025-full-dev-zero-few-shot/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_full_dev.py --experiment EXP-025
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_full_dev.py --experiment EXP-025
Verified by: verification.json 独立重建两组 5,426 x 28 标签矩阵并复算指标、bootstrap、parser、资源和哈希；max difference=0；test absent；四项隐私字段 false
Result: frozen prompting 略高于简单词法下界，但远低于监督 BERT；生成接口与复杂度未在当前 dev 协议下转化为更强分类性能
Failure or caveat: dev-only 模型选择；synthetic few-shot；post-trained 模型；constrained 系统不能直接归因于裸 Qwen；无上下文、LoRA、probe 或 test
Thesis destination: Table-G2-1、Figure-G2-1；方法章节的本地 LLM/decoder/invalid policy；讨论章节的性能-成本边界
```

### EXP-026: Matched Unconstrained Decoder Ablation

```text
Experiment ID: EXP-026
Tier / RQ: Major / RQ-G2
Status: Verified；行为消融完成；不得覆盖 EXP-025 prompt 选择；test 未获取
Controlled change: 与 EXP-025 的模型、prompt、dev 顺序、greedy 参数和 parser 相同，仅移除 finite-state token mask
Primary metric: unconstrained zero-shot/few-shot dev Macro-F1=0.228700/0.236465
Secondary metrics: Micro-F1=0.238562/0.246069；subset accuracy=0.161445/0.101364；predicted label cardinality=1.3056/1.7077
Format: parser=95.9823%/90.7298%；invalid-as-empty rows=218/503；无 retry、repair 或 synonym mapping
Parser failures: zero-shot 70 neutral-combined + 148 unknown-label；few-shot 1 invalid-json + 206 neutral-combined + 296 unknown-label
Decoder effect on Macro-F1: unconstrained - constrained=+0.005702 zero-shot（95% CI [-0.003906,+0.015234]，跨 0）；-0.004699 few-shot（95% CI [-0.008687,-0.000990]，低于 0.005 practical threshold）
Label-set diagnostics: zero-shot exact agreement=3947/5206=75.8164%、mean Jaccard=0.847289；few-shot exact agreement=4923/4923=100%、mean Jaccard=1.0
BERT comparison: 两个条件相对 EXP-020 各 seed 的 Macro-F1 差均为负，范围 -0.242287 至 -0.272144，六个 paired bootstrap interval 均排除 0
Tokens and latency: prompt tokens=932,344/1,540,056；generated tokens=50,786/51,873；median generation=0.6864/0.8801 s
Resource and cost: local Apple M3；total=8,768.00 s；peak MLX memory=3.6600 GB；API cost USD 0
Artifacts: experiments/goemotions/qwen3-1.7b/protocols/exp-026-unconstrained-decoder-ablation.md；configs/exp-026-unconstrained-decoder-ablation.json；runs/exp-026-unconstrained-decoder-ablation/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_full_dev.py --experiment EXP-026
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_full_dev.py --experiment EXP-026
Verified by: verification.json 独立复算 10,852 条无约束输出、9 个 bootstrap comparison 和 EXP-025/026 joint analysis；max difference=0；test absent；四项隐私字段 false
Result: constraint 对 few-shot 主要是格式恢复，对 zero-shot 则会改变相当一部分双方有效标签路径；其 Macro-F1 影响小于行为/格式影响且方向不一致
Failure or caveat: 这是 dev 上的 decoder behavior ablation，不是 test、内部机制或人类情绪识别证据；sequence score 不是校准的 28 标签概率
Thesis destination: Table-G2-1、Table-G2-2、Figure-G2-1；讨论章节的 decoder attribution boundary
```

### EXP-029: Supervised LoRA for Qwen3-1.7B

```text
Experiment ID: EXP-029
Tier / RQ: Major / RQ-G2
Status: Verified；三 seed 完成；按冻结 dev 规则选择 zero-shot；test 未获取
Dataset and protocol: DATA-GOE-V1；train 43,410 rows、dev 5,426 rows、28 labels；dev gold 不变；test absent
Provider and exact model: Qwen/Qwen3-1.7B revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e；本地未量化 MLX BF16
LoRA placement: final 16/28 blocks；attention q/k/v/o 与 MLP gate/up/down；rank=8；MLX scale=20.0；4,980,736 trainable parameters（约 0.289%）
Training: 1 epoch；micro-batch=2；gradient accumulation=5；effective batch=10；21,705 microiterations；Adam；constant learning rate=1e-5
Seeds: 42、43、44
Prompt and decoding: EXP-022 zero-shot prompt用于训练；dev 同时评估 zero-shot 与固定三条 synthetic few-shot；greedy constrained label-name JSON；无 retry/repair
Data mapping: 因冻结 ontology 禁止 neutral 与情绪共现，训练目标中 1,396 条仅移除 neutral；neutral-only 不变；dev gold 的 174 条共现完全保留
Primary metric: zero-shot dev Macro-F1=0.451374 +/- 0.019212；seed 42/43/44 为 0.437205/0.443673/0.473242
Prompt control: few-shot dev Macro-F1=0.425265 +/- 0.004858；zero-shot - few-shot mean=+0.026109，超过 0.005 practical threshold，选择 zero-shot
Secondary metrics: selected zero-shot mean Micro-F1=0.576343；Weighted-F1=0.552013；subset accuracy=0.508293；两条件三 seed parser validity 均为 100%
Frozen Qwen comparison: matched zero-shot +0.228376；matched few-shot +0.184101；selected EXP-029 - selected EXP-025=+0.210209
BERT comparison: selected EXP-029 - EXP-020 three-seed mean=-0.038061；LoRA 缩小但未消除监督编码器差距
Resource and cost: 每 seed 训练 6.13-6.52 h；双条件 dev 2.56-2.80 h；训练峰值 <=7.208 GB；API cost USD 0
Adapter hashes: seed 42/43/44 分别为 77624d77d2ba2225dcf51e7fbf9a8131aa746bfd0004d72ae203360fedfe88ff、8265d98f1ab8bb3ea40dff901aede2b56dba520c351acf97ea26f0a6e0e8f806、fd0c3a33add30eb24c62c7154eea8f20aab090a8d1f85159046ca263943b2e48
Artifacts: experiments/goemotions/qwen3-1.7b/protocols/exp-029-instruct-lora.md；configs/exp-029-instruct-lora.json；preflight/exp-029-*.json；runs/exp-029-instruct-lora/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_lora.py train --seed <42|43|44>；随后使用 dev --seed <42|43|44>
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_lora.py --seed <42|43|44>；随后 --aggregate
Verified by: 三份 seed verification 与 multi-seed-verification 均 Passed；复算全部 dev 标签矩阵、指标、bootstrap、资源和哈希；公开产物不含原文/comment ID；private adapters gitignored；test absent
Result: 监督 LoRA 为 post-trained 1.7B 模型增加了显著的任务能力，远强于 frozen prompting；固定 synthetic demonstrations 在适配后没有继续带来收益；BERT 仍是更强的监督 dev 基线
Failure or caveat: dev 同时承担 prompt 选择与开发证据；不同模型训练目标和读出接口使 BERT 差值不是纯架构消融；seed 44 明显较高，必须报告 mean +/- SD；训练目标的 neutral 映射可能影响 neutral recall；没有 test、论坛上下文或机制证据
Thesis destination: Table-G2-2、Figure-G2-1；结果章节的 LoRA 与冻结 Qwen/BERT 比较；讨论章节的监督收益、prompt 失配、资源成本和机制边界
```

### EXP-030: Frozen Cross-model Dev Error Analysis

```text
Experiment ID: EXP-030
Tier / RQ: Major / RQ-G1 and RQ-G2
Status: Verified；只使用冻结 dev gold 与既有预测；test 未获取或读取
Dataset and protocol: DATA-GOE-V1；dev 5,426 rows、28 labels；gold label cardinality=1.175820
Frozen conditions: EXP-020 BERT-base-cased seeds 42/43/44；EXP-025 Qwen3-1.7B constrained few-shot；EXP-029 Qwen3-1.7B LoRA constrained zero-shot seeds 42/43/44
Registration: 在读取错误原文前冻结输入哈希、6 个抽样角色、每组最多 8 条、可能来源编码、隐私边界和 test 禁令
Primary comparison: BERT / frozen Qwen / LoRA Macro-F1=0.489435/0.241164/0.451374；subset accuracy=0.440963/0.105234/0.508293；Samples-F1=0.596/0.264/0.586
Prediction cardinality: BERT 1.276；frozen Qwen 1.911；LoRA 1.034；LoRA 的较高 subset accuracy 主要来自 4,548 条单标签样本，不能替代 Macro-F1
Multilabel slice: 878 条 any-multilabel 上，BERT / frozen Qwen / LoRA subset accuracy 约为 0.179/0.040/0.043；Samples-F1 约为 0.556/0.264/0.475
Ontology boundary: dev 保留 174 条 neutral+emotion gold；EXP-025/029 的 Qwen ontology 禁止该组合，因此这些样本对 Qwen 的 exact-match 结构性不可达；其对全量 subset accuracy 的直接上限影响约 0.032，不能单独解释 Macro-F1 差距
Error transitions: BERT -> LoRA 有 1,263 条 seed-share improvement、695 条 worsening；稳定 0/3 -> 3/3 恢复 304 条，3/3 -> 0/3 回退 122 条。frozen Qwen -> LoRA 有 1,915 条稳定恢复、79 条稳定回退
Shared errors: 1,771 条样本被 frozen Qwen、全部 BERT seed 和全部 LoRA seed 稳定判错，占 dev 32.64%
Qualitative review: 确定性抽取 48 条匿名案例；lexical-cue conflict 39、annotation ambiguity 37、label overlap 19、mixed emotion 19、implicit emotion 18、context dependency 15、slang/noise 11、minority 6、sarcasm 4、negation 3。该 purposive single-reviewer 编码只描述样本，不估计总体流行率
Possible primary sources: overlapping ontology 18；annotation/data uncertainty 9；model representation limitation 9；missing context 6；output policy/mapping 5；surface noise 1
Artifacts: experiments/goemotions/error-analysis/protocols/exp-030-frozen-dev-error-analysis.md；configs/exp-030-frozen-dev-error-analysis.json；runs/exp-030-frozen-dev-error-analysis/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/error-analysis/analyze_frozen_dev_errors.py；随后 summarize_review.py
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/error-analysis/verify_error_analysis.py
Verified by: verification.json 独立复算 7 份预测、5,426 条 gold、8 个 CSV、3 个 JSON、48 条定性编码和报告；max difference=0；私有原文被 gitignore；公开原文泄漏 0；test absent
Official comparison boundary: GoEmotions 原论文只发布最终 test 的 BERT Macro-P/R/F1=0.40/0.63/0.46；官方仓库和指标代码未发布固定 validation accuracy。EXP-020 dev Macro-F1 比 0.46 高 0.029435 仅作量级参照，不是 matched-split 超越声明
Result: LoRA 已把冻结生成式模型的大量错误纠正为接近 BERT 的行为表现，但仍偏向近单标签输出；BERT 的优势集中在多标签召回、部分细粒度标签和重叠 ontology，而不是由单一 anger 类别频率解释
Failure or caveat: 所有比较仍在 dev；三类模型的读出接口不同；定性编码为单人目的抽样；structural neutral mismatch 是已识别候选因素，不构成因果效应，除非用新编号做受控消融
Thesis destination: Table-G1-2、Table-G2-3、Figure-G2-2；结果章节的跨模型错误结构与讨论章节的 ontology、上下文和多标签召回边界
```

### EXP-031: Neutral Co-occurrence Inference Ablation

```text
Experiment ID: EXP-031
Tier / RQ: Major / RQ-G2
Status: Verified；三 seed inference-only ablation；不训练、不选 test condition；test 未获取或读取
Dataset and protocol: DATA-GOE-V1；dev 5,426 rows、28 labels；174 条 gold neutral co-occurrence 完整保留
Parent and frozen models: EXP-029 seeds 42、43、44 的最终 Qwen3-1.7B LoRA adapters；模型、adapter、输入、环境、prompt、decoder、runner 和 verifier 均由 SHA-256 固定
Conditions: old-prompt-closed-decoder；old-prompt-open-decoder；aligned-prompt-open-decoder；EXP-029 historical closed 仅作可复现性参照
Primary metric: closed / old-open / aligned-open Macro-F1=0.451374 +/- 0.019213 / 0.451374 +/- 0.019213 / 0.453056 +/- 0.014757
Seed-level aligned-open Macro-F1: seed 42/43/44=0.440637/0.449159/0.469370
Decoder-only effect: old-open 与 contemporaneous closed 的 16,278 条 seed-row 预测完全一致；Macro-F1 平均差值=0
Total inference-policy effect: aligned-open - closed Macro-F1=+0.001682，低于 0.005 practical threshold；三个 seed 差值为 +0.003432/+0.005486/-0.003872
Secondary effects: Samples-F1=0.585848 -> 0.582608，差值=-0.003240；exact match=0.508293 -> 0.502764，差值=-0.005529；predicted cardinality=1.034 -> 1.045
Neutral slice: 174 条 neutral co-occurrence 上 Samples-F1=0.562261 -> 0.553129，差值=-0.009132；所有条件和 seed 的 predicted neutral co-occurrence rows 均为 0
Reproducibility audit: contemporaneous closed 与历史 EXP-029 closed 的预测和指标完全一致
Decision: no_material_inference_improvement；推理时修正没有达到预登记的一般改善或局部改善规则
Resource and cost: 每 seed active inference 3.72-3.78 h；峰值 MLX memory=3.8395 GB；API cost USD 0
Artifacts: experiments/goemotions/qwen3-1.7b/protocols/exp-031-neutral-ontology-inference-ablation.md；configs/exp-031-neutral-ontology-inference-ablation.json；runs/exp-031-neutral-ontology-inference-ablation/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_neutral_ontology_ablation.py full --seed <42|43|44>；三个 seed 完成后使用 aggregate
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_neutral_ontology_ablation.py --seed <42|43|44>；随后 --aggregate
Verified by: 三份 seed verification 与 multi-seed-verification 均 Passed；复算指标、切片、transitions、bootstrap、资源、哈希和隐私边界；test absent
Result: 对当前 target-misaligned adapters，仅在推理时放开 neutral ontology 不足以产生实质改善，也没有恢复 neutral 共现输出
Failure or caveat: 该结果不能证明训练目标是唯一原因，也不能拒绝 corrected retraining；它只排除了“推理约束修正本身足够”的解释，不支持内部情绪机制或人类认知结论
Thesis destination: Table-G2-4；错误分析的 neutral co-occurrence failure mode；讨论章节的 supervision/inference mismatch 与因果边界
```

### EXP-033: Target-Aligned LoRA, Seed 42

```text
Experiment ID: EXP-033
Tier / RQ: Major / RQ-G2
Status: Verified negative result；seed 42 formal train 与 validation 完成；seeds 43/44 未授权；test 未获取或读取
Dataset and protocol: DATA-GOE-V1；train 43,410 rows、dev 5,426 rows、28 labels；训练 target 保留全部 1,396 条 neutral+emotion
Provider and exact model: Qwen/Qwen3-1.7B revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e；本地未量化 MLX BF16
LoRA and training: final 16/28 blocks；q/k/v/o + gate/up/down；rank=8；4,980,736 trainable parameters；1 epoch；21,705 micro-iterations；4,341 optimizer updates；effective batch=10；constant lr=1e-5；seed=42
Training verification: duration=26,963.19 s；peak MLX memory=7.208 GB；initial/final loss window=0.4410/0.1618；112/112 LoRA-B tensors non-zero；真实 load/forward logits finite；train-only
Validation condition: final adapter；aligned prompt；open-neutral constrained label-name JSON；greedy；thinking off；max_new_tokens=64；每行一次；无 retry/repair；invalid-as-empty
Primary metric: dev Macro-P/R/F1=0.568150/0.386679/0.427959
Secondary metrics: Micro-F1=0.573055；Weighted-F1=0.549395；Samples-F1=0.584144；strict subset accuracy=0.501843；Hamming loss=0.034062；label accuracy=0.965938
Cardinality and parser: gold/predicted cardinality=1.175820/1.058054；parser=5,426/5,426=100%；empty rows=0；finish reason stop=5,426/5,426
Matched EXP-025 comparison: delta Macro-F1=+0.186795；paired 95% CI=[+0.166973,+0.205137]；repetition gate passed
Matched seed-42 target-alignment comparison: EXP-033 - EXP-029 adapter under EXP-031 aligned-open inference=-0.012678；paired 95% CI=[-0.026938,+0.001434]；预登记 improvement gate failed
BERT comparison: EXP-033 - EXP-020 three-seed mean=-0.061476；descriptive-only，非配对检验
Multi-label slice: 878 rows；subset accuracy=0.047836；Samples-F1=0.472096；gold/predicted cardinality=2.086560/1.145786
Neutral co-occurrence slice: 174 rows；subset accuracy=0；Samples-F1=0.561686；predicted neutral co-occurrence rows=0
Resource and cost: validation active duration=4,927.41 s（约 82.1 min）；peak MLX memory=3.868 GB；median generation=0.902 s/row；API cost USD 0
Adapter hash: c0077f484823970f0bbd507d63c605d51fbab6d770aaf03e95aeb1df8e7053ea
Artifacts: experiments/goemotions/qwen3-1.7b/preflight/exp-033-formal-gate-contract-v2.json；preflight/exp-033-seed42-validation-contract-v1.json；runs/exp-033-target-aligned-lora/seed-42/；runs/exp-033-target-aligned-lora/validation-seed-42-v1/
Reproduction command: run_target_aligned_formal_v2.py train --authorization preflight/exp-033-formal-authorization-v2.json；随后 run_target_aligned_validation_v1.py --contract preflight/exp-033-seed42-validation-contract-v1.json --contract-sha256 23e51743234c953d38d2ddf9905cc3af6eba6cb495713d971214fd48c971daa8
Verification command: verify_target_aligned_formal_training_v2.py --check；随后 verify_target_aligned_validation_v1.py --contract preflight/exp-033-seed42-validation-contract-v1.json --contract-sha256 23e51743234c953d38d2ddf9905cc3af6eba6cb495713d971214fd48c971daa8 --check
Verified by: formal training verification 与 validation verification 均 Passed；独立复算 adapter、训练轨迹、5,426 条预测、完整指标、切片、10,000 次 paired bootstrap、资源、隐私和哈希；test absent
Decision: target_alignment_improvement_not_established；实验完成且可复现，不是执行失败；观察下降超过 0.005 practical threshold，但 95% CI 跨 0
Result: 修复训练 target 的 ontology 失配没有在 seed 42 上提升全量 dev，也没有恢复 neutral 共现输出；模型仍明显偏向近单标签预测
Failure or caveat: 单 seed dev-only；不能推出 target alignment 永远无效，也不能将差异归因于单一内部机制；seeds 43/44、test、上下文与内部表征均未评估
Thesis destination: Table-G2-5；结果章节的 corrected retraining 负结果；讨论章节的 supervision mismatch、多标签读出偏差与负结果边界
```

### EXP-034: Train Neutral-co-occurrence Diagnostic

```text
Experiment ID: EXP-034
Tier / RQ: Minor / RQ-G2；parent=EXP-033
Status: Verified；仅回放最终 seed-42 adapter；不训练、不调参、不选 checkpoint；dev/test 未读取
Question: EXP-033 adapter 能否在训练时见过的全部 neutral+emotion 样本上复现该标签结构，还是 validation 的 0 共现主要来自 held-out generalization failure？
Dataset and slice: DATA-GOE-V1 train；完整 1,396 条 gold neutral+emotion；gold cardinality 2/3/4 标签分别为 1,335/60/1 条
Frozen inference: EXP-033 final seed-42 adapter；aligned training prompt；open-neutral constrained label-name JSON；greedy；thinking off；每行一次；无 retry/repair
Primary diagnostic: neutral co-prediction rows=0/1,396=0%；target-compatible co-prediction rows=0/1,396=0%
Cardinality: gold/predicted mean=2.044413/1.019341；预测为 1/2/3 标签的行数=1,370/25/1
Diagnostic metrics: subset accuracy=0；Samples-F1=0.537655；Macro-F1=0.308414；Micro-F1=0.535890；这些是训练切片记忆诊断，不是 held-out 性能
Validation reference: 174 条 neutral+emotion dev 样本同样 0 共现；predicted cardinality=1.017241；Samples-F1=0.561686；Macro-F1=0.231780
Resource and cost: active duration=1,255.98 s；peak MLX memory=3.879 GB；parser=1,396/1,396；API cost USD 0
Artifacts: experiments/goemotions/qwen3-1.7b/configs/exp-034-train-neutral-cooccurrence-diagnostic.json；runs/exp-034-train-neutral-cooccurrence-diagnostic/
Reproduction command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_train_neutral_cooccurrence_diagnostic.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/configs/exp-034-train-neutral-cooccurrence-diagnostic.json --config-sha256 bbef0d67bd05cfba813651652c2cb9f85158cd76ffa39dd324500934cf29236a
Verification command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_train_neutral_cooccurrence_diagnostic.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/configs/exp-034-train-neutral-cooccurrence-diagnostic.json --config-sha256 bbef0d67bd05cfba813651652c2cb9f85158cd76ffa39dd324500934cf29236a --check
Verified by: 独立 verifier 不导入 runner；重建冻结训练切片、重新解析全部 raw output、复算指标与共现统计、核对产物哈希和隐私字段；test absent；状态 Passed
Result: “只是不泛化到 held-out 样本”不足以解释失败；模型在已见训练样本上也没有学会输出 neutral+emotion 结构，表现为 under-learning 或近单标签生成偏差
Failure or caveat: 不能由此区分样本稀少、token-level loss、标签顺序、优化/LoRA 容量或 1.7B 模型容量；不支持内部机制结论
Decision consequence: 继续原样训练 EXP-033 seeds 43/44 的信息价值下降；下一步应先用新编号检验 exposure/objective，而不是把 seed 重复当作结构修复
Thesis destination: Table-G2-6；结果章节的 train-vs-dev structural diagnostic；讨论章节的 learnability、generation bias 与因果边界
```

### EXP-035: GoEmotions Neutral Co-occurrence Annotation Audit

```text
Experiment ID: EXP-035
Tier / RQ: Major / RQ-G2；parent=EXP-034
Status: Verified；只审计冻结 train allowlist；不训练、不推理、不调参；simplified dev/test 未读取
Question: 1,396 条 neutral+emotion target 是同一标注者直接共选，还是不同标注者判断经官方 >=2 票规则聚合后形成；单条文本的上下文与标签歧义有多大？
Data protocol: DATA-GOE-ANNOT-AUDIT-V1；官方 Google Research revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0
Transport boundary: 官方 raw annotations 以三个完整 CSV 发布，运行时流经 42,742,918 bytes 和 211,225 行；只持久化冻结 train allowlist 命中的 6,936 行逐标注者记录，非匹配字段不保留
Quantitative result: aggregation-only=1,396/1,396=100%；same-rater neutral+emotion co-selection=0/1,396；neutral 2/3 票=1,249/147 条；4/5 raters=44/1,352 条；含 unclear 投票=39/1,396=2.7937%
Aggregation reproduction: 官方 >=2 票阈值精确复现 1,396/1,396 条 simplified targets；mismatch=0
Qualitative sample: 冻结目的性抽样 48 条；standalone explicit/implicit/context-likely/indeterminate=24/14/6/4；cross-rater disagreement/genuine multilabel/unclear/uncertain=39/4/3/2；比例仅描述该目的性样本
Artifacts: experiments/goemotions/annotation-audit/configs/exp-035-neutral-cooccurrence-annotation-audit.json；runs/exp-035-neutral-cooccurrence-annotation-audit/
Reproduction command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/annotation-audit/run_annotation_audit.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/annotation-audit/configs/exp-035-neutral-cooccurrence-annotation-audit.json --config-sha256 babfa6094cc8e4300398cd209b8689b0a15039f530ffec47b391bdc0425f51bd
Verification command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/annotation-audit/verify_annotation_audit.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/annotation-audit/configs/exp-035-neutral-cooccurrence-annotation-audit.json --config-sha256 babfa6094cc8e4300398cd209b8689b0a15039f530ffec47b391bdc0425f51bd --check
Verified by: 独立 verifier 不导入 runner/finalizer；重建冻结 train allowlist，复算逐票聚合、全部公开 CSV/JSON、确定性抽样、48 条编码、报告、artifact hash 与隐私边界；最大数值差异 0；test absent
Result: neutral+emotion 异常结构的首要解释是跨标注者聚合，而不是单个标注者同时表达 neutral 与情绪；直接要求生成式模型复现该 hard target 混入了数据协议层冲突
Failure or caveat: 不能由此证明模型容量足够或上下文无关；48 条是目的性样本，6/48 的 context-likely 比例不可外推；未比较新的监督目标，也未访问 dev/test
Decision consequence: 不直接继续 EXP-033 seeds 43/44；下一步先预登记 official hard labels 与聚合分歧感知目标的受控设计，再决定是否值得完整重训
Thesis destination: Table-G2-7；数据与标注审计小节；讨论章节的 aggregated supervision、label semantics 与模型失败归因边界
```

### EXP-036: Dev Rater-aware Frozen-prediction Diagnostic

```text
Experiment ID: EXP-036
Tier / RQ: Major / RQ-G2；parent=EXP-035
Status: Verified；validation-only；不训练、不执行模型推理、不选择 checkpoint；test 未获取或读取
Question: 对 174 条 official neutral+emotion dev 样本，若按“与随机一名 clear annotator 的期望一致度”评分，Qwen 相对 BERT 的差距是否仍存在？
Data protocol: DATA-GOE-DEV-RATER-EVAL-V1；dev 5,426 rows；冻结 allowlist 174 rows；官方 Google Research revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0
Annotation integrity: raw per-rater rows=866；aggregation-only=174/174；same-rater neutral+emotion co-selection=0；含 unclear annotation 的样本=2；clear empty annotations=0；官方 >=2 票聚合 mismatch=0
Frozen predictions: EXP-020 BERT seeds 42/43/44；EXP-029 selected zero-shot seeds 42/43/44；EXP-033 target-aligned seed 42；共 7 份已验证 prediction files
Primary diagnostic metric: 每条样本先对 clear raters 的 set-F1 取平均，再对 174 条等权平均；不是 replacement ground truth，也不与 full-dev Macro-F1 比较
Family result: EXP-020 official/clear-rater set-F1=0.557982 +/- 0.007475 / 0.362531 +/- 0.002371；EXP-029=0.562261 +/- 0.031754 / 0.363250 +/- 0.017685
Primary paired comparison: EXP-029 - EXP-020 clear-rater set-F1=+0.000720，95% CI=[-0.018463,+0.019903]；46 win / 71 tie / 57 loss；classification=practical_tie_or_uncertain
Exact-match interpretation: official exact match BERT/Qwen=0.090038/0；clear-rater expected exact=0.231705/0.341284；any-clear-rater exact=0.591954/0.852490。聚合 hard target 会惩罚近单标签 Qwen 的 official exact match，但主 set-F1 比较没有发生 material shift
Secondary seed-42 result: EXP-033 - EXP-029 clear-rater set-F1=+0.007280，95% CI=[+0.000192,+0.016284]，6 win / 167 tie / 1 loss；这是单 seed、174-row slice 的局部差异，不建立整体模型优势
Artifacts: experiments/goemotions/disagreement-aware-evaluation/configs/exp-036-dev-rater-aware-diagnostic.json；runs/exp-036-dev-rater-aware-diagnostic/
Config SHA-256: 08ebf04951a164838072252ab1938447516b1ca8ead60f7134cda5809f88b2fb
Reproduction command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/run_rater_aware_evaluation.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/configs/exp-036-dev-rater-aware-diagnostic.json --config-sha256 08ebf04951a164838072252ab1938447516b1ca8ead60f7134cda5809f88b2fb
Verification command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/verify_rater_aware_evaluation.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/configs/exp-036-dev-rater-aware-diagnostic.json --config-sha256 08ebf04951a164838072252ab1938447516b1ca8ead60f7134cda5809f88b2fb --check
Verified by: 独立 verifier 不导入 runner；重建 174 条 dev allowlist、逐标注者 scoring view 与 7 份预测，复算 1,218 条样本级分数、family summaries、三组 paired bootstrap、报告、artifact hash 和隐私边界；最大数值差异 0；test absent
Result: 在这个跨标注者冲突切片上，没有证据表明 EXP-029 的期望逐标注者 set-F1 低于 BERT；同时 official exact-match 的 0 分主要反映它没有输出 aggregate union。该结论不能外推为 Qwen 在完整 GoEmotions dev 上追平 BERT
Failure or caveat: 只覆盖目的性定义的 174 条；annotator agreement 不等于语义真值；raters 未见上下文；bootstrap 只重采样样本而不覆盖训练 seed 不确定性；不能支持内部机制结论
Decision consequence: 不因这 174 条继续重训以强制生成 neutral+emotion；当时登记的下一依赖是扩展相同评分到完整 dev，该依赖现已由 EXP-037 完成
Thesis destination: Table-G2-8；结果章节的 disagreement-aware diagnostic；讨论章节的 aggregated supervision、evaluation target 与 single-label generation bias 边界
```

### EXP-037: Full-dev Rater-aware Frozen-prediction Diagnostic

```text
Experiment ID: EXP-037
Tier / RQ: Major / RQ-G2；parent=EXP-036
Status: Verified；validation-only；不训练、不执行模型推理、不选择 checkpoint；test 未获取或读取
Question: 把逐标注者评分扩展到完整 5,426 条 dev 后，标注聚合是否足以解释 EXP-029 相对 EXP-020 的总体性能差距？
Data protocol: DATA-GOE-FULL-DEV-RATER-EVAL-V1；全部 dev 5,426 rows；官方 Google Research revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0
Annotation integrity: raw per-rater rows=19,440；clear-rater label set 存在分歧=4,596/5,426=84.7033%；official aggregate target 不匹配任何 clear individual rater=509/5,426=9.3808%；含 unclear annotation 的样本=203；官方 >=2 票聚合 mismatch=0
Frozen predictions: EXP-020 BERT seeds 42/43/44；EXP-029 selected zero-shot seeds 42/43/44；EXP-033 target-aligned seed 42；共 7 份已验证 prediction files
Primary diagnostic metric: 用每个标签在 clear raters 中的投票比例作为 soft target 计算 Macro-F1；同时报告逐样本 clear-rater expected set-F1。二者都不是 replacement ground truth，也不用于模型选择
Family result: EXP-020 official/soft Macro-F1=0.489435 +/- 0.011063 / 0.383471 +/- 0.005210，expected rater set-F1=0.485977 +/- 0.001770；EXP-029=0.451374 +/- 0.019213 / 0.347253 +/- 0.014667，expected rater set-F1=0.475587 +/- 0.006934
Primary paired comparison: EXP-029 - EXP-020 official Macro-F1 delta=-0.038061，95% CI=[-0.053195,-0.024016]；soft Macro-F1 delta=-0.036218，95% CI=[-0.043834,-0.029494]；soft-vs-official shift=+0.001843，95% CI=[-0.006779,+0.011015]；classification=gap_remains；material shift=false
Expected-rater comparison: EXP-029 - EXP-020 expected set-F1=-0.010390，95% CI=[-0.015616,-0.005010]；1,404 win / 2,403 tie / 1,619 loss。逐标注者评分仍未消除总体差距
Secondary seed-42 result: EXP-033 - EXP-029 soft Macro-F1=-0.005071，95% CI=[-0.011047,+0.000365]，classification=practical_tie_or_uncertain；expected set-F1=+0.004741，95% CI=[+0.001449,+0.008017]。单 seed、不同指标方向不一致，不建立 EXP-033 优势
Artifacts: experiments/goemotions/disagreement-aware-evaluation/configs/exp-037-full-dev-rater-aware-diagnostic.json；runs/exp-037-full-dev-rater-aware-diagnostic/
Config SHA-256: 34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d
Reproduction command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/run_full_dev_rater_aware_evaluation.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/configs/exp-037-full-dev-rater-aware-diagnostic.json --config-sha256 34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d
Verification command: python3 projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/verify_full_dev_rater_aware_evaluation_v2.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/disagreement-aware-evaluation/configs/exp-037-full-dev-rater-aware-diagnostic.json --config-sha256 34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d --check
Verifier correction: 原冻结 verifier 首次核验仅因 JSON 把整数分布键序列化为字符串而停止；未修改 runner、config、protocol 或运行产物。V2 wrapper 只规范化该键类型后委托原 verifier 的数据、指标、bootstrap、产物和隐私检查，修正记录见 protocols/exp-037-verifier-correction-2026-08-04.md
Verified by: V2 verifier 独立重建 5,426 条 dev、19,440 行逐标注者记录与 7 份预测，复算 588 行逐标签指标、三组 paired comparison、2,000/10,000 次 bootstrap、报告、artifact hash 和隐私边界；最大数值差异 5.1159e-13；test absent
Result: 标注聚合会改变局部标签语义和部分样本的得分，但不能解释 EXP-029 与 BERT 的完整 dev 总体差距；EXP-036 的 174-row practical tie 是真实的局部边界，不可外推
Failure or caveat: rater disagreement 不是正式的 inter-annotator agreement 估计，也不等于潜在人类情绪真值；raters 未见会话上下文；bootstrap 重采样样本而非训练 seed；这是行为证据，不支持内部机制结论
Decision consequence: 不把 vote-distribution/soft-target 重训作为默认性能修复。若继续行为主线，优先冻结论坛数据与上下文协议；若继续表征主线，需在 EXP-028 Failed 之后登记资源可行的新 probe
Thesis destination: Table-G2-9；结果章节的 full-dev disagreement-aware control；讨论章节的局部标注语义效应与总体模型性能差距边界
```

### EXP-038: GoEmotions Frozen Formal Test Gate

```text
Experiment ID: EXP-038
Tier / RQ: Major / RQ-G1 + RQ-G2
Status: Verified；official test 已消费；9 个冻结单元各执行一次；无 test 后调参、模型选择或重跑
Data: DATA-GOE-V1 official test；5,427 rows；28 标签多标签；upstream revision 8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0；test SHA-256 0587b2dd8b27b97352adbfc3fb083d46005c8946657fdc2b1ca8b1cc7f1f8be4
Frozen config: experiments/goemotions/test-gate/configs/exp-038-frozen-test.json；SHA-256 87177da88dfb1ebb9bc78a71ac11aca87b8b85c98b126f40bb9c056eba316b0f
Primary metric: 28-label Macro-F1
EXP-018 result: Macro-F1=0.196197；Micro-F1=0.382080；Weighted-F1=0.334114；subset accuracy=0.250046
EXP-020 result: Macro-F1=0.488328 +/- 0.008771；Micro-F1=0.590427 +/- 0.001634；Weighted-F1=0.587884 +/- 0.002594；subset accuracy=0.443032 +/- 0.005061；3 seeds
EXP-025 result: Macro-F1=0.233653；Micro-F1=0.249278；Weighted-F1=0.267550；subset accuracy=0.112032；single run
EXP-029 result: Macro-F1=0.450652 +/- 0.032175；Micro-F1=0.579031 +/- 0.005213；Weighted-F1=0.555956 +/- 0.007159；subset accuracy=0.513543 +/- 0.009738；3 seeds；historical ontology-misaligned control
EXP-033 result: Macro-F1=0.444675；Micro-F1=0.580163；Weighted-F1=0.559297；subset accuracy=0.513175；single seed；primary target-aligned LLM result
Paper reference: GoEmotions BERT test Macro-F1=0.46；EXP-020 delta=+0.028328；同一 official split 和 full taxonomy，但现代 PyTorch/Transformers/MPS 与原 TensorFlow Estimator 实现不同，不声称 bitwise reproduction
Main comparison: EXP-029 - BERT=-0.037676 Macro-F1；EXP-033 - BERT=-0.043653；EXP-033 - historical EXP-029 seed 42=+0.001032，仅为单 seed 描述性差异
Generation resources: EXP-025 parser valid=99.9816%，median=0.949 s/row，peak=3.723 GB；EXP-029 三 seed parser=100%，median=0.729-0.811 s/row，peak=4.006 GB；EXP-033 parser=100%，median=0.763 s/row，peak=4.030 GB；API cost USD 0
Artifacts: experiments/goemotions/test-gate/runs/exp-038-frozen-test/；REPORT.md；condition-summary.csv；aggregate-metrics.json；各单元匿名 predictions、per-label metrics 和 confusion matrices
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/goemotions/test-gate/verify_frozen_test.py --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/test-gate/configs/exp-038-frozen-test.json --config-sha256 87177da88dfb1ebb9bc78a71ac11aca87b8b85c98b126f40bb9c056eba316b0f
Verifier correction: 注册 verifier 把生成 JSON 中的 label 顺序与 multi-hot 恢复出的 ID 排序直接比较，在 EXP-025 row 9 因同集合异序停止；EXP-038-VERIFY-V2 只增加 ID 类型、范围、唯一性检查并比较排序后的集合，不改变任何科学产物。原/新 verifier hash 均保存在 amendment 与 verification.json
Verified by: 独立重建全部 9 个 5,427 x 28 矩阵，复算 aggregate/per-label metrics 和 confusion matrices，核对公开产物哈希、隐私边界、test 行数、冻结 config、无 post-test tuning 和无 model selection；status=Verified
Result: BERT 是 primary metric 最强条件；1.7B LoRA 的 exact match 较高但 Macro-F1 较低，且预测标签基数偏低。GoEmotions 公开行为复现阶段可关闭，下一主线转向论坛数据和线程上下文
Failure or caveat: EXP-029 ontology 失配；EXP-033 只有一个 seed；test 已消费，不能再用于任何开发；分类表现不支持内部情绪机制或人类情感生成结论
Thesis destination: Table-G2-10；GoEmotions final test comparison；讨论章节的 dev-to-test 泛化、generative classifier trade-off、ontology 与证据边界
```

### EXP-047: Weibo EClass Matched Generative-LoRA Validation

```text
Experiment ID: EXP-047
Tier / RQ: Major / RQ-F1
Status: Verified；matched validation completed；sealed test 未访问
Data: DATA-WEIBO-TASK-V1 validation；1,272 rows；7 类单标签；335 个 group_id；target-only view
Model/runtime: Qwen3-4B post-trained；本地 MLX BF16；reasoning on；greedy singleton；同 prompt、parser、token budget 与模型文件
Conditions: matched no-adapter reference；epoch-2 LoRA adapters for seeds 42/43/44
Primary metric: 7-label Macro-F1
Reference result: Macro-F1=0.333598；Accuracy=0.222484；Weighted-F1=0.207222；parser-valid=90.8805%
LoRA seed results: Macro-F1=0.552028/0.548289/0.587096；Accuracy=0.768082/0.786164/0.783805；Weighted-F1=0.773339/0.770574/0.779033；parser-valid=100% for all seeds
Primary contrast: LoRA Macro-F1 mean=0.562471 +/- 0.021408；mean delta vs matched reference=+0.228873；frozen decision=material_improvement；threshold=0.005
Bootstrap: 2,000 group_id resamples；seed-42 delta 95% CI=[0.168960,0.272580]；seed-43=[0.153160,0.275628]；seed-44=[0.191876,0.308171]；三者 P(delta>0)=1.0
Historical encoder comparison: EXP-042 M2 target-only Macro-F1=0.594925 +/- 0.012919；EXP-047 LoRA mean delta=-0.032454，仅为同 split、同任务但跨架构的描述性差值
Resources: four-condition command time=87,122.823 s；reference=79,098.411 s；LoRA seeds=2,814.599/2,568.905/2,640.908 s；maximum peak memory=8.498 GB；API cost USD 0
Artifacts: experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/；公开 aggregate/report/verification 与私有 4 x 1,272 row-level predictions
Verification command: /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-generative-lora/verify_matched_validation.py --check
Verified by: EXP-047-MATCHED-VALIDATION-VERIFY-V1 重建 5,088 次生成及全部指标、bootstrap、资源、权限和 split boundary；10 类检查、0 mismatch
Result: 监督 LoRA 对 matched frozen Qwen 产生明确且跨三 seed 稳定的行为收益，并把严格格式有效率提升到 100%；但三 seed 均值仍未超过 EXP-042 中文 encoder
Failure or caveat: reference 的长 reasoning 造成 116 条疑似截断和约 21.97 小时耗时；LoRA 的极短输出同时改变了分类和生成行为，不能把收益解释为忠实推理或内部情绪机制；validation 已用于开发，不能声称 held-out 泛化
Decision consequence: 进入冻结 dev 错误分析，重点检查少数类、no_emotion 多数类、格式恢复与真实分类收益；完成后再决定 TEST-READY，不直接读取 sealed test
Thesis destination: Table-F1-3；Weibo 同任务 Stage 5 主比较；讨论章节的 LLM task adaptation、encoder gap、格式与成本边界
```

### EXP-048: Frozen Weibo EClass Dev Error Analysis

```text
Experiment ID: EXP-048
Tier / RQ: Major / RQ-F1
Status: Verified；validation-only descriptive analysis；sealed test 未访问
Data: DATA-WEIBO-TASK-V1 validation；1,272 rows；7 类单标签；同一冻结 gold 与行顺序
Frozen predictions: EXP-047 matched no-adapter reference；EXP-047 LoRA seeds 42/43/44；EXP-042 M2 target-only seeds 42/43/44
Primary questions: LoRA 增益是否只来自格式恢复；LoRA 与 encoder 的剩余差距位于哪些类；错误是否跨 seed 稳定；预抽样原文显示哪些可能因素
Aggregate results: reference/LoRA/encoder Macro-F1=`0.333598`/`0.562471`/`0.594925`；Accuracy=`0.222484`/`0.779350`/`0.792453`
Format attribution: 116 条 reference output failures；该 slice 的 Accuracy 增益贡献 `+0.070755`；1,156 条 valid-output slice 贡献 `+0.486111`；合计 `+0.556866`
Valid-output control: reference vs LoRA Accuracy=`0.244810` vs `0.779700`；Macro-F1=`0.342027` vs `0.577793`；640 条 reference valid-but-wrong 样本被 3/3 LoRA seeds 稳定恢复
Encoder gap: LoRA minus encoder Macro-F1=`-0.032454`，Accuracy=`-0.013103`；sadness/neutral/anger/positive 的逐类 F1 差分别为 `-0.084593`/`-0.065775`/`-0.039949`/`-0.029494`
Stability: LoRA 904 条 all-seed correct、201 条 all-seed wrong、167 条 mixed；encoder 为 970/224/78；LoRA/encoder pairwise final-label agreement mean=`0.884`/`0.943`
Qualitative review: 冻结目的性抽样 48 条；primary possible source 为 annotation_data_uncertainty 21、overlapping_label_ontology 13、model_representation_limitation 9、missing_local_context 2、surface_form_noise 2、output_parser_or_policy 1
Artifacts: experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/；公开 protocol/config/aggregate/tables/report/verification，私有 selected cases 与原文隔离
Verification: 独立实现复算 7 份预测、1,272 行、9 份 CSV、3 份 JSON、48 条编码、哈希和权限；maximum absolute numeric difference=0，公开 raw leak=0
Result: EXP-047 的行为收益包含显著的有效输出行标签改善，不只是 parser/truncation 修复；但 encoder 在少数类、边界类和稳定性上仍有优势
Failure or caveat: 定性案例是六类目的性抽样，不是总体随机样本；人工代码只表示可能解释，不能改 gold、证明因果或推出 hidden-state/人类情绪机制
Decision consequence: 不继续 validation 调参或启动迁移；下一步冻结 TEST-READY 候选、模型/prompt/parser/metrics/slices 和一次性 test 合同，等待用户单独授权
Thesis destination: Table-F1-4；Weibo 错误结构、格式归因、少数类与 ontology 边界；讨论章节的生成式 LLM 与 encoder trade-off
```

### EXP-049: Weibo EClass Frozen Formal Test Gate

```text
Experiment ID: EXP-049
Tier / RQ: Major / RQ-F1
Status: Frozen / Verified / Consumed；正式 test 已消费
Data: DATA-WEIBO-TASK-V1 test；1,273 rows；337 leakage groups；七类单标签
Frozen units: M0 majority；M1 target-only LinearSVC；Chinese RoBERTa-WWM-ext seeds 42/43/44；Qwen3-4B matched no-adapter reference；generative LoRA seeds 42/43/44
Access order: 九个单元全部完成 test predictions 后，finalizer 才一次性打开 test labels；标签打开后无模型调用
Primary metric: Macro-F1；补充 Accuracy、Macro-P/R、Weighted-F1、逐类指标、混淆矩阵和预注册切片
Unit results: M0=`0.116937`；M1=`0.374762`；encoder seeds=`0.655028/0.641233/0.652603`；reference=`0.316921`；LoRA seeds=`0.623451/0.625046/0.661339`
Family results: encoder Macro-F1=`0.649621 +/- 0.007365`，Accuracy=`0.829013 +/- 0.006349`；LoRA Macro-F1=`0.636612 +/- 0.021429`，Accuracy=`0.824823 +/- 0.009811`
Frozen contrasts: encoder-M1=`+0.274860`，CI=`[+0.226927,+0.324054]`；LoRA-reference=`+0.319691`，CI=`[+0.274779,+0.362068]`；LoRA-encoder=`-0.013009`，CI=`[-0.045671,+0.024011]`
Parser/cost: reference parser-valid=`91.4375%`、生成约 `20.89 h`；三个 LoRA 均为 100% valid，三次生成合计约 `2.31 h`
Verification: 独立实现复算 1,273 gold rows、9 个预测文件、11,457 条逐行预测、全部指标/切片/逐类/混淆矩阵和三组 2,000 次 group bootstrap；10 类检查、0 mismatch
Privacy: row-level predictions、source IDs、原文、gold labels 与 Qwen reasoning 保持私有；10 个私有文件均 ignored/untracked；公开 raw text/source ID leak=0
Incident: 首次 finalizer 已完成单次标签打开和全部指标落盘，但在报告渲染时因 non-generative parser 为 JSON null 抛错；使用只读取持久化 aggregate 的 recovery 生成报告并记录修复，未重开标签、未重跑模型或指标
Result: 监督 LoRA 的 test 收益相对 matched frozen Qwen 明确泛化；LoRA 与强 encoder 的总体表现接近，但点估计低 `0.013009` 且置信区间跨 0，不能声称任一方具有确定优势
Failure or caveat: frozen decision rule 把点估计低于 `-0.005` 记为 material_degradation，但统计区间跨 0；seed 44 的单次 LoRA 分数最高也不得被事后选为“最佳模型”；行为结果不支持内部机制结论
Decision consequence: Weibo test 永久标记为 consumed；只允许对冻结预测做预登记、只读的 post-test analysis，禁止据此修改 prompt、parser、threshold、checkpoint、seed 或模型族
Thesis destination: Table-F1-5；Weibo 正式 test 主表、泛化对比、成本/格式权衡与 test-gate 方法
```

### EXP-050: Stack Overflow Shared Model Preflight

```text
Experiment ID: EXP-050
Tier / RQ: Minor / RQ-S1
Status: Verified；train-only；validation/test 未访问；不含性能评价
Data: DATA-SO-TASK-V1 train；24 条确定性 smoke 样本；六标签均至少 2 个正例，5 条 neutral，4 条 cardinality-2
Frozen contract: EXP-051 M1 RoBERTa；EXP-052 M2 Frozen Qwen + Linear(2560,6)；EXP-053 M3 Classification LoRA + matched head；EXP-054 M4 Generative LoRA
Model/runtime: FacebookAI/roberta-base revision e2da8e2f...；Qwen/Qwen3-4B revision 1cfa9a72...；PyTorch CPU 与 MLX BF16 Apple Metal；offline only
Prompt/input: target-only；thinking off；Qwen final-layer last input token after empty-think wrapper；RoBERTa/Qwen max lengths 256/384
Static result: 完整 3,360-row train 的 token maximum 为 RoBERTa 222、Qwen 341；无截断；数据、prompt、tokenizer 与模型 manifest hash 全部匹配
M1 result: 2 x 12 samples；logits [12,6]；finite BCE；classification head changed
M2 result: frozen Qwen；pooled/logit shape [1,2560]/[1,6]；15,366 trainable head parameters；2 steps；peak 8.247 GB
M3 result: M2/M3 matched head and zero-step logits；zero initial LoRA function delta；112 insertions in blocks 20-35；7,340,032 LoRA + 15,366 head parameters；112/112 lora_b nonzero after 2 steps；peak 8.538 GB
M4 result: M3/M4 matched LoRA initialization；assistant-only mask；2 finite loss steps；112/112 lora_b nonzero；4 greedy outputs, 0 retries, 0/4 canonical-valid；peak 8.910 GB
Incident: first attempt stopped before LoRA insertion/optimizer step because M2 wrapper-scoped and M3 head-scoped parameter names produced different hashes for matched tensors；correction unified digest scope only；failed attempt retained and successful chain restarted from static
Resources: successful stage wall time total 44.18 s；API/network cost USD 0
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-050-shared-model-preflight/；REPORT.md；run.json；five stage reports；verification.json；frozen runner/config/prompt/parser/verifier
Verification command: /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/verify_preflight.py
Verified by: independent selection/tokenization/parameter/init/update/parser/privacy/resource/access audit；77/77 checks；model-preflight unit tests 7/7
Result: EXP-051 至 EXP-054 的本地实现与共享合同可以进入正式性能实验；下一步是 EXP-051 seed 42 train + validation 完整性门
Failure or caveat: 两个 optimizer steps 不代表收敛；M4 0/4 valid 不是正式格式率；没有 Accuracy/Macro-F1，不能比较 M1-M4、支持泛化或推出内部情绪机制
Thesis destination: 方法章节的实现与可复现性；不进入主性能结果表
```

### EXP-051: Stack Overflow M1 RoBERTa Three-Seed Validation

```text
Experiment ID: EXP-051
Tier / RQ: Major / RQ-S1；seeds 42/43/44 family completed
Status: Verified；train + validation；test 未访问；EXP-052 未授权
Data: DATA-SO-TASK-V1 train/validation=3,360/720；702 validation duplicate components；六标签多标签
Model: FacebookAI/roberta-base revision e2da8e2f...；全参数 float32；BCEWithLogitsLoss
Training: 5 epochs；batch 16；AdamW 2e-5；10% warmup + linear decay；1,050 optimizer steps
Selection: 按 fixed-0.5 Macro-F1 冻结 practical-tie rule 选择 epoch 4/4/5；seed 42/43/44 共享阈值分别为 0.25/0.30/0.50
Seed-42 result: fixed/shared Macro-F1=0.598759/0.604619；shared Micro-F1=0.764645；strict subset accuracy=0.740278；bootstrap 95% CI=[0.559703,0.638948]
Seed-43 result: fixed/shared Macro-F1=0.601329/0.625341；shared Micro-F1=0.774869；strict subset accuracy=0.758333；bootstrap 95% CI=[0.580438,0.661573]
Seed-44 result: fixed/shared Macro-F1=0.621803/0.621803；shared Micro-F1=0.773903；strict subset accuracy=0.783333；bootstrap 95% CI=[0.574086,0.660818]
Three-seed aggregate: fixed/shared Macro-F1=0.607297 +/- 0.012628 / 0.617254 +/- 0.011084；Micro-F1=0.766270 +/- 0.009590 / 0.771139 +/- 0.005645；strict subset accuracy=0.773611 +/- 0.011369 / 0.760648 +/- 0.021621
Low-support result: 三 seed 的 surprise support=7、predicted support=0、F1=0；shared five-label Macro-F1 aggregate=0.740705 +/- 0.013301，仅作敏感性分析
Incident: 首次 MPS attempt 在 epoch 1 内 OOM，未完成一个 epoch 或产生 validation 性能；失败目录保留，不关闭 allocator safety limit
Recovery/resources: seed 42 的 10-step train-only CPU preflight 通过后从头运行；seed 42/43/44 wall=30.99/32.22/30.94 min、peak RSS=6.42/5.24/5.36 GB；API/network cost=0
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/；experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/；experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-44/；experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-three-seed-validation/；私有 checkpoint/predictions Git ignored
Verification: 三 seed 均执行 independent checkpoint replay、probability/metric/threshold/bootstrap/hash/privacy/access audit；分别 67/67、72/72、72/72 checks passed；aggregate 由独立公式与源哈希复算 53/53 通过；当前 model-comparison tests 23/23
Result: EXP-051 M1 三 seed validation family 已冻结；共享阈值提高描述性 Macro-F1，但降低 strict subset accuracy，不构成统一指标改善
Failure or caveat: surprise 三 seed 均未识别；shared threshold 是 validation calibration；CPU/MPS 不声称 bitwise 等价；尚无 test 或跨模型比较
Decision consequence: 不改 M1、不读 test；下一步只能在独立授权后执行 EXP-052 M2 Frozen Qwen + linear head
Thesis destination: 方法章节的恢复与复现性记录；结果章节的 M1 validation baseline、阈值权衡与低频标签失败
```

### EXP-052: Stack Overflow M2 Frozen Qwen Seed-42 Validation Gate

```text
Experiment ID: EXP-052
Tier / RQ: Major / RQ-S1；seed 42 integrity gate completed
Status: Verified；train + validation；test、seeds 43/44、EXP-053/054 未授权
Data: DATA-SO-TASK-V1 train/validation=3,360/720；3,277/702 duplicate components；六标签多标签
Model: Qwen/Qwen3-4B revision 1cfa9a72...；MLX BF16 未量化；thinking off；max length 384；final-layer last input token pooling
Head/training: frozen Qwen + bias-enabled Linear(2560,6)，15,366 trainable parameters；2 epochs；batch 1；AdamW 1e-4、weight decay 0.01；6,720 optimizer steps；unweighted BCE
Preflight: attempt 4 的 24 条 train-only dry-run 通过 51/51；计入完整 extraction 开销后的 1.5x 安全投影=65.24 min；峰值 MLX=8.18 GB；validation/test 未访问
Selection: epoch 2；固定 0.5 Macro-F1=0.183391；共享阈值=0.25
Shared-threshold result: Macro-F1=0.324929；Micro-F1=0.509700；weighted F1=0.480957；strict subset accuracy=0.477778；hamming loss=0.128704；bootstrap 95% CI=[0.282747,0.370449]
Fixed-threshold tradeoff: Macro-F1=0.183391、subset accuracy=0.581944、hamming loss=0.086806；校准改善 Macro-F1/Micro-F1，但降低 exact match 并提高 hamming loss
Per-label result at shared threshold: love=0.583333；anger=0.555184；sadness=0.375000；joy=0.254237；fear=0.181818；surprise=0
Low-support result: surprise support=7、predicted support=0；五标签 Macro-F1=0.389915，说明总体弱表现不只由 surprise 造成
Matched descriptive comparison: 同 seed M1 shared-threshold Macro-F1=0.604619，M2-M1=-0.279691；Micro-F1/subset accuracy 同样更低
Resources: feature extraction=2,387.75 s；head training=3.76 s；total=2,400.09 s；peak MLX=8.23 GB；API/network cost=0；train/validation truncated rows=0/0
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/；private feature caches、head checkpoints、probabilities 与 row-level labels Git ignored
Verification: independent token/order/hash/feature/batch/head replay/checkpoint/threshold/metric/bootstrap/privacy/split audit；70/70 passed；selected-head probability replay max absolute error=0；EXP-052 tests 11/11 including real MLX checkpoint round-trip
Incident/correction: 首个受限 dry-run 因无 Metal 中止，attempt 2 暴露 `mlx` namespace path 假设；attempt 3 运行成功。正式运行前的只读审计又发现 formal gate 可空、失败 verifier 可能 KeyError、source audit 范围过窄和成本漏算非-forward 开销；修正后用全新 attempt 4 重跑并重新绑定所有源码与 gate hash，不覆盖旧尝试
Result: 当前 frozen Qwen final representation 在该固定线性 head 下只呈现较弱的六标签可解码性，明显落后同 seed RoBERTa；这是有验证的单 seed 负结果
Failure or caveat: 不能由单 seed 宣称 M2 family 已完成，不能把 linear-probe 弱表现写成 Qwen 没有情绪信息，更不能预判 classification LoRA 的增量收益；shared threshold 只在 validation 选择
Decision consequence: 不读 test、不启动 M3/M4；先冻结 seed-42 对照和 feature-cache 复用边界，再由独立授权决定 M2 seeds 43/44
Thesis destination: 结果章节的 M2 单 seed 完整性与负结果；方法章节的冻结表征、线性 probe、资源与验证边界
```

### EXP-052: Verified Feature-cache Reuse Gate

```text
Experiment ID: EXP-052 infrastructure gate / RQ-S1
Status: Verified；74/74 independent checks；无训练、无性能指标、无 Qwen forward、test 未访问
Source: EXP-052 seed 42 train/validation run + 70/70 verification，均以 SHA-256 绑定
Cache: train=(3360,2560)、validation=(720,2560)，float32、all finite、Git ignored、mmap_mode=r
Bound invariants: DATA-SO-TASK-V1 文件与顺序、Qwen revision/manifest、BF16、prompt/chat template/tokenizer、thinking off、max length、truncation、pooling、token stream
Allowed use: 仅 EXP-052 M2 seeds 43/44，且每个 seed 需独立授权；两者已分别按 EVID-052/EVID-053 消费一次，consumer 使用前后 cache hash 均不变
Forbidden reuse: EXP-053/M3、EXP-054/M4、context、router、test，或任何改变数据/模型/prompt/tokenization/pooling/precision 的运行
Seed isolation: head initialization、batch order、optimizer state、checkpoint、validation probability 与 bootstrap 必须为每个 seed 新生成
Artifact: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/
Decision consequence: seeds 43/44 的独立只读 consumers 与后续 M2 三 seed aggregate 均已完成；该 cache 不再授权新的用途，下一步只能另行登记 M3，M4 与 test 保持密封
Thesis destination: 方法章节的计算复用与可复现性边界；不进入性能结果表
```

### EXP-052: Stack Overflow M2 Seed-43 Cached-head Validation

```text
Experiment ID: EXP-052
Tier / RQ: Major / RQ-S1；seed 43 cached-head integrity gate completed
Status: Verified；train + validation；test、seed 44、EXP-053/054 未授权
Source cache: seed-42 verified train=(3360,2560)、validation=(720,2560) float32 hidden states；mmap_mode=r；运行前后 SHA-256 不变
Head/training: fresh seed-43 bias-enabled Linear(2560,6)，15,366 trainable parameters；2 epochs；batch 1；AdamW 1e-4、weight decay 0.01；6,720 optimizer steps；unweighted BCE
Preflight: attempt 1 因扁平 artifact 记录被错误当成嵌套结构而在训练前停止；无 checkpoint、性能指标或 test 访问。修复后的全新 attempt 通过 73/73
Selection: epoch 2；固定 0.5 Macro-F1=0.133610；共享阈值=0.20
Shared-threshold result: Macro-F1=0.353593；Micro-F1=0.537969；weighted F1=0.534761；strict subset accuracy=0.470833；hamming loss=0.116898；bootstrap 95% CI=[0.315104,0.392166]
Fixed-threshold result: Macro-F1=0.133610；Micro-F1=0.341549；weighted F1=0.301429；strict subset accuracy=0.526389；hamming loss=0.086574
Per-label result at shared threshold: love=0.663573；anger=0.559748；sadness=0.421053；joy=0.366071；fear=0.111111；surprise=0
Low-support result: surprise support=7、F1=0；五标签 Macro-F1=0.424311
Seed-42 comparison: fixed Macro-F1 delta=-0.049782；shared-threshold Macro-F1 delta=+0.028664；shared Micro-F1 delta=+0.028269；shared subset accuracy delta=-0.006944
Matched M1 comparison: 同 seed M1 shared-threshold Macro-F1=0.625341；M2-M1=-0.271748
Resources: cache validation=0.063 s；head training=3.266 s；total=4.233 s；peak MLX=0.000611 GB；process RSS=0.156254 GB；Qwen load/forward/extraction=0；API cost=0
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/；private checkpoint、probabilities 与 row-level labels Git ignored
Verification: corrected preflight 73/73；formal independent verifier 99/99；EXP-052 regression suite 26/26；cache hash before/after equal；selected-head replay and metrics exact
Result: 第二个 seed 仍显示 frozen final-layer representation 的线性可解码性远弱于 M1，但阈值选择改变了两 seed 的排序，显示明显 calibration/seed 敏感性
Failure or caveat: 两 seed 不能替代预注册三 seed aggregate；不能将弱 linear probe 归因为 Qwen 没有情绪信息；shared threshold 只在 validation 选择
Decision consequence: 不读 test、不启动 M3/M4；下一步只可在独立授权后执行 seed 44 的同一只读 cache consumer
Thesis destination: 结果章节的 M2 逐 seed、校准敏感性与计算复用；方法章节的只读 feature reuse 和独立验证
```

### EXP-052: Stack Overflow M2 Seed-44 Cached-head Validation

```text
Experiment ID: EXP-052
Tier / RQ: Major / RQ-S1；seed 44 cached-head integrity gate completed
Status: Verified；train + validation；完成本 gate 时 M2 aggregate 尚未授权，后续聚合见 EVID-054；test、EXP-053/054 未授权
Source cache: seed-42 verified train=(3360,2560)、validation=(720,2560) float32 hidden states；mmap_mode=r；运行前后 SHA-256 不变
Prerequisite: seed-43 formal run Completed 且 verifier 99/99；run/verification 文件大小与 SHA-256 在授权中冻结
Head/training: fresh seed-44 bias-enabled Linear(2560,6)，15,366 trainable parameters；2 epochs；batch 1；AdamW 1e-4、weight decay 0.01；6,720 optimizer steps；unweighted BCE
Preflight: seed-specific consumer preflight 通过 78/78；没有训练、性能指标、Qwen load/forward/extraction 或 test 访问
Selection: epoch 2；固定 0.5 Macro-F1=0.137657；共享阈值=0.25
Shared-threshold result: Macro-F1=0.278145；Micro-F1=0.494538；weighted F1=0.431140；strict subset accuracy=0.523611；hamming loss=0.117824；bootstrap 95% CI=[0.240756,0.314903]
Fixed-threshold result: Macro-F1=0.137657；Micro-F1=0.426426；weighted F1=0.321665；strict subset accuracy=0.572222；hamming loss=0.088426
Per-label result at shared threshold: love=0.574431；anger=0.536000；sadness=0.415584；fear=0.142857；joy=0；surprise=0
Low-support result: surprise support=7、F1=0；五标签 Macro-F1=0.333774；joy support=74 但 F1 仍为 0，因此不能把全部弱表现归因于 surprise
Prior-seed comparison: shared-threshold Macro-F1 相对 seeds 42/43 为 -0.046783/-0.075447；fixed Macro-F1 相对 seed 43 为 +0.004048，固定与校准后排序再次不同
Matched M1 comparison: 同 seed M1 shared-threshold Macro-F1=0.621803；M2-M1=-0.343658
Resources: cache validation=0.067 s；head training=3.739 s；total=4.791 s；peak MLX=0.000611 GB；process RSS=0.161022 GB；Qwen load/forward/extraction=0；API cost=0
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/；private checkpoint、probabilities 与 row-level labels Git ignored
Verification: consumer preflight 78/78；formal independent verifier 104/104；EXP-052 regression suite 28/28；cache hash before/after equal；selected-head replay、metrics 与 2,000 次 component bootstrap exact
Result: 第三个 seed 仍显示 frozen final-layer representation 在固定线性 head 下明显弱于 M1，并将 seed/calibration 敏感性从两 seed 警告扩展到完整的三个单 seed 证据
Failure or caveat: 本 gate 完成时，三个单 seed 仍不能替代尚未登记的 arithmetic mean/sample-std aggregate；后续 EVID-054 已补齐该聚合。单 seed 结果仍不能写成 Qwen 没有情绪信息或 LoRA 不会改善；shared threshold 只在 validation 选择
Decision consequence: 本 gate 不读 test、不启动 M3/M4；其后只执行了单独授权的只读 M2 三 seed validation aggregate
Thesis destination: 结果章节的 M2 三 seed 输入、低频标签与校准敏感性；方法章节的只读 feature reuse、seed 隔离和独立验证
```

### EXP-052: Stack Overflow M2 Three-Seed Validation Aggregate

```text
Experiment ID: EXP-052
Tier / RQ: Major family settlement / RQ-S1
Status: Verified；validation-only aggregate；test、EXP-053/054 未授权
Frozen inputs: seeds 42/43/44 completed run records and independent verification records；matched EXP-051 M1 three-seed aggregate
Aggregation rule: arithmetic mean + sample std (`ddof=1`) over the three seed-level metric records；不拼接 row-level predictions
Fixed-0.5 result: Macro-F1=0.151553 +/- 0.027647；Micro-F1=0.408950 +/- 0.060584；weighted F1=0.331794 +/- 0.036499；strict subset accuracy=0.560185 +/- 0.029669；hamming loss=0.087269 +/- 0.001009
Per-seed shared-threshold result: thresholds=0.25/0.20/0.25；Macro-F1=0.318889 +/- 0.038085；Micro-F1=0.514069 +/- 0.022042；weighted F1=0.482286 +/- 0.051823；strict subset accuracy=0.490741 +/- 0.028678；hamming loss=0.121142 +/- 0.006565
Calibration tradeoff: Macro-F1 +0.167336；strict subset accuracy -0.069444；hamming loss +0.033873
Matched descriptive comparison: fixed M2-M1 Macro-F1 delta=-0.455744 +/- 0.035919；shared-threshold delta=-0.298365 +/- 0.039425；两个条件下 3/3 seed delta 均为负；不对 n=3 做 p-value 或显著性声明
Per-label shared-threshold result: love=0.607112 +/- 0.049099；joy=0.206770 +/- 0.187595；surprise=0；anger=0.550311 +/- 0.012602；sadness=0.403879 +/- 0.025159；fear=0.145262 +/- 0.035415
Resource boundary: seed 42 包含完整 Qwen feature extraction，seeds 43/44 只训练 cached head；仅保留逐 seed 资源，不计算异质运行的 family 平均成本
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/；聚合产物不含私有逐行预测
Verification: independent verifier 85/85；EXP-052 regression suite 36/36；输入 hash、聚合规则、完整指标、逐类结果、配对差值、privacy、split access 与 resource boundary 均复核
Result: 当前 frozen Qwen final-layer last-input-token representation + Linear(2560,6) 在三个 seed 上稳定落后匹配的 M1；校准提高 Macro-F1 但牺牲 exact-set 与 hamming 指标
Failure or caveat: 不能由该线性读出推出 Qwen 没有情绪信息、其他层/池化/非线性 head 同样无效，或 Classification LoRA 不会改善；没有 test 结论
Decision consequence: EXP-052 validation family 完成；下一步只可另行登记 EXP-053 M3 Classification LoRA 的协议与资源门，M4 与 test 继续密封
Thesis destination: 主结果表的 M2 三 seed validation、校准权衡、低频标签和负结果边界；方法章节的聚合与资源可比性规则
```

### EXP-053: Stack Overflow M3 Train-only Resource Preflight

```text
Experiment ID: EXP-053
Tier / RQ: Major implementation/resource gate / RQ-S1
Status: Verified train-only resource preflight；在该 gate 完成时 formal seed-42 train + validation、seeds 43/44、EXP-054 与 test 均未授权；后续 formal seed-42 见 EVID-056
Frozen inputs: DATA-SO-TASK-V1 train；Qwen3-4B revision 1cfa9a7208912126459214e8b04321603b3df60c BF16；final-layer last-input-token pooling；Linear(2560,6)；matched M2 seed-42 head hash；112-point LoRA rank 8/scale 20/dropout 0
Sampling: tokenization 全部 3,360 条 train 后确定性抽取 32 条；公开层只保留标签、neutral、双标签和 token-length 覆盖摘要，row ID 与文本不公开
Training smoke: 32 optimizer steps；head AdamW 1e-4、LoRA AdamW 1e-5，weight decay 均为 0.01；7,355,398 个总可训练参数；112/112 lora_b 非零；base sentinel 不变；32/32 loss finite
Initialization/replay: head initial SHA-256=7308f5ca8300aa7343645f7783c7893e1120d79344052d531e9cd018d8afd819，与 EXP-052 seed 42 相同；initial LoRA logit delta=0；private adapter/head checkpoint reload max logit difference=0
Resource result: 训练阶段峰值 8.674 GB；独立 checkpoint-replay 阶段峰值 8.376 GB；稳态 train step 均值 1.513 s；按 1.5x 安全系数投影 4.436 h/seed、13.308 h/three sequential seeds；13 GB、8 h/seed、24 h/three-seed gates 全部通过
Preserved failure: attempt 1 的 32-step 训练 history 峰值为 8.674 GB，但旧 optimizer/gradient/tensor 引用未释放便在同进程加载第二份 Qwen，导致 process-wide peak gate 失败；attempt-2 amendment 只修正顺序阶段引用释放和峰值计量，失败目录保持 append-only
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/；adapter/head/reference logits 与样本 identity 位于 Git-ignored private 目录
Verification: EXP-053 tests 12/12；independent verifier 102/102；source/prerequisite hashes、完整 train tokenization、采样、参数、checkpoint、replay、资源、privacy 与 split boundary 均复核
Result: 本机 MLX 可在冻结资源预算内执行 M3 Classification LoRA，且 checkpoint 可精确恢复
Failure or caveat: 未访问 validation/test，未计算 Macro-F1 等性能，不能据此声称 LoRA 改善 M2/M1；32-step timing 仅是带 1.5x 安全系数的资源投影，不是正式训练实测耗时
Decision consequence: 该 gate 当时只允许下一步单独冻结并授权 EXP-053 formal seed 42；该运行现已完成并记录为 EVID-056，未直接授权三 seed
Thesis destination: 方法章节的 M2/M3 matched 初始化、LoRA 参数与资源预算；不进入性能结果表
```

### EXP-053: Stack Overflow M3 Formal Seed 42

```text
Experiment ID: EXP-053
Tier / RQ: Major single-seed integrity and performance gate / RQ-S1
Status: Verified train + validation；在该 gate 完成时 seeds 43/44、EXP-054 与 test 未授权；后续 seed 43 见 EVID-057
Frozen inputs: DATA-SO-TASK-V1 train/validation；Qwen3-4B BF16；final-layer last-input-token pooling；Linear(2560,6)；matched M2 seed-42 head initialization；112-point LoRA rank 8/scale 20/dropout 0
Training: 2 epochs、6,720 optimizer steps；head AdamW 1e-4、LoRA AdamW 1e-5、weight decay 0.01；unweighted BCEWithLogits；epoch-2 checkpoint selected by the frozen fixed-0.5 Macro-F1 rule
Fixed-0.5 result: Macro-F1=0.602846；Micro-F1=0.746445；weighted F1=0.737011；strict subset accuracy=0.754167；hamming loss=0.049537；component-bootstrap 95% CI=[0.512076,0.672759]
Shared-threshold result: threshold=0.40；Macro-F1=0.637786；Micro-F1=0.758315；weighted F1=0.751829；strict subset accuracy=0.755556；hamming loss=0.050463；component-bootstrap 95% CI=[0.548975,0.709997]
Low-support sensitivity: five-label Macro-F1 without surprise=0.692616；surprise support=7、F1=0.363636、95% CI=[0,0.714286]，不能声称少数类稳定解决
Matched M3-M2 delta: fixed Macro-F1 +0.419455，95% CI [+0.326063,+0.497920]；shared Macro-F1 +0.312857，95% CI [+0.223280,+0.388544]
Resources: wall=13,756.811 s (3.821 h)；peak MLX memory=8.702 GB；API cost=0；13 GB/8 h gates passed
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-42/；adapter/head checkpoints、batch orders 与 row-level validation predictions 位于 Git-ignored private 目录
Preserved verifier failure: attempt 1 完成全量 checkpoint replay、概率误差 0、test 未访问，但因读取资源 verifier 的旧字段名保留为 Failed (135/136)
Verification: schema-only amendment 绑定 attempt-1 hashes，attempt 2 重复完整 720-row replay 与全部检查，148/148 Passed，checkpoint probability max error=0
Result: 单 seed 证据支持 classification interface 下 LoRA 任务适配相对 frozen Qwen linear head 有实质增量
Failure or caveat: 不能由单 seed 推出三 seed 稳定性、M3 对 M1 的 family 优势、生成式 M4 结论或内部情绪机制；validation 用于 checkpoint/threshold 选择，test 尚无结果
Decision consequence: 该 gate 当时只允许下一步单独授权 EXP-053 seed 43；该运行现已完成并记录为 EVID-057，仍未直接授权 seed 44、EXP-054 或 TEST-READY
Thesis destination: 主结果表的 M3-M2 适配增量、校准与成本；低频标签和单 seed 边界进入讨论章节
```

### EXP-053: Stack Overflow M3 Formal Seed 43

```text
Experiment ID: EXP-053
Tier / RQ: Major second-seed integrity and performance gate / RQ-S1
Status: Verified train + validation；在该 gate 完成时 seed 44、EXP-054 与 test 未授权；后续 seed 44 见 EVID-058
Frozen inputs: DATA-SO-TASK-V1 train/validation；Qwen3-4B BF16；final-layer last-input-token pooling；Linear(2560,6)；matched M2 seed-43 head initialization；112-point LoRA rank 8/scale 20/dropout 0
Training: 2 epochs、6,720 optimizer steps；head AdamW 1e-4、LoRA AdamW 1e-5、weight decay 0.01；unweighted BCEWithLogits；epoch-2 checkpoint selected by the frozen fixed-0.5 Macro-F1 rule
Fixed-0.5 result: Macro-F1=0.659318；Micro-F1=0.736462；weighted F1=0.736294；strict subset accuracy=0.751389；hamming loss=0.050694；component-bootstrap 95% CI=[0.565783,0.728415]
Shared-threshold result: threshold=0.35；Macro-F1=0.663515；Micro-F1=0.756696；weighted F1=0.758532；strict subset accuracy=0.754167；hamming loss=0.050463；component-bootstrap 95% CI=[0.570351,0.732537]
Low-support sensitivity: five-label Macro-F1 without surprise=0.707329；surprise support=7、F1=0.444444、95% CI=[0,0.8]，不能声称少数类稳定解决
Matched M3-M2 delta: fixed Macro-F1 +0.525708，95% CI [+0.432380,+0.598715]；shared Macro-F1 +0.309922，95% CI [+0.208105,+0.390880]
Resources: wall=12,759.608 s (3.544 h)；peak MLX memory=8.699 GB；API cost=0；13 GB/8 h gates passed
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-43/；adapter/head checkpoints、batch orders 与 row-level validation predictions 位于 Git-ignored private 目录
Verification: independent verifier 重复完整 720-row selected-checkpoint replay 与全部检查，143/143 Passed，checkpoint probability max error=0
Result: 第二个 matched seed 再次支持 classification interface 下 LoRA 任务适配相对 frozen Qwen linear head 的实质增量
Failure or caveat: seeds 42/43 的 shared Macro-F1 描述性均值为 0.650650 +/- 0.018194，仍不能替代三 seed family；不能据此推出 M3 对 M1 的稳定优势、生成式 M4 结论或内部情绪机制；test 尚无结果
Decision consequence: 该 gate 当时只允许下一步单独授权 EXP-053 seed 44；该运行现已完成并记录为 EVID-058，仍未直接授权 M3 aggregate、EXP-054 或 TEST-READY
Thesis destination: 主结果表的 matched M3-M2 适配增量、校准与成本；低频标签和两 seed 边界进入讨论章节
```

### EXP-053: Stack Overflow M3 Formal Seed 44

```text
Experiment ID: EXP-053
Tier / RQ: Major third-seed integrity and performance gate / RQ-S1
Status: Verified train + validation；M3 aggregate、EXP-054 与 test 未授权
Frozen inputs: DATA-SO-TASK-V1 train/validation；Qwen3-4B BF16；final-layer last-input-token pooling；Linear(2560,6)；matched M2 seed-44 head initialization；112-point LoRA rank 8/scale 20/dropout 0
Training: 2 epochs、6,720 optimizer steps；head AdamW 1e-4、LoRA AdamW 1e-5、weight decay 0.01；unweighted BCEWithLogits；epoch-2 checkpoint selected by the frozen fixed-0.5 Macro-F1 rule
Fixed-0.5 result: Macro-F1=0.598812；Micro-F1=0.729017；weighted F1=0.708722；strict subset accuracy=0.733333；hamming loss=0.052315；component-bootstrap 95% CI=[0.517388,0.671741]
Shared-threshold result: threshold=0.25；Macro-F1=0.660795；Micro-F1=0.763713；weighted F1=0.756752；strict subset accuracy=0.741667；hamming loss=0.051852；component-bootstrap 95% CI=[0.584731,0.727760]
Low-support sensitivity: five-label Macro-F1 without surprise=0.720227；surprise support=7、F1=0.363636、95% CI=[0,0.705882]，不能声称少数类稳定解决
Matched M3-M2 delta: fixed Macro-F1 +0.461155，95% CI [+0.374006,+0.536410]；shared Macro-F1 +0.382650，95% CI [+0.298126,+0.455866]
Resources: wall=12,065.663 s (3.352 h)；peak MLX memory=8.702 GB；API cost=0；13 GB/8 h gates passed
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-44/；adapter/head checkpoints、batch orders 与 row-level validation predictions 位于 Git-ignored private 目录
Verification: independent verifier 重复完整 720-row selected-checkpoint replay 与全部检查，148/148 Passed，checkpoint probability max error=0；seed42/43/44 回归测试 47/47
Result: 第三个 matched seed 再次支持 classification interface 下 LoRA 任务适配相对 frozen Qwen linear head 的实质增量
Failure or caveat: 三个单 seed 均已验证，但本 gate 未授权只读 aggregate，不能提前报告 M3 family mean/std、稳定性、M3 对 M1 的 family 比较、生成式 M4 结论或内部情绪机制；test 尚无结果。正式 runner 的生成文案沿用了 seed-43 模板，误写为“第二个 seed / seed 44 仍密封”；为保留已验证哈希，原始 `run.json`、`REPORT.md` 与 frozen source 不改，正确解释和受影响位置记录于 seed-44 `CORRECTION.md`
Decision consequence: 下一道门需另行冻结并授权只读 M3 three-seed validation aggregate；不直接进入 EXP-054 或 TEST-READY
Thesis destination: 主结果表的 matched M3-M2 适配增量、校准与成本；低频标签和 aggregate 前边界进入讨论章节
```

### EXP-053: Stack Overflow M3 Three-Seed Validation Aggregate

```text
Experiment ID: EXP-053
Tier / RQ: Major validation-only family aggregate / RQ-S1
Status: Verified；test、EXP-054、TEST-READY 与错误分析未授权
Frozen inputs: EXP-053 seeds 42/43/44 verified run summaries；seed-42 verification-attempt-2；seed-44 CORRECTION；EXP-051 M1 与 EXP-052 M2 verified aggregates
Aggregation: arithmetic mean + sample standard deviation (ddof=1) over seed-level metrics；不拼接或读取 row-level predictions；不对 n=3 做显著性检验
Fixed-0.5 family result: Macro-F1=0.620325 +/- 0.033829；Micro-F1=0.737308 +/- 0.008745；weighted F1=0.727342 +/- 0.016130；strict subset accuracy=0.746296 +/- 0.011312；hamming loss=0.050849 +/- 0.001395
Shared-threshold family result: thresholds=[0.40,0.35,0.25]；Macro-F1=0.654032 +/- 0.014135；Micro-F1=0.759575 +/- 0.003674；weighted F1=0.755704 +/- 0.003472；strict subset accuracy=0.750463 +/- 0.007649；hamming loss=0.050926 +/- 0.000802
Matched M3-M2 delta: fixed Macro-F1=+0.468773 +/- 0.053535；shared Macro-F1=+0.335143 +/- 0.041168；两种条件均 3/3 seed 为正，支持 classification LoRA 相对 frozen Qwen + matched linear head 的稳定任务适配收益
Descriptive M3-M1 delta: shared six-label Macro-F1=+0.036778 +/- 0.003154；但 shared five-label Macro-F1 without surprise=-0.033981 +/- 0.008620、Micro-F1=-0.011564 +/- 0.006039、weighted F1=-0.008242 +/- 0.001563
Low-support boundary: surprise 只有 7 个 validation positives；M1 三 seed F1 均为 0，M3 shared-threshold surprise F1=0.390572 +/- 0.046655。六标签 Macro-F1 的正差主要受该低支持标签驱动，不能声称 M3 全面优于 encoder
Resources: homogeneous M3 path wall=12,860.694 +/- 850.094 s；peak MLX memory=8.701082 +/- 0.001801 GB；API cost=0。由于 M1 runtime 与 M2 cache 路径不同，不做跨模型成本结论
Artifacts: experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/
Verification: independent aggregate verifier 124/124 Passed；aggregate SHA-256=0e94fef16eb48e915b26be8279bad6c1e6757e5dd8b89efb2149c611538effab；verification SHA-256=893234a504e1d43f50a8f31a8cc710b22c9fa2456cd2e9d29228261f34edfb4b
Result: M3 family 已验证，且 LoRA 任务适配相对 M2 的收益跨三 seed 稳定；M3 与 M1 的总体优劣不能由六标签 Macro-F1 单独确定
Failure or caveat: 该 aggregate 是 validation-only descriptive evidence；未访问 test、未做错误分析、未证明内部情绪机制，也未授权 EXP-054
Decision consequence: 下一步应另行冻结 M1/M3 validation 错误分析，定位 surprise 与互补错误；错误分析完成前不进入 TEST-READY，EXP-054 仍需独立授权
Thesis destination: M1-M3 主结果表、LoRA 适配收益、低支持标签敏感性、校准与指标权衡、研究限制
```

### EXP-056: Unified TEST-READY Freeze

```text
Experiment ID: EXP-056
Tier / RQ: Major test-readiness gate / RQ-S1
Status: Verified TEST-READY；test sealed、未授权、未读取、未消费
Formal scope: M1/M2/M3/M4 x seeds 42/43/44，共 12 个单元；无 best-seed、ensemble、oracle 或 router
Frozen selection: M1 thresholds=[0.25,0.30,0.50] and epochs=[4,4,5]；M2 thresholds=[0.25,0.20,0.25] and epochs=[2,2,2]；M3 thresholds=[0.40,0.35,0.25] and epochs=[2,2,2]；M4 epochs=[2,2,2] with strict parser
Execution order: initialize -> predict-family -> seal-predictions -> score；全部 12 份预测 hash-sealed 前不得打开 labels
Evaluation: six-label Macro-F1 primary；five-label Macro-F1 without surprise、Micro/Weighted-F1、precision/recall、strict subset accuracy、hamming loss、per-label、empty/cardinality 和 M4 parser/resource metrics；五组 matched contrasts；2,000 次 duplicate-component bootstrap
Artifacts: experiments/stack-overflow-emotion-gold/test-gate/
Verification: final contract SHA-256=bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966；readiness verifier 89/89 Passed；unit tests 6/6；authorization absent；formal public/private output absent；test inputs/labels opened=false
Result: 统一冻结完成，但没有执行 test，也没有产生 test 指标
Decision consequence: 只有新的、绑定最终合同 hash 的一次性授权才能启动正式 test；之后严格按分阶段 runner 执行
Thesis destination: 方法章节的 test gate 与可复现性；正式 test 主表的预注册来源
```

### EXP-056: One-time Frozen Test Result

```text
Experiment ID: EXP-056
Tier / RQ: Major one-time held-out test / RQ-S1
Status: Verified；Stack Overflow test consumed
Authorization: 用户指令“授权”；authorization 绑定 final contract SHA-256=bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966
Scope: 720 test rows；702 duplicate components；M1/M2/M3/M4 x seeds 42/43/44，共 12 个冻结单元
Access discipline: initialize -> predict M1/M2/M3/M4 -> seal predictions -> score；labels 只在 prediction seal 后打开；test 后 selection/tuning=false
M1: Macro-F1=0.567459 +/- 0.007814；five-label Macro-F1=0.680951 +/- 0.009377；Micro-F1=0.748947 +/- 0.001954；weighted F1=0.743941 +/- 0.006278；subset accuracy=0.750000 +/- 0.017067；hamming loss=0.054244 +/- 0.002550
M2: Macro-F1=0.295226 +/- 0.020587；five-label Macro-F1=0.354271 +/- 0.024704；Micro-F1=0.508591 +/- 0.015366；weighted F1=0.474565 +/- 0.045017；subset accuracy=0.502778 +/- 0.046915；hamming loss=0.126080 +/- 0.009260
M3: Macro-F1=0.613804 +/- 0.025733；five-label Macro-F1=0.670216 +/- 0.012032；Micro-F1=0.753741 +/- 0.003607；weighted F1=0.750265 +/- 0.003552；subset accuracy=0.757407 +/- 0.007127；hamming loss=0.051620 +/- 0.001225
M4: Macro-F1=0.547823 +/- 0.015312；five-label Macro-F1=0.657388 +/- 0.018374；Micro-F1=0.746167 +/- 0.005484；weighted F1=0.734989 +/- 0.009252；subset accuracy=0.771296 +/- 0.006415；hamming loss=0.052778 +/- 0.000835；parser-valid=100%
Frozen contrasts: M2-M1 Macro=-0.272233, CI=[-0.310672,-0.227897]；M3-M1=+0.046345, CI=[-0.008674,+0.089730]；M3-M2=+0.318578, CI=[+0.254425,+0.369327]；M4-M1=-0.019636, CI=[-0.058325,+0.017981]；M4-M3=-0.065981, CI=[-0.107869,-0.011312]
Five-label sensitivity: M3-M1=-0.010735, CI=[-0.046061,+0.024305]；M4-M3=-0.012828, CI=[-0.045475,+0.018074]；surprise 仅有 7 个 test positives
Resources: M1 CPU mean=23.432 s/seed；M2 shared Qwen extraction=467.440 s + fresh heads，peak=8.225 GB；M3 Metal mean=610.664 s/seed，peak=8.593 GB；M4 Metal mean=1188.417 s/seed，peak=8.595 GB；API cost=0
Execution recovery: M2 首次受限 sandbox 启动因 no Metal device 在推理前停止，未产生 prediction、未开标签；随后以相同冻结命令在获批 native Metal 环境从头完成
Artifacts: experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/
Verification: pre-test readiness 89/89；unit tests 6/6；post-score independent verifier 29/29 Passed；verifier 未重开 sealed label source；results SHA-256=d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd
Result: Classification LoRA 相对 frozen-Qwen linear head 的适配收益在 test 成立；M3 与强 encoder 的差异不确定，不能声称全面超过 M1；M4 没有在主指标上超过 M3
Failure or caveat: M4 subset accuracy 最高是次指标；跨 CPU/shared-cache/per-seed Metal 的 runtime 不作直接速度排名；结果不支持内部机制、generation 因果效应、普遍 LLM 优势或可部署 router
Decision consequence: Stack Overflow test 已消费；禁止利用该 split 调参、选 seed、改阈值、改 prompt/parser 或补跑候选。后续仅允许预登记的既有预测只读分析，主线转入论文主表、系统演示与归档
Thesis destination: Stack Overflow 正式主结果表、模型比较、低支持标签敏感性、资源与可复现性、限制讨论
```

后续 LLM 实验继续使用以下登记模板：

```text
Dataset and protocol ID:
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
Frozen same-dataset baselines used for comparison:
Measured gain or loss:
```

“使用了某模型”不是结果。只有相对固定基线的可复核收益、代价和失败边界才构成证据。

## Controls, Ablations, and Robustness

| Test ID | Question | Control | Treatment | Metric | Artifact | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CTRL-001 | 回复上下文是否有效 | 无上下文 | 父回复或完整线程 | Macro-F1、上下文依赖子集 F1 | TBD | Planned |
| CTRL-002 | 检索示例是否有效 | 随机 few-shot | 语义检索 few-shot | Macro-F1、成本、延迟 | TBD | Planned |
| CTRL-003 | 监督任务适配是否有效 | EXP-025 frozen prompting | EXP-029 supervised LoRA | Macro-F1、per-class recall、成本、稳定性 | EXP-025、EXP-029 | Completed and verified on dev |
| CTRL-004 | 预训练语料域匹配是否有效 | `FacebookAI/roberta-base` | `cardiffnlp/twitter-roberta-base` | Macro-F1、per-class F1 | EXP-014、EXP-015、EXP-016 | Completed and test-verified |
| CTRL-005 | 预训练域变化是否改变稳定错误结构 | EXP-014 三 seed | EXP-015 三 seed | correct-seed transition、stable recovery/regression、error overlap | EXP-017 | Completed and verified |
| CTRL-006 | finite-state decoder 是否改变 Qwen 最终标签而非只修复格式 | EXP-026 unrestricted zero/few-shot | EXP-025 constrained zero/few-shot | Macro-F1、parser validity、exact set agreement、Jaccard、latency | EXP-025、EXP-026 | Completed and verified |
| CTRL-007 | EXP-029 的 neutral ontology 失配能否只靠推理策略修正 | old prompt + closed decoder | old prompt + open decoder；aligned prompt + open decoder | Macro-F1、Samples-F1、exact match、neutral co-occurrence slice、co-prediction count | EXP-031 | Completed and verified; no material inference improvement |
| CTRL-008 | 保留 neutral+emotion 训练 target 是否改善 matched seed-42 行为 | EXP-029 seed-42 adapter + EXP-031 aligned-open inference | EXP-033 seed-42 target-aligned LoRA + matched aligned-open inference | Macro-F1、paired bootstrap、cardinality、neutral co-occurrence behavior | EXP-033 | Completed and verified; improvement gate failed |
| CTRL-009 | EXP-033 的 0 条 neutral+emotion 输出是否主要是 held-out generalization failure | EXP-033 validation neutral+emotion slice | 同一冻结 adapter 在全部 train neutral+emotion 样本上的回放 | co-prediction count、gold/predicted cardinality、Samples-F1 | EXP-034 | Completed and verified; train 与 validation 均为 0 co-predictions |
| CTRL-010 | neutral+emotion 是否代表单一标注者的可学习共现判断 | 同一标注者 neutral 与 emotion 共选 | 不同标注者投票经 >=2 阈值聚合成 simplified target | same-rater co-selection、vote counts、unclear、冻结文本复核 | EXP-035 | Completed and verified; 1,396/1,396 为 aggregation-only |
| CTRL-011 | aggregate union 是否制造 Qwen 相对 BERT 的冲突切片评分差距 | official simplified target | clear-rater expected agreement；冻结 7 份 prediction files | official/clear-rater set-F1、exact match、paired bootstrap、relative shift | EXP-036 | Completed and verified; primary set-F1 practical tie，official exact-match 语义显著不同 |
| CTRL-012 | 标注聚合是否解释完整 dev 上 Qwen 相对 BERT 的总体差距 | official hard target | clear-rater vote-fraction soft target 与 expected individual-rater agreement；冻结 7 份 prediction files | official/soft Macro-F1、expected set-F1、paired bootstrap、relative shift | EXP-037 | Completed and verified; soft delta=-0.036218，shift CI 跨 0，gap remains |
| CTRL-013 | 冻结 dev 结论能否泛化到一次性 official test | EXP-018/020/025/029/033 的冻结 dev 条件 | 相同模型在 5,427 条 official test 上一次评估 | Macro/Micro/Weighted/Samples-F1、subset accuracy、per-label metrics、资源 | EXP-038 | Completed and verified; BERT Macro-F1=0.488328 +/- 0.008771，target-aligned LoRA=0.444675；test consumed |
| CTRL-014 | 固定局部前文和 reasoning mode 是否分别改变冻结 Qwen 的单标签表现 | target-only / reasoning off | previous-context / reasoning on 的配对 2x2 | Macro-F1、Accuracy、Weighted-F1、parser validity、paired bootstrap、资源 | EXP-043 | Completed and verified; context average=-0.021512，reasoning average=+0.030825，interaction CI 跨 0；reasoning 的整体指标与成本存在权衡 |
| CTRL-015 | reasoning-on 输出是否对 fresh-process replay、batch size 与共同批次组成稳定 | singleton 两次新进程重放 | 固定 batch 8 两次重放与 prompt-length batch 重排 | raw output、parser state、final-label agreement；不计算分类性能 | EXP-045、EXP-046 | EXP-045 初始化失败并保留；EXP-046 Verified，冻结 singleton，post-adapter/dev 前必须重放 |
| CTRL-016 | generative LoRA 是否在完全 matched singleton validation 下改善同一 Qwen | 无 adapter Qwen3-4B reference | seeds 42/43/44 epoch-2 LoRA adapters | Macro-F1、Accuracy、Weighted-F1、parser validity、group bootstrap、资源 | EXP-047 | Completed and verified；LoRA mean delta=+0.228873，仍比 EXP-042 M2 低 0.032454（descriptive） |
| CTRL-017 | EXP-047 的改善是否主要只是修复 reference 格式失败，且 LoRA 与 encoder 的剩余错误结构有何差异 | 116 条 reference output-failure slice；matched reference；EXP-042 encoder 三 seed | 1,156 条 reference valid-output slice；EXP-047 LoRA 三 seed；48 条预冻结目的性案例 | Accuracy 加性贡献、Macro-F1、逐类 F1、混淆、跨 seed 稳定性、匿名定性代码 | EXP-048 | Completed and verified；valid-output slice 贡献 `+0.486111` Accuracy，格式失败 slice 仅 `+0.070755`；LoRA 仍低于 encoder `0.032454` Macro-F1 |
| ROB-001 | 模型是否依赖表面形式 | 原文本 | 否定、拼写、网络用语等受控扰动 | 性能下降幅度 | TBD | Planned |

## Failure Case Register

失败案例不能只挑有趣样本，应按预先定义的类型统计：

| Case ID | Type | Gold label | Prediction | Context used | Likely cause | Evidence path | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EXP-017-SAMPLE | 冻结的 high-confidence / domain recovery / domain regression / shared / ordinary 五组样本 | anger / joy / optimism / sadness | 四条件十个冻结输出 | 无对话上下文 | ontology overlap、model limitation、annotation uncertainty、surface noise、missing context | `experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/` | 42 cases reviewed and verified |
| EXP-030-SAMPLE | 冻结的 LoRA recovery / BERT regression / frozen-Qwen recovery / neutral cooccurrence / shared / ordinary 六组样本 | GoEmotions 28 标签多标签 | BERT、frozen Qwen 与 LoRA 共 7 份冻结输出 | 无对话上下文 | overlapping ontology、annotation uncertainty、model limitation、missing context、output policy、surface noise | `experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/` | 48 cases reviewed and verified |
| EXP-048-SAMPLE | 冻结的 format recovery / valid-output recovery / LoRA regression / encoder recovery / seed instability / ordinary 六组样本 | Weibo EClass 七类单标签 | matched reference、LoRA 与 encoder 共 7 份冻结输出 | target-only；结构元数据记录局部前文可用性 | annotation/data uncertainty、overlapping ontology、model limitation、missing context、surface noise、output policy | `experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/` | 48 purposive cases reviewed and verified；not a prevalence estimate |
| EXP-035-SAMPLE | 冻结的 aggregation-only / unclear / high-cardinality / residual 四组样本 | GoEmotions neutral 与一个或多个 emotion | N/A；本实验审计逐标注者投票而非模型输出 | 单条 Reddit comment | cross-rater disagreement、genuine multilabel、unclear、missing context | `experiments/goemotions/annotation-audit/runs/exp-035-neutral-cooccurrence-annotation-audit/` | 48 cases reviewed and verified |

每类至少记录代表性真阳性、假阳性和假阴性，并区分：

- 数据或标注问题。
- 模型能力问题。
- 上下文缺失。
- 提示或输出解析问题。
- 类别定义本身不稳定。

## Reproducibility and Deliverables

| Deliverable | Required evidence | Path | Status |
| --- | --- | --- | --- |
| Data card | 来源、许可、字段、规模、标签、匿名化、划分 | `data/weibo-emotion-corpus/README.md`；`experiments/forum-context/protocols/data-weibo-eclass-task-v1.md`；`experiments/forum-context/weibo-eclass/reports/` | Weibo EClass data track verified; 33/33 independent checks passed |
| Baseline reproduction | 环境、命令、配置、日志、预测、指标 | `experiments/tweeteval-emotion/tfidf-logreg/`；`experiments/tweeteval-emotion/tfidf-linear-svm/`；`experiments/tweeteval-emotion/roberta-base/`；`experiments/tweeteval-emotion/test-gate/`；`experiments/tweeteval-emotion/error-analysis/`；`experiments/goemotions/tfidf-ovr-logreg/`；`experiments/goemotions/bert-base/`；`experiments/goemotions/error-analysis/`；`experiments/goemotions/test-gate/`；`experiments/weibo-eclass/stage-2-preflight/`；`experiments/weibo-eclass/stage-3-baselines/` | TweetEval 与 GoEmotions 已验证；Weibo Stage 2 train-only 执行门及 Stage 3 same-task dev baselines 已验证，Stage 4 Qwen 2x2 待登记 |
| LLM comparison | 模型版本、提示、解析、成本、延迟、对照 | `experiments/goemotions/qwen3-1.7b/runs/exp-025-full-dev-zero-few-shot/`；`experiments/goemotions/qwen3-1.7b/runs/exp-026-unconstrained-decoder-ablation/`；`experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/`；`experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/`；`experiments/goemotions/qwen3-1.7b/runs/exp-033-target-aligned-lora/validation-seed-42-v1/`；`experiments/goemotions/test-gate/` | Prompt/decoder、three-seed LoRA、ontology ablation、target-aligned retraining 与一次性 formal test 均已验证；EXP-033 未超过 BERT；formal probe pending |
| Robustness or ablation report | 预设问题、控制变量、完整结果 | `experiments/goemotions/qwen3-1.7b/runs/exp-026-unconstrained-decoder-ablation/joint-decoder-analysis.json`；`experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/REPORT.md` | Decoder and neutral-ontology inference ablations verified; broader robustness pending |
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
| 2026-07-30 | 在读错误原文前冻结 EXP-017 抽样协议，完成全量错误结构、42 条匿名定性复核和独立验证 | EVID-013 为 `Verified`；建立 optimism、共享错误、域恢复/回退和标签/上下文边界证据，公开原文泄漏为 0 |
| 2026-07-31 | 在读取 dev 结果前冻结并运行 EXP-018 GoEmotions 简单多标签基线，随后独立复算 | EVID-014 为 `Verified`；固定阈值下 Macro-F1=0.203644、Micro-F1=0.377639；识别出低预测标签基数、60.10% 空预测和五个零召回标签；test 未获取或读取 |
| 2026-07-31 | 完成 EXP-019 BERT 环境烟雾测试，并按冻结协议运行、复核 EXP-020 三随机种子 BERT-base-cased dev 基线 | EVID-015 为 `Verified`；Macro-F1=0.489435 +/- 0.011063、Micro-F1=0.586671 +/- 0.002928；三个 5,426 x 28 概率矩阵、模型和输入哈希复核一致；test 未获取或读取 |
| 2026-07-31 | 在正式 dev 访问前冻结 EXP-025/026 decoder x prompt 2x2，依次完成 constrained 与 unrestricted 全量运行和独立复算 | EVID-016/017 为 `Verified`；constrained few-shot 按 dev 规则选定但远低于 BERT；decoder 对 few-shot 主要恢复格式，对 zero-shot 会改变部分双方有效标签集合；test 未获取或读取 |
| 2026-08-02 | 完成 EXP-029 Qwen3-1.7B 监督 LoRA 三随机种子训练、双条件全量 dev 评估与独立复算 | EVID-018 为 `Verified`；选定 zero-shot Macro-F1=0.451374 +/- 0.019212，较 frozen Qwen 选定条件 +0.210209、较 BERT 均值 -0.038061；test 未获取或读取 |
| 2026-08-02 | 在读取原文前冻结并完成 EXP-030 跨 BERT、frozen Qwen 与 LoRA 的 GoEmotions dev 错误分析 | EVID-019 为 `Verified`；复算 7 份预测、5,426 条 gold 与 48 条匿名案例，识别 LoRA 的近单标签偏向、174 条 neutral+emotion 结构性不可达和多标签召回差距；公开原文泄漏 0，test 未获取 |
| 2026-08-03 | 完成 EXP-031 三 seed neutral ontology inference-only 消融及独立复算 | EVID-020 为 `Verified`；decoder-only 预测完全不变，aligned inference Macro-F1 仅 +0.001682、neutral 共现切片 Samples-F1 -0.009132，分类为 `no_material_inference_improvement`；test 未获取或读取 |
| 2026-08-04 | 冻结并完成 EXP-035 GoEmotions neutral 共现数据与标注审计 | EVID-023 为 `Verified`；1,396/1,396 条 target 均由跨标注者聚合形成，同一标注者共选为 0；官方 >=2 票规则精确复现，48 条目的性复核完成，公开原文和上游 ID 泄漏为 0，test 未获取或读取 |
| 2026-08-04 | 冻结并完成 EXP-036 GoEmotions dev 逐标注者评分诊断 | EVID-024 为 `Verified`；174/174 条 dev target 均为 aggregation-only；EXP-029 与 BERT 的 clear-rater expected set-F1 差 +0.000720、CI 跨 0，局部 practical tie；test 未获取或读取 |
| 2026-08-04 | 冻结并完成 EXP-037 GoEmotions 完整 dev 逐标注者评分诊断 | EVID-025 为 `Verified`；5,426/5,426 条 dev 和 19,440 行 raw annotations 复算通过；EXP-029 相对 BERT 的 soft Macro-F1 delta=-0.036218，relative shift CI 跨 0，标注聚合不能解释总体差距；test 未获取或读取 |
| 2026-08-04 | 完成 EXP-038 GoEmotions 一次性冻结 test gate，并透明修正 verifier 的多标签顺序比较 | EVID-026 为 `Verified`；9 个冻结单元、5,427 条 test、完整指标、混淆矩阵、资源与哈希均复算通过；BERT Macro-F1=0.488328 +/- 0.008771，EXP-033=0.444675；test 自此已消费 |
| 2026-08-05 | 完成 IAC 2.0 4forums V2 文本清洗与质量过滤，并保留 V1 quote 语义失败记录 | EVID-027 为 `Verified`；403,374 个候选、403,336 个 eligible，539,658 条 quote 全部闭合；独立 verifier 40 项检查、0 mismatch，尚未标注或划分 |
| 2026-08-05 | 完成 IAC 2.0 4forums `DATA-FCTX-DEDUP-V2` 精确、词法近似与语义近似去重，并保留 V1 检索门失败记录 | EVID-028 为 `Verified`；403,183 条自动去重后候选，153 条直接自动删除；249 个 review clusters 尚未裁决；独立 verifier 69 项检查、0 mismatch，mean recall@64=0.992554，semantic-only 自动删除=0 |
| 2026-08-06 | 完成 `DATA-FCTX-SAMPLE-V1` metadata-only calibration 抽样预检和独立重放 | EVID-029 为 `Verified`；120 条主样本与 60 条备用样本来自 180 个不同 thread，四个诊断池容量通过；独立 verifier 45 项检查、0 mismatch，公开文本或 ID 泄漏为 0，blind repeats 尚未生成 |
| 2026-08-06 | 导出并独立验证 120 条 `DATA-FCTX-LABEL-V1` 私有 staged views | EVID-030 为 `Verified`；独立 verifier 34 项检查、0 mismatch，全部视图与冻结 SQLite 逐份一致且不含 sampling/source metadata；人工标签、records 和 blind repeats 仍为 0 |
| 2026-08-07 | 完成 Human Pass 1，并按预登记 amendment 进行 Human/Model 1/Model 2 直接比较 | EVID-031 为 `Completed`；三方 Stage B 精确一致 21/120，106 条存在阶段分歧，发现 `approval/disapproval` 驱动的 stance-emotion 任务错位；不生成 gold、IAA 或稳定性结论 |
| 2026-08-08 | 完成 KOTE、Hotter and Colder 与 Weibo Emotion Cause Corpus 的固定版本可行性审计 | EVID-032 为 `Verified`；KOTE 通过 C0 候选门、Weibo 仅通过 auxiliary 门、Hotter 阻塞；独立 verifier 35/35 项通过，未下载 test、未 hydration、未训练或采用最终数据集 |
| 2026-08-08 | 审计后明确排除 Hotter and Colder | 不改变 EVID-032 的客观审计结果；冻结快照仅保留追溯，不再 hydration，且不进入训练、模型选择、评估或论文主张 |
| 2026-08-08 | 执行并独立验证 `DATA-WEIBO-TASK-V1`，采用 EClass 为下一阶段主数据轨 | EVID-033 为 `Verified`；8,540 条七分类 paired-view 样本按 leakage component 划分为 5,995/1,272/1,273，verifier 33/33、单元测试 10/10；test labels 密封，未训练模型 |
| 2026-08-08 | 完成 EXP-041 Weibo Stage 2 train-only 模型栈预检并保留两次前序失败与 verifier amendment | EVID-034 为 `Verified`；Qwen 严格格式有效率 37/42，精确 LoRA 两步更新与重载通过，独立审计 16/16、0 mismatch；该结果不是分类准确率，validation/test 未访问 |
| 2026-08-08 | 完成并独立验证 EXP-042 Weibo Stage 3 M0/M1/M2 train/dev baselines | EVID-035 为 `Verified`；M2 target/context Macro-F1=`0.594925 +/- 0.012919`/`0.594219 +/- 0.012046`，配对 context delta 实际并列并按规则选择 target-only；8/8 检查、0 mismatch，test 未读取 |
| 2026-08-09 | 完成并独立验证 EXP-043 Weibo Stage 4 frozen Qwen context x reasoning 2x2 | EVID-036 为 `Verified`；按 Macro-F1 选择 C=`0.333818`，context 平均效应为负、reasoning 平均效应为正但 Accuracy/Weighted-F1/格式和成本未同步改善；10/10 检查、0 mismatch，test 未读取 |
| 2026-08-09 | 完成并独立验证 EXP-044 Weibo Stage 5 本机 Qwen3-4B LoRA 成本预检 | EVID-037 为 `Verified`；200 step 耗时 `355.254 s`、峰值 `8.679 GB`，adapter 与重载通过；2 epochs x 3 seeds 的训练投影为 `21.72 h`，13/13 检查通过，validation/test 未读取且未报告性能指标 |
| 2026-08-09 | 在模型推理前保留 EXP-045 tokenization 初始化失败，并完成 EXP-046 reasoning-on runtime-equivalence gate | EVID-038 为 `Verified`；singleton 重放三层 `16/16`，batch 组成重排后标签 `14/16`、raw `5/16`，冻结 singleton；12/12 检查通过，validation/test 未读取且未报告性能指标 |
| 2026-08-10 | 完成 EXP-047 seed 42 正式 train-only、adapter load-forward 与双次 singleton replay，并保留两个 verifier 阶段状态缺陷及 amendment | EVID-039 为 `Verified`；训练与回放 V2 均 `Passed`，validation/test 未读取、seeds 43/44 未授权，不报告分类性能 |
| 2026-08-10 | 完成 EXP-047 seed 43 正式 train-only、adapter load-forward 与双次 singleton replay，并保留首次受限 Metal 启动失败 | EVID-040 为 `Verified`；attempt 2 训练与回放 verifier 及 `--check` 均 `Passed`，validation/test 未读取、seed 44 未授权，不报告分类性能 |
| 2026-08-11 | 完成 EXP-047 seed 44 正式 train-only、adapter load-forward 与双次 singleton replay | EVID-041 为 `Verified`；训练与回放 verifier 及 `--check` 均 `Passed`，至此三 seed 的训练/回放门全部完成；validation/test 未读取，不报告分类性能，下一步为 matched validation 授权门 |
| 2026-08-12 | 完成 EXP-047 matched singleton validation 与独立复算 | EVID-042 为 `Verified`；LoRA Macro-F1=`0.562471 +/- 0.021408`，相对 matched reference `+0.228873` 且三个 group-bootstrap CI 均高于 0；仍比 EXP-042 M2 低 `0.032454`，test 未读取，下一步为冻结 dev 错误分析 |
| 2026-08-12 | 完成 EXP-048 冻结 Weibo dev 错误分析、48 条目的性案例复核与独立复算 | EVID-043 为 `Verified`；LoRA 的主要 Accuracy 收益来自 reference 有效输出行而非仅格式失败，仍在少数类、ontology 边界和 seed 稳定性上落后 encoder；test 未读取，下一步为 TEST-READY 冻结清单 |
| 2026-08-13 | 冻结 TEST-READY 合同并完成 EXP-049 Weibo 一次性正式 test、report-only finalization recovery 与独立复算 | EVID-044 为 `Verified`；9 个冻结单元、1,273 条 test、11,457 条预测和全部预注册比较均复算一致；LoRA 明确优于 matched Qwen，但与 encoder 的 `-0.013009` 差值 CI 跨 0；test 自此已消费 |
| 2026-08-13 | 执行并独立验证 `DATA-SO-TASK-V1`，冻结 Stack Overflow C0 六标签主任务 | EVID-045 为 `Verified`；4,800 行按 4,681 个 duplicate components 划分为 3,360/720/720，53/53 项检查与 11/11 项 unit tests 通过；Stack Overflow test 保持 sealed、未授权、未消费，下一步登记 M1-M4 Major protocols 与共享 preflight |
| 2026-08-13 | 冻结 EXP-051 至 EXP-054 并完成 EXP-050 Stack Overflow 共享 train-only 模型预检 | EVID-046 为 `Verified`；保留首个 digest-scope 失败尝试，修正后五个 stage 与 77/77 项独立检查、7/7 项 unit tests 通过；validation/test 未访问、无性能指标，下一步为 EXP-051 seed 42 train + validation 完整性门 |
| 2026-08-13 | 完成 EXP-051 seed-42 train + validation 完整性门、MPS 失败留档与 CPU recovery | EVID-047 为 `Verified`；epoch 4、共享阈值 0.25、Macro-F1=`0.604619`，独立 verifier 67/67 与 model-comparison tests 16/16 通过；`surprise` F1=0，test 未访问，seeds 43/44 待单独授权 |
| 2026-08-13 | 按独立 amendment 完成 EXP-051 seed-43 train + validation 与 checkpoint 重放 | EVID-048 为 `Verified`；epoch 4、共享阈值 0.30、Macro-F1=`0.625341`，独立 verifier 72/72 通过；两 seed 描述性均值 `0.614980 +/- 0.014652`，`surprise` 再次 F1=0，seed 44 与 test 仍封存 |
| 2026-08-14 | 按独立 amendment 完成 EXP-051 seed-44，并冻结 M1 三 seed validation aggregate | EVID-049 为 `Verified`；seed 44 verifier 72/72、aggregate verifier 53/53；共享阈值 Macro-F1=`0.617254 +/- 0.011084`，但 subset accuracy 低于固定阈值；`surprise` 三 seed 均为 F1=0，test 与 EXP-052 仍封存 |
| 2026-08-14 | 完成 EXP-052 seed-42 frozen Qwen + linear head train + validation 完整性门，并在正式运行前吸收只读代码审计 | EVID-050 为 `Verified`；修正后 dry-run 51/51、EXP-052 tests 11/11、正式 verifier 70/70；共享阈值 Macro-F1=`0.324929`，比同 seed M1 低 `0.279691`，但仅形成单 seed 线性可解码性负证据；test、seeds 43/44 与 M3/M4 继续封存 |
| 2026-08-14 | 冻结并独立验证 EXP-052 seed-42 feature-cache 的只读跨 seed 复用边界 | EVID-051 为 `Verified`；cache gate 74/74、专项 tests 7/7，通过 source/cache/data/order/token/privacy/split 检查；无训练、无性能指标、无 Qwen forward，seeds 43/44、M3/M4 与 test 仍未授权 |
| 2026-08-14 | 按独立授权完成 EXP-052 seed-43 只读 cached-head train + validation，并保留首次 preflight 接口失败 | EVID-052 为 `Verified`；修复后 preflight 73/73、formal verifier 99/99、EXP-052 回归测试 26/26；共享阈值 Macro-F1=`0.353593`，两 seed 的 fixed/shared 排序相反，形成 calibration/seed 敏感性警告；test、seed 44 与 M3/M4 继续封存 |
| 2026-08-14 | 按独立授权完成 EXP-052 seed-44 只读 cached-head train + validation | EVID-053 为 `Verified`；preflight 78/78、formal verifier 104/104、EXP-052 回归测试 28/28；共享阈值 Macro-F1=`0.278145`，比同 seed M1 低 `0.343658`，进一步确认 frozen-linear 弱表现与 seed/calibration 敏感性；在该 gate 完成时，test、M3/M4 和 M2 三 seed aggregate 继续封存 |
| 2026-08-14 | 完成并独立验证 EXP-052 M2 三 seed validation aggregate | EVID-054 为 `Verified`；aggregate verifier 85/85、EXP-052 回归测试 36/36；共享阈值 Macro-F1=`0.318889 +/- 0.038085`，相对 matched M1 为 `-0.298365 +/- 0.039425` 且 3/3 seed 为负。结论限定于 frozen final-layer last-token + linear head；test、M3/M4 继续封存，下一步另行登记 EXP-053 |
| 2026-08-14 | 完成并独立验证 EXP-053 M3 Classification LoRA train-only 资源门，保留首次内存计量失败 | EVID-055 为 `Verified`；attempt 2 在未改变 13 GB/8 h-per-seed/24 h-three-seed 门的前提下通过，训练/回放峰值 `8.674`/`8.376 GB`、投影 `4.436 h/seed`、checkpoint replay 误差 0；专项 tests 12/12、verifier 102/102。Validation/test 未访问、无性能结果，正式 seed 42 仍需单独授权 |
| 2026-08-14 | 完成并独立验证 EXP-053 M3 formal seed 42，保留首次 verifier schema 失败 | EVID-056 为 `Verified`；共享阈值 Macro-F1=`0.637786`，相对 matched M2 delta=`+0.312857`、95% CI `[+0.223280,+0.388544]`；正式运行 `3.821 h`、峰值 `8.702 GB`。Attempt 1 为 `135/136 Failed` 且 replay 误差 0，schema-only attempt 2 完整重放 `148/148 Passed`；test、seeds 43/44 与 EXP-054 继续封存 |
| 2026-08-15 | 按第二份独立授权完成并验证 EXP-053 M3 formal seed 43 | EVID-057 为 `Verified`；共享阈值 Macro-F1=`0.663515`，相对 matched M2 delta=`+0.309922`、95% CI `[+0.208105,+0.390880]`；正式运行 `3.544 h`、峰值 `8.699 GB`，verifier 完整回放 `143/143 Passed` 且概率误差 0。Seeds 42/43 描述性均值为 `0.650650 +/- 0.018194`，仍不构成三 seed family；test、seed 44 与 EXP-054 继续封存 |
| 2026-08-15 | 按第三份独立授权完成并验证 EXP-053 M3 formal seed 44 | EVID-058 为 `Verified`；共享阈值 Macro-F1=`0.660795`，相对 matched M2 delta=`+0.382650`、95% CI `[+0.298126,+0.455866]`；正式运行 `3.352 h`、峰值 `8.702 GB`，verifier 完整回放 `148/148 Passed` 且概率误差 0，回归测试 `47/47`。三个单 seed 均已验证，但 M3 aggregate、EXP-054 与 test 继续封存 |
| 2026-08-15 | 完成并独立验证 EXP-053 M3 三 seed validation aggregate | EVID-059 为 `Verified`；aggregate verifier `124/124`。共享阈值 Macro-F1=`0.654032 +/- 0.014135`，相对 matched M2 为 `+0.335143 +/- 0.041168` 且 3/3 seed 为正；相对 M1 的六标签 Macro-F1 为 `+0.036778 +/- 0.003154`，但去除低支持 `surprise` 后为 `-0.033981 +/- 0.008620`，Micro-F1 与 weighted F1 也为负。Test、EXP-054 与错误分析继续封存，下一步为单独冻结 M1/M3 validation 错误分析 |
| 2026-08-15 | 完成并独立验证 EXP-055 M1/M3 validation 错误分析 | EVID-060 为 `Verified`；M1 在去除 `surprise` 的 Macro-F1 及多数整体指标上更强，M1/M3 同时存在稳定恢复与回退。不可部署 whole-vector oracle 通过五项 router headroom 门，45 条目的性案例完成边界化复核；attempt-2 verifier `220/220`、专项测试 `16/16`。只允许另行登记 train-OOF router feasibility；EXP-054 与 test 继续密封 |
| 2026-08-15 | 完成并独立验证 EXP-054 M4 Qwen Generative LoRA 三 seed validation family | EVID-061 为 `Verified`；Macro-F1=`0.615182 +/- 0.037632`，相对同 seed M3 为 `-0.038850 +/- 0.030200` 且 3/3 seed 为负；parser-valid 为 100%，六次 60 条新进程 replay 全部逐条一致。保留首次 preflight Metal OOM，修正后 preflight `26/26`、三个 seed 各 `92/92`、aggregate `33/33`、专项测试 `10/10`。Stack Overflow test 未访问，下一步为统一 TEST-READY 合同 |
| 2026-08-15 | 冻结并独立验证 EXP-056 Stack Overflow M1-M4 统一 TEST-READY 合同 | EVID-062 为 `Verified TEST-READY`；final contract SHA-256=`bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966`，冻结四个 family x 三 seed 共 12 个单元及全部 checkpoint/adapter/head、阈值、评估和 bootstrap 合同，readiness verifier `89/89`、专项测试 `6/6`。Authorization 不存在、正式输出目录不存在、test inputs/labels 均未读取；本条不含 test 结果，下一步仍需独立一次性授权 |
| 2026-08-16 | 按授权执行并独立验证 EXP-056 Stack Overflow M1-M4 一次性正式 test | EVID-063 为 `Verified`；12/12 冻结单元先预测并封存，再一次性开标签评分。M3 明确超过 M2，但相对 M1 的六标签与五标签 CI 均跨 0；M4 六标签 Macro-F1 明确低于 M3。Post-score verifier `29/29`，无 test 后选择；Stack Overflow test 自此已消费 |
