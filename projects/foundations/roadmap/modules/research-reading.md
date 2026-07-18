---
id: research-reading
title: Research Reading
status: not-started
learning_progress: 0
last_updated: 2026-07-18
priority: medium
plan_scope: long-term
navigation_group: practice
module_role: support
goal_role: 研究证据
subsystems: 1,2,3,4,5,6
---

## 目标

为当前活动单元提供必要的研究证据、机制解释和竞争假设。阅读不是独立课程，也不按论文数量结算；只有当它解释一个机制、改善一种评估、暴露错误假设或改变贾维斯 0.x 的设计决策时，才进入长期路线。

## 当前状态

Research Reading 是由问题触发的横向支撑能力。U1–U3 启动后只读取解释 causal mask、teacher forcing、自回归生成与评估错位所需的材料；人格、记忆、多模态和系统论文保持冻结，等对应单元解冻再读。

## 核心知识

### 触发条件

满足任一条件才开启 reading：

- 活动单元遇到无法解释的机制或失败。
- 需要为实验选择对照、指标或 baseline。
- 两种设计都有合理依据，需要比较竞争假设。
- 新证据可能推翻当前子系统判断。
- 准备进入候选专长试驾，需要建立最小领域地图。

### 阅读判断框架

- **Question**：它实际回答了什么问题。
- **Claim**：作者主张什么，结论强到什么程度。
- **Evidence**：数据、任务、对照、统计和消融是否支持该主张。
- **Mechanism**：结果说明了哪一层机制，哪些只是相关或预测。
- **Limitation**：样本、环境、模型、任务和泛化边界。
- **Competing hypothesis**：还有什么解释同样符合证据。
- **System implication**：它会改变哪个接口、实验、eval 或设计决策。

### 六子系统的研究入口

- **① 基座模型**：Transformer、训练目标、scaling、post-training 与生成行为。
- **② 人格与情感**：preference optimization、persona consistency、affective interaction 与行为评估。
- **③ 终身记忆**：写入、整合、遗忘、反思、长期一致性与用户控制。
- **④ 实时多模态**：语音、视觉、全双工交互、打断、延迟与 HCI。
- **⑤ Agent 执行**：tool use、planning、runtime、安全与人类审批。
- **⑥ 系统层**：inference、serving、端侧、成本、容量与可靠性。

这些只是检索入口，不是预先排好的阅读清单。

## 任务

### 最小研究卡

每次只保留能服务活动单元的内容：

1. 当前问题。
2. 一条核心 claim。
3. 支持它的关键 evidence。
4. mechanism 与 competing hypothesis。
5. 主要 limitation。
6. 对当前实验、评估或设计的具体影响。
7. 一个仍未解决的问题。

### 理论单元结算

当阅读本身构成理论单元时，需要：

- 不看资料复述核心机制。
- 把机制连接到当前贾维斯子系统。
- 指出证据不能推出什么。
- 留下一个可由实现、实验或后续检索回答的问题。

## 时间线

- 活动单元启动时：未开始；先列未知项，只读阻塞当前动作的最小材料。
- 实验设计前：未开始；补 baseline、指标、对照和已知 failure mode。
- 实验结果反常时：未开始；检索竞争解释，不用更多阅读替代复现与诊断。
- 校准触发时：未开始；只回看改变过判断的研究卡，并更新当前假设与置信度。
