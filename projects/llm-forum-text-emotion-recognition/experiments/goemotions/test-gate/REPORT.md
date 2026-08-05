# EXP-038 GoEmotions Frozen Test Report

## Status

- Status: `Verified`
- Official test rows: `5,427`
- Test SHA-256: `0587b2dd8b27b97352adbfc3fb083d46005c8946657fdc2b1ca8b1cc7f1f8be4`
- Frozen config SHA-256: `87177da88dfb1ebb9bc78a71ac11aca87b8b85c98b126f40bb9c056eba316b0f`
- Formal evaluations: 9 frozen units, one pass each
- Post-test tuning or model selection: none

## Main Results

Three-seed conditions report mean +/- sample standard deviation. Single-run conditions are marked
as such. Exact match is strict subset accuracy: a row is correct only when the complete predicted
label set equals the complete gold label set.

| Frozen condition | Runs | Macro-F1 | Micro-F1 | Weighted-F1 | Samples-F1 | Exact match |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EXP-018 TF-IDF + OVR Logistic Regression | 1 | 0.196197 | 0.382080 | 0.334114 | 0.279682 | 0.250046 |
| EXP-020 BERT-base-cased | 3 | 0.488328 +/- 0.008771 | 0.590427 +/- 0.001634 | 0.587884 +/- 0.002594 | 0.599429 +/- 0.002439 | 0.443032 +/- 0.005061 |
| EXP-025 Qwen3-1.7B prompting, few-shot | 1 | 0.233653 | 0.249278 | 0.267550 | 0.265998 | 0.112032 |
| EXP-029 Qwen3-1.7B LoRA, historical ontology | 3 | 0.450652 +/- 0.032175 | 0.579031 +/- 0.005213 | 0.555956 +/- 0.007159 | 0.587416 +/- 0.006813 | 0.513543 +/- 0.009738 |
| EXP-033 Qwen3-1.7B LoRA, target-aligned | 1 | 0.444675 | 0.580163 | 0.559297 | 0.590207 | 0.513175 |

## Interpretation

1. EXP-020 is the strongest condition by the pre-registered primary metric. Its mean Macro-F1 is
   `+0.292132` above EXP-018 and `+0.028328` above the GoEmotions paper's reported BERT test
   Macro-F1 `0.46`. The latter is a same-split, nominally same-task reference, not a bitwise
   reproduction: this implementation uses modern PyTorch, Transformers and Apple MPS rather than
   the paper's TensorFlow Estimator stack.
2. Frozen prompting is only `+0.037457` above the simple TF-IDF baseline and remains far below the
   supervised encoder. On this task, an untuned local generative LLM is not a competitive
   replacement for supervised fine-tuning.
3. Historical EXP-029 remains `-0.037676` below BERT in mean Macro-F1. Its training targets removed
   neutral from 1,396 neutral-plus-emotion rows, so it is retained only as an explicitly
   ontology-misaligned historical control.
4. Target-aligned EXP-033 reaches Macro-F1 `0.444675`, `-0.043653` below the BERT mean. It is only
   one seed; compared descriptively with historical EXP-029 seed 42 (`0.443643`), the difference is
   `+0.001032`, which does not establish a meaningful improvement.
5. Both LoRA conditions have higher exact match than BERT while lower Macro-F1. Their mean predicted
   label cardinality is about `1.03` to `1.05`, below the test gold mean `1.166`, whereas BERT is
   about `1.279`. Exact match therefore does not replace the class-balanced primary metric and must
   be interpreted alongside per-label recall and cardinality.

## Local LLM Resources

| Unit | Parser valid | Median generation | Peak MLX memory | API cost |
| --- | ---: | ---: | ---: | ---: |
| EXP-025 few-shot | 99.9816% | 0.949 s/row | 3.723 GB | USD 0 |
| EXP-029 seed 42 | 100% | 0.740 s/row | 4.006 GB | USD 0 |
| EXP-029 seed 43 | 100% | 0.729 s/row | 4.006 GB | USD 0 |
| EXP-029 seed 44 | 100% | 0.811 s/row | 4.006 GB | USD 0 |
| EXP-033 seed 42 | 100% | 0.763 s/row | 4.030 GB | USD 0 |

## Verification

The independent verifier reconstructed all nine `5,427 x 28` prediction matrices, recomputed all
aggregate and per-label metrics and confusion matrices, checked public artifact hashes and confirmed
that no post-test tuning or model selection occurred.

The registered verifier initially stopped at EXP-025 row 9 because it compared generated label IDs
as an ordered list with an ID-sorted multi-hot reconstruction. The label sets were identical. The
documented `EXP-038-VERIFY-V2` correction validates uniqueness and range, then compares sorted sets.
No model output, prediction, metric, config or test data changed. See
[`VERIFIER-AMENDMENT.md`](VERIFIER-AMENDMENT.md) and
[`verification.json`](runs/exp-038-frozen-test/verification.json).

## Evidence Boundary

EXP-038 closes the public GoEmotions behavioral reproduction stage. The test split is now consumed
and cannot be used for further model selection, prompt changes, threshold tuning or retraining.
These results support classification-performance claims only; they do not establish an internal
emotion mechanism or a correspondence with human emotion generation.
