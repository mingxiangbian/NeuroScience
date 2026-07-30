# EXP-005 Protocol: Word + Character TF-IDF with Linear SVM

## Registration

- Date: 2026-07-29
- Tier: Major
- RQ ID: RQ-B1
- Status at registration: Planned
- Dataset: TweetEval emotion, upstream commit
  `4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66`
- Splits accessed: official train and validation only
- Test split: prohibited

## Question

Does a paper-aligned traditional architecture combining word and character
n-gram TF-IDF features with a linear SVM improve fixed-validation performance
over the selected balanced word TF-IDF + Logistic Regression baseline?

## Comparison Boundary

This is a combination-model comparison, not a single-variable ablation. It
changes both the feature representation and classifier:

- EXP-004: word `(1,2)` TF-IDF + balanced Logistic Regression.
- EXP-005: word `(1,2)` plus character `(3,5)` TF-IDF + unweighted LinearSVC.

All methods use the same official train and validation files and the same label
mapping. EXP-005 must verify those hashes against EXP-004 before evaluation.

The TweetEval paper reports an SVM with word and character n-gram features and
an emotion validation Macro-F1 of `0.638`. The paper and public repository do
not disclose all SVM and n-gram hyperparameters. EXP-005 is therefore a
paper-aligned implementation, not an exact reproduction.

## Frozen Configuration

- Word TF-IDF: lowercase, `(1,2)` n-grams, `min_df=2`, L2 norm,
  `sublinear_tf=true`.
- Character TF-IDF: lowercase, raw character `(3,5)` n-grams, `min_df=2`,
  L2 norm, `sublinear_tf=true`.
- Feature union weights: word `1.0`, character `1.0`.
- Classifier: `LinearSVC`.
- `C=1.0`, `loss="squared_hinge"`, `penalty="l2"`, `dual="auto"`.
- `class_weight=None`, `tol=1e-4`, `max_iter=5000`, `random_state=42`.
- Runs: one; this deterministic traditional baseline does not require
  meaningless multi-seed repetition.

No hyperparameter may be changed after reading EXP-005 validation results
under this experiment ID.

## Metrics and Decision Rule

- Primary: validation Macro-F1.
- Secondary: Accuracy, weighted F1, per-class precision/recall/F1.
- Current comparison: EXP-004 Macro-F1 `0.5659805744`, Accuracy
  `0.6203208556`.
- Practical improvement: Macro-F1 delta at least `+0.005`.
- Accuracy improvement is reported separately and does not override the
  primary rule.

## Required Artifacts

- `run.json`
- `stdout.log`
- local gitignored `model.joblib`
- `predictions.csv` with decision scores
- `confusion_matrix.csv`
- `confusion_matrix.png`
- `verification.json` from independent metric recomputation

Predictions must not contain source text.

## Resource Budget

- Maximum runs: 1
- Device: local Mac CPU
- Wall-time budget: 5 minutes
- API cost: USD 0
- Stop on unexpected data hashes, test access, non-convergence, NaN, or a
  non-empty output directory.

## Thesis Destination

- Results chapter: traditional-baseline comparison table, number TBD.
- Interpretation: whether character subword features and a margin classifier
  provide a stronger non-neural lower bound before encoder experiments.

## Sources

- TweetEval paper:
  <https://aclanthology.org/2020.findings-emnlp.148/>
- Official repository:
  <https://github.com/cardiffnlp/tweeteval>
