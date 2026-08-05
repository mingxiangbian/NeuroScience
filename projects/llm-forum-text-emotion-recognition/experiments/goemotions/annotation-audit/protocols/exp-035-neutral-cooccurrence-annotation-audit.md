# EXP-035: Neutral Co-occurrence Annotation Audit

---
experiment_id: EXP-035
tier: Major
stage: train-only-annotation-and-data-audit
status: frozen-before-raw-annotation-access
date: 2026-08-04
rq_ids: [RQ-G2]
parent_experiment: EXP-034
data_protocol: DATA-GOE-ANNOT-AUDIT-V1
---

## Purpose

EXP-034 found zero `neutral+emotion` predictions on all 1,396 matching examples seen during
EXP-033 training. EXP-035 asks whether these official simplified targets primarily represent:

1. same-rater co-selection of neutral and emotion;
2. cross-rater disagreement that becomes a co-label only after the `>=2 raters` aggregation rule;
3. annotations marked unclear;
4. comments whose emotion is difficult to infer without conversational context.

The experiment audits data and annotation structure. It does not evaluate a model or infer an
internal mechanism.

## Frozen Inputs and Join

- Simplified source: `DATA-GOE-V1` train only, 43,410 rows.
- Train SHA-256: `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Labels SHA-256: `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Frozen audit slice: all 1,396 train rows containing label 27 (`neutral`) and another label.
- Raw sources, HTTP identities, retained fields, and transport caveat are defined by
  `DATA-GOE-ANNOT-AUDIT-V1` and the hashed config.
- Simplified dev and test are prohibited. Parent comments are not retrieved.

## Quantitative Questions

For every selected comment, independently aggregate raw per-rater records and report:

- number of raters and number marking `example_very_unclear`;
- vote count for neutral and each retained emotion;
- whether any individual rater selected neutral plus an emotion;
- whether the simplified co-label exists only because different raters supplied the neutral and
  emotion votes;
- whether applying the official threshold of at least two raters exactly reproduces the simplified
  label set;
- distributions by emotion label, gold cardinality, rater count, neutral votes, and same-rater
  co-selection count.

`aggregation-only` means the simplified target contains neutral and emotion while no individual
rater selected neutral together with any emotion. It is evidence about annotation aggregation, not
proof that the comment has no mixed emotional meaning.

## Frozen Qualitative Sample

After quantitative aggregation but before reading any selected text, choose at most 48 unique rows.
Roles are processed in order and exclude earlier selections:

1. `aggregation_only` (up to 16);
2. `same_rater_coselection` (up to 16);
3. `any_unclear` (up to 8);
4. `gold_cardinality_at_least_3` (up to 4);
5. `residual_fill` until the total reaches 48.

Within each role, rank by SHA-256 of
`20260804:EXP-035:<role>:<source_train_row>`. An underfilled role is not replaced by a new category;
the residual role may fill the remaining overall budget.

## Qualitative Coding

One reviewer assigns one value per field:

- standalone decidability: `explicit`, `implicit_but_decidable`, `context_likely_needed`, or
  `indeterminate`;
- label coherence: `both_plausible`, `emotion_only_plausible`, `neutral_only_plausible`, or
  `ambiguous`;
- context trigger: zero or more of `reply_reference`, `pronoun_or_deixis`, `sarcasm_or_irony`,
  `external_event`, or `none`;
- annotation interpretation: `cross_rater_disagreement_likely`, `genuine_multilabel_possible`,
  `unclear_case`, or `uncertain`;
- reviewer confidence: `low`, `medium`, or `high`.

These codes are hypotheses from a purposive single-reviewer sample. They do not revise gold labels,
estimate dataset-wide context prevalence, or measure inter-rater reliability.

## Decision Rules

- If more than half of all 1,396 rows are `aggregation-only`, treat annotation aggregation as a
  primary explanation for the disputed target structure. Keep the official baseline unchanged,
  but do not optimize a thesis model to reproduce this structure without a separate ontology or
  soft-label experiment.
- If at least half contain same-rater co-selection, the structure is not mainly explained by
  cross-rater aggregation; proceed to the previously proposed train-only learnability/exposure
  diagnostic.
- Context is considered a credible follow-up only descriptively. Regardless of the sample count,
  adding parent text to GoEmotions requires a new context-aware data protocol and ideally
  context-aware reannotation because original raters did not see thread context.
- Any join or threshold-reproduction discrepancy stops these decisions.

## Outputs

Tracked:

- `run.json`, `source-manifest.json`, `aggregate-summary.json`;
- `row-audit.csv`, `per-emotion-summary.csv`, `vote-patterns.csv`;
- `sample-manifest.csv`, `manual-annotations.csv`, `qualitative-summary.json`;
- `REPORT.md`, `verification.json`.

Private and gitignored:

- matched per-rater annotation records;
- selected raw comments and private reviewer notes.

## Resource Budget and Stop Rules

- Raw archive streams: at most one successful pass over each of three files.
- Model/API calls: 0.
- Maximum qualitative rows: 48.
- Wall time: 90 minutes.
- API cost: USD 0.

Stop on changed inputs, source identity mismatch, unexpected schema, missing/duplicate join,
text mismatch, threshold-reproduction mismatch, existing nonempty run directory, simplified test
presence, or tracked raw-text/identifier leakage.

