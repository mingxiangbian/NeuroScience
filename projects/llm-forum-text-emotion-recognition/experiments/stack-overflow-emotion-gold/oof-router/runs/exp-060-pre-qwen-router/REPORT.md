# EXP-060 Pre-Qwen Deployable Router

- Decision: `Pass`
- Selected policy: `logistic_router`
- Evidence scope: fully nested DATA-SO-TASK-V1 train OOF only.
- Validation/test/raw text/model forward access: `false`.

## Frozen policy candidates

- `m1_max_entropy`: passed=`True`, actual call rate=`0.100000`, Macro-F1 gain=`+0.027972`.
- `m1_threshold_proximity`: passed=`True`, actual call rate=`0.141667`, Macro-F1 gain=`+0.026272`.
- `logistic_router`: passed=`True`, actual call rate=`0.149107`, Macro-F1 gain=`+0.040168`.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. 
Point estimates determine the development gate; intervals qualify stability only.

## Claim boundary

This is train-OOF development evidence for one frozen seed-42 model pair. It is not an 
independent-test deployment result, a cross-seed claim, or evidence of an emotion mechanism.
