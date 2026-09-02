# EXP-075：允许精确零方差的表征几何分析

- Experiment ID：`EXP-075`
- Date：`2026-08-30`
- Tier：`Major`
- RQ：`RQ-S4.2`
- Parent：`DEC-SO-PHASE-B-REPRESENTATION-V1`、EXP-070、EXP-071 Incident 002
- Status：方法已登记；正式结果尚未读取
- 用户决策：确认保留 EXP-071 Failed，以本实验补充几何证据，再执行 EXP-072 与 EXP-074。

## 问题与既有信息

本实验比较 Frozen Qwen 与 fold-specific M3 对同一 heldout 样本的表征，回答 LoRA 在冻结
层位改变了哪些几何性质。EXP-071 在首个 `s42:H-1 / fold 0` 的 CKA 零分母处失败。
Incident 002 已独立验证这一定位，但没有完成几何分析。

研究者在看到该诊断后制定本协议，因此它属于 **post-diagnostic 方法决策**，不得称为原
EXP-071 的预注册结果或笔误修复。原 EXP-071 配置、代码、协议、失败和诊断工件均不改写。
本协议将 Phase B 的几何依赖改为 EXP-075 Verified；EXP-071 仍为 Failed。

## 数据、模型与固定项

沿用 EXP-071 active config 的完整 source contract：

`phase-b-representation/configs/exp-071-representation-drift-formal-attempt-1.json`

其 SHA-256 为 `0709c963f88242a706784f92d5033fe08eb46fb752d7e59e96607bc259d0ae35`。
新 config 绑定该文件、本文、实现和 tests 的 path、bytes、mode、SHA-256，运行前后核对来源。

只使用 DATA-SO-TASK-V1 train 的 3,360 行；每个冻结 outer fold 有 672 条 heldout 行。
数据版本、五折划分、九个读取点、16 个 EXP-070 representation caches、model revision、
prompt、last-token pooling、BF16 来源与 seed roles 均不变。几何计算使用 float64。
标签顺序仍为 `love, joy, surprise, anger, sadness, fear`，但本实验不读取标签。

固定比较顺序，共 75 个 fold-condition pairs：

```text
s42:H-1, s42:H7, s42:H15, s42:H19, s42:H20, s42:H27, s42:H31, s42:H35, s42:HF,
s43:H19, s43:H27, s43:HF, s44:H19, s44:H27, s44:HF
每个 condition 内按 fold 0..4，fold 内按 ascending ordinal。
```

只读取各 M3 checkpoint 对应 heldout fold 的表示。来源矩阵通过只读 memory map 打开；
不得重抽取、重训、加载模型或执行 forward。EXP-070 的 representation state 不变。

## 数值规则

除以下 CKA 缺失处理及其传播外，沿用原 EXP-071 的公式、精度、范围容差、距离统计、
pre-LoRA sanity、点位和比较顺序。

1. 对每个 fold 的特征列中心化：`Xc=X-mean(X,axis=0)`、`Zc=Z-mean(Z,axis=0)`。
   计算 `K=Xc@Xc.T`、`L=Zc@Zc.T` 和原 biased linear CKA。
2. 只有有限的 centered representation 精确全零，且对应 Gram 与平方范数精确为零时，
   才允许 `cka=null`，reason=`zero_centered_variance`。不使用 epsilon、近零阈值、
   NaN、伪造的 0/1 CKA 或替代估计量。
3. 非有限输入或中间量、非零 centered data 的零 Gram/norm、正范数乘积或开方下溢为零，
   均停止。若另一侧出现这些错误，不能用一侧精确零方差掩盖错误。
4. 非退化 CKA 使用原公式 `sum(K*L)/sqrt(sum(K*K)*sum(L*L))`；只在原
   `[-1e-12,1+1e-12]` 容差内 clip 至 `[0,1]`。
5. 保留五个 fold 的 CKA 值与逐 fold 缺失原因。仅在 5/5 defined 时计算 arithmetic mean
   和 sample SD（`ddof=1`）；否则两者均为 null，报告 `n_defined`。禁止 `nanmean`。
6. Seed-42 Spearman 保留九个点。任一点 CKA mean 缺失则 `rho=null`，
   reason=`undefined_cka_input`；不得删点或改为八点相关。九点均有效时沿用 average-rank
   Spearman 与 constant-vector null 规则，不计算 p-value 或替代相关。

Cosine distance 与 Frozen-denominator relative L2 仍按原公式计算；零向量范数停止。
距离按每 fold 和 pooled 3,360 行报告 mean、median、P90、P95，percentile method=`linear`；
不得平均 fold quantiles。Seed 42 的 H-1/H7/H15/H19，以及 seeds 43/44 的 H19，均须满足
float64 重测的最大绝对差 `<=1e-5`。不做 H19 baseline subtraction。

## 访问与工件

允许读取 16 个冻结 cache 的 heldout slices、row contract 的 `ordinal/fold_id`，以及
已验证 public probe.json 中九个 seed-42 AP5 deltas。读取 AP5 前复核 canonical results
digest。禁止读取 component codes、sample/component IDs、原文、标签、private probe
predictions/probabilities、thresholds、validation、test 或 test-gate artifacts。

使用新的 public/private roots，不覆盖或续写 EXP-071。最小执行流程：

```text
run（内置身份/header/environment/fresh-root gate） -> independent verify
```

Producer 保存 public `run.json`、`stdout.log`，private `geometry.npz` 与
`geometry-manifest.json`。Verifier 从冻结 sources 重算全部 75 pairs，并写入一次性
`verification.json`，只有 Passed 才设置 `complete=true`。失败工件保留，不自动重试。

Private NPZ 不压缩，成员依次为：

| Member | Shape | Dtype |
| --- | --- | --- |
| heldout_ordinals | (5, 672) | <i4 |
| cosine_distance | (15, 3360) | <f8 |
| relative_l2_distance | (15, 3360) | <f8 |
| max_abs_difference | (15, 5) | <f8 |

Nullable CKA 仅存在于 public aggregate JSON。Public 不保存 row-level 值、原文或标识。
Public dirs/files 为 0755/0644，private dirs/files 为 0700/0600；不允许 symlink、额外
hard link 或未登记成员。来源前后身份必须一致。

Verifier 不调用 producer 的数值函数。整型、顺序、字符串、booleans 与 null 精确比较；
浮点 arrays 和 JSON 统计使用 `rtol=0, atol=1e-12`。Synthetic tests 覆盖正常域与旧实现
一致、精确退化、非有限/下溢、五折缺失传播、九点缺失传播和 producer-verifier 互操作。

## 资源与停止条件

沿用 `/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python`，Python 3.10.20、
NumPy 2.2.6、arm64；OMP/OPENBLAS/MKL/VECLIB/NUMEXPR threads 均为 1。
最多一次 producer 和一次 verifier，单并发，各最多 7,200 秒，RSS 上限 4 GiB，private
output 上限 64 MiB，开始前至少 1 GiB free disk，API cost=USD 0。
以各进程启动后两小时作为相对截止时间；超预算前停止，不静默延长。

身份/hash/mode/environment 漂移、非空 root、source mutation、未登记字段访问、数值错误、
sanity failure、资源超限或独立复算不一致均停止。预计结果仅是假设：pre-LoRA 距离通过
等价性门，post-LoRA 出现表征变化；不要求某个 drift 值、符号或排序才算完成。

## 论文去向与结论限制

目标为 RQ-S4.2 的层位几何表、seed-42 drift curve 和跨 seed H19/H27/HF 对照。只有
Verified 数字进入 Phase B 报告。若 CKA/Spearman 未定义，原样报告缺失原因。
结果支持同一训练数据、outer-heldout、冻结输入与读取点下的几何描述；不能定位精确 onset、
证明 drift 导致 probe gain、证明新数据泛化，或解释人类情绪机制。
