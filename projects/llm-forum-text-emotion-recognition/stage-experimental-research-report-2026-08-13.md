---
title: 论坛文本情绪识别阶段性实验研究报告
date: 2026-08-13
project: Research and Implementation of Emotion Recognition System of Forum Text Based on LLM
report_type: stage-experimental-research-report
evidence_cutoff: EXP-048 / EVID-043
status: evidence-bounded snapshot
---

# 论坛文本情绪识别阶段性实验研究报告

## 报告边界

本报告汇总截至 2026-08-13 已完成并留有可核验产物的实验工作，覆盖 TweetEval
emotion、GoEmotions、IAC 2.0 论坛数据诊断和 Weibo EClass 当前主任务。正在进行的
Weibo 正式 test 评估不纳入本报告，也不使用其任何中间预测或未验证结果。

不同数据集的任务定义不同：TweetEval 是四分类单标签任务，GoEmotions 是 28 标签
多标签任务，Weibo EClass 是七分类单标签任务。因此，本文只在同一数据集、同一 split
和同一评价协议内比较模型，不直接比较三个数据集的 Macro-F1 数值。

证据状态沿用项目规范：`Verified` 表示结果可由保存的预测、配置和独立验证器复算；
`Completed` 表示运行完成但证据强度不足以作为最终冻结结论；`Failed` 表示触发预登记
失败门，即使产物完整也不得用于支持正式结论。

## 技术摘要

项目已形成从传统文本分类器、监督编码器到本地生成式大模型和 LoRA 的完整行为层证据链，
并建立了数据清洗、分组划分、test gate、独立复算、错误分析和隐私保护流程。当前最稳定的
结论不是“LLM 已超过 BERT”，而是以下五点：

1. **监督编码器目前仍是三个已完成比较任务中的最强或更强方法。** TweetEval 正式 test
   上，Twitter-domain RoBERTa 的 Macro-F1 为 `0.809973 +/- 0.007038`；GoEmotions
   正式 test 上，BERT-base-cased 为 `0.488328 +/- 0.008771`，高于两种 Qwen LoRA
   条件；Weibo validation 上，中文 encoder 为 `0.594925 +/- 0.012919`，仍高于
   Qwen3-4B LoRA 的 `0.562471 +/- 0.021408`。
2. **LoRA 对生成式 LLM 的任务适配是有效的，但尚未建立超越 encoder 的证据。**
   GoEmotions dev 上，Qwen3-1.7B LoRA 相对冻结 few-shot 条件提高约 `0.210` Macro-F1；
   Weibo validation 上，Qwen3-4B LoRA 相对 matched no-adapter reference 提高
   `0.228873`。两个任务中，LoRA 最终仍低于监督 encoder。
3. **上下文并非自动带来收益。** Weibo 的固定局部前文在中文 encoder 中与 target-only
   实际并列，在冻结 Qwen 2x2 中平均 context contrast 为 `-0.021512`，95% CI 排除 0。
   该证据只适用于相邻局部前文，不等于完整 thread context 或真实 reply parent。
4. **生成格式问题会影响 LLM 评价，但不是性能差距的唯一来源。** Weibo LoRA 将 parser-valid
   从 `90.88%` 提高到 `100%`；然而在 reference 本来就能有效解析的 1,156 条样本上，
   Accuracy 仍从 `0.245` 提高到 `0.780`。因此，收益同时包含输出可用性恢复和标签行为改善。
5. **标签体系和标注聚合是主要研究困难。** IAC 2.0 pilot 暴露了 stance 与 emotion 的任务
   错位；GoEmotions 中 `neutral+emotion` 的异常共现来自跨标注者投票聚合，而非同一标注者
   直接共选；Weibo 则混合具体情绪、正负极性、`neutral` 和 `no_emotion`。这些问题会改变
   评价语义和模型上限，不能全部归因于模型能力。

当前工作只建立了行为表现、错误结构和数据诊断证据。hidden-state probe、SAE 或人类情绪
机制尚未形成可接受结论；EXP-028 因超过冻结资源门被判为 `Failed`，其诊断数值不得作为
正式表征证据。

## 1. 数据集与方法概览

### 1.1 数据集

| 数据集或分支 | 任务与规模 | 当前用途 | 主要边界 |
| --- | --- | --- | --- |
| TweetEval emotion | 英文 Tweet 四分类单标签；train 3,257、validation 374、test 1,421；标签为 anger、joy、optimism、sadness | 验证传统分类器、通用/领域 encoder、正式 test gate 和错误分析流程 | 短文本社交媒体任务，不代表论坛 thread |
| GoEmotions | 英文 Reddit comment，28 标签多标签；train 43,410、dev 5,426、test 5,427 | 比较简单多标签基线、BERT、Qwen zero/few-shot、LoRA、标注分歧和正式 test | 当前官方发布基本是 target-only；不能直接恢复绝大多数 parent text |
| IAC 2.0 `4forums` | 414,453 帖；构建 403,374 个 parent-target 候选，去重后保留 403,183 | 论坛清洗、去重、采样和三来源标注 pilot；现作为 challenge/data-failure 分支 | 辩论话题集中，stance 比 emotion 更显著；没有现成情绪 gold |
| Weibo EClass | 11,075 个原始 EClass rows，经协议保留 8,540；train/dev/sealed-test 为 5,995/1,272/1,273 | 当前中文主任务；七分类、target-only 与局部前文 paired views | 微博多用户 clause 不是标准论坛；`PrevCL` 不是已验证 parent |

Weibo 的七个冻结标签为 `joy`、`sadness`、`anger`、`positive`、`negative`、
`neutral` 和 `no_emotion`。其中 `no_emotion` 占 5,929/8,540，类别极不平衡；
Accuracy 因而只作为辅助指标，主指标始终为 Macro-F1。

### 1.2 方法

所用方法可以简化为四组：

- **传统分类器：** word/character TF-IDF + Logistic Regression 或 Linear SVM。
- **监督 encoder：** RoBERTa-base、Twitter-domain RoBERTa、BERT-base-cased 和
  Chinese RoBERTa-wwm-ext，使用任务监督微调和分类头。
- **生成式 LLM：** Qwen3-1.7B 与 Qwen3-4B，比较 zero-shot、few-shot、受约束/开放
  decoder、reasoning on/off、target-only/局部前文以及生成式 LoRA。
- **诊断与质量控制：** 多随机种子、paired/group bootstrap、混淆矩阵、逐类指标、
  冻结错误抽样、逐标注者重评分、数据清洗、近似去重、HMAC ID、独立 verifier 和一次性
  test gate。

单标签任务报告 Macro-F1、Accuracy、macro precision/recall、Weighted-F1 和逐类指标；
GoEmotions 另报告 Micro-F1、Samples-F1、subset accuracy、标签 cardinality 和逐标签结果。

## 2. TweetEval：领域 encoder 的收益通过正式 test，label smoothing 未泛化

### 2.1 主要结果

| 条件 | Split | Macro-F1 | Accuracy | 证据状态 |
| --- | --- | ---: | ---: | --- |
| TF-IDF + Logistic Regression | validation | 0.493991 | 0.631016 | Completed |
| Balanced TF-IDF + Logistic Regression | validation | 0.565981 | 0.620321 | Completed |
| Word + character TF-IDF + Linear SVM | validation | 0.611866 | 0.671123 | Completed |
| Train-CV-selected Linear SVM | validation | 0.622678 | 0.676471 | Completed |
| Train-CV-selected Linear SVM | test | 0.646998 | 0.700915 | Verified |
| RoBERTa-base，3 seeds | test | 0.795761 +/- 0.003298 | 0.819845 +/- 0.003225 | Verified |
| RoBERTa-base + label smoothing，3 seeds | test | 0.792645 +/- 0.003658 | 0.820783 +/- 0.004686 | Verified |
| Twitter RoBERTa + label smoothing，3 seeds | test | 0.809973 +/- 0.007038 | 0.840019 +/- 0.008126 | Verified |

类别加权使 Logistic Regression 的 validation Macro-F1 提高 `0.071990`，但 Accuracy
下降 `0.010695`，说明多数类命中率不能代替类别平衡评价。加入 character n-gram 并改用
Linear SVM 后，传统基线继续改善；训练集内 5 折调参又带来 `0.010812` validation
Macro-F1 增益，但训练 Macro-F1 接近 `0.985`，显示稀疏高维模型仍有明显拟合和选择乐观性。

正式 test 中，通用 RoBERTa 相对 Linear SVM 提高 `0.148763` Macro-F1。label smoothing
在 validation 上曾提高 `0.007415`，但 test 配对差值为 `-0.003116`，2/3 seed 为负，
因此该开发集改善没有泛化。将 base encoder 换成 Twitter-domain RoBERTa 后，相对加入
label smoothing 的通用模型提高 `0.017328`，3/3 配对 seed 均提高，支持领域预训练收益。

### 2.2 错误结构

Twitter RoBERTa 的三个 seed 共有 155 条稳定错误和 147 条 seed 不稳定样本；
`optimism` 的稳定错误率为 `26.02%`，是四类中最高。传统基线与全部神经 seed 共同判错
87 条，说明一部分困难来自短文本歧义、类别边界或标注，而不是单一模型架构。领域 encoder
相对通用 encoder 有 21 条稳定恢复，也有 11 条稳定回退，收益并非逐样本单调。

## 3. GoEmotions：LoRA 显著改善 Qwen，但 BERT 仍保持总体优势

### 3.1 正式 test 结果

| 条件 | Macro-F1 | Micro-F1 | Subset accuracy | 证据状态 |
| --- | ---: | ---: | ---: | --- |
| TF-IDF + 28 个 OVR Logistic Regression | 0.196197 | 0.382080 | 0.250046 | Verified |
| Qwen3-1.7B constrained few-shot | 0.233653 | 0.249278 | 0.112032 | Verified |
| Qwen3-1.7B + LoRA，legacy ontology，3 seeds | 0.450652 +/- 0.032175 | 0.579031 +/- 0.005213 | 0.513543 +/- 0.009738 | Verified |
| Qwen3-1.7B + target-aligned LoRA，seed 42 | 0.444675 | 0.580163 | 0.513175 | Verified |
| BERT-base-cased，3 seeds | 0.488328 +/- 0.008771 | 0.590427 +/- 0.001634 | 0.443032 +/- 0.005061 | Verified |

BERT 的 test Macro-F1 比简单 TF-IDF 基线高 `0.292132`，并比 GoEmotions 论文中
full-taxonomy BERT test 参照 `0.46` 高 `0.028328`。这说明当前现代实现已经复现并略高于
论文参考水平，但不能据此声称架构改进，因为训练栈、实现和随机性并非与原论文完全相同。

冻结 Qwen few-shot 只略高于简单 TF-IDF 的 Macro-F1，同时 Micro-F1 和 subset accuracy
更低。监督 LoRA 将 Qwen 的 dev Macro-F1 从冻结选定条件 `0.241164` 提高到
`0.451374 +/- 0.019212`，证明任务适配有效；但正式 test 上 legacy LoRA 仍低于 BERT
`0.037676`，target-aligned seed 42 低 `0.043653`。因此，现有证据支持“LoRA 使 LLM
接近强 encoder”，不支持“LLM 已优于 encoder”。

### 3.2 Decoder、prompt 与多标签偏向

受约束 decoder 在 few-shot 条件中主要恢复 503 个无效输出；在双方都有效的 4,923 条
样本上，标签集合全部一致。zero-shot 中，双方有效的 5,206 条样本只有 `75.8164%`
标签集合完全一致，说明约束 decoder 不能笼统视为 label-neutral，但其 Macro-F1 影响较小
且方向不一致。

对 EXP-029 冻结 adapters 的推理消融显示，只开放 decoder 时 16,278 条 seed-row 预测
完全不变；同时对齐 prompt 和 decoder 后，Macro-F1 只提高 `0.001682`，并伴随 Samples-F1
和 exact match 下降。该结果排除了“只修改 inference prompt 就能修复多标签输出”的简单
解释。

LoRA 在 dev 上的 subset accuracy 高于 BERT，但在真正多标签样本上的 exact match 约为
`0.043`，低于 BERT 的约 `0.179`。LoRA 平均只预测约 `1.034` 个标签，表现出明显的
近单标签偏向。这也是其总体 Accuracy/Exact Match 与 Macro-F1 可能给出不同印象的原因。

### 3.3 标注聚合改变局部评价语义，但不足以解释总体差距

GoEmotions train 中 1,396 条 `neutral+emotion` target 全部由不同标注者投票聚合形成，
同一标注者直接共选该结构的数量为 0。即使使用保留全部官方标签的 target-aligned LoRA，
模型在这 1,396 条训练样本上仍产生 0 条目标共现预测，predicted cardinality 为
`1.019341`，gold 为 `2.044413`。这不是单纯的 held-out 泛化失败，而是训练目标、
token-level 生成、标签顺序、LoRA 容量和聚合语义共同构成的问题。

在 dev 的 174 条同类冲突切片上，Qwen LoRA 与 BERT 的 clear-rater expected set-F1
分别为 `0.363250` 和 `0.362531`，差值 `+0.000720`，95% CI
`[-0.018463, +0.019903]`，属于局部 practical tie。扩大到完整 5,426 条 dev 后，
Qwen/BERT 的 clear-rater soft Macro-F1 为 `0.347253/0.383471`，差值
`-0.036218`，95% CI `[-0.043834, -0.029494]`。相对 official scoring 的差值移动仅
`+0.001843` 且 CI 跨 0，故结论仍为 `gap_remains`：标注聚合影响局部评分语义，但不能
解释总体 encoder 优势。

### 3.4 表征分析尚未完成

EXP-027 只在六条合成文本上验证了 matched hidden-state 提取路径。EXP-028 完成了
Base/post-trained 特征和 probe 产物，但 fitting/evaluation 用时 `344.288` 分钟，超过
冻结的 240 分钟资源门，正式状态为 `Failed`。其诊断 Macro-F1 和差值只能用于检查流程，
不能进入论文结论。当前没有证据说明 Qwen 已形成可解释的情绪机制，更不能外推到人类
情绪产生机制。

## 4. IAC 2.0：上下文拓扑可用，但情绪任务定义不适合作为当前主训练集

### 4.1 数据工程结果

确定性清洗从 414,453 帖中重建 403,374 个直接 parent-target 候选，403,336 条通过
保守 hard filter；539,658 条 quote 完成层级和 offset 核对。去重后保留 403,183 条，
自动去除 139 条精确重复和 14 条纯格式差异；68,552 条 review-only 近邻边形成 249 个簇，
涉及 1,308 条候选，语义相似本身没有触发自动删除。近邻检索 mean recall@64 为
`0.992554`，超过 `0.98` 的冻结门槛。

在 403,183 条候选中，协议确定性抽取 120 条 calibration 主样本和 60 条备用样本；
180 条样本与 thread 全局唯一。120 条主样本随后被导出为私有 staged views，其中 89 条
含 target quote，共 164 个顶层引用块。所有原文、源 ID、HMAC key 和逐样本标签均保持
Git ignored。

### 4.2 三来源标注 pilot

Human、Model 1 和 Model 2 的 Stage B 三方精确一致只有 `21/120`；Human/Model 1 与
Human/Model 2 的一致率分别为 `25.8%` 和 `24.2%`，两个模型之间为 `58.3%`。共有
106 条样本在 Stage A 或 Stage B 至少出现一次分歧。模型更相似并不证明模型更正确，因为
它们共享标签定义、提示结构和相似的模型偏差。

加入上下文后，Human、Model 1 和 Model 2 分别有 `42.5%`、`35.0%` 和 `30.0%` 的标签
发生变化，但变化不总是对情绪消歧：Human 在代表性 80 条中频繁通过 `other_emotion`
填写 `approval` 或 `disapproval`，而这两者主要是立场或态度。Model 1 和 Model 2 对
`frustration`、`anger`、`neutral` 和 `cynicism` 也有明显分歧。可见当前样本常让“支持/反对
什么”比“表达了何种情绪”更突出。

人工观察还发现话题集中在堕胎、枪支等辩论，长引用或多段回复可能同时含有不同局部情绪。
这些观察没有经过正式总体 topic audit，不能外推为 IAC 全体比例，但足以说明它不应直接
进入最终训练标注。

### 4.3 数据选择结论

IAC 2.0 保留为政治辩论、stance-emotion 分离、引用和上下文处理的 challenge set，
不再继续构建主训练集。KOTE 只保留为低优先级 target-only 控制候选；Hotter and Colder
因缺少打包文本、依赖实时 hydration 且存在隐私/schema 风险被排除。Weibo EClass 随后被
采用为当前主任务，但其外部效度必须限定为中文微博多用户局部话语，而不是广义论坛 thread。

## 5. Weibo EClass：LoRA 接近 encoder，但局部上下文没有稳定收益

### 5.1 数据协议

冻结协议从 11,075 条 EClass rows 中保留 8,540 条七分类样本；同 target-label 折叠
2,422 条。划分以 source group 和 duplicate-bound leakage component 为单位，得到
train 5,995、validation 1,272 和 sealed test 1,273。共有 6,138 条样本存在相邻局部前文。

原始标签混合具体情绪、正负极性、`neutral` 和 `no_emotion`。`no_emotion` 占
69.43%，而 `sadness` 只有 136 条，因此主模型选择必须依赖 Macro-F1 和逐类结果，不能
依赖 Accuracy。上游未提供行级标注者信息或一致性指标，这是无法从本地数据修复的限制。

### 5.2 传统方法与中文 encoder validation

| 条件 | 输入 | Macro-F1 | Accuracy | 证据状态 |
| --- | --- | ---: | ---: | --- |
| M0 majority | target-only | 0.116913 | 0.692610 | Verified |
| M1 TF-IDF | target-only | 0.338267 | 0.650943 | Verified |
| M1 TF-IDF | local previous context | 0.271504 | 0.443396 | Verified |
| M2 Chinese encoder，3 seeds | target-only | 0.594925 +/- 0.012919 | 0.792453 +/- 0.003931 | Verified |
| M2 Chinese encoder，3 seeds | local previous context | 0.594219 +/- 0.012046 | 未作为选择依据 | Verified |

M0 的 Accuracy 高达 `0.692610`，但 Macro-F1 只有 `0.116913`，直接证明多数类偏置会
制造虚假的“高准确率”。M1 加入前文后明显下降。M2 的 target/context 配对 Macro-F1
差为 `-0.000706 +/- 0.024737`，按 `0.005` 实际并列规则选择更简单、成本更低的
target-only；当前没有证据支持为 encoder 无条件加入局部前文。

### 5.3 冻结 Qwen context x reasoning 2x2

| 条件 | 输入 | Reasoning | Macro-F1 | Accuracy |
| --- | --- | --- | ---: | ---: |
| A | target-only | off | 0.308684 | 0.230346 |
| B | local previous context | off | 0.281480 | 0.188679 |
| C | target-only | on | 0.333818 | 0.222484 |
| D | local previous context | on | 0.317997 | 0.219340 |

平均 context contrast 为 `-0.021512`，95% CI
`[-0.037515, -0.006905]`；平均 reasoning contrast 为 `+0.030825`，95% CI
`[+0.007225, +0.057146]`；交互项 CI 跨 0。按冻结主指标选择 C，即 target-only +
reasoning-on，但 C 仍比中文 encoder 低 `0.261107` Macro-F1。

该 2x2 不能把 reasoning 输出文本解释为忠实推理过程。后续 runtime-equivalence 实验还发现，
固定顺序 batch 8 可以重放，但改变共同 batch 成员后最终标签只有 `14/16` 一致。因此，
reasoning-on 的正式 matched 比较必须使用 singleton，D-C 也不能完全归因于语义上下文。

### 5.4 Qwen3-4B generative LoRA validation

| 条件 | Macro-F1 | Accuracy | Parser-valid |
| --- | ---: | ---: | ---: |
| Matched no-adapter singleton reference | 0.333598 | 0.222484 | 90.88% |
| LoRA seed 42 | 0.552028 | 0.768082 | 100% |
| LoRA seed 43 | 0.548289 | 0.786164 | 100% |
| LoRA seed 44 | 0.587096 | 0.783805 | 100% |
| LoRA 3-seed mean | 0.562471 +/- 0.021408 | 0.779350 | 100% |
| Chinese encoder 3-seed mean | 0.594925 +/- 0.012919 | 0.792453 | 100% |

LoRA 相对 matched reference 的 Macro-F1 提高 `0.228873`，三个 seed 的 paired
bootstrap 95% CI 均完全高于 0，因此属于明确的任务适配收益。LoRA 与 encoder 的
Accuracy 只差 `-0.013103`，但 Macro-F1 仍差 `-0.032454`；两者在多数类总体命中上接近，
差异主要落在少数类和类别边界。

错误分析显示，LoRA 相对 encoder 最大的逐类 F1 劣势为 sadness `-0.084593`、neutral
`-0.065775`、anger `-0.039949` 和 positive `-0.029494`。常见错误包括
`positive -> no_emotion`、`neutral -> no_emotion`、`no_emotion -> neutral` 和
`negative -> no_emotion`。LoRA 三 seed 两两标签一致率均值为 `0.884`，低于 encoder 的
`0.943`，因此不能只展示表现最好的 seed 44。

在 48 条预冻结目的性案例中，较常见的可能因素包括 sentiment-emotion overlap、长尾类别、
弱情绪与 `no_emotion` 边界、标注歧义和隐含情绪。该样本不是随机总体样本，计数只用于
形成错误类型，不得写成全 validation 的发生率。

### 5.5 资源与工程可复现性

三次 Qwen3-4B LoRA 训练实际合计约 `17.095` 小时，单 seed 峰值约 `8.805 GB`；matched
validation 四条件命令合计约 `24.20` 小时，其中无 adapter reference 占约 `21.97` 小时。
全部运行在本地 MLX/BF16 环境完成，API cost 为 USD 0。

运行中保留了多项失败证据：受限进程不可见 Metal device、错误的 target rendering、
384-token 截断、`BatchEncoding` 初始化错误以及 verifier 自匹配状态缺陷。修复均通过新目录、
correction 或独立 V2 verifier 完成，没有覆盖历史失败产物。这些问题说明本地 LLM 实验的
主要成本不仅是训练，还包括 runtime 等价性、长生成和验证器本身的可信度。

## 6. 跨实验综合结论

### 6.1 LLM 路线可行，但论文贡献不应写成“性能必然更高”

TweetEval、GoEmotions 和 Weibo 的共同结果是：任务监督 encoder 在有限标签分类上仍更
稳定、更高效，并在 Macro-F1 上占优。生成式 LLM 的价值主要体现在统一自然语言接口、
few-shot/zero-shot 能力、可生成解释以及后续表示分析潜力，而不是天然更擅长固定标签分类。

LoRA 在 GoEmotions 和 Weibo 上都带来大幅提升，说明 LLM 路线没有失败；但提升主要证明
任务适配有效，不证明模型形成了与人类相同的情绪识别机理。论文更可信的主张是：
**研究生成式 LLM 在论坛式文本情绪分类中的适配收益、成本、错误结构与上下文边界，并以
监督 encoder 作为强对照。**

### 6.2 Context 的作用依赖于数据结构和任务定义

IAC pilot 中上下文会显著改变部分决策，但经常是因为它揭示了立场、引用对象或局部话语功能；
Weibo 的相邻前文对 encoder 没有稳定收益，对冻结 Qwen 反而产生负平均 contrast。这不等于
“上下文无用”，而是说明相邻句不一定包含与 target 情绪有关的信息，甚至会引入其他说话者、
主题或立场噪声。要主张 context-aware emotion recognition，必须区分 verified parent、
adjacent clause、quoted text 和完整 thread。

### 6.3 评价协议本身是研究对象

Macro-F1、Accuracy、subset accuracy 和 individual-rater agreement 会强调不同误差。
GoEmotions 中 LoRA 的 subset accuracy 可以高于 BERT，同时 Macro-F1 更低；Weibo majority
baseline 的 Accuracy 很高但几乎没有少数类能力。标注聚合还会产生任何单个标注者都未直接
选择的标签组合。最终论文必须同时报告主指标、逐类结果、错误结构和评分语义，不能只选一个
看起来最好的数字。

### 6.4 当前证据停留在行为层

目前可以讨论模型在什么样本上预测正确、上下文是否改变输出、LoRA 是否改变标签行为以及
哪些类别线性分类更困难。还不能说明模型内部存在某个“情绪模块”，不能从 probe 相关性推出
机制，更不能据此解释人类如何产生情绪。若继续 hidden-state、SAE、activation intervention
或 causal tracing，必须使用新的资源可行协议和因果干预证据。

## 7. 当前主要困难

| 困难 | 已有证据 | 对研究的影响 |
| --- | --- | --- |
| 合适的公开论坛情绪数据稀缺 | GoEmotions 缺失绝大多数 parent text；IAC 有 thread 结构但无合适 emotion gold；Weibo 只有局部相邻 clause | 论文的 forum/context 外部效度必须收敛，不能把代理数据写成完整论坛线程 |
| Stance、sentiment 与 emotion 混淆 | IAC 的 approval/disapproval；Weibo 的 positive/negative、neutral/no_emotion | 标签边界重叠会制造系统性分歧，模型错误不全是表征失败 |
| 类别不平衡和长尾 | Weibo `no_emotion` 69.43%；GoEmotions 28 标签频率差异大；TweetEval optimism 最难 | Accuracy 容易虚高，少数类 F1 和多 seed 波动必须保留 |
| 生成式 LLM 倾向输出短、单一标签 | GoEmotions LoRA 平均约 1.034 标签，neutral 共现始终为 0 | 多标签任务中 exact-match 和 Macro-F1 受限，不能只靠 prompt 修复 |
| Parser 与生成策略会改变评价 | constrained/unconstrained decoder、长 thinking 截断、Weibo reference 116 条输出失败 | 需要把格式有效率、截断和无效输出作为正式指标，但不能把全部收益归因于格式 |
| Context 语义不稳定 | IAC 中 context 常揭示 stance；Weibo `PrevCL` 不是 parent，context contrast 非正 | 只能声称 fixed local discourse context，不能泛化为完整对话理解 |
| Batch/runtime 非等价 | reasoning-on 输出会随共同 batch 成员变化；受限进程可能看不到 MPS/Metal | 必须冻结 singleton 或经过验证的执行路径，资源成本显著增加 |
| 计算与时间成本高 | 4B LoRA 三 seed 训练约 17.1 小时；matched validation 约 24.2 小时 | 实验矩阵必须受资源门控制，不能为了追求模型数量牺牲重复和错误分析 |
| 表征解释证据不足 | EXP-028 超资源门失败，SAE 尚未执行 | 当前论文主线应以可复现行为实验为核心，可解释性只能作为受控扩展 |
| 标注者信息不足 | Weibo 没有行级 annotator provenance；IAC 只有一名人工标注者加两个模型 | 不能报告 IAA 或把模型多数票当作 gold，只能明确保留不确定性 |

## 8. 已形成的研究与工程产出

截至本报告证据截止点，项目已经完成：

- 两个公开基准的传统方法、encoder、LLM/LoRA 对照和正式 test gate；
- 三个任务上的多随机种子训练、完整指标、混淆矩阵和逐条私有预测；
- TweetEval、GoEmotions 和 Weibo 的冻结错误分析；
- GoEmotions 逐标注者聚合审计与 disagreement-aware evaluation；
- IAC 2.0 的清洗、quote 重建、近似去重、确定性抽样和三来源标注诊断；
- Weibo EClass 的七分类 ontology、分组去重划分、paired views 和 test 密封协议；
- 本地 Qwen3-4B LoRA 三 seed 训练、adapter 复核、runtime-equivalence 和成本记录；
- 原始文本、用户/行 ID、模型输出和私有 adapter 的 Git ignore、HMAC 与权限边界；
- 每个 Major 的 protocol、run metadata、artifact hash 和不导入 runner 的独立 verifier。

这些产出已经支持一条可信的本科毕设证据链：问题定义、数据协议、基线、LLM 适配、
负结果、错误分析、复现和局限均有对应产物，而不是只报告一个最终准确率。

## 9. 下一阶段与报告更新规则

1. 当前正式 test 完成后，只在独立 verifier 通过时把最终聚合结果加入本报告的后续版本；
   不使用 test 结果继续调 prompt、挑 seed、换 checkpoint 或修改标签。
2. 论文主结果表应同时保留传统基线、encoder、frozen Qwen、LoRA 三 seed mean +/- SD、
   Accuracy、Macro-F1、Weighted-F1、parser-valid 和逐类 F1。
3. 系统实现应接入冻结后的一个主模型，并明确输出 schema、无效输出处理、延迟和适用范围；
   系统演示不能替代模型评价。
4. 表征分析若继续，应重新登记实验编号、减少资源风险并预先定义 probe/SAE 的因果主张边界；
   它不阻塞行为层毕设闭环。
5. 论文标题中的 `forum text` 应在正文中操作化为当前代理任务的实际语料结构，明确 Weibo
   是中文多用户局部话语而不是完整现代论坛样本。

## 附录 A：阶段实验清单

| 分支 | 实验或协议 | 状态 | 阶段结论 |
| --- | --- | --- | --- |
| TweetEval | EXP-001 至 EXP-007 | Completed | 建立并调优 LR/SVM 传统基线；validation Macro-F1 由 0.494 提高到 0.623 |
| TweetEval | EXP-009/010 | Rejected | 分别因 logger 接口和受限 MPS 环境在正式训练前失败，保留失败证据 |
| TweetEval | EXP-011/014/015 | Completed，后由 test 验证 | 通用 RoBERTa、label smoothing 和 Twitter-domain encoder 三 seed 比较 |
| TweetEval | EXP-016 | Verified | 一次性 test gate；Twitter-domain encoder 最强，label smoothing 未泛化 |
| TweetEval | EXP-017 | Verified | 稳定错误、seed 波动、共享错误和领域迁移转移分析 |
| GoEmotions | EXP-018/020 | Verified | 简单 TF-IDF 多标签基线与 BERT 三 seed 监督基线 |
| GoEmotions | EXP-021 至 EXP-026 | Verified/保留失败 | Qwen 环境、parser/decoder 预检、zero/few-shot 和约束消融 |
| GoEmotions | EXP-027 | Passed smoke | matched hidden-state 路径仅在合成文本上通过 |
| GoEmotions | EXP-028 | Failed | probe 产物可复算，但超过资源门，不支持正式表征结论 |
| GoEmotions | EXP-029/030/031 | Verified | LoRA 三 seed、跨模型错误分析和 inference-only ontology 消融 |
| GoEmotions | EXP-032 | Verified Minor | 加速方案未满足等价性或收益门，保留原训练配置 |
| GoEmotions | EXP-033/034 | Verified | target-aligned 重训未改善，训练共现切片仍呈近单标签输出 |
| GoEmotions | EXP-035 至 EXP-037 | Verified | 逐标注者聚合审计、局部与完整 dev disagreement-aware 评价 |
| GoEmotions | EXP-038 | Verified | 一次性 test gate；BERT 仍高于 Qwen LoRA |
| IAC 2.0 | DATA-FCTX-CLEAN/DEDUP-V2 | Verified | 形成 403,183 条可用 parent-target 候选和可审计去重链 |
| IAC 2.0 | DATA-FCTX-SAMPLE-V1 + staged views | Verified | 冻结 120 主样本、60 备用样本并完成私有标注视图 |
| IAC 2.0 | Three-source pilot | Completed | 发现 stance-emotion 与 ontology mismatch，不生成 gold，关闭主训练分支 |
| Dataset audit | KOTE/Hotter/Weibo candidate audit | Verified | KOTE 降为控制候选，Hotter 排除，Weibo EClass 进入任务协议 |
| Weibo | DATA-WEIBO-TASK-V1 | Verified | 冻结 8,540 条七分类任务、paired views 和 group-disjoint split |
| Weibo | EXP-039/040/041 | Failed predecessors + Verified | 修复 target rendering/token budget，模型栈与 LoRA 插入预检通过 |
| Weibo | EXP-042 | Verified | M0/M1/M2 validation；中文 encoder target-only 被选定 |
| Weibo | EXP-043 | Verified | Qwen context x reasoning 2x2；context 平均为负，reasoning 平均为正 |
| Weibo | EXP-044 | Verified Minor | 本机 Qwen3-4B BF16 LoRA 成本与内存可行 |
| Weibo | EXP-045/046 | Failed predecessor + Verified | 修复 batch 接口并确认共同 batch 成员会改变输出，冻结 singleton |
| Weibo | EXP-047 | Verified | LoRA 三 seed train/replay/matched validation；显著优于 frozen Qwen，仍低于 encoder |
| Weibo | EXP-048 | Verified | 格式与标签收益分解、少数类差距、跨 seed 稳定性和定性错误分析 |

## 附录 B：主要证据入口

- [项目证据台账](evidence-log.md)
- [研究路线图与研究问题注册表](research-roadmap.md)
- [TweetEval 正式 test gate](experiments/tweeteval-emotion/test-gate/)
- [TweetEval 冻结错误分析](experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/)
- [GoEmotions 正式 test gate](experiments/goemotions/test-gate/)
- [IAC2 三来源比较报告](experiments/forum-context/annotation/reports/three-source-comparison-v1.md)
- [Weibo EClass 数据构建报告](experiments/forum-context/weibo-eclass/reports/data-weibo-eclass-v1.json)
- [Weibo Stage 3 基线](experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/)
- [Weibo Qwen 2x2](experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/)
- [Weibo LoRA matched validation](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/matched-validation-v1/)
- [Weibo 冻结 dev 错误分析](experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/REPORT.md)
