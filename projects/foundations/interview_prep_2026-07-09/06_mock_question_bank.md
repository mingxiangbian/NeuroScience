# 06 Mock Question Bank

## 项目深挖

1. 用 2 分钟介绍 Cyrene。
2. 你为什么把 memory 分成 project 和 global？
3. candidate memory 为什么不能直接写入长期 memory？
4. linked records 解决了什么问题？
5. 你怎么定义 stale-memory leakage？
6. 你的 benchmark 怎么设计？它和大规模 eval 有什么差距？
7. 如果用户反悔，memory 怎么回滚或失效？
8. hook error 为什么不能阻塞 Codex 工作？
9. 你在项目里最难的工程问题是什么？
10. 如果让你把 Cyrene 接到团队的 Agent 平台，你会先改哪三块？

## Coze 上下文工程

1. context engineering 和 prompt engineering 有什么区别？
2. 长对话里哪些信息该进 memory？
3. 你怎么处理上下文过长？
4. 你怎么评估模型是否记住了关键信息？
5. 如果 retrieved memory 和当前用户指令冲突，你怎么处理？
6. 你没做过 SFT/RL，怎么补这个短板？

## Agent Infra

1. Agent framework 需要哪些核心模块？
2. MCP 的 host、client、server 分别做什么？
3. tool schema 设计不好会造成什么问题？
4. Agent memory 和普通 database cache 有什么区别？
5. 企业级 Agent 为什么需要 identity、permission、audit log？
6. 你怎么设计 retrieval trace？

## Agent Eval

1. Agent eval 和普通 LLM eval 有什么区别？
2. 你怎么评估 tool-call accuracy？
3. 检索相关性怎么打分？
4. 任务规划合理性怎么评估？
5. bad case report 应该包含哪些字段？
6. 自动化 eval 和人工评测怎么结合？

## 基础知识

1. 讲一下 self-attention。
2. 为什么 attention score 要除以 $\sqrt{d_k}$？
3. RAG 的 chunking、retrieval、rerank、context assembly 分别做什么？
4. ReAct 和 Function Calling 的区别是什么？
5. embedding retrieval 可能失败在哪些地方？
6. 多 Agent 协作的常见失败模式有哪些？

## 行为面

1. 为什么投这个岗位？
2. 为什么你从电子信息工程转到 Agent / LLM？
3. 你怎么证明自己能胜任实习？
4. 你最想在实习里补哪块能力？
5. 如果 mentor 给你一个模糊任务，你怎么拆？
6. 如果评测结果和产品直觉冲突，你怎么处理？

## 回答评分标准

每题按 3 分打：

- 1 分：能答概念。
- 2 分：能接到 Cyrene 或你的项目证据。
- 3 分：能说出取舍、边界和下一步改进。

低于 2 分的问题，回到对应文档重写答案。不要背大段话，背结构。
