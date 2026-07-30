# EXP-007 Protocol: Train-CV-Selected Linear SVM

## Registration

- Date: 2026-07-29
- Tier: Major
- RQ ID: RQ-B1
- Status at registration: Planned
- Selection experiment: EXP-006, train-only 5-fold cross-validation
- Frozen selection artifact SHA-256:
  `8ddb3e3a479ebb53de8cee25401ff792acff770a6e5a4cc8823352f03f4f475e`
- Splits accessed by EXP-007: official train and validation only
- Test split: prohibited

## Question

Does the configuration selected without validation access in EXP-006 improve
official validation Macro-F1 over EXP-005?

## Frozen Configuration

- Word TF-IDF: lowercase `(1,2)` n-grams, `min_df=2`, L2 norm,
  `sublinear_tf=true`.
- Character TF-IDF: lowercase raw character `(3,6)` n-grams, `min_df=2`,
  L2 norm, `sublinear_tf=true`.
- LinearSVC: `C=0.25`, `class_weight="balanced"`,
  `loss="squared_hinge"`, `penalty="l2"`, `dual="auto"`,
  `tol=1e-4`, `max_iter=5000`, `random_state=42`.
- Runs: one.

These values are copied exactly from EXP-006 before EXP-007 validation is
read. No result-dependent changes are permitted under this experiment ID.

## Metrics and Decision Rule

- Primary: validation Macro-F1.
- Secondary: Accuracy, weighted F1 and per-class metrics.
- Comparison: EXP-005 Macro-F1 `0.6118659622`, Accuracy `0.6711229947`.
- Practical improvement: Macro-F1 delta at least `+0.005`.
- Accuracy is reported separately and cannot override the primary rule.

## Required Artifacts

- `run.json`, `stdout.log`, local gitignored `model.joblib`
- `predictions.csv` with decision scores
- `confusion_matrix.csv` and `confusion_matrix.png`
- `verification.json` from independent metric recomputation

## Resource Budget

- Maximum runs: 1
- Device: local Mac CPU
- Wall-time budget: 5 minutes
- API cost: USD 0
- Stop on selection hash mismatch, data hash mismatch, test access,
  non-convergence, NaN, or non-empty output directory.

## Interpretation Boundary

EXP-007 is a development-set confirmation. The official validation split was
previously used for architecture comparison in EXP-005, so EXP-007 does not
provide an unbiased final generalization estimate. That role remains reserved
for the untouched test split after the complete comparison set is frozen.

## Recorded Outcome

- Run date: 2026-07-29
- Status: Completed
- Validation Macro-F1: `0.6226779061`
- Validation Accuracy: `0.6764705882`
- Delta versus EXP-005: Macro-F1 `+0.0108119439`, Accuracy `+0.0053475936`
- Primary rule: passed
- Test split accessed: no
- Independent recomputation: passed for 374 predictions, per-class metrics,
  confusion matrix, input hashes and artifact hashes

## Baseline Freeze Decision

- Decision date: 2026-07-30
- Role: frozen local traditional baseline candidate
- Frozen model SHA-256:
  `c4744557448a5b6a3606c21b6ed655e45a19051058b3d1e7aa0d1d53ebca4590`
- Frozen configuration SHA-256:
  `8ddb3e3a479ebb53de8cee25401ff792acff770a6e5a4cc8823352f03f4f475e`
- Training data: unchanged official train split only
- Further tuning under EXP-007: prohibited
- Test status: deferred until the final comparison set is frozen and the
  project `TEST-READY` gate receives explicit user authorization

When test evaluation is authorized, evaluate the frozen model artifact rather
than refitting on train plus validation. Any later linear-model development
must use a new experiment ID and must not rewrite EXP-007.
