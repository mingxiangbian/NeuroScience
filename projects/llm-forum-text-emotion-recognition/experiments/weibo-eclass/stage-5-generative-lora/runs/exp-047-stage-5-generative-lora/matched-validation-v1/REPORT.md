# EXP-047 Matched Validation Report

Independent verification passed with zero mismatch.

| Condition | Macro-F1 | Accuracy | Weighted-F1 | Parser valid | Duration (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| reference | 0.333598 | 0.222484 | 0.207222 | 0.908805 | 79098.411 |
| seed-42 | 0.552028 | 0.768082 | 0.773339 | 1.000000 | 2814.599 |
| seed-43 | 0.548289 | 0.786164 | 0.770574 | 1.000000 | 2568.905 |
| seed-44 | 0.587096 | 0.783805 | 0.779033 | 1.000000 | 2640.908 |

## Primary Contrast

- LoRA mean Macro-F1: `0.562471`
- LoRA sample SD: `0.021408`
- Matched reference Macro-F1: `0.333598`
- Mean delta: `+0.228873`
- Frozen decision: `material_improvement`

Validation was accessed under explicit authorization. The sealed test was not accessed.
Generated reasoning and row-level predictions remain private.
