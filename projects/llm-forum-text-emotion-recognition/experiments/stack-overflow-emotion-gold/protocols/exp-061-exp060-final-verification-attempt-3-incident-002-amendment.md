# EXP-061 / EXP-060 Router Verification Attempt 3 — Incident 002

Status: **Frozen before execution**  
Incident: `002`  
Verification attempt: `3`  
Scope: seed-43 train-OOF router verification recovery only

## 1. Authorization and terminal lineage

The user explicitly authorized registration of Incident 002 and one append-only
verification attempt 3.  This authorization does not reopen or replace either
earlier attempt:

1. Attempt 1 remains `Failed` with its original `verification.json` and
   `VERIFICATION-SUMMARY.md` bytes and private modes.
2. Attempt 2 remains terminal `Failed` with
   `verification-attempt-2.json` and
   `VERIFICATION-SUMMARY-ATTEMPT-2.md`.
3. All six Incident-001 implementation files remain frozen: its protocol,
   machine config, recovery verifier, recovery tests, finalizer, and finalizer
   tests.
4. Attempt 3 may create only `verification-attempt-3.json` and
   `VERIFICATION-SUMMARY-ATTEMPT-3.md` during its `final` scope.
5. `router-complete.json` and run-level `selected-attempt.json` remain absent
   until a Passed Attempt 3 is independently consumed by their dedicated
   scopes.

Any Attempt-3 build failure is terminal at the same paths.  The verifier writes
the exact non-sensitive Failed JSON first and its deterministic summary second,
then rejects every retry.  `KeyboardInterrupt` and `SystemExit` are not caught.

## 2. Incident classification

Incident 002 is a verification-harness path canonicalization defect.  On macOS,
`TMPDIR` is lexically under `/var`, while `/var` resolves through the system
symlink to `/private/var`.  Incident-001 created a mirror from the lexical
temporary path, but the frozen base verifier derived `SCRIPT_DIR` with
`Path(__file__).resolve()`.  It then received a lexical `/var/.../configs/...`
argument and compared that parent with a resolved `/private/var/.../configs`
directory.  The canonical-config guard rejected the alias before reading the
config or any private array.

This incident does not change any scientific result, formal config, runner,
base verifier, overlay, mirror source manifest, recomputation rule, policy
inventory, threshold, seed, or claim boundary.

## 3. Sole recovery behavior change

The Attempt-3 wrapper preserves the Incident-001 mirror implementation with one
semantic correction:

```text
base verifier config := module.PROJECT_ROOT / FORMAL_CONFIG_REL
```

The loaded verifier must report that its resolved `PROJECT_ROOT` equals the
temporary root after resolution.  The temporary-copy mechanics remain
byte-for-byte semantically identical to Incident 001; only the config argument
uses the loaded verifier's canonical root.  No lexical `/var` alias may enter
artifact records or the config argument.  The frozen base verifier remains byte-identical and the
Incident-001 `/router/policies` SHA-bound overlay remains the only config
overlay.

## 4. Preflight contract

Before Mirror A, the Attempt-3 verifier must independently require all of the
following:

- Attempt-1 Failed verification and summary match their exact canonical paths,
  bytes, SHA-256 values, schemas, statuses, check inventory, modes, and link
  counts.
- Attempt-2 Failed verification and deterministic summary match their exact
  canonical paths, bytes, SHA-256 values, `failure-v1` schema, sealed failure
  code/stage, mode `0644`, and link count one.
- The six Incident-001 files and six Incident-002 files match the machine config
  records at their exact canonical paths.
- The original formal config, router run, selected operating point, paired OOF,
  and private router OOF match their frozen records.
- The authorized sixteen public mode targets remain exactly two directories at
  `0755` and fourteen regular, non-symlink, single-link files at `0644`, with
  their frozen bytes and SHA-256 values.
- The public content tree digest is unchanged.  Only the five exact router-root
  governance paths for Attempt-2 JSON/summary, Attempt-3 JSON/summary, and
  `router-complete.json` are excluded; nested files with the same basenames are
  included.
- Private artifact hashes and the `0700` directory / `0600` file mode contract
  are unchanged.  Preflight hashes files but does not inspect private array
  values.
- Attempt-3 JSON/summary, completion, and selection paths are all absent under
  `lexists` semantics.

A preflight failure creates no new artifact.

## 5. Independent verification contract

Formal Attempt 3 runs the unchanged frozen base verifier in two fresh,
separately resolved mirrors built from the same exact 30-file source manifest:

- Mirror A uses the unchanged frozen config and must produce exactly 4434 checks
  in the Attempt-1 order, with 4433 Passed and the sole failure
  `config.router`.
- Mirror B uses the same base verifier and source manifest.  A module-local JSON
  proxy may apply the already registered Incident-001 overlay exactly once and
  only to a parse whose bytes equal the frozen formal-config SHA.  Mirror B must
  produce the same 4434 check names/order with all checks Passed.
- The proxy must observe two matching config parses, apply once, and leave the
  frozen config bytes unchanged.
- Both mirrors must be copy-only, canonical, symlink-free, hardlink-free,
  mode-bound, distinct, and cleaned after use.
- Exactly two mirror executions are permitted, sequentially Mirror A then
  Mirror B.  Each inherits the frozen formal-config verification wall budget of
  1800 seconds and peak-memory budget of 4.0 GB; the corresponding base checks,
  API cost, GPU cost, and model-forward checks must Pass.  Copy/import/contract
  validation receives no separate budget extension.
- The analysis runner is never imported.  No validation/test input, raw text,
  model loading, model forward run, API call, GPU run, or new scientific
  analysis is authorized.

The two mirrors may read the already authorized train-OOF private arrays only
during the single formal Attempt-3 execution.  Tests before formal execution
must stop after the real macOS alias/canonical-config integration guard and must
not call the base verifier or `numpy.load`.

## 6. Attempt-3 artifacts

A Passed Attempt 3 uses schema
`exp-router-formal-verification-attempt-3-v1`, contains exactly 4434 all-true
main checks, the exact nine-key independence inventory, the unchanged four
verified scientific artifacts, and Incident-002 recovery evidence.  Recovery
evidence binds:

- Attempt-1 Failed JSON and summary;
- all Incident-001 records;
- Attempt-2 Failed JSON and summary;
- the Incident-002 config, protocol, verifier, tests, dedicated finalizer, and
  dedicated finalizer tests;
- the unique path canonicalization contract;
- the unchanged Incident-001 overlay;
- normalized public state, public content digest, and private invariant;
- complete Mirror-A and Mirror-B evidence and exact recovery checks.

The Passed JSON and summary are append-only regular, non-symlink, single-link
files at mode `0644`.  Public payloads are scanned recursively against the
frozen 25-key sensitive-field inventory.

## 7. Completion and dedicated finalizer

Only a Passed Attempt 3 allows the Attempt-3 verifier's `complete` scope to
create canonical `router-complete.json` with schema
`exp-router-completion-v3`.  The completion preserves the standard five router
artifacts while adding a strict recovery lineage that binds Failed → Failed →
Passed and both incidents' implementation records.  Its timestamp must follow
Attempt 3.  The fully constructed completion must pass the same strict
completion validator before the append-only writer is called; validation
failure leaves `router-complete.json` absent.

Only `finalize_router_replication_attempt3.py` may consume this completion.  The
dedicated finalizer is standalone: it does not import the old generic finalizer,
any verifier, or any runner.  It accepts only `EXP-061` and `attempt-1`,
independently validates the OOF and calibration completions plus the complete
Incident-002 recovery chain, and creates the canonical run-level
`selected-attempt.json` once.  The selection records an exact ordered attempt
chain:

```text
Attempt 1: Failed (4417 / 4434, 17 failures)
Attempt 2: Failed (0 / 1, deterministic verification_build failure)
Attempt 3: Passed (4434 / 4434)
```

Chronology must satisfy Attempt 1 ≤ Attempt 2 ≤ Attempt 3 ≤ completion ≤
selection.  The selection binds the dedicated finalizer's own bytes and hash,
all three completion records, the stage artifacts, both incidents, and the
same privacy boundary.  The writer uses an adjacent `O_EXCL` temporary file,
explicit `fchmod(0644)`, fsync, single-link identity checks, and never
overwrites.

## 8. Execution order and stop conditions

After implementation freeze and independent approval, the only permitted order
is:

1. Attempt-3 `final` exactly once.
2. Stop immediately if it is not Passed or exits non-zero.
3. Attempt-3 `complete`.
4. Attempt-3 `completion` verification; stop unless Passed.
5. Dedicated Incident-002 finalizer.

There is no normalization scope in Incident 002.  There is no fallback to the
Incident-001 verifier or the old generic finalizer.  No step may overwrite any
earlier artifact.
