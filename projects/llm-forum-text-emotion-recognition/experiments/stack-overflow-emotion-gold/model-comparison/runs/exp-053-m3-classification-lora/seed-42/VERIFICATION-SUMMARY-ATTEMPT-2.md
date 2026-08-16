# EXP-053 Seed-42 Verification Attempt 2

- Status: `Passed`
- Checks: `148/148`
- Selected checkpoint probability replay max abs error: `0`
- Shared-threshold Macro-F1: `0.637786`
- M3-M2 shared-threshold Macro-F1 delta: `+0.312857`
- Test accessed: no

Attempt 1 remains append-only as Failed (135/136) because it read an obsolete resource-verifier field.
This attempt applies only the registered schema correction and repeats the full independent replay.

This verification covers one seed only. Seeds 43/44, EXP-054 and test remain sealed.
