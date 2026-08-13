# Source-blind diagnostic adjudication results

- Protocol: `DATA-FCTX-ADJ-DIAG-V1`
- Status: `completed_and_aggregate_unblinded`
- Completed cases: 40/40
- Scope: same-author source-blind diagnostic adjudication, not formal gold or IAA.

## Candidate assessment after source unblinding

| Source | Supported | Acceptable | Unsupported | Undecidable | Strict support | Support or acceptable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| human | 12 | 8 | 20 | 0 | 30.0% | 50.0% |
| model_01 | 29 | 3 | 8 | 0 | 72.5% | 80.0% |
| model_02 | 24 | 3 | 13 | 0 | 60.0% | 67.5% |

## Decision stability

- Final decisions: 40
- Independent decision retained: 19
- Independent decision changed: 21 (52.5% of final decisions)
- No stable gold: 0 (0.0%)
- Final outcome statuses: {"labeled": 39, "unusable": 1}

## Unsupported-candidate reasons

- `human`: `anger_vs_frustration` 3, `insufficient_context` 1, `multi_segment_or_mixed` 1, `neutral_vs_unclear` 2, `stance_vs_emotion` 13
- `model_01`: `anger_vs_frustration` 1, `clear_protocol_violation` 1, `context_changes_interpretation` 1, `insufficient_context` 2, `neutral_vs_unclear` 2, `stance_vs_emotion` 1
- `model_02`: `anger_vs_frustration` 5, `clear_protocol_violation` 1, `context_changes_interpretation` 2, `insufficient_context` 2, `multi_segment_or_mixed` 1, `stance_vs_emotion` 2

## Frozen-stratum Phase 1 diagnosis

- `stance_candidate` (15): emotion_presence={"clear_emotion": 12, "uncertain": 3}; stance={"mixed": 1, "none": 1, "oppose": 8, "support": 3, "uncertain": 2}; unit_validity={"multi_segment_or_mixed_unit": 1, "unusable": 2, "valid_single_unit": 12}
- `all_three_different` (10): emotion_presence={"clear_emotion": 8, "no_clear_emotion": 1, "uncertain": 1}; stance={"oppose": 7, "uncertain": 3}; unit_validity={"unusable": 2, "valid_single_unit": 8}
- `model_boundary_conflict` (8): emotion_presence={"clear_emotion": 7, "uncertain": 1}; stance={"oppose": 7, "uncertain": 1}; unit_validity={"unusable": 1, "valid_single_unit": 7}
- `human_context_shift` (5): emotion_presence={"clear_emotion": 4, "uncertain": 1}; stance={"mixed": 1, "none": 1, "oppose": 2, "uncertain": 1}; unit_validity={"unusable": 1, "valid_single_unit": 4}
- `all_three_equal_control` (2): emotion_presence={"clear_emotion": 2}; stance={"none": 1, "oppose": 1}; unit_validity={"valid_single_unit": 2}

## Controls and execution

- All-equal controls: 2; all candidates supported or acceptable in 2; any candidate unsupported in 0.
- Final decision matched the unanimous control candidate in 2 cases; no stable gold in 0.
- Sessions: 2; completed per session: [20, 20]; maximum: 20/20.

## Claim boundary

These figures measure how the same project author judged anonymized candidate decisions after an independent first phase. They are not model accuracy, inter-annotator agreement, a reliability estimate, or a formal gold dataset.

The 40 cases are deliberately disagreement-enriched and include only two all-equal controls, so source-level rates cannot estimate performance on all 120 pilot cases or on the wider IAC2 corpus.
