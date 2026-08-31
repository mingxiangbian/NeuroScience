# EXP-070 Formal Extraction Verification Attempt 2

- Experiment ID: `EXP-070`
- Date: `2026-08-27`
- Source attempt: `formal-extraction-attempt-1`
- Verification attempt: `2`
- Stage: `model-free extraction verification recovery`
- Status: `Registered; execution waits for the immutable 16-worker terminal snapshot`

## 1. Purpose

This append-only consumer corrects two verifier-only defects. It does not change the formal
extraction protocol, config, runner, matrices, worker manifests, checkpoints or tolerances.

The frozen attempt-1 verifier:

1. compares an EXP-069/070 zero-based ordinal token digest with the legacy EXP-052 one-based row
   position digest, even though those serialization schemes are not comparable;
2. computes the independent saved-HF head replay with NumPy float32 accumulation and applies the
   `1e-5` gate used by the MLX runtime replay.

The extraction protocol requires all 16 current workers to share the Frozen-base digest. It does
not require equality with the legacy EXP-052 digest. The runner's MLX head replay remains the
runtime-path parity check.

## 2. Incident evidence observed before freeze

The base and `m3-s42-f0` artifacts were sealed before this recovery was registered. They remain
immutable inputs.

The bound private base worker and M2 metadata contain different digest values. The recovery binds
those file identities but does not copy either token-stream digest into a public protocol, config or
result.

The two digest functions serialize identical token streams differently:

```text
EXP-052: (index + 1) as little-endian uint64, length, int32 token IDs
EXP-069/070: zero-based ordinal as little-endian uint64, length, int32 token IDs
```

Observed `m3-s42-f0` parity:

```text
runner MLX head versus historical logits                    = 0.0
full-matrix H-1/H7/H15/H19 versus Frozen                   = 0.0
independent NumPy float32 affine versus historical logits   = 1.049041748046875e-05
independent NumPy float64 affine versus historical logits   = 2.086469194750862e-06
float32 elements above 1e-5                                = 1
```

The float64 result was observed during recovery design. This fact is part of the incident record.
No float64 replay for the other 14 M3 workers may be inspected before this protocol, config and
implementation are frozen.

The incident review read only `sample_ids`, `fold_ids` and `logits` from the fold-0 held-out NPZ.
It read no gold, train labels, validation or test values; loaded no model; fitted no probe; and
computed no classification metric.

## 3. Two semantic corrections

### 3.1 Token digest

Remove only this assertion from the frozen source verifier:

```text
EXP-070 base token digest == legacy EXP-052 M2 token digest
```

Retain:

- both scheme names and the fact that their values differ, without publishing either digest;
- exact cross-worker equality between every M3 worker and the EXP-070 Frozen base;
- source-order, tokenizer, prompt, model, row-identity and full M2-HF parity gates;
- the requirement that each digest is a valid 64-character lowercase SHA-256 string.

### 3.2 Independent head replay

Keep the runner metric unchanged:

```text
runner_mlx_head_vs_historical_logit_max_abs
```

The independent verifier uses one canonical formula:

```python
x64 = saved_hf.astype(np.float64)
w64 = saved_head_weight.astype(np.float64)
b64 = saved_head_bias.astype(np.float64)
replayed64 = x64 @ w64.T + b64
reference64 = historical_logits.astype(np.float64)
```

It compares `replayed64` directly with `reference64` using `rtol=0, atol=1e-5`. It must not cast
the result back to float32, change the matrix operator, use a relative tolerance or widen the
absolute tolerance.

The NumPy float32 affine replay remains a diagnostic for all 15 M3 workers. It cannot decide the
recovery gate and cannot be omitted from the recovery output.

The public recovery verification reports one aggregate record per M3 worker with `worker_id`,
runner MLX max abs, NumPy float32 max abs and NumPy float64 max abs. It contains no token-stream
digest value.

## 4. Anti-post-hoc safeguards

- Apply one formula and one tolerance to all 15 M3 workers.
- Freeze this consumer before inspecting workers other than `m3-s42-f0` with float64 replay.
- Report runner MLX, NumPy float32 diagnostic and NumPy float64 gate values separately.
- If any float64 replay exceeds `1e-5`, stop. Do not try another dtype, cast, operator or tolerance.
- Do not merge the token-digest and affine-replay incidents into one numeric result.
- Do not modify or overwrite the frozen attempt-1 verifier, config, runner or source snapshot.
- Do not run a model or rerun extraction, assemble or any worker.

## 5. Future terminal snapshot claim

The current source has only the Frozen base and `m3-s42-f0` sealed. Terminal verification is
forbidden until the formal source contains all 16 workers and `extraction.json` reports
`CompletedAwaitingVerification`.

At execution, the recovery consumer must:

1. require the source public inventory to contain only `run-claim.json` and `extraction.json`;
2. require the private terminal manifest to bind exactly 16 sealed workers and matrices;
3. compute a digest over every source public/private file identity;
4. write `source-snapshot-claim.json` in a fresh recovery root before replay;
5. capture all transformed verifier writes in memory, never in the source root;
6. recompute the source snapshot digest after replay and require exact equality.

The source root remains unchanged. A failed recovery preserves its claim and writes no completion.
If a process stops after writing a Passed `verification.json`, a later invocation may validate the
claim and unchanged source snapshot, rerun the complete transformed model-free replay, rebuild the
exact expected verification payload, require byte/object equality plus mode `0644` and one hard
link, then write only the missing completion.

## 6. Execution and access boundary

Allowed:

- read the frozen source verifier as text;
- apply exactly two anchored source transformations;
- memory-map sealed representations;
- read frozen row/fold metadata, M2 features, head tensors and held-out `sample_ids/fold_ids/logits`;
- compute parity errors and artifact identities;
- write the recovery claim, verification and extraction-stage completion in a fresh public root.

Forbidden:

- runner import;
- MLX, MLX-LM, Transformers or model loading;
- model forward, training, extraction or assemble rerun;
- train labels, held-out gold, validation or test access;
- probe fitting, threshold selection, label shuffle, bootstrap or classification metrics;
- source mutation or tolerance changes.

## 7. Outputs

Fresh recovery root:

```text
phase-b-representation/runs/exp-070-layerwise-probes/
  formal-extraction-verification-attempt-2/
  ├── source-snapshot-claim.json
  ├── verification.json
  └── extraction-complete.json
```

Passing recovery completes only formal representation extraction. It sets:

```text
formal_extraction_complete = true
probe_fitting_authorized = false
performance_metrics_computed = false
exp070_complete = false
exp071_authorized = false
```

Probe execution still requires a separate immutable consumer and authorization.
