# EXP-033: Target-Aligned LoRA for Qwen3-1.7B on GoEmotions

## Registration

- Experiment ID: `EXP-033`
- Tier: `Major`
- RQ: `RQ-G2`
- Registered: `2026-08-03`, before EXP-033 model execution or results
- Parent experiments: `EXP-029`, with the target-ontology correction established by `EXP-031`
- Status at registration: `Registered`
- Test gate: closed; `test.tsv` must remain absent

### Pre-smoke implementation correction, 2026-08-03

The first no-model runner dry-run passed its own independent recomputation, but a separate
read-only review found four execution-control weaknesses before any smoke or formal training:

- verification artifacts were not checked strictly enough before authorization;
- a silent MLX subprocess could evade the wall-clock timeout;
- runner and verifier duplicated the same runtime-config translation;
- this protocol was not bound by SHA-256.

The V1 dry-run artifacts remain append-only intermediate evidence. They do not authorize model
execution. Runner contract V2 must bind this protocol, consume a separately frozen canonical MLX
runtime contract, enforce timeout outside the stdout reader, re-run the independent verifier in
check mode before smoke authorization, and keep formal training hard-disabled until a smoke
verifier is separately frozen. This correction changes execution safeguards, not the research
question, data, model, training condition, metrics, or selection rule.

## Question

When every supervised target preserves the official GoEmotions label set, including
`neutral` co-occurring with emotion labels, does Qwen3-1.7B LoRA learn a materially better
multi-label classifier than EXP-029, whose training targets removed `neutral` from 1,396 such
rows?

The experiment isolates a target-contract correction. It measures classification behavior and
does not establish an emotion mechanism or a faithful account of the model's internal reasoning.

## Hypotheses

- Primary: target alignment improves validation Macro-F1 by at least `0.005` over the selected
  EXP-029 condition under the same aligned inference ontology.
- Diagnostic: target alignment increases predicted label cardinality and improves behavior on
  official `neutral + emotion` rows without materially degrading non-neutral labels.
- Negative result: the small model continues to emit mostly single-label predictions, implying
  that the low cardinality is not explained mainly by EXP-029's target deletion rule.

## Controlled Change

Changed:

- Preserve every official train label exactly, including `neutral + emotion` combinations.
- Use the EXP-031 prompt and finite-state output constraint that allow those combinations.

Held fixed from EXP-029:

- GoEmotions train rows, label order, and source SHA-256.
- Qwen3-1.7B revision, local BF16 weights, and absence of quantization.
- LoRA placement, rank, scale, dropout, trainable-parameter count, optimizer, learning rate,
  batch/accumulation, maximum sequence length, epoch count, and seed schedule.
- Prompt masking, disabled-thinking inference condition, greedy decoding, metrics, practical tie
  threshold, and resource gates.

The prepared JSONL is already frozen. EXP-033 has no command that can rebuild or rewrite it.

## Data Contract

- Source train: 43,410 rows; SHA-256
  `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Prepared train JSONL: 43,410 rows; SHA-256
  `493ecaafd6cd6ed5ee20f8ec3c262e291a6eee826a97816955b53effc1c1c09f`.
- Boundary smoke JSONL: 64 train rows; SHA-256
  `0fa3b51ff3ed68d3ba7460a7ace7d053faeb6dc5134967fdb113b826f0e13404`.
- Labels: 28 ordered labels; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Official `neutral + emotion` train rows retained: 1,396.
- Target cardinality support: 36,308 one-label; 6,541 two-label; 532 three-label;
  28 four-label; 1 five-label row.
- Truncation: two inputs have only their text tail truncated; every complete target is retained.
- Validation is not read during data preparation, dry-run, or train-only smoke.
- Test is absent and forbidden.

The smoke subset covers all 28 labels, includes 16 `neutral + emotion` rows, includes both
truncated rows, contains four- and five-label targets, and reaches 512 tokens. It is a boundary
test, not validation evidence.

## Model and Training

- Base: `Qwen/Qwen3-1.7B`, revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- Local format: MLX BF16, unquantized.
- Adapted blocks: final 16 of 28, indices 12 through 27.
- Modules per block: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, and
  `down_proj`.
- Rank: 8; MLX scale: 20.0; dropout: 0.0.
- Expected trainable parameters: 4,980,736.
- Optimizer: Adam; constant learning rate `1e-5`.
- Micro-batch: 2; gradient accumulation: 5; effective batch: 10.
- One epoch: 21,705 micro-iterations and 4,341 optimizer updates.
- Maximum sequence length: 512; prompt masking enabled.
- Seed 42 runs first. Seeds 43 and 44 remain gated by validation gain and resources.

## Execution Gates

The stages are ordered and cannot authorize themselves:

1. Hash-freeze the standalone EXP-033 runner and independent verifier.
2. Run a no-model dry-run that rechecks inputs, environment, output boundaries, and exact MLX
   runtime configs. It must not import or invoke model execution.
3. Independently verify the dry-run and recheck the PRE-EXP-033 execution V3 evidence chain.
4. Obtain explicit authorization bound to the current config and dry-run verification hashes.
5. Run one 50-iteration train-only smoke.
6. Independently verify finite loss, non-zero adapter weights, peak memory, throughput, exact
   iteration count, and train-only split access.
7. Freeze that smoke verifier and a new formal-execution gate; V2 keeps formal training disabled.
8. Obtain separate authorization before formal seed-42 training.

Smoke or formal commands without a valid stage-specific authorization artifact must fail before
creating an adapter directory or invoking `mlx_lm.lora`.

## Model Selection and Repetition

Formal validation is deferred until the seed-42 adapter is frozen. The primary metric remains
Macro-F1 across all 28 labels; auxiliary metrics include macro precision/recall, micro and
weighted F1, samples F1, subset accuracy, Hamming loss, per-label metrics, prediction cardinality,
parser validity, latency, and resource use.

An absolute Macro-F1 difference below `0.005` is a practical tie. Continue to seeds 43 and 44
only if the independently verified selected seed-42 EXP-033 result exceeds the selected EXP-025
frozen result by at least `0.005` and resource limits pass. A direct EXP-033 versus EXP-029
comparison must use the same validation rows, aligned inference ontology, and prompt condition.

No test result may affect this selection.

## Resource Budget

- No-model dry-run: no model forward/backward and no API use.
- Train-only smoke: 50 iterations, at most 30 minutes.
- Formal training: at most 18 active hours per seed.
- Full-validation generation: at most 4 active hours per seed.
- Peak MLX memory: at most 14 GB.
- Formal seeds: at most 3, subject to the repetition gate.
- API cost: USD 0.

## Artifacts and Thesis Mapping

Private/gitignored:

- Frozen prepared train and boundary-smoke JSONL.
- Adapter weights, runtime adapter configuration, and checkpoints.

Public:

- This protocol and frozen experiment config.
- No-model dry-run, generated runtime configs, and independent verification.
- Authorized smoke report and later per-seed run artifacts without raw text.
- Formal validation predictions, complete metrics, error analysis, and verification after training.

Planned thesis destinations:

- `Table-G2-2`: frozen Qwen, EXP-029 LoRA, target-aligned EXP-033 LoRA, and BERT-base.
- `Figure-G2-1`: training/resource trace for the selected LoRA condition.
- Results: effect of supervised target alignment.
- Discussion: output-format learning, multi-label competence, and small-model capacity limits.
- Limitations: post-training confound, single dataset, validation-based selection, and no
  mechanism claim.
