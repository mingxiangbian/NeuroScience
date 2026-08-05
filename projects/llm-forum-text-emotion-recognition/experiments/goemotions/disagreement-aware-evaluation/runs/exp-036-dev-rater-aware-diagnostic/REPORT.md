# EXP-036: Dev Rater-aware Frozen-prediction Diagnostic

## Boundary

This validation-only diagnostic rescored seven frozen prediction files on the 174
GoEmotions dev rows whose official target contains `neutral` plus another emotion.
It performed no training, inference, checkpoint selection, or test access.

## Annotation Integrity

- Rows joined and reproduced: 174; official aggregation mismatches: 0.
- Matched per-rater annotations: 866.
- Aggregation-only rows: 174 (1.000000).
- Rows with unclear annotations: 2 (0.011494).

## Frozen Predictions

| Condition | Runs | Official set-F1 | Clear-rater expected set-F1 | Any-rater exact |
| --- | ---: | ---: | ---: | ---: |
| bert-base-cased | 3 | 0.557982 | 0.362531 | 0.591954 |
| qwen3-1.7b-instruct-lora | 3 | 0.562261 | 0.363250 | 0.852490 |
| qwen3-1.7b-target-aligned-lora | 1 | 0.561686 | 0.361590 | 0.839080 |

The clear-rater score is the expected set-F1 against a randomly selected annotator
who did not mark the example unclear. It is not a replacement ground truth and is not
comparable to full-dev Macro-F1.

## Paired Comparisons

| Comparison (candidate - reference) | Official delta | Rater-aware delta | Relative shift | Decision |
| --- | ---: | ---: | ---: | --- |
| exp029-family-minus-exp020-family | +0.004278 | +0.000720 | -0.003559 | practical_tie_or_uncertain |
| exp033-seed42-minus-exp029-seed42 | +0.009004 | +0.007280 | -0.001724 | candidate_advantage |
| exp033-seed42-minus-exp020-seed42 | -0.003640 | -0.001398 | +0.002241 | practical_tie_or_uncertain |

Primary classification: `practical_tie_or_uncertain`. Aggregation materially shifts the
primary comparison under the frozen rule: `false`.

## Limits

- The analysis is restricted to a purposively defined 174-row label-conflict slice.
- Annotator agreement is not semantic truth, and original raters saw only one comment.
- Bootstrap intervals resample examples, not training seeds.
- Official full-dev metrics remain the primary model-performance evidence.
- The result is behavioral evidence and does not identify an internal model mechanism.

Status: completed, pending independent artifact verification.
