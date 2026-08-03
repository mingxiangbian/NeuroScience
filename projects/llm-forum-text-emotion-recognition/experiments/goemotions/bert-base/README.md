# GoEmotions BERT-base

This directory reproduces the paper-aligned `bert-base-cased` multi-label
baseline on the frozen `DATA-GOE-V1` train/dev split.

## Experiment Sequence

- `EXP-019` (Minor): offline model-integrity and synthetic MPS training smoke
  test. It reads no project dataset split.
- `EXP-020` (Major): three-seed train/dev fine-tuning under a frozen protocol.
  Test remains absent and inaccessible.

The implementation uses the paper's public configuration where specified:
28 independent sigmoid outputs, binary cross-entropy, maximum sequence length
50, batch size 16, learning rate `5e-5`, four epochs, 10% linear warmup,
dropout `0.1`, and a fixed global decision threshold of `0.3`.

This is a modern PyTorch/Transformers reproduction, not a bitwise rerun of the
original TensorFlow estimator stack.

## Verified Result

`EXP-020` completed on Apple MPS and was independently reconstructed from the
saved dev probabilities:

- Macro-F1: `0.489435 +/- 0.011063`
- Micro-F1: `0.586671 +/- 0.002928`
- Weighted-F1: `0.582821 +/- 0.002713`
- Subset accuracy: `0.440963 +/- 0.003963`
- Runtime: `13,048.7` seconds for three seeds
- Test: not acquired or accessed

See the append-only
[`REPORT.md`](runs/exp-020-bert-base-cased/REPORT.md), frozen
[`protocol`](protocols/exp-020-bert-base-cased.md), and
[`verification.json`](runs/exp-020-bert-base-cased/verification.json).

The paper reports BERT Macro-F1 `0.46` on test, while EXP-020 evaluates dev.
The two values are not a direct score comparison.

Final model binaries and the upstream base-model snapshot are local and
gitignored. Tracked predictions contain anonymous row numbers, label sets,
and probabilities only.
