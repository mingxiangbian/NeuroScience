# Hotter and Colder Candidate Snapshot

This directory contains the local CLARIN release audited under
[`DATA-FCTX-PUBLIC-AUDIT-V1`](../../experiments/forum-context/protocols/data-public-candidate-viability-audit-v1.md).

## Storage Boundary

- `official/` contains upstream annotation records, URLs and hydration code and
  is ignored by Git.
- `manifest.json` contains only source metadata, hashes and the aggregate audit
  decision.
- Hydration was not run, and no live blog page was requested.

## Pinned Source

- CLARIN record: <http://hdl.handle.net/20.500.12537/352>
- Release license: CC BY 4.0
- Package MD5: `6f26a58c5771158c0f9492096222ad6c` (verified)

## Audit Decision

The frozen audit manifest records `blocked_pending_review`: the package
contains labels and live links but no target text, prior comments or blog-post
text. Its hydration script scrapes live pages, has no timeout, processes only
50 rows by default, appends comment signatures and reconstructs chronological
history rather than explicit reply edges.

The eight emotion tasks are separate binary annotation rows, not a complete
eight-label matrix for each target. The README's emotion-label description also
conflicts with the observed fields.

## Project Decision

`excluded_by_project_decision` (2026-08-08): Hotter and Colder will not be used
for this thesis. Do not hydrate its links or use it for training, model
selection, evaluation or thesis claims. The ignored upstream snapshot and the
frozen audit artifacts are retained only for provenance. This post-audit
decision does not alter the manifest or the completed audit report.

See the [aggregate audit report](../../experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md).
