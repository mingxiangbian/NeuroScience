# TweetEval Emotion Error Analysis

This directory contains EXP-017, a preregistered descriptive analysis of the
frozen EXP-016 test predictions. It performs no training or new model
inference. Observed test cases must not be used for model, prompt, threshold, or
preprocessing selection.

## Reproduce the Aggregates

The original run directory is append-only. To reproduce the deterministic
aggregation and sample selection, use a new output directory in a copied config:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/error-analysis/analyze_frozen_errors.py \
  --config <copied-config-with-new-output-dir>
```

The fixed public artifacts are in:

```text
runs/exp-017-frozen-error-analysis/
```

The selected Tweet text is stored only under its gitignored `private/`
subdirectory. Public artifacts retain anonymous row IDs and coded categories,
not the raw text.

## Verify

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/error-analysis/verify_error_analysis.py
```

Read `REPORT.md` in the run directory for the findings and limitations.
