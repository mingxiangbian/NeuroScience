# EXP-054 Formal Execution Authorization

- Experiment: `EXP-054`
- RQ: `RQ-S1`
- Tier: Major
- Authorized: 2026-08-15
- Basis: user message `行，执行EXP-054`

## Authorized Scope

- Train and validation only.
- Seeds `42`, `43`, and `44` under the already registered M4 contract.
- Two epochs and `6,720` optimizer updates per seed.
- Validation generation after each epoch for checkpoint selection.
- Two fresh-process greedy replays on the frozen 60-row validation subset after selection.
- Per-seed independent verification and a three-seed aggregate.

Test, context recovery, routing, new prompts, retries, parser repair, alternative LoRA settings, and
post-result hyperparameter changes are not authorized by this record.

## Frozen Selection And Comparison

The selected checkpoint maximizes strict-parser six-label validation Macro-F1. If an epoch is less
than `0.005` below the maximum, it is practically tied; choose the earlier epoch. Invalid generations
remain in the denominator as all-zero predictions.

Each seed is paired with the same-seed frozen EXP-053 M3 shared-threshold predictions. The paired
duplicate-component bootstrap estimates `M4 - M3`. Because M3 and M4 jointly differ in head, loss,
supervision tokens, and decoding, the result supports only an end-to-end formulation comparison.

## Stop Conditions

Stop before starting another seed if any of these occurs:

- training exceeds 8 hours for the current seed;
- formal validation inference exceeds 12 hours for the current seed;
- peak MLX memory exceeds 13 GB;
- parser, prompt, target serialization, LoRA insertion set, assistant-only mask, or split boundary
  differs from the frozen contract;
- an output directory already exists;
- the prior seed does not pass independent verification.

The total EXP-054 family budget is 60 hours and API cost is fixed at USD 0.
