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
