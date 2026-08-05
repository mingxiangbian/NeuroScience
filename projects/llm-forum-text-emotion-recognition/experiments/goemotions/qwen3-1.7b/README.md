# Qwen3-1.7B Local LLM Experiments

本目录承载 GoEmotions 上的本地 Qwen3-1.7B 实验。它同时保留两条不同的证据线：

1. `Qwen3-1.7B` post-trained 模型的 zero-shot、few-shot 与 LoRA 实用性能。
2. `Qwen3-1.7B-Base` 与 `Qwen3-1.7B` 的 matched frozen probe，用于比较
   post-training 前后的情绪标签线性可解码性。

两条证据不能混写。Instruct 的提示遵循能力不能证明 Base 没有相关表征，probe
结果也不能直接证明模型或人类使用了某种情绪机制。

## Current Status

- EXP-018 与 EXP-020 已冻结。
- EXP-038 已完成并独立验证一次性 GoEmotions test gate；test 已消费。
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
- EXP-032 train-only Minor 加速预检已完成并独立验证。在相同有效 batch、100 次
  optimizer update 和 1000 条样本下，`batch5-grad2` 相对 `batch2-grad5` 的稳态
  rows/s 比值为 `0.981853`，峰值内存为 `7.312`/`5.179` GB，因此正式重训继续采用
  `batch2-grad5`。公共前缀 KV cache 在 32 条固定训练样本上快 `1.275726x`，但只有
  `31/32` 输出逐 token 一致，故按冻结门拒绝并继续使用完整 prompt。未读取 dev/test。
- 候选 EXP-033 的无训练合同审计与独立复算均已通过：43,410 条训练 target 逐条保留
  官方标签，包含全部 1,396 条 `neutral+emotion`；开放 grammar 接受 `43,410/43,410`，
  旧 closed grammar 恰好拒绝这 1,396 条。MLX-LM 的实际 chat-template 边界也在全部
  样本上等价：4 个空 thinking 控制 token 仍参与 loss，JSON target 所处上下文与
  `enable_thinking=false` 的正式推理前缀一致。该检查未加载模型或读取 dev/test。
- 第二层执行契约 V1 证明了 EXP-029 的完整 `model`、`training` 和 `preflight` 对象
  逐字段继承，并按 manifest 重新计算本地 MLX 模型目录 8 个文件共
  `3,452,636,312` bytes 的 SHA-256。真实 MLX-LM `TokenizerWrapper` 和
  `ChatDataset.process` 已复算 64 条私有边界 smoke：覆盖全部 28 标签、16 条
  `neutral+emotion`、全部 2 条 512-token 截断记录，以及 4/5 标签 target。
- 独立复核发现 V1 尚未冻结资源/seed 续跑门、标签顺序和 LoRA 运行时入口，因此
  V1 不能单独放行 runner。V2 补齐并 `--check`：`emotions.txt` 明确绑定 neutral
  ID `27`，资源预算和 seed 42 续跑判据逐字段继承 EXP-029，并重新哈希 Python 解释器
  条件、10 个运行时包版本，以及 `mlx_lm.lora` 入口和 9 个关键训练源码。
- 第二次独立复核指出 V2 的手选源码不是完整依赖闭包，且 verifier 复用了 auditor 的
  核心函数。当前有效的 V3 改为冻结整个 `mlx_lm/**/*.py` 源码树：166 个文件共
  `1,531,573` bytes；V3 verifier 独立实现全部关键复算，不导入 auditor。V1 的 8 个
  模型文件与 64 条 tokenizer 边界检查也在 V3 中再次执行。所有审计均未执行模型前向、
  反向或参数更新，且未读取 dev/test。
- 新 aligned prompt 使平均训练序列由 EXP-029 的约 `180` 增至约 `196` tokens；因此
  EXP-032 的耗时投影不能直接沿用。只消费冻结合同的 runner 已实现并通过无模型审计；
  64 条边界数据上的一次显式授权 50-iteration train-only smoke 已完成并独立验证。
  10 次 optimizer update 用时 `73.061` 秒，median throughput 为 `0.7435 it/s`，峰值
  MLX memory 为 `7.208` GB，完整 21,705 micro-iteration 投影为 `8.109` 小时。
- EXP-033 已作为 Major 登记。独立 runner 不包含数据制备、dev 或 test 命令，只接受
  SHA-256 冻结的 aligned train JSONL。首版 runner dry-run 保留为 V1 中间证据；只读
  复核发现授权绑定、静默超时、重复配置翻译和 protocol 绑定不足后，V2 改为消费
  单独冻结的 canonical MLX runtime contract，并由不导入 runner 的 verifier 独立复算。
  最终复核又发现 V2 在 stdout EOF 后使用无超时 `process.wait()`，故 V2 也保留为中间
  证据。当前 V3 对 EOF 后等待施加相同剩余 wall-time，并用“关闭输出后挂起”的假进程
  回归通过；V3 dry-run、独立 verification 和 PRE-EXP-033 V3 重放均为 `Passed`。
  它再次确认 43,410 条 target、1,396 条 `neutral+emotion`、完整模型文件、MLX-LM
  源码树及 train-only runtime config。smoke 授权严格绑定当前 config、dry-run
  verification 与 runtime 哈希；训练保存 224 个 LoRA 张量，共 `4,980,736` 个参数，
  112 个 `lora_b` 张量均非零。初末 loss 窗口为 `6.153`/`0.3545`，只属于小样本训练
  链路证据，不是分类性能。独立 smoke verifier 复算全部门为 `Passed`，未读取 dev/test。
  后续 formal V2 gate 重新冻结完整模型、MLX-LM 源码树、训练输入与独立 verifier，并在
  单独 seed-42 授权后完成正式 train-only 运行。21,705 次 micro-iteration、4,341 次
  optimizer update 用时 `26,963.19` 秒，峰值 `7.208` GB；独立 verifier 确认 112/112
  个 LoRA-B 张量非零、真实前向 logits finite，且训练只访问 train。
- EXP-033 seed-42 完整 dev validation 已完成并独立验证。Macro-F1 为 `0.427959`，较
  EXP-029 seed-42 adapter 在 EXP-031 aligned-open 条件下的 `0.440637` 低 `0.012678`；
  10,000 次 paired bootstrap 95% CI 为 `[-0.026938,+0.001434]`，预登记 improvement
  gate 未通过。parser 为 `5,426/5,426`，API cost USD 0，test 未获取或读取。
- 修复训练 target 后仍存在近单标签偏差：全量 gold/predicted cardinality 为
  `1.175820/1.058054`；878 条多标签样本为 `2.086560/1.145786`。174 条 gold
  `neutral+emotion` 上 subset accuracy 为 0，且目标组合预测数仍为 0。该结论是
  Verified 行为负结果，不是执行失败，也不支持内部机制推断。
- EXP-034 Minor 随后将同一冻结 adapter 回放到它见过的全部 1,396 条
  `neutral+emotion` 训练样本。目标共现预测仍为 `0/1,396`，gold/predicted
  cardinality 为 `2.044413/1.019341`；26 条输出虽含多个标签，却没有一条同时包含
  neutral。独立 verifier 返回 `Passed`，dev/test 未读取。这排除了“主要只是 held-out
  泛化失败”的简单解释，但不能在 exposure、objective、标签顺序、LoRA 或模型容量间归因。
- EXP-038 test 上，EXP-025 frozen prompting Macro-F1 为 `0.233653`，EXP-029 三 seed
  历史 LoRA 为 `0.450652 +/- 0.032175`，EXP-033 target-aligned seed 42 为 `0.444675`，
  均低于 EXP-020 BERT 的 `0.488328 +/- 0.008771`。EXP-029 保留 ontology-misaligned
  标记；EXP-033 是主要 aligned LLM 结果。test 不再用于任何开发。

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
-> EXP-032 train-only acceleration preflight (verified; both proposed optimizations rejected)
-> PRE-EXP-033 target-aligned train contract audit (verified; no model execution)
-> PRE-EXP-033 execution contract V1 (verified intermediate; insufficient alone)
-> PRE-EXP-033 execution contract V2 (verified intermediate; incomplete source closure)
-> PRE-EXP-033 execution contract V3 (verified current gate; no model execution)
-> EXP-033 runner dry-run V1 (verified intermediate; superseded for authorization)
-> EXP-033 runner dry-run V2 (verified intermediate; EOF wait timeout incomplete)
-> EXP-033 runner dry-run V3 (verified current smoke gate; no model execution)
-> EXP-033 50-iteration train-only smoke (verified; no dev/test access)
-> EXP-033 formal seed-42 train-only run (verified)
-> EXP-033 seed-42 dev validation (verified negative result; improvement gate failed)
-> EXP-034 exact train neutral-cooccurrence diagnostic (verified; 0/1,396 target co-predictions)
-> EXP-038 one frozen GoEmotions test gate (verified; consumed)
-> forum data and thread-context protocol

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
- [`preflight/pre-exp-033-target-aligned-contract.json`](preflight/pre-exp-033-target-aligned-contract.json)
- [`preflight/pre-exp-033-target-aligned-audit.json`](preflight/pre-exp-033-target-aligned-audit.json)
- [`preflight/pre-exp-033-target-aligned-verification.json`](preflight/pre-exp-033-target-aligned-verification.json)
- [`preflight/pre-exp-033-execution-contract.json`](preflight/pre-exp-033-execution-contract.json)
- [`preflight/pre-exp-033-execution-audit.json`](preflight/pre-exp-033-execution-audit.json)
- [`preflight/pre-exp-033-execution-verification.json`](preflight/pre-exp-033-execution-verification.json)
- [`preflight/pre-exp-033-execution-v2-contract.json`](preflight/pre-exp-033-execution-v2-contract.json)
- [`preflight/pre-exp-033-execution-v2-audit.json`](preflight/pre-exp-033-execution-v2-audit.json)
- [`preflight/pre-exp-033-execution-v2-verification.json`](preflight/pre-exp-033-execution-v2-verification.json)
- [`preflight/pre-exp-033-execution-v3-contract.json`](preflight/pre-exp-033-execution-v3-contract.json)
- [`preflight/pre-exp-033-execution-v3-audit.json`](preflight/pre-exp-033-execution-v3-audit.json)
- [`preflight/pre-exp-033-execution-v3-verification.json`](preflight/pre-exp-033-execution-v3-verification.json)
- [V1 intermediate: `preflight/exp-033-runner-dry-run-verification.json`](preflight/exp-033-runner-dry-run-verification.json)
- [`preflight/exp-033-canonical-mlx-runtime-v2.json`](preflight/exp-033-canonical-mlx-runtime-v2.json)
- [V2 intermediate: `preflight/exp-033-runner-dry-run-verification-v2.json`](preflight/exp-033-runner-dry-run-verification-v2.json)
- [`preflight/exp-033-runner-dry-run-v3.json`](preflight/exp-033-runner-dry-run-v3.json)
- [`preflight/exp-033-runner-dry-run-verification-v3.json`](preflight/exp-033-runner-dry-run-verification-v3.json)
- [`preflight/exp-033-smoke.json`](preflight/exp-033-smoke.json)
- [`preflight/exp-033-smoke-verification.json`](preflight/exp-033-smoke-verification.json)
- [`protocols/exp-033-target-aligned-lora-v3.md`](protocols/exp-033-target-aligned-lora-v3.md)
- [`configs/exp-033-target-aligned-lora-v3.json`](configs/exp-033-target-aligned-lora-v3.json)
- [`preflight/exp-033-formal-gate-contract-v2.json`](preflight/exp-033-formal-gate-contract-v2.json)
- [`preflight/exp-033-seed42-validation-contract-v1.json`](preflight/exp-033-seed42-validation-contract-v1.json)
- [`runs/exp-033-target-aligned-lora/seed-42/verification.json`](runs/exp-033-target-aligned-lora/seed-42/verification.json)
- [`runs/exp-033-target-aligned-lora/REPORT.md`](runs/exp-033-target-aligned-lora/REPORT.md)
- [`runs/exp-033-target-aligned-lora/validation-seed-42-v1/verification.json`](runs/exp-033-target-aligned-lora/validation-seed-42-v1/verification.json)
- [`runs/exp-029-instruct-lora/REPORT.md`](runs/exp-029-instruct-lora/REPORT.md)
- [`runs/exp-029-instruct-lora/multi-seed-aggregate.json`](runs/exp-029-instruct-lora/multi-seed-aggregate.json)
- [`runs/exp-029-instruct-lora/multi-seed-verification.json`](runs/exp-029-instruct-lora/multi-seed-verification.json)
- [`runs/exp-031-neutral-ontology-inference-ablation/REPORT.md`](runs/exp-031-neutral-ontology-inference-ablation/REPORT.md)
- [`runs/exp-031-neutral-ontology-inference-ablation/multi-seed-aggregate.json`](runs/exp-031-neutral-ontology-inference-ablation/multi-seed-aggregate.json)
- [`runs/exp-031-neutral-ontology-inference-ablation/multi-seed-verification.json`](runs/exp-031-neutral-ontology-inference-ablation/multi-seed-verification.json)
- [`runs/exp-032-acceleration-preflight/run.json`](runs/exp-032-acceleration-preflight/run.json)
- [`runs/exp-032-acceleration-preflight/training-benchmark.json`](runs/exp-032-acceleration-preflight/training-benchmark.json)
- [`runs/exp-032-acceleration-preflight/kv-cache-summary.json`](runs/exp-032-acceleration-preflight/kv-cache-summary.json)
- [`runs/exp-032-acceleration-preflight/verification.json`](runs/exp-032-acceleration-preflight/verification.json)
- [`configs/exp-034-train-neutral-cooccurrence-diagnostic.json`](configs/exp-034-train-neutral-cooccurrence-diagnostic.json)
- [`runs/exp-034-train-neutral-cooccurrence-diagnostic/REPORT.md`](runs/exp-034-train-neutral-cooccurrence-diagnostic/REPORT.md)
- [`runs/exp-034-train-neutral-cooccurrence-diagnostic/verification.json`](runs/exp-034-train-neutral-cooccurrence-diagnostic/verification.json)
- [`../../../models/qwen3-1.7b/manifest.json`](../../../models/qwen3-1.7b/manifest.json)
- [`../../../models/qwen3-1.7b-base/manifest.json`](../../../models/qwen3-1.7b-base/manifest.json)

## Failed But Audited Artifacts

- [`runs/exp-028-matched-frozen-probe/failure.json`](runs/exp-028-matched-frozen-probe/failure.json)
- [`runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md`](runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md)
- [`runs/exp-028-matched-frozen-probe/failed-run-manifest.json`](runs/exp-028-matched-frozen-probe/failed-run-manifest.json)
- [`runs/exp-028-matched-frozen-probe/failed-artifact-verification.json`](runs/exp-028-matched-frozen-probe/failed-artifact-verification.json)

These files establish why the formal run failed and that its diagnostic artifacts are internally
consistent. They do not convert EXP-028 into Verified evidence.
