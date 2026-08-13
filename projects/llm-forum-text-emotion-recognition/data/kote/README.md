# KOTE Candidate Snapshot

This directory contains the local KOTE candidate audited under
[`DATA-FCTX-PUBLIC-AUDIT-V1`](../../experiments/forum-context/protocols/data-public-candidate-viability-audit-v1.md).

## Storage Boundary

- `official/` contains upstream text and IDs and is ignored by Git.
- `manifest.json` contains only source metadata, hashes and the aggregate audit
  decision.
- `test.tsv` was not downloaded or parsed.

## Pinned Source

- Repository: <https://github.com/searle-j/KOTE>
- Revision: `cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977`
- Repository license: MIT
- Acquired splits: 40,000-row train and 5,000-row validation

## Current Decision

`eligible_training_control`: KOTE may be considered as a Korean C0
target-only multi-label training/control source. It has no parent, thread,
author or row-level platform field and cannot support a context claim.

The released labels intentionally reproduce the paper's five-rater vote
transformation and average 7.91 positive labels per comment. A later adoption
protocol must freeze ontology mapping and the treatment of `NO EMOTION`; this
audit does not authorize training or final dataset adoption.

See the [aggregate audit report](../../experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md).
