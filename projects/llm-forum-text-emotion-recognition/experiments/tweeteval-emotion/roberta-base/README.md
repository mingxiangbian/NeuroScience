# RoBERTa Base TweetEval Emotion Baseline

This directory contains the encoder baseline environment, controlled training
code, frozen configurations, and completed runs through EXP-015.

## Environment

The dedicated environment is separate from the shared `llm` environment:

```bash
conda create -n emotion-roberta python=3.10 pip
conda env config vars set -n emotion-roberta PYTHONNOUSERSITE=1 PIP_USER=0
conda activate emotion-roberta
PIP_USER=0 PYTHONNOUSERSITE=1 \
  python -m pip install -r requirements-lock.txt
python -m pip check
```

Current interpreter:

```text
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python
```

Key versions are Python 3.10.20, PyTorch 2.9.1, Transformers 5.8.0,
Datasets 5.0.1, Accelerate 1.13.0, Evaluate 0.4.6, and scikit-learn
1.7.2. Matplotlib 3.10.7 is used for figures. `requirements-lock.txt`
records the complete resolved runtime stack.

`PYTHONNOUSERSITE=1` is mandatory because this machine has a user-level pip
configuration that otherwise injects `~/.local` packages. EXP-011 checks
dependency paths before reading any dataset file.

## Models

The generic local gitignored snapshot is initialized from:

```text
FacebookAI/roberta-base
revision e2da8e2f811d1448a5b465c236feacd80ffbac7b
```

See `../../../models/roberta-base/manifest.json` for selected files and
SHA-256 hashes.

The domain comparison uses a separate base masked-language model:

```text
cardiffnlp/twitter-roberta-base
revision cbb417e9647b51504caf68cbe1af6bbf56da06b7
```

See `../../../models/twitter-roberta-base/manifest.json` for its selected
files and SHA-256 hashes. This is a Twitter-domain pretrained base encoder,
not an emotion-fine-tuned checkpoint. Every formal run loads a pinned local
snapshot rather than an unpinned model name.

## EXP-008 Environment Smoke Test

`EXP-008` is a Minor infrastructure run. It:

- verifies every local model file against the tracked manifest;
- loads tokenizer and pretrained weights with network access disabled;
- initializes a four-label classification head;
- completes one `Trainer` optimization step on eight synthetic English texts;
- runs synthetic inference and records the actual device and package versions;
- does not read train, validation, or test data.

Run it from the repository root:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/smoke_test.py
```

The default run directory is append-only:
`runs/exp-008-environment-smoke/`.

The post-run environment correction is documented in
`runs/exp-008-environment-smoke/correction-2026-07-30.md`; the original
`run.json` remains unchanged.

## EXP-009 Preserved Implementation Failure

EXP-009 stopped while loading the seed-42 model because the run logger did
not implement `isatty()`. It completed no optimization step and produced no
validation prediction or performance metric. The append-only failure
artifacts and source snapshot remain in
`runs/exp-009-roberta-base-finetuning/`.

## EXP-010 Preserved Execution Failure

EXP-010 stopped at the pre-data environment gate because its restricted
execution process did not expose Apple MPS. It opened no dataset file and
produced no model-performance result. Its append-only evidence remains in
`runs/exp-010-roberta-base-finetuning/`.

## EXP-011 Formal Fine-Tuning

EXP-011 is the execution-context retry. Its scientific design and training
code are identical to EXP-010; it runs outside the restricted process on the
same local MPS device. Its frozen configuration is
`configs/exp-011-roberta-base.json`, and its preregistration is
`protocols/exp-011-roberta-base-finetuning.md`.

The run uses three seeds, selects the best epoch within each seed by
validation Macro-F1, and retains all three selected checkpoints for the later
test gate. It does not choose a single seed using test results.

Run it from the repository root:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/train_finetune.py
```

### Result

| Seed | Best epoch | Validation Macro-F1 | Validation Accuracy |
| ---: | ---: | ---: | ---: |
| 42 | 4 | 0.730898 | 0.796791 |
| 43 | 3 | 0.738484 | 0.788770 |
| 44 | 5 | 0.729030 | 0.791444 |
| Mean +/- sample std | - | 0.732804 +/- 0.005007 | 0.792335 +/- 0.004084 |

Mean validation Macro-F1 exceeds frozen EXP-007 by `0.110126`. The mean
selected-checkpoint train diagnostic is Macro-F1 `0.956154` and Accuracy
`0.961621`, so the train-validation gap must remain part of the interpretation.
`optimism` is the weakest validation class (mean F1 `0.529918`) and has the
largest seed variation.

`runs/exp-011-roberta-base-finetuning/verification.json` independently
recomputes all three seed metrics and verifies prediction, model, input, and
artifact hashes. Its status is `Verified`; test access is `false`.

## EXP-012 and EXP-013 Train-Only Screening

These Minor runs use a fixed 85/15 stratified split made only from the official
training split. Official validation and test data are not opened.

- EXP-012 compared raw text against mention/URL normalization and the published
  CardiffNLP learning-rate, batch-size, and epoch combination. The current raw
  configuration won with inner-validation Macro-F1
  `0.792437 +/- 0.013076`. The normalization rule changed zero rows in this
  dataset, so the apparent difference from the nominal normalized candidate is
  rerun variation, not evidence for or against normalization.
- EXP-013 compared one-factor regularization treatments. Label smoothing
  `0.05` won with `0.795601 +/- 0.003187`, a paired mean gain of `0.009129`
  over its control. It improved all three matched seeds.

These are configuration-selection diagnostics, not official validation
results. No screening checkpoint was retained.

## EXP-014 Optimized Generic RoBERTa

EXP-014 freezes the train-only selection: raw text and label smoothing `0.05`,
with all other EXP-011 settings unchanged.

| Seed | Best epoch | Validation Macro-F1 | Validation Accuracy |
| ---: | ---: | ---: | ---: |
| 42 | 3 | 0.742165 | 0.796791 |
| 43 | 4 | 0.734136 | 0.794118 |
| 44 | 5 | 0.744356 | 0.799465 |
| Mean +/- sample std | - | 0.740219 +/- 0.005381 | 0.796791 +/- 0.002674 |

Mean Macro-F1 is `0.007415` above EXP-011. Seeds 42 and 44 improve; seed 43
declines by `0.004348`, which is inside the predeclared `0.005` practical-tie
band. The result is a modest validation improvement, not a statistical
significance or test claim.

## EXP-015 Twitter-Domain RoBERTa

EXP-015 changes only the base encoder from the generic RoBERTa snapshot to the
Twitter-domain pretrained snapshot.

| Seed | Best epoch | Validation Macro-F1 | Validation Accuracy |
| ---: | ---: | ---: | ---: |
| 42 | 3 | 0.765975 | 0.836898 |
| 43 | 5 | 0.769573 | 0.836898 |
| 44 | 3 | 0.749717 | 0.815508 |
| Mean +/- sample std | - | 0.761755 +/- 0.010579 | 0.829768 +/- 0.012350 |

All three paired seeds improve over EXP-014, with a mean Macro-F1 gain of
`0.021536`. The class-level result is mixed:

| Class | EXP-014 F1 | EXP-015 F1 | Delta |
| --- | ---: | ---: | ---: |
| anger | 0.874853 | 0.891352 | +0.016499 |
| joy | 0.780481 | 0.837945 | +0.057464 |
| optimism | 0.556824 | 0.521836 | -0.034988 |
| sadness | 0.748717 | 0.795888 | +0.047171 |

The overall domain-pretraining gain therefore does not imply that every
emotion class benefits. `optimism` remains the weakest class and is the main
target for preregistered error analysis.

## Controlled Runner

EXP-012 through EXP-015 use `controlled_runner.py` with a frozen JSON config
and an append-only output directory:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/roberta-base/controlled_runner.py \
  --config <config-path> \
  --output-dir <new-output-dir>
```

Use `verify_controlled.py --run-dir <run-directory>` to independently
recompute predictions, probabilities, metrics, confusion matrices, input
hashes, model hashes, and checkpoint hashes. EXP-014 and EXP-015 both have
`verification.json` status `Verified`; test access is `false`.

The retained EXP-011, EXP-014, and EXP-015 checkpoints were subsequently
evaluated once in the preregistered EXP-016 test gate. See
`../test-gate/README.md` for the verified test results. The development
runners in this directory remain validation-only and must not be modified to
read test.
