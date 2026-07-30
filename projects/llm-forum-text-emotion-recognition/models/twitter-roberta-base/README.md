# Twitter RoBERTa Base Model

This directory records the immutable Twitter-domain pretrained encoder used
for the TweetEval emotion domain-pretraining comparison.

- Upstream repository: `cardiffnlp/twitter-roberta-base`
- Frozen revision: `cbb417e9647b51504caf68cbe1af6bbf56da06b7`
- Local snapshot: `snapshot/`
- Integrity record: `manifest.json`

The downloaded snapshot is intentionally gitignored because it contains the
large pretrained weight file. The revision, selected files, sizes, and
SHA-256 hashes remain tracked in `manifest.json`.

This is the base pretrained encoder, not a TweetEval- or emotion-fine-tuned
checkpoint. EXP-015 initializes a new four-label classification head and uses
the same frozen downstream protocol as EXP-014 so the base encoder is the only
scientific-condition change.
