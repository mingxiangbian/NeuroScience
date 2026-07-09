# 字节 Agent 实习面试冲刺包

创建：2026-07-09（三岗已投当天）
目标岗位：Coze 上下文工程 / Agent Infra 计算 / Agent 评测-AI数据与安全（均为字节，已带内推码投出）

## 三件套定位

| 角色 | 载体 | 职责 |
| --- | --- | --- |
| 教案 | 本文件夹 01-08 | 学习材料的源头真相 |
| 教练 | AI 会话（契约见 [AGENTS.md](AGENTS.md)） | 出题、追问、判题、模拟面试、起草笔记 |
| 错题本 | 基石网站 foundations（interview-sprint 模块 + 能力模块） | 只存两样：每日冲刺卡 + 消化后的知识笔记 |

## 每日仪式（核心用法）

1. **打开网站 Interview Sprint 模块**：时间线上看昨天的冲刺卡（学了什么/答崩什么）和今天的任务行。
2. **开 AI 会话**：说「今天 Day N」。AI 读 AGENTS.md 后接管四段循环（自测 15 → 学习 35 → 手撕 25 → 沉淀 15，共 90 分钟）。
3. **会话收尾**：AI 产出今日冲刺卡 + 2-3 张知识笔记 → 更新网站 → 勾掉 [05](05_7_day_schedule.md) 里完成的项。
4. **约到面试**：当天放弃课表，用 [07](07_ai_study_protocol.md) Prompt D 做对应岗位全真 Mock；面试当天早上手机只看网站「面试转译」栏；面后 30 分钟内问题清单进 Logs。

首次使用先完成一次性安装：按 [08](08_sprint_module_for_website.md) 把 interview-sprint 模块装进网站。

## 文件地图

| 文件 | 内容 | 什么时候读 |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | AI 会话契约（怎么主持学习、笔记格式、怎么更新网站、诚实红线） | 每次 AI 会话开始 |
| [01_interview_map.md](01_interview_map.md) | 三岗面试差异、第一轮结构、自我介绍三版 | Day 1 前通读 |
| [02_cyrene_talk_track.md](02_cyrene_talk_track.md) | Cyrene 主项目叙事（三场通用） | Day 1 |
| [03_role_specific_qna.md](03_role_specific_qna.md) | 岗位专项问答（A=Coze / B=Infra / C=Eval）+ 各岗反问 | Day 2-4 |
| [04_coding_and_foundation_drills.md](04_coding_and_foundation_drills.md) | 手撕题单、说题模板、LLM 基础、Eino/LangGraph/MCP | 每天③段 |
| [05_7_day_schedule.md](05_7_day_schedule.md) | 七天完整课表（含差距补丁；勾选状态=进度源） | 每天 |
| [06_mock_question_bank.md](06_mock_question_bank.md) | 题库 + 3 分制评分标准 | 每天①段、Day 5-7 |
| [07_ai_study_protocol.md](07_ai_study_protocol.md) | 7 个差距补丁、四段循环定义、四个可粘贴 Prompt | Day 1 前通读 |
| [08_sprint_module_for_website.md](08_sprint_module_for_website.md) | 网站冲刺模块源文件 + 安装步骤 | 一次性安装时 |

## 面试主线

把自己讲成一个**做过可运行、可评估 Agent 系统的本科生**，而不是泛泛学过 LLM 的候选人。核心证据是 Cyrene Continuity：

- `memory`：project/global stores、linked records、pending queue、review hashes
- `context`：retrieval for follow-up sessions、stale-memory leakage checks
- `tooling`：TypeScript、Node.js、MCP、CLI、hooks、Vitest、GitHub Actions
- `eval`：retrieval accuracy、stale-memory leakage、runtime drift、release checks

## 不能编的内容（红线，AI 与本人共同遵守）

- 不说 Cyrene 有生产用户或线上流量
- 不说做过 SFT/RL 训练（只讲概念层 + 评估侧衔接）
- 不编 retrieval accuracy 的具体百分比
- benchmark 是 release gate / regression check，不是大规模 benchmark
- 升学问题照实答：申请 2027 fall 硕士；可连续实习 6 个月、每周 5 天

## 官方资料入口

- LangGraph memory/persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Eino docs: https://www.cloudwego.io/docs/eino/
- MCP introduction: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP tools spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OpenAI evals guide: https://developers.openai.com/api/docs/guides/evals
