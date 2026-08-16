# EXP-055 Verification Summary

- Status: `Passed`
- Formal verifier: attempt 2
- Checks: `220/220`
- Failed checks: `0`
- Split: validation only
- Test accessed: `false`
- New training or inference: `false`

## Attempt Provenance

A disposable attempt-1 preflight passed 208 of 209 checks. Its only failure was a
literal `access test` match across a Markdown line break. No tracked formal
verification was written. The frozen attempt-2 amendment authorized whitespace
normalization for report boundary checks only; all scientific artifacts remained
unchanged. Attempt 2 then independently reran every source, metric, transition,
slice, oracle, bootstrap, sample, annotation, privacy, and artifact check.

## Verified Findings

- M1 six-label Macro-F1: `0.617254 +/- 0.011084`.
- M3 six-label Macro-F1: `0.654032 +/- 0.014135`.
- M1 five-label Macro-F1 without surprise: `0.740705 +/- 0.013301`.
- M3 five-label Macro-F1 without surprise: `0.706724 +/- 0.013816`.
- M1 surprise F1 was `0` for all three seeds; M3 surprise F1 was
  `0.363636 / 0.444444 / 0.363636`.
- M1-only exact-correct rows averaged `56.00`; M3-only exact-correct rows averaged
  `48.67` across matched seeds.
- The non-deployable whole-vector oracle selected M3 on
  `8.333% +/- 0.773%` of rows. Its delta over M1 was
  `0.136394 +/- 0.009058` six-label Macro-F1 and
  `0.074784 +/- 0.010869` five-label Macro-F1.
- The preregistered router-headroom gate passed all five checks.

## Qualitative Boundary

The deterministic review contained 45 unique cases. The most frequent coded primary
possible sources were overlapping label ontology (`19`), model or representation
limitation (`13`), and annotation or data uncertainty (`9`). These are single-reviewer
hypotheses for a purposefully selected error sample. They are not corrected ground
truth, dataset-wide prevalence estimates, causal explanations, model reasoning, or
inter-rater evidence.

## Decision Boundary

The higher M3 six-label Macro-F1 is not a general superiority result: M1 remains
higher on micro-F1, weighted-F1, subset accuracy, hamming loss, and five-label
Macro-F1 without surprise. The oracle result demonstrates complementarity under gold
access, not a deployable router. It authorizes only a separately registered
train-OOF router feasibility experiment using pre-Qwen features. EXP-054 and test
remain unauthorized by EXP-055.
