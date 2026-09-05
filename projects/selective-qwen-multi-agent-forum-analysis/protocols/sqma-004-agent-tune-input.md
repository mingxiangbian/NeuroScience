# SQMA-004：Agent-Tune Fold-3 Input Materialization

日期：2026-09-04

层级：`Major infrastructure / data governance / no model`

状态：`Registered design / execution not authorized`

## 1. 目的与结论边界

SQMA-004 为后续完整 672-row Agent-Tune matched comparison 准备 fold 3 的两类密封输入：

- Agent producer 可读的 `gold-free-inference.jsonl`；
- 独立 scorer 可读的 `consumer-gold.npz`。

该单元不创建 `train-capable`，不加载模型、不训练、不生成 Agent 输出，也不计算任何准确率。即使通过，也只能声明 fold 3 的 classifier-free Tune 输入已按冻结身份和顺序生成并独立验证；它不等于 Agent-Tune 比较已执行或通过。

## 2. 前置门

执行前必须同时满足：

1. D0 classifier-free amendment 身份不变；
2. SQMA-002 completion 与 verification 保持 Passed；
3. SQMA-003 classifier-free Agent-Dev preflight 已完成并独立通过；
4. 本协议、config、runner、verifier 与 tests 的 bytes/SHA-256 已全部登记；
5. public/private 输出目标均不存在。

当前 SQMA-003 尚未形成绑定的 completion，因此 config 保持 `execution_authorized=false`。

后续绑定的 SQMA-003 completion 必须使用实际 completion schema 中的字段 `accuracy_scored=false`，并同时满足 `sqma003_complete=true`、`agent_preflight_verified=true`、`preflight_gate=Passed`、`gold_accessed=false` 和 `model_training_executed=false`。不存在的 `accuracy_evidence` 字段不得作为跨门依据。

## 3. 来源与解码边界

唯一输入仍为冻结的三份同序来源：

- EXP-058 public fold manifest；
- `DATA-SO-TASK-V1` private train；
- EXP-058 private fold manifest。

Data steward 使用 `zip_longest` 逐行读取三份来源，并先解析 public 行：

- public fold=3：才允许 UTF-8 decode 两份 private 行，并进行三方 sample/component/label/derived-field join；
- public fold=0、1、2、4：两份 private 行只进入流式 SHA-256，不调用 `decode()` 或 `json.loads()`；
- 任一来源提前结束、出现额外行或 source hash 前后变化，立即停止。

Access 必须明确记录：完整 private bytes 已流式读取；只 decode fold 3 的 672 行；folds 0–2 与 fold 4 的 private decoded rows 均为 0。不得笼统声称 private source 未读。

## 4. Private 输出

```text
private/sqma-004-agent-tune-input/attempt-1/
  fold-3/
    gold-free-inference.jsonl
    consumer-gold.npz
  private-manifest.json
```

`gold-free-inference.jsonl` exact fields：

`schema_version, protocol_id, sample_id, component_id, fold_id, source_ordinal, text`

`consumer-gold.npz` exact arrays：

- `sample_ids[672]`：Unicode，禁止 object dtype/pickle；
- `component_ids[672]`：Unicode，禁止 object dtype/pickle；
- `fold_ids int8[672]`，全部为 3；
- `source_ordinals int32[672]`；
- `gold uint8[672,6]`。

禁止创建 `train-capable`、fold 0–2 或 fold 4 输出。目录必须为 0700、文件必须为 0600、当前 UID 所有、link count=1、无 symlink/hardlink/temp/extra 文件。

## 5. 成功门

1. 三项 source identity、mode、owner 和 source hash before/stream/after 完全一致。
2. 三份来源严格 3,360 行对齐；仅 fold 3 private 行被 decode。
3. fold 3 输出为 672 rows / 657 components，source ordinal 严格递增。
4. sample/component/order/member hashes分别为冻结值；无 duplicate 或 component cross-fold。
5. public/train/private fold-3 行的 sample/component/labels/neutral/cardinality 逐项一致。
6. gold-free JSONL exact schema且递归不含 gold/label/target/neutral/cardinality 派生字段。
7. NPZ members、shape、dtype 和 values 与 source join 独立一致，`allow_pickle=false`。
8. 两类输出 sample/component/fold/source-order 完全一致，text 逐字保真。
9. private manifest 记录 source lineage、artifact identity、membership/value digests 和真实 access，但不自引用。
10. public 工件不含 text、IDs、gold、labels、逐行 digest 或 private 绝对路径。
11. independent verifier 不 import runner、不相信 runner aggregate，并重新读取 source 与输出复算。
12. 任一检查失败时整体失败，不得把部分工件提供给 Agent-Tune。

## 6. Public 输出

```text
runs/sqma-004-agent-tune-input/attempt-1/
  run-claim.json
  run.json
  verification.json
  complete.json
```

`run-claim.json` 必须在任何 private byte access 前写入。`complete.json` 只能在独立 verification Passed 后生成。Public 只允许 aggregate counts、schema/artifact identities、资源、access 与失败类别。

## 7. 资源与停止

- steward/verifier 各自 wall 不超过 300 秒、RSS 不超过 1 GiB；
- private output 不超过 64 MiB、public output 不超过 16 MiB、开始时 free disk 至少 20 GiB；
- model/MLX/Agent/network/validation/test 访问为 0；
- critical-memory、OOM、kill 和 orphan process 为 0。

Source drift、fold 0–2/4 decode、任何非 fold-3 输出、gold-free 污染、public 泄漏、mode/symlink/resource 异常均立即停止。Runner 失败保留 partial namespace；纯 verifier bug 可以登记 append-only recovery 并复用 sealed output，数据或 materialization 错误必须新 attempt，不能修改旧工件。

## 8. 完成与下一门

通过时必须记录：

- `sqma004_complete=true`
- `agent_tune_inputs_verified=true`
- `fold3_output_rows=672`
- `fold0_2_private_rows_decoded=0`
- `fold4_private_rows_decoded=0`
- `train_capable_created=false`
- `model_loaded=false`
- `training_executed=false`
- `agent_calls=0`
- `agent_tune_comparison_authorized=false`
- `next_gate=register_full_672_row_agent_tune_matched_comparison`

SQMA-004 通过后不自动运行 Agent-Tune。
