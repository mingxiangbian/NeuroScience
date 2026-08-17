# EXP-058 Attempt 2 Label-Vector Schema Correction

- Experiment ID: `EXP-058`
- Stage: `fold-manifest-preflight`
- Registered: 2026-08-16
- Attempt 1 status: `Failed before fold allocation`

## Observed Failure

Attempt 1 opened only the frozen train file and stopped at row-zero schema validation.
The builder expected `labels` to contain label names. The actual frozen
`DATA-SO-TASK-V1` schema stores a length-six binary vector whose positions follow:

```text
love, joy, surprise, anger, sadness, fear
```

No component assignment, model load, training, forward pass, logits, metric, calibration,
oracle, validation access, or test access occurred.

## Authorized Correction

Attempt 2 may change only label decoding and corresponding synthetic fixtures:

- require exactly six values, each an integer or Boolean equivalent to `0` or `1`;
- require `label_cardinality == sum(labels)`;
- require `neutral == (sum(labels) == 0)`;
- map vector positions to the already frozen label order for stratification;
- keep the private diagnostic manifest in the same six-bit vector form.

Fold count, component unit, seeds, gates, data hash, resource budget, public schema,
privacy boundary, and no-model/no-validation/no-test authorization remain unchanged.
