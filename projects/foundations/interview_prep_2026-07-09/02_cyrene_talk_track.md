# 02 Cyrene 项目讲法

## 30 秒版本

> Cyrene Continuity 是我给 Codex 做的 local-first memory plugin。它解决的问题是：Agent 跨 session 工作时，哪些信息值得长期保存，怎么把相关 memory 连接起来，怎么在后续 session 召回，同时避免旧 memory 或其他项目的 memory 污染当前上下文。我用 TypeScript/Node.js 做了 MCP tools、CLI、hooks、local UI、review queue 和 release checks。

## 2 分钟版本

> 我把 Cyrene 设计成四层：candidate、review、store、retrieval。Agent 工作过程中先产生 candidate memory，不直接写入长期 memory。用户或规则审核后，系统用 review hash 标记决策，再写入 project store 或 global store。后续 session 启动时，retrieval 根据项目和相关记录召回 memory，组成 context。  
>   
> 我这样设计，是因为 Agent memory 最大的问题不是“存不够”，而是“存错了还会继续影响后续任务”。所以我加了 pending queue、project/global separation、linked records 和 stale-memory leakage checks。工程上，我实现了 MCP tools、CLI commands、lifecycle hooks、local Web UI、Vitest 和 GitHub Actions。

## 5 分钟版本

按这个顺序讲：

1. 用户问题：Agent 跨 session 工作时会丢上下文，也可能召回过时信息。
2. 系统边界：Cyrene 不改模型，不做训练；它处理 memory lifecycle 和 context assembly。
3. 数据流：candidate memory -> review queue -> approved store -> linked records -> retrieval -> session context。
4. 工程实现：TypeScript/Node.js、MCP tools、CLI、hooks、local UI、Vitest、GitHub Actions。
5. 验证方式：retrieval accuracy、stale-memory leakage、runtime drift、release checks。
6. 下一步：加入更系统的 eval set，覆盖 tool-call success、memory relevance、cross-session task completion。

## 高频追问

### 为什么不让 Agent 自动写长期 memory？

自动写入会把临时计划、错误判断、过期状态带进后续 session。我让 candidate 先进入 pending queue，再通过 review hash 记录审批结果。这样做牺牲了一点自动化，换来可审计性和更低的污染风险。

### project memory 和 global memory 怎么分？

project memory 存项目内事实，比如 repo 结构、测试命令、模块边界。global memory 存跨项目偏好，比如用户的写作风格和工作流偏好。默认应该写 project memory，只有跨项目复用价值明确时才写 global memory。

### linked records 有什么用？

单条 memory 容易碎片化。linked records 让系统把同一决策、同一模块、同一 bug 的多条记录连起来。retrieval 时，系统可以召回一组相关 memory，而不是只拿到一条孤立片段。

### stale-memory leakage 怎么处理？

我用三类办法控制：project/global 分区，review queue 阻止未确认记录进入长期 memory，release checks 检查旧 memory 是否错误影响当前任务。面试时不要说它已经彻底解决。更准确的说法是：我把 leakage 当成 regression 风险，放进 release gate。

### 如果重做，你会改什么？

我会补三件事：

- 做一个标准化 eval set，覆盖 memory relevance、stale leakage、cross-session task completion。
- 给 memory 增加过期策略，比如 TTL、confidence、source scope。
- 把 retrieval logs 结构化，方便分析 bad case。

## 你要主动承认的边界

- Cyrene 是个人项目，没有线上用户规模。
- 现在的 benchmark 更像 release gate，不是大规模学术 benchmark。
- 项目核心贡献在 memory lifecycle、context management、tool integration 和 eval thinking，不在模型训练。
