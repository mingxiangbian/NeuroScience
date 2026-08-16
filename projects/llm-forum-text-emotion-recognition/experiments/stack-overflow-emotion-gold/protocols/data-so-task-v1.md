# DATA-SO-TASK-V1: Stack Overflow C0 多标签数据协议

- Protocol ID: `DATA-SO-TASK-V1`
- Frozen date: 2026-08-13
- Tier: Major data protocol
- RQ: `RQ-S1`
- Registration status before execution: `Registered`
- Execution status: `Verified` on 2026-08-13
- Source revision: `d6a679f39a198fdb0657a6116d35dd7b92496898`
- Split seed: `20260813`

## 1. 目的与边界

本协议把 Stack Overflow Emotion Gold Standard 的固定 XLSX 重建为六标签、target-only
的 C0 多标签任务。它只完成来源核验、标签复算、重复项绑定、数据划分和 test 封存，
不训练模型、不运行推理，也不读取任何模型结果。

工作簿只提供文本和发布内部坐标，没有经过核验的 Stack Overflow post/thread ID。
因此本版本只能称为 `duplicate-component-disjoint, multi-label-stratified split`，不得称为
thread-disjoint，也不得据此研究上下文收益。上下文恢复属于独立的条件协议。

## 2. 来源与许可边界

- Repository: <https://github.com/collab-uniba/EmotionDatasetMSR18>
- Input: `data/stack-overflow-emotion-gold/official/Emotions_GoldSandard_andAnnotation.xlsx`
- Expected SHA-256:
  `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`
- Upstream paper: Novielli, Calefato and Lanubile (2018), *A Gold Standard for
  Emotion Annotation in Stack Overflow*, DOI `10.1145/3196398.3196453`.

仓库 README 要求研究使用时引用论文，但仓库中没有标准化 `LICENSE` 文件。论坛原文还
可能受 Stack Overflow 内容许可与署名义务约束。本阶段采用保守边界：原始 XLSX、逐行
文本、逐行标签、标注者票和 sealed test 全部只在 Git-ignored 私有目录使用；公开层只
保存处理代码、协议、聚合统计、哈希和不含原文/标签的匿名 split ID。该边界不是法律意见。

## 3. 工作簿与标签重建

固定 sheet 顺序及标签顺序为：

```text
Love_all -> love
Joy_all -> joy
Surprise_all -> surprise
Anger_all -> anger
Sadness_all -> sadness
Fear_all -> fear
```

每个 sheet 必须有相同的 4,800 条数据行，且 `(Group, Set, local number, Text)` 逐行完全
一致。`Group/Set/local number` 只作为发布内部坐标，不解释为用户、post 或 thread ID。

每个标签的三位 rater 单元格只允许空值或大小写不敏感的 `x`。两票及以上为 1，否则为
0；重建值必须与该 sheet 的 `Gold Label` 完全一致。任一 sheet、行、标记或 gold 不一致，
协议立即失败，不进行猜测性修复。

冻结输出顺序为：

```text
[love, joy, surprise, anger, sadness, fear]
```

六维全为 0 时派生 `neutral=true`。主任务不是七类 softmax；训练时使用六个独立 sigmoid
输出和 `BCEWithLogitsLoss`。发布文件审计期望值为：

- love 1,220；joy 491；surprise 45；anger 882；sadness 230；fear 106；
- 1,959 条零标签，2,708 条单标签，133 条双标签；不存在三标签及以上样本；
- 至少一个情绪的样本为 2,841，neutral 为 1,959。

论文正文曾把 1,959/2,841 描述为 emotion/neutral，与当前工作簿逐行重建、标签支持总数
及 133 条双标签不一致。正式实验以固定工作簿重建结果为准，并将这一冲突作为来源限制，
不静默修改数据以迎合论文表述。

## 4. 文本与 ID

模型文本保留工作簿中的原始字符串，不做小写化、URL 删除、代码删除或标点清洗。重复
检测专用规范化不得回写模型输入：

1. Unicode NFKC；
2. Unicode `casefold()`；
3. 连续空白压缩为一个 ASCII space；
4. 去除首尾空白。

公开 `sample_id` 是协议、source revision、发布内部坐标和原文共同生成的 SHA-256 截断
标识；`component_id` 由组件内排序后的 `sample_id` 生成。二者只用于固定 split，不是
Stack Overflow 原始 ID，也不能用于恢复 thread。

## 5. 重复项与冲突标签

先分别建立 exact-text equality 和上述 normalized-text equality 边，再取并集的 connected
components。组件是不可拆分的最小 split 单位。当前审计预期：

- exact unique text 4,687；99 个重复组件覆盖 212 行；
- normalized unique text 4,681；99 个重复组件覆盖 218 行；最大组件 10 行；
- 26 个重复组件、52 行具有不一致的六维 gold。

冲突重复项不得删除、合并标签或跨 split 分散。它们原样保留在同一组件，并在私有诊断和
聚合限制中报告。这会保留来源数据的标注歧义，也意味着部分相同文本存在不可约的监督冲突。

本版本不自动合并语义近似文本。没有经人工验证的 near-semantic equivalence 不能升级为
泄漏组件；相关检查只能作为后续敏感性分析。

## 6. Split 冻结

- Split ratios by retained rows: train 70%、validation 15%、test 15%。
- Seed: `20260813`。
- Unit: exact/normalized duplicate connected component。
- Stratified dimensions: 六个标签、`neutral`、`cardinality_1`、`cardinality_2`、
  component count、duplicate rows/components、conflicting-duplicate rows/components 和行数。
- Allocation: 先按最大余数目标和 component size 解出冻结的结构配额，再在各结构桶内按
  gold strata 和固定 seed 分配；随后只交换同一结构桶内的组件做 deterministic
  pair-swap refinement，因此任何 refinement 都不能改变 split 行数或重复项配额。
- 禁止先按行划分再事后搬运重复项；禁止读取模型输出决定 split。

验收条件在运行前冻结为：

1. 4,800 条样本恰好出现一次，sample/component ID 唯一且一致；
2. exact 与 normalized duplicate component 均不跨 split；
3. 每个 split 的行比例与目标绝对误差不超过 `0.005`；
4. 六个标签在三个 split 都至少有一个正例；
5. 每个标签在各 split 的分配比例与目标绝对误差不超过 `0.05`；
6. neutral、cardinality 1/2、component count、duplicate rows/components 和
   conflicting-duplicate rows/components 的分配比例误差不超过 `0.03`；
7. split 报告必须给出每类正例数、包含该类的组件数和全部偏差；
8. 任一条件失败则状态保持 `Failed/Unverified`，不得事后放宽阈值。

`surprise` 只有 45 个正例、分布于预期 43 个 duplicate components，是预先登记的低支持
标签。它保留在六标签主 Macro-F1 中，但不得为它单独选择阈值；正式模型需报告逐类指标、
component-bootstrap 区间、三 seed 波动及排除 surprise 的五标签敏感性分析。

### 2026-08-13 pre-execution correction

第一次 `/private/tmp` 数据 preflight 在行数、标签、neutral 和 cardinality 上通过，但由于
初始 greedy allocator 优先选取大组件，26 个 conflicting-duplicate components 全部进入
validation。该输出从未成为正式数据、未被模型读取，也没有写入项目数据目录。正式构建器
因此在运行前把 component、duplicate 和 conflict slices 加入同一分层目标，并沿用原来的
`0.03` slice 容差。该修正不改变样本、标签、split 比例、seed 或 test gate。

固定工作簿对应的可行整数结构配额如下；它们由 99 个重复组件的 size histogram 和
`70/15/15` 最大余数目标确定，不读取模型结果：

| Component bucket | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| singleton | 3,208 | 687 | 687 |
| conflicting duplicate, size 2 | 18 | 4 | 4 |
| non-conflicting duplicate, size 2 | 47 | 9 | 9 |
| non-conflicting duplicate, size 3 | 2 | 1 | 1 |
| non-conflicting duplicate, size 4 | 0 | 1 | 1 |
| non-conflicting duplicate, size 6 | 1 | 0 | 0 |
| non-conflicting duplicate, size 10 | 1 | 0 | 0 |

由此得到重复组件 `69/15/15`、重复行 `152/33/33`、冲突组件 `18/4/4`，并由单例补齐
总行数 `3,360/720/720`。若固定来源不再满足这些结构配额，应由 source expectation gate
直接失败，而不是自动产生一个含义不同的 task v1。

## 7. 私有输出与 Test Gate

- `train.jsonl`、`validation.jsonl`：文本、六维 gold、派生 neutral 与组件元数据。
- `test.inputs.jsonl`：只含 sample/component ID 和文本，不含任何 gold 派生字段。
- `test.labels.sealed.jsonl`：只含 sample ID 与 gold 字段。
- `duplicate-conflicts.jsonl`：只在私有层保存冲突组件的匿名成员与标签向量。
- `private-manifest.json`：数据与私有产物哈希。

`official/` 与 `derived-private/` 目录权限收紧为 `0700`，其中全部文件为 `0600`；Git ignore
不是唯一的隐私控制。公开协议、代码、匿名 split index 和聚合报告不采用此限制。

本数据 verifier 可以为验证构建正确性读取 sealed labels；后续训练、阈值、prompt、checkpoint
选择和 validation 代码不得读取。第一次模型 test 评估仍需建立统一 `TEST-READY` 合同并
取得用户明确授权。

## 8. 公开产物

公开：

- 本协议、构建器、独立 verifier 和 synthetic unit tests；
- 匿名 `sample_id/component_id/split` 索引；
- 聚合 construction/verification report 与 artifact hashes。

公开文件不得包含论坛原文、发布内部 `Group/Set/local number`、逐行标签、rater votes 或
test gold。公开 split 索引不能被模型当作标签来源。

## 9. Stop Conditions

出现以下任一情况立即停止，不标记 `Verified`：

- source revision/hash 或 workbook 结构不匹配；
- 六个 sheet 未逐行对齐；
- gold 无法由三位 rater 的多数票复算；
- 发布统计或重复审计无法复算；
- split 超出冻结容差或 duplicate component 跨 split；
- test inputs 含标签、neutral、label cardinality 或 rater 信息；
- 私有数据未被 Git 忽略，或公开产物泄露原文/逐行标签；
- 私有目录或文件对 group/other 开放读取；
- 独立 verifier 未通过全部检查。

## 10. Execution Result

`Verified`。正式构建与独立 verifier 于 2026-08-13 完成，事实结果如下：

- 固定来源 revision 为 `d6a679f39a198fdb0657a6116d35dd7b92496898`，XLSX SHA-256 为
  `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`；六个 sheet
  的 4,800 行逐行对齐，全部 gold 均由三位 rater 的两票多数规则精确复算。
- 4,800 行按 4,681 个 connected components 划分为 train/validation/test
  `3,360/720/720` 行、`3,277/702/702` 个组件；没有 exact 或 normalized duplicate
  component 跨 split。
- 六标签支持数为 love `1,220`、joy `491`、surprise `45`、anger `882`、sadness `230`、
  fear `106`；`surprise` 在三个 split 中为 `31/7/7`，不存在零支持 split。
- 重复组件为 `69/15/15`、重复行为 `152/33/33`、冲突重复组件为 `18/4/4`；冲突重复项
  保留且绑定在同一 split。
- 最大标签分配比例误差为 `0.011111`，最大预登记 balance slice 分配比例误差为
  `0.007692`，行比例误差为 `0.0`，均通过冻结阈值。
- 独立 verifier 通过 `53/53` 项检查，synthetic unit tests 通过 `11/11`；正式私有目录为
  `0700`、文件为 `0600`，并经 Git-ignore 与公开内容扫描核验。
- test inputs 不含标签或标签派生字段，test labels 状态为
  `sealed_not_authorized_for_model_access`。本协议没有训练、推理或评价任何模型，test 尚未
  被模型实验消费。

机器可读结果见
[`reports/data-so-task-v1.json`](../reports/data-so-task-v1.json) 与
[`reports/data-so-task-v1-verification.json`](../reports/data-so-task-v1-verification.json)。
