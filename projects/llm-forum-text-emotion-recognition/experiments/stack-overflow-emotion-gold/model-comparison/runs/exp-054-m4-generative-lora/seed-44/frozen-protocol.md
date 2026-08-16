# EXP-054: M4 Qwen Generative LoRA

- Experiment ID: `EXP-054`
- Tier: Major
- RQ: `RQ-S1`
- Parent: `EXP-053`, execution gated by `EXP-050`
- Registered: 2026-08-13
- Status: `Formal train + validation execution authorized on 2026-08-15; test remains sealed`

## Question

在同一 Qwen、prompt prefix、训练行、seed 与 LoRA 容量下，直接生成多标签 JSON 的端到端
结果和系统成本如何？M3-M4 同时改变 head、loss、监督 token 与 decode，只允许称为
classification formulation 和 generative formulation 的端到端比较。

## Frozen Training And Output

- 继承 M2/M3 的 Qwen revision、MLX BF16、chat template、thinking=false、max length 384、
  right-truncate target 且保留完整 suffix，以及三 seed `42/43/44`。
- 使用与 M3 完全相同的 112 个 LoRA insertion、rank 8、scale 20、dropout 0、AdamW `1e-5`、
  weight decay `0.01`、2 epochs、batch 1、6,720 optimizer steps 和 gradient checkpointing。
- 只对 assistant target 与结束 token 计算 next-token cross entropy，system/user prompt 和 chat
  wrapper 均 mask；没有 rationale 或自由 CoT gold。
- target 必须是 canonical compact JSON，例如 `{"emotions":["love","anger"]}`；列表严格按
  `love, joy, surprise, anger, sadness, fear` 排序；全零为 `{"emotions":[]}`。
- validation 为 greedy singleton：temperature 0、max new tokens 48、无 retry/repair。严格 parser
  只接受一个 key、已知且不重复的 lowercase label、canonical 顺序和无额外空白的 compact JSON。
  invalid 输出保留在 denominator，并映射为全零预测；另报 invalid reason。

## Evaluation, Stability, Budget

报告共享多标签指标、格式有效率、预测 label cardinality、空预测率、generated tokens、median/p95
latency、throughput、wall time 和峰值内存。为估计生成行为稳定性，在冻结 validation 选择完成后，
对一个预先 hash 选出的 60-row validation subset 做两次 fresh-process greedy replay；不以 replay
结果选 checkpoint 或修 prompt。

正式 validation inference 上限 12 小时/seed，训练上限 8 小时/seed，总上限 60 小时，峰值
13 GB，API cost 0。parser 或 prompt 改变、missing/extra LoRA targets、supervision mask 不准确、
自动重试或丢弃 invalid、任一 seed 缺失均判失败。

正式 test 必须与 M1-M3 一起进入统一 TEST-READY，不在本协议中授权。

论文去向：Results 的 M3/M4 端到端结果、格式与成本表；Discussion 的生成式分类边界。

## 2026-08-15 Authorization And Frozen Clarifications

The user explicitly authorized formal execution of `EXP-054`. Authorization covers all three
registered seeds (`42/43/44`) on train and validation, including the two fresh-process 60-row
validation replays per seed. Test remains sealed.

Before observing any formal EXP-054 result, the following underspecified implementation details are
frozen:

- Checkpoint selection uses strict-parser six-label validation Macro-F1. The highest value wins;
  epochs within an absolute `0.005` of the maximum are treated as practically tied and the earlier
  epoch is selected.
- The 60-row replay subset is the first 60 validation rows after sorting by
  `SHA256("EXP-054-replay-subset-v1|" + sample_id)`. It is identical for all seeds.
- The primary matched comparison is each M4 seed minus the already frozen shared-threshold output
  of the same-seed EXP-053 M3 run, using duplicate-component bootstrap. This is an end-to-end
  formulation comparison, not an isolated causal estimate of head or loss effects.
- Replay output cannot change checkpoint selection, prompt, parser, training, or reported formal
  validation predictions. Replay disagreements are retained and reported as stability evidence.
- Generated-token count excludes the prompt and counts decoded continuation tokens before EOS;
  latency is singleton wall time around `mlx_lm.generate`.

## 2026-08-15 Preflight Correction

The first EXP-054-specific preflight attempt rendered all 3,360 train sequences and completed the
two optimizer updates, but failed with a Metal out-of-memory error while loading the adapter replay
model. The first model remained referenced by an initialization container after its local aliases
were deleted, so the process temporarily held two 4B models. The failed public/private directories
are retained as `exp-054-m4-generative-lora-preflight-attempt-1`; validation and test were not
accessed.

Attempt 2 releases the complete first initialization container before loading a fresh replay model
and writes to new append-only directories. This correction changes only object lifetime and output
paths; it does not change data, seed, target serialization, loss mask, LoRA, generation, parser,
selection, metric, or budget rules.
