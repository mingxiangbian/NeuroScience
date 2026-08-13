# EXP-048: Frozen Weibo EClass Dev Error Analysis

---
experiment_id: EXP-048
tier: Major
stage: descriptive-frozen-validation-error-analysis
status: frozen-before-raw-text-review
date: 2026-08-12
rq_ids: [RQ-F1]
---

## Purpose

EXP-048 analyzes predictions that were already frozen and independently verified in
EXP-042 and EXP-047. It does not train a model, rerun inference, change a prompt, select
a checkpoint, or access the sealed test split.

The analysis asks:

1. How much of EXP-047's improvement over its matched no-adapter reference occurs on
   rows where the reference output was invalid or truncated, and how much remains on
   rows with a valid reference label?
2. Which labels, confusion pairs, and metadata slices account for LoRA's remaining
   gap to the EXP-042 Chinese encoder?
3. Which successes and failures are stable across all three LoRA or encoder seeds,
   and which are seed-sensitive?
4. In a fixed qualitative sample, which linguistic, ontology, context, annotation,
   or output-policy factors plausibly contribute to the observed errors?

The expected pattern is that LoRA repairs both output validity and some label errors,
while the encoder retains an advantage on at least part of the minority-label task.
The registered analysis may falsify either expectation. It does not test an internal
mechanism claim.

## Frozen Inputs

- Dataset protocol: `DATA-WEIBO-TASK-V1`.
- Split: validation only, 1,272 rows.
- Validation SHA-256:
  `99d80e1433bddea7b639983b8fa874e45d585318aa47eb87ab29581e02f72a4a`.
- Labels: `anger`, `joy`, `negative`, `neutral`, `no_emotion`, `positive`,
  `sadness`.
- View: `target_only` for every compared prediction.
- EXP-042 M2 target-only seeds 42/43/44 prediction hashes:
  `7d45a061494162eba05579d0772d39ce4ea6239bbf8f6db0268e600471250d65`,
  `227cfb58a70ad191b50305e76739679eec161f81ef1b06376fce1a9403d610c3`,
  and `e279a142268b247a4e3b6c8e52e5172313bb8ceab8e78899a3cfba7183df8f8a`.
- EXP-047 matched reference and LoRA seeds 42/43/44 prediction hashes:
  `4d66c727b4515977d1e75e21e695f8d33029ea3ce4125aec67848bb20641b60d`,
  `22a6c8a6a81be57bae39f00330d0d152acbc8818bef1cc9fdcee43a0bca7386c`,
  `8204dac4f816a6e7d372887876cc712984288285e0263c5c5d7a884c7e6235df`,
  and `8b1ff34de1ae5ab55f2890790b5747eff1f30039c3408c85e6d8c819a244f128`.
- EXP-042 verification SHA-256:
  `a518135c9bbebf4fb9f6fb080f61c3996772d7d45a6077776ce6a4e99f0f9fb7`.
- EXP-047 matched-validation verification SHA-256:
  `42da926faa9fd4a18ed8d209d7d30bfd54403e8951e0b6b4bb3bb0aae0df90e9`.

The input hashes and row identities must match before analysis. The test inputs and
sealed test labels are prohibited and are not present in the EXP-048 configuration.

## Full-Validation Quantitative Analysis

All 1,272 validation rows enter these analyses:

- per-run Accuracy, Macro-F1, macro precision/recall, and Weighted-F1;
- per-label TP, FP, FN, precision, recall, F1, support, and seed variation;
- confusion-pair counts, including the reference `__invalid__` outcome;
- all-run correct, all-run wrong, and mixed outcomes for the three-seed conditions;
- pairwise seed prediction agreement and correctness agreement;
- reference-to-LoRA and encoder-to-LoRA correctness transitions;
- slices for all rows, local-context availability, first-clause rows,
  `ambiguous_target`, unambiguous rows, `no_emotion`, emotion labels, long-tail
  labels, valid reference output, and failed reference output.

Long-tail means a gold label with fewer than 100 validation examples. A three-seed
condition is `stable correct` only when 3/3 seeds are correct and `stable wrong` only
when 0/3 are correct. These are descriptive stability categories, not ensemble
predictions.

Reference output failure is defined before text review as `parse.valid=false` or
`likely_truncated=true`. Accuracy change can be additively separated into rows with
and without reference output failure. Macro-F1 is non-additive, so EXP-048 reports
valid-output-slice Macro-F1 but does not claim a numerical Macro-F1 decomposition.
Recovery on a failed-output row is evidence of a usable-output recovery, not proof
that formatting alone caused the original classification error.

## Manual Sample Frozen Before Reading Text

The maximum unique qualitative sample is 48 rows. Roles are processed in this order,
and later roles exclude rows selected earlier:

1. `format_recoveries` (up to 8): reference output failed and LoRA is correct for
   3/3 seeds.
2. `valid_reference_recoveries` (up to 8): reference output is valid but wrong and
   LoRA is correct for 3/3 seeds.
3. `lora_over_encoder` (up to 8): encoder is wrong for 3/3 seeds and LoRA is correct
   for 3/3 seeds.
4. `encoder_over_lora` (up to 8): encoder is correct for 3/3 seeds and LoRA is wrong
   for 3/3 seeds.
5. `shared_stable_errors` (up to 8): encoder and LoRA are both wrong for 3/3 seeds.
6. `seed_unstable_lora` (up to 8): LoRA has one or two correct seeds.

Within each role, rows are ordered by SHA-256 of
`20260812:<role>:<sample_id>`. A first pass permits at most two rows per least-supported
gold-label stratum; a second pass fills remaining slots. Underfilled roles remain
underfilled, and no post hoc case type is substituted.

## Qualitative Coding

One reviewer may assign multiple evidence flags:

- sarcasm or irony;
- negation;
- implicit emotion;
- mixed emotion;
- slang or surface noise;
- possible local-context dependency;
- annotation ambiguity;
- lexical-cue conflict;
- sentiment/emotion ontology overlap;
- weak-emotion versus `no_emotion` boundary;
- long-tail class.
- no listed surface or data factor observed.

The reviewer chooses one primary possible source:

- annotation or data uncertainty;
- overlapping label ontology;
- missing local context;
- model or representation limitation;
- output parser or output policy;
- surface-form noise;
- uncertain.

These codes are hypotheses about selected cases. They are not revised ground truth,
dataset-wide prevalence estimates, causal explanations, or faithful accounts of model
reasoning. Inter-rater reliability is unavailable with one reviewer.

## Privacy Boundary

Tracked outputs contain derived case IDs, labels, predictions, aggregate statistics,
and coded flags only. They exclude source sample IDs, group IDs, raw text, generated
reasoning, raw model output, and free-form review notes. The private mapping and review
text are written under:

```text
experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/private/
```

That directory is gitignored and must use restrictive local permissions.

## Outputs and Verification

Planned tracked outputs include:

- `run.json`, `aggregate_summary.json`, and `format_attribution.json`;
- `condition_stability.csv`, `per_class_metrics.csv`, and `class_gap.csv`;
- `confusion_pairs.csv`, `slice_metrics.csv`, `pairwise_transitions.csv`, and
  `seed_agreement.csv`;
- `sample_manifest.csv`, `manual_annotations.csv`, and qualitative summaries;
- `REPORT.md` and `verification.json`.

An independent verifier must recompute input hashes, row alignment, metrics, slices,
transitions, deterministic sampling, qualitative counts, artifact hashes, and public
privacy checks without importing the analysis runner.

## Resource Budget and Stop Rules

- New model runs or API calls: 0.
- Maximum qualitative rows: 48.
- Maximum wall time: 120 minutes.
- API cost: USD 0.

Stop if an input hash changes, an upstream verifier is not passed, row identities or
gold labels disagree, a tracked artifact contains private text or identifiers, or the
analysis attempts to access test. Findings may inform a separately registered future
experiment, but EXP-048 cannot alter EXP-042 or EXP-047 retrospectively.
