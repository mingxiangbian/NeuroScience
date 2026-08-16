# EXP-053 M3 Classification LoRA Resource Preflight

## Status

`Passed` as a train-only resource and checkpoint-integrity preflight. Independent
verification is still required. This run does not report classification performance
and does not authorize formal training.

## Gates

- Optimizer steps: `32` on `32` private train rows
- LoRA insertions / parameters: `112` / `7340032`
- Total trainable parameters: `7355398`
- Zero-step LoRA logit difference: `0.00000000`
- Nonzero `lora_b` tensors after training: `112`
- Checkpoint reload max absolute logit difference: `0`
- Training / checkpoint-replay phase peak MLX memory: `8.674` / `8.376 GB`
- Resource-gate peak (maximum sequential phase peak): `8.674 GB`
- Projected one-seed time with 1.5x safety: `4.436 h`
- Projected three-seed sequential time with 1.5x safety: `13.308 h`
- Validation accessed: no
- Test accessed: no

## Boundary

Passing means the frozen local MLX M3 implementation fits the registered resource
budget and its private checkpoints can be replayed. It is not evidence that M3
improves M2 or M1. Formal seed 42, seeds 43/44, EXP-054 and test remain sealed.
