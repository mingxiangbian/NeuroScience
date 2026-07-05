---
id: agent-design
title: Agent Design
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: high
---

## 目标

掌握 Agent runtime 的核心组件和 failure modes，并能把 tool calling、planner loop、safe execution、trace 和 user workflow 讲成完整 system design。

## 当前状态

Agent 是目标岗位主线之一。当前准备要避免只讲“planner + tools”的空泛架构，必须落到 schema validation、timeouts、permission model、human approval、observability 和 eval。

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
