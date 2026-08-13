# DATA-WEIBO-TASK-V1: Weibo EClass 数据构建协议

- Protocol ID: `DATA-WEIBO-TASK-V1`
- Frozen date: 2026-08-08
- Tier: Major data protocol
- Status before execution: `Registered`
- Source revision: `d385f8cdc7e7ab9ca1ec62b8202c664a5ba651f3`
- Split seed: `20260808`

## 1. 目的与边界

本协议把 Weibo Emotion Corpus 中的 EClass 行构造成论坛/社交媒体文本情绪识别的
首个正式单标签数据轨。它只完成数据解析、质量过滤、去重、分组划分和 test 封存，
不训练模型，不读取预测结果，也不使用 test 进行任何模型选择。

本数据轨回答的是：在同一批 target clause 上，加入部署时可获得的前文是否改善情绪
识别。它不把相邻前文表述成直接回复、parent post 或完整线程。

## 2. 来源与许可

- Repository: <https://github.com/wjhou/Weibo-Emotion-Corpus>
- License: Apache-2.0
- Input: `data/weibo-emotion-corpus/official/emotion_classification.tsv`
- Expected SHA-256:
  `cd31ced8f9a4034c83065099061a23df3b402797841d8ff120c459da55251793`
- Supporting paper: Chen et al. (2018), *Joint Learning for Emotion Classification
  and Emotion Cause Detection*, <https://aclanthology.org/D18-1066/>

原论文把 EClass 定义为 clause-level 分类，输入为 `PrevCL`、`CurCL`、`FolCL`，输出
为六类情绪加 `non-emotion`；由于 `fearful` 仅约 0.6%，原实验将其忽略。本文主系统
不得使用 `FolCL/SufCL`，因为它属于 target 之后的信息。

## 3. 解析规则

TSV 使用 UTF-8、tab delimiter、CSV quote 语义和大字段上限读取，禁止逐物理行
`split("\t")`。

1. 第二列为 `Y/N` 的记录属于 ECause 脚手架，不进入 EClass。
2. EClass 记录必须各包含一次且按顺序出现：
   `beg_preclause/end_preclause`、`beg_curclause/end_curclause`、
   `beg_sufclause/end_sufclause`。
3. source row ID 的最后一个 `-整数` 仅用于恢复同一 source group 内的顺序。
4. 每个健康 group 必须满足：EClass 序号连续；首条 `PrevCL` 为空；末条
   `SufCL` 为空；相邻行满足 `CurCL[i] == PrevCL[i+1]` 和
   `SufCL[i] == CurCL[i+1]`。
5. 任一 EClass 行结构损坏时，整个 source group 排除，不能只删除损坏行后保留
   一个断裂上下文。

`SufCL` 只用于上述完整性检查，不写入模型输入。

## 4. 标签冻结

主任务为单标签七分类：

| Upstream label | Frozen label |
| --- | --- |
| `快乐` | `joy` |
| `悲伤` | `sadness` |
| `愤怒` | `anger` |
| `正面` | `positive` |
| `负面` | `negative` |
| `中性` | `neutral` |
| `No_emotion` | `no_emotion` |

以下记录不进入主任务：

- `恐惧`：保留聚合计数，但遵循原论文 EClass 设置从主任务排除。
- 含 `+` 的复合标签：与冻结的单标签任务冲突，不拆分、不多数投票、不取首标签。
- 未知标签或结构损坏 group。

`neutral` 表示显式中性内容，`no_emotion` 表示未识别到情绪；二者不得合并。

## 5. 文本与隐私处理

marker 内 token 按原顺序拼接，执行 Unicode NFKC、空白压缩，并把 URL 与
`@mention` 分别替换为 `<URL>`、`<USER>`。保留 emoji、标点、话题和网络表达。

公开 Git 不得包含微博原文、上游 row ID 或上游 group ID。私有输出使用本地随机
HMAC key 生成不可逆的 `sample_id` 和 `group_id`；key 与全部逐行数据均位于
`derived-private/` 并由 Git 忽略。

## 6. 去重与泄漏控制

目标文本去重键为：隐私处理后的 `CurCL` 再做 lowercase 和移除空白。

1. 每个 `(normalized target, frozen label)` 只保留一条 canonical record。
2. canonical 选择不读取模型结果：优先保留非空 `PrevCL`，再取 source 顺序最早者。
3. 若同一 normalized target 对应多个标签，每个标签各保留一条。这些记录不是强行
   改标签，而是保留为 target-only 歧义/context 可能有用的样本。
4. 同一 source group、同一 normalized target 涉及的所有 canonical records 组成
   一个 leakage component，必须进入同一 split。
5. 使用 3-character n-gram、64-bit SimHash、4 x 16-bit LSH 候选和 Jaccard
   `>= 0.90` 做近重复审计。该方法只支持 lexical near-duplicate 判断，不宣称
   semantic equivalence；命中的 key 对也并入同一 leakage component。

不得把一个 target-only 重复文本分散到 train/validation/test。

## 7. Split 规则

- Unit: leakage component（同时约束 source group 与重复 target）。
- Ratios by retained rows: train 70%、validation 15%、test 15%。
- Seed: `20260808`。
- Stratification: 七类标签、`context_available/context_missing` 和
  `ambiguous_target`（同一 normalized target 对应多个冻结标签）。
- Allocation: 先以冻结目标构造 validation，再构造 test，余下为 train；只使用标签、
  context availability、component size 和 seed，不读取任何模型输出。

验收条件：

- split row ratio 与目标绝对误差不超过 0.5 个百分点；
- 每个标签在三个 split 均有样本；
- 每类分配比例与目标绝对误差不超过 5 个百分点；
- context available、context missing 与 ambiguous-target 三个切片的分配比例与目标
  绝对误差均不超过 3 个百分点；
- source group、normalized target 和 near-duplicate component 均不跨 split。

### 2026-08-08 pre-freeze correction

第一次真实数据 preflight 虽通过完整性检查，但只给 `context_available` 一个普通
stratum 权重，导致标签平衡而 context/ambiguity 切片明显偏向 validation/test。
在任何模型训练和 test 评估之前，最终构建器增加 `context_missing`、
`ambiguous_target` 及切片分配容差；原私有输出保留为 `eclass-v1-pre-balance`，不作为
正式数据版本。此修正不读取模型结果，也不改变标签或样本内容。

原论文使用 5-fold cross-validation；本协议建立独立 held-out test，因此后续结果不得
伪装成原论文的直接复现分数。

## 8. 成对输入视图

每个 retained record 只保存一次，并同时提供：

- `target_only`: `CurCL`；
- `previous_context`: 独立的 `previous` 与 `target` 字段。

首 clause 的 `previous` 为 `null`，`context_available=false`。后续模型必须在完全相同
的 sample IDs 上比较两种视图；不得因上下文缺失而单独删除某一侧。

正式报告至少包含：full split、context-available slice、first-clause slice。

## 9. Test 封存

- `train.jsonl`、`validation.jsonl` 含标签。
- `test.inputs.jsonl` 不含标签。
- `test.labels.sealed.jsonl` 只含 `sample_id` 与 gold label。
- test labels 和 HMAC key 全部 Git ignored。
- 本阶段 verifier 可以为数据完整性读取 test labels；训练、调参、prompt、threshold、
  checkpoint 选择代码不得读取。
- 第一次模型 test 评估仍需项目 `AGENTS.md` 的 `TEST-READY` 清单和用户明确授权。

## 10. 公开与私有产物

公开：

- 本协议；
- 构建器、独立 verifier 与 synthetic tests；
- aggregate construction report；
- aggregate verification report；
- source/private artifact hashes、计数和方法限制。

私有：

- 所有逐行 paired records；
- test labels；
- HMAC key；
- 近重复 pair 索引和 private manifest。

## 11. Stop Conditions

出现以下任一情况立即停止，不把数据标为 `Verified`：

- source SHA-256 不匹配；
- marker、group continuity 或标签计数无法独立复算；
- 公开产物出现原文或上游 ID；
- paired views 行数或 sample IDs 不一致；
- group/duplicate leakage；
- split 平衡超出冻结容差；
- test inputs 含 gold label，或私有目录未被 Git 忽略；
- verifier 未通过全部检查。

## 12. Execution Result

- Executed: 2026-08-08
- Status: `Verified`
- Retained rows: 8,540
- Split rows: train 5,995; validation 1,272; test 1,273
- Context available / missing: 6,138 / 2,402
- Frozen label counts: `no_emotion` 5,929; `negative` 736; `positive` 646;
  `joy` 408; `neutral` 401; `anger` 284; `sadness` 136
- Same target-label rows collapsed: 2,422
- Ambiguous target rows retained and split-bound: 295 across 117 normalized targets
- Lexical near-duplicate matches at the frozen threshold: 0
- Maximum label allocation error: 0.005882
- Maximum context/ambiguity allocation error: 0.022315
- Independent verification: 33/33 checks passed
- Test gate: labels sealed and Git ignored; model access remains unauthorized

The original preflight split is retained privately as `eclass-v1-pre-balance`.
It is not an official task version and must not be used for model comparison.
The public construction and verification reports are the authoritative
aggregate evidence. No model was trained or evaluated during this execution.
