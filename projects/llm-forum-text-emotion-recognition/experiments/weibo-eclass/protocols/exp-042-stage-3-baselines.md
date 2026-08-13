# EXP-042: Weibo EClass Stage 3 Train/Dev Baselines

---
date: 2026-08-08
experiment_id: EXP-042
tier: Major
rq: RQ-F1
status: Verified
stage: stage-3-m0-m1-m2-train-dev
dataset_protocol: DATA-WEIBO-TASK-V1
parent_experiment: EXP-041
---

## Observed Outcome

EXP-042 已按冻结协议完成，并通过独立 verifier 的 8 项检查，`mismatch_count=0`。
本次只访问 train/validation，sealed test 未读取。

| Model / view | Validation Macro-F1 | Accuracy |
| --- | ---: | ---: |
| M0 train majority | 0.116913 | 0.692610 |
| M1 target only | 0.338267 | 0.650943 |
| M1 previous context | 0.271504 | 0.443396 |
| M2 target only, 3 seeds | 0.594925 +/- 0.012919 | 0.792453 +/- 0.003931 |
| M2 previous context, 3 seeds | 0.594219 +/- 0.012046 | 0.790094 +/- 0.004910 |

M2 的配对 `previous_context - target_only` Macro-F1 差值为
`-0.000706 +/- 0.024737`。绝对均值差小于预注册的 `0.005` 实际并列阈值，因此按规则冻结
`target_only` 为后续系统主视图，同时保留两个视图的完整结果。该结果只说明冻结的相邻前文
在当前模型与数据上没有稳定增益，不支持“上下文普遍无用”的结论。

## Question and Scope

在冻结的 Weibo EClass 七类单标签任务上，多数类下界、传统 TF-IDF 线性模型和中文
RoBERTa encoder 在同一 train/dev split 上达到什么性能？将固定局部前文加入训练和推理后，
M1/M2 的表现是否发生可复现变化？

本实验只回答 `RQ-F1` 的 encoder/baseline 部分。它不运行 Qwen、不读取 test、不启动迁移、
LoRA 或错误分析，也不把 Weibo 结果外推到所有论坛。

## Frozen Data Boundary

- Protocol: `DATA-WEIBO-TASK-V1`.
- Train: 5,995 rows, SHA-256
  `b1fd309acf45dfa4ad0c907ee3f373ea95fce751d51b637d402e289aa79d19e0`.
- Validation: 1,272 rows, SHA-256
  `99d80e1433bddea7b639983b8fa874e45d585318aa47eb87ab29581e02f72a4a`.
- Test inputs and sealed labels are forbidden and absent from the runner config.
- Label order: `joy`, `sadness`, `anger`, `positive`, `negative`, `neutral`,
  `no_emotion`.
- Views: `target_only` and `previous_context`, rendered with the frozen Stage 2
  boundary templates. No future clause enters either view.
- Text, row IDs, predictions and checkpoints remain under the Git-ignored private
  data root. Public artifacts contain aggregate results and hashes only.

## M0 Majority Baseline

The single prediction is the most frequent train label. The runner must derive
it from train counts and stop unless it equals the preregistered expectation
`no_emotion`. No validation label may influence this choice.

## M1 Classical Baseline

For each view, independently fit on train and evaluate once on validation:

- word TF-IDF `(1, 2)`;
- character `char_wb` TF-IDF `(3, 5)`;
- `min_df=2`, sublinear TF, lowercase enabled;
- `LinearSVC(C=1.0, class_weight="balanced", random_state=42)`.

No validation hyperparameter search is allowed. This deterministic baseline is
not repeated across meaningless random seeds.

## M2 Chinese Encoder Baseline

- Model: `hfl/chinese-roberta-wwm-ext`.
- Revision: `5c58d0b8ec1d9014354d691c538661bf00bfdb44`.
- Architecture: BERT sequence classifier with a newly initialized seven-class
  softmax head.
- Two matched training conditions, one per frozen input view.
- Seeds: 42, 43 and 44 for each view, six runs total.
- Three fixed epochs; the final epoch is retained. There is no dev early stopping
  or best-epoch selection.
- Max sequence length 256 with dynamic batch padding. Stage 2 observed no train
  truncation; any target truncation stops EXP-042.
- Batch 16 train / 64 validation, AdamW, learning rate `2e-5`, weight decay
  `0.01`, 10% linear warmup, linear decay, gradient clipping `1.0`.
- Ordinary unweighted `CrossEntropyLoss`; no class weighting, resampling, focal
  loss or post-result tuning is introduced in this first encoder baseline.
- Full fine-tuning on Apple MPS, no mixed precision.

The final checkpoint for every seed/view is retained privately for the later
test gate. A failed formal seed is preserved and requires a new experiment ID;
it is not silently rerun under EXP-042.

## Evaluation and Selection

Primary metric: validation Macro-F1. Also report Accuracy, macro precision,
macro recall, Weighted-F1, per-class precision/recall/F1/support and a confusion
matrix whose rows are gold and columns are predicted.

Every condition reports:

- full validation split;
- `context_available` slice;
- `first_clause` slice where the frozen previous clause is absent.

M2 reports per-seed values and mean +/- sample standard deviation. The paired
context effect is `previous_context - target_only` at the same seed. An absolute
Macro-F1 difference below `0.005` is a practical tie. If M2 views tie, the
target-only condition is preferred for deployment simplicity, while both
conditions remain reported. M0 and M1 are not used to select M2 checkpoints.

## Planned Artifacts

- public `run.json`, `stdout.log`, metrics, per-class tables, confusion matrices,
  seed summary and aggregate report;
- private row-level predictions with scores/probabilities;
- private retained M2 checkpoints and tokenizer files;
- independent verification that reconstructs metrics from private predictions
  without importing the runner.

Target thesis output: the first part of the same-task model comparison table in
the results chapter. Only independently verified numbers enter the evidence log.

## Resource Budget and Stop Conditions

- External network/API access: forbidden; cost USD 0.
- Device: local Apple MPS.
- Maximum encoder runs: six.
- Maximum wall time: 240 minutes, excluding an approval wait.
- Retained checkpoint budget: six models and 4 GiB total private output.
- Validation is authorized; test is not.

Stop immediately on input/model hash drift, schema or paired-view mismatch,
target truncation, MPS unavailability, non-finite loss/scores, unexpected test
access, output-directory reuse, or resource-budget overflow.

## Pass Signal

1. M0 and both M1 views complete on the frozen train/dev data.
2. All six M2 final-epoch runs complete with finite losses and 1,272 validation
   predictions each.
3. Required full/slice metrics and artifacts exist without public source text or
   row-level predictions.
4. Independent verification reproduces every primary/auxiliary metric,
   per-class table, confusion matrix and M2 aggregate with zero mismatch.
5. `run.json` confirms only train/validation access and no test access.

Passing EXP-042 closes Stage 3 only. It authorizes registration, but not
execution, of the Stage 4 frozen-Qwen 2x2 Major experiment.
