# EXP-018 Protocol: TF-IDF + One-vs-Rest Logistic Regression

Registration time: 2026-07-31T03:29:26Z

## Registration

- Experiment ID: `EXP-018`
- Tier: `Major`
- RQ: `RQ-G1`
- Status: `FROZEN BEFORE VALIDATION`
- Parent experiment: `N/A` (first GoEmotions model baseline)
- Dataset protocol: `DATA-GOE-V1`
- Stage: train on official train; evaluate once on official dev
- Test access: prohibited; `test.tsv` must remain absent

## Research Question

在固定 GoEmotions 28 标签多标签任务上，一个低复杂度、可复现的词面模型能达到
什么水平，并为后续 BERT-base/RoBERTa 监督微调提供怎样的同数据集下界？

本实验不回答 LLM 是否更强，也不与 TweetEval 分数比较。

## Falsifiable Expectation

TF-IDF + 独立二元 Logistic Regression 应能学习显式词汇线索并得到非零的
validation Macro-F1，但可能对 `grief`、`pride`、`nervousness` 等少数标签出现
低召回或零召回。无论结果高低，本实验都作为固定简单基线保留，不因 validation
表现修改配置。

## Frozen Data

- Source revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`
- Train: `data/goemotions/official/train.tsv`, 43,410 rows,
  SHA-256 `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`
- Dev: `data/goemotions/official/dev.tsv`, 5,426 rows,
  SHA-256 `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`
- Labels: `data/goemotions/official/emotions.txt`, 28 ordered labels,
  SHA-256 `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`
- Test: not acquired and not read

The reviewed official split contains zero train/dev comment-ID overlap and 41
unique exact texts occurring in both splits. Official rows remain unchanged for
benchmark comparability; this limitation must remain visible in the run record.

## Frozen Model

### Features

- `TfidfVectorizer`
- analyzer: word
- lowercase: `true`
- n-gram range: `(1, 2)`
- minimum document frequency: `2`
- maximum features: `100000`
- norm: `l2`
- sublinear term frequency: `true`
- tokenization and token pattern: scikit-learn defaults
- fit vocabulary and IDF on train only; transform dev without refitting

### Classifier

- reduction: binary relevance through `OneVsRestClassifier`
- base estimator: `LogisticRegression`
- 28 independent binary targets, including `neutral`
- `C=1.0`
- `class_weight=None`
- `solver="liblinear"`
- `penalty="l2"`
- `max_iter=1000`
- `tol=1e-4`
- `random_state=42`
- `n_jobs=1`

### Decision Rule

- global probability threshold: `0.5`
- no per-label threshold tuning
- no forced top-1 fallback for empty predictions
- no suppression of `neutral` when another label is predicted
- no class weighting, resampling, label grouping or post-processing

The experiment records empty predicted sets and `neutral` co-predictions rather
than repairing them after observing dev results.

## Metrics

Primary:

- Macro-F1 over all 28 binary labels at threshold 0.5

Required secondary metrics:

- macro precision and recall;
- micro precision, recall and F1;
- weighted precision, recall and F1;
- samples-averaged precision, recall and F1;
- subset/exact-match accuracy;
- Hamming loss and label-level accuracy (`1 - Hamming loss`);
- per-label precision, recall, F1, gold support and predicted support;
- per-label 2 x 2 confusion matrices (`TN`, `FP`, `FN`, `TP`);
- gold and predicted label cardinality;
- empty prediction count and neutral co-prediction count.

This first GoEmotions baseline has no parent model comparison and no selection
step. The project default practical-tie threshold is therefore not applicable.

## Artifacts and Verification

The run must save:

- `run.json`;
- `stdout.log`;
- `predictions.csv` without text or upstream comment IDs;
- `per_label_metrics.csv`;
- `multilabel_confusion_matrix.csv`;
- local gitignored `model.joblib` with its SHA-256 recorded;
- `verification.json` produced by an independent predictions-based verifier.

The verifier must reconstruct gold multi-hot labels from the frozen dev TSV,
rebuild predictions from saved probabilities and threshold 0.5, and independently
recompute every reported aggregate and per-label metric.

## Resource Budget

- Maximum formal runs under this protocol: 1
- CPU wall-time budget: 20 minutes
- API cost: USD 0
- Random seeds: one fixed seed; deterministic classical baseline
- Output directory: `runs/exp-018-tfidf-ovr-logreg/`, initially empty

## Stop Conditions

Stop and preserve the failed run if any of the following occurs:

- an input hash or row count differs from this protocol;
- `test.tsv` exists or is accessed;
- the output directory is non-empty before the run;
- any label is outside `0..27` or any row has no gold label;
- a classifier emits a convergence warning;
- a probability or metric is NaN or infinite;
- runtime exceeds 20 minutes;
- predictions cannot be independently reconstructed and verified.

Any later class weighting, character features, threshold tuning or resampling is
a separate experiment and cannot overwrite `EXP-018`.

## Thesis Destination

- Method: simple multi-label text baseline and fixed decision rule
- Results: first row of the GoEmotions supervised-baseline table
- Discussion: lexical lower bound, class imbalance and rare-label failure modes

