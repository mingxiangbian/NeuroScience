# EXP-058 Fold Manifest Preflight Attempt 1

- Status: `Failed before allocation`
- Cause: the preflight assumed `labels` was a list of label names, while the frozen
  `DATA-SO-TASK-V1` private train schema stores a six-position binary vector in the
  documented label order.
- Data access: train only.
- Models/training/forward passes: none.
- Fold, logits, metrics, calibration, oracle, router, validation, and test artifacts:
  none.

The empty private attempt directory is retained. Attempt 2 is permitted only after the
schema correction is registered and its source/config hashes are frozen.
