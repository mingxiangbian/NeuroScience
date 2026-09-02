# EXP-070: Layerwise Linear Probe

- Experiment ID: `EXP-070`
- Date: `2026-08-27`
- RQ: `RQ-S4.1`
- Tier: `Major representation experiment`
- Parent decision: `DEC-SO-PHASE-B-REPRESENTATION-V1`
- Parent gate: `EXP-069 Complete via verification recovery attempt 2`
- Current status: `No-result preflight only; formal execution closed`

## 1. Question and claim boundary

EXP-070 asks which preregistered Phase B points show different linear accessibility of Stack Overflow
labels after Classification LoRA. It compares Frozen Qwen with fold-specific M3 checkpoints. The
nine sampled points cannot locate an exact onset layer.

The strongest supported claim is train-data, outer-heldout linear decodability under this probe and
pooling contract. The experiment cannot identify emotion neurons, human emotion mechanisms, causal
representations or independent-data generalization.

## 2. Parent evidence

EXP-069 verified the extraction path on 32 deterministic smoke rows. Those NPZ files remain parity
fixtures. EXP-070 cannot fit probes, select layers or report results from them.

The no-result preflight binds the Phase B decision and the complete EXP-069 chain:

- original and attempt-4 configs;
- attempt-4 run, failed final verification and private smoke manifest;
- recovery config, 25/25 Passed verification and completion;
- base plus 15 fold NPZ identities and header schemas.

The preflight reads no hidden-state, logit, label or text values from those artifacts.

## 3. Formal representation producer

EXP-070 will own its full train-only extraction stage. It will not write into EXP-069 directories.

The producer will create 16 private float32, C-order matrices:

```text
Frozen Qwen: one (3360, 9, 2560) matrix
M3 seed 42: five (3360, 9, 2560) matrices
M3 seeds 43/44: ten (3360, 3, 2560) matrices
seed-42 point order = H-1, H7, H15, H19, H20, H27, H31, H35, HF
seed-43/44 point order = H19, H27, HF
```

The first axis of every matrix follows the exact `DATA-SO-TASK-V1 train` source order, ordinals
`0..3359`. The private cache manifest binds separate SHA-256 digests for ordinal, sample-ID,
component-ID, fold-ID and token-ID streams. Row identifiers and digests remain private.

Each `M3_{seed,fold}` checkpoint processes all 3,360 train rows. Its 2,688 outer-train rows were seen
during M3 fine-tuning; its 672 outer-heldout rows were not. The cache must label these roles. Only
probe predictions on outer-heldout rows enter scientific results.

Frozen Qwen uses one shared matrix. The probe pipeline fits one Frozen baseline per layer and outer
fold, then reuses its outerheldout probabilities for the three M3 seed contrasts.

Every extraction worker uses the EXP-069 tokenizer, prompt, singleton forward, max length 384,
thinking-off and last-input-token pooling contracts. A fresh process handles one checkpoint. It
writes into a new private root, flushes the matrix, seals its identity and exits. The formal runner
must compare `H-1/H7/H15/H19` with Frozen Qwen in float32 using `rtol=0, atol=1e-5`. It stops on
token-stream, checkpoint, pre-LoRA, mode, resource or finite-value drift.

Seeds 43/44 compute `H-1/H7/H15` transiently for this parity gate, record only aggregate maximum
errors in their private worker manifests, then discard those arrays. Their persisted matrices remain
`H19/H27/HF`, so the raw-byte budget excludes the transient points.

## 4. Outer and inner splits

The experiment reuses the five EXP-058 component-disjoint folds. It does not generate new folds.

For outer fold `k`:

1. outer train contains the other four folds, 2,688 rows;
2. outer heldout contains fold `k`, 672 rows;
3. `M3_{seed,k}` supplies both outer-train and outerheldout representations;
4. the scaler and probe cannot see outerheldout rows or labels.

Inner OOF threshold selection reuses the four outer-train fold IDs. For inner fold `j`, the scaler
and six probes fit on the remaining three folds, 2,016 rows, and predict the 672 rows in `j`. The
four inner predictions form one 2,688-row inner-OOF probability matrix. The pipeline then refits the
scaler and probes on all 2,688 outer-train rows and predicts outer fold `k` once.

## 5. Probe

Each model, layer and fit uses:

```text
StandardScaler(with_mean=True, with_std=True)
six independent LogisticRegression classifiers
penalty = l2
C = 1.0
solver = liblinear
class_weight = None
fit_intercept = true
intercept_scaling = 1.0
dual = false
max_iter = 2000
tol = 1e-4
random_state = 42
```

The scaler fits inside the same split as its probes. The runner stops on a convergence warning,
single-class fit partition, non-finite coefficient or probability, unexpected shape, or access to an
excluded fold. No C-grid, solver search, nonlinear probe or per-label threshold is allowed.

## 6. Thresholds and metrics

Average Precision uses probabilities and does not depend on a classification threshold. The primary
decision metric is five-label Macro Average Precision, excluding `surprise`.

Secondary classification metrics use one shared six-label threshold selected from the inner-OOF
probabilities:

```text
grid = 0.05, 0.06, ..., 0.95
prediction = probability >= threshold
selection order:
1. highest five-label Macro-F1 within 1e-12
2. lowest six-label Hamming loss within 1e-12
3. threshold closest to 0.50
4. lower threshold
```

All F1 calculations use `zero_division=0`.

Required secondary outputs are six-label Macro AP/F1, five-label Macro-F1, Micro AP/F1, Hamming
loss, subset accuracy and per-label AP/F1. The public report contains aggregates only. Row-level
probabilities, predictions, labels, component IDs, coefficients and scalers remain private.

## 7. Seed roles and decision rule

Seed 42 runs all nine points and supplies the discovery curve. Seeds 43 and 44 run the frozen
confirmation points `H19/H27/HF`. The experiment will not select confirmation layers from the
seed-42 curve.

For each executed M3 seed and layer, concatenate the five outerheldout folds into one 3,360-row OOF
probability matrix. Compute:

```text
delta_AP = five-label Macro AP(M3) - five-label Macro AP(Frozen)
```

The Phase B vote remains unchanged. Seed 43 or 44 passes only when `H27` and `HF` both have positive
point deltas and paired component-bootstrap 95% lower bounds above zero. `H19` is a pre-LoRA sanity
point and does not vote. Seed 42 and all secondary metrics remain descriptive.

The protocol does not add p-values or a result-driven multiple-comparison correction. The nine-layer
curve is exploratory, while the frozen two-point conjunction controls the replication decision.

## 8. Label-shuffle control

The control covers `H27/HF`, Frozen Qwen and M3 seeds 42/43/44. It uses three frozen shuffle seeds:
`2026082711`, `2026082712` and `2026082713`.

For each shuffle seed and outer fold, `SeedSequence([shuffle_seed, outer_fold])` initializes PCG64.
The resulting permutation moves complete six-label row vectors within the 2,688-row outer-train
partition. This preserves outer-train label frequency, label cardinality and within-row
co-occurrence. Outerheldout labels do not enter permutation, fitting or selection. The evaluator may
read them only after it seals control probabilities.

The same permutation serves every layer, model and M3 seed for that outer fold. The runner records
its int64 permutation digest. A shuffled control fits one final scaler and six probes on the shuffled
outer-train labels and evaluates AP against the unchanged outerheldout labels. It does not run inner
threshold selection or produce F1 decisions. The main analysis plus controls contains at most 4,320
binary logistic fits.

For shuffle replicate `r`, the control contrast is 3,360-row OOF five-label Macro AP:
`AP5(M3 shuffled r) - AP5(Frozen shuffled r)`. The control cannot select a model, layer or
threshold. If any of the three shuffle replicates gives both seeds 43 and 44 a pass at H27 and HF
under the registered bootstrap rule, EXP-070 records `Negative-control failure`. This is a validity failure:
EXP-074 cannot assign any of the three representation states from the affected run, and it cannot
relabel the failure as no effect.

## 9. Bootstrap

Use 2,000 paired duplicate-component bootstrap replicates with PCG64 seed `2026082701`. Within each
outer fold, a replicate draws that fold's component count with replacement and includes every row
from each selected component. It then concatenates the five folds. The same component draws serve
Frozen and M3, every layer, seed and control. Percentile endpoints are 2.5% and 97.5%.

Thresholds and predictions stay frozen during bootstrap. The runner does not refit probes or select
thresholds inside a replicate. All six labels must contain at least one positive and one negative
row in every replicate. Otherwise the experiment stops; it does not discard or redraw that
replicate. Per-label and secondary intervals remain descriptive.

## 10. Runtime and resource contract

Formal extraction uses the frozen Phase A MLX environment. Probe fitting uses the existing
`emotion-roberta` CPU environment with Python 3.10.20, NumPy 2.2.6, scikit-learn 1.7.2, SciPy 1.15.3
and joblib 1.5.3. NPY files form the interface between the runtimes. The probe converts each selected
float32 representation slice to float64 before scaling and fitting.

EXP-069 measured 41.46 seconds for 32 base rows and 252.58 seconds for 96 M3 rows. Linear projection
to the registered full workload is 1.21 hours for Frozen Qwen and 36.83 hours for the 15 M3 workers,
38.04 hours total. This is a scheduling estimate, not a performance result.

Formal ceilings:

- 16 model workers, one at a time;
- 4 hours wall time and 10 GB MLX peak per model worker;
- 64 hours total model-worker wall time;
- raw representation bytes: `2,890,137,600`;
- private EXP-070 budget: 5 GiB;
- minimum free disk before extraction: 10 GiB;
- one CPU probe worker at a time;
- at most 4,320 binary logistic fits, 12 CPU hours and 8 GB peak RSS;
- BLAS and OpenMP threads fixed to one;
- API cost: USD 0.

## 11. Access and artifact policy

Formal EXP-070 may read DATA-SO train text and labels only after a separate formal config authorizes
the extraction and probe stages. It may read the frozen fold assignment and M3 checkpoints. It may
not read validation or test text, labels, predictions or test-gate artifacts.

Private directories use `0700`; private files use `0600` and remain Git ignored. The experiment
retains full train representation matrices until Phase B closeout because regeneration costs about
38 hours. A later cleanup must use a separate, explicit operation.

## 12. No-result preflight

The current preflight may read:

- public parent JSON;
- private manifest metadata;
- file identities and NPZ headers;
- package metadata, disk capacity and synthetic fixtures.

It may not read hidden-state, logit, train-text or label values. It cannot load a model, execute a
forward pass, fit a real probe, select a threshold, run bootstrap or calculate a scientific metric.

The runner writes public `static.json` and private `input-contract-manifest.json`. An independent
model-free verifier writes `static-verification.json` and `no-result-complete.json`. Passing this gate
freezes the method and confirms input readiness. It does not authorize formal extraction or fitting.

## 13. Stop rules

Stop on identity, mode, inventory, symlink, NPZ-header, environment, disk, split, method or output-root
drift. Stop if a process imports a model library, reads an array value, accesses text or labels,
creates a scientific metric, or finds a formal output root.

Failed attempts remain append-only. A correction requires a new attempt ID. EXP-071 stays closed
until EXP-070 finishes formal extraction, probing and independent verification.
