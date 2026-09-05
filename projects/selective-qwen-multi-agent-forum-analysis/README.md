# Selective Qwen Multi-Agent Forum Analysis

## 当前方案 · 2026-09-05

已确认硬件：**同一主机 2×NVIDIA RTX PRO 6000 96GB**。当前方向是强主 Agent 与小模型专家协作；优先评估 Qwen3.8-27B 主 Agent、Qwen3-8B 与一个 8–12B 异构专家，默认按 BF16 推理方案准备，不进行项目 LoRA 训练。

完整说明见 **[当前多智能体方案与硬件决策](docs/current-plan.md)**，包括模型角色、必要对照、数据边界、历史实验状态和下一步。硬件选择已经确定；具体模型 revision、第二专家、推理模式与预算尚未冻结，也未创建云实例或运行新模型。

继续沿用本目录，公开文档、代码、配置和public run纳入Git整合。整合前本目录只存在于 `/Users/phoenix/.codex/worktrees/72d6/NeuroScience`，这也是此前在主目录看不到它的原因。合并范围仅包含本项目和用户已删除的 `projects/uestc-fyp-topics-2026-2027` 三个旧选题文件；原情绪识别实验和无关IELTS改动分别保留。

`private/`继续被Git忽略，其当前有效副本位于上述72d6工作区。Git合并只同步公开内容，不代表private数据已迁移或备份；在另行迁移并核验前，保留原worktree。

下文保留 4B 阶段的历史记录。早期 M1/Router/M3 辅助路线已由 [classifier-free 决策](protocols/dec-sqma-classifier-free-v1.md) 替代；下文的本机 MLX、4B 和资源限额只适用于对应旧实验，不能直接用于新的双 GPU 阶段。旧配置、Prompt、脚本和 run 保留原样。SQMA-009 已有静态代码，但无执行结果，继续暂停。

## 历史方案与实验记录 · 截至 2026-09-04

状态：`SQMA-001–002 Complete / SQMA-003 attempts 1–2 Failed / SQMA-004–005 Not executed / SQMA-006 Failed / SQMA-007 Complete / SQMA-008 Failed`

项目类型：独立研究项目。它不是“基于大模型的论坛文本情感识别”毕设的 Phase D，也不改变原项目 EXP-001–086 的任何终态。

## 1. 研究目标

本项目研究一个受约束的选择性多智能体问题：

> 在相同 Qwen 计算预算下，角色化分析是否优于 Single Agent 与 Self-Consistency；如果角色化分析有效，选择性触发能否以较少 Qwen 调用保留主要收益？

第一版只使用三个样本级 role-conditioned passes：

1. **Evidence + Appraisal**：提出候选情绪、定位原文证据，并生成结构化评价线索。
2. **Pragmatics Critic**：检查 stance、技术批评、否定、反讽和弱情绪边界。
3. **Judge**：读取冻结分类结果与前两项结构化输出，接受、修改或拒答。

这些角色由同一个生成式 Qwen checkpoint 串行执行，不是多个独立训练模型或独立认知主体。

## 2. 与原项目的关系

原项目是冻结的只读 evidence base：

- M1：RoBERTa 多标签 encoder。
- M3：Qwen3-4B Classification LoRA + 六维分类头。
- EXP-058–063：paired OOF、校准与 pre-Qwen Router。
- Phase C：FastAPI、SQLite、来源适配、密封快照、成本记录与 staged model subprocesses。

新项目可以引用经过身份验证的配置和工件，但不得覆盖、重跑或重新解释原项目结果。新项目的正负结果都不能回写原项目的 Verified、Failed、Stopped 或 Not-executed 状态。

现有 M3 继续作为分类工具。生成式 Agent 已固定为未加载项目 adapter 的官方 post-trained `Qwen/Qwen3-4B` revision `1cfa9a7208912126459214e8b04321603b3df60c`，使用本地 MLX BF16、`thinking=false`。M3 Classification LoRA 和在完整 train 上训练的 M4 Generative LoRA 都不能作为 Agent Brain。

## 3. 已选择的证据路线

项目采用 **strict same-source nested route**，不把现有五折 OOF 直接包装成新的独立测试。该路线只能形成：

> 对 D0 后冻结的新 Agent 比较进行同来源、component-heldout 的前瞻性确认。

fold 4 的标签分布、Router 折级统计和五折 aggregate 已在原项目中使用，因此它不是从未接触的 pristine holdout，也不能证明跨论坛泛化。

复用 EXP-058 已冻结的 component-disjoint folds：

| Project split | Existing folds | Rows | Components | 用途 |
| --- | --- | ---: | ---: | --- |
| Agent-Dev | 0, 1, 2 | 2,016 | 1,963 | Prompt、schema、角色和失败分析 |
| Agent-Tune | 3 | 672 | 657 | 候选选择、触发规则与预算冻结 |
| Agent-Confirm | 4 | 672 | 657 | 方法冻结后的一次性同来源确认 |

fold 4 作为 Confirm 是在任何新 Agent 输出前按最高 fold ID 冻结的确定性映射，不依据新 Agent 结果；这不代表历史模型统计未知。Pilot 只能来自 Agent-Dev。

严格路线要求：

- Dev 预测在 folds 0–2 内重新 cross-fit，不读取 Tune/Confirm 组件。
- Tune 预测由只训练 Agent-Dev 的冻结模型产生。
- 方法选择完成后，允许使用 Dev+Tune 重新拟合最终 threshold/Router，再应用到 Confirm。
- fold 4 raw logits 在主工作区存在且身份核对通过，但当前 worktree 未绑定。两个源 NPZ 都含 `gold` 字段，Confirm producer 不能直接打开；必须先由独立 consumer 生成并密封无 gold 快照。旧 threshold、Router score 和派生预测不自动继承。
- Confirm 的逐行文本、gold、logits 和派生不确定性在正式配置冻结前均不可读；正式 runner 只读文本与已核验 base outputs，封存结果后由独立 scorer 一次性读取 gold。

完整合同见 [D0 数据与证据合同](docs/d0-data-evidence-contract.md)。

## 4. 核心比较

第一轮方法比较包括：

- Frozen classification pipeline：M1 → Router → M3。
- Single Qwen Agent。
- call-count-matched Self-Consistency。
- total-token-budget-matched Self-Consistency。
- Role-diverse Multi-Agent。

Selective Multi-Agent 只有在 Agent-Tune 上，Role-diverse 相对匹配的 Self-Consistency 出现预先定义的稳定信号后才进入 formal Confirm。若通过该 gate，S3、S4 与 S4-random 必须在读取 Confirm gold 前同时冻结并一次性产出，不能先看 Confirm 的 S3 结果再决定是否运行 S4。

S4-random 按 component 抽样，但必须匹配 S4 的实际 activated rows 和 Qwen calls，并报告 token 成本；只匹配 component 数不足以称为等调用量对照。

若 Role-diverse 不能同时越过 token-matched Self-Consistency 与 Hamming guardrail，第一轮按负结果收口，不进入 Selective。只优于 call-matched 对照不足以声称角色分工带来超出计算量的收益。

三角色正式路径固定为三次调用，不使用条件式 Qwen repair；无效输出和合法 abstain 都回退 S0并计入完整成本。这样 S4-random 才能精确匹配 activated rows 与 Qwen calls。

Planner、Report Agent 和网站新模式不进入第一轮样本级分类比较。

## 5. 指标与主张边界

- Primary：完整六标签 Macro-F1。
- Sensitivity：去除低支持 `surprise` 的五标签 Macro-F1。
- Guardrail：Hamming loss；non-inferiority margin 在读取结果前冻结。
- 辅助：Micro-F1、per-label F1、subset accuracy、abstention/risk-coverage、schema、evidence、calls、tokens、latency 与资源。

Primary 覆盖完整 Natural Confirm。若 Agent abstain，第一版默认回退冻结分类 pipeline，不能通过删除困难样本提高主指标。

Challenge Set 只是由不确定性或分歧富集的诊断切片，不是第二个 Confirm，也不能代表自然 activation rate。

## 6. 最低完成集

1. **Project charter 与 D0 合同**：冻结依赖、数据路线、角色、主比较、指标和停止条件。
2. **Dev scoped input**：由独立 consumer 从完整 private source生成并密封 folds 0–2 快照；训练 producer不能打开完整train或fold 3/4。
3. **Strict Agent-Dev production**：只完成 folds 0–2 的三折 cross-fitted M1/M3 outputs，不提前训练Tune与final-refit成员。
4. **Agent preflight**：仅使用 Agent-Dev 的32个 component，检查生成格式、证据定位、角色区分、停止与资源。
5. **Matched role comparison**：比较 frozen pipeline、Single Agent、两种 Self-Consistency 和三角色 Multi-Agent。
6. **Selective activation**：条件性阶段，仅在 Agent-Tune 的角色比较通过冻结门后执行。
7. **Read-only synthesis**：汇总预测质量、证据可靠性、真实成本、失败和结论边界。

项目不以“Multi-Agent 必须提高分数”为完成条件。若 Role-diverse 不优于 Self-Consistency，应以可信负结果收口。

## 7. 非目标

以下内容不属于最低完成集：

- 修改原论坛网站或重新执行 Phase C。
- 外部 gold 泛化；只有需要正式声称跨论坛预测泛化时才重新立项。
- Planner、Report Agent 与 Dashboard 扩展。
- 独立 Appraisal、remove-one 角色消融、角色 LoRA、Mixture-of-LoRA Experts 或 Dense-to-MoE。
- 使用原项目已消费的 validation/test 进行 Prompt、Trigger、阈值或 Agent 顺序选择。
- 并发驻留多个 4B 模型、自由无限讨论或未受限外部工具访问。

## 8. 当前状态与下一动作

`SQMA-001` no-training readiness preflight 已完成，verification attempt 3 为 `Passed`：20项检查全部通过，runner未重跑、密封run未修改。全过程没有加载模型、训练、forward、Agent调用、private row解析或Tune/Confirm/validation/test访问，也没有产生strict logits。

verification attempt 1因Python 3.14动态module登记错误停止；attempt 2因M1目录存在Hugging Face下载sidecar而停止。两个失败均在写verification前发生并已登记incident。attempt 3只允许精确结构的非加载cache sidecar，同时继续逐项核验manifest中的7个M1核心文件和9个M3文件。

`SQMA-002` Agent-Dev scoped-input materialization 已完成并独立验证通过。每个fold 0–2均密封了train-capable、gold-free inference和consumer-only gold三类工件，共2,016 rows、1,963 components；private目录为0700，全部文件为0600。

data steward和verifier流式经过monolithic private文件，但只decode folds 0–2的2,016行；fold 3/4各672行均未decode且输出为0。模型、训练、forward、Agent、validation和test访问均为0。

根据用户确认，首轮方法已改为纯classifier-free Qwen比较：不重新训练M1/M3，也不把分类器结果输入Critic、Judge或Single。SQMA-002快照继续作为gold隔离的数据基础，但train-capable和consumer-gold不会进入SQMA-003 producer。

`SQMA-003` classifier-free Agent-Dev preflight 的 attempt 1 与 attempt 2 均为 `Failed`。两次runner都完成144次物理调用并写出密封run，但冻结能力门均未通过。attempt 1的locked raw schema有效率为`0.2667`，technical fallback为24行，并有2次token-cap hit；attempt 2经过仅针对机械格式的Prompt修订后，raw schema有效率提高到`0.8000`，technical fallback降至4行，token-cap hit降为0，说明格式遵循显著改善。

attempt 2仍未达到冻结门：overall要求至少`0.98`，每个角色至少`0.95`，locked S3 technical fallback最多1行；实际Evidence、Judge和Single有效率分别为`0.9167`、`0.8750`和`0.6250`。因此格式改善不能写成能力预检通过。独立verifier以exit code 1停止，attempt 1与attempt 2均没有`verification.json`或`complete.json`；当前也没有登记或授权自动attempt 3。

`SQMA-006` 使用与SQMA-003不重叠的新32个Agent-Dev component和v3 syntax-only canonicalizer完成了120次classifier-free Qwen调用，终态为`Failed`。Locked canonical有效率overall为`0.8958`；Evidence、Critic、Judge和Single分别为`1.0000`、`0.9583`、`0.6250`和`1.0000`，locked S3 fallback为9行。因此overall、per-role和fallback三项冻结门失败。Evidence exact-substring rate为`1.0000`、out-of-ontology labels为0、Single agreement为`0.9583`、token-cap hit为0，full-Tune投影为`32,309.26 s`；这些通过项不能覆盖失败门。

该run用时`525.58 s`，资源门通过，且没有访问gold、classifier、fold 3/4、validation、test或network，也没有训练模型。Ranks 0–7的shakedown聚合仅记录Critic `json_decode` 2/8和Judge `label_item` 5/8，不含逐行文本或输出，不能替代locked gate。SQMA-006没有`verification.json`或`complete.json`；该失败没有自动触发后续实验，SQMA-007是在此后另行登记的独立C1 shakedown。

`SQMA-007` Dev-C1 visible shakedown已完成并通过独立验证。它在16个新visible components上执行48次调用；Judge的bare raw parse、exact six keys、array/int/allowed-ID与rendered合同均为16/16，Evidence和Critic有效率均为`1.0`，semantic repair、unhandled failure、token-cap hit和normalization events均为0。该结果只支持ordinary greedy fixed-slot合同进入预登记的locked acceptance，不支持准确率、角色贡献或总体可靠率结论。

`SQMA-008` Dev-C2 locked acceptance完成72次调用，但终态为`Failed`。Judge raw parse、exact six keys、array与integer检查均为24/24；其中1行出现illegal reference ID，使allowed-ID和rendered-valid均为23/24，`contract_errors=1`。C2对Judge合同采用零容忍门，因此该单行违规足以阻断通过。Evidence与Critic有效率均为`1.0`，fallback、normalization、semantic repair、unhandled failure和token-cap hit均为0；full projection为`10,031.98 s`，run用时`272.39 s`。

SQMA-008没有读取gold、classifier或fold 3/4，也没有向人工暴露locked raw。失败run没有`verification.json`或`complete.json`，formal matched comparison继续阻断。下一研究决策是静态设计Judge V3 constrained candidate scorer，而不是查看locked row、利用locked输出修Prompt或自动重跑。

`SQMA-004` fold-3 Agent-Tune输入materialization和`SQMA-005` 672-row classifier-free matched comparison均未执行。SQMA-005目前只有producer、scorer、verifier及相应小型测试的静态代码准备；这些文件没有产生模型输出、gold评分、方法比较或实验结果，不能作为SQMA-005已开始或已完成的证据。

## 9. 项目文件

- [D0 数据与证据合同](docs/d0-data-evidence-contract.md)
- [D0 static method contract](configs/d0-static-contract.json)
- [D0 dependency manifest](configs/d0-dependency-manifest.json)
- [Agent Prompt bundle v0](prompts/agent-bundle-v0.json)
- [Classifier-free decision](protocols/dec-sqma-classifier-free-v1.md)
- [Classifier-free Prompt bundle](prompts/agent-bundle-v1-classifier-free.json)
- [Classifier-free format revision](prompts/agent-bundle-v2-classifier-free.json)
- [Classifier-free schema](schemas/agent-output-v2.schema.json)
- [Agent output schema v1](schemas/agent-output-v1.schema.json)
- [Agent runtime validator](scripts/validate_agent_output.py)
- [D0 static verifier](scripts/verify_d0_static.py)
- [SQMA-001 protocol](protocols/sqma-001-strict-base-readiness-preflight.md)
- [SQMA-001 config](configs/sqma-001-strict-base-readiness-preflight.json)
- [Strict base contract](scripts/strict_base_contract.py)
- [SQMA-001 verification](runs/sqma-001-strict-base-readiness-preflight/attempt-1/verification.json)
- [SQMA-001 completion](runs/sqma-001-strict-base-readiness-preflight/attempt-1/complete.json)
- [SQMA-002 protocol](protocols/sqma-002-dev-scoped-input-materialization.md)
- [SQMA-002 config](configs/sqma-002-dev-scoped-input-materialization.json)
- [Scoped-input contract](scripts/scoped_input_contract.py)
- [SQMA-002 verification](runs/sqma-002-dev-scoped-input/attempt-1/verification.json)
- [SQMA-002 completion](runs/sqma-002-dev-scoped-input/attempt-1/complete.json)
- [SQMA-003 protocol](protocols/sqma-003-classifier-free-agent-preflight.md)
- [SQMA-003 config](configs/sqma-003-classifier-free-agent-preflight.json)
- [SQMA-003 attempt 1 run](runs/sqma-003-classifier-free-agent-preflight/attempt-1/run.json)
- [SQMA-003 attempt 2 protocol](protocols/sqma-003-incident-001-and-attempt-2.md)
- [SQMA-003 attempt 2 config](configs/sqma-003-classifier-free-agent-preflight-attempt-2.json)
- [SQMA-003 attempt 2 run](runs/sqma-003-classifier-free-agent-preflight/attempt-2/run.json)
- [SQMA-003 attempt 2 failure incident](incidents/sqma-003-attempt-2-capability-gate-failure.json)
- [SQMA-006 protocol](protocols/sqma-006-d1-canonical-output-preflight.md)
- [SQMA-006 config](configs/sqma-006-d1-canonical-output-preflight.json)
- [SQMA-006 failed run](runs/sqma-006-d1-canonical-output-preflight/attempt-1/run.json)
- [SQMA-006 capability-gate failure incident](incidents/sqma-006-d1-capability-gate-failure.json)
- [SQMA-007 protocol](protocols/sqma-007-dev-c1-visible-judge-shakedown.md)
- [SQMA-007 verified run](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/run.json)
- [SQMA-007 verification](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/verification.json)
- [SQMA-007 completion](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/complete.json)
- [SQMA-008 protocol](protocols/sqma-008-dev-c2-locked-acceptance.md)
- [SQMA-008 failed run](runs/sqma-008-dev-c2-locked-acceptance/attempt-1/run.json)
- [SQMA-008 locked-acceptance failure incident](incidents/sqma-008-dev-c2-locked-acceptance-failure.json)
- [SQMA-004 registered design](protocols/sqma-004-agent-tune-input.md)
- [SQMA-005 static producer](scripts/run_sqma005_agent_tune_comparison.py)
- [SQMA-005 static scorer](scripts/score_sqma005_agent_tune_comparison.py)
- [SQMA-005 static verifier](scripts/verify_sqma005_agent_tune_comparison.py)
- [项目交接](HANDOFF.md)
- [原毕设 Evidence Log](../llm-forum-text-emotion-recognition/evidence-log.md)
- [原毕设 Research Roadmap](../llm-forum-text-emotion-recognition/research-roadmap.md)
- [原 Stack Overflow HANDOFF](../llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/HANDOFF.md)
