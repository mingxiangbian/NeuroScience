# BERT Base Cased Model

This directory records the immutable upstream model used to initialize the
GoEmotions multi-label encoder baseline.

- Upstream repository: `google-bert/bert-base-cased`
- Frozen revision: `cd5ef92a9fb2f889e972770a36d4ed042daf221e`
- Local snapshot: `snapshot/`
- Integrity record: `manifest.json`

The downloaded snapshot is intentionally gitignored because it contains a
roughly 436 MB model binary. The revision, selected files, sizes, and SHA-256
hashes remain tracked in `manifest.json`.

The snapshot contains the pretrained encoder only. A randomly initialized
28-label classification head is added by the experiment code; this directory
does not contain a fine-tuned GoEmotions checkpoint.
