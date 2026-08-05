# EXP-036: Dev Rater-aware Frozen-prediction Diagnostic

---
experiment_id: EXP-036
tier: Major
stage: validation-only-frozen-prediction-diagnostic
status: frozen-before-dev-raw-annotation-access
date: 2026-08-04
rq_ids: [RQ-G2]
parent_experiment: EXP-035
data_protocol: DATA-GOE-DEV-RATER-EVAL-V1
---

## Purpose

EXP-035 found that all 1,396 train `neutral+emotion` targets were produced by cross-rater
aggregation rather than same-rater co-selection. EXP-036 tests the corresponding 174-row dev
slice and asks a narrower model question:

> After scoring frozen predictions against each clear annotator's own label set, does Qwen still
> underperform BERT, or was part of the apparent gap caused by requiring a model to reproduce an
> aggregate union that no individual annotator supplied?

This is a validation-only diagnostic. It performs no training, checkpoint selection, prompt
change, threshold tuning, or test evaluation.

## Frozen Inputs

- Official GoEmotions dev: 5,426 rows; SHA-256
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Labels: 28 labels with `neutral` at ID 27; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Slice: all 174 dev rows containing label 27 and at least one other label; ordered row-number
  SHA-256 `99368f7f6f014acb46bd96e0a7c6cb38acc60e31daedb5f2e07b9b5d86fd2c4f`.
- Raw source identities and retention rules: `DATA-GOE-DEV-RATER-EVAL-V1` and the hashed config.
- Frozen prediction sets:
  - EXP-020 BERT-base-cased seeds 42, 43, and 44;
  - EXP-029 Qwen3-1.7B Instruct LoRA zero-shot-selected seeds 42, 43, and 44;
  - EXP-033 target-aligned Qwen3-1.7B Instruct LoRA seed 42.
- Prediction and upstream verification SHA-256 values are frozen in the config.
- Simplified test must remain absent and unread.

## Metric Contract

For prediction set `P_i`, official simplified target `G_i`, and each clear rater set `R_ij`:

```text
set-F1(A, B) = 2 * |A intersect B| / (|A| + |B|)
Jaccard(A, B) = |A intersect B| / |A union B|
exact(A, B) = 1 if A equals B, else 0
```

If both sets are empty, set-F1 and Jaccard equal 1. No clear rater set is expected to be empty;
an empty clear-rater set stops the run.

Primary per-example score:

```text
mean over clear raters j of set-F1(P_i, R_ij)
```

The run-level primary diagnostic is the unweighted mean over 174 examples, so examples with more
raters do not receive more weight. Secondary metrics are expected clear-rater Jaccard, expected
clear-rater exact match, any-clear-rater exact match, best-clear-rater set-F1, and an all-labeled-
rater sensitivity set-F1. Official-target set-F1, Jaccard, and exact match are recomputed and kept
alongside the diagnostic.

The rater-aware score means expected agreement with a randomly selected clear annotator. It is not
accuracy against a replacement truth and is not comparable to full-dev Macro-F1.

## Frozen Comparisons and Statistics

Primary comparison:

- EXP-029 three-seed family mean minus EXP-020 three-seed family mean. For each example, average
  each family across its three seeds before the paired comparison.

Secondary seed-42 comparisons:

- EXP-033 minus EXP-029;
- EXP-033 minus EXP-020.

For official set-F1, expected clear-rater set-F1, and their paired difference-in-differences, use
10,000 paired bootstrap resamples over the 174 examples with seed `20260804`. The bootstrap treats
examples as the resampling unit; it does not estimate uncertainty over model training seeds.

Practical tie threshold: absolute score difference below `0.005`.

For a candidate-minus-reference comparison:

- `gap_remains` requires rater-aware delta `<= -0.005` and bootstrap upper 95% bound `< 0`;
- `candidate_advantage` requires delta `>= 0.005` and bootstrap lower 95% bound `> 0`;
- otherwise classify `practical_tie_or_uncertain`.

Aggregation materially shifts the comparison only if
`rater-aware delta - official-target delta >= 0.020` and the paired bootstrap lower 95% bound is
above zero. This rule may show that aggregation explains part of a gap; it cannot identify model
mechanism or dataset-wide performance.

## Integrity and Stop Rules

Before scoring:

- verify all local input, prediction, verification, protocol, and implementation hashes;
- verify each prediction file has exactly rows 1..5,426 and gold IDs matching frozen dev;
- verify all 174 raw joins, unique comment/rater pairs, nonempty clear-rater sets, and exact official
  `>=2` label reproduction;
- verify the output directory is empty and `test.tsv` is absent.

Stop on any mismatch. Do not repair labels, drop difficult rows, substitute seeds, or read test.

## Outputs

Tracked:

- `run.json`, `source-manifest.json`, `aggregate-summary.json`;
- `row-structure.csv`, `per-example-scores.csv`, `run-metrics.csv`, `family-summary.csv`;
- `pairwise-comparisons.csv`, `REPORT.md`, `verification.json`, `stdout.log`.

Private and gitignored:

- matched per-rater annotation records without raw text or upstream identifiers.

## Thesis Mapping

- Evidence target: `EVID-024`.
- Figure/table target: `Table-G2-8`.
- Thesis sections: results subsection on disagreement-aware diagnostic scoring; discussion on
  aggregated supervision, annotator disagreement, and why diagnostic agreement cannot replace the
  official benchmark.

## Resource Budget

- Raw archive: one successful stream of each of three official objects.
- Frozen prediction files: seven; no model inference.
- Bootstrap: 10,000 paired resamples per registered comparison.
- Model/API calls and API cost: 0.
- Maximum wall time: 45 minutes.
- Maximum formal runs: 1.

