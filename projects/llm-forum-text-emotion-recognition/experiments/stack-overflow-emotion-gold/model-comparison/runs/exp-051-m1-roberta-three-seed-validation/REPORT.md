# EXP-051 M1 Three-Seed Validation Aggregate

- Status: `Completed; pending independent aggregate verification`
- Seeds: `42, 43, 44`
- Splits: `train`, `validation`
- Test access: `false`
- Center / dispersion: arithmetic mean / sample standard deviation (`ddof=1`)

| Metric | Fixed 0.5 | Shared threshold |
|---|---:|---:|
| Six-label Macro-F1 | 0.607297 +/- 0.012628 | 0.617254 +/- 0.011084 |
| Micro-F1 | 0.766270 +/- 0.009590 | 0.771139 +/- 0.005645 |
| Weighted-F1 | 0.757108 +/- 0.008691 | 0.763946 +/- 0.004537 |
| Subset accuracy | 0.773611 +/- 0.011369 | 0.760648 +/- 0.021621 |
| Hamming loss | 0.048688 +/- 0.002475 | 0.049769 +/- 0.003241 |
| Five-label Macro-F1 without surprise | 0.728756 +/- 0.015154 | 0.740705 +/- 0.013301 |

## Seed-Level Primary Results

| Seed | Epoch | Threshold | Fixed Macro-F1 | Shared Macro-F1 | Surprise F1 |
|---:|---:|---:|---:|---:|---:|
| 42 | 4 | 0.25 | 0.598759 | 0.604619 | 0.000000 |
| 43 | 4 | 0.30 | 0.601329 | 0.625341 | 0.000000 |
| 44 | 5 | 0.50 | 0.621803 | 0.621803 | 0.000000 |

## Boundary

This is a validation-only M1 result. It does not authorize test access, establish TEST-READY status, or support an M1-versus-M2 conclusion. The six-label Macro-F1 remains primary; the five-label value is a registered low-support sensitivity analysis.
