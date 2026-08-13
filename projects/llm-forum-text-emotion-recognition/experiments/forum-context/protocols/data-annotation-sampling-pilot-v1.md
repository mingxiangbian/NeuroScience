# DATA-FCTX-SAMPLE-V1: 论坛情绪标签校准抽样协议

> 2026-08-07 execution amendment: the project author reclassified this sample as
> exploratory dataset diagnosis and authorized direct three-source comparison
> without the planned blind-repeat pass. See
> [`data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison.md`](data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison.md).

- Date frozen: 2026-08-05
- Dataset: IAC 2.0 `4forums`
- Input pipelines: `DATA-FCTX-CLEAN-V2`, `DATA-FCTX-DEDUP-V2`
- Annotation protocol: `DATA-FCTX-LABEL-V1`
- Purpose: ontology and annotation-view calibration, not final training data
- Unique annotation cases: 120
- Blind repeats: 24
- External API annotation: forbidden

## 1. Purpose and frozen boundary

本协议在查看任何真实 pilot 文本或人工标签前，冻结校准样本的数量、候选池、分层、随机
排序、重复标注和替换规则。它回答的是：现有标签定义和上下文视图是否足以进入下一轮
正式数据设计，而不是估计 4forums 的精确总体情绪比例，也不是直接构造 train/dev/test。

本协议冻结：

1. 120 个独立案例及 24 个盲重复的预算；
2. 80 个受约束随机样本和 40 个诊断性富集样本的用途边界；
3. 每个 thread 和 unresolved near-duplicate cluster 的抽取上限；
4. 固定 seed、hash 排序和四个诊断 strata；
5. reserve、`unusable` 替换和停止条件；
6. 一位人工标注者下的 intra-annotator consistency 记录与接受门。

本协议不冻结最终训练 ontology、正式标注规模、标签聚合方法、数据 split 或模型配置。
盲重复不是额外训练样本，40 个富集案例也不得与 80 个随机案例合并后声称自然类别分布。

## 2. Frozen inputs

抽样实现必须逐字节核对以下输入；任一 hash 不符即停止：

| Input | SHA-256 |
| --- | --- |
| `cleaning-v2.sqlite` | `b1f3022320980c96c5353be16401764a78e0bc40ebb21d71399fe4efcb05fcc7` |
| `dedup-v2.sqlite` | `13a5266a12f9574f073c3c7ce72e785e7d019573961507e1b0631f0a50bd7d4f` |
| `DATA-FCTX-LABEL-V1` | `0de4bf6243f223ea1a72b3fa48867b59abf6cd19ff95104ff53d00856b0d376a` |

抽样 seed 冻结为：

```text
07f4b8c18479c240af5354cc1d316fb8
```

所有随机次序使用确定性 rank：

```text
SHA256("DATA-FCTX-SAMPLE-V1\n" + seed + "\n" + lane + "\n" + sample_uid)
```

按 digest 的无符号十六进制升序排列，`sample_uid` 只在 gitignored 私有环境中参与计算，
不得写入公开报告。不同用途使用不同 `lane`，不能重用一次随机排列后人工挑选。

## 3. Candidate frame and global constraints

候选必须同时满足：

- cleaning `candidate_pairs.eligible = 1`；
- dedup `candidate_decisions.eligible_after_auto_dedup = 1`；
- parent、target、discussion title 和 V1 所需 quote view 可由冻结输入重建；
- 不属于 153 个自动删除的 exact/format-only candidates。

120 个 active unique cases 全局遵守：

- 每个 `thread_uid` 至多一个案例；
- 每个非空 `review_cluster_uid` 至多一个案例；
- 同一个 `sample_uid` 只能进入一个 sampling lane；
- IAC 既有 topic、sarcasm、hostility 和 argument-style 值不得显示给标注者；
- 不按情绪关键词、模型预测或人工预览正文挑样本。

公开的 403,183 是 pair 数，不是 403,183 个独立线程。上述约束会使 80 个随机案例成为
**受约束的 pair-level random sample**，适合观察校准分布，但不是严格简单随机样本；不得
从 80 条计算总体置信区间或把比例写成 4forums 的精确 prevalence。

topic link 只覆盖部分讨论，因此 topic 不作为配额。抽样后只做隐藏的 known-topic/
unlinked-topic、长度、quote 和 soft-flag 分布审计，不因审计结果更换 seed。

## 4. Sample budget

| Lane | Unique cases | Purpose |
| --- | ---: | --- |
| `representative` | 80 | 粗略观察自然候选中的标签、neutral、unclear 和上下文变化 |
| `diag_sarcasm` | 10 | 检查 sarcasm 与 cynicism/anger/joy 等 primary emotion 的边界 |
| `diag_hostility_affect` | 10 | 检查攻击性、情感诉求与原子情绪标签是否被混淆 |
| `diag_short_context` | 10 | 检查短 target 在 parent/title/quote 揭示后是否变得可判定 |
| `diag_distinct_quote` | 10 | 检查非 direct-parent quote 是否提供独立上下文价值 |
| **Total unique** | **120** | ontology/view calibration |
| Blind repeats | 24 | 一位标注者的重复一致性诊断，不进入样本总数 |

预计人工工作量为 4--6 小时，分批完成；实际时长必须记录，不能用预计值替代。

## 5. Representative lane

使用 `lane=representative` 对完整 candidate frame 排序，从首条开始扫描。若候选与已选
案例共享 thread 或 unresolved review cluster，则跳过；否则接收，直到取得 80 条。

该 lane 的 label count、`neutral/unclear/other_emotion`、context sufficiency 和 Stage A/B
变化率必须单独报告。40 个 diagnostic cases 只能解释边界和失败模式，不能补进这 80 条
后重算所谓自然分布。

## 6. Diagnostic lanes

先固定 80 条 representative，再按下列顺序从剩余候选中各取 10 条。每个 lane 内按自身
hash rank 随机排序，继续执行全局 thread、review cluster 和 sample 唯一性约束。

### 6.1 `diag_sarcasm`

候选 target 至少关联一条 IAC QR task-1 average annotation，且该行：

- `num_annots >= 3`；
- `sarcasm_yes >= 0.5`。

只读取 source ID linkage 和平均分，不读取 IAC 的 `presented_quote` 或
`presented_response`。该分数是隐藏抽样信号，不是 V1 sarcasm gold，更不是情绪标签。

### 6.2 `diag_hostility_affect`

候选 target 至少关联一条 `num_annots >= 3` 的 QR task-1 average annotation，并满足以下
任一条件：

- `attacking_respectful <= -2`；
- `nasty_nice <= -2`；
- `emotion_fact <= -2`。

这些维度分别表示攻击/不尊重、负面互动姿态和偏 feelings 的论证方式。它们只用于富集
可能暴露标签边界的案例，不得重命名为 anger、disgust、cynicism 或其他 emotion gold。

### 6.3 `diag_short_context`

候选包含冻结 cleaning flag `target_short`，即 target 自身少于 3 个 ASCII word tokens。
短文本不自动判为 neutral 或 unusable；该 lane 专门检验上下文揭示能否解决信息不足。

### 6.4 `diag_distinct_quote`

target 至少有一个有效 top-level quote，且其来源不是 direct parent，或来源无法在 IAC
关系中解析。该 lane 检验 target 主动引用的额外文本是否带来 direct parent 之外的信息。
quote 的 source relation 可以进入 V1 私有 view，但源 discussion/post ID 不进入 view。

若任一 diagnostic lane 在全部约束后不足 10 条，不得临时降阈值或改用关键词补齐；抽样
preflight 必须标记 `blocked`，并在新版本或 dated amendment 中明确替代规则。

## 7. Reserves and replacement

primary 120 条选定后再生成 reserve：

- representative reserve 20 条；
- 每个 diagnostic lane reserve 10 条，共 40 条；
- reserve 使用 `lane=<lane>_reserve` 的独立 hash rank；
- reserve 也必须与全部 primary 和其他 reserve 保持 thread、review cluster、sample 唯一。

只有 contextual decision 为 `status=unusable` 的案例可以按同 lane reserve 顺序替换。
`neutral`、`unclear`、low confidence、情绪稀有、标签难分或结果不符合预期都不得替换。
被替换案例及原因继续保留在私有审计记录中，但不计入 120 个 analyzable unique cases。

若初始 120 条中超过 6 条（5%）为 `unusable`，立即停止继续替换，先审查 view exporter、
清洗规则和 hard filter；不得通过不断取 reserve 隐去数据质量问题。

## 8. Blind repeats

完成全部 120 个 analyzable unique cases 后，才选择 repeat：

- representative 中 16 条，使用 `lane=repeat_representative`；
- 四个 diagnostic lane 各 2 条，使用 `lane=repeat_<diagnostic-lane>`；
- 合计 24 条，即每个 lane 的 20%；
- repeat 使用相同 `sample_uid` 和 `view_sha256`，但使用新的私有
  `annotation_instance_uid`；
- 第二次标注不得显示首次标签、note、confidence、repeat 标记或抽样 lane。

repeat 在第一次 120 条完成至少 72 小时后作为独立 pass 呈现，并重新执行 Stage A 和
Stage B。两次之间不得查看首次逐样本记录。24 条 repeat 不得进入类别频率、训练数据量
或样本总数，只用于 intra-annotator consistency。

## 9. Annotation order and model assistance

- 120 个 unique cases 在 pass 1 内按 `lane=annotation_order` 统一 hash 排序，界面不显示
  representative/diagnostic 身份。
- 单次连续标注不超过 40 条；开始和结束时间由工具记录。
- 人工 pass 1 和 blind-repeat pass 完成前，不显示任何模型建议或 IAC 原有标注。
- 两个 human-blind passes 完成后，本地模型可以独立生成 sidecar 建议，用于定位分歧；
  它不计作第二位人工标注者。
- IAC 原文不得发送到外部 LLM API、公共标注平台或远程日志服务。

## 10. Analysis and acceptance gates

### 10.1 Structural gates

进入 ontology review 前必须全部满足：

1. 120 个 analyzable unique cases 完成 Stage A 和 Stage B；
2. 120 个 active cases 对应 120 个不同 thread；
3. 非空 unresolved review cluster 没有重复；
4. 24 个 blind repeats 完成，且两次 `view_sha256` 一致；
5. sampling lane、IAC 弱标注和首次决定从 annotator view 中隐藏；
6. Git 中没有真实文本、source ID、HMAC ID、逐样本标签或 manifest。

### 10.2 Consistency gate

分别报告 Stage A 与 Stage B 的 status-plus-label exact agreement；`other_emotion` 还需比较
规范化后的 proposal。Stage B 是主 gate：

- `20--24/24`：通过 repeat consistency gate；
- `18--19/24`：进入 boundary review，修订说明后再决定是否追加 targeted calibration；
- `0--17/24`：V1 不足以进入正式标注，必须修订标签或视图并建立新 calibration 版本。

同时报告 raw agreement、Cohen's kappa 及 bootstrap interval，但 24 条样本很小，kappa
只作诊断，不单独决定通过。该结果只能称 intra-annotator consistency，不能称
inter-annotator agreement。

### 10.3 Ontology and context review triggers

以下规则触发复核，不自动增删或合并标签：

- representative 中 contextual `context_sufficiency=insufficient` 超过 16/80：审查是否建立
  包含祖先链的 `DATA-FCTX-LABEL-V2`；
- representative 中 contextual `unclear` 超过 20/80：审查标签边界或任务定义；
- representative 中 `other_emotion` 至少 4/80，或同一 proposal 在全部 120 条中至少出现
  3 次：把该原子情绪列入 ontology review；
- 任一候选标签在全部 120 条中少于 3 个 contextual uses：证据不足，不得仅凭本 pilot
  宣布删除，也不得据此开始正式训练；
- 同一标签对在 repeats 中出现至少 3 次互换，或一个已有至少 5 个案例的标签中超过一半
  为 low confidence：必须复核对应 operational definition。

neutral 比例高、某类稀有、Stage A/B 不变或模型后来不认同人工标签都不是失败条件。
Stage A/B 变化率受顺序效应影响，只支持“上下文揭示后判断发生变化”的描述，不构成
上下文因果收益或模型性能结论。

## 11. Required outputs and reporting boundary

未来 sampler/exporter 只能把真实逐样本产物写入：

```text
data/iac2/annotations/pilot-v1/
  sampling-manifest.jsonl
  reserve-manifest.jsonl
  repeat-manifest.jsonl
  views/
  records/
```

该目录必须保持 gitignored。可追踪产物仅包括：

- 本协议；
- 不含文本、source/HMAC ID 或逐样本标签的 aggregate sampling preflight；
- 独立 verification report；
- pilot 完成后的聚合分布、一致性和决策说明。

representative 与四个 diagnostic lanes 必须分表报告；reserve 和 repeat 不参与类别分布。
任何公开示例必须是 synthetic，不得从真实 IAC 文本改写后伪装为 synthetic。

## 12. Execution order and change control

执行顺序冻结为：

```text
verify frozen input hashes
-> build metadata-only candidate frame
-> select 80 representative cases
-> select 4 x 10 diagnostic cases
-> generate reserves
-> independently verify counts and uniqueness
-> export private V1 views
-> human-blind pass 1
-> wait at least 72 hours
-> blind-repeat pass
-> aggregate review and ontology decision
```

在 preflight 验证通过前不得读取或标注真实 sample。以下变化必须建立
`DATA-FCTX-SAMPLE-V2` 或在执行前登记明确 amendment，不能静默修改 V1：

- 改变 120/24 的预算或 80/40 配额；
- 改变 seed、hash rank、diagnostic thresholds 或 lane 顺序；
- 允许同 thread/review cluster 多例；
- 用关键词、模型预测或人工预览筛样本；
- 改变 repeat 数量、72 小时间隔或替换条件；
- 把 diagnostic 样本并入 representative prevalence。

仅修正文案、链接或不改变抽样结果的说明可以追加 dated correction note。

## References

- [`DATA-FCTX-LABEL-V1`](data-label-calibration-view-v1.md)
- [`DATA-FCTX-CLEAN-V2`](../dataset-construction/protocols/data-cleaning-quality-filter-v2.md)
- [`DATA-FCTX-DEDUP-V2`](../dataset-construction/deduplication/protocols/data-deduplication-v2.md)
- [IAC 2.0 source assessment](../../../../../sources/llm-forum-text-emotion-recognition-iac2-assessment.md)
