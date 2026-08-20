# DEC-SO-ROUTER-REPLICATION-V1: Prospective Router Replication Contract

- Decision ID: `DEC-SO-ROUTER-REPLICATION-V1`
- RQ: `RQ-S3`
- Parent protocols: [EXP-058](exp-058-paired-m1-m3-oof.md),
  [EXP-059](exp-059-calibration-selective-prediction.md), and
  [EXP-060](exp-060-pre-qwen-deployable-router.md)
- Registered: 2026-08-17
- Status: `Frozen protocol decision; implementation, preflight, and formal execution
  are not authorized by this document`

## Decision And Evidence Roles

The three model seeds have fixed roles:

```text
seed 42 = discovery evidence
seed 43 = prospective replication 1 (EXP-061)
seed 44 = prospective replication 2 (EXP-062)
```

Seed 42 does not vote in replication success. Seeds 43 and 44 must both run under
the same frozen algorithm; a seed-43 failure does not cancel seed 44. Features,
router family, logistic hyperparameters, call-rate point, tie rules, or gates may
not be reselected after either replication result is observed.

For terminology, EXP-060 is meta-level routing development over frozen base OOF
predictions. It is not an end-to-end nested estimate of a complete
base-training-to-router pipeline.

## Frozen Data And Base OOF Identity

Both prospective replications use only `DATA-SO-TASK-V1` train:

- `3,360` rows and `3,277` duplicate components;
- train SHA-256
  `fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc`;
- label order `love, joy, surprise, anger, sadness, fear`;
- the seed-42 five-fold manifest, assignment seed `20260816`, SHA-256
  `82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8`;
- the same component assignments, source order, model/tokenizer revisions,
  prompts, and complete base-asset hash manifest used by verified EXP-058.

The only scientific change between replications is `model_seed`. Every seed trains
five fresh M1 folds and five fresh M3 folds from the pinned original base assets.
No full-train model, prior adapter/head, prior optimizer state, prior-seed logits,
or regenerated fold manifest may be used.

M1 retains four OOF epochs and every EXP-058 optimizer, schedule, truncation, loss,
and batch setting. M3 retains two epochs and every EXP-058 Qwen, prompt, pooling,
BF16, LoRA, head, optimizer, truncation, and batch setting. The Phase-0
implementation must record the exact RNG map: Python/NumPy/PyTorch and the M1
batch generator use `model_seed`; the M3 head and PCG64 batch order use
`model_seed`; the existing M3 LoRA initialization uses MLX seed
`model_seed + 100000`.

Before any formal training, an initialization manifest must bind, per fold:

```text
model_seed
base_asset_manifest_sha256
fold_manifest_sha256
m1_classifier_init_sha256
m1_rng_state_digest
m1_initialization_state_sha256
m1_batch_order_sha256
m3_lora_a_init_sha256
m3_lora_b_init_sha256
m3_lora_combined_init_sha256
m3_classifier_head_init_sha256
m3_base_sentinel_sha256
m3_rng_state_digest
m3_initialization_state_sha256
m3_batch_order_sha256
m3_lora_b_zero_initialized = true
```

Seeds 43 and 44 must share base/fold identities and differ in randomized M1 head,
M3 LoRA-A, and M3 head initialization. Identical LoRA-B hashes are expected only
when the frozen zero initialization is independently confirmed.

Both no-result initialization preflights therefore run before either formal OOF
training starts. A separate cross-seed verifier must compare the two Passed
manifests fold by fold, confirm the shared base/fold identities and required
randomized differences, and bind its aggregate-only Passed record into both
formal configs. A mismatch stops formal training; it is not repaired by changing
the seed map or regenerating a successful manifest in place.

## Calibration Boundary

EXP-059 is rerun independently on each seed's paired raw OOF logits. It may report
identity and scalar-temperature NLL/Brier, the frozen temperature adoption
diagnostic, selective prediction, label retention, and whole-vector oracle
headroom. These remain diagnostics for that seed.

Every EXP-060 replication nevertheless uses only identity probabilities:

```text
p = sigmoid(raw_logit), T = 1
```

Temperature selection cannot change routing. The router must not consume any
EXP-059 row-level probability, prediction, threshold, `oracle_choose_m3`, route
target, or oracle array. EXP-059 temperature outputs may not rescue a failed
identity replication.

## Frozen Nested Router Construction

For each outer fold `k`:

1. Hold out `k` for router evaluation.
2. For each of the other four folds `j`, select separate M1 and M3 global
   thresholds from the remaining three outer-training folds, using identity
   probabilities recomputed from that seed's EXP-058 raw logits. Use those
   thresholds to build features, base predictions, and the whole-vector route
   target on `j`.
3. Concatenate the four inner-held-out partitions as router-training rows.
4. Select M1 and M3 thresholds on all four outer-training folds and apply them
   once to outer fold `k`.
5. Fit the scaler and router only on the nested router-training rows, apply them
   once to `k`, repeat for all five folds, and restore frozen source order.

The threshold grid is `0.05, 0.06, ..., 0.95`. Its deterministic tie order is
highest six-label Macro-F1, lowest Hamming loss within `1e-12`, closest to `0.50`,
then lower threshold. Thresholds must be recomputed from raw logits inside this
3-fold/4-fold construction; a threshold saved by EXP-059 is forbidden.

The target is `1` only when the complete thresholded M3 six-bit vector has lower
row Hamming loss than the complete M1 vector. Ties select M1. M3 outputs and gold
may construct this supervised target but may not enter runtime features.

## Frozen Features, Router, And Cutoff

The runtime feature matrix has exactly these 14 ordered columns:

```text
m1_probability_love
m1_probability_joy
m1_probability_surprise
m1_probability_anger
m1_probability_sadness
m1_probability_fear
m1_mean_binary_entropy
m1_max_binary_entropy
m1_minimum_threshold_margin
m1_predicted_cardinality
m1_highest_probability
m1_lowest_probability
character_length
m1_token_length
```

Raw M1 logits are retained for verifier recomputation but are not extra features.
M3 information, disagreement, gold, IDs, fold IDs, component IDs, raw text, and
validation/test statistics are forbidden model columns.

Each outer fold fits `StandardScaler` plus L2 logistic regression with `C=1.0`,
`class_weight=balanced`, `solver=liblinear`, `max_iter=1000`, and
`random_state=42`. The sole primary operating point is nominal Qwen call rate
`15%`. Its cutoff is derived only from outer/meta-training route scores:

```text
route_score >= cutoff -> call M3
route_score < cutoff  -> retain M1
```

Cutoff ties therefore call M3. Held-out IDs or labels cannot force an exact rate;
both nominal and actual rates must be reported. Other call rates and entropy or
margin policies are descriptive only and cannot rescue the primary point.

## Primary Gate And Frozen Diagnostics

For `logistic_router` at nominal `15%`, a replication passes only if all point
estimate conditions hold relative to fully nested M1-only:

1. actual Qwen call rate is at most `0.20`;
2. six-label Macro-F1 gain is at least `0.01`;
3. five-label Macro-F1 gain is at least `-0.005`;
4. Hamming-loss delta is at most `1e-12`;
5. at least one non-`surprise` label has F1 gain of at least `0.005`.

The run also reports exactly `100` deterministic component-aware random-routing
repetitions with seed `20260817` at the matched fold-policy call counts, and
exactly `2,000` duplicate-component bootstrap replicates with seed `20260817`
and 95% percentile intervals. These quantify diagnostics and uncertainty; they
do not select or change the point-estimate gate.

Each seed's terminal primary result is exactly `Pass` or `Fail`, with
`primary_policy=logistic_router` and `primary_nominal_call_rate=0.15` retained in
either case. A single-seed `Fail` is not a command to stop the router branch and
must not prevent the other prospective seed from running. Only EXP-063 may turn
the two terminal results into the `2/2`, `1/2`, or `0/2` system decision.

## Append-Only Execution And Access Boundary

Each seed-specific protocol freezes one public and one private experiment
namespace. Every formal configuration additionally freezes one matching
`attempt-N` directory below each namespace. Immediately before an attempt, both
attempt directories must be absent; an existing empty directory, file, symlink,
or redirected ancestor is a hard failure. Existing earlier attempts are retained
and do not make a later attempt writable.

Private attempt directories are Git-ignored and mode `0700`; private files are
mode `0600`. A failed or interrupted attempt is retained with its logs and
failure status. A retry uses `attempt-N+1`, starts every affected fold again from
the pinned base initialization, and may not resume a partial checkpoint or
overwrite the failed attempt.

No attempt directory is moved or rewritten after verification. After one attempt
passes the independent OOF, calibration, and router verifiers, a dedicated
finalizer atomically creates exactly one public `selected-attempt.json` inside the
experiment namespace. That immutable selection record binds the experiment ID,
seed, attempt ID, all three completion records, their configs, runs,
verifications, and artifact hashes. Its prior existence blocks all later
attempts; its absence means that no attempt has been selected. This single-file
commit marker avoids a non-atomic two-directory promotion and preserves every
verified artifact path and hash.

Validation inputs, validation labels, consumed test inputs, sealed test labels,
and every validation/test-derived artifact are forbidden for OOF training,
calibration diagnostics, routing, gate selection, and verification. Public
outputs are aggregate allowlisted artifacts only; row-level text, IDs, gold,
logits, probabilities, features, targets, masks, and predictions remain private.

## Replication Decision And Claim Boundary

After independent verification of both prospective seeds:

| EXP-061 / EXP-062 | Decision |
|---|---|
| `2/2` pass | frozen router replicated across training seeds on the same train data |
| `1/2` pass | seed-sensitive; do not promote as a stable system component |
| `0/2` pass | seed-42 discovery was not prospectively replicated |

Even `2/2` supports only a same-`DATA-SO-TASK-V1-train`, cross-training-seed,
meta-level routing claim. It is not independent-data validation, an end-to-end
pipeline estimate, production benefit, general-forum evidence, or a latency
result. Validation projection and latency benchmarking require separately
registered experiments.
