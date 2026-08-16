# EXP-053 M3 Seed-43 Formal Authorization

- Experiment ID: `EXP-053`
- RQ: `RQ-S1`
- Stage: `seed-43-train-validation`
- Authorized: 2026-08-14
- Basis: the user explicitly authorized execution of the next EXP-053 seed gate after reviewing the verified seed-42 result

## Authorized Scope

This authorization covers exactly one fresh seed-43 M3 Classification LoRA run. It may:

- read the frozen `DATA-SO-TASK-V1` train and validation splits;
- initialize the Qwen head exactly as matched EXP-052 seed 43;
- run a zero-update preflight that loads the same data and model but writes no performance result;
- train the frozen two-epoch, 6,720-step Classification LoRA configuration;
- evaluate both epoch checkpoints on validation at fixed threshold `0.5`;
- select the checkpoint and one shared six-label threshold using the frozen validation rules;
- report full validation metrics, component bootstrap intervals, and paired M3-minus-M2 seed-43 evidence;
- save private row-level predictions, batch order, adapter, and head checkpoints.

It may not:

- read the test split or any test-derived artifact;
- change the data, prompt, pooling, label order, model revision, precision, loss, optimizer,
  learning rates, LoRA insertion points, rank, scale, dropout, epochs, or batch order rule;
- use EXP-052 hidden-state caches as M3 inputs;
- modify or overwrite the append-only seed-42 implementation, run, failed verification, or corrected verification;
- authorize seed 44, EXP-054, context, router, error-analysis sampling, or TEST-READY.

## Frozen Prerequisites

1. EXP-053 seed 42 remains `Completed` and its verification attempt 2 remains `Passed` at
   `148/148`, with test unaccessed.
2. Matched EXP-052 seed 43 remains `Completed` and independently verified at `99/99`, with
   head initialization SHA-256 `079d853fc8644442262d7ff23d99a2822e5b5b9c3fa24e09c55a4ae8ddb802bc`.
3. The EXP-052 three-seed aggregate and EXP-053 resource preflight remain independently verified.

## Frozen Success Gates

1. The zero-update seed-43 preflight accesses only train and validation, performs no optimizer
   update, matches the M2 seed-43 head hash, and confirms exact-zero initial LoRA delta.
2. Exactly 112 insertion points and 7,340,032 LoRA parameters exist; only these tensors and the
   `Linear(2560,6)` head are trainable.
3. Exactly 6,720 finite optimizer updates complete using the continuous `PCG64(43)` batch order.
4. Both epoch adapter/head checkpoints are saved; the selected checkpoint follows the frozen
   fixed-0.5 Macro-F1 rule and reloads within maximum absolute probability error `1e-5`.
5. Validation outputs contain 720 rows in frozen order and all registered metrics are recomputed.
6. The paired comparison uses only matched EXP-052 seed-43 predictions.
7. Peak MLX memory remains at most 13 GB and total wall time remains at most 8 hours.
8. An independent verifier replays the selected checkpoint and confirms test was not accessed.

This produces two independent M3 seeds only after seed 43 passes verification. It cannot establish
the three-seed M3 family result or authorize test. Seed 44 requires a separate user decision.
