# EXP-058: Paired M1-M3 Out-of-Fold Predictions

- Experiment ID: `EXP-058`
- Tier: Major
- RQ: `RQ-S3`
- Parent: `DATA-SO-TASK-V1`, `EXP-051`, `EXP-053`, `EXP-055`
- Registered: 2026-08-16
- Status: `Fold-manifest preflight authorized; M1/M3 OOF training not authorized`

## Question And Scope

Can duplicate-component-disjoint out-of-fold (OOF) predictions from the frozen M1
RoBERTa and M3 Qwen Classification LoRA families provide uncontaminated train-level
inputs for later calibration, selective prediction, and a pre-Qwen router?

EXP-058 has two gates:

1. **Fold-manifest preflight**: build and independently verify one shared five-fold
   assignment. This gate performs no model loading, training, forward pass, threshold
   fitting, oracle analysis, or performance evaluation.
2. **Paired OOF production**: train M1 and M3 from their frozen base initializations on
   four folds and emit raw logits for the fifth fold. This gate requires a separate
   execution authorization after the manifest preflight passes.

This experiment uses train only. The existing validation split is reserved for a later
development confirmation and is not an EXP-058 input. The consumed test split and sealed
test labels are forbidden.

## Frozen Data Contract

- Protocol: `DATA-SO-TASK-V1`.
- Input: private train file only, exactly `3,360` rows and `3,277` duplicate components.
- Train SHA-256:
  `fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc`.
- Label order: `love, joy, surprise, anger, sadness, fear`.
- OOF folds: `5`, numbered `0` through `4`.
- Fold-assignment seed: `20260816`; canonical model seed: `42`.
- Unit of assignment: the existing exact plus NFKC/casefold/whitespace duplicate
  component. A component must occur in one fold only.
- M1 and M3 must consume the same frozen public fold manifest and verify its hash before
  and after every fold run.

The fold builder and verifier are allowlisted to open the train file. They must not open
`validation.jsonl`, `test.inputs.jsonl`, `test.labels.sealed.jsonl`, or any existing
validation/test prediction artifact.

## Fold Construction And Acceptance

The deterministic allocator first assigns non-singleton components and then fills exact
row capacity with singleton components. It balances row-level label support, neutral,
label cardinality, duplicate rows/components, and conflicting duplicate rows/components.
Deterministic within-bucket swaps may improve balance without changing fold size or
component integrity.

The preflight passes only when all of the following hold:

- all `3,360` train samples occur exactly once;
- all `3,277` components occur in exactly one fold;
- every fold contains exactly `672` rows;
- every fold contains all six labels;
- `surprise` support is between `5` and `7` in every fold;
- the maximum absolute allocation error for each label, relative to the ideal `0.20`
  share, is at most `0.05`;
- all `18` train conflicting duplicate components remain intact;
- M1 and M3 reference one identical manifest hash;
- public artifacts contain no text, gold labels, logits, probabilities, or source row
  coordinates;
- no validation or test file is opened.

The original proposal referred to 26 conflicting components. That is the full 4,800-row
dataset count; the EXP-058 train-only count is 18 and is the frozen acceptance value.
If these constraints cannot be met, the failed attempt is retained and no model training
starts.

## Frozen M1 OOF Configuration

M1 inherits EXP-051 except for the outer training subset:

- `FacebookAI/roberta-base`, pinned revision;
- target-only, right truncation, max length `256`;
- unweighted `BCEWithLogitsLoss`;
- batch `16`, AdamW `2e-5`, weight decay `0.01`, 10% warmup, linear decay;
- canonical seed `42` for every fold;
- the number of epochs is frozen to the EXP-051 seed-42 selected epoch and must be read
  from verified metadata before OOF execution;
- the held-out OOF fold cannot select an epoch, checkpoint, threshold, or hyperparameter.

Each fold starts from the pinned base model with a new classification head. Full-train
M1 checkpoints must not initialize an OOF fold.

## Frozen M3 OOF Configuration

M3 inherits EXP-053 except for the outer training subset:

- `Qwen/Qwen3-4B`, pinned revision, BF16 unquantized;
- target-only frozen prompt, thinking disabled, max length `384`;
- final-layer last non-padding input-token pooling and `Linear(2560, 6)` head;
- LoRA in blocks 20-35 at `q/k/v/o` and `gate/up/down`, 112 insertion points;
- rank `8`, scale `20`, dropout `0`;
- LoRA/head learning rates `1e-5`/`1e-4`, weight decay `0.01`;
- unweighted BCE, batch `1`, gradient checkpointing, exactly `2` epochs;
- canonical seed `42` for every fold.

Every fold starts from the same pinned Qwen base with newly initialized LoRA tensors and
head. Full-train adapters, heads, optimizer states, and checkpoints must not initialize an
OOF fold.

## OOF Output Contract

The private paired table must contain exactly one record per train sample with:

- `sample_id`, `component_id`, and `fold_id`;
- six gold bits in the frozen label order;
- six raw M1 logits and six raw M3 logits;
- character length and tokenizer-specific input length;
- source fold-run IDs and artifact hashes.

EXP-058 saves raw finite logits only. It does not fit temperatures, thresholds, router
targets, abstention scores, or final predictions. Those belong to EXP-059/060.

Public outputs may contain anonymous IDs, fold IDs, aggregate distributions, hashes,
resource accounting, and verifier results. Text, row-level gold, row-level logits, and
representations remain mode `0600` in Git-ignored private storage.

## Verification

An independent verifier that does not import the builder or future model runners must
recompute:

- train hash, schema, label order, row/component coverage, and fold balance;
- sample uniqueness and component non-overlap;
- M1/M3 manifest identity;
- one held-out prediction per sample and no train-fold membership for that sample;
- finite logits and exact label order after OOF production;
- checkpoint/adapter/head/config hashes;
- public privacy and private file permissions;
- split-access audit showing train only.

The fold-manifest gate verifies only the applicable subset and explicitly records that no
models, logits, oracle, calibration, or performance metrics exist yet.

## Diagnostics And Stop Boundary

After paired OOF production is independently verified, a fixed-0.5 whole-vector oracle
may be reported as an integrity diagnostic. It is not the router stop gate because
calibration and shared-threshold selection have not yet occurred. The router continuation
decision is made only under EXP-059/060 using their frozen cross-fitted contracts.

Seed 42 is a feasibility run, not a stable router conclusion. If a learned router later
passes its gate, seeds 43 and 44 are required before a strong stability claim. A seed-42
failure may stop the current canonical feasibility attempt but does not prove that routing
is impossible in general.

## Resource Budget

Fold-manifest preflight:

- model loads/training/forward passes: `0`;
- CPU wall time: at most `5` minutes;
- peak memory: at most `1` GB;
- API cost: `$0`.

Paired OOF production, not authorized by this registration step:

- M1: at most `5` fold runs and `4` CPU/GPU hours total;
- M3: at most `5` fold runs, `4.5` hours per fold, `22.5` Metal/GPU hours total;
- combined wall-time budget: `26.5` compute hours;
- M3 peak memory ceiling: `13` GB; the allocator safety limit may not be disabled;
- API cost: `$0`;
- stop before exceeding a per-family budget or after any integrity failure.

## Thesis Destination And Claim Boundary

Destination: Methods section for nested system evaluation and the conditional RQ-S3
system experiment; appendices for fold construction and reproducibility.

Passing the manifest preflight proves only that a leakage-controlled shared fold plan is
available. Passing full EXP-058 proves only that paired train OOF logits are available.
Neither result proves probability calibration, reliable abstention, deployable routing,
Qwen cost-effectiveness, context benefit, or internal emotion mechanisms.

## 2026-08-16 Full-OOF Execution Authorization

The user explicitly authorized paired five-fold OOF production after the fold-0 consumer
dry-run passed its independent verifier (`114/114`). This authorization covers exactly:

- five M1 fold runs and five M3 fold runs, all with model seed `42`;
- training on the four in-fold partitions and raw-logit forward passes on the fifth;
- a private, source-order paired table covering all `3,360` train rows exactly once;
- final checkpoints for M1 and final adapter/head artifacts for M3;
- per-fold and final independent integrity verification.

It does not authorize validation, test, thresholds, predictions, performance metrics,
oracle analysis, calibration, abstention, router fitting, or additional seeds.

The dry-run also froze two implementation details that were implicit in the original
registration. Consumers first preserve the frozen train-file order and then filter by
fold. For M1, each fold uses `168` steps per epoch, the original five-epoch scheduler
horizon of `840` steps, `84` warmup steps, and stops after the selected fourth epoch at
`672` optimizer steps. M3 executes exactly two epochs, or `5,376` optimizer steps per
fold. Each fold is a separate append-only process so completed folds survive a later
runtime interruption; an integrity failure stops the family before another fold starts.
