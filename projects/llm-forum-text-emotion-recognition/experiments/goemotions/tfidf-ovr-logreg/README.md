# GoEmotions TF-IDF + One-vs-Rest Logistic Regression

This directory contains the first simple supervised multi-label baseline for
`DATA-GOE-V1`.

## Frozen Experiment

- Experiment: `EXP-018`
- RQ: `RQ-G1`
- Features: word TF-IDF, 1-2 grams, train-fitted vocabulary and IDF
- Classifier: 28 independent Logistic Regression classifiers
- Decision threshold: fixed global `0.5`
- Data access: official train/dev only; test must remain absent
- Protocol:
  [`protocols/exp-018-tfidf-ovr-logreg.md`](protocols/exp-018-tfidf-ovr-logreg.md)

## Result

`EXP-018` completed and was independently verified on dev:

- Macro-F1: `0.203644`
- Micro-F1: `0.377639`
- Subset/exact-match accuracy: `0.246959`
- Empty prediction rows: `3,261 / 5,426`
- Test: not acquired or accessed

See the frozen run [`REPORT.md`](runs/exp-018-tfidf-ovr-logreg/REPORT.md) and
machine-readable [`verification.json`](runs/exp-018-tfidf-ovr-logreg/verification.json).

## Run

From the repository root:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/\
tfidf-ovr-logreg/train_and_evaluate.py
```

Then independently verify the saved predictions:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/\
tfidf-ovr-logreg/verify.py
```

`model.joblib` is local and ignored by Git. Public artifacts contain no comment
text or upstream comment IDs.
