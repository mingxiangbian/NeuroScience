# IAC 2.0 Local Data

This directory is the private local landing area for the IAC 2.0 corpus used by
the forum-context track.

## Data boundary

- `raw/` contains official source dumps and must never be committed or published.
- `derived-private/` contains extracted or de-identified per-sample text and must
  never be committed or published.
- `annotations/` contains per-sample human or model-assisted labels and must never
  be committed or published.
- `manifests/` may contain source metadata, checksums, schemas, and aggregate
  statistics, but no forum text, user identifiers, or reversible mappings.

The root `.gitignore` excludes all three private directories. Before using a new
file, confirm it is ignored with `git check-ignore -v`.

## Current local source

Only the 4forums dump has been retained because it is the selected pilot source.
The official compressed dump passed a gzip integrity check, and its copied hash
matches the downloaded source. See `manifests/raw-files.json` for the recorded
file metadata.

## Usage restrictions

Use the corpus only for local, non-commercial thesis research under the audited
IAC 2.0 research-use boundary. Do not upload raw or derived text to public model
APIs, public storage, Git, or annotation services. Do not publish raw text,
cleaned per-sample text, derived labels, embeddings, or checkpoints without
separate authorization.

The full permission assessment is recorded in:

`sources/llm-forum-text-emotion-recognition-iac2-assessment.md`
