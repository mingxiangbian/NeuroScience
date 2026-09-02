# EXP-061 Pre-Qwen Deployable Router

- Decision: `Pass`
- Selected policy: `logistic_router`
- Evidence scope: fully nested DATA-SO-TASK-V1 train OOF only.
- Validation/test/raw text/model forward access: `false`.

## Frozen policy candidates

- `m1_max_entropy`: passed=`False`, actual call rate=`0.152381`, Macro-F1 gain=`+0.030536`.
- `m1_threshold_proximity`: passed=`False`, actual call rate=`0.153571`, Macro-F1 gain=`+0.027599`.
- `logistic_router`: passed=`True`, actual call rate=`0.147321`, Macro-F1 gain=`+0.030883`.

## Uncertainty

All intervals use `2000` duplicate-component bootstrap replicates. 
Point estimates determine the development gate; intervals qualify stability only.

## Claim boundary

This is train-OOF evidence for the frozen seed-43 model pair. It is not an independent-test deployment result, a completed cross-seed claim, or evidence of an emotion mechanism.
