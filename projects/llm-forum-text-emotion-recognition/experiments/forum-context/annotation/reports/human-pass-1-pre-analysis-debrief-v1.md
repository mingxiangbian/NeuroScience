# Human Pass 1 Pre-analysis Debrief V1

## Evidence status

- Date: 2026-08-07
- Protocol: `DATA-FCTX-LABEL-V1` / `DATA-FCTX-SAMPLE-V1`
- Scope: 120 primary pilot cases, Stage A and Stage B complete
- Source: immediate self-report from the single human annotator
- Timing: recorded before aggregate label inspection, model-output disclosure and
  the 24-case blind-repeat pass
- Claim type: preliminary qualitative observation, not a measured dataset result

This report contains no forum text, per-case label, prediction or aggregate label
distribution. It preserves what the annotator noticed before quantitative analysis.

## Annotator observations

1. Many posts did not express an obvious emotion or were difficult to judge. Much
   of the visible interaction appeared to be support or opposition rather than
   emotion.
2. The boundary between `neutral` and `unclear` was difficult to apply consistently.
3. Context did not change the target-only judgment frequently, but it did change
   some decisions.
4. `anger` and `frustration` were the most difficult adjacent labels to separate.
5. Sarcasm was not a major annotation difficulty. Long quotation structures and
   multi-segment replies increased difficulty.
6. The discussion title and direct parent were usually sufficient as context.
7. Topics appeared concentrated around abortion and gun policy, with fewer cases
   concerning drugs and politics. The annotator judged the topic coverage to be
   narrow for a general forum claim.
8. Most cases appeared to have one dominant emotion, while a small number of labels
   seemed much more frequent than others.

Observation 8 cannot establish that the underlying task is naturally single-label:
V1 records only one primary emotion and a `mixed_emotion` diagnostic flag, not
secondary labels. Apparent class concentration may reflect the corpus, topic mix,
ontology boundaries, sampling lanes or annotator behavior.

## Competing explanations

### Emotion versus stance

Support and opposition are stance variables, not emotion labels. A high apparent
rate of stance-only posts could indicate a mismatch between an argumentative forum
corpus and the intended emotion-recognition task. It could also be a valid natural
property of the domain, in which case `neutral` is substantively important rather
than annotation residue.

### Topic concentration

Topic concentration may limit external validity and create topic-label shortcuts.
If IAC2 remains the only downstream corpus, claims should be scoped to argumentative
forum discussion. A general forum claim would require broader topic evidence or an
additional source.

### Label concentration

An imbalanced label distribution could be caused by the source domain, constrained
diagnostic sampling, insufficient ontology coverage or annotation drift. These
explanations cannot be separated from the annotator's impression alone.

### Context and segment complexity

Occasional Stage A to Stage B changes are compatible with a useful but non-universal
context effect. Long multi-quote posts may compress several local emotional acts
into one post-level target, increasing uncertainty even when the title and direct
parent are generally sufficient.

## Analysis after the blind-repeat pass

1. Compute label prevalence on the 80-case representative lane separately. Do not
   use the 40 diagnostic cases to estimate natural prevalence.
2. Report Stage A and Stage B status, label, confidence and transition counts,
   including `neutral`, `unclear` and context-resolved cases.
3. Measure blind-repeat raw agreement and per-label confusion, with a dedicated
   `anger` versus `frustration` analysis.
4. Test whether quote count and target length are associated with low confidence,
   `unclear`, mixed emotion or Stage A to Stage B changes.
5. Audit topic coverage independently, then test topic-label association without
   treating topic words as emotion evidence.
6. Separate possible corpus imbalance from sampling-lane effects and annotator
   inconsistency before changing the ontology or sampling policy.

## Blinding and change control

- Do not inspect aggregate human labels or unseal model outputs before completing
  the 24 blind repeats.
- Do not revise the 120 completed primary records in response to this debrief.
- Any segment-level labels, stance attributes, ontology changes or broader-source
  sampling require a new protocol version; they must not be retrofitted into V1.

## Frozen checkpoint

The private checkpoint contains 120 complete primary records and no partial case:

- Archive: `data/iac2/annotations/pilot-v1/checkpoints/human-pass-1-complete_20260807T194808+0800.tar.gz`
- SHA-256: `5e03ebbef49ae558db6b6ce426aaf95d3e819949431f4132762868da631ff03a`
