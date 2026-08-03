# EXP-023: Fixed Label-ID Parser Repair Trial

Registration date: 2026-07-31 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-023`
- Tier: `Minor`
- RQ: `RQ-G2 implementation gate`
- Parent: `EXP-022`
- Stage: controlled label-ID prompt/parser repair
- Status: completed and independently verified; parser gate failed
- Config: [`../configs/exp-023-label-id-parser-trial.json`](../configs/exp-023-label-id-parser-trial.json)
- Config SHA-256: `53ed7eafd5c227e97c0dde197644b35fff1ba6d7d7f1d4986e39d6ab525e2e93`
- Prompt: [`../prompts/exp-023-label-id-v1.json`](../prompts/exp-023-label-id-v1.json)
- Prompt SHA-256: `09079207271900b84db7ab0f209bf884a22f67f2f2872a2e3ea88cab9c5f2516`
- Runner SHA-256: `0e4c77ef39d79fc07266bdc67db9ee615eb86e8a81cfc10c48eea6fb53dd9add`
- Verifier SHA-256: `66145f893f01fc9425ef4b2ee9d28069edb6a7c6f9a8ca2fd95911e8e632eefb`

## Question and Controlled Change

EXP-022 的资源门通过，但 few-shot 自由标签字符串的严格解析率只有 `87.5%`。
EXP-023 只检验一个实现修复：把输出从自由标签名 JSON
`{"labels":["joy"]}` 改为固定整数 ID JSON `{"label_ids":[17]}`。

以下内容保持不变：

- EXP-022 的同一批 32 条匿名 train 样本、顺序和长度分层；
- Qwen3-1.7B post-trained MLX BF16 模型及 revision；
- zero-shot 与三个固定合成示例的 few-shot 条件；
- greedy decoding、thinking off、batch size 1、最大 64 个生成 token；
- 64 次测量、两次合成 warm-up、资源预算和每条件 95% parser 门。

本实验不评估情绪分类性能，不读取或保留 gold label，不访问 dev/test，也不据此
选择标签、示例或模型。通过只表示该固定接口具备登记正式 full-dev Major 的工程
条件。

## Frozen Inputs and Selection

- Dataset: `DATA-GOE-V1` official agreement-filtered train split.
- Train rows: 43,410; SHA-256
  `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Labels: 28 ordered names; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- EXP-022 selection digest:
  `7dcdbe002627948d6e1c5ed4eceb950085585ad0c726333ba3012515dbd8c525`.
- Selection utility: frozen EXP-022 runner SHA-256
  `d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e`.
- Dev is prohibited. Test remains absent and prohibited.

The runner may parse only the text and comment-ID columns needed to reconstruct the frozen
sample. Gold label strings are discarded immediately and never retained, evaluated or written.
Public artifacts expose only sample index, length stratum, character count and aggregate hashes.

## Frozen Label-ID Interface

The prompt includes the complete ordered ontology:

```text
0=admiration, 1=amusement, 2=anger, 3=annoyance, 4=approval,
5=caring, 6=confusion, 7=curiosity, 8=desire, 9=disappointment,
10=disapproval, 11=disgust, 12=embarrassment, 13=excitement,
14=fear, 15=gratitude, 16=grief, 17=joy, 18=love, 19=nervousness,
20=optimism, 21=pride, 22=realization, 23=relief, 24=remorse,
25=sadness, 26=surprise, 27=neutral
```

After surrounding whitespace is removed, the entire output must parse as one JSON object:

```json
{"label_ids":[17]}
```

Validity requires:

- exactly one key named `label_ids`;
- a non-empty list of unique integers; booleans are not integers for this schema;
- every integer is in the inclusive range 0 through 27;
- ID 27 (`neutral`) is not combined with another ID;
- no prefix, suffix, Markdown, explanation or additional key.

Invalid output is counted without retry, synonym mapping, label-name fallback, neutral deletion
or any other silent repair. Valid outputs may retain only canonical ID JSON; invalid outputs retain
only SHA-256, character count and error category.

## Resource Budget and Gate

- 32 fixed train rows and 64 measured generations.
- One synthetic warm-up per condition, excluded from measured summaries.
- Maximum wall time: 30 minutes.
- Peak MLX memory: at most 14.0 GB.
- Linear 5,426-row dev estimate: at most 8 hours per condition.
- Strict parser validity: at least 95% in each condition.
- Generation failures and length-terminated outputs: zero.
- Network/API disabled; API cost USD 0.

The full-dev estimate is an engineering projection for the same unbatched implementation, not a
task-performance result. If any gate fails, preserve the run and register another controlled
repair rather than editing this experiment.

## Required Artifacts and Verification

```text
runs/exp-023-label-id-parser-trial/
├── run.json
├── summary.json
├── selected-samples.json
├── sample-results.jsonl
├── stdout.log
└── verification.json
```

The independent verifier must reconstruct the EXP-022 sample, confirm the same selection digest
and condition order, recompute all aggregates and gates, verify frozen hashes, confirm test is
absent, and reject public raw text, comment IDs, gold labels or unrestricted generations.

## Decision Rule

Only a verified pass on every frozen gate permits registration of a formal full-dev zero/few-shot
Major. EXP-023 itself does not authorize running that Major, selecting a prompt on dev, or claiming
classification accuracy.

## Execution Result

EXP-023 completed on 2026-07-31 and its deterministic sample identity, artifacts, aggregate
measurements, gates and privacy boundary were independently verified.

- The same 32 anonymous EXP-022 train samples produced 64 measured generations; gold labels,
  dev and test were not accessed.
- All time, memory, generation-failure and truncation checks passed. Total runtime was `73.4471`
  seconds and peak MLX memory was `3.7260` GB.
- Zero-shot strict validity was `16/32 = 50.0%`; all 16 invalid outputs were `invalid-json`.
- Few-shot strict validity was `21/32 = 65.625%`; invalid outputs comprised nine
  `neutral-combined` and two `duplicate-label-id` cases.
- Linear full-dev estimates were `1.4665` hours for zero-shot and `1.7883` hours for few-shot.

The overall gate failed solely on strict parser validity. Replacing label names with numeric IDs
therefore did not repair EXP-022 and substantially reduced format validity in both conditions.
The completed run remains a negative implementation result and does not authorize full-dev.

Artifacts:

- [`../runs/exp-023-label-id-parser-trial/summary.json`](../runs/exp-023-label-id-parser-trial/summary.json)
- [`../runs/exp-023-label-id-parser-trial/verification.json`](../runs/exp-023-label-id-parser-trial/verification.json)
