# EXP-069 Verification Attempt 2

Date: 2026-08-27

## 1. Purpose

This is an append-only, model-free recovery for EXP-069 attempt 4. The attempt-4
run, private smoke manifest, workers and failed `verification.json` remain
immutable. No model worker or assemble stage may be rerun.

Attempt 4 failed final verification because one name covered two different
quantities:

- runner `manual_logit`: saved MLX manual-head logits versus saved MLX
  standard-wrapper logits;
- independent head replay: saved float32 HF multiplied by the saved float32
  head in NumPy versus saved MLX manual-head logits.

The first quantity is `0.0`. The second is
`7.62939453125e-06`. Both satisfy the frozen `1e-5` numeric gate. The failure
occurred when the verifier merged them and then required the merged value to
equal the runner aggregate within `1e-12`.

## 2. Recovery rule

Verification attempt 2 keeps the original tolerance and separates the metrics:

- `runner_manual_vs_standard_logit_max_abs` must equal worker, smoke-manifest
  and public-run `manual_logit` aggregates within `1e-12`;
- `independent_saved_hf_head_vs_manual_logit_max_abs` is independently checked
  against the frozen `manual_logit_atol=1e-5`.

The other four aggregates retain the frozen verifier semantics and exact
aggregate comparison. The recovery does not substitute the independent replay
value into the run or smoke manifest.

## 3. Frozen inputs

The recovery config SHA-binds:

- attempt-4 config, run claim, completed run and failed verification;
- attempt-4 private smoke manifest;
- the frozen attempt-1 independent verifier;
- the attempt-4 wrapper verifier and all attempt-4 lineage transitively bound
  by its config.

The source public inventory must contain exactly the four pre-verification
artifacts plus the preserved failed `verification.json`. The private inventory
must contain exactly 34 files under a `0700` root and three real, non-symlink
`0700` seed directories. Every private file remains `0600`.

## 4. Execution boundary

Allowed:

- read the immutable attempt-4 snapshot;
- load and text-transform the exact frozen model-free verifier;
- recompute all 22 original smoke-verification checks with the metric split;
- write the recovery verification and completion in a fresh public root.

Forbidden:

- runner or model import;
- model loading or forward execution;
- worker or assemble rerun;
- train-text, label-value, validation, test or gold access beyond the frozen
  verifier's existing attestations;
- performance-metric computation;
- modification, deletion, replacement or copying-back of attempt-4 evidence;
- tolerance changes.

## 5. Outputs and stop rule

Fresh root:

`phase-b-representation/runs/exp-069-representation-extraction-preflight/attempt-5-verification-recovery`

Success writes exactly:

- `verification.json`
- `preflight-complete.json`

Any failure writes only an append-only failed `verification.json` and stops.
Completion must bind the attempt-4 run, preserved failed verification, recovery
config and passed recovery verification. It marks `exp069_complete=true`, while
also recording that attempt-4 verification remains failed and that no model was
rerun.

Passing this recovery completes only EXP-069's representation-extraction and
checkpoint-parity infrastructure gate. EXP-070 remains separately registered
and unexecuted.
