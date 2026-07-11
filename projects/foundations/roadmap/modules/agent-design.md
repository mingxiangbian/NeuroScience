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
