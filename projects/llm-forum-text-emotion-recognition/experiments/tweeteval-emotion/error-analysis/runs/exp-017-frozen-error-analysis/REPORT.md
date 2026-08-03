# EXP-017 Frozen TweetEval Test Error Analysis

## Scope

This report describes the fixed predictions produced by EXP-016. It does not
rerun inference, select a seed, construct an ensemble, or tune a model. All
1,421 test rows enter the quantitative analysis. Qualitative coding uses the
42 cases selected by the protocol frozen before raw-text review.

Neural "stable wrong" means wrong for all three seeds; "mixed" means the seeds
do not have the same correctness outcome. These are stability categories, not
ensemble metrics. The Linear SVM has one deterministic prediction per row.

## Error Stability

| Condition | All-run correct | All-run wrong | Mixed |
| --- | ---: | ---: | ---: |
| EXP-007 Linear SVM | 996 (70.09%) | 425 (29.91%) | N/A |
| EXP-011 generic RoBERTa | 1,084 (76.28%) | 183 (12.88%) | 154 (10.84%) |
| EXP-014 generic RoBERTa + label smoothing | 1,088 (76.57%) | 181 (12.74%) | 152 (10.70%) |
| EXP-015 Twitter RoBERTa + label smoothing | 1,119 (78.75%) | 155 (10.91%) | 147 (10.34%) |

EXP-015 reduces the stable-error set relative to both generic encoders, but 155
rows remain wrong under every seed. A further 147 rows change correctness
across seeds, so a single-seed error list would conflate persistent failures
with initialization-sensitive cases.

## Class-Level Pattern

| EXP-015 gold class | Stable wrong | Mixed | Stable correct |
| --- | ---: | ---: | ---: |
| anger | 37 / 558 (6.63%) | 42 / 558 (7.53%) | 479 / 558 (85.84%) |
| joy | 32 / 358 (8.94%) | 44 / 358 (12.29%) | 282 / 358 (78.77%) |
| optimism | 32 / 123 (26.02%) | 21 / 123 (17.07%) | 70 / 123 (56.91%) |
| sadness | 54 / 382 (14.14%) | 40 / 382 (10.47%) | 288 / 382 (75.39%) |

Optimism is difficult in two distinct ways: it has both the highest stable-wrong
rate and the highest seed-instability rate. Across the 369 optimism
seed-sample predictions, 62 are mapped to anger (16.80%), 42 to joy (11.38%),
and 25 to sadness (6.78%). The main sadness error is also anger: 129 of 1,146
sadness seed-sample predictions (11.26%).

These counts show where predictions move; they do not establish that the
underlying emotions are psychologically discrete or that the gold label is
wrong.

## Controlled Transitions

Label smoothing changes little at the row-stability level. From EXP-011 to
EXP-014, 80 rows gain correct seeds and 82 lose correct seeds; 1,259 keep the
same correct-seed count. There are no direct 0/3-to-3/3 recoveries or
3/3-to-0/3 regressions. This agrees with the frozen metric result that the small
validation gain did not generalize to test.

Changing only the frozen base encoder from generic to Twitter-domain RoBERTa
has a clearer direction:

| EXP-014 to EXP-015 transition | Rows |
| --- | ---: |
| More correct seeds | 129 |
| Fewer correct seeds | 90 |
| Stable recovery (0/3 to 3/3) | 21 |
| Stable regression (3/3 to 0/3) | 11 |
| Unchanged correct-seed count | 1,170 |

Stable recoveries comprise 12 anger, 2 joy, 0 optimism, and 7 sadness rows.
Stable regressions comprise 4 anger, 0 joy, 0 optimism, and 7 sadness rows.
The small test improvement for optimism therefore does not come from complete
0/3-to-3/3 reversals; it is composed of less extreme seed-level changes.

## Shared and Specific Errors

Eighty-seven rows, 6.12% of the test set, are wrong for the Linear SVM and every
seed of all three neural conditions. They account for 56.13% of EXP-015's 155
stable errors. Their gold-class counts are 15 anger, 19 joy, 21 optimism, and 32
sadness.

Only 12 rows (0.84% of the test set) have EXP-015 as the sole condition in the
stable-wrong state. This does not mean every other model is correct on those
rows: "not stable wrong" also includes mixed-seed outcomes. The complete
four-condition overlap patterns are retained in `stable_error_overlaps.csv`.

## Qualitative Review

The frozen sample contains 16 high-confidence EXP-015 errors, 6 stable domain
recoveries, 4 stable domain regressions, 8 shared errors, and 8 ordinary final
errors. Evidence flags can overlap.

| Possible factor | Cases in the 42-case sample |
| --- | ---: |
| Lexical-cue conflict | 32 |
| Mixed emotion | 27 |
| Possible context dependency | 18 |
| Annotation ambiguity | 16 |
| Slang or surface noise | 16 |
| Implicit emotion | 14 |
| Sarcasm or irony | 13 |
| Negation | 7 |
| Minority-class membership | 6 |

The single reviewer assigned the primary possible source as ontology overlap
for 14 cases, model or representation limitation for 12, annotation or data
uncertainty for 7, surface-form noise for 5, and missing context for 4.

Among the 16 high-confidence errors, 14 contain a lexical-cue conflict and 12
contain mixed emotional evidence; 7 were primarily coded as ontology overlap.
High confidence therefore does not imply that the text cleanly supports one
human-interpretable category.

Five of the six sampled stable domain recoveries contain slang or surface
noise, and three were primarily coded as surface-form noise. This is consistent
with a Twitter-pretrained encoder helping on platform-specific forms in some
cases. It is not a causal attribution: the sample is small, purposive, and the
encoder representations were not intervened on. All four sampled stable domain
regressions contain lexical-cue conflict, but the same limitation prevents a
general prevalence claim.

## What This Establishes

- EXP-015's aggregate gain is accompanied by fewer stable errors and more
  favorable than unfavorable seed-count transitions.
- Optimism remains the clearest failure point, especially through confusion
  with anger and elevated cross-seed instability.
- More than half of EXP-015's stable errors are shared by every frozen
  condition, which points to a hard data/task subset rather than a defect unique
  to one encoder.
- The reviewed failures frequently contain competing lexical, pragmatic, or
  contextual signals. A flat four-class label does not expose that ambiguity.

## Limits and Next Use

The 42-case sample is deliberately stratified and enriched for informative
failures. Its percentages must not be reported as test-set prevalence.
Qualitative coding was performed by one reviewer, so no inter-rater agreement
is available. Possible context dependence cannot be confirmed because the
benchmark supplies isolated Tweets. The codes are hypotheses about errors, not
new labels, causal mechanisms, or evidence about how humans generate emotion.

For future forum data, these findings justify prospectively defining
`unclear/mixed` handling, retaining thread context, and measuring annotation
agreement. Any resulting model or prompt change must be developed on validation
or a new dataset, never selected against these TweetEval test cases.
