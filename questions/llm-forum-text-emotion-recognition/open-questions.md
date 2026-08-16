# Open Questions: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
status: active
tags: [emotion-recognition, forum-text, llm, open-questions]
project: llm-forum-text-emotion-recognition
sources:
  - ../../sources/llm-forum-text-emotion-recognition-sources.md
---

## Primary Question

在固定 Stack Overflow 六标签多标签任务上，Encoder、Frozen Qwen linear probe、
Qwen Classification LoRA 与 Qwen Generative LoRA 在情绪识别性能、稳定性和成本上有何
差异；若上下文可可靠恢复，真实论坛上下文是否提供可验证的额外收益？

Status: mainline-test-completed; EXP-056-verified; held-out-test-consumed; conditional-context-and-router-branches-open

## Q1. 目标论坛、语言和数据授权边界是什么？

Why it matters: 数据领域和语言决定可用预训练模型、标签设计、代码复现价值与跨域风险；平台条款和隐私边界决定数据能否采集、保存和公开。

Current view: 主任务已冻结为 Stack Overflow Emotion Gold Standard 的英文 C0 多标签
任务，不再继续搜索主数据集。作者仓库提供研究使用与引用说明，但没有标准化数据
`LICENSE`；Stack Overflow/SOTorrent 原始文本另受相应 CC BY-SA 条款约束。现阶段仅承诺
私有研究训练、聚合结果和不含原文的可复现产物，不重新打包发布完整文本或预先承诺公开
衍生权重。

Status: resolved-for-private-research; redistribution-boundary-remains

Next action:

- 公开交付前重新审查将要发布的文本、split ID、模型权重和派生产物；在此之前保持保守
  发布策略。

## Q2. 主任务采用粗粒度单标签还是细粒度多标签？

Why it matters: 标签体系决定标注难度、损失函数、指标和论文主线。细粒度标签更丰富，但不一定更可靠。

Current view: 主任务冻结为 `love`、`joy`、`surprise`、`anger`、`sadness`、`fear` 六个
独立二元标签；六标签全为 0 时派生 `neutral=true`。使用 `BCEWithLogitsLoss`，不改成七类
softmax，也不在本阶段扩展 ontology。

Status: frozen-and-data-verified

Next action:

- `DATA-SO-TASK-V1` 已从固定 XLSX 精确重建六维标签矩阵；train/validation/test 为
  `3,360/720/720`，`surprise` 正例为 `31/7/7`。
- 在 M1-M4 协议中落实低支持保护：`surprise` 保留于主 Macro-F1，禁止单独调阈值，并报告
  三 seed、component-bootstrap 区间和五标签敏感性分析。

## Q3. 单条文本分类是否足够，还是必须保留回复树？

Why it matters: 没有 `thread_id`、`parent_id`、回复顺序和匿名作者标识，就无法严格研究论坛上下文，也不能把结果写成 ERC。

Current view: Stack Overflow C0 target-only 是不依赖上下文的必做主任务。历史 dump/SOTorrent
文本回连是并行数据实验；只有唯一 ID 恢复率、歧义率和有效 answer/comment 配对数通过冻结
门槛，才启动 true context、matched shuffled context 和 target-only 三视图实验。未通过不
更换主数据集，也不阻塞 M1-M4。

Status: mainline-resolved; context-conditional

Next action:

- 登记 `DATA-SO-CONTEXT-RECOVERY-V1` 并在冻结历史数据上报告恢复率、歧义率和失败原因。
- 只有恢复门通过后才冻结 answer 与 comment 各自的上下文视图；不得把 host-post context
  写成 comment-to-comment parent。

## Q4. LLM 相对编码器基线的研究价值是什么？

Why it matters: 题目包含 LLM，但这不意味着 LLM 必然性能更好。需要预先定义比较维度，避免项目退化为 API 演示。

Current view: 下一阶段固定四个同数据条件：M1 Encoder、M2 Frozen Qwen + fixed linear
head、M3 Qwen Classification LoRA、M4 Qwen Generative LoRA。M2/M3 固定 final-layer
最后一个非 padding 输入 token pooling 和同一线性 head；M2-M4 共享 Qwen checkpoint、
tokenizer、输入、split、seed 与评估边界。M3-M2 只支持 classification interface 下的 LoRA
增量收益；M3-M4 只作端到端任务表述比较，不能归因为纯生成接口或内部机制。

Status: EXP-056-test-verified; representation-claim-open

Next action:

- EXP-051 至 EXP-054 Major protocols 与 EXP-050 共享 train-only preflight 已冻结并通过；
  77/77 项独立检查确认 M2/M3 matched initialization 与 M3/M4 matched LoRA initialization。
- EXP-051 M1、EXP-052 M2 与 EXP-053 M3 三 seed validation family 均已完成。M3 共享阈值
  Macro-F1=`0.654032 +/- 0.014135`，相对 matched M2 为
  `+0.335143 +/- 0.041168`；只读 aggregate 独立检查通过 `124/124`。
- M3 相对 M1 的共享 Macro-F1 为 `+0.036778 +/- 0.003154`，但排除仅 7 个正例的
  `surprise` 后为 `-0.033981 +/- 0.008620`，Micro-F1 与 Weighted-F1 也较低。因此
  不能把六标签 Macro-F1 点估计写成全面优势。
- EXP-055 已完成全量 validation 错误互补分析。M1-only/M3-only exact-correct 每 seed
  分别为 `42/53/73` 和 `53/50/43`；不可部署 whole-vector oracle 的六标签 Macro-F1
  headroom 为 `+0.136394 +/- 0.009058`，五项 router gate 均通过。45 条目的性人工复核只
  支持 selected-case 解释，不代表总体错误比例。
- EXP-054 M4 三 seed validation 已验证；相对 M3 的 Macro-F1 为
  `-0.038850 +/- 0.030200`，3/3 seed 为负。该比较只支持端到端任务表述差异，不能归因
  为纯生成接口或内部机制。
- EXP-056 已按冻结合同完成一次性 test。M1/M2/M3/M4 Macro-F1 分别为
  `0.567459/0.295226/0.613804/0.547823`；M3-M2 的 95% CI 全为正，但 M3-M1 的六标签与
  五标签 CI 均跨 0，M4-M3 的主指标 CI 全为负。Test 已消费，禁止据此继续调参或选择模型。
- Router 只获得另行登记 train-OOF feasibility 的资格；内部情绪表征仍是待验证问题，
  不能由分类分数直接推出。

## Q5. 上下文收益是否只发生在特定失败类型？

Why it matters: 总体分数可能掩盖反讽、指代、否定和情绪转移样本上的真实收益。

Current view: 不再人工定义“context-sensitive subset”，避免根据哪个模型答对产生循环。
恢复门通过后，在完整可验证 answer subset 及预先定义的类型/长度/标签分层上做三视图配对
评价。Whole-vector oracle 每条样本只能选择一个完整六维预测向量，按冻结 Hamming loss
选择后重新计算 Macro-F1；逐标签拼接不能作为可部署 headroom。

Status: oracle-headroom-passed; train-OOF-feasibility-protocol-pending

Next action:

- 只有恢复门通过后比较 target-only、true context 和 matched shuffled context。
- 只有 whole-vector oracle 有足够预登记收益才训练 gate；learned gate 必须使用 train OOF
  predictions，dev 选择，test 一次性评价。

## Q6. Encoder-Qwen 路由是否有实际系统价值？

Why it matters: 即使两个模型总体分数接近，也只有错误互补且可在调用 Qwen 前识别困难样本，
选择性路由才可能降低平均成本并保持或提高性能。

Current view: Router 不是必做主实验。先比较 M1/M3 的错误重叠、whole-vector oracle、
risk/coverage 和 Qwen 在 encoder deferred subset 上的条件收益。可部署 router 只能使用
encoder 概率、熵、margin、文本长度等 pre-Qwen features；不得先运行 Qwen 再决定是否调用。

Status: conditional

Next action:

- EXP-055 已通过冻结的 oracle headroom 门；下一步若启动该条件支线，必须先单独登记
  train-OOF router protocol，不能直接在 validation 上拟合。
- learned router 只能使用 encoder 概率、熵、margin、文本长度等 pre-Qwen features；若合理
  Qwen 调用率下无正收益，关闭分支并部署单一最佳模型。

## Q7. 哪些证据足以支持最终申请表述？

Why it matters: 计划、演示和单次最好结果不能自动成为 CV 或 SOP 事实。

Current view: 只有 [`../../projects/llm-forum-text-emotion-recognition/evidence-log.md`](../../projects/llm-forum-text-emotion-recognition/evidence-log.md) 中状态为 `Verified` 的条目可以支持完成性和量化表述。

Status: process-defined

Next action:

- 从第一次复现实验开始同步记录 commit、配置、日志、预测和复核方式。
- 每个阶段结束时审计一次项目表述与证据编号。
