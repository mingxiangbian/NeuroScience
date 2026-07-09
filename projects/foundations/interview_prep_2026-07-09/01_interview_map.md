# 01 面试地图

## 三个岗位的面试差异

| 岗位 | 面试官想确认 | 你的证据 | 风险 |
| --- | --- | --- | --- |
| Coze 上下文工程 | 你是否理解 long-context、memory、prompt structuring、SFT/RL eval | Cyrene 的 layered memory、retrieval、stale-memory checks | 你没有 SFT/RL 实验，回答时要把经验放在 context/eval，不要装训练经验 |
| AI Agent开发-计算 | 你是否能写工程代码，理解 Agent framework、tool use、lifecycle、infra | TypeScript/Node.js、MCP、CLI、hooks、Vitest、GitHub Actions | 字节可能手撕代码，TypeScript 项目不等于算法题能力 |
| Agent评测-AI数据与安全 | 你是否会拆评测维度，能输出报告，能把 bad case 变成指标 | benchmark/release checks、review queue、failure-case taxonomy | 岗位偏运营/评测管理，不能只讲工程实现 |

## 第一轮面试可能结构

1. 5 分钟：自我介绍 + 为什么投这个岗位。
2. 20 分钟：深挖 Cyrene。
3. 20 分钟：岗位知识题。
4. 20 分钟：代码题或 case 题。
5. 5 分钟：反问。

字节研发岗更可能有代码题。评测岗更可能问 case：如何评估 Agent 的工具调用、检索、规划、推理链。

## 你的一分钟自我介绍

通用版：

> 我是电子信息工程 2027 届本科生，GPA 3.65/4.0。我的项目集中在 Agent memory、context management 和 applied ML。最近做了 Cyrene Continuity，一个给 Codex 用的 local-first memory plugin，用 TypeScript 和 Node.js 实现了 project/global memory stores、linked records、retrieval、review queue、MCP tools、CLI 和 release checks。我投这个岗位，是因为 JD 里的 long-context、Agent memory、tool use 或 Agent eval，和这个项目的核心问题重合。我希望在真实业务里继续做可运行、可评估的 Agent 系统。

Coze 版加一句：

> 我最想继续做的是长对话里哪些信息该进入 memory、什么时候召回、怎么防止 stale memory 影响当前任务。

Infra 版加一句：

> 我更关注 Agent 系统怎么接入 tools、hooks、CLI 和权限边界，怎么让它作为工程系统稳定运行。

Eval 版加一句：

> 我准备重点讲 Cyrene 里的 retrieval regression、stale-memory leakage 和 review workflow，因为这些能对应 Agent 评测里的工具调用、检索相关性和任务规划问题。

## 面试前必须准备的证据

- GitHub 仓库能打开，README 能说明安装、运行、核心设计。
- 准备 1 张 Cyrene 架构图，文字版也可：input -> candidate memory -> review queue -> approved memory -> retrieval -> session context。
- 准备 2 个失败案例：错误召回旧 memory、跨项目污染。
- 准备 1 个取舍：为什么 local-first，为什么 project/global 分开，为什么 pending queue 不自动写入。
- 准备 1 个扩展计划：如果进入团队，你会把 Cyrene 的 eval 扩展成哪些指标。
