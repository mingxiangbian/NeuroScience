# 情感与大模型：论坛文本情感识别论文与复现路线

- 更新日期：2026-07-17
- 毕设题目：Research and Implementation of Emotion Recognition System of Forum Text Based on LLM
- 当前任务：查阅相关论文，复现公开代码，自行准备论坛文本数据，为开题做准备

## 先说结论

最合理的推进顺序不是直接复现 7B 级 LLM，而是先建立一个可信、可复查的文本分类基线，再加入 LLM 对比：

1. **先跑通 TweetEval 的 emotion 子任务**：数据划分、评估脚本和预训练模型齐全，最适合验证完整训练与评估流程。
2. **把 GoEmotions 作为主参考数据集**：它来自 Reddit 评论，和论坛文本最接近；先映射为 6 类基本情绪加 neutral，再视数据质量尝试细粒度多标签。
3. **用 SpanEmo 做多标签方法对比**：只有当一条论坛文本允许同时包含多种情绪时才需要。
4. **最后做 LLM 实验**：先做 zero-shot / few-shot prompting，再考虑 LoRA；InstructERC 用来设计上下文、检索示例和辅助任务，不宜作为第一个复现对象。

**关键边界**：如果自建数据只保存单条帖子正文，主线应是 GoEmotions / TweetEval / SpanEmo；只有保存 `thread_id`、`parent_id`、回复顺序和匿名作者标识后，DialogueGCN 与 InstructERC 的会话上下文方法才真正适用。

## P1 ERC survey

### Emotion Recognition in Conversation: Research Challenges, Datasets, and Recent Advances

- Citation：Soujanya Poria, Navonil Majumder, Rada Mihalcea, and Eduard Hovy. 2019. arXiv:1905.02947.
- 原文：[arXiv](https://arxiv.org/abs/1905.02947)
- 本地 PDF：[2019-poria-erc-survey.pdf](pdfs/2019-poria-erc-survey.pdf)
- 角色：领域综述，不是首个复现对象。
- 阅读重点：情绪识别会受到上下文、说话者依赖、情绪转移、讽刺和类别不平衡影响；需要分清单条文本情绪分类与会话情感识别（Emotion Recognition in Conversation, ERC）。
- 对本项目的价值：帮助开题报告定义问题、梳理数据集与方法谱系，也能说明为什么论坛回复链可能比孤立帖子更有信息。
- 局限：综述聚焦会话数据，不能自动证明对任意论坛帖子都有效。

## P2 GoEmotions

### GoEmotions: A Dataset of Fine-Grained Emotions

- Citation：Dorottya Demszky et al. ACL 2020. DOI: 10.18653/v1/2020.acl-main.372.
- 原文：[ACL Anthology](https://aclanthology.org/2020.acl-main.372/)
- 本地 PDF：[2020-demszky-goemotions.pdf](pdfs/2020-demszky-goemotions.pdf)
- 数据与代码：[google-research/goemotions](https://github.com/google-research/google-research/tree/master/goemotions)
- 数据：58,009 条英文 Reddit 评论，27 个细粒度情绪标签加 neutral，允许多标签；官方提供固定 train/dev/test 划分与 BERT 基线。
- 角色：**本项目最重要的领域数据参考**。
- 首次复现：先用官方划分微调 `bert-base-cased` 或 `roberta-base`，报告 macro-F1、micro-F1、每类 F1 和混淆矩阵；再把 27 类映射为 6 类基本情绪加 neutral，测试标签粒度对结果的影响。
- 复现风险：官方基线环境较旧；若改用当前 Transformers/PyTorch，应标为“现代实现复现”，不要声称逐项复现原论文环境。
- 对本项目的价值：评论来源、语言风格、短文本噪声和多标签属性都比影视对白数据更接近论坛。

## P3 TweetEval

### TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification

- Citation：Francesco Barbieri, Jose Camacho-Collados, Luis Espinosa Anke, and Leonardo Neves. Findings of EMNLP 2020. DOI: 10.18653/v1/2020.findings-emnlp.148.
- 原文：[ACL Anthology](https://aclanthology.org/2020.findings-emnlp.148/)
- 本地 PDF：[2020-barbieri-tweeteval.pdf](pdfs/2020-barbieri-tweeteval.pdf)
- 数据与代码：[cardiffnlp/tweeteval](https://github.com/cardiffnlp/tweeteval)
- 数据：统一的 Twitter 文本分类基准；emotion 子任务为 anger、joy、sadness、optimism 四分类，并提供固定划分、评估脚本和 RoBERTa 系列基线。
- 角色：**最适合先跑通的低风险复现实验**。
- 首次复现：只运行 emotion 子任务，先验证官方评估脚本，再微调 RoBERTa；保存随机种子、版本、训练日志和测试预测文件。
- 对本项目的价值：能快速形成传统预训练语言模型基线，也能复用其数据格式和评估流程。
- 局限：Twitter 短文本与论坛长帖存在领域差异；四类标签也不足以覆盖复杂论坛情绪。

## P4 SpanEmo

### SpanEmo: Casting Multi-label Emotion Classification as Span-prediction

- Citation：Hassan Alhuzali and Sophia Ananiadou. EACL 2021. DOI: 10.18653/v1/2021.eacl-main.135.
- 原文：[ACL Anthology](https://aclanthology.org/2021.eacl-main.135/)
- 本地 PDF：[2021-alhuzali-spanemo.pdf](pdfs/2021-alhuzali-spanemo.pdf)
- 代码：[hasanhuz/SpanEmo](https://github.com/hasanhuz/SpanEmo)
- 方法：把多标签情绪分类表述为 span prediction，并通过相关性损失建模情绪标签之间的关系；实验覆盖英语、阿拉伯语和西班牙语 SemEval-2018 数据。
- 角色：多标签主线的首选方法论文。
- 首次复现：先复现 English 数据；与普通 `BCEWithLogitsLoss` 的 BERT/RoBERTa 多标签分类头比较，避免只复现一个复杂模型而没有强基线。
- 复现风险：仓库记录的 Python 3.6、PyTorch 1.2 环境较旧，数据还需从原竞赛入口获取；建议先锁定旧环境，再决定是原样复现还是迁移实现。
- 适用条件：标注协议允许一条文本同时拥有多个情绪，并使用 micro-F1、macro-F1、Jaccard score 等多标签指标。

## P5 DialogueGCN

### DialogueGCN: A Graph Convolutional Neural Network for Emotion Recognition in Conversation

- Citation：Deepanway Ghosal et al. EMNLP-IJCNLP 2019. DOI: 10.18653/v1/D19-1015.
- 原文：[ACL Anthology](https://aclanthology.org/D19-1015/)
- 本地 PDF：[2019-ghosal-dialoguegcn.pdf](pdfs/2019-ghosal-dialoguegcn.pdf)
- 代码：[declare-lab/conv-emotion](https://github.com/declare-lab/conv-emotion)
- 方法：把会话中的话语建成图，显式建模同一说话者与不同说话者之间的依赖以及相对位置。
- 角色：论坛线程上下文建模的结构参考，不是默认主线。
- 首次复现：先用仓库已有会话数据跑通；只有自建论坛数据保留回复关系和作者标识后，才把一条回复视为 utterance、把回复边视为关系边进行适配。
- 局限：论坛通常是异步、多分支、多参与者结构，不等同于线性对话；直接把帖子按时间排序会丢失回复树信息。

## P6 InstructERC

### InstructERC: Reforming Emotion Recognition in Conversation with Multi-task Retrieval-Augmented Large Language Models

- Citation：Shanglin Lei, Guanting Dong, Xiaoping Wang, Keheng Wang, Runqi Qiao, and Sirui Wang. arXiv:2309.11911, first submitted in 2023; local PDF is v6, 2024.
- 原文：[arXiv](https://arxiv.org/abs/2309.11911)
- 本地 PDF：[2023-lei-instructerc.pdf](pdfs/2023-lei-instructerc.pdf)
- 官方代码：[LIN-SHANG/InstructERC](https://github.com/LIN-SHANG/InstructERC)
- 方法：把 ERC 从判别式分类改写为生成任务，加入相似示例检索、说话者识别和下一情绪预测等辅助任务，并使用 LoRA 适配 ChatGLM/LLaMA 系列模型。
- 角色：LLM 主线的核心方法参考。
- 首次复现：先运行仓库 demo 并检查输入模板，再选择一个小规模数据集和单一开源模型做 LoRA；不要一开始追求论文全部数据集与全部 7B 模型的完整复现。
- 复现风险：仓库要求较特定的 Transformers 版本与 7B 级模型，且 README 明确提示模型参数发布受限；完整复现对 GPU、存储和环境兼容性要求最高。
- 适用条件：论坛数据保留上下文；若只有单条文本，可借鉴检索示例和标签描述，但不能把结果等同于 ERC 复现。

## 建议的实验矩阵

| 层级 | 模型 | 目的 | 主要指标 |
| --- | --- | --- | --- |
| Sanity baseline | TF-IDF + Logistic Regression | 检查数据与标签是否可学习 | macro-F1、per-class F1 |
| Encoder baseline | BERT/RoBERTa fine-tuning | 建立可复现的强判别式基线 | macro-F1、weighted-F1 |
| Multi-label | BCE baseline vs. SpanEmo | 检验标签相关性建模是否有效 | micro/macro-F1、Jaccard |
| LLM prompting | zero-shot vs. few-shot | 衡量无需训练时的能力与成本 | macro-F1、格式有效率、成本 |
| LLM adaptation | LoRA + retrieval template | 检验领域适配与检索示例的增益 | macro-F1、消融实验 |
| Thread context | no-context vs. parent/thread context | 判断回复上下文是否真的有用 | macro-F1、分层误差分析 |

最少需要三组对照：

1. 无上下文 vs. 父回复上下文 vs. 完整线程上下文。
2. 不做领域适配 vs. 在自建论坛数据上微调或 LoRA。
3. 随机 few-shot 示例 vs. 语义检索示例，验证检索模块是否真的贡献增益。

## 自建论坛数据的最低要求

建议每条样本至少保存这些字段：

```text
post_id, thread_id, parent_id, author_hash, created_at,
title, body, reply_depth, forum_section, source_url, labels
```

- 在采集前确定平台条款、隐私边界和可再分发范围；用户名应散列或删除。
- 清理 HTML、引用块、签名、重复转帖和纯链接内容，但保留表情符号、标点与大小写等情绪信号。
- 按 `thread_id` 划分 train/dev/test，防止同一线程泄漏到不同集合。
- 先做小规模双人标注试验，再冻结标签说明；报告一致性，而不是把 LLM 自动标签直接当作金标准。
- 首版建议采用 6 类基本情绪加 neutral；只有一致性和样本量足够时再升级为 GoEmotions 式细粒度多标签。
- 预先设定 `unclear/other` 处理规则，并记录类别分布和每类最少样本量。

## 开题阶段可形成的研究问题

1. 在论坛文本上，领域微调后的编码器与 zero-shot/few-shot LLM 哪一种更准确、稳定且成本更低？
2. 回复链上下文能否显著改善情绪识别，还是只对讽刺、指代和情绪转移样本有效？
3. 语义检索示例、标签定义和 LoRA 分别贡献多少增益？
4. 从粗粒度单标签升级为细粒度多标签后，性能下降来自模型能力还是标注一致性？

## 证据边界

- **文献结论**：论文的任务定义、数据规模、公开代码与作者报告的实验设置，均以原文和官方仓库为准。
- **助手综合判断**：GoEmotions 最接近论坛数据、TweetEval 最适合先跑通、InstructERC 不宜作为首个完整复现，属于基于数据形态、代码环境和算力要求做出的项目规划判断。
- **待验证问题**：自建数据是英文还是中文、是否保留回复树、采用单标签还是多标签。这三项会直接改变最终模型与论文主线。
