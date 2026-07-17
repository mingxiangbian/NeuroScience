# 基石

## Purpose

`基石` 是面向 AI / Agent 面试的长期准备区。当前第一条路线聚焦 **Agent / LLM Systems Engineer**，目标难度对齐 OpenAI、Anthropic、Google DeepMind、xAI 这类顶尖 AI Lab / AGI 团队。

这不是通用课程，也不是大型 demo 项目目录。它的目标是把准备过程压到面试有用的能力上：

- coding 能稳定过关。
- Python / TypeScript 实现能落到真实 Agent / LLM 组件。
- system design 能讲清 tradeoff、failure mode 和 eval。
- LLM / Agent 概念能从“知道”推进到“能设计、能调试、能辩护”。
- 面试表达能被识别为强工程候选人信号。

## Current Track

当前 track 的用户假设：

- 目标岗位：Agent / LLM Systems Engineer。
- 时间形态：核心 30 天，可延展到 45/60 天。
- 准备方式：每天时间不固定，因此使用 `minimum` / `standard` / `stretch` 三层任务。
- 主要短板：coding 和实现能力优先，其次是面试表达；LLM/Agent 系统知识已有基础但需要深入。
- 技术栈：Python + TypeScript 为主，Rust 作为 optional systems-depth add-on。
- 项目策略：不做大型项目，优先做小型 implementation drills 和 system design casebook。

## How To Use This Folder

1. 先读 `ai-professional-roadmap.md` 确认方向（战略层），再读 `llm-agent-engineer-roadmap.md`，从 Week 1 的 `minimum` 任务开始。
2. 每周用 roadmap 里的 review checklist 复盘一次。
3. 需要重新生成计划时，使用 `multi-agent-planner.md`，更新输入字段后重新跑 6-agent 流程。
4. 后续如果要做大型展示项目，再从 roadmap 的 mini drills 中挑一个扩展。

## Files

- `ai-professional-roadmap.md`：战略层——从现在到"贾维斯"的职业路线图（六子系统 × 四阶段 + 结算制运行系统），对应 reader 里的 Career Roadmap 模块。
- `ledger.md`：结算台账——活动单元、断点续传、结算记录、撞墙记录。数字只涨不跌，空窗不记债。
- `multi-agent-planner.md`：可复用的 6-agent planner 模板。
- `llm-agent-engineer-roadmap.md`：战术层——面试准备路线。
- `README.md`：当前入口说明。

## First Day

第一天只做三件事：

1. Coding：做 2 道 easy / medium 的 array 或 hash map 题，用 Python 写清楚边界条件。
2. System design：用 20 分钟写一个 `Design a tool-calling agent runtime` 的草图，只写 requirements、components、failure modes。
3. Expression：录音或写稿回答 `Tell me about a technical project where you handled ambiguity`，限制 2 分钟。

完成后不要补很多阅读。先建立节奏。

## Source Alignment

当前路线按 2026-07-05 可见的公开岗位信号校准：

- OpenAI Codex / Agents 相关岗位强调 coding agents、tool-using LLM systems、evals、inference behavior、runtime constraints、logs/traces、Python/Rust/API layers。
- OpenAI applied AI / evals / agent infrastructure 岗位强调 shipping LLM products、Python、FastAPI/gRPC、backend systems、multi-agent workflows、tool use、long context 和 production evals。
- Anthropic alignment 相关岗位强调 empirical AI research、safety-relevant evals、multi-agent experiments 和 LLM-generated jailbreak eval tooling。
- Google DeepMind Research Engineer role family 强调 software engineering、ML/deep learning、research implementation、scaling systems 和 evaluation of ideas。

这些信号决定本路线的优先级：coding + implementation drills + system design + eval，比泛泛读论文更重要。
