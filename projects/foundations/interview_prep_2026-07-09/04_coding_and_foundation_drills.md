# 04 代码题和基础知识

## 代码题清单

每天 2 题，先写出可运行代码，再复述思路和复杂度。

| 主题 | 题目 |
| --- | --- |
| Array / Hash | Two Sum, Valid Anagram, Group Anagrams |
| Two Pointers | Valid Palindrome, Container With Most Water |
| Sliding Window | Longest Substring Without Repeating Characters |
| Stack | Valid Parentheses, Min Stack |
| Binary Search | Binary Search, Search Insert Position |
| BFS / DFS | Number of Islands, Binary Tree Level Order Traversal |
| Heap | Top K Frequent Elements |
| Dynamic Programming | Climbing Stairs, House Robber |

## 面试说题模板

1. 复述输入输出和边界条件。
2. 给出朴素解。
3. 给出优化思路。
4. 写代码。
5. 讲复杂度。
6. 用一个例子手动跑。

## LLM / Agent 基础

### Transformer

要能讲清：

- token embedding、position encoding。
- self-attention 的 Q/K/V。
- attention score 为什么要除以 $\sqrt{d_k}$。
- decoder-only LLM 为什么适合 next-token prediction。

### RAG

要能讲清：

- chunking：按语义、标题、token 长度切。
- embedding retrieval：召回候选文档。
- rerank：提高相关性。
- context assembly：控制顺序、去重、截断。
- eval：看 recall、faithfulness、answer relevance。

### ReAct / Tool Use

要能讲清：

- ReAct 把 reasoning 和 action 交替执行。
- tool schema 要约束参数。
- tool result 要进入下一步 context。
- 常见失败：选错工具、参数错、无效重试、忽略 tool result。

### Function Calling

要能讲清：

- function schema 描述函数名、参数、类型和约束。
- 模型输出结构化调用请求，程序执行函数。
- 需要处理参数校验、权限、超时、错误恢复。

### Memory

要能讲清：

- short-term memory：当前 session state。
- long-term memory：跨 session 保存的事实和偏好。
- episodic memory：过去事件。
- semantic memory：稳定知识。
- working memory：当前推理需要的信息。

Cyrene 最适合讲 short-term 和 long-term 的边界，以及 memory promotion policy。

## Eino / LangGraph / MCP 快速准备

### Eino

官方文档把 Eino 定义为 Golang-based AI application development framework。你不用装成熟练开发者，但要知道它服务于 LLM app 和 Agent app 的工程化开发。准备重点：

- Go 生态。
- components / orchestration / agent app。
- 为什么字节 JD 会提它：后端和 infra 团队更偏 Go/服务化。

### LangGraph

LangGraph 重点是 stateful agent、persistence、human-in-the-loop。准备重点：

- graph state。
- checkpointer 处理 thread-scoped short-term memory。
- store 处理 long-term memory。
- interrupt + approve/edit/reject 支持 human review。

### MCP

MCP 是连接 AI application 和外部系统的 open standard。准备重点：

- host / client / server。
- tools 暴露可调用动作。
- resources 暴露上下文数据。
- prompts 暴露可复用 prompt/workflow。
- 安全边界：tool permission、data scope、prompt injection。

## 不需要现在深学的东西

- PPO 公式细节。
- 大规模 distributed training。
- CUDA kernel。
- 完整 SFT/RLHF pipeline 实操。

如果面试官问到训练，你要承认没做过公司级训练，再把话题接到 eval、data quality、context behaviour。
