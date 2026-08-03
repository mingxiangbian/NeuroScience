# EXP-020 Protocol: GoEmotions BERT-base-cased

Registration time: 2026-07-31T03:59:07Z

This protocol was frozen before EXP-020 loaded GoEmotions train/dev or
produced a model-performance result. EXP-019 had already verified only the
local model files and a synthetic 28-label MPS optimization path.

## Registration

- Experiment ID: `EXP-020`
- Tier: `Major`
- RQ: `RQ-G1`
- Parent experiment: `EXP-018` as the same-dataset simple comparison
- Dataset protocol: `DATA-GOE-V1`
- Stage: train on official train; evaluate on official dev
- Test access: prohibited; `test.tsv` must remain absent
- Frozen config:
  [`../configs/exp-020-bert-base-cased.json`](../configs/exp-020-bert-base-cased.json)
- Config SHA-256:
  `8ec432ddecc8e400bed2e676bcfb36649f1f1a48ce8b9c811ebde60f525277d5`

## Research Question

在固定 GoEmotions 28 标签多标签任务上，按原论文公开条件微调
`bert-base-cased`，能否建立一个稳定、可复算且明显强于 EXP-018 词法模型的监督
编码器基线？

该实验回答的是同一数据集上的监督基线问题，不回答 LLM 是否更强，也不支持从分类
性能直接推断情绪表征机制。

## Prior Expectation

GoEmotions 论文报告完整 28 标签体系的 BERT **test** Macro-F1 为 `0.46`。
EXP-020 只评估 **dev**，因此该数字仅提供数量级背景，不能进行直接差值比较或宣称
已经复现官方 test 结果。本实验预期三 seed dev Macro-F1 明显高于 EXP-018 的
`0.203644`，预先规定的最低实际改善为 `0.005`。

官方 `0.46` 不是 checkpoint 选择条件，也不得用于本协议内继续调参。若结果与预期
不符，保留结果并检查实现、运行时、随机性和指标定义；不得在看过 dev 后覆盖本
实验配置。只有后续通过独立 `TEST-READY` gate，才允许在同 split 上与论文数字做
正式复现比较。

Official references:

- [GoEmotions paper](https://aclanthology.org/2020.acl-main.372/)
- [Google Research BERT classifier](https://github.com/google-research/google-research/blob/master/goemotions/bert_classifier.py)
- [Google Research metric script](https://github.com/google-research/google-research/blob/master/goemotions/calculate_metrics.py)

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
unique exact texts occurring in both splits. The official split remains
unchanged for benchmark comparability.

## Frozen Model

- Upstream model: `google-bert/bert-base-cased`
- Revision: `cd5ef92a9fb2f889e972770a36d4ed042daf221e`
- Local snapshot only; network disabled during training
- Model manifest SHA-256:
  `795076f67146a80a2bd875d198305dcd663c84feccdf314b7b426354a1b6d75b`
- Head: randomly initialized 28-output sequence-classification layer
- Output/loss: independent sigmoid logits with binary cross-entropy
- Maximum sequence length: 50 WordPiece tokens, including special tokens
- Casing: preserved
- Static padding: length 50
- Hidden, attention, and classifier dropout: `0.1`
- Class weights, resampling, label grouping, and relation regularization: none

## Frozen Training Configuration

| Setting | Value |
| --- | --- |
| Seeds | 42, 43, 44 |
| Epochs | 4 |
| Train batch size | 16 |
| Evaluation batch size | 64 |
| Batches per epoch | 2,713 (`drop_last=true`) |
| Total optimizer steps | 10,852 per seed |
| Optimizer | AdamW |
| Learning rate | `5e-5` |
| Betas / epsilon | `0.9`, `0.999` / `1e-6` |
| Weight decay | `0.01`, excluding bias and LayerNorm weights |
| Scheduler | linear warmup then linear decay |
| Warmup | 1,085 steps (10%) |
| Maximum gradient norm | `1.0` |
| Gradient accumulation | 1 |
| Mixed precision | disabled |
| Device | local Apple MPS |

Training evaluates dev after every epoch for diagnostics. The formal model for
each seed is always the final epoch-4 checkpoint; there is no dev-based early
stopping or best-epoch selection.

## Reproduction Boundary

The public paper implementation uses the original TensorFlow BERT estimator.
EXP-020 uses PyTorch `2.9.1` and Transformers `5.8.0` because the historical
stack is not the maintained local runtime. Architecture, tokenizer, sequence
length, batch size, learning rate, epochs, warmup, dropout, BCE objective, and
threshold are aligned where the public code specifies them.

Consequently, EXP-020 is a paper-aligned numerical reproduction, not a bitwise
re-execution. Optimizer kernels, data-loader order, device arithmetic, library
versions, and three explicitly chosen seeds may produce different values.

## Decision Rule and Metrics

Decision rule:

- global probability threshold: `0.3`;
- positive when probability is greater than or equal to `0.3`;
- no per-label threshold tuning;
- no forced top-1 label for empty predictions;
- no suppression of `neutral` when another label is predicted.

Primary metric:

- Macro-F1 over all 28 labels, averaged equally.

Required secondary metrics:

- macro precision and recall;
- micro precision, recall, and F1;
- weighted precision, recall, and F1;
- samples-averaged precision, recall, and F1;
- strict subset/exact-match accuracy;
- Hamming loss and label-level accuracy;
- per-label precision, recall, F1, gold support, and predicted support;
- per-label 2 x 2 confusion matrices;
- gold and predicted label cardinality;
- empty-prediction and neutral-co-prediction counts;
- train/dev loss and epoch runtime.

Report each seed plus the three-seed mean and sample standard deviation.
EXP-020 is practically stronger than EXP-018 only if:

```text
mean(EXP-020 dev Macro-F1) - 0.20364430957028798 >= 0.005
```

This is a practical comparison, not a statistical-significance claim.

## Artifacts and Verification

The run must save:

- root `run.json`, `stdout.log`, `aggregate_metrics.json`, and
  `seed_summary.csv`;
- per-seed `history.csv`, `metrics.json`, `predictions.csv`,
  `per_label_metrics.csv`, and `multilabel_confusion_matrix.csv`;
- one local gitignored final model per seed with its SHA-256 recorded;
- `verification.json` produced by an independent predictions-based verifier.

Predictions contain sequential anonymous row numbers, gold/predicted label
sets, and 28 probabilities. They must not contain raw comment text or upstream
comment IDs.

The verifier must reconstruct dev gold labels from the frozen TSV, rebuild
predictions at threshold `0.3`, recompute all seed and aggregate metrics, and
check input, model, config, implementation, and output hashes.

## Resource Budget

- Maximum formal seed runs: 3
- Maximum retained models: 3
- Maximum total wall time: 360 minutes
- API cost: USD 0
- Output directory: `runs/exp-020-bert-base-cased/`, initially empty

## Stop Conditions

Stop and preserve the failed run if:

- an input, config, or model hash differs from this protocol;
- `test.tsv` exists or is accessed;
- the output directory is non-empty before launch;
- labels or row counts violate `DATA-GOE-V1`;
- MPS is unavailable, loss becomes non-finite, or an unexplained OOM occurs;
- total runtime exceeds 360 minutes;
- saved predictions cannot be independently reconstructed.

Any threshold tuning, class weighting, longer sequence length, alternative
checkpoint rule, RoBERTa model, or relation regularization requires a new
experiment ID and cannot overwrite EXP-020.

## Thesis Destination

- Methods: paper-aligned multi-label BERT fine-tuning and reproduction boundary
- Results: GoEmotions simple baseline versus BERT table with three-seed spread
- Discussion: external-result deviation, rare labels, threshold behavior, and
  remaining test uncertainty

Test remains behind a separate `TEST-READY` gate.
