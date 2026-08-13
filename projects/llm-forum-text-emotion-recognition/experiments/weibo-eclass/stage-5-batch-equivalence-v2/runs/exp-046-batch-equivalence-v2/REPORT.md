# EXP-046 Batch-Equivalence Gate

Status: `Completed; awaiting independent verification`

This train-only Minor experiment computed no classification performance and did not access validation/test.

| Comparison | Final-label agreement | Raw-output agreement |
| --- | ---: | ---: |
| singleton_replay | 16/16 (1.000) | 16/16 (1.000) |
| batch8_replay | 16/16 (1.000) | 16/16 (1.000) |
| batch8_composition | 14/16 (0.875) | 5/16 (0.312) |
| singleton_vs_batch8 | 15/16 (0.938) | 0/16 (0.000) |

## Frozen Decision

- Gate: `Passed`
- Recommended execution protocol: `singleton`
- Requirement: batch_size=completion_batch_size=prefill_batch_size=1
- Requirement: repeat the train-only replay after each adapter is trained and before dev access

## Boundary

The result concerns runtime reproducibility only. It does not show that reasoning improves emotion recognition,
does not validate generated reasoning as faithful, and does not authorize Stage 5 training or test access.
