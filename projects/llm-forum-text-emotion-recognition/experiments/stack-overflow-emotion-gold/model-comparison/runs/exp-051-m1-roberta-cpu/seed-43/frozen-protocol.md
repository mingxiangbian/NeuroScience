# EXP-051: M1 RoBERTa 六标签基线

- Experiment ID: `EXP-051`
- Tier: Major
- RQ: `RQ-S1`
- Parent: `DATA-SO-TASK-V1`, execution gated by `EXP-050`
- Registered: 2026-08-13
- Status: `Seed 42 execution authorized; seeds 43/44 and test not authorized`

## Question And Hypothesis

在冻结的 Stack Overflow C0 六标签任务上，标准全参数 RoBERTa-base 能建立怎样的强监督
encoder 基线？预期它在小规模监督分类上是强基线；若 LLM 后续不超过它，仍能界定 LLM 的
成本与适用边界。

## Frozen Configuration

- Data: train `3,360`、validation `720`；test 不读。标签顺序固定为
  `love, joy, surprise, anger, sadness, fear`。
- Model: `FacebookAI/roberta-base` revision
  `e2da8e2f811d1448a5b465c236feacd80ffbac7b`；本地 manifest SHA-256
  `b6e508ca9783b9e79e3cfc445f3abc7d2792ac5cfa6f44a9b3cf5d5607cd30b6`。
- Input: 原始 target text，right truncation，max length 256；现有 train 最大 222 tokens，故
  冻结来源下不预期截断。head 为 RoBERTa classification head 的六个独立 logits。
- Loss: unweighted `BCEWithLogitsLoss`；不做 label smoothing、class weighting 或 resampling。
- Seeds `42/43/44`；5 epochs；batch 16；AdamW `2e-5`；weight decay `0.01`；10% warmup
  后 linear decay；float32；全模型和 head 可训练。

## Selection And Evaluation

每 epoch 完整评估 validation。先按固定阈值 0.5 的六标签 Macro-F1 选择 checkpoint；绝对差
小于 0.005 时选更早 checkpoint。仅在选定 checkpoint 上，从冻结 grid 选择一个全标签共享
阈值；不得逐标签调阈值，阈值不得反向改变 checkpoint。

逐 seed 报告固定阈值与共享阈值下的 subset accuracy、macro precision/recall/F1、Micro-F1、
Weighted-F1、Hamming loss、逐类指标和排除 surprise 的五标签敏感性；主结论使用三 seed
mean +/- sample std。正式 test 只在后续统一 TEST-READY 协议和用户授权后进行。

## Artifacts, Budget, Stop

私有保存 checkpoint、row-level validation gold/probabilities/predictions；公开保存 history、聚合
指标、环境、命令、哈希、耗时和峰值内存。三 seed 总训练预算 6 小时；每 seed 一次正式运行。
EXP-050 未通过、输入哈希变化、non-finite loss、任一 seed 缺失或 validation 被用于改标签规则
时，保持 Failed/Blocked，不形成主表结果。

论文去向：Methods 的 encoder baseline 与 Results 的 M1-M4 主表。

## Implementation Clarification And Staged Authorization

The following operational details were frozen on 2026-08-13 before EXP-051
read validation or produced a performance result. They clarify the registered
configuration without changing the research question or model condition:

- dynamic per-batch padding; validation batch size 32; shuffled train batches;
  `drop_last=false`; `num_workers=0`;
- AdamW betas `0.9/0.999`, epsilon `1e-8`, maximum gradient norm `1.0`;
  bias and `LayerNorm.weight` are excluded from weight decay;
- Python, NumPy, PyTorch and MPS use the registered seed; deterministic
  algorithms are requested with warnings retained because MPS is not claimed
  to be bitwise deterministic;
- checkpoint selection is computed after all five epochs: find the maximum
  fixed-0.5 validation Macro-F1, then retain the earliest epoch whose deficit
  from that maximum is strictly below `0.005`;
- bootstrap intervals use 2,000 duplicate-component resamples and the 2.5th and
  97.5th percentiles with NumPy's linear quantile method.

The user's 2026-08-13 instruction authorizes one formal seed-42 train +
validation run as an integrity gate. It does not authorize seeds 43/44 or any
test access. Seed 42 alone is diagnostic evidence and cannot form the planned
three-seed M1 result.

### 2026-08-13 recovery note

The first seed-42 attempt failed during epoch 1 before any complete-epoch
validation metric because the MPS allocator reached the machine's unified-memory
limit. The failed directory is retained. The allocator high-watermark safety
limit must not be disabled.

The registered M1 backend already permits the same PyTorch stack on MPS or CPU.
One CPU recovery attempt is therefore allowed after a 10-step, train-only
optimizer-state and throughput preflight. This changes only the execution
device: batch 16, no gradient accumulation, model initialization, batch order,
optimizer, scheduler, epochs, seed, checkpoint selection and evaluation rules
remain identical. CPU/MPS results must not be presented as bitwise equivalent;
the recovery's exact environment and device are reported.
