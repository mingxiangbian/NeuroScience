# EXP-053 Seed-44 Documentation Correction

Date: 2026-08-15

This correction addresses copied prose in the immutable formal artifacts. It does
not change the authorization, training, predictions, metrics, checkpoints, or
verification result.

## Incorrect prose

The following generated text incorrectly describes seed 44 as the second seed
and says that seed 44 remains sealed:

- `run.json` field `warnings[0]`
- the final sentence of `REPORT.md`
- the corresponding strings in `frozen-runner.py`
- the corresponding summary template in `frozen-verifier.py`

These files are retained unchanged so their recorded hashes and the independent
replay remain auditable.

## Correct interpretation

- Seed 44 is the third authorized EXP-053 M3 seed.
- The seed-44 formal run completed on train + validation.
- The seed-44 independent verifier passed 148/148 checks with zero probability
  replay error.
- All three individual M3 seeds, 42, 43, and 44, are now verified.
- The M3 three-seed aggregate, EXP-054, and test remain sealed.

The machine-readable fields in `run.json` are authoritative:
`authorization.seed_44_authorized=true`, `authorization.seeds=[44]`,
`training.seed=44`, `status=Completed`, and
`test_split_accessed=false`.
