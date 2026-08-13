# Forum Annotation Contract

This directory contains only trackable annotation specifications and synthetic
fixtures. It must never contain real IAC forum text or per-sample labels.

## Frozen V1 contract

- Protocol: [`DATA-FCTX-LABEL-V1`](../protocols/data-label-calibration-view-v1.md)
- Sampling protocol: [`DATA-FCTX-SAMPLE-V1`](../protocols/data-annotation-sampling-pilot-v1.md)
- Private view schema: [`schemas/annotation-view-v1.schema.json`](schemas/annotation-view-v1.schema.json)
- Sidecar record schema: [`schemas/annotation-record-v1.schema.json`](schemas/annotation-record-v1.schema.json)
- Synthetic view: [`fixtures/annotation-view-v1.synthetic.json`](fixtures/annotation-view-v1.synthetic.json)
- Synthetic annotation: [`fixtures/annotation-record-v1.synthetic.json`](fixtures/annotation-record-v1.synthetic.json)

Real exports belong under the gitignored directory:

```text
data/iac2/annotations/
```

V1 freezes the calibration labels, staged display order and record format.
`DATA-FCTX-SAMPLE-V1` additionally freezes 120 unique calibration cases, 24
blind repeats, the deterministic sample lanes and their acceptance gates. The
final training ontology, formal annotation scale and train/dev/test split remain
unfrozen.

## Verified sampling preflight

`sample_iac2_pilot_v1.py` applies the frozen hash ranking and global uniqueness
constraints without exporting forum text. The 2026-08-06 full-data run produced:

- 403,183 eligible candidates;
- 120 primary cases and 60 reserves;
- 180 unique samples from 180 unique threads;
- diagnostic capacities of 662 sarcasm, 1,153 hostility-affect, 1,757 short-context
  and 37,233 distinct-quote candidates;
- no materialized repeat manifest, because the 24 blind repeats are defined only
  after unusable replacements.

The private manifests are mode `0600` and remain under the gitignored
`data/iac2/annotations/pilot-v1/` directory. The aggregate public results are in
[`reports/sampling-preflight-v1.json`](reports/sampling-preflight-v1.json).
[`verify_sampling_pilot_v1.py`](verify_sampling_pilot_v1.py) independently
replayed the selection and passed 45 checks with zero mismatches; see
[`reports/sampling-verification-v1.json`](reports/sampling-verification-v1.json).

## Verified private view export

`export_annotation_views_v1.py` reconstructed the 120 selected cases from the
frozen cleaning database without reading an external service or exposing the
sampling lanes. The private files are named `0001.json` through `0120.json` in
annotation order and stored under `data/iac2/annotations/pilot-v1/views/`.

The export contains 89 cases with target quotes and 164 top-level quote blocks:
123 from the direct parent, 29 from another post in the same thread and 12 with
an external or unresolved source. These counts describe view structure only;
they are not emotion labels or quality judgments.

[`verify_annotation_views_v1.py`](verify_annotation_views_v1.py) independently
rebuilt every view from SQLite and passed 34 checks with zero mismatches, zero
schema problems and zero hidden-metadata violations. See
[`reports/view-export-v1.json`](reports/view-export-v1.json) and
[`reports/view-export-verification-v1.json`](reports/view-export-verification-v1.json).

## Sealed model outputs and recorded deviation

Two independently produced Stage A files and two Stage B files were
mechanically validated, then sealed in the private
`data/iac2/annotations/pilot-v1/model-outputs/` directory. Output files use mode
`0400` and the directory uses `0500`. The public
[`model-output-seal-v1.json`](reports/model-output-seal-v1.json) contains only
filenames, hashes, sizes, row counts and validation states; it contains no forum
text, labels or prediction distributions.

These outputs were generated before human-blind pass 1 and the planned
blind-repeat pass, which deviates from the execution order frozen in
`DATA-FCTX-SAMPLE-V1`. They remained quarantined from the human annotator until
all 120 Human Pass 1 records were complete. The project author then registered a
[`direct-comparison amendment`](../protocols/data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison.md),
waived the repeat pass and authorized semantic disclosure. The seal report now
records that disclosure and the resulting comparison artifacts. Human Pass 1
remains blind to model labels, but delayed intra-annotator stability and strict
compliance with the original execution order cannot be claimed.

## Local human annotator

[`human_annotator/`](human_annotator/) implements the two-stage blind interface
without third-party dependencies. It binds only to `127.0.0.1`, returns only
`target.body` during Stage A, atomically locks Stage A before serializing Stage B
context, and writes private records with mode `0600`. The server has no model
output or sampling-lane data route. Automated tests cover the response boundary,
lock conflicts, contextual completion, permissions, local-origin checks and the
40-case continuous-session gate.

All 120 primary cases have complete Stage A and Stage B human records, with no
partial case. The private read-only checkpoint
`human-pass-1-complete_20260807T194808+0800.tar.gz` has SHA-256
`5e03ebbef49ae558db6b6ce426aaf95d3e819949431f4132762868da631ff03a`.
The annotator's observations before aggregate-label inspection are preserved in
[`human-pass-1-pre-analysis-debrief-v1.md`](reports/human-pass-1-pre-analysis-debrief-v1.md).

[`compare_three_sources_v1.py`](compare_three_sources_v1.py) revalidated all four
sealed hashes and row mappings, compared Human Pass 1 with both model sources,
and produced a privacy-checked aggregate
[`JSON report`](reports/three-source-comparison-v1.json) plus a reviewed
[`Markdown diagnosis`](reports/three-source-comparison-v1.md). A gitignored
private sidecar contains the 106 cases with at least one Stage A or Stage B
disagreement. No source was treated as gold.

## Source-blind diagnostic adjudication

The frozen
[`DATA-FCTX-ADJ-DIAG-V1`](../protocols/data-three-source-blind-adjudication-v1.md)
selects 40 diagnostic cases across five predeclared strata. Candidate identities
use a balanced private A/B/C mapping, so every source appears 13 or 14 times in
each position. [`build_blind_adjudication_v1.py`](build_blind_adjudication_v1.py)
verified the Human checkpoint, model seals, 120 row mappings and every selected
view hash before creating the gitignored bundle. The privacy-screened preparation
result is in
[`blind-adjudication-bundle-v1.json`](reports/blind-adjudication-bundle-v1.json).

[`blind_adjudicator/`](blind_adjudicator/) provides a two-phase local interface.
Phase 1 records an independent diagnosis before the server reveals anonymous
Candidate A/B/C decisions; Phase 2 records candidate support, a final diagnostic
decision or `no_stable_gold`, and one reason code. The server does not read the
private source map. This is model-assisted diagnostic adjudication, not a second
independent human pass, IAA, ontology acceptance or formal gold construction.

The review completed all 40 cases in two sessions of 20. The write server was
stopped, the private records were sealed read-only, and
[`finalize_blind_adjudication_v1.py`](finalize_blind_adjudication_v1.py) joined
the hidden source map only for aggregate analysis. The privacy-screened
[`JSON result`](reports/blind-adjudication-results-v1.json) and
[`Markdown result`](reports/blind-adjudication-results-v1.md) contain no forum
text, private identifiers, per-case labels or per-case source mappings. Because
the sample is deliberately disagreement-enriched and has only two all-equal
controls, its source support rates are diagnostic rather than model accuracy or
population-performance estimates.
