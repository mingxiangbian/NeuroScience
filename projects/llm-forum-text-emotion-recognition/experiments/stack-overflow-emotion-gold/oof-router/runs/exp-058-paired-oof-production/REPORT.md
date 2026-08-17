# EXP-058 Paired M1-M3 Train OOF Production Report

## Experiment Identity

- Experiment: `EXP-058`
- Research question: `RQ-S3`
- Tier: Major infrastructure experiment
- Stage: paired M1/M3 out-of-fold (OOF) production
- Evidence status: `Verified`
- Final verification: `26,989 / 26,989 Passed`

## Purpose

This experiment generated leakage-controlled, row-aligned train OOF raw logits for the
M1 RoBERTa encoder and M3 Qwen Classification LoRA. These logits are the training-only
input required by a later calibration, selective-prediction, and deployable-router
experiment.

EXP-058 was not a performance comparison. It did not select thresholds, calculate
classification metrics, run an oracle, train a router, or access validation or test.

## Frozen Contract

- Dataset: `DATA-SO-TASK-V1` train split only
- Rows: `3,360`
- Duplicate components: `3,277`
- Folds: five shared M1/M3 folds of `672` held-out rows each
- Training rows per fold: `2,688`
- Assignment seed: `20260816`
- Canonical model seed: `42`
- Component leakage: `0`
- `surprise` support by held-out fold: `6 / 6 / 6 / 7 / 6`
- Public fold-manifest SHA-256:
  `82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8`

Both model families consumed the same held-out row order. Each train row therefore has
one M1 logit vector and one M3 logit vector produced by models that did not train on
that row.

## Execution Summary

| Family | Fold | Optimizer steps | Final train loss | Wall time (h) | Peak memory (GB) | Fold verification |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| M1 | 0 | 672 | 0.097104 | 0.329 | 5.273 RSS | 53/53 |
| M1 | 1 | 672 | 0.097960 | 0.329 | 5.169 RSS | 53/53 |
| M1 | 2 | 672 | 0.093137 | 0.330 | 5.135 RSS | 53/53 |
| M1 | 3 | 672 | 0.094602 | 0.321 | 5.353 RSS | 53/53 |
| M1 | 4 | 672 | 0.096961 | 0.321 | 5.543 RSS | 53/53 |
| M3 | 0 | 5,376 | 0.134212 | 2.474 | 8.721 MLX | 48/48 |
| M3 | 1 | 5,376 | 0.125331 | 2.444 | 8.732 MLX | 48/48 |
| M3 | 2 | 5,376 | 0.120601 | 2.805 | 8.730 MLX | 48/48 |
| M3 | 3 | 5,376 | 0.124296 | 1.957 | 8.730 MLX | 48/48 |
| M3 | 4 | 5,376 | 0.119190 | 1.894 | 8.726 MLX | 48/48 |

M1 used the frozen four-epoch selected-stop rule. M3 used two complete epochs with
gradient checkpointing. All recorded losses and logits were finite. The losses are
training-health records only and must not be interpreted as comparative performance.

Resource totals:

- M1 wall time: `5,865.660 s` (`1.629 h`)
- M3 wall time: `41,668.653 s` (`11.575 h`)
- Combined model wall time: `47,534.313 s` (`13.204 h`)
- API cost: `$0`

Fold 2 experienced a machine sleep/network interruption in calendar time. The process
and checkpoints remained intact, and its independently recorded effective run,
held-out output, and fold verification all completed without restart.

## Paired Artifact

- Paired rows: `3,360`
- M1 finite logit values: `20,160`
- M3 finite logit values: `20,160`
- Source-order SHA-256:
  `c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3`
- Private paired artifact SHA-256:
  `e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc`
- Public paired summary SHA-256:
  `fb6d89f45537b31febcf76afa329d3daadd36aa9ab694cd25b44c0701b6527ae`

The row-level labels, identifiers, and logits remain in the Git-ignored private tree.
The public run contains aggregate metadata and hashes only.

## Verification And Incident

All five M1 folds passed `53/53` independent checks and all five M3 folds passed
`48/48`, for `505/505` fold-level checks. Final assembly verification passed
`26,989/26,989` checks.

The first final-verification attempt passed `26,984/26,989` checks and detected that
the five intermediate private `fold-N` directories were mode `0755` instead of
`0700`. The failed report and its hashes were preserved. Remediation changed only
those five directory modes; no model, checkpoint, label, logit, row order, or paired
artifact was regenerated. The paired artifact hash remained unchanged before and
after remediation.

## Result And Claim Boundary

**Verified result:** a complete, component-disjoint, train-only paired M1/M3 OOF table
now exists for every `DATA-SO-TASK-V1` training row.

**Not established:** which model is more accurate on these rows, whether either model
is calibrated, whether abstention improves risk, whether an oracle has useful
headroom, or whether a pre-Qwen router can outperform the best single model at a
controlled call rate.

The next admissible step is a separately registered EXP-059 calibration and selective
prediction experiment. It must consume the frozen paired artifact read-only and remain
within the train-OOF boundary until its own protocol authorizes any other split.

