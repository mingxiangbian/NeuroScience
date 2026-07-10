# 06 Mock Question Bank 与评分规约

题号用于本地私有 `09_eval_ledger.local.md`，格式见 [09_eval_ledger.md](09_eval_ledger.md)。正式盲测应由 interviewer 从题库主题生成**未见变式**，不要直接复用已练原题。

## 项目深挖（P）

- P1：用 2 分钟介绍 Cyrene。
- P2：为什么把 memory 分成 project 和 global？
- P3：actual-use count + AI 判断如何驱动周度 memory 晋升、更新和撤销？如何确认模型确实使用了某条 memory，而不只是检索或注入了它？
- P4：linked records 解决了什么问题？
- P5：怎样定义 stale-memory leakage？
- P6：benchmark 怎样设计？它与生产/学术 benchmark 有什么差距？
- P7：如果用户反悔，memory 怎样回滚或失效？
- P8：hook error 为什么不能阻塞 Codex 工作？
- P9：项目里最难的工程问题是什么，证据在哪里？
- P10：若接入团队 Agent 平台，先改哪三块？

## Coze 上下文工程（C）

- C1：context engineering 和 prompt engineering 有什么区别？
- C2：长对话里哪些信息应该进入 memory？
- C3：上下文过长时如何筛选、压缩和保留 provenance？
- C4：怎样评估模型是否正确使用了关键信息？
- C5：retrieved memory 与当前用户指令冲突时如何处理？
- C6：你没做过 SFT/RL，如何匹配岗位？
- C7：KV cache 能解决什么，不能解决什么？
- C8：长上下文、RAG、summary memory 分别适合什么场景？

## Agent Infra（I）

- I1：Agent framework 需要哪些核心模块？
- I2：MCP 的 host、client、server 分别做什么？
- I3：tool schema 设计不好会造成什么问题？
- I4：Agent memory 和 database cache 有什么区别？
- I5：企业级 Agent 为什么需要 identity、permission、audit log？
- I6：怎样设计 retrieval trace？
- I7：怎样处理 tool timeout、retry、cancel 和 partial execution？
- I8：幂等重试与普通重试有什么区别？

## Agent Eval（E）

- E1：Agent eval 和普通 LLM eval 有什么区别？
- E2：怎样评估 tool-call accuracy？
- E3：检索相关性怎样打分？
- E4：任务规划合理性怎样评估？
- E5：bad case report 应该包含哪些字段？
- E6：自动化 eval 和人工评测怎样结合？
- E7：LLM-as-a-judge 的偏差怎样校准？
- E8：如何把一个线上 bad case 变成稳定 regression case？

## 基础知识（F）

- F1：讲 self-attention，并说明 Q/K/V 的形状。
- F2：为什么 attention score 要除以 $\sqrt{d_k}$？
- F3：decoder-only Transformer 的训练与推理路径有什么不同？
- F4：KV cache 为什么省计算却增加显存压力？
- F5：RAG 的 chunking、retrieval、rerank、context assembly 各做什么？
- F6：ReAct 和 Function Calling 的区别是什么？
- F7：embedding retrieval 可能失败在哪里？
- F8：分别讲 `SFT → preference data → explicit RM → PPO-style RLHF` 与 `SFT → preference pairs + fixed reference policy → DPO`。
- F9：Node.js event loop 中 microtask 和 macrotask 的顺序是什么？
- F10：任选一个：进程/线程/协程、TCP/UDP、死锁、哈希冲突、URL 到渲染。

## System Design 与安全（S）

- S1：设计 multi-tenant Agent memory/runtime，明确用户、规模、SLO、API 和 data model。
- S2：如何隔离 project/global/team scope，防止跨租户污染？
- S3：高风险工具怎样在 automatic / confirm / human approval / block-or-escalate 之间分级？
- S4：怎样处理 prompt injection、memory poisoning、provenance 和敏感信息 redaction？
- S5：工具执行到一半失败时，如何 preview、cancel、undo、resume 或补偿？
- S6：哪些 trace、metric 和 eval 能证明系统可靠？
- S7：在 latency、cost、quality、privacy 之间怎样取舍？

## Component Implementation（X）

- X1：实现 Python Tool Router：registry、schema validation、timeout、trace 和测试。
- X2：为副作用工具增加 idempotency key、bounded retry、cancel 和 approval gate。
- X3：实现 TypeScript async executor，正确处理 Promise rejection、AbortSignal 和 partial result。
- X4：给一段错误 tool trace，修复 bug 并补最小 regression test。

## 行为面（B）

- B1：为什么投这个岗位？
- B2：为什么从电子信息工程转到 Agent / LLM？
- B3：讲一次 ownership：没有人替你定义完成标准时你怎样推进？
- B4：讲一次 ambiguity：需求模糊时怎样澄清和拆解？
- B5：讲一次 failure/debugging：最初判断哪里错了，怎样定位？
- B6：讲一次 conflict/collaboration：你与队友或 reviewer 意见不同时怎样处理？
- B7：讲一次 changed mind after evidence：什么证据改变了你的方案？
- B8：之后读研还是工作，能实习多久？

故事证据不要全部来自 Cyrene。优先从 Cyrene、NeRF、机器人车/团队课程项目中各取不同类型证据；没有真实冲突就不要编冲突。

## Readiness level（0-3）

- **0 - fail**：事实错误、代码不运行、未完成核心要求，或遗漏安全/权限等致命约束。
- **1 - coached**：在实质提示后完成，或答案只覆盖一部分；只要用了实质提示，本题最高 1。
- **2 - independent**：无提示独立正确完成，能解释核心机制并处理基本边界。
- **3 - transferable**：在 2 的基础上，能迁移到新场景，给出证据、tradeoff、failure mode 和验证方案。

硬规则：正确性不是可被表达能力平均掉的维度。事实/代码/关键架构错误时 readiness level 必须为 0。

## 分类诊断维度（每项 0-2）

### 知识题 / 项目题

correctness、mechanism、evidence、tradeoff/boundary、communication。

### Coding / implementation

correctness、independence/hints、implementation quality、tests/debugging、complexity/communication。

### System design / case

requirement clarification、architecture/decomposition、failure/recovery/security、eval/metrics、tradeoffs。

维度分只用于诊断，不取平均替代 readiness level。

## Hard gate 与通过标准

- Coding hard gate：对应 coding artifact 在限时内实际运行通过且 readiness level ≥2，则 gate=`pass`，否则 `fail`。
- System/case hard gate：对应 artifact 未提示完成核心链路，覆盖 failure recovery、安全和 eval，且 readiness level ≥2，则 gate=`pass`，否则 `fail`。
- 一次日级/Mock 评估包必须同时包含两个 artifact。coding artifact 可以来自紧邻 Mock 的独立限时 coding 段；system/case artifact 必须来自该岗位 Mock，不能用 component implementation 替代。
- 项目/知识题：一次 Mock 中至少 80% readiness level ≥2。
- 任一 hard gate 未通过，该岗位 Mock 就是未通过；不能靠其他题高分平均。

常用 failure tag：`knowledge-gap`、`wrong-mechanism`、`no-evidence`、`missed-requirement`、`coding-bug`、`hint-dependent`、`weak-test`、`security-omission`、`unclear-communication`。
