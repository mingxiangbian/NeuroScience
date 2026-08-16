# EXP-053 M3 Three-Seed Validation Aggregate

- Status: `Completed; pending independent aggregate verification`
- Seeds: `42, 43, 44`
- Source splits: `train`, `validation`
- Test access: `false`
- Center / dispersion: arithmetic mean / sample standard deviation (`ddof=1`)
- Predictions pooled across seeds: `false`

| Metric | Fixed 0.5 | Per-seed shared threshold |
|---|---:|---:|
| Six-label Macro-F1 | 0.620325 +/- 0.033829 | 0.654032 +/- 0.014135 |
| Micro-F1 | 0.737308 +/- 0.008745 | 0.759575 +/- 0.003674 |
| Weighted-F1 | 0.727342 +/- 0.016130 | 0.755704 +/- 0.003472 |
| Strict subset accuracy | 0.746296 +/- 0.011312 | 0.750463 +/- 0.007649 |
| Hamming loss | 0.050849 +/- 0.001395 | 0.050926 +/- 0.000802 |
| Five-label Macro-F1 without surprise | 0.673851 +/- 0.026204 | 0.706724 +/- 0.013816 |

## Seed-Level Primary Results

| Seed | Epoch | Threshold | Fixed Macro-F1 | Shared Macro-F1 | Surprise F1 |
|---:|---:|---:|---:|---:|---:|
| 42 | 2 | 0.40 | 0.602846 | 0.637786 | 0.363636 |
| 43 | 2 | 0.35 | 0.659318 | 0.663515 | 0.444444 |
| 44 | 2 | 0.25 | 0.598812 | 0.660795 | 0.363636 |

## Matched M3 Minus M2

| Metric | Fixed 0.5 delta | Per-seed shared-threshold delta |
|---|---:|---:|
| Six-label Macro-F1 | 0.468773 +/- 0.053535 | 0.335143 +/- 0.041168 |
| Micro-F1 | 0.328358 +/- 0.058125 | 0.245506 +/- 0.025367 |
| Weighted-F1 | 0.395548 +/- 0.035834 | 0.273418 +/- 0.050968 |
| Strict subset accuracy | 0.186111 +/- 0.034134 | 0.259722 +/- 0.036191 |
| Hamming loss | -0.036420 +/- 0.000744 | -0.070216 +/- 0.006953 |
| Five-label Macro-F1 without surprise | 0.491988 +/- 0.056539 | 0.324057 +/- 0.054925 |

## Seed-Matched Descriptive M3 Minus M1

| Metric | Fixed 0.5 delta | Per-seed shared-threshold delta |
|---|---:|---:|
| Six-label Macro-F1 | 0.013028 +/- 0.041224 | 0.036778 +/- 0.003154 |
| Micro-F1 | -0.028962 +/- 0.018241 | -0.011564 +/- 0.006039 |
| Weighted-F1 | -0.029765 +/- 0.022971 | -0.008242 +/- 0.001563 |
| Strict subset accuracy | -0.027315 +/- 0.021621 | -0.010185 +/- 0.028945 |
| Hamming loss | 0.002160 +/- 0.003834 | 0.001157 +/- 0.003956 |
| Five-label Macro-F1 without surprise | -0.054905 +/- 0.031217 | -0.033981 +/- 0.008620 |

## M3 Resources

- Wall time: 12860.694275 +/- 850.093707 seconds
- Peak MLX memory: 8.701082 +/- 0.001801 GB
- API cost: 0.000000 +/- 0.000000 USD

## Boundary

This is a validation-only M3 family result. No row-level predictions were read or pooled. Shared-threshold comparisons use each model's already frozen validation operating point; fixed 0.5 is the calibration-independent companion. M3-minus-M2 and M3-minus-M1 values are descriptive for three seed-matched runs; no p-value, confidence interval, or significance claim is authorized. M3 resources are summarized only within the homogeneous M3 execution path and are not a cross-model cost comparison. Surprise has seven validation positives, so its stability remains uncertain. Test, TEST-READY, EXP-054 and error analysis remain sealed.
