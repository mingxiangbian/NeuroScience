# EXP-071: Representation Drift and Geometry

- Experiment ID: `EXP-071`
- Date: `2026-08-29`
- RQ: `RQ-S4.2`
- Tier: `Major representation experiment`
- Parent decision: `DEC-SO-PHASE-B-REPRESENTATION-V1`
- Parent extraction: `EXP-070 formal extraction Complete via verification attempt 2`
- Parent probe: `EXP-070 Complete via formal-probe verification attempt 2`
- Status: `Method registered; implementation and execution closed`

## 1. Question and claim boundary

EXP-071 measures how fold-specific Classification LoRA changes the same heldout sample's last-token
representation relative to Frozen Qwen at the registered Phase B points. It reports rowwise cosine
distance, rowwise Frozen-denominator relative L2 distance and fold-local linear CKA.

The strongest supported claim concerns same-train outer-heldout representation drift under the
frozen prompt, pooling, checkpoint and point contracts. EXP-071 cannot identify an exact onset
layer, assign a new representation state, establish statistical significance, show that drift causes
probe gain, infer independent-data generalization or support a human-emotion mechanism claim.

Relative L2 is scale-sensitive; cosine distance and linear CKA have different scale and rotation
invariances. Their values describe different geometry properties and need not move together. `HF`
is the final-RMSNorm interface endpoint, not an ordinary raw-residual point adjacent to `H35`.
Because EXP-071 does not read component codes, duplicate components remain row-weighted; the
results do not support a component-balanced inference.

The experiment does not train, fit, calibrate, load a model or execute a forward pass. It does not
change the verified EXP-070 state. Seeds 43 and 44 provide cross-training-seed descriptions at the
three preregistered points; they do not vote on a new state.

## 2. Immutable parents and source boundary

The configs bind the Phase B decision, the EXP-069 terminal recovery, the EXP-070 extraction
terminal chain, the EXP-070 probe terminal chain, the verified public fold manifest and all 16
EXP-070 formal representation matrices by path, bytes, mode and SHA-256.

EXP-069's 32-row smoke matrices remain parity fixtures. Neither the runner nor verifier may read
their values or use them in a geometry calculation. Scientific geometry uses the 16 full EXP-070
caches:

```text
Frozen Qwen: one (3360, 9, 2560) float32 matrix
M3 seed 42: five (3360, 9, 2560) float32 matrices
M3 seed 43: five (3360, 3, 2560) float32 matrices
M3 seed 44: five (3360, 3, 2560) float32 matrices
```

The consumer reads fold assignments from `row-contract.npz`. It may read only `ordinal.npy` and
`fold_id.npy`; it cannot read `component_code.npy`. The public fold manifest and its Passed
verification serve as immutable provenance. Formal execution hashes them but does not parse their
sample-ID or component-ID values.

The probe relation reads only the nine verified aggregate seed-42 AP deltas from public
`probe.json`. It must reproduce the bound canonical results digest before using those fields. It
cannot read private probe artifacts, probabilities, predictions, labels or thresholds.

## 3. Rows, folds, points and condition order

The experiment uses the five frozen component-disjoint folds. Each fold contains 672 heldout rows.
For fold `k`, every comparison uses:

```text
X[k,p] = Frozen Qwen representations for rows with fold_id == k at point p
Z[s,k,p] = m3-s{seed}-f{k} representations for the same rows and point
```

The runner sorts heldout rows by representation ordinal. It cannot use any of the 2,688 outer-train
rows from that M3 checkpoint. It cannot compare a row with another fold's M3 checkpoint.

The condition order is exact:

```text
s42:H-1, s42:H7, s42:H15, s42:H19, s42:H20,
s42:H27, s42:H31, s42:H35, s42:HF,
s43:H19, s43:H27, s43:HF,
s44:H19, s44:H27, s44:HF
```

Each fold contains 15 comparisons. The complete run contains 75 fold-condition comparisons. Seed
42 supplies the nine-point discovery curve. Seeds 43 and 44 remain limited to `H19/H27/HF`.

## 4. Numeric contract shared by all metrics

The runner opens every source matrix as a read-only NumPy memory map and marks the mapping
non-writeable. It selects one `(672, 2560)` slice at a time and converts both Frozen and M3 slices
to C-order float64 before calculation.

Every input and derived value must be finite. A zero vector norm, zero CKA denominator, unexpected
shape, wrong dtype, writable source mapping or source mutation stops the attempt. The runner does
not round a metric before aggregation or comparison.

The independent verifier compares ordinals, shapes, dtypes, condition order, fold order, strings,
booleans and JSON `null` values exactly. It compares stored float arrays, recursive numeric JSON
summaries and defined Spearman rho with `rtol=0, atol=1e-12`. The constant-vector Spearman reason
and its `rho=null` value must match exactly.

## 5. Cosine distance

For heldout row `i`, Frozen vector `x_i` and M3 vector `z_i`:

```text
raw_cosine_i = dot(x_i, z_i) / (l2_norm(x_i) * l2_norm(z_i))
cosine_distance_i = 1 - clip(raw_cosine_i, -1, 1)
```

The runner stops if a norm equals zero or if `raw_cosine_i` lies outside
`[-1 - 1e-12, 1 + 1e-12]`. It clips only values inside that numeric tolerance. It applies no
centering, standardization, whitening, Procrustes alignment or other transformation before the
rowwise distance.

## 6. Relative L2 distance

The reference denominator is Frozen Qwen:

```text
relative_l2_i = l2_norm(z_i - x_i) / l2_norm(x_i)
```

The runner does not add epsilon and does not substitute an M3, mean, maximum or symmetric
denominator. A zero Frozen norm stops the attempt.

## 7. Linear CKA

The experiment uses standard biased linear CKA. For one fold-condition pair, center each feature
column within that fold:

```text
Xc = X - mean(X, axis=0)
Zc = Z - mean(Z, axis=0)
K = Xc @ Xc.T
L = Zc @ Zc.T
raw_cka = sum(K * L) / sqrt(sum(K * K) * sum(L * L))
```

All operations use float64. The normalization cancels the common biased-HSIC scaling factor. The
runner stops if the denominator is zero or if `raw_cka` lies outside
`[-1e-12, 1 + 1e-12]`. It clips values inside that tolerance to `[0, 1]`.

The runner centers within each 672-row fold. It does not standardize feature variances and does not
calculate unbiased CKA. It does not calculate a pooled 3,360-row CKA because the five row groups
come from five different M3 checkpoints.

## 8. Aggregation

For cosine and relative L2, each fold-condition reports:

```text
mean, median, P90, P95
```

The runner then concatenates the five 672-row vectors in fold order `0..4`, with ascending ordinal
inside each fold, and reports the same four statistics over 3,360 rows. Median, P90 and P95 use
NumPy 2.2.6 `percentile(..., method="linear")`. The report does not average fold quantiles.

For CKA, the report contains all five fold values, their arithmetic mean and their sample standard
deviation with `ddof=1`. It does not average across training seeds.

## 9. Pre-LoRA sanity gate

The hard gate converts the heldout slices to float64, recomputes maximum absolute difference and
applies the `1e-5` threshold inherited from EXP-070. This is a new float64 remeasurement under the
parent tolerance, not a claim that it replays the parent's float32 arithmetic:

```text
seed 42: H-1, H7, H15, H19 in every fold
seed 43: H19 in every fold
seed 44: H19 in every fold
maximum absolute difference <= 1e-5
```

Seeds 43 and 44 did not persist `H-1/H7/H15`; the config binds the verified extraction chain that
checked their transient values. EXP-071 does not reconstruct those arrays.

The runner reports H19 cosine, relative L2 and CKA under the same formulas as every other point. It
does not subtract H19 from post-LoRA measurements and does not introduce a second near-zero
threshold. A parity value above `1e-5` is a technical failure rather than evidence of pre-LoRA
drift.

## 10. Seed-42 nine-point Spearman description

EXP-071 computes one Spearman coefficient. In point order
`H-1,H7,H15,H19,H20,H27,H31,H35,HF`:

```text
x[p] = 1 - mean_fold_linear_CKA(seed42, p)
y[p] = verified EXP-070 main contrast
       results.main_contrasts["m3-s42:{p}"].delta.five_label_macro_ap
```

The runner assigns average ranks to ties, then calculates the Pearson correlation between the two
rank vectors. It reports rho only. It does not calculate a p-value, interval, distance-based
Spearman, seeds-43/44 three-point correlation or result-driven alternate. If either rank vector is
constant, it reports `rho=null` with reason `constant_vector`; this remains a valid result.

The coefficient describes nine sampled points from one training seed. A positive or negative rho
does not establish that geometry drift causes probe gain. The shared pre-LoRA/post-LoRA boundary
can influence the rank pattern.

## 11. Lifecycle and authorization

The runner exposes three stages:

```text
static -> initialize -> analyze
```

The verifier exposes four stages:

```text
static-verify -> static-complete -> formal-verify -> formal-complete
```

Static may hash bytes, inspect JSON schemas, inspect NPZ/NPY headers, verify environment and run
synthetic fixtures. It cannot load a representation array value, read a probe metric value, compute
a scientific metric or create a formal root.

Initialize requires fresh formal public and private roots. It writes public `run-claim.json` and
private `input-manifest.json`. Analyze accepts only that exact initialized state, computes all 75
comparisons in one process, writes private `geometry.npz`, writes `geometry-manifest.json`, then
writes public `drift.json` last. It does not create fold seals or resume a partial geometry bundle.

The independent verifier cannot import the runner. Formal verification rereads the source matrices
and verified public AP deltas and recomputes every stored array, summary, sanity gate and rho. Formal
completion reruns the read-only verification, reproduces the same verification payload and writes
`drift-complete.json`.

## 12. Formal artifacts

The private formal root contains exactly:

```text
input-manifest.json
geometry.npz
geometry-manifest.json
```

`geometry.npz` uses no compression and contains exactly:

| Member | Shape | Dtype |
| --- | --- | --- |
| `heldout_ordinals` | `(5, 672)` | little-endian int32 |
| `cosine_distance` | `(15, 3360)` | little-endian float64 |
| `relative_l2_distance` | `(15, 3360)` | little-endian float64 |
| `linear_cka` | `(15, 5)` | little-endian float64 |
| `max_abs_difference` | `(15, 5)` | little-endian float64 |

Distance axis 1 concatenates folds `0..4`, with ascending ordinal inside each fold. CKA and maximum
absolute difference axis 1 follows fold order `0..4`. `geometry-manifest.json` binds the array
member order, shapes, dtypes, source identities before and after analysis, numeric checks, access
attestations, resources and the `geometry.npz` identity.

The formal public success root contains exactly:

```text
run-claim.json
drift.json
verification.json
drift-complete.json
```

`drift.json` may contain fold and pooled aggregates, CKA mean/sample-SD, pre-LoRA maxima, the single
Spearman rho, source identities, resources and access flags. It cannot contain ordinals, rowwise
distances, representations, sample IDs, component IDs, labels, probabilities, predictions or text.

Public directories use `0755`; public files use `0644`. Private directories use `0700`; private
files use `0600`. Every file has one hard link. No root may contain a symlink or unexpected member.

## 13. Access and resources

Formal execution may read representation values from the 16 EXP-070 matrices, `ordinal.npy` and
`fold_id.npy` from the row contract, and the nine verified public AP5 deltas. It may hash all bound
sources. It cannot read labels, component codes, component IDs, sample IDs, private probe artifacts,
probe probabilities, predictions, train text, validation, test or test-gate data. It cannot load a
model, adapter, tokenizer or execute a forward pass.

The frozen runtime is:

```text
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python
Python 3.10.20
NumPy 2.2.6
architecture = arm64
OMP/OPENBLAS/MKL/VECLIB/NUMEXPR threads = 1
```

Resource ceilings:

| Resource | Ceiling |
| --- | ---: |
| Concurrent workers | `1` |
| Runner wall time | `7,200 seconds` |
| Independent verifier wall time | `7,200 seconds` |
| Peak RSS | `4,294,967,296 bytes` |
| Private output | `67,108,864 bytes` |
| Free disk before formal initialization | `1,073,741,824 bytes` |
| API cost | `USD 0` |

## 14. Stop rules and completion claim

The runner or verifier stops on parent, source, config, method, implementation, environment, mode,
inventory, hard-link or hash drift; a non-fresh formal root; wrong fold or condition order; access
to a forbidden row or field; a writable source mapping; non-finite values; zero norm or denominator;
numeric-range violation; pre-LoRA maximum above `1e-5`; source mutation; resource breach; public
row-level leakage; model, validation or test access; or a mismatch between independently recomputed
and reported output.

A technical failure remains append-only. A new attempt must preserve the failed evidence and cannot
change a metric, tolerance, point, seed role, aggregation or correlation after result access.

Successful completion supports this bounded claim:

> EXP-071 measured same-sample outer-heldout representation drift between Frozen Qwen and the
> corresponding fold-specific M3 checkpoint at the registered Phase B points, under the frozen
> distance, fold-local CKA and descriptive correlation contracts.

Completion sets `exp071_complete=true` and keeps `exp072_authorized=false`.
