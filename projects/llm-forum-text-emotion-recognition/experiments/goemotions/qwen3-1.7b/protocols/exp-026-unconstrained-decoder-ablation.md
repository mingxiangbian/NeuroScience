# EXP-026: Unconstrained Decoder Ablation

Registration date: 2026-07-31 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-026`
- Tier: `Major`
- RQ: `RQ-G2`
- Parent: `EXP-025`
- Stage: matched full-dev unconstrained-decoder ablation
- Status: completed and independently verified
- Config: [`../configs/exp-026-unconstrained-decoder-ablation.json`](../configs/exp-026-unconstrained-decoder-ablation.json)
- Config SHA-256: `01cd49cb0d020ad1c4d3cc5ef8d1acef9426ebfdaf9db22dda702b85e0565ed3`
- Runner SHA-256: `ec2615c44b6c13d9843dabd344f3e2bcc05e44b1df05e2215771b7dc5a4a41ee`
- Metric implementation SHA-256:
  `38e50c725a5f065d0babb263ad497b5d8dc21ad6edcd11a5e4d4c79310ff44d4`
- Independent verifier SHA-256:
  `f36d6417a0bcaa194635d398de0de7d95b155104996b325ef5aefc99cdc1b534`

This experiment was registered before any EXP-025/026 dev generation or result access. It does not
authorize test acquisition or use.

## Preflight Gate

Passed at 2026-07-31 22:14 CST, before formal dev access:

- the independent `scikit-learn` verifier passed parser and metric fixtures, verified all frozen
  implementation/input hashes, and reported `dev_accessed=false` and `test_absent=true`;
- the model-backed runner loaded the frozen local Qwen model in `7.176130333013134` seconds and all
  four synthetic cells (constrained/unconstrained x zero/few-shot) ended with `stop` and strict
  parser validity;
- both formal output directories and `test.tsv` were absent;
- an initial sandbox-only model invocation exited before loading because Metal was unavailable
  (`exit 134`), without split access or output creation. The identical frozen command passed with
  normal local Metal access.

EXP-026 remains gated on a complete, independently verified EXP-025 run.

## Why This Control Is Required

EXP-025 estimates the behavior of the complete `Qwen3-1.7B + constrained decoder` system. A
finite-state token mask is not a post-hoc parser: it removes invalid next tokens during generation,
so the selected token changes whenever the unrestricted argmax is disallowed. The new token then
changes the autoregressive state and can change the eventual label set.

A pre-registration audit paired the existing EXP-022 unconstrained and EXP-024 constrained runs.
They used the same 32 train texts, model, prompt, conditions and greedy decoding; no raw text, gold,
dev or test was read for this audit.

- EXP-022 sample results SHA-256:
  `63e29ed4f1705328f05f3b94c3caa9f1e19f240fbf7bb264244c2902590d6f99`.
- EXP-024 sample results SHA-256:
  `1bb791ddcb7a93fe0cdff67812eb5baa8a48d668d128159386906d201839de1f`.
- Zero-shot: 31/32 unconstrained outputs parsed; 27/31 valid pairs had the same label set and
  4/31 differed; mean label-set Jaccard was `0.9032258064516129`.
- Few-shot: 28/32 unconstrained outputs parsed; all 28 valid pairs had the same label set.
- Both constrained conditions parsed 32/32.

These small train-sample results are design evidence only. They do not estimate accuracy or the
full-dev effect. They establish that constrained decoding cannot be assumed label-neutral.

## Research Question and Expected Result

Holding the model, prompt, dev rows and greedy generation fixed, how does removing the finite-state
token mask change:

1. end-to-end 28-label Macro-F1 when invalid outputs count as empty predictions;
2. output validity, label sets, label cardinality and per-label behavior;
3. latency and generated-token cost?

The expected result is that the constraint materially improves format validity. Its effect on
Macro-F1 and individual labels is uncertain. Based on the 32-row audit, some zero-shot outputs may
change even when the unrestricted output is parseable; few-shot may be more stable, but this is not
assumed for full dev.

## Frozen 2x2 Design

The joint table contains four cells:

| Prompt condition | EXP-026 unrestricted | EXP-025 constrained |
| --- | --- | --- |
| zero-shot | strict parser after free generation | finite-state token mask |
| few-shot-synthetic-3 | strict parser after free generation | finite-state token mask |

EXP-026 changes only the decoder factor. Both experiments use:

- all 5,426 official agreement-filtered GoEmotions dev rows;
- the same ordered 27 emotion labels plus `neutral`;
- the same post-trained `Qwen/Qwen3-1.7B` revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`;
- the same local unquantized MLX BF16 model;
- the exact EXP-022 prompt and three synthetic examples;
- thinking disabled, greedy decoding, batch size 1 and maximum 64 generated tokens;
- no prompt cache, KV quantization, network, API, retry, synonym mapping or post-hoc repair.

The two EXP-026 conditions cover every dev row exactly once. Odd rows run zero-shot first; even rows
run few-shot first. EXP-025 runs and verifies before EXP-026 so the matched constrained artifacts
exist before joint analysis.

## Frozen Inputs

- Dataset protocol: `DATA-GOE-V1`.
- Dev rows: 5,426; SHA-256
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Label ontology SHA-256:
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Prompt SHA-256:
  `2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c`.
- Strict-parser source SHA-256:
  `d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e`.
- Model manifest SHA-256:
  `7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877`.
- Train access: prohibited; demonstrations are synthetic.
- Test access: prohibited; `test.tsv` must remain absent.

## Parser and Failure Policy

EXP-026 generates without a logits processor. After generation, the frozen strict parser accepts
only one JSON object with exactly the `labels` key, a non-empty list of unique ontology names, and
`neutral` alone if selected. Leading/trailing whitespace accepted by `json.loads(output.strip())`
does not itself invalidate an output.

Every row remains in the denominator. A length finish or parser failure produces an empty predicted
label set, with only error category, output hash and byte/character count retained. Raw invalid text
is not retained. No retry, extraction, Markdown stripping beyond outer whitespace, synonym mapping
or repair is allowed. Exceptions, OOM, non-finite values, hash mismatches or unintended split access
stop and reject the whole formal run.

## Metrics and Matched Diagnostics

Primary metric: end-to-end Macro-F1 across all 28 labels, scoring invalid outputs as empty.

Each EXP-026 condition reports the same complete metric set as EXP-025: macro/micro/weighted/
samples precision, recall and F1; strict subset accuracy; Hamming loss; label accuracy; per-label
metrics and 2x2 matrices; label cardinality; empty predictions; parser/finish rates; tokens, latency,
throughput, peak memory and USD 0 API cost.

Selected-token sum and mean log probability are saved as unrestricted sequence scores. They are
not calibrated 28-label probabilities.

For each prompt condition, joint analysis reports:

- end-to-end Macro-F1 difference, unrestricted minus constrained;
- parser-validity difference;
- exact label-set agreement and mean Jaccard on rows where unrestricted output is valid;
- label-cardinality and per-label prediction/support changes;
- latency, prompt-token and generated-token differences;
- EXP-025 raw-argmax intervention rate and first blocked step distribution.

Metrics restricted to rows where both outputs parse are diagnostic only because conditioning on
parser success selects an easier/non-random subset. They cannot replace the all-row primary metric.

## Frozen Statistics and Selection Boundary

Use the same 10,000 paired dev-row bootstrap replicates, seed `20260731`, and percentile 95%
intervals for:

- unrestricted zero-shot minus unrestricted few-shot;
- unrestricted minus constrained within zero-shot and within few-shot;
- each unrestricted condition minus each frozen EXP-020 BERT seed.

An improvement claim requires an absolute Macro-F1 difference of at least `0.005` and a paired 95%
interval excluding zero. Bootstrap reflects dev-row sampling uncertainty, not model stochasticity.

EXP-026 is an ablation and cannot override EXP-025's frozen zero/few-shot selection. All four cells
are reported, while the downstream prompting candidate remains the EXP-025 constrained condition
selected under its own rule. This prevents a post-hoc parser-valid subset or ablation result from
silently changing the production candidate.

## Required Artifacts and Privacy

```text
runs/exp-026-unconstrained-decoder-ablation/
├── run.json
├── stdout.log
├── generation-records.jsonl
├── condition-summary.csv
├── aggregate-metrics.json
├── paired-bootstrap.json
├── joint-decoder-analysis.json
├── zero-shot/
│   ├── predictions.csv
│   ├── metrics.json
│   ├── per-label-metrics.csv
│   └── multilabel-confusion-matrix.csv
├── few-shot-synthetic-3/
│   ├── predictions.csv
│   ├── metrics.json
│   ├── per-label-metrics.csv
│   └── multilabel-confusion-matrix.csv
└── verification.json
```

Public artifacts store one-based row number, gold/predicted labels, canonical valid JSON or invalid
metadata, generation resources and sequence scores. They must not contain raw input text, comment
ID, prompt-expanded input or invalid raw generation.

## Independent Verification

The verifier must independently read the frozen dev labels, reconstruct all task metrics with a
separate implementation, and check:

- every frozen source/input/model hash and test absence;
- exactly 5,426 unique rows per condition in the required order;
- strict parsing, invalid-as-empty handling and no retries;
- every metric, confusion matrix, sequence/resource aggregate and bootstrap interval;
- EXP-025 artifact hashes before computing joint analysis;
- exact-set/Jaccard/cardinality/latency and intervention summaries;
- the public privacy boundary and all artifact hashes.

Only a complete run with `verification.json` status `Passed` may enter the evidence ledger.

## Resource Budget and Stop Conditions

- EXP-026 measured generations: 10,852 plus two synthetic warm-ups.
- Projected active generation: `2.731889558940673` hours.
- Combined EXP-025/026 projection: `5.272179626111559` hours.
- EXP-026 hard wall time: 240 minutes; combined hard caps: 480 minutes.
- Peak MLX memory: at most 14.0 GB.
- API/external compute cost: USD 0; local Apple Silicon only.

Before dev access, runner/verifier hashes, synthetic model generation, metric fixtures, output
absence and test absence must pass. Stop on any hash/split/output gate failure, unexplained
generation exception, OOM/non-finite value or resource-limit breach.

## Evidence-to-Thesis Destination

- `Table-G2-1`: all four decoder/prompt cells with Macro-F1 and complete supporting metrics.
- `Table-G2-2`: parser validity, exact agreement, Jaccard, cardinality and intervention rates.
- `Figure-G2-1`: latency/token cost by prompt and decoder condition.
- Methods: decoder-factor ablation, strict parser and invalid-as-empty policy.
- Discussion: distinguish Qwen label behavior from the deployable constrained system and explain
  when format control changes autoregressive decisions.

This ablation is behavioral. It does not establish an internal emotion mechanism or a human-like
recognition process.

## Execution and Verified Result

The frozen ablation ran from `2026-07-31T17:03:44Z` to `2026-07-31T19:29:52Z`, completed all
10,852 generations without retry and produced the pre-registered joint analysis against EXP-025.
The independent verifier returned `Passed` with maximum numeric difference `0.0`; it confirmed
test absence, all frozen hashes, row coverage, strict parsing, invalid-as-empty scoring, bootstrap
intervals, joint diagnostics and the public privacy boundary.

| Unconstrained condition | Macro-F1 | Micro-F1 | Subset accuracy | Parser valid | Empty predictions | Predicted labels/row | Median generation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zero-shot | 0.228700 | 0.238562 | 0.161445 | 95.9823% | 218 | 1.3056 | 0.6864 s |
| few-shot-synthetic-3 | 0.236465 | 0.246069 | 0.101364 | 90.7298% | 503 | 1.7077 | 0.8801 s |

The unconstrained parser failures were not repaired or retried. Zero-shot produced 70
`neutral-combined` and 148 `unknown-label` failures. Few-shot produced one invalid JSON, 206
`neutral-combined` and 296 `unknown-label` failures. All were scored as empty predictions.

### Matched Decoder Effects

| Prompt | Unconstrained - constrained Macro-F1 | Paired bootstrap 95% CI | Validity delta | Exact label-set agreement among both-valid rows | Mean Jaccard among both-valid rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| zero-shot | +0.005702 | [-0.003906, 0.015234] | -3.9808 pp | 3947/5206 = 75.8164% | 0.847289 |
| few-shot-synthetic-3 | -0.004699 | [-0.008687, -0.000990] | -9.2702 pp | 4923/4923 = 100.0000% | 1.000000 |

For zero-shot, the point difference crossed the `0.005` practical threshold but its interval
included zero, so the run does not establish a reliable performance gain from removing the mask.
For few-shot, the interval excluded zero in favor of the constrained system, but the absolute point
difference was `0.004699`, below the pre-registered practical threshold. The decoder effect is
therefore behaviorally important but not a practically large Macro-F1 effect under this rule.

The few-shot result cleanly separates format recovery from valid-label behavior: every one of the
4,923 unconstrained valid rows had the same final label set under constrained decoding, while the
constraint supplied valid predictions for the remaining 503 rows. Zero-shot is different: even
among both-valid rows, 1,259/5,206 final label sets differed. The constrained system therefore
cannot generally be described as a label-neutral wrapper around Qwen.

Both unconstrained cells remained far below all three EXP-020 BERT seeds. Their Macro-F1 deficits
ranged from `0.250053` to `0.272144` for zero-shot and from `0.242287` to `0.264378` for few-shot;
all six paired bootstrap intervals excluded zero. EXP-026 cannot override the EXP-025 prompt
selection and does not authorize test access.

Removing the mask reduced total generation time by `429.76` seconds for zero-shot and `800.72`
seconds for few-shot. Total EXP-026 runtime was `8768.00` seconds, peak MLX memory was `3.6600` GB
and API cost was USD 0.

Verified artifacts:

- [`../runs/exp-026-unconstrained-decoder-ablation/run.json`](../runs/exp-026-unconstrained-decoder-ablation/run.json)
- [`../runs/exp-026-unconstrained-decoder-ablation/aggregate-metrics.json`](../runs/exp-026-unconstrained-decoder-ablation/aggregate-metrics.json)
- [`../runs/exp-026-unconstrained-decoder-ablation/paired-bootstrap.json`](../runs/exp-026-unconstrained-decoder-ablation/paired-bootstrap.json)
- [`../runs/exp-026-unconstrained-decoder-ablation/joint-decoder-analysis.json`](../runs/exp-026-unconstrained-decoder-ablation/joint-decoder-analysis.json)
- [`../runs/exp-026-unconstrained-decoder-ablation/verification.json`](../runs/exp-026-unconstrained-decoder-ablation/verification.json)
