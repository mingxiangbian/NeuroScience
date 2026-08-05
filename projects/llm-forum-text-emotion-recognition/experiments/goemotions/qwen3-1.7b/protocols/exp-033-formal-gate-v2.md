# EXP-033 Formal Seed-42 Execution Gate V2

## V1 Supersession

The V1 no-model gate passed, but it is superseded before authorization because it did not
recompute every model-weight file and the frozen MLX-LM source tree at the transition into the
formal run. V2 closes that execution-control gap. V1 remains immutable provenance; no V1
artifact authorizes training. This correction changes no research question, data, model,
hyperparameter, output path, or evaluation rule.

## Scope

This is an execution-control addendum to the frozen EXP-033 Major protocol. It does not change
the research question, prepared data, model, LoRA placement, hyperparameters, prompt, decoder,
metrics, selection rule, or resource budget.

- Experiment: `EXP-033`
- Stage: `formal-seed-42`
- Seed authorized: `42` only
- Training split: allowed
- Validation split during training: forbidden
- Test split: absent and forbidden
- Seeds 43 and 44: closed until the registered repetition gate is evaluated

The user explicitly authorized proceeding through seed-42 training, independent training
verification, and seed-42 validation evaluation on `2026-08-03`. This authorization does not
open the test gate or authorize additional training seeds.

## Frozen Runtime

- Train rows: 43,410
- Runtime data-root inventory: `train.jsonl` plus the frozen `smoke/` child directory; MLX reads
  only the root `train.jsonl`, and root-level valid/dev/test files remain forbidden
- Micro-iterations: 21,705
- Optimizer updates: 4,341
- Epochs: 1
- Micro-batch: 2
- Gradient accumulation: 5
- Effective batch: 10
- Optimizer: Adam
- Learning rate: constant `1e-5`
- Maximum sequence length: 512
- LoRA: final 16 transformer blocks, rank 8, scale 20, dropout 0
- Target modules: attention q/k/v/o and MLP gate/up/down projections
- Trainable parameters: 4,980,736
- Intermediate checkpoints: iterations 5,000, 10,000, 15,000, and 20,000
- Final selection: the final one-epoch adapter; validation does not select a training checkpoint

## Preconditions

Formal training can start only when all of the following pass:

1. The V3 runner remains formal-disabled and hash-identical.
2. Its no-model dry-run verification remains hash-identical and records a passed, no-model,
   train-only transition. Its old output-absence assertion is not replayed after smoke artifacts
   exist.
3. The 50-iteration train-only smoke verifier still passes in check mode.
4. The canonical formal runtime and prepared train JSONL match their frozen SHA-256 values.
5. Every frozen model file, the model manifest and revision, all installed-package versions,
   the complete MLX-LM Python source tree, and the four canonical runtime-semantics sources are
   independently re-hashed at the gate and again immediately before the training subprocess.
6. The seed-42 formal adapter and run directories do not exist.
7. `test.tsv` remains absent.
8. A standalone formal gate dry-run passes independent recomputation.
9. A separate authorization artifact binds the gate, runtime, config, and smoke-verification
   hashes and permits only train-only seed 42.

## Completion And Verification

The formal runner must preserve failures and may not overwrite an existing run. A successful
subprocess is not sufficient evidence. The independent training verifier must recompute:

- exact split boundaries, command, runtime, authorization, and artifact hashes;
- current model weights, model identity, installed packages, full MLX-LM source tree, and
  canonical runtime-semantics sources against the pre-training record;
- complete reporting iterations, finite loss, constant learning rate, positive throughput,
  monotonic trained-token count, wall time, and peak MLX memory;
- exact adapter tensor keys, 4,980,736 parameters, and non-zero finite LoRA B tensors;
- exact intermediate checkpoint set and final adapter configuration.

Only a `Passed` independent training verification opens creation of a validation-only inference
contract. It does not itself read validation.

## Validation Transition

After training verification, freeze and independently audit a separate seed-42 validation
contract. That contract must bind the final adapter, official dev split, EXP-031 neutral
co-occurrence ontology, disabled thinking, deterministic decoding, output parser, metric code,
comparison inputs, privacy schema, four-hour validation budget, and absent test split.

Validation results must be recomputed from saved predictions before evaluating the registered
repetition gate. The primary metric is 28-label Macro-F1. Full auxiliary metrics, per-label
metrics, parser validity, predicted cardinality, latency, and resource use must also be reported.

## Resource Gates

- Formal seed-42 training wall time: at most 18 active hours
- Peak MLX memory: at most 14 GB
- Seed-42 full-validation generation: at most 4 active hours
- API cost: USD 0

Crossing a resource gate records a failed run and does not authorize silent retries or changed
settings.
