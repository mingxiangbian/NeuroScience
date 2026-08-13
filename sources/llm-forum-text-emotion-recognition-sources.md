# Source Map: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
last-reviewed: 2026-08-08
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
| Demszky et al., "GoEmotions: A Dataset of Fine-Grained Emotions" | 2020 | 已完成的 Reddit target-only 细粒度多标签基线 | [ACL Anthology](https://aclanthology.org/2020.acl-main.372/) | [google-research/goemotions](https://github.com/google-research/google-research/tree/master/goemotions) | local reading package |
| Barbieri et al., "TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification" | 2020 | 首个低风险复现与统一评估流程 | [ACL Anthology](https://aclanthology.org/2020.findings-emnlp.148/) | [cardiffnlp/tweeteval](https://github.com/cardiffnlp/tweeteval) | local reading package |
| Alhuzali and Ananiadou, "SpanEmo: Casting Multi-label Emotion Classification as Span-prediction" | 2021 | 多标签方法与普通 BCE 基线的对照 | [ACL Anthology](https://aclanthology.org/2021.eacl-main.135/) | [hasanhuz/SpanEmo](https://github.com/hasanhuz/SpanEmo) | local reading package |
| Ghosal et al., "DialogueGCN: A Graph Convolutional Neural Network for Emotion Recognition in Conversation" | 2019 | 回复上下文和关系图建模参考 | [ACL Anthology](https://aclanthology.org/D19-1015/) | [declare-lab/conv-emotion](https://github.com/declare-lab/conv-emotion) | local reading package |
| Lei et al., "InstructERC: Reforming Emotion Recognition in Conversation with Multi-task Retrieval-Augmented Large Language Models" | 2023 | LLM、示例检索、辅助任务与 LoRA 参考 | [arXiv](https://arxiv.org/abs/2309.11911) | [LIN-SHANG/InstructERC](https://github.com/LIN-SHANG/InstructERC) | local reading package |

## Dataset Selection Standard

Frozen: 2026-08-08

### Task identity

本项目默认任务是：根据目标用户的帖子或评论，识别**该作者在目标文本中表达的情绪**。单标签和多标签数据均可进入候选池，但必须保留原始标注定义，不把立场、毒性、风险、读者反应或主题整体情绪改写成作者情绪。

“论坛”按异步用户讨论理解，包括传统论坛、问答社区、微博/社交媒体评论线程和主题讨论区；即时聊天与剧本对话只作为迁移数据，不作为最终论坛域证据。

### Context priority

上下文是强优先项，不是硬性入场条件。无上下文但人工标注可靠、规模足够且领域真实的数据集仍可用于训练或 target-only 对照。

| Level | Available information | Permitted role |
| --- | --- | --- |
| C2 | 显式 parent/reply 关系、此前评论或完整线程 | 主上下文实验；同一样本做 `target-only` 与 `target + context` 配对消融 |
| C1 | 主题、标题、根帖、事件或被回复文本，但没有完整回复链 | 有限上下文实验；必须说明缺少哪一层关系 |
| C0 | 只有目标文本 | 训练、单文本基线或跨域对照；不能回答“上下文是否有帮助” |

语言不作为质量减分项。若混合语言训练或跨语言比较，需将语言迁移单独登记为实验变量，不能把语言差异误写成模型差异。

### Access and evidence states

| State | Meaning |
| --- | --- |
| executable now | 数据文件可直接取得，且研究使用条款或许可证足够明确 |
| conditional | 需要邮件申请、平台审批、伦理确认、API 授权或进一步核对条款 |
| literature only | 论文描述符合，但未找到可用的官方数据发布 |
| auxiliary only | 标签目标、标注来源或领域与主任务不一致，只能用于迁移、弱监督或方法参考 |
| excluded by project decision | 已完成必要审计，但明确不进入本论文后续数据、实验或结论；仅保留来源与排除依据 |

规模只是用途判据，不替代标注质量：约 3,000 条以上可考虑训练，500--2,999 条适合定量评估，100--499 条更适合挑战集或错误分析，更小的数据只作定性案例。

## Search Snapshot

Reviewed: 2026-08-08

本轮检索覆盖 ACL Anthology、作者或实验室仓库、GitHub、CLARIN、Zenodo、大学数据页及论文引用链。检索同时覆盖英文、中文、韩文、越南文、孟加拉文、冰岛文等候选；没有因为数据语言为中文或非英文而降级。

本轮没有联系作者或平台。以下“可公开访问”仅表示找到了官方文件入口；没有明确许可证时，仍不能推断可以重新发布原文、衍生标注或模型 checkpoint。

`KOTE + Hotter and Colder + Weibo Emotion Cause Corpus` 的固定版本、真实字段与样本质量已按
[`DATA-FCTX-PUBLIC-AUDIT-V1`](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-public-candidate-viability-audit-v1.md)
完成本地审计；聚合结果和独立 35 项复核见
[audit report](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md)。

### Hugging Face Follow-up Snapshot

Reviewed: 2026-08-09

本轮补充检索 Hugging Face Dataset Hub，并核对数据卡和可取得的论文说明。下表仅登记候选，**不改变当前已冻结实验、数据采用决定或模型路线**；待当前实验结束后，再对值得保留的候选执行字段、切分、重复、标签长尾、许可证和平台条款审计。

| Dataset | Domain, labels and scale | Context | Access state | Deferred assessment |
| --- | --- | --- | --- | --- |
| [EXPRESS](https://huggingface.co/datasets/bangzhao/express-emotion-recognition) / [paper](https://arxiv.org/abs/2509.09593) | 约 3.36 万条英文 Reddit 自述文本，覆盖约 6,930 个 subreddit；把作者显式自述的情绪词替换为 `<mask>`，形成 251 类细粒度开放词表情绪恢复任务 | C0；有平均约 259 词的同帖长文本语境，但没有结构化 parent/target 回复关系 | candidate：数据卡标注 Apache-2.0，Hub 当前只显示 train split；正式使用前仍须核对原始 Reddit 数据条款 | **最值得后续审计的新候选**；它把固定标签分类改为更适合生成式 LLM 的 masked/open-vocabulary prediction，但自述标签、单一 split、长尾和 segment leakage 都需要专项控制 |
| [BRIGHTER Emotion Categories](https://huggingface.co/datasets/brighter-dataset/BRIGHTER-emotion-categories) | 139,583 条、28 种语言的人工标注社交媒体文本；anger/disgust/fear/joy/sadness/surprise 六类多标签，含英文和普通话配置 | C0 | candidate：CC BY 4.0，提供 train/dev/test | 许可和标签体系清楚，适合多语言或固定六标签控制；没有论坛线程，不能单独回答上下文问题 |
| [ALOE](https://huggingface.co/datasets/Blablablab/ALOE) | 真实英文 Reddit 发帖者与回复者文本，含 distress、condolence、empathy 分数、appraisal span 和 alignment；数据卡报告 9,284 个 appraisal annotations、3,262 个 alignments | C2-like parent/response pair | auxiliary only：gated，CC BY-NC-SA 4.0，需提交联系信息 | 有真实回复结构，但预测对象不是目标作者的离散情绪类别；只保留为 appraisal、empathy 或上下文表征辅助候选 |
| [EmotionAnalysis](https://huggingface.co/datasets/llama-lang-adapt/EmotionAnalysis) | SemEval-2025 Task 11 Track C 的多语言社交媒体六类多标签版本 | C0 | benchmark candidate：CC BY-SA 4.0；数据卡仅列 validation/test，viewer 因文件布局不可用 | 可作外部 challenge set；缺少训练划分且与 BRIGHTER 任务重合，不作为优先训练源 |
| [COVID-19 Weibo Emotion](https://huggingface.co/datasets/souljoy/COVID-19_weibo_emotion) | 15,606 条中文微博，neutral/happy/angry/sad/fear/surprise 六类单标签；数据卡列出 8,606/2,000/3,000 的 train/validation/test | C0 | conditional：可访问，但数据卡未提供足够明确的许可证信息 | 可作中文领域控制；COVID-19 单一主题限制外部效度，正式使用前须核对来源和使用权 |
| [NUSTM/ECF](https://huggingface.co/datasets/NUSTM/ECF) | 1,374 段影视对话、13,619 个 utterances，含情绪标签与 emotion-cause pairs | 多轮对话上下文 | auxiliary only | 可用于情绪原因或上下文迁移，但属于剧本对话而非论坛，不承担论坛域最终结果 |

本轮也检查了若干合成情绪对话、社区重映射版 GoEmotions 和混合来源聚合数据。它们没有提供比官方数据更可靠的新 gold labels，或存在合成文本、来源与泄漏边界不清的问题，因此未进入当前候选池。Hugging Face 检索仍未发现同时具备真实论坛线程、明确 parent/target、目标作者类别情绪金标、足够规模和清晰许可的可直接执行 C2 主数据集。

## Target-author Emotion Candidates

| Dataset | Domain, labels and scale | Context | Access state | Recommended role |
| --- | --- | --- | --- | --- |
| [RESEMO](https://aclanthology.org/2024.findings-acl.970/) / [official repository](https://github.com/Alack1/RESEMO) | 3,813 条中文微博根帖、68,781 条评论；人工标注 16 类作者情绪、响应对象和上文情绪原因 | C2 | conditional：仓库未发布数据或许可证，README 要求邮件索取 | **科学匹配度最高**；若后续取得使用许可，可作为主数据集。论文报告加入响应关系后 13B 微调模型 accuracy 从 0.5580 到 0.5740，但未报告 Macro-F1，不能把该提升直接当作本项目预期 |
| [Stack Overflow Emotion Gold Standard](https://github.com/collab-uniba/EmotionDatasetMSR18) / [paper](https://arxiv.org/abs/1803.02300) | 4,800 条 Stack Overflow 问题、回答或评论；6 类离散情绪加隐含 neutral，允许多标签；每条 3 人标注 | C0 | conditional：文件可下载且实验室说明供研究使用，但仓库无明确 LICENSE，原文再分发边界待核对 | 真实论坛域 target-only 训练/评估；软件问答领域窄，且只有 133 条双标签样本 |
| [JIRA Emotion Corpus](https://iris.unica.it/handle/11584/211649) | 来自软件 issue tracker 的 2,000 条评论和 4,000 个句子；由三个标注子集组成，标注人数和 emotion label space 不统一 | C0；若原始 issue ID 完整，理论上可回接 issue thread，但不能预设可恢复 | literature only：机构页仍在，旧数据归档与许可证未得到当前确认 | 真实异步论坛的补充证据；在统一标签、去重和访问边界解决前，不适合作为主训练集 |
| [Hotter and Colder](https://aclanthology.org/2025.nodalida-1.18/) / [CLARIN release](https://repository.clarin.is/repository/xmlui/handle/20.500.12537/352?locale-attribute=en) | 冰岛语博客评论；论文报告 12,232 条评论、19,301 次人工判断；本地发布包实测 12,675 个 URL/时间目标键、19,828 行标注，8 个情绪分别做二元标注 | 理论上可恢复此前评论形成 C2；当前包只有链接、标签和时间 | audited then excluded：审计时因无文本、实时抓取、隐私和 schema 风险判为 blocked；2026-08-08 项目决定排除 | 不进入本论文的 hydration、训练、模型选择、评估或结果主张；冻结审计仅作追溯 |
| [Chinese Event-comment Social Media Corpus](https://aclanthology.org/2020.lrec-1.203/) | 200 个微博新闻事件、30,000 条评论，其中 10,000 条人工标注 happiness/sadness/anger/fear/surprise；多标签 | C1：保留新闻根帖，主动移除评论间回复 | literature only：未找到官方数据入口或数据许可证 | 与作者情绪和事件上下文高度匹配；若未来可取得，适合 C1 主评估 |
| [Weibo Emotion Cause Corpus](https://github.com/wjhou/Weibo-Emotion-Corpus) / [paper](https://doi.org/10.1145/3132684) | 本地固定仓库实测 12,586 条原因任务逻辑记录；名为 `emotion_classification.tsv` 的文件有 23,127 条逻辑记录，其中 12,052 条为原因 scaffold、11,075 条为情绪 clause | C1 auxiliary | eligible auxiliary：仓库标注 Apache-2.0；未恢复额外微博内容 | 两个 TSV 是不同任务视图，不能按行 join；情绪标签混合离散情绪、正负中性、`No_emotion` 和 composite。仅在另行冻结映射、group split 与泄漏规则后用于情绪原因/有限上下文辅助实验 |
| [KOTE](https://aclanthology.org/2024.lrec-main.1499/) / [official repository](https://github.com/searle-j/kote) | 50,000 条韩语在线评论；43 类情绪加 `NO EMOTION`，5 人投票经作者缩放和阈值转成多标签，平均 7.91 个正标签；固定 40k/5k/5k 划分 | C0 | eligible training/control：仓库 MIT；本轮仅取得并审计 train/validation，未下载 test | **当前最强公开 target-only 训练/控制候选**；train/validation 无 ID 或精确文本重合，但必须先冻结标签映射和 `NO EMOTION` 共现规则，且不能单独回答上下文研究问题 |
| [GoEmotions](https://aclanthology.org/2020.acl-main.372/) | 58,009 条英文 Reddit 评论，27 类情绪加 neutral，人工多标签 | C0 in practice | completed locally；新增 Reddit 获取仍受当前平台研究政策约束 | 已完成的通用 target-only 复现基准；官方闭集无法规模化恢复 parent，不再把它当上下文数据集 |
| [CancerEmo](https://aclanthology.org/2020.emnlp-main.715/) | 在线癌症社区的 25,000 个句子；8 个 Plutchik 情绪逐类二元人工判断，允许多标签；约 8,500 句至少有一种情绪 | C0；论文将相邻帖子上下文列为未来工作 | literature only：未找到官方数据发布或当前许可证 | 人工标注质量和规模都强，但医疗领域窄、无上下文且不可立即取得；可作高质量 C0 文献对照，不改变当前主路线 |
| [MMEmo](https://aclanthology.org/2022.wassa-1.1/) / [university release](https://www.ims.uni-stuttgart.de/en/research/resources/corpora/mmemo/) | 1,380 条 Reddit 帖子，第二阶段保留 1,054 条情绪样本；8 个 Plutchik 标签，3 人标注，多模态 | C0 | conditional：官方文件可下载，正式采用前仍需核对数据条款 | 社交文本小型挑战集；按情绪词检索造成选择偏差，不适合作为主训练集 |
| [Vent self-labeled emotion corpus](https://arxiv.org/abs/1901.04856) / [Zenodo metadata](https://zenodo.org/records/2537838) | 约 3,300 万条作者自选情绪标签帖子，705 个标签、63 个大类 | C0 | conditional：公开包不含文本，文本仅按研究和非商业用途申请 | 作者自标标签对“谁的情绪”最清楚，但访问、标签长尾和平台领域均需专项审核 |
| [MedSenti / IVF forum](https://aclanthology.org/W14-5907/) | 80 个医疗论坛讨论、1,438 条消息；6 个标签混合情绪与交流功能 | C2 | conditional：论文说明研究用途可索取，未找到公开数据或许可证 | 小型顺序上下文基准；医疗领域极窄且标签不是纯情绪，不宜作为主任务 |
| [Nota Bene educational forum](https://homes.cs.washington.edu/~axz/papers/las_emojis.pdf) | 教学论坛中 25,564 条作者自标帖子；后续研究报告 79,309 条帖子中 55,437 条带标签 | C2 | literature only：未找到公开发布，且涉及课程平台授权 | 线程结构和作者自标很有价值；标签混合 interested/confused/question/idea/help/frustrated 等情绪、认知和意图 |
| [MASIVE](https://aclanthology.org/2024.emnlp-main.1139/) | 英文和西班牙文 Reddit 文本，超过 1,000 个开放式 affective states；把封闭分类改为 masked-span/生成式识别 | C0 | literature only：本轮未确认官方可用数据发布 | 为“把分类改造成 LLM 擅长的生成任务”提供核心方法参考；不是当前可执行主数据集 |
| [ViGoEmotions](https://aclanthology.org/2026.eacl-long.129/) / [repository](https://github.com/ricardo-tran/ViGoEmotions) | 20,664 条越南语社交评论；27 个细粒度标签 | C0 | conditional：仓库公开，采用前核对数据许可证和平台条款 | 多语言 target-only 控制；任务覆盖好，但不是上下文论坛评估 |
| [EmoNoBa](https://aclanthology.org/2022.aacl-short.17/) / [repository](https://github.com/KhondokerIslam/EmoNoBa) | 22,698 条孟加拉语公共评论，12 个领域、6 类多标签情绪 | C0 | conditional：仓库公开，采用前核对许可证 | 多领域、非英文 target-only 控制 |
| [SM-FEEL-BG](https://aclanthology.org/2024.lrec-main.1301/) | 约 6,000 条保加利亚语 Twitter、Telegram、Facebook 文本，21 类人工情绪标签 | C0 | conditional：并非所有平台原文都能公开 | 多平台 target-only 参考；分享范围和平台差异限制直接整合 |
| [SemEval-2018 Affect in Tweets](https://aclanthology.org/S18-1001/) | 英语、阿拉伯语、西班牙语推文；多标签情绪任务，也是 SpanEmo 的实验来源 | C0 | conditional：采用前单独核对文本获取和许可 | 标准多标签对照，不是论坛上下文数据 |
| TweetEval emotion | Twitter 四分类单标签 | C0 | completed locally | 只承担评估流程和 encoder 基线验证；不再作为最终数据候选 |

## Response and Community Emotion: Separate Task Family

以下数据有论坛/评论上下文和真实系统价值，但预测对象不是目标作者当前表达的情绪。除非论文任务被明确改为“受众反应或社区情绪”，否则不得与上表混合训练或汇报同一个指标。

| Dataset | Prediction target | Context and access | Use boundary |
| --- | --- | --- | --- |
| [HEC: Hashtags, Emotions, and Comments](https://aclanthology.org/2020.emnlp-main.106/) / [repository](https://github.com/polyusmart/HEC-Dataset) | 预测微博热门话题引发的公众响应情绪；13,766 个话题，24 个 emoji 情绪，以 top-3 为多标签 | 每个话题平均约 409 条评论；仓库提供数据入口并标注 CC BY 3.0 | 与“社区情绪分布/舆情系统”高度匹配，但这是**任务目标变更**，不能用来证明作者情绪识别 |
| [CARE](https://aclanthology.org/2022.conll-1.5/) / [archived repository](https://github.com/facebookresearch/care) | 根据评论中的高精度模式，给帖子推断 7 类读者 affective response | 约 23 万条帖子 ID；弱标签、需 hydration，仓库许可表述存在不一致 | 只作弱监督和任务建模参考，不是人工作者情绪 gold set |

## Contextual Dialogue Transfer Pool

这些数据具有多轮上下文，可用于 supervised fine-tuning、上下文编码预训练或方法 sanity check，但剧本对话、面对面对话、即时聊天和客服会话与异步论坛存在明显领域差异。

| Group | Datasets | Permitted role |
| --- | --- | --- |
| 通用 ERC | EmotionLines/Friends、EmotionPush、DailyDialog、MELD、EmoryNLP、IEMOCAP | 上下文模型和 SFT 迁移；不得作为论坛域最终结果 |
| 中文对话 ERC | CPED、M3ED、MPDD | 中文上下文迁移与跨域评估 |
| 原因与同理对话 | RECCON、EmpatheticDialogues | 情绪原因、响应生成和解释任务参考 |
| 任务型对话 | EmoWOZ | 客服/任务场景鲁棒性，不代表开放论坛 |
| 共享任务短对话 | EmoContext | 短三轮上下文 sanity check |

原计划中的 EmotionLines/EmotionPush SFT 仍然可保留，但它们只能回答“对话上下文训练是否迁移到论坛”，不能代替论坛数据上的最终评估。

## Adjacent or Non-gold Sources

| Source family | Why it is not a primary emotion dataset | Possible use |
| --- | --- | --- |
| [IAC 2.0](https://nlds.engineering.ucsc.edu/iac2/) | 有完整论辩线程和 stance/agreement 等标注，但没有类别情绪 gold；[Fact-Feeling](https://nlds.soe.ucsc.edu/factfeel) 标的是事实型/感受型论证，[后续情绪研究](https://doi.org/10.1002/pra2.255) 则用外部语料训练分类器后给 IAC2 生成单标签预测，二者都不是人工类别情绪 gold；本地 pilot 还暴露出主题集中、frustration/anger 偏高和立场-情绪混淆 | 以后若需要自建论坛集，可作候选原料；当前不继续扩大标注，也不能把论文中的模型预测当真值 |
| DepressionEmo | 6,037 条 Reddit 根帖、8 个抑郁相关状态，主要标签来自四个 zero-shot NLI 模型多数票 | 弱标签或心理健康领域方法参考，不能作为人工金标准 |
| [BeCOPE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0316906) | 21 个心理健康 subreddit 的 10,118 个根帖和 58,279 条评论；约 5,000 个根帖人工标注后，用 BERT 为其余约 5,000 个生成行为与情绪伪标签；评论用于参与度分组，不是逐评论情绪 gold | 可申请完整数据，用于心理健康论坛、参与度或弱监督研究；不能作为全人工 C2 作者情绪基准 |
| Sentiment、stance、toxicity、risk、sarcasm datasets | 标签分别描述正负极性、立场、有害性、风险或修辞，不等于离散情绪 | 辅助任务、错误分析或数据过滤 |
| 自动情绪分类的大规模论坛研究 | 论文用既有分类器给数十万帖子打标签，规模大但没有独立人工 gold | 只能研究趋势或弱监督，不可用其分数验证新分类器 |
| 无标签 threaded corpora（含 IAC2、CIDC 等） | 有上下文但没有目标情绪标签 | 仅在来源、隐私、采样和标注协议通过后用于自建数据 |

## Current Recommendation

1. **理想主数据集：RESEMO。** 它同时具备真实社交讨论、显式响应对象、上文情绪原因和作者情绪标签，最接近当前研究问题；但在数据和使用条款取得前只能列为 conditional，不能开始训练。
2. **本轮审计没有找到可直接执行的 C2 主数据集。** KOTE 可承担 C0 训练/控制，Weibo 只适合 C1 情绪原因辅助；Hotter 因文本缺失、实时 hydration、隐私和 schema 风险已由项目决定排除。不能再把三者写成一个已经可执行的 `C0 + C1 + C2` 组合。
3. **上下文结论必须来自配对消融。** 对同一目标样本分别输入 `target-only` 和 `target + context`；不能拿一个 C0 数据集的 BERT 分数与另一个数据集的 LLM 分数比较后声称上下文有效。
4. **HEC 是合理但不同的论文方向。** 若最终系统改为社区情绪分布或受众响应预测，应单独修改任务定义、标签和评价指标；当前不静默切换。
5. **IAC2 暂停扩标，保留为候选 challenge source。** 已完成 pilot 足以证明当前论辩域和 V1 ontology 存在 stance-emotion 错位，不再为扩大样本量投入标注成本。

下一门是**数据采用决策**，不是立即训练：确认是否以 KOTE 作为 C0 主训练/控制、以 Weibo 作为独立辅助任务，并把上下文主结论保留为 conditional；若确认，再另行冻结 label mapping、group-disjoint split、模型对照和 test gate。Hotter 不再进入候选；RESEMO 仍保留第一顺位，但本轮按用户要求不联系作者。

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
- “RESEMO 科学匹配度最高”“KOTE 可作 C0、Weibo 只作 auxiliary”属于助手基于文献与本地审计的项目规划判断，不是文献共识；“Hotter 不用于本论文”是审计后的项目决策，不是对该数据集普遍价值的否定。
- 自建数据的规模、语言、标签、合规性和模型效果均为待验证信息。
