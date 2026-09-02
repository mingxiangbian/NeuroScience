# Stack Overflow Emotion Gold Experiment Track

This module contains the frozen C0 multi-label data pipeline and the M1-M4
model-comparison protocols. The data track is defined by
[`DATA-SO-TASK-V1`](protocols/data-so-task-v1.md); model performance experiments
remain separate Major runs.

Current execution handoff: [`HANDOFF.md`](HANDOFF.md).

Latest update (2026-08-30): EXP-075 completed all 75 geometry comparisons and passed
20/20 independent checks under the user-approved post-diagnostic rule. H-1 CKA and
the fixed nine-point Spearman remain undefined; original EXP-071 remains Failed.
EXP-072 completed all 70 inference workers, sealed scoring and 20/20 independent checks;
all 15 A0 replays had zero error. EXP-074 synthesis and independent verification passed.
The Phase B minimum experimental set is complete: representation effect replicated, with
Attention-dominant dependency in the preregistered confirmation seeds 43/44. Seed 42 showed
the opposite Attention/MLP direction and remains an explicit counterexample. EXP-073 is optional
and unexecuted; context/C2 remains paused. The research report is local and Git ignored at
[`phase-b-research-report-2026-08-30.md`](phase-b-representation/private/reports/phase-b-research-report-2026-08-30.md).

Current phase: the Phase A lifecycle is `Closed`, with closeout outcome
`Closed with partial success`; the frozen EXP-068 decision remains `Failed or incomplete`. The
verified seed-42 headless/CLI stack remains a local research demo. The formal efficiency benchmark
did not complete, so no deployment-efficiency claim is supported. Phase B representation and
functional-dependency work is registered under `RQ-S4`. EXP-069 is Complete: static verification
passed 14/14, base attempt 3 passed 23/23, and all 15 fold workers completed with zero recorded
model-side parity error. Attempt-4 final verification remains append-only Failed because its verifier
merged two differently defined manual-logit aggregates. Model-free verification attempt 2 separated
them and passed 25/25: runner manual-vs-standard remained `0.0`, while independent NumPy head
replay was `7.62939453125e-06`, below the unchanged `1e-5` gate. No model was rerun and no source
snapshot was modified. EXP-070 then froze the full extraction, nested component-disjoint probe,
label-shuffle and bootstrap contracts. Its synthetic tests passed 15/15 and its model-free no-result
preflight verifier passed 24/24. The 32-row EXP-069 smoke remains a parity fixture and cannot train
the probes. EXP-070 probe fitting sealed all five folds, and assemble produced a private
`probe-manifest.json` plus public `probe.json`; both remain `CompletedAwaitingVerification`. The
extraction-only formal consumer has a
frozen protocol, config, runner and independent verifier; its synthetic tests passed 11/11. Formal
attempt 1 completed worker extraction at 16/16 and frozen assemble. The append-only source run keeps
its `CompletedAwaitingVerification` status. Frozen base completed
3,360 rows x nine points in 2,032.24 seconds, with zero M2-HF and standard-HF error and an 8.24 GB
MLX peak. M3 seed 42 / fold 0 then
completed the same shape in 3,289.41 seconds with zero runner and pre-LoRA parity errors and an 8.60
GB peak. Its model-free float64 head replay was `2.086469194750862e-06`, below the unchanged `1e-5`
gate. Fold 1 completed in 2,085.12 seconds with the same zero runner/pre-LoRA errors and 8.60 GB
peak; its float64 replay was `1.5347208552896063e-06`. Fold 2 completed in 2,093.59 seconds; its
corresponding values were zero and `1.5044781136452912e-06`. Fold 3 completed in 2,578.34 seconds
with zero runner/pre-LoRA errors; its float64 replay was `1.7814840784780017e-06`. Fold 4 completed
in 2,151.06 seconds with zero runner/pre-LoRA errors; its float64 replay was
`2.0908623792337266e-06`. Seed 42 is complete at 5/5 folds. A pre-run audit found two defects in the
original terminal verifier: an equality check across
incompatible token-digest encodings and a float32 cross-backend replay at the tolerance edge. A new
append-only verification-attempt-2 consumer fixes only those verifier rules and passed 12/12 tests.
Seed 43 / fold 0 completed its three-point cache in
2,124.92 seconds; persisted H19 and transient parity records were zero, while its float64 replay was
`1.912518955649034e-06`. Fold 1 completed in 2,380.40 seconds with the same zero parity values and a
float64 replay of `2.409579250794991e-06`. Fold 2 completed in 2,229.21 seconds; persisted/transient
parity stayed zero and float64 replay was `2.3480084774263332e-06`. Fold 3 completed in 1,943.42
seconds with zero parity values and a float64 replay of `2.0202858195261797e-06`. Fold 4 completed
in 2,258.69 seconds with zero parity values and a float64
replay of `1.7818263131630374e-06`. Seed 43 is complete at 5/5 folds. Seed 44 folds 0–4 completed in
2,305.14, 2,300.78, 2,048.08, 2,099.80 and 2,035.08 seconds. All five saved 3,360 rows x three
points with zero persisted H19, transient pre-LoRA and runner replay error; their maximum float64
replay was
`2.3313519861289933e-06 < 1e-5`. The maximum float32 diagnostic was
`1.239776611328125e-05` and does not gate the frozen recovery verifier. Seed 44 is complete at 5/5,
so all 16/16 workers are sealed. Frozen assemble bound the 16 matrices in a 10,612-byte private
manifest (`sha256=ef8092d...51d347`) and a 1,596-byte public `extraction.json`
(`sha256=1ad33d...93cfe`). Verification attempt 2 then passed 28/28 checks. Runner MLX replay stayed
at `0.0`; the maximum float32 diagnostic was `1.239776611328125e-05`; the maximum float64 gate was
`2.409579250794991e-06 < 1e-5`. The source snapshot stayed unchanged, and the completion marks
formal extraction Complete without authorizing probe fitting or EXP-071. The separate probe consumer
now has a frozen protocol, runner, probability-only verifier and formal config. Its 34 synthetic tests
passed, and the no-result static verifier passed 25/25 checks without reading label or representation
values. Static completion authorized only the frozen formal config. Formal initialize then sealed
`run-claim.json` and a private input manifest with an empty fold prefix; it read no label or
representation values. Fold 0 sealed 864 binary fits in 2,119.20 seconds with a 1.507 GB peak RSS.
Fold 1 sealed another 864 binary fits in 2,096.91 seconds with a 1.554 GB peak RSS. Both folds
were followed by folds 2–4, which sealed 864 fits each in 2,121.81, 2,139.69 and 2,127.09 seconds;
their peak RSS values were 1.475, 1.551 and 1.550 GB. All five folds decoded only their outer-train
labels. Assemble then read the train-only outer-heldout labels and computed the registered aggregate
metrics, controls, 2,000 bootstrap intervals and provisional seed votes. Seeds 43/44 passed H27/HF,
and no shuffle seed triggered the negative-control failure.
The frozen verifier CLI did not run because it mistakes the exact-bound method phrase
`component-disjoint` for a sensitive component ID. The run remains `CompletedAwaitingVerification`
under the original verifier. The append-only recovery consumer passed 12 synthetic tests, 18
no-result static checks and 44 formal verification checks. It reproduced the assemble result digest,
verified negative-control failure=False and state 2 `Representation effect replicated`, and left the
source snapshot unchanged. Recovery verification read only the sealed probabilities and train-only
labels needed to recompute thresholds, metrics and bootstrap; it did not read representations, refit
the probe, load a model, run forward, or access validation/test. Lifecycle completion remains
separate from the source run: recovery `formal-complete` replayed the exact Passed verification and
wrote terminal completion. EXP-070 is Complete via verification attempt 2 with verified state 2.
EXP-071 is registered and its no-result preflight is Complete via Incident 001 attempt 2: synthetic
tests passed 53/53 and the independent static verifier passed 24/24 without reading representation,
row-contract values or probe metrics. Formal initialize then wrote one public `run-claim.json` and
one private `input-manifest.json`, without reading scientific values. Formal analyze stopped on the
registered `Zero or non-finite CKA denominator` gate. It read `ordinal/fold_id` and
some representation values, but stopped before AP5 access or geometry publication. The failed prefix
contains only the run claim, failure record and private input manifest; source identity remains
unchanged. Formal verification must not run. The conclusion remains limited to train-only
outer-heldout linear label accessibility under the frozen pooling and probe contract.

Incident 002 registers a Minor category-only denominator diagnostic. Its no-result preflight passed
15 synthetic tests and 12 independent checks. The diagnostic is now Complete: independent
verification passed 19/19 and completion replay matched. The verified first failure is pair 1,
`s42:H-1 / fold 0`, with all three denominator-term categories `zero`. No AP5/probe files or later
pairs were accessed. Original EXP-071 remains Failed; the diagnostic does not change its method.

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
router feasibility study only; it does not establish a deployable router. At that
EXP-055 stage, EXP-054 and test were still sealed.

RQ-S3 then continued with paired M1/M3 train OOF (EXP-058), calibration/selective
prediction (EXP-059), and the frozen pre-Qwen router contract (EXP-060). The preserved
EXP-060 no-result preflight passed `7/7` synthetic tests, `25/25` runner checks and
`66/66` independent checks. The formal contract suite passed `23/23`, and formal
EXP-060 is `Verified Pass` after `4,412/4,412` independent verification checks. The
selected logistic router calls M3 for `501/3,360` rows (`14.9107%`); relative to M1-only,
six-label Macro-F1 changes by `+0.040168`, five-label Macro-F1 by `+0.006097`, and
Hamming loss by `-0.004365`. Router target discrimination is PR-AUC=`0.318653` and
ROC-AUC=`0.850804`.

The 2,000-replicate duplicate-component bootstrap 95% intervals are
`[13.6673%, 16.2172%]` for actual call rate, `[+0.009891, +0.071126]` for six-label
Macro-F1 gain, `[-0.007688, +0.019733]` for five-label Macro-F1 gain, and
`[-0.006332, -0.002515]` for Hamming-loss delta. The point estimate determines the
frozen development gate; the intervals qualify stability, including a five-label
interval that crosses zero. This result uses fully nested train OOF only. EXP-060 did
not access validation or test, read raw text, or run M1/M3 model forward, so
`Verified Pass` supports only development-stage routing feasibility for this frozen seed-42 pair,
not an independent-test result or a general deployment-benefit claim.

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
router-headroom decision, and
[`oof-router/runs/exp-060-pre-qwen-router/REPORT.md`](oof-router/runs/exp-060-pre-qwen-router/REPORT.md)
and
[`oof-router/runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md`](oof-router/runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md)
for the formal EXP-060 result, claim boundary and independent verification.

## Phase C current handoff — 2026-08-31

The local [topic workspace](../../forum-topic-emotion-web/README.md) preserves all Phase A/B evidence.
EXP-076 source attempt3 and inherited smoke are Verified; current UI/statistics/CSV controls pass
212 software tests and read-only QA on 5 existing jobs / 372 results. See its
[acceptance record](../../forum-topic-emotion-web/docs/acceptance.md).

New EXP-077 stopped after 40.221628s at critical memory pressure: 1 of 36 planned jobs completed,
the Research job was cancelled before any item receipt, and 34 jobs were not submitted.
Independent audit Passed, but exp077_complete=false and soak_gate_passed=false; stop-required.
This does not establish M3 OOM/leakage, a production success rate, or repair EXP-067/068.

Python Help Discourse review, adapter and EXP-078 tools are ready; its formal 300–400-item run was
not executed because the safe-to-continue prerequisite failed. Reports and the final claims ledger
remain Git-ignored under module private/reports. External gold and old context/C2 remain paused;
no training, test access, automatic retry, commit, stage, push or public deployment was performed.
