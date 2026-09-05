# D0 数据与证据合同

日期：2026-09-03

状态：`D0 static contract registered / Strict nested route / No run authorized`

本合同只定义 Selective Qwen Multi-Agent Forum Analysis 的数据、依赖和评价边界。它不授权数据生成、训练、模型加载、Agent 调用、外部数据访问、网站修改、实验编号、commit 或 push。

机器可读合同：

- [D0 dependency manifest](../configs/d0-dependency-manifest.json)
- [D0 static method contract](../configs/d0-static-contract.json)
- [Agent Prompt bundle v0](../prompts/agent-bundle-v0.json)
- [Agent output schema v1](../schemas/agent-output-v1.schema.json)

## 1. 主研究问题

> 在相同 Qwen 调用数和总 token 预算的匹配对照下，受约束的角色化分析是否优于 Single Agent 与 Self-Consistency；若有效，选择性触发能否相对相同调用量的 Random Activation 保留更多收益？

第一轮角色固定为 Evidence + Appraisal、Pragmatics Critic 和 Judge。现有 M1/M3 只提供冻结分类结果；生成式 Agent 使用另行冻结的模型身份。

## 2. 来源快照与只读依赖

来源项目快照：`e70cfcf76744ce8473db1b9744fd258cdbc0c64c`

以下工作树文件已逐项与该 commit 内容核对一致：

| Path | SHA-256 | Git blob |
| --- | --- | --- |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json` | `e38e90b851925ae7eb9dabca45cbcbe17baaaf3dc017a60c06fe468d79b15124` | `a92326dddb208de1797c30fcab3e08e8176e59ec` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json` | `5156bfd583c13816e6d97eda1de7ba1b9237409036506001c5fcdb717b273cf3` | `27dd5a4aa94312ede8e0a84bf7937eaf29aa1d65` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/config.json` | `d97b7c837b5de4ef014a553fa255ebea4ecdffa848d19715d084bf7ed46177d6` | `faa8654bd4736138f0447c8d14cecd00de44809c` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/prompt-v1.json` | `0722ff947ba030cdf5b42358c7ba45a4d0d6372ccf0e2be28d131a0c24bdb90d` | `99c0a67c4b098b93bc84c54fdf182fe0452b0030` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-051-m1-roberta-seed-42-cpu-recovery.json` | `0c2ddbebd66bbd5ee627ecb1d4d3060e387d4f1d4fbcd70860d23ad278bf052d` | `b47e3b755987dc6879737daccf4df9607fae5de6` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-053-m3-seed-42.json` | `4490d19d24c58b15c857309bf15bd49fe4329b4e3702e6d4714f3432605755fe` | `71e18a7d7c1c53321d3aaada3ff8004b60181ad2` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/configs/exp-053-m3-seed-42-verification-attempt-2.json` | `1cb071c5187b173128c113dafc73c7289f1da911bcbf8bfe0f86b0a1f1a54cfc` | `209f1cd99543785871328e10c66601c8bbc8682c` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl` | `82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8` | `985dd4842a947809ca9524ebfc62c1b14af499bc` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-fold-manifest-preflight-attempt-2/fold-summary.json` | `89b40f26948a5bf44141bdb74e654d7eb0b19161b29d84d9a91ccda409fcf74c` | `1d48d0a3084adbbfbb4926dec3399cab5bda2b67` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-oof-production.json` | `909da4093e1c8a6bb84113e1e7d361c125159b54856a51988b4515eb267363da` | `3cac306c3ce9135ca0bc91d174048e5308c95ec4` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-059-calibration-selective-prediction.json` | `c7da87f3eddd4dd3e196bf80c0426a1791595c55872aa539cbf3797fd0f552fb` | `38c829f7692f71b655bda3696ed6a71058c44439` |
| `projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-060-pre-qwen-router.json` | `397df4b8e3df856893b6c7bab57eaa9664f20fc9a42f41a1f917da9e41361cad` | `d4974cdbc72444f73a0e07f69a55bf3101051296` |

该 manifest 只绑定公开元数据和配置。原始论坛文本、row-level gold、logits、模型权重和 private outputs 不进入 Git；后续只在受限本地目录记录其身份与访问证明。

已由公开运行元数据登记的 private 候选身份如下：

| Artifact identity | Expected SHA-256 |
| --- | --- |
| `DATA-SO-TASK-V1` train snapshot | `fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc` |
| EXP-058 fold 4 M1 raw logits | `41b77d212670d75bb18fec4cfaf174efdf599c2edde59159188b47deb3f1da76` |
| EXP-058 fold 4 M3 raw logits | `99e0e3c8142ef28202f25c27fdaa9cae169124b8bcc9d0ef618315e258b07ff8` |
| EXP-058 fold 4 held-out row order | `beb0af83e2ededd220681c435a9c4a20b67ba02fdbc433faec4ef2e9cb8e970d` |

主工作区中的 train、private fold manifest 及 fold 4 M1/M3 NPZ 已完成存在性、权限和 SHA-256 核对；当前 Codex worktree 未绑定这些 private 实体。执行时必须显式绑定只读归档根目录并复核身份，不能让相对路径静默指向缺失文件。

fold 4 两个源 NPZ 都含 `gold` 字段，因此 Confirm producer 禁止直接打开。后续必须由独立 consumer 从已核验源文件生成不含 `gold` 的密封快照，producer 只能读取该快照。当前只完成源身份与 schema 审计，没有生成 Confirm 快照。

## 3. 数据范围与禁止访问

- 唯一候选数据来源：`DATA-SO-TASK-V1` 的 train 3,360 rows。
- 原 validation 720 rows：禁止用于 Prompt、Trigger、阈值、模型或角色选择。
- 原 test 720 rows：已消费，禁止重新打开、评分或用于新项目选择。
- 标签顺序：`love, joy, surprise, anger, sadness, fear`。
- 分组单位：exact + NFKC/casefold/whitespace duplicate connected component。
- 原文、labels 与预测只能在对应 producer/consumer 权限下读取；公开工件不得包含逐行文本、gold、概率、route score 或样本身份。

## 4. Project split

复用 EXP-058 在结果前建立的五个 component-disjoint folds，不重新随机搜索划分：

| Split | Folds | Rows | Components | love | joy | surprise | anger | sadness | fear | neutral |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Agent-Dev | 0,1,2 | 2,016 | 1,963 | 512 | 206 | 18 | 370 | 97 | 44 | 824 |
| Agent-Tune | 3 | 672 | 657 | 171 | 68 | 7 | 124 | 32 | 15 | 274 |
| Agent-Confirm | 4 | 672 | 657 | 171 | 69 | 6 | 124 | 32 | 15 | 274 |

选择规则在任何新 Agent 输出前固定为：最低三个 fold ID → Dev，下一 fold ID → Tune，最高 fold ID → Confirm。该确定性映射不依据新 Agent 结果，但不代表 fold 4 的历史模型统计未知。

fold 4 的标签 support、Router 折级统计和五折 aggregate 已在原项目公开或消费。它只对 D0 后冻结的新 Agent 增量比较提供 process-heldout 约束，不是历史上完全未触碰的独立数据集，也不重新确认旧 M1/M3/Router。

## 5. Strict nested prediction route

现有 OOF 不能整体直接进入新项目确认。旧 folds 0–3 的模型训练集包含 fold 4，因此它们的预测不能用于严格隔离的 Dev/Tune 开发。

### 5.1 Agent-Dev producer

- 独立 scoped-input consumer 先读取完整 private train/fold manifest，只输出分别密封的 folds 0、1、2 快照；训练 producer禁止打开完整源文件。
- 仅在 folds 0–2 内做三折 component-disjoint cross-fitting。
- 每个 Dev row 的 M1/M3 raw logits 必须来自没有训练该 row/component 的模型。
- 训练、threshold、calibration 与 Prompt 开发均禁止读取 folds 3–4。
- Pilot 只能从这些 Dev rows 中选择。

### 5.2 Agent-Tune producer

- 使用只在 folds 0–2 训练的冻结 M1/M3 配置，对 fold 3 生成 raw logits。
- Prompt/schema 候选进入 Tune 前先冻结；Tune 只选择候选，不新增角色或特征。
- Trigger、abstention fallback、预算和输出 contract 在离开 Tune 前冻结。

### 5.3 Final development refit

- 方法选择完成后，允许在 folds 0–3 内建立新的四折 cross-fitted development predictions。
- 最终 threshold、calibration、Router 与 Agent Activation Gate 只能使用 folds 0–3 的 labels 和 cross-fitted outputs。
- 最终配置的 refit 不得改变已由 Tune 选择的 Prompt、角色、schema、预算或指标。

### 5.4 Agent-Confirm producer

- Confirm input 固定为 fold 4 的672 rows，顺序与 component identity 不变。
- EXP-058 fold 4 raw M1/M3 logits只有在独立核对其模型训练成员恰为 folds 0–3、配置身份一致、行顺序和 SHA-256 均通过后才可复用。
- 旧 EXP-059 threshold、旧 EXP-060 Router score/mask、旧派生预测和旧 gold comparison 不进入 Confirm producer。
- 在正式配置、代码和停止规则冻结前，任何开发进程不得读取 fold 4 的逐行文本、gold、logits、派生不确定性或结果。
- 正式 Confirm producer 才可读取文本与冻结 base outputs，运行各候选系统并先封存输出；不得读取 labels，也不得根据 Confirm 输入分布继续调整 Prompt、schema、预算或 Trigger。
- 独立 consumer 在输出、模型身份、Prompt、schema、预算和代码 hash 全部封存后一次性读取 Confirm labels并复算结果。
- 所有672行必须进入 primary；abstain、timeout、解析失败、repair 和 fallback 均保留并计入对应成本与失败率。
- 正式尝试中的技术失败计入第一次 formal attempt。任何接触 Confirm gold 后的失败不得通过修改 Prompt、代码、schema 或 fallback 后重跑；只能保留工件并按预登记失败分支收口。

历史项目已经使用过 train labels，因此最终最多声明：`same-source prospective component-heldout confirmation of the newly frozen Agent comparison`。不能声称 fold 4 从未被研究者打开、构成独立数据集，或证明跨论坛泛化。

## 6. Agent roles 与系统比较

### 6.1 角色

1. Evidence + Appraisal。
2. Pragmatics Critic。
3. Judge。

所有角色共享同一生成式模型身份，但上下文彼此隔离，只通过冻结 JSON schema 交换结构化字段。Appraisal 只是任务内分析线索，不是人的认知过程或模型内部机制。

### 6.2 系统

| ID | System | 说明 |
| --- | --- | --- |
| S0 | Frozen pipeline | M1 → Router → M3 |
| S1 | Single Agent | 一次生成完成证据、语用分析与最终判断 |
| S2a | Call-matched Self-Consistency | 三次相同Single Prompt独立采样 |
| S2b | Token-budget-matched Self-Consistency | 在S3总prefill+generated ceiling内运行最多完整Single调用，至少两次 |
| S3 | Role-diverse Multi-Agent | Evidence + Appraisal → Critic → Judge，共三次调用 |
| S4 | Selective Multi-Agent | 条件性系统，仅在 S3 有稳定信号后执行 |
| S4-random | Random Activation | 按component抽样，匹配S4实际activated rows与Qwen calls |

S3 相对 S2a/S2b 是角色价值的核心比较。S4 相对 S4-random 是 Trigger 价值的核心比较。

S2a/S2b 都按标签严格多数票聚合；偶数调用平票时使用对应 S0 标签状态。单次 invalid 或 abstain 作为一票 S0 label set并单独计数，不触发整个 Self-Consistency 丢弃。Evidence 从最终 labels 恰好等于 aggregate 的有效调用中选择最低 seed 输出，否则为空；不调用额外 Qwen aggregator。

S4 是否进入 formal Confirm，只能由结果前冻结的 Agent-Dev/Agent-Tune 统计规则决定。若 gate 通过，S3、S4 与 S4-random 必须在 Confirm gold 被 consumer 打开前同时冻结并一次性产出；不得先读取 Confirm 上的 S3 结果再启动 S4。若 gate 未通过，按负结果分支收口，不在 Confirm 上追加 Selective。

## 7. Budget matching

生成模型现冻结为：

- `Qwen/Qwen3-4B` revision `1cfa9a7208912126459214e8b04321603b3df60c`，原始 post-trained MLX BF16，不加载 M3/M4 adapter。
- runtime：Python 3.11.15、MLX 0.32.0、mlx-lm 0.31.3；离线单重模型进程。
- `enable_thinking=false`；temperature `0.6`、top-p `0.95`、top-k `20`，所有 seed 从冻结 namespace 派生。
- context cap `4096`；Evidence/Appraisal、Critic、Judge、Single 的 generated caps 分别为 `256/192/128/384`。
- 原文先用冻结 tokenizer 一次性生成最多1,024 tokens的 `analysis_text`，所有系统共享同一版本；constructed Prompt超过4,096 tokens即 hard stop，不允许各角色静默截断。
- preflight seed 固定由 `SHA256(namespace|system_id|sample_id|role_id|call_index)` 的前4字节生成。
- 正式方法不使用条件式 Qwen repair；无效输出或合法 abstain 均回退 S0并计数。
- Evidence/Appraisal 不见分类器输出；Critic 与 Judge 只见离散 M1/M3/final labels，不见概率、Router score 或 gold。

同时报告 call-matched 与 token-budget-matched 对照。S2b 的完整调用数和 token allocation 由 preflight 实测后、读取 Tune 前冻结；至少容纳两次完整输出，否则停止并压缩 schema。只有调用数相同不能称为等计算预算。

## 8. 指标与 abstention

- Primary：完整 Natural Confirm 的六标签 Macro-F1。
- Sensitivity：五标签 Macro-F1，不含 `surprise`。
- Guardrail：Hamming loss；non-inferiority margin 为绝对 `+0.0025`。
- Secondary：Micro-F1、subset accuracy、per-label precision/recall/F1、empty prediction rate。
- Selective：coverage、risk-coverage、abstention rate、fallback rate。
- Agent：schema validity、evidence exact-substring validity、repair、calls、tokens、latency 和资源。

第一版 primary 使用全覆盖最终标签。Agent abstain 默认回退 S0 的冻结最终标签；同时单独报告 abstain coverage 和风险。Exact-substring validity 只证明片段来自原文，不证明片段与情绪判断相关。

任何关于 evidence relevance、Appraisal 正确性或 Report 质量的主张都需要另行冻结的人工 rubric；没有人工评价时只能报告 schema 与来源一致性。

全部主要 contrast 使用 duplicate-component paired bootstrap：2,000次、固定 seed `20260903`、共享 component multiplicities、percentile 95% interval，zero-division=0且不删除无正例 replicate。

Role-diverse 进入 Confirm 的 Agent-Tune gate 固定为：相对 S2b 的六标签 Macro-F1 点差至少 `+0.010` 且 bootstrap `q0.05>0`，五标签点差不低于 `-0.005`，Hamming 差的 `q0.95<=+0.0025`；同时相对 S2a 的六标签 `q0.05>=-0.005` 且 Hamming `q0.95<=+0.0025`。任一条件失败即以 development-stage negative 收口，不读取 Confirm，也不执行 Selective。

## 9. Natural Confirm 与 Challenge diagnostic

- Natural Confirm 是 fold 4 全部672 rows，是唯一主决策总体。
- Challenge diagnostic 只能在方法完全冻结后，从 Confirm 输入和 base-model 非gold信号中生成。
- random 与 difficult strata 必须 component-disjoint；分别报告结果。
- 不把人为混合后的 Challenge F1 写成自然分布性能或 activation rate。
- Challenge 结果不得用于修改 Prompt、Trigger、角色、模型或阈值。

Challenge 的具体样本数和分层规则尚未冻结；D0 评审前不创建该切片。

## 10. Trigger availability

Agent Activation Gate 固定放在 S0 pipeline 之后：

- 全量可得：M1 probabilities、entropy、threshold margin、cardinality、character length、M1 token length、`route_requested`。
- 仅已调用 M3 的 rows 可得：M1/M3 disagreement、M3 margin、M3 empty prediction。
- 未调用 M3 的 rows 对 M3-derived features 保持缺失，并使用冻结 missingness 处理；不得为了计算 Trigger 静默增加 M3 调用。
- implicit emotion、sarcasm 或 Agent disagreement 不能作为 Agent 启动前的特征。

S4 必须以 component 为单位一致开关。S4-random 保存 S4 激活 component 的 size multiset，再从相同 size strata 无放回抽取；tie-break 为 `SHA256(namespace|formal_seed|component_id)` 升序。这样精确匹配 activated rows 和三次固定 Qwen calls；token 只报告，不声称匹配。无法精确匹配时该正式比较失败即停，不事后换 mask。手动 Deep Review 不进入 Trigger 方法评价。

## 11. Access、隐私与输出边界

| Stage | Text | Gold | Base outputs | Allowed use |
| --- | --- | --- | --- | --- |
| Agent-Dev | 可读 | 可读 | 新Dev-only cross-fitted | Prompt/schema开发与失败分析 |
| Agent-Tune | 可读 | 仅候选选择consumer可读 | Dev-trained | 候选、Trigger与预算冻结 |
| Agent-Confirm snapshot consumer | 最小必要 | 只为剥离 | private train/manifest与含gold源NPZ | 连接text、IDs、M1/M3 logits并生成密封无gold snapshot |
| Agent-Confirm producer | 仅从密封snapshot读取analysis_text | 禁止 | 无gold的frozen strict-route snapshot | 生成与封存输出 |
| Agent-Confirm consumer | 最小必要 | 一次性可读 | sealed | 指标复算和验证 |

Private 保存：原文、row/component ID、gold、概率、Prompt输出、evidence spans、route/activation mask、逐条预测与人工评价。

Public 只允许：配置身份、聚合指标、区间、调用与资源汇总、失败类别计数和不含原文的匿名切片统计。

## 12. Preflight 范围与停止

完整 Agent preflight 以前必须先生成 strict Agent-Dev base outputs；旧 folds 0–2 OOF 的训练包含 fold 4，不能替代。preflight 固定为：

- Agent-Dev 32个互异 component：16 random + 16 non-gold difficult；先8条 shakedown，后24条 locked verification。
- S3 在全部32行运行三次角色调用；固定8条 locked rows 运行三次 Single作为S2a，其中最低seed同时作为S1，再运行三次 provisional S2b，总调用硬上限144。provisional S2b只用于最坏情况压力与token测量，不构成预算匹配结果。
- 不使用 Qwen repair。locked部分要求系统完成率100%、technical fallback为0、evidence exact-substring为100%、越界标签和未处理失败为0。
- locked部分所有输出的 raw schema validity必须为100%；8条三采样 Single 的 mean modal exact-label-set agreement至少85%。shakedown不进入通过率分母。
- 单call context不超过4096，generated不超过角色cap；全preflight generated不超过58,368 tokens、wall不超过4小时、private输出不超过512 MiB。
- MLX peak不超过10 GB，process RSS不超过12 GiB；二者不相加。critical-memory、OOM/kill必须为0；连续3个5秒采样区间的swap写入达到100 MiB/s即停；结束后无 orphan process。
- 不读取 Tune/Confirm，不计算正式方法结论，不修改网站。

若生成模型身份不明确、输入hash漂移、输出目录非空、意外访问Tune/Confirm、schema或证据路径无法可靠封存、资源超过预登记预算，立即停止。

## 13. D0 状态与执行阻塞

静态 D0 已登记：模型/runtime、Prompt/schema、无 repair 策略、strict split、统计门、Random Activation匹配、隐私边界和机器可读 manifest 均已明确。首版不评价 evidence relevance、Appraisal正确性或 Report质量，也不声称外部泛化。

这不等于已经可以运行完整 Agent preflight。当前仍需依次完成：

1. D0 static verifier 已实现并通过：它绑定 static contract自身身份，核对source commit tree、12项公开依赖、4项private身份、9个模型文件、runtime、Prompt/schema和runtime validator；未加载模型或解析private rows。
2. `SQMA-001` no-training readiness preflight 已完成并通过独立verification attempt 3；20项检查通过，未解析private rows或产生strict outputs，runner未重跑且run未修改。
3. `SQMA-002` folds 0–2 scoped-input materialization 已完成并独立验证：九个数据工件与private seal通过，fold3/4私有行值未decode且输出为0。
4. `DEC-SQMA-CLASSIFIER-FREE-V1`已取消当前阶段的M1/M3重训和分类器输入；SQMA-001/002历史工件保留，但不再作为Agent调用前置模型链。
5. 当前执行SQMA-003 classifier-free preflight；它只评价能力、格式、稳定性和资源，不评分准确率。
6. 根据SQMA-003实测，在读取Tune前冻结S2b token allocation、正式wall/storage预算和generation-seed范围。
7. 若SQMA-003通过且完整比较投影不超过48小时，独立密封fold 3并执行672-row S1/S2a/S2b/S3 matched comparison。
8. 只有Agent-Tune gate通过后，才考虑fold 4 Confirm和Selective Trigger；是否重新引入分类器另行决定。

本文件仍不授权上述执行、模型加载、训练或数据派生产物。
