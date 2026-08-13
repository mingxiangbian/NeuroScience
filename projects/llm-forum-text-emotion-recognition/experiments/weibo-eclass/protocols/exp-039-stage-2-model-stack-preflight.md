# EXP-039: Weibo EClass Stage 2 Model-Stack Preflight

---
date: 2026-08-08
experiment_id: EXP-039
tier: Minor
rq: RQ-F1, RQ-F2
status: Failed
stage: environment-model-parser-lora-preflight
dataset_protocol: DATA-WEIBO-TASK-V1
---

## Purpose

Before any full training, verify that the frozen Weibo task can pass through
the planned classical, encoder and LLM stacks without label, prompt, parser,
truncation, checkpoint or LoRA-insertion errors. This experiment is an
implementation and resource gate, not a model comparison.

No Macro-F1, Accuracy or model-selection claim is produced. A successful smoke
run only authorizes registration of later Major train/dev experiments.

## Data Boundary

- Read only `derived-private/eclass-v1/train.jsonl`.
- Validation access: forbidden.
- Test inputs and sealed test labels: forbidden.
- Deterministically select four rows from every `(label, context_available)`
  stratum, for 56 private smoke rows covering all seven labels and both context
  states.
- Public artifacts may contain only aggregate counts, hashes, timing and
  pass/fail states. Text, sample/group IDs, generated output and predictions
  remain under the Git-ignored private data root.

## Frozen Stack

### M1 classical smoke

- Word TF-IDF: `(1, 2)` n-grams, `min_df=2`, sublinear TF.
- Character TF-IDF: `char_wb`, `(3, 5)` n-grams, `min_df=2`, sublinear TF.
- Classifier: `LinearSVC(C=1.0, class_weight="balanced", random_state=42)`.
- Smoke only checks fitting and finite seven-class decision scores on both
  paired input views. It does not choose hyperparameters from smoke accuracy.

### M2 encoder smoke

- Model: `hfl/chinese-roberta-wwm-ext`.
- Revision: `5c58d0b8ec1d9014354d691c538661bf00bfdb44`.
- License: Apache-2.0.
- Architecture is loaded with BERT sequence-classification classes, as required
  by the upstream model card.
- Seven-class head, max length 256, batch 14, two CPU optimizer steps at
  `2e-5`; one target-only and one previous-context step.
- Pass requires finite loss, correct tensor shapes and changed trainable
  parameters. Loss improvement is not required and is not a performance result.

### M3/M4 Qwen smoke

- Model: `Qwen/Qwen3-4B`.
- Revision: `1cfa9a7208912126459214e8b04321603b3df60c`.
- License: Apache-2.0.
- Local runtime: unquantized MLX BF16 converted from the official revision.
- This original Qwen3 checkpoint is used because the same weights support the
  hard `enable_thinking` switch. Separate 2507 Instruct and Thinking weights
  would confound the planned context x reasoning comparison.
- Qwen Base is not downloaded in Stage 2; it belongs only to the optional later
  representation branch.

The common prompt, label definitions, user content and output schema are fixed.
Thinking on/off changes only the official chat-template switch. Both use the
same preflight sampler and output cap: temperature 0.6, top-p 0.95, top-k 20,
min-p 0 and 384 maximum new tokens. The thinking condition may emit reasoning
before a `</think>` boundary; the opening marker may be template-prefilled and
therefore absent from the generated text. Only the strict final JSON label is
evaluated or retained in public aggregates.

The train-only inference smoke covers one context-available row per label under
all four context x thinking conditions, plus one context-missing row per label
under both thinking conditions. Strict final-label validity must be at least
80% overall and nonzero in every condition. This gate concerns parseability,
not correctness.

### LoRA insertion and two-step smoke

- Exact base: the Qwen revision above, unquantized BF16.
- Adapted blocks: final 16 transformer blocks, indices 20-35.
- Target modules per block: `q_proj`, `k_proj`, `v_proj`, `o_proj`,
  `gate_proj`, `up_proj`, `down_proj`.
- Rank 8, scale 20, dropout 0, prompt masked from loss.
- Batch 1, max sequence length 512, gradient checkpointing enabled, two
  optimizer iterations, learning rate `1e-5`.
- Pass requires the exact intended insertion set, finite losses, nonzero LoRA B
  tensors, saved adapter reload and finite post-reload logits.

If the 16 GB local host cannot complete the exact 4B LoRA smoke, record
`blocked_gpu_required` rather than silently reducing precision, layers or target
modules. The identical smoke must then pass on the rented GPU before full
training. A 1.7B substitute cannot close this gate.

## Prompt and Parser Contract

- Output schema: exactly `{"label":"<one frozen label>"}`.
- Allowed labels: `anger`, `joy`, `negative`, `neutral`, `no_emotion`,
  `positive`, `sadness`.
- Context helps interpret the target but is never itself labeled.
- `SufCL` and future replies are absent.
- Non-thinking output must contain only the JSON object.
- Thinking output must contain exactly one `</think>` boundary followed by
  exactly one JSON object. An opening `<think>` marker is accepted but not
  required because the official template may prefill it. Markdown fences,
  extra keys, unknown labels and multiple labels are invalid.
- Target-preserving truncation may shorten only the preceding context. It must
  never truncate the target in the frozen task, whose observed target lengths
  fit both sequence budgets.

## Resource Budget

- Network model-download attempts: at most 2 per model.
- Local Qwen source plus conversion: at most 20 GiB.
- Local wall time: at most 120 minutes excluding download stalls.
- Qwen smoke generations: 42.
- LoRA smoke iterations: 2.
- API cost: USD 0; external API use is forbidden.
- Validation rows: 0.
- Test rows: 0.

## Pass Criteria

1. Source revisions, licenses, local hashes and Git-ignore boundaries verify.
2. The 56-row deterministic private selection covers all frozen strata.
3. Label parser synthetic tests pass, and paired prompt construction changes
   only allowed fields.
4. All observed train inputs fit the frozen encoder and Qwen limits without
   target truncation.
5. M1 and M2 smoke checks pass without reporting task performance.
6. Qwen loads, all required conditions run, and the parser-validity gate passes.
7. Exact 4B LoRA insertion and two-step checkpoint/reload smoke passes locally
   or is explicitly blocked pending the required GPU smoke.
8. Independent verification passes, and no public artifact contains row-level
   text, IDs, outputs, predictions or test information.

Only a full pass authorizes Stage 3 registration. A GPU-blocked LoRA smoke keeps
Stage 2 open until the same check passes on the rented environment.

## Outcome

The first static prompt-contract check failed before model download or training.
The JSON assistant target used Python `str.format` without escaping its outer
braces, causing a `KeyError` after the deterministic private selection was
written. Validation and test were not accessed, optimizer steps remained zero,
and no model was downloaded. Frozen code/config snapshots and the failure record
are retained under `runs/exp-039-model-stack-preflight/`. The one-line rendering
correction is rerun under `EXP-040`; this failed run is not overwritten.
