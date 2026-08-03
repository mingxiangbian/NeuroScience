# EXP-029: Supervised LoRA for Qwen3-1.7B on GoEmotions

## Registration

- Experiment ID: `EXP-029`
- Tier: `Major`
- RQ: `RQ-G2`
- Registered: `2026-08-01`, before EXP-029 train or dev results
- Parent comparison: `EXP-025`
- Status at registration: `Registered`
- Test gate: closed; `test.tsv` must remain absent

## Question

Does supervised generative LoRA make the post-trained Qwen3-1.7B a materially better
GoEmotions classifier than its frozen zero/few-shot behavior, and how does the resulting system
compare with the frozen BERT-base encoder baseline on the same 28-label dev split?

This experiment measures task behavior. It does not establish that LoRA creates a human-like
emotion mechanism or that generated label strings are faithful explanations of model internals.

## Hypotheses

- Primary: supervised LoRA increases dev Macro-F1 by at least `0.005` over the matched frozen
  EXP-025 prompt condition.
- Secondary: the improvement is large enough to narrow the gap to the EXP-020 BERT-base mean.
- Negative result: LoRA mainly improves output-format compliance or frequent labels while
  leaving Macro-F1 and minority-label recall near the frozen model.

## Controlled Change

Changed:

- Add supervised LoRA adapters to the post-trained Qwen3-1.7B.
- Train on GoEmotions `train` with canonical label-name JSON targets.

Held fixed:

- `DATA-GOE-V1` train/dev files and 28-label order.
- Qwen model revision, BF16 precision, and absence of quantization.
- EXP-022 system/user prompt and disabled thinking mode.
- Greedy constrained label-name JSON decoding used by EXP-025.
- Dev rows, metrics, invalid-output policy, and practical tie threshold.

Training uses the zero-shot prompt without repeating the three synthetic demonstrations in every
row. Dev evaluates both the same zero-shot prompt and the frozen three-example prompt. This yields
a controlled `frozen versus LoRA` comparison under each prompt condition and tests whether the
examples remain useful after supervision.

## Data

- Train: 43,410 rows; SHA-256
  `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Dev: 5,426 rows; SHA-256
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Labels: 28 ordered labels; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Test: not acquired and forbidden in EXP-029.

Each target is an exact compact JSON object, for example `{"labels":["anger","annoyance"]}`.
Labels are sorted by their frozen numeric IDs. Prompt tokens are masked from the loss, but the
assistant non-thinking prefix and target tokens remain supervised.

### Pre-result correction: neutral co-occurrence mapping

During the first data-preparation pass, before any model or dev result, the runner found that the
official simplified files contain `neutral` together with emotion labels in 1,396 train rows and
174 dev rows. The frozen EXP-022/025 output ontology forbids `neutral` from being combined with an
emotion, so those gold sets cannot be serialized unchanged as valid training targets.

To keep the decoder and prompt matched to EXP-025, EXP-029 drops only `neutral` from those 1,396
training targets and retains every non-neutral gold label. Neutral-only rows are unchanged. The dev
gold matrix remains completely unchanged, including all 174 co-occurrence rows, so this mapping
does not make evaluation easier and can lower neutral recall. Allowing neutral co-occurrence would
change the output ontology and therefore requires a separately registered decoder/target ablation.

The maximum sequence length is 512 tokens. A pre-result token audit found two train rows longer
than 512 tokens. Those rows are deterministically truncated at the end of the input text only;
the system prompt, user framing, assistant prefix, complete target, and EOS remain intact. The
public preparation report records anonymous row numbers and before/after lengths, not text.

## Model and LoRA Placement

- Base: `Qwen/Qwen3-1.7B`, revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- Local format: MLX BF16, unquantized.
- Adapted blocks: final 16 of 28, indices 12 through 27.
- Target modules in each adapted block:
  `self_attn.q_proj`, `self_attn.k_proj`, `self_attn.v_proj`,
  `self_attn.o_proj`, `mlp.gate_proj`, `mlp.up_proj`, `mlp.down_proj`.
- Rank: 8.
- MLX scale: 20.0. This is recorded as MLX's direct LoRA multiplier and is not relabeled as a
  PEFT `alpha/r` value.
- Dropout: 0.0.
- Embeddings, normalization layers, base weights, and `lm_head` remain frozen.
- Expected trainable parameters: 4,980,736 (about 0.29% of the model).

The seven linear projections are a capacity/cost design choice, not a claim that each is necessary.
A target-module ablation would require a new experiment.

## Training Configuration

- Optimizer: Adam.
- Learning rate: constant `1e-5`.
- Epochs: exactly 1.
- Micro-batch: 2.
- Gradient accumulation: 5 micro-batches.
- Effective batch: 10 rows per optimizer update.
- Iterations: 21,705 micro-batches, covering all 43,410 rows once.
- Optimizer updates: 4,341.
- Seed schedule: 42 first; seeds 43 and 44 are resource-gated below.
- Checkpoints: periodic private checkpoints plus a fixed final adapter; dev does not choose a
  checkpoint.
- External network/API: disabled; API cost is zero.

## Preflight and Smoke Gates

Formal training is authorized only if all checks pass:

1. Frozen input hashes match and `test.tsv` is absent.
2. Prepared training data has 43,410 rows, every target is valid canonical JSON, and no sequence
   exceeds 512 tokens.
3. LoRA conversion reaches exactly the registered modules and trainable parameter count.
4. With zero-initialized LoRA B matrices, base and converted last-token logits are exactly equal;
   save/reload preserves this zero-step equality.
5. A 50-iteration, train-only smoke run has finite loss, non-zero trained adapter weights, no OOM,
   peak MLX memory at most 14 GB, and a non-divergent final loss window.
6. Smoke throughput projects one formal training seed at no more than 18 active hours.

The smoke set is a deterministic 64-row subset of train covering all 28 labels. It is not used as
validation evidence.

## Dev Evaluation

After a seed finishes training, evaluate the fixed final adapter once on all 5,426 dev rows under:

1. `zero-shot`
2. `few-shot-synthetic-3`

Both conditions use greedy decoding, a 64-token limit, no retry or repair, and the same finite-state
label JSON constraint as EXP-025. Invalid or length-terminated outputs are empty predictions and
remain in every denominator.

Primary metric: Macro-F1 across all 28 labels.

Also report Macro precision/recall, Micro-F1, weighted F1, samples F1, strict subset accuracy,
Hamming loss, per-label precision/recall/F1/support, label cardinality, parser validity, decoder
intervention, latency, tokens, and peak memory.

Prompt selection uses dev Macro-F1. An absolute zero/few difference below `0.005` is a practical
tie and selects zero-shot for lower cost. Otherwise select the higher condition. This selection
does not open the test gate.

## Comparisons and Repetition Gate

Matched comparisons:

- LoRA zero-shot versus EXP-025 frozen zero-shot.
- LoRA few-shot versus EXP-025 frozen few-shot.
- Each LoRA condition versus all three frozen EXP-020 BERT predictions.

Use 10,000 paired dev-row bootstrap replicates for within-seed Macro-F1 differences.

Seed 42 is the resource-stage gate. Continue to seeds 43 and 44 only when its selected LoRA
condition exceeds the selected frozen EXP-025 condition by at least `0.005`, all verification gates
pass, and the measured budget remains acceptable. Otherwise stop after seed 42 and report it as a
single-seed negative or diagnostic result, not stable superiority. If three seeds run, select the
prompt condition from mean dev Macro-F1 and report mean +/- sample standard deviation.

## Resource Budget

- Train-only smoke: 50 iterations, at most 30 minutes.
- Formal training: at most 18 active hours per seed.
- Full-dev generation: at most 4 active hours per seed.
- Peak MLX memory: at most 14 GB.
- Formal training seeds: at most 3.
- API cost: USD 0.

Crossing a limit stops the run before starting another seed. A stopped or failed run is retained.

## Artifacts and Thesis Mapping

Private/gitignored:

- Expanded train JSONL and smoke JSONL.
- Adapter weights, runtime adapter config, and intermediate checkpoints.

Public:

- Protocol and frozen config.
- Data preparation, zero-step, and smoke reports without raw text.
- Per-seed `run.json`, `stdout.log`, `history.csv`, anonymous dev predictions, complete metrics,
  paired bootstrap, and independent verification.
- Multi-seed aggregate when the repetition gate opens.

Planned thesis destinations:

- `Table-G2-2`: frozen Qwen, LoRA Qwen, and BERT-base dev comparison.
- `Figure-G2-1`: LoRA training loss and resource trace.
- Results: supervised local LLM comparison.
- Discussion: whether supervision adds task competence, format compliance, or both.
- Limitations: post-training confound, dev-only selection, single dataset, and no mechanism claim.
