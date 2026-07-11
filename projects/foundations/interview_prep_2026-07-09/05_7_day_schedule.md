# 05 七天冲刺完整计划（v4，2026-07-10）

前提：字节三岗已投（Coze 上下文工程 / Agent Infra 计算 / Agent 评测-AI 数据与安全），面试可能在 3-14 天内到来。

## 冲刺目标与优先级

D1 暴露的真实基线是：能读写基础 Python，但标准库、数据结构和算法模式尚未系统训练；Agent Runtime 与 Agent Eval 的正式概念接近从零开始；Cyrene 有真实问题定义和架构取舍，但 benchmark 只看过汇总，也没有保存同步 hook 改造前后的 latency/cost 对照数据。

因此 D2-D7 不再假设七天内把三个岗位全部练到同一深度，而按当前最短准备距离排序：

1. **Agent Eval**：先达到较低门槛岗位的基础可面试状态；从 case、指标和 bad-case report 开始，不把 Cyrene 汇总数字当成已有能力。
2. **Python**：每天一个完整基础块，先补容器、标准库和常见模式，再做独立题。
3. **Coze / Context Engineering**：平行建立正式知识，并把 Cyrene 的真实取舍转成可验证叙事。
4. **Agent Infra**：本周先建立 runtime vocabulary 与可靠工具执行前置；未收到该岗邀约时，不提前做完整 system design gate。

这里的排序表示“从当前水平到可面试的距离”，不是对岗位绝对难度或录取概率的断言。

## 时间合同

- D1 的 210 分钟作为已完成历史记录保留。
- D2-D7 每天有 **两个必修 90 分钟块，共 180 分钟**；不同块切换主题，避免整天只做一个项目。
- 当天理解和精力允许时增加 **第三个 90 分钟块**，总计 270 分钟；第三块不是完成当日计划的必要条件。
- 休息另算，两个块之间建议离开屏幕 20-30 分钟。不能通过压缩讲解、worked example 或独立重构来塞入更多任务。
- 未完成的完整块顺延；不把半个块或跟着答案完成记为掌握。

### 90 分钟学习块

对 `unlearned` 内容使用：

1. 概念与题意 15 分钟。
2. 具体数组、trace 或真实 case 的 worked example 25 分钟。
3. 用户合上资料复述机制并重新实现/分析 25 分钟。
4. 一个小型独立变式 20 分钟。
5. 记录理解、误区和下一次复测 5 分钟。

对已有基础但应用失败的内容，才使用 `attempt → targeted review → reconstruct → transfer`。未知术语不能先靠连续追问猜答案。

## 全局规则

1. **约面优先于课表**：收到邀约后，未来 24 小时切换到该岗位 overlay；共同底座仍保留 coding 和项目叙事，其他日程顺延。
2. **盲测和教学隔离**：盲测前不能看 02、03、06 的答案或让同一 AI 先辅导后出同题。先留原始回答，再在独立会话评分。
3. **Coding 分层协议**：新数据结构先讲 API、复杂度并手动 trace，再 guided implementation，最后才做独立题；已经学过的模式可直接限时。代码必须在本地或 judge 运行，AI 不能代替执行结果。
4. **理解后输出**：`unlearned` 内容先建立模型；已有基础才输出优先。无论哪条路径，最终都要合上资料重构和做小型变式。
5. **间隔复测**：失败项写入本地私有 `09_eval_ledger.local.md`（格式见 [09_eval_ledger.md](09_eval_ledger.md)），在 D+2 和 D+7 用变式复测；冲刺结束后仍要完成到期的 D+7。
6. **网站只沉淀强内容**：每天只要求一张冲刺卡 + 一张最重要弱项知识卡，不追求数量。
7. **真实面试回路**：面后 30 分钟内记录问题和原回答，标注答好/答虚/答崩；答崩项进入 D+2/D+7 队列。

---

## Day 1 - 盲测基线 + Cyrene 主线（210 分钟）

- [x] **盲测基线 90 min**：不看答案材料完成一题未见过的 medium coding（45）+ production Agent system design（30）+ 录音讲 Cyrene（15）。保留代码、设计稿和录音/转写。
- [x] **基线补缺 35 min**：根据独立评分分流；重构 sliding-window 解法并做 differential tests，同时为尚未系统学习的 Agent Runtime 建立四层知识地图。补缺不覆盖原始 baseline。
- [x] **叙事与升学 20 min**：练 Cyrene 60 秒/2 分钟版、两个失败案例、三个取舍；按真实情况完成升学答案。
- [x] **手撕 50 min**：Two Sum、Valid Parentheses，各 25 分钟并实际运行。
- [x] **沉淀 15 min**：独立评分后写 09 ledger；网站更新 D1 冲刺卡 + 一张最弱项知识卡。
- **完成判据**：三份 baseline artifact 都存在；coding 和 system design 分别有独立评分；两道手撕可运行通过。不能用后续润色答案覆盖原始 baseline。

## Day 2 - Eval 入门 + Python 容器基础（180-270 分钟）

- [x] **必修块 A｜Python 90 min**：从 `list`、stack、queue、`deque` 的用途、核心 API 和复杂度开始；带具体数组手动运行，再独立重写一个小型 queue/deque 函数。`max_running_robots` 只作为已见案例回顾，不直接当新题盲测。
- [x] **必修块 B｜Eval 90 min**：区分 system performance benchmark 与 Agent behavior eval；学习一个 case 的 input、expected、actual、assertion、metric、evidence 六部分；在教练带领下审计 Cyrene `T0-MODE-FAST`。
- [x] **可选块 C｜Context 90 min**：画出“每轮同步 summarization hook”与“周期性 maintenance”两条 pipeline；明确 `freshness vs latency/cost`，并设计应测的 added latency、token/cost 和 memory quality，不虚构旧数据。
- **完成判据**：能解释 `popleft()`、queue 与 stack 的差别；完成第一份 coached case audit；能准确说出 Cyrene 的观察、决策和证据边界。D2 不做 blind hard gate。

## Day 3 - Hash 基础 + Context Engineering 入门（180-270 分钟）

- [ ] **必修块 A｜Python 90 min**：先用 15-20 分钟做 D1 的 D+2 学习检查点：闭卷解释 monotonic deque 中存什么并手动 trace，不要求直接通过新 medium；随后学习 `dict`、`set`、hash lookup 和常用 API，用 Contains Duplicate 或 Valid Anagram 完成一题独立小题。
- [ ] **必修块 B｜Context 90 min**：建立 prompt、context、state、memory 的边界；用 Cyrene 讲清 candidate、maintenance、store、retrieval 与 context assembly，区分 retrieval hit、context injection 和模型实际使用。
- [ ] **可选块 C｜Agent Runtime 90 min**：只建立 vocabulary 和流程图：request、state、tool call、trace、operation、retry、reconcile；使用一个 worked example，不进行完整 system design 盲测。
- **完成判据**：一题 hash 基础题独立运行通过；能从用户请求沿 pipeline 讲到 context injection；Agent Runtime 即使完成也只记 coached readiness。

## Day 4 - Sliding Window + Agent 行为评测（180-270 分钟）

- [ ] **必修块 A｜Python 90 min**：在 `dict/set` 前置基础上学习 sliding window；带字符串逐步运行 Longest Substring Without Repeating Characters，再合上资料重写并做一个小变式。
- [ ] **必修块 B｜Eval 90 min**：学习 task success、tool selection、argument correctness、execution outcome、recovery；教练先完整拆一条 Agent trace，再由用户写 bad-case 五段报告：expected、actual、failure layer、evidence、regression check。
- [ ] **可选块 C｜Context 90 min**：学习 context selection、compression、scope、stale memory、conflict 和 human review；把每个概念映射回 Cyrene，但不把映射当作已经实现或验证。
- **完成判据**：能手动解释窗口移动与数据结构状态；完成一份 coached bad-case report；D2 的 Eval 内容完成一次闭卷概念检查。

## Day 5 - 第一次独立检查 + Eval Case Audit（180-270 分钟）

- [ ] **必修块 A｜Python 90 min**：从 D2-D4 已学模式中抽一题同级未见变式，先独立完成并运行；剩余时间只修复真实 failure，不开启新难题。独立通过只说明该模式达到 readiness level 2，不代表任意 medium 已掌握。
- [ ] **必修块 B｜Eval 90 min**：独立审计第二个 Cyrene case（优先 `T0-PENDING-BOUNDARY` 或 `T0-CROSS-PROJECT-PROMPT-INJECTION`），写清 fixture、预期、断言、指标和局限；随后设计一个最小 behavior case，并由 evaluator 单独评分。
- [ ] **可选块 C｜Agent Infra 90 min**：学习 operation state machine、timeout、retry、idempotency、unknown outcome 和 reconciler；先讲概念和具体状态流，不要求完成 Tool Router 项目。
- **完成判据**：至少一个已学 coding pattern 独立通过；第二份 case audit 不依赖逐句提示；只在 Eval case readiness level ≥2 时把 Eval case gate 标为 pass。

## Day 6 - BFS 基础 + Agent Eval Mini Mock（180-270 分钟）

- [ ] **必修块 A｜Python 90 min**：学习 BFS、queue 与 visited 的关系；用具体树逐层运行 Binary Tree Level Order Traversal，再独立完成一个小型 BFS 变式。尚未掌握 recursion/graph 时不直接跳 Number of Islands。
- [ ] **必修块 B｜Eval 90 min**：做一次无提示 mini mock：分析未见 Agent trace、输出 bad-case report、提出 regression metrics，并用 10 分钟回答自动评测与人工校准；结束后另开 evaluator 会话评分。
- [ ] **可选块 C｜Coze 90 min**：做 context case rehearsal；只补与岗位直接相关的 attention/KV cache 长上下文代价和 `SFT/RLHF/DPO` 边界，不在一天内扩成完整 post-training 课程。
- **完成判据**：BFS worked example 可闭卷重构；Eval mini mock 有独立 artifact 和评分；Coze 可选块未完成时顺延，不挤压两个必修块。

## Day 7 - 平行复测 + 下一阶段分流（180-270 分钟）

- [ ] **必修块 A｜Coding 90 min**：从本周已学模式抽一题未见变式；先独立澄清、实现、运行和补边界测试，再由 evaluator 评分。与 D1 比较用时、hint、failure tag 和解释质量，不比较题目名义难度。
- [ ] **必修块 B｜Role 90 min**：完成一条未见 Agent Eval case（45）+ Cyrene Context deep dive（30）+ D1/D7 证据对比（15）；分别评分，不能用项目表达掩盖 case 错误。
- [ ] **可选块 C｜分流 90 min**：根据真实邀约和本周最低 readiness，三选一：Behavioral 证据索引、Coze 知识补齐、Agent Infra 前置；不默认同时做三个。
- **完成判据**：目标是 Agent Eval case 达到 readiness level ≥2、至少一个已学 coding pattern 达到 level 2、Coze 形成一条诚实且可验证的项目叙事。Agent Infra 未独立通过就明确留到下一阶段，不把七天结束写成三岗全部 ready。

---

## 面试日流程（任何一天触发）

1. 前一晚：对应岗位做 45-60 分钟盲测 Mock，之后才评分。
2. 当天早上：15 分钟只看目标模块的面试转译和证据表，不再扩展新知识。
3. 面试中：先澄清、再作答；项目数字只引用可定位 artifact；不知道就明确边界并给验证路径。
4. 面后 30 分钟内：原题与原答进入 09 ledger 和 Logs，答崩项安排 D+2/D+7。

## 并行求职小回路（不占上述净训练时长）

- 每两天最多 15 分钟：核对投递状态、JD-CV 对齐和作品链接。
- 面试前做一次 fresh-clone preflight：README 路径、安装/测试命令、公开 benchmark 链接都能由陌生人复现。
- 未收到具体邀约前轮换三个岗位 overlay；收到邀约后只提高目标岗权重，不删除共同底座。
