# EXP-051 Seed 43 Authorization Amendment

- Experiment: `EXP-051`
- Authorized seed: `43`
- Authorized splits: `train`, `validation`
- Test access: not authorized
- Seed 44: not authorized
- Authorization date: 2026-08-13

## Basis

The user's instruction to proceed to the next step authorizes one formal seed-43
train and validation run after the completed seed-42 integrity gate. Seed 42 was
independently verified with 67 of 67 checks passed and no test access.

## Scientific Invariance

This amendment changes staged execution authorization only. The frozen
`EXP-051` scientific protocol remains unchanged: the same train and validation
files, model revision, six-label head, loss, optimizer, schedule, five epochs,
checkpoint-selection rule, threshold grid, metrics and bootstrap procedure are
used. CPU is retained as the registered execution backend because the seed-42
MPS attempt exceeded unified memory, while the matching CPU recovery completed
within the registered resource budget.

Seed 43 remains a validation result. It does not authorize seed 44, access to
the test split, a three-seed aggregate, or any test-ready claim.
