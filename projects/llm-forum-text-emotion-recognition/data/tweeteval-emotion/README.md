# TweetEval Emotion Data Snapshot

---
downloaded: 2026-07-29
status: local-upstream-snapshot
task: emotion
language: English
---

## Source

- Official repository: <https://github.com/cardiffnlp/tweeteval>
- Upstream commit: `4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66`
- Local snapshot: `official/`
- Download method: shallow clone to a temporary directory, followed by a copy of the emotion task, upstream example predictions, evaluation script, and upstream documentation.

The upstream snapshot is ignored by Git. It contains social-media text and must not be republished from this repository without a separate terms and licensing review.

## Included Files

```text
official/
├── README.md
├── evaluation_script.py
├── datasets/
│   ├── README.txt
│   └── emotion/
│       ├── mapping.txt
│       ├── train_text.txt
│       ├── train_labels.txt
│       ├── val_text.txt
│       ├── val_labels.txt
│       ├── test_text.txt
│       └── test_labels.txt
└── predictions/
    └── emotion.txt
```

## Fixed Task Definition

| Label ID | Label |
| --- | --- |
| 0 | anger |
| 1 | joy |
| 2 | optimism |
| 3 | sadness |

| Split | Text rows | Label rows |
| --- | ---: | ---: |
| train | 3,257 | 3,257 |
| validation | 374 | 374 |
| test | 1,421 | 1,421 |

The official train, validation, and test splits are retained unchanged.

## Integrity

| File | SHA-256 |
| --- | --- |
| `datasets/emotion/mapping.txt` | `656dea85d149716af96206ca19bec0d94e9dc6de3f5079f5c7c2a241ec76cadb` |
| `datasets/emotion/train_text.txt` | `2c62f67aeb3eac1aea0e5a9c3d0f4bc337992581f3f858061786a1fb4d79d95e` |
| `datasets/emotion/train_labels.txt` | `987e767d8679e18abdf7de37a6d2bcd0a40a296ddd704e8d515cf0e3033c8d9c` |
| `datasets/emotion/val_text.txt` | `e2e30c86b8cbb97944d6543aedc06eace3bb275cb2f381aba787b838b4f23ca5` |
| `datasets/emotion/val_labels.txt` | `313730630160b7e0a6b4235b800c76683f4aeeb72d094eb69646630cd5cfe338` |
| `datasets/emotion/test_text.txt` | `7e1070f5d3e3fcece5bc73680bff9981e90d8f7b2f1009bfe7a01d059d1c6091` |
| `datasets/emotion/test_labels.txt` | `245072348c711961785be6d395997f97cf7fcda3effeae7805664171dc75f913` |
| `predictions/emotion.txt` | `16c6cf2b1c678bc739a738aa565e1f1bfb67e365cfc06fb413bfda9ddbaf88a0` |
| `evaluation_script.py` | `86c824e466ffba0cd407655fbbda759c6a9c09e541be4bfaaf547df8255d2793` |

## Evaluator Smoke Test

Environment:

- Python: `/Users/phoenix/miniconda3/envs/llm/bin/python`
- scikit-learn: `1.7.2`

Command:

```bash
cd projects/llm-forum-text-emotion-recognition/data/tweeteval-emotion/official
/Users/phoenix/miniconda3/envs/llm/bin/python evaluation_script.py \
  --tweeteval_path ./datasets \
  --predictions_path ./predictions \
  --task emotion
```

Observed result:

```text
TweetEval Score (emotion): 0.7982724123055319
```

This score comes from the example `predictions/emotion.txt` supplied by the upstream repository. It verifies that the downloaded labels, predictions, and evaluator are mutually compatible. It is not a result produced by this project and must not be entered as project evidence.

## Next Step

Freeze the selected balanced TF-IDF baseline and test protocol, preserve the
reproducible code and validation comparison, and then evaluate the selected
model once on the test split. Keep all project-generated configuration,
predictions, and metrics separate from this upstream snapshot.
