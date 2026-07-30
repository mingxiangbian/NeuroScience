# Word + Character TF-IDF + Linear SVM

`EXP-005` evaluates a stronger traditional TweetEval emotion baseline using
word and character n-gram TF-IDF features with a linear support vector
classifier. `EXP-006` then tunes a bounded grid using train-only
cross-validation, and `EXP-007` confirms the frozen winner once on validation.

This is paper-aligned, not an exact reproduction: TweetEval documents the use
of word and character n-gram SVM features, but does not publish the complete
feature ranges and SVM hyperparameters.

## Frozen Configuration

- Word TF-IDF: `(1,2)` n-grams, `min_df=2`, sublinear TF.
- Character TF-IDF: raw character `(3,5)` n-grams, `min_df=2`, sublinear TF.
- Classifier: unweighted `LinearSVC(C=1.0)`.
- Train and evaluation: official train and validation splits only.
- Test split: not read.

The complete pre-run registration is in
[`protocols/exp-005-word-char-linear-svm.md`](protocols/exp-005-word-char-linear-svm.md).

## Run

From the repository root:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/run_experiment.py
```

The command refuses to reuse a non-empty output directory. Its default output
is `runs/exp-005-word-char-linear-svm/`.

## Verify

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/verify.py
```

The verifier independently reloads the validation labels and predictions,
recomputes all metrics and the confusion matrix, and writes
`verification.json`. It does not load the test split.

## EXP-006 Train-Only Tuning

`EXP-006` is a Minor experiment that diagnoses and tunes EXP-005 without
reading validation or test:

- Five-fold stratified cross-validation inside the official train split.
- Primary metric: mean CV Macro-F1.
- `C`: `0.05`, `0.1`, `0.25`, `0.5`, `1.0`.
- `class_weight`: `None`, `balanced`.
- Character n-grams: `(3,5)`, `(2,5)`, `(3,6)`.
- Word `(1,2)` n-grams and `min_df=2` remain fixed.
- One grid search: 30 candidates and 150 total CV fits.
- Resource budget: local CPU, at most five minutes, no API cost.

The highest mean CV Macro-F1 selects the candidate. Only after selection is
the configuration frozen for one separate validation confirmation.

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/tune_train_cv.py
```

EXP-006 completed the frozen train-only search in `101.626` seconds:

| Configuration | Mean CV Macro-F1 | Mean CV Accuracy |
| --- | ---: | ---: |
| EXP-005 parameters in the same CV | 0.644607 | 0.705558 |
| EXP-006 selected parameters | **0.670851 +/- 0.010910** | **0.720913 +/- 0.010316** |

The selected parameters are `C=0.25`, `class_weight=balanced`, and character
`(3,6)` n-grams. Word `(1,2)` n-grams and `min_df=2` remain fixed. Validation
and test were not accessed during selection.

The top four candidates span only `0.002120` mean CV Macro-F1, below the
project's `0.005` practical-tie threshold. All four use balanced class weights
and `C` of `0.1` or `0.25`; the search supports stronger regularization and
class balancing more clearly than it supports one exact character range.

## EXP-007 Frozen Validation Confirmation

The selected configuration and its SHA-256 were frozen in
[`protocols/exp-007-tuned-linear-svm.md`](protocols/exp-007-tuned-linear-svm.md)
before reading its official validation result.

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/run_tuned_validation.py
```

The independent verification command is:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/verify.py \
  --run-dir projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/tfidf-linear-svm/runs/exp-007-tuned-linear-svm \
  --expected-experiment-id EXP-007
```

The single frozen validation run completed on 2026-07-29:

| Metric | EXP-005 | EXP-007 tuned | Delta |
| --- | ---: | ---: | ---: |
| Train Accuracy (diagnostic) | 0.996930 | 0.985877 | -0.011053 |
| Train Macro-F1 (diagnostic) | 0.997644 | 0.984713 | -0.012931 |
| Validation Macro-F1 | 0.611866 | **0.622678** | **+0.010812** |
| Validation Accuracy | 0.671123 | **0.676471** | **+0.005348** |
| Validation weighted F1 | 0.664025 | **0.673440** | **+0.009415** |
| Anger F1 | 0.741379 | **0.759644** | +0.018265 |
| Joy F1 | 0.624277 | **0.636872** | +0.012594 |
| Optimism F1 | 0.444444 | **0.472727** | +0.028283 |
| Sadness F1 | **0.637363** | 0.621469 | -0.015894 |

The frozen primary rule passed because Macro-F1 improved by more than `0.005`.
The lower training score and higher validation scores are consistent with
reduced overfitting under stronger regularization and class balancing.
This is not proof that either change caused the gain individually because the
selected configuration also changed the character n-gram range.

EXP-007 is now the strongest local traditional validation baseline. It remains
a development result: validation has already served model selection, and test
was not accessed. Its Macro-F1 remains `0.015322` below the TweetEval paper's
reported SVM validation result of `0.638`. The selected train-CV estimate
(`0.670851`) was also higher than the held-out validation result (`0.622678`);
search selection effects and split variance therefore remain material.

## EXP-005 Initial Comparison

`EXP-005` completed one frozen local CPU run on 2026-07-29. The independent
verifier reproduced all 374 validation predictions and aggregate/per-class
metrics. Test was not accessed.

| Metric | EXP-004 balanced LR | EXP-005 word+char SVM | Delta |
| --- | ---: | ---: | ---: |
| Macro-F1 | 0.565981 | 0.611866 | +0.045885 |
| Accuracy | 0.620321 | 0.671123 | +0.050802 |
| Weighted F1 | 0.629235 | 0.664025 | +0.034790 |
| Anger F1 | 0.719243 | 0.741379 | +0.022136 |
| Joy F1 | 0.603352 | 0.624277 | +0.020926 |
| Optimism F1 | 0.361446 | 0.444444 | +0.082999 |
| Sadness F1 | 0.579882 | 0.637363 | +0.057481 |

The primary rule passed: validation Macro-F1 improved by more than the frozen
`0.005` practical threshold. EXP-005 therefore replaced EXP-004 before the
train-only tuning stage.

This does not mean every diagnostic improved. Optimism recall fell from
`0.535714` to `0.357143`, while optimism precision rose from `0.272727` to
`0.588235`. The higher optimism F1 reflects fewer false positives at the cost
of more false negatives.

The result remains below the TweetEval paper's reported SVM validation
Macro-F1 of `0.638` by `0.026134`. Because the official feature ranges and SVM
hyperparameters were not fully disclosed, this run is evidence for the frozen
local implementation, not a claim of exact reproduction.
