# EXP-072：LoRA 功能消融

- Experiment ID：`EXP-072`
- Date：`2026-08-30`
- Tier：`Major`
- RQ：`RQ-S4.3`
- Parent：`DEC-SO-PHASE-B-REPRESENTATION-V1`；EXP-058/061/062 fold-specific M3
- 前置条件：EXP-069、EXP-070 Complete，EXP-075 independent verification Passed。
- Status：方法已登记；尚无消融结果。

## 问题与固定项

本实验检验最终联合训练的 M3 对 Attention、MLP 与深度分组 LoRA 的功能依赖。
沿用 Phase B 的 discovery/replication 条件，不寻找最优模块子集，不重训 base、adapter
或 head，不拟合阈值、temperature 或校准器。

数据为 DATA-SO-TASK-V1 train，3,360 行，3,277 duplicate components，固定五个
component-disjoint outer folds，每 fold 672 heldout 行。Train SHA-256：
`fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc`；public fold
manifest SHA-256：`82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8`。
标签顺序为 `love, joy, surprise, anger, sadness, fear`。

每行只由未训练过该 outer-heldout fold 的对应 M3 checkpoint 推理。使用原 Qwen3-4B
revision `1cfa9a7208912126459214e8b04321603b3df60c`、MLX BF16 unquantized、原
fold-specific adapter 和 linear head。Prompt、tokenizer、thinking-off、max_length=384、
singleton forward、last non-padding input token 与父实验相同。Config 绑定原 EXP-069
source records 和全部 runtime/source hashes；禁止 checkpoint reconstruction。

## 条件与执行顺序

每个 worker 只运行一个 seed/fold/condition，并在 fresh process 中加载模型。

| Condition | 关闭的 LoRA 分支 | 关闭数 | Seeds |
| --- | --- | ---: | --- |
| A0 Full | 无 | 0 | 42/43/44 |
| A1 All-off | 全部 | 112 | 42/43/44 |
| A2 Attention-off | q_proj/k_proj/v_proj/o_proj | 64 | 42/43/44 |
| A3 MLP-off | gate_proj/up_proj/down_proj | 48 | 42/43/44 |
| A4 Lower-off | blocks 20..27 的七类模块 | 56 | 42 |
| A5 Upper-off | blocks 28..35 的七类模块 | 56 | 42 |

先按 seed 42/43/44、fold 0..4 运行全部 15 个 A0 完整重放，各 672 行。通过全部 A0
implementation gates 后，再运行 55 个消融 worker。总计 70 workers、47,040 singleton
forwards。相同 seed 的 Full 与 ablation 使用相同 heldout 行、head 和冻结阈值。

运行前确认 112 个 LoRALinear 的 blocks、module names、rank=8、scale=20、dropout=0。
完整装载后，仅将目标 module 的 runtime scale 设为 0，其余保持 20。运行后检查固定
scale map、adapter/head tensors 和 base sentinel；不改写参数文件，不 fuse/unfuse。
Base sentinel 沿用 EXP-053 的采样规则：按名称排序非 LoRA tensors，均匀选 16 个，
每 tensor 取四个固定位置。它检测采样位置变化，不声称证明全部内存参数逐字节不变；
原 checkpoint 文件另做完整前后 SHA-256 检查。

## 无性能结果的 A0 门

A0 重放全部 15 个 seed/fold 的已保存 heldout logits，不选择 smoke 子集。
按原 sample identity 与 fold 对齐，以 float32 MLX head 输出比较：
`rtol=0, atol=1e-5`，继承 EXP-069/070 的 model replay 容差。
该门只计算 replay difference，不计算 F1、阈值后预测或其他性能结果。

每个 worker 的 model/checkpoint 来源、LoRA 模块范围、base sentinel 和输入 rendering
必须通过前后检查。任一 A0 不通过，不启动消融；不得按观察到的误差放宽容差。

## 输入与标签隔离

Inference 只解码当前 heldout 行的 text 和必要 sample identity；逐字段跳过 labels，
不能调用整行 JSON loader 将 gold 一起物化。父 fold manifest 用于冻结 row/fold 对齐，
不重建划分。没有持久化 token cache；本实验不新增 token-cache 流程。

每个 worker 保存 private logits、ordinals/fold identity 和 manifest。只有全部 70 个
workers 成功且 prediction seal 绑定其 hashes 后，score 阶段才可解码 train labels。
Score 从原 `fold-manifest.private.jsonl` 读取已绑定 train source order 的标签与身份，
其 SHA-256 为 `d518e97c3332f2d59ea3556aecbb3a8cf9253438aee5ba02cd2ab105663862af`。
该文件不含 text。Score 不重新推理，也不读取 text；independent verifier 从同一 seal
和冻结 sources 复算。
预测 seal 后不得改变条件、输入、checkpoint、阈值、评价规则或选择 seed。

## 阈值与评分

只从以下容器读取 `fold_ids` 和 `m3_raw_thresholds`，按冻结 train source order 对齐。
不得解码容器中的 gold、probabilities、predictions、oracle 或 temperature 字段。

| Seed | Source（相对于 oof-router/private） | SHA-256 |
| --- | --- | --- |
| 42 | exp-059-calibration-selective-prediction/cross-fitted-calibration.npz | 47aaa4a8a9a8e45a9ddd1a4ee9f99573ab56b592cf6d921546a2025e36421f27 |
| 43 | exp-061-seed-43-router-replication/attempt-1/calibration/cross-fitted-calibration.npz | e53f61344e1b298c2ea2894c02f5a5eec74c6a0cb2b30f90bc97c7c6660ecc37 |
| 44 | exp-062-seed-44-router-replication/attempt-1/calibration/cross-fitted-calibration.npz | 25b6d2702e769d52e555840c93d23e3e8f70ae1cf339e50099a68638c25e6e99 |

对 float32 logits 转 float64 后计算数值稳定 sigmoid，逐行以
`probability >= m3_raw_threshold` 生成六位预测，不使用 temperature scaling。
每条件合并五个 fold 为原顺序的 3,360-row OOF 结果，再计算指标，不平均 fold F1。

报告 Full、各 ablation 的绝对值及 `Ablation - Full`：six-label Macro-F1、排除
surprise 的 five-label Macro-F1、Micro-F1、Hamming loss、subset accuracy、per-label
precision/recall/F1/support。零分母的 precision/recall/F1 为 0；补充 weighted F1。
另报 prediction-vector flip rate（六位向量任一位变化的行比例）与 3,360×6 logits 的
mean absolute change。Hamming loss 增加表示退化；其余性能指标下降表示退化。
本实验不引入 bootstrap、p-value、最佳条件选择或跨 seed 结果驱动的阈值。

Primary functional summary 使用 five-label Macro-F1 drop=`Full - Ablation`。
EXP-074 仅当 seeds 43/44 的 `drop(A2)-drop(A3)` 都至少为 +0.01 时报告
`Stable Attention-dominant dependency`；都至多为 -0.01 时报告
`Stable MLP-dominant dependency`；其余为 `Both contribute / no stable dominance`。
这继承 Phase B 的方向与幅度门；seed 42 和 A4/A5 不投票。

## 实现、工件与验证

执行顺序为 runner（内置静态门、15 A0、55 ablations、prediction seal）、score、
independent verify。正式推理前冻结 runner、score、verifier、tests 和 source hashes。
不建立重复 initialize/complete 授权层。私有逐行输出使用 0700/0600，公开 aggregate
使用 0755/0644；输出根目录必须全新，禁止 symlink 或多个 hard links。

Major 保存 public run.json、stdout.log、prediction-seal.json、score aggregates、
verification.json，以及 private worker logits/manifests 和 scored prediction bundle。
Verifier 核对 70 workers 的身份、完整覆盖、fold-heldout 对齐、A0 replay、scale masks、
source before/after、private seal，并独立重算所有评分值。无须再次运行全部模型。
浮点评分允许 `rtol=0, atol=1e-12`，离散 predictions/identities/conditions 必须相同。
只有独立 verification Passed 才称为 Complete/Verified。

## 资源与停止条件

冻结本地 `phase-a-runtime`：Python 3.11.15、NumPy 2.4.6、MLX 0.32.0、mlx-lm 0.31.3、
safetensors 0.8.0、tokenizers 0.22.2、transformers 5.14.1，arm64。HF/transformers
offline；线程和 prompt/model sources 继承 EXP-069。

最多 70 个模型 workers，无重试，每 worker 最多 3,600 秒，runner 总上限 57,600 秒
（16 小时）；独立模型-free score/verifier 各最多 1 小时。最多一个 heavy worker，
peak MLX 10 GB、RSS 16 GiB、private output 1 GiB、开始前至少 10 GiB free disk，API cost=0。
参考 EXP-070 的已记录吞吐量，预计完整推理约 9–12 小时；这不是部署效率结论。

任一非零退出、A0 replay mismatch、hash/mode/source/runtime drift、fold leakage、非有限
值、OOM、source mutation、意外 validation/test 访问、并发 heavy workload 或预算超限
均停止并保留失败。禁止自动重试、续接失败单元或读取后续结果来修正方法。

## 论文去向与限制

目标为 RQ-S4.3 的三 seed 功能消融表与 seed-42 深度分组补充表。既有理论预期是关闭
LoRA 会削弱任务适配，但允许无性能下降或 seed-sensitive 的有效负结果。
Inference-time 关闭联合训练模块支持功能依赖描述，不能证明单独训练某模块得到同样
结果，也不能证明模块独立贡献、独立数据泛化或人类情绪机制。EXP-073 可选支线与
已暂停的 context/C2 不在本次范围。
