# EXP-058 Final Verification Incident 001

- First verification time: `2026-08-16T19:52:09.101458+00:00`
- First verification status: `Failed`
- Checks passed: `26,984 / 26,989`
- Failed checks: `final.private_mode.fold-0` through `final.private_mode.fold-4`
- Observed mode: `0755`
- Required mode: `0700`

## Evidence Before Remediation

- Failed verification SHA-256: `ff30806965436da99c613e8855dd191e5bd86eab33e3557110975174600fe061`
- Failed summary SHA-256: `e882d7d5d887c24e21dbfb1590ee38b6665a70fc95531515cb0bdceeb28c4a37`
- Paired OOF artifact SHA-256: `e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc`

## Root Cause

The runner created each private model leaf directory with mode `0700`, but its
intermediate `fold-N` parent was created under the process umask and remained
`0755`. Fold-level verification covered each model leaf. Final recursive
verification correctly detected the five intermediate parent directories.

This was a privacy-permission defect. The first final verification reported no
failure in model outputs, fold coverage, source order, paired OOF assembly, or
train-only split discipline.

## Authorized Remediation

1. Preserve the failed verification report and summary without changing their
   bytes.
2. Change only the five intermediate private `fold-N` directories to `0700`.
3. Rerun the same frozen final verifier.
4. Do not retrain models or rewrite fold logits, labels, sample identifiers, or
   the paired OOF artifact.

