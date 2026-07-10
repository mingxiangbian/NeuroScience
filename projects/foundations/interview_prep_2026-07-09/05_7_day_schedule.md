# 05 七天冲刺完整计划（v3，2026-07-10）

前提：字节三岗已投（Coze 上下文工程 / Agent Infra 计算 / Agent 评测-AI 数据与安全），面试可能在 3-14 天内到来。

## 时间合同

- **标准日 180 分钟**：D2、D4、D5、D7。
- **重日 210 分钟**：D1、D3、D6。
- 以上都是净训练时间，休息另算。建议每 50-60 分钟休息 10 分钟。
- 不再把两道 25 分钟代码题塞进一个 25 分钟时段。当天被打断就记录实际完成处并顺延，不把未完成项算完成。

## 全局规则

1. **约面优先于课表**：收到邀约后，未来 24 小时切换到该岗位 overlay；共同底座仍保留 coding 和项目叙事，其他日程顺延。
2. **盲测和教学隔离**：盲测前不能看 02、03、06 的答案或让同一 AI 先辅导后出同题。先留原始回答，再在独立会话评分。
3. **手撕实战协议**：Python；每题 25 分钟；纯文本编辑器、无补全；口述思路 → 写码 → 在本地或 judge 实际运行 → 补 3 个边界测试 → 讲复杂度。AI 只能补反例，不能代替执行结果。
4. **输出优先学习**：先尝试 → 只查缺口 → 合上资料重构 → 换一个题面迁移。阅读本身不计作掌握。
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

## Day 2 - Coze 上下文工程 + Post-training（180 分钟）

- [ ] **提取练习 20 min**：不看资料复述 D1 最弱三项；只记录，不立即纠正。
- [ ] **机制链 50 min**：self-attention、KV cache、长上下文代价；正确区分两条 post-training 路径：`SFT → preference data → RM → PPO-style RLHF` 与 `SFT → preference pairs + fixed reference policy → DPO`。
- [ ] **Coze overlay 35 min**：context engineering、长对话一致性、压缩、memory conflict；扫读 LangGraph persistence 的 checkpointer/store/interrupt。
- [ ] **手撕 50 min**：Longest Substring Without Repeating Characters、Valid Palindrome。
- [ ] **沉淀 25 min**：合上资料画机制链并口述；更新 09 ledger、D2 冲刺卡和一张知识卡。
- **完成判据**：能在 90 秒内分别讲清 PPO-style RLHF 与 DPO，不暗示 DPO 需要独立 RM；两题独立通过。

## Day 3 - Agent Infra + 系统设计 + 计算机基础（210 分钟）

- [ ] **D+2 分流 20 min**：Coding 用未见变式复测；标记为 `unlearned` 的 Agent Runtime 只检查前置知识地图，不做盲目 system design gate。
- [ ] **结构化学习 + component 60 min**：先用 30 分钟建立 Production Agent Architecture 四层、operation state machine 和 reliable tool execution，再用 30 分钟完成第一份 guided system design / Python Tool Router artifact。
- [ ] **基础与 Node 50 min**：进程/线程/协程、死锁、TCP/UDP、HTTP/HTTPS、URL 到渲染、哈希冲突；event loop、microtask/macrotask、async/await。
- [ ] **手撕 50 min**：Group Anagrams、Min Stack。
- [ ] **实现验收与沉淀 30 min**：补齐 Tool Router 的 timeout/error/idempotency 测试并实际运行；随后更新 ledger、D3 卡和一张系统设计知识卡。
- **完成判据**：Agent Runtime 有知识地图和第一份 guided artifact，明确标注尚未掌握的部分；Tool Router 测试实际通过；coding artifact readiness level ≥2。System/case hard gate 保持 fail，直到后续未见场景独立达到 readiness level 2；随机四个基础题能在 60 秒内给出正确机制和边界。

## Day 4 - Agent 评测 + Bad Case（180 分钟）

- [ ] **D+2 复测 20 min**：复测 D2 到期弱项。
- [ ] **评测框架 40 min**：Agent eval vs LLM eval、工具调用四层评估、bad case 五段结构、自动评测与人工校准。
- [ ] **Case ×2 40 min**：每个 20 分钟，用未见过的 trace 独立定位失败层、给证据、修复和回归指标。
- [ ] **手撕 50 min**：Number of Islands、Binary Tree Level Order Traversal。
- [ ] **沉淀 30 min**：复盘 failure tags；更新 ledger、D4 卡和一张 Evals & Debugging 知识卡。
- **完成判据**：两份 report 都能定位到具体 trace 证据；至少一份 case readiness level ≥2；两题实际运行通过。

## Day 5 - Mock 1：Coze 全真（180 分钟）

- [ ] **D+2 复测 15 min**：用变式复测 D3 最弱项；只记录原答，不边答边纠正。
- [ ] **盲测 Mock 60 min**：用 07 Prompt D；interviewer 只看 CV、JD 和 sealed questions，必须产出一份 Coze system/case artifact，不加载 02/03/06 的答案内容。
- [ ] **手撕 50 min**：Binary Search、Search Insert Position；若 Mock 已完整包含其中一道，则换同模式未见题。
- [ ] **独立评分与重构 35 min**：新会话用 Prompt E 评估 transcript；对最低两项执行“查缺口 → 合资料 → 重答变式”。
- [ ] **沉淀 20 min**：更新 ledger、D5 卡和一张最弱项知识卡。
- **完成判据**：独立 coding artifact 和 Mock 内 system/case artifact 都达到 readiness level ≥2，因此两个 hard gate 均 pass；知识/项目题至少 80% readiness level ≥2。

## Day 6 - Mock 2+3：Infra + Eval（210 分钟）

- [ ] **D+2 复测 20 min**：复测 D4 到期弱项。
- [ ] **Infra 盲测 Mock 45 min**：必须含 system design；component implementation 可作为追问，但不能替代 system design artifact。
- [ ] **Eval 盲测 Mock 45 min**：必须含未见过的 trace case 和安全/数据质量追问。
- [ ] **手撕 50 min**：Top K Frequent Elements、Climbing Stairs。
- [ ] **独立评分与重构 25 min**：两个 Mock 分开评分，不能互相平均；最低项做一次变式重答。
- [ ] **行为面与沉淀 25 min**：完成五个真实故事的证据索引；更新 ledger、D6 卡和一张知识卡。
- **完成判据**：共同 coding artifact readiness level ≥2；Infra system design 与 Eval case artifact 分别 ≥2，因此两个岗位的 hard gate 都 pass。五个故事覆盖 ownership、ambiguity、failure/debugging、conflict/collaboration、changed mind after evidence，且不能全部用 Cyrene。

## Day 7 - 平行盲测 + 收官整备（180 分钟）

- [ ] **平行盲测 90 min**：换题但保持 D1 难度和结构：medium coding（45）+ Agent system design（30）+ Cyrene deep dive（15）。
- [ ] **D+2 + 随机快问 25 min**：先复测 D5 到期最弱项，再从 06 抽未见变式；只记录 readiness level 和 failure tag。
- [ ] **第二道 coding 25 min**：House Robber 或本周失败模式的未见变式。
- [ ] **行为面与反问 25 min**：五个故事各过一遍 opening/result/reflection；每岗三问定稿。
- [ ] **评分与归档 15 min**：独立比较 D1/D7；写 weekly review、D7 卡和 D+7 待办，不用“平均分”掩盖 hard gate。
- **完成判据**：相对 D1 至少两个 assessment axis 提升；coding 与 system/case artifact 当前都达到 readiness level ≥2，因此两个 hard gate 均 pass；所有未通过项都有下一次 D+2/D+7 日期。

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
