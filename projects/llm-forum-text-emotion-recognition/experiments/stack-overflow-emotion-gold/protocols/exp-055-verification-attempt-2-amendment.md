# EXP-055 Verification Attempt 2 Amendment

---
experiment_id: EXP-055
verification_attempt: 2
status: frozen-before-formal-attempt-2
date: 2026-08-15
---

## Trigger

A disposable preflight copy of the completed EXP-055 run passed 208 of 209
independent checks. The only failure was `report test boundary`: the report contains
the words `access` and `test` on adjacent Markdown lines, while verifier attempt 1
required the literal contiguous substring `access test`.

This was a verifier string-matching defect. The preflight did not identify a metric,
source-hash, row-alignment, sampling, annotation, privacy, artifact-hash, test-gate,
or claim-boundary failure. No formal `verification.json` was written to the tracked
run directory.

## Authorized Correction

Attempt 2 may normalize report whitespace with `re.sub(r"\\s+", " ", report)`
before repeating the same five boundary-string checks. It must independently rerun
all source, metric, transition, slice, oracle, bootstrap, sampling, annotation,
privacy, and artifact checks from attempt 1.

No analysis artifact, manual annotation, report, summary, threshold, model output,
source input, or claim may change. The original frozen verifier remains unchanged in
the run for provenance.

## Frozen References

- Base config SHA-256:
  `2c026c4e59a2f7595aad679eb8bc7debaf3ba05cf2b2035d8f66f9a5515ff430`.
- Original frozen verifier SHA-256:
  `b0d1ca81531b6a9f6c4bbce7ed31bf3df3914c0ce715b69cb57c6a10f079e5be`.
- Attempt-2 verifier SHA-256:
  `d66ef422d59aa5190c0d46bd704c95aa7394d6d75646671c8f6e94e251fba94f`.
- Expected formal output: `verification-attempt-2.json`.

The attempt-2 authorization JSON must bind this amendment and verifier by byte size
and SHA-256. A failed formal attempt remains append-only and requires another
explicit amendment; it must not be overwritten.
