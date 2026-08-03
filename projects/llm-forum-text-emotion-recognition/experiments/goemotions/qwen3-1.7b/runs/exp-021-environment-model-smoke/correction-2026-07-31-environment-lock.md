# EXP-021 Environment Lock Correction

Date: 2026-07-31

## Issue

The completed run called `pip freeze --local`. In this Conda environment, pip classified the
environment packages outside that command's local subset and returned an empty list. The
original `environment-lock.txt`, its hash in `run.json`, and `verification.json` are preserved
unchanged under the append-only run policy.

## Correction

The full environment was captured with:

```bash
PYTHONNOUSERSITE=1 /Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  -m pip --isolated freeze
```

The non-empty result is saved as `environment-lock-corrected.txt`. The setup script now uses
the corrected command and rejects an empty lock in any future run.

Verification on 2026-07-31:

- Package lines: 34.
- SHA-256: `982efc879bb3ab3668685abfdd1ff1961934a4050e3d9bd23349bdde110ac1e5`.
- The saved content exactly matched a fresh `pip --isolated freeze` from the recorded Conda
  environment.

This correction changes no model file, revision, conversion, smoke result, project data access
record, or task metric.
