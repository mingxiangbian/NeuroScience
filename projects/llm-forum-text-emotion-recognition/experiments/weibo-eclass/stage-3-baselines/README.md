# Weibo EClass Stage 3 Baselines

This module runs the registered `EXP-042` train/dev comparison for the frozen
`DATA-WEIBO-TASK-V1` task:

- M0 train-majority baseline;
- M1 word/character TF-IDF plus `LinearSVC` for both input views;
- M2 `hfl/chinese-roberta-wwm-ext` for both views and three seeds.

The runner never opens the sealed test inputs or labels. Row-level validation
predictions and retained encoder checkpoints are written below the Git-ignored
Weibo private data root. Public run artifacts contain only aggregate metrics,
configuration, hashes and timing.

## Result

`EXP-042` is complete and independently verified with eight checks and zero
mismatches. On the frozen validation split, M2 reached Macro-F1
`0.594925 +/- 0.012919` for target only and `0.594219 +/- 0.012046` with the
previous clause. The paired context delta was `-0.000706 +/- 0.024737`, so the
views are a practical tie under the preregistered `0.005` rule and target only
is selected for simplicity. M0/M1 results and all auxiliary metrics are in the
aggregate report. The sealed test was not accessed.

The formal execution order is:

```text
initialize
m0-m1
m2 --view target_only --seed 42|43|44
m2 --view previous_context --seed 42|43|44
aggregate
independent verification
```

See [`EXP-042`](../protocols/exp-042-stage-3-baselines.md) for the frozen
research and resource contract. See
[`REPORT.md`](runs/exp-042-stage-3-baselines/REPORT.md),
[`aggregate_metrics.json`](runs/exp-042-stage-3-baselines/aggregate_metrics.json)
and [`verification.json`](runs/exp-042-stage-3-baselines/verification.json) for
the completed evidence.
