# TF-IDF + Logistic Regression Baseline

This experiment fits the first non-neural baseline for the fixed TweetEval
emotion task.

## Shared Frozen Training Configuration

- Input split: official `train` split only.
- Text processing: lowercase word TF-IDF with unigram and bigram features.
- Feature thresholds: `min_df=2`, `sublinear_tf=true`.
- Classifier: Logistic Regression with `C=1.0` and `solver=lbfgs`.
- Random seed: `42`.
- Maximum iterations: `1,000`.

The only registered controlled change is Logistic Regression `class_weight`:
`none` for `EXP-001` and `balanced` for `EXP-003`. The training script has no
validation or test evaluation code.

## Train Unweighted Baseline

From the repository root:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/train.py
```

The default output directory is `runs/exp-001-train-only/`. It contains:

- `model.joblib`: fitted TF-IDF vocabulary, IDF values, and classifier weights.
- `run.json`: data hashes, aggregate label counts, frozen configuration,
  environment versions, fit duration, and artifact paths.

`model.joblib` is ignored by Git because its learned vocabulary is derived from
the upstream social-media text. The aggregate `run.json` metadata can be
retained as reproducibility evidence.

## Train Balanced Controlled Variant

This comparison was registered after inspecting `EXP-002` and before evaluating
the balanced model:

- Change only `class_weight` from `None` to `"balanced"`.
- Keep the dataset, TF-IDF configuration, classifier settings, and seed fixed.
- Use validation Macro-F1 as the primary comparison metric.
- Use per-class recall, especially optimism recall, as secondary diagnostics.
- Do not use the test split until the model-selection protocol is frozen.

Training command:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/train.py \
  --class-weight balanced \
  --output-dir \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only
```

## Validate

After `EXP-001` has been trained:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/validate.py
```

The validation evaluator verifies the parent model path, reads only
`mapping.txt`, `val_text.txt`, and `val_labels.txt`, and writes
`runs/exp-002-validation/`:

- `run.json`: Macro-F1, accuracy, aggregate and per-class metrics, provenance,
  hashes, and the numeric confusion matrix.
- `predictions.csv`: row numbers, gold/predicted labels, and class
  probabilities; source text is not copied.
- `confusion_matrix.csv` and `confusion_matrix.png`: true-label rows and
  predicted-label columns.

Validation results may guide a controlled model-selection decision. They are
not final test results, and the test split remains untouched.

### Validate Balanced Variant

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/validate.py \
  --model \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/model.joblib \
  --train-metadata \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-003-balanced-train-only/run.json \
  --output-dir \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-logreg/runs/exp-004-balanced-validation
```

## Internal Validation Comparison

These are model-selection results on the validation split, not final test
results.

| Metric | Unweighted EXP-002 | Balanced EXP-004 | Delta |
| --- | ---: | ---: | ---: |
| Macro-F1 | 0.493991 | 0.565981 | +0.071990 |
| Accuracy | 0.631016 | 0.620321 | -0.010695 |
| Anger recall | 0.906250 | 0.712500 | -0.193750 |
| Joy recall | 0.412371 | 0.556701 | +0.144330 |
| Optimism recall | 0.071429 | 0.535714 | +0.464286 |
| Sadness recall | 0.550562 | 0.550562 | 0.000000 |

The balanced variant wins the pre-registered primary comparison on validation
Macro-F1 and is therefore the selected TF-IDF baseline for the eventual
single test evaluation. Optimism precision is only `0.272727`, so class
weighting improves minority-class recall by introducing substantial optimism
false positives rather than solving the task.
