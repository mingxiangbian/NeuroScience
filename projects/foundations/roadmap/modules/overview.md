---
id: overview
title: Overview
status: in-progress
progress: 45
last_updated: 2026-07-05
priority: high
---

## 目标

目标岗位：**Agent / LLM Systems Engineer**。

目标难度：OpenAI / Anthropic / Google DeepMind / xAI 这类顶尖 AI Lab / AGI 团队。

当前策略：

- 主线不是大项目，而是面试可用能力包。
- 第一优先级是 coding 和实现能力。
- 第二优先级是面试表达：能把设计、tradeoff、failure mode、eval 讲清楚。
- LLM/Agent 系统知识不从 0 讲起，而是拉深到可设计、可实现、可调试。
- Python + TypeScript 是主栈，Rust 只作为 45/60 天 optional add-on。

公开岗位信号校准：

- [OpenAI AI Systems Engineer, Codex Agents](https://openai.com/careers/ai-systems-engineer-codex-agents-san-francisco/) 强调 coding agents、tool-using LLM systems、evals、inference behavior、logs/traces、runtime constraints、Rust/Python/API layers。
- [OpenAI Applied AI Engineer, Codex Core Agent](https://openai.com/careers/applied-ai-engineer-codex-core-agent-san-francisco/) 强调 shipping LLM products、Python、model evaluation、fine-tuning、prompt design 和 agent UX。
- [OpenAI Software Engineer, Agent Infrastructure](https://openai.com/careers/software-engineer-agent-infrastructure-san-francisco/) 强调 FastAPI/gRPC APIs、agentic infrastructure、research-production collaboration 和 scaling。
- [OpenAI Backend Software Engineer (Evals)](https://openai.com/careers/backend-software-engineer-%28evals%29-san-francisco/) 强调 AI agents、production evals、multi-agent workflows、tool use、long context 和 backend systems。
- [Anthropic Alignment roles](https://www.anthropic.com/careers/jobs/4631822008) 强调 empirical AI research、safety-relevant evals、multi-agent experiments 和 LLM-generated jailbreak eval tooling。
- [Google DeepMind Careers](https://deepmind.google/careers/) 中 Research Engineer role family 强调 engineering + ML/deep learning + research implementation，能 build and scale systems to test and evaluate ideas。

结论：这条路线必须把 coding、Agent/LLM implementation、eval、trace/debugging 和表达训练放在阅读之前。

## 当前状态

6-agent debate 的收敛结论：

- Research Agent 想扩大论文阅读：限制为 high-signal reading，每组 reading 必须能转成 system design 或面试追问。
- CTO Agent 强调 production infra：保留 latency、cost、reliability、trace、eval，但不把准备变成云原生/SRE 复习。
- Coding Agent 要求可测量训练：每周固定 coding patterns 和 implementation drills。
- Product Agent 强调 agent UX：每个 design case 必须包含用户 workflow、failure recovery、human-in-the-loop。
- Strategy Agent 强调强信号：所有任务都要能产出面试叙事：我做了什么、为什么这样设计、怎么验证。

最终优先级：

1. Python coding fluency。
2. Agent / LLM component implementation。
3. System design casebook。
4. Eval and failure analysis。
5. Mock interview expression。
6. Focused research reading。
7. Optional Rust systems-depth。

## 核心知识

总知识地图拆成八个稳定模块：

- Coding：基础算法、Python fluency、TypeScript interfaces、optional Rust depth。
- LLM Systems：tokenization、attention、KV cache、batching、streaming、post-training、structured outputs。
- Agent Design：tool registry、tool router、planner loop、sandbox、approval gate、trace。
- RAG & Memory：chunking、retrieval、reranking、context assembly、freshness、privacy、memory conflict。
- Evals & Debugging：task success eval、regression eval、tool correctness、trace debugging、golden/adversarial sets。
- Research Reading：Transformer、scaling、instruction tuning、preference optimization、tool use、RAG、agent memory、evals。
- Behavioral / Strategy：STAR stories、project evidence、tradeoff answer、mock scoring rubric。
- Logs：weekly review、cross-module reflection、uncategorized notes。

## 任务

每天时间不固定时，用三层任务：

- `minimum`：30-45 分钟，维持连续性。
- `standard`：2-3 小时，推荐强度。
- `stretch`：有额外时间时做，用来冲击高信号。

任何一天中断时，不做补偿性堆积；下一天回到当前模块的 `minimum` 和 `standard`。

## 时间线

### 30/45/60-Day Plan

### Week 1: Coding Baseline And Agent Vocabulary

目标：建立节奏，补齐基础表达。

`minimum`：

- 1 道 Python coding 题。
- 10 分钟复盘：bug、复杂度、可复用 pattern。
- 读一个 Agent 系统概念：tool calling、RAG、memory、eval 任选一个。

`standard`：

- 2 道 coding 题：array/hash map/sliding window。
- 写一个 50-100 行 Python tool router。
- 练 1 个 2 分钟口头回答：`How would you design a tool-calling agent?`

`stretch`：

- 用 TypeScript 写同一个 tool schema interface。
- 做一次 30 分钟 mock coding，限制时间。

产出：

- `tool_router.py`
- 10 道 coding 题复盘笔记
- 1 页 `tool-calling agent` design answer

### Week 2: Graphs, RAG, And Trace

目标：把 coding patterns 接到 LLM system components。

`minimum`：

- 1 道 tree/graph 题。
- 画一个 RAG data flow。
- 写 5 行 failure notes。

`standard`：

- 8-10 道 tree/graph/BFS/DFS 题。
- 写一个 mini retrieval evaluator：输入 query、documents、expected doc ids，输出 recall@k。
- 练 system design：`Design a production RAG system`。

`stretch`：

- 给 retrieval evaluator 加 TypeScript API wrapper。
- 加 trace log：query、retrieved docs、latency、score。

产出：

- `retrieval_eval.py`
- RAG case answer
- failure taxonomy: bad chunking, stale docs, wrong citation, prompt injection

### Week 3: DP / Heap / Memory System

目标：处理中高频 coding，并能讲长期 memory tradeoff。

`minimum`：

- 1 道 heap、interval 或 DP basic 题。
- 写一个 memory design bullet answer。

`standard`：

- 8-10 道 heap/interval/DP 题。
- 实现一个 JSON-backed memory store：write、retrieve、update、delete。
- 练 system design：`Design long-term memory for a personal assistant`。

`stretch`：

- 给 memory store 加 conflict resolution。
- 加 eval：memory 是否应该写入、是否应该删除。

产出：

- `memory_store.py`
- memory design case
- 1 个 behavioral story：如何在 ambiguity 下做取舍

### Week 4: Mock Sprint And Integration

目标：进入可面试状态。

`minimum`：

- 1 道 mixed coding 题。
- 复述一个 system design case。

`standard`：

- 2 次 timed coding mock。
- 2 次 system design mock。
- 写一个 agent trace/debugging answer。
- 整理 5 个 behavioral stories。

`stretch`：

- 做一轮 full loop mock：coding 45 分钟 + system design 45 分钟 + behavioral 20 分钟。
- 把 Week 1-3 drills 包装成一个 project narrative。

产出：

- mock score sheet
- 3 个 system design answers
- 5 个 behavioral stories
- mini drill portfolio summary

### Days 31-45: Depth Extension

- 每周 2 次 timed coding。
- 深入 eval harness：golden set、adversarial set、regression suite。
- 加一个 multi-agent workflow case：planner-worker-reviewer。
- 读 post-training / RLHF / DPO / RLVR 概念，并能解释它们和 Agent eval 的关系。

### Days 46-60: Top Lab Signal Extension

- 做 1 个 capstone only if time permits：Agent eval and trace workbench。
- optional Rust module：写一个小型 sandbox runner 或 log parser。
- 练 research-engineering discussion：如何把 ambiguous failure 转成 experiment。
- 做 3 次 full mock，并按 rubric 复盘。

## 资源

推荐项目方向：

1. **Agent Runtime Casebook + Drills**：最佳当前 fit。组合 tool router、memory store、trace logger、eval harness 和 written design answers。
2. **RAG Evaluation Pack**：适合 evals、applied AI、backend LLM roles。重点是 retrieval quality、citations、regression tests。
3. **Memory System Mini Portfolio**：适合 personal assistant 或 agent memory roles。重点是 write policy、retrieval、deletion、stale memory。
4. **Trace Debugging Workbench**：适合 top lab signal。重点是 observability、replay、diff、latency/cost。
5. **Optional Rust Trace Parser**：只有 coding baseline 稳定后再做，用作 systems-depth add-on。

## 反思

总览页不要追求“每天都完成计划”的假线性叙事。更真实的叙事是：能力模块会反复回归、螺旋深入。全局时间线只负责节奏校准，具体成长轨迹放到每个模块的 `时间线` 和 `Logs`。

## 面试表达

总叙事模板：

1. 我选择了 Agent / LLM Systems Engineer 作为目标，因为岗位同时需要 coding、LLM systems、agent runtime、eval 和 production debugging。
2. 我没有先做一个大而散的 demo，而是拆成 tool router、retrieval evaluator、memory store、trace logger、eval harness 这些可测量 drills。
3. 每个 drill 都能对应一个 system design case 和一个 failure mode。
4. 我的准备目标不是背概念，而是在面试中能写、能设计、能解释 tradeoff、能给 eval。

## 验收标准

- 能在 45 分钟内完成中等 Python coding 题，并解释复杂度。
- 能独立讲清至少 4 个 system design case。
- 能把每个 mini drill 讲成“问题、约束、设计、失败模式、验证”的面试故事。
- 能解释 high-signal reading 的 claim、mechanism、limitation、interview use 和 system design implication。
- 每周 strategy rubric 至少有两个维度提升。

## 下一步

- 先推进 Coding、Agent Design、RAG & Memory、Evals & Debugging 四个高权重模块。
- 每周只做一次总览复盘，不把 Overview 变成流水账。
- 后续新增材料时优先落到能力模块，而不是新增全局时间目录。
