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

在合规取得并可靠标注的论坛文本上，传统基线、预训练编码器和 LLM 方法在情绪识别的准确性、稳健性、成本及上下文利用方面有何差异？

Status: opening-preparation

## Q1. 目标论坛、语言和数据授权边界是什么？

Why it matters: 数据领域和语言决定可用预训练模型、标签设计、代码复现价值与跨域风险；平台条款和隐私边界决定数据能否采集、保存和公开。

Current view: 2026-08-04 的官方 GoEmotions closed-corpus audit 已完成。48,836 个
train/dev targets 中只有 157 个 parent comment 在 raw release 内有文本，48,679 个
缺失 parent text；因此不能只靠 GoEmotions 官方发布构建大规模上下文数据。直接 API、
抓取或第三方 archive 恢复仍为 `NO-GO`。Reddit 学术研究需要通过获批的 Reddit for
Researchers 项目，ML/AI training 需要明确同意；其当前五年历史覆盖也没有说明能够
访问 GoEmotions 的 2005--2019 年原始 parents。目标论坛与可替代的授权数据源仍未
最终确认。

Status: blocked-by-source-authorization-and-historical-coverage

Next action:

- 向导师确认学校能否提供 RFR 所需的 sponsor 与伦理批准或 exemption。
- 向 Reddit 书面确认历史 parent 覆盖、ML/AI training、保存、删除和发表边界。
- 若无法获批，比较具有明确上下文和训练许可的替代数据源，再由用户确认主数据路线。
- closed-corpus 路线已由
  [`DATA-FCTX-CJ-V1`](../../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-closed-corpus-parent-coverage-v1.md)
  判定为不足以支撑大规模 Dataset A；任何外部 recovery 继续受
  [`DATA-FCTX-PR-V1`](../../projects/llm-forum-text-emotion-recognition/experiments/forum-context/protocols/data-source-parent-recovery-pilot-v1.md)
  约束。

## Q2. 主任务采用粗粒度单标签还是细粒度多标签？

Why it matters: 标签体系决定标注难度、损失函数、指标和论文主线。细粒度标签更丰富，但不一定更可靠。

Current view: 首版可用 6 类基本情绪加 neutral 进行标注试验；只有一致性和样本量足够时再扩展多标签。

Status: open

Next action:

- 起草标签定义和正反例。
- 做小规模双人标注。
- 报告一致性、争议样本和 `unclear/other` 比例后再冻结方案。

## Q3. 单条文本分类是否足够，还是必须保留回复树？

Why it matters: 没有 `thread_id`、`parent_id`、回复顺序和匿名作者标识，就无法严格研究论坛上下文，也不能把结果写成 ERC。

Current view: 第一版基线可以做单条文本分类；上下文实验需要从数据采集阶段保留结构。
GoEmotions 官方 raw release 仅为 157/48,836 个 train/dev targets 提供 parent comment
text，且 raw 未分 split，因此不能直接承担正式上下文实验。

Status: open

Next action:

- 与导师确认上下文建模是否为必做项。
- 若保留线程结构，定义回复路径、截断长度和匿名作者字段。

## Q4. LLM 相对编码器基线的研究价值是什么？

Why it matters: 题目包含 LLM，但这不意味着 LLM 必然性能更好。需要预先定义比较维度，避免项目退化为 API 演示。

Current view: GoEmotions 的 EXP-018 简单多标签基线与 EXP-020 BERT-base-cased
dev 基线已经冻结，可以据此登记 zero-shot/few-shot LLM 对照。比较维度包括
Macro-F1、按类别指标、格式有效率、稳定性、成本和延迟。核心问题是 LLM 是否
真正增加无需监督微调的能力，还是只成为成本更高的分类器；解释生成仅作为附加
功能。TweetEval 分数不能作为 GoEmotions LLM 的性能对照。

Status: open; ready for protocol; GoEmotions test gate remains closed

Next action:

- 固定首个 LLM 的精确版本、zero-shot/few-shot 提示、标签解析和重试规则。
- 预登记成本、延迟、示例选择和数据处理边界，再读取任何 LLM 结果。
- 根据基线结果决定是否需要 LoRA。

## Q5. 上下文收益是否只发生在特定失败类型？

Why it matters: 总体分数可能掩盖反讽、指代、否定和情绪转移样本上的真实收益。

Current view: 需要将总体评估和预先定义的上下文依赖子集评估分开。

Status: open

Next action:

- 定义上下文依赖样本的标注规则。
- 比较无上下文、父回复和完整线程。
- 检查上下文是否也引入主题或说话者泄漏。

## Q6. 哪些证据足以支持最终申请表述？

Why it matters: 计划、演示和单次最好结果不能自动成为 CV 或 SOP 事实。

Current view: 只有 [`../../projects/llm-forum-text-emotion-recognition/evidence-log.md`](../../projects/llm-forum-text-emotion-recognition/evidence-log.md) 中状态为 `Verified` 的条目可以支持完成性和量化表述。

Status: process-defined

Next action:

- 从第一次复现实验开始同步记录 commit、配置、日志、预测和复核方式。
- 每个阶段结束时审计一次项目表述与证据编号。
