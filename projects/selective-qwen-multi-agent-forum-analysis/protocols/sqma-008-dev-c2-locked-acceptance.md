# SQMA-008：Dev-C2 locked acceptance

## 1. 状态与目的

- Experiment：`SQMA-008`
- Stage：`dev-c2-locked-acceptance`
- 当前状态：`FrozenReady`
- 执行授权：`true`
- 样本层级：24个`locked_acceptance` components，无visible shakedown

SQMA-008不是SQMA-007的恢复attempt，也不修改SQMA-003、SQMA-006或SQMA-007的工件。SQMA-007已完成48/48 calls，Judge在16/16 visible rows上通过bare raw、六键、整数引用、allowlist与rendered合同，随后通过独立verification并写入completion。因此ordinary greedy分支被保留，失败条件对应的constrained-decoding decision没有触发。SQMA-008用一批未进入前三次Agent-Dev预检的新components检查同一合同能否在locked acceptance set上保持零违规。

本实验不读取gold、不评分准确率，也不比较Single、Self-Consistency、Role-diverse或Selective。Runner、independent verifier与tests已绑定最终identity，完整config的exact pins与mutation tests已建立。执行授权只覆盖SQMA-002 fold 0–2 gold-free private input、冻结模型和72次generation；SQMA-008尚未执行。

## 2. 前置条件与冻结方法

执行前必须同时满足：

1. SQMA-007 C1的public run、verification与completion均已通过并绑定到SQMA-008 config；
2. SQMA-008绑定SQMA-007实际执行时的Prompt、schema、validator/renderer、模型、backend、chat template、thinking mode、role token caps和sampling参数；
3. 除C2选择namespace、输出namespace和调用样本外，不得改变通过C1的方法条件；
4. SQMA-008 runner、independent verifier和tests已根据完整config补齐exact pins；执行前仍须由independent static verifier复核当前identity与授权profile。

冻结Judge合同使用C1的六个label slots：

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

每个slot只能包含当前row Evidence spans的整数ID；`allowed_evidence_ids`必须等于`list(range(len(evidence.evidence_spans)))`。Evidence与Critic沿用C1绑定的v3合同，Judge沿用C1绑定的v4 fixed-slot合同。

## 3. C2 selection

唯一候选池是SQMA-002封存的fold 0、1、2 gold-free snapshots。每个`component_id`只保留`source_ordinal`最小的代表行，预期为1,963个components。选择排序只使用`component_id`和`source_ordinal`，不使用文本内容、gold、classifier、M1/M3、Router、模型特征或旧Agent输出。

按以下顺序重算并排除旧集合：

1. 在完整代表池中，用`SQMA-003-agent-dev-random-v1`按`SHA256(namespace|component_id)`升序重算SQMA-003的32个components；
2. 在剩余池中，用`SQMA-006-d1-fresh-agent-dev-random-v1`重算SQMA-006的32个components；
3. 在再次剩余的池中，用`SQMA-007-dev-c1-visible-shakedown-v1`重算SQMA-007 C1的16个components；
4. 排除上述80个components后，用新namespace `SQMA-008-dev-c2-locked-acceptance-v1`取前24个components。

每一步的排序键固定为`(SHA256(namespace|component_id), component_id)`，不存在从旧private selection读取ID的捷径。四个集合必须两两不相交；任一步component count、pool顺序、namespace、代表行或overlap异常均在模型加载前停止。C2 ranks 0–23全部为locked，不允许先查看部分输出再修订Prompt或合同。

## 4. 72-call plan

每个row严格顺序执行：

```text
Evidence v3
→ Critic v3
→ Judge v4 fixed slots
```

24 rows × 3 calls = 72 physical calls。不得增加Single、Self-Consistency、repair call、重采样或provisional system。Evidence invalid时，Critic与Judge只接收C1冻结的Evidence sentinel；Critic invalid时，Judge只接收C1冻结的Critic sentinel。任一row发生Evidence或Critic fallback，该row计一次system fallback。

生成参数与通过的C1一致：analysis-text cap 1,024、context cap 4,096、`thinking=false`、top-p 0.95、top-k 20；Evidence为temperature 0.6/max-new 256，Critic为0.6/192，Judge为greedy temperature 0/max-new 128。C2使用自己的确定性seed namespace `SQMA-008-dev-c2-generation-v1`，seed material仍为`namespace|system_id|sample_id|role|call_index`。所有repair calls为0。

Judge可见字段仍为`analysis_text`、`ontology`、validated Evidence或sentinel、validated Critic或sentinel、`allowed_evidence_ids`。任何角色均不得看到gold、classifier output、fold 3/4、validation、test、其他sample或外部工具结果。

## 5. Deterministic renderer边界

Judge raw output必须能被C1的raw JSON parser解析为单一object，并包含且只包含`love, joy, surprise, anger, sadness, fear`六个keys。Raw object不以key顺序作为有效条件；固定label顺序只用于deterministic rendering与derived labels。每个值必须是array；其中每一项必须是JSON integer且属于当前row的`allowed_evidence_ids`。不允许补missing key、删除extra key、映射label、转换类型、增加或丢弃非法ID、跨slot移动ID、改变slot emptiness或依据文本修正标签。

同一slot内合法ID的排序和去重是C1预先允许的确定性renderer行为。它必须单独报告：

- `reference_normalization_events`；
- `duplicate_references_removed`；
- `reference_order_normalized_slots`。

这些事件不算semantic repair，也不因计数大于0而失败。`normalization_ambiguity`只指预登记排序/去重规则无法唯一决定输出的情况；它必须为0。Renderer不得调用Qwen、外部工具或任何语义修复步骤。

## 6. Locked acceptance gate

所有24个C2 rows共同组成唯一acceptance set。通过必须同时满足：

- 72/72 calls terminal，调用顺序与seed replay一致；
- Judge raw JSON parse：24/24；
- Judge exact six-key set：24/24；
- Judge missing/extra keys：0 rows；
- Judge non-array slot values：0 rows；
- Judge non-integer reference items：0 rows；
- Judge illegal reference IDs：0 rows；
- Judge rendered-valid：24/24；
- semantic repair：0；
- normalization ambiguity：0；
- unhandled failure：0；
- contract error：0；
- Evidence validator-valid rate：`>= 0.95`；
- Critic validator-valid rate：`>= 0.95`；
- system fallback rows：`<= 1`；
- token-cap hits：0；
- wall `<= 7,200 s`、MLX peak `<= 10,000,000,000 bytes`、RSS `<= 12,884,901,888 bytes`、generated tokens `<= 13,824`，并满足冻结的output-byte与free-disk边界。

Evidence与Critic validity以及system fallback是运行门，不是准确率或角色价值指标。Normalization events只报告，不进入零事件门。

## 7. 结论边界

若Judge达到24/24，只能写为：

> 在预先排除SQMA-003、SQMA-006和SQMA-007样本后确定选择的24个Agent-Dev C2 locked components上，冻结C1 Judge合同未观察到违规。

24/24不能写成总体Judge合同有效率`>= 0.98`，也不能证明future Tune、Confirm、其他论坛或任意输入上的零违规。该结果同样不支持准确率提高、Evidence与标签的语义蕴含、Critic因果贡献或多智能体优于匹配对照。SQMA-008仍属于同来源Agent-Dev acceptance，不是Agent-Tune、Agent-Confirm或外部泛化证据。

## 8. 失败与停止规则

任何Judge零容忍项失败、Evidence/Critic门失败、fallback超过1行、调用不完整、identity/access/resource drift或独立重放失败，都将SQMA-008记为`Failed`并保留sealed/partial工件。失败后不得查看locked逐行内容来修改同一实验，不自动retry、修Prompt、修改C1合同、启动SQMA-009或进入formal comparison。

只有producer gate与independent verification均通过时才可创建`complete.json`。即使通过，后续实验也必须另行登记；`automatic_next_stage`保持`false`。

## 9. 计划工件

Private：

- `selection.json`
- `calls.jsonl`
- `private-manifest.json`

Public：

- `run-claim.json`
- `run.json`
- `verification.json`
- `complete.json`

Public只允许aggregates、artifact identity、访问记录、资源和gate结果；不得包含row ID、文本、raw/rendered output、slot references、evidence span或label set。Independent verifier不得import runner或模型框架，必须重算四段selection、72-call schedule、seed、C1合同结果、允许的normalization events、fallback与全部门禁。

## 10. FrozenReady边界

当前config已绑定C1 public run/verification/completion、Prompt/schema/validator、SQMA-008 runner、independent verifier和tests的identity，并写明attempt-1命令与输出namespace。`execution_authorized`、`private_input_access`、`model_loading`与`generation`为`true`；其余权限均为`false`，包括gold、classifier、adapter、training、locked content visibility、validation、test、fold 3/4、network与automatic next stage。Runner进程可以读取确定选择的24个C2 locked gold-free rows，但不得把其文本、raw output或row identity暴露到public工件或人工修订路径。
