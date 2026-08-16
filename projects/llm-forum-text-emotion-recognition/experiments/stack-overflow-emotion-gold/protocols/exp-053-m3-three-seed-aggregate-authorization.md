# EXP-053 M3 Three-Seed Validation Aggregate Authorization

Date: 2026-08-15
Tier / RQ: Major / RQ-S1
Stage: \`m3-three-seed-validation-aggregate\`

## Purpose

Freeze and independently verify the validation-only family summary for the
three completed EXP-053 M3 Classification LoRA seeds. This stage measures the
stability of the registered M3 configuration and its descriptive improvement
over the matched M2 frozen-Qwen linear head and the M1 encoder baseline. It
does not train, select, or evaluate a model.

## Authorization

The user's instruction to proceed to the next registered step authorizes only
this read-only aggregate. It does not authorize training, error analysis,
EXP-054 M4, TEST-READY, or test access.

## Authorized Inputs

Only these public machine-readable files may be read:

- EXP-053 seed 42 \`run.json\` and the successful
  \`verification-attempt-2.json\` (\`148/148\` passed). The earlier
  \`verification.json\` remains a preserved failed verifier attempt and is not
  valid aggregate evidence.
- EXP-053 seed 43 \`run.json\` and \`verification.json\` (\`143/143\` passed).
- EXP-053 seed 44 \`run.json\` and \`verification.json\` (\`148/148\` passed),
  plus \`CORRECTION.md\` documenting copied prose in immutable artifacts.
- Verified EXP-051 M1 and EXP-052 M2 three-seed \`aggregate.json\` and
  \`verification.json\`, only for descriptive seed-matched deltas.

Every source path, byte size, SHA-256 and expected verification count must be
frozen in the execution config and checked before statistics are produced.

The aggregate must not read checkpoints, adapters, cached features,
probabilities, row-level predictions, row-level labels, raw text, private
artifacts, or any test file.

## Frozen Method

- Seed order: \`42, 43, 44\`.
- Center: arithmetic mean.
- Dispersion: sample standard deviation with \`ddof=1\`.
- No pooled predictions and no concatenation across seeds.
- Report both pre-existing conditions without choosing between them:
  - fixed threshold \`0.5\`;
  - each seed's already frozen shared validation threshold.
- Primary metric: six-label Macro-F1.
- Additional metrics: macro precision/recall, Micro-F1, Weighted-F1, strict
  subset accuracy, Hamming loss, five-label Macro-F1 without \`surprise\`,
  empty prediction rows, and predicted label cardinality.
- Report per-label precision, recall, F1, support, and predicted support as the
  three source values, arithmetic mean, and sample standard deviation.
- Compute M3 minus M2 and M3 minus M1 deltas by matching seed and condition for
  Macro-F1, Micro-F1, Weighted-F1, subset accuracy, Hamming loss, and five-label
  Macro-F1. These are descriptive paired summaries for \`n=3\`; no p-value,
  confidence interval, or significance claim is authorized.
- Shared-threshold comparisons use each model's already frozen validation
  operating point. Fixed \`0.5\` is the calibration-independent companion.
- Aggregate M3 wall time and memory descriptively because all three M3 seeds
  use the same formal implementation and execution path. Cross-model resource
  comparison is not authorized: M1 uses a different runtime and M2 mixes full
  extraction with cache-only runs.

## Sealed Work

- Stack Overflow test remains sealed, unrequested, and unread.
- No TEST-READY status is created.
- EXP-054 M4, error analysis, context, routing, and new model runs remain
  unauthorized.
- Source runs, verifications, and correction notes are append-only and cannot
  be modified or replaced by this aggregate.

## Required Outputs

- \`aggregate.json\`
- \`REPORT.md\`
- frozen config, protocol, runner, verifier, and tests
- independent \`verification.json\`
- \`VERIFICATION-SUMMARY.md\`

The stage passes only if all source identities and hashes match, the successful
verification for each seed remains passed, the independent implementation
exactly reproduces all summaries and paired deltas, public artifacts contain no
row-level or private paths, and test access remains false.

## Decision Boundary

After verification, EXP-053 M3 validation is complete at family level. The
result may support a stability claim limited to these three seeds and this
frozen validation protocol. It cannot establish test performance, internal
emotion mechanisms, M4 performance, or statistical significance. The next
possible action must be chosen separately between validation error analysis,
EXP-054, and a unified TEST-READY gate.
