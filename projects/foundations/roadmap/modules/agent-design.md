---
id: agent-design
title: Agent Design
status: learning
learning_progress: 0
last_updated: 2026-07-10
priority: high
---

## 目标

掌握 Agent runtime 的核心组件和 failure modes，并能把 tool calling、planner loop、safe execution、trace 和 user workflow 讲成完整 system design。

## 当前状态

Agent 是目标岗位主线之一。当前自评只接触过 Reasoning 层的 planner、tool use 等表层概念；Runtime、Platform、Evals / Security 尚未系统学习。当前进入学习状态，但在未见 system design 中独立达到 readiness level 2 前，学习进度保持 0%。

## 核心知识

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

### Production Agent Architecture Layers

- Reasoning：planning、task decomposition、tool selection、memory retrieval。
- Runtime / Orchestration：state machine、idempotency、timeout、retry、cancellation、human approval。
- Platform：queue、multi-tenant isolation、authorization、audit、scaling。
- Evals / Security：trace、regression eval、prompt injection、tool abuse、rollback criteria。

关键边界：LLM 可以提出下一步行动，但幂等、权限、状态转换和安全策略必须由确定性的 Runtime / Platform 层强制执行。

## 任务

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

### Case 6: Design A Safe Tool Execution Layer

必须覆盖：

- permission model
- sandboxing
- file/network restrictions
- approval gates
- audit logs
- abuse cases
- recovery from partial execution

### Drill 1: Tool Router

Build：

- Python tool registry
- JSON schema validation
- timeout wrapper
- trace event for each call

Interview story：

- tool calling needs validation, permissions, timeouts, and observability.

### Drill 6: TypeScript Agent Interface

Build：

- `ToolCall`
- `ToolResult`
- `AgentState`
- `AgentTrace`
- `EvalCase`

Interview story：

- typed interfaces clarify boundaries between model, tools, runtime, and UI.

### Drill 7: Streaming Wrapper

Build：

- async token stream simulator
- cancellation
- partial output handling
- error event

Interview story：

- user experience and runtime control matter for production LLM systems.

## 时间线

- Week 1：写 50-100 行 Python tool router；练 `How would you design a tool-calling agent?`
- Week 1 stretch：用 TypeScript 写 tool schema interface。
- Week 4：把 Week 1-3 drills 包装成 project narrative。
- Days 31-45：加一个 multi-agent workflow case：planner-worker-reviewer。
- Days 46-60：如果需要 capstone，把 Agent runtime、trace、eval 合成 Agent eval and trace workbench。

## 知识笔记

### Reliable Tool Execution

核心理解：

- 幂等的目标是让同一个逻辑 operation 即使被重复投递，也最多产生一次有效副作用。
- `operation_id` 标识逻辑操作，`attempt_id` 标识单次调用尝试，`idempotency_key` 把重复请求映射回同一个 operation。
- 调用超时只表示调用方不知道结果，应进入 `UNKNOWN / RECONCILING`，不能直接当作 `FAILED` 重试。
- 重复事件命中唯一键后返回已有 operation；reconciler 再根据下游的 `SUCCEEDED / RUNNING / NOT_FOUND` 状态完成确认或使用相同 key 重试。
- 工具端若不支持幂等键和状态查询，就无法完全消除“副作用已发生但响应丢失”的不确定性。

常见误区：

- 用语义相似度代替稳定 event / command ID 判断重复投递。
- 把 timeout 当作 failure，直接重试有副作用的工具。
- 为每次网络重试创建新的 operation，导致重复执行和审计状态分裂。
- 声称天然 exactly-once；更准确的目标是通过去重、幂等和对账实现 effectively-once。

面试转译：

- “I separate a logical operation from its network attempts. A timeout moves the operation into an unknown state, and a reconciler resolves it before any retry with the same idempotency key.”

复习提示：

- 后续继续学习 transactional outbox、retry/backoff、circuit breaker、compensation、idempotency retention 和跨租户 operation store。
- D+2 先做结构化学习检查点：复述四层架构、operation state machine 和 reliable tool execution，并完成第一份 guided artifact，不判 hard gate。
- 完成前置学习后，再用未见场景复测：工具已产生副作用但响应超时，同时发生重复投递和跨租户恶意指令。

### Agent Runtime With Tool Calling

核心理解：

- Agent runtime 不是一个简单 loop，而是 tool registry、router、executor、trace logger、approval gate 的组合。
- Tool calling 必须覆盖 schema validation、execution timeout、retry policy、trace logger、risky-tool approval。
- eval 至少包括 tool selection accuracy、task success、loop failures。

常见误区：

- 把 tools 当成 prompt 里的字符串，而不是 typed, permissioned interfaces。
- 只画 planner + tools，不讲权限、timeout、partial execution 和可复现 trace。

面试转译：

- “I would treat tools as typed, permissioned interfaces, not just strings in a prompt.”

### Safe Tool Execution Layer

核心理解：

- Safe Tool Execution Layer 要覆盖 permission model、sandboxing、file/network restrictions、approval gates、audit logs、abuse cases 和 recovery。
- Risky tools need approval gates and audit logs; safe tools can be executed automatically with timeout and retry policy。

常见误区：

- 只说 sandbox，但不说明什么操作需要用户批准、日志怎样审计、失败后如何恢复。

面试转译：

- “Every model/tool/retrieval step needs a trace span, otherwise debugging multi-step failures becomes guesswork.”

### Tool Router

核心理解：

- Drill 1: Tool Router 包含 Python tool registry、JSON schema validation、timeout wrapper、trace event for each call。
- TypeScript Agent Interface 包含 `ToolCall`、`ToolResult`、`AgentState`、`AgentTrace`、`EvalCase`。

相关资料：

- Tool use：ReAct、Toolformer。Need to know：reasoning + acting、tool selection。
- Agent memory：Generative Agents、MemGPT、LLM agent memory surveys。Need to know：memory write/read、reflection、context management。

复习提示：

- Agent design 的强信号不是“我会写一个 loop”，而是知道 loop 会怎样坏掉：错误 tool、错误参数、无限循环、权限越界、partial execution、不可复现 trace。
