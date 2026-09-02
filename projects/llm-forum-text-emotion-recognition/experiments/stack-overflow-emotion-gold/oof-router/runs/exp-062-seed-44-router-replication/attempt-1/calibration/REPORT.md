# EXP-059 Cross-Fitted Calibration And Selective Prediction

## Scope

This report uses only the frozen seed-44 paired train-OOF artifact from EXP-062. Validation and test were not accessed.
Temperature adoption is diagnostic only for this seed; EXP-060 replication uses identity probabilities computed directly from raw OOF logits (`T=1`).

## Calibration

| Family | Raw NLL | Temperature NLL | Raw Brier | Temperature Brier | Selected calibrator | Final T |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| M1 | 0.140435 | 0.140451 | 0.037920 | 0.037911 | identity | 1.000000 |
| M3 | 0.125877 | 0.124047 | 0.034961 | 0.034679 | temperature | 1.181793 |

## Selected Classification

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Hamming loss | Subset accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | 0.573741 | 0.688489 | 0.754083 | 0.052282 | 0.759821 |
| M3 | 0.657633 | 0.710372 | 0.764667 | 0.052331 | 0.745536 |

## Abstention Gates

- M1: Failed; no preregistered operating point qualified.
- M3: Passed at 0.80 target coverage with `margin`; Hamming-risk relative reduction `0.300284`.

## Router Headroom Diagnostic

- M3 selection rate: `0.097321`
- Six-label Macro-F1 gain over M1: `0.185691`
- Five-label Macro-F1 gain over M1: `0.118068`
- Preliminary EXP-060 headroom gate: `True`

This is a non-deployable whole-vector oracle and is not a learned-router result.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. They are train-OOF development intervals and do not replace an independent test.

## Claim Boundary

EXP-059 can support claims about the frozen seed-44 pair's cross-fitted calibration and selective-risk ranking. It does not support a new test result, a three-seed stability claim, deployment benefit, context benefit, or an internal emotion mechanism.
