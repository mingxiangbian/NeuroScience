# 08 网站冲刺模块 - 备份源与安装步骤

设计原则：Interview Sprint 是与 Logs 同类的横向时间驾驶舱，不是新的知识板块。知识本体进入既有能力模块；本模块只保存日程、artifact、hard gate 和复测线索。

当前仓库已经安装该模块。只有丢失或迁移时才执行以下步骤：

1. 把下方代码块保存为 `projects/foundations/roadmap/modules/interview-sprint.md`。
2. 在 `projects/foundations/scripts/build-roadmap-data.mjs` 的 `MODULES` 数组登记 `interview-sprint`。
3. 运行 `node projects/foundations/scripts/build-roadmap-data.mjs`。
4. 运行 `node tests/foundations-roadmap-requirements.mjs`。

## 模块源文件

```md
---
id: interview-sprint
title: Interview Sprint
status: in-progress
learning_progress: 0
last_updated: 2026-07-10
priority: high
---

## 目标

7 天内把字节三个已投岗位（Coze 上下文工程 / Agent Infra 计算 / Agent 评测）准备到可独立作答和验证的状态。本模块是横向时间驾驶舱：显示今天练什么、留下什么 artifact、下一次复测何时到期；知识本体一律沉淀到对应能力模块，这里不复制知识正文。

## 当前状态

D1 盲测基线已完成并保留原始 artifact。当前独立 readiness 为 Coding 0、System Design 0、Project Deep Dive 1，因此 coding 与 system/case hard gate 仍为 fail；后续 coached 重构不能覆盖该结论。Two Sum 与 Valid Parentheses 已由用户确认运行通过。D2 转入 Coze 上下文工程与 post-training，D1 三项弱点在 2026-07-12 做 D+2 变式复测。

## 核心知识

- 时间合同：标准日 180 分钟（D2/D4/D5/D7），重日 210 分钟（D1/D3/D6），休息另算。
- 盲测与教学隔离：interviewer 不预读答案，不提示；结束后由独立 evaluator 评分。
- 学习循环：先尝试 → 精准补缺 → 合资料重构 → 换场景迁移 → D+2/D+7 复测。
- hard gate：coding 与 system/case 必须分别独立通过，不能被表达或知识题平均掉。
- 站内每天只收一张冲刺卡和一张最重要弱项知识卡；原始错答、hint 和评分留在本地 eval ledger。

## 任务

每日仪式：

1. 看时间线和上一张冲刺卡，确认今日预算与到期复测。
2. 开 AI 会话，说「今天 Day N」；blind、coach、evaluator 使用不同会话。
3. coding 在本地或 judge 实际运行；system design 留下白板/文字 artifact。
4. 收尾更新本地 ledger、今日冲刺卡和最多一张能力模块知识卡。
5. 面试后 30 分钟内记录原题、原答、failure tag 与 D+2/D+7。

## 时间线

- D1（2026-07-10）：已完成；三项 baseline + 精准补缺 + Cyrene 叙事/升学回答 + Two Sum/Valid Parentheses；hard gate 仍为 fail；D+2 复测 2026-07-12
- D2（2026-07-11）：未开始；180 min；Coze 上下文工程 + Transformer/post-training + 两道 coding → 更新 LLM Systems、RAG & Memory
- D3（2026-07-12）：未开始；210 min；Agent Infra + canonical system design + Tool Router + 计算机基础/Node event loop → 更新 Agent Design、Coding
- D4（2026-07-13）：未开始；180 min；Agent 评测 + unseen bad case ×2 + 两道 coding → 更新 Evals & Debugging
- D5（2026-07-14）：未开始；180 min；Mock 1：Coze 盲测 + 独立评分 + 两道 coding → 最弱项回填
- D6（2026-07-15）：未开始；210 min；Infra/Eval 双盲测 + 行为证据库 + 两道 coding → 最弱项回填
- D7（2026-07-16）：未开始；180 min；平行盲测 + hard-gate 对比 + 反问/复测归档 → Logs weekly review

## 知识笔记

### D1 冲刺卡

核心理解：

- 完成三份原始 baseline：Coding readiness 0、System Design readiness 0、Project Deep Dive readiness 1。
- coached 阶段重构 `max_running_robots`，固定用例和 randomized differential tests 通过；该结果证明补缺有效，但不改写 blind baseline。
- Agent Runtime 被识别为尚未系统学习，而不是一次应用失误；已回填 Agent Design 的四层架构与 reliable tool execution 知识卡。
- Cyrene 叙事已校正为 actual-use count + weekly AI maintenance；晋升、更新和撤销都以周为周期，敏感或高风险内容走人工审核例外路径。
- Two Sum 与 Valid Parentheses 由用户确认运行通过；代码未保留在公开冲刺卡中。

复习提示：

- 2026-07-12 分别复测 sliding-window 变式、Agent Runtime 前置知识和 Cyrene 冲突/撤销场景。只有未提示独立通过，才能提高 readiness。

### 冲刺卡格式

核心理解：

- 每日格式：`D{N}：完成{artifact}；hard gate：{结果}；主要 failure：{tag}；已回填：{模块/笔记}；下一次复测：{日期}`。
- 冲刺卡记录训练轨迹，不承载知识正文；未完成项直接顺延，不缩短题目时间。

复习提示：

- D1 原始 baseline 必须保留。D7 使用平行题比较 readiness、用时、hint 和 failure tag，而不是比较润色后的答案。
```
