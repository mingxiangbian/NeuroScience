# Source Map: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
status: active
tags: [emotion-recognition, forum-text, llm, sources]
project: llm-forum-text-emotion-recognition
---

## Scope

本来源地图服务 [`../projects/llm-forum-text-emotion-recognition/`](../projects/llm-forum-text-emotion-recognition/)。论文阅读笔记和本地 PDF 保存在 [`../papers/llm-forum-text-emotion-recognition/`](../papers/llm-forum-text-emotion-recognition/)，本文件只追踪来源角色、代码、数据和使用边界。

当前来源支持开题与复现规划，不代表自建论坛数据、模型结果或项目结论已经完成。

## Project Sources

| Source | Role | Local record | Status |
| --- | --- | --- | --- |
| UESTC graduation topic listing | 题目、项目领域、类型、导师与邮箱 | [`../projects/uestc-fyp-topics-2026-2027/topics.md`](../projects/uestc-fyp-topics-2026-2027/topics.md) | archived snapshot |
| Supervisor reply relayed by user | 当前准备任务：查论文、复现代码、准备数据、完成开题 | 原始邮件由用户保留；摘要见项目 README | user-confirmed |
| Structured reading route | 论文顺序、复现风险、实验矩阵与数据最低要求 | [`../papers/llm-forum-text-emotion-recognition/reading-route.md`](../papers/llm-forum-text-emotion-recognition/reading-route.md) | available |

## Core Literature

| Source | Year | Role in project | Paper | Official code or data | Status |
| --- | --- | --- | --- | --- | --- |
| Poria et al., "Emotion Recognition in Conversation: Research Challenges, Datasets, and Recent Advances" | 2019 | 定义 ERC、上下文、说话者依赖与情绪转移问题 | [arXiv](https://arxiv.org/abs/1905.02947) | N/A | local reading package |
| Demszky et al., "GoEmotions: A Dataset of Fine-Grained Emotions" | 2020 | 最接近论坛评论的数据参考与细粒度多标签基线 | [ACL Anthology](https://aclanthology.org/2020.acl-main.372/) | [google-research/goemotions](https://github.com/google-research/google-research/tree/master/goemotions) | local reading package |
| Barbieri et al., "TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification" | 2020 | 首个低风险复现与统一评估流程 | [ACL Anthology](https://aclanthology.org/2020.findings-emnlp.148/) | [cardiffnlp/tweeteval](https://github.com/cardiffnlp/tweeteval) | local reading package |
| Alhuzali and Ananiadou, "SpanEmo: Casting Multi-label Emotion Classification as Span-prediction" | 2021 | 多标签方法与普通 BCE 基线的对照 | [ACL Anthology](https://aclanthology.org/2021.eacl-main.135/) | [hasanhuz/SpanEmo](https://github.com/hasanhuz/SpanEmo) | local reading package |
| Ghosal et al., "DialogueGCN: A Graph Convolutional Neural Network for Emotion Recognition in Conversation" | 2019 | 回复上下文和关系图建模参考 | [ACL Anthology](https://aclanthology.org/D19-1015/) | [declare-lab/conv-emotion](https://github.com/declare-lab/conv-emotion) | local reading package |
| Lei et al., "InstructERC: Reforming Emotion Recognition in Conversation with Multi-task Retrieval-Augmented Large Language Models" | 2023 | LLM、示例检索、辅助任务与 LoRA 参考 | [arXiv](https://arxiv.org/abs/2309.11911) | [LIN-SHANG/InstructERC](https://github.com/LIN-SHANG/InstructERC) | local reading package |

## Candidate Public Datasets

| Dataset | Relevance | Known boundary | Decision |
| --- | --- | --- | --- |
| TweetEval emotion | 适合先验证训练和评估管线 | Twitter 四分类与论坛长文本存在领域差异 | reproduce first |
| GoEmotions | 58,009 条英文 Reddit 评论，27 类情绪加 neutral，可多标签 | 标签粒度高，官方基线环境较旧 | primary reference |
| SemEval-2018 Affect in Tweets | SpanEmo 的英语多标签实验来源 | 需单独核查数据获取与许可 | pending review |
| 自建论坛数据 | 与最终题目最直接相关 | 平台、授权、隐私、语言和再分发均未确认 | blocked |

## Source Checks Before Use

每个论文、代码仓库或数据集进入实验前记录：

- 固定 URL、访问日期、版本、release 或 commit。
- 论文是否同行评议，代码是否为作者官方仓库。
- License、数据条款和允许的再分发方式。
- 原始任务、标签、划分与本项目改造之间的差异。
- 代码环境是否过旧，当前运行属于原样复现还是现代化实现。
- 论文报告结果与本地复现结果是否使用相同指标。

## Forum Data Source Checklist

在目标论坛确定前，不把任何论坛列为已批准数据源。候选来源必须回答：

- 平台条款是否允许自动采集和研究使用。
- 文本是否包含用户名、联系方式、地理位置或其他直接标识符。
- 删除用户名是否足够，还是文本本身仍可能重新识别作者。
- 是否需要伦理审查、导师书面确认或平台许可。
- 原始文本能否公开，还是只能发布匿名化派生数据或统计结果。
- 用户删帖后是否有同步删除机制。
- 线程结构和时间信息如何保留而不暴露身份。

## Evidence Boundary

- 论文作者报告的结果属于文献结论，不能写成本项目结果。
- “GoEmotions 最接近论坛数据”“TweetEval 最适合先跑通”属于当前项目规划判断。
- 自建数据的规模、语言、标签、合规性和模型效果均为待验证信息。
