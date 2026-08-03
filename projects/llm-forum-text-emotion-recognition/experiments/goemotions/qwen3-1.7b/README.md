# Qwen3-1.7B Local LLM Experiments

本目录承载 GoEmotions 上的本地 Qwen3-1.7B 实验。它同时保留两条不同的证据线：

1. `Qwen3-1.7B` post-trained 模型的 zero-shot、few-shot 与 LoRA 实用性能。
2. `Qwen3-1.7B-Base` 与 `Qwen3-1.7B` 的 matched frozen probe，用于比较
   post-training 前后的情绪标签线性可解码性。

两条证据不能混写。Instruct 的提示遵循能力不能证明 Base 没有相关表征，probe
结果也不能直接证明模型或人类使用了某种情绪机制。

## Current Status

- EXP-018 与 EXP-020 已冻结。
- GoEmotions test 未获取，test gate 关闭。
- EXP-021 已完成并独立验证：两个官方固定 revision 已下载并转换为未量化 MLX
  BF16，Base 与 post-trained 条件均通过合成输入生成检查。
- 四份本地模型副本共 `14,437,414,837` bytes；逐文件大小与 SHA-256 位于两个
  model manifest，运行与复核位于 `runs/exp-021-environment-model-smoke/`。
- EXP-021 未读取 GoEmotions train/dev/test；合成生成不构成任务性能证据。
- EXP-022 小样本成本与 parser 试跑已完成并独立验证。时间、内存、生成失败与截断
  门均通过：zero-shot/few-shot 的完整 dev 线性估计分别为约 `1.25`/`1.48` 小时，
  峰值 MLX memory 为 `3.65` GB。
- EXP-022 总门未通过：zero-shot 严格 JSON 有效率为 `31/32 = 96.875%`，但
  few-shot 只有 `28/32 = 87.5%`，低于预注册的 95%。该结果不含 gold label 或
  性能指标，不能据此比较 zero-shot 与 few-shot 的准确性。
- EXP-023 固定数字 label-ID 修复已完成并独立验证，但有效率进一步降为
  zero-shot `50.0%`、few-shot `65.625%`，因此作为负结果保留。
- EXP-024 回到 EXP-022 的标签名 prompt，只增加有限状态 constrained decoding；
  两条件均达到 `32/32 = 100%` 严格有效，64 次均正常结束。完整 dev 线性估计约为
  `1.08`/`1.46` 小时，峰值 MLX memory `3.65` GB，全部冻结门通过并独立复核。
- EXP-024 的 100% 是解码器结构保证，不是无约束模型的提示遵循或分类性能证据。
- EXP-025 constrained full-dev Major 已完成并独立验证。zero-shot/few-shot Macro-F1 为
  `0.222998`/`0.241164`，parser 有效率为 `99.9631%`/`100%`；按冻结选择规则选择
  few-shot，其相对 zero-shot 的配对差值为 `+0.018166`，95% bootstrap 区间为
  `[+0.002977, +0.034469]`。
- EXP-026 matched unconstrained decoder ablation 已完成并独立验证。zero-shot/few-shot
  Macro-F1 为 `0.228700`/`0.236465`，parser 有效率为 `95.9823%`/`90.7298%`。
  verifier 对 10,852 条记录的复算最大数值差异为 0，test 仍未获取。
- 2x2 显示 constraint 不是普遍 label-neutral：few-shot 的 4,923 个双方有效输出标签
  集合完全一致，约束主要救回 503 个无效输出；zero-shot 的 5,206 个双方有效输出中
  只有 `75.8164%` 标签集合完全一致。decoder 的 Macro-F1 影响较小且方向不一致。
- 四个冻结 Qwen prompt/decoder 条件都仅略高于 EXP-018 简单词法 Macro-F1，并显著低于 EXP-020 BERT
  三 seed；当前证据不支持用冻结 Qwen prompt 替代监督编码器。
- EXP-027 合成 hidden-state smoke 已完成并独立验证：两条件使用完全相同的 token ID，
  均得到有限的 `6 x 2048` final-layer mean-pooled 表征，峰值 MLX memory 约 `3.53` GB；
  配对表征平均余弦相似度为 `0.970346`。该结果只验证 matched probe 接口，不是情绪
  性能或机制证据，且未读取任何项目 split。
- EXP-028 matched Base/post-trained frozen probe 的零数据 preflight `28/28` 通过，四份
  train/dev 特征和 8 个真实/置乱探针均完成；但 probe fitting/evaluation 实际耗时
  `344.288` 分钟，超过冻结的 240 分钟资源上限，因此正式状态为 `Failed`，没有
  `run.json` 或正式 `verification.json`。
- 失败产物审计重算概率、指标和 10,000 次 bootstrap 后全部一致。失败运行中的诊断值
  为 Base/post-trained Macro-F1 `0.310534`/`0.306373`，配对差值 `-0.004161`，95%
  CI `[-0.013156, 0.004711]`，按冻结阈值属于 `practical_tie`。这些值不能进入
  `evidence-log.md`，正式表征结论需要新的实验编号。
- EXP-029 Qwen3-1.7B 监督 LoRA 已完成三个正式 seed 并独立验证。zero-shot/few-shot
  三 seed dev Macro-F1 分别为 `0.451374 +/- 0.019212` 与
  `0.425265 +/- 0.004858`；冻结规则选择 zero-shot。选定结果较 EXP-025 的 frozen
  few-shot 提高 `0.210209`，但仍比 EXP-020 BERT 均值低 `0.038061`。
- EXP-029 三个 seed 的训练和双条件全量 dev 评估均通过时间、内存、隐私与 test
  gate；parser 有效率均为 100%，API 成本为 USD 0。LoRA 是行为证据，不补救或替代
  EXP-028 缺失的 Verified 表征结论；4B 和 GoEmotions test 尚未执行。
- EXP-031 复用三个冻结 EXP-029 adapters，完成 closed decoder、仅开放 decoder、
  prompt/decoder 同时对齐的三条件全量 dev 推理消融。old-prompt/open-decoder 与
  closed condition 的预测完全一致；aligned-open 的 Macro-F1 平均差值为
  `+0.001682`，Samples-F1、exact match 与 neutral 共现切片 Samples-F1 分别变化
  `-0.003240`、`-0.005529` 和 `-0.009132`，且所有 seed 均未产生 neutral 共现预测。
- EXP-031 三份 seed verification 与聚合 verification 均通过，正式分类为
  `no_material_inference_improvement`。它只说明 inference-only correction 对当前
  target-misaligned adapters 不足，不估计 target-aligned retraining，也不是机制证据。

## Planned Order

```text
Behavior line
EXP-021 environment/model smoke
-> EXP-022/023 parser failures
-> EXP-024 constrained decoder gate (verified)
-> EXP-025/026 prompt x decoder full-dev comparison (verified)
-> EXP-029 Instruct LoRA, three seeds (verified)
-> EXP-030 pre-registered cross-model error analysis (verified)
-> EXP-031 neutral ontology inference ablation (verified negative result)
-> new experiment ID for target-aligned retraining, if registered
-> one GoEmotions test gate after candidate freeze

Representation line
EXP-027 matched hidden-state smoke (verified interface only)
-> EXP-028 matched frozen probe (failed resource gate; artifacts audited)
-> new experiment ID required for any formal probe claim
-> optional SAE/intervention only after a valid representation baseline
```

## Model Storage

官方源模型与本地 MLX BF16 转换分别存放在：

```text
models/qwen3-1.7b/{upstream,mlx-bf16}/
models/qwen3-1.7b-base/{upstream,mlx-bf16}/
```

模型二进制必须由各模型目录的 `.gitignore` 排除。仓库只保留 README、revision、
下载与转换版本、文件大小及 SHA-256 manifest。

## Protocols

- [`protocols/exp-021-qwen3-1.7b-environment-smoke.md`](protocols/exp-021-qwen3-1.7b-environment-smoke.md)
- [`protocols/exp-022-resource-parser-trial.md`](protocols/exp-022-resource-parser-trial.md)
- [`protocols/exp-023-label-id-parser-trial.md`](protocols/exp-023-label-id-parser-trial.md)
- [`protocols/exp-024-constrained-json-trial.md`](protocols/exp-024-constrained-json-trial.md)
- [`protocols/exp-025-full-dev-zero-few-shot.md`](protocols/exp-025-full-dev-zero-few-shot.md)
- [`protocols/exp-026-unconstrained-decoder-ablation.md`](protocols/exp-026-unconstrained-decoder-ablation.md)
- [`protocols/exp-028-matched-frozen-probe.md`](protocols/exp-028-matched-frozen-probe.md)
- [`protocols/exp-029-instruct-lora.md`](protocols/exp-029-instruct-lora.md)
- [`protocols/exp-031-neutral-ontology-inference-ablation.md`](protocols/exp-031-neutral-ontology-inference-ablation.md)

## Verified Artifacts

- [`runs/exp-021-environment-model-smoke/run.json`](runs/exp-021-environment-model-smoke/run.json)
- [`runs/exp-021-environment-model-smoke/verification.json`](runs/exp-021-environment-model-smoke/verification.json)
- [`runs/exp-022-resource-parser-trial/summary.json`](runs/exp-022-resource-parser-trial/summary.json)
- [`runs/exp-022-resource-parser-trial/verification.json`](runs/exp-022-resource-parser-trial/verification.json)
- [`runs/exp-023-label-id-parser-trial/summary.json`](runs/exp-023-label-id-parser-trial/summary.json)
- [`runs/exp-023-label-id-parser-trial/verification.json`](runs/exp-023-label-id-parser-trial/verification.json)
- [`runs/exp-024-constrained-json-trial/summary.json`](runs/exp-024-constrained-json-trial/summary.json)
- [`runs/exp-024-constrained-json-trial/verification.json`](runs/exp-024-constrained-json-trial/verification.json)
- [`runs/exp-025-full-dev-zero-few-shot/run.json`](runs/exp-025-full-dev-zero-few-shot/run.json)
- [`runs/exp-025-full-dev-zero-few-shot/aggregate-metrics.json`](runs/exp-025-full-dev-zero-few-shot/aggregate-metrics.json)
- [`runs/exp-025-full-dev-zero-few-shot/paired-bootstrap.json`](runs/exp-025-full-dev-zero-few-shot/paired-bootstrap.json)
- [`runs/exp-025-full-dev-zero-few-shot/verification.json`](runs/exp-025-full-dev-zero-few-shot/verification.json)
- [`runs/exp-026-unconstrained-decoder-ablation/run.json`](runs/exp-026-unconstrained-decoder-ablation/run.json)
- [`runs/exp-026-unconstrained-decoder-ablation/aggregate-metrics.json`](runs/exp-026-unconstrained-decoder-ablation/aggregate-metrics.json)
- [`runs/exp-026-unconstrained-decoder-ablation/paired-bootstrap.json`](runs/exp-026-unconstrained-decoder-ablation/paired-bootstrap.json)
- [`runs/exp-026-unconstrained-decoder-ablation/joint-decoder-analysis.json`](runs/exp-026-unconstrained-decoder-ablation/joint-decoder-analysis.json)
- [`runs/exp-026-unconstrained-decoder-ablation/verification.json`](runs/exp-026-unconstrained-decoder-ablation/verification.json)
- [`runs/exp-027-frozen-probe-smoke/run.json`](runs/exp-027-frozen-probe-smoke/run.json)
- [`runs/exp-027-frozen-probe-smoke/verification.json`](runs/exp-027-frozen-probe-smoke/verification.json)
- [`preflight/exp-028-matched-frozen-probe.json`](preflight/exp-028-matched-frozen-probe.json)
- [`preflight/exp-029-data-preparation.json`](preflight/exp-029-data-preparation.json)
- [`preflight/exp-029-zero-step.json`](preflight/exp-029-zero-step.json)
- [`preflight/exp-029-smoke.json`](preflight/exp-029-smoke.json)
- [`runs/exp-029-instruct-lora/REPORT.md`](runs/exp-029-instruct-lora/REPORT.md)
- [`runs/exp-029-instruct-lora/multi-seed-aggregate.json`](runs/exp-029-instruct-lora/multi-seed-aggregate.json)
- [`runs/exp-029-instruct-lora/multi-seed-verification.json`](runs/exp-029-instruct-lora/multi-seed-verification.json)
- [`runs/exp-031-neutral-ontology-inference-ablation/REPORT.md`](runs/exp-031-neutral-ontology-inference-ablation/REPORT.md)
- [`runs/exp-031-neutral-ontology-inference-ablation/multi-seed-aggregate.json`](runs/exp-031-neutral-ontology-inference-ablation/multi-seed-aggregate.json)
- [`runs/exp-031-neutral-ontology-inference-ablation/multi-seed-verification.json`](runs/exp-031-neutral-ontology-inference-ablation/multi-seed-verification.json)
- [`../../../models/qwen3-1.7b/manifest.json`](../../../models/qwen3-1.7b/manifest.json)
- [`../../../models/qwen3-1.7b-base/manifest.json`](../../../models/qwen3-1.7b-base/manifest.json)

## Failed But Audited Artifacts

- [`runs/exp-028-matched-frozen-probe/failure.json`](runs/exp-028-matched-frozen-probe/failure.json)
- [`runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md`](runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md)
- [`runs/exp-028-matched-frozen-probe/failed-run-manifest.json`](runs/exp-028-matched-frozen-probe/failed-run-manifest.json)
- [`runs/exp-028-matched-frozen-probe/failed-artifact-verification.json`](runs/exp-028-matched-frozen-probe/failed-artifact-verification.json)

These files establish why the formal run failed and that its diagnostic artifacts are internally
consistent. They do not convert EXP-028 into Verified evidence.
