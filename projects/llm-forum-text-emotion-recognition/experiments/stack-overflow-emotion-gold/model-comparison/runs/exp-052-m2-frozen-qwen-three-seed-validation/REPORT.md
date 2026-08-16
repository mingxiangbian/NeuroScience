# EXP-052 M2 Three-Seed Validation Aggregate

- Status: `Completed; pending independent aggregate verification`
- Seeds: `42, 43, 44`
- Source splits: `train`, `validation`
- Test access: `false`
- Center / dispersion: arithmetic mean / sample standard deviation (`ddof=1`)
- Predictions pooled across seeds: `false`

| Metric | Fixed 0.5 | Per-seed shared threshold |
|---|---:|---:|
| Six-label Macro-F1 | 0.151553 +/- 0.027647 | 0.318889 +/- 0.038085 |
| Micro-F1 | 0.408950 +/- 0.060584 | 0.514069 +/- 0.022042 |
| Weighted-F1 | 0.331794 +/- 0.036499 | 0.482286 +/- 0.051823 |
| Strict subset accuracy | 0.560185 +/- 0.029669 | 0.490741 +/- 0.028678 |
| Hamming loss | 0.087269 +/- 0.001009 | 0.121142 +/- 0.006565 |
| Five-label Macro-F1 without surprise | 0.181863 +/- 0.033177 | 0.382667 +/- 0.045702 |

## Seed-Level Primary Results

| Seed | Epoch | Threshold | Fixed Macro-F1 | Shared Macro-F1 | Surprise F1 | Mode |
|---:|---:|---:|---:|---:|---:|---|
| 42 | 2 | 0.25 | 0.183391 | 0.324929 | 0.000000 | verified_cache_reuse_head_only |
| 43 | 2 | 0.20 | 0.133610 | 0.353593 | 0.000000 | verified_cache_reuse_head_only |
| 44 | 2 | 0.25 | 0.137657 | 0.278145 | 0.000000 | verified_cache_reuse_head_only |

## Matched M2 Minus M1

| Metric | Fixed 0.5 delta | Per-seed shared-threshold delta |
|---|---:|---:|
| Six-label Macro-F1 | -0.455744 +/- 0.035919 | -0.298365 +/- 0.039425 |
| Micro-F1 | -0.357320 +/- 0.066161 | -0.257070 +/- 0.021312 |
| Weighted-F1 | -0.425313 +/- 0.044359 | -0.281660 +/- 0.049519 |
| Strict subset accuracy | -0.213426 +/- 0.035473 | -0.269907 +/- 0.015299 |
| Hamming loss | 0.038580 +/- 0.003243 | 0.071373 +/- 0.004283 |
| Five-label Macro-F1 without surprise | -0.546893 +/- 0.043102 | -0.358038 +/- 0.047310 |

## Boundary

This is a validation-only M2 family result. No row-level predictions were read or pooled. Shared-threshold comparisons use each model's already frozen validation operating point; fixed 0.5 is the calibration-independent companion. The paired M2-minus-M1 values are descriptive for three matched seeds and do not authorize significance claims. Heterogeneous execution paths are reported per seed and are not averaged into a family cost. Test, TEST-READY, EXP-053 and EXP-054 remain sealed.
