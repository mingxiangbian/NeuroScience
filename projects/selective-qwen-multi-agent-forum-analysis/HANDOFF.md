# Selective Qwen Multi-Agent Forum Analysis · HANDOFF

日期：2026-09-05

## 当前接手入口

先读 [当前多智能体方案与硬件决策](docs/current-plan.md)。用户已选择同一主机 **2×RTX PRO 6000 96GB**；下一阶段拟用强主 Agent（优先候选 Qwen3.8-27B）与 8B/12B 级专家，按 GPU 0 主模型、GPU 1 小模型、BF16、无项目 LoRA 的方式准备。

本次仅完成决策记录和方案汇总。云实例尚未创建，具体 GPU 版本/主机、模型 revision、第二专家、解码与成本预算未冻结。新阶段需要独立的 CUDA 环境与模型合同，旧 MLX 预检不能作为其通过证据。

项目沿用本目录，公开内容通过Git整合到main和主checkout。整合前它是仅在 `72d6` worktree 存在的未跟踪文件夹；private数据继续被Git忽略，其有效副本仍留在72d6，尚未通过此次合并迁移。用户删除的 `uestc-fyp-topics-2026-2027` 三个旧选题文件单独记录在提交 `852406a`，合并应包含该删除。原情绪识别实验和主目录无关IELTS文件保持原样；本次不push，也不删除模型或checkpoint。

SQMA-001/002/007 保留历史完成状态，SQMA-003/006/008 保留失败状态；SQMA-004/005 未执行。SQMA-009 的 runner/verifier/tests 已存在，但 config 仍含实现占位项、执行开关为 false，且无 run，因此只能算静态准备；旧文中“尚未实现”的描述已滞后。不自动继续 SQMA-009 或重试旧实验。

后续先整理只包含本项目及所需数据身份的云端输入清单，核对旧路径依赖；再冻结候选模型/调用图和输出合同，完成新的 Agent-Dev 预检及 matched comparison。当前方案继续采用 classifier-free 路线，旧文中的 M1/M3 重训及分类器输入不属于新阶段。

## 历史交接记录 · 截至 2026-09-04

状态：`Independent project / SQMA-001–002 Complete / SQMA-003 attempts 1–2 Failed / SQMA-004–005 Not executed / SQMA-006 Failed / SQMA-007 Complete / SQMA-008 Failed`

本文件用于把“选择性 Qwen 多智能体论坛情绪分析”从现有毕设中独立出来，帮助后续接手者继续设计。当前SQMA-001、SQMA-002与SQMA-007已完成；SQMA-003两次能力预检、SQMA-006 D1能力预检和SQMA-008 C2 locked acceptance均失败；SQMA-004与SQMA-005 formal均未执行。没有网站修改、外部上传或新的模型训练。

SQMA-001 已作为独立的无结果、无训练readiness preflight完成。verification attempt 3通过20/20检查；密封run SHA-256为`3121683d...58db`，verification为`fc2d40d6...0c48`，completion为`6a4326b6...5f75`。attempt 1的动态import错误和attempt 2的HF cache inventory策略过严均已登记；两次都未写verification，attempt 3复用原run，runner未重跑、run未修改。

SQMA-001不支持“strict outputs已产生”或“formal已授权”。它只确认三折计划、依赖、模型文件身份、runtime、访问边界和资源门已通过静态检查。

SQMA-002 已完成并通过独立验证。Public run SHA-256为`552cb5ce...49b6`，verification为`9ba3f6c1...1635`，completion为`38f2d5cd...d688`。它生成folds 0–2共九个密封工件和一个private manifest，总private output约2.29 MB。每fold672行、components为658/654/651；fold3/4 output rows均为0。

SQMA-002诚实记录monolithic private bytes已流式经过，但private row只decode folds 0–2的2,016行；fold3/4各672行未decode。模型、训练、forward、Agent、validation和test均未执行或访问。

SQMA-003 attempt 1与attempt 2均完成了各自计划的144次classifier-free Qwen物理调用，但冻结能力门均未通过，终态均为`Failed`。attempt 1的locked raw schema有效率为`0.2667`，technical fallback为24行，token-cap hit为2；attempt 2仅修订机械输出格式后，相应数值改善为`0.8000`、4行和0。该变化支持“格式遵循显著改善”，不支持“preflight已通过”。

attempt 2仍低于overall `0.98`、per-role `0.95`与technical fallback最多1行的冻结门；其中Evidence、Judge、Single有效率分别为`0.9167`、`0.8750`、`0.6250`。独立verifier以exit code 1停止，两个attempt目录都只有`run-claim.json`和`run.json`，没有`verification.json`或`complete.json`。没有登记或授权自动attempt 3。

SQMA-006以不重叠的新32个Agent-Dev component、v3扁平schema和syntax-only canonicalizer完成120次classifier-free Qwen调用，但冻结能力门仍失败。Locked canonical有效率overall为`0.8958`；Evidence、Critic、Judge、Single依次为`1.0000`、`0.9583`、`0.6250`、`1.0000`，locked S3 fallback为9行。失败项是overall、per-role和fallback；evidence exact-substring、ontology、Single agreement、token cap与`32,309.26 s` full-Tune投影均通过。

SQMA-006 run用时`525.58 s`，generated tokens为3,164，MLX peak约8.43 GB，RSS peak约1.33 GB，private output为220,394 bytes。没有gold、classifier、fold 3/4、validation、test、training或network访问。Shakedown ranks 0–7的已知错误聚合为Critic `json_decode` 2/8和Judge `label_item` 5/8；它只是诊断，不是locked gate分母。该实验没有`verification.json`或`complete.json`，formal matched comparison继续阻断。SQMA-007不是自动恢复，而是此后另行登记的独立C1 shakedown。证据见[public run](runs/sqma-006-d1-canonical-output-preflight/attempt-1/run.json)和[append-only incident](incidents/sqma-006-d1-capability-gate-failure.json)。

SQMA-007 Dev-C1 visible shakedown已完成并独立验证为`Passed`。16个新visible components共执行48次调用；Judge bare raw、六键、array/int/allowlist与rendered合同均为16/16，Evidence/Critic有效率均为`1.0`，semantic repair、unhandled、token cap和normalization events均为0。它只证明ordinary greedy fixed-slot合同可进入新的locked acceptance，不证明准确率、角色贡献或总体合同可靠率。证据见[run](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/run.json)、[verification](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/verification.json)和[completion](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/complete.json)。

SQMA-008 Dev-C2 locked acceptance完成72次调用但终态为`Failed`。Judge raw parse、exact six keys、array和integer均为24/24；1行illegal reference ID使allowed-ID与rendered-valid降为23/24，并产生1个contract error。Evidence/Critic有效率均为`1.0`，fallback、normalization、semantic repair、unhandled和token-cap均为0。Full projection为`10,031.98 s`；实际wall为`272.39 s`，MLX peak约8.42 GB，RSS peak约1.37 GB，private output为126,496 bytes。

SQMA-008没有gold、classifier、fold 3/4或locked raw human access。零容忍合同门失败后没有写`verification.json`或`complete.json`，formal matched comparison仍被阻断。不得查看locked row或利用locked输出修Prompt；下一研究决策是设计并静态审查Judge V3 constrained candidate scorer，不能自动执行。证据见[public run](runs/sqma-008-dev-c2-locked-acceptance/attempt-1/run.json)和[append-only incident](incidents/sqma-008-dev-c2-locked-acceptance-failure.json)。

SQMA-004目前只有fold-3输入materialization的登记设计与静态实现，formal未执行。SQMA-005目前只有producer、scorer、verifier和小型测试的static code preparation；没有config冻结、模型调用、gold scorer结果或独立verification，因此不构成实验已执行或方法结果。

## 1. 项目定位

本项目是独立的第二研究项目，不是现有“基于大模型的论坛文本情感识别”毕设的 Phase D。

原毕设继续作为已经收口的冻结 evidence base，保留 EXP-001–086 中的 Verified、Failed、Stopped 和 Not-executed 混合终态。它不是“所有实验均完成或通过”。新项目只复用其中经过验证的模型与系统资产，并采用独立的研究问题、数据合同、实验编号、证据台账和完成标准。新项目的正负结果都不得回写或改变原毕设终态。

研究问题为：

> 在相同 Qwen 计算预算下，受约束的角色分工是否优于单 Agent 和重复采样；若有效，选择性触发能否以更少 Qwen 调用保留角色流程的主要收益？

当前系统名称：

> **An Uncertainty-Triggered Qwen Multi-Agent System for Topic-Oriented Forum Emotion Analysis**

## 2. 候选复用的只读依赖

source snapshot 为原项目提交 `e70cfcf76744ce8473db1b9744fd258cdbc0c64c`。D0 dependency manifest 已逐项绑定 M1/M3/Router 配置、fold身份、生成模型、runtime和private来源；执行前仍须由 static verifier 重新核对，禁止复制后静默修改。

### 2.1 行为模型

- M1：RoBERTa 多标签 encoder。
- M3：Qwen3-4B Classification LoRA + 六维分类头。
- M3 明确优于当前 frozen-Qwen linear readout；M3 与 M1 没有建立稳健的全面优劣。
- M3 seeds 42/43/44 已保存训练与 OOF 相关工件。

### 2.2 条件路由

- EXP-058–063 已建立 component-disjoint paired OOF、校准和 pre-Qwen Router。
- Router 只使用 M1 概率、熵、阈值距离、标签数和长度等运行时字段。
- seeds 43/44 在同一 train 数据的前瞻性训练 seed 复现中 2/2 通过，M3 调用率约为 15%。
- 现有 Router 学习的是“调用 M3 是否可能相对 M1 获益”，不是通用困难样本检测器，也没有验证样本是否适合角色协作。

### 2.3 表征与系统

- Phase B 已完成 probe、geometry 和 functional ablation；这些结果可作为角色多样性的研究动机，但不能证明多 Agent 必然有效。
- Phase C 已完成 FastAPI、SQLite、论坛来源适配、密封快照、任务队列、成本记录和 staged model subprocesses。
- 固定九任务和 Python Help 400-item 无金标链路已通过相应验证。
- Phase C 的通过不自动覆盖新 Agent 模型、角色调用、生成成本或新资源风险；新项目必须重新验收。

### 2.4 复核入口

- [原毕设 Evidence Log](../llm-forum-text-emotion-recognition/evidence-log.md)
- [原毕设 Research Roadmap](../llm-forum-text-emotion-recognition/research-roadmap.md)
- [Stack Overflow 实验交接](../llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/HANDOFF.md)
- [OOF Router](../llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/README.md)
- [本地论坛话题工作台](../llm-forum-text-emotion-recognition/forum-topic-emotion-web/README.md)
- 现有完整实验汇总（仅在恢复本地 private 归档后可见）：`../llm-forum-text-emotion-recognition/forum-topic-emotion-web/private/reports/pre-thesis-complete-experiment-report-2026-09-01.md`
- [Qwen3 官方 Function Calling 指南](https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md)

## 3. 初期方法构想

### 3.1 基础流程

```text
论坛文本
  → 冻结分类底座 M1 / Router / M3
  → 候选困难样本触发角色化 Qwen 流程
  → Evidence + Appraisal
  → Pragmatics Critic
  → Judge
  → 结构化标签、证据或 abstain
```

第一版最多使用三个样本级 role-conditioned passes：

1. Evidence + Appraisal：提出候选情绪、定位文本证据，并生成结构化评价线索。
2. Pragmatics Critic：检查 stance、技术批评、否定、反讽和弱情绪边界。
3. Judge：读取基础分类和结构化角色输出，接受、修改或拒答。

这些角色由同一个官方 post-trained `Qwen/Qwen3-4B` revision `1cfa9a7208912126459214e8b04321603b3df60c` 串行执行，使用 MLX BF16、`thinking=false`，不加载项目 adapter。它们不是多个独立训练模型或独立认知主体。现有 M3 Classification LoRA 继续作为分类工具，不承担生成式角色输出；完整 train 上训练的 M4 Generative LoRA 也被排除。

### 3.2 核心对照

最低比较包括：

- Frozen classification pipeline：M1 → Router → M3。
- Single Qwen Agent。
- call-count-matched Self-Consistency。
- total-token-budget-matched Self-Consistency。
- Role-diverse Multi-Agent。
- Selective Multi-Agent，仅在 Role-diverse 有稳定信号后执行。
- component-level Random Activation，匹配实际 activated rows 与 Qwen calls，用于检验 Trigger 是否真的选对样本。

Planner 和 Report Agent 属于后续系统层，不进入第一轮样本级 Macro-F1 主比较。

## 4. 启动前必须解决的科学阻塞

### 4.1 数据划分已选择，Pilot 只能来自 Dev

D0 charter 已选择复用 EXP-058 在结果前冻结的 component-disjoint folds：folds 0–2 为 Agent-Dev（2,016 rows / 1,963 components），fold 3 为 Agent-Tune（672 / 657），fold 4 为 Agent-Confirm（672 / 657）。选择规则按 fold ID 固定，不重新搜索划分，也不拆分 component。Pilot 只能来自 Agent-Dev。

### 4.2 现有 OOF 不是天然独立 Confirm

现有 OOF 保证每行预测来自没有训练该行的 fold model，但 Dev 行的旧 fold model 可能训练过未来 Confirm 组件。D0 charter 已选择 strict nested route：Dev 在 folds 0–2 内重新三折 cross-fit，Tune 只使用 folds 0–2 训练的模型，方法冻结后才在 folds 0–3 建立最终 development refit。

fold 4 只能用于对 D0 后冻结的新 Agent 比较做同来源、component-heldout 的前瞻性确认。它的标签 support、Router 折级统计和五折 aggregate 已在旧项目使用，因此不能称 pristine holdout、独立数据集或跨论坛泛化。raw logits 在主工作区存在且身份审计通过，但当前 worktree 未绑定；源 NPZ 含 `gold` 字段，Confirm producer 禁止直接打开，必须先由独立 consumer 生成并密封无 gold 快照。

### 4.3 指标与 abstention

- 原六标签 Macro-F1 默认保持 primary。
- 五标签 Macro-F1 作为 `surprise` 低支持敏感性分析。
- Hamming loss 作为 guardrail，并在协议中冻结 non-inferiority margin。
- Primary 必须覆盖完整 Natural Confirm，不能通过 abstain 删除困难行。
- 若 abstain 回退冻结分类器，必须明确最终标签、coverage 和成本口径。
- Challenge Set 只是由不确定性/分歧富集的诊断切片，不能作为第二个独立 Confirm，也不能代表自然 activation rate。

### 4.4 Trigger 的部署可得性

必须先确定 Agent Activation Gate 位于 M3 前还是 M3 后：

- M1 entropy 和 M1 threshold margin 可以全量获得。
- M1/M3 disagreement、M3空预测和M3 margin只在已经执行M3后可得。
- 不得使用只有 Agent 运行后才能知道的 implicit emotion 或 sarcasm 作为启动 Agent 前的特征。
- 如果为了 Trigger 额外执行 M3，必须把调用和资源计入完整成本。

Selective 是否进入 formal Confirm 必须由 Agent-Tune 上预登记的稳定信号决定。若通过 gate，Full、Selective 和 matched-random 必须在读取 Confirm gold 前同时冻结并一次性产出，不能先看 Confirm 的 Full 结果再决定是否运行 Selective。

Random Activation 按 component 抽样，但必须匹配 Selective 的实际 activated rows 与 Qwen calls，并报告 token 成本；只匹配 component 数不能称为等调用量。只比较 Selective 与 Full 也不能证明 Trigger 具有选择价值。

### 4.5 角色与报告证据

- Exact-substring validator 只能证明 evidence span 来自原文，不能证明它与情绪判断相关。
- Appraisal 字段没有 gold；schema 稳定不等于 appraisal 正确，也不能解释为人的认知过程或模型内部机制。
- 如果声称解释或报告质量提高，需要独立人工 rubric 或其他冻结评价；数字绑定只能验证统计引用，不验证整段叙述是否合理。

## 5. 建议的最低完成集

不要预先占用 EXP-087–096。方向、数据合同和最低比较冻结后，再按实际研究问题编号。

### Stage 0：Project charter 与数据合同

- 已登记单一主问题、角色、生成模型 revision、chat template、thinking mode、schema 和停止规则。
- 已建立只读依赖的逐项路径、commit、SHA-256 与 public/private 边界 manifest。
- 已选择 strict nested route，并完成主工作区 private 来源的 identity/schema audit。
- 已冻结主指标、统计门、Random Activation匹配和preflight硬预算；正式token/wall预算待preflight实测后、Tune前冻结。

### Stage 1：Dev scoped input

- 独立 consumer 从完整private train/fold manifest生成并密封folds 0–2快照。
- 训练producer只能读取这些快照，不能打开完整源文件或任何fold 3/4 row。
- 输入materialization必须有独立verifier、row order/hash和0600权限门。

### Stage 2：strict Agent-Dev production

- folds 0–2 内重新三折 cross-fit，生成 Agent-Dev M1/M3 outputs。
- 首个formal只做三组M1+三组M3；不在同一运行中生成Tune或final-refit成员。
- validation、test 和 fold 3/4 均不可访问；组合 wall硬上限为14小时。

### Stage 3：小规模 Agent preflight

- 仅使用 Agent-Dev 的32个互异 component。
- 验证 JSON、Evidence、角色区分、调用停止和本地资源；不使用 Qwen repair。
- 预检失败即停止，不扩大样本量。

### Stage 4：matched role comparison

- 比较 frozen pipeline、Single Agent、两种匹配口径的 Self-Consistency 和三角色 Multi-Agent。
- 同时报告质量、schema、evidence、calls、prefill/generated tokens、wall time 和资源。
- 正式角色价值不能只依赖点估计；统计规则和 contrast 顺序必须在读结果前冻结。

### Stage 5：selective activation

- 仅在 Agent-Tune 上，Role-diverse 相对 Self-Consistency 有预登记稳定信号后进入 formal Confirm。
- 比较 Full、Selective 和 matched-random activation。
- 若 Full 本身没有正且稳定的收益，不计算没有意义的 gain-retention ratio。

### Stage 6：只读综合

- 汇总正结果、负结果、成本、限制和是否值得进入系统层。
- 如果 Role-diverse 不优于 Self-Consistency，项目仍可完成为可信负结果。

最低完成集包含 strict base production、preflight、matched comparison 和 final synthesis。Selective activation 是条件性实验，只在 Agent-Tune 的 Role-diverse gate 通过后执行；负结果分支不得为了凑实验数量继续运行。

## 6. 条件性扩展，不属于最低完成集

### 6.1 外部 gold

只有项目要声称跨论坛预测泛化更强时才必需。候选数据必须先通过来源许可、标签 ontology、粒度和划分审计。Python Help 400条无 gold 只能用于运行与成本验证。

### 6.2 网站、Planner 与 Report

Agent 方法没有通过 matched comparison 前，不修改现有网站。通过后可以先做32–64条运行等价 smoke，再决定是否增加 Planner、Report、新模式和 Dashboard。

### 6.3 角色拆分与训练

独立 Appraisal、角色 remove-one 消融、角色 LoRA、Mixture-of-LoRA Experts 和 Dense-to-MoE 全部留作条件性研究。第一版三角色方案没有通过前，不进入这些方向。

## 7. 资源与运行提醒

- 当前机器为16 GiB环境，任何时刻只允许一个重模型 resident；角色按顺序执行。
- 既有 Weibo no-adapter reference 对1,272条推理耗时79,098.411秒，约62秒/条；结构化短输出可能更快，但不能据此假设 Agent 成本很低。
- preflight 固定32个 component、最多144次 Qwen调用、4小时 wall、10 GB MLX peak和12 GiB RSS；critical-memory、OOM/kill或连续swap-thrashing触发即停。正式规模预算只能依据preflight实测投影。
- 所有调用必须记录模型 revision、prompt、thinking mode、input/prefill/generated tokens、latency、repair、fallback 和完整任务成本。

## 8. 禁止事项

在用户正式批准 Project charter 前：

- 不创建实验编号、protocol、数据 split 或正式输出目录。
- 不访问或重新使用原毕设已消费的 validation/test 结果进行选择。
- 不下载、上传或标注新的外部数据。
- 不修改原论坛网站、M1/M3、Router 或原实验工件。
- 不训练角色 LoRA，不实施 MoE，不启动生成式 Agent 运行。
- 不把计划中的 Agent、泛化或系统能力写成已完成成果。

## 9. 接手后的第一个动作

1. 阅读本文件、README、D0数据合同以及SQMA-003、SQMA-006、SQMA-007和SQMA-008的public终态证据；不要把runner完成误写成verification通过。
2. 保持SQMA-003 attempts 1–2、SQMA-006和SQMA-008为`Failed`；SQMA-007是当前唯一通过的生成合同shakedown，但其16个visible samples不能替代C2 locked acceptance。
3. 下一步只设计并静态审查Judge V3 constrained candidate scorer。不得查看SQMA-008 locked row、根据locked输出修Prompt、自动重跑SQMA-008或直接进入formal comparison。
4. SQMA-004与SQMA-005均保持未执行。现有SQMA-005代码和tests只属于static preparation，不能据此读取fold 3、运行模型或启动gold scorer。
5. 若未来另行授权完整matched comparison，Tune结果仍只能作为development gate，不能替代fold 4 Confirm或外部泛化证据。

## 10. 当前开放决策

- 项目最终名称和是否保持当前候选题目。
- preflight 后的正式token、wall-time、storage和generation-seed重复预算。
- 是否在后续扩展中另设人工评价者；最低完成集不评价evidence relevance或Report质量。
- 是否在未来另立外部gold泛化阶段；当前最低完成集不作跨论坛泛化主张。
- 项目取得方法证据后是否与原毕设共同展示；研究与证据台账仍保持独立。

## 11. 完成口径

该项目不以“多 Agent 必须提高分数”为完成条件。满足以下要求即可形成可信成果：

- 数据、Prompt、角色、预算和评价边界在结果前冻结。
- Role-diverse 与两种预算匹配的 Self-Consistency 完成公平比较。
- Selective 只在有前置信号时执行，并与 matched-random activation 比较。
- 结果同时报告预测质量、证据/格式可靠性和真实计算成本。
- 负结果按预登记分支收口，不用更复杂 Agent 或更换数据集追分。
- 所有主张都能回溯到代码、配置、保存输出和独立验证。
