# EXP-053 M3 Resource Preflight Attempt-2 Amendment

- Experiment ID: `EXP-053`
- Stage: `train-only-resource-preflight`
- Registered: 2026-08-14
- Parent attempt: `runs/exp-053-m3-classification-lora-resource-preflight-seed-42/`
- Scope: implementation-only resource-accounting correction

## Observed Failure

Attempt 1 completed all 32 train-only optimizer steps with finite losses. Its training
history reached a maximum recorded MLX peak of `8.67435875 GB`, below the frozen
`13 GB` limit. The time gates passed, but the process-wide memory gate failed after
checkpoint replay loaded a second Qwen instance while Python references from the
training phase still retained the first model, optimizers, gradients, and tensor
lists. Validation and test were not accessed, and no performance metric was computed.

## Authorized Correction

Attempt 2 must preserve the same frozen data, sample-selection rule, seed, model,
precision, head, LoRA insertion contract, optimizers, 32 update steps, checkpoint
replay tolerance, `13 GB` memory ceiling, and `1.5x` time projection. It may only:

1. detach the reference logits needed for replay;
2. explicitly release all training-model, optimizer, gradient, and tensor references;
3. clear the MLX cache and reset peak accounting before loading the replay model;
4. report the training-phase and replay-phase peaks separately;
5. apply the unchanged `13 GB` gate to the maximum of those two sequential phase peaks.

The failed attempt remains append-only. Attempt 2 must use new public and private
directories. This correction does not authorize validation, test, performance
evaluation, formal EXP-053 training, seeds 43/44, or EXP-054.
