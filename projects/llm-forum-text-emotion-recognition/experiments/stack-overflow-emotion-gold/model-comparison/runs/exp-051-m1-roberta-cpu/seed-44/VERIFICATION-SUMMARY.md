# EXP-051 Seed 44 Verification Summary

Status: `Verified` on 2026-08-14. This is the third independently verified
train + validation seed. Test was not accessed.

## Result

| Measure | Fixed 0.5 | Shared threshold 0.50 |
| --- | ---: | ---: |
| Macro-F1 | 0.621803 | 0.621803 |
| Macro precision | 0.636286 | 0.636286 |
| Macro recall | 0.611401 | 0.611401 |
| Micro-F1 | 0.773903 | 0.773903 |
| Weighted-F1 | 0.763814 | 0.763814 |
| Strict subset accuracy | 0.783333 | 0.783333 |
| Hamming loss | 0.046528 | 0.046528 |
| Five-label Macro-F1 without surprise | 0.746163 | 0.746163 |

Epoch 5 was selected by the frozen fixed-threshold rule. The selected shared
threshold remained 0.50, so calibration did not change this seed's predictions.
The shared-threshold component-bootstrap Macro-F1 95% interval was
`[0.574086, 0.660818]` over 2,000 duplicate-component resamples. `surprise`
again had seven validation positives, zero predicted positives and F1 `0`.

## Verification And Boundary

The run used the unchanged EXP-051 scientific condition on CPU and completed
1,050 optimizer steps in 1,856.63 seconds with peak process RSS 5.36 GB. The
seed-44 contract froze its own authorization amendment and required the
unchanged, 72/72-verified seed-43 run and verification hashes as a prerequisite.

The independent verifier replayed the selected checkpoint and recomputed saved
probabilities, checkpoint and threshold selection, aggregate and per-label
metrics, component bootstrap, hashes, resource gates, split access and public
privacy. It passed `72/72` checks with no failed check and exact checkpoint
replay (`max_abs_error=0`).

After this verification, seeds 42, 43 and 44 were aggregated using the
pre-registered arithmetic mean and sample standard deviation. That separate
aggregate passed `53/53` independent checks. Stack Overflow test remains sealed,
and neither TEST-READY nor EXP-052 / M2 is authorized by this result.
