# EXP-010 Protocol: RoBERTa-Base Fine-Tuning Retry

Registration date: 2026-07-30

This protocol is frozen before EXP-010 reads validation predictions or
produces any model-performance result.

## Registration

- Tier: Major
- RQ: RQ-B2
- Parent experiment: EXP-009
- Retry reason: EXP-009 failed before optimization because its terminal
  `Tee` did not implement `isatty()`
- Stage: train-validation
- Dataset: TweetEval emotion
- Allowed splits: official train and validation only
- Prohibited split: test
- Frozen config:
  `configs/exp-010-roberta-base.json`
- Frozen config SHA-256:
  `db3b9c2772447d66bf0d83c69f7caedde43eba4fcf2b251574e7b121f0b327ee`

## Retry Boundary

EXP-009 loaded the train and validation files, then failed while loading the
seed-42 model. It completed no optimization step and produced no validation
prediction or performance metric. Its source, failure metadata, and log are
preserved under `runs/exp-009-roberta-base-finetuning/`.

EXP-010 changes no scientific condition. Data, model revision, tokenization,
hyperparameters, seeds, selection rules, metrics, comparison baseline, and
resource budget are identical to EXP-009. The active runner only adds standard
stream compatibility (`isatty`, `encoding`, and `fileno`) to its `Tee` logger
and changes experiment-specific paths and identifiers. Any further functional
correction requires another experiment ID.

## Research Question

On the same fixed TweetEval emotion train and validation splits, does standard
RoBERTa-base fine-tuning produce a practically stronger validation Macro-F1
than the frozen EXP-007 word and character TF-IDF Linear SVM baseline?

Expected outcome: the three-seed mean validation Macro-F1 exceeds EXP-007 by
at least `0.005`.

Negative outcome: if the threshold is not reached, EXP-010 still establishes
the encoder implementation, optimization behavior, seed variance, class-level
failure pattern, and compute cost. It does not justify hiding the result or
tuning EXP-010 after validation is read.

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

Label order is fixed as `anger`, `joy`, `optimism`, `sadness`.

The implementation must construct an explicit allowlist from these five
paths. It must not glob the data directory or refer to a `test_*` path.
Existing checks report 25 exact duplicate train rows, no validation
duplicates, and no exact train-validation text overlap. EXP-010 records these
checks again but does not deduplicate, so its data remains identical to prior
baselines.

## Model and Tokenization

- Base model: `FacebookAI/roberta-base`
- Revision: `e2da8e2f811d1448a5b465c236feacd80ffbac7b`
- Local snapshot only; network access disabled
- Model manifest SHA-256:
  `b6e508ca9783b9e79e3cfc445f3abc7d2792ac5cfa6f44a9b3cf5d5607cd30b6`
- Head: newly initialized four-class sequence-classification head
- Truncation: enabled
- Maximum sequence length: 128 tokens
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
| Scheduler | linear |
| Warmup ratio | `0.1` |
| Maximum gradient norm | `1.0` |
| Mixed precision | disabled |
| Evaluation and save cadence | every epoch |
| Retained checkpoints | one best checkpoint per seed |

There is no EXP-010 learning-rate, batch-size, epoch, class-weight, or
max-length search. Any later tuning is a new experiment with a new ID.

## Selection and Metrics

Primary metric: validation Macro-F1.

For each seed, retain the epoch with maximum validation Macro-F1. An exact
tie keeps the earlier checkpoint. All three selected checkpoints remain
candidates for the later test gate; the best validation seed is not silently
promoted to the sole test model.

The aggregate result is mean and sample standard deviation across all three
seeds. A practical improvement over EXP-007 requires:

```text
mean(EXP-010 validation Macro-F1) - 0.6226779061 >= 0.005
```

This threshold supports a local practical-comparison statement, not a claim
of statistical significance.

Required secondary outputs:

- Accuracy, macro precision/recall, and weighted F1.
- Per-class precision, recall, F1, and support.
- Rows-true, columns-predicted confusion matrix for every seed.
- Selected-checkpoint train diagnostic metrics, not used for selection.
- Train/evaluation loss, learning rate, step, epoch, Macro-F1, and Accuracy.
- Per-row validation prediction and four class probabilities.
- Model, input, config, environment, prediction, and figure hashes.

## Comparison

Frozen comparison: EXP-007.

- Metadata SHA-256:
  `02b75009b580dfa5faf4170c9b14160e0c11b17f05c55ca2ecb6ec82e0848a7e`
- Validation Macro-F1: `0.6226779061`
- Validation Accuracy: `0.6764705882`

The official TweetEval RoBERTa-base test score is not used for checkpoint
selection and is not directly comparable to this validation result.

## Environment Gate

EXP-008 later received a correction because machine-level pip configuration
allowed `~/.local` packages into the Conda interpreter. Before loading data,
EXP-010 must verify:

- `PYTHONNOUSERSITE=1`
- `site.ENABLE_USER_SITE` is false
- the user-site directory is absent from `sys.path`
- all key dependencies resolve below the `emotion-roberta` prefix
- `pip check` has no broken requirements
- the 70-package runtime lock SHA-256 is
  `123e455840fb9e5e9230cd3eb7feda625a8819c4cd3dbf82b91068a7d60797fd`
- Apple MPS is built and available

Failure at this gate stops before any dataset file is opened.

## Artifacts

The append-only run directory is:

```text
runs/exp-010-roberta-base-finetuning/
```

It must contain:

- `run.json`, `stdout.log`, and `aggregate_metrics.json`
- `seed_summary.csv` and `learning_curves.png`
- per-seed `metrics.json`, `history.csv`, `predictions.csv`
- per-seed confusion matrix CSV and PNG
- one gitignored selected checkpoint per seed
- post-run `verification.json`

Raw text is never written to tracked artifacts.

## Resource Budget

- Maximum seed runs: 3
- Maximum retained checkpoints: 3
- Maximum wall time: 120 minutes
- API cost: USD 0
- Device: local Apple MPS

If the run exceeds the wall-time budget, encounters unexplained NaN/OOM, or
reads an unexpected path, stop and preserve the partial run as failed.

## Thesis Destination

- Results chapter: traditional versus encoder baseline table
- Methods chapter: reproducible fine-tuning configuration
- Appendix: environment, seed-level metrics, learning curves, and artifact
  hashes

Test remains behind the project TEST-READY gate.
