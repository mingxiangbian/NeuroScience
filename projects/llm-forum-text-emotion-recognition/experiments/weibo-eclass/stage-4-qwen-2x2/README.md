# Weibo EClass Stage 4 Frozen Qwen 2x2

This module owns `EXP-043`, a deterministic validation-only comparison of
context and reasoning mode for the frozen Qwen3-4B model.

| Condition | Input view | Reasoning |
| --- | --- | --- |
| A | target only | off |
| B | previous local clause + target | off |
| C | target only | on |
| D | previous local clause + target | on |

The execution order is fixed:

```text
initialize
train-only batch/runtime smoke
infer A
infer B
infer C
infer D
aggregate
independent verification
```

Inference is greedy and batched for reproducibility and feasible local runtime.
Parser-invalid or truncated outputs are retained privately and count as wrong.
The sealed test, LoRA adapters and transfer datasets are outside this experiment.

See [`EXP-043`](../protocols/exp-043-frozen-qwen-2x2.md) for the registered
research and resource contract.

## Verified Result

EXP-043 completed 5,088 formal validation generations. Independent verification
passed 10 checks with zero mismatches; the sealed test was not accessed.

| Condition | Macro-F1 | Accuracy | Weighted-F1 | Parser valid |
| --- | ---: | ---: | ---: | ---: |
| A · target/off | 0.308684 | 0.230346 | 0.239951 | 0.999214 |
| B · context/off | 0.281480 | 0.188679 | 0.176090 | 0.999214 |
| C · target/on | 0.333818 | 0.222484 | 0.202040 | 0.918239 |
| D · context/on | 0.317997 | 0.219340 | 0.194241 | 0.908019 |

Condition C was selected by the frozen Macro-F1 rule. Across the factorial
contrasts, the observed context contrast was negative (`-0.021512`, 95% CI
`[-0.037515, -0.006905]`) and reasoning was positive (`+0.030825`, 95% CI
`[+0.007225, +0.057146]`), while their interaction interval crossed zero.
Reasoning did not improve Accuracy or Weighted-F1 over condition A, reduced
strict parser validity and increased generation from about 8 thousand to about
0.67 million tokens per condition.

On the 332 first-clause rows, paired prompt hashes matched exactly, but the two
reasoning-on batched runs agreed on only 273 final labels. The reasoning-on
context contrast therefore also contains a batch-runtime reproducibility
component and must not be read as a pure semantic-context effect.

Public artifacts:

- [`REPORT.md`](runs/exp-043-frozen-qwen-2x2/REPORT.md)
- [`aggregate_metrics.json`](runs/exp-043-frozen-qwen-2x2/aggregate_metrics.json)
- [`verification.json`](runs/exp-043-frozen-qwen-2x2/verification.json)
- [`run.json`](runs/exp-043-frozen-qwen-2x2/run.json)

The report and aggregate were generated before the verifier and retain that
intermediate status internally. `verification.json` and `run.json` are the
authoritative final status records.
