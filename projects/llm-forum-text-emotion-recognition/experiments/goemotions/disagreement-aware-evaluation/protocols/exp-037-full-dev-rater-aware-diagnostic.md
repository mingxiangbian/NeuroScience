# EXP-037: Full-dev Rater-aware Frozen-prediction Diagnostic

---
experiment_id: EXP-037
tier: Major
stage: validation-only-frozen-prediction-diagnostic
status: frozen-before-full-dev-match-retention-and-scoring
date: 2026-08-04
rq_ids: [RQ-G2]
parent_experiment: EXP-036
data_protocol: DATA-GOE-FULL-DEV-RATER-EVAL-V1
---

## Purpose

EXP-036 showed that the Qwen and BERT families were practically tied on expected individual-rater
set-F1 within the 174-row `neutral+emotion` dev slice. That slice was selected for one aggregation
pathology and cannot establish whether annotation aggregation explains the models' full-dev
Macro-F1 gap. EXP-037 therefore asks:

> Across all 5,426 frozen dev examples, does the EXP-029 versus EXP-020 gap remain when each label
> is scored against its clear-annotator vote fraction, and is the conclusion consistent with
> expected agreement with one clear individual annotator?

This is a validation-only diagnostic. It performs no training, checkpoint selection, prompt
change, threshold tuning, or test evaluation.

## Frozen Inputs

- Official GoEmotions dev: 5,426 rows; SHA-256
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Labels: 28 labels with `neutral` at ID 27; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Selection: rows `1..5426`; ordered row-number SHA-256
  `973b9f662bf3fac69c014da03f4741bf312e409bd38ddb1d8e4d8c6c48a3fa98`.
- Raw source identities and retention rules: `DATA-GOE-FULL-DEV-RATER-EVAL-V1` and the hashed
  config.
- Frozen prediction sets:
  - EXP-020 BERT-base-cased seeds 42, 43, and 44;
  - EXP-029 Qwen3-1.7B Instruct LoRA zero-shot-selected seeds 42, 43, and 44;
  - EXP-033 target-aligned Qwen3-1.7B Instruct LoRA seed 42.
- Prediction and upstream verification SHA-256 values are frozen in the config.
- Simplified test must remain absent and unread.

## Metric Contract

For example `i`, label `l`, binary prediction `z_il`, official target `g_il`, and the `m_i` clear
individual-rater label sets `R_ij`, define:

```text
q_il = count of clear raters selecting label l / m_i
set-F1(A, B) = 2 * |A intersect B| / (|A| + |B|)
```

The primary diagnostic is clear-rater soft-label Macro-F1. For each label:

```text
soft_TP_l = sum_i z_il * q_il
soft_FP_l = sum_i z_il * (1 - q_il)
soft_FN_l = sum_i (1 - z_il) * q_il
soft_F1_l = 2 * soft_TP_l / (2 * soft_TP_l + soft_FP_l + soft_FN_l)
```

Macro-F1 is the unweighted mean of the 28 label F1 values. Soft micro-F1 and per-label soft
precision, recall, F1, and support are secondary. Every example contributes total weight one per
label regardless of its number of raters.

The complementary sample-level diagnostic is, for each example, the mean of
`set-F1(P_i, R_ij)` over clear raters, followed by an unweighted mean over examples. Expected
clear-rater exact match, any-clear-rater exact match, best-clear-rater set-F1, and all-labeled-rater
sensitivity metrics are also retained.

Official-target Macro-F1, micro-F1, sample set-F1, and subset accuracy are recomputed beside the
diagnostics. The vote fractions and expected-rater scores describe agreement with observed
annotations; neither is a replacement truth or a direct measure of latent emotion.

## Frozen Comparisons and Statistics

Primary comparison:

- EXP-029 three-seed family mean minus EXP-020 three-seed family mean. A family mean is the mean
  of the three independently scored runs; predictions are not ensembled.

Secondary seed-42 comparisons:

- EXP-033 minus EXP-029;
- EXP-033 minus EXP-020.

Use paired example-level bootstrap resampling with seed `20260804`:

- 2,000 iterations for official and clear-rater soft Macro-F1, their model deltas, and the
  difference-in-differences between those deltas;
- 10,000 iterations for official sample set-F1, expected clear-rater set-F1, their model deltas,
  and the corresponding difference-in-differences.

The bootstrap treats dev examples as the resampling unit. It does not estimate uncertainty over
the three training seeds. Family metrics are averaged across their registered runs inside each
bootstrap replicate.

Practical tie threshold: absolute score difference below `0.005`.

For the primary candidate-minus-reference comparison:

- `gap_remains` requires soft Macro-F1 delta `<= -0.005` and bootstrap upper 95% bound `< 0`;
- `candidate_advantage` requires delta `>= 0.005` and bootstrap lower 95% bound `> 0`;
- otherwise classify `practical_tie_or_uncertain`.

Annotation-aware scoring materially shifts the comparison only if
`soft Macro-F1 delta - official Macro-F1 delta >= 0.020` and the paired bootstrap lower 95% bound
is above zero. A material shift can show that hard aggregation explains part of the measured gap;
it cannot establish a model mechanism or invalidate the official benchmark.

## Integrity and Stop Rules

Before scoring:

- verify all local input, prediction, verification, protocol, and implementation hashes;
- verify each prediction file has exactly rows `1..5426` and gold IDs matching frozen dev;
- verify all 5,426 raw joins, unique comment/rater pairs, nonempty clear-rater sets, and exact
  official `>=2` label reproduction;
- verify the output directory is empty and `test.tsv` is absent.

Stop on any mismatch. Do not repair labels, drop difficult rows, substitute seeds, or read test.

## Outputs

Tracked:

- `run.json`, `source-manifest.json`, `aggregate-summary.json`;
- `row-structure.csv`, `run-metrics.csv`, `family-summary.csv`, `per-label-metrics.csv`;
- `pairwise-comparisons.csv`, `REPORT.md`, `verification.json`, `stdout.log`.

Private and gitignored:

- matched per-rater annotation records without raw text or upstream identifiers.

The full public per-example score matrix is intentionally omitted. Bootstrap inputs are
reconstructed from frozen predictions and private matched records by both implementations.

## Thesis Mapping

- Evidence target: `EVID-025`.
- Figure/table target: `Table-G2-9`.
- Thesis sections: full-dev results on aggregate versus annotation-aware scoring; discussion of
  annotator disagreement, supervision targets, and limits of soft-label diagnostics.

## Resource Budget

- Raw archive: one successful stream of each of three official objects.
- Frozen prediction files: seven; no model inference.
- Bootstrap: 2,000 soft-Macro and 10,000 sample-level paired resamples.
- Model/API calls and API cost: 0.
- Maximum wall time: 60 minutes.
- Maximum formal runs: 1.
