# EXP-070 Formal-Probe Verification Attempt 2

- Experiment ID: `EXP-070`
- Run ID: `exp-070-layerwise-probe-formal-probe`
- Source attempt: `formal-probe-attempt-1`
- Verification attempt: `2`
- Date: `2026-08-29`
- Stage: `verifier-only public-privacy recovery`
- Status: `Registered; static gate only`

## 1. Incident

The formal probe producer completed `initialize`, five `fit-fold` stages and `assemble`. Its public
run reports `CompletedAwaitingVerification`. The frozen verifier has not executed, and the source
root contains no `verification.json`, `probe-complete.json` or failed verification seal.

The frozen verifier's `_public_sensitive` function scans every public string for the substring
`component-`. The exact claim boundary bound by the formal config contains the method term
`component-disjoint` once. The function therefore classifies the public `probe.json` as sensitive
before the verifier performs its probability-only replay.

The claim boundary contains no sample identifier, component identifier, label vector, probability
vector, prediction vector, private path or absolute user path. The source public files expose no
private row-level value. This incident records a lexical false positive, not a privacy leak or an
experimental failure.

The same predicate also checks the frozen verifier's failure payload. Because that payload carries
the same claim boundary, the frozen failure recorder would decline to write a failure seal. The
absence of a failed `verification.json` does not indicate that attempt 1 passed.

## 2. Recovery rule

The recovery consumer held-loads the exact frozen verifier bytes. It replaces only the loaded
module's `_public_sensitive` binding in memory.

The replacement applies one exception to a complete root public payload:

1. The payload must be a mapping with the exact root path `$.claim_boundary`.
2. The root value must equal the frozen source claim boundary byte for byte and match its frozen
   SHA-256.
3. The adapter removes only that root field from a shallow copy, then passes the remaining payload
   to the original predicate.
4. A missing, nested, renamed, non-string or altered boundary fails closed. Every other value,
   including the same string outside the exact root path, goes to the original predicate unchanged.

The adapter restores the original function after success, ordinary exceptions and
`BaseException`. It does not edit the source verifier, config, protocol, runner, tests, public run,
private manifests or fold bundles.

The recovery calls the frozen verifier's read-only validation, recomputation and payload builders;
it does not call the frozen CLI or `verify_formal`. A write guard rejects any source
`create_json_once` call. During completion replay, an in-memory artifact adapter supplies the
virtual source-verification identity required by the frozen completion builder. The source attempt
remains unchanged. The recovery consumer writes its own verification and completion records in a
fresh root.

## 3. Preserved verifier semantics

The recovery calls the frozen probability-only formal verifier. It retains the frozen:

- source, config, method, row and fold identity checks;
- five sealed fold-bundle checks;
- threshold, metric, negative-control and bootstrap recomputation;
- representation-state decision rule;
- numeric tolerances, resource ceilings and forbidden-import checks;
- public forbidden-key, private-path, sample-marker and component-identifier checks outside the
  exact source claim boundary exception.

The recovery may read the sealed probabilities and train-only label source required by the frozen
formal verifier. It may not fit a probe, read representation values, import the producer, load a
model, execute a forward pass, access validation or test data, change a threshold, change a
tolerance or select a new result.

## 4. Frozen source snapshot

The recovery config binds the following source files by project-relative path, bytes, mode and
SHA-256:

- the formal config, formal protocol, runner, verifier and tests;
- public `run-claim.json` and `probe.json`;
- private `input-manifest.json` and `probe-manifest.json`;
- `f0` through `f4`, with one JSON seal and one NPZ bundle per fold.

The source public inventory must contain exactly `run-claim.json` and `probe.json`. The source
private inventory must contain exactly the two manifests, the `folds` directory and its ten bound
files. Public files use mode `0644`; private files use mode `0600`. Roots use modes `0755` and
`0700`. No additional empty or populated directory may exist below either source or recovery root.
The consumer rejects symbolic links, special files and link counts other than one.

Before formal replay, the consumer computes a canonical digest over the complete source public and
private inventories and writes `source-snapshot-claim.json`. It recomputes the digest after replay
and requires equality.

## 5. Four stages

### 5.1 `static-verify`

This no-result stage checks:

- config and implementation identities;
- exact recovery protocol/tests records and verifier self path;
- exact source inventories, modes, link counts and hashes;
- the source status `CompletedAwaitingVerification`;
- absence of source verification, completion and failure files;
- one exact root boundary path, value and SHA, plus the single incident-token occurrence;
- original-predicate failure on the frozen claim boundary;
- adapter acceptance of that exact boundary;
- rejection of near misses, real reserved markers, forbidden keys and private paths;
- write capture, virtual inventory, patch restoration and source immutability;
- synthetic tests under the frozen environment;
- exact Python executable, Python/package versions, architecture, thread variables and
  `PYTHONNOUSERSITE=1`;
- absence of label, probability, representation, validation, test, model and forward access.

Success writes only `static-verification.json` in the fresh preflight root. Failure writes a Failed
`static-verification.json` when the output contract remains safe, then stops.

### 5.2 `static-complete`

This stage reruns the static checks and requires exact object and byte equality with an existing
Passed `static-verification.json`. It writes `no-result-complete.json`, which records
`formal_verification_authorized=true`, `formal_probe_complete=false`, `exp070_complete=false` and
`exp071_authorized=false`.

The current step stops after this stage. It does not execute either formal stage.

### 5.3 `formal-verify`

This stage requires the exact no-result completion. It writes `source-snapshot-claim.json` before
reading label or probability values, runs the full frozen probability-only verifier under the
single privacy adapter, captures the source verification payload in memory, checks the unchanged
snapshot and writes the recovery `verification.json`.

The recovery verification binds the source claim, run, private manifests, fold bundles, captured
payload digest, recomputed result digest, check inventory and access record. It reports
`source_original_verifier_unexecuted=true`, `probe_refit=false`, `source_mutated=false` and
`exp071_authorized=false`.

### 5.4 `formal-complete`

This stage requires an exact Passed recovery verification prefix. It reruns the complete formal
replay, reconstructs the expected recovery verification and requires object and canonical-byte
equality. It then writes `probe-complete.json`.

The completion may set:

```text
formal_probe_complete = true
exp070_complete = true
exp071_authorized = false
source_mutated = false
source_original_verifier_unexecuted = true
```

Completion does not authorize EXP-071.

## 6. Output roots

Static no-result root:

```text
phase-b-representation/runs/exp-070-layerwise-probes/
  formal-probe-verification-attempt-2-preflight/
  ├── static-verification.json
  └── no-result-complete.json
```

Formal recovery root:

```text
phase-b-representation/runs/exp-070-layerwise-probes/
  formal-probe-verification-attempt-2/
  ├── source-snapshot-claim.json
  ├── verification.json
  └── probe-complete.json
```

The recovery creates no private output root.

## 7. Failure and resume rules

- Any nonzero result, Failed status, identity drift, hash drift, mode drift, link drift, inventory
  drift, source change, resource breach or forbidden access stops the sequence.
- A static failure writes no no-result completion.
- A formal failure may preserve the snapshot claim and a Failed recovery verification. It writes no
  probe completion.
- A process that stops after a Passed recovery verification may resume only through
  `formal-complete`. That stage performs the full replay again before writing completion.
- The consumer never writes into the source public or private root.

## 8. Claim boundary

This recovery corrects one exact public-privacy method-token false positive and replays the frozen
probability-only verifier. It adds no alternate metric, experimental result, representation
mechanism, emotion-neuron claim, human-mechanism claim or EXP-071 authorization.
