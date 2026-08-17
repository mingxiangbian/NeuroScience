# Stack Overflow C0 / RQ-S3 实验交接

Date: 2026-08-17

Workspace: `/Users/phoenix/Assistant/NeuroScience`

Project: `projects/llm-forum-text-emotion-recognition`

当前交接点：EXP-060 的科学协议与 no-result preflight 历史保持冻结；正式
pre-Qwen router 已完成，独立终验为 `Verified Pass`。

## 1. 新对话先读什么

按以下顺序读取，不要只依赖本文件中的摘要：

1. 项目实验规则：`projects/llm-forum-text-emotion-recognition/AGENTS.md`
2. 本交接：`experiments/stack-overflow-emotion-gold/HANDOFF.md`
3. EXP-060 冻结协议：
   `experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md`
4. EXP-060 preflight 终验摘要：
   `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router-preflight/VERIFICATION-SUMMARY.md`
5. EXP-060 formal 报告：
   `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/REPORT.md`
6. EXP-060 formal 独立终验摘要：
   `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md`
7. RQ-S3 当前路线：项目根目录 `research-roadmap.md` 的
   `Conditional Encoder-Qwen Router` 与 `RQ-S3` 条目
8. 证据台账：项目根目录 `evidence-log.md` 的 `EVID-065` 至 `EVID-069`
9. Stack Overflow C0 总实验报告：
   `stack-overflow-c0-experiment-report-2026-08-16.md`

`README.md`、`research-roadmap.md` 和 `evidence-log.md` 是长期权威记录。本文件负责
恢复执行现场，不取代它们。

## 2. 研究任务与当前问题

毕设题目：

> Research and Implementation of Emotion Recognition System of Forum Text Based on LLM

Stack Overflow C0 使用六标签多标签任务：

```text
love, joy, surprise, anger, sadness, fear
```

当前 RQ-S3 不是继续比较更多模型，而是回答：

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

EXP-060 formal 已完成。新对话先只读复核 formal `REPORT.md` 与
`VERIFICATION-SUMMARY.md`，并保持现有 formal/preflight 目录 append-only；不要重跑、覆盖、
换 seed、调 target、改 feature whitelist 或依据结果改 gate。

下一项研究工作应是把这个 train-OOF `Verified Pass` 按现有证据边界纳入路线与论文叙事，
并决定是否需要另行预注册一个真正独立的部署成本/泛化验证。后者不是 EXP-060 已经给出的
结论，也不能通过重新打开 validation/test 来补做。若没有新的独立数据或明确授权，保持
RQ-S3 结论为“冻结 seed-42 pair 的开发阶段路由可行性”，不继续制造部署收益主张。

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
branch: main
HEAD: 64fa05571b936516be0b3f9415464adedf6856cc
```

项目工作树是 dirty；EXP-057 至 EXP-060 的多个目录仍为 untracked，项目 README、roadmap、
evidence log 有未提交修改。本轮没有 commit 或 push。

不要 reset、checkout 或删除这些文件。不要使用 `git add .` / `git add -A`。若用户之后要求
提交，先重新查看完整 status，再只暂存明确的项目公共路径；绝不能提交 `private/`、原始论坛
文本、模型权重或 checkpoint。

## 11. 当前事实状态

```text
EXP-058: Verified
EXP-059: Verified
EXP-060 protocol: Frozen
EXP-060 no-result preflight: Verified (7/7, 25/25, 66/66)
EXP-060 formal contract tests: Passed (23/23)
EXP-060 formal result: Verified Pass (4,412/4,412)
Selected router: logistic_router, 14.9107% call rate (501/3,360)
Six-label Macro-F1 delta: +0.040168
Five-label Macro-F1 delta: +0.006097
Hamming-loss delta: -0.004365
Router discrimination: PR-AUC 0.318653, ROC-AUC 0.850804
EXP-060 evidence split: train OOF only
Validation/test/model forward/raw-text access for EXP-060: False
Validation access for EXP-060: Forbidden
Test status: Consumed; forbidden for development
Commit/push of current work: Not done
```

新对话最重要的边界是：EXP-060 已按冻结合同给出可复算的 `Verified Pass`，但它仍是
train-OOF development evidence；后续必须保持 test、隐私、append-only 和 nested OOF
边界，不把它改写成独立 test 或通用部署结论。
