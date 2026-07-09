# 05 七天冲刺完整计划（v2，2026-07-09）

前提：字节三岗已投（Coze 上下文工程 / Agent Infra 计算 / Agent 评测-AI数据与安全），面试可能 3-14 天内到来。
本计划已并入 07 号文件的 7 个差距补丁。每天 90 分钟，四段循环（见 [07_ai_study_protocol.md](07_ai_study_protocol.md) 第二节）。
AI 会话怎么配合本计划执行，见 [AGENTS.md](AGENTS.md)。

## 全局规则

1. **约面优先于课表**：任何一天收到面试邀约，当天立即切换成对应岗位的 Mock 日（用 07 的 Prompt D），课表顺延。
2. **手撕实战协议**（每天③段执行）：Python；每题计时 25 分钟；纯文本编辑器写（无补全，模拟飞书代码板）；流程＝口述思路 → 写码 → 自己出 3 个测试用例走查 → 讲时间/空间复杂度。
3. **真实面试回路**：面完 30 分钟内把记得的所有问题写进网站 Logs → AI 归类（答好/答虚/答崩）→ 答崩的当天重写成笔记回填模块。
4. 完成一项勾一项。AI 会话开始时靠这些勾判断进度。

---

## Day 1 — Cyrene 主线叙事 + 升学答案

- [ ] ① 自测：06 题库「项目深挖」1-5 题，不看资料口答，AI 按 3 分制打分
- [ ] ② 学习：02 全文；口述文字架构图（candidate → review → store → retrieval → context）；准备 2 个失败案例（stale memory、跨项目污染）+ 3 个取舍（为何 local-first / 为何 project-global 分层 / 为何 pending queue 不自动写入）
- [ ] ② 升学答案初稿（补丁6）：「申请 2027 fall 硕士，方向与 Agent 一致；可连续实习 6 个月、每周 5 天、到毕业前可持续」——照实改写成自己的话
- [ ] ③ 手撕：Two Sum、Valid Parentheses
- [ ] ④ 网站：Behavioral/Strategy 模块 Project deep dive 笔记更新（Cyrene 60 秒版 + 2 分钟版，写成第一人称口语）；冲刺卡 D1
- **完成判据**：不看稿讲完 2 分钟版，被 AI 连续追问 3 层不卡壳；两题 AC

## Day 2 — Coze 上下文工程 + SFT/RLHF 概念层

- [ ] ① 自测：昨日弱项 3 题 + 06「Coze 上下文工程」区 2 题
- [ ] ② 学习：03A 全部（context engineering 定义、长对话一致性三步、上下文压缩策略、"没做过 SFT/RL"话术）
- [ ] ② 补丁3：SFT/RLHF 概念层——能白板讲流程 pretrain → SFT → 偏好数据 → RM → PPO/DPO；一句话说清 DPO 与 PPO 区别；落点永远接回"评估侧我能做什么"
- [ ] ② 扫读 LangGraph persistence 官方文档（README 有链接），记 checkpointer/store/interrupt 三个词的作用
- [ ] ③ 手撕：Longest Substring Without Repeating Characters、Valid Palindrome
- [ ] ④ 网站：LLM Systems 模块扩充 Post-training 相关笔记（加 RLHF 流程卡）；RAG & Memory 模块加「长对话一致性」笔记；冲刺卡 D2
- **完成判据**：RLHF 流程 90 秒讲完；「无训练经验」回答说得自然不心虚

## Day 3 — Agent Infra + 计算机八股 + Node 运行时（最重的一天）

- [ ] ① 自测：昨日弱项 + 06「Agent Infra」区 2 题
- [ ] ② 学习：03B（Agent Infra 定义、MCP 三件套、hooks 为什么不阻塞、企业级 memory 五模块）
- [ ] ② 补丁1 八股（每个练成 60 秒口述）：进程 vs 线程 vs 协程；TCP vs UDP；三次握手/四次挥手；HTTP vs HTTPS；从输入 URL 到页面渲染全过程；哈希表实现与冲突处理；死锁四条件
- [ ] ② 补丁2 Node 运行时：event loop（宏任务/微任务执行顺序，能画图）；async/await 与 Promise 关系；单线程为何高并发
- [ ] ③ 手撕：Group Anagrams、Min Stack
- [ ] ④ 网站：Coding 模块新增两张笔记「OS/网络面试八股」「Node.js event loop」；冲刺卡 D3
- **完成判据**：8 个八股问题随机抽 4 个，各 60 秒答完；event loop 给段代码能说对输出顺序

## Day 4 — Agent 评测 + Bad Case 现场演练

- [ ] ① 自测：昨日弱项 + 06「Agent Eval」区 2 题
- [ ] ② 学习：03C（Agent 评测 vs LLM 评测、工具调用四层评估、bad case 报告五段结构、自动化评测落地）
- [ ] ③ Case 演练 ×2（补丁5，各 20 分钟，代替一道手撕）：让 AI 现编 trace，按五段结构现场写报告。参考题面：「Agent 订 7 月 15 日机票订成 7 月 5 日，trace 含 3 次 tool call」「Agent 把旧项目的部署配置带进了新项目回答」
- [ ] ③ 手撕：Number of Islands
- [ ] ④ 网站：Evals & Debugging 模块的 Eval Harness / Trace Debugging 笔记融入 Cyrene 证据（retrieval regression、leakage checks 怎么对应岗位的评测维度）；冲刺卡 D4
- **完成判据**：20 分钟内独立产出结构完整、失败层定位准确的 bad case report

## Day 5 — Mock 1：Coze 全真 60 分钟

- [ ] ① 快速过 06「基础知识」区 6 题
- [ ] ② Mock：07 Prompt D，指定 Coze 岗，60 分钟全程不出戏（含 1 道手撕）
- [ ] ③ 补手撕（若 mock 未含）：Binary Search、Search Insert Position
- [ ] ④ 网站：答崩清单逐条重写成笔记回填对应模块；冲刺卡 D5
- **完成判据**：mock 评分 ≥2 分的题占 80% 以上

## Day 6 — Mock 2+3：Infra 40 分钟 + 评测 40 分钟

- [ ] ② Mock ×2：Prompt D 分别指定 Infra、评测岗（Infra 场必含八股抽查，评测场必含 case）
- [ ] ② 升学答案终稿：两场 mock 里都被问到并流畅回答
- [ ] ③ 手撕：Top K Frequent Elements、Climbing Stairs
- [ ] ④ 网站：答崩回填；冲刺卡 D6
- **完成判据**：两场合计答崩 ≤3 题

## Day 7 — 收官整备

- [ ] ① AI 从 06 全题库随机抽 15 题快问快答
- [ ] ② 每岗 3 个反问定稿（03 各区末尾有底稿）并背熟
- [ ] ③ 手撕：House Robber + 复盘前 13 题中做错的
- [ ] ④ 网站：Logs 写本周 weekly review；Overview「待补知识」把已完成补丁划掉；手机打开全站过一遍所有「面试转译」栏
- **完成判据**：抽查 ≥2 分占 90%；三岗自我介绍变体 + 反问全部脱稿

---

## 面试日流程（任何一天触发）

1. 前一晚：对应岗位 mock 一场（40 分钟精简版）
2. 当天早上：手机打开网站，只看目标模块的「面试转译」栏，15 分钟
3. 面试中：说题模板、Cyrene 证据优先、不知道就说不知道 + 给排查思路
4. 面后 30 分钟内：问题清单进 Logs → AI 归类 → 答崩当天补
