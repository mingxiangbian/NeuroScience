# EXP-070 Formal Representation Extraction

- Experiment ID: `EXP-070`
- Stage: `formal representation extraction`
- Date: `2026-08-27`
- RQ: `RQ-S4.1`
- Tier: `Major experiment infrastructure stage`
- Parent method: `EXP-070: Layerwise Linear Probe`
- Parent gate: `EXP-070 no-result preflight attempt-1 Complete, 24/24 Passed`
- Status: `Protocol registered; execution closed until a separate formal config authorizes it`

## 1. Purpose and boundary

This stage creates the full train-only representation caches required by the frozen EXP-070 probe
method. It owns one Frozen Qwen cache and 15 fold-specific M3 caches in a new EXP-070 private root.
EXP-069 remains an immutable 32-row parity preflight and is not rerun or used as formal probe data.

This protocol authorizes no probe fitting, threshold selection, label shuffle, bootstrap,
classification metric, seed vote, representation state or EXP-071 work. Passing extraction means
only that the 16 formal caches are complete and verified.

## 2. Frozen parent gate

The formal config must bind these exact no-result artifacts:

| Artifact | Bytes | Mode | SHA-256 |
| --- | ---: | --- | --- |
| EXP-070 method protocol | 11,748 | `0644` | `d4a481d2846d36651786c3f7458c67ca828c7e4c39463ef41750bbe33422f690` |
| No-result config | 13,178 | `0644` | `5355cd828ca8751c83f531307e6c9e8283bc0f19d92433b868d96abbb2063d1b` |
| No-result static run | 3,016 | `0644` | `42ad2148afed823df183b87e2b3556ad3719516af97ebe3c2401a741b11dbdff` |
| No-result verification | 2,522 | `0644` | `9aadc4de6b870da018a0f536bc10bc8bd2879470b1c39ea2eb5f313e9c3804ad` |
| No-result completion | 1,883 | `0644` | `5582d0ac68158c12782b8b1b52c5a403a67714fe99d7763c4e46ff6df1e9807e` |
| Private input contract | 63,253 | `0600` | `9bf597dd1b2a43000c726033ed25f0ead3ed7c89251f093e8b799ff25a954c86` |

The no-result completion records `formal_execution_authorized=false`. This protocol does not change
that value. A new immutable formal config must authorize model loading, train-text forward execution
and cache creation before the first worker starts. It must keep probe fitting, threshold selection,
bootstrap, metrics, formal EXP-070 completion and EXP-071 unauthorized.

## 3. Access history and current access contract

Before the formal config was frozen, one design-time schema inspection command displayed two
`DATA-SO-TASK-V1 train` rows in terminal output. This counts as design-time train-row value exposure.
The displayed rows were not used to select layers, folds, checkpoints, tolerances, resources or any
other method field. That command loaded no model, ran no forward pass, computed no metric and
accessed no validation or test data. No displayed value may be copied into a config, manifest,
public record, private result or later report.

This history occurred outside the no-result runner and verifier. Their recorded access attestations
remain process-local facts and must not be generalized to the entire design session.

Formal extraction may:

- parse the frozen 3,360 train rows and use their target text for tokenization and forward execution;
- read the frozen public/private fold manifests for alignment;
- load the Frozen Qwen base and the 15 verified M3 adapters;
- read parent manifests, identities and model files required for provenance checks.

Formal extraction must record that it accesses a label-bearing train container. It cannot use label
values for selection, branching, filtering or computation, and it cannot persist or log them. It may
not access validation, test, test-gate artifacts, historical performance results or raw text outside
the frozen train source.

## 4. Frozen data, model and rendering contract

```text
data = DATA-SO-TASK-V1 train
rows = 3,360
source order = ordinals 0..3359
outer folds = frozen EXP-058 component-disjoint folds
base = Qwen/Qwen3-4B
base revision = 1cfa9a7208912126459214e8b04321603b3df60c
precision = MLX BF16, unquantized
hidden size = 2,560
max length = 384
thinking = off
forward = singleton
pooling = last non-padding input token
```

The tokenizer, prompt, special tokens, rendering logic, hook locations and Qwen implementation must
match the EXP-069 verified source. No context, cleaning, normalization, prompt or batching change is
allowed.

Every matrix uses exact train source order on axis 0. Each private worker manifest binds separate
SHA-256 digests for the ordinal, sample-ID, component-ID, fold-ID and token-ID streams. IDs and these
row-identity digests remain private.

## 5. Worker inventory and order

Exactly 16 fresh model processes run in this order:

```text
00  Frozen Qwen
01  M3 seed 42 fold 0
02  M3 seed 42 fold 1
03  M3 seed 42 fold 2
04  M3 seed 42 fold 3
05  M3 seed 42 fold 4
06  M3 seed 43 fold 0
07  M3 seed 43 fold 1
08  M3 seed 43 fold 2
09  M3 seed 43 fold 3
10  M3 seed 43 fold 4
11  M3 seed 44 fold 0
12  M3 seed 44 fold 1
13  M3 seed 44 fold 2
14  M3 seed 44 fold 3
15  M3 seed 44 fold 4
```

One process loads one checkpoint, processes all 3,360 train rows, seals one matrix and exits. A
single exclusive heavy-process lock covers model load, forward execution, flush and source
post-hash. Concurrent MLX model workers are forbidden.

## 6. Matrix and point contract

The worker output is a C-order `.npy` matrix with dtype `float32`:

| Condition | Count | Shape | Persisted point order |
| --- | ---: | --- | --- |
| Frozen Qwen | 1 | `(3360, 9, 2560)` | `H-1,H7,H15,H19,H20,H27,H31,H35,HF` |
| M3 seed 42 | 5 | `(3360, 9, 2560)` | `H-1,H7,H15,H19,H20,H27,H31,H35,HF` |
| M3 seed 43 | 5 | `(3360, 3, 2560)` | `H19,H27,HF` |
| M3 seed 44 | 5 | `(3360, 3, 2560)` | `H19,H27,HF` |

`H-1` through `H35` are raw residual-stream values. `HF` is the final RMSNorm output. No worker
persists full-token activations, logits, probabilities, predictions, labels or raw text.

Each worker must check every persisted value is finite before sealing the matrix. The declared raw
representation total is exactly `2,890,137,600` bytes, excluding NPY headers and manifests.

## 7. Token identity and pre-LoRA parity

All workers must produce the same token-ID stream digest as Frozen Qwen for the 3,360 rows. A token
length, special-token, truncation or row-order difference stops the attempt.

For every M3 worker, compare `H-1/H7/H15/H19` with the Frozen Qwen matrix in `float32`:

```text
rtol = 0
atol = 1e-5
```

Seed-42 workers persist all four points. Seeds 43/44 persist `H19` and compute `H-1/H7/H15`
transiently. They record the four aggregate maximum absolute errors in their private worker
manifests, then release the three transient arrays without writing them to disk. The raw-byte budget
therefore covers only `H19/H27/HF` for seeds 43/44.

Any pre-LoRA maximum above `1e-5` stops extraction. The worker must not reinterpret the mismatch as
a representation effect.

## 8. Source immutability

Before and after each worker, hash and stat every source that the worker consumes:

- base-model sentinel set and tokenizer files;
- fold-specific adapter;
- fold-specific head and held-out-logit source when used for the verified identity chain;
- frozen extraction implementation and Qwen source.

Paths, bytes, modes and SHA-256 values must match the formal config and the no-result input
contract. A worker cannot modify, copy back, replace or relabel a source artifact. Any before/after
drift stops the attempt.

## 9. Resume and append-only behavior

The first invocation creates a fresh public root, private root and `run-claim.json`. Neither root may
be a symlink. Before creation, both formal roots must be absent.

Resume is limited to a verified completed prefix of the fixed worker order:

1. Validate every completed prefix matrix and its public/private worker records by path, shape,
   dtype, bytes, mode, SHA-256, row digests, source identities, parity gates and resource gates.
2. Confirm there is no sealed worker artifact after the prefix and no terminal failure record.
3. Run only the next expected worker. Never rerun or overwrite a sealed worker.
4. Include all prefix workers when calculating aggregate wall time and disk usage.

Only the next expected worker may own `representations.npy.part` and mutable `progress.json`.
Progress commits a continuous 32-row prefix and binds each committed slice plus its token and parity
digests. A fresh process may resume after it rechecks every committed chunk. Progress corruption,
an orphan technical file, a technical file under any later worker, an invalid sealed prefix or a
terminal failure blocks same-attempt resume.

At finalization the worker verifies 3,360 rows, hard-links the part file to the unused final name,
unlinks the technical part, and writes immutable `worker.json` last. A crash between link and worker
seal may resume only after the next process verifies the final matrix and committed progress.

## 10. Resource contract

| Resource | Ceiling |
| --- | ---: |
| Model workers | `16` |
| Concurrent heavy workers | `1` |
| Wall time per worker | `4 hours` |
| Aggregate model-worker wall time | `64 hours` |
| Peak MLX memory per worker | `10 GB` |
| Private EXP-070 disk | `5 GiB` |
| Minimum free disk before initialization | `10 GiB` |
| API cost | `USD 0` |

The EXP-069 smoke projection of about `38.04 hours` is a scheduling estimate, not a scientific or
performance result. The formal runner records worker and aggregate resource use but cannot compute
classification or representation-effect metrics.

The extractor runs offline with the Phase A MLX environment:

```text
/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python
Python 3.11.15
NumPy 2.4.6
MLX 0.32.0
MLX-LM 0.31.3
safetensors 0.8.0
tokenizers 0.22.2
transformers 5.14.1
```

## 11. Public schema

Public root:

```text
phase-b-representation/runs/exp-070-layerwise-probes/formal-extraction-attempt-1/
├── run-claim.json
├── extraction.json
├── extraction-verification.json
├── extraction-complete.json
└── failure.json                    # failure only
```

Public directories use `0755`; public files use `0644`. No per-worker public file is allowed.
`extraction.json` may contain worker counts, shapes, point names, matrix bytes/hash/mode, aggregate
parity maxima, elapsed time, peak resources, access flags and status. It cannot contain row IDs, row
digests, token digests, text, labels, representations, logits, probabilities, predictions or
checkpoint values.

`extraction.json` aggregates worker counts, shapes, point inventories, maximum parity errors,
resource use, access flags and the private manifest identity. `extraction-complete.json` certifies
only that formal extraction passed independent verification. It must set:

```text
formal_extraction_complete = true
probe_fitting_authorized = false
exp070_complete = false
exp071_authorized = false
```

On failure, write a terminal public failure record instead of fabricating the remaining success
files.

## 12. Private schema

Private root:

```text
phase-b-representation/private/exp-070-layerwise-probes/formal-extraction-attempt-1/
├── input-manifest.json
├── row-contract.npz
├── extraction/
│   ├── base/{representations.npy,worker.json}
│   ├── m3-s42-f{0..4}/{representations.npy,worker.json}
│   ├── m3-s43-f{0..4}/{representations.npy,worker.json}
│   └── m3-s44-f{0..4}/{representations.npy,worker.json}
└── extraction-manifest.json
```

The technical `.part` and `progress.json` files may exist only under the next expected worker during
an unsealed run. `row-contract.npz` contains ordinal, fold and component-code arrays but no label,
text or token-ID values.

The private root and every private subdirectory use `0700`; every private file uses `0600`. The
entire root must remain Git ignored and contain no symlink.

Each private worker record contains:

- condition, seed, fold, point order, shape, dtype and layout;
- ordinal, sample-ID, component-ID, fold-ID and token-stream digests;
- source identities before and after execution;
- four pre-LoRA maximum errors;
- finite-value, row-count and token-count checks;
- access attestations, elapsed time, MLX peak and output identity.

`extraction-manifest.json` lists exactly 16 sealed matrices and 16 worker records. It binds their
relative paths, bytes, modes and SHA-256 values plus the frozen config, protocol, runner, verifier,
tests and no-result parent gate.

## 13. Independent extraction verification

The independent verifier is model-free and cannot import the runner, MLX, MLX-LM or Transformers.
It may memory-map the 16 matrices to verify headers, C-order layout, finite values, row count and
persisted pre-LoRA parity. It reads no train text or label values and computes no probe or scientific
metric.

It independently verifies:

1. config, implementation and no-result gate identities;
2. exact public/private inventory, modes, ignored state and absence of symlinks;
3. the fixed 16-worker order and completed-prefix history;
4. all shapes, point orders, dtype, layout, bytes and hashes;
5. private row-identity and token-stream digests;
6. persisted pre-LoRA parity at `H-1/H7/H15/H19` for seed 42 and `H19` for seeds 43/44;
7. recorded transient parity maxima for seeds 43/44 and the frozen runner path that produced them;
8. source before/after identities, finite scans and resource ceilings;
9. public privacy and access boundaries;
10. absence of probe, threshold, shuffle, bootstrap, classification metric and result-state output.

The verifier writes `extraction-verification.json`. Only a Passed verification may be bound by
`extraction-complete.json`.

If the verifier process stops after writing the exact Passed verification but before completion, a
fresh verifier process must rerun every read-only check, reproduce the same verification payload and
then write only the missing completion. It cannot accept a changed or partially written verification.

## 14. Stop rules

Stop the attempt on any of these conditions:

- no-result completion, method, config, input contract, source or implementation identity drift;
- missing formal authorization or an authorization field outside extraction becoming true;
- initial formal root already exists, except for an exact valid completed-prefix resume;
- unexpected worker order, duplicate worker, orphan output, partial file or terminal failure;
- model, tokenizer, prompt, rendering, hook, row order, fold, point, dtype, layout or token drift;
- source hash or mode drift before or after a worker;
- pre-LoRA error above `1e-5`, non-finite value, wrong shape or wrong row count;
- model-worker concurrency above one, worker wall time above four hours, aggregate wall time above
  64 hours, MLX peak above 10 GB, private disk above 5 GiB or free disk below the frozen gate;
- private path not ignored, wrong file/directory mode, symlink or public row-level leakage;
- persistence or logging of raw text or label values;
- validation, test or test-gate access;
- probe fitting, threshold selection, label shuffle, bootstrap, classification metric, seed vote,
  representation state or EXP-071 activity.

Failure evidence remains append-only. The runner cannot weaken a tolerance, raise a resource limit,
change a point, skip a worker or start probe fitting to recover the attempt.

## 15. Completion claim

Successful completion supports one claim:

> EXP-070 has a verified, train-only, fold-specific representation cache suitable for the separately
> frozen probe consumer.

It does not establish label decodability, a LoRA representation effect, a replicated seed state,
functional dependence, independent-data generalization or an emotion mechanism. Probe execution
requires a separate immutable consumer contract and authorization.
