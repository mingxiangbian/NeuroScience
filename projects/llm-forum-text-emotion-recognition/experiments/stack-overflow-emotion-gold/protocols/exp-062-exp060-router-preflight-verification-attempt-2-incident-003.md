# EXP-062 / EXP-060 Router Preflight Verification Attempt 2 — Incident 003

## Authorization and boundary

The user authorized exactly one append-only Incident 003 recovery verification
attempt.  This protocol does not authorize rerunning the no-result preflight
runner, formal router analysis, primary-gate publication, attempt selection,
validation/test access, model loading, raw-text access, or private array-value
loading.

The failed verifier invocation is terminal.  Its canonical Attempt-1 sidecars
remain absent.  Attempt-1 config, run, contract, frozen sources, upstreams, and
private-input metadata are immutable predecessor evidence.

## Incident record

The failed command exited nonzero before launching any child test and before any
sidecar writer.  The public failure classification is:

- incident: `003`
- verification attempt: `1`
- failure stage: `child_test_preflight`
- failure code: `missing_repo_root`
- exception type: `NameError`
- canonical verification sidecar: absent
- canonical verification summary: absent

The root cause is clerical governance code: the frozen verifier refers to
`REPO_ROOT` in `_run_child_test`, but the module does not define that global.
No scientific code or result was executed.

## Recovery namespace

The only recovery output root is:

`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-062-seed-44-router-replication/attempt-1/router-preflight-verification-attempt-2`

Any lexical presence of this root is a durable claim and blocks every later
invocation.  Nothing may be deleted, repaired, resumed, or overwritten.

A clean Passed tree contains exactly:

- `verification-attempt-2-claim.json`
- `attempt-1-failure-seal.json`
- `verification.json`
- `VERIFICATION-SUMMARY.md`
- `verification-attempt-2-terminal.json`
- `frozen-sources/`

A clean Failed tree contains exactly:

- `verification-attempt-2-claim.json`
- `attempt-1-failure-seal.json`
- `attempt-2-failure.json`
- `FAILURE-SUMMARY.md`
- `frozen-sources/`

Partial trees, root-only trees, and a Passed candidate accompanied by a failure
record are terminal Failed/incomplete states.  A failure record is authoritative
over every captured or materialized Passed candidate.

## Claim state machine

All config, source, predecessor, header-only, resource, privacy, mode, hash,
absence, and output-path checks occur before claim.  Claim begins at root mkdir.
The claim JSON is the first file written.  Frozen sources and the Attempt-1
failure seal follow with create-once writes.

After claim, any `Exception` writes `attempt-2-failure.json` first when absent,
then `FAILURE-SUMMARY.md`.  Neither raw exception text nor private values may be
published.  If summary creation fails, the JSON remains the terminal seal.  A
`KeyboardInterrupt` or `SystemExit` is not converted; the claimed partial root
still blocks retry.

After a syntactically complete Passed tree is published and postchecked, the
wrapper must perform two final gates before returning or printing success:

1. `final_state_audit`: recompute the complete Attempt-1 public, frozen-source,
   upstream, private metadata/hash/header, live-source, downstream-absence, and
   pyc snapshot and require exact typed equality with both pre-call snapshots;
2. `final_resource_audit`: take a fresh outer wall/RSS/cost/forward sample that
   includes publication and postcheck and require the 300-second/2.0-GB/zero-cost
   contract.

Failure at either gate writes the distinct authoritative failure JSON and
summary.  The already materialized Passed candidate may remain, but the process
exits nonzero and the namespace is permanently non-retryable.  The allowlisted
stage/code pairs are `final_state_audit/terminal_state_drift` and
`final_resource_audit/terminal_resource_budget_exceeded`.  Terminal-seal
publication and postcheck use the additional allowlisted pairs
`terminal_seal/terminal_success_seal_failure` and
`terminal_postcheck/terminal_success_postcheck_failure`.

After both gates pass, the wrapper writes
`verification-attempt-2-terminal.json` exactly once.  This terminal-success
seal binds the materialized Passed JSON and summary hashes, the fresh terminal
resource sample, the final physical-state digest, `formal_gate_authorized:
false`, and the claim boundary.  A Passed candidate tree without a valid
terminal-success seal is incomplete and must never be consumed as Passed.  The
seal is the final write; success may be reported only after its exact
inventory/content/mode postcheck.

## Verified-bytes execution and exact patch ledger

The recovery verifier reads the frozen original verifier through a held
`O_NOFOLLOW` descriptor and requires the frozen and canonical live copies to be
regular one-link mode-0644 files with identical 84,331 bytes and SHA-256
`31d985d37940994f8caabcb065a426d92afe710d6ecaed8a22a33511f8ef870c`.

It compiles and executes only those held bytes in an isolated module.  Before
execution, `__file__` is set to the canonical live verifier path so the frozen
module reconstructs the intended `SCRIPT_DIR` and `PROJECT_ROOT`.

The exact temporary patch surface is:

1. define missing `REPO_ROOT = PROJECT_ROOT.parents[1]`;
2. replace `_create_bytes_once` with a pure in-memory exact-two-call capture;
3. replace `_assert_replication_preflight_tree` with a virtual namespace hook.

The virtual hook delegates every `verified=False` call to the original function.
For `verified=True`, it reuses the original physical unverified-tree audit,
requires canonical sidecars to remain absent, requires the two captured intended
sidecars in JSON-then-summary order with mode 0644, and proves that the effective
physical-plus-virtual manifest equals the original verified manifest.  It does
not patch checks, clocks, resources, `os.scandir`, or science logic.

All three patched attributes are restored in `finally`.  Because `REPO_ROOT`
was absent, it is deleted.  The isolated module is destroyed after use.

## Captured candidate contract

The original `verify_replication_preflight` is called exactly once.  Its stdout
and stderr are captured in memory.  Success requires:

- return code `0`;
- exactly one terminal stdout JSON with Passed/20/0;
- empty stderr;
- exact JSON-then-summary writer calls;
- one delegated unverified-tree audit and one equivalent virtual verified-tree
  audit;
- captured verification schema, identity, exact ordered 20 checks, all true,
  no-result claims, resources, artifacts, privacy, and deterministic summary;
- physical Attempt-1 public/private/upstream/source/pyc snapshots unchanged.

Captured bytes are candidates only.  They are never written, linked, or copied
to the canonical Attempt-1 sidecar paths.

## Attempt-2 Passed envelope

Schema: `exp-router-preflight-verification-incident-003-attempt-2-v1`.

Exact top-level keys:

`schema_version, incident_id, verification_attempt, experiment_id,
replication_parent_experiment_id, run_id, attempt_id, model_seed, seed_contract,
rq_id, scope, status, verified_at_utc, patch_ledger, original_artifacts,
physical_invariants, virtual_namespace, captured_candidate, checks, passed_count,
failed_count, resources, formal_gate_authorized, claim_boundary`

The scope is `preflight-recovery`.  The status is `Passed`.  The envelope has
the following required typed fields:

- `namespace_virtualized: true`
- `original_postwrite_audit: equivalent_virtual_overlay`
- `canonical_verification_written: false`
- `formal_gate_authorized: false`

Recovery checks are exact, ordered, unique, and all true:

1. `recovery.incident_config`
2. `recovery.attempt1_failure`
3. `recovery.canonical_absence`
4. `recovery.runner_seal`
5. `recovery.contract`
6. `recovery.frozen_inventory`
7. `recovery.original_verifier_bytes`
8. `recovery.repo_root_injection`
9. `recovery.writer_capture`
10. `recovery.virtual_tree_audit`
11. `recovery.original_return`
12. `recovery.original_checks_20`
13. `recovery.no_result_claims`
14. `recovery.resources_privacy`
15. `recovery.physical_invariants`
16. `recovery.downstream_absence`

The captured candidate record contains its raw byte count/SHA-256, parsed
canonical digest, and captured-summary byte count/SHA-256.  It is not a
canonical verification artifact.

## Attempt-2 failure schema

Schema: `exp-router-preflight-verification-incident-003-attempt-2-failure-v1`.

Exact top-level keys:

`schema_version, incident_id, verification_attempt, experiment_id,
replication_parent_experiment_id, run_id, attempt_id, model_seed, seed_contract,
rq_id, scope, status, failed_at_utc, failure_stage, failure_code,
exception_type, completed_checks, original_artifacts, resources,
formal_gate_authorized, claim_boundary`

Failure stage/code/exception values are allowlisted.  No exception message,
traceback, row-level field, or private value is published.

## Other exact records

- Claim schema: `exp-router-preflight-verification-incident-003-attempt-2-claim-v1`.
- Terminal-success schema:
  `exp-router-preflight-verification-incident-003-attempt-2-terminal-v1`.

Terminal-success exact top-level keys:

`schema_version, incident_id, verification_attempt, experiment_id,
replication_parent_experiment_id, run_id, attempt_id, model_seed, seed_contract,
rq_id, scope, status, completed_at_utc, verification, summary,
terminal_resources, terminal_state_sha256, formal_gate_authorized,
claim_boundary`

`terminal_state_sha256` must equal both Passed-envelope
`physical_invariants.before_sha256` and `after_sha256`.  Terminal wall time and
peak RSS must be finite, in budget, and monotonically no smaller than the
pre-publication Passed-envelope sample.
- Attempt-1 failure-seal schema:
  `exp-router-preflight-verification-incident-003-attempt-1-failure-v1`.
- Incident config schema:
  `exp-router-preflight-verification-incident-003-attempt-2-config-v1`.

All JSON uses sorted keys, two-space indentation, ASCII escaping, no NaN, and
one terminal newline.  Summaries are deterministic functions of their JSON.

## Resources, privacy, and filesystem

The outer attempt is limited to 300 wall seconds, 2.0 GB peak RSS using the
normalized maximum of self and children, and zero API/GPU/model-forward use.
Child tests retain `-B`, `PYTHONDONTWRITEBYTECODE=1`, sixty-second timeouts, and
no-pyc invariants.  Public payloads receive the complete 25-key sensitive-field
scan.  Private data is limited to frozen record/hash/mode and NPZ/NPY header
inspection; `np.load` is forbidden.

The terminal resource sample, rather than the earlier pre-publication sample,
is authoritative for launch success.

Every directory is a real mode-0755 directory.  Every file is a regular,
one-link mode-0644 file.  Reads and writes require `O_NOFOLLOW`; writes use
`O_EXCL`, `fsync`, FD mode/link/type checks, and post-path identity checks.

## Formal remains blocked

`formal_gate_authorized` is always false.  The existing v3 formal launcher still
requires the absent canonical Attempt-1 verification and must continue to
reject.  A Passed recovery envelope requires a separately authorized,
Incident-003-aware formal consumer and config.  There is no alias, copy,
fallback, or implicit promotion to canonical verification.
