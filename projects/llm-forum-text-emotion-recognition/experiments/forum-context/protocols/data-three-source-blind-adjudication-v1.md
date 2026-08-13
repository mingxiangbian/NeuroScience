# DATA-FCTX-ADJ-DIAG-V1: Source-blind Diagnostic Adjudication

## Registration

- Date: 2026-08-07
- Parent protocol: `DATA-FCTX-LABEL-V1`
- Parent amendment:
  `data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison`
- Decision owner and adjudicator: project author
- Registration timing: before selecting cases or inspecting selected case text
- Frozen sample size: 40 unique cases
- Selection seed: `f3b9b141f728d436b42e8fd8464c3c46`
- Human source: sealed Human Pass 1 checkpoint
- Human checkpoint SHA-256:
  `5e03ebbef49ae558db6b6ce426aaf95d3e819949431f4132762868da631ff03a`
- Three-source disagreement sidecar SHA-256:
  `b85136c226e5e82db43cfaaef2734f0b13e9e7271fde6cdf1c56abe83289720f`

Pre-execution design correction: before case selection or semantic inspection,
the candidate assignment rule was changed from independent per-case hashing to
the balanced permutation schedule below. This prevents accidental source-position
imbalance from confounding candidate support rates.

Preflight correction: the first implementation ranked the six permutations
directly. Its pre-write balance assertion failed because the final four cases of
a 40-case cycle were not guaranteed to be balanced. The run aborted before any
bundle, source map, manifest or report was written, and no selected text was
displayed or semantically inspected. The frozen schedule-selection rule below was
then made explicit before retrying generation.

## Purpose

This pass diagnoses why Human Pass 1, Model 1 and Model 2 disagree and whether
the disagreement is caused by source error, stance-emotion confusion, ontology
coverage, context, or an invalid annotation unit. It is not a second independent
human annotation pass and does not create formal gold labels.

The same project author who produced Human Pass 1 performs this adjudication.
Candidate source identities are hidden during review, but the author may remember
some original cases. Results are therefore source-blind diagnostic judgments,
not independent inter-annotator agreement evidence.

## Frozen inputs and validation

Before building the review bundle, the builder must:

1. Recompute all four sealed model-output hashes and match the existing seal
   report.
2. Require 120 valid and complete Human Pass 1 records.
3. Require exact `annotation_order`, `sample_uid` and `view_sha256` alignment
   across all three sources.
4. Recompute each private annotation view hash.
5. Abort on any invalid decision, duplicate case, missing case or hash mismatch.

The three original decision sets and Human Pass 1 records are immutable. This
pass writes only to a separate private adjudication directory.

## Frozen sampling plan

Selection uses the Stage B exact decision key. A labeled `other_emotion` decision
includes its normalized proposal, for example `other_emotion:disapproval`.

Cases are selected in the following priority order. Each later stratum excludes
all cases already selected. If any stratum cannot fill its quota, the builder
must fail rather than substitute from another pool.

| Priority | Stratum | Quota | Eligibility |
| --- | --- | ---: | --- |
| 1 | `stance_candidate` | 15 | Human Stage B is `other_emotion:approval` or `other_emotion:disapproval`, and the three Stage B exact keys are not all equal |
| 2 | `all_three_different` | 10 | Human, Model 1 and Model 2 have three different Stage B exact keys |
| 3 | `model_boundary_conflict` | 8 | Model 1 and Model 2 differ, and both exact keys are in `anger`, `frustration`, `neutral`, `unclear`, `cynicism` |
| 4 | `human_context_shift` | 5 | Human Stage A and Stage B exact keys differ |
| 5 | `all_three_equal_control` | 2 | All three Stage B exact keys are equal |

Within each stratum, eligible cases are ranked in ascending order by:

```text
SHA256(seed + "|select|" + stratum + "|" + sample_uid)
```

The 40 selected cases are presented in ascending order by:

```text
SHA256(seed + "|present|" + sample_uid)
```

The browser receives only sequential blind case IDs `001` through `040`. It does
not receive original annotation order, sample UID, sampling lane or stratum.

## Candidate anonymization

Generate all six permutations of source names `human`, `model_01` and `model_02`.
Then enumerate all 720 orders of those six permutations. Retain only orders whose
first four permutations place every source in every candidate position either
once or twice. Rank the valid orders in ascending order by:

```text
SHA256(seed + "|schedule|" + semicolon_joined_comma_source_permutations)
```

Choose the lowest-ranked valid order and cycle it over the 40 cases in frozen
presentation order. For blind position `p`, use schedule entry `(p - 1) mod 6`;
its three entries are assigned `candidate_a`, `candidate_b` and `candidate_c`.
This gives every source 13 or 14 appearances in each candidate position. The
mapping is stored in a server-private file and is never returned to the browser.
Candidate displays include only:

- `status`;
- `primary_emotion`;
- `other_emotion_text` when applicable.

Original confidence, notes, sarcasm, mixed-emotion and context-sufficiency fields
are not displayed because writing style or field patterns could reveal source
identity.

Source identities must not be unblinded until all 40 cases are locked. The local
review server exposes no mapping endpoint and serves static files from an explicit
allowlist.

## Two-phase review contract

### Phase 1: independent diagnosis

The adjudicator sees the complete Stage B view but no candidate decisions. The
following fields are required and then permanently locked:

- `emotion_presence`: `clear_emotion`, `no_clear_emotion`, or `uncertain`;
- `stance`: `support`, `oppose`, `mixed`, `none`, or `uncertain`;
- `unit_validity`: `valid_single_unit`, `multi_segment_or_mixed_unit`,
  `insufficient_context`, or `unusable`;
- `independent_decision`: one V1 emotion decision with status `labeled`,
  `unclear`, or `unusable`;
- `confidence`: `low`, `medium`, or `high`;
- `note`: optional, except an unusable decision requires a note.

### Phase 2: source-blind candidate assessment

Only after Phase 1 is saved does the server reveal Candidates A, B and C. The
following fields are required and then permanently locked:

- one assessment for every candidate: `supported`,
  `acceptable_but_not_primary`, `unsupported`, or `undecidable`;
- `resolution`: `final_decision` or `no_stable_gold`;
- `final_decision`: one V1 emotion decision when resolution is
  `final_decision`;
- one primary reason code:
  - `stance_vs_emotion`;
  - `neutral_vs_unclear`;
  - `anger_vs_frustration`;
  - `context_changes_interpretation`;
  - `multi_segment_or_mixed`;
  - `ontology_gap`;
  - `insufficient_context`;
  - `clear_protocol_violation`;
  - `other_documented_reason`;
- `note`: required for `no_stable_gold` and `other_documented_reason`, optional
  otherwise.

Phase 2 may retain the independent Phase 1 decision, choose a candidate-supported
decision, or conclude that no stable gold label is justified. Candidate agreement
does not determine the final decision automatically.

## Session and persistence rules

- Maximum continuous review: 20 completed cases; the reviewer then starts a new
  local session.
- The server binds only to `127.0.0.1`.
- Every state-changing request requires a per-process CSRF token and same-origin
  request.
- Phase locks and completed records use atomic replacement, file mode `0600` and
  a private directory mode `0700`.
- Existing locked phases cannot be edited through the interface.
- Stopping or refreshing the server must preserve the next incomplete phase.

## Planned analysis after unblinding

After all 40 cases are complete, a separate script may join the private source
map with locked judgments to report aggregate, privacy-screened diagnostics:

- candidate support rate by source;
- unsupported rate by source and reason code;
- independent-to-final decision changes;
- `no_stable_gold` rate;
- stance, emotion-presence and unit-validity distributions by frozen stratum;
- whether the two all-equal controls remain supported.

No per-case forum text, private identifier, source mapping or label may enter a
tracked report. The analysis cannot be called IAA, a reliability estimate, a
formal ontology validation or a gold-dataset result.

## Status

Completed on 2026-08-07. All 40 unique cases have locked Phase 1 and Phase 2
records. Review used two sessions of 20 cases, satisfying the continuous-session
gate. The write server was stopped before finalization; the private bundle,
source map, manifest, session log and records were archived and sealed read-only.

Aggregate source unblinding was executed by
`finalize_blind_adjudication_v1.py`. The tracked outputs are
`reports/blind-adjudication-results-v1.json` and
`reports/blind-adjudication-results-v1.md`. The private checkpoint SHA-256 is
`7fe047f5ef2b234ec765a9c4c27facbb74f6b340644c2aa2aa557406a65d19af`.
The reports retain the registered diagnostic-only claim boundary.
