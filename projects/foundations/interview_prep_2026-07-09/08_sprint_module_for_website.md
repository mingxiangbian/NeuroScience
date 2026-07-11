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
last_updated: 2026-07-11
priority: high
---

## 目标

7 天内优先把 Agent Eval 准备到基础可面试状态，同时建立 Python 可迁移基础和 Coze / Context Engineering 的真实项目主线；Agent Infra 先补 vocabulary 与前置，不假装三岗能在同一周达到相同深度。本模块是横向时间驾驶舱：显示今天练什么、留下什么 artifact、下一次复测何时到期；知识本体一律沉淀到对应能力模块，这里不复制知识正文。

## 当前状态

D1 盲测基线已完成并保留原始 artifact。当前独立 readiness 为 Coding 0、System Design 0、Project Deep Dive 1，因此 coding 与 system/case hard gate 仍为 fail；后续 coached 重构不能覆盖该结论。D2 已完成 Python 容器、第一份 Cyrene Eval case audit 和 Context pipeline 三个 coached 学习块；这些结果建立了概念模型，但没有独立提高 hard gate。Cyrene benchmark 已从“只看过汇总”推进到在教练带领下审计 `T0-MODE-FAST`，原始同步 summarization hook 改造仍没有 before/after latency 或 cost 数据。

## 核心知识

- 时间合同：D2-D7 每天两个必修 90 分钟块；理解和精力允许时增加第三个 90 分钟块，休息另算。
- 优先级：Agent Eval 最短路径 → Python 每日底座 → Coze / Context 平行深化 → Agent Infra 前置。
- 盲测与教学隔离：interviewer 不预读答案，不提示；结束后由独立 evaluator 评分。
- 学习循环：`unlearned` 先解释概念和题意 → 具体数组/trace/case → 合资料重构 → 小型独立变式；已有基础才先 attempt。
- hard gate：coding 与 system/case 必须分别独立通过，不能被表达或知识题平均掉。
- 证据边界：Cyrene 的 `59/8/0` 是 full profile 汇总，不等于用户已审计全部 case；同步 hook 的 latency/cost 改进没有量化对照。
- 站内每天只收一张冲刺卡和一张最重要弱项知识卡；原始错答、hint 和评分留在本地 eval ledger。

## 任务

每日仪式：

1. 看时间线和上一张冲刺卡，确认两个必修块与到期复测。
2. 开 Coach 会话，说「今天 Day N」；陌生内容先教再练，blind、coach、evaluator 使用不同会话。
3. 每个 90 分钟块完成概念/题意、worked example、用户重构、小型变式和记录；coding 在本地或 judge 实际运行。
4. 前两个块理解稳定且精力允许时再开启第三块；不能压缩必修块换取数量。
5. 收尾更新本地 ledger、今日冲刺卡和最多一张能力模块知识卡；面试后另记录原题与原答。

## 时间线

- D1（2026-07-10）：已完成；三项 baseline + 精准补缺 + Cyrene 叙事/升学回答 + Two Sum/Valid Parentheses；hard gate 仍为 fail；D+2 复测 2026-07-12
- D2（2026-07-11）：已完成 coached 学习；Python 容器与 `deque` + `T0-MODE-FAST` Eval case anatomy + Cyrene Context pipeline；独立 hard gate 不变；D+2 复测 2026-07-13
- D3（2026-07-12）：未开始；180 core / +90 optional；hash + Context Engineering；可选 Agent Runtime vocabulary → Coding、RAG & Memory、Agent Design
- D4（2026-07-13）：未开始；180 core / +90 optional；sliding window + Agent behavior eval；可选 Context conflict → Coding、Evals & Debugging
- D5（2026-07-14）：未开始；180 core / +90 optional；已学 coding pattern 独立检查 + Cyrene case audit；可选 Agent Infra → Coding、Evals & Debugging
- D6（2026-07-15）：未开始；180 core / +90 optional；BFS + Agent Eval mini mock；可选 Coze overlay → Coding、Evals & Debugging、LLM Systems
- D7（2026-07-16）：未开始；180 core / +90 optional；parallel post-test + 下一阶段分流 → Logs weekly review

## 学习记录

### D1 冲刺卡

完成记录：

- 完成三份原始 baseline：Coding readiness 0、System Design readiness 0、Project Deep Dive readiness 1。
- coached 阶段重构 `max_running_robots`，固定用例和 randomized differential tests 通过；该结果证明补缺有效，但不改写 blind baseline。
- Agent Runtime 被识别为尚未系统学习，而不是一次应用失误；已回填 Agent Design 的四层架构与 reliable tool execution 知识卡。
- Cyrene 叙事已校正为 actual-use count + weekly AI maintenance；晋升、更新和撤销都以周为周期，敏感或高风险内容走人工审核例外路径。
- Cyrene benchmark 的用户 ownership 已进一步校正：最初关注回答结束后的 summarization hook latency，并参考 MemGPT；用户只查看过归档汇总，没有逐项审计 case，也没有保存架构改造前后的量化对照。
- Two Sum 与 Valid Parentheses 由用户确认运行通过；代码未保留在公开冲刺卡中。

后续检查：

- 2026-07-12 对 sliding-window 做学习检查点，并检查 Context/Agent Runtime 的前置概念关系；尚未教学的内容不做盲目 hard gate。只有学过后在未见变式中独立通过，才能提高 readiness。

### D2 冲刺卡

完成记录：

- Python 容器块完成 `list`、stack、queue、`deque` 的用途和复杂度学习；`list.pop(0)` 会移动后续元素，而 `deque.popleft()` 从左端常数时间移除。用户重写双队列 `service_order` 并确认测试通过；单调队列中右端 `pop()` 删除被新值支配的候选，左端 `popleft()` 只删除过期候选。
- Eval 块区分 system performance benchmark 与 Agent behavior eval，并用 input、expected、actual、assertion、metric、evidence 六部分审计 `T0-MODE-FAST`。当前 case 缺少 Active Memory 的正向断言；Evidence 的多个零值只由 Fast Summary 是否存在决定；`continuityGetP95FastMs` 实际只有一次计时；`fastTokenOverhead` 是字符数除以四的估算。
- Balanced Mode 近迁移发现 Policy 明确要求 `includeFastSummaries: false`，但现有 case 没有断言 Fast Summary 必须缺席，也没有断言 Active Memory 必须出现。测试名称、架构策略和可执行断言必须一致。
- Context 块区分每轮同步 summarization hook 与周期维护：前者 freshness 高但增加前台等待和调用成本；后者移除同步关键路径开销，但引入可用延迟。项目偏好每日演化，全局记忆按周或更长周期更新，因此 time-to-availability 必须按 scope 分开测。
- 项目叙事的证据边界保持不变：同步 Hook 的延迟和成本来自定性使用观察，没有保留改造前后的量化对照；后续应比较新增前台延迟、总 Token 成本、scope-specific availability、Memory Precision/Recall 和下游任务成功率。

后续检查：

- D2 三个块均为 coached readiness 1，不代表独立通过。2026-07-13 做概念与 guided artifact 检查；D5 独立审计未见 Cyrene case；2026-07-18 对仍低于 readiness 2 的内容做 D+7 迁移复测。

### 冲刺卡格式

完成记录：

- 每日格式：`D{N}：完成{artifact}；hard gate：{结果}；主要 failure：{tag}；已回填：{模块/笔记}；下一次复测：{日期}`。
- 冲刺卡记录训练轨迹，不承载知识正文；未完成项直接顺延，不缩短题目时间。

后续检查：

- D1 原始 baseline 必须保留。D7 使用平行题比较 readiness、用时、hint 和 failure tag，而不是比较润色后的答案。
```
