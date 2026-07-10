# 01 面试地图

## 三个岗位的面试差异

| 岗位 | 面试官想确认 | 你的证据 | 风险 |
| --- | --- | --- | --- |
| Coze 上下文工程 | 你是否理解 long-context、memory、prompt structuring、SFT/RL eval | Cyrene 的 layered memory、retrieval、stale-memory checks | 你没有 SFT/RL 实验，回答时要把经验放在 context/eval，不要装训练经验 |
| AI Agent开发-计算 | 你是否能写工程代码，理解 Agent framework、tool use、lifecycle、infra | TypeScript/Node.js、MCP、CLI、hooks、Vitest、GitHub Actions | 字节可能手撕代码，TypeScript 项目不等于算法题能力 |
| Agent评测-AI数据与安全 | 你是否会拆评测维度，能输出报告，能把 bad case 变成指标 | benchmark/release checks、review queue、failure-case taxonomy | 岗位偏运营/评测管理，不能只讲工程实现 |

## 准备策略：共同底座 + 岗位 overlay

收到具体邀约前，不押注单一岗位：

- 共同底座：coding、Cyrene 证据、Agent system design、计算机基础、behavioral。
- Coze overlay：context engineering、long context、memory、post-training 概念与 eval。
- Infra overlay：runtime、tool execution、MCP、权限、安全、可靠性和 Node.js。
- Eval overlay：trace、failure taxonomy、自动/人工评测、数据质量与安全。

收到邀约后，未来 24 小时提高目标岗位 overlay 的训练权重，但不删除 coding 和项目深挖。Coze 当前是首选，Infra 第二，Eval 是相对更容易转化现有证据的岗位；这只是准备顺序，不代表用一个岗位的分数替代另外两个岗位的 hard gate。

## 第一轮面试可能结构

1. 5 分钟：自我介绍 + 为什么投这个岗位。
2. 20 分钟：深挖 Cyrene。
3. 20 分钟：岗位知识题。
4. 20 分钟：代码题或 case 题。
5. 5 分钟：反问。

字节研发岗更可能有代码题。评测岗更可能问 case：如何评估 Agent 的工具调用、检索、规划、推理链。

## 你的一分钟自我介绍

通用版：

> 我是电子信息工程 2027 届本科生，GPA 3.65/4.0。我的项目集中在 Agent memory、context management 和 applied ML。最近做了 Cyrene Continuity，一个给 Codex 用的 local-first memory plugin。我负责问题定义、架构、系统边界和 benchmark 设计，使用 AI 辅助实现 TypeScript/Node.js、project/global memory stores、retrieval、MCP tools、CLI 和 release checks，并负责 review 与 release gate。我投这个岗位，是因为 JD 里的 long-context、Agent memory、tool use 或 Agent eval，和这个项目的核心问题重合。我希望在真实业务里继续做可运行、可评估的 Agent 系统。

Coze 版加一句：

> 我最想继续做的是长对话里哪些信息该进入 memory、什么时候召回、怎么防止 stale memory 影响当前任务。

Infra 版加一句：

> 我更关注 Agent 系统怎么接入 tools、hooks、CLI 和权限边界，怎么让它作为工程系统稳定运行。

Eval 版加一句：

> 我准备重点讲 Cyrene 里的 retrieval regression、stale-memory leakage 和 review workflow，因为这些能对应 Agent 评测里的工具调用、检索相关性和任务规划问题。

## 面试前必须准备的证据

- GitHub 仓库能打开，README 能说明安装、运行、核心设计。
- 准备 1 张 Cyrene 架构图，文字版也可：input -> candidate memory -> usage count -> weekly AI review -> promote/update/revoke -> project/global memory -> retrieval -> session context；异常候选转人工 review queue。
- 准备 2 个失败案例：错误召回旧 memory、跨项目污染。
- 准备 1 个取舍：为什么 local-first，为什么 project/global 分开，为什么使用调用次数 + AI 判断进行周度晋升和撤销，而不是每轮即时整理。
- 准备 1 个扩展计划：如果进入团队，你会把 Cyrene 的 eval 扩展成哪些指标。
- 完成 D1 blind baseline：一题 coding、一题 Agent system design、一次 Cyrene deep dive；保留未经润色的 artifact。
- 准备 5 个来自不同真实项目的行为故事索引，不把所有问题都回答成 Cyrene。

## 求职侧并行检查

这不是每日训练主线，每两天最多花 15 分钟：

- JD-CV 对齐：每个 CV bullet 都能指向代码、报告或可解释的限制。
- Portfolio preflight：从 fresh clone 按 README 跑一次安装、测试和 benchmark 入口。
- 投递跟踪：有邀约就切换 overlay；没有反馈时先检查首屏证据和岗位匹配，不盲目扩大课程范围。
