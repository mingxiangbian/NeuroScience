# EXP-062 / EXP-060 Incident 004 Final-Verification Recovery

## Incident

The seed-44 EXP-060 formal runner completed successfully, but the first final
verification command stopped before writing a final claim:

```text
ValueError: v4 run terminal seal drift
```

The run terminal and the runner both hash the immutable evidence as
`2538d77098d13ab0ebeef7c0ed12e9cdd76a116f5126dbd256080f4b9d07ba2f`.
The verifier hashes the same 34 values as
`442c930db4158641dc6388be9938285509d4bb10f3bbe0c338d7d8482893dd1d`
because it uses different dictionary keys.

## Recovery

`verify_exp060_router_v5_incident004.py` held-loads the frozen v4 runner and
verifier bytes. It patches only the loaded verifier module's
`_immutable_snapshot` function in memory. The adapter performs this exact,
bijective rename:

- `input` -> `input.paired_oof`
- `attempt1.*` -> `recovery.attempt1.*`
- `attempt2.*` -> `recovery.attempt2.*`
- `frozen.*` -> `recovery.frozen.*`
- `absent` -> `canonical_absent`

The normalized verifier snapshot must be exactly type-equal to the held
runner snapshot and must reproduce the sealed run digest. The patch is restored
even on `BaseException`. No runner, verifier, config, run terminal, public
router, or private router file is modified by the adapter itself.

## Authorized sequence

1. Recovery verifier with `--scope final`.
2. Frozen Incident-003-aware runner with `--stage complete`.
3. Recovery verifier with `--scope completion`.

Any nonzero result, failed check, partial state, identity/hash/mode/resource
drift, or selection appearance stops the sequence. The formal runner is not
rerun. Selection is not authorized.

