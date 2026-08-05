# DATA-GOE-FULL-DEV-RATER-EVAL-V1: Full-dev Per-rater Diagnostic Boundary

Registration date: 2026-08-04 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-GOE-FULL-DEV-RATER-EVAL-V1`
- Parent protocols: `DATA-GOE-V1`, `DATA-GOE-DEV-RATER-EVAL-V1`
- Status: `FROZEN BEFORE FULL-DEV MATCH RETENTION AND SCORING`
- Purpose: retain the raw per-rater label sets for every row in the already-frozen GoEmotions
  official dev split, then use them only to rescore frozen model predictions.

The official raw archive bytes were previously streamed by EXP-036, but only its frozen 174-row
allowlist was retained. This protocol is frozen before retaining or analysing annotations for the
remaining dev rows.

## Scope

This protocol does not replace the official simplified dev labels and does not construct a new
ground truth. It adds two diagnostic views of the same 5,426 dev examples:

1. expected agreement with one clear individual annotator;
2. a soft target equal to the fraction of clear annotators selecting each label.

It does not:

- acquire or read simplified `test.tsv`;
- train, tune, select, or rank checkpoints;
- change prompts, decoders, thresholds, or label mappings;
- retrieve parent comments, threads, authors, subreddits, or timestamps;
- treat any individual rater or vote fraction as authoritative;
- replace official full-dev metrics in benchmark or thesis comparisons.

## Authoritative Sources

- Repository revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`.
- Official simplified dev and label files are frozen by SHA-256 in the EXP-037 config.
- Raw objects are the three official `goemotions_[1-3].csv` files published at
  `https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/`.
- Because the raw URLs are not revision-addressed, byte size, ETag, Last-Modified, MD5, SHA-256,
  and raw row count are frozen in the EXP-037 config.

## Selection Boundary

The allowlist contains every row of the frozen official `dev.tsv`, in source order.

- Expected rows: 5,426.
- Expected row numbers: exactly `1..5426`.
- Ordered comma-separated row-number SHA-256:
  `973b9f662bf3fac69c014da03f4741bf312e409bd38ddb1d8e4d8c6c48a3fa98`.

No raw annotation, text, metadata, model output, label cardinality, or prior error pattern may
affect inclusion.

## Streaming Boundary

The raw annotations are published as three whole CSV objects rather than split-specific files.
Each object must be streamed once to find the frozen dev allowlist. Nonmatching records may
contribute only to whole-object integrity hashes and row counts; their content must not be
persisted, logged, sampled, or summarized.

This transport may traverse records associated with other simplified splits, but simplified test
membership and labels remain unknown and unused. Reports must describe this as full-archive
transport with full-dev-allowlist persistence.

## Retained Fields

Private, gitignored matched records may retain:

- anonymous SHA-256 of the comment ID and rater ID;
- source dev row number, source object, and source line;
- SHA-256 of text plus an equality check against `dev.tsv`;
- `example_very_unclear`;
- the selected per-rater label IDs.

Raw text, upstream IDs, author, subreddit, link ID, parent ID, timestamp, and raw rater ID must not
be persisted. Public artifacts may contain anonymous row numbers, label names, counts, metrics,
and methodology only. Public per-example artifacts must not contain text or upstream identifiers.

## Join and Scoring Eligibility

- All 5,426 allowlisted IDs must be found.
- Every retained raw text must exactly match its frozen simplified dev text.
- Each anonymous comment/rater pair must be unique.
- Reapplying the official `>=2 raters` rule must reproduce all 5,426 simplified targets exactly.
- Primary scoring includes only annotations where `example_very_unclear=false`.
- Every primary-scoring annotation must contain at least one of the 28 labels; otherwise the run
  stops instead of silently interpreting an empty set.
- Every dev example must have at least one primary-scoring annotation.
- Sensitivity scoring may include unclear annotations only when they contain at least one label.

A source, schema, join, text, duplicate, aggregation, or coverage mismatch stops model scoring and
interpretation.
