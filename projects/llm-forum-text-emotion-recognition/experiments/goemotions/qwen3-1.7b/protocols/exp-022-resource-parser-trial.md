# EXP-022: Qwen3-1.7B Small-sample Resource and Parser Trial

Registration date: 2026-07-31 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-022`
- Tier: `Minor`
- RQ: `RQ-G2 implementation gate`
- Parent: `EXP-021`
- Stage: small-sample throughput and parser budget
- Status: completed and independently verified; resource gate failed
- Config: [`../configs/exp-022-resource-parser-trial.json`](../configs/exp-022-resource-parser-trial.json)
- Config SHA-256: `58fce1005e1dc8a61fcb122ea4748df1ecf9d0916d29dd3557ced2bfbfb0e10e`
- Prompt: [`../prompts/exp-022-resource-v1.json`](../prompts/exp-022-resource-v1.json)
- Prompt SHA-256: `2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c`

## Question and Boundary

在不评估情绪分类性能的前提下，本地未量化 BF16 `Qwen3-1.7B` post-trained
模型能否以可接受的时间和内存稳定处理真实长度分布的 GoEmotions 文本，并按严格
JSON schema 输出可解析标签？

本实验只决定是否具备登记正式 zero/few-shot Major 的工程条件。它不计算或查看
Accuracy、F1、gold label，也不比较 Base、BERT、LoRA 或 4B。任何生成内容都不能
作为模型更懂情绪的证据。

## Frozen Data Sampling

- Dataset: `DATA-GOE-V1` official agreement-filtered train split.
- Train rows: 43,410; SHA-256
  `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Labels: 28 ordered names; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Dev is prohibited. Test remains absent and prohibited.
- The runner parses only the text and comment-ID columns. Gold label strings are discarded,
  never retained, never evaluated and never written to artifacts.

The fixed sample contains 32 train rows. All rows are ranked by text character length and split
into four rank quartiles. Within each quartile, the eight smallest deterministic salted hashes of
the comment ID are selected. The exact rule is frozen in the config. This gives eight measured
texts per length stratum without selecting on labels or model output.

Artifacts expose only sequential sample indices, length strata and aggregate selection hashes.
They do not contain raw text, upstream comment IDs or gold labels.

## Frozen Model and Conditions

- Model: `Qwen/Qwen3-1.7B`
- Revision: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Local runtime: EXP-021 verified MLX BF16 conversion
- Quantization: none
- Network/API: disabled; API cost USD 0
- Thinking: disabled
- Decoding: greedy, batch size 1, maximum 64 generated tokens
- Prompt cache and KV-cache quantization: disabled

Each selected text is measured once in each condition:

1. `zero-shot`: system instruction plus the target comment.
2. `few-shot-synthetic-3`: the same instruction plus three fixed synthetic demonstrations and
   the target comment.

The synthetic demonstrations are prompt-shape controls, not selected GoEmotions examples. One
synthetic warm-up per condition is excluded from measured summaries. Measured condition order
alternates by sample index to reduce a fixed first-condition ordering effect.

## Strict Parser

After surrounding whitespace is removed, the entire output must parse as one JSON object:

```json
{"labels":["joy"]}
```

Validity requires:

- exactly one key named `labels`;
- a non-empty list of unique strings;
- every string belongs to the frozen 28-label ontology;
- `neutral` is not combined with another label;
- no prefix, suffix, Markdown or explanation outside the JSON object.

The parser is frozen before the run. Invalid output is counted, not repaired or retried.

## Measurements and Privacy

Record for every measured generation:

- prompt tokens, generated tokens and finish reason;
- end-to-end generation seconds;
- prompt and generation tokens per second reported by MLX-LM;
- MLX peak memory;
- strict parser validity and error category;
- output character count and SHA-256;
- parsed labels only when strict validation succeeds.

Do not store raw input text, comment IDs, gold labels or unrestricted raw generations. A valid
output may be stored only as canonical label JSON; an invalid output is represented only by its
hash, size and error category.

## Resource Budget and Gate

- 32 selected train rows.
- 64 measured generations plus two synthetic warm-ups.
- Maximum wall time: 30 minutes.
- Peak MLX memory: at most 14.0 GB.
- Projected full 5,426-row dev runtime: at most 8 hours per condition.
- Strict parser validity: at least 95% in each condition.
- Generation failures and length-terminated outputs: zero.

The full-dev estimate is a linear engineering estimate for this unbatched, no-prompt-cache
implementation. It is not a benchmark claim and may not generalize to other hardware or code.

If any gate fails, retain the run and revise the implementation or prompt under a new experiment
ID. Do not edit this parser or silently retry outputs after seeing failures.

## Required Artifacts

```text
runs/exp-022-resource-parser-trial/
├── run.json
├── summary.json
├── selected-samples.json
├── sample-results.jsonl
├── stdout.log
└── verification.json
```

The independent verifier must reconstruct the deterministic sample, recompute all aggregates,
check model/config/prompt/data hashes, confirm that test is absent and reject any raw text,
comment-ID or gold-label field in public artifacts.

## Next Decision

Passing EXP-022 permits registration of a formal full-dev zero/few-shot Major. It does not freeze
the final prompt or prove that either prompting condition is accurate. Prompt selection and any
classification comparison remain validation-only decisions under a later protocol.

## Execution Result

EXP-022 completed on 2026-07-31 and its saved aggregates, deterministic sample selection, hashes
and privacy boundary were independently verified.

- 32 anonymous train samples produced 64 measured generations; dev and test were not accessed.
- Total measured run time was `62.2052` seconds, including a `2.0504` second model load.
- Overall peak MLX memory was `3.6541` GB; no OOM or length termination occurred.
- Zero-shot mean generation latency was `0.8296` seconds, giving a linear full-dev estimate of
  `1.2504` hours. Strict parser validity was `31/32 = 96.875%`.
- Few-shot mean generation latency was `0.9829` seconds, giving a linear full-dev estimate of
  `1.4815` hours. Strict parser validity was `28/32 = 87.5%`.
- Few-shot invalid outputs comprised three `unknown-label` cases and one `neutral-combined` case;
  zero-shot had one `unknown-label` case.

All time, memory, completion and truncation checks passed. The overall gate failed solely because
few-shot strict parser validity was below the frozen 95% threshold. Therefore EXP-022 does not
authorize a formal full-dev run. A new experiment ID must freeze one controlled prompt/parser
repair and retest the same engineering gate without using gold labels.

Artifacts:

- [`../runs/exp-022-resource-parser-trial/summary.json`](../runs/exp-022-resource-parser-trial/summary.json)
- [`../runs/exp-022-resource-parser-trial/verification.json`](../runs/exp-022-resource-parser-trial/verification.json)
- Runner SHA-256: `d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e`
- Verifier SHA-256: `02c88592fd968eba5e58ebba84b8d83e228c8725d9f0f6a1842a950f1e0fa20d`
