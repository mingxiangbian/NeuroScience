# EXP-031 Verified Report

Validation-only, three-seed inference ablation. No test split was acquired or read.

| Condition | Macro-F1 | Samples-F1 | Exact match | Predicted cardinality |
| --- | ---: | ---: | ---: | ---: |
| old-prompt-closed-decoder | 0.4514 +/- 0.0192 | 0.5858 +/- 0.0100 | 0.5083 +/- 0.0133 | 1.034 |
| old-prompt-open-decoder | 0.4514 +/- 0.0192 | 0.5858 +/- 0.0100 | 0.5083 +/- 0.0133 | 1.034 |
| aligned-prompt-open-decoder | 0.4531 +/- 0.0148 | 0.5826 +/- 0.0126 | 0.5028 +/- 0.0163 | 1.045 |
| exp-029-zero-shot-closed-ontology | 0.4514 +/- 0.0192 | 0.5858 +/- 0.0100 | 0.5083 +/- 0.0133 | 1.034 |

## Paired Mean Effects

- Concurrent closed minus historical closed Macro-F1: +0.0000.
- Old prompt/open decoder minus closed Macro-F1: +0.0000.
- Aligned prompt/open decoder minus closed Macro-F1: +0.0017.
- Aligned prompt/open decoder minus old prompt/open decoder Macro-F1: +0.0017.
- Aligned-open minus closed Samples-F1 on the 174-row neutral co-occurrence slice: -0.0091.

## Decision

Classification: `no_material_inference_improvement`.

Inference-time ontology correction does not meet the registered general or localized improvement rule for these target-misaligned adapters.

This experiment isolates inference policy only. The adapters were trained with co-occurring neutral removed, so the result does not estimate target-aligned retraining and does not support an internal-mechanism claim.
