# EXP-010 Failure Note

Date: 2026-07-30

EXP-010 stopped at the pre-data environment gate because the restricted Codex
process could not expose Apple MPS to PyTorch.

Observed exception:

```text
RuntimeError: MPS is unavailable in this process
```

No dataset file was opened, no optimization step occurred, and no validation
prediction or performance metric was produced. This is an execution-context
failure, not a model-performance result.

EXP-011 retries the unchanged scientific configuration outside the restricted
process so the already verified local MPS device is available. No training
logic or hyperparameter changes are permitted.

Preserved evidence:

| Artifact | SHA-256 |
| --- | --- |
| `train_finetune_exp010_failed.py` | `f5ae5859fa56c0c21af5370b629670bd6418ae6d32f4db8f699bec5969fd89fd` |
| `run.json` | `7d4e1dd1371119a041d79081661653b8ef81f39453d919ea88c80919a5b00f77` |
| `stdout.log` | `6c4356550f8be8f0601a060fe14303b542fa33522d2564197723cb8c061a8513` |

The original failure artifacts and source snapshot are append-only.
