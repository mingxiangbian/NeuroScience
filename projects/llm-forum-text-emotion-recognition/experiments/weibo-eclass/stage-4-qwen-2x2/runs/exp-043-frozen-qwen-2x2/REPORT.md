# EXP-043 Frozen Qwen 2x2 Results

Status: Awaiting independent verification.

| Condition | View | Reasoning | Macro-F1 | Accuracy | Parser valid |
| --- | --- | --- | ---: | ---: | ---: |
| A | target_only | false | 0.308684 | 0.230346 | 0.999214 |
| B | previous_context | false | 0.281480 | 0.188679 | 0.999214 |
| C | target_only | true | 0.333818 | 0.222484 | 0.918239 |
| D | previous_context | true | 0.317997 | 0.219340 | 0.908019 |

Frozen Qwen condition: `C`.
Selected Qwen minus EXP-042 M2 target-only Macro-F1: `-0.261107`.

These are validation results. The sealed test split was not accessed.
