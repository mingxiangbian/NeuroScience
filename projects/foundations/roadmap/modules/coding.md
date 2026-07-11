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

### deque、stack 与 queue

> Stack、queue 和 deque 的区别不在于“装了哪些值”，而在于允许从哪一端加入和取出，以及这个操作需要付出什么代价。

`list` · `collections.deque` · `LIFO` · `FIFO`

#### 核心定义

- **Stack（栈）** 遵循后进先出（Last In, First Out, LIFO）。最后加入的元素最先离开。Python 中通常用 `list.append()` 入栈、`list.pop()` 出栈。
- **Queue（队列）** 遵循先进先出（First In, First Out, FIFO）。最早加入的元素最先离开。Python 中通常用 `deque.append()` 入队、`deque.popleft()` 出队。
- **Deque（双端队列）** 允许从左右两端加入或删除元素。它既能实现 stack，也能实现 queue，还能支持需要同时维护两端的算法。

| 需求 | 推荐操作 | 典型复杂度 |
| --- | --- | --- |
| 栈顶加入 / 删除 | `list.append()` / `list.pop()` | 摊销 `O(1)` / `O(1)` |
| 队尾加入、队首删除 | `deque.append()` / `deque.popleft()` | `O(1)` / `O(1)` |
| 双端加入 / 删除 | `deque.appendleft()`、`append()`、`popleft()`、`pop()` | `O(1)` |
| 删除 list 第一个元素 | `list.pop(0)` | `O(n)` |

#### 核心机制

Python `list` 是按连续位置组织的动态数组。执行 `list.pop(0)` 后，为了继续让第一个有效元素位于索引 0，后续元素都要向左移动一个位置。删除本身只发生一次，但移动量与列表长度成正比，因此是 `O(n)`。

`collections.deque` 针对两端操作设计。`popleft()` 更新左端边界并返回元素，不需要把剩余元素整体搬动，因此是 `O(1)`。从使用者视角看，剩余元素的**逻辑索引**仍会变小；但这不等于底层把每个元素都复制到前一个物理位置。

这也解释了一个容易混淆的点：复杂度描述的是操作量如何随输入规模增长，而不是 Python 表面上有没有重新编号。

#### 程序流程

1. 根据规则确定新元素从左端还是右端进入。
2. 根据服务顺序确定元素从哪一端离开。
3. 如果不同优先级内部仍要求 FIFO，为每个优先级维护独立队列。
4. 总是先清空高优先级队列，再处理普通队列。

#### 逐步示例

考虑事件：

```python
events = [
    ("normal", "A"),
    ("urgent", "C"),
    ("normal", "B"),
    ("urgent", "D"),
]
```

如果紧急任务也要求先到先得，就不能把紧急任务不断 `appendleft()` 到同一个队列，因为后来的 `D` 会跑到先来的 `C` 前面。使用两个 FIFO 队列时：

| 读入事件 | urgent_queue | normal_queue |
| --- | --- | --- |
| `normal A` | `[]` | `[A]` |
| `urgent C` | `[C]` | `[A]` |
| `normal B` | `[C]` | `[A, B]` |
| `urgent D` | `[C, D]` | `[A, B]` |

最终服务顺序是 `C → D → A → B`：优先级之间是“紧急优先”，同一优先级内部仍然是 FIFO。

#### 代码实现

```python
from collections import deque


def service_order(events):
    urgent_queue = deque()
    normal_queue = deque()
    served = []

    for typ, person in events:
        if typ == "urgent":
            urgent_queue.append(person)
        else:
            normal_queue.append(person)

    while urgent_queue or normal_queue:
        if urgent_queue:
            served.append(urgent_queue.popleft())
        else:
            served.append(normal_queue.popleft())

    return served
```

#### 复杂度分析

设一共有 `n` 个事件。每个人只进入一次队列、离开一次队列，所以总时间复杂度是 `O(n)`。两个队列和结果列表最多保存 `n` 个名字，额外空间复杂度是 `O(n)`。

如果对普通 `list` 连续执行 `pop(0)`，移动次数约为 `(n-1) + (n-2) + ... + 1`，总时间会增长到 `O(n²)`。

#### 边界与常见错误

- `deque.popleft()` 是从左端删除；`deque.pop()` 是从右端删除。两者都是 `O(1)`，但表达的顺序规则不同。
- `appendleft()` 会让后来元素先被 `popleft()` 取出；它适合“插队即反转顺序”的规则，不自动保证同优先级 FIFO。
- `deque` 不适合频繁随机访问中间位置。需要按索引反复读取时，`list` 通常更合适。
- 说“索引减一”不足以解释复杂度。要继续追问：是逻辑编号变化，还是底层元素发生了线性搬移？

#### 一句话总结

Stack 和 queue 定义取出顺序，deque 提供两端 `O(1)` 操作；选择容器时要同时匹配语义和复杂度。

### 单调队列

> 单调队列不保存窗口中的全部元素，也不只保存最大值和次大值；它保存所有仍可能在未来成为答案的候选索引。

`deque` · `sliding window` · `monotonic invariant` · `O(n)`

#### 核心定义

求滑动窗口最大值时，单调队列（monotonic deque）通常保存**索引**，并维持两个不变量：

1. 索引从队首到队尾递增，因此可以从左端判断候选是否已经离开窗口。
2. 对应的值从队首到队尾单调不增，因此队首始终是当前窗口最大值。

队列里可能有两个、三个甚至更多候选。例如严格递减序列 `[9, 7, 5, 3]` 中，没有较新的值能支配较旧的值，四个索引都需要暂时保留。

#### 核心机制

**右端 `pop()` 处理值支配。** 当新值大于或等于队尾候选时，新值更大、出现得又更晚。只要新值还在窗口，旧候选就不可能先于它成为最大值，因此旧候选可以永久删除。

**左端 `popleft()` 处理位置过期。** 当队首索引小于窗口左边界时，它已经不属于当前窗口。即使它的值最大，也必须删除。

这两个删除条件彼此独立：右端比较“谁更有竞争力”，左端判断“谁还在窗口内”。不能把 `pop()` 和 `popleft()` 简化成“都在删左边的旧数字”。

#### 程序流程

1. 读取右端新元素。
2. 从队尾删除所有值不大于新值的候选。
3. 把新元素的索引加入队尾。
4. 从队首删除已经小于窗口左边界的索引。
5. 当窗口形成后，从队首读取当前最大值。

#### 逐步示例

对 `values = [3, 5, 2, 4]`、窗口大小 `k = 3`：

| right | 新值 | 队列变化（索引） | 候选值 | 当前输出 |
| --- | ---: | --- | --- | ---: |
| 0 | 3 | `[] → [0]` | `[3]` | 窗口未形成 |
| 1 | 5 | `[0] → [] → [1]` | `[5]` | 窗口未形成 |
| 2 | 2 | `[1] → [1, 2]` | `[5, 2]` | 5 |
| 3 | 4 | `[1, 2] → [1] → [1, 3]` | `[5, 4]` | 5 |

在 `right = 1` 时，5 从右端淘汰 3；在 `right = 3` 时，4 从右端淘汰 2，但不能淘汰更大的 5。

过期是另一件事。若窗口为 `[5, 3, 4]` 后继续右移到 `[3, 4, 2]`，值 5 的索引已经越过左边界，此时才从队首 `popleft()`。

#### 代码实现

```python
from collections import deque


def sliding_window_max(values, k):
    if k <= 0 or k > len(values):
        return []

    candidates = deque()
    answer = []

    for right, value in enumerate(values):
        while candidates and values[candidates[-1]] <= value:
            candidates.pop()
        candidates.append(right)

        left = right - k + 1
        if candidates[0] < left:
            candidates.popleft()

        if left >= 0:
            answer.append(values[candidates[0]])

    return answer
```

#### 复杂度分析

虽然代码里有嵌套 `while`，总复杂度仍是 `O(n)`。每个索引只会进入队列一次，并且最多因为“被支配”或“过期”离开一次。所有 `pop()` 和 `popleft()` 的总次数不会超过 `n`。

队列最多保存一个窗口内的候选，空间复杂度是 `O(k)`。

#### 边界与常见错误

- 队列保存索引而不是只保存值，否则无法判断元素是否已经离开窗口。
- 使用 `<` 还是 `<=` 取决于是否保留相等值。用 `<=` 会保留更新的相等候选，通常更容易处理过期。
- 队首是当前最大值；队列其余元素是按优先级排列的未来候选，不等于严格意义上的“第二大、第三大”。
- 右端 `pop()` 的触发条件是新值支配旧候选；左端 `popleft()` 的触发条件是索引过期。
- 看到嵌套循环不能直接判断为 `O(n²)`，要计算每个元素在所有循环中总共被处理几次。

#### 一句话总结

单调队列用右端删除被支配候选、用左端删除过期候选，使每个索引只进出一次并在线性时间内维护窗口最大值。
