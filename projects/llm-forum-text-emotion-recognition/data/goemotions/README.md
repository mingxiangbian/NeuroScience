# GoEmotions Data Snapshot

GoEmotions data is stored at the project level, parallel to the existing
TweetEval snapshot:

```text
projects/llm-forum-text-emotion-recognition/data/
├── tweeteval-emotion/
└── goemotions/
    ├── README.md
    ├── manifest.json
    └── official/
        ├── emotions.txt
        ├── train.tsv
        └── dev.tsv
```

`official/` contains upstream text and is ignored by Git. `manifest.json`
contains only source metadata, hashes, counts and validation results; it must
not contain comment text or upstream comment IDs.

The source, label space and split rules are frozen in
[`DATA-GOE-V1`](../../experiments/goemotions/protocols/data-protocol-v1.md).

## Current Snapshot

- `train.tsv`: acquired and verified, 43,410 rows.
- `dev.tsv`: acquired and verified, 5,426 rows.
- `emotions.txt`: acquired and verified, 28 ordered labels.
- `test.tsv`: not acquired.
- [`manifest.json`](manifest.json): source revision, hashes, counts and reviewed
  train/dev overlap diagnostics.

## Preparation Command

Run from the project root:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  experiments/goemotions/prepare_data.py
```

The script can acquire only `train.tsv`, `dev.tsv` and `emotions.txt`.
It has no option to acquire `test.tsv`, and it stops if a local test file is
present.

## Test Boundary

`test.tsv` must remain absent until a separate GoEmotions `TEST-READY`
protocol freezes all encoder and LLM conditions and the user explicitly
authorizes the test gate.
