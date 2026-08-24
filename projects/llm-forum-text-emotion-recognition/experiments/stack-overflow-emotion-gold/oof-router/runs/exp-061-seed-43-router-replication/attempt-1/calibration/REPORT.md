# EXP-059 Cross-Fitted Calibration And Selective Prediction

## Scope

This report uses only the frozen seed-43 paired train-OOF artifact from EXP-061. Validation and test were not accessed.
Temperature adoption is diagnostic only for this seed; EXP-060 replication uses identity probabilities computed directly from raw OOF logits (`T=1`).

## Calibration

| Family | Raw NLL | Temperature NLL | Raw Brier | Temperature Brier | Selected calibrator | Final T |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| M1 | 0.138220 | 0.138260 | 0.037186 | 0.037206 | identity | 1.000000 |
| M3 | 0.123393 | 0.123008 | 0.034462 | 0.034420 | temperature | 1.075725 |

## Selected Classification

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Hamming loss | Subset accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | 0.581024 | 0.697229 | 0.760768 | 0.050694 | 0.763690 |
| M3 | 0.602394 | 0.700650 | 0.748311 | 0.059127 | 0.703274 |

## Abstention Gates

- M1: Passed at 0.90 target coverage with `max_entropy`; Hamming-risk relative reduction `0.213133`.
- M3: Passed at 0.80 target coverage with `max_entropy`; Hamming-risk relative reduction `0.304209`.

## Router Headroom Diagnostic

- M3 selection rate: `0.082440`
- Six-label Macro-F1 gain over M1: `0.090669`
- Five-label Macro-F1 gain over M1: `0.108803`
- Preliminary EXP-060 headroom gate: `True`

This is a non-deployable whole-vector oracle and is not a learned-router result.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. They are train-OOF development intervals and do not replace an independent test.

## Claim Boundary

EXP-059 can support claims about the frozen seed-43 pair's cross-fitted calibration and selective-risk ranking. It does not support a new test result, a three-seed stability claim, deployment benefit, context benefit, or an internal emotion mechanism.
