---
id: llm-systems
title: LLM Systems
status: learning
learning_progress: 0
last_updated: 2026-08-07
priority: high
plan_scope: long-term
navigation_group: systems
module_role: domain
goal_role: 基座模型与推理系统
subsystems: 1,6
---

## 目标

承担贾维斯六子系统中的 **① 基座模型理解** 与 **⑥ 推理系统**。目标不是独自训练通用基座模型，而是理解模型如何学习、生成和受约束，并能把模型可靠地接入贾维斯 0.x。

这个模块最终要回答两类问题：模型为什么产生当前行为；系统如何在延迟、成本、上下文和可靠性约束下提供这个行为。

## 当前状态

已经有从零实现 decoder-only Transformer 和训练小模型的经验。U1 已通过 causal / non-causal 对照解释未来 token 泄漏、teacher forcing 与 training loss 的证据边界；详细实验笔记归入 Evals & Diagnostics。当前活动单元 U2 将比较 held-out teacher-forced loss 与自回归生成；后续 U3 完成失败分析，U4–U6 再把 post-training 原理接到人格试驾。

基座模型是必须理解的底层能力，推理系统是其他子系统运行的地基；两者都服务长期系统，不单独形成脱离贾维斯 0.x 的课程表。

下列“核心知识”是长期能力地图，不是 U1 的前置课程或逐项打卡清单。知识只在活动单元中形成可指认的理解或证据后登记。

## 核心知识

### ① 基座模型

- tokenization、embedding 与 context window
- causal attention、mask 与 position representation
- 训练目标、teacher forcing 与自回归生成
- sampling、temperature 与生成行为
- SFT、DPO、RLHF 等 post-training 方法的作用边界
- benchmark、loss 与真实行为之间的证据边界

需要能解释：

- 为什么 decoder 必须阻止当前位置看到未来 token。
- 为什么 teacher-forced loss 不能单独证明自回归生成质量。
- 为什么 long context 不等于长期记忆。
- 为什么 post-training 改变的是行为分布，而不是凭空创造稳定人格。

### ⑥ 推理系统

- KV cache 与 prefill / decode
- batching、streaming 与 cancellation
- context assembly 与 token budgeting
- model selection、fallback 与降级
- structured output、schema validation 与 retry
- latency、cost、throughput 与资源约束
- serving failure、版本变化与可观测性

需要能解释：

- 为什么 KV cache 会改变延迟、显存和 serving 设计。
- 为什么结构化输出仍需确定性的 schema 校验。
- 为什么更大的模型或更长的上下文不一定带来更好的系统行为。
- 哪些约束应由模型承担，哪些必须由 Agent Runtime 强制执行。

## 任务

### 当前验证链：U1–U3

- 保存错误掩码下的基线，再修复 causal mask。
- 同时比较 held-out loss 与自回归生成质量。
- 把失败原因、指标错位和修复证据写成可复核笔记。

### 人格试驾支撑：U4–U6

- 为 SFT 明确要改变的单一行为、训练数据与 before / after 样例。
- 为 DPO 明确偏好对、对照与行为评估，不把“跑通训练”当作成功。
- 记录模型行为没有变化或变坏时的原因假设。

### 推理系统实验模板

1. 写清要验证的系统约束：延迟、成本、上下文、输出契约或资源。
2. 固定模型、输入、环境和观测字段。
3. 建立简单基线，再只改变一个设计因素。
4. 保存输出、trace 和性能样本。
5. 说明结果如何改变贾维斯 0.x 的接口或设计决策。

## 时间线

- 当前：进行中；U1 已结算 causal mask 对照，U2 正在建立 teacher-forced 与自回归生成的指标对照。
- 人格试驾解冻时：未开始；U4–U6 补齐 SFT / DPO 的机制、对照和行为解释。
- 0.1 运行后：未开始；当上下文、流式输出、结构化返回或模型切换成为真实瓶颈时，加入对应推理实验。
- 系统墙出现时：未开始；按需进入 batching、KV cache、serving、成本或底层实现，不提前制造课程债。
