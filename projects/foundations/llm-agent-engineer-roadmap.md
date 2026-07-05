# LLM / Agent Systems Engineer Roadmap

## Profile And Target

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

## Supervisor Synthesis

6-agent debate 的收敛结论：

| 冲突 | 处理 |
| --- | --- |
| Research Agent 想扩大论文阅读 | 限制为 high-signal reading，每组 reading 必须能转成 system design 或面试追问 |
| CTO Agent 强调 production infra | 保留 latency、cost、reliability、trace、eval，但不把准备变成云原生/SRE 复习 |
| Coding Agent 要求可测量训练 | 每周固定 coding patterns 和 implementation drills |
| Product Agent 强调 agent UX | 每个 design case 必须包含用户 workflow、failure recovery、human-in-the-loop |
| Strategy Agent 强调强信号 | 所有任务都要能产出面试叙事：我做了什么、为什么这样设计、怎么验证 |

最终优先级：

1. Python coding fluency。
2. Agent / LLM component implementation。
3. System design casebook。
4. Eval and failure analysis。
5. Mock interview expression。
6. Focused research reading。
7. Optional Rust systems-depth。

## 1. Knowledge Map

### Coding Fundamentals

必须掌握到能限时写对：

- Arrays and strings：two pointers、sliding window、prefix sum。
- Hash maps and sets：frequency counting、dedup、index mapping。
- Stack and queue：monotonic stack、BFS queue。
- Trees：DFS recursion、iterative traversal、lowest common ancestor。
- Graphs：BFS/DFS、topological sort、shortest path basics。
- Heap：top-k、merge k lists、priority scheduling。
- Intervals：merge、sweep line basics。
- Greedy：排序后局部决策、反例检查。
- DP basics：1D/2D state、transition、base case。

面试表达要求：

- 先说 brute force。
- 再说 bottleneck。
- 再给 optimized approach。
- 写代码时主动说明 invariants。
- 结束时给 complexity 和 edge cases。

### Python / TypeScript Implementation

Python：

- clean function signatures
- dataclass / TypedDict
- heapq / deque / defaultdict
- async basics
- file and JSON handling
- testable small modules

TypeScript：

- typed interfaces
- async API wrappers
- discriminated unions for tool calls
- error result types
- simple Node service structure

### LLM Systems

核心概念：

- tokenization and context windows
- attention and KV cache intuition
- batching, streaming, rate limits
- latency and cost tradeoff
- prompt assembly and context budgeting
- model selection and fallback
- structured outputs and schema validation

### Agent Systems

核心组件：

- planner / policy loop
- tool registry
- tool router
- execution sandbox
- short-term context
- long-term memory
- trace logger
- eval harness
- human approval gate

核心风险：

- tool hallucination
- prompt injection
- stale memory
- runaway loops
- hidden state mismatch
- eval overfitting
- latency explosion

### RAG And Memory

必须会解释：

- chunking strategy
- embedding retrieval
- reranking
- metadata filtering
- context assembly
- citation and provenance
- freshness
- deletion and privacy
- memory write policy
- memory conflict resolution

### Eval And Debugging

必须会设计：

- task success eval
- regression eval
- tool-use correctness eval
- latency/cost metrics
- human review sampling
- trace-based debugging
- golden set and adversarial set
- failure taxonomy

## 2. 30/45/60-Day Plan

每天时间不固定时，用三层任务：

- `minimum`：30-45 分钟，维持连续性。
- `standard`：2-3 小时，推荐强度。
- `stretch`：有额外时间时做，用来冲击高信号。

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

适合还有时间时继续：

- 每周 2 次 timed coding。
- 深入 eval harness：golden set、adversarial set、regression suite。
- 加一个 multi-agent workflow case：planner-worker-reviewer。
- 读 post-training / RLHF / DPO / RLVR 概念，并能解释它们和 Agent eval 的关系。

### Days 46-60: Top Lab Signal Extension

适合冲顶尖团队：

- 做 1 个 capstone only if time permits：Agent eval and trace workbench。
- optional Rust module：写一个小型 sandbox runner 或 log parser。
- 练 research-engineering discussion：如何把 ambiguous failure 转成 experiment。
- 做 3 次 full mock，并按 rubric 复盘。

## 3. Coding Plan

### Weekly Pattern Allocation

| Week | Patterns | Target |
| --- | --- | --- |
| 1 | arrays, strings, hash maps, sliding window | 写稳基础题，减少语法和边界错误 |
| 2 | trees, graphs, BFS, DFS | 建立 recursion / traversal / visited set 直觉 |
| 3 | heap, intervals, greedy, DP basics | 覆盖中频题型 |
| 4 | mixed mock | 提升限时表现和解释质量 |

### Daily Coding Loop

1. 3 分钟澄清输入输出和 edge cases。
2. 5 分钟写 brute force 和瓶颈。
3. 20-35 分钟写 optimized solution。
4. 5 分钟手动跑测试。
5. 5 分钟写复盘：pattern、bug、复杂度。

### Python Standards

每题必须做到：

- 函数签名清楚。
- 不依赖全局变量。
- 变量名能表达含义。
- 主动处理 empty input、single item、duplicates。
- 复杂度能说出来。

### TypeScript Standards

TypeScript 不作为算法主语言，主要用于 Agent interfaces：

- `ToolCall`
- `ToolResult`
- `AgentTrace`
- `MemoryRecord`
- `EvalCase`

用它训练 API boundary 和 schema thinking。

## 4. System Design Plan

### Answer Template

每个 design case 用同一套结构：

1. Clarify requirements。
2. Define success metrics。
3. State assumptions。
4. Draw components。
5. Explain data flow。
6. Identify failure modes。
7. Propose evals and monitoring。
8. Discuss tradeoffs and follow-ups。

### Case 1: Design A Production RAG System

必须覆盖：

- ingestion pipeline
- chunking and metadata
- embedding and index
- retrieval and reranking
- context assembly
- citations
- freshness
- prompt injection defense
- eval: recall@k, answer faithfulness, latency, cost

### Case 2: Design An Agent Runtime With Tool Calling

必须覆盖：

- tool registry
- schema validation
- planner loop
- execution timeout
- retry policy
- trace logger
- human approval for risky tools
- eval: tool selection accuracy, task success, loop failures

### Case 3: Design Long-Term Memory For A Personal Assistant

必须覆盖：

- what should be remembered
- write policy
- retrieval policy
- update/delete policy
- privacy and user control
- conflict resolution
- stale memory detection
- eval: precision of memory use, harmful memory rate

### Case 4: Design An Eval Harness For Agent Regressions

必须覆盖：

- task set
- graders
- golden traces
- adversarial cases
- CI integration
- pass/fail thresholds
- flaky eval handling
- model and prompt versioning

### Case 5: Design Trace Debugging For Multi-Step LLM Workflows

必须覆盖：

- trace schema
- span hierarchy
- prompt/tool/model events
- latency/cost aggregation
- redaction
- replay
- diff between runs

### Case 6: Design A Safe Tool Execution Layer

必须覆盖：

- permission model
- sandboxing
- file/network restrictions
- approval gates
- audit logs
- abuse cases
- recovery from partial execution

## 5. Research Reading List

阅读原则：只读能转化为面试答案的材料。

| Topic | Read | Need To Know | Interview Use |
| --- | --- | --- | --- |
| Transformer basics | Attention Is All You Need | attention, positional encoding, encoder/decoder intuition | 解释 LLM inference 和 context limits |
| Scaling | Kaplan scaling laws, Chinchilla | data/model/compute tradeoff | 讨论模型能力和成本边界 |
| Instruction tuning | InstructGPT | SFT, RLHF, human preference | 解释 post-training 为什么重要 |
| Preference optimization | DPO, PPO basics | reward model vs direct preference optimization | 回答 RLHF / DPO 追问 |
| Tool use | ReAct, Toolformer | reasoning + acting, tool selection | 设计 tool-calling agents |
| RAG | Lewis RAG paper plus modern retrieval notes | retrieval, generation, faithfulness | 设计 production RAG |
| Agent memory | Generative Agents, MemGPT, LLM agent memory surveys | memory write/read, reflection, context management | 设计 long-term memory |
| Evals | OpenAI evals ideas, HELM-style thinking, agent eval discussions | eval set, graders, contamination, regression | 设计 eval harness |

每篇 reading 的输出只要 5 行：

1. paper claim
2. mechanism
3. limitation
4. interview question it helps answer
5. one system design implication

## 6. Mock Interview Set

### Coding

1. Longest substring without repeating characters。
2. Merge intervals。
3. Top K frequent elements。
4. Number of islands。
5. Course schedule。
6. LRU cache。
7. Word ladder 或 shortest path variant。
8. Coin change。

Strong signal:

- clarify edge cases
- write clean Python
- test manually
- explain complexity

Weak signal:

- jump into code without constraints
- cannot debug own code
- cannot explain why algorithm works

### Python / TypeScript Implementation

1. Implement a tool router with schema validation。
2. Implement an in-memory vector retrieval stub and recall@k evaluator。
3. Implement a trace logger for an agent loop。
4. Implement retry with timeout and exponential backoff。
5. Define TypeScript interfaces for ToolCall, ToolResult, AgentTrace。

Strong signal:

- small testable units
- clear error handling
- typed boundaries
- observability hooks

### LLM Fundamentals

1. Explain attention and why KV cache matters。
2. Explain why long context is not the same as memory。
3. Explain SFT vs RLHF vs DPO。
4. Explain why benchmark scores can mislead。
5. Explain temperature, sampling, and structured outputs。

### Agent System Design

1. Design a coding agent runtime。
2. Design a RAG assistant for internal engineering docs。
3. Design long-term memory for a personal assistant。
4. Design evals for an autonomous workflow agent。
5. Design a safe tool execution layer。

### Behavioral And Project Deep Dive

1. Tell me about a project where requirements were ambiguous。
2. Tell me about a time you debugged a difficult issue。
3. Tell me about a tradeoff you made between speed and correctness。
4. Tell me about a time you changed your mind after evidence。
5. Walk me through a system you built and what you would improve。

## 7. Mini Implementation Drills

### Drill 1: Tool Router

Build:

- Python tool registry
- JSON schema validation
- timeout wrapper
- trace event for each call

Interview story:

- tool calling needs validation, permissions, timeouts, and observability.

### Drill 2: Retrieval Evaluator

Build:

- document list
- query set
- expected relevant ids
- recall@k and failure report

Interview story:

- RAG quality is measured before generation, not only by final answer.

### Drill 3: Memory Store

Build:

- write/read/update/delete
- metadata tags
- conflict detection
- deletion test

Interview story:

- long-term memory requires write policy, user control, and stale memory handling.

### Drill 4: Agent Trace Logger

Build:

- trace id
- spans for model call, tool call, retrieval
- latency and error fields
- redaction policy

Interview story:

- agents fail across steps; trace is the debugging primitive.

### Drill 5: Eval Harness

Build:

- test cases
- expected outcomes
- grader functions
- pass/fail summary

Interview story:

- agent regressions need evals tied to tasks, not only unit tests.

### Drill 6: TypeScript Agent Interface

Build:

- `ToolCall`
- `ToolResult`
- `AgentState`
- `AgentTrace`
- `EvalCase`

Interview story:

- typed interfaces clarify boundaries between model, tools, runtime, and UI.

### Drill 7: Streaming Wrapper

Build:

- async token stream simulator
- cancellation
- partial output handling
- error event

Interview story:

- user experience and runtime control matter for production LLM systems.

### Drill 8: Optional Rust Log Parser

Build:

- parse JSONL traces
- aggregate latency by span type
- output slowest traces

Interview story:

- Rust is optional depth: useful for performance/system credibility, not core preparation.

## 8. Project Recommendations

Do not start with a large project. Use this priority:

1. **Agent Runtime Casebook + Drills**  
   Best current fit. Combines tool router, memory store, trace logger, eval harness, and written design answers.

2. **RAG Evaluation Pack**  
   Good if applying to evals, applied AI, or backend LLM roles. Focus on retrieval quality, citations, regression tests.

3. **Memory System Mini Portfolio**  
   Good if interviewing for personal assistant or agent memory roles. Focus on write policy, retrieval, deletion, stale memory.

4. **Trace Debugging Workbench**  
   Good extension for top lab signal. Focus on observability, replay, diff, latency/cost.

5. **Optional Rust Trace Parser**  
   Only if coding baseline is stable. Use as a systems-depth add-on.

## 9. Strategy Rubric

Score yourself weekly from 1 to 5:

| Dimension | 1 | 3 | 5 |
| --- | --- | --- | --- |
| Coding correctness | Cannot finish medium | Finishes with hints | Finishes cleanly and explains |
| Coding communication | Silent or scattered | Explains main idea | Clarifies, narrates, tests |
| LLM systems | Knows terms | Explains components | Designs with tradeoffs and evals |
| Agent design | Generic loop | Names tools/memory | Handles safety, trace, failure |
| Research depth | Name-drops papers | Explains claims | Connects papers to systems |
| Behavioral | Vague stories | STAR-ish | Crisp, evidence-backed, reflective |
| Project evidence | No artifacts | Small scripts | Drills tied to interview stories |

Weekly target:

- Week 1: average 2.5
- Week 2: average 3
- Week 3: average 3.5
- Week 4: average 4
- Day 45+: push weakest two dimensions toward 4
- Day 60+: one standout dimension should reach 5

## 10. Weekly Review Checklist

Every week, answer:

1. Which coding pattern still causes mistakes?
2. Which system design case can I explain without notes?
3. Which Agent/LLM component did I implement?
4. What failure mode did I learn to detect?
5. Which answer sounded vague during mock practice?
6. What is one artifact I can mention in an interview?
7. What should I cut next week because it is not interview-relevant?

If a week goes badly, do not restart the whole plan. Repeat the current week with only `minimum` and `standard` tasks.
