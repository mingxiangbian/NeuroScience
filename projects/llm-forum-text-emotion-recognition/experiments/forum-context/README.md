# Forum Context Experiment Track

Current gate: `WEIBO_ECLASS_VERIFIED_MODEL_PREFLIGHT_NEXT`

This track owns the data-source, authorization and parent-context work that
follows the completed TweetEval and GoEmotions behavioral reproduction.

## Current Decision

- The three official GoEmotions raw CSVs were downloaded into the gitignored
  data directory and audited under `DATA-FCTX-CJ-V1`.
- All 48,836 train/dev targets matched raw metadata and had a `parent_id`.
- Only 157 targets (0.3215%) have parent-comment text available inside the raw
  release. The other 48,679 targets (99.6785%) lack parent text in that release:
  19,987 point to submissions and 28,692 point to comments absent from the raw
  corpus.
- The raw release is unpartitioned. The 157 available pairs are not automatically
  split-safe and are not authorized for training by this audit.
- Direct Reddit API access, scraping and third-party archive recovery are
  `NO-GO` for this project unless Reddit grants explicit research and AI/ML
  training approval.
- IAC 2.0 was audited as an alternative official release. The verified V2
  cleaning run produced 403,374 direct parent-target candidates; 403,336 pass
  its conservative hard filters, so its context topology is viable.
- The verified V2 deduplication run retains 403,183 pairs after 153 exact or
  format-only automatic drops. It identifies 249 unresolved near-duplicate
  review clusters with 1,308 members; semantic similarity alone caused no
  deletion.
- The `DATA-FCTX-SAMPLE-V1` metadata-only preflight selected 120 primary cases
  and 60 reserves from the 403,183-row candidate frame. All 180 selected rows
  and threads are unique; the independent verifier passed 45 checks with zero
  mismatches. No forum text, source IDs or per-sample labels entered the public
  reports.
- The 120 primary cases have been exported to private staged V1 views in frozen
  annotation order. Independent database reconstruction passed 34 checks with
  zero mismatches, zero schema problems and zero hidden-metadata violations.
  Human Pass 1 then completed Stage A and Stage B for all 120 cases. After a
  registered amendment waived the blind-repeat pass, Human, Model 1 and Model 2
  were compared without treating any source or model majority as gold.
- The comparison found only 21/120 exact three-source matches in Stage B and 106
  cases with at least one Stage A or Stage B disagreement. Human/model exact
  agreement stayed near 25%; the human frequently used `approval/disapproval`
  through `other_emotion`, exposing a stance-versus-emotion task mismatch.
- IAC 2.0 is not a ready-made emotion dataset: its labels concern argument
  relations, hostility, emotional-vs-factual appeal and sarcasm rather than
  categorical emotions. UCSC's current corpus index explicitly makes IAC V2
  available for free research use, so local noncommercial thesis annotation,
  training and evaluation are conditionally approved. The dump metadata still
  leaves the dataset license blank, and no corpus-specific terms authorize raw
  text, derived labels, commercial use or checkpoint redistribution.
- `DATA-FCTX-PUBLIC-AUDIT-V1` then audited pinned KOTE train/validation, the
  Hotter and Colder CLARIN package and the Weibo Emotion Cause Corpus without
  training, reading KOTE test data or running live hydration. An independent
  verifier passed 35/35 checks.
- KOTE is eligible only as a C0 target-only training/control candidate. Its
  released 7.91 mean label cardinality is the paper's intended five-rater vote
  transformation, not a parser defect; the downstream ontology and treatment
  of `NO EMOTION` remain unfrozen.
- The frozen audit classified Hotter and Colder as blocked because the package
  has labels and live links but no source text, its hydration script has access
  and privacy defects, and the released emotion rows do not form a complete
  eight-label matrix. The post-audit project decision now excludes it from this
  thesis: no hydration, training, model selection, evaluation or thesis claims.
- The broad candidate audit classified the Weibo repository only as a C1
  emotion-cause auxiliary source. A subsequent task-specific protocol isolated
  its independently defined EClass records without joining the two TSVs and
  adopted that subset as the primary single-label context task.
- `DATA-WEIBO-TASK-V1` retains 8,540 records with paired target-only and
  previous-context views. The group- and duplicate-disjoint split is 5,995
  train, 1,272 validation and 1,273 sealed test; 6,138 records have available
  local preceding context. The independent verifier passed 33/33 checks.
- This adoption verifies data construction only. `PrevCL` is an adjacent local
  clause, not a guaranteed parent or full forum thread, and model test access
  remains unauthorized.

## Files

- [`protocols/data-source-parent-recovery-pilot-v1.md`](protocols/data-source-parent-recovery-pilot-v1.md):
  source evidence, authorization gates and external-recovery prohibitions.
- [`protocols/data-weibo-eclass-task-v1.md`](protocols/data-weibo-eclass-task-v1.md):
  frozen EClass ontology, parsing, deduplication, split, paired-view and test
  sealing contract, with the verified execution result.
- [`weibo-eclass/README.md`](weibo-eclass/README.md): deterministic builder,
  independent verifier, tests and public aggregate report locations.
- [`protocols/data-closed-corpus-parent-coverage-v1.md`](protocols/data-closed-corpus-parent-coverage-v1.md):
  frozen definitions and reviewed execution result.
- [`preflight/local-filtered-id-inventory.json`](preflight/local-filtered-id-inventory.json):
  privacy-safe inventory derived from the existing GoEmotions manifest.
- [`preflight/closed-corpus-parent-coverage.json`](preflight/closed-corpus-parent-coverage.json):
  primary aggregate report with source and implementation hashes.
- [`preflight/closed-corpus-parent-coverage-verification.json`](preflight/closed-corpus-parent-coverage-verification.json):
  independent SQLite recomputation; status `passed` with zero mismatches.
- [`audit_iac2_source.py`](audit_iac2_source.py): aggregate-only parser and
  source audit for the official no-parse MySQL dumps.
- [`preflight/iac2-source-assessment.json`](preflight/iac2-source-assessment.json):
  artifact hashes, schema counts, parent/quote coverage and annotation linkage.
- [IAC 2.0 source assessment](../../../../sources/llm-forum-text-emotion-recognition-iac2-assessment.md):
  task fit, licensing boundary, privacy risks and adoption decision.
- [`dataset-construction/README.md`](dataset-construction/README.md): frozen V2
  cleaning and deduplication rules, aggregate results and independent audits.
- [`protocols/data-label-calibration-view-v1.md`](protocols/data-label-calibration-view-v1.md):
  frozen atomic calibration labels, staged context boundary and annotation rules.
- [`protocols/data-annotation-sampling-pilot-v1.md`](protocols/data-annotation-sampling-pilot-v1.md):
  frozen 120-case calibration sample, 24 blind repeats, diagnostic strata,
  deterministic seed, reserves and acceptance gates.
- [`annotation/README.md`](annotation/README.md): machine-readable private-view and
  sidecar annotation schemas with synthetic fixtures.
- [`annotation/sample_iac2_pilot_v1.py`](annotation/sample_iac2_pilot_v1.py):
  deterministic metadata-only sampler and private manifest writer.
- [`annotation/reports/sampling-preflight-v1.json`](annotation/reports/sampling-preflight-v1.json):
  aggregate candidate capacities, selected quotas and privacy claims.
- [`annotation/verify_sampling_pilot_v1.py`](annotation/verify_sampling_pilot_v1.py)
  and [`annotation/reports/sampling-verification-v1.json`](annotation/reports/sampling-verification-v1.json):
  independent deterministic replay and 45-check verification result.
- [`annotation/export_annotation_views_v1.py`](annotation/export_annotation_views_v1.py):
  local-only exporter for the 120 frozen staged views.
- [`annotation/reports/view-export-v1.json`](annotation/reports/view-export-v1.json):
  aggregate private-view counts, hashes and annotation-state boundary.
- [`annotation/verify_annotation_views_v1.py`](annotation/verify_annotation_views_v1.py)
  and [`annotation/reports/view-export-verification-v1.json`](annotation/reports/view-export-verification-v1.json):
  independent database reconstruction, schema, allowlist and privacy checks.
- [`protocols/data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison.md`](protocols/data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison.md):
  registered decision to treat the pilot as exploratory diagnosis and waive the
  delayed blind-repeat pass before model comparison.
- [`annotation/reports/three-source-comparison-v1.md`](annotation/reports/three-source-comparison-v1.md):
  privacy-safe Human/Model 1/Model 2 comparison, task diagnosis and claim limits.
- [`protocols/data-public-candidate-viability-audit-v1.md`](protocols/data-public-candidate-viability-audit-v1.md):
  frozen KOTE, Hotter and Colder, and Weibo acquisition and audit boundary.
- [`public-candidate-audit/reports/public-candidate-viability-audit-v1.md`](public-candidate-audit/reports/public-candidate-viability-audit-v1.md):
  aggregate schema, sample-quality, access and role decisions.
- [`public-candidate-audit/reports/public-candidate-viability-audit-v1-verification.json`](public-candidate-audit/reports/public-candidate-viability-audit-v1-verification.json):
  independent 35-check recomputation and Git-ignore verification.

## Next Gate

The Weibo EClass data-adoption gate, Stage 2 model-stack preflight and Stage 3
M0/M1/M2 train/dev baselines have passed. EXP-042 selected target only after the
two M2 views reached a practical tie on validation. The next gate is a separately
registered frozen-Qwen context x reasoning 2x2 Major experiment on development
data.

The next experiment may read validation under a preregistered comparison and
selection rule. It may not read sealed test labels or choose a model from test
behavior. KOTE remains an
optional control, IAC2 remains a closed data-diagnosis branch, and Hotter and
Colder remains excluded.
