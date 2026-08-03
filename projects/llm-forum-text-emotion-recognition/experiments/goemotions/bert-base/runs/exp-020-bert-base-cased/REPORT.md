# EXP-020 GoEmotions BERT-base-cased Report

Status: `Verified`

## Question

在固定 `DATA-GOE-V1` 的 28 标签多标签任务上，按 GoEmotions 论文公开条件
现代化实现 `bert-base-cased` 微调，能否建立稳定且明显强于 EXP-018 词法模型的
监督编码器 dev 基线？

## Frozen Condition

- Model: `google-bert/bert-base-cased`
- Revision: `cd5ef92a9fb2f889e972770a36d4ed042daf221e`
- Train/dev rows: 43,410 / 5,426
- Seeds: 42, 43, 44
- Epochs: 4; final epoch fixed before training
- Batch size: 16
- Maximum sequence length: 50
- Learning rate: `5e-5`
- Warmup: 10%
- Loss: independent 28-label sigmoid BCE
- Decision threshold: fixed global `0.3`
- Test: not acquired or accessed

The protocol, configuration, implementation, data, and base-model hashes are
recorded in `run.json`.

## Dev Results

| Seed | Macro-F1 | Micro-F1 | Weighted-F1 | Subset accuracy | Empty predictions |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 0.478753 | 0.586641 | 0.581983 | 0.444895 | 81 |
| 43 | 0.488709 | 0.583759 | 0.580626 | 0.436970 | 101 |
| 44 | 0.500843 | 0.589614 | 0.585853 | 0.441025 | 93 |
| Mean +/- sample SD | **0.489435 +/- 0.011063** | **0.586671 +/- 0.002928** | **0.582821 +/- 0.002713** | **0.440963 +/- 0.003963** | **91.7 +/- 10.1** |

Additional aggregate diagnostics:

- Macro precision: `0.508192 +/- 0.013995`
- Macro recall: `0.503652 +/- 0.008881`
- Samples-F1: `0.595936 +/- 0.003159`
- Hamming loss: `0.036193 +/- 0.000285`
- Predicted label cardinality: `1.275955 +/- 0.004188`
- Gold label cardinality: `1.175820`

## Comparison With EXP-018

EXP-018 obtained dev Macro-F1 `0.203644`, Micro-F1 `0.377639`, subset accuracy
`0.246959`, and 3,261 empty predictions. EXP-020 improves mean dev Macro-F1 by
`0.285791` and reduces empty predictions to a mean of 91.7.

This is a method-level comparison, not a pure encoder ablation: EXP-018 uses
its pre-registered threshold `0.5`, while EXP-020 uses the paper-aligned
threshold `0.3`. Neither threshold was changed after reading dev.

## Epoch Diagnostics

Mean across the three seeds:

| Epoch | Dev loss | Macro-F1 | Micro-F1 | Subset accuracy |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.092158 | 0.392417 | 0.576839 | 0.431933 |
| 2 | **0.085291** | 0.476550 | **0.600524** | **0.446738** |
| 3 | 0.086722 | **0.489754** | 0.597161 | 0.441270 |
| 4 | 0.093219 | 0.489435 | 0.586671 | 0.440963 |

Epoch 4 and epoch 3 are a practical tie in Macro-F1 (`-0.000319`), but dev
loss and Micro-F1 worsen by epoch 4. This is evidence of metric-dependent
overfitting, not grounds to replace the pre-registered final-epoch rule after
the fact. A future configuration may pre-register early stopping separately.

## Label Diagnostics

Highest mean F1:

- `gratitude`: `0.901493`
- `amusement`: `0.793396`
- `love`: `0.783643`
- `remorse`: `0.728241`
- `admiration`: `0.721486`

Lowest or least stable:

- `grief`: F1 `0` for all seeds; dev support 13
- `relief`: mean F1 `0.035088`; dev support 18
- `realization`: mean F1 `0.254477`; dev support 127
- `disappointment`: mean F1 `0.303140`; dev support 163
- `pride`: mean F1 `0.349828 +/- 0.243638`; dev support 15

Rare support is associated with several failures, but these results alone do
not prove that frequency is the only cause. Label overlap, annotation
ambiguity, lexical evidence, and missing context remain competing
explanations for later error analysis.

## Paper Result Boundary

The [GoEmotions paper](https://aclanthology.org/2020.acl-main.372/) reports
BERT Macro-F1 `0.46` on its held-out **test** split. EXP-020 reports
`0.489435 +/- 0.011063` on **dev**. These values are in the same broad range,
but the split difference means EXP-020 cannot be described as reproducing or
exceeding the official test score.

EXP-020 is also a modern PyTorch `2.9.1` / Transformers `5.8.0` / Apple MPS
implementation rather than a bitwise rerun of the historical TensorFlow
estimator. The public architecture, tokenizer, objective, sequence length,
batch size, learning rate, epochs, warmup, dropout, and threshold are aligned.

## Verification

`verification.json` independently:

- reconstructed 5,426 x 28 gold and prediction matrices for all three seeds;
- applied threshold `0.3` to saved probabilities;
- recomputed aggregate, per-label, and confusion-matrix results;
- obtained maximum numeric difference `0.0`;
- checked data, model, protocol, configuration, implementation, and artifact
  hashes;
- confirmed prediction files contain no raw text or upstream comment ID;
- confirmed all three 413 MB final models are gitignored;
- confirmed `test.tsv` is absent and test was not accessed.

## Reproduction

The completed run is append-only. To reproduce into a new directory:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
projects/llm-forum-text-emotion-recognition/experiments/goemotions/\
bert-base/train_and_evaluate.py \
  --output-dir /private/tmp/exp-020-reproduction
```

Verify the preserved run:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
projects/llm-forum-text-emotion-recognition/experiments/goemotions/\
bert-base/verify.py
```

## Current Conclusion

EXP-020 establishes the frozen GoEmotions supervised encoder dev baseline
needed before a same-dataset zero-shot/few-shot LLM comparison. It does not
consume the GoEmotions test gate and does not establish a mechanism-level
explanation of emotion recognition.
