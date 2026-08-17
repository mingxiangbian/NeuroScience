# EXP-057: Stack Overflow Frozen Result Synthesis

---
experiment_id: EXP-057
tier: Major
stage: post-test-read-only-result-synthesis
status: frozen-before-execution
date: 2026-08-16
rq_ids: [RQ-S1, RQ-S2, RQ-S3]
---

## Purpose

EXP-057 converts the already frozen and verified Stack Overflow C0 validation,
validation-error-analysis, and test aggregates into thesis-ready tables. It does not
train a model, rerun inference, inspect row-level predictions, open test labels, fit a
threshold, select a seed, change a parser, or add a model.

The synthesis answers only these reporting questions:

1. What are the matched three-seed validation and held-out test results for M1-M4?
2. Which frozen pairwise test contrasts are supported by the precomputed
   duplicate-component bootstrap intervals?
3. How do the test results vary by label and resource path?
4. Which conclusions are supported, unresolved, or outside the experiment's claim
   boundary?

This is post-test descriptive work. Its outputs cannot be used to change any frozen
Stack Overflow configuration or to authorize another test run.

## Frozen Public Inputs

The configuration binds the SHA-256 and byte size of exactly these tracked artifacts:

- EXP-051 M1 three-seed validation aggregate and verifier;
- EXP-052 M2 three-seed validation aggregate and verifier;
- EXP-053 M3 three-seed validation aggregate and verifier;
- EXP-054 M4 three-seed validation aggregate and verifier;
- EXP-055 validation error-analysis summary and successful verifier;
- EXP-056 frozen test results and successful verifier.

Every upstream verifier must have `status=Passed` and no failed checks. EXP-056 must
retain contract SHA-256
`bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966`,
results SHA-256
`d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd`,
`labels_opened_after_prediction_seal=true`, and
`selection_or_tuning_after_test=false`.

No configured source may be a private directory, `.npz` prediction artifact, raw
forum-text file, checkpoint, adapter, or sealed label file. Paths mentioned inside an
upstream provenance record are not dereferenced.

## Frozen Transformations

The analyzer performs deterministic presentation transformations only:

- extract the pre-registered operating-point validation metrics for M1-M4;
- independently recompute mean and sample standard deviation from the 12 public
  EXP-056 unit metric records and compare them with the frozen family aggregates;
- summarize test Macro-F1, five-label Macro-F1 without `surprise`, Micro-F1,
  Weighted-F1, strict subset accuracy, Hamming loss, precision, recall, empty-output
  rate, and predicted label cardinality;
- summarize per-label precision, recall, F1, predicted support, and gold support;
- reproduce the five frozen pairwise bootstrap contrasts without recalculating or
  changing bootstrap samples;
- report validation-to-test differences descriptively, never as a selection rule;
- summarize existing EXP-055 error-analysis findings without opening its private
  review deck;
- summarize recorded inference resource paths without claiming a hardware-fair speed
  benchmark.

No additional hypothesis test, confidence interval, threshold search, ensemble,
router, calibration, or qualitative case selection is permitted.

## Planned Outputs

Tracked outputs under
`post-test-analysis/runs/exp-057-read-only-result-synthesis/` are:

- `validation-family-summary.csv`;
- `test-family-summary.csv`;
- `test-per-label-summary.csv`;
- `test-contrast-summary.csv`;
- `test-resource-summary.csv`;
- `result-synthesis.json`;
- `THESIS-TABLES.md`;
- `run.json`;
- frozen copies of the protocol, config, analyzer, verifier, and tests;
- `verification.json` and `VERIFICATION-SUMMARY.md`.

All public outputs contain aggregate metrics, anonymous model-family names, and
artifact hashes only. They contain no forum text, source identifiers, row-level
predictions, or private paths.

## Independent Verification

The verifier must not import the analyzer. It independently checks source hashes,
upstream verification states, test-gate invariants, family/seed scope, mean and sample
standard deviation calculations, per-label supports, CSV values, contrast orientation,
resource summaries, claim-boundary statements, artifact hashes, and public privacy.

The run is `Verified` only if all checks pass. A failed check invalidates the synthesis
and prevents its tables from entering the experiment report.

## Claim Boundary

EXP-057 may support behavioral statements about this six-label Stack Overflow C0 task
under the frozen split and models. It cannot establish:

- that Qwen or LLMs generally outperform encoders;
- that generation causes better or worse emotion recognition independent of all other
  M3/M4 differences;
- that a deployable router can realize the validation oracle;
- that `surprise` performance is stable with only seven test positives;
- that any hidden feature is a causal emotion mechanism;
- that model behavior explains how humans generate emotion.

## Resource Budget and Stop Rules

- New training, inference, API calls, or test-label reads: 0.
- Maximum wall time: 5 minutes.
- API cost: USD 0.

Stop if an input hash changes, an upstream verifier is not Passed, the EXP-056 contract
or result hash differs, any family/seed is missing, a configured path enters a private
or raw-data location, an output leaks a private path or source identifier, or a script
attempts to create a new scientific comparison.
