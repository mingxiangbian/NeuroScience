# Weibo EClass Experiments

This track owns model experiments on the frozen `DATA-WEIBO-TASK-V1` dataset.
Row-level data, prompts containing source text, model outputs, adapters and test
labels remain private and Git ignored.

## Current Gate

Stages 2 and 3 have passed. Under train-only `EXP-041`, the classical pipeline, Chinese
RoBERTa optimizer path, Qwen3-4B thinking on/off prompt-parser path and exact
16-block LoRA insertion/checkpoint reload all completed. Independent amendment
`AUDIT-EXP-041-V1` passed 16 checks with zero mismatch.

The failure chain remains part of the record:

- `EXP-039` failed the static JSON-target rendering check before model download
  or training.
- `EXP-040` passed the earlier stages but failed Qwen strict parseability at
  28/42 because 14 thinking outputs hit the 384-token cap; LoRA did not start.
- The frozen EXP-041 verifier stopped on a self-matching source-string guard.
  The registered AST-based audit amendment corrected only that independent
  check and verified the existing artifacts without rerunning models.

EXP-041 Qwen strict parseability was 37/42; this is not classification accuracy.
No validation or test row was accessed and no performance metric was computed
in that preflight.

`EXP-042` then completed the Stage 3 train/dev Major comparison. Validation
Macro-F1 was `0.116913` for M0, `0.338267`/`0.271504` for M1 target/context,
and `0.594925 +/- 0.012919`/`0.594219 +/- 0.012046` for M2 target/context. The
paired M2 context delta was `-0.000706 +/- 0.024737`; this is a practical tie,
so target only is frozen as the simpler selected view. Independent verification
passed 8 checks with zero mismatch.

`EXP-043` then completed the Stage 4 frozen-Qwen context x reasoning 2x2. The
frozen Macro-F1 rule selected target-only with reasoning on at `0.333818`, but
reasoning did not improve Accuracy or Weighted-F1 over target-only reasoning off,
reduced parser validity to `0.918239` and increased generation cost sharply.
The observed average context contrast was `-0.021512` with a paired 95% interval below zero;
selected Qwen remained `-0.261107` Macro-F1 below EXP-042 M2 target-only.
Independent verification passed 10 checks with zero mismatches.

Reasoning-on first-clause prompts matched exactly across the paired views, but
only 273/332 final labels matched between the two batched runs. Stage 5 must
therefore freeze and verify evaluation batch semantics before model comparison.

`EXP-044` then completed a train-only 200-step Stage 5 local-cost preflight.
Qwen3-4B BF16 LoRA ran in `355.254` seconds at a steady median `0.575 step/s`;
peak memory was `8.679 GB`. All 112 insertion points, 224 adapter tensors and
7,340,032 trainable parameters matched, checkpoint reload passed, and the
independent verifier passed 13/13 checks. With a 1.25 safety factor, two epochs
across three sequential seeds project to `21.72 h`; three epochs project to
`32.58 h`, excluding validation generation and analysis.

`EXP-045` then stopped during train-only initialization before any model inference:
Transformers 5.14.1 returned a `BatchEncoding`, and the first implementation treated
its two field names as token IDs. The failed run is preserved. Corrected `EXP-046`
explicitly enforced integer token IDs and completed 80 train-only generations.
Singleton and fixed-order batch-8 fresh-process replay were each `16/16` identical,
but changing batch composition reduced final-label agreement to `14/16` and raw-output
agreement to `5/16`. The pre-registered rule therefore freezes singleton reasoning-on
inference for Stage 5. Independent verification passed 12/12 checks; validation/test
remained closed and no classification performance was computed.

`EXP-047` has completed the Stage 5 generative-LoRA Major through matched validation.
The three two-epoch seed runs, adapter load-forward checks and two-pass train-only
singleton replays were independently verified before validation access. The matched
no-adapter reference reached Macro-F1 `0.333598`; LoRA seeds 42/43/44 reached
`0.552028`/`0.548289`/`0.587096`, for `0.562471 +/- 0.021408` and a frozen mean
delta of `+0.228873`. All three LoRA conditions were parser-valid on 1,272/1,272
rows, while the reference valid rate was `90.8805%`.

Independent verification reconstructed all 5,088 validation generations, metrics,
group-level bootstrap comparisons, resources and privacy boundaries with zero
mismatch. The LoRA mean remains `0.032454` below the EXP-042 M2 target-only encoder
mean, so the result supports effective task adaptation but not encoder superiority.
`EXP-048` then completed the frozen dev error analysis without new model runs. It
independently recomputed seven prediction files over all 1,272 validation rows and
reviewed 48 cases selected under a protocol frozen before raw-text access. Of the
LoRA-reference Accuracy gain, `+0.070755` came from the 116 reference output-failure
rows and `+0.486111` from the 1,156 rows whose reference output was already valid.
The gain therefore cannot be reduced to parser repair. Against the encoder, LoRA
remained `-0.032454` Macro-F1 and `-0.013103` Accuracy, with the largest F1 gaps on
sadness, neutral, anger and positive. Its mean pairwise seed agreement was also lower
(`0.884` versus `0.943`). The qualitative sample most often implicated annotation/data
uncertainty, overlapping label ontology, implicit emotion and the no_emotion boundary;
because it was purposively sampled, those counts are not prevalence estimates.

Independent verification reproduced nine CSVs and three JSON summaries with zero
numeric difference, checked all 48 annotations and confirmed that the raw review file
is private and gitignored. The held-out test remains sealed. The next dependency is a
frozen TEST-READY candidate list and explicit one-time test authorization, not further
validation tuning.
