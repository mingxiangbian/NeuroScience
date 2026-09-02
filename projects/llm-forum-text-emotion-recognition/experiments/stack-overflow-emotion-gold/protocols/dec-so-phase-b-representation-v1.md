# DEC-SO-PHASE-B-REPRESENTATION-V1: LoRA 表征变化与功能依赖分析

- Decision ID: `DEC-SO-PHASE-B-REPRESENTATION-V1`
- Date: `2026-08-26`
- Primary RQ: `RQ-S4`
- Parent behavioral evidence: `RQ-S1`, `EXP-052`, `EXP-053`, `EXP-056`
- Parent system evidence: `RQ-S3`, `EXP-058` to `EXP-068`
- Phase A closeout: `DEC-SO-PHASE-A-CLOSEOUT-V1`
- Status: `Registered; EXP-069 static stage authorized, model smoke closed`
- Tier: `Major representation and intervention program`

## 1. 研究决策

Phase B 研究一个限定问题：

> Classification LoRA 如何改变 Qwen3-4B 中与 Stack Overflow 六标签情绪分类相关的层级
> 表示，以及最终 M3 行为在功能上依赖哪些 LoRA 路径？

行为证据已显示 matched M3 Classification LoRA 相对 M2 Frozen Qwen 的 held-out
Macro-F1 delta 为 `+0.318578`。该结果证明任务适配收益，不解释 hidden-state 变化或
LoRA 路径的功能依赖。Phase B 补充表征与干预证据，不重新评价 test performance。

### 1.1 子问题

| ID | Question | Primary method |
| --- | --- | --- |
| `RQ-S4.1` | LoRA 从哪些层开始提高标签线性可分性？ | Layerwise linear probe |
| `RQ-S4.2` | M3 与 Frozen Qwen 的同样本表示从哪些层开始漂移？ | Cosine drift, relative L2, linear CKA |
| `RQ-S4.3` | 最终 M3 对 Attention、MLP 和深度分组 LoRA 有何功能依赖？ | Inference-time LoRA ablation |

可选 `EXP-073` 解释 Phase A router 使用哪些 pre-Qwen features。它继续归 `RQ-S3`，不构成
`RQ-S4` 的内部表征证据，也不阻塞 Phase B 收口。

## 2. 允许与禁止的主张

Phase B 可以研究：

- 标签线性可分性；
- residual representation 的层级变化；
- 最终联合训练模型对 LoRA 模块的功能依赖；
- 上述结果在同一训练数据的不同训练 seed 间是否复现。

Phase B 不能声称：

- 人类情绪产生机制；
- 模型感受或体验了情绪；
- 某一层是情绪存储区；
- 找到了 emotion neurons；
- 大幅 drift 等于更深理解；
- train-OOF 证据构成 independent-data mechanism validation。

证据等级固定为 `train-OOF developmental representation evidence`。Seeds 43/44 若按
冻结关键层和 ablation 条件复现，可升级为
`same-train cross-training-seed representation replication`。

## 3. 数据合同

Phase B 主数据只使用 `DATA-SO-TASK-V1 train`：

| Field | Frozen value |
| --- | --- |
| Rows | `3,360` |
| Duplicate components | `3,277` |
| Labels | `love, joy, surprise, anger, sadness, fear` |
| Train SHA-256 | `fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc` |
| Outer folds | 5 component-disjoint folds, 672 held-out rows each |
| Fold manifest SHA-256 | `82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8` |

Phase B 复用 EXP-058、EXP-061 和 EXP-062 的 fold assignment。任何 fold regeneration、
component reassignment 或 split substitution 都必须停止。

禁止访问：

- C0 test text；
- C0 test labels；
- C0 test predictions；
- test-gate artifacts；
- validation performance for layer, probe, threshold or ablation selection。

Validation 不进入 Phase B 主证据。只有在全部方法冻结后，新的单独协议才可登记一次不反馈
调参的 development projection。

## 4. 模型与输入合同

### 4.1 Frozen representation

```text
Qwen/Qwen3-4B
revision = 1cfa9a7208912126459214e8b04321603b3df60c
precision = MLX BF16, unquantized
hidden size = 2560
blocks = 36, indexed 0..35
```

### 4.2 Adapted representation

M3 使用相同 base checkpoint，加 fold-specific Classification LoRA 与对应 linear head。

```text
LoRA blocks = 20..35
Attention modules = q_proj, k_proj, v_proj, o_proj
MLP modules = gate_proj, up_proj, down_proj
rank = 8
scale = 20
dropout = 0
```

EXP-069 必须逐 fold 验证 seed 42、43、44 的 adapters、heads、held-out logits、provenance
和 public verification。若原 checkpoint 缺失，只能登记新的 reconstruction run；重建模型
不得冒充原 OOF checkpoint。

### 4.3 Input rendering and pooling

Frozen Qwen 与 M3 共享：

```text
tokenizer and revision
target-only classification prompt
special tokens
max_length = 384
thinking = off
singleton forward
pooling = last non-padding input token
```

Phase B 不增加 context、HTML/Markdown cleaning、code removal、Unicode normalization 或
新的 prompt。Input rendering hash drift 立即停止。

## 5. Representation points

Phase B 冻结九个读取点：

| ID | Definition |
| --- | --- |
| `H-1` | Embedding output |
| `H7` | Residual stream after block 7 |
| `H15` | Residual stream after block 15 |
| `H19` | Residual stream after block 19; last pre-LoRA point |
| `H20` | Residual stream after block 20; first potentially LoRA-affected point |
| `H27` | Residual stream after block 27 |
| `H31` | Residual stream after block 31 |
| `H35` | Residual stream after block 35 |
| `HF` | Final RMSNorm output used by the M2/M3 classification interface |

`H-1` 至 `H35` 保存 raw residual stream，不额外应用 final RMSNorm。只有 `HF` 使用模型的
真实 final RMSNorm。所有点只保存最后一个非 padding 输入 token。

## 6. Experiment map

| EXP | Purpose | Blocking role |
| --- | --- | --- |
| `EXP-069` | Representation extraction and parity preflight | Hard gate |
| `EXP-070` | Layerwise linear probing | Primary representation experiment |
| `EXP-071` | Representation drift and geometry | Primary representation experiment |
| `EXP-072` | LoRA functional ablation | Primary intervention experiment |
| `EXP-073` | Router interpretability | Optional RQ-S3 bridge |
| `EXP-074` | Read-only Phase B synthesis | Required closeout |

顺序固定为 `EXP-069 -> EXP-070 -> EXP-071 -> EXP-072 -> optional EXP-073 -> EXP-074`。
`EXP-070` 至 `EXP-072` 各自仍需在运行前建立独立 Major protocol、config、tests 和 verifier。

## 7. EXP-069 hard gate

EXP-069 不计算 classification performance。它在 32 条 deterministic train-only smoke rows
上验证抽取路径。

### 7.1 Artifact and identity checks

- Frozen Qwen base revision 与 tokenizer 可离线加载；
- seeds 42/43/44 各五个 fold-specific M3 adapters、heads 和 held-out logits 存在；
- 所有 public fold verifications 为 Passed；
- fold manifest、label order、prompt、pooling 和 max length 与父实验一致；
- 每个 private artifact 的 path、bytes、mode 和 SHA-256 写入 private manifest。

### 7.2 M2 path replay

仓库没有 train-only M2 logits 或 probabilities fixture。EXP-069 不制造该 reference，也不
使用 validation predictions 代替 train evidence。

32-row train smoke 的主门改为：新抽取的 Frozen Qwen `HF` representation 与已通过 74/74
reuse-gate 的 seed-42 train feature cache 对齐。Reference 为：

```text
experiments/stack-overflow-emotion-gold/model-comparison/private/
  exp-052-m2-frozen-qwen/seed-42/
  feature-cache/train/features.npy
shape = (3360, 2560)
dtype = float32
```

EXP-069 protocol 必须在读取 smoke 结果前绑定 cache manifest、row order、bytes、SHA-256、
mode 和 numeric tolerance。32 个 ordinals 的 representation 必须在 tolerance 内一致。
M2 head replay 不是 Phase B hard gate；后续若需要，必须先登记独立且有真实 reference 的检查。

### 7.3 M3 fold replay

每个 fold 选取少量该 fold held-out rows：

```text
fold-specific M3 checkpoint
-> HF representation
-> original fold classification head
-> logits and probabilities
```

输出必须与 EXP-058、EXP-061 或 EXP-062 对应 held-out logits 在预注册 tolerance 内一致。
Full-data seed-42 checkpoint 不能替代 fold-specific replay。

### 7.4 Hook and pre-LoRA equivalence

同一输入的 Frozen Qwen 与 M3 在 `H-1/H7/H15/H19` 应只有预注册 tolerance 内的数值差异。
EXP-069 必须在执行前冻结 hidden-state tolerance 和 dtype comparison rule。

若 H19 前出现超限差异，EXP-069 停止。优先检查 hook 位置、tokenization、input rendering、
checkpoint injection 和 RMSNorm 口径，不把异常解释为 LoRA representation effect。

当前 MLX-LM `model.model(...)` 返回 final RMSNorm output，不能直接提供九个 raw residual
points。EXP-069 必须实现并验证逐 block extraction：`HF` 与标准模型调用结果一致，
`H-1` 至 `H35` 不提前应用 final RMSNorm，且 hook 不改变 logits。

### 7.5 Resource and privacy gates

- 每个 seed/fold/checkpoint 使用 fresh process；
- 同时只允许一个 4B MLX heavy process；
- hidden states、row IDs、component IDs 和 replay logits 全部保存在 gitignored private tree；
- private directories 使用 `0700`，private files 使用 `0600`；
- public outputs只允许 aggregate checks、layer names、hashes、resource records 和 status；
- 不保存 full-token by full-layer activations。

EXP-069 任一 identity、parity、hook、resource、mode 或 privacy gate 失败，Phase B formal
extraction 停止。

## 8. EXP-070 layerwise linear probe

### 8.1 Outer evaluation

对每个 outer fold `k`：

- `M3_k` 在其余 2,688 rows 上训练，未见过 held-out fold `k`；
- probe 在 outer-train representations 上拟合；
- probe 只在 672-row outer-held-out representations 上评价；
- Frozen Qwen 使用相同 outer split 和读取点。

### 8.2 Probe

每个 layer、model、seed 和 outer fold 使用：

```text
StandardScaler
+ six independent L2 LogisticRegression classifiers
C = 1
solver = liblinear
class_weight = None
max_iter = 2000
random_state = 42
```

Scaler 只在 outer-train representations 上拟合。Probe 与原 M2/M3 head 无关。

### 8.3 Threshold selection

每个 outer-train partition 内执行 component-disjoint inner OOF：

1. 生成 probe inner-OOF probabilities；
2. 在 `0.05..0.95`, step `0.01` 中选择一个 six-label shared threshold；
3. tie order 为 five-label Macro-F1、Hamming loss、离 0.5 最近、较低 threshold；
4. 在全部 outer-train 上重拟合 probe；
5. 将冻结 threshold 应用于 outer-held-out。

### 8.4 Metrics and seed roles

唯一 decision metric 为 `five-label Macro Average Precision`。它不依赖 threshold，用于判断
representation 的标签排序可分性。`Five-label Macro-F1` 作为 behavioral-alignment metric，
不决定 Phase B replication state。

Mandatory secondary metrics：six-label Macro-F1/AP、five-label Macro-F1、Micro-F1/AP、
Hamming loss、subset accuracy 与 per-label F1/AP。Five-label decision choice 只用于降低
train 中 31 个 `surprise` positives 对层判断的支配；六标签结果必须完整报告。

Seed 42 运行全部九层，作为 discovery curve。Seeds 43/44 在查看 seed-42 结果前冻结为
`H19/H27/HF` 三个确认点，不根据 discovery curve 改层。

每层使用 2,000 次 duplicate-component bootstrap 比较
`metric(M3) - metric(Frozen)`。九层曲线保持探索性；正式 cross-seed claim 只围绕
`H19/H27/HF`。

## 9. EXP-071 representation drift

EXP-071 只使用每个 outer fold 的 672 held-out rows，并逐层比较同一样本 Frozen Qwen 与
`M3_k` representation：

- cosine distance：mean、median、P90、P95；
- relative L2 distance：mean、median、P90、P95；
- linear CKA：每 fold、每层计算，再汇总五折 mean 与 SD。

`H19` 前 drift 应接近 0、CKA 应接近 1，这属于 sanity check。Post-LoRA drift 大小不能
单独解释为更强情绪理解。Layerwise drift 与 probe gain 的 Spearman correlation 只作
九点描述，不构成稳定机制证据。

## 10. EXP-072 LoRA functional ablation

EXP-072 使用 fold-specific M3 checkpoints，只在各自 held-out fold 上推理，并恢复 3,360-row
OOF ablation predictions。它复用原 M3 head，不训练或校准新 head。

每行使用父实验冻结的 raw-identity cross-fitted M3 threshold。来源和 SHA-256 固定为：

| Seed | Private source | SHA-256 |
| ---: | --- | --- |
| 42 | `experiments/stack-overflow-emotion-gold/oof-router/private/exp-059-calibration-selective-prediction/cross-fitted-calibration.npz` | `47aaa4a8a9a8e45a9ddd1a4ee9f99573ab56b592cf6d921546a2025e36421f27` |
| 43 | `experiments/stack-overflow-emotion-gold/oof-router/private/exp-061-seed-43-router-replication/attempt-1/calibration/cross-fitted-calibration.npz` | `e53f61344e1b298c2ea2894c02f5a5eec74c6a0cb2b30f90bc97c7c6660ecc37` |
| 44 | `experiments/stack-overflow-emotion-gold/oof-router/private/exp-062-seed-44-router-replication/attempt-1/calibration/cross-fitted-calibration.npz` | `25b6d2702e769d52e555840c93d23e3e8f70ae1cf339e50099a68638c25e6e99` |

EXP-072 只读取 `fold_ids` 与 `m3_raw_thresholds`，按冻结 source order 对齐。它不读取或使用
该 private container 中的 gold、probabilities、predictions 或 oracle arrays。Temperature
diagnostic 不进入 ablation threshold。

Seed-42 discovery conditions：

| ID | Condition |
| --- | --- |
| `A0 Full` | All LoRA enabled |
| `A1 All-off` | All LoRA disabled |
| `A2 Attention-off` | q/k/v/o LoRA disabled; MLP LoRA retained |
| `A3 MLP-off` | gate/up/down LoRA disabled; Attention LoRA retained |
| `A4 Lower-off` | Blocks 20..27 LoRA disabled |
| `A5 Upper-off` | Blocks 28..35 LoRA disabled |

Seeds 43/44 只复现预冻结的 `A1/A2/A3`。所有结果报告 `Ablation - Full`：six/five-label
Macro-F1、Micro-F1、Hamming loss、subset accuracy、per-label F1、prediction-vector flip
rate 和 mean absolute logit change。

关闭模块属于联合训练模型上的 inference intervention。结果可以说明最终行为对该路径的
功能依赖，不能证明单独训练该模块会得到相同结果。

正式 ablation 前必须通过 no-result implementation gate：

- `A0 Full` 重放对应 fold 保存的 OOF logits；
- 每个 condition 只关闭目标 LoRA modules，其他 adapters、head 和 base weights 保持不变；
- runtime 核对实际 LoRA scale=`20`、dropout=`0`；
- checkpoint 文件和 base sentinel 在运行前后 hash 不变；
- 每个 fold/condition 使用 fresh process，不复用已修改的 model object。

## 11. EXP-073 optional router bridge

EXP-073 只读取冻结的 seed-42/43/44 router artifacts，分析 standardized coefficients、
meta-held-out fold-wise permutation importance 和 routed-subset aggregate。它不重新拟合
router，不使用 Phase A efficiency failure 生成新部署主张。

该实验最多说明 frozen router 在 development data 中利用哪些统计特征。它不证明特征的
因果作用、新数据泛化或部署成本收益。

## 12. EXP-074 synthesis and decision states

EXP-074 不训练、不推理，只读取 verified public aggregates。Representation state 只能是：

```text
Representation effect replicated
Representation effect seed-sensitive
No replicated representation effect
```

Functional-dependency state 独立分配：

```text
Stable Attention-dominant dependency
Stable MLP-dominant dependency
Both contribute / no stable dominance
```

每个 seed 的正式 representation pass 只由 `five-label Macro AP` 决定。对合并五个
outer-held-out folds 的 3,360-row OOF predictions，定义：

```text
delta_AP(layer) = five-label Macro AP(M3) - five-label Macro AP(Frozen Qwen)
interval-supported positive = point delta_AP > 0
                              and duplicate-component bootstrap 95% lower bound > 0
```

Seed 43 或 44 只有在 `H27` 与 `HF` 都达到 interval-supported positive 时才记为 pass。
`H19` 是 pre-LoRA sanity point，不参与 positive vote。Representation state 按两个
prospective seeds 的 pass 数量唯一分配：

| Seeds 43/44 | State |
| --- | --- |
| 2/2 pass | `Representation effect replicated` |
| 1/2 pass | `Representation effect seed-sensitive` |
| 0/2 pass | `No replicated representation effect` |

Seed-42 九层 curve 只作 discovery，不投票。Five-label Macro-F1、six-label metrics 与完整
bootstrap intervals 必须报告，但不能替代 Macro-AP decision rule。

Attention/MLP dominance 只有在 seeds 43/44 的方向一致，且 five-label Macro-F1 drop
差值均至少 `0.01` 时才成立。其他结果归为 both contribute / no stable dominance。

## 13. Completion, negative results and stop rules

Phase B 最低完成集：`EXP-069`、EXP-070 seed-42 九层与 seeds 43/44 key-layer replication、
`EXP-071`、EXP-072 `A1/A2/A3` cross-seed replication、`EXP-074`。`EXP-073` 可省略。

以下结果均可形成有效负结论：

- probe 无提升：当前层位、last-token 与线性 probe 不能解释 M3 行为提升；
- 有 drift、无 probe gain：LoRA 改变表示，但未提高当前协议下的线性解码；
- ablation seed-sensitive：LoRA 整体有作用，但没有稳定模块主导关系。

以下情况立即停止当前 experiment：checkpoint 或 hash drift、fold/component leakage、
unexpected validation/test path、pre-LoRA equivalence failure、NaN/inf、OOM、输出目录非空、
private mode 错误、public row-level leakage、未冻结 threshold/tolerance，或 concurrent heavy
MLX workload。

## 14. Resource and artifact policy

Phase B 不重新训练 Qwen。主要成本来自 fold-specific forward、representation extraction 和
ablation inference。每个 seed/fold/condition 使用 fresh process，完成固定任务后写入 chunked
private artifact、flush、验证并退出。

持久化 selected held-out last-token representations、probe predictions、ablation logits、
aggregate drift 与 manifests。Outer-train representations 只服务 probe fitting；具体临时保存
和安全清理策略由 EXP-070 protocol 在运行前冻结。

API cost 固定为 USD 0。完整 wall-time、disk budget 和每次运行上限在 EXP-069 resource
smoke 后登记；EXP-069 未通过前不得估算为正式预算或启动全量抽取。

## 15. Immediate next action

EXP-069 的 protocol、config、runner、independent verifier、ignore rules 与 synthetic tests
已完成。Frozen config 只授权 no-model static runner 与 independent static verifier。

Static verification 通过前，不得执行 base smoke、15 个 fold smoke 或任何 hidden-state
artifact creation。Model loading、forward、training、metrics、validation 和 test 均保持关闭。
