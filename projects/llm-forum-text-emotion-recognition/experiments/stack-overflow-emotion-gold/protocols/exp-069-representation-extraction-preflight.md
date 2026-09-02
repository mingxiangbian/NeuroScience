# EXP-069: Phase B Representation Extraction Preflight

- Experiment ID: `EXP-069`
- Date: `2026-08-26`
- RQ: `RQ-S4`
- Tier: `Major infrastructure gate`
- Parent decision: `DEC-SO-PHASE-B-REPRESENTATION-V1`
- Status: `Static stage authorized; model smoke closed`
- Data: `DATA-SO-TASK-V1 train only`
- Test access: `false`

## 1. Gate question

EXP-069 checks whether the current local runtime can reproduce the frozen M2 final representation
and all 15 fold-specific M3 OOF logits while exposing the nine registered representation points.
It computes no classification metric and makes no representation-effect claim.

EXP-070 cannot start until EXP-069 reaches `Complete` after independent verification.

## 2. Frozen inputs

EXP-069 binds:

- 3,360-row train source and the verified five-fold component-disjoint manifest;
- Qwen3-4B BF16 revision `1cfa9a7208912126459214e8b04321603b3df60c`;
- the frozen target-only prompt, tokenizer, chat template and 384-token contract;
- the verified seed-42 M2 train feature cache `(3360, 2560)`, float32;
- seeds 42, 43 and 44, each with five M3 OOF adapters, heads and held-out logits;
- MLX-LM `0.31.3` Qwen3 source and the Phase A runtime environment.

Seed-42 provenance comes from EXP-058 fold run/evidence records. Seeds 43/44 also require their
checkpoint-provenance records. EXP-069 does not manufacture a common provenance file.

## 3. Smoke rows

The 32 train ordinals are fixed before execution:

```text
floor(k * 3359 / 31 + 0.5), k = 0..31
```

Exact values:

```text
0, 108, 217, 325, 433, 542, 650, 758,
867, 975, 1084, 1192, 1300, 1409, 1517, 1625,
1734, 1842, 1950, 2059, 2167, 2275, 2384, 2492,
2601, 2709, 2817, 2926, 3034, 3142, 3251, 3359
```

The frozen fold counts are `8/6/5/7/6` for folds `0..4`. Each seed uses the same rows.
Sample and component identifiers remain private.

## 4. Representation semantics

The runner uses the M2 tokenization algorithm from `run_exp052_m2.py`. It performs singleton,
unpadded forward passes and saves only the last input token at:

```text
H-1, H7, H15, H19, H20, H27, H31, H35, HF
```

`H-1` through `H35` are raw residual values. `HF` applies the model final RMSNorm. A manual
block-by-block forward must match the standard `model.model(input_ids)` HF output and must not
change classification logits.

## 5. Numeric gates

All comparisons use float32, `rtol=0`:

| Gate | Maximum absolute error |
| --- | ---: |
| New base HF vs verified M2 train cache | `1e-5` |
| Manual HF vs standard model HF | `1e-5` |
| Manual-head logits vs standard-wrapper logits | `1e-5` |
| Standard M3 logits vs frozen fold held-out logits | `1e-5` |
| Base vs M3 at H-1, H7, H15 and H19 | `1e-5` |

Each array must have the registered shape and finite values. Post-LoRA points may differ.

## 6. Execution sequence

### 6.1 Static stage

The static runner performs no model load or forward. It verifies:

- config, source, package and implementation identities;
- train, fold, base, prompt, cache and 15 checkpoint lineages;
- adapter tensor inventory, head shape and private modes;
- parent verification status;
- output roots are absent;
- test, validation and forbidden-path allowlists.

It writes public `static.json` and private `input-manifest.json`. The independent verifier then
writes `static-verification.json`. Any static failure blocks smoke execution.

### 6.2 Base smoke

One fresh process loads Frozen Qwen and extracts all nine points for the 32 rows. It compares HF
against the M2 cache and the standard model path, then writes private `base.npz` and
`base-worker.json`.

### 6.3 Fold smoke

Fifteen fresh processes run one seed/fold checkpoint each. Every worker:

1. loads the frozen base, adapter and original head;
2. verifies the 112 insertion points, 224 adapter tensors, rank 8, scale 20 and dropout 0;
3. extracts the registered points for that fold's selected rows;
4. checks manual and standard logits;
5. replays the stored held-out logits without reading `gold`;
6. compares H-1/H7/H15/H19 with the base smoke;
7. confirms checkpoint hashes did not change;
8. writes one private NPZ and worker manifest.

A worker failure writes a terminal public failure and stops the attempt. The same output root cannot
be reused.

### 6.4 Assemble and verify

Assemble requires the base worker and all 15 fold workers. It writes private
`smoke-manifest.json` and aggregate-only public `run.json`.

The independent verifier imports no runner or model library. It independently recomputes:

- base HF vs the M2 cache;
- HF vs standard HF;
- saved HF through the original head vs manual and standard logits;
- standard logits vs parent held-out logits;
- H-1/H7/H15/H19 base-to-M3 equality;
- exact row/fold/seed coverage, schemas, hashes, modes and public privacy.

Passed verification creates `verification.json` and `preflight-complete.json`.

## 7. Access contract

Allowed row-level members:

- train container: the label-bearing JSON row is parsed, but label values are neither used nor persisted;
- fold manifest: `sample_id`, `component_id`, `fold_id`; labels remain unread;
- historical heldout NPZ: `sample_ids`, `fold_ids`, `logits` only;
- M2 feature cache: the 32 selected rows only.

Forbidden members include `gold`, predictions, correctness, oracle arrays and validation/test data.
The runner records the member allowlist in each worker manifest.

## 8. Privacy and outputs

Private directories use mode `0700`; private files use `0600` and remain Git ignored. Hidden states,
text, row IDs, component IDs, token IDs and logits never enter public outputs.

Public allowlist:

```text
static.json
static-verification.json
run-claim.json
run.json
verification.json
preflight-complete.json
```

Public files contain status, counts, layer names, aggregate maximum errors, resource records,
private-manifest hashes, access booleans and the claim boundary.

## 9. Resource budget

- Training: none
- API cost: USD 0
- Concurrent heavy MLX processes: 1
- Process scope: one base worker or one seed/fold worker
- Maximum MLX peak per worker: 10 GB
- Maximum wall time per worker: 20 minutes
- Maximum smoke workers: 16 runner workers
- Independent verifier model load: none

The static stage may hash checkpoint files but does not map them into a model.

## 10. Stop rules

Stop on identity/hash/mode/symlink/hardlink/schema drift, missing or extra checkpoint, parent
verification failure, token/rendering drift, output presence, NaN/inf, tolerance failure, OOM,
worker timeout, concurrent heavy workload, validation/test access, forbidden NPZ member access,
private-mode failure or public row-level leakage.

Failed attempts remain append-only. Recovery requires a new attempt ID and a registered correction.

## 11. Claim boundary

The maximum claim is:

> A train-only 32-row extraction and checkpoint-parity preflight for the frozen Phase B stack.

EXP-069 supports no classification-performance, representation-effect, functional-dependency,
independent-data, deployment-efficiency, production or emotion-mechanism claim.

The frozen config authorizes the no-model static runner and static verifier only. Base smoke,
fold smoke, assemble and any model load or forward remain unauthorized.
