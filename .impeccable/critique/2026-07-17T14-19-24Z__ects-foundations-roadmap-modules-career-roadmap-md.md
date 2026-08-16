---
target: Career Roadmap 审视与改进
total_score: 27
p0_count: 0
p1_count: 3
timestamp: 2026-07-17T14-19-24Z
slug: ects-foundations-roadmap-modules-career-roadmap-md
---
Method: dual-agent (A: /root/roadmap_assessment_a2 · B: /root/roadmap_assessment_b)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | 有活动单元、台账和更新时间，但当前状态在多处重复 |
| 2 | Match System / Real World | 3 | “贾维斯六子系统”易理解，尚未落成真实岗位入口 |
| 3 | User Control and Freedom | 3 | 可空窗、可合法离场，但缺少改线与专长重选机制 |
| 4 | Consistency and Standards | 2 | 状态、任务、时间线及战略/战术文档存在重复口径 |
| 5 | Error Prevention | 3 | mask、eval 与卡住协议体现出强验证意识 |
| 6 | Recognition Rather Than Recall | 2 | repo、文件、产物和硬期限仍需用户自行回忆 |
| 7 | Flexibility and Efficiency | 3 | 单线程、断点和玩耍券适合长期反复使用 |
| 8 | Aesthetic and Minimalist Design | 2 | 视觉壳成熟，但正文多次复述同一战略 |
| 9 | Error Recovery | 3 | 三次报错与墙记录协议具体，但无市场或专长判断失效后的恢复门 |
| 10 | Help and Documentation | 3 | 方法解释清楚，单元验收与证据模板仍不完整 |
| **Total** | | **27/40** | **Acceptable：方向正确，但战略决策层仍需补强** |

## Anti-Patterns Verdict

**LLM assessment**：不像通用 AI 模板。北极星目标、个人经历、mask 失败、结算制和断点协议都高度具体。风险不在视觉“AI 味”，而在口号和隐喻重复：房间、军火库、玩耍券很有个人性，但当它们取代岗位、能力和证据字段时，会降低外部可验证性。

**Deterministic scan**：对 `projects/foundations/index.html` 的扫描返回 0 条 findings。这个结果只覆盖静态 reader shell；Career Roadmap 正文由 JS 从 Markdown 动态渲染，因此不能把 0 命中解释为内容或渲染后 DOM 已完全无问题。

**Visual overlays**：线上页面成功加载，标题、当前模块、0% 状态和正文可见，控制台无 warning/error。浏览器只提供只读求值，无法完成可信的脚本注入，因此没有可见的 `[Human]` overlay。

## Overall Impression

这是一个有鲜明个人目标、并认真处理“长期计划为什么会中断”的优秀雏形。最大的机会不是继续扩充知识清单，而是把“我要进入造贾维斯的房间”翻译成：先从哪类岗位进入、每类岗位需要什么证据、什么时候在②③④之间做选择、什么结果会让路线转向。

## What's Working

1. 北极星目标被拆成六个子系统，愿景与技能投资之间有可解释桥梁。
2. “活动单元—冻结队列—断点续传—卡住协议”是真正针对长期中断设计的运行机制。
3. U1–U3 把验证能力置于组装能力之前，并要求真实对比、eval 和失败分析，方向正确。

## Priority Issues

### [P1] 有候选专长，没有专长选择门

**Why it matters**：②③④都被标记为候选专长，但当前阶段只安排人格方向的 U4–U6，记忆和实时语音被推到远期。先做哪个会被误当成哪个最适合，产生路径依赖。

**Fix**：在 2027.08 前给三条候选方向各一个 2–4 session 的同尺度试验；统一按兴趣持续性、已有优势、导师/数据/算力可得性、反馈周期、岗位需求、可形成作品证据六项评分。在 U6 后设置一次选择门，选主专长、辅专长和明确放弃项。

**Suggested command**：`$impeccable shape`

### [P1] 缺少“入场岗位 → 能力 → 证据”的映射

**Why it matters**：路线描述了最终房间，却没有定义第一份可进入的岗位。Post-training Research Engineer、Personalization/Memory、Speech/Realtime、Agent Evals/ML Systems 的门槛不同；没有映射，就无法判断 CS 系统、训练、研究和产品能力各需多深。

**Fix**：新增四列岗位矩阵：岗位原型、核心能力、当前证据、下一个缺口。把“CSAPP/C++ 被墙触发才学”改为“仍按项目触发，但每个专业项目必须带一个系统指标”，例如 profiling、显存/延迟、数据管线、测试、可复现或分布式概念。无需另开基础课。

**Suggested command**：`$impeccable shape`

### [P1] “专业级作品”的验收标准仍偏浅

**Why it matters**：现有“四个有”——评估、数据、失败分析、文档——很好，但不足以证明人格、记忆或 Agent 研究能力。当前岗位更看重从模糊行为问题到假设、数据、grader、训练、分析和产品决策的完整实验闭环。

**Fix**：为专业级作品增加统一 Evidence Rubric：研究问题/用户问题、baseline、指标与方差、ablation/对照、可复现运行、失败分类、延迟/成本、外部 review、README/demo。普通单元不必全做；阶段性 capstone 必须满足。

**Suggested command**：`$impeccable clarify`

### [P2] 伴侣型 AI 缺少跨子系统的人本约束

**Why it matters**：长期记忆、人格和主动性并不只靠 SFT/DPO 跑通。用户同意、可删除性、记忆冲突、情感依赖、奖励投机、长期用户价值和安全边界，都会决定系统是否值得信任。

**Fix**：不要新增第七个“安全模块”；把 Trust / Safety / Privacy / Human Control 作为②③④⑤的横切验收项。人格试验至少加入偏好异质性与过度迎合，记忆试验加入删除/过期/冲突，主动 Agent 加入授权与失败恢复。

**Suggested command**：`$impeccable harden`

### [P2] Roadmap 页面缺少唯一的重返入口

**Why it matters**：活动单元同时出现在“当前状态”和“任务”，四阶段又在“核心知识”和“时间线”重复。`learning_progress: 0`、已结算数和 checkbox 是三套状态语义；久别返回仍要交叉阅读。

**Fix**：页首固定一张“现在”摘要，只放当前单元、下一步第一动作、完成定义、阻塞、产物链接、最近复核日期。正文保留“为什么”，移除状态复述。把 repo/文件/命令、ledger、战略层、战术层和外部日历都改成可定位链接；外部日历除雅思外，还要列申请、奖学金、实验室联系和实习窗口。

**Suggested command**：`$impeccable distill`

## Persona Red Flags

**Alex（长期返回的工作区主人）**：不能在 60 秒内从首屏直接打开目标 repo、看到验收缺口和最近产物；必须在状态、任务、ledger 与战略文档之间建立记忆桥。

**Jordan（导师或第一次查看的协作者）**：无法快速区分“已验证能力、用户假设、助手综合判断、待验证问题”；“军火库、玩耍券、进房间”等内部隐喻也没有岗位语言对照。

**Casey（被频繁打断的移动用户）**：虽然 localStorage 能保存 checkbox，但长期状态的真相在 Markdown/ledger，跨设备和清缓存后可能不一致；外部硬期限也没有统一入口。

## Minor Observations

- “基座模型不用造”应改成“不竞争预训练规模，但保持训练与优化的实验熟练度”，避免把 post-training 所需底层能力误判成可跳过。
- “Agent 执行已有基础”最好标为 prototype-level，并附 Cyrene 的可验证证据，而不是二元的“有/没有”。
- “正在爆发”“学界正热”应附来源日期和复核周期；事实、用户假设、综合判断、待验证问题需分栏。
- 结算数字只涨不跌可以保留，但应另设会变化的“当前置信度/证据新鲜度”，防止旧成果永久代表当前能力。

## Questions to Consider

- 如果明年只能用一个作品敲开实验室或实习的门，它应该证明人格、记忆、语音，还是证明你能把三者稳定地集成和评估？
- 哪个结果会让你放弃当前候选专长？如果没有答案，选择门还不是真正的选择门。
- Cyrene 是长期北极星项目，还是求职证据载体？两者可以重合，但验收标准不同。
