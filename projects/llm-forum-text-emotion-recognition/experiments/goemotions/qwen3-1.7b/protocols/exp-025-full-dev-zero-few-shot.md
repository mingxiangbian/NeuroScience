# EXP-025: Qwen3-1.7B Full-Dev Zero/Few-Shot Evaluation

Registration date: 2026-07-31 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-025`
- Tier: `Major`
- RQ: `RQ-G2`
- Parent: `EXP-024`
- Stage: full GoEmotions dev zero/few-shot comparison
- Status: completed and independently verified
- Config: [`../configs/exp-025-full-dev-zero-few-shot.json`](../configs/exp-025-full-dev-zero-few-shot.json)
- Config SHA-256: `dfb182a0ca20146f92f6832d5b7536f29419c64e0448c2ce12e4f6c91c964e07`
- Parent verification SHA-256: `171e327ad9281aee195622b05688b51d545155b78ec73631e97c4f8f3b8f590b`

The implementation was frozen before dev access:

- runner SHA-256: `ec2615c44b6c13d9843dabd344f3e2bcc05e44b1df05e2215771b7dc5a4a41ee`;
- metric implementation SHA-256:
  `38e50c725a5f065d0babb263ad497b5d8dc21ad6edcd11a5e4d4c79310ff44d4`;
- independent verifier SHA-256:
  `f36d6417a0bcaa194635d398de0de7d95b155104996b325ef5aefc99cdc1b534`.

This registration does not itself authorize dev generation. The empty-output gate, test-absence
gate, model-backed synthetic preflight and independent verifier preflight must pass first.

EXP-025 estimates the complete constrained system. The matched EXP-026 protocol was registered
before either formal run and removes only the finite-state token mask. EXP-025 additionally records
whether the unrestricted argmax was blocked, the number of blocked decoding steps and the first
blocked step/token. This telemetry and the full 2x2 result are required before attributing a label
change to Qwen rather than to the output constraint.

## Preflight Gate

Passed at 2026-07-31 22:14 CST, before formal dev access:

- the independent `scikit-learn` verifier passed parser and metric fixtures, verified all frozen
  implementation/input hashes, and reported `dev_accessed=false` and `test_absent=true`;
- the model-backed runner loaded the frozen local Qwen model in `7.176130333013134` seconds and all
  four synthetic cells (constrained/unconstrained x zero/few-shot) ended with `stop` and strict
  parser validity;
- EXP-025 and EXP-026 output directories were absent and `test.tsv` was absent;
- an initial sandbox-only model invocation exited before loading because Metal was unavailable
  (`exit 134`); it accessed no project split and created no run directory. The identical frozen
  command then passed with normal local Metal access.

The gate authorizes one EXP-025 formal dev pass, followed only after independent verification by
one EXP-026 formal dev pass. It does not authorize test acquisition or access.

## Research Question and Expected Result

On the same frozen GoEmotions dev split and 28-label ontology as EXP-018 and EXP-020, how well does
the local post-trained Qwen3-1.7B perform as a constrained generative multi-label classifier under
zero-shot and fixed synthetic three-shot prompting? Does either condition add enough predictive
value to justify its latency and complexity relative to the simple lexical baseline and the
supervised BERT encoder?

The pre-registered expectation is:

- at least one Qwen condition may exceed the weak EXP-018 lexical baseline by the practical
  `0.005` Macro-F1 margin;
- there is no prior assumption that a 1.7B generative model will exceed the supervised EXP-020
  BERT baseline;
- the direction of the zero-shot versus few-shot difference is uncertain because the three
  examples are synthetic and improve task specification without adapting model weights.

A result below EXP-020 remains informative: it would show that local generative inference adds
cost and a flexible interface without adding dev classification quality under this protocol. A
result near or below EXP-018 would reject the practical case for using this frozen prompt/model as
a classifier and redirect later work toward supervised adaptation rather than prompt expansion.

## Controlled Change

Relative to the verified EXP-024 implementation gate, this Major changes only the evaluation
population and the use of gold labels:

- replace the 32 fixed anonymous train texts with all 5,426 official dev rows;
- evaluate the parsed predictions against frozen dev gold labels;
- save complete multi-label metrics, anonymous predictions, latency, token and cost evidence;
- compare both prompt conditions with frozen EXP-018 and EXP-020 dev artifacts.

The model, precision, prompt, synthetic examples, output grammar, constrained decoder, greedy
decoding and 64-token limit remain fixed. No prompt, example, synonym, threshold, label definition
or decoder rule may be changed under `EXP-025` after dev access begins.

## Frozen Data and Split Discipline

- Dataset protocol: `DATA-GOE-V1`.
- Split: official agreement-filtered `dev`, exactly 5,426 rows.
- Dev SHA-256 from the frozen data manifest:
  `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Ordered 28-label ontology SHA-256:
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Labels: 27 emotion classes plus `neutral`, with the existing GoEmotions ID order unchanged.
- Train access during this run: prohibited; the three demonstrations are synthetic.
- Test access: prohibited. `test.tsv` must be absent before and after the run.

The runner may read dev text and gold labels only after the implementation preflight passes. It
must not use gold labels while generating. Evaluation occurs after each condition has produced one
prediction for every row. Dev is used for condition selection, so EXP-025 results are validation
evidence rather than final test or public benchmark results.

## Frozen Model, Prompt and Decoder

- Provider/source: Qwen official Hugging Face repository, acquired and verified in EXP-021.
- Model: `Qwen/Qwen3-1.7B`, post-trained condition.
- Upstream revision: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- Local model: `models/qwen3-1.7b/mlx-bf16`, unquantized BF16.
- Model manifest SHA-256:
  `7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877`.
- Prompt: frozen EXP-022 label-name prompt and its three synthetic examples.
- Prompt SHA-256:
  `2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c`.
- Constraint implementation SHA-256:
  `6e4d1d21d79d2fed3c8a5d118748591db6e72cfcfefb74386f913fb5fd164efa`.
- Thinking/rationale: disabled; no generated explanation is requested or retained.
- Decoding: greedy, temperature `0.0`, batch size `1`, maximum 64 generated tokens.
- Prompt cache and KV-cache quantization: disabled.
- External network and API calls: disabled.

The finite-state token mask permits only one complete canonical object such as:

```json
{"labels":["joy","excitement"]}
```

It permits only frozen label names, rejects duplicates, and permits `neutral` only by itself. It
does not cap non-neutral label cardinality below 27. There is no unrestricted fallback, retry,
synonym mapping, silent repair, explanation or extra key. Format validity under this decoder is an
engineering guarantee and must not be reported as unconstrained instruction-following ability.

## Conditions and Execution Order

1. `zero-shot`: no demonstrations.
2. `few-shot-synthetic-3`: the exact three synthetic demonstrations in the frozen prompt file.

Both conditions cover every dev row exactly once, for 10,852 measured generations. One synthetic
warm-up per condition is excluded from every task and timing aggregate. To balance fixed order and
thermal/cache drift, odd one-based dev rows run zero-shot first and even rows run few-shot first.

Generation is deterministic under the frozen greedy setup, so repeated generation seeds would not
measure meaningful model variability. There is one formal generation pass. If interrupted, a
technical resume is allowed only from an independently checked exact prefix with unchanged hashes;
completed row-condition pairs cannot be regenerated, and the interruption and resume must be
recorded in `run.json`.

## Invalid Outputs and Run Failures

Every dev row remains in the denominator:

- a `length` finish or strict-parser failure becomes an empty predicted label set for that condition;
- the failure category, output hash, output byte count and finish reason are retained;
- the raw invalid output is not retained publicly;
- no retry, deletion or fallback is permitted.

An exception, OOM, non-finite model/resource value, hash mismatch, unexpected row count, duplicate
row-condition pair or unintended split access stops and rejects the formal run. Such a run is
preserved as interrupted/failed and cannot be presented as EXP-025 performance evidence.

## Metrics and Decision Scores

Primary metric: Macro-F1 over all 28 labels, including labels with zero predicted positives.

Required secondary evidence:

- macro, micro, weighted and samples-averaged precision, recall and F1;
- strict subset accuracy, Hamming loss and label-level accuracy;
- per-label precision, recall, F1, gold support and predicted support;
- one 2x2 confusion matrix per label;
- gold and predicted label cardinality;
- empty-prediction and `neutral` co-prediction counts;
- strict-parser rate and finish-reason counts;
- prompt/generated token totals and distributions;
- generation latency total, median and p95, throughput and peak MLX memory;
- API cost, fixed at USD 0.

Each prediction records the sum and mean of selected-token log probabilities after the finite-state
mask, excluding EOS and covering only tokens that form the canonical JSON. These are constrained
sequence scores, not calibrated 28-label probabilities and not the confidence of the unconstrained
model. The experiment will not fabricate per-label probability columns comparable to EXP-020.

## Frozen Comparisons and Statistics

The comparison inputs were fixed before EXP-025 dev access:

- EXP-018 predictions SHA-256:
  `c54d1ba5ee1c4f78122db5c8cedaffa33211b5e15165520a4f9eb9ada263d901`;
  frozen dev Macro-F1 `0.20364430957028798`.
- EXP-020 aggregate SHA-256:
  `5e81a8877bdbade1fd8de1d8280253c2d014c1033ef6aebf51cafc3e36d16e7e`;
  frozen dev Macro-F1 `0.4894350234249331 +/- 0.011063210636681352`.
- EXP-020 seed prediction SHA-256 values:
  seed 42 `eadde158ab9d9b42a0dffc554ec662b6d9aeb7bd4376c32c1c6ac310dc7e57b3`,
  seed 43 `cdae577732f10872326ab0ef263e61ad3a736ae56a224f9b5fdcbbe70a29e317`,
  seed 44 `b4d35702dc75eb75f2aba20cf5e94c53fad516b52de769c910bfe856c99d3bce`.

Use 10,000 paired dev-row bootstrap replicates with seed `20260731` and percentile 95% intervals
for Macro-F1 differences:

- zero-shot minus few-shot;
- each Qwen condition minus each of the three frozen EXP-020 seeds.

Bootstrap estimates uncertainty from resampling dev rows; it does not estimate prompt/model
stochasticity. A claim of improvement requires both an absolute Macro-F1 gain of at least `0.005`
and a paired 95% interval excluding zero. Results against EXP-018 are reported descriptively with
the same practical-effect threshold. Because prompt selection occurs on this dev split, all
comparisons remain model-selection evidence and cannot be described as an independent test claim.

## Condition Selection Rule

- If the absolute zero/few Macro-F1 difference is at least `0.005`, select the higher condition.
- If the difference is below `0.005`, declare a practical tie and select zero-shot for shorter
  prompts, lower projected latency and lower complexity.
- Weighted-F1 does not override this rule.
- The bootstrap interval controls wording about evidence strength; it does not replace the frozen
  selection threshold.
- Selection only identifies the prompting candidate for later LoRA or a future `TEST-READY` gate.
  It does not authorize downloading or reading GoEmotions test.

## Required Artifacts and Privacy

The formal run must create a previously absent, empty target directory and produce:

```text
runs/exp-025-full-dev-zero-few-shot/
├── run.json
├── stdout.log
├── generation-records.jsonl
├── condition-summary.csv
├── aggregate-metrics.json
├── paired-bootstrap.json
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

Each prediction row stores one-based dev row number, gold/predicted label IDs and names, canonical
valid JSON or invalid-output metadata, finish reason, token counts, latency and constrained
sequence scores. Public artifacts must not contain comment IDs, raw input text, prompt-expanded
input, or invalid raw generations.

EXP-025 produces the anonymous quantitative substrate for later error analysis. Reading error text
or assigning qualitative error types requires a separately registered Major with a frozen sampling
rule and privacy boundary; this run does not select interesting examples after seeing outcomes.

## Independent Verification

The verifier must run separately from the generator and:

- confirm config, prompt, constraint, model manifest, dev, labels and comparison artifact hashes;
- confirm `test.tsv` is absent and only dev was accessed;
- confirm both conditions contain each of 5,426 one-based rows exactly once and in the frozen order;
- reparse canonical outputs and independently map names to the 28 label IDs;
- apply the frozen empty-prediction policy to every invalid/length output;
- recompute all aggregate, per-label and confusion-matrix metrics from saved predictions;
- recompute the selection rule and all paired bootstrap intervals;
- verify token, latency, finish-reason, parser and resource aggregates against row records/logs;
- verify no prohibited raw text or identifiers appear in public artifacts;
- write artifact SHA-256 values and a final `Passed` or `Failed` status to `verification.json`.

Only a complete run with independent verification status `Passed` may be promoted to
`evidence-log.md` as a quantitative result.

## Resource Budget and Stop Conditions

- Formal generation passes: one, containing both conditions.
- Measured generations: 10,852; synthetic warm-ups: two.
- Projected active generation time: approximately `2.5403` hours in total.
- Hard wall-time limit: 240 minutes, including model load, grammar initialization and evaluation.
- Peak MLX memory limit: 14.0 GB.
- API cost limit: USD 0.
- External GPU/CPU service budget: none; local Apple Silicon only.
- Deadline: no calendar deadline is imposed; the run stops at the resource gates above.

Stop before dev access if any frozen input hash differs, the output directory exists/non-empty, the
runner/verifier preflight is incomplete, or `test.tsv` exists. Stop during execution on the run
failures defined above or before exceeding the wall-time/memory budget. Any proposal to change the
research question, split, prompt, decoder, primary metric or selection rule requires a new Major ID.

## Evidence-to-Thesis Destination

- `Table-G2-1`, Results: GoEmotions dev comparison of EXP-018, EXP-020 and both EXP-025 conditions.
- `Figure-G2-1`, Results/Engineering analysis: latency, token and peak-memory cost by Qwen condition.
- Methods: local Qwen provenance, fixed zero/few-shot prompts, constrained decoding, invalid-output
  policy, multi-label metrics and paired bootstrap.
- Discussion: whether a generative LLM adds classification value beyond a supervised encoder; the
  difference between constrained format validity and unconstrained instruction following.
- Limitations: dev-only model selection, synthetic few-shot examples, post-trained-model confounds,
  no context and no mechanistic claim.

The result cannot establish how humans generate emotion, that Qwen uses a human-like recognition
process, or that constrained sequence scores reveal internal emotion mechanisms. Those questions
require later representation and intervention experiments after the behavioral baseline is stable.

## Execution and Verified Result

The frozen formal pass ran from `2026-07-31T14:15:20Z` to `2026-07-31T17:02:00Z` and completed
all 10,852 measured generations (5,426 dev rows x two prompt conditions) without retry. The
independent verifier subsequently returned `Passed` with maximum numeric difference `0.0`; it
confirmed test absence, source and artifact hashes, row coverage, metric reconstruction and the
public privacy boundary.

| Constrained condition | Macro-F1 | Micro-F1 | Subset accuracy | Parser valid | Empty predictions | Predicted labels/row | Median generation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zero-shot | 0.222998 | 0.235917 | 0.179137 | 99.9631% | 2 | 1.1896 | 0.7499 s |
| few-shot-synthetic-3 | 0.241164 | 0.250627 | 0.105234 | 100.0000% | 0 | 1.9112 | 0.9690 s |

Few-shot exceeded zero-shot Macro-F1 by `0.018166`. The paired 10,000-replicate bootstrap 95%
interval for `few-shot - zero-shot` was `[0.002977, 0.034469]`; the interval excluded zero and the
point difference exceeded the frozen `0.005` practical threshold. The registered selection rule
therefore selects `few-shot-synthetic-3` for the constrained system. This selection is dev-only.

Both conditions exceeded EXP-018 Macro-F1 by `0.019353` and `0.037520`, respectively, but remained
below the EXP-020 BERT three-seed mean by `0.266437` and `0.248271`. Thus frozen prompting produced
only a small gain over the lexical baseline and did not approach the supervised encoder.

The decoder blocked at least one unrestricted argmax step on all 5,426 zero-shot rows and on 503
few-shot rows. This telemetry does not by itself show how many final label sets changed; that
question is answered by the matched EXP-026 ablation. Total local runtime was `10000.27` seconds,
peak MLX memory was `3.6600` GB and API cost was USD 0.

Verified artifacts:

- [`../runs/exp-025-full-dev-zero-few-shot/run.json`](../runs/exp-025-full-dev-zero-few-shot/run.json)
- [`../runs/exp-025-full-dev-zero-few-shot/aggregate-metrics.json`](../runs/exp-025-full-dev-zero-few-shot/aggregate-metrics.json)
- [`../runs/exp-025-full-dev-zero-few-shot/paired-bootstrap.json`](../runs/exp-025-full-dev-zero-few-shot/paired-bootstrap.json)
- [`../runs/exp-025-full-dev-zero-few-shot/verification.json`](../runs/exp-025-full-dev-zero-few-shot/verification.json)
