# EXP-053 M3 Seed-42 Formal Authorization

- Experiment ID: `EXP-053`
- RQ: `RQ-S1`
- Stage: `seed-42-train-validation`
- Authorized: 2026-08-14
- Basis: the user explicitly requested the next gate after the verified EXP-053 resource preflight

## Authorized Scope

This authorization covers exactly one fresh seed-42 M3 Classification LoRA run. It may:

- read the frozen `DATA-SO-TASK-V1` train and validation splits;
- initialize the Qwen head exactly as matched EXP-052 seed 42;
- train the frozen two-epoch, 6,720-step Classification LoRA configuration;
- evaluate both epoch checkpoints on validation at fixed threshold `0.5`;
- select the checkpoint and one shared six-label threshold using the frozen validation rules;
- report full validation metrics, component bootstrap intervals, and paired M3-minus-M2 evidence;
- save private row-level predictions, batch order, adapter, and head checkpoints.

It may not:

- read the test split or any test-derived artifact;
- change the data, prompt, pooling, label order, model revision, precision, loss, optimizer,
  learning rates, LoRA insertion points, rank, scale, dropout, epochs, or batch order rule;
- use EXP-052 hidden-state caches as M3 inputs;
- select seed 42 after seeing seeds 43/44, or authorize either later seed;
- authorize EXP-054, context, router, error-analysis sampling, or TEST-READY.

## Frozen Success Gates

1. The verified resource preflight and its 102-check independent verification remain unchanged.
2. The seed-42 head initialization hash equals matched EXP-052 seed 42.
3. Initial LoRA delta is exactly zero; 112 insertion points and 7,340,032 LoRA parameters exist.
4. Only the LoRA tensors and `Linear(2560,6)` head are trainable.
5. Exactly 6,720 finite optimizer updates complete using the frozen continuous PCG64 batch order.
6. Both epoch adapter/head checkpoints are saved; the selected checkpoint follows the frozen
   fixed-0.5 Macro-F1 rule and reloads within maximum absolute probability error `1e-5`.
7. Validation outputs contain 720 rows in frozen order and all registered metrics are recomputed.
8. Peak MLX memory remains at most 13 GB and total wall time remains at most 8 hours.
9. An independent verifier replays the selected checkpoint and confirms test was not accessed.

This is a single-seed integrity and performance result. It cannot establish the M3 family result
or authorize test. Seeds 43/44 require separate decisions after this run is verified.

## Pre-run Implementation Correction

The first `--preflight-only` invocation on 2026-08-14 stopped before split or model access because
the runner expected obsolete `checks_passed` and `checks_total` fields in the frozen resource
verification record. The actual verified schema uses `check_count` plus the `checks` array. No
formal run directory or result was created. The gate was corrected to require `status=Passed`, the
registered `check_count`, a matching `checks` length, and an empty `failed_checks` list; a regression
test was added before regenerating the frozen implementation hashes.
