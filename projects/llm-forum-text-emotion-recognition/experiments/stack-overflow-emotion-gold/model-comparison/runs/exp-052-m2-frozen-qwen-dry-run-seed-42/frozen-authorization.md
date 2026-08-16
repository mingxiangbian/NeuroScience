# EXP-052 Seed 42 Authorization

- Experiment: `EXP-052` / M2 Frozen Qwen + Linear Head
- Authorized stage: `seed-42 train + validation integrity gate`
- Authorized at: 2026-08-14
- Basis: the user explicitly authorized the next experiment after the verified
  three-seed EXP-051 validation result.

## Scope

This authorization permits exactly:

1. a train-only dry-run that extracts a deterministic feature sample, verifies
   the frozen Qwen/prompt/pooling/head contract, and projects extraction cost;
2. one formal `seed=42` run over the frozen train and validation splits after
   the dry-run passes independent verification;
3. private float32 train/validation feature caches, matched batch-order records,
   head checkpoints, and row-level validation probabilities;
4. public aggregate validation metrics and an independent verification report.

The Qwen3-4B backbone remains in evaluation mode with no trainable parameters.
Only the bias-enabled `Linear(2560, 6)` head may receive optimizer updates. The
head is initialized with MLX seed 42. Training uses two epochs, batch size 1,
AdamW at `1e-4`, weight decay `0.01`, unweighted BCE, no scheduler, and a
continuous NumPy PCG64 permutation stream initialized with seed 42. These head
initialization and batch-order artifacts are retained for the later matched M3
comparison.

## Gates

Formal execution requires all of the following:

- the verified EXP-050 run and its 77/77 independent checks remain unchanged;
- the train-only dry-run passes its independent verifier;
- projected full feature extraction, including a 1.5 safety factor, is at most
  four hours;
- peak MLX memory is at most 13 GB;
- model, prompt, tokenizer, data, protocol, runner, verifier, and test hashes
  match the frozen run contract;
- no validation performance is computed during the dry-run.

## Explicit Non-Authorization

This amendment does not authorize Stack Overflow test access, TEST-READY
status, seeds 43 or 44, EXP-053/M3, EXP-054/M4, context recovery, routing, or a
paper-level conclusion from one seed. A feature cache produced here may not be
used by another seed or experiment until that later run receives its own
authorization.
