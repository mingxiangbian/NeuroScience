# EXP-034 Train Neutral-Co-occurrence Diagnostic

## Status

`Verified` Minor diagnostic on the exact EXP-033 training examples whose gold targets contain
`neutral` plus at least one emotion. The final seed-42 adapter was frozen; this run did not train,
tune, select a checkpoint, or access GoEmotions `dev` or `test`.

## Question

Can the frozen EXP-033 seed-42 adapter reproduce `neutral+emotion` targets on the 1,396 training
examples it saw, or is the zero-co-prediction result observed on validation mainly a held-out
generalization failure?

## Frozen Setup

- Parent: EXP-033 target-aligned LoRA, final seed-42 adapter only.
- Model: `Qwen/Qwen3-1.7B`, revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, local MLX BF16.
- Slice: all 1,396 official training rows whose gold set contains `neutral` and another label.
- Gold cardinality: 1,335 two-label rows, 60 three-label rows, and one four-label row.
- Inference: aligned training prompt, open-neutral constrained label-name JSON, greedy decoding,
  thinking disabled, one generation per row, and no retry or repair.
- Primary diagnostic: rate of predictions containing `neutral` plus another label.

## Results

| Diagnostic | Training slice | EXP-033 validation slice |
| --- | ---: | ---: |
| Rows | 1,396 | 174 |
| Neutral co-predictions | **0 (0%)** | **0 (0%)** |
| Target-compatible co-predictions | **0 (0%)** | Not separately reported |
| Gold mean cardinality | 2.044413 | 2.045977 |
| Predicted mean cardinality | **1.019341** | **1.017241** |
| Strict subset accuracy | 0 | 0 |
| Samples-F1 | 0.537655 | 0.561686 |
| Macro-F1 | 0.308414 | 0.231780 |

The training predictions contained 1,370 one-label outputs, 25 two-label outputs, and one
three-label output. Thus the adapter can emit multiple labels, but none of those 26 multi-label
outputs contained `neutral`. All 1,396 outputs parsed successfully and stopped normally.

The run took 1,255.98 seconds (20.93 minutes), peaked at 3.879 GB of MLX memory, and incurred no
API cost.

## Interpretation

The near-identical cardinality and zero `neutral+emotion` rate on train and validation make a
held-out generalization-only explanation insufficient. The adapter did not reproduce this target
structure even on examples used during training. This is strong behavioral evidence of
under-learning or a near-single-label generation bias.

This diagnostic does **not** identify the cause. Plausible explanations still include the rarity of
these rows (1,396 of 43,410 training examples), token-level loss weighting, label order under
autoregressive training, optimization or LoRA capacity, and base-model capacity. It also does not
support a claim about an internal emotion mechanism. The training-slice classification scores are
memorization diagnostics, not held-out performance estimates.

## Decision Consequence

Repeating the same EXP-033 protocol with seeds 43 and 44 is now low-value: seed 42 failed both the
registered validation improvement gate and the more direct training-slice structural check. A more
informative next experiment would first alter exposure or objective conditions in a train-only
controlled diagnostic, then authorize another full training run only if the target structure
becomes learnable.

## Reproduction and Verification

```bash
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_train_neutral_cooccurrence_diagnostic.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/configs/exp-034-train-neutral-cooccurrence-diagnostic.json \
  --config-sha256 bbef0d67bd05cfba813651652c2cb9f85158cd76ffa39dd324500934cf29236a

/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_train_neutral_cooccurrence_diagnostic.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/configs/exp-034-train-neutral-cooccurrence-diagnostic.json \
  --config-sha256 bbef0d67bd05cfba813651652c2cb9f85158cd76ffa39dd324500934cf29236a \
  --check
```

The independent verifier does not import the runner. It reconstructed the frozen slice from the
official training TSV and prepared targets, re-parsed every raw output, recomputed metrics and
cardinality diagnostics, checked artifact hashes and privacy fields, confirmed `test` was absent,
and returned `Passed`.
