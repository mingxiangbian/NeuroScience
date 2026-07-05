---
id: coding
title: Coding
status: not-started
learning_progress: 0
last_updated: 2026-07-05
priority: high
---

## 目标

把 coding 能力转成可测量的面试信号。重点不是刷题数量本身，而是限时写对、边写边解释、主动验证 edge cases，并能把实现能力连接到 Agent / LLM components。

## 当前状态

当前短板优先级最高的是 coding 和实现能力。Python 是主面试语言；TypeScript 用于 service/API/interface style drills；Rust 只作为 45/60 天后 optional systems-depth。

## 核心知识

### Coding Fundamentals

必须掌握到能限时写对：

- Arrays and strings：two pointers、sliding window、prefix sum。
- Hash maps and sets：frequency counting、dedup、index mapping。
- Stack and queue：monotonic stack、BFS queue。
- Trees：DFS recursion、iterative traversal、lowest common ancestor。
- Graphs：BFS/DFS、topological sort、shortest path basics。
- Heap：top-k、merge k lists、priority scheduling。
- Intervals：merge、sweep line basics。
- Greedy：排序后局部决策、反例检查。
- DP basics：1D/2D state、transition、base case。

面试表达要求：

- 先说 brute force。
- 再说 bottleneck。
- 再给 optimized approach。
- 写代码时主动说明 invariants。
- 结束时给 complexity 和 edge cases。

### Python / TypeScript Implementation

Python：

- clean function signatures
- dataclass / TypedDict
- heapq / deque / defaultdict
- async basics
- file and JSON handling
- testable small modules

TypeScript：

- typed interfaces
- async API wrappers
- discriminated unions for tool calls
- error result types
- simple Node service structure

TypeScript 不作为算法主语言，主要用于 Agent interfaces：

- `ToolCall`
- `ToolResult`
- `AgentTrace`
- `MemoryRecord`
- `EvalCase`

用它训练 API boundary 和 schema thinking。

## 任务

### Coding Plan

### Weekly Pattern Allocation

- Week 1：arrays, strings, hash maps, sliding window。目标是写稳基础题，减少语法和边界错误。
- Week 2：trees, graphs, BFS, DFS。目标是建立 recursion / traversal / visited set 直觉。
- Week 3：heap, intervals, greedy, DP basics。目标是覆盖中频题型。
- Week 4：mixed mock。目标是提升限时表现和解释质量。

### Daily Coding Loop

1. 3 分钟澄清输入输出和 edge cases。
2. 5 分钟写 brute force 和瓶颈。
3. 20-35 分钟写 optimized solution。
4. 5 分钟手动跑测试。
5. 5 分钟写复盘：pattern、bug、复杂度。

### Python Standards

每题必须做到：

- 函数签名清楚。
- 不依赖全局变量。
- 变量名能表达含义。
- 主动处理 empty input、single item、duplicates。
- 复杂度能说出来。

### TypeScript Standards

- 用 typed interfaces 表达 API boundary。
- 对 tool call 使用 discriminated unions。
- 对失败返回 error result types。
- 对 async wrapper 写 timeout、retry、trace hooks。

## 时间线

- Week 1：10 道 array/hash map/sliding window 题，写 50-100 行 Python tool router。
- Week 2：8-10 道 tree/graph/BFS/DFS 题，写 mini retrieval evaluator。
- Week 3：8-10 道 heap/interval/DP 题，写 JSON-backed memory store。
- Week 4：2 次 timed coding mock，混合复盘。
- Days 31-45：每周 2 次 timed coding。
- Days 46-60：如果 coding baseline 稳定，加入 Optional Rust Log Parser。

## 知识笔记

### Python Standards

核心理解：

- Python 是主面试语言，目标是 45 分钟内写出 medium 题，并能解释 complexity 和 edge cases。
- 每题都按 clarify、brute force、bottleneck、optimized approach、invariants、manual tests 的顺序推进。
- `heapq`、`deque`、`defaultdict`、dataclass / TypedDict 是当前最常用的实现工具。

常见误区：

- 只刷数量但不复盘 bug，会让同一类边界错误反复出现。
- 写代码时沉默会降低面试信号；需要边写边说明 invariant 和测试用例。

面试转译：

- “I first clarify constraints and edge cases, then write the simplest correct invariant before optimizing.”
- “Coding 不是和 Agent/LLM 系统分开的训练。每周的算法 pattern 之后都要接一个小型 component drill。”

### TypeScript Standards

核心理解：

- TypeScript 主要训练 API boundary 和 schema thinking，不作为算法主语言。
- Agent interfaces 包括 `ToolCall`、`ToolResult`、`AgentTrace`、`MemoryRecord`、`EvalCase`。
- 对 tool call 使用 discriminated unions，对失败返回 error result types，对 async wrapper 写 timeout、retry、trace hooks。

面试转译：

- “I use typed interfaces to make tool schema, traces, and eval cases auditable across model, runtime, and UI boundaries.”

### Mock Interview Set: Coding

核心理解：

- 题型池：Longest substring without repeating characters、Merge intervals、Top K frequent elements、Number of islands、Course schedule、LRU cache、Word ladder、Coin change。
- Strong signal：clarify edge cases、write clean Python、test manually、explain complexity。
- Weak signal：jump into code without constraints、cannot debug own code、cannot explain why algorithm works。

复习提示：

- 每道错题只记录四件事：pattern、bug、edge case、可复用模板。

### Optional Rust Log Parser

核心理解：

- Optional Rust Log Parser 只在 coding baseline 稳定后进入，不是核心准备。
- Build：parse JSONL traces、aggregate latency by span type、output slowest traces。

面试转译：

- “Rust is optional depth: useful for performance/system credibility, not core preparation.”
