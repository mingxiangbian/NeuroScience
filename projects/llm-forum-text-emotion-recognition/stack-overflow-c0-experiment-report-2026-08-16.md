---
title: Stack Overflow C0 六标签多标签情绪识别实验报告
date: 2026-08-16
project: Research and Implementation of Emotion Recognition System of Forum Text Based on LLM
report_type: stack-overflow-c0-main-experiment
evidence_cutoff: EXP-057
status: Verified evidence synthesis
---

# Stack Overflow C0 六标签多标签情绪识别实验报告

## 报告边界

本报告只汇总 Stack Overflow Emotion Gold Standard 上的 C0 target-only 六标签主实验，
覆盖 `DATA-SO-TASK-V1` 与 EXP-050 至 EXP-057。TweetEval、GoEmotions、IAC 2.0、Weibo、
上下文恢复、学习型路由和内部表征分析不纳入本报告。

报告中的定量结果均来自已冻结并通过独立验证的公开聚合产物。EXP-057 只读取这些聚合
结果，没有重新训练、推理、选择阈值、读取私有逐行预测或重新打开 sealed test labels。
独立 verifier 通过 `748/748` 项检查，确认 analyzer 未导入 verifier、未打开私有预测，
也未重新打开测试标签源。

本文使用以下证据状态：

- `Verified`：保存的配置、预测或聚合产物已由独立 verifier 复算。
- `Failed`：运行触发预先定义的失败条件，原记录保留，但不支持性能结论。
- `Consumed`：一次性测试集已经按冻结合同使用，之后不得参与调参或模型选择。

## 技术摘要

本实验在同一份 4,800 条 Stack Overflow 文本、同一套六标签本体、同一组
duplicate-component-disjoint split 和三个随机种子上比较四种方法：RoBERTa encoder、
冻结 Qwen3-4B 加线性头、Qwen3-4B Classification LoRA，以及 Qwen3-4B Generative
LoRA。正式 held-out test 的主结果如下：

1. M3 Classification LoRA 的六标签 Macro-F1 点估计最高，为
   `0.613804 +/- 0.025733`。它相对 M2 Frozen Qwen + linear head 的差值为
   `+0.318578`，95% duplicate-component bootstrap CI 为
   `[+0.254425,+0.369327]`。这支持监督 LoRA 任务适配带来实质收益。
2. M3 相对 M1 RoBERTa 的六标签差值为 `+0.046345`，但 CI
   `[-0.008674,+0.089730]` 跨 0。排除只有 7 个 test positives 的 `surprise` 后，
   五标签差值变为 `-0.010735`，CI `[-0.046061,+0.024305]`。现有证据不能证明 M3
   全面超过强 encoder。
3. M4 Generative LoRA 的六标签 Macro-F1 为 `0.547823 +/- 0.015312`，相对 M3
   低 `-0.065981`，CI `[-0.107869,-0.011312]`。M4 的 strict subset accuracy 最高，
   为 `0.771296 +/- 0.006415`，但该次指标不能替代预注册主指标。
4. M2 的 Macro-F1 为 `0.295226 +/- 0.020587`，明显低于 M1 与 M3。该结果只说明
   final-layer、last-input-token、linear-head 这一冻结表示读取方案较弱，不能推出 Qwen
   不含情绪信息。
5. 当前实验建立的是行为性能、错误结构和资源证据。它没有检验 hidden-state 因果机制，
   也不能外推为人类情绪产生机制。

## 1. 研究问题与实验目标

本实验回答 `RQ-S1`：

> 在固定 Stack Overflow 六标签多标签任务上，Encoder、Frozen Qwen linear probe、
> Qwen Classification LoRA 与 Qwen Generative LoRA 的性能、稳定性和成本有何差异？

实验把问题拆成三个可检验比较：

1. **M2 对 M1：** 冻结 Qwen 的最后层表示加线性分类头，能否达到监督微调 encoder 的
   表现？
2. **M3 对 M2：** 保持 Qwen backbone、分类接口、pooling、head 和训练预算尽量一致时，
   LoRA 任务适配是否提高多标签情绪识别？
3. **M4 对 M3：** 使用相同 Qwen、LoRA 容量和数据时，生成标签集合的端到端方案与分类头
   方案有何表现差异？

第三个比较是 formulation comparison。M3 与 M4 同时改变了 head、loss、监督 token、
解码和 parser，因此结果不能单独归因于“generation”这一项。

## 2. 数据协议

### 2.1 来源与许可边界

- 上游仓库：<https://github.com/collab-uniba/EmotionDatasetMSR18>
- 固定 revision：`d6a679f39a198fdb0657a6116d35dd7b92496898`
- 固定 XLSX SHA-256：
  `29f667701227fc3f1ffc005c5d5364c30f24476005baac23fff8338dbd2f0179`
- 对应论文：Novielli, Calefato and Lanubile (2018), *A Gold Standard for Emotion
  Annotation in Stack Overflow*, DOI `10.1145/3196398.3196453`

上游仓库要求研究使用时引用论文，但仓库没有标准化 `LICENSE` 文件。Stack Overflow
原文还可能涉及平台内容许可和署名义务。实验采用保守边界：原始工作簿、逐行文本、逐行
标签、标注者票和测试标签只保存在 Git-ignored 私有目录；公开仓库只保留代码、协议、
聚合统计、哈希和匿名 split ID。该处理降低公开泄漏风险，但不构成法律意见，也没有解决
上游许可未标准化的问题。

### 2.2 标签重建

任务包含六个独立标签，顺序固定为：

```text
love, joy, surprise, anger, sadness, fear
```

每个标签由三位标注者判断，两票及以上记为正例。六维均为 0 时派生 `neutral=true`，
但模型仍输出六个独立 sigmoid，不把 neutral 作为第七个 softmax 类别。

| 标签 | 全量正例数 |
| --- | ---: |
| love | 1,220 |
| joy | 491 |
| surprise | 45 |
| anger | 882 |
| sadness | 230 |
| fear | 106 |

全量 4,800 条样本中，1,959 条为零标签，2,708 条为单标签，133 条为双标签，没有三标签
及以上样本。原论文正文曾把 `1,959/2,841` 描述为 emotion/neutral，与固定工作簿逐行
重建结果冲突。本实验以工作簿和多数票复算为准，并公开保留该来源差异。

### 2.3 重复项、冲突项与划分

实验用 exact-text equality 与 NFKC、casefold、空白压缩后的 normalized-text equality
建立重复边，再取 connected components。组件不可跨 split。审计结果为：

- exact unique text：4,687；normalized unique text：4,681；
- 99 个重复组件覆盖 218 行，最大组件含 10 行；
- 26 个重复组件、52 行具有互相冲突的六维 gold；
- 冲突项不删除、不合并，完整保留在同一 split。

冻结划分如下：

| Split | 行数 | Duplicate components | `surprise` positives |
| --- | ---: | ---: | ---: |
| Train | 3,360 | 3,277 | 31 |
| Validation | 720 | 702 | 7 |
| Test | 720 | 702 | 7 |

没有 exact 或 normalized duplicate component 跨 split。数据构建 verifier 通过
`53/53` 项检查，synthetic unit tests 通过 `11/11`。

工作簿没有经过核验的 Stack Overflow post/thread ID，因此该划分只能称为
`duplicate-component-disjoint, multi-label-stratified split`。它不是 thread-disjoint，
也不能支持上下文收益结论。本报告统一把任务写为 **C0 target-only**。

## 3. 模型与训练合同

| Family | 实现 | 训练参数 | 输入与输出 |
| --- | --- | ---: | --- |
| M1 | `FacebookAI/roberta-base` 全模型监督微调 | 约 125M 全部可训练 | 最大长度 256；六 logits；unweighted BCE |
| M2 | 冻结 `Qwen/Qwen3-4B` + `Linear(2560,6)` | 15,366 | 最大长度 384；最后层 final norm 后取最后一个非 padding 输入 token；六 logits |
| M3 | Qwen3-4B Classification LoRA + 同结构 linear head | 7,355,398 | 与 M2 相同 prompt、pooling 和分类接口；六 logits |
| M4 | Qwen3-4B Generative LoRA | 与 M3 匹配 LoRA 容量 | 生成严格 JSON 标签集合；无 rationale 或 CoT |

四组模型均使用 seeds `42/43/44`。Qwen 使用固定 revision
`1cfa9a7208912126459214e8b04321603b3df60c`、BF16、非量化 MLX 路线，并关闭
thinking mode。

### 3.1 M1 RoBERTa

- 5 epochs，batch size 16；
- AdamW，learning rate `2e-5`，weight decay `0.01`；
- 10% warmup 后线性衰减；
- checkpoint 按 validation 固定阈值 `0.5` 的 Macro-F1 选择；
- 实际并列差值小于 `0.005` 时选更早 epoch；
- checkpoint 冻结后再从 validation 选择一个全标签共享阈值，不做 per-label threshold。

### 3.2 M2 Frozen Qwen + linear head

- Qwen backbone 全部冻结；
- final-layer last-input-token 表示输入带 bias 的 `Linear(2560,6)`；
- 2 epochs，batch size 1，共 6,720 optimizer steps；
- head AdamW，learning rate `1e-4`，weight decay `0.01`；
- seed 42 提取并冻结 hidden-state cache，seeds 43/44 只训练 fresh linear heads；
- 三个 seed 的 head 初始化与 M3 一一匹配。

M2 只检验当前读取位置上的线性可解码性。它没有测试 layer pooling、token pooling、
非线性 probe 或 end-to-end 适配。

### 3.3 M3 Classification LoRA

- 在 transformer blocks 20 至 35 的 `q/k/v/o` 与 `gate/up/down` projections 插入 LoRA，
  共 112 个 insertion points；
- rank 8，scale 20，dropout 0；A 随机初始化，B 零初始化；
- Qwen base weights 冻结，LoRA learning rate `1e-5`；
- linear head learning rate `1e-4`，weight decay `0.01`；
- 2 epochs、6,720 steps、gradient checkpointing；
- 数据顺序、head 初始化、prompt、pooling、loss 和预算与同 seed M2 匹配。

因此，M3 与 M2 的差值可以解释为当前 classification interface 下的 LoRA 任务适配收益，
但不能推广到所有 Qwen 表征读取方法。

### 3.4 M4 Generative LoRA

- 使用与 M3 相同的 Qwen revision、LoRA 插入位置、rank、scale、seed 和训练行；
- 训练目标为 assistant JSON token 的 next-token cross-entropy；
- 标准输出为 `{"emotions":["love","anger"]}`，标签顺序固定；空数组表示 neutral；
- greedy singleton decoding，temperature 0，最多 48 个新 token；
- strict parser，无 retry、repair 或宽松映射；invalid output 按全零预测计入分母；
- 不生成或监督 rationale/Chain-of-Thought。

全部 validation 和 test 输出均可由 strict parser 解析，parser-valid rate 为 100%。

## 4. 评估与测试纪律

预注册主指标为六标签 Macro-F1。辅助指标包括：

- 排除低支持 `surprise` 的五标签 Macro-F1；
- Micro-F1、Weighted-F1；
- strict subset accuracy，即六维标签集合完全一致率；
- Hamming loss；
- 每标签 precision、recall、F1 和 support；
- 空预测率、预测 cardinality、M4 parser validity 与资源。

三 seed family 报告算术均值和 sample standard deviation，`ddof=1`。正式 test 比较使用
2,000 次 duplicate-component bootstrap，单位为 702 个测试组件。差值方向统一为表中
第二个模型减第一个模型。

EXP-056 在读取 test 前冻结了 12 个单元的 checkpoint、adapter、head、阈值、parser、
指标和比较方式。执行顺序固定为：

```text
initialize
-> predict M1/M2/M3/M4
-> hash-seal all predictions
-> open labels once
-> score
```

TEST-READY verifier 通过 `89/89`；评分后 verifier 通过 `29/29`。测试集现已
`Frozen / Verified / Consumed`，之后禁止利用它修改阈值、prompt、parser、checkpoint、
seed 或候选模型。

## 5. Validation 结果

下表使用每个 seed 已冻结的共享阈值；M4 使用严格生成输出。

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Subset accuracy |
| --- | ---: | ---: | ---: | ---: |
| M1 RoBERTa encoder | 0.617254 +/- 0.011084 | 0.740705 +/- 0.013301 | 0.771139 +/- 0.005645 | 0.760648 +/- 0.021621 |
| M2 Frozen Qwen + linear head | 0.318889 +/- 0.038085 | 0.382667 +/- 0.045702 | 0.514069 +/- 0.022042 | 0.490741 +/- 0.028678 |
| M3 Qwen Classification LoRA | **0.654032 +/- 0.014135** | 0.706724 +/- 0.013816 | 0.759575 +/- 0.003674 | 0.750463 +/- 0.007649 |
| M4 Qwen Generative LoRA | 0.615182 +/- 0.037632 | 0.701182 +/- 0.026073 | 0.755144 +/- 0.009373 | **0.776389 +/- 0.013679** |

Validation 上，M3 的六标签 Macro-F1 比 M2 高 `+0.335143 +/- 0.041168`，三个 seed
均为正。M3 比 M1 高 `+0.036778 +/- 0.003154`，但去除 `surprise` 后比 M1 低
`-0.033981 +/- 0.008620`，Micro-F1、Weighted-F1、subset accuracy 和 Hamming loss
也没有超过 M1。M3 的表面主指标优势高度依赖只有 7 个 validation positives 的
`surprise`。

M4 比同 seed M3 低 `-0.038850 +/- 0.030200` Macro-F1，3/3 seed 为负；它的 subset
accuracy 则高 `+0.025926 +/- 0.017859`。生成式方案更常得到完全正确的六维集合，但对各类
别的平衡召回较弱。

## 6. Validation 错误分析

EXP-055 在读取逐行 validation 预测和原文前冻结抽样与分析规则。主要结果如下：

- M1 三 seed 中每个 seed 独有的 exact-correct 样本为 42、53、73 条；M3 对应为
  53、50、43 条。
- M1 有 497 条跨三 seed 稳定 exact-correct 样本，M3 有 468 条；seed 不稳定样本分别为
  95 与 139 条。
- 一个不可部署的 whole-vector oracle 平均只在 `8.33% +/- 0.77%` 的样本上选择 M3，
  就能相对 M1 获得 `+0.136394 +/- 0.009058` 六标签 Macro-F1 上界。五标签上界为
  `+0.074784 +/- 0.010869`。

该 oracle 使用真实 gold 选择整条预测，只能量化互补错误上限。它通过了预冻结的 router
headroom gate，但没有证明只用 pre-Qwen features 的学习型路由可以达到该上限。本实验没有
训练或测试 deployable router。

人工复核 45 条目的性案例时，primary code 分布为：ontology overlap 19、
model/representation limitation 13、annotation/data uncertainty 9、surface form 2、
missing context 1、low support 1。可并列出现的主要 flags 为：

- ontology overlap：24；weak emotion/neutral boundary：21；implicit emotion：20；
- lexical cue conflict：14；mixed emotion：12；surface form：10；
- annotation ambiguity：9；multi-label underprediction：9；
- low-support surprise：7；possible missing context：5；sarcasm：5；negation：2。

这些案例来自预先冻结的目的性抽样，只用于解释错误类型，不能当作总体发生率。复核者只有
一人，因此定性代码也不构成标注者一致性证据。

## 7. Held-Out Test 主结果

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Weighted-F1 | Subset accuracy | Hamming loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M1 RoBERTa encoder | 0.567459 +/- 0.007814 | **0.680951 +/- 0.009377** | 0.748947 +/- 0.001954 | 0.743941 +/- 0.006278 | 0.750000 +/- 0.017067 | 0.054244 +/- 0.002550 |
| M2 Frozen Qwen + linear head | 0.295226 +/- 0.020587 | 0.354271 +/- 0.024704 | 0.508591 +/- 0.015366 | 0.474565 +/- 0.045017 | 0.502778 +/- 0.046915 | 0.126080 +/- 0.009260 |
| M3 Qwen Classification LoRA | **0.613804 +/- 0.025733** | 0.670216 +/- 0.012032 | **0.753741 +/- 0.003607** | **0.750265 +/- 0.003552** | 0.757407 +/- 0.007127 | **0.051620 +/- 0.001225** |
| M4 Qwen Generative LoRA | 0.547823 +/- 0.015312 | 0.657388 +/- 0.018374 | 0.746167 +/- 0.005484 | 0.734989 +/- 0.009252 | **0.771296 +/- 0.006415** | 0.052778 +/- 0.000835 |

表中粗体仅标示各列最高点估计，不代表差异通过统计检验。M3 的主指标点估计最高，M1 的
五标签 Macro-F1 最高，M4 的 exact-set subset accuracy 最高。模型排序随评价目标变化，
不能只报一项指标后声称某个方法全面最佳。

### 7.1 预注册配对比较

| Contrast | Macro-F1 delta | 95% CI | Five-label delta | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| M2 - M1 | -0.272233 | [-0.310672, -0.227897] | -0.326680 | [-0.372806, -0.273476] |
| M3 - M1 | +0.046345 | [-0.008674, +0.089730] | -0.010735 | [-0.046061, +0.024305] |
| M3 - M2 | +0.318578 | [+0.254425, +0.369327] | +0.315945 | [+0.265264, +0.360323] |
| M4 - M1 | -0.019636 | [-0.058325, +0.017981] | -0.023563 | [-0.069990, +0.021578] |
| M4 - M3 | -0.065981 | [-0.107869, -0.011312] | -0.012828 | [-0.045475, +0.018074] |

由这些区间可以得到三条正式结论：

1. **M3 明确超过 M2。** 六标签和五标签区间都完全高于 0，说明 LoRA 的收益不只来自
   `surprise`。
2. **M3 与 M1 的总体优劣未确定。** 六标签点估计偏向 M3，五标签点估计偏向 M1，
   两个区间都跨 0。
3. **M4 在六标签主指标上低于 M3。** 五标签区间跨 0，因此证据只支持主指标结论；
   它也不能证明 generation 本身造成差异。

### 7.2 每标签结果

| Label (test support) | M1 | M2 | M3 | M4 |
| --- | ---: | ---: | ---: | ---: |
| love (183) | 0.833069 +/- 0.006778 | 0.623725 +/- 0.059913 | 0.841502 +/- 0.006842 | **0.848050 +/- 0.007714** |
| joy (74) | 0.602446 +/- 0.036392 | 0.193660 +/- 0.170914 | **0.622421 +/- 0.023874** | 0.542468 +/- 0.065150 |
| surprise (7) | 0.000000 +/- 0.000000 | 0.000000 +/- 0.000000 | **0.331746 +/- 0.143675** | 0.000000 +/- 0.000000 |
| anger (132) | **0.789238 +/- 0.012357** | 0.530876 +/- 0.013898 | 0.783076 +/- 0.003858 | 0.781405 +/- 0.005130 |
| sadness (35) | **0.655246 +/- 0.037096** | 0.358578 +/- 0.004383 | 0.629518 +/- 0.030685 | 0.643076 +/- 0.034937 |
| fear (16) | **0.524756 +/- 0.030015** | 0.064516 +/- 0.111745 | 0.474561 +/- 0.075004 | 0.471942 +/- 0.090852 |

M3 是唯一在 `surprise` 上得到非零平均 F1 的模型，这也抬高了六标签 Macro-F1。该类只有
7 个 test positives，标准差达到 `0.143675`，不能写成少数类问题已经解决。排除它后，
M1 与 M3 的差距接近 0，且 M1 在 anger、sadness、fear 的点估计更高。

M2 除 love 和 anger 外表现都很弱，joy 的 seed 波动尤其大。冻结表示加单层线性头没有
形成稳定的六标签决策边界，但该结果没有覆盖其他层、其他 token 或非线性读取方案。

### 7.3 Validation 到 test 的变化

| Family | Six-label Macro-F1 change | Five-label Macro-F1 change |
| --- | ---: | ---: |
| M1 | -0.049795 | -0.059754 |
| M2 | -0.023663 | -0.028396 |
| M3 | -0.040228 | -0.036508 |
| M4 | -0.067359 | -0.043793 |

四个 family 的 test 点估计都低于 validation。该表是冻结结果之间的描述性差值，没有为
“下降原因”做统计检验，也不能用 test 下降反向选择模型。M4 的六标签下降最大，M3 的
主指标排序仍保持第一，但其跨 seed 标准差从 validation 的 `0.014135` 增至 test 的
`0.025733`。

## 8. 资源与工程表现

正式 test 的已记录资源如下：

| Family | Backend | Test wall time | Peak memory | 补充说明 |
| --- | --- | ---: | ---: | --- |
| M1 | PyTorch CPU | 23.432 s/seed | 未记录 | 每 seed 独立推理 |
| M2 | MLX Apple Metal | 467.440 s shared extraction + 0.128 s/head | 8.225 GB | 三个 head 共享冻结 Qwen features |
| M3 | MLX Apple Metal | 610.664 s/seed | 8.593 GB | 每 seed 独立加载 adapter 与推理 |
| M4 | MLX Apple Metal | 1,188.417 s/seed | 8.595 GB | greedy generation；parser-valid 100% |

M3 三次正式训练分别耗时约 3.821、3.544 和 3.352 小时，峰值均约 8.70 GB。M4 的
三 seed train + validation 平均 wall time 约 3.553 小时。全部本地运行 API cost 为 0，
正式推理没有发生截断。

这些路径不能组成严格的速度排行榜。M1 使用 CPU，M2 共享 feature cache，M3/M4 使用
Metal 且执行接口不同。可以确认的是：M4 生成式 test 推理在当前实现中约为 M3 分类式
推理的 1.95 倍，同时没有取得更高主指标。

## 9. 过程中出现的问题与处理

### 9.1 数据分配器的结构偏置

第一次临时数据 preflight 的 greedy allocator 把 26 个 conflicting-duplicate components
全部放进 validation。模型从未读取该输出。正式构建前，协议把 component、duplicate 和
conflict slices 加入结构配额，并只允许同结构桶内 deterministic pair swaps。最终 split
通过全部冻结平衡门。

这次问题说明，只做标签分层无法保证重复冲突组件的合理分布。修正发生在正式数据生成和
模型实验之前，没有形成结果后调 split。

### 9.2 共享 preflight 的哈希范围错误

EXP-050 第一次 preflight 因 digest scope 不一致失败，发生在 LoRA 插入和 optimizer 执行
之前。修正哈希合同后完整重跑，五个 stage 与独立 verifier 通过 `77/77`。模型定义和
科学配置没有改变。

### 9.3 M1 的 MPS OOM 与 CPU recovery

M1 seed 42 首次 MPS 运行在 epoch 1、完整 validation 前 OOM。失败记录保留，随后使用
相同科学配置从头在 CPU 训练。CPU recovery 通过独立 checkpoint replay。CPU 与 MPS 不被
声明为 bitwise equivalent；正式三 seed M1 结果来自可验证的 CPU 路线。

### 9.4 M2 的 cache consumer 接口错误

M2 seed 43 首次 consumer preflight 因 schema mismatch 在训练前停止。修正只涉及 cache
consumer 的接口读取，随后 preflight 和正式 verifier 分别通过。seed 42 的 feature cache
经过独立只读复用 gate，seeds 43/44 没有重新运行 Qwen forward。

### 9.5 M3 资源计量与 verifier schema

M3 资源 preflight attempt 1 把仍被旧对象引用的模型内存计入第二次加载，触发虚假的
process-wide peak failure。attempt 2 只修正对象生命周期和阶段内存计量，原 13 GB 与
8 h/seed 资源门保持不变。

M3 seed 42 第一次 verifier 完整 replay 后通过 `135/136`，唯一失败来自旧资源字段名；
checkpoint probability max error 为 0。schema amendment 后重新完整 replay，通过
`148/148`。原失败目录未覆盖，也没有修改训练结果。

### 9.6 M4 preflight 的对象生命周期 OOM

M4 首次 preflight 在第二个模型仍持有第一份初始化对象时触发 Metal OOM。该尝试没有读取
validation 或 test。修正对象释放后在新目录从头运行，preflight 通过 `26/26`，三个正式
seed 各通过 `92/92`，aggregate 通过 `33/33`。

### 9.7 正式 test 的受限 Metal 环境

EXP-056 第一次在 restricted sandbox 启动 M2 时无法看到 Metal device，在任何推理、预测
写入和标签访问前停止。随后使用同一冻结命令在获批的 native Metal 环境从头执行。四组
预测全部先 hash-sealed，再一次性打开标签评分。

### 9.8 EXP-057 汇总器的字段差异

EXP-057 attempt 1 的 analyzer 已完成输出，但 verifier 因 M1 至 M3 使用
`empty_prediction_rows`、M4 使用 `empty_prediction_rate` 而抛出 `KeyError`。该尝试没有
读取私有预测或测试标签。attempt 2 预先登记转换规则，以
`empty_prediction_rows / 720` 计算 M1 至 M3 的 rate。随后 unit tests 通过 `11/11`，
独立 verifier 通过 `748/748`。

这些失败主要来自资源、接口和验证 schema，没有一项被删除或伪装成科学结果。恢复运行
均保持数据、模型、seed、阈值和评价合同不变。

## 10. 结论与证据强度

### 10.1 可以写入论文的结论

| 结论 | 证据强度 | 结论类型 | 边界 |
| --- | --- | --- | --- |
| Classification LoRA 明显优于 matched Frozen Qwen + linear head | 强证据 | 实验结论 | 六标签和五标签 test bootstrap CI 均高于 0；只适用于当前 Qwen、pooling、head 和数据 |
| M3 与 RoBERTa 在当前任务上具有竞争性，但没有建立全面优势 | 强证据 | 实验结论 | M3-M1 两个主敏感性 CI 均跨 0；不同指标排序不同 |
| M4 在六标签 Macro-F1 上低于 M3 | 强证据 | 实验结论 | M4-M3 主指标 CI 完全低于 0；五标签 CI 跨 0 |
| Frozen final-layer last-token linear probe 表现较弱 | 强证据 | 实验结论 | 不代表 Qwen 没有情绪信息，也不覆盖其他 probe 设计 |
| `surprise` 低支持会显著影响六标签 Macro-F1 解释 | 强证据 | 数据与敏感性结论 | Validation/test 各只有 7 个正例，必须同时报告五标签结果 |
| M1 与 M3 存在互补错误上限 | 初步证据 | 诊断结论 | whole-vector oracle 不可部署；学习型 router 尚未实验 |

### 10.2 不能由本实验支持的说法

- “LLM 已全面超过 BERT/RoBERTa。”
- “生成式情绪识别一定优于分类头。”
- “M2 证明 Qwen 内部没有情绪表征。”
- “M3 与 M4 的差异由 generation 单独造成。”
- “模型找到了人类产生情绪的机制。”
- “当前结果证明上下文无用或有用。”
- “oracle router 的收益可以在部署中实现。”
- “测试集还能继续用于选阈值、选 seed 或改 prompt。”

## 11. 研究限制

1. **任务是 target-only。** 缺少经过核验的 thread/post ID，当前实验没有真实 parent 或
   thread context。
2. **低支持标签影响主指标。** `surprise` 全量只有 45 个正例，validation/test 各 7 个。
3. **数据存在不可约冲突。** 26 个 normalized duplicate components 含冲突 gold，说明
   相同文本在来源中可能得到不同监督信号。
4. **许可没有标准化。** 数据可用于当前私有研究流程，但公开再发布仍需单独处理来源许可、
   署名和平台条款。
5. **M2 读取方案较窄。** 只使用最后层最后输入 token 和线性头，不能代表全部 hidden-state
   可解码性。
6. **M3 与 M4 不是单变量消融。** 两者在 objective、head、监督 token、decode 和 parser
   上共同变化。
7. **定性错误分析只有一位复核者。** 45 条目的性样本支持错误解释，不支持总体比例或
   标注一致性结论。
8. **资源路径不统一。** CPU、shared cache 和 Metal per-seed 路线不能做严格硬件效率比较。
9. **没有表征或因果实验。** 现有结果停留在行为层，不能支持 SAE、activation feature 或
   人类情绪机制主张。

## 12. 对毕设主线的含义

这组实验已经形成一个完整、可写入论文的行为比较闭环：

```text
固定论坛 gold 与泄漏控制
-> 强 encoder baseline
-> frozen LLM representation baseline
-> classification LoRA adaptation
-> generative LoRA formulation
-> 三 seed validation
-> 冻结错误分析
-> 一次性 held-out test
-> 只读结果汇总与独立验证
```

若论文以六标签 Macro-F1 为主指标，M3 可以作为 LLM 主模型，因为它取得最高点估计，并
明确超过 matched M2。论文仍应把 M1 作为强且高效的实际基线，避免把 M3 对 M1 的未确定
差异写成胜出。M4 证明生成式标签接口可以稳定运行，但当前没有带来主指标收益，推理时间也
更长。

因此，最稳妥的论文表述是：

> 在 Stack Overflow 六标签多标签情绪识别中，监督 LoRA 使 Qwen3-4B 从弱线性可解码
> 基线提升到与 RoBERTa 具有竞争性的水平；现有 held-out 证据没有证明 LLM 全面优于
> encoder，生成式标签输出也没有超过 classification LoRA。低支持标签、标签本体重叠和
> 隐式情绪仍是主要限制。

## 13. 可复现性入口

- 数据协议：
  [`experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md`](experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md)
- 四组模型协议：
  [`EXP-051`](experiments/stack-overflow-emotion-gold/protocols/exp-051-m1-roberta.md)、
  [`EXP-052`](experiments/stack-overflow-emotion-gold/protocols/exp-052-m2-frozen-qwen-linear-head.md)、
  [`EXP-053`](experiments/stack-overflow-emotion-gold/protocols/exp-053-m3-qwen-classification-lora.md)、
  [`EXP-054`](experiments/stack-overflow-emotion-gold/protocols/exp-054-m4-qwen-generative-lora.md)
- Validation 错误分析：
  [`EXP-055 REPORT`](experiments/stack-overflow-emotion-gold/error-analysis/runs/exp-055-m1-m3-validation-error-analysis/REPORT.md)
- 一次性 test 合同与结果：
  [`EXP-056 protocol`](experiments/stack-overflow-emotion-gold/test-gate/protocols/exp-056-unified-frozen-test-gate.md)、
  [`EXP-056 REPORT`](experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/REPORT.md)、
  [`verification.json`](experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/verification.json)
- 只读汇总与论文表格：
  [`EXP-057 protocol`](experiments/stack-overflow-emotion-gold/protocols/exp-057-read-only-result-synthesis.md)、
  [`THESIS-TABLES.md`](experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/THESIS-TABLES.md)、
  [`VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/VERIFICATION-SUMMARY.md)

所有面向论文、CV、SOP 或推荐信的数字都应从上述 Verified 产物引用。测试集已经消费，
后续工作只能使用新的数据或预登记的既有预测只读分析，不能修改本报告中的冻结比较。
