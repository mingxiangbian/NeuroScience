# EXP-062 Pre-Qwen Deployable Router

- Decision: `Pass`
- Selected policy: `logistic_router`
- Evidence scope: fully nested DATA-SO-TASK-V1 train OOF only.
- Validation/test/raw text/model forward access: `false`.

## Frozen policy candidates

- `m1_max_entropy`: passed=`False`, actual call rate=`0.150298`, Macro-F1 gain=`+0.085685`.
- `m1_threshold_proximity`: passed=`False`, actual call rate=`0.145536`, Macro-F1 gain=`+0.058366`.
- `logistic_router`: passed=`True`, actual call rate=`0.150893`, Macro-F1 gain=`+0.086036`.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. 
Point estimates determine the development gate; intervals qualify stability only.

## Claim boundary

This is train-OOF evidence for the frozen seed-44 model pair. It is not an independent-test deployment result, a completed cross-seed claim, or evidence of an emotion mechanism.
