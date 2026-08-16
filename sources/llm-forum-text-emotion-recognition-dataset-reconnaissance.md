# 论坛文本情绪识别数据集侦察与可行性审计

---
date: 2026-08-13
last-reviewed: 2026-08-13
status: completed-reconnaissance
project: llm-forum-text-emotion-recognition
tags: [dataset-audit, forum-emotion, context, llm, licensing]
---

## 结论先行

截至 2026-08-13，本轮没有找到一个已经核实、可以立即执行、同时满足以下全部条件的数据集：

```text
真实异步论坛或 threaded community
+
目标作者/文本表达的可信 emotion gold
+
实际文本当前可获得
+
direct parent 或可验证回复路径
+
明确的研究训练权限
+
冻结且可复现的版本与划分
```

这不是检索失败，而是一个会改变论文设计的负结果。当前最合理的方案不是让一个数据集承担全部结论，而是按用途分层：

1. **主任务第一候选：RESEMO（conditional）**。科学匹配度最高，具有响应关系、情绪和原因标注；但必须先取得数据、字段和书面使用边界，当前不能训练。
2. **真实论坛 C0 金标候选：CancerEmo、Stack Overflow Emotion Gold**。二者文本可获得、人工标签较强，但都没有可用 parent；数据许可与统一无泄漏划分仍需解决。
3. **LLM 式任务候选：CovidET、EXPRESS、MASIVE**。CovidET 的“情绪 + trigger 摘要”最接近生成式任务；EXPRESS/MASIVE 适合开放词汇弱监督或中间训练，不是最终 gold。
4. **上下文辅助候选：ALOE、MPDD、EmotionPush/EmoContext**。它们可以训练或检验上下文处理，但预测目标或数据域不是论坛作者离散情绪，不能替代主评估。
5. **当前已完成的 Weibo EClass 分支保持冻结**。本报告不替换 `EXP-049` 已消费的 test，也不授权任何新训练、下载或数据采用。

因此，本轮不存在可直接打 `A. 最终主数据集` 的无条件候选，也没有通过恢复率门槛的 `B. 最终上下文子集`。最接近主路线的是“取得 RESEMO 授权”；若短期不联系作者，则可把 CancerEmo 或 Stack Overflow Gold 作为新的 target-only 论坛挑战集，并把 context 结论降为独立辅助实验，而不是伪造一个完整 C2 数据集。

## 1. 范围与判定口径

### 1.1 本轮回答的问题

现有三角矛盾是：

- GoEmotions 有细粒度人工情绪标签，但官方闭集几乎没有 parent 文本；
- IAC 2.0 有真实论坛拓扑，但没有可靠类别情绪 gold；
- Weibo EClass 有标签和局部前文，但不是可验证的 direct reply parent。

本轮目标是确认是否存在候选能比三者多满足一到两个条件，并将它们固定为以下角色之一：

| 角色 | 含义 |
| --- | --- |
| A. 最终主数据集 | 真实 forum + 可信 emotion gold + 当前文本 + 可训练 + 足够规模 |
| B. 最终上下文子集 | 可信 gold + 可验证 direct parent，可做配对 context 消融 |
| C. 弱监督/中间训练 | 自报、模板、反应或伪标签；可训练但不能作最终 gold |
| D. 外部 challenge | 真实但窄域、小样本或结构复杂，只检验泛化/失败模式 |
| E. 非论坛辅助 | 对话、共情、情绪原因等迁移或方法验证 |
| F. 淘汰/阻塞 | 文本、构念、许可或可复现性硬门未通过 |

### 1.2 标签目标

为防止把相邻任务混成 emotion recognition，本报告使用以下缩写：

| 缩写 | 预测对象 | 能否作为本论文 emotion gold |
| --- | --- | --- |
| `AE` | 第三方根据文本判断作者/文本**表达的情绪** | 可以，但不是作者内心状态的直接测量 |
| `AS` | 作者明确自报或自选的情绪/affective state | 可以作为自报信号，但需检查提示效应和标签词泄漏 |
| `RR` | 读者或社区产生的反应 | 不可以，除非论文改题为受众/社区反应预测 |
| `STA` | stance、agreement、hostility 等立场或互动功能 | 不可以；只作挑战或辅助任务 |
| `EMP` | empathy、appraisal、distress、supportiveness | 不可以直接重命名为 emotion |
| `SEN` | positive/negative/neutral sentiment | 不可以替代离散情绪 |

`AE` 仍然只是感知到的表达情绪。除非标签由作者本人提供，否则不能写成“模型识别了作者真实感受”。

### 1.3 上下文等级

| 等级 | 定义 |
| --- | --- |
| `C0` | 只有 target 文本；没有可验证的发表前上下文 |
| `C1` | 有主题、根帖、事件或相邻话语，但没有可靠 direct parent |
| `C2` | 有 `parent_id`、reply relation、目标发表前路径或完整对话 |

answer、后续回复或产生标签的评论不能被当作预测 target 时的输入，否则会引入未来信息或 label leakage。

### 1.4 证据等级

| 等级 | 本报告中的含义 |
| --- | --- |
| `L1-discovered` | 找到论文/数据名称和大致任务，关键事实仍不完整 |
| `L2-documented` | 核对原始论文与当前官方仓库/数据页，足以作角色判断 |
| `L3-file-audited` | 实际解析固定文件或本地闭集，核对字段、数量、重复与标签结构 |

本轮完成：**30 个候选家族广泛发现，10 个重点文档审计，6 项文件/闭集审计**。没有执行模型训练、外部 ID hydration 或 test 读取。

## 2. 硬条件与统一评分

主数据硬条件：真实论坛、实际文本、emotion 构念、可信标注、研究训练权限、足够规模、版本/划分可复现。上下文是高价值加分项，但不是单独否决 C0 金标的条件。

评分只用于项目排序，不代表数据集学术质量：

| 维度 | 满分 |
| --- | ---: |
| 真实 forum 属性 | 15 |
| Emotion gold 可信度 | 25 |
| 实际文本当前可获得 | 15 |
| Thread/parent context | 15 |
| 规模和类别分布 | 10 |
| 许可与训练权限 | 10 |
| 划分、ID、版本复现性 | 5 |
| 最终系统任务匹配 | 5 |
| **总分** | **100** |

解释：`>=80` 强主候选；`70-79` 可用但有明显缺陷；`55-69` 更适合作子集、预训练或 challenge；`<55` 通常不进入主路线。未知信息按 0 或保守分计，因此低分可能反映**证据缺失**而非数据本身较差。

硬覆盖规则优先于总分：文本不可获得、标签不是 emotion、训练权限明确禁止，任一成立都不能作为主数据。

## 3. 广泛候选池

### 3.1 论坛、社区与社交讨论候选

| # | 数据集 | 平台/语言 | 目标与上下文 | 当前初筛角色 |
| ---: | --- | --- | --- | --- |
| 1 | [RESEMO](https://aclanthology.org/2024.findings-acl.970/) | Weibo / 中文 | `AE`, `C2`，响应关系 + 情绪 + 原因 | 主任务首选，但访问/许可阻塞 |
| 2 | [Stack Overflow Emotion Gold](https://github.com/collab-uniba/EmotionDatasetMSR18) | Stack Overflow / 英文 | `AE`, `C0`，6 情绪 + implicit neutral | 真实论坛 target-only challenge |
| 3 | [CancerEmo](https://aclanthology.org/2020.emnlp-main.715/) | 癌症支持论坛 / 英文 | `AE`, `C0`，Plutchik-8 | 健康论坛 target-only gold |
| 4 | [JIRA Emotion Corpus](https://iris.unica.it/handle/11584/211649) | issue tracker / 英文 | `AE`, 潜在 `C2`，协议不统一 | 条件性软件社区 benchmark |
| 5 | [Chinese Event-comment Corpus](https://aclanthology.org/2020.lrec-1.203/) | Weibo 事件评论 / 中文 | `AE`, `C1`，5 情绪 + cause/reaction/target | 高价值但数据不可得 |
| 6 | [CovidET](https://aclanthology.org/2022.emnlp-main.642/) | Reddit 支持社区 / 英文 | `AE`, `C0`，7 情绪 + trigger 摘要 | LLM 生成式 challenge/辅助 |
| 7 | [CHQ-SocioEmo](https://www.nature.com/articles/s41597-023-02203-1) | Yahoo Answers 健康问答 / 英文 | `AE`, 问答对；情绪 + evidence/cause/support | 文本协议阻塞的解释辅助集 |
| 8 | [MedSenti](https://aclanthology.org/W14-5907/) | IVF 论坛 / 英文 | `AE/EMP` 混合，`C2`，1,438 messages | 小型方法参考，不作主 gold |
| 9 | [Nota Bene](https://people.csail.mit.edu/axz/papers/las_emojis.pdf) | MOOC 讨论 / 英文 | `AS` 混合情绪、认知、意图，潜在 `C2` | 自标/UI 参考，数据未发布 |
| 10 | [GoEmotions](https://aclanthology.org/2020.acl-main.372/) | Reddit 评论 / 英文 | `AE`, 实际 `C0`，27 情绪 + neutral | 已完成的 target-only 控制 |
| 11 | [KOTE](https://aclanthology.org/2024.lrec-main.1499/) | 在线评论 / 韩文 | `AE`, `C0`，43 情绪 + no emotion | 可执行跨语言 C0 控制 |
| 12 | [BRIGHTER](https://huggingface.co/datasets/brighter-dataset/BRIGHTER-emotion-categories) | 28 语种社交文本 | `AE`, `C0`，6 类多标签 | 多语言 C0 训练/挑战池 |
| 13 | [WRIME](https://github.com/ids-cv/wrime) | SNS / 日文 | `AS + AE`, `C0`，作者与读者双视角 | perspective control |
| 14 | [MMEmo](https://aclanthology.org/2022.wassa-1.1/) | Reddit 根帖 / 英文 | `AE`, `C0`，8 情绪，多模态 | 小型外部 challenge |
| 15 | [Vent](https://arxiv.org/abs/1901.04856) | 情绪分享平台 / 英文 | `AS`, `C0`，705 用户自选 affect 标签 | 授权后开放词汇辅助 |
| 16 | [EXPRESS](https://huggingface.co/datasets/bangzhao/express-emotion-recognition) | Reddit / 英文 | 模板抽取 `AS`, `C0`，开放词汇 mask | 条件性弱监督/SFT |
| 17 | [MASIVE](https://aclanthology.org/2024.emnlp-main.1139/) | Reddit / 英西文 | 模板抽取 `AS`, `C0`，开放 affective state | cloze/生成式弱监督 |
| 18 | [CARE](https://aclanthology.org/2022.conll-1.5/) | Reddit / 英文 | `RR`，评论反应生成弱标签 | 社区反应分支，不是作者情绪 |
| 19 | [HEC](https://aclanthology.org/2020.emnlp-main.106/) | Weibo 话题评论 / 中文 | `RR`, `C1`，emoji 反应分布 | 舆情/社区反应独立任务 |
| 20 | [IAC 2.0](https://nlds.engineering.ucsc.edu/iac2/) | 论辩论坛 / 英文 | `STA`, `C2`，无 emotion gold | 反讽/立场 challenge source |
| 21 | [ALOE](https://aclanthology.org/2024.naacl-long.172/) | Reddit 回复对 / 英文 | `EMP`, `C2`，appraisal/target-observer alignment | 上下文与解释辅助 |
| 22 | [EPITOME](https://github.com/behavioral-data/Empathy-Mental-Health) | 心理支持回复对 / 英文 | `EMP`, `C2`，同理心及 rationale | 解释 SFT 辅助 |
| 23 | [BeCOPE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0316906) | 心理健康 Reddit / 英文 | 人工 + 伪标签混合，根帖与评论 | 当前排除完整主路线 |
| 24 | [DepressionEmo](https://github.com/abuBakarSiddiqurRahman/DepressionEmo) | 心理健康 Reddit / 英文 | 模型伪标签，情绪/症状/风险混合 | 伪标签压力测试，不训练 |
| 25 | [Ubuntu-fr OSE Corpus](https://aclanthology.org/L16-1280/) | Ubuntu 论坛 / 法文 | opinion/sentiment/emotion 混合，`C2` | 构念错位，排除主任务 |

### 3.2 非论坛上下文迁移候选

| # | 数据集家族 | 数据域/上下文 | 允许的角色 |
| ---: | --- | --- | --- |
| 26 | [EmotionLines / EmotionPush](https://sites.google.com/view/emotionx2019/datasets) | Friends 剧本 + 私聊，`C2` | 对话 SFT；优先真实聊天的 EmotionPush |
| 27 | [DailyDialog](https://aclanthology.org/I17-1099/) / [MELD](https://github.com/declare-lab/MELD) | 人工日常对话 / 影视对话，`C2` | 上下文模型 sanity check |
| 28 | [IEMOCAP](https://sail.usc.edu/iemocap/iemocap_release.htm) / EmoryNLP | 表演对话 / Friends 剧本，`C2` | 多模态或跨域挑战，不证明 forum 泛化 |
| 29 | [CPED](https://github.com/scutcyr/CPED) / [M3ED](https://github.com/AIM3-RUC/RUCM3ED) / [MPDD](https://aclanthology.org/2020.lrec-1.76/) | 中文对话，`C2`；MPDD 含目标听者 | 中文上下文迁移；MPDD 最接近显式回复对象 |
| 30 | [EmoContext](https://aclanthology.org/S19-2005/) / [EmoWOZ](https://huggingface.co/datasets/hhu-dsml/emowoz) | 三轮短对话 / 任务型对话，`C2` | 固定上下文消融和 Agent 场景辅助 |

中文或非英文数据没有因为语言被扣分；扣分只来自论坛属性、构念、上下文、许可和复现性。语言可通过跨语言模型或单语模型解决，不是硬性排除项。

## 4. 重点候选文档审计

### 4.1 RESEMO

- **平台与任务**：3,813 个 Weibo 根帖、68,781 条评论；论文标注 16 类 responsive emotion、语义响应关系和词级原因，属于 `AE + C2`。
- **标注**：10 名高频 Weibo 用户参与，两人一组；论文报告 emotion Cohen's kappa 约 `0.51`。这是第三方感知的表达情绪，不是作者自报。
- **文本/字段**：官方仓库当前要求邮件联系，未公开可审计数据包和 schema。
- **许可**：仓库没有明确数据许可证；在书面许可前不能训练或承诺发布派生数据/权重。
- **判断**：科学匹配度最高，是唯一同时接近“论坛、响应对象、情绪、原因”的候选；当前被硬门阻塞。
- **角色**：`A-main-gold (conditional)`。

### 4.2 CancerEmo

- **平台与任务**：Cancer Survivors Network 在线健康社区；25,000 句，Plutchik 八类逐类二元人工标注，允许一条文本具有多种情绪；约 8,500 句至少含一种情绪。
- **标注**：3 名 AMT 标注者/句，多数票；论文报告平均 Krippendorff's alpha 约 `0.69`。
- **文本/字段**：作者仓库当前仍给出数据下载链接；发布格式为 8 套二分类数据，只有 sentence/emotion/split 一类字段，没有 post/thread/parent ID，属于 `C0`。
- **划分风险**：把八个任务直接合并成多标签矩阵会造成同句跨 split 风险，必须先按规范化文本分组，重新冻结统一 split。
- **许可**：仓库代码是 MIT，但这不能自动证明外部 Drive 中的论坛文本同样为 MIT；正式训练前要得到数据许可解释。
- **角色**：`D-real-forum-target-only challenge`；许可和 split 修复后可竞争 C0 主评估。

### 4.3 Stack Overflow Emotion Gold Standard

- **平台与任务**：4,800 条 questions/answers/comments；love、joy、surprise、anger、sadness、fear，缺省为 neutral；支持多标签。
- **标注**：12 名 CS 研究生，每条 3 人、多数票；各类 Fleiss kappa 约 `0.30-0.66`。
- **当前文件**：XLSX 有 6 个 sheet，每个 `4,800 x 10`；列为 `Group`、`Set`、本地序号、`Text`、三位 rater、`Gold Label` 和两个空列。
- **ID 与 context**：本地序号在组/轮次中重复，不是原始 Stack Overflow ID；文件没有 question/answer/comment ID、URL、thread 或 parent。因此不能仅因 Stack Exchange 有 data dump 就宣称可恢复上下文。
- **标签统计**：当前 release 中 love `1,220`、joy `491`、surprise `45`、anger `882`、sadness `230`、fear `106`；`133` 条双标签。逐 sheet 合并得到 `2,841` 条至少一个情绪、`1,959` 条无情绪，但论文正文写成相反的 `1,959 emotion / 2,841 neutral`。这与各类计数和 133 条双标签不一致，正式使用应以当前 release 逐行重建结果为准并记录文档冲突。
- **重复与 split**：`212` 行涉及 exact duplicate text，形成 `113` 条额外重复；没有官方 train/dev/test。必须先 deduplicate/group split。
- **许可**：仓库只有引用/使用说明，没有正式 LICENSE。Stack Overflow 平台内容的 CC BY-SA 版本依日期变化；平台许可、标注文件分发和模型训练边界必须分别确认。
- **角色**：`D-real-forum-target-only challenge`；不是 `B-context subset`。

### 4.4 GoEmotions

- **平台与任务**：58,009 条 Reddit 评论；27 类 emotion + neutral，多标签，`AE`。
- **标注**：82 名标注者，通常 3 人/条，分歧样本增加到 5 人；标注时没有给 parent context。
- **本地闭集审计**：官方 raw release 中 48,836 个已冻结 train/dev targets 全部能匹配 metadata 且都有 `parent_id`，但只有 `157` 个 parent 文本也存在于 raw release，覆盖率 `0.321%`；缺失率 `99.679%`。
- **解释**：即使未来恢复 parent，也是在定义一个新的 context-aware 任务；不能写成原始 gold 本来就由上下文标注。
- **权利边界**：项目已完成 GoEmotions 复现并消费 test；不得再以该 test 调参。新增 Reddit 获取或 hydration 仍需当前平台明确授权。
- **角色**：`completed C0 control`；闭集 parent 路线已经关闭。

### 4.5 CovidET

- **平台与任务**：1,883 个英文 Reddit 支持社区长根帖；7 类 perceived emotion，并为每个存在的情绪提供作者视角的 abstractive trigger summary。
- **标注**：两人/条，论文报告整体百分比一致率约 `0.804`。
- **上下文**：公开任务是根帖内部的长文本上下文，不是 parent-target reply，属于 `C0`。
- **LLM 价值**：输出可以设计为固定标签 + 可核验 trigger span/summary，比自由 CoT 更接近 LLM 的生成优势，也能分别评估分类与依据质量。
- **风险**：规模小、主题单一；仓库未见明确数据 LICENSE，原始 Reddit 权利也需单独核对。
- **角色**：`D-LLM challenge / E-explanation auxiliary`。

### 4.6 CHQ-SocioEmo

- **平台与任务**：1,500 组 Yahoo Answers 消费健康 question-answer pair；情绪标签包括 sadness、fear、confusion、denial、anger、joy、disgust、trust、surprise、anticipation、neutral，并有 evidence、cause、社会支持需求和 answer support。
- **标注**：10 名受训标注者；129 条由另外 3 人复标。各情绪 overall agreement 约 `60.5%-95.3%`，说明不同标签难度差异较大。
- **因果/时间边界**：answer 是 question 发表后的内容。若预测 question 中的情绪，answer 不能作为发表时 context，只能作为响应/支持分析对象。
- **实际文本**：公开记录提供 question ID 与标注；论文明确说明 Yahoo 原始问题因版权不能直接分享，需另签 Yahoo 协议取得文本。
- **角色**：`E-evidence/cause auxiliary (blocked on source text)`，不是当前可执行主任务。

### 4.7 EXPRESS

- **任务**：从自我披露模板自动抽取 affective state 并在 segment 中遮蔽，要求生成开放词汇标签；这属于模板派生 `AS` 弱监督，不是人工判断的 emotion gold。
- **当前文件**：Hub 当前只有一个 train 文件。实际 CSV 为 `33,640 x 10`，字段包括 `original_ids`、`segment`、`number_of_labels`、`labels`、`original_labels`、`word_count`、`topic_id/name`。
- **版本漂移**：数据卡/论文写约 33,679 或 33,697 条、251 labels；当前 CSV 实际 33,640 行，按规范化 `labels` 解析出 **404** 个不同标签。正式使用前必须冻结文件 hash 和解释 taxonomy drift。
- **长尾**：52,547 个标签实例；404 个标签中 99 个少于 5 条、157 个少于 10 条、221 个少于 20 条、322 个少于 100 条；top-10 仅覆盖 `35.86%`。
- **重复/划分**：只有 27,370 个唯一 `original_ids`；10,018 行来自重复 original ID，单一 ID 最多 12 段；407 行涉及 exact duplicate segment。必须按 `original_ids` 分组划分，不能随机按行切。
- **质量/泄漏**：16 行的 `number_of_labels` 与解析标签数不一致。模板本身泄露“这里在说感受”，且部分 segment 仍可能包含同标签或近义词；需完成 exact/morphological/synonym cue 分层后才可训练。
- **许可**：数据卡标记 Apache-2.0，但这不自动替代 Reddit 平台对训练、删除和再分发的约束。
- **角色**：`C-open-vocabulary weak supervision`，不能作最终 gold。

### 4.8 MASIVE

- **任务与规模**：英文 train `93,736`、test `10,049`、challenge `4,720`；另有西班牙文。任务同样由自我披露模板抽取并遮蔽 affective state，属于开放词汇生成。
- **标签可信度**：论文对英文样本的人工检查中，约 `88.4%` 的词被判断为 affective state，但只有约 `34.2%` 被判断为 emotion，其余包含 mood、态度或其他状态。
- **上下文**：未发现 thread/parent 字段，属于 `C0`。
- **许可**：官方仓库有下载脚本，但当前根目录未见明确数据 LICENSE；代码/采集工具许可不能替代文本训练权限。
- **角色**：`C-cloze/open-state weak supervision` 和 LLM 任务设计参考，不是主 emotion gold。

### 4.9 KOTE

- **平台与任务**：50,000 条韩语在线评论，43 类情绪 + `NO EMOTION`，5 人标注；发布 train/validation/test 为 `40k/5k/5k`。
- **本地 L3 审计**：train/validation 无 ID 或 exact-text overlap；train 平均标签数 `7.911`，39,639/40,000 条超过一个正标签，符合上游聚合方法，不是 parser 错误。
- **本体风险**：`NO EMOTION` 与其他标签在 train 共现 6,261 次、validation 共现 763 次，采用前必须冻结是否排他、保留或删除。
- **上下文**：没有 thread/parent/author/platform 字段，属于 `C0`。
- **角色**：`C/E cross-lingual C0 training/control`，不能回答 context 研究问题。

### 4.10 ALOE

- **平台与任务**：真实 Reddit poster-replier pair；包含 distress、condolence、empathy、appraisal span 和 target-observer alignment，具有一层 `C2` 关系。
- **标注**：训练标注者 + 仲裁，数据为 gated，卡片标注 CC BY-NC-SA 4.0。
- **构念边界**：gold 是 appraisal/empathy/observer alignment，不是目标作者的固定离散 emotion labels。
- **角色**：`E-context/appraisal auxiliary`。可训练依据抽取或表征对齐，但不能把 appraisal 分数重命名成 emotion accuracy。

## 5. 文件级与闭集审计摘要

| 候选 | 审计范围 | 关键发现 | 决策 |
| --- | --- | --- | --- |
| GoEmotions | 官方 raw 闭集 train/dev metadata | 48,836 targets 只有 157 个 parent 文本，覆盖 `0.321%` | 关闭闭集 C2 路线 |
| KOTE | train 40k + validation 5k | 无 ID/文本交叉；平均 7.911 标签；`NO EMOTION` 大量共现 | 合格 C0 control |
| Hotter and Colder | CLARIN 未 hydration 包 | 无文本；URL/time 恢复；8 个二元任务没有完整八标签矩阵；计数漂移 | 已排除本论文 |
| Weibo Emotion Cause | 固定仓库两个 TSV | 两文件是不同任务视图；标签混合情绪/极性/结构标记 | 仅 C1 cause auxiliary |
| Stack Overflow Gold | 6-sheet XLSX | 无原生 ID/context；标签与论文 neutral 计数冲突；113 个额外 exact duplicates | 条件性 C0 challenge |
| EXPRESS | 当前 Hub CSV | 33,640 行、404 解析标签；严重长尾、原帖分段重复、单一 split | 条件性弱监督 |

本轮临时文件仅用于统计，没有提交原始文本或 ID。校验值：

- Stack Overflow XLSX SHA-256: `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`
- EXPRESS CSV SHA-256: `81e8e997fb783f772a8fc3de10091a21acb43883bcf550a8506df464a72984b7`

## 6. 统一评分与角色

评分中的 `BLOCK` 表示硬门覆盖总分；`UNK` 表示当前官方材料不足，不应被误读为“允许”。

| 排名 | 候选 | 分数 | Context | 硬门/主要缺陷 | 最终角色 |
| ---: | --- | ---: | --- | --- | --- |
| 1 | RESEMO | 78 | C2 | `BLOCK`: 数据与训练/发布许可未取得 | conditional main gold |
| 2 | CancerEmo | 76 | C0 | 数据许可未覆盖清楚；八任务 split 要重建 | real-forum C0 challenge |
| 3 | Stack Overflow Gold | 73 | C0 | 无原始 ID、无官方 split、无正式数据 LICENSE | real-forum C0 challenge |
| 4 | KOTE | 72 | C0 | 非稳定单一论坛来源；无 context；本体需映射 | cross-lingual C0 control |
| 5 | GoEmotions | 71 | C0 | Reddit 新获取受限；闭集 parent 覆盖仅 0.321% | completed C0 control |
| 6 | BRIGHTER | 70 | C0 | 非论坛线程、无 context | multilingual C0 control |
| 7 | CovidET | 66 | C0 | 小且主题单一；许可边界未清 | LLM explanation challenge |
| 8 | ALOE | 65 | C2 | `BLOCK as main`: 标签是 appraisal/empathy，不是 emotion | context auxiliary |
| 9 | Chinese Event-comment | 64 | C1 | `BLOCK`: 当前数据和许可未找到 | conditional C1 candidate |
| 10 | CHQ-SocioEmo | 63 | Q/A pair | `BLOCK`: 原文须 Yahoo 协议；answer 是未来信息 | evidence/cause auxiliary |
| 11 | EXPRESS | 59 | C0 | 弱标签、taxonomy drift、长尾、单 split、平台权利 | weak supervision |
| 12 | JIRA Emotion | 58 | 潜在 C2 | 归档/许可/ID join 未核实，子集协议不统一 | conditional challenge |
| 13 | MASIVE | 55 | C0 | 仅约 34.2% 英文状态被判为 emotion；许可不明 | weak supervision |
| 14 | Weibo Emotion Cause | 55 | C1 | 标签/任务视图混合，不是现成主 gold | cause auxiliary |
| 15 | Vent | 54 | C0 | `BLOCK`: 正文申请制；许可和平台边界未过 | conditional self-report auxiliary |
| 16 | IAC 2.0 | 45 | C2 | `BLOCK as main`: 无 emotion gold | challenge/raw annotation source |
| 17 | CARE | 43 | 反应来源 | `BLOCK as main`: reader reaction + hydration/leakage | separate RR task |
| 18 | DepressionEmo | 37 | C0 | 伪标签、构念混合、All Rights Reserved | reject for training |
| 19 | Hotter and Colder | 36 | 理论 C2 | `BLOCK`: 无文本、hydration/隐私/schema 风险 | excluded |
| 20 | BeCOPE | 34 | root/comments | 完整 gold、release、许可和 split 不可验证 | reject pending complete release |

没有候选达到 80 分。RESEMO 虽最接近，但仍不能绕过访问与许可硬门；KOTE/GoEmotions/BRIGHTER 分数较高并不表示它们是更好的“论坛上下文”数据，只表示其 C0 标签与复现性较强。

## 7. 淘汰与降级清单

| 数据集/家族 | 淘汰或降级原因 |
| --- | --- |
| Hotter and Colder | 当前包没有文本；依赖实时 URL hydration；字段与任务矩阵不完整；隐私和复现风险 |
| IAC 2.0 | 有 thread，但 gold 是 stance/agreement/sarcasm 等；本地 pilot 已显示 stance-emotion 错位 |
| CARE / HEC | 预测读者或社区反应，不是目标作者表达情绪；把生成标签的评论作 context 会泄漏 |
| ALOE / EPITOME | appraisal、distress、empathy、support rationale，不是离散 emotion gold |
| MedSenti / Nota Bene | 标签把情绪与交流功能、认知状态、意图混合；数据当前不可直接取得 |
| DepressionEmo | 主要由模型投票伪标；类别混合情绪、症状和风险；未获训练许可 |
| BeCOPE | 完整人工/伪标签边界、评论树、release 和许可无法核验；敏感心理健康文本风险高 |
| Ubuntu-fr OSE | emotion 只是 Opinion/Sentiment/Emotion 混合方案的一部分，构念与 IAA 不足 |
| MELD / IEMOCAP / DailyDialog 等 | 非异步论坛；只能训练 context 方法，不能支撑论文中的 forum 结论 |
| 仅 sentiment / stance / toxicity / engagement 的论坛集 | 标签目标不同，即使规模或 context 很好也不能替代 emotion gold |

## 8. 对论文设计的直接启发

### 8.1 不再寻找“一套数据完成所有实验”

合理证据链应拆成：

```text
真实论坛 C0 人工 gold
-> 主要分类与 LLM/encoder 公平比较

独立的 C2 或 context pair 数据
-> target-only / true-parent / shuffled-parent 配对消融

开放词汇或 trigger 数据
-> LLM 生成式优势、解释依据与中间训练

对话数据
-> 仅检验迁移，不承担 forum 结论
```

### 8.2 把任务改成 LLM 擅长的形式，但不放弃可验证性

CovidET 比自由 Chain-of-Thought 更适合当前论文：系统输出可以是：

```json
{
  "emotion": ["anger", "sadness"],
  "evidence_spans": ["..."],
  "trigger_summary": "...",
  "abstain": false
}
```

正式评估分别计算标签 F1、evidence span overlap/faithfulness、trigger summary 质量与无效输出率。模型生成的解释仍是行为输出，不自动等于忠实推理或内部机制。

### 8.3 Context 实验必须是同一样本配对消融

必须比较：

```text
target only
vs true parent + target
vs shuffled parent + target
```

不能拿一个 C0 数据集的 BERT 分数与另一个 C2 数据集的 LLM 分数比较后声称 context 有效。gold 如果在 target-only 条件下标注，也必须在论文中说明加入 parent 定义了新的模型输入条件，而不是更“真实”的原标签。

## 9. 推荐决策路径

### 路径 1：保留真正的上下文主问题（推荐但需外部联系）

1. 向 RESEMO 作者询问数据包、字段、研究训练、派生统计/预测/模型权重和论文图表的许可。
2. 取得后先做 100 条 schema/reply 验证和标签/线程泄漏审计，不立即训练。
3. 若通过，RESEMO 才升级为 `A-main`，并冻结 target-only / true-context / shuffled-context 协议。

当前用户此前要求“先不联系”，因此本报告没有发送任何邮件或申请。

### 路径 2：不等待授权，完成一个稳健的 forum C0 毕设

1. 在 CancerEmo 与 Stack Overflow Gold 中选择一个作真实论坛 target-only challenge；采用前先完成许可确认和无泄漏 split。
2. 保留现有 Weibo EClass/GoEmotions 结果作为已完成证据，不重复消费 test。
3. 将 context 从主数据硬要求降为 ALOE/MPDD/EmotionPush 上的迁移或方法消融，并明确 domain mismatch。
4. 用 CovidET 做“标签 + 依据/trigger 摘要”的 LLM 扩展，比直接追加自由 CoT 更可评估。

### 路径 3：开放词汇 LLM 路线（探索性）

1. EXPRESS/MASIVE 只作中间训练或诊断；先冻结 `original_id` group split、taxonomy 版本和 leakage audit。
2. 最终评价仍回到人工 gold，不用自动 self-disclosure 标签证明模型理解情绪。
3. 该路线要先解决 Reddit 训练授权，不能只依赖 Hugging Face 数据卡许可证。

## 10. 下一步门槛

本轮之后的下一步是**数据采用决策**，不是下载后直接训练。需要用户先决定：

- 是否允许联系 RESEMO/相关作者处理访问与许可；或
- 是否接受“真实论坛 C0 主评估 + 独立 context 辅助 + LLM trigger 输出”的组合路线。

任何新候选进入训练前都必须单独完成：

1. 固定 URL、版本/commit、文件 SHA-256 和来源日期；
2. 分开记录数据集许可证、原平台条款、训练/再发布/权重权限；
3. 核对实际字段、文本、标签、ID、split 和缺失值；
4. 按 thread/original post 分组去重与划分；
5. 冻结 label ontology、主指标、context 输入和 test gate；
6. 对敏感健康/心理文本完成伦理、脱敏、删除与私有存储方案。

## 11. 来源锚点

### 主候选与方法

- RESEMO: <https://aclanthology.org/2024.findings-acl.970/>；官方仓库 <https://github.com/Alack1/RESEMO>
- Stack Overflow Emotion Gold: <https://arxiv.org/abs/1803.02300>；官方仓库 <https://github.com/collab-uniba/EmotionDatasetMSR18>
- CancerEmo: <https://aclanthology.org/2020.emnlp-main.715/>；官方仓库 <https://github.com/tsosea2/CancerEmo>
- CovidET: <https://aclanthology.org/2022.emnlp-main.642/>；官方仓库 <https://github.com/honglizhan/CovidET>
- CHQ-SocioEmo: <https://www.nature.com/articles/s41597-023-02203-1>；数据 DOI <https://doi.org/10.17605/OSF.IO/3DX2S>
- GoEmotions: <https://aclanthology.org/2020.acl-main.372/>；官方仓库 <https://github.com/google-research/google-research/tree/master/goemotions>
- KOTE: <https://aclanthology.org/2024.lrec-main.1499/>；官方仓库 <https://github.com/searle-j/KOTE>
- EXPRESS: <https://huggingface.co/datasets/bangzhao/express-emotion-recognition>；论文 <https://ojs.aaai.org/index.php/ICWSM/article/view/42743>
- MASIVE: <https://aclanthology.org/2024.emnlp-main.1139/>；官方仓库 <https://github.com/NickDeas/MASIVE>
- ALOE: <https://aclanthology.org/2024.naacl-long.172/>；数据页 <https://huggingface.co/datasets/Blablablab/ALOE>

### 平台与合规

- Reddit 数据访问：<https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data>
- Reddit for Researchers：<https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program>
- Reddit Responsible Builder Policy：<https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy>
- Stack Overflow 内容许可：<https://stackoverflow.com/help/licensing>

### 本地证据

- 既有来源地图：[llm-forum-text-emotion-recognition-sources.md](llm-forum-text-emotion-recognition-sources.md)
- 已完成公开候选文件审计：[KOTE / Hotter / Weibo audit](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md)
- GoEmotions closed-corpus parent 协议：[DATA-FCTX-CJ-V1](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-closed-corpus-parent-coverage-v1.md)
- 项目路线与冻结边界：[research-roadmap.md](../projects/llm-forum-text-emotion-recognition/research-roadmap.md)

## 12. 证据边界

- 数据规模、标注流程和论文指标属于**文献结论**；文件行数、字段、hash、重复、长尾和闭集覆盖率属于**本地审计结果**。
- “RESEMO 科学匹配度最高”“CancerEmo/Stack Overflow 可作 C0 challenge”“CovidET 更适合 LLM 可验证输出”属于**助手综合判断**，不是领域共识。
- 数据许可与平台条款部分是研究可行性审查，不构成法律意见；`UNK` 不等于允许。
- 本报告没有保存论坛原文、可反查 URL 或用户 ID；没有下载 test、运行 hydration、训练模型或修改既有实验结论。
- 本报告不把任何计划中的数据、模型、context 结果或解释性分析写成已完成成果。
