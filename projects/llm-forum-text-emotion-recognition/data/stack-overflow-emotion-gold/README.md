# Stack Overflow Emotion Gold: Frozen C0 Track

This directory contains the public metadata for the six-label Stack Overflow
target-text task defined by
[`DATA-SO-TASK-V1`](../../experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md).

## Storage Boundary

- `official/` contains the pinned upstream XLSX and is ignored by Git.
- `derived-private/` contains row-level text, train/validation labels, sealed
  test labels and duplicate diagnostics and is ignored by Git.
- `task-v1.split-index.jsonl` contains only opaque sample/component IDs and
  split assignments. It contains no text, labels or upstream row fields.
- `task-v1.manifest.json` contains source metadata, aggregate counts, hashes
  and verification state.

## Pinned Source

- Repository: <https://github.com/collab-uniba/EmotionDatasetMSR18>
- Revision: `d6a679f39a198fdb0657a6116d35dd7b92496898`
- Workbook: `Emotions_GoldSandard_andAnnotation.xlsx`
- SHA-256: `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`

The repository README asks researchers to cite Novielli, Calefato and
Lanubile (MSR 2018), but the repository does not contain a standard data
license. Row-level data therefore remains private to this research workspace.
This conservative storage decision is not a legal determination.

## Task Boundary

The task is target-only multi-label classification over `love`, `joy`,
`surprise`, `anger`, `sadness` and `fear`. `neutral=true` is derived only when
all six labels are zero; it is not a seventh softmax class. The workbook's
`Group`, `Set` and local number fields are annotation-release coordinates, not
verified Stack Overflow post IDs or thread identifiers. This split is therefore
duplicate-component-disjoint, not thread-disjoint.

## Verified Result

`DATA-SO-TASK-V1` passed independent verification on 2026-08-13:

- 4,800 rows and 4,681 duplicate components;
- train/validation/test rows: 3,360/720/720;
- train/validation/test components: 3,277/702/702;
- `surprise` positives: 31/7/7;
- duplicate components: 69/15/15, including 18/4/4 conflicting components;
- independent checks: 53/53; synthetic unit tests: 11/11.

See [`task-v1.manifest.json`](task-v1.manifest.json), the
[construction report](../../experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json)
and the
[verification report](../../experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json).
Test labels remain sealed and are not authorized for model access until a later
`TEST-READY` protocol receives explicit approval. No model was trained or
evaluated during data construction.
