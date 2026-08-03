# AGENTS.md - 论坛文本情绪识别毕设实验协议

本文件适用于 `projects/llm-forum-text-emotion-recognition/` 及其子目录。
它补充仓库根目录规则，目标是用足够严谨、但本科毕设可以持续执行的方式完成：

```text
Research Question -> Experiment -> Evidence -> Figure/Table -> Thesis Section
```

优先形成可信论文闭环，不以实验数量、模型数量或记录篇幅作为成果。

## 0. 项目文件分工

不要在多个文件重复维护同一内容：

- `README.md`：题目、边界、当前状态和近期行动。
- `research-roadmap.md`：Research Question Registry 与 Experiment Map。
- `hypotheses.md`：仅保留会影响论文结论的核心假设。
- `evidence-log.md`：实验结果、证据状态和论文去向。
- `experiments/`：代码、配置和运行产物。

`research-roadmap.md` 中的每个核心研究问题至少记录：

- RQ ID、问题和研究价值。
- 预期贡献，以及负结果仍能说明什么。
- 对应的 Major experiments。
- 计划进入的图、表或论文章节。
- 当前状态和下一步。

研究问题和预期贡献属于项目内容，不写死在本协议中。助手不得自行新增或冻结会
改变毕设主线的 RQ；先与用户确认，必要时再由用户与导师确认。

## 1. 不可违反的边界

- train、validation 和 test 必须严格分离。
- 词表、IDF、标准化、特征选择等预处理只能在 train 上拟合。
- validation 用于模型、阈值、提示、示例和 checkpoint 选择。
- test 只评估已经由 train/validation 选定并冻结的配置。
- test 结果不得反向用于调参、改标签、改提示或挑 checkpoint。
- 不得删除、覆盖或隐藏失败运行。
- TweetEval emotion 的主指标为 Macro-F1，不得只报告 Accuracy。
- 不得把 validation 数字写成 test 或公开 benchmark 数字。
- 不得把 probe、SAE feature 或相关性直接写成模型或人类的情绪机制。
- 不得直接比较 TweetEval 四分类单标签分数与 GoEmotions 28 标签多标签分数。
- GoEmotions LLM 对照只能在同数据集的简单多标签与 BERT/RoBERTa 监督基线
  冻结后登记；LLM 不替代 TweetEval 已完成的传统分类器与 RoBERTa 比较。

原始论坛文本、Tweet、用户标识和含原文的错误案例默认不得提交到公开 Git。
使用自建论坛数据时，应在可行情况下按 `thread_id` 或等价群组划分，避免同一会话
跨 split 泄漏。

## 2. Major 与 Minor 实验

所有运行继续使用单调递增的 `EXP-NNN`，并在 `run.json` 中标注 `tier`。

### Major experiment

以下默认属于 Major：

- 论文核心模型或基线比较。
- 将进入论文结论的 LLM prompting、fine-tuning 或 context 实验。
- 消融、鲁棒性、错误模式或可解释性实验。
- 多随机种子正式比较。
- 任何读取 test split 的运行。

Major 需要独立 protocol、完整产物、证据复算和论文去向。

### Minor experiment

以下通常属于 Minor：

- 环境和代码可行性检查。
- learning rate、batch size、`C` 等小范围调参。
- 调试、短跑、单 seed 探索和实现检查。
- 不单独支撑论文结论的快速受控比较。

Minor 只需保存 `run.json`、必要训练日志和结果摘要，不要求单独写完整假设、
protocol 或 amendment。Minor 不得访问 test，也不能单独支撑“模型更优”等论文
结论。

Minor 可以用于选择候选配置。选定后应将配置冻结为 Major；可以引用原运行，但
不得把事后选择伪装成预注册实验。

同一配置的训练和 validation 可以共享一个 EXP ID 与运行目录。只有研究问题或
实质配置发生变化时才新建 EXP，不再为了“train-only”和“validation”机械拆号。

Parent experiment 仅在声称受控增量、消融或继承配置时必填；其他情况写 `N/A`，
不强制制造父子关系。

## 3. Major Protocol 与资源预算

Major 在读取本次结果前，于 `protocols/exp-NNN-*.md` 登记：

- RQ ID、实验问题和预期结果。
- 本次改变什么、保持什么不变。
- 数据版本、split、样本数、标签映射和输入 SHA-256。
- 模型、配置、随机种子与比较对象。
- 主指标、辅助指标、模型选择规则和停止条件。
- 计划保存的图、表、预测和错误分析。
- 论文目标章节或表格。
- 资源预算：最大运行次数、GPU/CPU 时长、API 费用和截止时间。

无法可靠估算的资源写 `N/A` 和原因。预算不是形式字段；超过预算前应停止并向
用户说明收益、代价和替代方案。

Major protocol 发现笔误时，直接追加带日期的 correction note。只有改变研究问题、
数据、指标或选择规则时才建立新 Major，不维护复杂 amendment 流程。

Minor 在运行前只需确定：

- RQ 或所属 Major。
- 唯一变化项和固定数据 split。
- 命令、配置、seed、最大运行次数和输出目录。

## 4. Test Gate

test 前必须建立一次 `TEST-READY` 清单并等待用户明确授权。清单包括：

- 本次要评估的全部冻结配置及其选择依据。
- 主指标、辅助指标和统计汇总方式已经冻结。
- 代码、数据哈希、模型或 checkpoint 均可追溯。
- validation 预测和指标可以复算。
- test 输出目录为空且不会覆盖历史运行。
- 用户明确批准读取 test。

每个冻结配置只执行一次正式 test 评估。若 test 后继续开发，必须标记为
post-test development，不得继续把同一 test 当作 validation。

## 5. 模型选择与统计重复

默认选择规则：

1. 以 validation Macro-F1 为 primary metric。
2. 核心随机模型比较使用至少 3 个 seed，报告 mean +/- std。
3. 确定性传统基线或纯可行性运行不强制做无意义的多 seed。
4. LLM 输出具有随机性且结论依赖该随机性时，按资源预算重复调用并报告波动。

Major protocol 应预先给出“实际并列”的阈值。若没有另行登记，Macro-F1 绝对差
小于 `0.005` 视为工程上的实际并列，而不是证明显著优于。实际并列时优先选择：

1. 更低复杂度与更容易复现的模型。
2. 更低推理成本和延迟的模型。
3. 预先指定的 per-class recall 或辅助指标。

Weighted-F1 必须报告，但不自动作为通用 tie-breaker，因为它可能掩盖少数类表现。
若论文声称模型显著更好，应使用多 seed、bootstrap 或合适的配对检验，并区分
统计显著性与实际效应大小。

## 6. 运行记录与产物

每个运行都生成机器可读的 `run.json`，至少包含：

- Experiment ID、tier、RQ、stage、status 和时间。
- 完整命令、工作目录、Git commit/dirty 状态。
- 数据版本、split、样本数、标签顺序和输入哈希。
- 模型配置、随机种子和初始化来源。
- 开始、结束、耗时、warning、异常和收敛状态。
- 指标、产物路径和是否访问 validation/test。

Major 另需记录完整环境、关键依赖、硬件、artifact 哈希和复现命令。长时间训练或
Major 应持久化 `stdout.log`；短小 Minor 不要求为已有结构化字段复制终端输出。

目录沿用：

```text
experiments/<dataset>/<model>/
├── README.md
├── protocols/                 # 仅 Major 强制
└── runs/
    └── exp-NNN-name/
        ├── run.json
        ├── stdout.log         # Major 或长时间训练
        ├── history.csv        # 神经网络训练
        ├── predictions.csv    # 正式 validation/test
        └── confusion_matrix.*
```

传统 LR/SVM 没有可解释的逐 epoch loss 时，不得伪造训练曲线；记录迭代次数、
收敛 warning、特征数和 fit time。BERT/RoBERTa 等神经网络保存 train/validation
loss、learning rate、Macro-F1、Accuracy、step/epoch 和 checkpoint 选择记录。

已完成 run 目录视为 append-only。发现错误时新增 correction note 或新实验，不
改写原结果。模型、checkpoint、原始数据和含原文日志默认 gitignored，但记录本地
路径与哈希。

## 7. 评估与 Error Analysis

正式 validation/test 至少保存：

- Macro-F1、Accuracy、macro precision/recall 和 weighted F1。
- 每类 precision、recall、F1 和 support。
- 明确 `rows=true, columns=predicted` 的混淆矩阵。
- 每条样本的 row ID、gold、prediction 和概率或 decision score。
- 输入、模型哈希、推理耗时及适用时的成本。

指标必须从 `predictions.csv` 独立复算，并核对行数、标签顺序、split 和混淆矩阵。

只有进入论文核心比较的 Major 模型需要完整 Error Analysis。开始阅读错误原文前，
先冻结抽样规则和样本预算，避免只挑有趣案例。至少覆盖：

- 各类别高置信 false positive 与 false negative。
- 分层随机抽取的普通错误。
- sarcasm、negation、implicit emotion、mixed emotion、slang/noise。
- context dependency、annotation ambiguity 和 minority class。

每个案例区分可能来源：

- 数据、标签或标注分歧。
- 类别定义本身重叠。
- 模型表征或上下文能力不足。
- LLM prompt、label mapping 或 parser 问题。

报告错误类型数量或比例，并比较模型共享错误与特有错误。公开台账只保存匿名 ID、
类型和聚合统计；受限原文保存在 gitignored 本地文件。

## 8. LLM 专项记录

每个 LLM Major 配置记录：

- Provider、精确模型名/版本和访问日期。
- label ontology、数值标签、允许输出词及确定性 mapping rule。
- system/user prompt、模板版本、hash 和 zero/few-shot 设置。
- 示例选择、检索规则及是否使用上下文。
- temperature、top_p、max tokens、seed 等可用参数。
- 输出 schema、parser、重试和无效输出处理。
- token、费用、median/tail latency 和失败率。
- 数据保留、日志和隐私设置。

若使用 rationale 或 Chain-of-Thought 风格提示，记录其 enabled/disabled、提示版本
及解析方式。不要求获取或保存供应商未提供的隐藏推理；模型生成的解释只能视为
输出行为，不能直接当作忠实内部机制。

LoRA 或其他参数高效微调另需记录：

- base model 与 revision。
- trainable parameter 数量和比例。
- rank、alpha、dropout、target modules。
- quantization、sequence length、batch/accumulation。
- optimizer、learning rate、scheduler、epoch 和 checkpoint。

外部 API、付费调用或将项目数据发送给第三方前，必须获得用户明确批准。

## 9. 可解释性范围

可解释性是建立稳定性能基线后的 Major 扩展，不应阻塞毕设最低闭环。Probe、
activation attribution、SAE feature 或 hidden-state clustering 首先只支持表征
相关性。

若要声称某特征参与情绪判断，至少需要 held-out 数据、合理控制任务，以及
intervention、ablation、patching 等因果测试。必须记录替代解释、失败样本和跨
seed/模型稳定性。

模型内部模式不能直接外推为人类情绪产生机制。AI 与人类的比较必须说明对应发生
在任务、行为、表征、算法还是实现层面。

## 10. Evidence-to-Thesis Pipeline

只有 Major 或被正式选入核心比较的 Minor 才写入详细 `evidence-log.md`。普通
Minor 可在所属 Major 的调参摘要中合并记录，不逐条扩写论文证据。

每条论文证据至少关联：

```text
Evidence ID
RQ ID
EXP ID
Claim and limitation
Artifact path
Verification status
Target figure/table
Target thesis section
```

论文中的图表必须能回溯到配置、预测和生成脚本。只有 `Verified` 的定量结果可以
进入 CV、SOP、推荐信或公开成果；`Completed` 可以描述过程，但不能作为冻结数字。

负结果只要设计有效，也应保留并说明它排除了什么，而不是从台账中删除。

## 11. Agent 执行顺序

每次实验：

1. 读取本文件、`research-roadmap.md`、`evidence-log.md` 和相关父实验。
2. 判断 Major 或 Minor，并说明 RQ、变化项、固定项和资源预算。
3. Major 先写 protocol；Minor 只登记最小配置。
4. 检查输入哈希、split 和空输出目录。
5. 执行并持久化对应层级要求的记录。
6. 检查 warning、NaN、OOM、收敛、行数和意外 test 访问。
7. 从保存预测独立复算正式指标。
8. 只为核心 Major 做完整错误分析和论文映射。
9. 报告结果、代价、限制和下一步。

遇到数据/标签不一致、哈希意外变化、输出目录非空、未解释的 NaN/OOM、意外读取
test、版本不明确或未授权外部上传时，立即停止。

## 12. Git、发布与历史迁移

- 只暂存本项目明确相关路径，不使用 `git add .` 或 `git add -A`。
- 不提交原始文本、用户标识、模型二进制或 checkpoint。
- 不夹带用户已有且与当前实验无关的修改。
- commit 前检查 `git diff --check`、tracked 内容和 ignore 规则。
- 只有用户明确要求时才 commit、push、发布或调用 test。

本协议从 `EXP-005` 起执行。`EXP-001` 至 `EXP-004` 按创建时结构保留：

- 不补造 stdout、Git commit、资源数据或训练历史。
- 不为满足新分级规则重写原始 `run.json`。
- 可在 `evidence-log.md` 说明其历史层级和缺失项。

现有分数、具体结论和下一步属于 `evidence-log.md`、`research-roadmap.md` 或实验
README，不写入本文件作为永久规则。
