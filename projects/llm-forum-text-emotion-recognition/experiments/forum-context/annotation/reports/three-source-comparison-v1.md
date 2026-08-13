# IAC2 Pilot Three-source Comparison V1

- Date: 2026-08-07
- Protocol: `DATA-FCTX-LABEL-V1` / `DATA-FCTX-SAMPLE-V1`
- Amendment: `2026-08-07-direct-comparison`
- Status: exploratory dataset diagnosis; no gold labels produced
- Scope: 120 primary cases, including 80 representative cases and 40 diagnostic cases
- Sources: Human Pass 1, Model 1 and Model 2

## Claim boundary

Model 1 and Model 2 are model outputs, not independent human annotators. The
numbers below are three-source exact comparisons, not inter-annotator agreement.
Model majority does not define gold, Human Pass 1 is not assumed correct by
default, and the waived blind-repeat pass means this pilot provides no estimate of
the human annotator's stability over time.

The comparison script revalidated all four sealed model-output hashes, the 120-row
identity mapping and the decision contracts before calculating aggregates. The
tracked report contains no forum text, source identifiers, sample IDs or per-case
labels. The 106 cases with at least one Stage A or Stage B disagreement remain in a
gitignored private sidecar.

## Main comparison

Agreement is exact status-plus-label agreement. For `other_emotion`, the proposed
label text must also match.

| Stage and subset | All three | Human / M1 | Human / M2 | M1 / M2 | Models agree, human differs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage A, all 120 | 26 (21.7%) | 30 (25.0%) | 31 (25.8%) | 91 (75.8%) | 65 |
| Stage A, representative 80 | 17 (21.3%) | 20 (25.0%) | 21 (26.3%) | 60 (75.0%) | 43 |
| Stage B, all 120 | 21 (17.5%) | 31 (25.8%) | 29 (24.2%) | 70 (58.3%) | 49 |
| Stage B, representative 80 | 15 (18.8%) | 21 (26.3%) | 20 (25.0%) | 49 (61.3%) | 34 |

Three-source agreement is low in both stages. The two models resemble each other
much more than either resembles the human labels, especially in Stage A. This is
not evidence that the models are correct: shared prompts, label definitions and
similar model behavior can produce correlated errors. The lower M1/M2 agreement
after context is revealed also shows that context does not force one stable label
mapping under the current protocol.

## Representative Stage B distribution

Only the representative lane is used for a rough prevalence description. Even
there, the counts describe this constrained IAC2 sample, not forums in general.

| Decision | Human | Model 1 | Model 2 |
| --- | ---: | ---: | ---: |
| `anger` | 9 | 15 | 18 |
| `confusion` | 5 | 0 | 0 |
| `cynicism` | 4 | 11 | 10 |
| `disappointment` | 2 | 1 | 1 |
| `disgust` | 6 | 0 | 2 |
| `fear` | 1 | 2 | 2 |
| `frustration` | 10 | 17 | 4 |
| `joy` | 2 | 1 | 2 |
| `neutral` | 15 | 31 | 39 |
| `other_emotion` | 21 | 0 | 0 |
| `sadness` | 2 | 1 | 1 |
| `surprise` | 0 | 0 | 1 |
| `unclear` | 2 | 1 | 0 |
| `unusable` | 1 | 0 | 0 |

The largest structural difference is Human `other_emotion` versus model
`neutral`. A private aggregate-only inspection of Human Stage B proposals found:

| Subset | `approval` | `disapproval` | `regret` | Total `other_emotion` |
| --- | ---: | ---: | ---: | ---: |
| All 120 | 11 | 18 | 1 | 30 |
| Representative 80 | 5 | 15 | 1 | 21 |

Under the frozen protocol, ordinary agreement or disagreement may be `neutral`,
while `other_emotion` requires a clear emotion outside the candidate set.
`approval` and `disapproval` are primarily stance or attitude labels. Their use
therefore exposes a task-definition mismatch: the sample often makes stance more
salient than communicated emotion, and the human annotation sometimes answered
that stance question through the `other_emotion` escape hatch. This is an
ontology/protocol diagnosis, not evidence that `approval` and `disapproval` should
automatically become emotion classes.

Model behavior is not interchangeable either. On representative Stage B cases,
Model 1 used `frustration` 17 times while Model 2 used it 4 times. The models also
disagreed on 31 of 80 representative cases, including frequent movement among
`frustration`, `anger`, `neutral` and `cynicism`.

## What context changed

| Source | Changed, all 120 | Changed, representative 80 |
| --- | ---: | ---: |
| Human | 51 (42.5%) | 33 (41.3%) |
| Model 1 | 42 (35.0%) | 27 (33.8%) |
| Model 2 | 36 (30.0%) | 19 (23.8%) |

The measured Human change rate is higher than the annotator's initial qualitative
recollection that context changed decisions only sometimes. These are not
independent before/after judgments because Stage B followed Stage A. Moreover, 24
of the 30 Human Stage B `other_emotion` cases had a different Stage A decision, so
part of the measured context effect is context revealing stance alignment rather
than resolving emotion alone.

On the 80 representative cases:

- Human marked context sufficient in 71 cases; each model marked all 80 sufficient.
- Human marked mixed emotion in 15 cases, Model 1 in 4 and Model 2 in 13.
- Human marked sarcasm present in 7 cases, Model 1 in 18 and Model 2 in 26.

The models' higher sarcasm counts do not establish false positives without
adjudication, but they show that sarcasm is another unstable boundary under the
current instructions.

## Dataset diagnosis

### Directly computed observations

- Only 15 of 80 representative Stage B cases received the same exact decision
  from all three sources.
- Human used `other_emotion` in 21 representative cases, predominantly for
  `approval` or `disapproval`; neither model did so in the representative lane.
- Human marked 5 of all 120 Stage B cases unusable, including 1 representative
  case. Replacements were not executed after the pilot was reclassified as
  exploratory.
- Human/model exact agreement stayed near 25% in both stages.

### Annotator observations requiring broader verification

- The visible discussions were dominated by abortion and gun-policy debates,
  with fewer drug and general political discussions.
- Long quoted or multi-segment replies sometimes contained different local
  affects that were difficult to reduce to one post-level label.
- Many posts primarily communicated support or opposition rather than a clear
  emotion.

These observations are useful failure evidence, but the pilot did not include a
formal topic-coverage audit and cannot establish population prevalence.

### Assistant synthesis

The IAC2 `4forums` pilot should not move directly into final training annotation.
It remains useful as an adversarial diagnostic set for political argument,
stance-emotion separation, quotation and context handling. The main task should
first decide whether it predicts strictly communicated emotion or jointly predicts
emotion and stance. Given the thesis title, the cleaner design is to keep emotion
as the primary target and record stance as a separate auxiliary field when it is
needed, rather than treating support and opposition as emotions.

## Next decision

Do not adjudicate all 106 disagreement cases yet. A bounded, source-blinded
diagnostic adjudication should first cover the main failure strata: Human
`approval/disapproval`, all-three-different cases, model `anger/frustration`
disagreements, and a small all-three-equal control set. Its purpose is to decide
whether to revise the ontology/view and whether IAC2 remains only a challenge set.
It must not be presented as construction of the final dataset.

Machine-readable aggregate evidence is stored in
[`three-source-comparison-v1.json`](three-source-comparison-v1.json).
