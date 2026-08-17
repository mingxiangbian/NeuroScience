# EXP-057 Verification Attempt 2 Schema Amendment

Date: 2026-08-16

Attempt 1 stopped in the independent verifier with
`KeyError: 'empty_prediction_rate'`. The cause was a public aggregate schema
difference: EXP-051 to EXP-053 expose `empty_prediction_rows`, while EXP-054 exposes
`empty_prediction_rate`.

Attempt 2 changes presentation logic only:

1. For M1-M3 validation, compute each seed's empty-prediction rate as
   `empty_prediction_rows / 720`, then report its arithmetic mean and sample standard
   deviation.
2. Keep M4's already recorded `empty_prediction_rate` unchanged.
3. Add a unit test for this conversion and repeat all independent checks in a new run
   directory.

All frozen sources, model metrics, contrasts, claim boundaries, and test-gate hashes
remain unchanged. No private prediction, raw text, test label, model inference,
threshold, seed, parser, prompt, checkpoint, or bootstrap replicate may be accessed or
changed.
