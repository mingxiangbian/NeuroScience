# RoBERTa Base Model

This directory records the immutable upstream model used to initialize the
TweetEval emotion encoder baseline.

- Upstream repository: `FacebookAI/roberta-base`
- Frozen revision: `e2da8e2f811d1448a5b465c236feacd80ffbac7b`
- Local snapshot: `snapshot/`
- Integrity record: `manifest.json`

The downloaded snapshot is intentionally gitignored because it contains a
roughly 499 MB model binary. The revision, selected files, sizes, and SHA-256
hashes remain tracked in `manifest.json`.

The snapshot contains the pretrained encoder only. A four-label TweetEval
classification head is initialized later by the training code; no fine-tuned
checkpoint exists at this stage.
