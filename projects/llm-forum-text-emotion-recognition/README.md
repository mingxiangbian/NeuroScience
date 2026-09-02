# 基于大模型的论坛文本情感识别

---
date: 2026-07-23
status: opening-preparation
tags: [emotion-recognition, forum-text, llm, nlp, final-year-project]
sources:
  - ../../sources/llm-forum-text-emotion-recognition-sources.md
papers:
  - ../../papers/llm-forum-text-emotion-recognition/reading-route.md
---

## Project Identity

- English title: Research and Implementation of Emotion Recognition System of Forum Text Based on LLM
- Project area: Artificial Intelligence Technology
- Project type: Engineering Design
- Ownership: 中方
- Supervisor: 王玉林
- Supervisor email: `wyl@uestc.edu.cn`
- Current stage: 开题准备
- Supervisor's current instruction, as relayed by the user: 查阅情感识别相关论文，复现公开代码，自行准备论坛文本数据，并完成开题准备。

题目与导师信息来自已保存的毕设题目公示记录。导师指示来自用户转述的邮件回复；原始邮件应由用户另行保留，项目仓库只记录任务摘要。

## Project Question

在合规取得并可靠标注的论坛文本上，传统机器学习、预训练编码器与大语言模型（Large Language Model, LLM）方法在情绪识别的准确性、稳健性、成本和上下文利用能力方面有何差异？

## Working Objective

项目目标不是只做一个调用 LLM API 的界面，而是形成完整、可复核的研究闭环：

```text
问题定义 -> 数据与标注 -> 可复现基线 -> LLM 对照 -> 鲁棒性与失败分析 -> 可运行演示 -> 论文与证据归档
```

最终成果应同时包含：

- 一个边界明确的论坛文本情绪识别任务。
- 一套来源、授权、匿名化和数据划分均可说明的数据集。
- 至少一个简单基线和一个有竞争力的编码器基线。
- 与 LLM 方法的公平比较，而不是只展示单次模型输出。
- Macro-F1、各类别指标、混淆矩阵及失败案例分析。
- 可复现代码、环境、配置、预测结果和技术报告。
- 在研究结论支撑下形成的可运行演示。

## Experiment Route and Comparison Boundary

模型路线按数据集和依赖关系分为四段：

```text
TweetEval（已完成）
TF-IDF + Logistic Regression
-> TF-IDF + Linear SVM
-> 通用 RoBERTa
-> Twitter-domain RoBERTa
-> 验证训练、评估、test gate 和错误分析流程

GoEmotions（公开行为复现已完成）
简单多标签基线
-> BERT-base / RoBERTa 监督微调
-> 建立同一数据集上的冻结编码器基线与正式 test 结果

GoEmotions 本地 LLM 对照（行为线已完成）
Qwen3-1.7B Instruct zero-shot / few-shot
+ Qwen3-1.7B Base / Instruct matched frozen probes
-> 区分实用分类表现与 post-training 对表征可解码性的影响

任务适配
Instruct LoRA
-> 与冻结的简单基线和 BERT 比较性能、稳定性、成本和延迟
-> 只有出现明确容量证据时才做 matched 1.7B / 4B scale control

后续
冻结错误分析（EXP-030 已完成） -> neutral ontology 推理消融（EXP-031 已完成）
-> 重训加速预检（EXP-032 已完成） -> target-aligned retraining（EXP-033 已完成）
-> frozen test gate（EXP-038 已完成） -> 论坛上下文 -> 内部表征 -> SAE
```

LLM 是后续新增的第三类模型路线，不替代 TweetEval 已完成的传统分类器与
RoBERTa 比较。模型分数只能在相同数据集、任务定义、split 和评估代码下作正式
比较。TweetEval emotion 是四分类单标签任务，GoEmotions 是 28 标签多标签任务，
两者的分数不能直接横向比较。

如果最终完全取消 LLM 路线，本项目仍可退化为普通情绪分类研究，但题目、开题报告
和研究动机必须同步调整，不能继续声称完成“基于大模型”的比较。

## Scope

项目范围分阶段覆盖：

- 英文论坛或社交媒体文本情绪识别。
- 单条文本与回复上下文两种输入设定。
- GoEmotions 保持官方 28 标签多标签任务；自建论坛数据先做原子标签的
  single-primary-label calibration，再由协议诊断和后续人工验证冻结最终 ontology。
- 在 GoEmotions 上依次建立简单多标签基线、BERT/RoBERTa 监督基线和
  zero-shot/few-shot LLM 对照。
- 先以本地 1.7B Base/Instruct 配对模型建立 prompting 与后训练控制，再在资源
  允许时评估 LoRA、检索示例或上下文建模。
- 反讽、否定、网络用语、类别不平衡和上下文依赖等失败模式。

## Non-goals

当前不把以下内容视为项目成果：

- 只调用一次 LLM API 并展示几个样例。
- 只报告 accuracy。
- 没有固定数据划分、基线或可复现配置的模型比较。
- 在未确认平台条款、授权和匿名化方案前大规模采集论坛数据。
- 把计划中的模型、功能、指标或实验写成已经完成。
- 为追求复杂度而直接从 7B 级模型完整复现开始。

## Current State

### 2026-09-01：Phase C在有界本地研究范围内完成收口

用户已确认最终范围修订：Phase C lifecycle为Closed，outcome为
`Completed within bounded local research scope`；Phase C.1为`Completed / Verified Pass`。
最终系统定级为“经过验证的有界本地研究原型，并完成两个技术论坛来源的服务链路迁移”。
外部gold、context/C2、长期SLA、多用户、公网部署和商业再发布移入未来独立范围，
不是当前Phase C内部尚未完成的实验。

范围决策见[DEC-PHASE-C-FINAL-SCOPE-AND-CLOSEOUT-V1](experiments/stack-overflow-emotion-gold/protocols/dec-phase-c-final-scope-and-closeout-v1.md)；
当前报告、claims与发布QA入口见[工作台README](forum-topic-emotion-web/README.md)，
实验结果、参数和保留边界见[Artifact Index](experiments/stack-overflow-emotion-gold/ARTIFACT-INDEX.md)。这项收口不改写
EXP-077/079/083/085 attempt1的失败，也不把EXP-078/080写成已执行。

### 2026-09-01：Phase C.1最低闭环完成

EXP-085 attempt2已通过固定九任务资源门；随后EXP-086在已审核Python Help公开前缀上完成一次
400条staged Research任务。来源69次匿名响应，M1/M3阶段各400回执，46次M3全部成功，
独立来源/成本/聚合/安全核验Passed。全部进程退出，无critical/unknown采样。

这个闭环回答的是“本地系统能否在第二论坛按固定来源合同安全完成一次任务”，没有gold，
不回答跨域准确率。400条达到item limit且1个topic截断，不能外推论坛总体或完整线程。
Phase C.1已收尾；随后通过最终范围修订将总体Phase C关闭在有界本地研究范围内。
CancerEmo等外部gold、旧context/C2和公网部署作为未来独立范围继续暂停。
完整数字与hash见[HANDOFF](experiments/stack-overflow-emotion-gold/HANDOFF.md)。

### 2026-09-01：EXP-085 attempt 2有界验收通过

Attempt 1的软件回调错误保留为Failed；封存该版本后只改内部参数名并补真实组合回归。
Attempt 2执行固定三轮九任务：9/9任务、3060最终结果、5100阶段回执完整，独立verification=Passed，
成本与跨轮一致性复算通过，所有模型进程正常退出。557个系统样本有12个warning、无critical/unknown；
最高swap较高但仅连续2段，未触发三段停止门。因此只支持当前机器和固定负载的有限有界运行，
不支持SLA、外部准确率或因果内存修复主张。

通过版本及协议已封存。其后登记的EXP-086已经完成一次已审核`discuss.python.org` Python Help
公开前缀的匿名、无gold staged Research闭环。旧EXP-080仍未执行，外部gold/context继续暂停。
详细数字、工件hash和证据边界见[HANDOFF](experiments/stack-overflow-emotion-gold/HANDOFF.md)。

### 2026-09-01：EXP-085 attempt 1网站分时接入失败（历史记录）

新路径已接入完整任务与三模式，538项合成测试及审查后执行唯一一次九任务验收。
98.639秒后因新增进度回调的`kind`参数重名停止：M1-only完成340，Research的M1预计算完成340，
回放6项后失败；其余7任务未启动。完整verification=Failed/staged_lower_bound_range，
原因是首次M3进度事件未写入journal，成本下界不能完整核验。本次没有观察到资源门触发，
所有进程已退出，但当时未完成M3工作量，不能宣布内存问题已解决。有界运行和Discourse在该尝试终态中仍未完成。
随后只修复回调接线并补组合回归，另登记attempt 2；本段失败终态保持不变。
详见[交接与工件哈希](experiments/stack-overflow-emotion-gold/HANDOFF.md)。

### Phase C.1：实际验证仍受阻（2026-08-31）

用户确认退出占用应用后，9个目标应用主进程均不在运行；前检10个样本正常，swap I/O为0。
EXP-079 attempt3仍在61.144110秒内触发critical pressure：M1完成340条（338计算+2cache），
Research取得6条回执后取消，整体1/9完成，后续7任务未启动。58个系统样本含1个critical，
没有warning或unknown；最大swap I/O为292.029MiB/s，连续高值仅2个间隔，未达到thrashing定义。
完整记录独立审核Passed，但安全门为false、exp079_complete=false、状态为stop-required；
这不表示资源问题已解决。EXP-080正式闭环仍未执行，旧attempt2的Failed记录保持原样。
[减载后验证报告](forum-topic-emotion-web/private/reports/phase-c1-attempt3-reduced-background-report-2026-08-31.md)
保存在Git-ignored私有目录。下面的原Phase C记录与所有旧失败保持不变。

后续EXP-082单次七项阶段诊断已独立通过，首次M3完成、累计MLX peak8.528GB，仍有2个warning样本。
这不是与旧失败的受控对照，也未补足九任务验收；[阶段结论与边界](evidence-log.md)已追加。
之后EXP-083加入完整M1前置负载：M1完成340，Research6/7后触发连续高换页停止。
独立审核确认加载已完成、首次前向未确认返回；终止峰值未知。记录通过不等于资源验收通过，
需继续处理加载至前向的内存/换页压力，Discourse仍未执行。

最新EXP-084分时驻留原型已通过：同次M1回执转交独立M3进程，347/347完整、七项功能等价、
本次资源门通过。仍有2个warning，不证明绝对RSS下降或旧故障已因果修复；尚未接入网站或替代九任务验收。

### 2026-08-31：Phase C 功能交付与稳定性阻塞

已按用户要求暂停 CancerEmo、JIRA 等外部金标泛化，转入
[话题情绪工作台](forum-topic-emotion-web/README.md)：上传、Stack Overflow Question Cohort、
冻结 M1/Research/Demo 模式、私有任务存储与来源追溯。实现已落盘，真实有限验收登记为
[EXP-076](experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md)。
最新212/212合成/集成测试通过；四个原有小批jobs、32条预测及Research重放保持通过。
评论联合字段对照已通过；source attempt3完成46问题、46回答、248评论共340条M1推理，
独立22/22 Passed。前两次失败保留，数值验收后仅修正公开评论链接，私有数据不变；
详见 [验收记录](forum-topic-emotion-web/docs/acceptance.md)。
完整统计、CSV/全文清除与使用材料已补齐，已有5任务372条新视图只读QA通过。
EXP-077 Soak在40.22秒因critical memory pressure停止：1/36完成，第2Research取消且0回执。
独立审计Passed但Soak未过，exp077_complete=false、stop-required，不自动重试。
Python Help Discourse审核、adapter和验证工具完成，EXP-078正式运行因安全前提未满足而未执行。
系统报告与Final claims ledger保留在模块private/reports，Git-ignored；不能说Phase C全部完成。
context/C2维持暂停。不将本地工程验收视为外部泛化或对Phase A旧效率结论的修复。

### 已确认

- 毕设题目、项目类型、导师及导师当前准备要求已经记录。
- 已建立 6 篇核心论文的本地阅读包与复现路线。
- 已提出初始实验矩阵、最低数据字段和开题研究问题。
- 已使用固定 TweetEval emotion 训练集拟合首个 TF-IDF + Logistic Regression 基线，并完成固定验证集评估；测试集尚未读取。
- 已在其余配置不变的条件下拟合并评估 `class_weight="balanced"` 受控变体；按预先登记的 validation Macro-F1，balanced 版本暂选为后续 TF-IDF 基线。
- 已完成 paper-aligned word + character n-gram TF-IDF + Linear SVM 基线；EXP-005 的 validation Macro-F1 和 Accuracy 均高于 balanced Logistic Regression，成为当前更强的传统基线；测试集仍未读取。
- 已在不读取 validation/test 的条件下完成 EXP-006 训练集 5 折调参，并用冻结配置执行一次 EXP-007 validation 确认；Macro-F1 从 0.611866 提高到 0.622678，Accuracy 从 0.671123 提高到 0.676471，成为当前最强的本地传统基线；测试集仍未读取。
- 已建立独立的 `emotion-roberta` 环境并固定 `FacebookAI/roberta-base` 上游 revision；EXP-008 已通过离线模型哈希校验、MPS 单步训练和合成推理检查，未读取任何项目数据。
- 已完成 EXP-011 RoBERTa-base 三随机种子正式微调；validation Macro-F1 为 `0.732804 +/- 0.005007`，Accuracy 为 `0.792335 +/- 0.004084`，相对 EXP-007 的平均 Macro-F1 提高 `0.110126`。逐条预测、类级指标、训练曲线、checkpoint 哈希和独立复算均已保存；测试集仍未读取。
- 已通过 EXP-012 与 EXP-013 两轮仅使用训练集的 Minor 筛选确定正式调优配置：保留原始文本，加入 `label_smoothing_factor=0.05`。Tweet 归一化规则未改变当前数据中的任何样本，因此不能从分差判断其效果；论文同款超参数组合未在当前受控设置下胜出。
- 已完成 EXP-014 通用 RoBERTa-base 优化配置的三随机种子验证；validation Macro-F1 为 `0.740219 +/- 0.005381`，相对 EXP-011 提高 `0.007415`。两个 seed 明确提高，一个 seed 与 EXP-011 属于 practical tie；独立复算已通过，测试集仍未读取。
- 已完成 EXP-015 Twitter 域预训练 RoBERTa-base 的配对比较；validation Macro-F1 为 `0.761755 +/- 0.010579`，Accuracy 为 `0.829768 +/- 0.012350`，相对 EXP-014 的 Macro-F1 提高 `0.021536`，三个配对 seed 均提高。收益主要来自 joy、sadness 和 anger；optimism F1 反而从 `0.556824` 降至 `0.521836`，不能把整体收益解释为所有类别均受益。独立复算已通过，测试集仍未读取。
- 已完成并由用户确认冻结一次性测试门 EXP-016。test Macro-F1 分别为 EXP-007 `0.646998`、EXP-011 `0.795761 +/- 0.003298`、EXP-014 `0.792645 +/- 0.003658`、EXP-015 `0.809973 +/- 0.007038`。EXP-014 相对 EXP-011 的配对均值为 `-0.003116`，说明 label smoothing 的小幅 validation 收益没有泛化；EXP-015 相对 EXP-014 为 `+0.017328`，且 3/3 seed 提高，支持 Twitter 域预训练收益。14,210 条模型-样本预测的指标、类别结果、混淆矩阵和哈希已独立复算通过，并归档于提交 `f061ec9`；此后不得再用该 test 调参。
- 已完成 EXP-017 冻结错误分析。EXP-015 在 1,421 条 test 中有 155 条 3/3 seed 稳定错误和 147 条 seed 结果不稳定样本；optimism 的稳定错误率为 `26.02%`，明显高于 anger `6.63%`、joy `8.94%` 和 sadness `14.14%`。87 条样本被传统基线和全部神经模型 seed 共同判错。按读原文前冻结的五组规则复核 42 条匿名案例，并将原文隔离在 gitignored 本地目录；独立验证确认 14,210 条预测、抽样身份、定性编码、聚合表和公开隐私边界一致。
- 已创建与 TweetEval 并行的 GoEmotions 数据与实验分支，并冻结 `DATA-GOE-V1`：官方 agreement-filtered split、完整 27 类情绪加 `neutral`、多标签单评论任务、固定标签顺序和独立 test gate。train、dev 和 `emotions.txt` 已从固定 revision 获取并校验；官方 train/dev 的 41 个 exact-text overlap 已审阅记录，comment ID overlap 为 0，test 仍未获取。
- 已完成并独立验证 EXP-018 GoEmotions 简单多标签基线：word TF-IDF + 28 个独立 Logistic Regression 在固定 dev 上得到 Macro-F1 `0.203644`、Micro-F1 `0.377639` 和 subset accuracy `0.246959`。固定阈值 0.5 下有 3,261/5,426 条空预测，disappointment、grief、nervousness、pride 和 relief 的 recall 为 0；test 未获取或读取。
- 已通过 EXP-019 完成 BERT-base-cased 离线模型、MPS 训练与 28 标签推理烟雾测试，并完成 EXP-020 三随机种子正式微调。EXP-020 固定 dev 的 Macro-F1 为 `0.489435 +/- 0.011063`，Micro-F1 为 `0.586671 +/- 0.002928`，相对 EXP-018 的 Macro-F1 提高 `0.285791`。三个 seed 的 5,426 x 28 概率、完整指标、模型和输入哈希均已独立复算，最大数值差异为 0；test 未获取或读取。
- 已完成并独立验证 EXP-021：从 Qwen 官方仓库下载固定 revision 的 Qwen3-1.7B post-trained/Base 配对模型，在同一 MLX-LM 环境转换为未量化 BF16，并分别通过合成输入生成检查。四份模型副本共 `14,437,414,837` bytes，逐文件 SHA-256 与来源 manifest 已保存；本阶段未读取任何 GoEmotions split，也不构成情绪识别性能证据。
- 已完成并独立验证 EXP-022 本地成本与 strict-parser 试跑：32 条匿名 train 文本共 64 次测量，未读取 gold label、dev 或 test。资源门全部通过，zero-shot/few-shot 完整 dev 线性估计约 `1.25`/`1.48` 小时，峰值 MLX memory `3.65` GB；但 few-shot 严格 JSON 有效率为 `87.5%`，低于预注册的 95%，因此总门失败，尚不能进入 full-dev。
- 已完成并独立验证 EXP-023 数字 label-ID 修复负结果：zero-shot/few-shot 严格有效率降为 `50.0%`/`65.625%`，说明数字接口没有修复格式门。
- 已完成并独立验证 EXP-024 constrained label-name JSON 修复：复用 EXP-022 prompt 与同一批 32 条匿名 train 文本，两条件均为 `32/32 = 100%` 严格有效，64 次均正常结束；完整 dev 线性估计约 `1.08`/`1.46` 小时，峰值 MLX memory `3.65` GB，全部门通过。该格式率由解码约束保证，不是分类性能证据。
- 已完成并独立验证 EXP-025 constrained full-dev zero/few-shot Major。Macro-F1 为
  `0.222998`/`0.241164`，parser 有效率为 `99.9631%`/`100%`；few-shot 相对
  zero-shot 的配对差值为 `+0.018166`，按冻结规则成为当前 constrained Qwen dev
  条件，但仍比 EXP-020 BERT 三 seed 均值低 `0.248271`。
- 已完成并独立验证 EXP-026 matched unconstrained decoder ablation。Macro-F1 为
  `0.228700`/`0.236465`，parser 有效率为 `95.9823%`/`90.7298%`。联合 2x2 显示：
  few-shot 中双方有效的 4,923 条标签集合完全一致，约束主要救回 503 个无效输出；
  zero-shot 中双方有效的 5,206 条只有 `75.8164%` 标签集合完全一致，finite-state
  mask 不能笼统视为 label-neutral。两个 verifier 的最大数值差异均为 0，test 未获取。
- 已完成并独立验证 EXP-027 合成 hidden-state smoke：Base 与 post-trained 使用相同
  token ID，均得到有限的 `6 x 2048` final-layer mean-pooled 表征，未读取 train/dev/test。
  EXP-028 matched frozen probe 的零数据 preflight `28/28` 通过，四份特征与 8 个探针
  均完成，但 fitting/evaluation 用时 `344.288` 分钟，超过冻结的 240 分钟资源上限，
  因而正式状态为 `Failed`。失败产物审计的概率、指标与 bootstrap 复算差异均为 0；
  Base/post-trained 的诊断 Macro-F1 为 `0.310534`/`0.306373`，但不能写入 Verified 证据。
- 已完成并独立验证 EXP-029 Qwen3-1.7B 监督 LoRA 三随机种子实验。冻结规则选择
  zero-shot 条件，其 dev Macro-F1 为 `0.451374 +/- 0.019212`，较 EXP-025 选定的
  frozen few-shot 提高 `0.210209`，但仍比 EXP-020 BERT 均值低 `0.038061`。
  few-shot-synthetic-3 为 `0.425265 +/- 0.004858`，没有在 LoRA 后继续提供收益；
  三个 seed 均通过独立复算和资源门，test 未获取或读取。
- 已完成并独立验证 EXP-030 冻结跨模型 dev 错误分析。LoRA 的 subset accuracy 为
  `0.508293`，高于 BERT 的 `0.440963`，但其 Macro-F1 低 `0.038061`；LoRA 平均
  只输出 `1.034` 个标签，在 878 条多标签样本上的 subset accuracy 约 `0.043`，
  明显低于 BERT 的约 `0.179`。当前 Qwen ontology 使 174 条 `neutral+emotion`
  gold 在结构上无法 exact-match。7 份预测、5,426 条 gold、48 条冻结匿名案例和
  隐私边界均已复算通过，公开原文泄漏为 0；test 仍未获取。
- 已完成并独立验证 EXP-031 三随机种子推理消融。仅放开 decoder 时，三个 seed 的
  预测与冻结 closed condition 完全一致；同时对齐 prompt 与 decoder 后，Macro-F1
  从 `0.451374 +/- 0.019213` 变为 `0.453056 +/- 0.014757`，平均差值仅
  `+0.001682`，低于 `0.005` practical threshold。Samples-F1 与 exact match 分别
  下降 `0.003240` 和 `0.005529`，174 条 neutral co-occurrence 切片 Samples-F1
  下降 `0.009132`，所有条件均产生 0 条 `neutral+emotion` 预测。正式分类为
  `no_material_inference_improvement`；这只说明推理时修正不足以改变当前冻结 adapter，
  不能替代 target-aligned retraining，也不支持内部机制结论。test 仍未获取。
- 已完成并独立验证 train-only Minor EXP-032 加速预检。保持 100 次优化更新、1000 条
  样本和有效 batch 10 不变时，`batch5-grad2` 的稳态吞吐只有 `batch2-grad5` 的
  `0.981853`，峰值内存由 `5.179` GB 增至 `7.312` GB，因此后续重训保留
  `batch2-grad5`。公共前缀 KV cache 在 32 条固定训练样本上获得 `1.275726x`
  端到端速度，但只有 `31/32` 输出逐 token 一致；唯一分歧为 `surprise` 与
  `disappointment`，因此拒绝该优化并保留完整 prompt 推理。该预检没有读取
  validation/test，也不构成分类性能证据。
- 已登记 Major EXP-033 target-aligned retraining，并完成独立 runner 的 no-model
  dry-run 与复算。当前 V3 将 protocol、runner、独立 verifier 和 canonical MLX runtime
  contract 全部绑定到 SHA-256；训练入口逐字段继承 EXP-029 的模型、LoRA、训练、资源和
  seed 门，但只消费保留全部官方标签的冻结 JSONL。43,410 条 target 中的 1,396 条
  `neutral+emotion` 均保留；smoke/formal runtime config 明确设置 `train=true`、
  `val_batches=0`、`test=false`。V3 另修复并实测 stdout EOF 后的 wall-time 门。一次
  显式授权的 50-iteration train-only smoke 已完成并由不导入 runner 的 verifier 独立
  复算：10 次 optimizer update 用时 `73.061` 秒，峰值 MLX memory `7.208` GB，正式训练
  投影 `8.109` 小时；224 个 LoRA 张量共 `4,980,736` 个参数，112 个 `lora_b` 张量均
  非零。初末两个日志窗口的 train loss 为 `6.153`/`0.3545`，只证明边界小样本可训练，
  不是 validation 性能。随后建立的 formal V2 gate 与 seed-42 单独授权已完成完整
  train-only 运行：4,341 次 optimizer update 用时约 `7.49` 小时，峰值 `7.208` GB，
  adapter 加载与真实前向均由独立 verifier 复核通过。
- EXP-033 seed-42 dev validation 已完成并独立验证。Macro-F1=`0.427959`，相对匹配的
  EXP-029 seed-42 aligned-open 参考下降 `0.012678`，paired 95% CI
  `[-0.026938,+0.001434]`，因此预登记 target-alignment improvement gate 未通过。
  全量 predicted cardinality 为 `1.058054`；174 条 gold `neutral+emotion` 上仍产生
  0 条对应共现预测。该实验是 `Verified` 负结果而非运行失败；seeds 43/44 未执行，
  test 未获取或读取。
- 已完成并独立验证 Minor EXP-034。冻结 EXP-033 seed-42 adapter 在训练时见过的全部
  1,396 条 `neutral+emotion` 样本上仍产生 0 条对应共现预测；gold/predicted
  cardinality 为 `2.044413/1.019341`。26 条输出虽然包含多个标签，但没有一条同时包含
  neutral。该结果排除了“主要只是 held-out 泛化失败”的简单解释，但不能进一步区分
  exposure、token-level objective、标签顺序、优化/LoRA 容量或模型规模。
- 已完成并独立验证 Major EXP-035 数据与标注审计。冻结 train 的 1,396/1,396 条
  `neutral+emotion` target 全部由不同标注者投票经官方 `>=2` 阈值聚合形成，同一
  标注者共选为 0；官方 simplified labels 全部精确复现。39 条含 unclear 投票。
  冻结目的性复核的 48 条中有 6 条被编码为可能需要上下文，但该比例不能外推。
  这把跨标注者聚合确认为当前异常结构的首要解释，不排除上下文或模型容量因素。
- 已完成并独立验证 Major EXP-036 dev 逐标注者评分诊断。174/174 条对应
  `neutral+emotion` dev target 仍为 aggregation-only，866 行 raw annotations 经官方
  `>=2` 票规则全部精确复现。EXP-029 与 BERT 的 clear-rater expected set-F1 分别为
  `0.363250 +/- 0.017685` 与 `0.362531 +/- 0.002371`，三 seed family delta
  `+0.000720`、95% CI `[-0.018463,+0.019903]`，属于该切片上的 practical tie。
  Qwen 的 official exact match 为 0，但 clear-rater expected/any-rater exact 为
  `0.341284/0.852490`，说明 aggregate union 的 exact-match 与个体标注一致度不是同一
  问题；该局部结果不能外推为完整 dev 上追平 BERT。
- 已完成并独立验证 Major EXP-037 完整 dev 逐标注者评分诊断。5,426/5,426 条 dev
  与 19,440 行 raw annotations 已复算，官方 `>=2` 票聚合 mismatch 为 0。BERT 与
  EXP-029 的 clear-rater soft Macro-F1 为 `0.383471/0.347253`；EXP-029 - BERT
  delta=`-0.036218`、95% CI `[-0.043834,-0.029494]`。相对 official Macro-F1 delta
  的 shift 仅 `+0.001843` 且 CI 跨 0；clear-rater expected set-F1 delta 也为
  `-0.010390`、CI 不跨 0。结论为 `gap_remains`：标注聚合影响局部评分语义，但不能
  解释完整 dev 的总体性能差距。
- 已完成并独立验证 EXP-038 一次性 GoEmotions test gate。EXP-018、EXP-020、
  EXP-025、EXP-029 和 EXP-033 的 test Macro-F1 分别为 `0.196197`、
  `0.488328 +/- 0.008771`、`0.233653`、`0.450652 +/- 0.032175` 和 `0.444675`。
  BERT 比论文报告的 test 参照 `0.46` 高 `0.028328`；EXP-033 未超过 BERT，
  历史 EXP-029 因训练 ontology 失配只保留为显式受限对照。9 个单元的预测、逐标签
  指标、混淆矩阵与哈希均已复算；test 自此视为已消费。
- 已在条件性、非商业本地研究边界下将 IAC 2.0 4forums 作为论坛上下文候选源，并
  完成 `DATA-FCTX-CLEAN-V2` 全量清洗。414,453 帖生成 403,374 个 parent-target 候选，
  403,336 个通过保守 hard filter；539,658 条 quote 的层级和 offset 全部闭合。独立
  验证通过 40 项检查且 mismatch 为 0，私有文本、源 ID 与 HMAC key 均未进入 Git。
- 已完成并独立验证 `DATA-FCTX-DEDUP-V2`。403,336 个 eligible pairs 中保留
  403,183 个，仅 139 个精确重复和 14 个纯格式差异被自动去除；68,552 条词法/语义
  近邻边形成 249 个待复核簇、涉及 1,308 条候选，semantic-only 自动删除为 0。
  HNSW mean recall@64=`0.992554`，高于冻结门槛 0.98，69 项独立检查全部通过。
- 已冻结 `DATA-FCTX-LABEL-V1`：10 种不合并的原子情绪候选加 `neutral`，先锁定
  target-only 判断，再展示 discussion title、direct parent 和 target quote 得到 contextual
  判断；sarcasm 独立记录，不采集强度或 secondary label。私有 view 与 annotation sidecar
  已建立 JSON Schema。
- 已冻结 `DATA-FCTX-SAMPLE-V1`：120 个独立 calibration cases 包含 80 个受约束随机样本
  和 4 组各 10 个 diagnostic samples，另设 24 个相隔至少 72 小时的 blind repeats。
  固定 seed、每 thread/review cluster 至多一例、reserve 仅替换 `unusable`，并预登记
  一致性、context sufficiency、unclear 和 other-emotion 复核门。最终训练 ontology 仍待
  pilot 结果。
- 已完成并独立验证 `DATA-FCTX-SAMPLE-V1` metadata-only preflight。403,183 条候选中
  确定性抽取 120 条主样本和 60 条备用样本，180 条样本与 180 个 thread 均全局唯一；
  sarcasm、hostility-affect、short-context 和 distinct-quote 诊断池分别有 662、1,153、
  1,757 和 37,233 条候选。独立 verifier 通过 45 项检查且 mismatch 为 0；公开报告不含
  论坛文本、源 ID、HMAC ID 或逐样本标签，24 条 blind repeats 按协议暂不生成。
- 已为冻结的 120 条主样本导出本机私有 staged views，并完成独立数据库重建。视图按
  `0001.json` 至 `0120.json` 排列，89 条包含 target quote，共 164 个顶层引用块；独立
  verifier 通过 34 项检查，mismatch、schema problem 和隐藏元数据违规均为 0。私有目录
  权限为 `0700`、文件为 `0600`。
- Human Pass 1 已完成全部 120 条 Stage A/Stage B 并固定只读 checkpoint。由于 pilot 暴露
  明显数据缺陷，项目在模型语义比较前登记 amendment，取消 blind repeats 并将本轮改为
  探索性诊断。Stage B 三方精确一致仅 21/120，106 条至少有一次阶段分歧；Human 的
  `other_emotion` 主要为 `approval/disapproval`，说明当前设计混入了 stance 任务。
- 已冻结、运行并独立复核 `DATA-FCTX-PUBLIC-AUDIT-V1`。KOTE train/validation 通过 C0
  训练/控制候选门，Hotter and Colder 因无打包文本、实时 hydration 和 schema 风险阻塞，
  Weibo Emotion Cause Corpus 仅通过 C1 情绪原因辅助门；独立 verifier 35/35 项通过。
  本轮未下载 KOTE test、未 hydration、未训练，也未采用任何候选为最终论文数据集。
- 审计完成后已明确排除 Hotter and Colder。保留冻结审计和本地忽略的上游快照仅为追溯，
  不再 hydration，也不进入训练、模型选择、评估或论文结果。
- 已执行并独立验证 `DATA-WEIBO-TASK-V1`，将 EClass 作为边界明确的中文论坛式社交文本
  主任务代理。8,540 条七分类 paired-view 样本划分为 train 5,995、validation 1,272 和
  sealed test 1,273；split 按 leakage component 隔离，test labels 保持私有密封。
- 已完成 EXP-041 train-only Stage 2 模型栈预检。M1/M2 执行路径、Qwen3-4B BF16 的
  paired prompt/thinking/parser 路径，以及 16-block LoRA 两步更新和 checkpoint 重载均
  通过；Qwen 严格格式有效率为 37/42，LoRA 峰值内存 8.65 GB。独立 amendment 通过
  16/16 项、0 mismatch。该结果不含分类准确率，validation/test 均未访问。
- 已完成并独立验证 EXP-042 Stage 3 train/dev 基线。M0 Macro-F1 为 `0.116913`；M1
  target/context 为 `0.338267`/`0.271504`；M2 target/context 三 seed 为
  `0.594925 +/- 0.012919`/`0.594219 +/- 0.012046`。配对 context delta 为
  `-0.000706 +/- 0.024737`，达到实际并列条件，按预注册规则选择 target-only；test 未读取。
- 已完成并独立验证 EXP-043 Stage 4 frozen Qwen 2x2。A/B/C/D Macro-F1 分别为
  `0.308684`/`0.281480`/`0.333818`/`0.317997`，按冻结主指标选择 target-only +
  reasoning on。观测到的平均 context contrast 为 `-0.021512`、95% CI
  `[-0.037515,-0.006905]`；平均 reasoning effect 为 `+0.030825`、95% CI
  `[+0.007225,+0.057146]`，但 Accuracy、Weighted-F1、格式有效率和成本没有同步改善。
  5,088 次 validation 生成经独立 verifier 10/10 通过，test 未读取。
- 已完成并独立验证 EXP-044 Stage 5 train-only 本地成本预检。Qwen3-4B BF16 的
  200-step LoRA 训练耗时 `355.254 s`、稳态中位吞吐 `0.575 step/s`、峰值内存
  `8.679 GB`；112 个插入点、224 个 adapter tensors、7,340,032 个可训练参数和
  checkpoint 重载均通过，独立 verifier 13/13。按 1.25 安全系数，2 epochs x 3 seeds
  顺序训练投影为 `21.72 h`，3 epochs 为 `32.58 h`，均不含 validation 生成和分析。
- EXP-045 在 train-only 初始化审计时发现 tokenization contract 错误并停止：
  Transformers 5.14.1 返回 `BatchEncoding`，旧实现误把两个字段名当作 token IDs；未开始
  模型推理，validation/test 均未读取。修正版 EXP-046 已完成并独立验证 80 次 train-only
  生成。singleton 与固定顺序 batch 8 重放均为三层 `16/16` 一致，但改变共同批次后最终
  标签仅 `14/16`、raw output 仅 `5/16` 一致；按预注册规则冻结 Stage 5 reasoning-on
  singleton 推理，独立 verifier 12/12 通过。
- EXP-047 Stage 5 generative LoRA Major 已完成 seed 42 的正式 train-only 门。Qwen3-4B BF16
  按冻结协议训练 2 epochs，共 `11,990` 次 micro-iterations、`160,736` 个训练 tokens，耗时
  `20,577.547 s`（约 5 小时 43 分）、峰值 MLX 内存 `8.804 GB`；epoch-2 adapter 含
  224 个 tensors、112/112 个非零 `lora_b` tensors 和 7,340,032 个可训练参数，并通过独立
  load-forward 核验。随后两次全新进程、16 条 train-only singleton replay 的 final label、
  parser state 和 raw output 均为 `16/16` 一致，严格 parser 为 `16/16`。训练与回放 verifier
  的两个阶段状态缺陷均以 amendment 保留并修正，没有重训或重跑推理。该 train-only 门
  没有读取 validation/test，也不单独支持 LoRA 分类性能结论。
- EXP-047 seed 43 已完成相同的正式 train-only 门。首次受限启动因无法访问 Metal，在首个
  training iteration 前以状态 `-6` 停止；失败记录原样保留，随后以独立 attempt 2 目录重新
  执行，没有覆盖或续训。attempt 2 完成 2 epochs、`11,990` 次 micro-iterations 和 `160,736`
  个训练 tokens，耗时 `20,548.721 s`（约 5 小时 42 分）、峰值 MLX 内存 `8.804 GB`；最终
  adapter load-forward 及两次 16 条 train-only singleton replay 均通过独立 verifier，final
  label/parser/raw 为 `16/16` 一致。
- EXP-047 seed 44 已完成第三组正式 train-only 门：2 epochs、`11,990` 次 micro-iterations、
  `160,736` 个训练 tokens，耗时 `20,415.953 s`（约 5 小时 40 分）、峰值 MLX 内存
  `8.805 GB`。最终 adapter 的 224 个 tensors、112/112 个非零 `lora_b` tensors、7,340,032
  个可训练参数与独立 load-forward 均通过；两次全新进程、16 条 train-only singleton replay
  的 final label/parser/raw 均为 `16/16` 一致，parser-valid 也均为 `16/16`。至此三个 seed
  的训练与回放门全部通过；这些 train-only 产物本身不构成分类性能结论。
- EXP-047 matched singleton validation 已完成并独立验证。无 adapter reference 的
  Macro-F1/Accuracy/Weighted-F1 为 `0.333598`/`0.222484`/`0.207222`；LoRA seeds 42/43/44
  的 Macro-F1 为 `0.552028`/`0.548289`/`0.587096`，均值 `0.562471 +/- 0.021408`，相对
  reference 提高 `+0.228873`，三个 group-bootstrap 95% CI 均高于 0。三 seed parser-valid
  均为 `100%`，但 LoRA 均值仍比 EXP-042 M2 target-only `0.594925` 低 `0.032454`。
  独立 verifier 重建 5,088 次生成并通过 10 类检查、0 mismatch；sealed test 未读取。
- EXP-048 冻结 dev 错误分析已完成并独立验证。分析复算 EXP-047 reference、三个 LoRA seed
  与 EXP-042 三个 encoder seed 在同一 1,272 条 validation 上的 7 份预测，并在读取原文前
  冻结抽取 48 条案例。reference 的 116 条输出失败只解释 LoRA Accuracy 增益中的
  `+0.070755`；在另外 1,156 条 reference 输出有效的样本上，LoRA Accuracy 仍从
  `0.244810` 提高到 `0.779700`，说明提升不只是格式修复。LoRA 与 encoder 的 Accuracy
  仅差 `-0.013103`，但 Macro-F1 仍差 `-0.032454`，主要劣势位于 sadness、neutral、anger
  和 positive；LoRA 跨 seed 最终标签一致率也低于 encoder（`0.884` vs `0.943`）。48 条
  定性案例主要暴露标签/数据不确定性、ontology 重叠、隐含情绪和 no_emotion 边界；这些
  计数来自目的性抽样，不能外推为总体发生率。sealed test 未读取，未重训或重新推理。
- EXP-049 已按 TEST-READY 合同完成一次性正式 test 并独立验证。九个冻结单元均先完成
  1,273 条预测，再一次性打开标签；encoder 与 LoRA 三 seed 的 Macro-F1 分别为
  `0.649621 +/- 0.007365` 与 `0.636612 +/- 0.021429`，matched no-adapter Qwen 为
  `0.316921`。LoRA 相对 matched Qwen 提高 `+0.319691`，95% group-bootstrap CI
  `[+0.274779,+0.362068]`；LoRA 相对 encoder 为 `-0.013009`，CI
  `[-0.045671,+0.024011]`，因此不能把小幅点估计差写成已确定的 encoder 优势。独立
  verifier 复算 11,457 条预测、0 mismatch；Weibo test 自此为 `Frozen / Verified /
  Consumed`，不得用于调参、选 seed 或重跑候选。

### 尚未完成

- Stack Overflow C0 主线的数据阶段、EXP-050 共享预检与 EXP-051 M1 三 seed validation 已
  完成并独立验证。M1 固定 0.5 Macro-F1 为 `0.607297 +/- 0.012628`，per-seed 共享阈值
  Macro-F1 为 `0.617254 +/- 0.011084`；后者同时将 strict subset accuracy 从
  `0.773611` 降至 `0.760648`，不是全面改善。三个 seed 的 `surprise` F1 均为 0，六标签
  主指标与五标签敏感性结果都已保留。EXP-052 frozen Qwen + linear head 的 seeds 42/43/44
  及其只读三 seed aggregate 均已独立验证。M2 固定 0.5 与 per-seed 共享阈值 Macro-F1
  分别为 `0.151553 +/- 0.027647` 和 `0.318889 +/- 0.038085`；共享阈值同时把 strict
  subset accuracy 从 `0.560185` 降至 `0.490741`、把 hamming loss 从 `0.087269` 提高至
  `0.121142`，因此校准不是全面改善。匹配 M1 的固定/共享阈值 paired Macro-F1 delta
  为 `-0.455744 +/- 0.035919`/`-0.298365 +/- 0.039425`，三个 seed 的 delta 均为负。
  `surprise` 三 seed F1 均为 0；`joy` 的共享阈值 F1 为 `0.206770 +/- 0.187595`，并在
  seed 44 降至 0，显示低频标签之外仍有明显不稳定性。Aggregate verifier 通过 `85/85`，
  当前 EXP-052 回归测试通过 `36/36`；它没有读取或拼接逐行预测，也没有将 seed 42 的
  完整特征提取耗时与 seeds 43/44 的 cache-only 耗时做误导性平均。该结果只支持当前
  final-layer last-token pooling + linear head 的稳定弱表现，不能推出 Qwen 没有情绪信息或
  Classification LoRA 不会改善。EXP-053 M3 的 train-only 资源门已独立验证：32/32 次更新
  loss 有限，112/112 个 `lora_b` 均非零，checkpoint 重载误差为 0；训练/回放阶段峰值为
  `8.674`/`8.376 GB`。随后 formal seed 42 完成 2 epochs、6,720 steps，选中 epoch 2：固定
  0.5 Macro-F1=`0.602846`，共享阈值 `0.40` 下 Macro-F1=`0.637786`、Micro-F1=`0.758315`、
  strict subset accuracy=`0.755556`、hamming loss=`0.050463`，component-bootstrap 95% CI
  `[0.548975,0.709997]`。相对 matched M2 seed 42，共享阈值 Macro-F1 delta=`+0.312857`，
  95% CI `[+0.223280,+0.388544]`；该增量只支持 classification interface 下 LoRA 适配收益。
  正式运行耗时 `3.821 h`、峰值 `8.702 GB`。第一次 verifier 完整回放后因旧字段名仅通过
  `135/136`，Failed 记录原样保留；schema-only amendment 后完整重放通过 `148/148`，概率
  误差为 0。Formal seed 43 随后按独立授权完成相同的 2 epochs、6,720 steps，并同样选中
  epoch 2：固定 0.5 Macro-F1=`0.659318`，共享阈值 `0.35` 下 Macro-F1=`0.663515`、
  Micro-F1=`0.756696`、strict subset accuracy=`0.754167`、hamming loss=`0.050463`，
  component-bootstrap 95% CI `[0.570351,0.732537]`。相对 matched M2 seed 43，共享阈值
  Macro-F1 delta=`+0.309922`，95% CI `[+0.208105,+0.390880]`；独立 checkpoint replay
  概率误差为 0，`143/143` 项检查通过。运行耗时 `3.544 h`、峰值 `8.699 GB`。Formal seed 44
  也按独立授权完成相同训练并选中 epoch 2：固定 0.5 Macro-F1=`0.598812`，共享阈值 `0.25`
  下 Macro-F1=`0.660795`、Micro-F1=`0.763713`、strict subset accuracy=`0.741667`、hamming
  loss=`0.051852`，component-bootstrap 95% CI `[0.584731,0.727760]`。相对 matched M2
  seed 44，共享阈值 Macro-F1 delta=`+0.382650`，95% CI `[+0.298126,+0.455866]`；完整
  checkpoint replay 概率误差为 0，`148/148` 项检查通过。运行耗时 `3.352 h`、峰值
  `8.702 GB`。随后只读 M3 三 seed aggregate 以 arithmetic mean + sample std
  (`ddof=1`) 冻结并通过独立复算 `124/124`。固定 0.5 / 各 seed 共享阈值的 Macro-F1
  分别为 `0.620325 +/- 0.033829` / `0.654032 +/- 0.014135`；共享阈值下相对 matched
  M2 的 Macro-F1 delta 为 `+0.335143 +/- 0.041168`，三个 seed 均为正。相对 M1 的共享
  Macro-F1 delta 为 `+0.036778 +/- 0.003154`，但五标签敏感性 delta 为
  `-0.033981 +/- 0.008620`，Micro-F1 与 Weighted-F1 delta 也分别为
  `-0.011564 +/- 0.006039` / `-0.008242 +/- 0.001563`；表面 Macro-F1 优势由只有 7 个
  validation 正例的 `surprise` 驱动，不能写成 M3 全面优于 encoder。聚合没有读取或拼接
  逐行预测，test 未访问。EXP-053 validation family 至此完成。随后 EXP-055 在冻结的六份
  M1/M3 validation 预测上完成错误分析：M3 的六标签 Macro-F1 比 M1 高
  `+0.036778`，但去除仅 7 个正例的 `surprise` 后低 `-0.033981`，Micro-F1、
  Weighted-F1、subset accuracy 和 hamming loss 也均未超过 M1。三个 seed 中 M1-only
  exact-correct 平均 `56.00` 条、M3-only 平均 `48.67` 条，whole-vector oracle 平均只需
  选择 M3 `8.33%` 的样本即可相对 M1 获得 `+0.136394` 六标签 Macro-F1 上界，因此冻结的
  router headroom gate 通过。45 条目的性案例复核主要指向标签 ontology 重叠、弱情绪与
  neutral 边界、隐式情绪及模型/表征限制；该小样本不代表总体发生率。Attempt 2 在只修正
  verifier 的 Markdown 空白归一化后通过 `220/220`。这只授权另行登记 train-OOF router
  可行性实验，不证明可部署 router 有效。随后 EXP-054 M4 Qwen Generative LoRA 完成三 seed
  validation：seeds 42/43/44 均选中 epoch 2，Macro-F1 为
  `0.589699`/`0.658405`/`0.597443`，聚合为 `0.615182 +/- 0.037632`；Micro-F1、
  Weighted-F1 与 strict subset accuracy 分别为 `0.755144 +/- 0.009373`、
  `0.745278 +/- 0.016138` 与 `0.776389 +/- 0.013679`。全部 validation 输出均通过 strict
  parser，每 seed 两次全新进程、每次 60 条 replay 都逐条一致；三个 seed verifier 各通过
  `92/92`，aggregate verifier 通过 `33/33`。相对同 seed M3，M4 Macro-F1 delta 为
  `-0.038850 +/- 0.030200` 且 3/3 seed 为负，但 subset accuracy delta 为
  `+0.025926 +/- 0.017859`。该结果只比较端到端 formulation，不能把差异单独归因于
  generation。首次 preflight 的 Metal OOM 与对象生命周期修正均已留档；修正后 preflight
  通过 `26/26`。M1-M4 validation 主线至此完成。EXP-056 随后按统一 TEST-READY 合同完成
  12 个冻结单元的一次性正式 test，并在全部预测 hash-sealed 后才打开标签。M1/M2/M3/M4
  test Macro-F1 分别为 `0.567459 +/- 0.007814`、`0.295226 +/- 0.020587`、
  `0.613804 +/- 0.025733` 和 `0.547823 +/- 0.015312`。M3-M2 的 95% component-bootstrap
  CI 完全高于 0；M3-M1 六标签差为 `+0.046345`，但 CI `[-0.008674,+0.089730]` 跨 0，
  去除仅 7 个 test 正例的 `surprise` 后点估计为 `-0.010735`。M4-M3 六标签差为
  `-0.065981`，CI `[-0.107869,-0.011312]`。独立 verifier 通过 `29/29`，没有 test 后选择
  或调参；Stack Overflow test 自此已消费。
- RQ-S3 系统支线为 EXP-058 OOF -> EXP-059 calibration/selective prediction -> EXP-060
  pre-Qwen router。EXP-058 的 3,360-row paired train OOF 已通过 `26,989/26,989` 终验；
  EXP-059 也已完成。两 family 均保留 identity calibration；M1/M3 selected OOF Macro-F1
  为 `0.598919`/`0.637843`，五标签结果为 `0.718703`/`0.710509`。Abstention gate 在 M1
  约 90% coverage、M3 约 80% coverage 通过，但 M1 的风险下降 bootstrap interval 跨过
  20% 门，M3 更稳。Whole-vector oracle 仅在 9.32% rows 选择 M3，却留下六标签/五标签
  `+0.109930`/`+0.087472` Macro-F1 headroom；attempt-2 verifier `4,684/4,684`。EXP-060
  正式 nested OOF 现已 `Verified Pass`：选中 `logistic_router` 的 nominal 15% 调用点，实际
  调用 `501/3,360` 条（`14.9107%`），六标签 Macro-F1 从 M1-only 的 `0.598919` 提高到
  `0.639087`（`+0.040168`），五标签 Macro-F1 delta=`+0.006097`，Hamming-loss
  delta=`-0.004365`；相对同为 nominal 15% 的最佳 heuristic，Macro-F1 再高 `+0.013896`。
  2,000 次 duplicate-component bootstrap 的六标签 Macro-F1 gain CI 完全高于 0，但五标签
  gain CI 跨 0；独立 verifier 通过 `4,412/4,412`。该结果全程只使用 train OOF，是一个冻结
  seed-42 模型对的开发证据，不是独立 test、跨 seed 或普遍部署收益结论。
- Weibo 主任务从数据协议、dev 基线、Qwen 2x2、LoRA 三 seed、冻结错误分析到 EXP-049
  一次性正式 test 已形成完整行为证据链。后续只允许对既有 test 预测做预登记的只读分析，
  不再利用该 split 调参、选 seed 或补跑模型。尚需完成系统演示、论文表格与结果归档；
  IAC 2.0 只保留为 challenge 候选，KOTE 只保留为可选 C0 控制，Hotter 已排除。
- 已有传统基线、编码器、一次性正式 test、冻结错误分析和 GoEmotions 本地 LLM
  prompt/decoder 2x2、LoRA 与跨模型错误结构证据；Base/post-trained probe 的首次
  正式运行触发资源门，尚无 Verified 表征结论。尚未完成自建数据集、广义鲁棒性
  实验或可运行系统。
- GoEmotions 的 BERT-base-cased dev 与正式 test 基线已经冻结；RoBERTa alternative
  尚未执行，但不再为关闭当前复现阶段而补跑。EXP-018 与 EXP-020 不再事后调参，
  后续阈值、类别权重或模型变体必须在新的开发数据上使用新实验编号。
- Qwen3-1.7B Base/post-trained 本地环境、资源试跑、parser 修复门和 EXP-025/026
  full-dev 2x2 已完成并验证；EXP-027 probe smoke 已通过，EXP-028 正式 matched probe
  因 wall-time 门失败并保留。EXP-029 三 seed LoRA、EXP-030 错误分析、EXP-031
  推理消融、EXP-032 加速预检及 EXP-033 seed-42 target-aligned 正式训练与 dev
  validation 已完成并验证；EXP-034 进一步确认训练共现切片也没有目标共现输出，
  EXP-035 则确认这些 official hard targets 全部来自跨标注者聚合，EXP-036 完成
  174 条 dev 冲突切片的逐标注者评分，EXP-037 已把相同诊断扩展到完整 dev 并确认
  总体差距仍存在，EXP-038 已完成正式 test。EXP-033 improvement gate 未通过；
  正式 probe 与 EXP-033 seeds 43/44 未执行，也不作为当前 GoEmotions 阶段的关闭条件。

## Evidence Standard

[`evidence-log.md`](evidence-log.md) 是本项目面向 CV、SOP 和推荐信的事实来源。只有状态为 `Verified`，且能由代码、日志、数据说明、报告或导师材料复核的条目，才能写成对外成果。

即使新方法没有超过基线，只要问题定义清楚、实验严谨、失败原因分析充分，仍可形成可信的申请项目。

## Core Files

- [`opening-report.md`](opening-report.md): 开题报告研究内容草案、技术路线、创新点与范围控制。
- [`research-roadmap.md`](research-roadmap.md): 从开题到论文交付的阶段路线和通过条件。
- [`hypotheses.md`](hypotheses.md): 当前待验证假设、反证条件和对应实验。
- [`evidence-log.md`](evidence-log.md): 项目事实、实验产物和申请证据台账。
- [`stack-overflow-c0-experiment-report-2026-08-16.md`](stack-overflow-c0-experiment-report-2026-08-16.md): Stack Overflow C0 六标签主实验的数据协议、M1-M4 validation/test、错误分析、资源、失败记录和结论边界。
- [`experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md`](experiments/stack-overflow-emotion-gold/protocols/data-so-task-v1.md): 当前 Stack Overflow C0 主线的来源、六标签重建、重复组件划分、低支持标签和 test gate 冻结合同及执行结果。
- [`experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json`](experiments/stack-overflow-emotion-gold/reports/data-so-task-v1.json): 4,800 行数据构建、标签、重复组件、split 与隐私边界的聚合结果。
- [`experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json`](experiments/stack-overflow-emotion-gold/reports/data-so-task-v1-verification.json): `DATA-SO-TASK-V1` 的 53 项独立复算结果与 test 封存状态。
- [`data/stack-overflow-emotion-gold/task-v1.manifest.json`](data/stack-overflow-emotion-gold/task-v1.manifest.json): 当前任务的固定来源、公开/私有产物哈希与 sealed test manifest。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-050-shared-model-preflight/REPORT.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-050-shared-model-preflight/REPORT.md): M1-M4 共享 train-only 执行门、匹配初始化、LoRA 插入、严格 parser、资源和失败尝试记录。
- [`experiments/stack-overflow-emotion-gold/protocols/exp-051-m1-roberta.md`](experiments/stack-overflow-emotion-gold/protocols/exp-051-m1-roberta.md): M1 RoBERTa 三 seed 合同、seed-42 CPU recovery 与结论边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/VERIFICATION-SUMMARY.md): EXP-051 seed-42 validation 指标、独立复算和 MPS 失败留档。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-43/VERIFICATION-SUMMARY.md): EXP-051 seed-43 validation 指标、独立 checkpoint 重放与两 seed 描述性边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-44/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu/seed-44/VERIFICATION-SUMMARY.md): EXP-051 seed-44 validation 指标、独立 checkpoint 重放和三 seed 聚合入口。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-three-seed-validation/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-three-seed-validation/VERIFICATION-SUMMARY.md): EXP-051 M1 三 seed validation 均值、样本标准差、阈值权衡、低支持标签失败与 test 边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-42/VERIFICATION-SUMMARY.md): EXP-052 frozen Qwen + linear head seed-42 validation 指标、精确 head 回放、70 项独立检查与单 seed 结论边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-feature-cache-reuse-gate/VERIFICATION-SUMMARY.md): EXP-052 seed-42 hidden-state cache 的只读复用边界、74 项独立检查和后续 seed 授权限制。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-43/VERIFICATION-SUMMARY.md): EXP-052 seed-43 只读 cache consumer、fresh linear head、validation 指标、99 项独立检查与两 seed 结论边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen/seed-44/VERIFICATION-SUMMARY.md): EXP-052 seed-44 只读 cache consumer、fresh linear head、validation 指标、104 项独立检查与 aggregate 前结论边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-052-m2-frozen-qwen-three-seed-validation/VERIFICATION-SUMMARY.md): EXP-052 M2 三 seed validation 均值、样本标准差、匹配 M1 paired delta、资源边界与 85 项独立检查。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2/VERIFICATION-SUMMARY.md): EXP-053 M3 train-only 参数更新、checkpoint 回放、阶段内存、正式训练时间投影、公私边界与 102 项独立检查。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-42/VERIFICATION-SUMMARY-ATTEMPT-2.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-42/VERIFICATION-SUMMARY-ATTEMPT-2.md): EXP-053 M3 formal seed-42 validation、matched M3-M2 增量、完整 checkpoint 重放、验证修复留档与 148 项独立检查。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-43/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-43/VERIFICATION-SUMMARY.md): EXP-053 M3 formal seed-43 validation、matched M3-M2 增量、完整 checkpoint 重放、两 seed 描述性边界与 143 项独立检查。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-44/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-44/VERIFICATION-SUMMARY.md): EXP-053 M3 formal seed-44 validation、matched M3-M2 增量、完整 checkpoint 重放、aggregate 前边界与 148 项独立检查。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora-three-seed-validation/VERIFICATION-SUMMARY.md): EXP-053 M3 三 seed validation 均值、matched M2/M1 descriptive delta、低支持 `surprise` 敏感性、资源边界与 124 项独立检查。
- [`experiments/stack-overflow-emotion-gold/error-analysis/runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/error-analysis/runs/exp-055-m1-m3-validation-error-analysis/VERIFICATION-SUMMARY.md): EXP-055 的 M1/M3 全量 validation 错误互补性、whole-vector oracle、45 条目的性复核、router headroom 门与 220 项独立检查。
- [`experiments/stack-overflow-emotion-gold/protocols/exp-054-m4-qwen-generative-lora.md`](experiments/stack-overflow-emotion-gold/protocols/exp-054-m4-qwen-generative-lora.md): EXP-054 的生成式监督、严格 parser、checkpoint selection、replay、资源和 M4-M3 结论边界。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-054-m4-generative-lora-preflight-attempt-1/attempt-failure.json`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-054-m4-generative-lora-preflight-attempt-1/attempt-failure.json): 首次 preflight 的 Metal OOM、停止位置和只修正对象生命周期的恢复记录。
- [`experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-054-m4-generative-lora-three-seed-validation/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-054-m4-generative-lora-three-seed-validation/VERIFICATION-SUMMARY.md): EXP-054 M4 三 seed validation、M4-M3 配对差值、格式/重放稳定性、资源边界与 33 项 aggregate 检查。
- [`experiments/stack-overflow-emotion-gold/test-gate/protocols/exp-056-unified-frozen-test-gate.md`](experiments/stack-overflow-emotion-gold/test-gate/protocols/exp-056-unified-frozen-test-gate.md): EXP-056 的 12 单元统一 TEST-READY 协议、访问顺序、指标、bootstrap、资源和结论边界。
- [`experiments/stack-overflow-emotion-gold/test-gate/configs/exp-056-test-ready.json`](experiments/stack-overflow-emotion-gold/test-gate/configs/exp-056-test-ready.json): 冻结全部 checkpoint/adapter/head、阈值、实现与上游证据哈希的机器可读合同。
- [`experiments/stack-overflow-emotion-gold/test-gate/preflight/exp-056-test-ready-verification-v1.json`](experiments/stack-overflow-emotion-gold/test-gate/preflight/exp-056-test-ready-verification-v1.json): TEST-READY 的 89 项独立检查、未授权状态和 test 未读取证明。
- [`experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/REPORT.md`](experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/REPORT.md): EXP-056 一次性正式 test 的四 family 三 seed 结果、五组冻结比较、资源、执行恢复与结论边界。
- [`experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/results.json`](experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/results.json): 12 个冻结单元的正式指标、逐标签结果、2,000 次 component-bootstrap 与封存记录。
- [`experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/verification.json`](experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/verification.json): 对预测封存顺序、12 个单元、聚合指标、bootstrap、公私边界和无事后选择的 29 项独立检查。
- [`experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/THESIS-TABLES.md`](experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/THESIS-TABLES.md): EXP-057 从 Verified 公开聚合产物生成的 validation、test、对比、逐标签与资源论文表格。
- [`experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2/VERIFICATION-SUMMARY.md): EXP-057 的 748 项独立复算、私有预测未访问和 sealed test-label source 未重开证明。
- [`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-fold-manifest-preflight-attempt-2/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-fold-manifest-preflight-attempt-2/VERIFICATION-SUMMARY.md): EXP-058 的五折共享 manifest、稀有标签平衡、零 component leakage、no-model/train-only 边界与 131 项独立检查。
- [`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-paired-oof-production/REPORT.md`](experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-paired-oof-production/REPORT.md): EXP-058 的十个 OOF fold runs、3,360-row 配对产物、资源、权限事故和结论边界。
- [`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-paired-oof-production/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-paired-oof-production/VERIFICATION-SUMMARY.md): 对五折完整性、source order、logits、隐私、split access 和 paired assembly 的 `26,989/26,989` 终验。
- [`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/REPORT.md`](experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/REPORT.md): EXP-060 正式 train-OOF nested router 的冻结 operating point、通过结论、bootstrap 边界和适用范围。
- [`experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md`](experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md): 对 nested thresholds、scaler/router、调用率曲线、公私边界和 train-OOF-only 声明的 `4,412/4,412` 独立复算。
- [`experiments/tweeteval-emotion/test-gate/README.md`](experiments/tweeteval-emotion/test-gate/README.md): EXP-016 一次性正式 test 结果、受控比较、外部参照与复算入口。
- [`experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/REPORT.md`](experiments/tweeteval-emotion/error-analysis/runs/exp-017-frozen-error-analysis/REPORT.md): EXP-017 全量稳定性、共享错误、受控转移和匿名定性分析。
- [`experiments/goemotions/protocols/data-protocol-v1.md`](experiments/goemotions/protocols/data-protocol-v1.md): GoEmotions 官方多标签数据来源、标签顺序、split 纪律和 test gate。
- [`data/goemotions/manifest.json`](data/goemotions/manifest.json): GoEmotions train/dev 固定快照的来源 revision、SHA-256、规模和数据质量检查。
- [`experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/REPORT.md`](experiments/goemotions/tfidf-ovr-logreg/runs/exp-018-tfidf-ovr-logreg/REPORT.md): EXP-018 简单多标签基线结果、类别诊断和独立验证说明。
- [`experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/REPORT.md`](experiments/goemotions/bert-base/runs/exp-020-bert-base-cased/REPORT.md): EXP-020 BERT-base-cased 三随机种子 dev 复现、逐类诊断、论文边界和独立验证说明。
- [`experiments/goemotions/qwen3-1.7b/README.md`](experiments/goemotions/qwen3-1.7b/README.md): Qwen3-1.7B 配对模型来源、EXP-021 至 EXP-034 的行为实验、probe 门和后续 LLM 实验顺序。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-028-matched-frozen-probe/FAILURE-REPORT.md): EXP-028 资源门失败、诊断结果、独立产物审计和证据边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-029-instruct-lora/REPORT.md): EXP-029 三随机种子 LoRA dev 结果、冻结比较、资源记录和证据边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-031-neutral-ontology-inference-ablation/REPORT.md): EXP-031 三随机种子 neutral ontology 推理消融、冻结判定与 target-aligned retraining 边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-032-acceleration-preflight/verification.json`](experiments/goemotions/qwen3-1.7b/runs/exp-032-acceleration-preflight/verification.json): EXP-032 train-only batch 吞吐与公共前缀 KV cache 等价性预检。
- [`experiments/goemotions/qwen3-1.7b/protocols/exp-033-target-aligned-lora-v3.md`](experiments/goemotions/qwen3-1.7b/protocols/exp-033-target-aligned-lora-v3.md): EXP-033 官方标签对齐重训、V3 wall-time 门、资源门与授权顺序。
- [`experiments/goemotions/qwen3-1.7b/preflight/exp-033-runner-dry-run-verification-v3.json`](experiments/goemotions/qwen3-1.7b/preflight/exp-033-runner-dry-run-verification-v3.json): EXP-033 V3 独立 runner、冻结数据、MLX runtime contract、进程超时门和 train-only config 的 no-model 复算。
- [`experiments/goemotions/qwen3-1.7b/preflight/exp-033-smoke-verification.json`](experiments/goemotions/qwen3-1.7b/preflight/exp-033-smoke-verification.json): EXP-033 50-iteration train-only smoke 的 loss、吞吐、内存、split 边界与 LoRA 权重独立复算。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-033-target-aligned-lora/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-033-target-aligned-lora/REPORT.md): EXP-033 seed-42 正式训练、完整 dev 指标、配对比较、multi-label/neutral 诊断与证据边界。
- [`experiments/goemotions/qwen3-1.7b/runs/exp-034-train-neutral-cooccurrence-diagnostic/REPORT.md`](experiments/goemotions/qwen3-1.7b/runs/exp-034-train-neutral-cooccurrence-diagnostic/REPORT.md): EXP-034 对已见训练共现样本的冻结回放、train-vs-dev 结构诊断与归因边界。
- [`experiments/goemotions/annotation-audit/runs/exp-035-neutral-cooccurrence-annotation-audit/REPORT.md`](experiments/goemotions/annotation-audit/runs/exp-035-neutral-cooccurrence-annotation-audit/REPORT.md): EXP-035 对逐标注者投票、官方聚合复现、上下文可判别性和隐私边界的审计。
- [`experiments/goemotions/disagreement-aware-evaluation/runs/exp-036-dev-rater-aware-diagnostic/REPORT.md`](experiments/goemotions/disagreement-aware-evaluation/runs/exp-036-dev-rater-aware-diagnostic/REPORT.md): EXP-036 对 174 条 dev 冲突切片、7 份冻结预测和逐标注者期望一致度的受控诊断。
- [`experiments/goemotions/disagreement-aware-evaluation/runs/exp-037-full-dev-rater-aware-diagnostic/REPORT.md`](experiments/goemotions/disagreement-aware-evaluation/runs/exp-037-full-dev-rater-aware-diagnostic/REPORT.md): EXP-037 对完整 5,426 条 dev、soft-label Macro-F1、逐标注者一致度和总体差距解释的冻结诊断。
- [`experiments/goemotions/test-gate/REPORT.md`](experiments/goemotions/test-gate/REPORT.md): EXP-038 一次性正式 test 的五组冻结结果、论文参照、资源记录、证据边界和独立验证说明。
- [`experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/REPORT.md`](experiments/goemotions/error-analysis/runs/exp-030-frozen-dev-error-analysis/REPORT.md): EXP-030 跨 BERT、冻结 Qwen 与 LoRA 的 dev 错误结构、匿名定性复核和官方结果边界。
- [`experiments/forum-context/dataset-construction/README.md`](experiments/forum-context/dataset-construction/README.md): IAC 2.0 4forums 的 V2 清洗与去重协议、私有产物边界、聚合结果和独立验证入口。
- [`experiments/forum-context/protocols/data-label-calibration-view-v1.md`](experiments/forum-context/protocols/data-label-calibration-view-v1.md): 论坛原子标签 calibration、两阶段上下文、反讽规则和隐私边界。
- [`experiments/forum-context/protocols/data-annotation-sampling-pilot-v1.md`](experiments/forum-context/protocols/data-annotation-sampling-pilot-v1.md): 120 个独立案例、24 个盲重复、四类诊断富集、固定 seed、替换和接受门。
- [`experiments/forum-context/annotation/README.md`](experiments/forum-context/annotation/README.md): 私有标注 view、sidecar record 与已验证抽样预检的机器可读入口。
- [`experiments/forum-context/annotation/reports/sampling-preflight-v1.json`](experiments/forum-context/annotation/reports/sampling-preflight-v1.json): 120 条主样本、60 条备用样本、诊断池容量和公开隐私声明。
- [`experiments/forum-context/annotation/reports/sampling-verification-v1.json`](experiments/forum-context/annotation/reports/sampling-verification-v1.json): 确定性重放、全局唯一性、私有文件权限和公开隐私边界的 45 项独立核验。
- [`experiments/forum-context/annotation/reports/view-export-v1.json`](experiments/forum-context/annotation/reports/view-export-v1.json): 120 条私有 staged views 的聚合结构、组合哈希与空标注状态。
- [`experiments/forum-context/annotation/reports/view-export-verification-v1.json`](experiments/forum-context/annotation/reports/view-export-verification-v1.json): 逐视图数据库重建、Schema、allowlist、文件权限与公开隐私边界的 34 项独立核验。
- [`experiments/forum-context/annotation/reports/three-source-comparison-v1.md`](experiments/forum-context/annotation/reports/three-source-comparison-v1.md): Human Pass 1 与两个模型来源的聚合比较、任务缺陷和结论边界。
- [`experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md`](experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1.md): KOTE、Hotter and Colder 与 Weibo 的固定版本 schema、样本质量、访问和用途审计。
- [`experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1-verification.json`](experiments/forum-context/public-candidate-audit/reports/public-candidate-viability-audit-v1-verification.json): 35 项独立复算、test/hydration 边界与 Git ignore 核验。
- [`experiments/weibo-eclass/stage-2-preflight/runs/exp-041-model-stack-preflight/verification.json`](experiments/weibo-eclass/stage-2-preflight/runs/exp-041-model-stack-preflight/verification.json): EXP-041 train-only 模型栈、Qwen parser、精确 LoRA adapter 和公私边界的 16 项独立验证。
- [`experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/REPORT.md`](experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/REPORT.md): EXP-042 M0/M1/M2 train/dev 指标、三 seed 波动、配对 context effect 与冻结选择。
- [`experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/verification.json`](experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/verification.json): EXP-042 预测、指标、逐类结果、混淆矩阵、checkpoint、公私边界和 split access 的独立复算。
- [`experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/REPORT.md`](experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/REPORT.md): EXP-043 四条件 validation 指标、冻结选择与 encoder 描述性比较。
- [`experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/verification.json`](experiments/weibo-eclass/stage-4-qwen-2x2/runs/exp-043-frozen-qwen-2x2/verification.json): 5,088 条生成、严格 parser、配对效应、资源、选择规则与 test 边界的独立复算。
- [`experiments/weibo-eclass/stage-5-cost-preflight/runs/exp-044-local-lora-cost-preflight/REPORT.md`](experiments/weibo-eclass/stage-5-cost-preflight/runs/exp-044-local-lora-cost-preflight/REPORT.md): EXP-044 本机 Qwen3-4B LoRA 的真实吞吐、内存、三 seed 成本投影和解释边界。
- [`experiments/weibo-eclass/stage-5-cost-preflight/runs/exp-044-local-lora-cost-preflight/verification.json`](experiments/weibo-eclass/stage-5-cost-preflight/runs/exp-044-local-lora-cost-preflight/verification.json): train-only 抽样、监督 mask、运行时、adapter、成本和公开隐私边界的 13 项独立复算。
- [`experiments/weibo-eclass/stage-5-batch-equivalence/runs/exp-045-batch-equivalence/failure.json`](experiments/weibo-eclass/stage-5-batch-equivalence/runs/exp-045-batch-equivalence/failure.json): EXP-045 的 `BatchEncoding` 初始化失败、停止边界与修复去向。
- [`experiments/weibo-eclass/stage-5-batch-equivalence-v2/runs/exp-046-batch-equivalence-v2/REPORT.md`](experiments/weibo-eclass/stage-5-batch-equivalence-v2/runs/exp-046-batch-equivalence-v2/REPORT.md): train-only singleton、固定 batch 8 与共同批次重排的三层一致性比较和冻结决策。
- [`experiments/weibo-eclass/stage-5-batch-equivalence-v2/runs/exp-046-batch-equivalence-v2/verification.json`](experiments/weibo-eclass/stage-5-batch-equivalence-v2/runs/exp-046-batch-equivalence-v2/verification.json): 抽样、prompt token、strict parser、80 次生成、资源、公私边界和决策的 12 项独立复算。
- [`experiments/weibo-eclass/protocols/exp-047-stage-5-generative-lora.md`](experiments/weibo-eclass/protocols/exp-047-stage-5-generative-lora.md): EXP-047 label-only generative LoRA、三 seed、matched singleton reference、post-adapter replay、比较规则与本机资源边界；作为原始冻结协议保持不改。
- [`experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run.json`](experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run.json): EXP-047 全量 train 渲染、token 边界、三 seed train-only runtime config、模型零执行与 split 访问声明。
- [`experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run-verification.json`](experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-runner-dry-run-verification.json): 私有训练文件、源码入口、模型/环境哈希、权限、Git ignore、资源算术与公开隐私边界的 11 项独立复算。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-42/verification.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-42/verification.json): seed 42 正式训练 history、adapter、checkpoint、权限、合同、环境和独立 load-forward 的 post-run V2 核验。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-42-replay-verification-v2.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-42-replay-verification-v2.json): 两次 train-only singleton replay 的 parser/final-label/raw-output 一致性、公私边界与 post-run V2 核验。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-43-attempt-2/verification.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-43-attempt-2/verification.json): seed 43 新目录 attempt 2 的正式训练 history、adapter、checkpoint、权限、合同、环境和独立 load-forward 核验；首次 Metal 启动失败另行保留。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-43-replay/verification.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-43-replay/verification.json): seed 43 两次 train-only singleton replay 的独立 tokenization、parser/final-label/raw-output 一致性和公私边界核验。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44/verification.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44/verification.json): seed 44 正式训练 history、adapter、两个 epoch checkpoint、权限、合同、环境和独立 load-forward 核验。
- [`experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44-replay/verification.json`](experiments/weibo-eclass/stage-5-generative-lora/runs/exp-047-stage-5-generative-lora/seed-44-replay/verification.json): seed 44 两次 train-only singleton replay 的独立 tokenization、parser/final-label/raw-output 一致性和公私边界核验。
- [`experiments/weibo-eclass/protocols/exp-048-frozen-dev-error-analysis.md`](experiments/weibo-eclass/protocols/exp-048-frozen-dev-error-analysis.md): EXP-048 在原文复核前冻结的分析问题、定量分解、六类目的性抽样、定性代码与证据边界。
- [`experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/REPORT.md`](experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/REPORT.md): EXP-048 的格式归因、逐类差距、跨 seed 稳定性、48 条匿名定性复核与 TEST-READY 边界。
- [`experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/verification.json`](experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/verification.json): 对 7 份冻结预测、1,272 行、9 份 CSV、3 份 JSON、48 条定性编码和私有原文隔离的独立复算。
- [`experiments/weibo-eclass/test-gate/protocols/exp-049-frozen-test-gate.md`](experiments/weibo-eclass/test-gate/protocols/exp-049-frozen-test-gate.md): EXP-049 九个正式评估单元、访问顺序、指标、切片、bootstrap、停止规则和一次性授权合同。
- [`experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/REPORT.md`](experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/REPORT.md): EXP-049 全部冻结 test 指标、三 seed 汇总与三组预注册对比。
- [`experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/verification.json`](experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test/verification.json): 对 1,273 条 test、9 个预测文件、11,457 条逐行预测、全部指标、bootstrap、公私边界和单次标签访问的独立复算。
- [`../../questions/llm-forum-text-emotion-recognition/open-questions.md`](../../questions/llm-forum-text-emotion-recognition/open-questions.md): 会改变项目主线的开放问题。
- [`../../sources/llm-forum-text-emotion-recognition-sources.md`](../../sources/llm-forum-text-emotion-recognition-sources.md): 论文、代码、数据与合规来源地图。
- [`../../papers/llm-forum-text-emotion-recognition/reading-route.md`](../../papers/llm-forum-text-emotion-recognition/reading-route.md): 论文阅读器与复现建议。

## Next Action

1. 保持 EXP-038 与 EXP-049 及其来源模型冻结；两个 test 均已消费，不再用于调参、
   prompt/threshold 修改、checkpoint 选择或补跑候选。
2. `DATA-SO-TASK-V1`、EXP-050 与 EXP-051 M1 三 seed validation 均已通过独立验证；保留
   首次 MPS OOM 及 CPU recovery，并把阈值收益、subset accuracy 代价和 `surprise` 失败
   一并作为 M1 主结果边界。
3. EXP-052 M2、EXP-053 M3、EXP-054 M4、EXP-055 错误分析和 EXP-056 一次性正式 test
   均已独立验证。正式 test 支持 M3 相对 M2 的稳定任务适配收益，但不支持 M3 全面超过
   M1，也不支持 M4 超过 M3。Stack Overflow test 已消费；后续不得据此调参、选择 seed、
   修改阈值或补跑候选，只能对既有冻结预测做另行预登记的只读分析。当前主线转入论文主表、
   系统演示和证据归档，不再增加主模型分支。
4. EXP-058、EXP-059 与 EXP-060 均已完成并独立验证。EXP-060 在 train OOF 上由
   `logistic_router` 以 `14.9107%` 实际调用率通过冻结门，六标签 Macro-F1 gain 为
   `+0.040168`；该证据不外推为独立 test、跨 seed 或普遍部署收益。EXP-060 到此冻结，不再
   调整 feature、router、cutoff 或 operating point；下一步只做系统演示与论文证据归档，或
   另行登记新数据上的独立确认。Stack Overflow ID/context 回连继续要求独立的数据恢复门与
   matched shuffled-context 对照，不与本次 router 支线混用。
5. 不再增加主数据集或主模型分支。保留 EXP-028 的 `Failed` 状态；representation/SAE
   仍是后置可选支线，不能从当前分类分数推出情绪机制。
