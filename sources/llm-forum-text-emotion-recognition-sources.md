# Source Map: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
last-reviewed: 2026-08-05
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
| GoEmotions | 58,009 条英文 Reddit 评论，27 类情绪加 neutral，可多标签 | 官方 raw release 可闭集关联 metadata，但 train/dev 仅 157/48,836 个 parent comment 有文本；raw 未分 split | benchmark completed; closed-corpus context not viable at scale |
| IAC 2.0 | 三个英文论辩论坛子库；4forums 有大量显式 parent 与 quote-response 关系 | 没有类别情绪标签；官方允许免费研究使用，但没有语料专属开放许可证或公开再分发条款，且含用户名及部分人口属性 | conditional research-use candidate; [audit complete](llm-forum-text-emotion-recognition-iac2-assessment.md) |
| SemEval-2018 Affect in Tweets | SpanEmo 的英语多标签实验来源 | 需单独核查数据获取与许可 | pending review |
| 自建论坛数据 | 与最终题目最直接相关 | 平台、授权、隐私、语言和再分发均未确认 | blocked |

## Forum Context Compliance Check

Reviewed: 2026-08-05

| Source | Current official statement relevant to this project | Project consequence |
| --- | --- | --- |
| [GoEmotions README](https://github.com/google-research/google-research/blob/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/README.md) | filtered TSV 的第三列为 comment ID；raw release 包含 `id`、`parent_id`、subreddit 和时间等元数据 | 闭集 join 已验证：48,836 个 train/dev targets 全部匹配 metadata，但只有 157 个 parent comment 在 raw 中有文本；详见 `DATA-FCTX-CJ-V1` |
| [GoEmotions paper](https://aclanthology.org/2020.acl-main.372/) | 来源评论覆盖 Reddit 2005 年至 2019 年 1 月 | parent recovery 需要能覆盖这一历史区间的数据源 |
| [Reddit developer access](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data) | 当前唯一授权的学术研究路径是 Reddit for Researchers；ML/AI training 需要明确同意 | 普通 API、网页抓取和未授权第三方工具不能用于本毕设恢复或训练 |
| [Reddit for Researchers](https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program) | 申请需要高校身份、机构 sponsor 和伦理批准或 exemption；当前数据说明为五年历史并有六个月延迟 | 标准覆盖没有说明包含 GoEmotions 的 2005--2019 parents，必须书面确认 |
| [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | 未经 RFR 的研究数据收集不被允许；数据保留、删除和 AI training 均受限制 | 在批准前不得下载新增 Reddit 数据、恢复 parent 或训练模型 |
| [Deleted-data handling](https://support.reddithelp.com/hc/en-us/articles/24656943463828-What-happens-when-I-delete-my-data) | 第三方应停止展示或使用已删除内容 | 正式数据协议必须包含删除同步和销毁规则 |
| [IAC 2.0 official release](https://nlds.engineering.ucsc.edu/iac2/) and [UCSC corpora policy](https://nlds.engineering.ucsc.edu/software/) | 官方 MySQL dump 提供显式 parent、quote 和论辩标注；UCSC 将 IAC V2 列为可供其他研究者免费研究使用；本地实测 4forums 有 403,374 个可解析 parent links | 本地非商业毕设标注、训练和评估有条件通过；没有类别情绪 gold labels，也没有原文、衍生数据、商用或 checkpoint 的明确发布权，详见 [专项评估](llm-forum-text-emotion-recognition-iac2-assessment.md) |

当前决定记录于
[`DATA-FCTX-PR-V1`](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-source-parent-recovery-pilot-v1.md)
与
[`DATA-FCTX-CJ-V1`](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-closed-corpus-parent-coverage-v1.md)。

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
