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
        ├── dev.tsv
        ├── test.tsv
        └── full_dataset/
            ├── goemotions_1.csv
            ├── goemotions_2.csv
            └── goemotions_3.csv
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
- `test.tsv`: acquired once for EXP-038, 5,427 rows, SHA-256
  `0587b2dd8b27b97352adbfc3fb083d46005c8946657fdc2b1ca8b1cc7f1f8be4`;
  the test gate is consumed.
- [`manifest.json`](manifest.json): source revision, hashes, counts and reviewed
  train/dev overlap diagnostics.
- `full_dataset/goemotions_{1,2,3}.csv`: official unpartitioned raw release,
  acquired for `DATA-FCTX-CJ-V1`; 211,225 rater rows and 58,011 unique comment
  IDs. File hashes and parent-coverage results are recorded in
  [`closed-corpus-parent-coverage.json`](../../experiments/forum-context/preflight/closed-corpus-parent-coverage.json).

## Preparation Command

Run from the project root:

```bash
/Users/phoenix/miniconda3/envs/llm/bin/python \
  experiments/goemotions/prepare_data.py
```

The script prepares only `train.tsv`, `dev.tsv` and `emotions.txt`. EXP-038
acquired and bound `test.tsv` separately through
[`acquire_test.py`](../../experiments/goemotions/test-gate/acquire_test.py).

## Test Boundary

EXP-038 consumed the one authorized GoEmotions test gate. The raw file remains
gitignored and may now be read only for frozen-result verification or explicitly
registered post-hoc analysis, never for prompt, threshold, model or checkpoint
selection. New forum/context development must use a new validation split and an
independent holdout.

The full raw release is unpartitioned and therefore necessarily includes comments
that later belong to filtered splits. The parent-coverage audit did not read
`test.tsv`, resolve test membership or use raw emotion labels. Raw comments found
as parents must not enter model development until a separate split/leakage rule is
frozen.
