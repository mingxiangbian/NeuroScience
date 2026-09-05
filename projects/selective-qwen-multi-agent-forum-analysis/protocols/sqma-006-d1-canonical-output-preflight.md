# SQMA-006：D1 fresh canonical-output preflight

## 1. 状态

- Experiment：`SQMA-006`
- Stage：`d1-fresh-canonical-output-preflight`
- 当前状态：`FrozenExecutionReady`
- 执行授权：`true`
- 授权范围：仅 SQMA-002 fold 0–2 gold-free input、冻结 Qwen 模型和 120 次 generation

本文件冻结 D1 的抽样、调用预算、统计口径、grammar mode 和停止规则。v3 prompt、输出 schema、canonicalizer、runner、verifier 与 tests 的 immutable identities 已绑定。gold、classifier、adapter、training、fold 3/4、validation、test、network 与 automatic next stage 仍未授权。

## 2. 为什么是 SQMA-006，而不是 SQMA-003 attempt 3

SQMA-003 attempt 2 已完成 144 次调用，但 capability gate 失败。D1 不再只修改同一批样本上的 prompt。它同时改变三项方法条件：

1. 从 Agent-Dev 重新抽取一批与 SQMA-003 不重叠的 32 个 component；
2. 删除 `provisional_s2b` 的额外 24 次调用，将 physical cap 从 144 降为 120；
3. 将主门禁从 raw strict JSON validity 改为 canonical system-output validity，raw strict validity 只保留为诊断。

这些变化使 D1 不再是对同一实验的 verification recovery，所以登记为新实验 `SQMA-006`。SQMA-003 的 Failed 结论保持不变。

## 3. 数据边界

唯一输入是 SQMA-002 已封存的 fold 0、1、2 三份 `gold-free-inference.jsonl`。选择过程只允许读取：

- `sample_id`
- `component_id`
- `fold_id`
- `source_ordinal`
- `text`
- schema/protocol identity

选择排序只使用 `component_id` 和 `source_ordinal`，不使用 `text`、gold、分类器输出、模型特征或先前 agent 输出。fold 3、fold 4、validation、test、`consumer-gold`、`train-capable`、M1、M3 与 Router 均禁止访问。

## 4. Fresh selection

1. 在 2016 个 Agent-Dev rows 中，每个 `component_id` 只保留 `source_ordinal` 最小的代表行；预期得到 1963 个 component。
2. 使用旧 namespace `SQMA-003-agent-dev-random-v1`，按 `SHA256(namespace|component_id)` 升序重算旧 top 32。
3. 从候选池中排除这 32 个 component。此步骤不读取 SQMA-003 private selection。
4. 对剩余 component 使用新 namespace `SQMA-006-d1-fresh-agent-dev-random-v1`，按同一规则取前 32 个。
5. 新 selection ranks `0–7` 为 shakedown，`8–31` 为 locked。
6. Single pool 只覆盖 locked ranks `8–15`。

若输入 component 数不是 1963、旧排除集不是 32 个、新 selection 不足 32 个或两个集合有交集，立即失败。

## 5. 调用计划

| System | Rows | Calls per row | Physical calls |
|---|---:|---:|---:|
| S3 role-diverse | 32 | 3 | 96 |
| Single pool | locked ranks 8–15，共 8 rows | 3 | 24 |
| Total |  |  | 120 |

S3 顺序固定为 `evidence → critic → judge`。Single pool 使用 v3 `single` role，每行固定 `call_index=0,1,2`。S1 复用 single call 0；SC 复用同一行三次 single calls。不得为 S1、SC 或任何 provisional system 增加物理调用。

generation seed 使用 `SQMA-006-d1-generation-v1|system_id|sample_id|role|call_index` 的 SHA-256 前 4 bytes，以 big-endian unsigned integer 解释。

## 6. Canonical output contract

v3 冻结后，每次调用必须同时保存：

- 原始输出与 raw strict validation 结果；
- 确定性 canonicalization 的结果、错误码和 canonical output；
- 最终 label set；
- evidence exact-substring 与 ontology diagnostics；
- token、latency、seed、输入上下文和 prompt identity。

Grammar mode 固定为 `no_native_grammar_exact_json_fence_canonicalizer_v1`：不使用模型后端的 native constrained decoding。唯一允许的 consumer 是 `validate_agent_output_v3.validation_result` 所实现的 exact-fence syntax-only canonicalizer。它只接受 bare JSON object 或一个精确的 `json` code fence，去除允许的 wrapper 后进行 canonical JSON serialization；不得补字段、改标签、修 evidence 或做其他语义修复。

Canonicalization 必须是确定性的本地过程，不得触发额外 Qwen repair call、外部工具或网络访问。canonical output 只有在 v3 role schema、evidence 和 ontology 约束全部通过时才算 valid。invalid 或 token-cap 的最终 label set 为空；S3 任一角色 canonical-invalid 时，该 row 计入 fallback，后续角色只接收冻结 sentinel。

角色可见上下文固定为：Evidence 只看 `analysis_text + ontology`；Critic 只额外看 `evidence`；Judge 只额外看 `evidence + critic`；Single 只看 `analysis_text + ontology`。四个角色均不得看到 gold、classifier result、M1/M3/Router output、其他 sample 或外部检索结果。

Raw strict validity 仍公开报告 overall/per-role 数值，但不参与 pass/fail。这样可以区分“模型原始字符串已经是 bare strict JSON”的格式能力与“允许 exact fence 后，确定性 consumer 能否得到合法系统输出”的系统能力。grammar mode 和 canonicalizer 规则不得在看到 D1 输出后修改。

这里的证据边界必须保留：合法 `evidence_refs` 只说明 Judge 引用了 Evidence Appraisal 中存在且与原文精确匹配的 span，不证明该 span 对每一个输出 label 构成语义蕴含。Critic 的结构化输出只记录一个可复算的中间判断；即使最终 Judge 输出与 Critic 建议一致，也不能据此声称 Critic 对预测产生了因果修正。任何角色贡献或因果解释仍需单独消融和匹配对照。

## 7. Locked gate

除 call completion、token hits 和 full-Tune projection 外，validity、fallback、evidence、ontology 与 agreement 均以 locked records 为分母。门禁同时要求：

- planned calls：`120/120` terminal；
- canonical system-output validity overall：`>= 0.98`；
- canonical validity per role：每个 role `>= 0.95`；
- locked S3 fallback rows：`<= 1`；
- token-cap hits：`0`；
- evidence exact-substring rate：`1.0`；
- out-of-ontology labels：`0`；
- ranks 8–15 三次 Single 输出的 mean modal exact-label-set agreement：`>= 0.85`；
- conservative full-Tune wall projection：`<= 172800 s`。

Full-Tune projection 继续使用：

```text
model_load_seconds
+ 1.25 × 672 × (
    p95(evidence)
  + p95(critic)
  + p95(judge)
  + 3 × p95(single)
)
```

任何一项失败，`SQMA-006` 停在 Failed，不进入 Tune scoring、Confirm 或 Selective。

## 8. 输出与独立验证

计划 private inventory：

- `selection.json`
- `calls.jsonl`
- `private-manifest.json`

计划 public inventory：

- `run-claim.json`
- `run.json`
- `verification.json`
- `complete.json`

Public 只允许 aggregate、artifact identity、资源与 gate 结果，不得包含 row ID、文本、raw/canonical output、evidence span 或 label set。Independent verifier 不得 import runner 或模型框架；它必须重算 fresh selection、120-call schedule、seed、canonicalization、fallback、agreement、资源投影和全部门禁。

## 9. Execution-ready boundary

Config 必须绑定以下 immutable identities：

1. `agent-bundle-v3-classifier-free.json`
2. `agent-output-v3.schema.json`
3. `validate_agent_output_v3.py` 及 canonicalizer API
4. 已冻结的 `no_native_grammar_exact_json_fence_canonicalizer_v1` contract identity

上述 identities、模型 revision、runtime、input snapshots、selection namespace、call plan 与 gate 已共同冻结。Static tests 和 independent static verifier 通过后，producer 可按已登记授权执行；任一 identity、权限、资源或 schema drift 都必须在 private input/model load 前停止。Producer 完成且 public gate 通过后才允许 independent verifier 读取 sealed private calls；verifier 失败或 producer gate 失败时不创建 `complete.json`，也不自动进入后续实验。
