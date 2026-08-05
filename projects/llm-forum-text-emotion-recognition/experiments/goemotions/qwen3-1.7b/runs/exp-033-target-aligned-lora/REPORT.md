# EXP-033 Seed-42 Target-Aligned LoRA Validation

## Status

`Verified` negative result on the official GoEmotions `dev` split. Formal training and validation
both completed under frozen contracts and passed independent verification. GoEmotions `test` was
absent and was not accessed.

## Question

Does preserving every official multi-label target, including all `neutral+emotion` co-occurrences,
improve the seed-42 Qwen3-1.7B LoRA adapter over the matched EXP-029 adapter evaluated with the
aligned prompt and open-neutral decoder?

## Frozen Setup

- Model: `Qwen/Qwen3-1.7B`, revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, local MLX BF16.
- Train data: 43,410 rows, including all 1,396 `neutral+emotion` targets.
- LoRA: final 16 blocks, attention `q/k/v/o` and MLP `gate/up/down`, rank 8, 4,980,736 trainable parameters.
- Training: seed 42, one epoch, 21,705 micro-iterations, 4,341 optimizer updates, effective batch 10, constant learning rate `1e-5`.
- Validation: official dev, 5,426 rows, final adapter only, aligned prompt, open-neutral constrained JSON, greedy decoding, thinking disabled, one generation per row, no retry or repair.
- Primary metric: 28-label Macro-F1.

## Training Evidence

- Duration: 26,963.19 seconds, approximately 7.49 hours.
- Peak MLX memory: 7.208 GB.
- Initial/final logged loss windows: 0.4410 / 0.1618.
- Adapter SHA-256: `c0077f484823970f0bbd507d63c605d51fbab6d770aaf03e95aeb1df8e7053ea`.
- All 112 LoRA-B tensors were non-zero; an independent model load and finite-logit forward pass succeeded.
- Training accessed `train` only.

## Validation Results

| Metric | Value |
| --- | ---: |
| Macro precision / recall / F1 | 0.568150 / 0.386679 / **0.427959** |
| Micro precision / recall / F1 | 0.604947 / 0.544357 / 0.573055 |
| Weighted-F1 | 0.549395 |
| Samples-F1 | 0.584144 |
| Strict subset accuracy | 0.501843 |
| Hamming loss | 0.034062 |
| Label accuracy | 0.965938 |
| Gold / predicted label cardinality | 1.175820 / 1.058054 |

All 5,426 outputs parsed successfully and stopped normally. No prediction was empty. Median
generation latency was 0.902 seconds per row, the validation peak memory was 3.868 GB, and API cost
was USD 0.

## Frozen Comparisons

| Reference | Reference Macro-F1 | EXP-033 delta | Paired 95% CI | Decision |
| --- | ---: | ---: | ---: | --- |
| EXP-025 frozen few-shot | 0.241164 | +0.186795 | [+0.166973, +0.205137] | Repetition gate passed |
| EXP-029 seed 42 under EXP-031 aligned-open inference | 0.440637 | -0.012678 | [-0.026938, +0.001434] | Target-alignment improvement gate failed |
| EXP-020 BERT three-seed mean | 0.489435 | -0.061476 | Not paired | Descriptive only |

The observed decrease relative to the matched seed-42 adapter is larger than the 0.005 practical
threshold, but its paired 95% interval includes zero. Therefore this run does not establish a
statistically decisive degradation; it does establish that the pre-registered improvement gate was
not met.

## Multi-Label and Neutral Diagnostics

- On 878 multi-label rows, subset accuracy was 0.047836 and Samples-F1 was 0.472096. Gold label
  cardinality was 2.086560, while predicted cardinality was 1.145786.
- On 174 gold `neutral+emotion` rows, subset accuracy was 0, Samples-F1 was 0.561686, and the model
  produced zero `neutral+emotion` co-predictions.
- The complete dev run contained one neutral co-prediction, but it was outside the gold
  `neutral+emotion` slice.
- Lowest label F1 values included grief 0, relief 0.095238, pride 0.117647, and realization
  0.164384. Highest included gratitude 0.904624, amusement 0.793363, and love 0.768946.

Preserving co-occurrence targets removed the known supervision mismatch, but the seed-42 result did
not restore the desired co-occurrence behavior. This is behavioral evidence only; it does not show
why the model failed to learn the targets and does not support an internal emotion-mechanism claim.

## Reproduction and Verification

```bash
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/run_target_aligned_validation_v1.py \
  --contract projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/preflight/exp-033-seed42-validation-contract-v1.json \
  --contract-sha256 23e51743234c953d38d2ddf9905cc3af6eba6cb495713d971214fd48c971daa8

/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/verify_target_aligned_validation_v1.py \
  --contract projects/llm-forum-text-emotion-recognition/experiments/goemotions/qwen3-1.7b/preflight/exp-033-seed42-validation-contract-v1.json \
  --contract-sha256 23e51743234c953d38d2ddf9905cc3af6eba6cb495713d971214fd48c971daa8 \
  --check
```

The independent verifier does not import the runner. It rebuilt all gold and prediction matrices,
recomputed metrics, slices, paired bootstrap intervals, resource accounting, CSVs, and artifact
hashes, and returned `Passed`.
