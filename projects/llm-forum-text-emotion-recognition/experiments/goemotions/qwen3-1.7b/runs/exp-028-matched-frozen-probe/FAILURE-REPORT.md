# EXP-028 Matched Frozen Probe Failure Report

Formal status: `Failed`

Artifact audit: `Passed`

Evidence eligibility: `Not eligible for Verified evidence`

## Question

在固定 `DATA-GOE-V1` train/dev、相同 token 流和相同线性 readout 下，
`Qwen3-1.7B-Base` 与 post-trained `Qwen3-1.7B` 的 final-layer mean-pooled
表征对 28 个 GoEmotions 标签是否具有不同的线性可解码性？

## Frozen Condition

- Train/dev rows: `43,410 / 5,426`
- Hidden representation: final transformer output after final RMSNorm and before the LM head
- Pooling: attention-mask-aware mean over non-padding token states
- Feature size: `2,048`
- Probe: 28 balanced one-vs-rest logistic regressions
- Solver: `liblinear`, `C=1`, threshold `0.5`, `n_jobs=1`
- Negative control: train-label shuffles with seeds `42`, `43`, and `44`
- Comparison: 10,000 paired bootstrap replicates on dev Macro-F1
- Probe wall-time limit: `240` minutes
- Test: not acquired or accessed

The frozen config SHA-256 is
`a932e62a1dbbd6d5cf0c46656b74043caedf63ddc488a578d0e5ac8a0ded4cea`.

## Execution Outcome

All four feature extractions completed:

- Base and post-trained used identical token-ID streams within train and dev.
- Feature shapes were `43,410 x 2,048` and `5,426 x 2,048` per condition.
- All vectors were finite, each extraction stayed below its 120-minute limit, and test remained
  absent.
- Total feature-extraction time was `3,576.307` seconds (`59.605` minutes).

All eight probe fits also converged and wrote predictions, metrics and private model bundles.
However, probe fitting and evaluation took `20,657.255` seconds (`344.288` minutes), exceeding
the frozen 240-minute limit by `6,257.255` seconds (`104.288` minutes). The fitter therefore
wrote `failure.json` and exited with `TimeoutError` before creating formal `run.json`.

The failed directory is preserved append-only. It must not be relabeled `Completed` or supplied
with a synthetic `run.json`.

## Diagnostic Results

These values were generated before the resource stop condition and were independently recomputed,
but they remain diagnostics from a failed run rather than Verified thesis evidence.

| Condition | Macro-F1 | Micro-F1 | Weighted-F1 | Subset accuracy | Max shuffled Macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base | 0.310534 | 0.385844 | 0.440400 | 0.100442 | 0.068491 |
| Post-trained | 0.306373 | 0.390750 | 0.442748 | 0.096203 | 0.068580 |

| Condition | Seed 42 | Seed 43 | Seed 44 | Mean |
| --- | ---: | ---: | ---: | ---: |
| Base shuffled labels | 0.068491 | 0.064154 | 0.066132 | 0.066259 |
| Post-trained shuffled labels | 0.068580 | 0.063694 | 0.067468 | 0.066581 |

The real probes exceeded their condition's maximum shuffled-label Macro-F1 by `0.242043` for
Base and `0.237793` for post-trained, well above the frozen `0.02` validity margin.

The paired diagnostic comparison was:

- Post-trained minus Base Macro-F1: `-0.004161`
- 95% percentile bootstrap interval: `[-0.013156, 0.004711]`
- Frozen practical threshold: `0.005`
- Diagnostic outcome: `practical_tie`

If reproduced in a valid formal run, this pattern would support two limited statements: both
checkpoints contain linearly recoverable label information under this readout, and post-training
does not show a meaningful increase in final-layer linear decodability. It would not establish an
emotion-recognition mechanism, human-like processing, or absence of changes at other layers.

## Failure Artifact Audit

`audit_failed_frozen_probe.py` independently checked the preserved failed run and wrote
`failed-run-manifest.json` plus `failed-artifact-verification.json`.

- Private feature files checked: `4`
- Private probe model files checked: `8`
- Public source files checked: `25`
- Maximum probability difference: `0`
- Maximum metric or bootstrap difference: `0`
- Maximum per-label CSV difference: `4.98e-13` from decimal formatting
- Base/post-trained token streams: identical within each split
- Test present/accessed: `no / no`

The audit establishes artifact integrity only. It intentionally records
`source_experiment_status: Failed` and does not make EXP-028 eligible for `evidence-log.md`.

## Required Follow-up

A formal claim requires a new experiment ID and explicit review. The successor must preserve the
EXP-028 failure and freeze one transparent recovery policy before execution, such as an exact
technical repeat with a realistic wall-time budget or a pre-registered audit of the immutable
EXP-028 model bundles. No successor may change labels, threshold, layer, pooling or comparison
rules in response to these diagnostic scores.

