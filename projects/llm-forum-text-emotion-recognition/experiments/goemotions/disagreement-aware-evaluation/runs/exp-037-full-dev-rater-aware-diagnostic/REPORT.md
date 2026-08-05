# EXP-037: Full-dev Rater-aware Frozen-prediction Diagnostic

## Boundary

This validation-only diagnostic rescored seven frozen prediction files on all 5,426
official GoEmotions dev rows. It performed no training, model inference, checkpoint
selection, threshold change, or test access.

## Annotation Integrity

- Rows joined and reproduced: 5426; official aggregation mismatches: 0.
- Matched per-rater annotations: 19440.
- Rows with disagreement among clear raters: 4596 (0.847033).
- Official targets matching no clear individual rater: 509 (0.093808).
- Rows with unclear annotations: 203 (0.037412).

## Frozen Predictions

| Condition | Runs | Official Macro-F1 | Clear-rater soft Macro-F1 | Expected rater set-F1 |
| --- | ---: | ---: | ---: | ---: |
| bert-base-cased | 3 | 0.489435 | 0.383471 | 0.485977 |
| qwen3-1.7b-instruct-lora | 3 | 0.451374 | 0.347253 | 0.475587 |
| qwen3-1.7b-target-aligned-lora | 1 | 0.427959 | 0.334503 | 0.475033 |

Soft Macro-F1 uses each clear annotator's vote fraction as the label target. Expected
rater set-F1 instead averages set agreement against one clear annotator at a time.
Neither diagnostic is replacement truth; official dev metrics remain the benchmark.

## Paired Comparisons

| Comparison (candidate - reference) | Official Macro delta | Soft Macro delta | Macro shift | Decision |
| --- | ---: | ---: | ---: | --- |
| exp029-family-minus-exp020-family | -0.038061 | -0.036218 | +0.001843 | gap_remains |
| exp033-seed42-minus-exp029-seed42 | -0.009246 | -0.005071 | +0.004176 | practical_tie_or_uncertain |
| exp033-seed42-minus-exp020-seed42 | -0.050794 | -0.044061 | +0.006733 | gap_remains |

Primary classification: `gap_remains`. Annotation-aware soft scoring
materially shifts the primary Macro-F1 comparison under the frozen rule: `false`.

## Limits

- Annotator votes measure observed agreement, not latent human emotion.
- Original raters saw isolated comments, so missing conversational context remains.
- Bootstrap intervals resample dev examples, not training seeds.
- Soft-label rescoring does not change the official benchmark target or model outputs.
- The result is behavioral evidence and does not identify an internal mechanism.

Status: completed, pending independent artifact verification.
