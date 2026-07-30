# EXP-009 Failure Note

Date: 2026-07-30

EXP-009 stopped while loading the first seed's model, before the first
optimization step and before validation inference. Transformers queried
`sys.stdout.isatty()` while `sys.stdout` was the experiment's `Tee` logger,
which did not yet implement that standard stream method.

Observed exception:

```text
AttributeError: 'Tee' object has no attribute 'isatty'
```

This is an implementation failure, not a model-performance result. No
hyperparameter or scientific-design change is justified by it. The retry is
registered as EXP-010 with the same data, model revision, training settings,
selection rule, and seeds; the only functional correction is standard-stream
compatibility in `Tee`.

Preserved evidence:

| Artifact | SHA-256 |
| --- | --- |
| `train_finetune_exp009_failed.py` | `31adaeca66f8634c234299bfc269529298f44bb695437b07651fa3a9a8415fe8` |
| `run.json` | `01fa9e42af72e6ddddf292a2fb526adfbe85f3ef6dafc4d084792b9ec6619e56` |
| `stdout.log` | `cec58df889b83ef5c06e5e65eb04ec37b77197ff6af5f2ee3e439846d9390f09` |

The original `run.json`, `stdout.log`, and source snapshot are append-only
failure evidence and must not be reused as a successful run directory.
