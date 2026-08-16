# EXP-053 Seed-42 Verification Attempt-2 Amendment

- Experiment ID: `EXP-053`
- Stage: `seed-42-verification-attempt-2`
- Registered: 2026-08-14
- Scope: verification-schema-only correction

## Observed Failure

The first independent verification completed the full 720-row checkpoint replay and passed
135 of 136 checks. Its maximum absolute replay probability error was `0.0`, and test was not
accessed. The only failed check, `resource_verifier_102`, read the obsolete field
`checks_passed`; the frozen resource verification record uses `check_count` and a `checks`
array instead.

The failed attempt remains append-only:

- `verification.json`: `453028b2dac8abb0e0475133cc34b73c964890ddbf2f5da3103c37e8e3056e7a`
- `VERIFICATION-SUMMARY.md`: `eed84e07c8b05c2ae224054e3ecb033eec8ae3422a05990f98735b52952d6241`

## Authorized Correction

Attempt 2 may only replace that prerequisite check with the actual frozen schema:

1. `status == Passed`;
2. `check_count == 102`;
3. `len(checks) == 102`;
4. `failed_checks == []`.

It must otherwise repeat the complete independent validation replay and all original checks.
It writes `verification-attempt-2.json` and `VERIFICATION-SUMMARY-ATTEMPT-2.md`; it may not
overwrite attempt 1, change the trained checkpoint, access test, authorize seeds 43/44, or
authorize EXP-054.
