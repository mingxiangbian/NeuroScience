# 02 Cyrene 项目讲法

## 30 秒版本

> Cyrene Continuity 是我给 Codex 做的 local-first memory plugin。它解决的问题是：Agent 跨 session 工作时，哪些信息值得长期保存，怎么把相关 memory 连接起来，怎么在后续 session 召回，同时避免旧 memory 或其他项目的 memory 污染当前上下文。候选记忆不会即时写入长期存储：系统记录调用次数，并由 AI 按周判断它是否符合长期 memory 的要求；同一个周度流程也会整理、更新或撤销已有 memory。敏感、冲突或高风险候选才进入人工审核。我负责问题定义、架构、系统边界和 benchmark 设计，并使用 AI 辅助实现；我负责 review 实现、检查测试结果和决定 release gate。

## 2 分钟版本

> 我把 Cyrene 设计成四层：candidate、review、store、retrieval。Agent 工作过程中先产生 candidate memory，并记录它后续被模型实际用于任务执行或答案生成的次数；单纯被检索或注入上下文不计数。系统每周运行一次 memory maintenance：AI 结合实际使用次数和内容本身，判断候选是否符合长期 memory 的要求，再自动晋升到 project memory 或 global memory；对已有长期 memory，也用实际使用次数和 AI 判断决定保留、更新或撤销。敏感、冲突、模糊或高风险候选进入人工 review queue。后续 session 启动时，retrieval 根据 scope 和相关记录召回 memory，组成 context。
>   
> 我这样设计，是因为 Agent memory 最大的问题不是“存不够”，而是“存错了还会继续影响后续任务”。周度维护让系统保留自动化，同时避免每轮对话都生成和整理 memory 带来的延迟与频繁变动。调用次数提供行为信号，AI 判断它是否稳定、可复用并符合长期 memory 的要求。为控制错误放大，我加入了 project/global separation、linked records、exception review 和 stale-memory leakage checks。我负责架构、边界、benchmark 与 release gate，并使用 AI 辅助完成 TypeScript/Node.js、MCP tools、CLI、hooks、local UI 和测试实现。

## 5 分钟版本

按这个顺序讲：

1. 用户问题：Agent 跨 session 工作时会丢上下文，也可能召回过时信息。
2. 系统边界：Cyrene 不改模型，不做训练；它处理 memory lifecycle 和 context assembly。
3. 数据流：candidate memory -> usage count -> weekly AI review -> promote/update/revoke -> project/global store -> linked records -> retrieval -> session context；异常候选进入人工 review queue。
4. 工程实现与职责：我负责问题定义、架构、系统边界、benchmark 和 release gate，使用 AI 辅助实现 TypeScript/Node.js、MCP tools、CLI、hooks、local UI、Vitest 和 GitHub Actions。
5. 验证方式：用 archived benchmark report、adversarial fixtures、real-project replay 和 release gate 说明验证范围。
6. 下一步：加入更系统的 eval set，覆盖 tool-call success、memory relevance、cross-session task completion。

## 证据账本（面试前核对）

公开入口：[Cyrene Continuity repository](https://github.com/mingxiangbian/cyrene-continuity)；[2026-06-06 benchmark report](https://github.com/mingxiangbian/cyrene-continuity/blob/main/benchmark/reports/2026-06-06/summary.md)。

| 可以说的 claim | 可定位 artifact | 面试表达 | 必须同时说的限制 |
| --- | --- | --- | --- |
| 项目有可运行的 benchmark/release gate | archived gate profile：67 cases 中 24 passed、43 skipped、0 failed | “The archived gate run passed its selected 24 cases with no failures.” | skipped 不是 passed；这是项目自己的 case catalog，不是行业 benchmark |
| full profile 覆盖更多 capability cases | archived full profile：67 total、59 passed、8 skipped、0 failed | “The full deterministic profile recorded 59 passed cases and 8 skipped cases.” | fixture 结果不能外推到生产用户或开放世界流量 |
| 有 repo-grounded task utility 检查 | archived real-replay profile 运行 4 个 repo-grounded cases | “I added four isolated repo-grounded replay cases instead of only unit-level checks.” | 仍是临时 fixture 与确定性任务，不是真实线上 A/B test |
| 针对跨项目污染和 stale memory 有对抗 fixture | expanded report 中相应 fixtures 记录 `crossProjectPollutionRate=0`、`staleMemoryLeakageRate=0` | “Those specific adversarial fixtures observed zero leakage; I use them as regression guards.” | 只能说“这些 fixtures 中为 0”，不能说系统已经彻底没有 leakage |
| release gate 记录模式延迟 | gate snapshot 记录 fast/balanced/review p95 为 38/48/119 ms | “The local fixture separates fast, balanced and review paths and gates their latency.” | 本地 deterministic fixture、单机环境，不代表生产 SLO |

表达顺序固定为：**claim → artifact/metric → scope/limitation**。若面试当天仓库或 CI 状态变化，以现场可打开的 artifact 为准，不背动态 badge 状态。

## 高频追问

### 为什么不让 candidate memory 即时、无条件晋升？

Cyrene 并没有放弃自动晋升，而是把判断延迟到每周一次的 memory maintenance。系统记录 memory 被模型实际用于任务执行或答案生成的次数，而不是把 retrieval hit 或 context injection 当作使用；再由 AI 判断它是否稳定、可复用并符合长期 memory 的要求。已有长期 memory 也在同一周期中根据实际使用次数和 AI 判断被保留、更新或撤销，敏感、冲突、模糊或高风险内容才转人工审核。这样避免每轮对话都整理 memory 的延迟与频繁变动，同时保留自动化。代价是新记忆可用得更晚，而且“模型是否实际使用”本身需要可靠的 attribution，AI 判断也仍可能出错。

这里有两个必须主动承认的风险。第一，实际使用次数是“被采用”的信号，不是“内容正确”的证据，错误 memory 仍可能因反复使用而形成自我强化。第二，模型是否真的使用了某条 memory 并不天然可观察；如果依赖模型自报或归因判断，计数本身也会有误差。因此使用次数只能作为一个输入，不能替代 AI 对内容有效性和冲突的判断；后续还应补 provenance、版本、可回滚记录、usage attribution checks 和针对错误强化的 regression checks。

### 错误 memory 怎么撤销？

撤销不是只靠人工发现。每周维护时，系统会重新检查已有长期 memory 的调用次数，并让 AI 判断它是否仍然有效、可复用；不再符合要求的记录会被更新或撤销。人工审核保留给敏感、冲突或高风险情况。面试时要说明，当前机制的薄弱点不是“没有撤销”，而是 AI 同时参与写入与撤销判断，可能产生相关性错误，所以需要可追踪的历史版本和独立 regression cases 来约束它。

### project memory 和 global memory 怎么分？

project memory 存项目内事实，比如 repo 结构、测试命令、模块边界。global memory 存跨项目偏好，比如用户的写作风格和工作流偏好。默认应该写 project memory，只有跨项目复用价值明确时才写 global memory。

### linked records 有什么用？

单条 memory 容易碎片化。linked records 让系统把同一决策、同一模块、同一 bug 的多条记录连起来。retrieval 时，系统可以召回一组相关 memory，而不是只拿到一条孤立片段。

### stale-memory leakage 怎么处理？

我用四类办法控制：project/global 分区；周度维护结合调用次数和 AI 判断，完成晋升、更新与撤销；人工 review queue 处理敏感和高风险例外；release checks 检查旧 memory 是否错误影响当前任务。面试时不要说它已经彻底解决。更准确的说法是：我把 leakage 当成 regression 风险，放进 release gate。

### 如果重做，你会改什么？

我会补三件事：

- 做一个标准化 eval set，覆盖 memory relevance、stale leakage、cross-session task completion。
- 给 memory 增加过期策略，比如 TTL、confidence、source scope。
- 把 retrieval logs 结构化，方便分析 bad case。

## 你要主动承认的边界

- Cyrene 是个人项目，没有线上用户规模。
- 现在的 benchmark 更像 release gate，不是大规模学术 benchmark。
- 可以引用 archived report 的具体数字，但必须连同 profile、日期和 skipped/fixture 边界一起说；不能把单个 fixture 的 `retrievalAccuracy=1` 说成整体 100% 准确率。
- 项目核心贡献在 memory lifecycle、context management、tool integration 和 eval thinking，不在模型训练。
