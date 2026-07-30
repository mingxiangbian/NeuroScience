# EXP-008 Correction: Python User-Site Leakage

Date: 2026-07-30

After EXP-008 completed, an environment audit found that the machine-level pip
configuration contained `global.user=true`. The EXP-008 process therefore
resolved installed packages through `~/.local/lib/python3.10/site-packages`
even though the interpreter itself belonged to the `emotion-roberta` Conda
environment.

## Impact

- The offline model load, file-hash checks, MPS device selection, optimization
  step, and synthetic inference remain valid functional checks.
- EXP-008 does not by itself prove that all dependencies were isolated inside
  the dedicated Conda environment.
- Its synthetic loss remains non-evidential, as already stated in `run.json`.

## Correction

- Runtime packages were installed again with `PIP_USER=0` and
  `PYTHONNOUSERSITE=1`.
- Both variables were stored in the `emotion-roberta` Conda environment.
- A subsequent audit confirmed that Python user-site loading is disabled and
  that NumPy, pandas, PyTorch, Transformers, Datasets, scikit-learn,
  Matplotlib, python-dateutil, and six all resolve from
  `/Users/phoenix/miniconda3/envs/emotion-roberta/`.
- EXP-009 performs the same isolation checks before it is allowed to read
  train or validation data.

The original EXP-008 `run.json` is intentionally unchanged.
