---
id: coding
title: Coding
status: in-progress
progress: 35
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

## 资源

### Mock Interview Set: Coding

1. Longest substring without repeating characters。
2. Merge intervals。
3. Top K frequent elements。
4. Number of islands。
5. Course schedule。
6. LRU cache。
7. Word ladder 或 shortest path variant。
8. Coin change。

Strong signal：

- clarify edge cases
- write clean Python
- test manually
- explain complexity

Weak signal：

- jump into code without constraints
- cannot debug own code
- cannot explain why algorithm works

### Python / TypeScript Implementation Mock

1. Implement a tool router with schema validation。
2. Implement an in-memory vector retrieval stub and recall@k evaluator。
3. Implement a trace logger for an agent loop。
4. Implement retry with timeout and exponential backoff。
5. Define TypeScript interfaces for ToolCall, ToolResult, AgentTrace。

Strong signal：

- small testable units
- clear error handling
- typed boundaries
- observability hooks

## 反思

Coding 不是和 Agent/LLM 系统分开的训练。每周的算法 pattern 之后都要接一个小型 component drill，让“会写代码”能转成面试证据。

## 面试表达

回答 coding 题时的表达顺序：

1. Clarify input/output and constraints。
2. State brute force。
3. Identify bottleneck。
4. Explain optimized idea。
5. Define invariants。
6. Code cleanly。
7. Manually test representative cases。
8. Give complexity。

Implementation drill 的表达句式：

- “我把它拆成可测试的小模块，因为 agent runtime 的失败通常跨越 model/tool/runtime 三层。”
- “这个 boundary 用 TypeScript interface 表达，是为了让 tool schema、trace 和 eval case 可审计。”

## 验收标准

- 45 分钟内完成 medium 题并能解释复杂度。
- Python 代码不依赖全局变量，变量名清楚。
- 每周至少一次 timed mock。
- 能完成 `ToolCall`、`ToolResult`、`AgentTrace`、`EvalCase` 的 TypeScript interface。
- 能把 coding 训练和 Agent/LLM component drill 连接起来讲。

## 下一步

- 先执行 Week 1 array/hash map/sliding window。
- 同步做 `Tool Router` drill。
- 记录每道错题的 pattern、bug、edge case 和可复用模板。

### Drill 8: Optional Rust Log Parser

Build：

- parse JSONL traces
- aggregate latency by span type
- output slowest traces

Interview story：

- Rust is optional depth: useful for performance/system credibility, not core preparation.
