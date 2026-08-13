# Forum Dataset Construction

This directory owns the deterministic preprocessing that turns the private IAC
2.0 4forums dump into auditable parent-target candidates. It does not assign
emotion labels, choose train/dev/test splits, or send text to external services.

## Boundary

- Trackable files contain code, protocols, tests, and aggregate-only reports.
- Per-sample text, source IDs, HMAC mappings, and duplicate keys remain under
  `data/iac2/derived-private/` and are excluded from Git.
- The pipeline does not read the IAC `author` table or retain discussion URLs.
- Cleaning is deliberately conservative: stylistic and emotional cues are kept,
  while uncertain cases receive flags instead of being silently deleted.

## Current Version

- [`deduplication/README.md`](deduplication/README.md) records the verified
  `DATA-FCTX-DEDUP-V2` exact, lexical-near and semantic-near stage.
- [`protocols/data-cleaning-quality-filter-v2.md`](protocols/data-cleaning-quality-filter-v2.md)
  freezes the rules and privacy boundary.
- [`prepare_iac2_candidates.py`](prepare_iac2_candidates.py) builds the private
  SQLite artifact and aggregate report.
- [`verify_cleaning_output.py`](verify_cleaning_output.py) independently checks
  hashes, database integrity, counts, privacy invariants, and report agreement.
- [`tests/test_prepare_iac2_candidates.py`](tests/test_prepare_iac2_candidates.py)
  exercises normalization, quote handling, filtering, HMAC IDs, and a synthetic
  end-to-end dump.

## Verified Full Run

`DATA-FCTX-CLEAN-V2` completed on the private 4forums dump and passed 40
independent checks with zero mismatches:

- 414,453 posts produced 403,374 declared parent-target candidates.
- 403,336 candidates are eligible; 38 received explicit hard exclusions.
- All 539,658 quote rows are accounted for: 537,778 top-level and 1,880 nested
  offsets are valid, with no missing parent, out-of-bounds offset, or cycle.
- Exact duplicates are registered but retained for later thread-aware sampling.
- The private SQLite artifact is 2,471,235,584 bytes and remains gitignored.

The aggregate evidence is in
[`reports/cleaning-preflight-v2.json`](reports/cleaning-preflight-v2.json), the
independent audit is in
[`reports/cleaning-verification-v2.json`](reports/cleaning-verification-v2.json),
and artifact hashes are recorded in
[`../../../data/iac2/manifests/cleaning-v2.json`](../../../data/iac2/manifests/cleaning-v2.json).

V1 is retained as a failed pre-verification attempt. It incorrectly interpreted
`quote.text_offset` as the beginning of quote content embedded inside a post.
The IAC schema instead stores post-owned text and quote text separately; the
offset is an insertion point in the owning post or parent quote. The aggregate
failure record is in
[`reports/cleaning-v1-correction.json`](reports/cleaning-v1-correction.json).

The downstream `DATA-FCTX-DEDUP-V2` run also passed independent verification:
403,183 of the 403,336 eligible pairs remain after 153 exact or format-only
automatic drops. Its 68,552 review-only near-duplicate edges form 249 clusters
with 1,308 members; semantic similarity caused no automatic deletion. The
frozen HNSW audit reached mean recall@64 of 0.992554, with no query saturated at
the maximum `k = 512`. See
[`deduplication/reports/dedup-verification-v2.json`](deduplication/reports/dedup-verification-v2.json).

Deduplication V1 remains failed evidence because mean recall@64 was below its
frozen gate and its padded token-length metadata was wrong. V2 reused only
hash-verified embeddings and the HNSW graph, then regenerated token counts,
searches, edges and decisions.

The next stage may now define the label ontology and register a small sampling
and annotation pilot. Review-cluster adjudication or grouping, sample selection,
annotation, and thread-disjoint splitting remain intentionally separate
decisions and have not been performed by this pipeline.
