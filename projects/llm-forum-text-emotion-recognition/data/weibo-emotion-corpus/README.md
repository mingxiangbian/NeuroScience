# Weibo Emotion Corpus: Frozen EClass Track

This directory contains the public repository snapshot first audited under
[`DATA-FCTX-PUBLIC-AUDIT-V1`](../../experiments/forum-context/protocols/data-public-candidate-viability-audit-v1.md)
and the aggregate manifest for the subsequently adopted EClass task defined by
[`DATA-WEIBO-TASK-V1`](../../experiments/forum-context/protocols/data-weibo-eclass-task-v1.md).

## Storage Boundary

- `official/` contains upstream microblog text and structural identifiers and
  is ignored by Git.
- `derived-private/` contains row-level task data, HMAC identifiers, duplicate
  diagnostics and sealed test labels and is ignored by Git.
- `manifest.json` contains only source metadata, hashes and the aggregate audit
  decision.
- `eclass-v1.manifest.json` contains only aggregate task counts, artifact hashes
  and the independent verification status.
- No external Weibo content was recovered.

## Pinned Source

- Repository: <https://github.com/wjhou/Weibo-Emotion-Corpus>
- Revision: `d385f8cdc7e7ab9ca1ec62b8202c664a5ba651f3`
- Repository license: Apache-2.0

## Frozen Task Decision

`adopted_primary_single_label_context_task`: the independently parsed EClass
subset is the primary formal data track for the next same-dataset experiments.
This does not alter the earlier broad-audit finding that the repository as a
whole is not a ready-made general forum-emotion benchmark.

The two TSV files are separate task releases and cannot be joined by row
position. `DATA-WEIBO-TASK-V1` therefore uses only the independently defined
EClass records from `emotion_classification.tsv`; the ECause rows and the other
TSV do not supply labels or joined context.

The frozen task retains 8,540 seven-class records after structural filtering,
label filtering and target-label canonicalization. The group- and duplicate-
disjoint split contains 5,995 train, 1,272 validation and 1,273 sealed-test
records. Of the retained records, 6,138 have a preceding local clause and 2,402
do not. Every sample has paired `target_only` and `previous_context` views;
future clauses are excluded from model input.

The independent verifier passed 33/33 checks. This verifies data construction,
split balance, leakage controls, paired views, public privacy boundaries and
test sealing only. It does not authorize test access and is not a model result.

The dataset remains a limited proxy: `PrevCL` is an adjacent clause in the same
multi-user group, not a guaranteed reply parent or complete forum thread.

See the [aggregate audit report](../../experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md).
See also the [EClass construction report](../../experiments/forum-context/weibo-eclass/reports/data-weibo-eclass-v1.json)
and [independent verification report](../../experiments/forum-context/weibo-eclass/reports/data-weibo-eclass-v1-verification.json).
