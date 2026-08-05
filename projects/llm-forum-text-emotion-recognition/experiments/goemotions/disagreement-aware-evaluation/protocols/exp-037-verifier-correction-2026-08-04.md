# EXP-037 Verifier Correction Note

Date: 2026-08-04 (Asia/Shanghai)

## Trigger

The first independent verification attempt stopped after all CSV recomputations and before writing
`verification.json` with:

```text
JSON object differs at $.structure.clear_rater_count_distribution
```

JSON requires object keys to be strings. The in-memory independently rebuilt distributions use
integer count keys, while `json.loads` returns their stored equivalents as string keys. The
original verifier compared key types before comparing values, so this failure is deterministic and
does not indicate a metric, row, annotation, or artifact-content difference.

## Frozen Identities

- Original config SHA-256:
  `34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d`.
- Original verifier SHA-256:
  `135dd9987baeff83e4e385d9091ac1ece43823c553eb327feb0c5fd108599716`.
- Corrected verifier wrapper:
  `verify_full_dev_rater_aware_evaluation_v2.py`.
- Corrected verifier wrapper SHA-256:
  `645214c412995ab7cb7b12bd64413504df6c6d9ed43f2eae86491439c04b5275`.

## Authorized Correction

The wrapper changes only JSON dictionary-key comparison by normalizing observed and expected keys
to strings. It delegates data loading, private-record reconstruction, all metric formulas, both
bootstrap procedures, CSV checks, privacy checks, artifact hashing, report regeneration, and
`run.json` discipline to the original frozen verifier.

It must not:

- alter the original config, runner, verifier, protocol, predictions, or run artifacts;
- rerun raw archive transport, model inference, training, scoring, or bootstrap generation;
- change any tolerance, decision rule, metric, sample, seed, or comparison;
- read `test.tsv`.

The corrected verifier records its own file identity in `verification.json`. A subsequent
`--check` pass must reproduce the same verification record exactly.
