# EXP-057 Verification Attempt 1 Failure

- Date: 2026-08-16
- Stage: independent verification
- Result: failed before verification output was written
- Error: `KeyError: 'empty_prediction_rate'`

M1-M3 validation aggregates store `empty_prediction_rows`, while M4 stores
`empty_prediction_rate`. The attempt-1 analyzer left the unavailable M1-M3 rate cells
blank, but the verifier incorrectly assumed a uniform upstream field. No private
prediction, raw text, sealed test-label source, model inference, threshold selection,
or scientific result changed.

Attempt 2 must use a new output directory, bind a correction amendment, and derive the
M1-M3 rate deterministically as `empty_prediction_rows / 720` in both the analyzer and
the independent verifier.
