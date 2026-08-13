# EXP-044 Local Qwen3-4B LoRA Cost Preflight

Status: `Verified`（Minor；13/13 independent checks passed）

## Decision Answered

RQ-F1 / Stage 5 resource gate：Qwen3-4B BF16 的精确生成式 LoRA 训练形状能否在本机
16 GB 统一内存中稳定运行，完整三 seed 训练的量级是多少？

## Frozen Boundary

- 只读取 `DATA-WEIBO-TASK-V1` train；validation/test 未访问。
- 200 条样本按 train 标签比例分配，再按各标签内 token 长度分位点系统抽样。
- target-only、严格单标签 JSON、label-only SFT；无人工或合成 rationale。
- Qwen3 chat template 的监督区为自动加入的空 `<think>` wrapper、JSON 标签和结束 token；
  `mask_prompt=true`，完整 prompt 不参与 loss。
- Qwen3-4B BF16，blocks 20-35，112 个 LoRA 插入点，rank 8、scale 20、dropout 0，
  AdamW、learning rate `1e-5`、batch 1、gradient checkpointing、seed 42。

## Observed Result

| Item | Value |
| --- | ---: |
| Steps | 200 |
| Training wall time | 355.254 s |
| Steady median throughput | 0.575 step/s |
| Steady p25-p75 throughput | 0.568-0.58275 step/s |
| Peak memory | 8.679 GB |
| Trainable parameters | 7,340,032 |
| Adapter tensors | 224 |
| Nonzero `lora_b` tensors | 112/112 |
| Adapter reload | finite logits |
| API cost | USD 0 |

No OOM, NaN, non-finite adapter tensor, split violation or public row-level leakage was found.

## Training-Only Projection

The projection uses the median post-warmup throughput and a `1.25x` safety multiplier.

| Epochs | One seed, raw | One seed, with safety | Three seeds sequential, with safety |
| ---: | ---: | ---: | ---: |
| 2 | 5.79 h | 7.24 h | 21.72 h |
| 3 | 8.69 h | 10.86 h | 32.58 h |

These estimates exclude validation generation, checkpoint selection, repeated stability checks and
error analysis. They therefore establish technical local feasibility, not that local execution is the
best practical choice.

## Interpretation Boundary

This run contains no classification metric and cannot support a model-quality claim. The empty
`<think>` wrapper is a chat-template artifact, not a supervised reasoning chain. The Stage 5 Major
protocol must still freeze the reasoning policy, batch-equivalence gate, epochs/checkpoint rule,
three seeds, comparisons against EXP-043 and EXP-042 M2, and the actual local-versus-rented-GPU
resource decision.

## Evidence and Thesis Destination

- Evidence ID: `EVID-037`
- RQ: `RQ-F1`
- Thesis use: methods/resource-budget note and reproducibility appendix; not a result-table model row.
- Machine-readable evidence: `run.json`, `history.csv`, `sample_summary.json`,
  `cost_projection.json`, `verification.json`.
