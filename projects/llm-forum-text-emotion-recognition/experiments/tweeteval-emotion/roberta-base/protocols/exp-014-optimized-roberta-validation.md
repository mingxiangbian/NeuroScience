# EXP-014 Protocol: Optimized Plain RoBERTa Validation

Registration date: 2026-07-30

This protocol is frozen before EXP-014 opens the official validation files or
produces any EXP-014 validation prediction. EXP-011 has previously evaluated
the same validation split, but EXP-014's only changed condition was selected
without consulting validation: EXP-012 and EXP-013 used a fixed inner split
constructed exclusively from the official training split.

## Registration

- Tier: Major
- RQ: RQ-B2
- Parent experiment: EXP-011
- Selection experiments: EXP-012 and EXP-013
- Stage: formal optimized plain-RoBERTa validation
- Dataset: TweetEval emotion
- Allowed splits: official train and validation only
- Prohibited split: test
- Frozen config:
  `configs/exp-014-optimized-roberta-validation.json`
- Frozen config SHA-256:
  `9131f9d633fe9b3197278603aec43b46b5a160b5da55b4de979a244ca1106c37`

Any functional change after this registration requires a new experiment ID.

## Research Question

When all other conditions are held equal to EXP-011, does label smoothing
selected on train-only data improve the three-seed official-validation
Macro-F1 of plain `FacebookAI/roberta-base`?

Expected outcome: mean validation Macro-F1 exceeds EXP-011 by at least
`0.005`, with a positive paired difference in at least two of three seeds.

Negative outcome: if the threshold is not reached, the train-only improvement
did not transfer reliably to the official validation split. EXP-014 remains a
valid negative result; its outcome must not trigger further tuning against the
same validation split.

## Train-Only Selection Evidence

EXP-012 screened raw text versus the TweetEval mention/URL normalization and
the three hyperparameters published with the official CardiffNLP run. Raw text
with the existing EXP-011 training settings was retained. The normalization
and published hyperparameter trio did not improve the fixed inner-validation
split.

EXP-013 then screened one-factor regularization changes. On the same fixed
train-only split:

| Candidate | Mean Macro-F1 | Sample SD |
| --- | ---: | ---: |
| EXP-011 control | `0.786472` | `0.005159` |
| Weight decay `0.05` | `0.789304` | `0.008837` |
| Label smoothing `0.05` | `0.795601` | `0.003187` |

Label smoothing improved the mean by `0.009129` and beat the paired control in
all three runs, although the seed-44 difference (`0.002500`) was below the
`0.005` practical threshold. It was therefore selected under the registered
rule requiring at least `0.005` mean improvement and positive differences in
at least two matched seeds.

Selection metadata:

- EXP-012 run SHA-256:
  `dcdab2adda399adaaf3d05ede9b47258aefbd1ae533a79cee84741b3f6645abc`
- EXP-013 run SHA-256:
  `8f64d46353df73c0ac84f7d57253af6685304308eca2825364c8172a9342a9b5`

Repeated MPS runs with the same nominal seed differed by approximately
`0.005` Macro-F1 during screening. EXP-014 therefore reports all seeds and
does not treat a borderline single-run difference as decisive.

## Data Contract

Upstream commit:
`4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66`

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `mapping.txt` | 4 | `656dea85d149716af96206ca19bec0d94e9dc6de3f5079f5c7c2a241ec76cadb` |
| `train_text.txt` | 3,257 | `2c62f67aeb3eac1aea0e5a9c3d0f4bc337992581f3f858061786a1fb4d79d95e` |
| `train_labels.txt` | 3,257 | `987e767d8679e18abdf7de37a6d2bcd0a40a296ddd704e8d515cf0e3033c8d9c` |
| `val_text.txt` | 374 | `e2e30c86b8cbb97944d6543aedc06eace3bb275cb2f381aba787b838b4f23ca5` |
| `val_labels.txt` | 374 | `313730630160b7e0a6b4235b800c76683f4aeeb72d094eb69646630cd5cfe338` |

Label order is fixed as `anger`, `joy`, `optimism`, `sadness`. Raw text is
used without mention or URL normalization. The runner uses an explicit
allowlist and rejects any path containing `test`.

## Model and Tokenization

- Base model: `FacebookAI/roberta-base`
- Revision: `e2da8e2f811d1448a5b465c236feacd80ffbac7b`
- Local snapshot only; network access disabled
- Model manifest SHA-256:
  `b6e508ca9783b9e79e3cfc445f3abc7d2792ac5cfa6f44a9b3cf5d5607cd30b6`
- Head: newly initialized four-class sequence-classification head
- Maximum sequence length: 128 tokens
- Truncation: enabled
- Padding: dynamic per batch
- Class weighting: none

## Frozen Training Configuration

| Setting | Value |
| --- | --- |
| Seeds | 42, 43, 44 |
| Epochs | 5 |
| Train batch size | 16 |
| Evaluation batch size | 32 |
| Gradient accumulation | 1 |
| Optimizer | AdamW (`adamw_torch`) |
| Learning rate | `2e-5` |
| Weight decay | `0.01` |
| Label smoothing | `0.05` |
| Scheduler | linear |
| Warmup ratio | `0.1` |
| Maximum gradient norm | `1.0` |
| Mixed precision | disabled |
| Evaluation and save cadence | every epoch |
| Retained checkpoints | one best checkpoint per seed |

The only scientific-condition change from EXP-011 is label smoothing from
`0.0` to `0.05`.

## Selection and Metrics

Primary metric: validation Macro-F1.

For each seed, retain the epoch with maximum validation Macro-F1. An exact tie
keeps the earlier checkpoint. Aggregate results use the mean and sample
standard deviation across all three seeds.

A practical improvement claim requires:

```text
mean(EXP-014 validation Macro-F1)
- mean(EXP-011 validation Macro-F1) >= 0.005
```

The paired per-seed differences must also be reported. This threshold is a
practical comparison rule, not a statistical-significance claim.

Required secondary outputs:

- Accuracy, macro precision/recall, and weighted F1.
- Per-class precision, recall, F1, and support.
- Rows-true, columns-predicted confusion matrix for every seed.
- Selected-checkpoint train diagnostic metrics, not used for selection.
- Per-epoch history and per-row validation predictions with probabilities.
- Config, protocol, model, data, environment, runner, and prediction hashes.

## Frozen Comparison

EXP-011 run metadata SHA-256:
`8ca285f136ade51db62c387a45a34c3f89d4b31344863f43bbab5a4593b8dd7c`

- Mean validation Macro-F1: `0.732804`
- Sample SD: `0.005007`
- Mean validation Accuracy: `0.792335`
- Sample SD: `0.004084`

The official TweetEval test result is contextual literature evidence only. It
is not used for EXP-014 selection or evaluation.

## Artifacts and Verification

The append-only run directory is:

```text
runs/exp-014-optimized-roberta-validation/
```

It must contain `run.json`, `stdout.log`, three per-seed metric/history/
prediction/confusion-matrix bundles, and one selected checkpoint per seed. A
separate verifier must recompute metrics and hashes into `verification.json`.

Raw text is not written to tracked artifacts.

## Resource Budget

- Maximum seed runs: 3
- Maximum retained checkpoints: 3
- Maximum wall time: 120 minutes
- API cost: USD 0
- Device: local Apple MPS

An unexpected path, model/input hash mismatch, NaN/OOM, or budget overrun stops
the run and preserves the partial metadata.

## Thesis Destination

- Results: whether train-only regularization transfers to official validation.
- Methods: nested selection boundary and frozen three-seed comparison.
- Limitations: MPS nondeterminism and the small official validation set.
- Appendix: seed-level metrics, confusion matrices, run hashes, and negative
  screening results.

Test remains behind the project TEST-READY gate.
