# EXP-030: Frozen GoEmotions Dev Error Analysis

---
experiment_id: EXP-030
tier: Major
stage: descriptive-frozen-dev-error-analysis
status: frozen-before-raw-text-review
date: 2026-08-02
rq_ids: [RQ-G1, RQ-G2]
---

## Purpose

EXP-030 describes the behavior of three already-selected GoEmotions systems on
the same 5,426-row official dev split:

1. EXP-020 BERT-base-cased supervised fine-tuning, seeds 42, 43, and 44;
2. EXP-025 frozen Qwen3-1.7B, selected constrained few-shot condition;
3. EXP-029 supervised Qwen3-1.7B LoRA, selected constrained zero-shot
   condition, seeds 42, 43, and 44.

The analysis asks:

1. Is LoRA's remaining gap to BERT concentrated in underprediction,
   multi-label rows, long-tail labels, or neutral co-occurrence?
2. Which exact-set errors are stable across seeds, and which are
   initialization-sensitive?
3. Which rows are recovered by LoRA relative to frozen prompting, and which
   rows regress relative to BERT?
4. Which missed-label and spurious-label pairs dominate mixed errors?
5. In a fixed qualitative sample, which linguistic, ontology, context, output
   policy, or annotation factors plausibly contribute to the predictions?

Expected pattern: LoRA should recover many frozen-Qwen failures, while BERT is
expected to retain higher label recall and stronger multi-label coverage. The
registered analysis may falsify either expectation. It does not test an
internal mechanism claim.

## Frozen Inputs

- Dataset: `DATA-GOE-V1`, Google Research agreement-filtered GoEmotions.
- Source revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`.
- Split: official dev only, 5,426 rows, 28 multi-label targets.
- Dev SHA-256:
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Label-order SHA-256:
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- GoEmotions test file: absent and prohibited.

The configuration pins all seven prediction SHA-256 values and these upstream
verification records:

- EXP-020 verification:
  `0a97b9af655c26d33d6c7e96aa1b54c301be2ec31ba222ccafbdad8b79d3780b`;
- EXP-025 verification:
  `3d095e27e24052f64e55cbeeeed2f37775b129f3c4de111f4c90b2e1bde9279c`;
- EXP-029 multi-seed verification:
  `798257185d17b797b3e131924688e30a43d2b87fa0e84acb54183751d090e2cd`.

No model, API, prompt, threshold, checkpoint, or decoder is run or selected in
EXP-030.

## Official Reference Boundary

The GoEmotions paper publishes BERT results on the final test split, not a
fixed validation accuracy. Its full-taxonomy test macro precision, recall, and
F1 are `0.40`, `0.63`, and `0.46`. The official repository publishes split
sizes and evaluation code, including strict multi-label accuracy, but no
single official dev accuracy value.

EXP-030 therefore records the paper's test table only as an external scale and
per-label pattern reference. It must not present a dev-minus-test difference as
a matched comparison, benchmark reproduction, or generalization estimate.

## Full-Split Quantitative Analysis

All 5,426 rows enter the following analyses:

- exact-set stability: all-run correct, all-run wrong, or mixed across seeds;
- per-run exact, underprediction-only, overprediction-only, mixed FP+FN, and
  empty-prediction counts;
- slice metrics for all rows, single-label, any multi-label, neutral-only,
  neutral-plus-emotion, emotion-only multi-label, and long-tail-label rows;
- per-label TP, FP, FN, precision, recall, F1, support, and seed variation;
- missed-label to spurious-label pair counts for mixed errors;
- BERT-to-LoRA and frozen-Qwen-to-LoRA exact-set transitions;
- shared stable errors across all three conditions;
- predicted label cardinality and seed-to-seed prediction-set agreement.

Long-tail means a gold label with fewer than 100 occurrences in this frozen
dev split. A multi-seed row is "stable correct" only when 3/3 seeds exactly
match the gold set and "stable wrong" only when 0/3 do. These are descriptive
stability categories, not ensemble predictions.

The EXP-025/029 output ontology forbids `neutral` from co-occurring with an
emotion label, while 174 unchanged dev gold rows contain that combination.
This structural mismatch is reported as an output-policy boundary. It is not
silently repaired or removed from any denominator.

## Manual Sample Frozen Before Reading Text

The maximum unique qualitative sample is 48 rows. Roles are processed in this
order, and later roles exclude rows selected earlier:

1. `lora_over_bert_recoveries` (up to 8): BERT is exact-wrong for 3/3 seeds and
   LoRA is exact-correct for 3/3 seeds.
2. `bert_over_lora_regressions` (up to 8): BERT is exact-correct for 3/3 seeds
   and LoRA is exact-wrong for 3/3 seeds.
3. `lora_over_frozen_recoveries` (up to 8): frozen Qwen is exact-wrong and LoRA
   is exact-correct for 3/3 seeds.
4. `neutral_cooccurrence_errors` (up to 8): gold contains `neutral` plus at
   least one emotion and LoRA is exact-wrong for 3/3 seeds.
5. `shared_errors` (up to 8): frozen Qwen and every BERT/LoRA seed are
   exact-wrong.
6. `ordinary_lora_errors` (up to 8): LoRA has at most one exact-correct seed;
   up to four rows bearing a long-tail gold label and four other rows are
   selected when eligible.

Within each role, rows are ordered by SHA-256 of
`20260802:<role>:<row_number>`. A first pass permits at most two cases per
least-supported gold-label stratum; a second pass fills remaining role slots
without replacing earlier roles. If a role is underfilled, no new case type is
substituted.

## Qualitative Coding

One reviewer may assign multiple evidence flags:

- sarcasm or irony;
- negation;
- implicit emotion;
- mixed emotion;
- slang or surface noise;
- possible context dependency;
- annotation ambiguity;
- lexical-cue conflict;
- minority-class membership;
- overlapping labels in the gold set.

The reviewer chooses one primary possible source:

- annotation or data uncertainty;
- overlapping label ontology;
- missing context;
- model or representation limitation;
- surface-form noise;
- output policy or label mapping;
- uncertain.

These codes are hypotheses about observed failures, not revised ground truth,
dataset-wide prevalence estimates, causal explanations, or internal-model
mechanism evidence. Inter-rater reliability is unavailable with one reviewer.

## Privacy Boundary

Tracked outputs contain anonymous row numbers, labels, predictions, metrics,
and qualitative codes only. Selected raw comments are written to:

```text
runs/exp-030-frozen-dev-error-analysis/private/selected_text.private.jsonl
```

That directory is gitignored. Upstream comment IDs, raw comments, and private
free-form notes must not enter tracked CSV, JSON, Markdown, or log artifacts.

## Outputs and Verification

Planned tracked outputs include:

- `run.json` and `aggregate_summary.json`;
- `condition_stability.csv`, `error_modes.csv`, and `slice_metrics.csv`;
- `per_label_metrics.csv` and `missed_spurious_pairs.csv`;
- `pairwise_transitions.csv` and `seed_agreement.csv`;
- `official_reference.json`;
- `sample_manifest.csv`, `manual_annotations.csv`, and qualitative summaries;
- `REPORT.md` and `verification.json`.

Verification must independently check pinned hashes, 5,426 aligned rows, gold
sets against official dev, label order, all aggregates, deterministic sampling,
annotation schema, artifact hashes, test absence, gitignore behavior, and raw
text leakage.

## Resource Budget and Stop Rules

- New model runs or API calls: 0.
- Maximum qualitative rows: 48.
- Maximum wall time: 120 minutes.
- API cost: USD 0.

Stop if an input hash changes, a verifier is not passed, row numbers or gold
sets disagree, `test.tsv` exists, the output directory already contains
artifacts, or a tracked output contains raw text. Observed dev cases may inform
future preregistered experiments, but EXP-030 cannot retroactively change the
frozen EXP-020/025/029 results.
