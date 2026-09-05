# 当前多智能体方案与硬件决策

日期：2026-09-05

项目：Selective Qwen Multi-Agent Forum Analysis

状态：硬件已由用户确认；方法方案待配置冻结与实验验证。

## 1. 已确定的决定

2026-09-05，用户明确决定使用 **2×NVIDIA RTX PRO 6000 96GB**。按同一主机两张完整 GPU 准备，分别承载强主模型与小模型专家。这是硬件选型记录，不表示已经租用、验机或完成云端部署。

研究继续沿用 `projects/selective-qwen-multi-agent-forum-analysis/`。研究问题仍是选择性协作，升级模型规模和部署环境不需要另开一个内容重复的项目。

| 项目 | 当前决定或状态 |
| --- | --- |
| GPU | 2×RTX PRO 6000，每卡 96GB；具体 Server/Workstation/Max-Q 版本及功耗待验机 |
| 部署位置 | 云端；AutoDL为当前考察平台，尚未锁定具体主机 |
| 推荐精度 | BF16作为正式比较默认方案；这是部署建议，待运行配置冻结 |
| 主 Agent | 用户提出 Qwen3.8-27B，作为优先候选；revision尚未冻结 |
| 专家模型 | Qwen3-8B优先；另一个8–12B模型待选，Mistral-NeMo-12B是当前候选 |
| 训练 | 第一轮使用官方 post-trained 权重，不加载项目 LoRA，不重训 M1/M3 |
| 已有4B实验 | 保留为格式与运行经验，不继续作为新阶段主模型 |
| 旧Qwen3-32B复核 | 不再列为当前最低完成集中的必做项 |

BF16意味着不额外做4-bit/8-bit权重量化，不是没有经过厂商预训练或后训练。Qwen3.8-27B官方模型卡确认其为带视觉编码器的27B级语言模型，并支持调整thinking；本项目只使用文本输入。官方Agent benchmark可支持将其列为候选，不能代替论坛情绪任务上的验证。[官方模型卡](https://huggingface.co/Qwen/Qwen3.8-27B)

## 2. 目录为什么看起来不见了

首次提交前的只读核对结果如下（整合前快照）：

| 工作区 | 多智能体目录 | 原情绪识别实验目录 |
| --- | --- | --- |
| `/Users/phoenix/.codex/worktrees/72d6/NeuroScience`，本任务实际目录 | 存在；整个目录未被Git跟踪 | 存在 |
| `/Users/phoenix/Assistant/NeuroScience`，主目录 | 不存在 | 存在 |
| `/Users/phoenix/Assistant/NeuroScience-ielts-reader-reliability`，当前main所在checkout | 不存在 | 存在 |

该次核对时，Git的已跟踪文件列表和全分支日志均无多智能体目录记录。因此，当时目录留在本任务的独立工作区；切回主目录、main或远程仓库时看不到，不能据此判定工件已经丢失。

用户在主目录删除的是 `projects/uestc-fyp-topics-2026-2027/` 的三个选题文件：`application-reasons-en.md`、`shortlist.md`、`topics.md`。初次核对时它们是主checkout中的未提交删除；2026-09-05按用户合并要求单独记入提交 `852406a`，随后纳入项目整合，保持删除。

后续沿用本目录。2026-09-05按用户要求，公开文档、代码、配置和public run通过Git整合到main及主目录的原工作分支；两者保留各自的IELTS状态，不整体切换或覆盖无关文件。本次不push。

private工件仍留在 `/Users/phoenix/.codex/worktrees/72d6/NeuroScience/projects/selective-qwen-multi-agent-forum-analysis/private/`，Git整合不包含这些数据，也不构成private备份。另一个checkout运行旧协议前仍需独立迁移并核验private输入；完成前保留72d6工作区。

## 3. 研究问题与系统目标

系统面向英语技术论坛文本的多标签情绪分析，保持六标签：`love`、`joy`、`surprise`、`anger`、`sadness`、`fear`；空标签集表示未检出这些情绪。

拟检验的主问题是：

> 强主 Agent 与小模型专家的角色协作，能否在可比的实际推理成本下改善论坛情绪识别；选择性调用能否减少开销，同时保留协作收益？

研究分三层回答：角色分工是否有价值；不同模型的判断是否互补；触发规则是否选对了需要额外计算的样本。不能把三个因素一起变化后的分数提升全部归因于“多智能体”。

最终系统可以承载话题级汇总、证据展示和成本记录。第一轮先验证样本级方法，网站和报告生成放在方法证据之后。当前不安排CancerEmo等外部金标泛化，也不恢复已暂停的context/C2构建。

## 4. 候选模型与角色

以下是待验证的分工，不是对各模型专长的既定结论。

| 角色 | 优先候选 | 职责 | 计划驻留位置 |
| --- | --- | --- | --- |
| Evidence + Appraisal | Qwen3-8B | 提出候选标签、定位原文证据、给出简短评价线索 | GPU 1 |
| Pragmatics Critic | 一个8–12B异构模型，优先考察Mistral-NeMo-12B | 检查否定、反讽、立场、技术批评与情绪的区别，指出证据不足 | GPU 1 |
| 主 Agent / Judge | Qwen3.8-27B | 结合原文与专家报告处理冲突，决定最终标签及证据引用 | GPU 0 |
| 编排与校验 | 确定性程序 | 调用顺序、预算、JSON/schema、合法ID、日志与异常记录 | CPU |

最低完整流程沿用已有的一轮有向调用：Evidence → Critic → 主 Agent。各角色均能读取同一份原始 `analysis_text`；Critic可读Evidence报告，主Agent可读前两份报告。主Agent本身也是Agent，“主”描述其最终决策职责。

首轮由程序固定调用图。让27B自由规划、递归召唤工具或多轮讨论，是另一项扩展，暂不混入当前比较。第二专家的模型身份必须通过Agent-Dev上的格式稳定性、任务表现和错误互补性选择；不能仅凭品牌不同就假设协作更好。

原项目的M1、M3及Router不进入新Agent输入。此前[无分类器辅助的决策](../protocols/dec-sqma-classifier-free-v1.md)继续适用；旧分类器仅可作为历史研究背景。

## 5. 选择性协作怎么做

先比较全量协作是否有收益，再在Agent-Tune上冻结选择性策略。当前建议优先检验“小模型专家先分析，出现分歧或证据不足时再调用27B裁决”。

这时节省的是强模型调用，前面小模型的调用仍必须全量计费。若改为“27B先处理每条文本，再决定是否请小专家”，则每条都已经支付主模型成本，属于另一个调用图，应另行比较，不能同时称为同一种节省策略。

触发信号只能来自触发前已经产生的信息，例如小模型标签分歧、证据缺失或结构化不确定性。模型自报置信度不是天然校准的概率。规则、阈值以及未触发样本采用哪个结果，均需在Tune阶段冻结。

随机触发对照采用相同调用位置，并按component抽样匹配选择性策略的实际activated rows与各模型物理调用数，同时报告token、GPU时间和时延差异。若选择性和随机触发表现相当，就不能声称触发器识别出了更值得协作的样本。

## 6. 必要比较与成本口径

以下是实验矩阵建议；本文件不替代可执行的冻结配置。

| 比较组 | 要回答的问题 |
| --- | --- |
| 每个入选模型的Single Agent，必须包括27B主模型 | 单个模型本身已经能做到什么 |
| Self-Consistency，包含强主模型的重复采样 | 额外计算用于重复独立判断是否已经足够 |
| 同一Qwen3-8B承担全部角色 | 对照已有角色设计，检验固定模型下的分工效果 |
| 固定同一个27B Judge，比较Qwen/Qwen专家与Qwen/异构专家 | 在裁决者不变时，替换专家是否有额外价值 |
| 完整异构协作与强Single、成本匹配的Self-Consistency | 最终协作系统是否优于强模型独立处理 |
| Selective、Full与matched-random，条件性阶段 | 是否以较少成本保留收益，且触发有选择价值 |

角色专长若要写成贡献，需要补角色互换或去掉角色的消融；只比较一种分工时，只能评价该组合的整体效果。8B/12B模型相互替换也同时改变了规模，因此不能称为纯粹的“异构性因果效应”。

异构系统的同调用数、同token数都不等于同计算成本。分别记录每个模型的输入/输出token、包含thinking的生成量、模型调用数、GPU活动时间、端到端时延、两卡租用时间及对应费用。正式性能对照按开发集实测冻结预算，不提前假定一条27B调用等于若干条8B调用。

没有硬件预算限制，仍然需要成本匹配对照：它决定论文能否区分方法收益与增加计算量的收益。

## 7. 输出、数据与评价

输出沿用固定六标签槽位、原文证据与合法证据ID检查的设计经验。JSON合法和引用存在只证明结构正确，不证明证据与情绪相关。若声称解释质量提高，还需要单独的人工评价标准。

计划不使用额外LLM修复调用。若使用schema约束解码，应明确记录并应用于适当的对照组，不能把约束器保证的合法率当作模型推理能力。正式评分应继承classifier-free阶段的全覆盖原则：invalid与abstain分别记录，并按预先固定规则处理，不能删掉失败行。现有合同将二者映射为空标签集；新配置若改变该规则，必须在看到评价结果前写明。

拟保留既有component-disjoint数据路线：

| 划分 | 既有fold | 行数 | 用途 |
| --- | --- | ---: | --- |
| Agent-Dev | 0–2 | 2,016 | Prompt/schema、模型筛选与预检 |
| Agent-Tune | 3 | 672 | 开发比较、触发与成本预算选择 |
| Agent-Confirm | 4 | 672 | 方法冻结后的同来源确认 |

划分来自[既有D0合同](d0-data-evidence-contract.md)。数据映射可复用，旧合同中为M1/M3重训设计的步骤不自动恢复。新云端阶段仍需重新核对输入身份、访问边界、样本排除清单和已有Dev暴露记录；不把旧locked样本重新称为全新blind样本。

Confirm的历史标签分布与旧模型统计已在原项目使用，不能称为完全未接触的独立测试集，也不能用于证明跨论坛泛化。producer只读无gold输入；预测封存后由独立scorer读取对应gold。

主指标为六标签Macro-F1；补充Micro-F1、per-label F1、Hamming loss、失败/拒答率和真实成本。五标签Macro-F1用于低支持surprise的敏感性分析。统计重复、component级配对区间和判定阈值在正式评分前冻结，不在本次摘要中任意添加样本量或数值门槛。

## 8. 双GPU部署建议

两张96GB是两个独立显存空间。建议GPU 0只运行27B主模型，GPU 1运行两个小专家，各模型独立推理，通过短结构化报告通信。无需为了汇总192GB显存而将主模型跨卡切分。

这能让主模型与专家均按BF16准备，并减少反复装卸模型的开销。它是基于容量的工程判断，尚未对实际模型和推理引擎进行峰值显存实测。[RTX PRO 6000官方规格](https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/)

实例选择建议：可用数据盘总容量先按300GB准备，主机RAM优先至少192GB；若另留多种精度权重或较多运行副本，应再增加磁盘。此前观察到的具体机器、单价和库存只是当时快照，不作为已锁定订单。

软件从Linux/CUDA、PyTorch和一个已验证支持目标模型的vLLM或SGLang版本开始，部署后固定版本和模型revision。4K–8K输入加输出上下文可作为首轮资源探测点，最终上限需覆盖真实Prompt与thinking输出，不能为了显存省事而截断推理后仍称公平比较。

小专家可常驻后顺序调用，不必强行并发；多个服务的显存份额必须明确。AutoDL页面所示“CUDA最高版本”是驱动兼容信息，不能直接当成已安装软件环境或目标模型兼容性证明。

## 9. 已有成果与尚未完成的内容

以下状态依据本次读取的public工件与配置，不依赖逐行private输出。

| 实验 | 已有状态 | 可支持的结论 |
| --- | --- | --- |
| SQMA-001/002 | 已完成并验证 | 旧依赖预检与Dev无gold输入密封已做过 |
| SQMA-003 attempts 1–2 | Failed | 4B的格式修订改善了输出，但能力门未通过 |
| SQMA-006 | Failed | 扁平schema/canonicalization仍未解决Judge合同问题 |
| SQMA-007 | Complete / verification Passed | 16个visible样本的固定槽位合同通过 |
| SQMA-008 | Failed | 24个locked样本中23个Judge输出满足引用合同，1个非法ID导致失败 |
| SQMA-009 | 静态准备，未执行 | 有协议、Prompt/schema与runner/verifier/tests；config仍含占位，不能称已完成冻结或验证 |
| SQMA-004/005正式比较 | 未执行 | 尚无正式角色收益或预测质量比较 |
| 双96GB云端与新模型组合 | 未运行 | 目前是硬件决策和方法计划 |

可追溯入口：[SQMA-007 verification](../runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/verification.json)、[SQMA-007 complete](../runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/complete.json)、[SQMA-008 run](../runs/sqma-008-dev-c2-locked-acceptance/attempt-1/run.json)、[SQMA-009 config](../configs/sqma-009-judge-v3-restricted-choice-backend-parity.json)。

新模型、新后端和新调用图需要新预检。旧失败保持原状态；也不能因为换了GPU就把旧格式问题视为已经解决。

## 10. 后续顺序

1. **项目与数据依赖整理**：保留本目录，明确要迁移的代码、无gold输入、scorer侧gold和原始来源身份；密封private工件单独备份。当前不自动合并旧分支或恢复删除的选题。
2. **最小运行方案冻结**：确定27B候选revision、第二专家、BF16、thinking模式、固定调用图与输出合同；保留强Single和Self-Consistency对照。
3. **租机后的环境与32条Agent-Dev预检**：核实两卡型号和磁盘、模型加载、JSON/证据ID、输出截断、成本及峰值显存。选样与visible/locked边界先冻结，预检不评分gold。
4. **Agent-Tune matched comparison**：通过技术预检后，完成模型单体、角色与异构系统比较。不要把4B历史延迟外推为新GPU成本。
5. **选择性阶段与Confirm**：协作有稳定信号时再选择触发策略；所有Confirm比较和预算同时冻结后运行。若协作不优于强基线，保留负结果。
6. **系统接入与报告**：依据方法结果决定是否接入话题级网站，再评价运行和报告质量。无gold服务闭环不替代预测泛化实验。

首轮记录完成了硬件决定、当前方案汇总和项目位置说明。2026-09-05的后续整合加入Git提交与合并，并保留旧选题删除；没有云端下单、数据上传、模型下载、训练、推理、旧实验重试或模型/checkpoint删除。
