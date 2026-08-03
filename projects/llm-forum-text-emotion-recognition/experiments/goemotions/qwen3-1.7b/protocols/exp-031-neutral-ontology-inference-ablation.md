# EXP-031: Neutral Co-occurrence Inference Ablation

## Registration

- Experiment ID: `EXP-031`
- Tier: `Major`
- RQ: `RQ-G2`
- Parent experiment: `EXP-029`
- Registered: `2026-08-02`, before any EXP-031 dev result
- Status at registration: `Registered`
- Test gate: closed; `test.tsv` must remain absent

## Motivation and Correction Boundary

The original EXP-022 prompt and finite-state decoder treated `neutral` as mutually exclusive with
all emotion labels. The official simplified GoEmotions files do not impose that restriction:
`neutral` co-occurs with another label in 1,396 train rows and 174 dev rows. EXP-029 therefore
removed only co-occurring `neutral` targets during training so its targets remained representable
under the already frozen EXP-022 output ontology.

That was an experiment-design mismatch, not a change in the official dataset. The completed
EXP-029 results remain valid evidence for a deliberately closed output ontology. EXP-031 measures
how much of the observed behavior changes when the inference ontology is opened. It does not
rewrite or overwrite EXP-029.

## Question and Hypotheses

Question: how much do the hard decoder restriction and the matching prompt instruction contribute
to the frozen EXP-029 LoRA model's dev predictions, especially on official neutral co-occurrence
rows?

- H1: opening only the decoder produces some `neutral + emotion` predictions, showing that the
  hard finite-state constraint previously blocked outputs the model would otherwise select.
- H2: aligning the prompt with the official open ontology increases neutral co-prediction and
  improves the 174-row neutral-co-occurrence slice relative to the closed EXP-029 condition.
- Negative result: neither inference change materially improves full-dev Macro-F1, because the
  LoRA adapters were trained on targets from which co-occurring `neutral` had been removed.

The practical-effect threshold is an absolute Macro-F1 change of `0.005`. A smaller change is
reported as practically tied, even if a bootstrap interval excludes zero.

## Frozen Conditions

EXP-031 reuses each seed's final EXP-029 adapter. It performs no training and no model selection.
All three inferential conditions are rerun contemporaneously under the same code and environment;
saved EXP-029 predictions are retained only as a reproducibility reference.

1. `old-prompt-closed-decoder` (primary baseline): old prompt plus old decoder, which forbids
   `neutral` co-occurrence.
2. `old-prompt-open-decoder`: old prompt still says never to combine `neutral`, while a new decoder
   permits any unique combination of the 28 labels.
3. `aligned-prompt-open-decoder`: corrected prompt and the same open decoder both permit
   `neutral` co-occurrence.
4. `exp-029-zero-shot-closed-ontology` (historical reference only): saved, independently verified
   EXP-029 predictions under condition 1's intended policy.

Matched interpretation:

- Condition 2 minus the contemporaneous condition 1 estimates the effect of removing the hard decoder restriction
  while holding the old instruction fixed.
- Condition 3 minus contemporaneous condition 2 estimates the effect of correcting the instruction under the
  same open decoder.
- Condition 3 minus contemporaneous condition 1 estimates the total inference-policy effect.
- Contemporaneous condition 1 minus historical condition 4 audits deterministic reproducibility;
  it is not used as the primary decoder-effect baseline.

These are matched behavioral condition contrasts, not mechanistic claims about internal emotion
representations. The design does not include `aligned-prompt-closed-decoder`, so it does not
estimate a full factorial prompt main effect or prompt-by-decoder interaction. Because the adapter
targets were not corrected, EXP-031 also cannot estimate the effect of target-aligned retraining.

## Frozen Inputs

- Dev: all 5,426 `DATA-GOE-V1` rows; SHA-256
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Labels: all 28 labels in official order; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Gold labels: unchanged, including all 174 rows containing `neutral` plus another label.
- Seeds/adapters: EXP-029 seeds 42, 43, and 44, each pinned by adapter-weight and adapter-config
  SHA-256.
- Historical closed references: each seed's independently verified EXP-029 zero-shot prediction
  file, pinned by SHA-256 and reused without regeneration only for the reproducibility audit; the
  primary closed baseline is regenerated contemporaneously in EXP-031.
- Model: local unquantized BF16 `Qwen/Qwen3-1.7B`, revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- Every model/tokenizer file listed by the frozen manifest is rehashed before execution; the MLX,
  MLX-LM, NumPy, Transformers, and Python versions are also frozen.
- Test: not acquired and forbidden.

No input text, Reddit comment ID, or raw generation is written to public artifacts. Records contain
only anonymous row numbers, gold/predicted labels, output hashes, parser state, scores, and resource
telemetry.

## Decoding and Execution

- Greedy decoding, temperature 0, batch size 1.
- Thinking disabled.
- Maximum 64 generated tokens.
- No retry, repair, fallback, or post-hoc label mapping.
- Invalid or length-terminated outputs become empty predictions.
- The old and new finite-state grammars both keep exact label-name JSON, a non-empty array, known
  labels, and no duplicates; the new grammar changes only the exclusivity rule for `neutral`.
- The three contemporaneous condition positions rotate by dev row to reduce simple runtime-order
  confounding.
- A synthetic-only smoke test on seed 42 must verify model loading, both prompts, open grammar
  examples, and the absence of test access before full dev inference.

## Evaluation

Primary metric: Macro-F1 across all 28 labels.

Secondary metrics:

- Macro precision and recall; Micro-F1; weighted F1; Samples-F1.
- Strict subset/exact-match accuracy, Hamming loss, and label accuracy.
- Gold and predicted label cardinality.
- Per-label precision, recall, F1, support, and predicted support.
- Parser validity, finish reasons, decoder intervention, latency, tokens, sequence scores, and peak
  memory.
- Number of predicted `neutral + emotion` rows.

Pre-registered slices:

- all 5,426 rows;
- 4,548 single-label rows;
- 878 multi-label rows;
- 174 gold neutral-co-occurrence rows;
- 5,252 rows outside that neutral-co-occurrence slice.

For each open condition, report exact-match transitions relative to the paired contemporaneous
closed baseline:
improved, worsened, unchanged correct, and unchanged wrong. Use 10,000 paired dev-row bootstrap
replicates for the three inferential Macro-F1 contrasts plus the historical reproducibility audit.
Report each seed separately and mean plus sample standard deviation across seeds; do not select a
condition for a later test from EXP-031.

## Decision Rule

- If the aligned open condition improves mean full-dev Macro-F1 by at least `0.005` over the
  closed condition, while neither exact match nor Samples-F1 falls by more than `0.005`, retain it
  as evidence that the inference ontology correction matters generally.
- If that general rule fails but Samples-F1 on the 174-row neutral-co-occurrence slice improves by
  at least `0.005`, and full-dev Macro-F1 does not fall by more than `0.005`, report a localized
  ontology correction rather than a general model improvement.
- If the slice improves but full-dev Macro-F1 falls by more than `0.005`, report "localized gain
  with global regression" rather than calling the condition an improvement.
- If opening the ontology increases false co-predictions or worsens full-dev behavior, retain the
  negative result. It supports neither keeping the wrong ontology nor rejecting corrected
  retraining; it shows only that inference-time correction is insufficient for this adapter.

The test gate remains closed for every outcome.

## Resource Budget and Stop Conditions

- New full-dev conditions: exactly 3 per seed.
- Seeds: exactly 42, 43, and 44; no additional seed or hyperparameter trial.
- Synthetic smoke: at most 10 active minutes.
- Full-dev inference and finalization: at most 6 cumulative active hours per seed.
- Peak MLX memory: at most 14 GB.
- API cost: USD 0.

Any hash mismatch, test-file presence, invalid parent verification, incomplete deterministic record
prefix, memory breach, or time breach stops the affected run. Failed or partial artifacts are
retained and never relabeled as verified evidence. A memory or time breach is terminal and cannot
be resumed. Non-resource interruptions may resume only from the exact deterministic record prefix;
metadata and aggregate publication use atomic writes or exact-content recovery.

## Artifacts and Thesis Mapping

Public artifacts:

- protocol and frozen config;
- synthetic smoke report without dataset text;
- per-seed run metadata and anonymous generation records;
- per-condition predictions, complete metrics, per-label metrics, and confusion matrices;
- paired bootstrap, registered slice metrics, ontology transition counts, and independent
  verification;
- multi-seed aggregate, seed summary, and concise report.

Planned thesis destinations:

- `Table-G2-4`: closed ontology versus decoder-open versus fully aligned inference.
- Error analysis: neutral co-occurrence and multi-label failure modes.
- Discussion: output-ontology design, constrained decoding, and supervision/inference mismatch.
- Limitations: dev-only inference ablation, post-trained base model, target-misaligned adapters, and
  no internal-mechanism claim.
