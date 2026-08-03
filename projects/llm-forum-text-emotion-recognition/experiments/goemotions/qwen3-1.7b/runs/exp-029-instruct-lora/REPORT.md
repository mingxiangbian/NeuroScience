# EXP-029 GoEmotions Qwen3-1.7B LoRA Report

Status: `Verified`

## Question

在固定 `DATA-GOE-V1` 的 28 标签多标签任务上，对 post-trained
`Qwen3-1.7B` 进行监督 LoRA 后，能否稳定超过同一模型的冻结 zero/few-shot
表现，并缩小与 EXP-020 BERT-base-cased 监督编码器的差距？

EXP-029 评估任务行为，不证明 LoRA 产生了人类式情绪机制，也不把生成的标签串
视为模型内部推理的忠实解释。

## Frozen Condition

- Model: `Qwen/Qwen3-1.7B`
- Revision: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Precision: unquantized MLX BF16
- Train/dev rows: 43,410 / 5,426
- Seeds: 42, 43, 44
- Training: 1 epoch; micro-batch 2; gradient accumulation 5; effective batch 10
- Optimizer: Adam; constant learning rate `1e-5`
- LoRA: rank 8, scale 20.0, final 16 transformer blocks
- Target modules: attention `q/k/v/o` and MLP `gate/up/down` projections
- Trainable parameters: 4,980,736, about 0.289% of the model
- Evaluation: constrained greedy label-name JSON, zero-shot and fixed synthetic 3-shot
- Test: not acquired or accessed

The protocol, configuration, data hashes, adapter hashes, and commands are recorded in the
public run metadata. Adapter weights and expanded training rows remain gitignored.

## Dev Results

| Seed | Zero-shot Macro-F1 | Few-shot Macro-F1 | Selected | Train time | Dev time | Peak train memory |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 42 | 0.437205 | 0.422043 | zero-shot | 6.51 h | 2.80 h | 7.208 GB |
| 43 | 0.443673 | 0.422898 | zero-shot | 6.52 h | 2.61 h | 7.190 GB |
| 44 | 0.473242 | 0.430853 | zero-shot | 6.13 h | 2.56 h | 7.208 GB |
| Mean +/- sample SD | **0.451374 +/- 0.019212** | **0.425265 +/- 0.004858** | **zero-shot** | - | - | - |

For the selected zero-shot condition, mean Micro-F1 is `0.576343`, mean Weighted-F1 is
`0.552013`, and mean strict subset accuracy is `0.508293`. Both prompt conditions produced valid
JSON labels for all three seeds and all 5,426 dev rows.

The frozen selection rule chooses zero-shot because its mean Macro-F1 exceeds few-shot by
`0.026109`, above the `0.005` practical threshold. This does not establish that demonstrations are
generally harmful. It shows only that the three fixed synthetic examples did not help after this
specific supervised adaptation.

## Frozen Comparisons

- Versus matched EXP-025 frozen zero-shot: `+0.228376` Macro-F1.
- Versus matched EXP-025 frozen few-shot: `+0.184101` Macro-F1.
- Versus the EXP-025 selected frozen condition: `+0.210209` Macro-F1.
- Versus the EXP-020 BERT-base-cased three-seed mean: `-0.038061` Macro-F1.

The primary hypothesis is supported on dev: supervised LoRA adds substantial task competence
beyond prompting alone. The secondary hypothesis is only partly supported: the BERT gap narrows
from `0.248271` for the selected frozen Qwen condition to `0.038061`, but LoRA does not surpass
the frozen supervised encoder baseline.

These are same-dataset dev comparisons, not test results. Seed 44 is noticeably stronger than
seeds 42 and 43, so the best seed must not be reported in place of the registered mean and sample
standard deviation.

## Data Mapping Boundary

The official simplified train data contains 1,396 rows where `neutral` co-occurs with an emotion
label. Because the frozen constrained output ontology forbids that combination, EXP-029 drops only
`neutral` from those training targets. Neutral-only rows are unchanged, and the dev gold matrix is
unchanged, including all 174 neutral co-occurrence rows.

This pre-result correction is documented in the protocol and preparation report. It may reduce
neutral recall and means that changing the output ontology requires a new registered ablation.

## Resource Record

- Training time per seed: 6.13-6.52 active hours
- Full dev evaluation per seed: 2.56-2.80 active hours for both prompt conditions
- Peak training MLX memory: 7.208 GB
- Peak dev MLX memory: 3.995 GB
- API cost: USD 0
- Final adapter hashes: one distinct SHA-256 for each seed in the corresponding `run.json`

All runs remained within the frozen 18-hour training, 4-hour dev, and 14 GB memory gates.

## Verification

Each seed-level verifier returned `Passed`. The multi-seed verifier confirmed:

- three complete 5,426-row dev evaluations for both prompt conditions;
- recomputed task metrics, per-label results, paired bootstrap results, and resource records;
- protocol, configuration, data, model, adapter, and public artifact hashes;
- no raw text or upstream comment ID in public prediction artifacts;
- private adapters and expanded training data remain gitignored;
- GoEmotions `test.tsv` is absent and test was not accessed.

The aggregate verifier is
[`multi-seed-verification.json`](multi-seed-verification.json), and the compact registered result is
[`multi-seed-aggregate.json`](multi-seed-aggregate.json).

## Current Conclusion

EXP-029 establishes a verified dev-level result: supervised LoRA turns the local 1.7B
post-trained model into a much stronger GoEmotions classifier than frozen prompting, but the
smaller BERT supervised encoder remains stronger and substantially cheaper to train and evaluate.
The next behavior experiment should be a pre-registered cross-model error analysis using the
already frozen dev predictions. The separate Base/Instruct representation question remains open
because EXP-028 failed its resource gate.
