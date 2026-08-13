# DATA-FCTX-DEDUP-V2: Exact, Lexical-near and Semantic-near Deduplication

- Date frozen: 2026-08-05
- Parent data: `DATA-FCTX-CLEAN-V2`
- Unit: eligible direct `parent -> target` pair
- Stage: before annotation, sampling and split assignment
- External services: forbidden
- Public raw/cleaned text, IDs, embeddings and indexes: forbidden

## 1. Purpose and claim boundary

The stage detects duplicate candidate pairs while preserving differences that
may change an emotion label. It produces:

1. deterministic auto-dedup decisions for exact and format-only duplicates;
2. lexical-near and semantic-near review queues;
3. aggregate evidence about duplicate prevalence and retrieval quality.

Semantic similarity is not treated as label equivalence. A negation, stance word
or emotion-bearing token can change the target while leaving an embedding highly
similar. Therefore no semantic-only edge can set
`eligible_after_auto_dedup = 0` in V2.

V2 supersedes V1 for downstream decisions. V1 is retained as failed evidence:
its deterministic 128-query audit obtained mean recall@64 of 0.975464, below the
frozen 0.98 gate, and its padded-batch `return_length` metadata incorrectly
flagged every embedded post as possibly truncated. V2 changes only retrieval
effort and token-count accounting. It does not loosen similarity thresholds or
automatic-deletion rules, and it does not reuse any V1 edge or decision.

## 2. Input and pair boundary

Input is the private
`data/iac2/derived-private/dataset-construction/cleaning-v2.sqlite` whose
SHA-256 must match `data/iac2/manifests/cleaning-v2.json`.

Only the 403,336 rows with `eligible = 1` enter this stage. Parent and target
roles remain separate throughout scoring. Target-only duplicates with different
parents are context variants, not automatic pair duplicates.

## 3. Exact duplicate

An exact pair duplicate has the same frozen `pair_sha256`, which is derived
from the parent and target `dedup_body` hashes. Each exact cluster keeps one
deterministic representative; every other row is marked `drop_exact`.

Exact grouping does not depend on embeddings or approximate retrieval.

## 4. Lexical-near duplicate

Lexical metrics are computed independently for parent and target over the full,
untruncated `dedup_body`:

- character 5-gram set Jaccard;
- character-length ratio;
- ordered alphanumeric token sequence;
- negation-token multiset and numeric-token sequence.

A pair is a lexical-near review candidate when both roles satisfy:

- character 5-gram Jaccard >= 0.85;
- character-length ratio >= 0.85;
- identical negation and numeric signatures.

A lexical edge is eligible for automatic format-only collapse only when the
ordered alphanumeric token sequences are identical for both parent and target.
This permits differences in punctuation or formatting but not insertion,
deletion, replacement or reordering of lexical tokens. Auto collapse is still
direct-to-representative; transitive chains cannot delete a row that lacks a
qualifying direct edge to its kept representative.

All other lexical-near edges remain `review_lexical`.

## 5. Semantic-near duplicate

Model:

- `sentence-transformers/all-MiniLM-L6-v2`
- frozen revision:
  `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`
- local-only loading; no API or network inference;
- 384-dimensional mean-pooled, L2-normalized float32 embeddings;
- `model_body` input, maximum 256 wordpieces.

Parent and target are embedded separately. Pair similarity is:

```text
pair_cosine = (parent_cosine + target_cosine) / 2
```

Candidate retrieval uses a FAISS HNSW inner-product index over the concatenated,
normalized parent and target embeddings:

- dimension: 768;
- `M = 32`;
- `efConstruction = 200`;
- `efSearch = 768`;
- initial `k = 64`, adaptive up to `k = 512`;
- retrieval floor: pair cosine >= 0.88.

An edge enters semantic review when:

- pair cosine >= 0.92;
- parent cosine >= 0.85;
- target cosine >= 0.85.

It is additionally marked `semantic_strong` when pair cosine >= 0.96 and both
role cosines >= 0.94. Neither class is an automatic deletion. Inputs reaching
the 256-token limit receive a possible-truncation flag on the review edge.
`token_count_capped` is the post-padding sum of the tokenizer attention mask,
so padding tokens are excluded; a value of 256 means that truncation is possible,
not proven.

The embedding and retrieval runtimes are process-isolated. A streaming worker
loads only PyTorch and MiniLM, writes private embeddings and capped token counts,
and exits before the parent process loads FAISS. This avoids mixing incompatible
OpenMP runtimes and prevents all source text from residing in memory at once.

V2 may reuse V1's frozen post-embedding file and HNSW graph only after verifying
the V1 failed-run status plus the cleaning-database, model-revision, selected
model-file, embedding-file, index-file, report and manifest hashes. Reuse is
valid here because input ordering, model, pooling, vector dimension, `M` and
`efConstruction` are unchanged. V2 recomputes token counts, sets
`efSearch = 768`, reruns retrieval and classification, and creates all edges and
decisions from scratch.

## 6. Representative selection and decisions

Representative rank is frozen before results:

1. fewer severe quality flags;
2. fewer total quality flags;
3. larger capped combined parent-target word count;
4. lexical order of private `sample_uid`.

Severe flags are `decode_replacement`, `quote_structure_unverified`,
`quote_text_missing`, `html_quote_unstructured`, `no_lexical_tokens` and
`url_only`, including parent/target prefixes.

Decision values:

- `keep`
- `drop_exact`
- `drop_format_only`
- `review_lexical`
- `review_semantic`

Review states do not override `keep`; they are stored separately. Every
automatic drop must point directly to a kept representative through an exact or
format-only edge.

`auto_decision` describes the direct relation to the final kept representative,
not original exact-group membership. If the best member of an exact group is
itself format-collapsed into another kept pair, all members of that exact group
may therefore receive `drop_format_only`. Exact duplicate clusters and members
remain independently accounted from the frozen `pair_sha256` values, and every
member of an exact group must resolve to the same final representative.

## 7. Approximate-retrieval quality gate

The HNSW stage is approximate and must not be described as exhaustive.

Before accepting the run:

- exact duplicate accounting must match the frozen cleaning database;
- deterministic synthetic retrieval tests must pass;
- exact flat-search recall@64 is recomputed for a deterministic 128-query audit
  sample and must be >= 0.98;
- no query may remain saturated at `k = 512` with its final returned score at
  or above the semantic review threshold of 0.92;
- every stored edge must independently satisfy its recorded score and guard
  rules.
- a deterministic 32-post sample must reproduce stored embeddings and token
  counts in a separate PyTorch-only replay process.
- reuse provenance must prove that only V1 embeddings and the HNSW graph were
  reused; V1 edges and decisions are forbidden.

Failure of a gate keeps the run as failed evidence and forbids use of its
automatic decisions.

## 8. Private and trackable outputs

Private and gitignored:

- `data/iac2/derived-private/dataset-construction/dedup-v2.sqlite`
- `data/iac2/derived-private/dataset-construction/dedup-v2-post-embeddings.f32`
- `data/iac2/derived-private/dataset-construction/dedup-v2-pair-hnsw.faiss`

Trackable and aggregate-only:

- `deduplication/reports/dedup-preflight-v2.json`
- `deduplication/reports/dedup-verification-v2.json`
- `data/iac2/manifests/dedup-v2.json`

Public files must not contain forum text, source IDs, HMAC IDs, embeddings,
duplicate hashes, absolute paths or per-edge records.

## 9. Out of scope and change control

V2 does not adjudicate semantic candidates, choose annotation samples, remove
topic imbalance, assign splits or train a model. Any change to the pair unit,
auto-drop rules, thresholds, embedding revision or HNSW parameters requires a
new protocol version.
