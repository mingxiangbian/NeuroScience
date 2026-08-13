# DATA-FCTX-LABEL-V1: 原子情绪标签校准与上下文标注视图协议

- Date frozen: 2026-08-05
- Dataset: IAC 2.0 `4forums`
- Input pipelines: `DATA-FCTX-CLEAN-V2`, `DATA-FCTX-DEDUP-V2`
- Stage: before sampling, annotation and split assignment
- Annotation task: staged single-primary-label calibration
- External API annotation: forbidden
- Emotion intensity: not collected

## 1. Purpose and frozen boundary

本协议冻结论坛标注 pilot 的任务定义和数据视图，避免在看到 pilot 分布或模型结果后
改变标签含义或上下文边界。它冻结：

1. target、上下文和标注案例的单位；
2. 用于 ontology calibration 的原子候选标签及判定边界；
3. `target-only -> context-revealed` 两阶段标注顺序；
4. 反讽、混合情绪、`neutral`、`other_emotion` 和 `unclear` 的处理；
5. 私有标注视图与 sidecar 标注记录的机器可读契约；
6. 隐私、泄漏和变更控制边界。

本协议不冻结最终训练 ontology。最终类别数必须在小规模 pilot 完成后，由类别频率、
可区分性、重复标注一致性和任务价值共同决定，并建立新版本。它也不决定 pilot 样本数、
分层比例、抽样 seed、train/dev/test 或训练模型；这些属于下一份 sampling protocol。

## 2. Unit definitions

三个单位不得混写：

- **存储候选单位**：清洗和去重阶段已有的 `direct parent -> target` pair。
- **标注案例单位**：一个 target，加上 discussion title、direct parent 和 target 自己
  引用的文本；不含任何后续回复。
- **预测单位**：target 发帖者自己的正文。标签只描述 target 在当前回复中表达或传达的
  情绪，不描述 parent、被引用者、整个讨论或标注者自己的情绪。

标注对象是可观察的 communicated emotion，不声称恢复作者不可观察的真实内心状态。
target 复述、否定或批评他人的情绪时，不自动继承该情绪标签。

## 3. Frozen context view

V1 上下文窗口按以下字段组成：

```text
discussion title
 direct parent model_body
 target quote blocks
 target model_body / model_full
```

具体规则：

- `discussion title` 使用清洗后的 `title_model`，单独保存，不拼接进正文。
- `direct parent` 只显示 parent 的 `model_body`，不递归展开 parent 自己的引用。
- `target quote blocks` 保留 target 主动选择引用的文本、原顺序和可解析的来源关系。
- `target body` 是 target 发帖者自己的正文；引用位置保留明确占位标记。
- `target full` 仅用于 context-revealed 视图，按清洗协议显示带边界的引用正文。
- root post、其他祖先回复和完整线程暂不加入 V1。
- 未来回复严格禁止进入视图、prompt 或人工判断。

若 title、parent 和 target quote 仍不足以判断，标记
`context_sufficiency=insufficient`，不得自行搜索论坛、查看后续回复或猜测缺失上下文。
是否扩展到祖先链由 pilot 的不足记录决定，不能在本协议下静默扩窗。

## 4. Two-stage annotation order

每条样本按固定顺序处理：

### Stage A: target-only

只显示 `target.body`。引用正文隐藏，但引用位置可以显示为 `[quoted text omitted]`，避免
删除占位后破坏句法。标注者提交并锁定：

- status；
- primary emotion；
- confidence。

Stage A 锁定后不得因看到上下文而回改。

### Stage B: context-revealed

再显示 discussion title、direct parent、target quote blocks 和 target full，提交最终：

- status；
- primary emotion；
- confidence；
- sarcasm；
- mixed emotion；
- context sufficiency；
- 必要的短 note。

若案例标为 `unusable`，只要求 confidence 和说明原因的 note；sarcasm、mixed emotion
和 context sufficiency 留空，避免为不可用文本伪造判断。

论文主任务的人工 target 是 Stage B 的 contextual decision。Stage A 只用于判断缺失
上下文时的可判定性以及上下文是否改变标签，不是第二套 gold。由脚本根据两阶段记录派生
`unchanged`、`changed`、`resolved_from_unclear` 或 `not_comparable`，不要求标注者手填。

同一标注者先看 target 再看上下文会产生顺序效应，因此 label-change 只能视为受控的
诊断证据，不等同于两个独立标注者之间的因果实验。

## 5. Calibration seed ontology

以下 10 种情绪和 `neutral` 是本轮 calibration 的冻结候选。每个名称表示一个原子
类别，不得把相邻但不同的情绪合并为同一标签。

| Label | Operational definition | Do not collapse into |
| --- | --- | --- |
| `anger` | 明确的愤怒、谴责、敌意或针对人/事件的激烈对抗 | frustration、disgust、普通 disagreement |
| `frustration` | 因目标受阻、反复失败、无效沟通或无法推进而产生的挫败 | anger、disappointment |
| `disappointment` | 先前期待未实现，对人、结果或承诺落空的失望 | sadness、frustration |
| `sadness` | 因损失、痛苦或不幸表达的悲伤、低落 | disappointment、compassion |
| `fear` | 对威胁、危险或可能伤害的害怕 | confusion、一般 uncertainty |
| `joy` | 明确的愉悦、开心或享受 | 礼貌、赞同、gratitude、pride |
| `surprise` | 对意外或违背预期事件的惊讶 | confusion、disbelief |
| `confusion` | 明确表示无法理解、理清或解释 | surprise、rhetorical question |
| `disgust` | 生理、道德或社会意义上的厌恶和排斥 | anger、disagreement |
| `cynicism` | 对他人诚意、动机或结果持嘲讽性不信任 | sarcasm 本身、普通 skepticism |
| `neutral` | target 没有清楚表达以上候选情绪；事实陈述或立场分歧可以是 neutral | unclear、无情绪词但可推断的明确情绪 |

两个非核心出口不直接作为最终训练类别：

- `other_emotion`：存在清楚情绪，但不在候选表中；必须填写具体名称。不得把它强塞进
  最相近标签。
- `unclear`：即使在相应阶段的可见信息下，也无法稳定判断主要情绪，或多个情绪没有
  可判定的主次。`unclear` 不是 neutral。

`unusable` 是数据质量状态，只用于文本损坏、非目标语言或其他导致案例无法进入标注的
情况。它不表示情绪难判断；情绪难判断应使用 `unclear`。

`cynicism` 是从 RESEMO 借鉴的论坛领域候选，兼具情绪与互动态度属性，不被预设为
跨领域的基本情绪。pilot 必须专门检查它能否与 sarcasm、skepticism 和 disagreement
稳定区分。

校准后只保留有实际样本支持、定义可操作且对论文任务有价值的原子类别。低频类别可以
退出主任务或留在 `other_emotion` 审计层，但不得通过临时合并制造支持数。

## 6. Single-primary-label rule

每个阶段最多选择一个 primary emotion：

1. 选择 target 当前交际行为中最突出的情绪，而不是话题通常会引发的情绪。
2. 多种情绪同时存在但有明显主导项时，选择主导项，并在 Stage B 记
   `mixed_emotion=true`。
3. 多种情绪没有稳定主次时，使用 `status=unclear`，不得任意挑一个。
4. `other_emotion` 只用于明确但表外的情绪，并填写简短、原子的英文名称。
5. 不从关键词直接映射；否定、引用、反问和反讽都要按完整语义判断。

V1 不收集 secondary label。若 pilot 表明混合情绪普遍且可以稳定标注，必须另建
多标签协议，不得事后把 `mixed_emotion` 当作第二标签。

## 7. Sarcasm and close-boundary rules

Sarcasm/irony 是独立的修辞属性，不是自动情绪标签。Stage B 使用：

- `present`：上下文足以支持非字面、反讽或嘲讽性表达；
- `absent`：没有此现象；
- `uncertain`：存在可能性但证据不足。

primary emotion 仍标注反讽实际传达的情绪。例如，嘲讽性不信任可以是
`cynicism + present`，带敌意的讽刺可以是 `anger + present`，友好调侃也可能是
`joy + present`。不得把所有 sarcasm 映射为 cynicism。

相邻类别优先使用以下判别问题：

- `anger` vs `frustration`：核心是攻击/谴责，还是目标受阻/无效沟通？
- `sadness` vs `disappointment`：核心是损失痛苦，还是期待落空？
- `surprise` vs `confusion`：核心是意外，还是无法理解？
- `disgust` vs `cynicism`：核心是厌恶排斥，还是对诚意/动机的不信任？
- `joy` vs `neutral`：是否真的表达愉悦，而不只是礼貌、赞同或陈述？

## 8. Intensity and confidence

V1 不收集 emotion intensity，也不允许从 confidence 推导强度。

`confidence` 只表示标注者对当前 decision 的把握：

- `high`：定义和上下文共同支持，替代标签明显较弱；
- `medium`：可判断，但存在合理替代；
- `low`：勉强可判，应进入复核。

低 confidence 不自动改成 unclear；反之，高 confidence 也不证明标签客观正确。

## 9. Machine-readable contracts

标注文本和标签分离保存，避免模型输入与 gold 混写：

- [`annotation-view-v1.schema.json`](../annotation/schemas/annotation-view-v1.schema.json)
  定义私有文本视图；
- [`annotation-record-v1.schema.json`](../annotation/schemas/annotation-record-v1.schema.json)
  定义 sidecar 标注记录；
- 两份 synthetic fixtures 只用于契约验证，不含 IAC 原文。

view 与 record 通过 `sample_uid` 关联。record 的 `view_sha256` 是 view 对象按 UTF-8、
key 排序、紧凑 JSON 分隔符序列化后的 SHA-256。Stage A 锁定、Stage B 展示及最终写入
由后续标注工具实现；工具不得把 Stage B 字段提前显示。

## 10. Privacy and annotation assistance

- 所有真实 view、annotation record 和逐样本 manifest 只能写入
  `data/iac2/annotations/`，保持 gitignored 和私有。
- view 不含源 discussion/post ID、作者、用户名、URL、人口属性或 IAC 既有评分。
- trackable fixture 必须完全 synthetic；公开文件只允许 schema、代码和聚合统计。
- IAC 原文不得发送到外部 LLM API、公共标注服务或公共存储。
- 本地模型可以产生独立建议，但不能称为第二位人工标注者，也不能在 human-blind 首标前
  显示给人工标注者。
- 最终 human gold 的形成过程必须记录为 blind、model-assisted 或 adjudicated，不能混写。

## 11. Deduplication and split constraints

本协议不抽样，但冻结后续协议必须满足：

- 同一 `thread_uid` 不得跨 train/dev/test；
- 同一 unresolved near-duplicate review cluster 的成员必须作为一组处理，或 pilot 中至多
  抽取一个成员；
- 自动删除的 153 条 pair 不得重新进入候选池；
- 抽样分层信息和 IAC 既有 sarcasm/hostility 分数不得显示给标注者。

## 12. Completion and change control

本阶段完成条件：

1. protocol、view schema、record schema 和 synthetic fixtures 均可解析；
2. fixture 的 `view_sha256` 可独立复算；
3. schema 不含 intensity 或 secondary-label 字段；
4. 真实 IAC 原文和源 ID 没有进入 Git；
5. 项目 roadmap 指向本协议，并明确最终 ontology 仍待 pilot。

以下变化必须建立 `DATA-FCTX-LABEL-V2`，不能直接改写 V1：

- 增删或合并 calibration labels；
- 从单 primary label 改为 multi-label；
- 增加情绪强度；
- 扩展到 root/ancestor/full-thread context；
- 改变两阶段展示顺序或允许回改 Stage A；
- 改变 sarcasm、neutral、other 或 unclear 的语义。

只修正文案笔误、链接或不改变语义的 schema 描述时，可以追加 dated correction note。

## References

- Chen et al. (2024), RESEMO: <https://aclanthology.org/2024.findings-acl.970/>
- Abbott et al. (2016), IAC 2.0: <https://aclanthology.org/L16-1704/>
- Local IAC 2.0 assessment:
  [`sources/llm-forum-text-emotion-recognition-iac2-assessment.md`](../../../../../sources/llm-forum-text-emotion-recognition-iac2-assessment.md)
