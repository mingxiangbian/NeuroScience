# EXP-016 Frozen Test Gate

EXP-016 is the one-time formal TweetEval emotion test evaluation for the
models selected and frozen by EXP-007, EXP-011, EXP-014, and EXP-015.
The gate was preregistered before any project test prediction was produced.
It performs inference only: no retraining, seed selection, ensemble, threshold
change, or post-result tuning is allowed.

Independent verification status: `Verified`.

## Freeze Decision

The user confirmed the final freeze on 2026-07-30 after reviewing the local
results against the pinned upstream references. The experiment code, anonymous
predictions, metrics, and verification record are archived in Git commit
`f061ec9c91e925236d6d481c66efc9dcbbfce907`.

EXP-016 is now the final TweetEval test estimate for this project. The test
split may be inspected for preregistered descriptive error analysis, but it
must not be used to tune prompts, choose new models, change preprocessing, or
replace these results.

## Test Results

| Frozen condition | Test Macro-F1 | Test Accuracy | Weighted F1 | Runs |
| --- | ---: | ---: | ---: | ---: |
| EXP-007 TF-IDF + Linear SVM | 0.646998 | 0.700915 | 0.695383 | 1 |
| EXP-011 generic RoBERTa | 0.795761 +/- 0.003298 | 0.819845 +/- 0.003225 | 0.820171 +/- 0.002974 | 3 seeds |
| EXP-014 generic RoBERTa + label smoothing | 0.792645 +/- 0.003658 | 0.820783 +/- 0.004686 | 0.820098 +/- 0.003121 | 3 seeds |
| EXP-015 Twitter RoBERTa + label smoothing | **0.809973 +/- 0.007038** | **0.840019 +/- 0.008126** | **0.838828 +/- 0.007877** | 3 seeds |

Neural values are mean +/- sample standard deviation across seeds 42, 43,
and 44. EXP-007 is a single deterministic frozen model.

## Controlled Comparisons

| Paired comparison | Mean test Macro-F1 delta | Seed deltas | Interpretation |
| --- | ---: | --- | --- |
| EXP-014 minus EXP-011 | -0.003116 | +0.001324, -0.001502, -0.009169 | Below the 0.005 practical threshold and negative on 2/3 seeds; label smoothing did not establish a test improvement |
| EXP-015 minus EXP-014 | +0.017328 | +0.024422, +0.012330, +0.015233 | Above the 0.005 threshold and positive on 3/3 seeds; the Twitter-domain encoder benefit generalized to test |
| EXP-015 minus EXP-007 | +0.162975 | not paired | The final encoder condition substantially exceeds the traditional baseline |

Label smoothing raised validation Macro-F1 by 0.007415 in EXP-014, but its
test mean is 0.003116 below EXP-011. The defensible conclusion is therefore
not that label smoothing improves this task, but that its small development
gain did not generalize under the frozen test protocol.

EXP-015 still contains label smoothing because it inherited the frozen
downstream condition from EXP-014. The EXP-015 versus EXP-014 comparison
therefore isolates the base encoder, but it does not show whether a
Twitter-domain model without label smoothing would be better. Training that
variant now would be post-test development and cannot replace EXP-016.

## Per-Class F1

| Condition | Anger | Joy | Optimism | Sadness |
| --- | ---: | ---: | ---: | ---: |
| EXP-007 | 0.773616 | 0.682493 | 0.464286 | 0.667598 |
| EXP-011 | 0.855149 | 0.831161 | 0.698912 | 0.797822 |
| EXP-014 | 0.859653 | 0.830098 | 0.684090 | 0.796739 |
| EXP-015 | **0.873872** | **0.849487** | **0.691421** | **0.825112** |

Relative to EXP-014, EXP-015 improves test F1 for anger (+0.014219), joy
(+0.019390), optimism (+0.007331), and sadness (+0.028374). Optimism remains
the weakest class. Its small test improvement reverses the validation decline,
so the earlier optimism regression is split-specific rather than a stable
domain-pretraining effect.

## External References

The pinned upstream TweetEval README reports test Macro-F1 of 0.647 for SVM,
0.761 for RoBERTa-Base, 0.720 for RoBERTa-Twitter, and 0.785 for
RoBERTa-Retrained. Its bundled `predictions/emotion.txt` independently
evaluates to 0.798272. The prediction file SHA-256 is
`16c6cf2b1c678bc739a738aa565e1f1bfb67e365cfc06fb413bfda9ddbaf88a0`;
the upstream evaluation script SHA-256 is
`86c824e466ffba0cd407655fbbda759c6a9c09e541be4bfaaf547df8255d2793`.

These numbers are external configurations, not project runs:

- EXP-007 matches the reported SVM score to the displayed three decimals,
  which is a useful evaluation-pipeline check.
- EXP-011 and EXP-015 exceed the corresponding historical leaderboard values
  under the local implementation.
- EXP-015 is 0.011701 above the bundled upstream prediction score, but this is
  not a controlled significance claim because the upstream artifact is a
  single external run with a different implementation history.

## Artifacts

The frozen protocol and config are:

- `protocols/exp-016-frozen-test.md`
- `configs/exp-016-frozen-test.json`

The append-only result directory is:

```text
runs/exp-016-frozen-test/
```

It contains:

- `run.json`: complete environment, hashes, results, aggregates, paired
  comparisons, and ranking;
- `condition_summary.csv` and `seed_results.csv`;
- one prediction, metric, and confusion bundle for every fitted model or
  checkpoint;
- `verification.json`: independent recomputation over 14,210 model-sample
  prediction rows.

Formal evaluation command:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/test-gate/evaluate_frozen_test.py
```

Independent verification command:

```bash
PIP_USER=0 PYTHONNOUSERSITE=1 \
  /Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/tweeteval-emotion/test-gate/verify_frozen_test.py
```

The evaluation command must not be run again against this test split. Further
TweetEval development is explicitly post-test and cannot replace EXP-016 as
the final unbiased gate.
