# IAC 2.0 Candidate Deduplication

This directory owns duplicate detection after the verified
`DATA-FCTX-CLEAN-V2` cleaning stage and before annotation or split assignment.
It operates only on the private, eligible parent-target candidates.

## Boundary

- The deduplication unit is the complete `parent -> target` pair.
- Target-only repetition under a different parent is retained as a context
  variant unless the complete pair also satisfies a duplicate rule.
- Exact and format-only duplicates may be auto-collapsed.
- Lexical-near and semantic-near matches remain review candidates. They do not
  become deletions without a later, explicit adjudication protocol.
- No raw or cleaned forum text, per-sample IDs, embeddings, or index files may
  enter Git.

## Files

- [`protocols/data-deduplication-v2.md`](protocols/data-deduplication-v2.md):
  current frozen definitions, thresholds, retrieval settings and reuse boundary.
- [`deduplicate_iac2_candidates_v2.py`](deduplicate_iac2_candidates_v2.py): V2
  orchestration, HNSW retrieval, duplicate classification and private output.
- [`embed_iac2_posts_v2.py`](embed_iac2_posts_v2.py): corrected token counting
  and isolated local embedding worker.
- [`replay_iac2_embeddings_v2.py`](replay_iac2_embeddings_v2.py): deterministic
  PyTorch-only replay used by independent verification.
- [`verify_dedup_output_v2.py`](verify_dedup_output_v2.py): independent
  aggregate, decision, score, retrieval, hash and privacy checks.
- [`tests/test_deduplicate_iac2_candidates.py`](tests/test_deduplicate_iac2_candidates.py):
  synthetic tests for metrics, guards, ranking and direct-to-canonical selection.

## Verified Full Run

`DATA-FCTX-DEDUP-V2` processed all 403,336 eligible pairs and passed 69
independent checks with zero mismatches:

- 403,183 pairs remain after 139 `drop_exact` and 14 `drop_format_only`
  decisions; every automatic drop has a direct qualifying edge to its kept
  representative.
- The source contains 116 exact duplicate groups with 262 total members and a
  maximum group size of 16. Exact-group membership is counted independently of
  the final direct decision type.
- 68,552 lexical-near or semantic-near edges between kept representatives form
  249 review clusters with 1,308 members; the largest has 349 members. None of
  these review-only edges caused automatic deletion.
- HNSW mean recall@64 is 0.992554 on the frozen 128-query FlatIP audit, above
  the 0.98 gate. No query remained saturated at `k = 512`.
- Corrected attention-mask token counts flag 64,840 of 414,421 used posts as
  possibly truncated at 256 tokens, rather than treating padding as content.

Aggregate evidence is in
[`reports/dedup-preflight-v2.json`](reports/dedup-preflight-v2.json), the
independent audit is in
[`reports/dedup-verification-v2.json`](reports/dedup-verification-v2.json), and
private artifact hashes are in
[`../../../../data/iac2/manifests/dedup-v2.json`](../../../../data/iac2/manifests/dedup-v2.json).

## Failed V1

V1 remains failed evidence. Its mean recall@64 was 0.975464, below the frozen
0.98 gate, and padded tokenizer lengths incorrectly marked every post as
possibly truncated. V2 reused only hash-verified post embeddings and the HNSW
graph, raised `efSearch` from 256 to 768, recomputed token counts, and regenerated
all searches, edges and decisions. No V1 decision or edge was reused.

No annotation labels or train/dev/test assignments are created here. Review
clusters must be grouped or explicitly adjudicated by a later sampling protocol;
semantic similarity alone is not label equivalence.
