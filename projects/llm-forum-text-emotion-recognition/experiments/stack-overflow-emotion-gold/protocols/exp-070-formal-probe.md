# EXP-070 Formal Probe Consumer

- Experiment ID: `EXP-070`
- Stage: `formal layerwise linear probe`
- Date: `2026-08-28`
- RQ: `RQ-S4.1`
- Tier: `Major representation experiment`
- Parent method: `EXP-070: Layerwise Linear Probe`
- Parent source gate: `formal extraction Complete via verification attempt 2`
- Status: `Consumer contract registered; static gate and formal execution unexecuted`

## 1. Purpose and claim boundary

This consumer fits the frozen EXP-070 linear probes against the verified train-only representation
caches. It computes nested outer-heldout probabilities, thresholded metrics, label-shuffle controls,
paired duplicate-component bootstrap intervals and the registered seed vote.

The consumer can support a claim about outer-heldout linear label accessibility under the frozen
split, pooling and probe contract. It cannot establish a causal representation mechanism,
emotion-specific neurons, human emotion processing, independent-data generalization, validation or
test performance.

The consumer does not load Qwen, an adapter or a tokenizer. It does not run a forward pass, rerun
extraction, modify a source cache or read an EXP-069 smoke artifact.

## 2. Immutable parents

The preflight and formal configs bind these parent chains by path, bytes, mode and SHA-256:

1. the frozen EXP-070 method protocol and no-result config;
2. the formal extraction protocol, config, public claim and assembled extraction record;
3. the verification-attempt-2 protocol, config, source snapshot claim, Passed verification and
   completion;
4. the private extraction input manifest, row contract and terminal extraction manifest;
5. all 16 sealed representation matrices listed by the extraction manifest;
6. the verified EXP-058 private fold manifest, which supplies sample IDs, component IDs, fold IDs
   and six-label vectors.

The recovery snapshot digest is
`cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad`.
The consumer recomputes the bound source identity before static completion, before and after each
formal fold, before assemble and after assemble. It writes nothing into an extraction, recovery,
fold-manifest or data source root.

The consumer treats verification attempt 2 as the terminal extraction authority. It does not import
or execute either extraction verifier. It leaves the failed or unexecuted earlier verification path
unchanged.

## 3. Two configs and one implementation pair

The implementation uses one runner, one independent verifier and one test module. Two configs keep
the static and formal authorization boundaries separate:

- `exp-070-formal-probe-preflight.json` authorizes source identity checks, NPY header checks,
  environment checks and synthetic tests. It denies source array values, label values, fitting and
  metrics.
- `exp-070-formal-probe.json` binds the Passed static run, verification and completion. It authorizes
  initialize, folds 0 through 4, assemble, final verification and completion.

Both configs contain an identical top-level `method` object. The runner and verifier require object
equality before any formal output creation. The formal config cannot weaken or extend a method
field.

## 4. Static no-result gate

The static runner writes `static.json` and a private `input-contract-manifest.json` into fresh
preflight roots. It may hash source file bytes and inspect NPY headers. It cannot load a representation
array, parse a private fold row, access a label value, fit a probe, choose a threshold, generate a
shuffle, generate a bootstrap draw or compute a scientific metric.

The independent static verifier does not import the runner. It verifies:

1. config, protocol, implementation and parent identities;
2. the Passed extraction recovery and unchanged snapshot;
3. the exact 16-matrix inventory, shapes, point orders, modes and NPY headers;
4. the label-source identity without parsing its JSONL rows;
5. Python and package identities, single-thread settings and the 512 MiB consumer-private budget;
6. fresh public and private formal roots;
7. runner and verifier import boundaries;
8. synthetic split, threshold, shuffle, bootstrap, fit-count, no-clobber and privacy tests;
9. access attestations showing no representation value, label value, model, fit or metric access.

A Passed verifier writes `static-verification.json`, reruns its read-only checks, then writes
`no-result-complete.json`. If it stops after the Passed record, a fresh invocation must reproduce the
same verification object before it writes the missing completion. Static completion authorizes only
the frozen formal config. It does not start formal execution.

## 5. Label and row alignment

The formal consumer uses
`fold-manifest.private.jsonl` as its only label-bearing source. It does not parse `train.jsonl` and
therefore does not read train text.

The consumer requires 3,360 private fold rows and exact fields:

    schema_version, protocol_id, experiment_id, sample_id, component_id,
    fold_id, labels, neutral, label_cardinality

It validates six binary labels in the order
`love, joy, surprise, anger, sadness, fear`. It recomputes sample-ID, component-ID and fold-ID order
digests under the extraction scheme and requires equality with the terminal extraction manifest.
The fold-manifest row order then defines representation ordinals `0..3359`. Any order or digest
drift stops the attempt.

The consumer does not use `neutral` or `label_cardinality` for fitting, selection, metrics or
branching. It checks their schema and ignores their values after validation.

## 6. Representation access

Each fold process opens representation matrices with NumPy read-only memory maps. It handles one
condition and one point slice at a time, casts that slice to float64, releases temporary arrays after
the fit and keeps the extraction files unchanged.

For outer fold `k`, the consumer uses:

- the shared Frozen Qwen matrix for every Frozen condition;
- `m3-s42-fk`, `m3-s43-fk` and `m3-s44-fk` for the three M3 conditions.

Inner fold `j` partitions the labels and rows inside outer fold `k`; it never switches to an
`m3-seed-fj` representation matrix. The runner stops on this binding error.

## 7. Condition and fit order

The runner uses this main condition order:

    frozen:H-1, frozen:H7, frozen:H15, frozen:H19, frozen:H20,
    frozen:H27, frozen:H31, frozen:H35, frozen:HF,
    m3-s42:H-1, m3-s42:H7, m3-s42:H15, m3-s42:H19,
    m3-s42:H20, m3-s42:H27, m3-s42:H31, m3-s42:H35, m3-s42:HF,
    m3-s43:H19, m3-s43:H27, m3-s43:HF,
    m3-s44:H19, m3-s44:H27, m3-s44:HF

For each outer fold, the runner traverses these 24 conditions in order. It traverses the four inner
fold IDs in ascending numeric order, then fits the final outer-train model. Inside each split it
traverses labels in the frozen six-label order.

One main condition and outer fold requires four inner fits plus one final fit for each label:
`24 conditions x 5 outer folds x 5 fits x 6 labels = 3,600` binary fits.

The shuffle condition order is:

    frozen:H27, frozen:HF, m3-s42:H27, m3-s42:HF,
    m3-s43:H27, m3-s43:HF, m3-s44:H27, m3-s44:HF

The runner traverses the three shuffle seeds in registered order, then these eight conditions, then
the six labels. Shuffle controls add
`3 seeds x 8 conditions x 5 outer folds x 6 labels = 720` fits. The terminal fit count is exactly
4,320. A duplicate Frozen fit, missing fit or extra fit stops the attempt.

## 8. Probe and threshold implementation

Every feature slice enters `StandardScaler(with_mean=True, with_std=True)` as float64. The scaler
fits inside the current training partition. Each label uses scikit-learn 1.7.2
`LogisticRegression` with:

    penalty='l2'
    dual=False
    C=1.0
    solver='liblinear'
    class_weight=None
    fit_intercept=True
    intercept_scaling=1.0
    tol=1e-4
    max_iter=2000
    random_state=42

The runner treats a convergence warning, a single-class fit partition, a non-finite scaler or model
value, or a probability outside `[0, 1]` as a terminal technical failure.

The threshold grid uses integer construction `arange(5, 96) / 100`, producing 91 float64 values.
The comparison rule is `probability >= threshold`. Selection uses this order with tolerance `1e-12`:

1. highest five-label Macro-F1;
2. lowest six-label Hamming loss among tied Macro-F1 values;
3. smallest absolute distance from 0.50;
4. lower threshold.

The runner never selects a threshold with outer-heldout labels.

## 9. Staged heldout-label access

`fit-fold k` reads label vectors only for the 2,688 outer-train rows. It generates inner-OOF main
probabilities, final outer-heldout main probabilities, selected thresholds and shuffled-control
outer-heldout probabilities. It seals those arrays before any process reads the 672 outer-heldout
label vectors for fold `k`.

The runner requires all five fold NPZ files and their JSON seals before `assemble` extracts any
outer-heldout label value. Assemble then reads the complete label matrix, concatenates folds in
numeric order and computes metrics, bootstrap intervals, control outcomes and seed votes. A fit
process cannot import or call assemble metric functions.

## 10. Label-shuffle control

For shuffle seed `s` and outer fold `k`, the runner constructs:

    SeedSequence([s, k])
    Generator(PCG64(seed_sequence))
    permutation(2688)

The 2,688 outer-train rows enter the RNG in ascending representation ordinal. The permutation moves
complete six-label row vectors. The runner hashes the C-order bytes of the permutation after casting
it to little-endian int64. The same permutation serves every control condition for that seed and
fold.

The runner does not run inner threshold selection for controls. It evaluates five-label Macro AP,
six-label Macro AP and per-label AP against the unchanged outer-heldout labels after all five fold
bundles are sealed.

## 11. Duplicate-component bootstrap

The bootstrap uses one `Generator(PCG64(2026082701))`. It traverses replicate IDs `0..1999` as the
outer loop and fold IDs `0..4` as the inner loop.

Within a fold, the consumer sorts unique component IDs by their UTF-8 byte sequences. For a fold
with `n` components it calls
`integers(0, n, size=n, dtype=int64, endpoint=False)`. It includes every row of each selected
component, orders rows inside a component by representation ordinal and preserves component draw
order. It concatenates sampled folds in numeric order. The same sampled row indices serve every
main and control contrast.

Each replicate must contain at least one positive and one negative for all six labels. The runner
stops at the first invalid replicate and does not discard or redraw it.

The consumer computes percentile endpoints with NumPy 2.2.6
`percentile(values, [2.5, 97.5], method='linear')` on float64 values. It does not round inputs or
endpoints before comparisons.

## 12. Metric APIs

The consumer calls scikit-learn 1.7.2 with binary labels and float64 probabilities:

- `average_precision_score(y_true, y_score, average='macro')` for five-label and six-label Macro AP;
- `average_precision_score(y_true, y_score, average='micro')` for Micro AP;
- `average_precision_score(y_true, y_score, average=None)` for per-label AP;
- `f1_score(y_true, prediction, average='macro', zero_division=0)` for five-label and six-label
  Macro-F1;
- `f1_score(y_true, prediction, average='micro', zero_division=0)` for Micro-F1;
- `f1_score(y_true, prediction, average=None, zero_division=0)` for per-label F1;
- `hamming_loss(y_true, prediction)` for Hamming loss;
- `accuracy_score(y_true, prediction)` for exact subset accuracy.

Average Precision always uses probabilities. F1, Hamming loss and subset accuracy use the frozen
outer-fold threshold. Five-label metrics index `love, joy, anger, sadness, fear` in that order.

## 13. Seed vote and control semantics

For each M3 seed and point, the consumer computes the paired 3,360-row contrast:

    delta_AP5 = AP5(M3) - AP5(Frozen)

Seed 43 or 44 passes when H27 and HF each have a positive point delta and a paired-bootstrap 95%
lower endpoint above zero. H19 does not vote. Seed 42 and all secondary metrics remain descriptive.

The valid representation states are:

- `2`: both prospective seeds pass;
- `1`: one prospective seed passes;
- `0`: neither prospective seed passes.

For each label-shuffle replicate, the consumer applies the same paired-bootstrap rule to H27 and HF.
If any of the three shuffle replicates gives both seed 43 and seed 44 a pass at both points, the
consumer records `Negative-control failure`. It sets `representation_state` to null and blocks a
later synthesis from assigning states 0, 1 or 2 from this run.

A no-effect state and a Negative-control failure are scientific outcomes. The runner records them in
`probe.json`; it does not write `failure.json` for either outcome. Technical contract violations use
`failure.json`.

## 14. Private fold artifact

Each fold writes `folds/f{k}.npz` with no compression and these arrays:

| Name | Shape | Dtype |
| --- | --- | --- |
| `outer_train_ordinals` | `(2688,)` | little-endian int32 |
| `outer_heldout_ordinals` | `(672,)` | little-endian int32 |
| `main_inner_oof_probability` | `(24, 2688, 6)` | little-endian float64 |
| `main_outer_heldout_probability` | `(24, 672, 6)` | little-endian float64 |
| `main_threshold_index` | `(24,)` | little-endian int16, values `5..95` |
| `main_n_iter` | `(24, 5, 6)` | little-endian int32 |
| `shuffle_outer_heldout_probability` | `(3, 8, 672, 6)` | little-endian float64 |
| `shuffle_n_iter` | `(3, 8, 6)` | little-endian int32 |

Arrays use C order. The NPZ contains no labels, predictions, sample IDs, component IDs, model
coefficients, scalers, representations or text.

The runner writes `folds/f{k}.json` last. The seal binds the NPZ artifact identity, fold and condition
orders, inner-fold order, source identities before and after fitting, three permutation digests, fit
counts, convergence checks, access attestations and resource use. A NPZ without its JSON seal is an
orphan. The runner does not resume or reinterpret it.

## 15. Append-only lifecycle

The formal stages run in this order:

    initialize -> fit-fold 0 -> fit-fold 1 -> fit-fold 2 ->
    fit-fold 3 -> fit-fold 4 -> assemble -> final verification -> completion

Initialize requires fresh public and private roots and creates `run-claim.json` plus private
`input-manifest.json`. Fold execution accepts only a verified, sealed prefix of the fixed fold order.
It rejects a later-fold artifact, a missing JSON seal, an orphan technical file or a terminal failure.
A sealed fold cannot run again.

Assemble requires all ten fold files. It writes private `probe-manifest.json` first and public
`probe.json` last. `probe.json` has status `CompletedAwaitingVerification`.

The final verifier does not import the runner and does not refit a probe. It validates the source and
fold artifacts, reads the sealed probability arrays and private label source, and independently
recomputes thresholds, metrics, bootstrap intervals, control outcomes and the seed vote. This
probability-only verification checks downstream computation and provenance. It does not reproduce
liblinear coefficients.

The verifier writes `verification.json`. A fresh completion invocation reruns the read-only final
verification, reproduces the same verification object and writes `probe-complete.json`. Completion
sets `exp070_complete=true`, keeps `exp071_authorized=false` and reports either a valid state or the
registered Negative-control failure.

An explicit runner exception after claim creation writes public `failure.json` once and stops the
attempt. A correction requires a new attempt ID. A verifier defect or failed verification requires a
new append-only verification attempt; no process overwrites a source result.

## 16. Public and private inventories

Static success public root:

    static.json
    static-verification.json
    no-result-complete.json

Static private root:

    input-contract-manifest.json

Formal success public root:

    run-claim.json
    probe.json
    verification.json
    probe-complete.json

Formal private root:

    input-manifest.json
    folds/f0.npz
    folds/f0.json
    folds/f1.npz
    folds/f1.json
    folds/f2.npz
    folds/f2.json
    folds/f3.npz
    folds/f3.json
    folds/f4.npz
    folds/f4.json
    probe-manifest.json

Public directories use mode `0755` and files use `0644`. Private directories use `0700` and files
use `0600`. Each regular file has one hard link. All roots reject symlinks and unexpected entries.
The consumer private root cannot exceed 512 MiB.

Public JSON can contain aggregate metrics, per-label aggregate metrics, bootstrap endpoints, seed
votes, the representation state, resource counts and artifact identities. It cannot contain row IDs,
fold-row membership, labels, probabilities, predictions, component draws, permutation arrays,
coefficients, scalers, representations or text.

## 17. Stop rules

The runner or verifier stops on:

- parent, source snapshot, config, method, implementation, environment, mode or inventory drift;
- row alignment, component isolation, matrix-to-outer-fold binding or point-order drift;
- source mutation, writable representation mapping, validation, test or raw-text access;
- single-class fitting, convergence warning, non-finite value, probability-range or shape failure;
- wrong fit count, wrong RNG traversal, invalid bootstrap replicate or resource breach;
- public private-data leakage, symlink, multiple hard links, overwrite or out-of-order artifact;
- result inspection used to change a layer, seed, fold, C, solver, tolerance, metric or RNG rule.

The runner does not recover a technical failure by changing the method. The next experiment remains
closed until this consumer reaches independently verified completion.
