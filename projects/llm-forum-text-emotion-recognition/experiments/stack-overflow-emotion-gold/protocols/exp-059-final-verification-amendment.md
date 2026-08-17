# EXP-059 Final Verification Amendment 001

- Experiment: `EXP-059`
- Scope: independent final verification only
- Registered: 2026-08-17
- Analysis rerun authorized: no
- Public/private result mutation authorized: no

## Incident

Final verification attempt 1 stopped before comparing any result because the verifier's
random-rejection recomputation looked up `classification()["hamming_risk"]`. The
independent classification function names that quantity `hamming_loss`; `hamming_risk`
is only the public output column name. Python raised `KeyError: 'hamming_risk'`.

The formal analyzer had already completed. It did not use this verifier code path, and
the failed verifier wrote no `verification.json` or `VERIFICATION-SUMMARY.md`. Formal
public and private analysis artifacts are therefore retained byte-for-byte and must not
be regenerated.

## Authorized Correction

Replace the generic random-metric lookup with the explicit mapping:

```text
hamming_risk          <- classification.hamming_loss
macro_f1              <- classification.macro_f1
five_label_macro_f1   <- classification.five_label_macro_f1
```

No formula, seed, threshold, calibrator, gate, oracle, bootstrap rule, tolerance, input,
or output schema changes. Attempt 2 must use a new frozen verification config that binds
the amended verifier, this amendment, the original formal config, the formal `run.json`,
and the analyzer-frozen attempt-1 verifier. It must independently recompute all results
from the unchanged EXP-058 input.

## Claim Boundary

This is a verifier implementation repair, not an experimental amendment. A passed
attempt 2 can validate the original formal outputs; it cannot conceal or delete this
incident and does not authorize a second formal analysis run.
