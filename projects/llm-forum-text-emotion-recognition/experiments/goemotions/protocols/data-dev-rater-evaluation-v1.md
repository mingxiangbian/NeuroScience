# DATA-GOE-DEV-RATER-EVAL-V1: Dev Per-rater Diagnostic Boundary

Registration date: 2026-08-04 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-GOE-DEV-RATER-EVAL-V1`
- Parent protocols: `DATA-GOE-V1`, `DATA-GOE-ANNOT-AUDIT-V1`
- Status: `FROZEN BEFORE DEV RAW ANNOTATION ACCESS`
- Purpose: retain the raw per-rater label sets for the 174 already-frozen GoEmotions dev rows
  whose simplified labels contain `neutral` plus at least one emotion, then use them only for a
  disagreement-aware diagnostic of frozen predictions.

## Scope

This protocol does not replace the official simplified dev labels and does not create a new ground
truth. It adds an analysis-only view that asks how well a frozen prediction agrees, on average,
with one clear individual annotator rather than with the union produced by the official
`>=2 raters` aggregation rule.

It does not:

- acquire or read simplified `test.tsv`;
- train, tune, select, or rank checkpoints;
- change prompts, decoders, thresholds, or label mappings;
- retrieve parent comments, threads, authors, subreddits, or timestamps;
- treat any individual rater as authoritative;
- replace full-dev official metrics in benchmark or thesis comparisons.

## Authoritative Sources

- Repository revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`.
- Official simplified dev and label files are frozen by SHA-256 in the EXP-036 config.
- Raw objects are the three official `goemotions_[1-3].csv` files published at
  `https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/`.
- Because the raw URLs are not revision-addressed, byte size, ETag, Last-Modified, MD5, and
  SHA-256 are all frozen in the EXP-036 config before the diagnostic run.

## Selection Boundary

The allowlist is derived only from the frozen official `dev.tsv`:

```text
neutral label ID 27 is present AND official label cardinality > 1
```

Expected selected rows: 174. The ordered source-dev row-number SHA-256 is
`99368f7f6f014acb46bd96e0a7c6cb38acc60e31daedb5f2e07b9b5d86fd2c4f`.

No raw annotation, text, metadata, or model output may affect row selection.

## Streaming Boundary

The raw annotations are published as three whole CSV objects rather than split-specific files.
Each object must be streamed once to find allowlisted IDs. Nonmatching records may contribute only
to whole-object integrity hashes and row counts; their content must not be persisted, logged,
sampled, or summarized.

This transport may traverse records associated with other simplified splits, but simplified test
membership and labels remain unknown and unused. Reports must describe this precisely as
full-archive transport with dev-allowlist persistence, not as an absence of raw test-associated
bytes.

## Retained Fields

Private, gitignored matched records may retain:

- anonymous SHA-256 of the comment ID and rater ID;
- source dev row number, source object, and source line;
- SHA-256 of text plus an equality check against `dev.tsv`;
- `example_very_unclear`;
- the selected per-rater label IDs.

Raw text, upstream IDs, author, subreddit, link ID, parent ID, timestamp, and raw rater ID must not
be persisted. Public artifacts may contain anonymous hashes, row numbers, official label names,
counts, metrics, and methodology only.

## Join and Scoring Eligibility

- All 174 allowlisted IDs must be found.
- Every retained raw text must exactly match its frozen simplified dev text.
- Each anonymous comment/rater pair must be unique.
- Reapplying the official `>=2 raters` rule must reproduce all 174 simplified targets exactly.
- Primary scoring includes only annotations where `example_very_unclear=false`.
- Every primary-scoring annotation must contain at least one of the 28 labels; otherwise the run
  stops instead of silently interpreting an empty set.
- Sensitivity scoring may include unclear annotations only when they contain at least one label.

A source, schema, join, text, duplicate, or aggregation mismatch stops model scoring and
interpretation.

