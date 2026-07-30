# EXP-015 Protocol: Twitter-Domain RoBERTa Base Comparison

Registration date: 2026-07-30

This protocol is frozen before EXP-015 opens the official validation files or
produces any EXP-015 prediction. EXP-014's result is known and is the frozen
comparison. No EXP-015 hyperparameter, preprocessing, or model-selection
decision may be changed after validation is read.

## Registration

- Tier: Major
- RQ: RQ-B3
- Parent experiment: EXP-014
- Stage: formal Twitter-domain-pretraining comparison
- Dataset: TweetEval emotion
- Allowed splits: official train and validation only
- Prohibited split: test
- Frozen config:
  `configs/exp-015-twitter-roberta-base-validation.json`
- Frozen config SHA-256:
  `a31aa206de492c32f76e6c1c9caaa290ac5b11b9a5579e7ba92737856d28cf29`

Any functional change after this registration requires a new experiment ID.

## Research Question

With the downstream data, raw-text preprocessing, optimization settings,
label smoothing, seeds, checkpoint selection, and metrics held equal to
EXP-014, does Twitter-domain pretraining produce a practically higher
official-validation Macro-F1 than generic RoBERTa pretraining?

Expected outcome: mean validation Macro-F1 exceeds EXP-014 by at least `0.005`
with a positive paired difference in at least two of three seeds. The
per-class comparison will test whether any benefit is concentrated in
`optimism` or another class.

Negative outcome: if the threshold is not reached, domain-pretraining benefit
is not established under this frozen downstream protocol. That result does
not justify changing preprocessing or training settings against the same
validation split within EXP-015.

## Controlled Condition

The only intended scientific-condition change from EXP-014 is the pretrained
base encoder:

| Condition | EXP-014 | EXP-015 |
| --- | --- | --- |
| Base repository | `FacebookAI/roberta-base` | `cardiffnlp/twitter-roberta-base` |
| Pretraining domain | general text | Twitter |
| Classification head | new four-class head | new four-class head |
| Downstream train/validation data | fixed TweetEval emotion | identical |
| Text preprocessing | raw | identical |
| Fine-tuning configuration | optimized frozen protocol | identical |
| Seeds | 42, 43, 44 | identical |

`cardiffnlp/twitter-roberta-base` is the base masked-language-model
checkpoint, not an emotion- or TweetEval-fine-tuned checkpoint. This prevents
task labels or test supervision from entering through the initialization.

The two checkpoints use the same 50,265-token RoBERTa vocabulary and merge
files. Architecture size is also matched at 12 layers and hidden size 768.

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
used without mention or URL normalization so the base encoder remains the
only changed condition. The runner rejects any path containing `test`.

## Frozen Model

- Base model: `cardiffnlp/twitter-roberta-base`
- Revision: `cbb417e9647b51504caf68cbe1af6bbf56da06b7`
- Local snapshot only; network access disabled during training
- Manifest SHA-256:
  `8de53639f979a947cb74c3165d42fb084315ba43544d68c7adc926414221b00f`
- Upstream architecture: `RobertaForMaskedLM`
- Downstream architecture: `RobertaForSequenceClassification`
- Downstream head: newly initialized four-class head
- Parameter count after head initialization: 124,648,708
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

## Selection and Metrics

Primary metric: validation Macro-F1.

For each seed, retain the epoch with maximum validation Macro-F1. An exact tie
keeps the earlier checkpoint. Aggregate results use the mean and sample
standard deviation across all three seeds.

A practical domain-pretraining improvement requires:

```text
mean(EXP-015 validation Macro-F1)
- mean(EXP-014 validation Macro-F1) >= 0.005
```

Paired per-seed differences must also be reported. The threshold is a local
practical-comparison rule, not a statistical-significance claim.

Required secondary outputs:

- Accuracy, macro precision/recall, and weighted F1.
- Per-class precision, recall, F1, and support.
- Rows-true, columns-predicted confusion matrix for every seed.
- Selected-checkpoint train diagnostic metrics, not used for selection.
- Per-epoch history and per-row validation predictions with probabilities.
- Config, protocol, model, data, environment, runner, and prediction hashes.

## Frozen Comparison

EXP-014 run metadata SHA-256:
`5b7078105514328a0c049fda889cdc63d41eca8fda09134c5a97ead8ad41a2c0`

- Mean validation Macro-F1: `0.740219`
- Sample SD: `0.005381`
- Mean validation Accuracy: `0.796791`
- Sample SD: `0.002674`
- Matched-seed improvement over EXP-011: 2 of 3 seeds

## Artifacts and Verification

The append-only run directory is:

```text
runs/exp-015-twitter-roberta-base-validation/
```

It must contain `run.json`, `stdout.log`, three per-seed metric/history/
prediction/confusion-matrix bundles, and one selected checkpoint per seed.
`verify_controlled.py` must independently recompute metrics, aggregates,
paired comparison, row order, probabilities, confusion matrices, and hashes
into `verification.json`.

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

- Results: generic versus Twitter-domain base encoder comparison.
- Methods: controlled domain-pretraining ablation.
- Analysis: per-class changes and whether optimism benefits.
- Limitations: one domain checkpoint, small validation set, and MPS
  nondeterminism.
- Appendix: seed-level metrics, predictions, checkpoint hashes, and manifest.

Test remains behind the project TEST-READY gate.
