# EXP-047: Weibo EClass Stage 5 Generative LoRA

---
date: 2026-08-09
experiment_id: EXP-047
tier: Major
rq: RQ-F1
status: Registered
stage: stage-5-generative-lora
dataset_protocol: DATA-WEIBO-TASK-V1
parent_experiment: EXP-042, EXP-043, EXP-044, EXP-046
execution_authorized: false
---

## Question and Expected Contribution

在冻结的 Weibo EClass 七类单标签任务上，使用完整 train split 对同一个
`Qwen/Qwen3-4B` 做 label-only generative LoRA 后，是否能在相同的 target-only、
reasoning-on、singleton 推理协议下，获得相对冻结 Qwen 的可复现 Macro-F1 增益？这种
适配后的系统与中文 RoBERTa encoder 之间还剩多大差距？

正结果支持任务监督能改善本地生成式情绪识别系统。负结果同样有效：它将说明在当前模型、
ontology、数据规模和资源预算下，LoRA 仍未抵消生成式 decoder 相对监督 encoder 的性能或
成本劣势。本实验只比较可观察的分类行为，不把生成过程文本写成忠实推理或内部情绪机制。

## Controlled Change

本实验只改变 Qwen 是否加载在 Weibo train 上训练的 LoRA adapter，以及 adapter 的训练
seed。下列项目保持不变：

- 数据协议、split、七类 ontology、target-only 输入和样本顺序；
- Qwen 精确 revision、BF16 非量化权重、chat template、system/user prompt；
- strict JSON 输出 schema、parser、greedy decoding、reasoning-on 和 1,024-token 上限；
- singleton 推理、指标、无效输出处理、切片和 group-level bootstrap；
- train 目标、LoRA 插入位置、容量、optimizer、学习率、epoch 和 checkpoint 规则。

EXP-043 C 使用 batch 8，EXP-046 已证明共同批次组成可能改变最终标签。因此 EXP-043 C 只
作为历史结果；EXP-047 必须新跑一次无 adapter 的 singleton full-dev reference，才能形成
严格的 LoRA 适配对照。

## Frozen Data Boundary

- Dataset protocol: `DATA-WEIBO-TASK-V1`.
- Train: 5,995 rows, SHA-256
  `b1fd309acf45dfa4ad0c907ee3f373ea95fce751d51b637d402e289aa79d19e0`.
- Validation: 1,272 rows, SHA-256
  `99d80e1433bddea7b639983b8fa874e45d585318aa47eb87ab29581e02f72a4a`.
- Evaluation label order: `anger`, `joy`, `negative`, `neutral`, `no_emotion`,
  `positive`, `sadness`.
- Training and formal inference both use `views.target_only.target`; `PrevCL`, `SufCL` and
  future text are absent from the model input.
- All 5,995 train rows are used once per epoch in the natural frozen distribution. No class
  resampling, class weight, synthetic sample or external corpus is introduced.
- The rendered full-train maximum observed in EXP-044 was 289 tokens. Formal preparation must
  stop on any row above 512 tokens rather than silently truncate it.
- Validation cannot be read until all three adapters and their train-only replay gates pass.
- Test inputs and labels are forbidden. EXP-047 does not authorize or implement a test path.

## Frozen Model, Prompt and Supervision

- Model: `Qwen/Qwen3-4B`, revision
  `1cfa9a7208912126459214e8b04321603b3df60c`, Apache-2.0.
- Runtime weights: local MLX BF16, unquantized; manifest SHA-256
  `da447350d9e43213dacc1202da03b50d7e7114b0a4fe2904ff353240b404a641`.
- Prompt: `stage-4-qwen-2x2/prompt-v1.json`, SHA-256
  `d9a92aab3a531b769c3b4794572cf0842536c7c38dcdd6a1cd4ac25885e6631b`.
- Parser: `stage-4-qwen-2x2/label_parser.py`, SHA-256
  `429c8708da864086c11859449ebf427b8a681c20eec58900d97574d508067a21`.
- Assistant target: exactly `{"label":"<gold_label>"}`. Prompt masking is enabled, so only
  assistant-channel tokens receive loss.
- The frozen Qwen chat template inserts `<think>\n\n</think>\n\n` before the JSON target. This
  is an empty wrapper, not rationale supervision. No human or synthetic rationale is used.
- The absence of rationale gold means any post-LoRA change in generated thinking length is an
  observed behavior, not evidence that a reasoning chain was learned or made the answer faithful.

## Frozen LoRA Training

All three seeds use exactly the EXP-044-tested configuration:

| Field | Frozen value |
| --- | --- |
| Seeds | `42`, `43`, `44` |
| Epochs | `2` |
| Iterations | `5,995` per epoch; `11,990` per seed |
| Micro-batch / accumulation | `1 / 1` |
| Maximum sequence length | `512` |
| Optimizer | MLX `adamw` with version-frozen package defaults |
| Learning rate / schedule | `1e-5`, constant (`lr_schedule=null`) |
| Gradient checkpointing | enabled |
| Prompt masking | enabled |
| Rank / scale / dropout | `8 / 20.0 / 0.0` |
| Adapted blocks | final 16 blocks, indices `20..35` |
| Target modules per block | `q/k/v/o_proj`, `gate/up/down_proj` |
| Expected insertion points | `112` |
| Expected trainable parameters | `7,340,032` |

Training data are shuffled only by the frozen seed. Loss is logged but cannot trigger early
stopping, epoch changes, seed cancellation or hyperparameter changes. Each seed saves an epoch-1
recovery checkpoint and a final epoch-2 adapter; only the final adapter is eligible for replay and
validation. Neither train loss nor validation score is used to choose between checkpoints.

An interrupted run may resume only if optimizer state, data cursor and RNG state can be restored
exactly and independently verified. Otherwise the attempt is retained as failed and a new dated
correction plus user authorization is required; existing artifacts are never overwritten.

## Adapter and Runtime Gates

Each seed must pass both gates before any validation access:

1. **Adapter integrity**: exactly 112 insertion points and 7,340,032 trainable parameters;
   exactly 224 finite adapter tensors; all 112 `lora_b` tensors non-zero; final adapter reload and
   one train-only forward pass are finite; peak memory is below 13 GB.
2. **Post-adapter singleton replay**: reuse the exact 16-row EXP-046 train-derived sample with
   selection digest
   `99f851612df7f5bc67792c9892655e126ded52a1618fca9113c3d3b9bbe0cebd`.
   Run two fresh-process singleton passes. Final label, parser state and raw output must each be
   `16/16` identical across replays, with at least `15/16` parser-valid outputs.

Failure of either gate stops EXP-047 before validation. It does not authorize a retry, relaxed
parser, reasoning-off substitution or different batch mode.

## Frozen Formal Inference

Only after all three adapters pass the preceding gates, run four fresh-process full-validation
passes in this order:

1. no adapter: matched frozen-Qwen singleton reference;
2. LoRA seed 42 final adapter;
3. LoRA seed 43 final adapter;
4. LoRA seed 44 final adapter.

Every pass uses target-only input, `enable_thinking=true`, greedy decoding (`temperature=0`),
`max_new_tokens=1024`, and
`batch_size=completion_batch_size=prefill_batch_size=1`. Invalid output, missing thinking
boundary, unknown/multiple label or exhausted token budget becomes `__invalid__`, remains in the
denominator and is never repaired, retried or dropped.

A process interruption may continue only from an independently verified exact, unique and ordered
prefix. Completed rows are not regenerated. The four passes must not share a live model process.

## Evaluation and Decision Rules

Primary metric: full-validation Macro-F1 over the seven frozen labels. Report the following for
the frozen reference and every LoRA seed:

- Accuracy, macro precision/recall, Weighted-F1 and per-class precision/recall/F1/support;
- 7-by-8 confusion matrix with rows=gold, columns=predicted and an `__invalid__` column;
- full split, `context_available` and `first_clause` slices;
- strict parser validity, invalid reason counts, thinking/final/generated token counts;
- singleton median/p95 latency, total wall time, throughput, peak memory and API cost;
- training history, adapter integrity and post-adapter replay results.

The LoRA result is the three-seed mean +/- sample standard deviation. No seed is silently dropped.
Primary adaptation contrast:

```text
mean(LoRA seed Macro-F1) - EXP-047 frozen-Qwen singleton Macro-F1
```

- delta `>= +0.005`: material LoRA improvement;
- absolute delta `< 0.005`: practical tie;
- delta `<= -0.005`: material degradation.

For each seed, use 2,000 `group_id` bootstrap resamples to compare its predictions with the matched
singleton reference. Report intervals and effect sizes without turning one deterministic reference
run into a repeated-training significance claim.

Secondary comparisons are descriptive:

- EXP-042 M2 target-only: Macro-F1 `0.594925 +/- 0.012919`;
- EXP-043 A batch-8 target-only reasoning-off: Macro-F1 `0.308684`;
- EXP-043 C batch-8 target-only reasoning-on: Macro-F1 `0.333818`.

A/C retain their original batch-8 caveat and cannot replace the EXP-047 singleton reference.
Accuracy or parser-validity gains alone do not establish that LoRA improved emotion recognition.
EXP-047 does not choose a test checkpoint or open the test gate; that decision requires a later
`TEST-READY` protocol and explicit user approval.

## Resource Budget and Backend Boundary

The registered execution backend is local Apple Metal with MLX BF16 because it is the only exact
model/template/adapter/runtime stack already verified by EXP-041, EXP-044 and EXP-046.

- Training: maximum 8 active hours per seed, 24 hours total.
- Post-adapter replay: maximum 40 minutes per seed, 2 hours total.
- Full-dev singleton inference: maximum 22 hours per pass, 88 hours total for four passes.
- Aggregation and independent verification: maximum 2 active hours.
- Total active model/verification budget: 116 hours.
- Peak MLX memory: 13 GB.
- Formal training attempts: exactly one per seed; no automatic retries.
- Formal dev generations: 5,088; replay generations: 96.
- API/network access and API cost: forbidden, USD 0.
- Calendar deadline: N/A until the user authorizes execution and a start time is recorded.

The 116-hour ceiling is conservative. EXP-044 projected 2 epochs x 3 seeds at 21.72 hours with a
1.25 multiplier. EXP-046 singleton timing projects four full-dev passes at 85.02 hours and three
post-adapter replays at 1.60 hours with the same multiplier.

A rented CUDA/PyTorch/PEFT backend is **not** an interchangeable execution route under this
registration. Migration requires, before any formal seed, a dated protocol correction, explicit
approval to transfer private data, and a new train-only Minor that verifies tokenization, chat
template, loss mask, LoRA placement/count, BF16 model revision, checkpoint reload and singleton
runtime replay. All formal seeds and the matched reference must then use the same backend.

## Planned Artifacts and Thesis Destination

Public, text-free artifacts:

- protocol, machine-readable config, frozen source hashes and run metadata;
- per-seed training history, adapter integrity summary and replay aggregates;
- aggregate/slice/per-class metrics, confusion matrices, bootstrap effects and resource report;
- independent verification and a final report that preserves failed or invalid outputs.

Private/gitignored artifacts:

- rendered train messages, raw source text and prompts;
- adapters, optimizer/recovery checkpoints and raw generated reasoning;
- row-level gold/prediction records keyed by private IDs.

Planned thesis mapping:

- Results: Stage 5 table comparing matched frozen Qwen, three-seed LoRA and M2 encoder.
- Methods: label-only generative LoRA, singleton runtime contract and resource accounting.
- Discussion: task adaptation versus encoder gap, format/latency tradeoffs and rationale limits.
- Limitations: imbalanced natural training distribution, one 4B post-trained model, local backend
  dependence and no mechanism claim.

## Pass Signal

EXP-047 is `Verified` only if:

1. all three two-epoch adapters pass integrity and post-adapter replay gates without dev/test
   access during training;
2. the matched reference and all three adapters each contain exactly 1,272 unique, ordered dev
   predictions under singleton reasoning-on inference;
3. invalid outputs remain in the denominator and every required metric, slice, comparison and
   resource field is present;
4. an independent verifier reconstructs data/model/config hashes, adapter gates, parser outputs,
   metrics, bootstrap effects and privacy/split boundaries with zero mismatch;
5. `run.json` records validation access only after the train-only gates, no test access, and no
   budget violation.

Registration alone is not evidence and does not authorize implementation, training, validation,
migration or test access.
