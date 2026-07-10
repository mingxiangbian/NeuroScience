# 字节 Agent 实习面试冲刺包

创建：2026-07-09
修订：2026-07-10
目标岗位：Coze 上下文工程 / Agent Infra 计算 / Agent 评测-AI 数据与安全。

## 三件套定位

| 角色 | 载体 | 职责 |
| --- | --- | --- |
| 教案与记录 | 本文件夹 01-09 | 学习材料、评分规约和原始 eval ledger 的源头真相 |
| 教练/面试官/评估者 | AI 会话，契约见 [AGENTS.md](AGENTS.md) | 教学、盲测和评分；三个角色在盲测中隔离 |
| 长期知识库 | Foundations 网站 | 只存每日冲刺卡和已经重构稳定的一张强知识卡 |

## 时间合同

- D2、D4、D5、D7：标准日 180 分钟。
- D1、D3、D6：重日 210 分钟。
- 都是净训练时间，休息另算。当天中断就顺延，不压缩单题或 Mock 来伪造完成。

## 每日仪式

1. 打开 Interview Sprint 模块，看今日主题和昨日冲刺卡。
2. 读 [05](05_7_day_schedule.md) 的当日时间块；让 AI 按 [AGENTS.md](AGENTS.md) 主持。
3. 先输出再学习：attempt → targeted review → reconstruct → transfer。
4. 将原答、用时、hint、readiness level、failure tag 和 D+2/D+7 写入 gitignored 的 `09_eval_ledger.local.md`；格式见 [09](09_eval_ledger.md)。
5. 收尾只发布一张冲刺卡 + 一张最重要弱项知识卡；勾掉真正完成的项。

D1 必须先做 blind baseline。约到面试后，使用 07 Prompt D 开 interviewer 会话，再使用 Prompt E 开独立 evaluator 会话；不得让 interviewer 预读答案材料。

## 文件地图

| 文件 | 内容 | 什么时候读 |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | AI 会话契约 | 每次 AI 会话开始 |
| [01_interview_map.md](01_interview_map.md) | 三岗差异、共同底座与岗位 overlay | D1 前通读 |
| [02_cyrene_talk_track.md](02_cyrene_talk_track.md) | Cyrene 叙事 + 可核对证据账本 | D1 baseline 后 |
| [03_role_specific_qna.md](03_role_specific_qna.md) | 岗位问答 + canonical system design + behavior evidence bank | D2-D6 |
| [04_coding_and_foundation_drills.md](04_coding_and_foundation_drills.md) | coding、LLM 基础、component implementation | 每天 |
| [05_7_day_schedule.md](05_7_day_schedule.md) | 七天时间预算与完成判据 | 每天 |
| [06_mock_question_bank.md](06_mock_question_bank.md) | 题库、readiness level、分类 rubric 与 hard gate | 自测/Mock 评分时 |
| [07_ai_study_protocol.md](07_ai_study_protocol.md) | 学习法、盲测隔离和可粘贴 Prompt | D1 前通读 |
| [08_sprint_module_for_website.md](08_sprint_module_for_website.md) | 网站驾驶舱模块的备份源与安装说明 | 模块重装时 |
| [09_eval_ledger.md](09_eval_ledger.md) | 可公开的空白 ledger 模板；实际记录写入同目录 `.local.md` | 每次练习前后 |

## 面试主线

把自己讲成一个**做过可运行、可评估 Agent 系统的本科生**。核心证据是 Cyrene Continuity：

- `memory/context`：candidate-review-store-retrieval、project/global scope、linked records。
- `tooling`：TypeScript、Node.js、MCP、CLI、hooks、local UI。
- `reliability/eval`：release gate、adversarial fixtures、repo-grounded replay、traceable artifacts。
- `boundary`：个人项目和 deterministic fixtures，不是生产流量或学术 benchmark。

行为题不能只讲 Cyrene。NeRF、机器人车/团队课程项目应分别承担 collaboration、debugging 或 changed-mind 证据，但只使用真实发生过的事件。

## 诚实红线

- 不说 Cyrene 有生产用户或线上流量。
- 不说做过 SFT/RL 训练；只讲概念层和评估/工程侧可迁移经验。
- 可引用 archived report 的数字，但必须同时说日期、profile、passed/skipped 和 fixture 边界。
- 不把单个 fixture 的 `retrievalAccuracy=1` 表述成整体 100% 准确率。
- benchmark 是 release gate/regression suite，不是大规模行业 benchmark。
- 升学与实习时长照实回答。

真实面试题、原始 transcript 和个人评分属于私有训练数据，只能写入 `09_eval_ledger.local.md` 或仓库外 artifact；不要回填到公开网站或 tracked Markdown。

## 官方资料入口

- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Eino docs: https://www.cloudwego.io/docs/eino/
- MCP introduction: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP tools spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OpenAI evals guide: https://developers.openai.com/api/docs/guides/evals
- Cyrene benchmark report: https://github.com/mingxiangbian/cyrene-continuity/blob/main/benchmark/reports/2026-06-06/summary.md

## 并行求职小回路

每两天最多额外花 15 分钟核对投递、JD-CV 和公开作品链接。面试前做一次 fresh-clone preflight；该检查不占 180/210 分钟训练预算。
