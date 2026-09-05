# SQMA-007：Dev-C1 visible JudgeV2 shakedown

## 1. 状态与目的

- Experiment：`SQMA-007`
- Stage：`dev-c1-visible-judge-shakedown`
- 当前状态：`FrozenExecutionReady`
- 执行授权：`true`
- 样本层级：全部为 `visible_shakedown`，没有 locked content

SQMA-006 已证明 v3 Evidence 和 Critic 可以稳定产生 canonical output，但普通解码下的 v3 Judge 合同仍不稳定。SQMA-007 不重跑 SQMA-006，也不把失败改写为通过。它用一批全新的可见样本，单独测试固定六槽 JudgeV2 能否在 greedy decoding 下稳定渲染机器可消费的引用结构。

Evidence/Critic 的 v3 prompt 与 JudgeV2 的 v4 prompt/schema/validator identities 已分别冻结。执行授权只覆盖 16 个 fresh visible rows、48 次调用和冻结模型；其余数据与后续动作仍未授权。

## 2. Fresh C1 selection

输入仅限 SQMA-002 fold 0、1、2 的三份 gold-free snapshots。选择过程不读取 gold、classifier、M1/M3、Router、SQMA-003 private、SQMA-006 private、fold 3/4、validation 或 test。

1. 每个 `component_id` 只保留 `source_ordinal` 最小的代表行，预期共 1963 components。
2. 用 `SQMA-003-agent-dev-random-v1` 重算旧 top 32 并排除。
3. 在剩余集合中用 `SQMA-006-d1-fresh-agent-dev-random-v1` 重算 SQMA-006 fresh 32 并排除。
4. 在再次剩余的集合中，用 `SQMA-007-dev-c1-visible-shakedown-v1` 取前 16 个 components。
5. ranks 0–15 全部标记为 `visible_shakedown`；locked rows 为 0。

三个集合必须两两不相交。排除过程只重算 namespace hash，不读取两个旧实验的 private selection。

## 3. 48-call plan

每个 row 严格执行：

```text
Evidence v3, temperature=0.6
→ Critic v3, temperature=0.6
→ JudgeV2 fixed slots, greedy temperature=0
```

16 rows × 3 calls = 48 physical calls。Evidence invalid 时向 Critic 和 Judge 传入冻结 Evidence sentinel；Critic invalid 时向 Judge 传入冻结 Critic sentinel。这样可以完成 Judge 合同测试，但 Evidence/Critic validity 只作为诊断报告，不参与 Gate 1。

Judge context 的可见字段固定为：

- `analysis_text`
- `ontology`
- validated Evidence 或 Evidence sentinel
- validated Critic 或 Critic sentinel
- `allowed_evidence_ids`

`allowed_evidence_ids` 由实际送入 Judge 的 Evidence `evidence_spans` 位置确定。Judge 不得看到 gold、classifier result、其他 sample 或外部工具结果。

## 4. JudgeV2 fixed-slot contract

Judge renderer 接受 bare JSON object 或一个精确的 `json` code fence，不接受自然语言前后缀、多对象提取或语义修复。Gate 1 的 `raw_json_parse` 只把 bare JSON object 计为通过；exact fence 即使 rendered-valid，也记为 `raw_json_parse=false`，因此不能满足 16/16 raw gate。对象必须包含且只包含六个字段：

```json
{
  "love": [],
  "joy": [],
  "surprise": [],
  "anger": [],
  "sadness": [],
  "fear": []
}
```

每个字段的值都是 evidence-ID array。array 中每一项必须是 JSON integer，且必须属于当前 row 的 `allowed_evidence_ids`。同一槽内允许确定性排序与去重，但不得改变槽的空/非空状态；`reference_normalization_events`、`duplicate_references_removed` 和 `reference_order_normalized_slots` 作为 report-only aggregate 公开，允许非零且不计作 semantic repair。某个 label 的 array 非空时，该 label 被渲染为 present；空 array 表示 absent，最终 labels 始终按 `love, joy, surprise, anger, sadness, fear` 顺序渲染。Consumer 不补字段、不删额外字段、不改 key、不转换类型、不猜测 ID，也不根据文本修正 label。

合法引用只证明 ID 指向当前 Evidence 中存在的 exact-substring span，不证明该 span对相应 label 构成语义蕴含；本实验也不证明 Critic 对 Judge 有因果修正。

## 5. Gate 1

Gate 1 要求：

- 48/48 calls terminal；
- Judge raw JSON parse：16/16；
- Judge exact six fields：16/16；
- no extra/missing key：16/16；
- six values 均为 arrays：16/16；
- 所有 reference items 均为 integers：16/16；
- 所有 reference IDs 均在当前 allowlist：16/16；
- semantic repair：0；
- unhandled failures：0；
- Judge rendered-valid：16/16；
- token-cap hits：0；
- process memory、MLX memory、wall time、output bytes 和 conservative full projection 均在冻结上限内。

Evidence/Critic canonical validity 只报告，不是 Gate 1。Full projection 使用 672 rows 的 Evidence、Critic、Judge 三次调用 p95 latency，加 25% buffer 和一次 model load。

## 6. 失败与后续边界

任一 Judge 合同项失败时，SQMA-007 记录为：

```text
ordinary_decoding_c1_failed
→ constrained_decoding_decision
```

失败不会自动触发 prompt revision、v4 修改、retry、constrained decoding run 或下一个实验。C1 内容可被查看，用于决定是否登记 constrained-decoding 实验；任何后续方法变化都必须形成新的冻结配置。

若 Gate 1 全部通过，只能说明普通 greedy decoding 在这 16 个 visible samples 上满足固定槽合同。它不证明准确率、locked 稳定性、角色贡献、同源 Confirm 或跨数据泛化。

## 7. 计划工件

Private：

- `selection.json`
- `calls.jsonl`
- `private-manifest.json`

Public：

- `run-claim.json`
- `run.json`
- `verification.json`
- `complete.json`

Public 只允许 aggregates、资源、identity 与 Gate 1 结果，不包含文本、row IDs、raw output、rendered slots 或 evidence。

## 8. Execution-ready boundary

Config 已分别绑定：

1. JudgeV2/v4 prompt identity；
2. exact six-slot schema identity；
3. raw-only JudgeV2 validator/renderer identity；
4. runner、independent verifier 和 tests identities。

Evidence/Critic generation 必须读取冻结 v3 bundle，Judge generation 必须读取冻结 v4 bundle；不得用 v4 中的简写 Evidence/Critic system 替代 v3 prompt。Static tests 和 static verifier 通过后，producer 可按已登记授权执行。任何 identity、selection、权限、资源或 prompt-source drift 都必须在 private input/model load 前停止。
