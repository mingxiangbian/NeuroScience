# EXP-053 M3 Seed-44 Formal Authorization

- Experiment ID: `EXP-053`
- RQ: `RQ-S1`
- Stage: `seed-44-train-validation`
- Authorized: 2026-08-15
- Basis: the user explicitly authorized EXP-053 seed 44 after reviewing the independently verified seeds 42 and 43

## Authorized Scope

This authorization covers exactly one fresh seed-44 M3 Classification LoRA run. It may:

- read the frozen `DATA-SO-TASK-V1` train and validation splits;
- initialize the Qwen head exactly as matched EXP-052 seed 44;
- run a zero-update preflight that loads the same data and model but writes no performance result;
- train the frozen two-epoch, 6,720-step Classification LoRA configuration;
- evaluate both epoch checkpoints on validation at fixed threshold `0.5`;
- select the checkpoint and one shared six-label threshold using the frozen validation rules;
- report full validation metrics, component bootstrap intervals, and paired M3-minus-M2 seed-44 evidence;
- save private row-level predictions, batch order, adapter, and head checkpoints.

It may not:

- read the test split or any test-derived artifact;
- change the data, prompt, pooling, label order, model revision, precision, loss, optimizer,
  learning rates, LoRA insertion points, rank, scale, dropout, epochs, or batch order rule;
- use EXP-052 hidden-state caches as M3 inputs;
- modify or overwrite the append-only seed-42 implementation, run, failed verification, or corrected verification;
- authorize the M3 three-seed aggregate, EXP-054, context, router, error-analysis sampling, or TEST-READY.

## Frozen Prerequisites

1. EXP-053 seed 42 remains `Completed` and its verification attempt 2 remains `Passed` at
   `148/148`, with test unaccessed.
2. EXP-053 seed 43 remains `Completed` and independently verified at `143/143`, with test
   unaccessed.
3. Matched EXP-052 seed 44 remains `Completed` and independently verified at `104/104`, with
   head initialization SHA-256 `e7edad8565112d37829fee405684637afc91c9a004a6cb95c572ce2c513b17bf`.
4. The EXP-052 three-seed aggregate and EXP-053 resource preflight remain independently verified.

## Frozen Success Gates

1. The zero-update seed-44 preflight accesses only train and validation, performs no optimizer
   update, matches the M2 seed-44 head hash, and confirms exact-zero initial LoRA delta.
2. Exactly 112 insertion points and 7,340,032 LoRA parameters exist; only these tensors and the
   `Linear(2560,6)` head are trainable.
3. Exactly 6,720 finite optimizer updates complete using the continuous `PCG64(44)` batch order.
4. Both epoch adapter/head checkpoints are saved; the selected checkpoint follows the frozen
   fixed-0.5 Macro-F1 rule and reloads within maximum absolute probability error `1e-5`.
5. Validation outputs contain 720 rows in frozen order and all registered metrics are recomputed.
6. The paired comparison uses only matched EXP-052 seed-44 predictions.
7. Peak MLX memory remains at most 13 GB and total wall time remains at most 8 hours.
8. An independent verifier replays the selected checkpoint and confirms test was not accessed.

This produces the third independent M3 seed only after seed 44 passes verification. It does not by
itself freeze the three-seed M3 aggregate or authorize EXP-054, error analysis, or test.
