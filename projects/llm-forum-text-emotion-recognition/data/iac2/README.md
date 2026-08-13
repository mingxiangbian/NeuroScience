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

## Current derived artifact

The first cleaning attempt is retained as failed evidence because it interpreted
the IAC quote offset incorrectly. Its public correction record is
`experiments/forum-context/dataset-construction/reports/cleaning-v1-correction.json`.

The schema-correct V2 artifact is stored privately at
`derived-private/dataset-construction/cleaning-v2.sqlite`. It contains 403,374
parent-target candidates, of which 403,336 pass the conservative hard filters.
The full run passed 40 independent checks with zero mismatches. Trackable hashes
and aggregate-only results are recorded in `manifests/cleaning-v2.json` and the
dataset-construction reports.

The verified deduplication outputs are stored privately as
`derived-private/dataset-construction/dedup-v2.sqlite`,
`dedup-v2-post-embeddings.f32`, and `dedup-v2-pair-hnsw.faiss`. V2 retains
403,183 pairs after 153 exact or format-only automatic drops. It also records
249 unresolved lexical-near or semantic-near review clusters containing 1,308
members; those clusters are not automatic deletions. The run passed 69
independent checks with zero mismatches, and aggregate hashes are recorded in
`manifests/dedup-v2.json`.

The verified sampling preflight stores its 120-row primary manifest and 60-row
reserve manifest privately under `annotations/pilot-v1/`. Both files are mode
`0600`, contain no forum text and are ignored by Git. Their aggregate-only
selection and independent verification reports are trackable under
`experiments/forum-context/annotation/reports/`.

The 120 selected primary cases have also been exported privately to
`annotations/pilot-v1/views/` in frozen annotation order. The directory is mode
`0700`, every view is mode `0600`, and independent database reconstruction
passed 34 checks with zero mismatches. Public reports contain only aggregate
structure and hashes.

No emotion labels, annotation records, blind-repeat records or train/dev/test
assignments have been created.

## Usage restrictions

Use the corpus only for local, non-commercial thesis research under the audited
IAC 2.0 research-use boundary. Do not upload raw or derived text to public model
APIs, public storage, Git, or annotation services. Do not publish raw text,
cleaned per-sample text, derived labels, embeddings, or checkpoints without
separate authorization.

The full permission assessment is recorded in:

`sources/llm-forum-text-emotion-recognition-iac2-assessment.md`
