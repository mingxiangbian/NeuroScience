# GoEmotions Experiments

本目录是与 [`../tweeteval-emotion/`](../tweeteval-emotion/) 并行的
GoEmotions 公开数据实验分支。

## Current Status

- `DATA-GOE-V1` 已于 2026-07-30 冻结。
- 使用 Google Research 发布的 agreement-filtered 官方划分。
- 任务固定为 27 类情绪加 `neutral` 的完整多标签分类。
- train、dev 和 `emotions.txt` 已从固定 revision 获取并通过完整性校验。
- 官方 train/dev 中 41 个 exact-text overlap 已审阅并记录；comment ID
  overlap 为 0，未改变官方 split。
- `EXP-018` 简单多标签基线已完成并独立验证：dev Macro-F1 `0.203644`、
  Micro-F1 `0.377639`、subset accuracy `0.246959`；3,261/5,426 条预测为空。
- `EXP-019` 已完成离线模型哈希、28 标签 BCE 和 Apple MPS 合成训练检查，
  未读取任何项目数据。
- `EXP-020` BERT-base-cased 三 seed dev 基线已完成并独立验证：Macro-F1
  `0.489435 +/- 0.011063`、Micro-F1 `0.586671 +/- 0.002928`、subset
  accuracy `0.440963 +/- 0.003963`。
- `EXP-021` Qwen3-1.7B Base/post-trained 本地环境与来源检查已完成并独立验证：
  两个固定 revision 均已下载、转换为未量化 BF16 并通过合成推理 smoke；它未读取
  任何 GoEmotions split，也不形成性能证据。
- `EXP-022` 32 条 train 小样本成本与 strict-parser 门已完成并独立验证：资源门
  全部通过，但 few-shot JSON 有效率为 `87.5%`，低于预注册的 95%，所以总门失败；
  未读取 gold label、dev 或 test，也未计算性能指标。
- `EXP-023` 数字 label-ID 修复已独立验证为负结果：zero-shot/few-shot 有效率仅为
  `50.0%`/`65.625%`，未授权 full-dev。
- `EXP-024` 标签名 JSON constrained decoding 修复已完成并独立验证：两条件均为
  `32/32 = 100%` 严格有效，资源、失败与截断门全部通过；它只授权登记正式
  full-dev Major，不提供分类性能证据。
- `EXP-025` constrained full-dev zero/few-shot Major 已完成并独立验证：Macro-F1
  `0.222998`/`0.241164`，parser 有效率 `99.9631%`/`100%`；冻结规则选择 few-shot，
  但其 Macro-F1 仍比 EXP-020 BERT 三 seed 均值低 `0.248271`。
- `EXP-026` matched unconstrained-decoder Major 已完成并独立验证：Macro-F1
  `0.228700`/`0.236465`，parser 有效率 `95.9823%`/`90.7298%`。2x2 表明 few-shot
  约束主要恢复 503 个格式失败，而 zero-shot 在双方都有效的 5,206 条中仍有 1,259
  条最终标签集合不同，因此 finite-state mask 不能笼统视为 label-neutral。
- `EXP-027` matched hidden-state smoke 已验证；`EXP-028` matched frozen probe 因
  `344.288` 分钟超过冻结的 240 分钟资源门而保持 `Failed`，其诊断值不进入证据链。
- `EXP-029` Qwen3-1.7B 监督 LoRA 三 seed 已完成并独立验证：冻结规则选择的
  zero-shot dev Macro-F1 为 `0.451374 +/- 0.019212`，较 EXP-025 提高 `0.210209`，
  但仍比 EXP-020 BERT 均值低 `0.038061`。
- `EXP-030` 冻结跨模型 dev 错误分析已完成并独立验证：LoRA subset accuracy
  `0.508293` 高于 BERT 的 `0.440963`，但在 878 条多标签样本上的 subset accuracy
  约为 `0.043`，低于 BERT 的约 `0.179`；174 条 `neutral+emotion` gold 对当前
  Qwen ontology 结构性不可达。48 条冻结匿名案例完成定性编码，公开原文泄漏为 0。
- `EXP-031` 三 seed neutral ontology 推理消融已完成并独立验证：仅开放 decoder
  不改变任何预测；同时对齐 prompt 与 decoder 后 Macro-F1 平均仅 `+0.001682`，
  neutral 共现切片 Samples-F1 为 `-0.009132`，所有条件均未产生 neutral 共现预测。
  正式分类为 `no_material_inference_improvement`，不等价于 target-aligned retraining。
- `EXP-033` seed-42 target-aligned LoRA 与 `EXP-034` train 回放均已独立验证：前者
  dev Macro-F1 为 `0.427959` 且未通过 improvement gate，后者在模型见过的全部
  1,396 条 `neutral+emotion` 训练样本上仍为 0 条目标共现输出。
- `EXP-035` 数据与标注审计已独立验证：1,396/1,396 条 `neutral+emotion` target
  都由跨标注者投票聚合形成，同一标注者共选为 0；官方 `>=2` 票 simplified labels
  精确复现。48 条冻结目的性复核中 6 条被编码为可能需要上下文，但不可外推。
- `EXP-036` dev 逐标注者评分诊断已独立验证：174/174 条对应 target 仍为
  aggregation-only。EXP-029/BERT 的 clear-rater expected set-F1 为
  `0.363250/0.362531`，family delta=`+0.000720`、95% CI 跨 0，属于该冲突切片上的
  practical tie；official exact-match 与个体标注一致度不能混为同一指标。
- `EXP-037` 完整 dev 逐标注者评分诊断已独立验证：5,426 条 dev 和 19,440 行
  raw annotations 全部重建，官方聚合 mismatch 为 0。EXP-029/BERT 的 clear-rater
  soft Macro-F1 为 `0.347253/0.383471`，delta=`-0.036218`、95% CI 不跨 0；相对
  official delta 的 shift=`+0.001843` 且 CI 跨 0，结论为 `gap_remains`。
- `EXP-038` 一次性正式 test gate 已完成并独立验证。EXP-018、EXP-020、EXP-025、
  EXP-029 和 EXP-033 的 test Macro-F1 分别为 `0.196197`、
  `0.488328 +/- 0.008771`、`0.233653`、`0.450652 +/- 0.032175` 和 `0.444675`。
  BERT 相对论文 test 参照 `0.46` 高 `0.028328`；历史 EXP-029 保留 ontology 失配
  标记，EXP-033 是主要 target-aligned LLM 结果。
- GoEmotions test 已消费；此后不得用它进行模型选择、prompt/threshold 修改或重训。
- EXP-018 的全局阈值固定为 `0.5`，EXP-020 固定为论文条件 `0.3`；两者
  均不得在原实验编号下事后调参。

## Files

- [`protocols/data-protocol-v1.md`](protocols/data-protocol-v1.md)：数据来源、
  标签空间、split 纪律、隐私边界和变更规则。
- [`prepare_data.py`](prepare_data.py)：只获取并验证 train/dev/labels 的脚本。
- [`../../data/goemotions/README.md`](../../data/goemotions/README.md)：项目级
  本地数据目录、Git 边界和 manifest 说明。
- [`../../data/goemotions/manifest.json`](../../data/goemotions/manifest.json)：
  不含原文和 comment ID 的已验证快照元数据。
- [`tfidf-ovr-logreg/`](tfidf-ovr-logreg/)：EXP-018 冻结协议、训练与验证代码、
  匿名预测、逐标签指标、混淆矩阵和结果报告。
- [`bert-base/`](bert-base/)：固定 BERT 模型 revision、EXP-019 smoke、
  EXP-020 三 seed 训练、匿名概率、逐标签指标、最终模型哈希和独立验证。
- [`qwen3-1.7b/`](qwen3-1.7b/)：本地 LLM 路线、EXP-021 至 EXP-027 的环境、
  prompt/decoder 和 hidden-state 门，EXP-028 probe 失败记录、EXP-029 LoRA，以及
  EXP-031 neutral ontology 推理消融。
- [`error-analysis/`](error-analysis/)：EXP-030 冻结协议、跨模型全量 dev 错误结构、
  48 条匿名定性复核、公开报告和独立 verifier。
- [`annotation-audit/`](annotation-audit/)：EXP-035 的逐标注者投票聚合、冻结文本复核、
  公开报告和独立 verifier。
- [`disagreement-aware-evaluation/`](disagreement-aware-evaluation/)：EXP-036 的
  174-row 冲突切片和 EXP-037 的完整 dev 逐标注者评分、soft-label Macro-F1、paired
  bootstrap、7 份冻结预测和独立 verifier。
- [`test-gate/`](test-gate/)：EXP-038 的冻结协议、9 个正式测试单元、完整指标、
  匿名预测、聚合结果、verifier 修正说明和独立验证记录。

## Storage Boundary

```text
projects/llm-forum-text-emotion-recognition/
├── data/goemotions/              # upstream data snapshot and manifest
└── experiments/goemotions/       # protocols, code and future runs
```

原始数据固定存放于 `data/goemotions/official/`，不放在 `experiments/`
下面。

## Next Step

1. 保持 EXP-018、EXP-020、EXP-025、EXP-029、EXP-033 和 EXP-038 的配置与 test
   结果冻结；test 已消费，不再用于开发。
2. GoEmotions 公开数据复现阶段可阶段性关闭：BERT 是 primary metric 最强条件，
   target-aligned 1.7B LoRA 未超过 BERT，但负结果及错误归因链完整。
3. 下一主线是根据导师意见冻结论坛数据、线程上下文、授权、匿名化、标注和
   thread-level holdout 协议，再复用已验证的训练与评估链路。
4. 表征支线若继续，必须在 EXP-028 失败之后使用新实验编号、现实资源门和透明恢复
   规则；不得把 EXP-028 的诊断值升级为 Verified 机制结论。
