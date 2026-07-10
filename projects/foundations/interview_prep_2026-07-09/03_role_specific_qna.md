# 03 岗位专项问答

## A. Coze 上下文工程

### 你怎么理解 context engineering？

context engineering 是把模型运行时需要的信息组织好：system instruction、user intent、tool results、retrieved memory、conversation state、constraints。它比写 prompt 更宽，因为它要管理信息选择、顺序、压缩、更新和验证。

### 长对话一致性怎么做？

我会分三步：

1. 抽取稳定事实和当前任务状态。
2. 把短期 session state 和长期 memory 分开。
3. 用 eval 检查模型是否在后续 turn 里正确使用这些信息。

Cyrene 里对应的是 candidate memory、project/global store、retrieval checks 和 stale-memory leakage checks。

### 如果上下文太长，你怎么压缩？

先按任务相关性筛，不先做摘要。具体做法：

- 保留当前目标、约束、用户确认过的决策。
- 删除中间推理草稿和过期计划。
- 对历史记录做 structured summary，保留 source 和 timestamp。
- 对需要精确引用的内容保留原文片段。

### 你没有做过 SFT/RL，怎么匹配 JD？

可以这样答：

> 我没有把 Cyrene 扩展到 SFT/RL 训练，但我做过 context 和 memory 行为的工程化验证。这个经验能对应 JD 里“上下文理解和评估”的部分。进入团队后，我需要补训练 pipeline 和 preference data 的经验，但我能先在 prompt/context、bad case analysis、eval set 构建上产出。

### 反问

- 团队现在更缺 long-context prompt/context engineering，还是 SFT/RL 数据构建？
- Coze 对长对话一致性有哪些核心 eval 指标？
- 实习生会参与 bad case 分析、eval set 构建，还是直接参与模型训练流程？

## B. AI Agent开发-计算

### 你怎么理解 Agent Infra？

Agent Infra 让 Agent 从 demo 变成可运行系统。它要处理 tool registry、identity、permission、memory、observability、lifecycle、error recovery 和 deployment。Cyrene 覆盖了 memory、MCP tools、CLI、hooks 和 release checks。

### MCP 在你的项目里解决了什么？

MCP 给模型和外部系统之间提供标准接口。Cyrene 通过 MCP tools 暴露 memory 相关能力，让 Agent 可以用统一方式读写或查询外部状态。这个设计比把逻辑写进 prompt 更可控，也更容易测试。

### lifecycle hooks 为什么重要？

Agent 工作发生在 session 之间，不只发生在一次模型调用里。hooks 可以在 session start、task end、release check 等阶段插入 memory 检查和状态更新。它们也带来风险，所以我让 hook errors 不阻塞 Codex work。

### 如果你要设计企业级 Agent memory，会加什么？

我会加五个模块：

- access control：区分用户、项目、团队 scope。
- audit log：记录 memory 写入、修改、删除和来源。
- expiration policy：处理过期事实。
- retrieval trace：记录为什么召回某条 memory。
- eval dashboard：跟踪 recall relevance、leakage、tool-call success。

### 代码题准备方向

研发岗会问基础算法。优先刷：

- hash map：two sum、group anagrams。
- two pointers：valid palindrome、container with most water。
- sliding window：longest substring without repeating characters。
- BFS/DFS：number of islands、binary tree level order traversal。
- stack/queue：valid parentheses、min stack。

### 反问

- 这个 Agent Infra 岗主要做框架层、平台层，还是业务 Agent 落地？
- 实习生能接触 memory、observability 或 tool registry 相关模块吗？
- 团队现在用 Eino、LangGraph 还是自研框架为主？

## C. Agent评测-AI数据与安全

### Agent 评测和普通 LLM 评测有什么不同？

普通 LLM 评测常看单轮输出质量。Agent 评测要看过程：任务规划、工具选择、参数填写、检索相关性、推理链、恢复能力和最终任务完成。工具调用错一次，最终答案可能看起来合理，但系统已经失败。

### 你会怎么评估工具调用准确性？

我会拆成四层：

- selection：是否选对 tool。
- arguments：参数是否完整、合法。
- timing：是否在合适步骤调用。
- outcome：tool result 是否被正确使用。

Cyrene 可对应 memory retrieval：系统是否在合适时机召回正确 memory，是否把过期 memory 带入 context。

### 你会怎么写 Agent bad case report？

固定结构：

1. 用户任务和预期行为。
2. Agent 实际步骤。
3. 失败点：planning、tool selection、retrieval、reasoning、final answer。
4. 证据：trace、tool call、retrieved memory、输出。
5. 修复建议：prompt、tool schema、retrieval policy、eval case。

### 自动化评测怎么落地？

先做小规模高质量 eval set。每条 case 包含 task、available tools、expected tool calls、acceptable final answer、failure tags。自动跑完后，用人工复核抽样校准指标。

### 你没有正式评测实习，怎么证明能做？

可以这样答：

> 我在 Cyrene 里做过 retrieval regression、stale-memory leakage 和 release checks。它不是公司级评测平台，但我已经把 Agent 行为拆成可观察的 failure modes。这个岗位需要的评测设计、bad case 分析和报告输出，我可以用 Cyrene 的 trace 和 memory review workflow 来展开。

### 反问

- 团队目前更关注工具调用准确性、检索质量，还是复杂任务规划？
- Agent eval 结果会反馈给 prompt、数据生产、模型训练，还是产品策略？
- 实习生会负责 eval case 设计、自动化框架，还是评测任务管理？

## D. Canonical System Design：Multi-tenant Agent Memory Runtime

题面：为团队设计一个 production Agent runtime。多个用户和项目共享平台；Agent 可读写 memory、调用有副作用工具、暂停等待人工审批，并能从失败中恢复。

### 30 分钟回答骨架

1. **Clarify**：用户/tenant、核心任务、读写比例、并发、数据保留、允许的失败、latency/cost/privacy 目标。数值是设计假设，必须先说假设再画架构。
2. **API 与 data model**：`Run`、`Step`、`ToolCall`、`ToolResult`、`MemoryRecord`、`Approval`、`TraceSpan`；每个对象带 tenant/project/user scope、provenance、version 和 idempotency key。
3. **Execution path**：request → policy/context assembly → planner → tool router → permission/risk gate → executor → state store → trace/eval → response。
4. **Memory path**：candidate → actual-use count → weekly AI review → promote/update/revoke → scoped store → retrieval/rerank → context；默认 project scope，跨 scope 需要显式 policy，敏感、冲突或高风险候选转人工 review。`actual-use count` 只统计模型在任务执行或答案生成中实际采用该 memory，不统计单纯 retrieval hit 或 context injection；它仍不能单独证明 memory 正确。
5. **Reliability**：bounded retry 只用于可重试错误；副作用工具先查 idempotency；timeout/cancel 传播到子调用；partial execution 用 checkpoint + compensation/undo，不假装原子事务。
6. **Observability 与 eval**：每个 model/tool/retrieval/approval step 有 trace；指标覆盖 task success、tool selection/argument、leakage、approval precision、retry loop、latency、cost 和 recovery success。
7. **Tradeoff**：自动化越高，用户摩擦越低但不可逆风险越高；memory 召回越多，continuity 越好但污染、隐私和 token cost 越高。

### HITL 风险决策表

| 级别 | 例子 | 默认动作 | UX |
| --- | --- | --- | --- |
| automatic | 只读、低敏、可重复查询 | 自动执行 | 展示 trace，可取消后续步骤 |
| confirm | 可逆写入、低金额或低影响变更 | 执行前确认参数 | preview + edit + cancel |
| human approval | 外发消息、付款、删除、权限变更 | 暂停 run，指定审批人 | approve/reject/edit，超时后安全终止 |
| block or escalate | 越权、敏感数据外传、来源不可信的高风险指令 | 拒绝或升级安全审核 | 给出原因和安全替代路径 |

### 安全追问必须覆盖

- prompt injection：外部内容只作为 untrusted data；instruction 与 data 分层；tool permission 不由模型自行扩大。
- memory poisoning：provenance、review/promotion policy、scope isolation、version/conflict、TTL/invalidations。
- privacy：least privilege、redaction、encryption、retention/deletion、tenant isolation、audit log。
- partial execution：记录已完成副作用，支持 cancel、compensation、manual repair 和 resume from checkpoint。

常见失分：只画 planner + tools；不问规模；重试所有错误；没有 idempotency；只说 sandbox 不说 approval；只讲 final answer 不讲 trace/eval；把 global memory 当默认共享库。

## E. Behavioral Evidence Bank

先填证据索引，再写 STAR。没有真实事件就更换项目，不编故事。

| 能力 | 首选项目候选 | 必须准备的证据 |
| --- | --- | --- |
| ownership | Cyrene | 你主动定义了什么完成标准、产出了什么 artifact、哪里仍未完成 |
| ambiguity | Cyrene 或机器人车 | 原始需求哪里模糊、你问了什么、如何收窄 scope |
| failure/debugging | Cyrene benchmark 或 NeRF | 原假设、失败信号、排查顺序、修复与 regression |
| conflict/collaboration | NeRF/机器人车团队项目 | 分歧双方的合理性、你如何用实验/接口/时间约束收敛；无真实分歧就不用该素材 |
| changed mind after evidence | Cyrene fixture 或 NeRF ray sampling | 什么新证据推翻原方案、你实际改了什么、结果和限制 |

每个故事准备 15 秒 opening、60-90 秒主体和一句 reflection。结果尽量引用可核对 artifact；没有数字时说具体行为变化，不编百分比。

## F. 升学与可实习性

面试回答：

> 我计划申请 2027 Fall 硕士，后续方向也会继续围绕 Agent 和 AI systems。目前最早可以在两周内到岗，并且可以连续实习 6 个月、每周 5 天。这段实习期间我可以保持完整、稳定的时间投入。

只承诺已经确认的到岗时间和实习周期。若被追问毕业后的长期去向，如实说明当前升学计划，不承诺尚未确定的留任或入职安排。
