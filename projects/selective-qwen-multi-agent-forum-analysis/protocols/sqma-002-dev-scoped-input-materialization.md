# SQMA-002：Agent-Dev Scoped-Input Materialization

日期：2026-09-03

层级：`Major infrastructure / data governance / no model`

状态：`Registered / execution authorized for scoped materialization only`

## 1. 目的与结论边界

SQMA-002由独立data steward把完整private train和EXP-058 fold assignment转换为folds 0–2的密封输入，使后续M1/M3训练producer无需打开monolithic train或接触fold 3/4行值。

该单元不加载模型、不训练、不产生logits、不评价Agent或分类性能。通过后最多声明：

> folds 0–2的strict Agent-Dev输入已按冻结身份和顺序生成，并通过独立内容验证；正式训练仍未执行或授权。

## 2. 输入与访问方式

唯一private来源：

- `DATA-SO-TASK-V1` train：3,360行；
- EXP-058 private fold manifest：3,360行。

辅助public来源是EXP-058 public fold manifest。三者已由冻结构建流程按`sample_id`排序，但runner和verifier仍逐行zip核对，不能只依赖这一假设。

先解析public行：

- public fold为0–2时，才decode对应private train和private manifest行；
- public fold为3–4时，只流式读取相同行字节，不JSON decode、不使用或输出其值。

因此access必须写成：

- `monolithic_private_bytes_streamed=true`；
- `private_rows_decoded=2016`；
- `fold3_rows_decoded=0`；
- `fold4_rows_decoded=0`。

不能写成private source完全未读，也不能把monolithic路径传给后续模型producer。

## 3. Private输出

每个fold 0、1、2各生成三份工件，共9份：

```text
private/sqma-002-dev-scoped-input/attempt-1/
  fold-0/
    train-capable.jsonl
    gold-free-inference.jsonl
    consumer-gold.npz
  fold-1/...
  fold-2/...
  private-manifest.json
```

### Train-capable

包含：`schema_version, protocol_id, sample_id, component_id, fold_id, source_ordinal, text, labels, label_cardinality, neutral`。

### Gold-free inference

只包含：`schema_version, protocol_id, sample_id, component_id, fold_id, source_ordinal, text`。禁止`labels/gold/target/neutral/cardinality`及其变体。

### Consumer-only gold

NPZ exact arrays：

- `sample_ids[672]`
- `component_ids[672]`
- `fold_ids int8[672]`
- `source_ordinals int32[672]`
- `gold uint8[672,6]`

禁止object dtype、pickle、text、logits和额外array。

`source_ordinal`是train JSONL的零起始全局行号。每个fold内部保持该顺序；未来组合多个fold时按`source_ordinal`全局排序，不能直接按fold拼接。

## 4. 完整成功门

1. protocol/config/contract/runner/verifier/tests与三项source identity全部匹配；source前后hash不变。
2. source均为当前用户所有的regular non-symlink文件，private mode为0600；路径无glob或逃逸。
3. 三份source逐行对齐；folds 0–2的sample/component/labels/derived字段一致，无duplicate、missing或unknown row。
4. 输出每fold672行，components为658/654/651；总计2,016 rows、1,963 components；fold3/4 output rows严格为0。
5. 每fold三个scope的sample/component/fold/source-order完全一致；train与inference text逐字一致；consumer gold与train labels逐位一致。
6. JSONL exact schema；label vector固定六位0/1，cardinality和neutral复算一致；gold-free inference递归禁止gold-derived字段。
7. NPZ exact members、shape、dtype和value；`allow_pickle=false`，ZIP member无重复。
8. private目录0700、文件0600、owner为当前UID、link count为1、无symlink/hardlink/temp/extra文件。
9. private manifest记录source lineage、logical artifact、bytes/SHA/mode、counts、order/membership/value digest，但不自引用。
10. public run/verification只含aggregate、schema ID、artifact identity、资源和access；无text、IDs、gold、labels、逐行digest或private绝对路径。
11. independent verifier不import runner，不信任runner自报counts；重新读取冻结source和全部output复算。
12. 任一fold/scope失败则整体失败，不能把部分snapshot交给训练。

## 5. Public输出

```text
runs/sqma-002-dev-scoped-input/attempt-1/
  run-claim.json
  run.json
  verification.json
  complete.json
```

`run-claim.json`必须在private访问前写入，预先声明允许的source与机械访问边界。`complete.json`只能在独立verification Passed后生成。

## 6. 资源与停止

- steward/verifier各自wall不超过300秒、RSS不超过1 GiB；
- private output不超过128 MiB，public output不超过16 MiB，开始时free disk至少20 GiB；
- model/MLX/Agent/network/validation/test访问均为0；
- critical-memory、OOM、kill和orphan process均为0。

任何source drift、fold3/4输出、gold-free污染、public泄漏、mode/symlink/resource异常均立即停止。runner失败保留partial namespace，不删除后重跑。纯verifier bug可登记append-only recovery并复用sealed output；数据或materialization错误必须使用新attempt，不能修改旧工件。

## 7. 完成与下一门

通过时必须记录：

- `sqma002_complete=true`
- `scoped_inputs_verified=true`
- `training_executed=false`
- `model_loaded=false`
- `agent_calls=0`
- `fold3_output_rows=0`
- `fold4_output_rows=0`
- `formal_training_authorized=false`
- `next_gate=register_strict_agent_dev_formal_three_m1_three_m3`

SQMA-002通过后不自动启动训练。
