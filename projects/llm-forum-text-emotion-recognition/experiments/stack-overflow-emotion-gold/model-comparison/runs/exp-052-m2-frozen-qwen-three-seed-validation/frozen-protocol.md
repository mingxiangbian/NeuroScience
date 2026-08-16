# EXP-052 M2 Three-Seed Validation Aggregate Authorization

Date: 2026-08-14
Tier / RQ: Major / RQ-S1
Stage: `m2-three-seed-validation-aggregate`

## Purpose

Freeze and independently verify the validation-only family summary for the
three completed EXP-052 M2 seeds. This stage answers whether the frozen
Qwen3-4B final-layer representation plus a fresh linear head remains weak and
seed-sensitive across the registered seeds. It does not train a model or select
a new configuration.

## Authorized Inputs

Only these public machine-readable files may be read:

- EXP-052 seed 42 `run.json` and `verification.json` (`70/70` passed).
- EXP-052 seed 43 `run.json` and `verification.json` (`99/99` passed).
- EXP-052 seed 44 `run.json` and `verification.json` (`104/104` passed).
- The verified EXP-051 M1 three-seed `aggregate.json` and
  `verification.json` (`53/53` passed), only for matched descriptive deltas.

Every source path, byte size and SHA-256 must be frozen in the execution
config. Source hashes must be checked before any statistic is produced.

The aggregate must not read feature caches, checkpoints, probabilities,
row-level labels, raw text, private artifacts or any test file.

## Frozen Method

- Seed order: `42, 43, 44`.
- Center: arithmetic mean.
- Dispersion: sample standard deviation with `ddof=1`.
- No pooled predictions and no concatenation across seeds.
- Report both conditions; neither may be selected after aggregation:
  - fixed threshold `0.5`;
  - each seed's already frozen shared threshold.
- Primary metric: six-label Macro-F1.
- Additional metrics: macro precision/recall, Micro-F1, Weighted-F1, strict
  subset accuracy, Hamming loss, five-label Macro-F1 without `surprise`, empty
  prediction rows and predicted label cardinality.
- Report per-label precision, recall, F1, support and predicted support as
  mean, sample standard deviation and the three source values.
- Compute M2 minus M1 paired deltas by matching the same seed and condition for
  Macro-F1, Micro-F1, Weighted-F1, subset accuracy, Hamming loss and five-label
  Macro-F1. Report arithmetic mean and sample standard deviation only; no
  p-value, confidence interval or significance claim is authorized for `n=3`.
- Shared-threshold comparisons use each model's already frozen validation
  operating point. Fixed-0.5 comparisons remain the calibration-independent
  companion result.
- Resource measurements are reported per seed only. Seed 42 includes Qwen
  feature extraction while seeds 43/44 are cache-only head runs, so their wall
  times must not be averaged into a family cost claim.

## Sealed Work

- Stack Overflow test remains sealed, unrequested and unread.
- No TEST-READY status is created.
- EXP-053 M3, EXP-054 M4, context, routing, error analysis and any new model run
  remain unauthorized.
- The aggregate cannot modify or replace any source run or verification file.

## Required Outputs

- `aggregate.json`
- `REPORT.md`
- frozen config, protocol, runner, verifier and tests
- independent `verification.json`
- `VERIFICATION-SUMMARY.md`

The stage passes only if source identities and hashes match, all three source
verifications remain passed, the independent implementation exactly reproduces
the complete aggregate and paired deltas, public artifacts contain no row-level
or private paths, and test access remains false.

## Decision Boundary

After this aggregate is verified, EXP-052 M2 validation is complete. The next
possible model stage is EXP-053 M3, but it still requires a separate protocol,
resource decision and explicit user authorization.
