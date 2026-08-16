# EXP-055: Stack Overflow M1/M3 Frozen Validation Error Analysis

---
experiment_id: EXP-055
tier: Major
stage: descriptive-frozen-validation-error-analysis
status: frozen-before-row-level-prediction-and-raw-text-review
date: 2026-08-15
rq_ids: [RQ-S1, RQ-S3]
---

## Purpose

EXP-055 analyzes the already frozen and independently verified validation predictions
from EXP-051 M1 RoBERTa and EXP-053 M3 Classification LoRA. It does not train a model,
rerun inference, select a checkpoint, change a threshold, access test, or authorize
EXP-054.

The analysis asks:

1. Which exact-set and label-level errors are shared, recovered by M3, or introduced
   by M3 relative to M1 across seeds 42, 43, and 44?
2. Is the apparent M3 six-label Macro-F1 advantage confined to the seven-positive
   `surprise` label, or is there complementary information on the other five labels?
3. How do neutral, single-label, two-label, empty-prediction, prediction-cardinality,
   and calibration slices differ between M1 and M3?
4. Does a non-deployable whole-vector oracle show enough headroom to justify a later
   train-OOF router feasibility experiment?
5. In a deterministic qualitative sample, which linguistic, ontology, annotation,
   context, calibration, or representation limitations plausibly explain the errors?

The expected pattern is that M3 recovers `surprise` and some M1 errors while
introducing regressions on more common labels. This expectation may be falsified.
EXP-055 is behavioral error analysis and does not test an internal mechanism claim.

## Frozen Inputs

- Dataset protocol: `DATA-SO-TASK-V1`.
- Split: validation only, 720 rows in 702 duplicate components.
- Validation SHA-256:
  `e83ea51f32c7a1a067f8ed63d499c5540a46542efefdb3afdc7de9937921e4f7`.
- Label order: `love`, `joy`, `surprise`, `anger`, `sadness`, `fear`.
- Validation supports: 183, 74, 7, 132, 34, and 16 respectively; 294 neutral,
  406 single-label, and 20 two-label rows.
- M1 selected epochs: seed 42/43/44 = 4/4/5.
- M1 shared thresholds: seed 42/43/44 = 0.25/0.30/0.50.
- M3 selected epochs: seed 42/43/44 = 2/2/2.
- M3 shared thresholds: seed 42/43/44 = 0.40/0.35/0.25.
- Fixed-threshold companion for both families: 0.50.

Frozen row-level prediction SHA-256 values:

| Family | Seed | SHA-256 |
| --- | ---: | --- |
| M1 | 42 | `ddd0bfb7e4be3336a2e8a1154e45e7866c3ea16d01717c443fb7a18a51c67ef8` |
| M1 | 43 | `fb366b99a1ade7aabdfd45ece92f5643cd91c4436fb0a51f884324a03f046e99` |
| M1 | 44 | `7e1803b7b25800343f96e2080f4c912c9eac7bc27ea5eba1361dc165507f93f4` |
| M3 | 42 | `d10b3179efd4814a4fcb3fbef0e12869649894c0330a766c86922bf1fb43006f` |
| M3 | 43 | `5eb6f549c9e342ece24829bebde5f337118887970b831007cc020c8c8a9c36bf` |
| M3 | 44 | `fb33a535aee73ada5938e6bf70d194246906b75ce0d597ad5d996146a87c3aef` |

The configuration must also bind the successful per-seed and aggregate verifier
hashes. Seed 42 M3 must use `verification-attempt-2.json`; the preserved failed
first verifier is provenance only and cannot authorize this analysis.

The configuration contains no train or test path. Any missing or changed source hash,
non-Passed upstream verifier, row-order mismatch, or gold mismatch stops the run.

## Full-Validation Quantitative Analysis

The primary operating condition is each seed's already frozen shared threshold.
Fixed 0.50 is a calibration-independent sensitivity condition. No threshold is fitted
or selected in EXP-055.

All 720 validation rows enter:

- independent recomputation of per-seed Macro-F1, Micro-F1, Weighted-F1, strict
  subset accuracy, samples-F1, Hamming loss, per-label TP/FP/FN/TN, and five-label
  Macro-F1 without `surprise`;
- row-level exact-set transitions for each matched seed: both correct, M1 only,
  M3 only, and both wrong;
- family stability counts: 3/3 exact correct, 0/3 exact correct, or 1--2/3 exact
  correct; these are descriptive categories, not ensemble predictions;
- label-level correctness transitions and M1-to-M3 FP/FN recovery or regression;
- neutral, single-label, two-label, and each-gold-label slices;
- empty-prediction rate, mean predicted cardinality, false-empty positive rows,
  neutral false-positive rows, and two-label underprediction;
- shared-versus-fixed prediction flips and their metric consequences;
- top three high-confidence false positives and false negatives per family and label,
  ranked by the three-seed mean selected-epoch probability. These tracked rows use
  derived case IDs and contain no text or source identifiers.

Macro-F1 is not additively decomposable. Counts may be decomposed, but the report
must not describe a label or slice as contributing an exact additive quantity to the
overall Macro-F1 difference.

## Whole-Vector Oracle and Router Gate

For each matched seed and operating condition, the oracle compares the two complete
six-dimensional prediction vectors on each row. It selects M3 only when M3 has
strictly fewer label errors than M1; ties select M1. The selected vectors are then
evaluated as one diagnostic prediction matrix. Per-label mixing is prohibited.

The report includes oracle Macro-F1, five-label Macro-F1, Micro-F1, Weighted-F1,
strict subset accuracy, Hamming loss, M3 selection rate, and deltas from both M1 and
M3. Component bootstrap with 2,000 replicates reports descriptive 95% intervals for
the oracle-minus-M1 six-label and five-label Macro-F1 deltas.

The router-headroom gate passes only if the shared-threshold condition satisfies all
of the following:

1. oracle-minus-M1 six-label Macro-F1 is positive for 3/3 seeds and its three-seed
   arithmetic mean is at least 0.020;
2. oracle-minus-M1 five-label Macro-F1 without `surprise` is positive for 3/3 seeds
   and its three-seed mean is at least 0.010;
3. M3 is strictly preferred by row-level Hamming error on at least 5% of validation
   rows for every seed.

Passing this gate authorizes only a separately registered train-OOF router
feasibility protocol. It does not show that a deployable router can identify those
rows. Failing closes the router branch for the current M1/M3 pair unless new model
evidence is separately authorized.

## Qualitative Sample Frozen Before Reading Text

The maximum unique qualitative sample is 48 rows. Roles are processed in this order,
and later roles exclude rows already selected:

1. `surprise_gold` (up to 7): every available gold-`surprise` row.
2. `m3_stable_exact_recovery` (up to 8): M1 is exact-wrong for 3/3 seeds and M3 is
   exact-correct for 3/3 seeds.
3. `m1_stable_exact_recovery` (up to 8): M1 is exact-correct for 3/3 seeds and M3 is
   exact-wrong for 3/3 seeds.
4. `shared_stable_exact_error` (up to 8): both families are exact-wrong for 3/3 seeds.
5. `m1_seed_unstable` (up to 6): M1 has one or two exact-correct seeds.
6. `m3_seed_unstable` (up to 6): M3 has one or two exact-correct seeds.
7. `two_label_disagreement` (up to 5): a two-label gold row where the families'
   per-label majority vectors differ.

Within each role, rows are ordered by SHA-256 of
`20260815:EXP-055:<role>:<sample_id>`. A first pass permits at most two rows per gold
label-set stratum; a second pass fills remaining slots. Underfilled roles remain
underfilled, and no post hoc role is substituted.

Tracked case IDs are `case-` plus the first 16 hex characters of
SHA-256(`EXP-055:<sample_id>`). The private case map retains source sample/component
IDs and text. Tracked artifacts never contain those fields.

## Qualitative Coding

One reviewer may assign multiple evidence flags:

- sarcasm or irony;
- negation;
- implicit emotion;
- mixed emotion;
- slang, code, quotation, or surface noise;
- possible missing forum context;
- annotation ambiguity;
- lexical-cue conflict;
- emotion-ontology overlap;
- weak emotion versus neutral boundary;
- multi-label underprediction;
- low-support `surprise`;
- no listed factor observed.

The reviewer chooses one primary possible source:

- annotation or data uncertainty;
- overlapping label ontology;
- missing forum context;
- model or representation limitation;
- calibration or threshold policy;
- surface-form noise;
- low-support label uncertainty;
- uncertain.

The reviewer also records whether the gold label is `plausible`, `debatable`, or
`implausible` from the isolated text. These codes are hypotheses about selected cases.
They are not revised ground truth, dataset-wide prevalence estimates, causal
explanations, or faithful accounts of model reasoning. Inter-rater reliability is
unavailable with one reviewer.

## Privacy Boundary

Tracked outputs contain derived case IDs, labels, predictions, probabilities,
aggregate statistics, and coded flags only. They exclude source sample/component IDs,
raw forum text, free-form notes, checkpoints, and train/test data.

The private case map and review deck are written under:

```text
experiments/stack-overflow-emotion-gold/error-analysis/private/exp-055-m1-m3-validation-error-analysis/
```

That directory is gitignored and must use mode 0700 for the directory and 0600 for
files. Public privacy checks reject source IDs and any exact raw-text substring of
20 or more non-whitespace characters.

## Outputs and Independent Verification

Planned tracked outputs:

- `run.json` and `summary.json`;
- `seed_metrics.csv`, `per_label_metrics.csv`, `exact_transitions.csv`,
  `family_stability.csv`, `per_label_transitions.csv`, `slice_metrics.csv`, `cardinality_summary.csv`,
  `calibration_sensitivity.csv`, and `oracle_summary.csv`;
- `high_confidence_errors.csv`, `sample_manifest.csv`, `manual_annotations.csv`,
  and `qualitative_summary.json`;
- `REPORT.md`, `verification.json`, and `VERIFICATION-SUMMARY.md`.

The independent verifier must not import the runner. It recomputes source hashes,
row alignment, metrics, transitions, slices, oracle decisions, bootstrap values,
deterministic sampling, annotation summaries, artifact hashes, permissions, Git
isolation, public privacy, and `test_accessed=false`.

## Resource Budget and Stop Rules

- New model runs or API calls: 0.
- Maximum qualitative rows: 48.
- Bootstrap replicates: 2,000 per seed and operating condition.
- Maximum wall time: 120 minutes.
- API cost: USD 0.

Stop if any frozen input changes, a source verifier is not Passed, a prediction file
does not contain exactly 720 aligned rows, gold labels disagree, sampling exceeds the
budget, a tracked artifact leaks private text/identifiers, or any code path attempts
to read test. EXP-055 findings may motivate a separately registered experiment but
cannot alter EXP-051 or EXP-053 retrospectively.
