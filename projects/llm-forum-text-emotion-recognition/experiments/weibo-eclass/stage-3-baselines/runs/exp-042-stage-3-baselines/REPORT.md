# EXP-042 Stage 3 Results

Status: Awaiting independent verification.

| Model | View | Validation Macro-F1 | Accuracy |
| --- | --- | ---: | ---: |
| M0 | target_only | 0.1169 | 0.6926 |
| M1 | target_only | 0.3383 | 0.6509 |
| M1 | previous_context | 0.2715 | 0.4434 |
| M2 | target_only | 0.5949 +/- 0.0129 | 0.7925 +/- 0.0039 |
| M2 | previous_context | 0.5942 +/- 0.0120 | 0.7901 +/- 0.0049 |

Frozen M2 primary view: `target_only` (practical tie; prefer lower-complexity target-only input).

These are validation results. The sealed test split was not accessed.
