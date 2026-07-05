---
id: logs
title: Logs
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: medium
---

## 目标

保存跨模块复盘、当周实际发生的事、未归类想法和下一轮调整。Logs 不替代能力模块，只提供横向视角。

## 当前状态

第一版 logs 从 Weekly Review Checklist 初始化，后续按日期追加。它解决“这周/这个月总体做了什么”的问题，而不是重新变成主导航。

## 核心知识

复盘应服务面试准备，而不是写情绪流水账。每条 log 尽量关联：

- coding pattern
- system design case
- Agent/LLM component
- failure mode
- mock answer
- interview artifact

## 任务

### Weekly Review Checklist

Every week, answer:

1. Which coding pattern still causes mistakes?
2. Which system design case can I explain without notes?
3. Which Agent/LLM component did I implement?
4. What failure mode did I learn to detect?
5. Which answer sounded vague during mock practice?
6. What is one artifact I can mention in an interview?
7. What should I cut next week because it is not interview-relevant?

If a week goes badly, do not restart the whole plan. Repeat the current week with only `minimum` and `standard` tasks.

## 时间线

- 2026-07-05：建立 Foundations roadmap reader 结构。决定主导航按能力模块，而不是按周；时间叙事放入模块内部时间线和 Logs。
- Week 1 review：记录 coding baseline、tool router、tool-calling agent answer。
- Week 2 review：记录 graph/RAG/retrieval evaluator 和 failure taxonomy。
- Week 3 review：记录 heap/DP/memory store 和 ambiguity story。
- Week 4 review：记录 mock sprint、system design answers、behavioral stories 和 portfolio summary。

## 知识笔记

### Weekly Review

核心理解：

- Weekly Review Checklist 用来回答：哪类 coding pattern 还错、哪个 system design case 不看笔记能讲、实现了哪个 Agent/LLM component、学会了哪个 failure mode、哪个 mock answer sounded vague。
- Logs 不是主导航，只提供跨模块复盘视角。

复习提示：

- If a week goes badly, do not restart the whole plan. Repeat the current week with only `minimum` and `standard` tasks.

### Review template

核心理解：

- 复盘模板：

```md
### YYYY-MM-DD

- Coding pattern:
- System design case:
- Component implemented:
- Failure mode learned:
- Vague answer:
- Interview artifact:
- Cut next:
```

### Cross-module synthesis

核心理解：

- 如果全局计划执行得不好，不要重启整个 plan。更好的动作是找出一个最弱模块，回到该模块的 `minimum` 和 `standard`，减少阅读和额外扩展。
- 每月检查一次哪些 logs 应该沉淀回模块正文。

面试转译：

- “我一开始计划按周推进，后来发现长期维护会膨胀，所以把主导航改成能力模块，并在模块内保留时间线。”
