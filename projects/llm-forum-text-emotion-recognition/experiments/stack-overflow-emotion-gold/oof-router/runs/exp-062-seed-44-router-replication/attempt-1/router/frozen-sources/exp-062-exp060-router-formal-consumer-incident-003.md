# EXP-062 / EXP-060 Incident 003 Formal Consumer Protocol

Date: 2026-08-24

Status: implementation and synthetic verification authorized; formal execution not authorized

## Goal

Add a governance-only consumer for a future seed-44 EXP-060 formal router run after
Incident 003. The consumer may recognize the append-only lineage

```text
Attempt-1 verifier: Failed (missing REPO_ROOT; canonical sidecars absent)
    -> Incident 003 verification Attempt-2: Passed
    -> terminal success seal: Complete
```

without changing the frozen router science, the verified v3 launchers, the
Attempt-1 tree, or the Incident 003 recovery tree.

This protocol authorizes only the four source files named below, their synthetic
tests, and their byte/hash freeze. It does not authorize creation of a formal
config or execution of `run`, `final`, `complete`, `completion`, a primary gate,
or selection.

## Non-goals

- No router fit, feature construction, metric computation, bootstrap, primary
  gate, completion, finalizer, or selection is executed in this change.
- No private NPZ array values are loaded.
- No canonical Attempt-1 preflight verification or summary is synthesized.
- No existing v2/v3 runner, verifier, test, config, protocol, run artifact, or
  Incident 003 artifact is edited.
- No canonical or workspace formal config is written. Synthetic tests may use a
  temporary config outside the workspace and must remove it automatically.

## Authorized source inventory

The implementation inventory for this change is exactly:

1. `protocols/exp-062-exp060-router-formal-consumer-incident-003.md`
2. `oof-router/run_exp060_router_v4_incident003.py`
3. `oof-router/verify_exp060_router_v4_incident003.py`
4. `oof-router/tests/test_exp060_router_v4_incident003.py`

The future formal config is not part of this authorization.

## Architecture

Each v4 launcher independently opens the corresponding live and Attempt-1
frozen v3 launcher with `O_NOFOLLOW`, requires a regular one-link `0644` file,
holds and rechecks the descriptor identity, and requires byte equality plus the
frozen SHA-256. It compiles those held bytes with the canonical live v3
`__file__` in an isolated `ModuleType`.

The v4 launcher temporarily changes exactly two v3 module attributes:

1. `FORMAL_CONFIG_SCHEMA` to
   `exp-router-replication-config-v4-incident-003`;
2. `validate_launch_contract` to that launcher's independent recovery-aware
   adapter.

Both attributes are restored in `finally`, including for `KeyboardInterrupt`,
`SystemExit`, and other `BaseException` paths. The isolated module is not added
to `sys.modules`. The v3 `execute` function is called exactly once. The verifier
launcher loads only the frozen v3 verifier and never imports a runner.

The frozen v3 launcher remains responsible for its already-approved adaptation
of the base v2 schema/prerequisite constants and, for verification, its atomic
writers. Those are not additional v4 patches.

## Future config contract

After separate formal authorization, one canonical config may be frozen at:

`oof-router/configs/exp-062-seed-44-router-replication-router-formal-attempt-1-incident-003.json`

Its schema is `exp-router-replication-config-v4-incident-003`. Its top-level
inventory is the v3 formal inventory plus one exact `preflight_recovery` object.

The future implementation inventory is exact11:

- original protocol;
- frozen base runner, verifier, and tests;
- frozen v3 runner launcher, verifier launcher, and launcher tests;
- this Incident 003 consumer protocol;
- v4 runner launcher, verifier launcher, and launcher tests.

All basenames must be unique. The future formal frozen-source directory must
therefore contain exactly the config plus those eleven records.

The prerequisite inventory remains exact5. The
`exp060_preflight_verification` record points to the Incident 003 Attempt-2
`verification.json`. Claim, Attempt-1 failure seal, summary, terminal seal, and
Incident implementation records are carried by `preflight_recovery`; adding a
sixth prerequisite is forbidden because it would expand the approved patch
surface.

## Adapter invariants

The adapter independently reproduces the full v3 formal launch contract:

- registered EXP-062 / seed-44 / attempt-1 / RQ-S3 identity;
- canonical config, output, input, command, and implementation paths;
- explicit formal authorization and forbidden validation/test/model/raw-text
  access;
- exact runtime, artifact, resource, provenance, and privacy contracts;
- exact scientific contract, including fourteen features, inner-3/outer-4
  threshold fitting, five policies, three deployable policies, and the frozen
  logistic-router primary policy at nominal 15 percent;
- exact upstream and paired-OOF artifact binding, using byte hashing and header
  metadata only, never `numpy.load` or private array values;
- exact old-seven and future exact-eleven implementation lineage.

It then independently validates the Incident 003 lineage:

- Attempt-1 config, run, contract, frozen verifier, and failure seal;
- failure outcome `missing_repo_root`, `NameError`, exit code 1, and absent
  canonical Attempt-1 verifier sidecars;
- the exact six-entry Attempt-2 terminal tree and exact four frozen sources;
- claim, Passed 16/16 recovery checks, captured original Passed 20/20 checks,
  deterministic summaries, exact patch ledger, virtual namespace audit,
  physical invariant digest, and resource records;
- terminal `Complete` seal bound to the actual verification and summary records;
- no Attempt-2 failure artifact and no selection;
- `formal_gate_authorized` remains false in all recovery evidence.

Recovery evidence does not grant formal authorization. A future formal config
must carry the exact, separately obtained user authorization basis frozen by
the wrappers. Merely defining that future string in source is not evidence that
the authorization has already been given.

## State and failure contract

The recovery adapter is read-only and is valid both before and after a v3 base
call. Stage-specific output checks are performed outside the adapter.

Before and after the single v3 call, each wrapper snapshots the immutable
Attempt-1, Incident 003, upstream, implementation, and paired-input records.
Only the exact append-only outputs allowed by the selected scope may appear;
selection must remain absent.

Formal scopes use a separate append-only governance namespace at
`attempt-1/router-formal-consumer-v4/`. Each scope writes its claim before the
v3 call. After substantive post-state and resource checks it writes a Complete
terminal seal containing the pre-publication resource sample, then performs a
fresh terminal-publication resource and persistence audit. The seal-writing
overhead is covered by that fresh gate but is not retroactively inserted into
the immutable Complete seal. If the terminal audit fails, a Failed seal is
appended alongside Complete and is authoritative; the later exact-manifest
consumer rejects the coexistence. An ordinary exception writes a non-sensitive Failed seal;
process-control exceptions leave a claimed-incomplete state. A root-only or
partially written claim is also terminal incomplete. Every later scope must
rehash the current immutable state and consume exact Complete seals for all
prior scopes; any failure, partial, extra file, wrong digest, or missing seal
blocks both retry and advancement. These governance files are outside the
frozen v3 `router/` manifest.

The outer v4 wall/memory budget, including validation and postchecks, is at most
1800 seconds and 4 GB. API cost, GPU cost, and model-forward runs are zero.

Any nonzero result or exception, including a post-state or outer-budget failure,
makes that scope terminal failed/incomplete. The caller must stop: it may not
retry the scope or advance to the next scope merely because a lower-layer
sidecar exists. The wrappers never delete, overwrite, or repair artifacts.

## Required tests

- held live/frozen byte, path, mode, inode, link-count, size, and SHA checks;
- exact-two patch surface, exact-once v3 call, and restoration under ordinary
  exceptions and `BaseException`;
- direct v3 rejection of the v4 schema;
- independent runner/verifier validation of identity, authorization, commands,
  exact11 implementation, exact5 prerequisites, science, typed numbers, NaN,
  resource, privacy, and canonical paths;
- Incident tree, claim, failure seal, Passed 16, captured 20, summary, terminal,
  physical-state/resource, failure-coexistence, and canonical-sidecar tampering;
- pre/post adapter calls with permitted stage transitions;
- restrictive umask, public/private modes, no-clobber behavior, and terminal
  nonzero stop semantics;
- AST prohibition of runner import and `numpy.load` in the verifier;
- regression suites for frozen base, v3, preflight, Incident 003 recovery, and
  existing finalizers.

All tests in this change are synthetic or read-only contract checks. They must
run with bytecode generation disabled and must not invoke a real formal scope.
