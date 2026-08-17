# EXP-058 OOF Consumer Dry-Run

- Experiment ID: `EXP-058`
- Tier: Minor implementation gate under the registered Major experiment
- RQ: `RQ-S3`
- Stage: `fold-0-m1-m3-two-step-dry-run`
- Registered: 2026-08-16
- Status: Authorized by the user's request to proceed to the next gate

## Purpose

Verify that dedicated M1 and M3 OOF consumers can use the frozen shared fold manifest
without validation/test access, train only on the four in-fold partitions, and emit raw
six-label logits only for held-out rows. This run checks implementation integrity; it
does not estimate performance or authorize five-fold OOF production.

## Pre-allocation Prerequisite Correction

The first static invocation on 2026-08-16 stopped before output allocation because the
configuration referenced the retained EXP-053 seed-42 attempt-1 verifier. That verifier
failed only its obsolete resource-field schema check and is not valid positive evidence.
The dry-run prerequisite is corrected to the independently replayed
`verification-attempt-2.json`, which passed all 148 checks. The consumer must verify the
exact `148/148` counts and an empty failed-check list in addition to `status: Passed`.
No EXP-058 run directory or model execution existed before this correction.

## Authorized Scope

The run may access only the frozen `DATA-SO-TASK-V1` train file and the verified public
EXP-058 fold manifest. It is limited to fold `0`, model seed `42`, and:

- M1: two optimizer steps, each with the frozen batch size `16`, followed by forward
  passes for the first two held-out rows in canonical source order;
- M3: two batch-size-one optimizer steps, followed by forward passes for the same two
  held-out rows;
- private storage of row identities, losses, gradients, state hashes, and raw logits;
- public storage of aggregate integrity results, hashes, timing, and resource use.

The run may not access validation, test, existing validation/test predictions, full-train
checkpoints, adapters, heads, or optimizer states. It may not compute probabilities,
thresholds, predictions, metrics, calibration, oracle gain, abstention, or router targets.
It does not authorize any third optimizer step or another fold.

## Canonical Fold Consumption

The consumer must first load the 3,360 train rows in their frozen source-file order and
then filter by the public fold assignment:

- held-out rows: `fold_id == 0`, preserving source order;
- training rows: `fold_id != 0`, preserving source order.

The resulting counts must be 672 held-out rows and 2,688 training rows, with no sample or
duplicate-component overlap. M1 and M3 must verify the same manifest SHA-256 before and
after their stage. This order rule is frozen because seeded permutations operate on row
positions and are not defined without a canonical pre-permutation order.

## M1 Scheduler Correction

EXP-051 seed 42 selected epoch 4 from a five-epoch linear-decay schedule. Replacing the
schedule horizon with four epochs would change the training trajectory and would produce
`67.2` warmup steps for a fold, which violates the registered exact-integer warmup rule.

For every future M1 OOF fold, the corrected frozen interpretation is therefore:

- steps per epoch: `ceil(2688 / 16) = 168`;
- planned scheduler horizon: `168 * 5 = 840` steps;
- warmup: `840 * 0.10 = 84` steps;
- selected stopping point: `168 * 4 = 672` executed steps;
- dry-run execution in this gate: only the first two of those 672 steps.

This preserves the original five-epoch schedule shape while stopping at the selected
epoch. The held-out fold cannot choose the stopping point or any other hyperparameter.

## Frozen Model Conditions

M1 loads the pinned `FacebookAI/roberta-base` base snapshot and creates a fresh six-logit
classification head after seed 42 is set. All model parameters are trainable, matching
EXP-051. It must not load an EXP-051 checkpoint.

M3 loads the pinned unquantized BF16 `Qwen/Qwen3-4B` base. It creates a fresh seed-42
`Linear(2560, 6)` head and fresh seed-plus-100000 LoRA tensors. The initial LoRA delta
must be exactly zero; there must be 112 insertion points and exactly 7,355,398 trainable
parameters. Only the head and LoRA tensors may be trainable, and the frozen-base sentinel
must be identical before and after the two updates.

## Acceptance Gates

The dry-run passes only if:

1. the fold manifest remains the independently verified 5-fold artifact and its hash is
   unchanged before and after both model stages;
2. both consumers use exactly 2,688 training and 672 held-out rows in canonical order;
3. the M1 scheduler records horizon 840, warmup 84, and selected stop 672;
4. M1 completes exactly two finite-loss updates with finite gradient norms and a changed
   classifier hash;
5. M3 has the expected head/LoRA initialization hashes, exact zero initial LoRA delta,
   112 insertion points, the frozen trainable whitelist, two finite-loss updates, changed
   head and LoRA hashes, and an unchanged base sentinel;
6. each model emits a finite `2 x 6` held-out raw-logit matrix without using held-out
   labels in its forward path;
7. public artifacts contain no text, row identities, gold labels, logits, probabilities,
   or predictions; private evidence is mode `0600` and Git-ignored;
8. an independent verifier that imports neither model runner nor model libraries passes;
9. M1 peak process memory stays at or below 8 GB and M3 peak MLX memory stays at or below
   13 GB;
10. validation and test remain unopened.

Passing authorizes only implementation review before a separate full-OOF decision. It is
not evidence that either model is accurate, calibrated, selective, or useful for routing.
