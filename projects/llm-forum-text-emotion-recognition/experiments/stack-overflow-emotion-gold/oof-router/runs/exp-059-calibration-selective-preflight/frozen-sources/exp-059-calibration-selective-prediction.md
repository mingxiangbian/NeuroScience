# EXP-059: Cross-Fitted Calibration And Selective Prediction

- Experiment ID: `EXP-059`
- Tier: Major
- RQ: `RQ-S3`
- Parent: `EXP-055`, `EXP-058`
- Registered: 2026-08-17
- Status: authorized for no-result preflight and, only after that gate passes, formal
  train-OOF analysis

## Question And Purpose

EXP-059 asks two system questions:

1. Can scalar temperature scaling make M1 RoBERTa and M3 Qwen Classification LoRA
   probabilities more reliable on fully out-of-fold (OOF) training predictions?
2. Can simple uncertainty scores identify high-risk samples well enough to support an
   explicit abstention state without discarding most rare positive examples?

It also recomputes a calibrated whole-vector M1/M3 oracle as a non-deployable headroom
diagnostic for the later EXP-060 router. EXP-059 does not train a router and cannot
establish deployment benefit.

## Authorization And Access Boundary

The user requested the next registered step after EXP-058 completed and passed final
verification. This authorizes deterministic CPU analysis of the frozen paired OOF
artifact, creation of private row-level calibrated outputs, aggregate public metrics and
figures, and independent verification.

Allowed input:

- `EXP-058` private `paired-oof.npz`, SHA-256
  `e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc`;
- exactly `3,360` `DATA-SO-TASK-V1` train rows;
- frozen fields `sample_ids`, `component_ids`, `fold_ids`, `gold`, `m1_logits`,
  `m3_logits`, character lengths and model token lengths;
- EXP-058 public run, paired summary, and passed final verification.

Forbidden:

- validation inputs, predictions, labels, or metrics;
- test inputs, sealed labels, predictions, or metrics;
- model loading, model training, forward passes, new logits, prompt changes, or new
  seeds;
- threshold, calibrator, abstention, or router selection using validation or test;
- row-level public labels, logits, probabilities, predictions, IDs, or text.

The existing Stack Overflow test remains consumed. EXP-059 evidence is fully
cross-fitted train-OOF development evidence, not a new held-out test result.

## Input Integrity Gate

Before any metric is computed, a no-result preflight must verify:

- input bytes and SHA-256;
- all expected NPZ keys, shapes and dtypes from array headers only;
- EXP-058 final status `Passed` with `26,989/26,989` checks;
- the passed EXP-058 verification and public summary report five folds with exactly
  `672` rows each; the formal analyzer must recheck those counts from values before
  computing any metric;
- no validation/test path in the formal config or allowlist;
- NumPy, SciPy and Matplotlib availability in the frozen runtime;
- output paths do not exist.

Formal analysis is forbidden until the independent preflight verification passes.

## Meta-Level Cross-Fitting

EXP-059 reuses the five EXP-058 fold IDs. For each held-out meta fold `k`:

1. fit calibration and threshold parameters on the other four OOF folds;
2. apply those parameters to fold `k`;
3. save one calibrated probability vector, one threshold and one prediction vector for
   every held-out row;
4. repeat for all five folds and restore frozen EXP-058 source order.

This ensures that both the base model and the calibrator/threshold pipeline did not fit
the evaluated row. Duplicate components remain fold-disjoint because the same manifest
is reused.

Parameters fitted once on all `3,360` OOF rows are saved only as future deployment or
validation-development parameters. They are not used to score the same OOF rows in the
primary cross-fitted results.

## Scalar Temperature Calibration

M1 and M3 are calibrated independently. All six labels in one family share one scalar
temperature:

```text
p = sigmoid(logit / T), T > 0
```

Frozen optimization:

- objective: mean binary cross-entropy with logits over all rows and six labels;
- optimize `log(T)` with bounded scalar minimization;
- bounds: `T in [0.05, 20.0]`;
- numeric dtype: float64;
- convergence tolerance: `1e-12` in log-temperature;
- maximum iterations: `1,000`;
- record success, iterations, objective and boundary proximity for every fold and the
  full-OOF fit.

Both raw identity probabilities (`T=1`) and temperature-scaled cross-fitted
probabilities are reported. A family adopts temperature scaling for downstream EXP-059
outputs only when aggregate cross-fitted NLL improves by at least `1e-6` and Brier score
does not worsen by more than `1e-6`. Otherwise its selected calibrator is identity and
its final deployment temperature is frozen to `1.0`. Worse calibration is reported,
not hidden.

## Global Threshold Selection

Calibration and classification thresholds are separate. For both identity and
temperature pipelines, each meta-training partition searches one shared threshold over
all six labels:

```text
0.05, 0.06, ..., 0.95
```

Selection order:

1. highest six-label Macro-F1;
2. lowest Hamming loss within numeric tolerance `1e-12`;
3. threshold closest to `0.50`;
4. lower threshold as the final deterministic tie-break.

No per-label threshold is allowed. The selected family pipeline uses its corresponding
cross-fitted thresholds. A final all-OOF global threshold is saved for later use but is
not used for the primary OOF score.

## Calibration And Classification Metrics

Calibration metrics:

- mean BCE/NLL over all label bits;
- Brier score over all label bits;
- micro expected calibration error (ECE);
- macro classwise ECE;
- 15 deterministic equal-frequency bins, stable probability sort, weighted absolute
  confidence-frequency gap.

Classification metrics:

- six-label Macro-F1;
- five-label Macro-F1 excluding low-support `surprise`;
- Micro-F1;
- Hamming loss;
- strict subset accuracy;
- per-label precision, recall, F1 and support.

Raw fixed-0.5, raw cross-fitted-threshold, temperature fixed-0.5,
temperature cross-fitted-threshold, and the protocol-selected pipeline are all retained.
Temperature scaling is not expected to change the fixed-0.5 decision boundary.

## Selective Prediction And Abstention

Neutral and abstention are distinct:

- six predicted zeros means neutral/no detected emotion;
- `abstain=true` means the system withholds a prediction because uncertainty is high.

Three uncertainty scores are evaluated separately on each family’s selected
cross-fitted probabilities:

1. `mean_entropy`: mean binary entropy across six labels;
2. `max_entropy`: maximum binary entropy across six labels;
3. `margin`: negative minimum absolute distance to that row’s cross-fitted global
   threshold.

Higher values always mean more uncertain. For target coverages
`1.00, 0.95, 0.90, 0.80, 0.70, 0.60`, each held-out fold accepts the least-uncertain
rows with deterministic score and sample-ID tie ordering. This is a cross-fitted ranking
diagnostic. Full-OOF uncertainty cutoffs are saved separately for future online use.

Primary selective risk:

- Hamming risk over accepted rows.

Secondary metrics:

- subset error;
- Micro-F1;
- six-label and five-label Macro-F1;
- actual coverage and accepted-row count;
- per-label positive retention count and rate.

An explicit random-rejection baseline uses `100` deterministic repetitions, seed
`20260817`, and the same accepted count within every fold. It reports mean, 5th, 2.5th,
50th, 95th and 97.5th percentiles.

## Abstention Practical Gate

For each family, a qualifying operating point must have target coverage at least `0.80`
and satisfy all of the following relative to its selected full-coverage prediction:

- Hamming-risk relative reduction at least `20%`;
- five-label Macro-F1 decrease no larger than `0.01`;
- positive retention at least `50%` for every non-`surprise` label;
- observed Hamming risk strictly below the 5th percentile of matched random rejection.

Among qualifying points, select highest Hamming-risk reduction, then higher coverage,
then method order `mean_entropy`, `max_entropy`, `margin`. If no point qualifies, the
family gate fails. A failed gate permits calibrated probabilities but forbids the claim
that abstention reliably identifies errors.

## Whole-Vector Oracle Diagnostic

Using the selected cross-fitted M1 and M3 predictions, compute sample Hamming loss for
each complete six-bit vector. Select M3 only when its loss is strictly lower; ties select
the cheaper M1. Recompute aggregate metrics after whole-vector selection.

This oracle is not deployable and cannot be used as a router feature. The preliminary
EXP-060 headroom gate stops only when both the oracle’s six-label and five-label
Macro-F1 gains over M1 are below `0.01`. If six-label passes but five-label fails, mark a
`surprise_only_or_low_support_warning`; continuation still requires explicit review and
a new EXP-060 protocol.

## Uncertainty And Bootstrap

Use `2,000` duplicate-component bootstrap replicates with seed `20260817`. Components,
not rows, are resampled; all rows in a sampled component travel together. Report 95%
percentile intervals for:

- temperature-minus-identity NLL and Brier deltas for each family;
- whole-vector oracle six-label and five-label Macro-F1 gains over M1;
- Hamming-risk relative reduction for a selected abstention gate point, when one exists.

These intervals quantify uncertainty in the current OOF sample. They do not correct for
post-selection across uncertainty methods and are not independent-test confidence
intervals.

## Outputs And Privacy

Private mode-`0600`, Git-ignored artifacts:

- cross-fitted selected and temperature probabilities;
- cross-fitted thresholds and prediction vectors;
- uncertainty scores and acceptance masks;
- original anonymous sample/component IDs, fold IDs and gold vectors;
- a private machine-readable recomputation table for EXP-060.

Public aggregate artifacts:

- `run.json` and frozen source/config copies;
- `calibration-parameters.json`;
- `calibration-metrics.json`;
- `classification-metrics.json`;
- `oracle-summary.json`;
- `abstention-gates.json` and `bootstrap.json`;
- `reliability-bins.csv`, `risk-coverage.csv`, `label-retention.csv`, and
  `random-rejection.csv`;
- reliability and risk-coverage PNG figures;
- `REPORT.md`, `verification.json`, and `VERIFICATION-SUMMARY.md`.

No public artifact may contain row-level IDs, folds, gold, logits, probabilities,
predictions, uncertainty scores, text, or source coordinates.

## Independent Verification

The verifier must not import the analyzer. It independently:

- verifies all frozen hashes, schemas, output permissions and split-access claims;
- recomputes temperatures, cross-fitted probabilities, thresholds, calibration and
  classification metrics from the EXP-058 private input;
- recomputes uncertainty rankings, random baselines, retention, gates, oracle and
  component bootstrap;
- compares every public JSON/CSV numeric field within `1e-10` absolute tolerance;
- compares every private array exactly for integer/string fields and within `1e-10` for
  float fields;
- verifies PNG signatures and dimensions and binds their hashes;
- scans public outputs for prohibited row-level fields;
- records that validation/test and model inference were not accessed.

## Resource Budget And Stop Conditions

- runtime: `/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python`;
- CPU wall time: at most `30` minutes formal analysis and `30` minutes verification;
- peak process memory: at most `4` GB;
- formal runs: one, after one no-result preflight;
- bootstrap replicates: exactly `2,000`;
- random-rejection repetitions: exactly `100`;
- API cost: `$0`;
- stop on source/input hash drift, non-finite data, fold/component leakage, public
  privacy violation, output collision, failed preflight, or budget breach.

## Thesis Destination And Claim Boundary

Destination: methods and system-results sections for calibration, confidence,
abstention, and conditional routing; appendix for nested cross-fitting and
reproducibility.

EXP-059 may support cross-fitted train-OOF claims about calibration quality and
selective-risk ranking for the frozen seed-42 M1/M3 pair. It does not support a new test
result, stable three-seed conclusion, deployed latency/cost benefit, learned-router
benefit, context benefit, or internal emotion mechanism.
