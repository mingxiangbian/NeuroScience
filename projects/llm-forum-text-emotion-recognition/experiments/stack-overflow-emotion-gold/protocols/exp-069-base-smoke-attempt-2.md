# EXP-069 Base Smoke Continuation, Attempt 2

- Experiment ID: `EXP-069`
- Attempt ID: `attempt-2-base-smoke`
- Date: `2026-08-26`
- RQ: `RQ-S4`
- Parent: EXP-069 attempt-1 static verification `14/14 Passed`
- Status: `Base smoke authorized; fold and assemble closed`
- Test access: `false`

## 1. Purpose

Attempt 1 sealed a static-only config and verified all source identities without model load. This
continuation binds those immutable records and runs one 32-row Frozen-Qwen base smoke. It does not
change or copy attempt-1 outputs.

The base smoke checks two paths:

1. manual nine-point extraction `HF` against the standard `model.model()` output;
2. extracted `HF` against the verified EXP-052 train feature cache.

This attempt does not load any M3 adapter or head. It does not authorize fold smoke, assemble,
classification metrics or representation claims.

## 2. Frozen parent records

The attempt-2 config binds exact bytes, mode and SHA-256 for:

- attempt-1 config;
- attempt-1 `static.json`;
- attempt-1 `static-verification.json`;
- attempt-1 private `input-manifest.json`;
- the frozen attempt-1 runner source reused for tokenization and manual extraction.

The consumer replays the attempt-1 config/implementation/environment gates before model load.
Parent config, static outputs and input manifest remain immutable.

## 3. Authorization

```text
base_smoke_authorized = true
model_loading_authorized = true
forward_authorized = true
fold_smoke_authorized = false
assemble_authorized = false
training_authorized = false
performance_metrics_authorized = false
validation_access = false
test_access = false
```

The consumer accepts only `--stage base-smoke`. Any other stage fails before creating outputs.

## 4. Inputs and rows

The runner reuses the 32 ordinals and fold mapping from the private attempt-1 input manifest. It
parses the corresponding train JSON rows for text. The label-bearing container is accessed, but
label values are neither used nor persisted.

It reuses:

- Qwen3-4B BF16 revision `1cfa9a7208912126459214e8b04321603b3df60c`;
- the frozen target-only prompt and tokenizer contract;
- the M2 train feature cache `(3360, 2560)`, float32;
- points `H-1/H7/H15/H19/H20/H27/H31/H35/HF`.

## 5. Numeric gates

All comparisons use float32 and `rtol=0`:

| Gate | Maximum absolute error |
| --- | ---: |
| Manual HF vs standard HF | `1e-5` |
| Manual HF vs M2 train cache | `1e-5` |

Arrays must be finite. Base output shape is `(32, 2560)` for every point. The consumer records a
per-fold token-stream digest for later fold-smoke comparison.

## 6. Sequence and outputs

The append-only sequence is:

```text
run-claim.json
-> private base.npz + base-worker.json
-> public run.json
-> independent verification.json
-> base-complete.json
```

Public output contains aggregate errors, counts, resources, access booleans and private artifact
hashes. It cannot contain text, row/component IDs, ordinals, token IDs, hidden states or logits.

Private directories use `0700`; private files use `0600` and remain Git ignored.

## 7. Independent verifier

The verifier imports no runner, project module or model library. It independently checks:

- parent record hashes and parent static `Passed` status;
- current config and implementation hashes;
- exact public/private inventories and modes;
- base NPZ keyset, shape, dtype, finite values and 32-row coverage;
- `HF` against standard HF and the M2 cache;
- run aggregates, resource aggregates, access boundaries and public privacy.

## 8. Resource budget

- Heavy processes: 1
- Model loads: 1 Frozen Qwen load
- Forward rows: 32 singleton rows
- Wall-time ceiling: 20 minutes
- MLX peak ceiling: 10 GB
- Training: none
- API cost: USD 0

## 9. Stop rules

Stop on parent/config/source drift, output presence, model/tokenizer identity drift, NaN/inf,
tolerance failure, OOM, timeout, private-mode failure, validation/test access or public leakage.
Failure seals this attempt; recovery requires another append-only attempt.

If the process stops after `run-claim.json` but before terminal `run.json`, the attempt is
`Interrupted` and cannot resume in place. A no-model closeout may record the interruption; any model
retry requires a new attempt.

## 10. Claim boundary

The maximum claim is:

> A verified 32-row Frozen-Qwen base representation-path smoke for the frozen Phase B stack.

This attempt supports no M3 checkpoint parity, classification performance, representation effect,
functional dependency, independent-data, deployment or emotion-mechanism claim.

`base-complete.json` must set `base_smoke_complete=true` and `exp069_complete=false`.
