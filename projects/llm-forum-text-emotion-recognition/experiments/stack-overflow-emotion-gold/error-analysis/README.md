# Stack Overflow Error Analysis

`EXP-055` is a validation-only, read-only comparison of the frozen EXP-051 M1
RoBERTa and EXP-053 M3 Classification LoRA predictions. It does not train or rerun
models and does not access the sealed Stack Overflow test split.

The tracked run contains only aggregate metrics, derived case IDs, predictions and
qualitative codes. Raw forum text and source identifiers remain under the gitignored
`private/` directory.

The verified result is recorded in
[`runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md`](runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md).
The whitespace-only verifier amendment passed 220/220 checks. Its router gate is an
oracle-headroom eligibility result, not evidence that a learned router is deployable.
