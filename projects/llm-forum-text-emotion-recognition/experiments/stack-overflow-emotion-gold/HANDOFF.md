# Stack Overflow Phase A 到 Phase B 实验交接

Date: 2026-08-30

Workspace: `/Users/phoenix/Assistant/NeuroScience`

Project: `projects/llm-forum-text-emotion-recognition`

当前交接点：Phase A 已由 `DEC-SO-PHASE-A-CLOSEOUT-V1` 收口为
`Closed with partial success`。EXP-068 原始科学终态保持 `Failed or incomplete`；本地
headless/CLI research demo 已验证，deployment-efficiency evidence 未建立。

Phase B 已由 `DEC-SO-PHASE-B-REPRESENTATION-V1` 登记为
`LoRA 表征变化与功能依赖分析`。EXP-069 representation extraction preflight 已完成：
15 个 fold workers 与 assemble 全部完成，模型侧 parity errors 均为 0。Attempt-4 final
verification 因 verifier 混合两个 `manual_logit` 统计口径而保留为 Failed；model-free
verification attempt 2 拆分指标后 25/25 Passed，独立 NumPy head replay 最大误差为
`7.62939453125e-06 < 1e-5`，未重跑模型或修改 source snapshot。EXP-070 方法与 no-result
preflight 也已完成：synthetic tests 15/15、independent verifier 24/24 Passed。
Extraction-only protocol、config、runner、verifier 与 tests 已冻结，synthetic tests 11/11
Passed。Formal worker extraction 已完成 16/16：Frozen base 与 M3 seed 42 各保存 3,360 rows
× 9 points；M3 seeds 43/44 各自 5/5 folds 保存 3,360 rows × 3 points。全部 worker 的 runner
replay、pre-LoRA parity 与 standard-HF parity 均为 0。Seed 44 五折独立 float64 head replay
最大值为 `2.3313519861289933e-06 < 1e-5`；float32 最大值
`1.239776611328125e-05` 只按冻结规则记录为 diagnostic。Frozen assemble 已完成；public
`extraction.json` 状态为 `CompletedAwaitingVerification`，绑定 16 workers、16 matrices 与
private `extraction-manifest.json`。
原 terminal verifier 的跨口径 token-digest 等值条件和 float32 累加条件已在执行前登记为
verifier-only recovery。Append-only verification attempt 2 已执行并 28/28 Passed：runner MLX
最大误差为 `0.0`，float32 diagnostic 最大值为 `1.239776611328125e-05`，float64 gate 最大值为
`2.409579250794991e-06 < 1e-5`。Source snapshot 在 replay 前后保持
`cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad`；未重跑模型、worker
或 assemble，也未修改 source。Formal extraction 已完成。EXP-070 probe consumer、独立
verifier 与 34 项 synthetic tests 现已冻结；
no-result static verifier 25/25 Passed，completion 将 `formal_probe_authorized=true` 绑定到
formal config `sha256=16a66d187bc16c46997e0ab7d729848e03a02bcd088139964debc370d6e5067c`。
Formal probe `initialize` 已完成：public 只有 `run-claim.json`，private 只有
`input-manifest.json` 与 `folds/`。`fit-fold 0–4` 各封存 864/864 binary fits，共 4,320 fits；
aggregate elapsed 为 `10,604.71 s`，最大 peak RSS 为 `1.554 GB`。五个 fold 的
outer-heldout labels 在各自 `fit-fold` 阶段均未解码。`assemble` 随后首次读取全部 3,360 行
train-only outer-heldout labels，并计算 aggregate metrics、三组 label-shuffle controls 和 2,000 次
paired duplicate-component bootstrap。Runner 写入 private `probe-manifest.json` 与 public
`probe.json`，状态为 `CompletedAwaitingVerification`。Seeds 43/44 的 H27/HF votes 均通过，三组
shuffle controls 均未触发 negative-control failure，assemble 的 provisional state 为 2。

执行前审计发现 frozen formal verifier 的 public-privacy predicate 会把 exact-bound
`claim_boundary` 中的方法术语 `component-disjoint` 误判为 component ID。旧 `formal-verify`
尚未执行；当前没有实际 private-data exposure。Append-only verifier-only recovery 已冻结为
verification attempt 2，synthetic tests 12/12、static checks 18/18 Passed，no-result completion
为 `Complete`。Recovery `formal-verify` 随后完成 44/44 independent checks；result digest 与
assemble 完全一致，negative-control failure=False，state 2 `Representation effect replicated`
已通过结果验证。Recovery `formal-complete` 完整重放同一 verification 并写入 terminal
`probe-complete.json`。Source snapshot 保持 `e8e26dd0...50a8`；`formal_probe_complete=true`、
`exp070_complete=true`、`exp071_authorized=false`。EXP-070 已通过 verification attempt 2 完成。

EXP-071 已单独登记并完成 no-result preflight。Attempt 1 因相对 `--config` 路径未在 artifact
identity 序列化前规范化而 Failed；failure 与原 config 保持 append-only。Incident 001 attempt 2
只修复路径规范化并切换 fresh namespace，synthetic tests 53/53、independent static verifier
24/24 Passed，completion 为 `Complete`。静态阶段未读取 representation、row-contract value 或
probe metric value。Active formal config 已冻结并通过 runner/verifier activation gate。Formal
`initialize` 已完成；public 仅有 `run-claim.json`，private 仅有 `input-manifest.json`。Initialize
未读取 scientific values。Formal `analyze` 随后触发注册的 CKA denominator gate，状态为
Failed，error 指纹对应 `Zero or non-finite CKA denominator`。Runner 已读取 `ordinal/fold_id`
与部分 representation values，但尚未读取 9 个 AP5 values，也未写出 geometry 或 drift。
原 failure 本身不记录 condition/fold，不能单凭该文件区分零分母与非有限分母。Source snapshot 经
identity-only 重放保持 `df5e9d00...535d9`。Formal verification 和 completion 均未执行。

Incident 002 已登记为 Minor denominator diagnostic。它只按原顺序定位首个失败 pair，并报告
`norm_x`、`norm_z`、`denominator` 的类别，不保存数值或其他 drift metrics。Diagnostic
no-result preflight 已完成：synthetic 15/15、independent verifier 12/12 Passed。Active diagnostic
config 已冻结。Incident 002 已完成 independent verification（19/19 Passed）与 completion 重放，
终态为 `Complete`。已验证首个失败 pair 为 `s42:H-1 / fold 0`，`pairs_examined=1`，
`norm_x`、`norm_z`、`denominator` 的类别均为 `zero`。AP5、后续 pairs 和其他 drift metrics
均未访问或计算。原 EXP-071 保持 Failed，诊断 run.json 保留其历史状态。

## 1. 新对话先读什么

按以下顺序读取，不要只依赖本文件中的摘要：

1. 项目实验规则：`projects/llm-forum-text-emotion-recognition/AGENTS.md`
2. 本交接：`experiments/stack-overflow-emotion-gold/HANDOFF.md`
3. Phase A closeout：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-a-closeout-v1.md`
4. Phase B 决策协议：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-b-representation-v1.md`
5. EXP-069 verification recovery：
   `experiments/stack-overflow-emotion-gold/protocols/exp-069-verification-attempt-2.md`
6. EXP-070 layerwise probe：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-layerwise-probe.md`
7. EXP-070 formal extraction：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-formal-extraction.md`
8. EXP-070 formal extraction verification attempt 2：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-verification-attempt-2.md`
9. EXP-071 representation drift：
   `experiments/stack-overflow-emotion-gold/protocols/exp-071-representation-drift.md`
   与当前 Incident 002：
   `experiments/stack-overflow-emotion-gold/protocols/exp-071-denominator-diagnostic-incident-002.md`
10. EXP-068 synthesis 与终验：
   `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-068-phase-a-synthesis/`
11. Phase A 方法：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-a-inference-v1.md`
12. 当前路线：项目根目录 `research-roadmap.md` 的 `RQ-S3` 与 `RQ-S4` 条目
13. Stack Overflow C0 总实验报告：
   `stack-overflow-c0-experiment-report-2026-08-16.md`

`README.md`、`research-roadmap.md` 和 `evidence-log.md` 是长期权威记录。本文件负责
恢复执行现场，不取代它们。

## 2. 历史 RQ-S3 任务与背景

毕设题目：

> Research and Implementation of Emotion Recognition System of Forum Text Based on LLM

Stack Overflow C0 使用六标签多标签任务：

```text
love, joy, surprise, anger, sadness, fear
```

RQ-S3 当时回答：

> 在已经运行 M1 RoBERTa 后，只使用调用 Qwen 前可得的信息，能否识别少量值得升级到
> M3 Qwen3-4B Classification LoRA 的样本，从而在受控 Qwen 调用率下超过单一模型？

EXP-059 的 whole-vector oracle 证明 M1/M3 存在互补上界，但 oracle 使用 gold，不能部署。
EXP-060 的任务是验证这种互补性是否可由真实 pre-Qwen 信号预测。

## 3. 已完成证据链

### 数据与主模型

- `DATA-SO-TASK-V1`：4,800 rows，冻结为 3,360 train / 720 validation / 720 test；
  duplicate-component-disjoint。
- EXP-050：M1-M4 shared preflight，Verified。
- EXP-051 M1：RoBERTa 三 seed。
- EXP-052 M2：Frozen Qwen final-layer last-input-token + linear head 三 seed。
- EXP-053 M3：Qwen3-4B Classification LoRA 三 seed。
- EXP-054 M4：Qwen3-4B Generative LoRA 三 seed。
- EXP-055：M1/M3 validation 错误分析与不可部署 oracle。
- EXP-056：一次性 frozen test，test 此后为 `Consumed`。
- EXP-057：只读结果汇总和 Stack Overflow C0 实验报告。

冻结 test 的三 seed Macro-F1：

| Model | Macro-F1 |
| --- | ---: |
| M1 RoBERTa | `0.567459 +/- 0.007814` |
| M2 Frozen Qwen + linear head | `0.295226 +/- 0.020587` |
| M3 Qwen Classification LoRA | `0.613804 +/- 0.025733` |
| M4 Qwen Generative LoRA | `0.547823 +/- 0.015312` |

结论边界：M3 明确超过 M2；M3-M1 六标签 delta=`+0.046345`，但 bootstrap CI 跨 0；
去除低支持 `surprise` 后 delta=`-0.010735`。M4 六标签 Macro-F1 明确低于 M3。
不能写成“LLM 全面优于 encoder”，也不能从这些行为结果推出内部情绪机制。

### RQ-S3 系统支线

```text
EXP-058 paired M1/M3 train OOF
-> EXP-059 calibration + selective prediction + oracle
-> EXP-060 pre-Qwen deployable router
```

EXP-058：

- 五个 duplicate-component-disjoint folds，每折 672 rows。
- M1/M3 各五个折外模型，共为 3,360 rows 产生配对 raw logits。
- paired artifact SHA-256：
  `e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc`
- final verifier：`26,989/26,989 Passed`。
- 只访问 train；没有计算 performance、calibration、oracle 或 router。

EXP-059：

- M1/M3 均选择 identity calibration。
- selected OOF 六标签 Macro-F1：M1=`0.598919`，M3=`0.637843`。
- 去除 `surprise` 后：M1=`0.718703`，M3=`0.710509`。
- M1 max-entropy abstention 在约 90% coverage 时 Hamming-risk reduction=`20.01%`，
  bootstrap interval=`[16.80%,23.24%]`，属于边界信号。
- M3 margin abstention 在约 80% coverage 时 reduction=`31.57%`，interval=
  `[27.79%,35.74%]`。
- whole-vector oracle 只在 `313/3,360` rows 选择 M3，但相对 M1 六标签/五标签
  Macro-F1 上界为 `+0.109930/+0.087472`；这是不可部署 headroom。
- final verifier：`4,684/4,684 Passed`。

EXP-060：

- protocol 保持 frozen；no-result preflight 历史保持为 synthetic tests `7/7`、runner
  `25/25`、independent verifier `66/66 Passed`；
- formal contract suite `23/23 Passed`；formal independent verifier
  `4,412/4,412 Passed`，最终状态为 `Verified Pass`；
- selected policy=`logistic_router`，实际调用率=`14.9107%`，即 `501/3,360` rows；
- 相对 M1-only，六标签 Macro-F1 delta=`+0.040168`，五标签 Macro-F1
  delta=`+0.006097`，Hamming-loss delta=`-0.004365`；
- router target discrimination：PR-AUC=`0.318653`，ROC-AUC=`0.850804`；
- 2,000 次 duplicate-component bootstrap 95% intervals：调用率
  `[13.6673%,16.2172%]`，六标签 Macro-F1 delta=`[+0.009891,+0.071126]`，
  五标签 delta=`[-0.007688,+0.019733]`，Hamming-loss delta=
  `[-0.006332,-0.002515]`；
- 点估计决定冻结的 development gate；interval 只限定稳定性，五标签区间跨 0；
- 证据严格来自 fully nested `DATA-SO-TASK-V1` train OOF；没有访问 validation/test、
  原始文本或运行 M1/M3 model forward。

该 `Verified Pass` 只支持冻结 seed-42 M1/M3 pair 的开发阶段路由可行性，不是独立 test
结果，也不能外推为通用部署收益。

## 4. EXP-060 冻结合同

### 数据边界

- 只允许 `DATA-SO-TASK-V1` train OOF 3,360 rows。
- validation 禁止用于本实验；test 已消费，绝对禁止重新打开或评分。
- 不加载模型 checkpoint，不运行 M1/M3 forward，不重新训练 M1/M3。
- 不读取原始论坛文本，不启动 context、M2、M4 或新模型分支。

正式 row-level 输入必须是：

```text
experiments/stack-overflow-emotion-gold/oof-router/private/
  exp-058-paired-oof-production/paired-oof.npz
```

使用 EXP-058 raw logits，并从 EXP-059 public calibration record 冻结两边均为 identity。
不要把 `cross-fitted-calibration.npz` 中已有的 threshold-derived 字段直接当 formal router
输入，也不要把 `oracle_choose_m3` 当正式 target。

### Nested cross-fitting

对每个 outer fold `k`：

1. outer held-out 为 fold `k`，其余四折是 router training partition。
2. 对这四个 training folds 分别做 inner held-out：用另外三折选择 M1/M3 threshold，
   再为该 inner fold 构造 threshold-derived features 和 router target。
3. 拼接四个 inner-held-out partitions，拟合 scaler 与 logistic router。
4. 用全部四个 outer-training folds 选择 M1/M3 threshold，再构造 outer fold `k` 的
   features、target 和完整 M1/M3 predictions。
5. 只在 outer fold `k` 上生成 router score；重复五次并恢复 EXP-058 source order。

这是 EXP-060 相比原始三步建议增加的关键防泄漏修正。不得退回到“直接对 EXP-059
cross-fitted rows 再套一层普通五折”的实现。

### Router target

每条样本比较完整六位预测向量的 row Hamming loss：

```text
target=1  iff  Hamming(M3, gold) < Hamming(M1, gold)
target=0  otherwise
```

平局选 M1。M3 和 gold 只能生成 supervised outcome，不能进入 runtime feature matrix。
禁止逐标签混合 M1/M3。

### 14 列 feature whitelist

顺序必须完全固定：

```text
m1_probability_love
m1_probability_joy
m1_probability_surprise
m1_probability_anger
m1_probability_sadness
m1_probability_fear
m1_mean_binary_entropy
m1_max_binary_entropy
m1_minimum_threshold_margin
m1_predicted_cardinality
m1_highest_probability
m1_lowest_probability
character_length
m1_token_length
```

禁止：任何 M3 值、gold/correctness/oracle/disagreement、sample/component/fold ID、raw
text、validation/test statistic、M3 token length。IDs 只能用于对齐、fold integrity 与
component bootstrap，不能作为模型列。

### Policies 与调用率

- R0：M1 only。
- R1：M3 only。
- R2：M1 maximum entropy。
- R3：M1 threshold proximity。
- R4：`StandardScaler + LogisticRegression`，L2、`C=1.0`、balanced、liblinear、
  `max_iter=1000`、`random_state=42`。
- 不做 C grid，不增加 MLP/XGBoost/tree ensemble。
- 另做 100 次 deterministic component-aware random-routing diagnostic，不作为候选 policy。

Frozen nominal Qwen call rates：

```text
0%, 5%, 10%, 15%, 20%, 30%, 50%, 100%
```

cutoff 只可在 outer router-training scores 上确定，再应用到 held-out fold。cutoff ties
全部 route；报告 actual call rate，不能按 held-out scores 排序来强制精确调用率。

### Gate

只从 actual Qwen call rate `<=20%` 的点中按冻结顺序选择 candidate。相对 fully
cross-fitted M1-only，policy 必须同时满足：

1. six-label Macro-F1 gain `>=0.01`；
2. five-label Macro-F1 gain `>=-0.005`；
3. Hamming loss increase `<=1e-12`；
4. 至少一个非 `surprise` 标签 F1 gain `>=0.005`。

R2-R4 任一通过，deployable-routing feasibility 才通过。R4 是否超过 simple heuristics
单独报告；若 heuristic 通过但 R4 不通过，只能支持简单路由，不能声称 learned router 有
增量价值。

对选择点做 2,000 次 duplicate-component bootstrap，seed=`20260817`，报告 95%
percentile intervals。点估计决定 development gate；interval 只决定是否可写成稳定信号。
这仍不是独立 test。

## 5. 新对话的下一项工作

EXP-070 已通过 recovery verification attempt 2 完成。当前没有自动执行的下一门实验：

1. 保持 source formal run、五折 bundles、assemble、verification 和 completion append-only；
2. 保留 state 2 的 train-only outer-heldout linear-accessibility claim boundary；
3. 不把 probe 结果改写成 causal representation、emotion neuron 或 human mechanism；
4. EXP-071 只有在另行登记方法、输入、资源和执行门后才能启动，本次 completion 不构成授权。

不要运行旧 frozen verifier，也不要重跑 extraction verifier、model、worker、probe folds 0–4 或
assemble。Recovery verification 与 completion 必须分步写入 fresh append-only root。

Phase A 与 EXP-069 所有 terminal 目录保持 append-only；不要重跑 EXP-067、EXP-069 workers
或 assemble。C0 test 已消费，Phase B 禁止读取 test text、labels、predictions 或 test-gate
artifacts。

## 6. 已冻结并实现的 formal 细节

以下是 formal config/测试中已冻结的约束，不得在结果后调整：

- component-aware random routing 在 multi-row component 下如何达到最接近的 matched row
  count，以及 overshoot/tie policy；
- threshold grid 精确为 `0.05..0.95 step 0.01`，tie order 为 Macro-F1、Hamming、离 0.5
  最近、较低 threshold；
- candidate operating-point tie order：最高 six-label Macro-F1、最低 Hamming、较低 actual
  call rate、较低 nominal rate；
- routed-system uncertainty 如何从被选 family 的最终概率与 nested threshold 计算；
- PR-AUC/ROC-AUC 在某 outer fold target 缺少类别时的预登记处理：停止或明确记为 undefined，
  不能临时改 fold；
- public/private schema、浮点比较 tolerance 与 artifact modes。

formal 启动前的冻结 stop rules 是：若真实 nested target 出现单类 outer-training
partition、NaN/inf、component leakage、输入 hash drift、formal output 目录非空或
unexpected validation/test path，立即停止，不得用改 seed、改 C、改 fold 或改 target
绕过。正式运行与终验均已按这些规则完成；这些规则继续作为产物审计边界保留。

## 7. 环境与资源

Formal router 使用 CPU 环境：

```text
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python
Python 3.10.20
NumPy 2.2.6
scikit-learn 1.7.2
```

预算：formal analysis <=30 min，independent verification <=30 min，peak memory <=4 GB，
API/GPU cost=0。正式 analysis wall time 约 `28.16 s`、peak RSS 约 `0.200 GB`；它只拟合
轻量 logistic router，没有重新训练 4B Qwen。

## 8. Append-only 与隐私

- 已完成 run 目录 append-only。不要覆盖或“整理”历史失败记录。
- 不要再次运行 EXP-060 preflight runner 到现有
  `runs/exp-060-pre-qwen-router-preflight/`；该目录已完成并验证，runner 会拒绝覆盖。
- 不要再次运行 EXP-060 formal runner 到现有 `runs/exp-060-pre-qwen-router/` 或覆盖
  `private/exp-060-pre-qwen-router/`；正式 public/private 产物已完成并验证。
- private row-level outputs 位于 `oof-router/private/exp-060-pre-qwen-router/`，目录
  mode `0700`、文件 mode `0600`，且必须保持 Git ignored。
- public artifacts 禁止逐行 ID、fold、gold、logits、probabilities、features、targets、route
  scores/masks、predictions 或原文。
- test 已消费。任何“为了确认 router”重新读 test 的做法都是 test leakage。
- validation 已参与模型开发；EXP-060 正式主证据只来自 train OOF。

## 9. 已知事故，不要重复

- EXP-058 attempt 1：把六位 binary vector 误当标签名列表；修正记录已保留。
- EXP-058 final attempt 1：private fold parent mode 为 `0755`；收紧到 `0700` 后通过，
  paired hash 未变。
- EXP-059 final verifier attempt 1：把 `hamming_risk` 映射到不存在的 classification key；
  正式产物未重跑，修订 verifier 后通过。
- EXP-060 设计审查发现二层 threshold leakage 风险，因此冻结 nested recomputation。
  不得为了代码简单取消这个修正。

## 10. Git 现场

交接时：

```text
branch: codex/exp061-exp062-preflight-configs
HEAD: 50ce970e5794867cbbd89c1af600ddbac39ec577
remote: origin/codex/exp061-exp062-preflight-configs
remote status at transition start: synchronized
```

Commit `50ce970` 已归档并推送 EXP-064 至 EXP-068 的 105 个公共 Phase A 文件。Phase A
closeout、Phase B protocol、本 HANDOFF、experiment README 与 research roadmap 是当前衔接
步骤的新工作，尚未 commit 或 push。

工作树另有用户已有的 IELTS PDF 与 context-recovery source-preflight records。它们不属于
本衔接步骤，不得暂存或修改。

不要 reset、checkout 或删除这些文件。不要使用 `git add .` / `git add -A`。若用户之后要求
提交，先重新查看完整 status，再只暂存明确的项目公共路径；绝不能提交 `private/`、原始论坛
文本、模型权重或 checkpoint。

## 11. 当前事实状态

```text
RQ-S3 router replication: 2/2 prospective seeds Passed
Phase A lifecycle: Closed
Phase A closeout outcome: Closed with partial success
EXP-068 frozen decision: Failed or incomplete
EXP-064 bundle: Complete, verification 30/30 Passed
EXP-065 selected attempt: attempt-2 Complete, verification 30/30 Passed
EXP-066 selected attempt: attempt-2 Complete, verification 35/35 Passed, CLI open
EXP-067 attempts 1/2: Failed by preregistered RSS gate, benchmark incomplete
EXP-068: Complete, verification 20/20 Passed
System classification: Verified local research demo
Deployment-efficiency evidence: Not established
Phase B protocol: Registered under RQ-S4
EXP-069 design: Complete, synthetic tests 15/15 Passed
EXP-069 static runner: CompletedAwaitingVerification
EXP-069 independent static verifier: Passed, 14/14
EXP-069 model/forward access in static: False/False
EXP-069 validation/test access in static: False/False
EXP-069 base attempt-2: Failed before model load, FileNotFoundError
EXP-069 base attempt-3: Complete, independent verifier 23/23 Passed
EXP-069 base max errors: M2 HF=0.0, standard HF=0.0
EXP-069 base resources: 41.46 s, MLX peak 8.21 GB
EXP-069 base M3/validation/test/metrics access: False/False/False/False
EXP-069 fold workers: 15/15 Completed, all recorded parity errors=0.0
EXP-069 aggregate resources: 294.04 s, MLX peak 8.51 GB
EXP-069 attempt-4 final verification: Failed, preserved metric-contract incident
EXP-069 verification attempt-2: 25/25 Passed; NumPy head replay=7.62939453125e-06
EXP-069 overall: Complete via attempt-5-verification-recovery; no model rerun/source mutation
EXP-070 method: Frozen; full extraction owned by EXP-070, smoke fixtures excluded from fitting
EXP-070 synthetic tests: 15/15 Passed
EXP-070 no-result preflight: Complete, independent verifier 24/24 Passed
EXP-070 formal extraction implementation: Frozen, synthetic tests 11/11 Passed
EXP-070 Frozen base: Complete, 3,360 rows x 9 points, M2-HF/standard-HF errors=0.0
EXP-070 Frozen base resources: 2,032.24 s, MLX peak 8.24 GB, resume_count=0
EXP-070 M3 seed 42 / fold 0: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 0 resources: 3,289.41 s, MLX peak 8.60 GB, resume_count=1
EXP-070 fold-0 independent affine replay: float32=1.049041748046875e-05; float64=2.086469194750862e-06
EXP-070 M3 seed 42 / fold 1: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 1 resources: 2,085.12 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-1 independent affine replay: float32=9.5367431640625e-06; float64=1.5347208552896063e-06
EXP-070 M3 seed 42 / fold 2: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 2 resources: 2,093.59 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-2 independent affine replay: float32=7.62939453125e-06; float64=1.5044781136452912e-06
EXP-070 M3 seed 42 / fold 3: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 3 resources: 2,578.34 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-3 independent affine replay: float32=1.049041748046875e-05; float64=1.7814840784780017e-06
EXP-070 M3 seed 42 / fold 4: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 4 resources: 2,151.06 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-4 independent affine replay: float32=8.106231689453125e-06; float64=2.0908623792337266e-06
EXP-070 M3 seed 43 / fold 0: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 0 resources: 2,124.92 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold0 affine replay: float32=1.1444091796875e-05; float64=1.912518955649034e-06
EXP-070 M3 seed 43 / fold 1: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 1 resources: 2,380.40 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold1 affine replay: float32=1.1444091796875e-05; float64=2.409579250794991e-06
EXP-070 M3 seed 43 / fold 2: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 2 resources: 2,229.21 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold2 affine replay: float32=1.1444091796875e-05; float64=2.3480084774263332e-06
EXP-070 M3 seed 43 / fold 3: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 3 resources: 1,943.42 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold3 affine replay: float32=1.1444091796875e-05; float64=2.0202858195261797e-06
EXP-070 M3 seed 43 / fold 4: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 4 resources: 2,258.69 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold4 affine replay: float32=7.62939453125e-06; float64=1.7818263131630374e-06
EXP-070 M3 seed 44 / fold 0: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 0 resources: 2,305.14 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold0 affine replay: float32=1.049041748046875e-05; float64=1.8554483744992467e-06
EXP-070 M3 seed 44 / fold 1: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 1 resources: 2,300.78 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold1 affine replay: float32=1.049041748046875e-05; float64=2.1061606059191718e-06
EXP-070 M3 seed 44 / fold 2: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 2 resources: 2,048.08 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold2 affine replay: float32=1.049041748046875e-05; float64=2.3313519861289933e-06
EXP-070 M3 seed 44 / fold 3: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 3 resources: 2,099.80 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold3 affine replay: float32=1.239776611328125e-05; float64=1.7293328546941211e-06
EXP-070 M3 seed 44 / fold 4: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 4 resources: 2,035.08 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold4 affine replay: float32=9.5367431640625e-06; float64=1.9140310225651547e-06
EXP-070 formal assemble: Complete, status=CompletedAwaitingVerification, 16 workers/16 matrices
EXP-070 formal assemble resources: total=35,955.28 s, peak MLX=8.60 GB, private bytes=2,890,351,543
EXP-070 extraction manifest: bytes=10,612, sha256=ef8092d7c8704199d7f5d8dce0c240418fde62a0b71ff4ba07a9da45c151d347
EXP-070 public extraction: bytes=1,596, sha256=1ad33d4197517993a07e2af7f9fea14d7185e537a52376c1a400c91237793cfe
EXP-070 verification attempt-2: Passed 28/28, failed=0, formal extraction Complete
EXP-070 attempt-2 max errors: runner MLX=0.0, float32 diagnostic=1.239776611328125e-05, float64 gate=2.409579250794991e-06
EXP-070 attempt-2 snapshot: cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad, unchanged=True
EXP-070 attempt-2 verification: bytes=7,097, sha256=21e41625527702a4d8534225692a5d06fbf672add51eb67395af2a6e8803e5f5
EXP-070 attempt-2 completion: bytes=2,302, sha256=02755a7985e83e988fa5f0e3e2fbfaa22c7255ca1cfa7a8f2191ea5f222cb5cb
EXP-070 formal extraction: Complete via formal-extraction-verification-attempt-2
EXP-070 formal probe protocol: Frozen, bytes=17,832, sha256=0c4d927e9bded6d914700c587b1125de5af745ad91be92d09ae6a1569c853c29
EXP-070 formal probe runner/verifier: bytes=111,545/114,123, frozen identities Passed
EXP-070 formal probe synthetic tests: 34/34 Passed
EXP-070 formal probe static verification: Passed 25/25, failed=0
EXP-070 formal probe static completion: Complete, formal_probe_authorized=True, real probe=False
EXP-070 formal probe preflight config: bytes=30,871, sha256=ae9d729a57eaa759831292fda7fe63584a74ce40d64b9e9652a44708d183f8e5
EXP-070 formal probe config: Frozen, bytes=35,922, sha256=16a66d187bc16c46997e0ab7d729848e03a02bcd088139964debc370d6e5067c
EXP-070 formal probe initialize: Complete, sealed fold prefix=0/5
EXP-070 formal probe run claim: bytes=1,357, sha256=e1cac842098da65c04a7e8537d20ca1dc787ecdf3427244caec4b4e447742455
EXP-070 formal probe input manifest: bytes=21,305, sha256=7e34c0c1e42ce5850d0116776affd0ea96ec903a5a25aff551cd79ee8a504c7c
EXP-070 initialize label/representation/probe/metric access: False/False/False/False
EXP-070 formal probe fold 0: Sealed, 720 main + 144 shuffle fits, elapsed=2,119.20 s, peak RSS=1.507 GB
EXP-070 formal probe fold 0 convergence: main max_iter=29, shuffle max_iter=11, all within 2,000
EXP-070 formal probe fold 0 NPZ: bytes=4,664,038, sha256=b1e71ac421f5463005ce5fd7be18084e4a368ca49de8c23dc228fa75d15a380b
EXP-070 formal probe fold 0 seal: bytes=28,661, sha256=d3f156294fd37f59b4c857a685270ffae8aabdfee0814d3b723c3f126c2ada3a
EXP-070 fold 0 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 1: Sealed, 720 main + 144 shuffle fits, elapsed=2,096.91 s, peak RSS=1.554 GB
EXP-070 formal probe fold 1 convergence: main max_iter=35, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 1 NPZ: bytes=4,664,038, sha256=0c237e0d3192225cf619758b1ebab9e881061e33269875d1930b925c0ffd3c81
EXP-070 formal probe fold 1 seal: bytes=28,661, sha256=465ada0d1f9d65243d3766e888cb2a420f6aa51ce2a2b8569eef56ef5696160e
EXP-070 fold 1 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 2: Sealed, 720 main + 144 shuffle fits, elapsed=2,121.81 s, peak RSS=1.475 GB
EXP-070 formal probe fold 2 convergence: main max_iter=29, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 2 NPZ: bytes=4,664,038, sha256=f2af1c4ff64dad11b338030885d45cfad1233bb4fcd988b1c0f22b87f9b9a614
EXP-070 formal probe fold 2 seal: bytes=28,663, sha256=b49ac9506c254699bd0a472d51e34103f681a6b2f51ecb354c35847555687224
EXP-070 fold 2 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 3: Sealed, 720 main + 144 shuffle fits, elapsed=2,139.69 s, peak RSS=1.551 GB
EXP-070 formal probe fold 3 convergence: main max_iter=42, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 3 NPZ: bytes=4,664,038, sha256=a79210ac75936b10ec73180d96bbebf4dc1a30a1bafb8e071936293d4528faf6
EXP-070 formal probe fold 3 seal: bytes=28,663, sha256=a0c69fade6ced6613f8ea3f0770ec62c768860cad7da0a5e6331098169f39292
EXP-070 fold 3 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 4: Sealed, 720 main + 144 shuffle fits, elapsed=2,127.09 s, peak RSS=1.550 GB
EXP-070 formal probe fold 4 convergence: main max_iter=42, shuffle max_iter=11, all within 2,000
EXP-070 formal probe fold 4 NPZ: bytes=4,664,038, sha256=e8e23151060552f32d4043a2144d6908d687a4108e2d784a2e56966ec6f47b03
EXP-070 formal probe fold 4 seal: bytes=28,662, sha256=907f2eda0006f3ccf5e4925bff0a3e838cb866f0bdf88dbada9f3adbde577ee3
EXP-070 fold 4 heldout-label/metric/bootstrap access: False/False/False
EXP-070 probe fitting: fold prefix 5/5, 4,320/4,320 fits sealed
EXP-070 assemble: CompletedAwaitingVerification, 2,000 bootstrap replicates
EXP-070 assemble resources: elapsed=1,305.92 s, aggregate elapsed=11,910.63 s, max RSS=1.554 GB
EXP-070 public probe: bytes=53,748, sha256=977021e97a5c6a69dc6894161f4717b53c2a651919d7a5655f1b9e6ac246f89b
EXP-070 private probe manifest: bytes=68,146, sha256=307af86570048752e31c098224fe92e1d78c7e875a70f3818810e13543bc9fe0
EXP-070 seed 43 votes: H27 delta=+0.171805, CI=[+0.135379,+0.197979]; HF delta=+0.160120, CI=[+0.125498,+0.190265]; Passed
EXP-070 seed 44 votes: H27 delta=+0.170951, CI=[+0.133225,+0.197842]; HF delta=+0.153390, CI=[+0.118997,+0.183234]; Passed
EXP-070 shuffle controls: 0/3 both-prospective-seeds pass; negative_control_failure=False
EXP-070 assemble provisional state: 2, Representation effect replicated; result identity later verified by recovery attempt 2
EXP-070 assemble outer-heldout labels read after 5/5 seals: True
EXP-070 aggregate metrics/bootstrap: executed; validation/test access: False/False
EXP-070 extraction model/forward: True/True for 16 sealed workers
EXP-070 assemble model/forward: False/False
EXP-070 attempt-2 model/forward/source mutation: False/False/False
EXP-070 frozen formal verifier: Unexecuted
EXP-070 pre-verification blocker: public-privacy false positive on exact-bound method text component-disjoint
EXP-070 source probe.json historical formal-probe/EXP-070 complete flags: False/False; EXP-071 authorized=False
EXP-070 verifier recovery protocol: bytes=9,070, sha256=e908da3625297ddce317fb585b1e8cbc8b46f2c3adeda70b9375f0949f04e187
EXP-070 verifier recovery config: bytes=10,091, sha256=65f3753cb6680d8e17dfb9c3e7df4fd2fbf9274b5e404eb6d3914e6c5514b3cd
EXP-070 verifier recovery verifier/tests: bytes=62,825/39,071, sha256=c6d8def966c2742034f5a287844e1cb6189fb9648468e43bfaa3cc0ec3d4a237/725cea6f3e8b8545e352585e4563b658b7302ddc264a36544489ba3918ce9532
EXP-070 verifier recovery synthetic/static: 12/12 Passed, 18/18 Passed
EXP-070 verifier recovery static verification: bytes=4,289, sha256=abe114ec963208b8a274f976833944cd6dadb07c7f1fc5783292c90590a75829
EXP-070 verifier recovery no-result completion: Complete, bytes=1,679, sha256=1193246a23e9cbce6f9304b5e5771481575408fdf5cf3bd74d9ece68cdf97d6d
EXP-070 verifier recovery static access label/probability/representation: False/False/False
EXP-070 recovery snapshot claim: bytes=2,365, sha256=75e73e2867c8d4eae7444c1a2ff4066ec2bd705b0b29d4cea42625ddb6d55972
EXP-070 recovery verification: Passed 44/44, bytes=5,195, sha256=c39ecb65ccbc706e4a709bacb66d7e292e6d3e379cd0303bc1f1021a12dcf9cf
EXP-070 recovery result digest: 8097645dc0812c95242b517d966790c660e4571ba1196aea691b265027b7f88d
EXP-070 recovery source-verification payload digest: 0f777afadeb953e9958dbe464b7e7b0bff607e6631a738556a35fd3f77836cf3
EXP-070 recovery verified result: negative_control_failure=False, state=2, Representation effect replicated
EXP-070 recovery access label/probability/thresholds/metrics/bootstrap: True/True/True/True/True
EXP-070 recovery access representation/refit/model/forward/validation/test: False/False/False/False/False/False
EXP-070 recovery source snapshot: e8e26dd014d21371041409a78e95be147ac0bd495ad01ff5a268cafaf94b50a8, unchanged=True
EXP-070 recovery completion: Complete, bytes=2,654, sha256=0e15d164b1539d51d2917001629b9ccd5c89d0569fc863a37d61e2990aad0cd2
EXP-070 recovery source-completion payload digest: d23863930ab4f984e0eb61217833011224c9637cc0a192f6c78a44d54b4aa97d
EXP-070 recovery terminal inventory: claim + Passed verification + completion
EXP-070 formal probe/EXP-070 complete: True/True; EXP-071 authorized=False
EXP-070 final state: 2, Representation effect replicated; negative_control_failure=False
EXP-070 completion boundary: EXP-071 unauthorized there; superseded by the separate registration below
EXP-071 method: registered; method sha256=f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210
EXP-071 preflight attempt 1: Failed; relative config path normalization defect; failure preserved
EXP-071 Incident 001 attempt 2: Complete; synthetic 53/53; static verifier 24/24 Passed
EXP-071 static access representation/row-contract-value/probe-metric: False/False/False
EXP-071 active formal config: configs/exp-071-representation-drift-formal-attempt-1.json; bytes=30,400; sha256=0709c963f88242a706784f92d5033fe08eb46fb752d7e59e96607bc259d0ae35
EXP-071 formal initialize: Initialized; run-claim bytes=2,565, sha256=763fee43dbc643cb01b9a477a92ebd9a3e339bbe0740948ab055e8caabc7d937
EXP-071 private input manifest: bytes=5,769, sha256=3e5671aaad9f702d95168a05a5cb3d4d1cf0382550d1ba83196b5792ffe0ec42
EXP-071 formal access representation/row-contract-value/probe-metric: False/False/False
EXP-071 formal analyze: Failed; error=Zero or non-finite CKA denominator; failure bytes=390, sha256=3900425566334ceeac9c920e547cec252504303ac045a52a3b82820c98789d40
EXP-071 analyze access representation/ordinal-fold/AP5: True/True/False
EXP-071 source snapshot after failure: df5e9d00c2464462eb541b3416efe4d96c6836efb43d778699392fe3501535d9, unchanged=True
EXP-071 formal lifecycle: Failed; no geometry/drift/verification/completion; no EXP-071 state
EXP-071 Incident 002 diagnostic preflight: Complete; synthetic 15/15; independent verifier 12/12 Passed
EXP-071 diagnostic minimal snapshot: 28 artifacts, ee5e1c53b090f377795e17551971105f5126d070d1efc3e5e269ba3ce939cff8
EXP-071 active diagnostic config: configs/exp-071-denominator-diagnostic-formal-attempt-1.json; bytes=26,323; sha256=07f06972de22b32b9b9baea74bb000bb506ba6dac00142cc0cd2666739c13080
EXP-071 diagnostic initialize: Initialized; public run-claim bytes=2,171, sha256=10fa878949342c06c3e0e1debe2f933e9e174c70e0387be68ec0874babd33e5b
EXP-071 diagnostic input manifest: bytes=11,624, sha256=ee697f438cf0f78742167b0100c0176ddb2c4c07b7b0aebb9e0b836da1aa7936
EXP-071 diagnostic run: CompletedAwaitingVerification; run.json bytes=2,983, sha256=4ad3446b3a23fb15445790401def833830f8c8eea16d66c4e1aa105c64d2d09d
EXP-071 diagnostic manifest: bytes=16,215, sha256=c1396ec4e4df079aad1f3e9bf2de448896b6249cfa878ae44093a53e7586d211
EXP-071 verified diagnostic localization: s42:H-1, fold=0, pairs_examined=1; norm_x/norm_z/denominator=zero/zero/zero
EXP-071 diagnostic verification: Passed 19/19; bytes=3,668, sha256=d6a445112bb133ed18bffb8d860d1f4db245782df1d6c2730bbb4e363c4a7b5b
EXP-071 diagnostic completion: Complete; bytes=2,146, sha256=2f016322e863575b500ac6e82cb15aa65eeec84e28c034761cba94553f6732d1
EXP-071 diagnostic_complete=True; original_exp071_status=Failed; exp071_complete=False; recovery_authorized=False
EXP-071 diagnostic access representation/ordinal-fold/AP5: True/True/False; no exact-term persistence or other drift metrics
Test status: Consumed; forbidden for development
Phase A evidence commit: 50ce970, pushed
Transition documents: local working-tree changes, not committed
```

EXP-070 已完成，不重跑旧 verifier、model、worker、extraction assemble、probe folds 0–4、probe
assemble、recovery verification 或 completion。EXP-071 formal attempt 1 已 Failed；禁止删除
failure、同 attempt 重跑或执行原 formal verifier。Incident 002 diagnostic 已完成封存，不再重跑
diagnose、diagnostic-verify 或 diagnostic-complete。本次只确认首个 CKA 分母零值位置；原实验
recovery 或 method change 不属于该诊断。Phase B 继续保持
outerheldout OOF、test consumed、private hidden-state 和 append-only 边界。任何 layerwise
probe、drift 或 ablation 结果都不能改写为人类情绪机制或 independent-data mechanism
validation。

### 2026-08-30：EXP-075 完成，进入 EXP-072

用户已确认 post-diagnostic 新 Major EXP-075，并授权连续执行 EXP-075 → EXP-072 → EXP-074。
EXP-075 已完成，不需重跑：26/26 synthetic，75/75 geometry pairs，20/20 independent
verification Passed；`exp075_complete=true`，`exp071_complete=false`。
Public terminal 为 `phase-b-representation/runs/exp-075-degenerate-aware-geometry/attempt-1/verification.json`，
SHA256=`0b2d73bd8775881e43f15578296458dfb541c0be1fe50f3eff71070cfd672468`。
H-1 的五折 CKA 均为 null/zero_centered_variance；九点 Spearman 为
null/undefined_cka_input；其他 70 个 CKA 有定义，pre-LoRA sanity 通过。
Results digest=`35342caaa55116f36b81a90bae7158c5069de045ee612a07a97f7e700127e46b`。

EXP-072 和 EXP-074 独立协议已登记。EXP-072 固定 15 个完整 A0 replay 后再执行 55 个
消融 workers，每个 fresh process；全部预测封存后才评分。不需要逐步骤授权，遇到实际
失败或方法变化仍停止。Context/C2 暂停、EXP-073 可选。

EXP-072 已在 `2026-08-30T03:22:56Z` 启动完整连续执行。49/49 synthetic tests 通过，
119-artifact metadata gate Passed，source snapshot 为
`be16768a22f7d1d3691ddfe27c991b7fd02c5fea5c0d5e6820f8202b54f35549`。
Active config：`phase-b-representation/configs/exp-072-lora-functional-ablation.json`，
9,954 bytes / 0644 / SHA256=`60f670d53fa551a5b43c38dcd1ddb861709e80df9b6b2022e388876db9c75a4e`。

后台 shell 已串联 `run --stage run` → `score_exp072_ablation.py` →
`verify_exp072_ablation.py`，每一步仅在前一步 exit 0 后执行。Exec session=`45924`，
最初 scheduler PID=`10843`；不要重复启动 runner 或手动同时启动 scorer/verifier。
进度在 `phase-b-representation/runs/exp-072-lora-functional-ablation/formal-attempt-1/stdout.log`。
`run-claim.json` 的 Running 是不可改写的历史声明；当前状态应从进程、worker records、
run.json、score.json、verification.json 和 failure records 判断。若 PID 已复用，不能
据 PID 存在就认定本实验仍运行，必须核对 command identity。

App heartbeat `phase-b` 每小时在本任务继续检查；运行中只读取 metadata，失败即暂停
跟进并报告，禁止修改 frozen sources、重试或恢复。EXP-072 Passed 后生成 EXP-074 配置，
绑定七个 verified public inputs，再执行 synthesis → independent verify → private Markdown
研究报告。报告和最低完成集都交付后暂停 heartbeat。

EXP-074 代码与 12/12 synthetic tests 已完成。已按真实 EXP-070 recovery 终态核对
metadata compatibility：verification 用 `source_probe`、`source_snapshot_unchanged`；
completion 通过 `verification` 绑定前者，没有 `run` 或 `source_unchanged` 字段。
当前尚无 EXP-072 评分结果或 EXP-074 正式结果，不得宣称 Phase B 已完成。

### 2026-08-30：最终实验收口

本节取代上节的运行中状态。后台 session 45924 已退出 0，不得重新启动该 pipeline。
EXP-072 于 `2026-08-30T11:09:31Z` 完成全部 70 workers，随后 score 与 independent verifier
均成功；20/20 checks Passed，`exp072_complete=true`。15 个 A0 replay 最大误差均为 0。
推理 wall time=27,993.56 s，MLX peak=8.593 GB，RSS peak=5.553 GB。
Verification SHA256=`896c8a913606ce861676e3da2849830f8b664ff06c1bef777934ba5548f9f3c0`。

EXP-074 active config：`phase-b-representation/configs/exp-074-phase-b-synthesis.json`，
SHA256=`eab598e7988c3e02147946b5642f2a26453c294a44b354400f524e552ad00c89`。
12/12 synthetic tests 通过，正式 synthesis 与 independent verification Passed。
最终 verification：`phase-b-representation/runs/exp-074-phase-b-synthesis/attempt-1/verification.json`，
SHA256=`c1e5dc3e2961cbd4505566f116514e5ca104f26018b08e6fee7fbd0ec0137f88`。
`exp074_complete=true`，`phase_b_minimum_complete=true`，`source_unchanged=true`。
Summary SHA256=`9459600ddb4b1d5809c79e48c1e5f6848c34cdadc48d4a50a3e42fd40ca8133d`。

两项独立结论为 `Representation effect replicated` 与
`Stable Attention-dominant dependency`。确认 seeds43/44 的 D 为 +0.137906/+0.110372；
seed42 的 D 为 −0.164585，方向相反，不能写“三个 seed 一致”。所有结论限定 same-train
outer-heldout；A1 不是重新训练的 M2，深度分组只在 seed42 实施。

报告：`phase-b-representation/private/reports/phase-b-research-report-2026-08-30.md`，
本地 Git-ignored Markdown，reports 目录 0700、报告文件 0600。报告核对已通过：405 个表格
数值单元、213 项差值及科学边界均无待修正问题；10 张表的列结构与 12 个本地链接通过。
Heartbeat `phase-b` 已设置为 PAUSED；本次未 commit/stage/push，Phase B 最低实验集及报告
交付已完成，不再自动运行后续实验。
原 EXP-071 Failed 与诊断 Complete、EXP-075 post-diagnostic、H-1 CKA 和固定九点
Spearman 的 null 均保留。EXP-073 未执行、context/C2 暂停，不属于已完成的扩展实验。

### 2026-08-30：Phase C 本地网站当前交接

用户最新范围：先不做 CancerEmo 等其他数据集的泛化，推进系统其余部分。
新模块为项目根目录 `forum-topic-emotion-web/`，不要改 Phase A/B 的冻结来源。
读模块 README、docs/spec.md、docs/plan.md、docs/acceptance.md 与
`protocols/exp-076-phase-c-local-system.md` 恢复当前状态。

95/95 合成/集成 tests 通过。真实 smoke 四 jobs、每 job 8 条新编英文输入均完成；
Research 每次 3 个实际 M3 forwards + 1 个缓存命中，Demo budget0 显式回退 4 条。
独立函数复算 snapshot、标签统计、成本和重放通过；M1/M3 replay max abs 均为 0。
该 smoke-only 检查不是完整 EXP-076 verification，不能说 Phase C 或真实来源闭环完成。

EXP-076 source job `83dd3569136d42f1abedcfba135c0bd3` 于 fetching 阶段 Failed，
`worker_failed`、manifest null、sealed rows=0，没有进入模型推理。
工件：模块 `private/validation/exp-076/attempt-1/`，包括 smoke/source 各自终态与日志。
原异常未保留为具体类别；只读 API filter、同 query pagesize0 metadata 均能正常访问，
因此目前不能确定原失败原因。只读审查另合成复现无 header gzip/deflate decoder 缺口，
但其与原失败的关联未证实。未在失败后修改代码、重采 posts 或运行完整 verifier。

下一步应先对新模块做最小采集错误留痕/压缩兼容修复，测试通过后再登记有界来源复测；
不需要重跑已经完成的四个模型 smoke jobs，更不重跑 Phase A/B。
继续保留失败工件，不冒充“原 attempt 已修好”。Runtime Soak V2、Discourse 真站接入、
normalized unique-text/完整时间视图和最终答辩材料仍待完成。
Discourse 站点尚未由用户指定；未选站点时 live 入口拒绝。外部 gold 与 context/C2 暂停。

本地服务启动命令为模块 `.venv/bin/python start.py`，监听 127.0.0.1:8787；
本轮服务 PID=44570、exec session=25544，先检查存活，勿重复启动。浏览器已本机登录，
令牌在 ignored `private/access-token`（0600），不要输出或提交令牌。
模型仍使用冻结 conda `phase-a-runtime`，网站依赖在独立 `.venv`；无 stage/commit/push。
原 phase-b heartbeat 保持 PAUSED，未为本地网站创建新自动化。

### 2026-08-31：source attempt 2 已停，明确评论字段阻塞

本节更新上一节的当前执行点。用户“下一步”后，collector已补gzip/deflate/代理明文兼容，
worker已补安全错误类别、阶段、计数与最多4条文件/函数/行号栈帧，112/112 tests通过。
模型bridge、core和fixture均未变；旧source/smoke所有文件保持原hash。
原实现与协议在模块 `private/validation/exp-076/attempt-2/` 归档，38项源码hash匹配。

`.venv/bin/python scripts/validate_local.py source --attempt 2` 已执行一次并退出1。
新job：`3467697c6e954893a59d0c1e17fbaf2a`，error=`source_body_markdown_missing`。
具体定位：第3次API请求、comments/page1、record校验；HTTP200、gzip、4,229 wire bytes、
返回100条且has_more=true。失败前92条问题/回答仅在内存，sealed/predictions=0/0。
没有进入模型推理，没有重跑四个smoke，没有执行完整verifier或第三次采样。
Source terminal SHA256：`205778bf617dac7712010de0367ea544829c4a438bc518bd6f1d94b8a6083a37`。
只读复核source.json与数据库progress一致、代码和继承hash未变；这不是完整EXP-076 Passed。

查到 [上游字段依赖报告](https://meta.stackexchange.com/questions/247899/creating-an-api-filter-with-comment-body-markdown-but-without-comment-body)：
comment.body_markdown可能必须与comment.body同时请求才返回。旧filter只额外请求Markdown；
本次症状相符，但尚未做当前接口字段A/B验证，不能声称已修好或确定原attempt1原因。
下一步应先做最小filter联合字段确认：额外请求comment.body，仍只使用返回的body_markdown，
不把HTML转成模型输入；确认后再登记有界来源复测。保留两次失败，沿用EXP-076，
不要重新运行模型smoke、Phase A/B，或引入复杂Incident/授权链。

旧服务PID44570已在所有任务终态时正常停止。当前修复版服务PID=48767、session=59886，
监听127.0.0.1:8787；恢复时先只读检查，勿重复启动。来源runner session95209已退出1。
浏览器已显示新错误代码，本机token仍在private/access-token。没有stage/commit/push。
外部gold、context/C2、Discourse和Runtime Soak V2本轮均未执行；phase-b heartbeat仍PAUSED。

### 2026-08-31：EXP-076 有限来源验收完成，下一步 Soak V2

本节为当前状态。用户再次“下一步”后，按原protocol追加的attempt3执行了最多5请求的字段
检查：同3个comment IDs，旧filter缺body_markdown 3/3，新filter额外请求comment.body后
两字段返回3/3。没有HTML-to-text回填、没有模型或gold访问。Field-probe SHA256：
`dfe0438fe73f2db5e220aa88359b42e5d620e01f5757220757c8c8a0186e92d7`。
新filter固定为 `nFzTOPGAOEckIq4PwsL9Jd`，只把原生Markdown送模型。

source attempt3已完成：46 questions、46 answers、248 comments，总340/340预测。
同原Python标签、`[2026-08-23,2026-08-30)` UTC窗口；5次API请求，sampling_complete=true。
M1 only：338实际计算+2缓存命中，M3=0、fallback=0。Job耗时32.77s；RSS peak803,782,656 bytes。
Job ID=`5ab3326150ee448ba326233264967d34`。原source1/2 Failed与4个成功smoke都保留，未重跑。

`.venv/bin/python scripts/verify_local.py --attempt 3` 已22/22 Passed，exp076_verified=true。
源码、协议、旧失败/归档、field-probe、来源/parent/time、输入hash、统计、缓存和原重放均已核对。
工件在模块 `private/validation/exp-076/attempt-3/`：

- source.json SHA=`3779713265e507787678e471320834e13f09f9a2a1a8683c69b03603eec9e272`。
- verification.json SHA=`7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8`。
- sealed snapshot SHA=`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
- 数值验收源码在verified-code.tar.gz，SHA=`09d4c2b771edb1920767fc61924a35777fa2c99919d199e4f0ae1225cab891e3`，21项匹配。

数值验收之后，网页链接抽检发现原评论`/posts/{post}`路径404。因此仅修改Store.items的
public projection：使用`/questions/{thread}#comment{comment}_{parent}`，旧地址保留为
recorded_source_url。私有record/source snapshot/model input/预测不改，API与export一致。
实际API核对340条identity/hash及全部248条comment链接映射通过，见presentation-verification.json。
源码验收时134tests，展示修正后147/147。原22项数值verification不覆盖HTTP活性，
不能把link字段覆盖率100%写成匿名HTTP可用率100%；问题/回答HEAD可重定向但网站最终返回403。

不要重跑已有source或overwrite verification；后续代码已有presentation-only差异，旧源码
以verified-code归档为准，不要把当前store.py差异误判成模型或数据漂移。
完整结论与历史见模块docs/acceptance.md，当前工作计划见docs/plan.md。
下一步是有界Runtime Soak V2协议/实现/验收；它不是context/C2恢复，也不是旧EXP-067重跑。
Discourse仍待指定审核站点，外部gold和context/C2继续暂停；Phase C整体尚未完成。

当前服务PID=55532、session=2493，监听127.0.0.1:8787；PID54665已在任务完成后正常停止。
source runner session6371已退出0，字段probe session5349已退出0。先核对进程身份，勿重复启动。
未stage/commit/push、未公开部署或上传数据。phase-b heartbeat继续PAUSED，没有新增自动化。

### 2026-08-31：Phase C功能交付，EXP-077安全停止，EXP-078未执行

本节为当前状态。用户要求一次完成已规定步骤、不逐门授权；该授权不取消资源停止门。
Module：`forum-topic-emotion-web/`。完整两权重/日周/六标签构成/类型路由分层、运行诊断、CSV、
单job全文清除和4份使用材料已实现，212/212tests及JS syntax通过。
已有5成功任务372条新视图/CSV只读复核Passed，原source/smoke逻辑记录不变；
工件`private/validation/phase-c-views-qa.json`和可复核脚本`check_phase_c_views.py`。

已登记并实际执行EXP-077（新Soak，不是旧context/C2），固定36job/15,120事件，不能更改分母。
于UTC02:35:43.987598、elapsed40.221628s在critical_memory_pressure门停止：
M1 job `6c1f57fde85d4da2a5d322039fdd4d0c` completed420/420；Research job
`a510bc76034e43dc97a5bbfdc7872485` cancelled，420已封存、0结果回执；34job未提交。
独立verification Passed，**exp077_complete=false、soak_gate_passed=false、stop-required**。
不要把审核Passed说成benchmark成功，不要重跑、修复/覆盖attempt-1或自动启动后续模型。

M1已确认338forward+82cache，child plateau1.037315≤1.05；cross-job无法评价。
40系统样本含2个critical（相隔约22.7ms，不是2秒），交换超阈值最长连续2间隔，没有达到
3间隔thrashing定义。Research尝试/峰值未知，不能记0或归因M3 OOM。保留全机因果边界。
输出`private/validation/exp-077/attempt-1/`，verification SHA256
`339bd2da52e3bffa0cfe796239ecd857f80becead5f2b829c5cf3a3b03d61f13`；
run SHA=`69c7e18f1dd2664cdef170d9e899a7dd57b6748bbb902af222ad8e4613ddd81e`。
Serve PID61665/session42910及driver session59779已停止/退出1；无模型child存活，停服后6绑定hash一致。

EXP-078：Python Help（discuss.python.org category7）已审核，匿名原生raw两帖子三返回可行；
adapter、固定来源UI、run_discourse_validation.py、verify_discourse_validation.py及tests完成。
因Soak不是safe-to-continue，**未执行正式300–400条采样或Research任务**，不存在正式verification。
这不是Discourse采样失败或数据为0；不能绕过Soak门来补平台数。

本地API恢复为PID62541/session62736，127.0.0.1:8787；仅用于本轮查看已有任务，不提交模型任务。
恢复时仍须核对PID身份；服务启动本身不加载模型。Browser已登录，token不输出。
报告与结论清单位于模块`private/reports/phase-c-system-report-2026-08-31.md`及
`final-claims-2026-08-31.md`，Git-ignored。使用手册/schema/model-bundle/demo-script在docs。
功能和材料已交付，不能宣称完整Phase C实测完成。后续需先确定资源问题的处理方向，
本轮不自动诊断负载、重试、降低门限或恢复C3。外部gold与旧context/C2暂停；无stage/commit/push、
公开部署或数据上传，原phase-b heartbeat维持PAUSED，没有新自动化。
