# EXP-051 M1 Three-Seed Validation Verification Summary

Status: `Verified` on 2026-08-14. This freezes the registered M1 validation
family for seeds 42, 43 and 44. It is not a test result.

## Aggregate Result

Values are arithmetic mean +/- sample standard deviation across the three
independently trained seeds.

| Measure | Fixed 0.5 | Per-seed shared threshold |
| --- | ---: | ---: |
| Six-label Macro-F1 | 0.607297 +/- 0.012628 | 0.617254 +/- 0.011084 |
| Micro-F1 | 0.766270 +/- 0.009590 | 0.771139 +/- 0.005645 |
| Weighted-F1 | 0.757108 +/- 0.008691 | 0.763946 +/- 0.004537 |
| Strict subset accuracy | 0.773611 +/- 0.011369 | 0.760648 +/- 0.021621 |
| Hamming loss | 0.048688 +/- 0.002475 | 0.049769 +/- 0.003241 |
| Five-label Macro-F1 without surprise | 0.728756 +/- 0.015154 | 0.740705 +/- 0.013301 |

| Seed | Selected epoch | Shared threshold | Fixed Macro-F1 | Shared Macro-F1 |
| ---: | ---: | ---: | ---: | ---: |
| 42 | 4 | 0.25 | 0.598759 | 0.604619 |
| 43 | 4 | 0.30 | 0.601329 | 0.625341 |
| 44 | 5 | 0.50 | 0.621803 | 0.621803 |

Shared-threshold selection increased the descriptive mean Macro-F1 by
`0.009957`, but strict subset accuracy decreased by `0.012963` and Hamming loss
increased by `0.001080`. It is therefore a tradeoff, not a uniform improvement.
All three seeds predicted zero `surprise` positives from seven validation
positives, so `surprise` F1 was `0` throughout. The five-label value is retained
only as the registered low-support sensitivity analysis; the six-label
Macro-F1 remains primary.

## Verification And Boundary

The aggregate binds the exact public `run.json` and `verification.json` hashes
for all three seeds. It does not pool row-level predictions across seeds. An
independent implementation recomputed the mean and sample standard deviation,
checked every source hash and verification gate, and passed `53/53` checks.

This result freezes M1 on validation. It does not authorize Stack Overflow test
access, establish TEST-READY status, or support an M1-versus-M2 conclusion.
EXP-052 / M2 requires a separate protocol authorization and must use the same
frozen train/validation task before any model comparison is made.
