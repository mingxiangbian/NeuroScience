# EXP-059 Cross-Fitted Calibration And Selective Prediction

## Scope

This report uses only the frozen EXP-058 paired train-OOF artifact. Validation and test were not accessed.

## Calibration

| Family | Raw NLL | Temperature NLL | Raw Brier | Temperature Brier | Selected calibrator | Final T |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| M1 | 0.144015 | 0.144052 | 0.038666 | 0.038641 | identity | 1.000000 |
| M3 | 0.127263 | 0.127689 | 0.035514 | 0.035555 | identity | 1.000000 |

## Selected Classification

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Hamming loss | Subset accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | 0.598919 | 0.718703 | 0.762081 | 0.051042 | 0.761607 |
| M3 | 0.637843 | 0.710509 | 0.765455 | 0.050248 | 0.754762 |

## Abstention Gates

- M1: Passed at 0.90 target coverage with `max_entropy`; Hamming-risk relative reduction `0.200135`.
- M3: Passed at 0.80 target coverage with `margin`; Hamming-risk relative reduction `0.315662`.

## Router Headroom Diagnostic

- M3 selection rate: `0.093155`
- Six-label Macro-F1 gain over M1: `0.109930`
- Five-label Macro-F1 gain over M1: `0.087472`
- Preliminary EXP-060 headroom gate: `True`

This is a non-deployable whole-vector oracle and is not a learned-router result.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. They are train-OOF development intervals and do not replace an independent test.

## Claim Boundary

EXP-059 can support claims about the frozen seed-42 pair's cross-fitted calibration and selective-risk ranking. It does not support a new test result, a three-seed stability claim, deployment benefit, context benefit, or an internal emotion mechanism.
