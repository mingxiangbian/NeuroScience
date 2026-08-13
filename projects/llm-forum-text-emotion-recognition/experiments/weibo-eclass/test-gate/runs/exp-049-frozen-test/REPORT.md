# EXP-049 Weibo EClass Frozen Test Report

Status: Verified by an independent metric and privacy reconstruction.

| Unit | Macro-F1 | Accuracy | Macro-P | Macro-R | Weighted-F1 | Parser valid | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| m0-majority | 0.116937 | 0.692852 | 0.098979 | 0.142857 | 0.567142 | N/A | 0.040 |
| m1-target-only | 0.374762 | 0.673998 | 0.406484 | 0.355843 | 0.662273 | N/A | 3.063 |
| encoder-seed-42 | 0.655028 | 0.832679 | 0.681610 | 0.648939 | 0.828595 | N/A | 9.785 |
| encoder-seed-43 | 0.641233 | 0.821681 | 0.669413 | 0.624645 | 0.817958 | N/A | 8.660 |
| encoder-seed-44 | 0.652603 | 0.832679 | 0.674099 | 0.645601 | 0.827825 | N/A | 8.291 |
| qwen-reference | 0.316921 | 0.224666 | 0.360527 | 0.461705 | 0.223741 | 0.914375 | 75186.913 |
| qwen-lora-seed-42 | 0.623451 | 0.813826 | 0.665392 | 0.646297 | 0.814210 | 1.000000 | 3015.835 |
| qwen-lora-seed-43 | 0.625046 | 0.827965 | 0.697094 | 0.576969 | 0.816803 | 1.000000 | 2678.290 |
| qwen-lora-seed-44 | 0.661339 | 0.832679 | 0.694269 | 0.649390 | 0.827832 | 1.000000 | 2614.229 |

## Family Summary

- `encoder` Macro-F1: `0.649621 +/- 0.007365`
- `m0` Macro-F1: `0.116937 +/- 0.000000`
- `m1` Macro-F1: `0.374762 +/- 0.000000`
- `qwen_lora` Macro-F1: `0.636612 +/- 0.021429`
- `qwen_reference` Macro-F1: `0.316921 +/- 0.000000`

## Frozen Contrasts

- `encoder_mean_minus_m1`: delta `+0.274860`, 95% group bootstrap CI `[+0.226927, +0.324054]`, decision `material_improvement`.
- `lora_mean_minus_encoder_mean`: delta `-0.013009`, 95% group bootstrap CI `[-0.045671, +0.024011]`, decision `material_degradation`.
- `lora_mean_minus_qwen_reference`: delta `+0.319691`, 95% group bootstrap CI `[+0.274779, +0.362068]`, decision `material_improvement`.

All nine configurations were frozen before test access and are reported without best-seed selection.
Row-level predictions, source identifiers, text, gold labels, and Qwen reasoning remain private.
No result may be used to tune or rerun this held-out split.
