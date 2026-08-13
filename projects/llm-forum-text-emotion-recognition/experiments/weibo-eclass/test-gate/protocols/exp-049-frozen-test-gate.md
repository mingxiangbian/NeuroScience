# EXP-049: Weibo EClass Frozen Test Gate

---
experiment_id: EXP-049
tier: Major
stage: formal-frozen-test-gate
status: TEST-READY before test access
date: 2026-08-12
rq_ids: [RQ-F1]
---

## Question

On the held-out Weibo EClass split, how do the frozen majority and TF-IDF
baselines, three supervised Chinese encoder seeds, a matched Qwen3-4B
no-adapter reference, and three Qwen3-4B generative LoRA seeds compare in
classification quality, stability, output validity, and local inference cost?

The primary scientific questions are whether the three-seed LoRA family retains
its validation gain over the matched no-adapter Qwen reference and whether it
closes the remaining gap to the three-seed supervised encoder. A negative result
is valid evidence about the limits of using a local generative LLM as a
single-label forum-emotion classifier. This experiment does not test a claim
about internal mechanisms or the faithfulness of generated reasoning.

## Frozen Evaluation Matrix

The formal test contains nine units in this exact order. Every unit is reported;
test results cannot select a seed or an ensemble.

| Unit | Frozen condition | Pre-test selection basis |
| --- | --- | --- |
| 1 | M0 train-majority (`no_emotion`) | Deterministic sanity baseline from EXP-042 |
| 2 | M1 target-only word+character TF-IDF + LinearSVC | Frozen target-only traditional baseline from EXP-042 |
| 3-5 | Chinese RoBERTa-WWM-ext target-only, seeds 42/43/44 | EXP-042 final epoch checkpoints; target-only selected by the frozen practical-tie rule |
| 6 | Qwen3-4B BF16 target-only reasoning-on, no adapter | Matched singleton reference from EXP-047 |
| 7-9 | Qwen3-4B BF16 target-only reasoning-on LoRA, seeds 42/43/44 | All three verified EXP-047 adapters; no best-seed selection |

The `previous_context` conditions are excluded because EXP-042 and EXP-043
selected `target_only` on validation before this gate. EXP-049 does not reopen
input-view selection. M0 and M1 are fitted once from the frozen train split
under their deterministic EXP-042 algorithms; the encoder and LoRA units load
the exact frozen checkpoints or adapters.

## Data And Sealing

- Dataset protocol: `DATA-WEIBO-TASK-V1`.
- Train: 5,995 rows, used only to reconstruct M0 and M1.
- Held-out test: 1,273 input rows.
- Labels: `anger`, `joy`, `negative`, `neutral`, `no_emotion`, `positive`,
  `sadness`.
- Test-input SHA-256:
  `5229637a285179a3626858edc369664d159fe9c99cd7bb03aae8fbc868f4406e`.
- Sealed-label SHA-256:
  `649ce91f58aa7550e76450c25a571f5dbbe3b03c70ba0e9e07fb53c84cdfd002`.

The TEST-READY builder and verifier may read the public dataset manifest and
the already-consumed train/validation evidence. They must not open either test
file. During formal execution, each inference worker may open the label-free
test inputs. The sealed labels remain unopened until all nine complete private
prediction files exist and their hashes are recorded. The finalizer then opens
the labels once and does not call any model.

This two-phase state machine prevents partial test metrics from influencing the
remaining formal units. Technical resume is permitted only for an exact prefix
of one Qwen prediction file; completed rows are never regenerated.

## Metrics And Frozen Contrasts

Primary metric: Macro-F1 over all seven labels.

Required auxiliary evidence:

- Accuracy, macro precision, macro recall, and Weighted-F1;
- per-label precision, recall, F1, support, and predicted support;
- confusion matrices with rows as gold and columns as predictions, including an
  `__invalid__` Qwen-output column;
- the frozen slices `all`, `context_available`, `first_clause`,
  `ambiguous_target`, `unambiguous_target`, `no_emotion`, `emotion_label`, and
  `long_tail_label`;
- for Qwen: strict-parser validity and errors, likely truncation, generated and
  reasoning token counts, latency, peak memory, and API cost;
- three-seed family mean and sample standard deviation.

`long_tail_label` is frozen from validation before test and means the four labels
with fewer than 64 validation examples: `anger`, `joy`, `neutral`, and `sadness`.

The primary contrasts are:

1. mean LoRA Macro-F1 minus matched Qwen-reference Macro-F1;
2. mean LoRA Macro-F1 minus mean encoder Macro-F1.

A secondary diagnostic contrast is mean encoder Macro-F1 minus M1 Macro-F1.
Each contrast uses 2,000 deterministic paired bootstrap resamples at `group_id`
level. The frozen practical-effect threshold is an absolute Macro-F1 difference
of `0.005`: larger positive values are material improvements, larger negative
values are material degradations, and values inside the interval are practical
ties. Bootstrap intervals quantify held-out group sampling uncertainty; three
observed seeds still provide only limited training-run uncertainty.

## Test Gate And Stop Rules

Before test access, all of the following must pass:

- this protocol, runner, unit tests, independent verifier, and contract builder
  have frozen hashes;
- EXP-042, EXP-047 matched validation, and EXP-048 verification artifacts retain
  their expected status and hashes;
- all three encoder checkpoints, the Qwen BF16 model, all three adapters, prompt,
  parser, train data, and public dataset manifest match their frozen hashes;
- both Python environments and package versions match the validated runtimes;
- the public and private EXP-049 output directories are absent;
- the explicit user authorization record covers all nine units and one final
  label-opening step;
- the TEST-READY verifier records that neither test file was opened.

Formal execution stops on artifact drift, output-order drift, duplicate or
missing row identity, schema drift, non-finite scores, token-budget overflow,
MPS/MLX failure, private-output permission failure, unexpected label access,
or resource-budget excess. No retry, prompt repair, parser repair, checkpoint
replacement, result-based seed choice, or model change is allowed. A failed
technical run must be documented; it cannot be silently replaced.

After finalization, the test is consumed. Any later development is explicitly
post-test development and cannot use this split as validation.

## Resource Budget

- Formal test units: 9, one pass per unit.
- Baseline and encoder wall time: at most 2 hours total.
- Qwen no-adapter reference: at most 30 active generation hours.
- Each Qwen LoRA unit: at most 3 active generation hours; all Qwen units at
  most 39 active generation hours total.
- Peak MLX memory: at most 13 GB.
- Bootstrap repeats: 2,000.
- External API calls and API cost: none, USD 0.
- Hardware: local Apple Metal using the already-verified MPS and MLX runtimes.

The unusually large reference budget is based on its frozen validation runtime,
where long reasoning generations took about 22 hours. Reducing `max_new_tokens`,
changing batching, or disabling reasoning would define a different condition and
is prohibited in this gate.

## Privacy And Outputs

Raw text, source IDs, group IDs, gold labels, per-row predictions, probabilities,
and generated reasoning remain under the gitignored private data tree with mode
`0600` and parent mode `0700`. Public outputs contain only aggregate metrics,
resource summaries, hashes, and condition names. Public files must not contain
source sample IDs, raw target text, or raw generation output.

A separate verifier must independently rebuild row alignment, all metrics,
slices, confusion matrices, family summaries, bootstrap contrasts, artifact
hashes, file permissions, Git ignore state, and the public privacy boundary
without importing the runner or its common module. Only a final
`verification.json` with status `Verified` permits these numbers to enter the
thesis evidence log.

## Thesis Destination

- Results: the same-task Weibo EClass model comparison table, per-label appendix,
  dev-to-test generalization summary, and cost table.
- Discussion: supervised encoder versus generative LLM, LoRA gains over a matched
  base-model runtime, minority-label limits, invalid-output behavior, and the
  distinction between classification evidence and representation mechanisms.
- Evidence registry: one EXP-049 entry linked to RQ-F1.
