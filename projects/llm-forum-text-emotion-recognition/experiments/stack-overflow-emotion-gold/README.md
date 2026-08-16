# Stack Overflow Emotion Gold Experiment Track

This module contains the frozen C0 multi-label data pipeline and the M1-M4
model-comparison protocols. The data track is defined by
[`DATA-SO-TASK-V1`](protocols/data-so-task-v1.md); model performance experiments
remain separate Major runs.

## Commands

Run from `projects/llm-forum-text-emotion-recognition/` with the bundled
workspace Python runtime, which provides `openpyxl`:

```bash
WORKSPACE_PYTHON=/Users/phoenix/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"$WORKSPACE_PYTHON" experiments/stack-overflow-emotion-gold/prepare_data_so_task_v1.py
"$WORKSPACE_PYTHON" experiments/stack-overflow-emotion-gold/verify_data_so_task_v1.py
"$WORKSPACE_PYTHON" -m unittest discover \
  -s experiments/stack-overflow-emotion-gold/tests \
  -p 'test_*.py'
```

Run the verified train-only model preflight with the project-specific runtimes:

```bash
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py --stage static
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py --stage m1
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py --stage m2
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py --stage m3
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py --stage m4
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/verify_preflight.py
```

Replay any completed EXP-051 independent verifier offline:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/verify_exp051_m1.py \
  --config experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-051-m1-roberta-seed-42-cpu-recovery.json \
  --seed 42

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/verify_exp051_m1.py \
  --config experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-051-m1-roberta-seed-43-cpu.json \
  --seed 43

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/verify_exp051_m1.py \
  --config experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-051-m1-roberta-seed-44-cpu.json \
  --seed 44

/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  experiments/stack-overflow-emotion-gold/model-comparison/verify_exp051_aggregate.py
```

Private row-level artifacts are written to
`data/stack-overflow-emotion-gold/derived-private/task-v1/` and ignored by
Git. Public outputs contain no forum text or row-level labels:

- `data/stack-overflow-emotion-gold/task-v1.manifest.json`
- `data/stack-overflow-emotion-gold/task-v1.split-index.jsonl`
- `reports/data-so-task-v1.json`
- `reports/data-so-task-v1-verification.json`

## Status

`Verified` on 2026-08-13. The builder reconstructed all 4,800 rows, froze a
3,360/720/720 duplicate-component-disjoint split and sealed the test labels.
The independent verifier passed 53/53 checks, and the synthetic unit-test suite
passed 11/11 tests.

The M1-M4 protocols are registered as EXP-051 through EXP-054. Their shared
train-only preflight, EXP-050, is also `Verified`: all five execution stages
passed, the independent verifier passed 77/77 checks, and the model-preflight
unit tests passed 7/7. The preflight computed no performance metric and accessed
neither validation nor test.

EXP-051 seed 42 passed its train + validation integrity gate. The first
MPS attempt stopped before a complete validation epoch because of unified-memory
exhaustion; a frozen 10-step CPU recovery preflight passed, then the unchanged
scientific condition completed in 30.99 minutes with peak process RSS 6.42 GB.
Epoch 4 was selected. Fixed-0.5 validation Macro-F1 was 0.598759; the frozen
shared-threshold rule selected 0.25 and produced Macro-F1 0.604619, Micro-F1
0.764645 and strict subset accuracy 0.740278. The independent verifier passed
67/67 checks.

Seed 43 then completed the unchanged scientific condition on CPU in 32.22
minutes with peak process RSS 5.24 GB. Epoch 4 was selected. Fixed-0.5 Macro-F1
was 0.601329; shared threshold 0.30 produced Macro-F1 0.625341, Micro-F1
0.774869 and strict subset accuracy 0.758333. The independent verifier passed
72/72 checks with exact checkpoint replay.

Seed 44 completed the same condition in 30.94 minutes with peak process RSS
5.36 GB. Epoch 5 was selected; the shared threshold remained 0.50, so fixed and
shared Macro-F1 were both 0.621803. Its independent verifier passed 72/72 checks
with exact checkpoint replay. The registered three-seed validation aggregate is
now frozen and independently verified 53/53: fixed-0.5 Macro-F1 is
0.607297 +/- 0.012628, while per-seed shared-threshold Macro-F1 is
0.617254 +/- 0.011084. Shared thresholds improve descriptive Macro-F1 but reduce
strict subset accuracy from 0.773611 to 0.760648. `surprise` F1 is 0 for all
three seeds.

EXP-052 seed 42 then passed its frozen-Qwen linear-head train + validation
integrity gate. The verified dry-run projected 65.24 minutes with safety; the
formal run completed in 40.00 minutes with peak MLX memory 8.23 GB. Epoch 2 was
selected. Fixed-0.5 Macro-F1 was 0.183391; shared threshold 0.25 produced
Macro-F1 0.324929, Micro-F1 0.509700 and strict subset accuracy 0.477778. The
component-bootstrap 95% interval for shared-threshold Macro-F1 was
[0.282747, 0.370449]. `surprise` F1 remained 0, and five-label Macro-F1 without
`surprise` was 0.389915. The independent verifier passed 70/70 checks with
exact selected-head replay.

The seed-42 train/validation feature cache is now frozen behind a separate
read-only reuse gate. The gate independently passed 74/74 checks over source
run/verification hashes, cache hashes, shapes, dtype, finite values, sample
order, token stream, privacy and split access. It performed no training, Qwen
forward pass or performance evaluation. Only separately authorized EXP-052
seeds 43/44 may consume it; EXP-053/054 reuse is forbidden.

EXP-052 seed 43 then consumed the verified cache through a fresh cached-head
runner. The first preflight stopped before training because it expected a
nested artifact record where the gate stores a flat record; it produced no
checkpoint, metric or test access. The corrected preflight passed 73/73 checks.
The formal run initialized a fresh seed-43 `Linear(2560,6)` head, completed two
epochs and 6,720 optimizer steps in 4.23 seconds, and left both cache hashes
unchanged. It loaded or executed no Qwen model. Fixed-0.5 Macro-F1 was 0.133610;
shared threshold 0.20 produced Macro-F1 0.353593, Micro-F1 0.537969 and strict
subset accuracy 0.470833. Its component-bootstrap 95% interval was
[0.315104, 0.392166], and five-label Macro-F1 without `surprise` was 0.424311.
The independent verifier passed 99/99 checks. Fixed and calibrated scores rank
seeds 42/43 differently, so seed/calibration sensitivity remained explicit and
no M2 family conclusion was formed at that stage. EXP-053/054 and test remained
sealed.

EXP-052 seed 44 then passed a separately authorized cached-head consumer
preflight with 78/78 checks. The formal run initialized a fresh seed-44
`Linear(2560,6)` head, completed two epochs and 6,720 optimizer steps in 4.79
seconds, and left both cache hashes unchanged. Qwen load, forward and feature
extraction time were all zero. Fixed-0.5 Macro-F1 was 0.137657; shared threshold
0.25 produced Macro-F1 0.278145, Micro-F1 0.494538, strict subset accuracy
0.523611 and a component-bootstrap 95% interval of [0.240756, 0.314903]. The
five-label Macro-F1 without `surprise` was 0.333774; `joy` and `surprise` both
had F1 0. The independent verifier passed 104/104 checks and the complete
EXP-052 regression suite passed 28/28. Shared-threshold Macro-F1 was lower than
seeds 42/43 by 0.046783/0.075447 and lower than matched M1 seed 44 by 0.343658.
All three individual M2 seeds then entered the separately registered read-only
validation aggregate. Its independent verifier passed 85/85 checks and the
complete EXP-052 regression suite passed 36/36. Fixed-0.5 Macro-F1 was
0.151553 +/- 0.027647. Per-seed shared-threshold Macro-F1, Micro-F1 and strict
subset accuracy were 0.318889 +/- 0.038085, 0.514069 +/- 0.022042 and
0.490741 +/- 0.028678. Calibration improved Macro-F1 by 0.167336 but reduced
strict subset accuracy by 0.069444 and increased hamming loss by 0.033873.

Against matched M1 seeds, the shared-threshold Macro-F1 paired delta was
-0.298365 +/- 0.039425 and all three deltas were negative. `surprise` F1 was 0
for all seeds, while `joy` F1 was 0.206770 +/- 0.187595. The aggregate did not
concatenate row-level predictions, run inferential statistics at n=3, or average
heterogeneous resource records: seed 42 includes full Qwen feature extraction,
whereas seeds 43/44 are cache-only. This completes the EXP-052 validation
family only for frozen final-layer last-input-token pooling plus
`Linear(2560,6)`; it does not establish that Qwen lacks emotion information or
that other readouts or LoRA will fail. EXP-054 and test remain sealed.

The EXP-053 M3 train-only resource gate is now independently verified. The
runner tokenized all 3,360 train rows, selected 32 private length-aware rows,
completed 32 finite-loss updates, changed all 112 `lora_b` tensors, preserved
the frozen-base sentinel, and replayed the private adapter/head checkpoint with
zero logit difference. The first attempt retained training references while
loading a second Qwen instance for replay and therefore failed the process-wide
13 GB gate; that failed attempt remains append-only. The attempt-2 amendment
changed only sequential-phase cleanup and accounting. Training/replay peaks were
8.674/8.376 GB, and the 1.5x projection was 4.436 hours per seed and 13.308 hours
for three sequential seeds. The dedicated tests passed 12/12 and the independent
verifier passed 102/102. This is resource-feasibility evidence only.

Formal EXP-053 seed 42 then completed two epochs and 6,720 optimizer steps under
the separately frozen train+validation authorization. Epoch 2 was selected.
Fixed-0.5 Macro-F1 was 0.602846; shared threshold 0.40 produced Macro-F1
0.637786, Micro-F1 0.758315, strict subset accuracy 0.755556 and hamming loss
0.050463. The 2,000-replicate duplicate-component bootstrap interval for shared
Macro-F1 was [0.548975, 0.709997]. Against matched M2 seed 42, the paired shared
Macro-F1 delta was +0.312857 with interval [+0.223280, +0.388544]. This supports
LoRA task-adaptation gain under the matched classification interface, not an
internal emotion mechanism or a three-seed M3 result. The run took 3.821 hours,
peaked at 8.702 GB MLX memory and used no API.

The first independent verifier replayed all 720 rows with zero probability
error but retained Failed status at 135/136 because it read an obsolete field in
the resource-verification record. A schema-only amendment preserved that output
and repeated the full replay; attempt 2 passed 148/148 with zero probability
error. Test was not accessed. At that gate, seeds 43/44 and EXP-054 remained
sealed.

Formal EXP-053 seed 43 then completed the same two epochs and 6,720 optimizer
steps under a second independent authorization. Epoch 2 was selected. Fixed-0.5
Macro-F1 was 0.659318; shared threshold 0.35 produced Macro-F1 0.663515,
Micro-F1 0.756696, strict subset accuracy 0.754167 and hamming loss 0.050463.
The shared Macro-F1 component-bootstrap interval was [0.570351, 0.732537].
Against matched M2 seed 43, the paired shared Macro-F1 delta was +0.309922 with
interval [+0.208105, +0.390880]. The run took 3.544 hours, peaked at 8.699 GB MLX
memory and used no API. The independent verifier replayed the selected
checkpoint with zero probability error and passed 143/143 checks. Test was not
accessed. At that gate, the two-seed shared Macro-F1 descriptive mean was
0.650650 +/- 0.018194; this was not the preregistered three-seed M3 family
result.

Formal EXP-053 seed 44 then completed the same two epochs and 6,720 optimizer
steps under a third independent authorization. Epoch 2 was selected. Fixed-0.5
Macro-F1 was 0.598812; shared threshold 0.25 produced Macro-F1 0.660795,
Micro-F1 0.763713, strict subset accuracy 0.741667 and hamming loss 0.051852.
The shared Macro-F1 component-bootstrap interval was [0.584731, 0.727760].
Against matched M2 seed 44, the paired shared Macro-F1 delta was +0.382650 with
interval [+0.298126, +0.455866]. The run took 3.352 hours, peaked at 8.702 GB MLX
memory and used no API. The independent verifier replayed the selected
checkpoint with zero probability error and passed 148/148 checks. Test was not
accessed. All three individual M3 seeds were then entered into the separately
authorized read-only aggregate. It passed 124/124 independent checks without
reading or pooling row-level predictions. Fixed/shared-threshold Macro-F1 was
0.620325 +/- 0.033829 / 0.654032 +/- 0.014135. The shared-threshold M3-M2
Macro-F1 delta was +0.335143 +/- 0.041168 and all three seed deltas were
positive.

The shared-threshold M3-M1 Macro-F1 delta was +0.036778 +/- 0.003154, but the
five-label delta without `surprise` was -0.033981 +/- 0.008620; Micro-F1 and
Weighted-F1 deltas were also negative. The apparent six-label Macro-F1
advantage is therefore driven by `surprise`, which has only seven validation
positives and was never predicted correctly by M1. This does not support a
broad claim that M3 outperforms the encoder. EXP-053 validation is complete.

EXP-055 then compared the six frozen M1/M3 validation prediction sets without
training or model inference. M1 remained stronger on five-label Macro-F1,
Micro-F1, Weighted-F1, subset accuracy and hamming loss. Across seeds, M1-only
exact-correct rows were 42/53/73 and M3-only rows were 53/50/43. The non-deployable
whole-vector oracle selected M3 on only 65/61/54 rows but improved six-label
Macro-F1 over M1 by 0.136394 +/- 0.009058; all preregistered router-headroom checks
passed. A single reviewer coded 45 purposefully sampled cases, most often marking
ontology overlap, the weak-emotion/neutral boundary, implicit emotion and
model/representation limitations. Those frequencies describe the selected sample,
not validation prevalence or model reasoning. The whitespace-only verifier
amendment passed 220/220 checks. This permits a separately registered train-OOF
router feasibility study only; it does not establish a deployable router. EXP-054
and test remain sealed.

See
[`model-comparison/runs/exp-050-shared-model-preflight/REPORT.md`](model-comparison/runs/exp-050-shared-model-preflight/REPORT.md)
for the shared gate, and
[`model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/VERIFICATION-SUMMARY.md)
for the seed-42 result and preserved MPS incident, and
[`model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/VERIFICATION-SUMMARY.md)
for the seed-43 result,
[`model-comparison/runs/exp-051-m1-roberta-cpu/seed-44/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-051-m1-roberta-cpu/seed-44/VERIFICATION-SUMMARY.md)
for the seed-44 result, and
[`model-comparison/runs/exp-051-m1-roberta-three-seed-validation/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-051-m1-roberta-three-seed-validation/VERIFICATION-SUMMARY.md)
for the frozen three-seed M1 validation result and evidence boundary, and
[`model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/VERIFICATION-SUMMARY.md)
for the verified EXP-052 seed-42 integrity result, and
[`model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/VERIFICATION-SUMMARY.md)
for the verified read-only cache-reuse boundary, and
[`model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/VERIFICATION-SUMMARY.md)
for the verified seed-43 cached-head result, and
[`model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/VERIFICATION-SUMMARY.md)
for the verified seed-44 cached-head result and aggregate boundary, and
[`model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/VERIFICATION-SUMMARY.md)
for the verified M2 three-seed validation aggregate and claim boundary, and
[`model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/VERIFICATION-SUMMARY.md)
for the verified EXP-053 train-only resource, checkpoint and split boundary, and
[`model-comparison/runs/exp-053-m3-classification-lora/seed-42/VERIFICATION-SUMMARY-ATTEMPT-2.md`](model-comparison/runs/exp-053-m3-classification-lora/seed-42/VERIFICATION-SUMMARY-ATTEMPT-2.md)
for the verified formal seed-42 validation result, M3-M2 delta and preserved verifier correction, and
[`model-comparison/runs/exp-053-m3-classification-lora/seed-43/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-053-m3-classification-lora/seed-43/VERIFICATION-SUMMARY.md)
for the verified formal seed-43 validation result, M3-M2 delta and two-seed evidence boundary, and
[`model-comparison/runs/exp-053-m3-classification-lora/seed-44/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-053-m3-classification-lora/seed-44/VERIFICATION-SUMMARY.md)
for the verified formal seed-44 validation result and M3-M2 delta, and
[`model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/VERIFICATION-SUMMARY.md`](model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/VERIFICATION-SUMMARY.md)
for the verified M3 family aggregate, M1/M2 comparison and claim boundary, and
[`error-analysis/runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md`](error-analysis/runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md)
for the verified M1/M3 error complementarity, qualitative coding boundary and
router-headroom decision.
