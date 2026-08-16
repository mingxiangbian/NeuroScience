# EXP-053 M3 Train-only Resource Preflight Authorization

- Experiment ID: `EXP-053`
- RQ: `RQ-S1`
- Stage: `train-only-resource-preflight`
- Authorized: 2026-08-14
- Basis: the user requested the next registered experiment step after EXP-052 settlement

## Authorized Scope

This authorization covers one seed-42 train-only dry-run for the already registered
M3 Qwen Classification LoRA condition. It may:

- read the frozen `DATA-SO-TASK-V1` train split only;
- tokenize all 3,360 train rows only to build a deterministic length-aware sample;
- run exactly 32 classification-LoRA optimizer steps;
- initialize the seed-42 head and LoRA tensors under the frozen M2/M3 rules;
- save private LoRA/head checkpoints and a private checkpoint-replay reference;
- reload those checkpoints once for an integrity replay;
- estimate one-seed and three-seed runtime with a frozen `1.5x` safety factor.

It may not:

- read validation or test rows, labels, predictions, metrics, or caches;
- compute classification performance, choose a checkpoint, threshold, seed, or model;
- change the Qwen revision, BF16 precision, pooling, label order, loss, LoRA targets,
  rank, scale, dropout, learning rates, optimizer, epochs, or formal step count;
- reuse EXP-052 hidden-state caches, because M3 must update Qwen LoRA parameters;
- authorize a formal EXP-053 seed, EXP-054, error analysis, context, router, or test.

## Frozen Gates

The preflight passes only if all of the following hold:

1. The seed-42 head initialization hash matches the verified EXP-052 seed-42 head.
2. LoRA insertion creates exactly 112 insertion points and 7,340,032 parameters.
3. The initial LoRA delta is exactly zero and the total trainable parameter count is
   7,355,398.
4. The trainable whitelist contains only LoRA `lora_a`/`lora_b` tensors and the
   `Linear(2560,6)` head; deterministic frozen-base sentinels do not change.
5. Both independent AdamW optimizers update, all 32 losses are finite, and all 112
   `lora_b` tensors become nonzero.
6. The private adapter/head checkpoints reload and reproduce the frozen reference
   logits within maximum absolute error `1e-5`.
7. Peak MLX memory is at most 13 GB.
8. The `1.5x` safety projection is at most 8 hours per seed and 24 hours for three
   sequential seeds.
9. An independent verifier passes and confirms that validation/test were not read.

Passing this preflight establishes local execution and resource feasibility only. It
does not authorize formal training and does not provide evidence that M3 improves M2
or M1.
