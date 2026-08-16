# EXP-051 Seed 43 Verification Summary

Status: `Verified` on 2026-08-13. This is the second independently verified
train + validation seed, not the registered three-seed M1 result. Test was not
accessed.

## Result

| Measure | Fixed 0.5 | Shared threshold 0.30 |
| --- | ---: | ---: |
| Macro-F1 | 0.601329 | 0.625341 |
| Macro precision | 0.619957 | 0.594737 |
| Macro recall | 0.591685 | 0.662328 |
| Micro-F1 | 0.769401 | 0.774869 |
| Weighted-F1 | 0.760219 | 0.768547 |
| Strict subset accuracy | 0.776389 | 0.758333 |
| Hamming loss | 0.048148 | 0.049769 |
| Five-label Macro-F1 without surprise | 0.721595 | 0.750409 |

Epoch 4 was selected by the frozen fixed-threshold rule. The shared-threshold
component-bootstrap Macro-F1 95% interval was `[0.580438, 0.661573]` over 2,000
duplicate-component resamples. `surprise` again had seven validation positives,
zero predicted positives and F1 `0`; the rare-label failure is therefore not
specific to seed 42.

## Verification And Boundary

The run used the same frozen scientific condition as seed 42 on CPU and
completed 1,050 optimizer steps in 1,933.45 seconds with peak process RSS
5.24 GB. The seed-43 contract independently froze its authorization amendment
and required the unchanged, 67/67-verified seed-42 artifacts as a prerequisite.

The independent verifier replayed the selected checkpoint and recomputed saved
probabilities, checkpoint and threshold selection, aggregate and per-label
metrics, component bootstrap, hashes, resource gates, split access, Git ignore
and public privacy. It passed `72/72` checks with no failed check and exact
checkpoint replay (`max_abs_error=0`). Seed 44 remains unauthorized, and Stack
Overflow test remains sealed.

Across seeds 42 and 43 only, the calibrated Macro-F1 descriptive mean and sample
standard deviation are `0.614980 +/- 0.014652`. This two-seed diagnostic is not
the pre-registered three-seed aggregate and must not be reported as the final M1
result.
