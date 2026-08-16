# EXP-055 M1/M3 Frozen Validation Error Analysis

- Status: `Completed; pending independent verification`
- Split: validation only (`720` rows; `702` duplicate components)
- New training or inference: `false`
- Test access: `false`
- Primary operating point: each seed's frozen shared threshold
- Companion: fixed threshold `0.50`

## Primary Family Results

| Family | Six-label Macro-F1 | Five-label Macro-F1 without surprise |
| --- | ---: | ---: |
| M1 RoBERTa | 0.617254 +/- 0.011084 | 0.740705 +/- 0.013301 |
| M3 Classification LoRA | 0.654032 +/- 0.014135 | 0.706724 +/- 0.013816 |

M3's mean six-label Macro-F1 is higher than M1's, but that ordering does not extend to the five-label sensitivity result. Macro-F1 is non-additive, so this report does not assign an
additive share of the overall gap to any one label.

## Exact-Set Transitions

Across matched seeds, M1-only exact-correct rows average `56.00 +/- 15.72`;
M3-only exact-correct rows average `48.67 +/- 5.13`; rows where
both are exact-wrong average `123.67 +/- 10.50`.

- M1: 3/3 exact correct 497, seed-unstable 95, 0/3 exact correct 128.
- M3: 3/3 exact correct 468, seed-unstable 139, 0/3 exact correct 113.

## Surprise and Cardinality

- M1 surprise F1: seed 42=0.000000 / seed 43=0.000000 / seed 44=0.000000.
- M3 surprise F1: seed 42=0.363636 / seed 43=0.444444 / seed 44=0.363636.

- M1: mean empty predictions 261.33/720, false-empty positive rows 28.33, neutral rows with at least one false positive 61.00.
- M3: mean empty predictions 281.00/720, false-empty positive rows 43.67, neutral rows with at least one false positive 56.67.

## Whole-Vector Oracle

The oracle selects one complete six-label vector per row using gold Hamming error and
ties to M1. It is not deployable. Relative to M1, shared-threshold oracle six-label
Macro-F1 delta is `0.136394 +/- 0.009058` and five-label delta is
`0.074784 +/- 0.010869`. M3 is selected on
`8.333% +/- 0.773%` of rows.

Router-headroom gate: `Passed`.

| Check | Passed |
| --- | --- |
| five_label_mean_at_least_0.010 | `true` |
| five_label_positive_3_of_3 | `true` |
| m3_selection_rate_at_least_0.05_3_of_3 | `true` |
| six_label_mean_at_least_0.020 | `true` |
| six_label_positive_3_of_3 | `true` |

Passing only authorizes a separately registered train-OOF router feasibility test. It
does not show that pre-Qwen features can learn the oracle decision.

## Qualitative Review

- Frozen unique sample: `45` rows.
- Primary possible sources: overlapping_label_ontology=19, model_or_representation_limitation=13, annotation_or_data_uncertainty=9, surface_form_noise=2, missing_forum_context=1, low_support_label_uncertainty=1.
- Evidence flags: emotion_ontology_overlap=24, weak_emotion_neutral_boundary=21, implicit_emotion=20, lexical_cue_conflict=14, mixed_emotion=12, surface_noise=10, annotation_ambiguity=9, multilabel_underprediction=9, low_support_surprise=7, possible_missing_context=5, sarcasm_or_irony=5, negation=2.
- Gold plausibility: plausible=33, debatable=11, implausible=1.

These counts describe a purposefully selected sample reviewed once by the assistant.
They are hypotheses about failure cases, not dataset-wide prevalence, revised labels,
inter-rater evidence, causal explanations, or model reasoning.

## Boundary

EXP-055 used only frozen validation predictions and private validation text for the
pre-registered sample. It did not train, rerun inference, change thresholds, access
test, authorize EXP-054, or establish an internal emotion mechanism. Any router,
model change, TEST-READY decision, or generative comparison requires a new protocol.
