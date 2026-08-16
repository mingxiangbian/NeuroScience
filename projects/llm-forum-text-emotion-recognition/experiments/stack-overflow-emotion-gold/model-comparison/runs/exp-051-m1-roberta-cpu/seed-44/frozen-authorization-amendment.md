# EXP-051 Seed 44 Authorization Amendment

- Experiment: `EXP-051`
- Authorized seed: `44`
- Authorized splits: `train`, `validation`
- Test access: not authorized
- Three-seed validation aggregation: authorized after independent seed-44 verification
- EXP-052 / M2: not authorized
- Authorization date: 2026-08-14

## Basis

The user's instruction to proceed to the next step authorizes one formal seed-44
train and validation run after the completed seed-43 integrity gate. Seed 43 was
independently verified with 72 of 72 checks passed and no test access.

## Scientific Invariance

This amendment changes staged execution authorization only. The frozen
`EXP-051` scientific protocol remains unchanged: the same train and validation
files, model revision, six-label head, loss, optimizer, schedule, five epochs,
checkpoint-selection rule, threshold grid, metrics and bootstrap procedure are
used. CPU remains the registered recovery backend, matching the verified seed-42
and seed-43 scientific execution contracts.

After seed 44 passes independent verification, the three verified validation
runs for seeds 42, 43 and 44 may be aggregated using the protocol's pre-registered
arithmetic mean and sample standard deviation. The aggregation must preserve both
fixed-0.5 and selected shared-threshold metrics and must report the low-support
`surprise` result rather than excluding it from the primary six-label metric.

This amendment does not authorize test access, a TEST-READY claim, EXP-052 / M2,
or comparison conclusions involving models that have not yet been run.
