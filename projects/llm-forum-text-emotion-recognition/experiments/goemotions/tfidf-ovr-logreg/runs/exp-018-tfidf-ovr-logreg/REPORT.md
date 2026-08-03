# EXP-018 Result: GoEmotions Simple Multi-label Baseline

## Scope

`EXP-018` trains word TF-IDF plus 28 independent Logistic Regression
classifiers on the frozen GoEmotions train split and evaluates once on dev.
The global threshold is fixed at `0.5`; no class weighting, threshold tuning,
resampling or post-processing is used. The test split remains unacquired.

## Verified Dev Results

| Metric | Value |
| --- | ---: |
| Macro-F1 | 0.203644 |
| Macro precision | 0.555610 |
| Macro recall | 0.144754 |
| Micro-F1 | 0.377639 |
| Weighted-F1 | 0.332809 |
| Samples-F1 | 0.278179 |
| Subset/exact-match accuracy | 0.246959 |
| Hamming loss | 0.035319 |
| Mean gold labels per row | 1.175820 |
| Mean predicted labels per row | 0.413196 |
| Empty prediction rows | 3,261 / 5,426 |

Independent verification reconstructed the 5,426 x 28 gold and prediction
matrices from frozen dev labels and saved probabilities. Aggregate metrics,
per-label metrics, confusion matrices and artifact hashes matched exactly.

## Per-label Pattern

The strongest F1 values are:

- `gratitude`: 0.860248
- `love`: 0.614657
- `amusement`: 0.547461
- `admiration`: 0.499295
- `neutral`: 0.484634

The model predicts no positives for `disappointment`, `grief`, `nervousness`,
`pride` or `relief`, giving those labels zero recall and F1. This is not only a
rare-class effect: `disappointment` has 163 dev positives but still receives no
positive prediction at threshold 0.5.

## Interpretation

The model converged without warnings, so the low Macro-F1 is not evidence of a
failed optimizer. Its macro precision is much higher than macro recall, the
predicted label cardinality is far below the gold cardinality, and 60.10% of
dev rows receive an empty label set. The fixed unweighted model is therefore a
conservative lexical lower bound that misses many positives, especially for
fine-grained and low-frequency labels.

This result does not establish that threshold tuning or class weighting would
improve held-out performance; neither was tested in `EXP-018`. It also cannot be
compared directly with TweetEval scores because the task and label structure
are different.

## Limitations

- Dev is for development evidence, not a final generalization estimate.
- The official train/dev split contains the reviewed 41 exact-text overlaps.
- The baseline uses only word n-grams and no context or pretrained encoder.
- A fixed 0.5 threshold is intentionally untreated as a tunable advantage.
- No qualitative error text was reviewed or published in this run.

## Next Dependency

`EXP-018` completes the simple-baseline half of `RQ-G1`. The next model stage is
a BERT-base/RoBERTa supervised baseline on the same GoEmotions train/dev data.
Only after that encoder condition is frozen may the GoEmotions LLM comparison
be designed.

