# DATA-GOE-ANNOT-AUDIT-V1: Train-only Raw Annotation Audit Boundary

Registration date: 2026-08-04 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-GOE-ANNOT-AUDIT-V1`
- Parent protocol: `DATA-GOE-V1`
- Status: `FROZEN BEFORE RAW ANNOTATION ACCESS`
- Purpose: inspect per-rater votes for the 1,396 already-frozen GoEmotions train rows whose
  simplified labels contain `neutral` plus at least one emotion.

## Scope

This protocol does not replace or modify `DATA-GOE-V1`. It adds a private, analysis-only view of
the official raw annotation archive for a train-ID allowlist fixed before raw annotations are read.
It may answer whether simplified `neutral+emotion` targets reflect same-rater co-selection,
cross-rater aggregation, or unclear annotations.

It does not:

- reconstruct parent comments or conversation threads;
- use author, subreddit, link, parent, or timestamp metadata;
- acquire or read the simplified `test.tsv`;
- select a model, prompt, checkpoint, threshold, or training configuration;
- revise official labels or create a new ground truth.

## Authoritative Sources

- Repository revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`.
- Official schema: `goemotions/README.md` at that revision.
- Raw archive declaration: `goemotions/data/full_dataset/README.md` at that revision.
- Raw objects:
  - `https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_1.csv`
  - `https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_2.csv`
  - `https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_3.csv`

The raw objects are not revision-addressable URLs. Their byte sizes, ETags, server MD5 values, and
last-modified timestamps are therefore frozen in the EXP-035 config before streaming.

## Selection Boundary

The allowlist is derived only from the already-acquired official `train.tsv`:

```text
neutral label ID 27 is present AND label cardinality > 1
```

Expected selected rows: 1,396. The ordered source-train row-number SHA-256 is
`6d2ce3b10b41365eba24d5d5aaa1afce66f6b3f043d49204559deb4b8b0a59d9`.

No label, text, metadata, or annotation from a non-allowlisted raw row may affect selection.

## Streaming and Test Boundary

Google publishes the raw annotations as three whole CSV objects rather than split-specific files.
The acquisition process must therefore stream each complete object to find allowlisted IDs. This
transport necessarily traverses raw records later used across the official simplified splits.

To preserve the development boundary:

- only records whose `id` is in the frozen train allowlist may be retained;
- nonmatching rows may contribute only source byte hash and row-count integrity checks;
- no nonmatching text, ID, metadata, rater vote, label, or split membership may be logged,
  persisted, summarized, sampled, or exposed to the reviewer;
- `test.tsv` must remain absent and must not be requested;
- the run must report this as full-archive transport with train-only persistence, rather than
  claiming that no raw test-associated bytes traversed the process.

This audit does not consume a model test gate because no model is evaluated and no simplified test
membership or labels are used. It must nevertheless retain this transport caveat in every report.

## Retained Private Fields

For matching train IDs only, the private extraction may retain:

- comment ID and its SHA-256;
- source train row number;
- source raw file and line number;
- SHA-256 of the comment text and an equality check against `train.tsv`;
- SHA-256 of rater ID, not the raw rater ID;
- `example_very_unclear`;
- the 28 binary per-rater labels.

Raw text is retained only for the deterministic qualitative sample and only inside a gitignored
`private/` directory. Author, subreddit, link ID, parent ID, timestamp, and raw rater ID are never
persisted.

## Public Output Boundary

Tracked outputs may contain anonymous row numbers, SHA-256 identifiers, official label names,
vote counts, aggregate statistics, qualitative codes, source hashes, and methodology. They must
not contain raw comment text, upstream comment IDs, raw rater IDs, usernames, subreddit names,
parent IDs, or free-form private notes.

## Join and Integrity Rules

- Every one of the 1,396 allowlisted IDs must be found in the raw archive.
- Every retained raw text must exactly match the corresponding simplified train text.
- Each comment/rater pair must be unique after hashing.
- Reapplying the official `>=2 raters` rule must reproduce every simplified target exactly.
- A source size, ETag, MD5, header, join, text, or label-reproduction mismatch stops qualitative
  interpretation and is reported as a source-linkage discrepancy.

