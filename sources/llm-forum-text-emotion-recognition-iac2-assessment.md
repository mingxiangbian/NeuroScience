# IAC 2.0 数据源评估

---
date: 2026-08-05
status: conditional-candidate
tags: [emotion-recognition, forum-context, dataset-audit, iac2]
project: llm-forum-text-emotion-recognition
---

## 结论

IAC 2.0 **不是可以直接替换 GoEmotions 或 EmotionLines 的情绪分类数据集**。它没有
anger、joy、sadness 等目标情绪标签，已有标注主要描述论辩关系、攻击性、礼貌、讽刺
和“情感诉求 vs. 事实论证”。

但它是目前审计过的候选中很强的 **英文论坛上下文来源**，尤其是 4forums：

- 414,453 帖、11,079 个讨论；
- 403,374 帖有可在同一讨论内解析的直接 parent，占 97.33%；
- 389,648 个 parent-target 对同时通过最低文本门槛；
- 另有 310,529 个可解析的唯一 quote-response 对；
- 9,954 个 quote-response 对同时具有可关联的平均人工标注。

因此当前总决定是：

| 用法 | 决定 | 原因 |
| --- | --- | --- |
| 作为论坛线程结构和上下文消融的候选来源 | **CONDITIONAL GO** | 4forums 的 parent 和 quote 关系充足 |
| 不新增标注，直接训练多类别 emotion classifier | **NO-GO** | 没有本课题所需的情绪标签 |
| 作为 IAC 原任务的攻击性、讽刺、论辩风格辅助数据 | **POSSIBLE** | 有相关人工标注，但任务定义不同 |
| 本地非商业毕设标注、训练和评估 | **CONDITIONAL GO** | UCSC 当前总页明确列为供其他研究者免费研究使用；模型训练属于该用途的合理解释，但没有单独 ML 条款 |
| 公开原始文本、用户信息或可逆 ID | **NO-GO** | 含用户名、URL 和部分敏感人口属性 |
| 公开清洗数据、逐样本衍生标签或 checkpoint | **NOT AUTHORIZED** | 没有语料专属正式许可证，也没有再分发、衍生数据或模型权重条款 |

这是一项 **数据源审计结论**，不是法律意见，也没有把 IAC 2.0 冻结为毕设主数据集。

## 审计范围

来源：

- [UCSC IAC 2.0 官方页](https://nlds.engineering.ucsc.edu/iac2/)
- [官方 Google Drive 发布目录](https://drive.google.com/drive/folders/11UMZbpLaLOkxT53vVWUHVJkdyWL1H7Gx)
- [Abbott et al. (2016), IAC 2.0](https://aclanthology.org/L16-1704/)
- [当前保存仓库](https://github.com/sl-m-lab/Internet-Argument-Corpus)

本次读取 2016-05-18 的三个 no_parse MySQL dumps。它们省略 CoreNLP 解析表，但保留
帖子、文本、讨论、parent、quote、论辩关系和人工标注，足以评估本课题的数据可用性。
三个压缩包均通过 gzip 完整性检查；文件大小和 SHA-256 见
[iac2-source-assessment.json](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/preflight/iac2-source-assessment.json)。

审计脚本只输出聚合统计，不输出论坛原文、用户名或来源 URL：
[audit_iac2_source.py](../projects/llm-forum-text-emotion-recognition/experiments/forum-context/audit_iac2_source.py)。

## 发布物实测

“可用 parent 对”要求：

1. target 的 parent_post_id 非空；
2. parent 能在同一 discussion_id 中解析；
3. parent_missing=0；
4. target 和 parent 均至少有 20 个去空白字符、5 个 ASCII word tokens；
5. 文本不是常见删除占位符。

该门槛只排除明显不可用文本，不代表样本已有情绪标签或语义质量已经通过人工审查。

| 子库 | 时间范围 | 讨论 | 帖子 | 作者 | 可解析 parent | 可用 parent 对 | 唯一 quote-response |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CreateDebate | 2008--2015 | 63 | 3,051 | 743 | 2,058 (67.45%) | 1,999 (65.52%) | 290 |
| ConvinceMe | 2007--2012 | 5,413 | 65,368 | 5,783 | 33,148 (50.71%) | 31,519 (48.22%) | 0 |
| 4forums | 2003--2012 | 11,079 | 414,453 | 3,452 | 403,374 (97.33%) | 389,648 (94.02%) | 310,529 |

三个子库分别有 98.43%、96.59% 和 97.89% 的帖子通过最低文本门槛。所有非空
parent_post_id 都能在各自讨论中解析，说明 parent 外键本身不是估算或文本匹配结果。

4forums 和 ConvinceMe 的帖子、讨论、作者总数与论文相符。论文描述 CreateDebate
gun-control subset 为 2,958 帖，而当前官方 dump 实测为 3,051 帖，多 93 帖。原因尚未
由发布说明解释；后续实验必须报告 dump 哈希和 3,051 的实际口径，不能套用论文数字。

## 三个子库的区别

### CreateDebate

- 当前 release 只包含 gun control，主题过窄。
- 3,051 帖中有 1,703 条 disputed、226 条 supported、129 条 clarified，
  其余 993 条没有 response type。
- parent 质量尚可，但规模不足以单独支撑细粒度多标签情绪研究。
- author 表含 username、gender、age、marital status、political party、country、
  religion 和 education。模型输入不需要这些字段，应全部排除。

结论：适合做小型论辩关系 pilot，不适合作为主语料。

### ConvinceMe

- 65,368 帖，规模中等，31,519 个最小可用 parent-target 对。
- 所有帖子都被记录为 is_rebuttal=1，因此这个字段不能在库内形成正负对照。
- 只有 187/5,413 个讨论有 topic link；不能假定剩余讨论都有可用主题标签。
- 官方 metadata 也说明，不是所有帖子都有可识别 parent，且站点的“回复必须站在对方
  一侧”规则可能让 stance 与作者真实立场不一致。

结论：能提供回复上下文，但平台规则会混淆 stance、语气和真实情绪。

### 4forums

- parent 覆盖最高，直接回复树和 quote-source 关系可以分别构造两种上下文。
- 2,894/11,079 个讨论有 topic link；其中 gun control 905、evolution 856、
  abortion 550、gay marriage 305，其余主题合计 278。topic 标注不是全库覆盖。
- 有 9,982 行平均 quote-response 标注；其中 9,954 行能同时关联当前 post、quote 和
  平均标注。每行平均由 5.41 名标注者评价。
- 标注维度包括 disagree_agree、attacking_respectful、emotion_fact、
  nasty_nice 和 sarcasm。前四项是 [-5, 5] 标尺；sarcasm 是选择 Yes 的比例。

结论：在当前研究使用边界内，4forums 是三个子库中唯一值得进入正式数据设计的主候选。

## 为什么现有标注不等于情绪标签

IAC 论文中的 emotion_fact 问题是：回复者是在进行事实论证，还是诉诸感受和情绪。
它测量的是 **argument style**，不是回复者表达了 anger、fear、sadness、joy 中的哪一种。

同样：

- attacking_respectful 和 nasty_nice 是互动姿态；
- sarcasm 是修辞现象；
- disagree_agree、supported/disputed/clarified 和 rebuttal 是论辩关系。

这些信号适合作为辅助任务、抽样分层或 error-analysis 属性，但不能改名后当作离散情绪
gold labels。若用 IAC 2.0 完成本课题，仍需新增一个与论文研究问题一致的 emotion
ontology 和标注层。

## 与毕设研究问题的匹配

| 研究用途 | 匹配度 | 判断 |
| --- | --- | --- |
| 比较 target-only 与 parent+target | 高 | 4forums 有大量显式 parent，可按 thread 划分 |
| 比较 parent context 与 quoted context | 高 | 4forums 同时保留 parent 和 quote-source |
| 直接复现 GoEmotions 式多标签情绪分类 | 低 | 缺少 emotion category labels |
| 研究 sarcasm、hostility 对情绪识别的影响 | 中高 | 有人工辅助维度，可作为分层或控制变量 |
| 代表现代一般论坛 | 低 | 数据来自 2003--2015 的英文论辩网站，领域和年代偏移明显 |
| 支持中文论坛模型 | 低 | 三库 metadata 均为 eng，只能作为英语路线 |

论坛来源集中在政治、宗教和争议议题。合理预期是 disagreement、hostility 和 anger-like
表达偏多，但 IAC 没有类别情绪 gold labels，因此当前证据不足以断言具体情绪分布。正式
标注前必须先做分层抽样审计。

## 许可与隐私门

### 已确认

- [UCSC 语料总页](https://nlds.engineering.ucsc.edu/software/)明确称所列语料可供
  其他研究者免费研究使用，并在紧接的列表中列出 IAC V2 和 V1。当前 WordPress 记录
  修改于 2026-07-17；[2019 年存档](https://web.archive.org/web/20190813053135/https://nlds.soe.ucsc.edu/software)
  也保留相同表述。
- [IAC 2.0 官方页](https://nlds.engineering.ucsc.edu/iac2/)直接提供数据下载，并要求研究
  使用者引用 2012 和 2016 论文。[2018 年旧版下载表单](https://web.archive.org/web/20181123020021/https://nlds.soe.ucsc.edu/iac2)
  只收集姓名、邮箱和机构，没有可见的用户协议、许可勾选框或 `I agree` 条款。
- dump 内 metadata 的 license 字段在三个子库中均为 NULL。
- Drive README 只有 MySQL 备份/恢复说明，没有数据许可条款。
- 当前保存仓库没有给出 IAC 2.0 dataset license。仓库历史中曾有一份
  [MIT LICENSE](https://github.com/sl-m-lab/Internet-Argument-Corpus/blob/cdfd0f8af7d6e1ddd8ec5a21caeaaaa255b1c7ec/v2/bitbucket%20repo/LICENSE.txt)，
  但它只位于 Python 包目录，正文明确授权的是 `Software`；同目录
  [setup.py](https://github.com/sl-m-lab/Internet-Argument-Corpus/blob/cdfd0f8af7d6e1ddd8ec5a21caeaaaa255b1c7ec/v2/bitbucket%20repo/setup.py)
  也只给 `InternetArgumentCorpus` 软件包声明 MIT。SQL dumps 位于上级数据发布目录，
  根 README 没有把 MIT 扩展到语料。因此 **代码可按 MIT 使用，论坛数据不能按 MIT 处理**。
- ACL Anthology 页面对论文 PDF 的 CC BY 4.0 不会自动给论坛数据授予同一许可。

没有找到覆盖 IAC 语料的标准开放数据许可证，也没有找到商业使用、原文再分发、
衍生标签、embedding、模型训练或 checkpoint 发布的专门条款。`license=NULL` 表示发布物
没有填写许可证，不能解释成公共领域或无限制授权。

### 上游论坛权利

- CreateDebate 的 2016 年
  [User Agreement 存档](https://web.archive.org/web/20160611132830/http://www.createdebate.com/about/agreement)
  将未引用外部来源的 user content 指向 Creative Commons；同期页脚链接为
  [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)。但协议正文另称 Public Domain
  License，二者表述冲突；外部引文和人口属性也不在该许可的可靠覆盖范围内。
- ConvinceMe.net 的历史首页能确认存在 `/terms` 页面，但尚未取得条款正文，无法判断
  原文再利用和再分发范围。
- 未找到 4forums 的第一方 Terms、Privacy 或版权页面。UCSC 对 4forums 的重新抓取和
  发布是事实，但不等于公开证明了完整的上游可再许可权利链。

这些缺口不会否定 UCSC 明确给出的研究使用许可，也不足以支持把原始论坛内容重新
发布给第三方。项目因此采用“研究使用通过、公开再分发关闭”的分层判断。

### 使用权矩阵

| 行为 | 项目判断 | 条件 |
| --- | --- | --- |
| 从官方目录下载并本地保存 | **GO** | 仅限本毕设研究，记录版本、哈希和来源 |
| 本地标注、训练、验证和测试 | **CONDITIONAL GO** | 非商业学术研究；引用两篇 IAC 论文；最小化字段并匿名化 |
| 私有租赁 GPU 训练 | **CONDITIONAL GO** | 实例和存储不公开；服务商不得将输入用于训练；关闭日志，结束后删除数据卷 |
| 论文报告聚合指标、图表和误差类型 | **GO** | 不含可搜索原文、用户名、URL 或可逆 ID |
| 论文展示少量案例 | **CONDITIONAL GO** | 优先释义；确需原文时只用必要短摘录并去标识，先过导师或伦理审查 |
| 发布代码、配置、schema 和聚合统计 | **GO** | 若复用 IAC Python code 则保留 MIT notice；产物不能还原论坛文本或身份 |
| 上传原文到外部 LLM API | **NO-GO** | 当前授权与隐私条件不足 |
| 发布 SQL、清洗文本或逐样本标签 | **NOT AUTHORIZED** | 没有明确再分发或衍生数据条款 |
| 发布训练 checkpoint | **NOT AUTHORIZED** | 没有模型权重条款，也未排除记忆和原文泄露 |
| 商业使用 | **NOT AUTHORIZED** | `free research use` 不能扩展解释为商业许可 |

### 当前项目边界

在上述研究用途内：

- 允许本地或受控私有算力上的 schema 审计、人工标注、模型训练和评估；
- 训练数据、映射表和逐样本预测只能保存在 gitignored 私有目录；
- 不把原文、username、URL、人口属性或可逆映射提交到 Git；
- 不把 IAC 原文发送给外部 LLM API；
- 不公开由该数据生成的训练集；
- 不把“free research use”写成开放数据许可、商用许可或任意再分发许可；
- 公开 checkpoint 和逐样本衍生数据继续视为未通过许可门。

进入 pilot 时，抽取只保留任务必需字段，使用不可逆 surrogate IDs，并按
discussion_id 划分 train/dev/test。随机按帖子划分会让同一线程跨 split，造成明显泄漏。

## 推荐决定

保留 IAC 2.0，但把它定位为：

> **4forums-based contextual forum candidate, not an emotion-labeled benchmark.**

不要把三个子库立即混合。在上述研究使用边界内，优先以 4forums 做受控 pilot：

1. 先冻结情绪 ontology、target 定义和上下文窗口；
2. 只从 4forums 的 direct-parent pairs 分层抽样；
3. 将 quote、sarcasm、hostility 和 argument-style 标注作为辅助属性；
4. 由人工验证新增 emotion labels；
5. 按 discussion 做隔离划分，再比较 target-only 与 context-aware LLM。

许可审计已经为本地非商业毕设训练提供了有条件的使用依据，不再把正式训练整体阻塞在
许可证门上。但 IAC 2.0 仍只解决了“哪里有可靠论坛上下文”，没有解决“哪里有可直接
训练的高质量情绪标签”；下一步仍应先冻结 ontology 和人工标注 pilot，而不是直接训练
全量模型。
