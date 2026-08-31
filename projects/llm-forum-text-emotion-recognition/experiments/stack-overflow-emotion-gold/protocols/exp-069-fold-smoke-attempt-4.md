# EXP-069 Fold Smoke Continuation, Attempt 4

- Experiment ID: `EXP-069`
- Attempt ID: `attempt-4-fold-smoke`
- Date: `2026-08-27`
- Parent static: attempt 1, independent verifier `14/14 Passed`
- Parent base: attempt 3, independent verifier `23/23 Passed`
- Status: `Fold smoke and assemble authorized`

## 1. Purpose

Attempt 4 completes the remaining EXP-069 gate. It runs seeds 42, 43 and 44 across folds 0..4 in
15 fresh processes, assembles aggregate parity evidence, then invokes a model-free independent
verifier. EXP-070 remains closed until completion.

Attempt 2 and attempt 3 remain immutable. Attempt 4 copies exact static/input/base evidence into a
fresh private/public root so the frozen attempt-1 worker and verifier logic can operate without
writing to older attempts.

## 2. Parent evidence

The config binds exact records for:

- attempt-1 config, static run, static verification and input manifest;
- attempt-3 config, run, verification, base completion, base NPZ and base worker;
- frozen attempt-1 runner and independent verifier sources.

Initialization copies, with bytes and SHA-256 unchanged:

```text
public:  static.json, static-verification.json
private: input-manifest.json, base.npz, base-worker.json
```

Copied private files remain `0600`; the private root is `0700`. The parent roots remain unchanged.

## 3. Authorization

```text
fold_smoke_authorized = true
assemble_authorized = true
model_loading_authorized = true
forward_authorized = true
training_authorized = false
performance_metrics_authorized = false
validation_access = false
test_access = false
```

Each worker accepts one registered `(seed, fold)` pair. The orchestrated order is:

```text
(42,0)..(42,4), (43,0)..(43,4), (44,0)..(44,4)
```

Any worker failure writes a terminal Failed run and stops later workers.

## 4. Frozen worker contract

Each fresh process:

- loads one Qwen base, one fold adapter and one original head;
- checks 112 LoRA insertion points, 224 adapter tensors, rank 8, scale 20 and dropout 0;
- processes only the 5 to 8 smoke rows assigned to that held-out fold;
- writes nine last-token representation points and private logits;
- compares manual HF with standard HF;
- compares manual-head logits with standard-wrapper logits;
- compares standard logits with the frozen held-out logits;
- compares H-1/H7/H15/H19 against the verified base smoke;
- checks the copied base evidence before each worker and adapter/head/heldout identities before and
  after that worker;
- reads historical NPZ members `sample_ids/fold_ids/logits` only.

M2 cache and Qwen identities remain bound by the verified static/base lineage and the final parity
recomputation; fold workers do not reopen the M2 cache or rehash the full Qwen tree.

Numeric gates remain float32, `rtol=0`, `atol=1e-5`.

## 5. Resources

- Fresh model workers: 15
- Concurrent heavy workers: 1
- Per-worker wall ceiling: 20 minutes
- Per-worker MLX peak ceiling: 10 GB
- Training: none
- API cost: USD 0

## 6. Assemble and independent verification

Assemble requires the verified base worker and all 15 completed fold workers. It writes one private
smoke manifest and aggregate-only public `run.json`.

The independent verifier imports no runner or model library. It recomputes M2/base parity,
manual-head logits, held-out-logit parity, pre-LoRA equivalence, token/fold/seed coverage, resource
aggregates, modes, hashes, access attestations and public privacy.

Attempt-3 base evidence adds one access field, `m3_artifacts_accessed=false`, beyond the original
attempt-1 base-worker schema. The verifier accepts this field only for the copied base worker and
only when its value is exactly `false`; fold-worker and aggregate schemas remain unchanged.

Passed verification writes `verification.json` and `preflight-complete.json` with
`exp069_complete=true`.

## 7. Stop and claim boundary

Stop on parent/config/source drift, copied-evidence mismatch, output presence, worker gap or
duplication, checkpoint drift, NaN/inf, tolerance failure, OOM, timeout, forbidden member access,
validation/test access, mode failure or public leakage.

The maximum claim is:

> A verified 32-row, three-seed, five-fold representation-extraction and checkpoint-parity
> preflight for the frozen Phase B stack.

EXP-069 supports no classification performance, representation effect, functional dependency,
independent-data, deployment or emotion-mechanism claim.
