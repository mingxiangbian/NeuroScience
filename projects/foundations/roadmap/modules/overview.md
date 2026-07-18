---
id: overview
title: Interview Overview
status: not-started
learning_progress: 0
last_updated: 2026-07-18
priority: high
plan_scope: interview
navigation_group: interview
module_role: interview
goal_role: 临时面试突击
subsystems:
---

## 目标

为临时面试突击提供能力地图和入口。它回答“如果近期需要面试，应该检查哪些信号、进入哪个冲刺任务”，不定义个人长期学习方向。

长期北极星、六子系统、活动单元和结算状态只由 **Career Roadmap** 与 `ledger.md` 管理；这里的岗位、readiness、mock 和日期不会改写长期队列。

## 使用边界

- **Interview Overview**：临时能力地图、风险和材料入口。
- **Interview Sprint**：实际日期、训练块、blind baseline、复测和冲刺卡的唯一时间驾驶舱。
- **Behavioral / Strategy**：项目表达、tradeoff、failure story 与结构化沟通。
- **长期能力模块**：保存可复用的技术知识和真实产物，不承载面试倒计时。
- **Career Roadmap**：唯一长期北极星；面试结束后仍按原活动单元继续。

面试训练若产生真实实现、实验或失败分析，可以在满足长期结算判据后被明确晋升；完成一道题、一次 mock 或一份润色答案本身不自动结算长期单元。

## 面试能力地图

- **Engineering Foundations**：coding correctness、Python fluency、edge cases 与验证。
- **LLM Systems**：attention、KV cache、context、structured outputs、post-training 与 inference constraints。
- **Agent Runtime**：tool registry、state、sandbox、approval、trace 与 recovery。
- **Lifelong Memory**：retrieval、write policy、conflict、deletion、privacy 与 user control。
- **Evals & Diagnostics**：task success、regression、grader、trace debugging 与 evidence boundary。
- **Research Reading**：从 claim 和 evidence 推到 system implication。
- **Behavioral / Strategy**：把真实项目、取舍、失败和改变判断讲清楚。

这些是面试观察维度，不是长期路线的优先级排序。

## Signal Rubric

- **Coding signal**：能独立完成目标难度的题，解释 invariant、complexity 和 edge cases。
- **Systems signal**：能把 LLM / Agent system 拆成 state、tools、memory、eval、trace 与 failure recovery。
- **Research signal**：能区分 claim、evidence、limitation 和 system implication，不停留在论文名。
- **Project signal**：能讲清 problem、constraint、tradeoff、failure mode 和 verification，且不夸大证据。
- **Communication signal**：回答包含假设、取舍、验证动作和结论边界。

readiness 只由未见任务中的独立表现提高；coached 重构、熟题复述和材料润色不能覆盖 blind baseline。

## 任务

1. 打开 Interview Sprint，确认当前 Day、必修块和到期复测。
2. 使用 blind、coach、evaluator 分离的会话完成训练。
3. 把原始回答、hint、评分和 failure tag 留在面试 eval ledger。
4. 技术知识只回填对应长期模块，冲刺页面不复制知识正文。
5. 面试窗口结束后关闭临时组，回到 Career Roadmap 的原活动单元。

## 时间线

- 冲刺期间：进行中；具体日期、Day 计划与 readiness 变化只在 Interview Sprint 维护。
- 计划边界：进行中；本页不再维护第二份 30 / 45 / 60 天计划。
- 新面试窗口：未开始；先重新做 baseline，再决定临时突击范围。
- 面试窗口结束：未开始；只晋升满足长期结算判据的真实产物。
