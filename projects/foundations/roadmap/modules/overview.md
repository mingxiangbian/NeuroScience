---
id: overview
title: Overview
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: high
---

## Dashboard

目标岗位：**Agent / LLM Systems Engineer**。

目标难度：OpenAI / Anthropic / Google DeepMind / xAI 这类顶尖 AI Lab / AGI 团队。

当前策略不是从头开课，而是建立一个长期可复习、可扩展的知识库。主导航按能力模块组织，模块内部保留学习记录、时间线和知识笔记。

全局进度现在从 **0%** 开始，因为这些百分比代表“已经完成并可复述/可面试的学习进度”，不是页面内容的完整度。

核心优先级：

- 主线不是大项目，而是面试可用能力包。
- 第一优先级是 coding 和实现能力。
- 第二优先级是面试表达：能把设计、tradeoff、failure mode、eval 讲清楚。
- LLM/Agent 系统知识不从 0 讲起，而是拉深到可设计、可实现、可调试。
- Python + TypeScript 是主栈，Rust 只作为 45/60 天 optional add-on。

## Interview Signal

这个区块不替代 Dashboard。Dashboard 回答“这个项目现在是什么状态”，Interview Signal 只回答“如果明天面试，哪些信号强、哪些信号弱、哪些判断还没有证据”。

当前主判断：

- 最强可塑信号：Agent / LLM component implementation + eval / failure analysis。
- 当前最大风险：目标岗位过宽，容易把准备做成知识库，而不是可验证的面试表现。
- 需要先校准的真实 baseline：coding、LLM systems、Agent design、research discussion、behavioral communication。
- 当前证据资产：Foundations reader、Agent Runtime Casebook、RAG Evaluation Pack、Memory System Mini Portfolio、Trace Debugging Workbench。
- 近期校准动作：做一次 45 分钟 coding baseline 和一次 30 分钟 Agent system design mock，然后把扣分点写回对应模块。

### Signal Rubric

- Coding signal：45 分钟内完成 medium 题，并能解释 invariant、complexity、edge cases。
- Systems signal：能把 LLM / Agent system 拆成 state、tools、memory、eval、trace、failure recovery。
- Research signal：能从论文 claim 推到 system implication，不停留在论文名。
- Project signal：每个项目能讲清 problem、constraint、tradeoff、failure mode、verification。
- Communication signal：回答不只正确，还要让面试官听到假设、取舍和验证动作。

### Current Uncertainty

眼下最没有把握的是你的真实 baseline。没有 timed coding、mock system design 和 project deep dive 记录，任何进度判断都只能是计划假设。

## 模块总览

总知识地图拆成八个稳定模块：

- Coding：基础算法、Python fluency、TypeScript interfaces、optional Rust depth。
- LLM Systems：tokenization、attention、KV cache、batching、streaming、post-training、structured outputs。
- Agent Design：tool registry、tool router、planner loop、sandbox、approval gate、trace。
- RAG & Memory：chunking、retrieval、reranking、context assembly、freshness、privacy、memory conflict。
- Evals & Debugging：task success eval、regression eval、tool correctness、trace debugging、golden/adversarial sets。
- Research Reading：Transformer、scaling laws、instruction tuning、preference optimization、tool use、RAG、agent memory、evals。
- Behavioral / Strategy：STAR stories、project evidence、tradeoff answer、mock scoring rubric。
- Logs：Weekly Review Checklist、cross-module review、uncategorized notes、复盘。

模块关系：

- Coding 提供实现可信度。
- LLM Systems 和 Agent Design 提供系统设计骨架。
- RAG & Memory、Evals & Debugging 提供面试中最容易体现深度的 failure-mode 讨论。
- Research Reading 只服务 system design 和追问，不单独扩成论文综述。
- Behavioral / Strategy 和 Logs 负责把学习转成可讲的证据。

## 计划节奏

### 30/45/60-Day Plan

整体节奏可以按 30、45、60 天伸缩，不强行固定在 30 天：

- Week 1：Coding Baseline And Agent Vocabulary。建立 Python coding 节奏，写 `Tool Router`，练 2 分钟 tool-calling agent 回答。
- Week 2：Graphs, RAG, And Trace。做 tree/graph patterns，写 `Retrieval Evaluator`，练 production RAG。
- Week 3：DP / Heap / Memory System。做 heap/interval/DP，写 `Memory Store`，练 long-term memory design。
- Week 4：Mock Sprint And Integration。做 timed coding、system design mock、behavioral stories 和 drill portfolio summary。
- Days 31-45：深入 eval harness、multi-agent workflow、post-training / RLHF / DPO / RLVR。
- Days 46-60：只在基础稳定后做 capstone、Optional Rust Log Parser 或 Agent eval and trace workbench。

推荐项目方向（Project Recommendations）：

1. **Agent Runtime Casebook + Drills**：tool router、memory store、trace logger、eval harness 和 written design answers。
2. **RAG Evaluation Pack**：retrieval quality、citations、regression tests。
3. **Memory System Mini Portfolio**：write policy、retrieval、deletion、stale memory。
4. **Trace Debugging Workbench**：observability、replay、diff、latency/cost。
5. **Optional Rust Trace Parser**：只有 coding baseline 稳定后再做，用作 systems-depth add-on。

## 待补知识

公开岗位信号校准：

- [OpenAI AI Systems Engineer, Codex Agents](https://openai.com/careers/ai-systems-engineer-codex-agents-san-francisco/) 强调 coding agents、tool-using LLM systems、evals、inference behavior、logs/traces、runtime constraints、Rust/Python/API layers。
- [OpenAI Applied AI Engineer, Codex Core Agent](https://openai.com/careers/applied-ai-engineer-codex-core-agent-san-francisco/) 强调 shipping LLM products、Python、model evaluation、fine-tuning、prompt design 和 agent UX。
- [OpenAI Software Engineer, Agent Infrastructure](https://openai.com/careers/software-engineer-agent-infrastructure-san-francisco/) 强调 FastAPI/gRPC APIs、agentic infrastructure、research-production collaboration 和 scaling。
- [OpenAI Backend Software Engineer (Evals)](https://openai.com/careers/backend-software-engineer-%28evals%29-san-francisco/) 强调 AI agents、production evals、multi-agent workflows、tool use、long context 和 backend systems。
- [Anthropic Alignment roles](https://www.anthropic.com/careers/jobs/4631822008) 强调 empirical AI research、safety-relevant evals、multi-agent experiments 和 LLM-generated jailbreak eval tooling。
- [Google DeepMind Careers](https://deepmind.google/careers/) 中 Research Engineer role family 强调 engineering + ML/deep learning + research implementation，能 build and scale systems to test and evaluate ideas。

结论：这条路线必须把 coding、Agent/LLM implementation、eval、trace/debugging 和表达训练放在阅读之前。

6-agent debate 的收敛结论：

- Research Agent 想扩大论文阅读：限制为 high-signal reading，每组 reading 必须能转成 system design 或面试追问。
- CTO Agent 强调 production infra：保留 latency、cost、reliability、trace、eval，但不把准备变成云原生/SRE 复习。
- Coding Agent 要求可测量训练：每周固定 coding patterns 和 implementation drills。
- Product Agent 强调 agent UX：每个 design case 必须包含用户 workflow、failure recovery、human-in-the-loop。
- Strategy Agent 强调强信号：所有任务都要能产出面试叙事：我做了什么、为什么这样设计、怎么验证。

1. Python coding fluency。
2. Agent / LLM component implementation。
3. System design casebook。
4. Eval and failure analysis。
5. Mock interview expression。
6. Focused research reading。
7. Optional Rust systems-depth。
