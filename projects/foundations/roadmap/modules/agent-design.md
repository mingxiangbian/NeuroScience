---
id: agent-design
title: Agent Runtime
status: learning
learning_progress: 0
last_updated: 2026-07-18
priority: high
plan_scope: long-term
navigation_group: systems
module_role: domain
goal_role: 执行与安全运行时
subsystems: 5
---

## 目标

承担贾维斯六子系统中的 **⑤ Agent 执行**：把模型提出的意图变成可检查、可取消、可恢复的真实行动，并让用户始终保有权限与控制权。

模型可以提出下一步行动，但状态转换、参数校验、幂等、权限、安全策略和失败恢复必须由确定性的 Runtime 强制执行。

## 当前状态

Cyrene 0.0 已证明能够搭出 planner、tool use、memory 与 MCP 连接的 Agent 架构，也暴露了 vibe-coding 和验证不足的代价。旧 TypeScript 载体已归档为经验资产，不再继续堆功能。

U7 将用 Python 点火贾维斯 0.1：先建立最小连续对话循环，再让后续工具、记忆和多模态部件沿同一条 0.x 血脉生长。

## 核心知识

### Agent Runtime 核心组件

- planner / policy loop
- tool registry 与 schema validation
- deterministic state machine
- timeout、retry、cancellation 与 idempotency
- execution sandbox 与权限模型
- human approval gate
- short-term context 与 long-term memory interface
- trace events、audit log 与 replay boundary
- partial execution、rollback 与用户可见恢复

### 架构层次

- **Reasoning**：planning、task decomposition、tool selection、memory retrieval。
- **Runtime / Orchestration**：state machine、idempotency、timeout、retry、cancellation、human approval。
- **Platform**：queue、authorization、isolation、audit、scaling。
- **Evals / Security**：trace、regression eval、prompt injection、tool abuse、rollback criteria。

Agent Runtime 负责产生完整、稳定的执行事实；Evals & Diagnostics 负责判断这些事实是否满足行为契约，二者不维护两套 trace 定义。

### 核心风险

- tool hallucination 与参数错误
- prompt injection 与越权行动
- stale 或错误记忆影响决策
- runaway loop 与重复副作用
- hidden state mismatch
- timeout、部分成功与取消后的不一致
- latency / cost explosion
- 失败后用户无法理解或夺回控制

## 任务

### Python Tool Router

实现一个最小、可测试的工具路由器：

- 显式 tool registry
- 输入 schema validation
- timeout 与 cancellation
- 每次调用的 trace event
- 对风险动作要求 approval
- 对失败返回结构化结果，不把异常伪装成成功

### Safe Execution Layer

围绕一个真实工具建立：

- permission model
- file / network / process 边界
- sandbox 或最小权限策略
- approval gate 与审计记录
- 重试、幂等和部分执行恢复
- 滥用与 prompt injection case

### Runtime Loop

让 planner、tool、state 与用户控制形成最小闭环：

1. 模型提出结构化意图。
2. Runtime 校验权限、参数和当前状态。
3. 用户批准高风险动作。
4. 工具执行并返回结构化结果。
5. Runtime 保存 trace、更新状态或进入恢复路径。
6. Evals 对 tool correctness、task outcome 和 loop failure 做判断。

### 跨子系统整合

- **人格 × Agent**：表达风格不能绕过权限和安全策略。
- **记忆 × Agent**：记忆可以影响行动，但必须保留来源、置信度和纠错入口。
- **全系统恢复**：失败后解释发生了什么、哪些动作已完成、怎样撤销或继续。

## 时间线

- U7 点火：未开始；先建立 Python 最小对话循环与清晰接口，不复制 Cyrene 0.0 的全部功能。
- 首个工具解冻时：未开始；加入 schema、timeout、trace 和 approval，形成最小安全执行链。
- 记忆接入时：未开始；验证记忆怎样改变规划和工具选择，并加入错误记忆 case。
- 系统墙出现时：未开始；再进入 queue、并发、隔离、扩展和平台层，不提前扩张基础设施。
