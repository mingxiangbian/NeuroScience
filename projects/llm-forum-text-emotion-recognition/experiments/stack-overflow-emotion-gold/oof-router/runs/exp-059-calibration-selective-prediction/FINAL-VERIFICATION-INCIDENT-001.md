# EXP-059 Final Verification Incident 001

- Date: 2026-08-17
- Attempt: 1
- Outcome: verifier crashed before result comparison
- Formal analysis rerun: no

The attempt-1 verifier raised `KeyError: 'hamming_risk'` while rebuilding the random
rejection table. Its independent classification function exposes the same quantity as
`hamming_loss`; only the public table calls it `hamming_risk`.

No verification result or summary was written. The formal analysis artifacts remain
unchanged. The correction and attempt-2 boundary are frozen in
`protocols/exp-059-final-verification-amendment.md`.
