# EXP-017: Frozen TweetEval Test Error Analysis

---
experiment_id: EXP-017
tier: Major
stage: descriptive-frozen-test-error-analysis
status: frozen-before-raw-text-review
date: 2026-07-30
rq_ids: [RQ-B2, RQ-B3]
---

## Purpose

EXP-017 describes where the already-frozen EXP-016 systems succeed and fail. It
does not train, tune, select, or rerun a model. The official TweetEval test split
has already been consumed, so all findings are descriptive and cannot be used to
replace EXP-016 or justify a new "unbiased" test result.

The analysis asks:

1. Which classes and confusion pairs account for the frozen systems' errors?
2. Which errors are stable across seeds, and which depend on initialization?
3. Which cases are shared by the traditional and neural conditions?
4. Which cases are consistently recovered or regressed when only the base
   encoder changes from generic RoBERTa (EXP-014) to Twitter-domain RoBERTa
   (EXP-015)?
5. In a fixed qualitative sample, which linguistic or data factors plausibly
   contribute to the observed predictions?

## Frozen Inputs

- Dataset: TweetEval emotion, upstream commit
  `4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66`.
- Split: official test only, 1,421 rows.
- Labels: `0=anger`, `1=joy`, `2=optimism`, `3=sadness`.
- Test text SHA-256:
  `7e1070f5d3e3fcece5bc73680bff9981e90d8f7b2f1009bfe7a01d059d1c6091`.
- Test labels SHA-256:
  `245072348c711961785be6d395997f97cf7fcda3effeae7805664171dc75f913`.
- EXP-016 run SHA-256:
  `f12617542c943193e8e069c782622bd2227e14d78030a904a80814c57ab352f4`.
- EXP-016 verification SHA-256:
  `0173ccfbd40c82f02f6c3b37578072b4d3250a4a8c4fc3bd8149ccfd6299d9b8`.

The four conditions are the single frozen EXP-007 Linear SVM and seeds 42, 43,
and 44 from EXP-011, EXP-014, and EXP-015. Prediction artifact hashes are read
from the pinned EXP-016 run and verified before analysis.

## Full-Split Analysis

All 1,421 anonymous rows are included in:

- per-condition and per-class counts of all-seed correct, all-seed wrong, and
  mixed-seed outcomes;
- seed-level confusion counts and rates;
- EXP-011 to EXP-014 and EXP-014 to EXP-015 transitions based on the number of
  correct seeds;
- shared errors across EXP-007 and all three neural conditions;
- class-focused reporting for optimism.

A neural row is "all-seed correct" only when 3/3 seeds are correct and
"all-seed wrong" only when 0/3 are correct. These categories describe
cross-seed stability; they are not ensemble predictions. Seed-level confusion
counts retain every seed as a separate model-sample observation.

## Manual Sample Frozen Before Reading Text

The maximum unique sample budget is 48. Roles are processed in this order, and
later roles exclude rows selected earlier:

1. `final_high_confidence_errors` (up to 16): EXP-015 predicts one identical
   wrong class for 3/3 seeds. Select up to two false negatives per gold class,
   ranked by mean probability on the unanimous wrong class, then up to two
   previously unseen false positives per predicted class using the same rank.
2. `domain_recoveries` (up to 8): EXP-014 is wrong for 3/3 seeds and EXP-015 is
   correct for 3/3 seeds. Select up to two per gold class by descending increase
   in mean gold-label probability.
3. `domain_regressions` (up to 8): EXP-014 is correct for 3/3 seeds and EXP-015
   is wrong for 3/3 seeds. Select up to two per gold class by ascending change
   in mean gold-label probability.
4. `shared_errors` (up to 8): EXP-007 is wrong and every seed of EXP-011,
   EXP-014, and EXP-015 is wrong. Select up to two per gold class in
   deterministic SHA-256 order using seed `20260730`.
5. `ordinary_final_errors` (up to 8): EXP-015 has at most one correct seed and
   the row was not selected earlier. Select up to two per gold class in the same
   deterministic hash order.

If a role or class stratum contains too few eligible unseen rows, it remains
underfilled. No other case type is substituted. The public manifest records the
realized count.

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
- minority-class membership.

The reviewer must also choose one primary possible source:

- annotation or data uncertainty;
- overlapping label ontology;
- missing context;
- model or representation limitation;
- surface-form noise;
- uncertain.

These are qualitative judgments, not new ground-truth labels or causal
explanations. `possible_context_dependency` means the isolated text appears
insufficient; no conversation context is available in TweetEval to verify that
claim. Inter-rater reliability is unavailable with one reviewer.

## Privacy Boundary

Tracked artifacts contain only row IDs, labels, predictions, probabilities,
qualitative flags, and aggregate statistics. Selected raw texts are written to:

```text
runs/exp-017-frozen-error-analysis/private/selected_text.private.jsonl
```

That directory is gitignored. Raw text and free-form private notes must never be
copied into the public report, `run.json`, evidence log, or tracked CSV files.

## Outputs and Verification

Planned tracked outputs:

- `run.json`;
- `aggregate_summary.json`;
- `condition_stability.csv`;
- `seed_confusions.csv`;
- `pairwise_transitions.csv`;
- `sample_manifest.csv`;
- `manual_annotations.csv`;
- `REPORT.md`;
- `verification.json`.

Verification must check pinned input hashes, 1,421 aligned row IDs, label
consistency across all ten prediction files, deterministic sample membership,
public annotation schema, aggregate recomputation, artifact hashes, and absence
of a raw-text column in tracked tables.

## Resource Budget and Stop Rules

- New model runs or API calls: 0.
- Maximum qualitative cases: 48.
- Maximum wall time: 120 minutes.
- API cost: USD 0.

Stop if any pinned hash changes, row IDs or labels disagree, EXP-016 is not
verified, a tracked output contains raw text, or the output directory already
exists. Do not use any observed case to tune a model, prompt, threshold,
preprocessing rule, or label mapping.
