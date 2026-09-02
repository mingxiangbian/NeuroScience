# EXP-061 / EXP-060 Final Verification Attempt-2 Amendment 001

- Parent experiment: `EXP-061`
- Stage: `EXP-060` seed-43 router final verification
- Frozen stage identity: `pre-qwen-router-replication`
- Frozen research question: `RQ-S3`
- Incident: `001`
- Registered: 2026-08-21
- User authorization: explicit, verification-incident recovery only
- Scientific analysis rerun authorized: no
- Validation/test/model/raw-text access authorized: no
- Private artifact mutation authorized: no

## Incident

The seed-43 router analyzer completed once and wrote the frozen train-OOF result. The
first independent final verifier then completed all recomputation and wrote an
append-only `Failed` result:

- `verification.json`: `69057b2f1af3ab2964f6d6a5037d1cc28a9a1c3017d68be44c872a71d44a5d62`;
- `VERIFICATION-SUMMARY.md`: `f783230f779fcb149def1cca1c0b0b8cdce8c659a2dbd0aa6a319c7971b1822e`;
- passed checks: `4417`;
- failed checks: `17`.

Sixteen failures were public-mode mismatches caused by running under a restrictive
umask: the router public root and `frozen-sources` directory were `0700` instead of
`0755`, and the fourteen registered public result files were `0600` instead of
`0644`. The private router root and `router-oof.npz` already passed their required
`0700` / `0600` checks.

The remaining failure, `config.router`, exposed one clerical config misencoding. The
parent protocol freezes five compared policies, R0 through R4:

```text
m1_only
m3_only
m1_max_entropy
m1_threshold_proximity
logistic_router
```

The formal config correctly records the three deployable policies in
`/router/deployable_policy_order`, but the same three-item list was also copied into
the broader `/router/policies` field. The effective value of `/router/policies` is
therefore corrected from the exact three-item deployable list to the exact five-item
R0--R4 list. `deployable_policy_order` remains unchanged.

This is not a verifier defect. The original verifier correctly enforced the frozen
five-policy comparison. It is also not a scientific change: the analyzer does not
read either config list to determine computation; it constructs R0/R1 explicitly and
computes R2--R4 from its frozen deployable order. The first verifier independently
recomputed and matched the 26-row call-rate table, whose policy inventory contains
all five R0--R4 policies, and matched the public feature contract whose policy order
also contains all five. The selected operating point correctly contains only the
three deployable policies.

## Preserved Evidence

The following artifacts are immutable inputs to attempt 2:

- formal config: `d74beb9b3dd1140be0215e29e87b71b2a25f332682420a2883af7aa867cd566b`;
- router `run.json`: `199249d6d7a1cc1e8fb2daab43ade9ca63deabc3a25dc8bdf3f1a3370c677884`;
- selected operating point: `8bb32ef80a594a9b8341877efa37d0deb1d54f11650801dfae7bf232d66fa7a7`;
- private router OOF: `9c71020d194454e60e384f5f195089d6bced95e45d67e8046cb55b74afeeb755`;
- paired OOF input: `b9513696e80aca12e60e719fb109e24f1412781e9996e5ad6b9e0221803bb2e8`;
- attempt-1 verifier: `920f6565bd378c8f7cfe415a78e505123336602fb228dad95771fcc14e471b15`.

The original config, frozen config, runner, verifier, scientific outputs, failed
verification and failed summary must remain at their original paths and retain their
bytes. They may not be renamed, copied over, deleted or rewritten.

## Authorized Public-Mode Normalization

Before formal attempt 2, orchestration may change mode metadata only for the exact
sixteen paths reported by attempt 1:

```text
router/                                      0700 -> 0755
router/frozen-sources/                       0700 -> 0755
router/REPORT.md                             0600 -> 0644
router/bootstrap.json                        0600 -> 0644
router/call-rate-performance.csv             0600 -> 0644
router/call-rate-performance.png             0600 -> 0644
router/feature-contract.json                  0600 -> 0644
router/fold-summary.csv                       0600 -> 0644
router/policy-comparisons.csv                 0600 -> 0644
router/positive-label-retention.csv           0600 -> 0644
router/random-routing.csv                     0600 -> 0644
router/routed-risk-coverage.csv               0600 -> 0644
router/routed-risk-coverage.png               0600 -> 0644
router/router-discrimination.json             0600 -> 0644
router/run.json                               0600 -> 0644
router/selected-operating-point.json          0600 -> 0644
```

No recursive chmod, wildcard target, private path or unlisted public path is
authorized. Every listed file SHA-256 must be recorded before and after and remain
identical. The failed verification and summary are deliberately excluded from this
mode-only repair.

The machine-readable amendment config at
`oof-router/configs/exp-061-seed-43-router-replication-router-verification-attempt-2-amendment.json`
freezes the full pre-normalization manifest, the public content-tree digest, both
private artifact hashes, the unique recursive JSON diff, all governing source
hashes and all append-only output paths. No separate mutable repair record is
permitted. The final attempt-2 result itself is the append-only post-repair evidence:
it records the exact before and after mode manifests and proves equal public-content
and private-artifact digests.

The public content-tree digest excludes only these three exact paths relative to the
router root: `verification-attempt-2.json`,
`VERIFICATION-SUMMARY-ATTEMPT-2.md`, and `router-complete.json`. A file with any of
those basenames below `frozen-sources/` or another nested directory remains covered
by the digest.

The amendment config also freezes live records for the recovery verifier, its
synthetic tests, the recovery-aware finalizer and its synthetic tests. The attempt-2
result binds that config; the selected-attempt record additionally binds the live
finalizer. The private namespace, attempt and router directories must remain `0700`,
and `paired-oof.npz` plus `router-oof.npz` must remain `0600` throughout recovery.

The normalizer must complete a full preflight before changing any mode. It must open
only the sixteen literal paths with `O_NOFOLLOW`, bind the opened descriptor to the
preflight device/inode and file type, and use `fchmod` on those descriptors. It must
not recurse or expand a glob. The `final` scope never normalizes implicitly and must
refuse to run unless all sixteen post-normalization modes already match.
Every file target must have link count one, and the post-change path must still bind
the same device/inode held during preflight.
After all sixteen descriptors are open and before the first `fchmod`, the normalizer
must read each of the fourteen files through its held descriptor and match the frozen
byte count and SHA-256 in the pre-manifest. It must record descriptor device, inode,
link count, mode and file digest in the normalization stdout evidence.

After normalization, every later `final` preflight, attempt-2 validator and recovery
finalizer must independently re-open the same exact sixteen paths without following
links. The fourteen files must remain regular files with link count one and mode
`0644`; the two directories must remain directories with mode `0755`. A new hardlink,
type replacement, symlink or mode drift is terminal even when content hashes and the
public tree digest are unchanged.

All four recovery scopes must use the frozen environment interpreter, never the
ambient `python3` on `PATH`:

```text
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router_attempt2.py --scope normalize
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router_attempt2.py --scope final
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router_attempt2.py --scope complete
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router_attempt2.py --scope completion
```

## Attempt-2 Contract

The amended verifier must not import the analyzer. It must execute the unchanged
attempt-1 verifier in two different fresh canonical mirrors. Each mirror has a new
row-level temporary project root with mode `0700`; all inputs are copied byte for
byte into their canonical project-relative paths. Symlinks and hardlinks are
forbidden, and each mirror is removed when its verifier run ends. Neither verifier
executes against the original tree.

The mirror source inventory is not supplied by mirror metadata. Both the recovery
verifier and finalizer independently rebuild it from the frozen amendment, formal
config, run, canonical runner, base verifier and every artifact record reachable
from the formal config and run, in canonical sorted order. The resulting exact
30-file count and canonical manifest digest must match both Mirror A and Mirror B,
whose metadata objects have an exact registered key inventory. The canonical runner
bytes must also equal the runner record in `run.json`'s frozen sources.

Mirror A loads the frozen verifier and the original config unchanged. With the
authorized public modes represented in the mirror, it must produce exactly
`4433 / 4434` passing checks and its unique failure must be `config.router`. This is
the control proving that the frozen verifier has no second failure.

Mirror B executes the same frozen verifier logic. Its verifier-module-local JSON
proxy may overlay only a `json.loads` input whose raw UTF-8 bytes match the original
formal-config SHA-256 exactly. That sole load changes only `/router/policies` from
the registered three-item value to the registered five-item value. The global JSON
module, the frozen verifier source, `POLICY_ORDER`, `DEPLOYABLE_POLICIES`, the runner
and every artifact remain unchanged. The unique recursive diff must contain one
node. Mirror B must produce exactly `4434 / 4434` passing checks.

The same frozen config bytes also occur in `frozen-sources/config.json` and are read
later by the privacy scan. The proxy records both SHA matches but applies the overlay
only to the first match, which is the verifier's canonical config load; the later
frozen-source parse remains byte-semantic and unmodified. Thus the registered JSON
diff is applied exactly once.

Attempt 2 must:

1. bind the immutable artifacts and hashes above;
2. prove that the original config contains the exact three/three clerical state;
3. apply only the registered `/router/policies` three-to-five effective correction,
   once, in Mirror B's SHA-bound local JSON proxy;
4. prove that the actual and independently recomputed evidence covers all five
   R0--R4 policies while selection remains restricted to the three deployable
   policies;
5. preserve all 4,434 original verifier checks with the exact same names and order;
6. repeat public/private mode, privacy, resource and split-boundary checks;
7. prove the paired OOF, private router OOF, attempt-1 failure and summary are
   unchanged after recomputation;
8. record full Mirror-A check evidence plus a digest binding Mirror B's checks to the
   top-level check list;
9. keep the top-level `checks` equal to Mirror B's 4,434 checks, all true, with
   `scope: final`, an exact nine-key all-true independence object, and the unchanged
   original config/run/input/private verified-artifact inventory;
10. write only new append-only outputs:
   `verification-attempt-2.json` and
   `VERIFICATION-SUMMARY-ATTEMPT-2.md`.

The exact top-level independence keys are `base_verifier_unchanged`,
`recovery_verifier_runner_import_absent`, `fresh_mirror_a`, `fresh_mirror_b`,
`mirrors_distinct`, `raw_exp058_recomputed_in_both`,
`nested_thresholds_recomputed_in_both`, `scalers_and_routers_refit_in_both`, and
`public_and_private_outputs_recomputed_in_both`. Missing, additional, renamed or
false-valued keys fail the contract.

Every top-level and Mirror-A check row has exactly `name`, `passed`, and `detail`;
`name` is a string and `passed` is a Boolean. Counts are non-Boolean integers, so
`false` cannot stand in for zero. Every artifact record has exactly `path`, `bytes`,
and `sha256`, with a normalized string path, a non-Boolean non-negative integer byte
count and a lowercase 64-hex digest. The attempt-1, attempt-2 and completion UTC
timestamps are canonical ISO-8601 values and must satisfy attempt 1 <= attempt 2 <=
completion.

The public verifier result is scanned recursively for the frozen base verifier's
complete sensitive-key inventory: singular and plural component, feature, fold,
logit, prediction, probability, route mask, route score, sample and target fields,
plus `feature_matrix`, `gold`, `router_targets`, `raw_text`, and `text`. The recovery
verifier and finalizer maintain the same exact key set; a sensitive key nested in a
check detail is still forbidden.

Any other failed base check remains failed. Pre-Mirror-A readiness failures write no
attempt-2 sidecar. Once Mirror A is entered, any deterministic verification or result
construction exception must instead be converted to the exact non-sensitive
`exp-router-formal-verification-attempt-2-failure-v1` schema. Its enumerated stage is
`verification_build`, its enumerated code is `deterministic_contract_failure`, and it
must not contain the original exception message, raw values or private diagnostics.
The verifier writes the append-only JSON first and then its deterministic Failed
summary. Either sidecar makes all later attempt-2 invocations refuse to run. A
sidecar-write error is propagated and no later stage may continue; a JSON already
created before a summary-write error remains the terminal seal. `KeyboardInterrupt`
and `SystemExit` are process-control events and must not be converted into scientific
failure records. An attempt-2 failure is terminal and does not authorize another
attempt.

Before Mirror A, all four downstream governance paths must be absent:
`verification-attempt-2.json`, `VERIFICATION-SUMMARY-ATTEMPT-2.md`,
`router-complete.json`, and the run-level `selected-attempt.json`. The three new
attempt/completion sidecars and the final selection are append-only regular files,
mode `0644`, link count one, and are created through held-descriptor atomic writers
that explicitly defeat a restrictive umask. Each later consumer independently
revalidates those properties for every sidecar it accepts. The original Failed JSON
and summary retain their original modes and bytes and are never normalized.

## Completion Contract

Only a matching `Passed` attempt-2 verification may create `router-complete.json`.
The completion record must retain the standard five-artifact inventory:

```text
config
run
selected_operating_point
final_verification
private_router_oof
```

`config` continues to bind the unchanged original formal config, while
`final_verification` binds `verification-attempt-2.json`. Completion verification
must independently rehash all five artifacts, re-evaluate the frozen
`logistic_router@15%` primary Pass/Fail rule and confirm that the experiment-level
selection record is still absent. It must accept only the exact attempt-2 path and
schema; no attempt-1 fallback is allowed.

The standard five-artifact inventory remains unchanged to preserve the completion
schema. The recovery-only `recovery_lineage` must additionally contain
`passed_summary`, an artifact record for the exact
`VERIFICATION-SUMMARY-ATTEMPT-2.md` path. Before completion, completion verification,
or final selection, the recovery verifier/finalizer must independently render the
deterministic Passed summary from the Passed attempt-2 JSON and require byte-for-byte
equality, mode `0644`, link count one, byte count and SHA-256 equality. The summary
does not record its own hash, so this binding has no self-reference. The
selected-attempt record inherits the same summary record in its recovery lineage.

The pipeline finalizer may enter the recovery branch only for `EXP-061`,
`attempt-1`, and the exact `verification-attempt-2.json` basename. It must
independently validate the original Failed verification and summary, this protocol,
the amendment config, both verifier sources, the one-node overlay, the exact sixteen
mode transitions, unchanged public/private digests, all Mirror A/B evidence and the
4,434-check contract, the exact nine-key independence object, and the deterministic
attempt-2 summary. The selected-attempt record must preserve the explicit
`Failed` attempt-1 to `Passed` attempt-2 lineage. All other router attempts continue
to use the unamended frozen finalizer path.

Recovery config, run, selected operating point, paired OOF, private router OOF,
attempt-1 verification, attempt-1 summary, attempt-2 verification, attempt-2
summary, completion and selection paths are constructed from the registered
`EXP-061` / `attempt-1` identity. Self-reported alternate paths are not accepted.

This amendment does not itself authorize seed 44, validation/test access, a second
router analysis, or any claim beyond the verified seed-43 train-OOF result.
