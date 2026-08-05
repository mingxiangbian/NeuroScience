# Forum Context Experiment Track

Current gate: `IAC2_RESEARCH_USE_CONDITIONAL_GO`

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
- IAC 2.0 was audited as an alternative official release. Its 4forums dump has
  403,374 resolved direct-parent links and 389,648 pairs passing the minimal
  text gate, so its context topology is viable.
- IAC 2.0 is not a ready-made emotion dataset: its labels concern argument
  relations, hostility, emotional-vs-factual appeal and sarcasm rather than
  categorical emotions. UCSC's current corpus index explicitly makes IAC V2
  available for free research use, so local noncommercial thesis annotation,
  training and evaluation are conditionally approved. The dump metadata still
  leaves the dataset license blank, and no corpus-specific terms authorize raw
  text, derived labels, commercial use or checkpoint redistribution.

## Files

- [`protocols/data-source-parent-recovery-pilot-v1.md`](protocols/data-source-parent-recovery-pilot-v1.md):
  source evidence, authorization gates and external-recovery prohibitions.
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

## Next Gate

The official GoEmotions release alone is insufficient for the planned contextual
Dataset A. IAC 2.0 shows that 4forums can supply reliable thread context, but it
does not solve categorical emotion labeling. Its official research-use statement
is sufficient for a controlled, noncommercial thesis pilot, while public data and
checkpoint release remain closed. The next gate is therefore the label protocol:
freeze the emotion ontology, context unit, privacy fields and annotation design,
then register a small thread-disjoint 4forums pilot before any full-scale model
training.
