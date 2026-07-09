# 08 网站冲刺模块 — 现成源文件与安装步骤

设计原则（沿用你自己在 Logs 模块定下的架构）：**主导航按能力模块，时间叙事放模块内时间线**。
所以 7 天冲刺不做成内容板块，而是一个与 Logs 同类的横向「时间驾驶舱」模块：只管"昨天学了什么、今天学什么、进度打勾"，知识本体全部沉淀进现有能力模块。冲刺结束后 status 改 done 归档，foundations 恢复 60 天节奏。

## 安装步骤（4 步）

1. 把下面代码块内容存为 `projects/foundations/roadmap/modules/interview-sprint.md`
2. 在 `projects/foundations/scripts/build-roadmap-data.mjs` 顶部 `MODULES` 数组中登记 `interview-sprint`（建议放在 overview 之后、logs 之前，让它显眼）
3. `node projects/foundations/scripts/build-roadmap-data.mjs && node tests/foundations-roadmap-requirements.mjs`
4. commit + push，刷新站点确认模块出现

> 动仓库前先读仓库根目录的 AGENTS.md，以仓库规则为准。

## 模块源文件（整块复制）

```md
---
id: interview-sprint
title: Interview Sprint
status: in-progress
learning_progress: 0
last_updated: 2026-07-09
priority: high
---

## 目标

7 天内把字节三个已投岗位（Coze 上下文工程 / Agent Infra 计算 / Agent 评测）的面试准备到可作战状态。本模块是时间驾驶舱：每天打开即知昨天学了什么、今天学什么；知识本体一律沉淀到对应能力模块，这里不存知识。

## 当前状态

2026-07-09 三岗全部投出（均带内推码）。冲刺从 D1 开始，任何一天约到面试则切换为 Mock 日，课表顺延。冲刺结束本模块归档（status: done），foundations 恢复原节奏。

## 核心知识

- 每日四段循环（90 分钟）：冷启动自测 15 → 主题学习 35 → 手撕/case 25 → 沉淀输出 15。全程由 AI 会话主持，契约见本地 interview_prep 文件夹 AGENTS.md。
- 学习材料在本地面试包（01-07），本站只收两样东西：每日冲刺卡（本模块时间线）+ 消化后的知识笔记（对应能力模块）。
- 七个补丁项优先级：计算机八股 > Node event loop > SFT/RLHF 概念 > 手撕实战协议 > 评测 case 演练 > 升学答案 > 面试反馈回路。

## 任务

每日仪式：

1. 打开本模块时间线：看昨天的冲刺卡（学了什么/答崩什么）和今天的任务行。
2. 开 AI 会话，说「今天 Day N」，AI 按本地 AGENTS.md 接管四段循环。
3. 会话结束：AI 产出今日冲刺卡 + 2-3 张知识笔记 → 更新本模块时间线和对应能力模块 → 构建推送。
4. 面试日：早上只看目标模块的「面试转译」栏；面后 30 分钟内问题清单进 Logs。

## 时间线

- D1（2026-07-10）：Cyrene 主线叙事 + 升学答案 → 更新 Behavioral/Strategy（Project deep dive）
- D2（2026-07-11）：Coze 上下文工程 + SFT/RLHF 概念层 → 更新 LLM Systems、RAG & Memory
- D3（2026-07-12）：Agent Infra + 计算机八股 + Node event loop → 更新 Coding（新增两张笔记）
- D4（2026-07-13）：Agent 评测 + bad case 演练 ×2 → 更新 Evals & Debugging
- D5（2026-07-14）：Mock 1：Coze 全真 60 分钟 → 答崩回填对应模块
- D6（2026-07-15）：Mock 2+3：Infra 40 分钟 + 评测 40 分钟 → 答崩回填
- D7（2026-07-16）：全题库抽查 + 反问定稿 + 全站「面试转译」过一遍 → Logs 写 weekly review

## 知识笔记

### 冲刺卡格式

核心理解：

- 每天一张卡追加到本模块时间线对应日期行后，格式：`学了{主题}；答崩：{清单}；已回填：{模块/笔记名}；明天：{主题}`。
- 冲刺卡是复盘线索不是知识本体；月底按 Logs 的惯例决定哪些沉淀回模块正文。

复习提示：

- 若某天崩盘，不要重排整个冲刺：当天只完成①自测和④沉淀两段，其余顺延一天。
```
