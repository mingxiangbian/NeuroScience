# DEC-SQMA-CLASSIFIER-FREE-V1

日期：2026-09-04

状态：`Registered / supersedes classifier-assisted first comparison`

## 1. 决策

首轮Agent实验直接使用未经本项目LoRA调参的官方post-trained `Qwen/Qwen3-4B`。Single Agent、Self-Consistency和Role-diverse Multi-Agent只接收同一份`analysis_text`、冻结六标签ontology和各自方法内部产生的结构化输出。

首轮不向任何生成调用提供M1/M3标签、概率、Router score或其他分类器结果；不训练M1、M3或Agent adapter。

## 2. 原因

此前计划重做M1/M3 cross-fit，是为了让分类器结果能作为Judge与Trigger输入而不污染后续fold。但当前研究问题首先是：

> 在相同原始Qwen3-4B和匹配计算预算下，角色分工是否优于单次调用与重复采样？

这个问题不需要重新训练辅助分类器。先加入M1/M3会增加训练成本、引入额外信息路径，并削弱“角色分工本身”的解释。

## 3. 首轮系统

- `S1`：Single Agent，一次调用完成evidence、appraisal、pragmatics和final labels。
- `S2a`：call-matched Self-Consistency，三次独立Single调用，逐标签严格多数票。
- `S2b`：token-budget-matched Self-Consistency，在S3总prefill+generated ceiling内运行最多完整Single调用，至少两次。
- `S3`：Evidence + Appraisal → Pragmatics Critic → Judge，三次顺序调用。

所有系统共享：

- 同一Qwen checkpoint/revision、chat template和non-thinking模式；
- 同一`analysis_text`和ontology；
- 同一sampling参数及预登记seed派生；
- 无Qwen repair、无外部工具、无自由讨论。

## 4. 输出与失败

Judge不再执行`accept_baseline/revise_labels`。它只能：

- `decide_labels`：直接输出六标签子集，空集表示neutral；
- `abstain`：不输出标签。

技术invalid或合法abstain在全覆盖指标中都映射为空标签集，并分别报告invalid/abstain率。Self-Consistency中相应调用作为空标签票；偶数调用的逐标签平票判为该标签不存在。

## 5. 执行顺序

1. `SQMA-003`：32个Agent-Dev component的classifier-free preflight；只评价schema、evidence substring、稳定性、token、latency和资源，不读取gold。
2. 若SQMA-003通过且完整672-row比较的保守wall投影不超过48小时，独立密封Agent-Tune fold 3。
3. 在Agent-Tune全部672行完成S1/S2a/S2b/S3 matched comparison，并由独立consumer读取gold评分。
4. 只有Role-diverse通过冻结gate后，才重新讨论Selective Trigger；届时是否需要分类器及其strict outputs另行决定。

## 6. 证据边界

Agent-Tune比较是development/tuning evidence，不是最终Confirm。它可以决定是否值得进入fold 4，但不能单独支持外部泛化、最终独立测试或普遍优于分类器的主张。

SQMA-001和SQMA-002仍作为已完成的数据治理证据保留；本决策只取消当前阶段的M1/M3重训，不改写它们的状态或工件。
