# EXP-046: Stage 5 Batch-Equivalence Gate V2

Status: `Verified` (Minor; train only)

## Purpose

EXP-043 found that 273/332 reasoning-on first-clause samples retained the same final label when
identical prompts were generated in different co-batches. EXP-046 separates three possible sources:

1. fresh-process replay instability within one execution mode;
2. singleton versus batch-8 execution;
3. changed co-batch composition under batch 8.

This experiment computes no classification performance, reads train only, and does not train a model.

EXP-045 was stopped before inference because Transformers 5.14.1 returned a `BatchEncoding` during
initialization. EXP-046 explicitly requests `return_dict=False` and rejects any chat-template result
that is not a non-empty integer token sequence.

## Frozen Design

- Select 16 train rows proportionally by label, then by prompt-length quantiles within each label.
- Run `singleton-r1/r2` in two fresh processes.
- Run `batch8-r1/r2` in two fresh processes with the frozen native order.
- Run `batch8-length-stress` on the same rows ordered by prompt length to change co-batch membership.
- Use the same Qwen3-4B BF16 model, target-only prompt, reasoning on, greedy decoding,
  `max_new_tokens=1024`, and strict parser in every mode.
- Compare raw output, parser state, and final label. Gold labels are used only for train sampling.

## Pre-registered Decision

1. If batch-8 replay and batch-composition final-label agreement are both 100%, freeze batch 8.
2. Otherwise, if singleton fresh-process replay is 100%, freeze singleton.
3. Otherwise, block reasoning-on as the Stage 5 primary protocol and register a reasoning-off replay gate.

Even if batch 8 passes, formal validation must freeze row order and all batch settings. Every trained
LoRA adapter must repeat this train-only replay before any dev access.

## Result

- Singleton fresh-process replay: final label, parser state, and raw output were all `16/16` identical.
- Fixed-order batch-8 replay: all three surfaces were also `16/16` identical.
- Changed batch composition: final labels and parser states were `14/16` identical; raw outputs were
  only `5/16` identical.
- Singleton versus fixed batch 8: final labels were `15/16` identical and raw outputs were `0/16`
  identical.
- The frozen rule therefore selected `singleton` for Stage 5 reasoning-on evaluation.
- All 80 generations used train only. Total recorded wall time was `2432.088 s`; peak memory was
  `9.532 GB`. No performance metric was computed and validation/test remained closed.
- The independent verifier passed `12/12` checks without importing the runner.
