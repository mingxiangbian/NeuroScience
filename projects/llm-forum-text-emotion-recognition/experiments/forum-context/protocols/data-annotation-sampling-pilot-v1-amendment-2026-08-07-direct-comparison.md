# DATA-FCTX-SAMPLE-V1 Amendment: Direct Three-source Comparison

## Registration

- Date: 2026-08-07
- Parent protocol: `DATA-FCTX-SAMPLE-V1`
- Decision owner: project author
- Registered before semantic inspection of the sealed model outputs
- Human checkpoint:
  `human-pass-1-complete_20260807T194808+0800.tar.gz`
- Human checkpoint SHA-256:
  `5e03ebbef49ae558db6b6ce426aaf95d3e819949431f4132762868da631ff03a`

## Reason for the change

The 120-case human pass exposed substantial concerns about task-data fit, topic
coverage, stance-dominant posts, class concentration and post-level annotation of
long multi-segment replies. The project author therefore treats this IAC2 sample
as an exploratory calibration and dataset-diagnostic resource rather than the
presumptive final training dataset.

The immediate decision need is to determine where the completed human annotation,
Model 1 and Model 2 agree, why they disagree and which protocol or dataset defects
the disagreements reveal. This is prioritized over measuring delayed
intra-annotator consistency on a dataset that may not advance to formal annotation.

## Authorized deviation

The project will not execute the frozen 24-case blind-repeat pass or its 72-hour
delay before model comparison. The two sealed model-output sets may be disclosed
after this amendment is saved and their hashes and row mappings are revalidated.

The 120 completed human records remain immutable. Model comparison and any later
adjudication must be stored as separate sidecars and must not overwrite Human Pass
1, Model 1 or Model 2 decisions.

## Consequences and prohibited claims

1. This pilot cannot report the planned blind-repeat raw agreement, Cohen's kappa
   or `20--24/24` repeat-consistency gate.
2. It cannot claim that the single human annotator was independently reliable
   across time.
3. Model 1 and Model 2 are not independent human annotators. Three-source agreement
   must not be described as inter-annotator agreement.
4. Two-model majority agreement does not automatically define gold. Correlated
   model errors and shared prompt or ontology effects remain possible.
5. Any final decision produced after disclosure is a model-assisted adjudication,
   not a blind human label. Original decisions and disagreement reasons must remain
   recoverable.
6. This amended pilot cannot by itself accept the V1 ontology for formal dataset
   construction. It may reject or revise a route and generate requirements for a
   later protocol.

Human Pass 1 remains legitimately blind to model labels because the model files
were quarantined until all 120 human cases were complete. The earlier deviation in
which model outputs were generated before the human passes remains disclosed in
the model-output seal report.

## Frozen comparison plan

### Mechanical validation

- Recompute all four model-output hashes against the seal report.
- Require 120 unique rows in every file.
- Require exact agreement on `annotation_order`, `sample_uid` and `view_sha256`
  across Human, Model 1 and Model 2.
- Reject any row with an invalid decision schema before computing statistics.

### Aggregate comparison

Report Stage A and Stage B separately:

- three-source exact status-plus-label agreement;
- Human versus Model 1, Human versus Model 2 and Model 1 versus Model 2 agreement;
- all-three-different, two-model-agree-against-human and human-plus-one-model
  patterns;
- confusion counts for `neutral` versus `unclear` and `anger` versus
  `frustration`;
- Stage A to Stage B transitions for each source;
- Stage B diagnostic agreement for sarcasm, mixed emotion and context sufficiency.

Representative and diagnostic sampling lanes must be reported separately. Only
the 80 representative cases may be used to describe apparent natural prevalence.
No real forum text, source identifier, sample UID, per-row label or prediction may
enter a tracked report.

### Reason-coded adjudication

Only disagreement cases proceed to a later adjudication pass. Candidate labels
should be source-blinded where practical. The adjudicator may select a supported
final decision or `no_stable_gold` and must record one primary reason:

- `stance_vs_emotion`;
- `neutral_vs_unclear`;
- `anger_vs_frustration`;
- `context_changes_interpretation`;
- `multi_segment_or_mixed`;
- `ontology_gap`;
- `insufficient_context`;
- `clear_protocol_violation`;
- `other_documented_reason`.

Adjudication results must remain separate from the three original sources.

## Execution status

The frozen comparison plan was executed on 2026-08-07 after all four sealed
model-output hashes and all 120 row mappings were revalidated. Aggregate results
are stored in
[`../annotation/reports/three-source-comparison-v1.json`](../annotation/reports/three-source-comparison-v1.json)
and interpreted in
[`../annotation/reports/three-source-comparison-v1.md`](../annotation/reports/three-source-comparison-v1.md).
The gitignored private disagreement sidecar contains 106 cases. No adjudication
has been performed and none of the three original sources has been modified.
