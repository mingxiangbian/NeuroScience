---
id: coding
title: Engineering Foundations
status: not-started
learning_progress: 0
last_updated: 2026-07-18
priority: high
plan_scope: long-term
navigation_group: practice
module_role: support
goal_role: 工程基础
subsystems: 1,3,5,6
---

## 目标

为贾维斯 0.x 提供可独立完成、可测试、可诊断的工程基础。重点是把一个机制写成最小实现，定义行为边界，主动验证 edge cases，并在失败时定位原因。

## 当前状态

Python 是贾维斯 0.1 及独立实验的主语言。TypeScript 主要用于阅读 Cyrene 0.0 的历史实现或处理必要的接口互操作，不再作为长期训练主线。C++ 属于系统层军火库，只在性能、内存、并发或底层实现成为活动单元的真实墙时取用。

当前队列以 U1–U3 修复 decoder causal mask、建立 eval 和写失败分析，把“能组装”推进到“能验证和诊断”。

## 核心知识

### 算法与数据结构工具箱

这些知识按活动单元需要取用，不形成独立练习债：

- Arrays and strings：two pointers、sliding window、prefix sum。
- Hash maps and sets：frequency counting、dedup、index mapping。
- Stack and queue：monotonic stack、BFS queue。
- Trees：DFS recursion、iterative traversal、lowest common ancestor。
- Graphs：BFS/DFS、topological sort、shortest path basics。
- Heap：top-k、merge k lists、priority scheduling。
- Intervals：merge、sweep line basics。
- Greedy：排序后局部决策、反例检查。
- DP basics：1D/2D state、transition、base case。

每次取用都应说明：当前问题的简单基线是什么、瓶颈在哪里、关键 invariant 是什么、复杂度与边界如何影响系统。

### Python 实现基础

- clean function signatures
- dataclass / TypedDict
- heapq / deque / defaultdict
- async basics
- file and JSON handling
- testable small modules
- explicit state 与 typed boundaries
- unit test、property test 与 differential test 的基本使用
- profiling、logging 与最小可复现实例

### 系统层军火库

- 进程、线程、异步 I/O 与取消
- 内存布局、缓存与数据移动
- 文件、网络与序列化边界
- profiling、benchmark 与资源观测
- 需要时用 C++ 理解或实现性能关键路径

军火库只由真实工程问题触发。学到的内容必须回写到当次实现、实验或失败分析，不能脱离目标单独囤积。

## 任务

### 实现单元循环

1. 写清输入、输出、状态变化和禁止行为。
2. 先建立最简单的可运行基线。
3. 写最小测试和一个容易失败的边界 case。
4. 实现并记录关键 invariant、复杂度和外部依赖。
5. 保存失败现象与诊断证据，而不是只保留最终答案。
6. 说明这个实现怎样服务当前子系统或改变 0.x 的设计。

### Python 质量标准

每个实现单元必须做到：

- 函数签名清楚。
- 不依赖全局变量。
- 变量名能表达含义。
- 主动处理 empty input、single item、duplicates 和失败返回。
- 对状态变化、外部 I/O 和权限边界写测试。
- 能解释复杂度、失败模式与为什么采用当前设计。

### 与子系统的连接

- **① 基座模型**：tensor shape、mask、sampling 与训练 / 生成脚本。
- **③ 终身记忆**：索引、检索、更新、冲突和删除的数据结构。
- **⑤ Agent 执行**：状态机、队列、异步工具、timeout 与 cancellation。
- **⑥ 系统层**：profiling、I/O、并发、内存和性能关键路径。

## 时间线

- 当前：未开始；U1–U2 在 toy Transformer 上完成基线保存、mask 修复、对照与 eval 脚本。
- U7 解冻时：未开始；用 Python 建立贾维斯 0.1 的最小对话循环和清晰接口。
- 领域单元解冻时：未开始；只补该单元需要的数据结构、异步、测试与诊断能力。
- 系统墙出现时：未开始；按需进入 CSAPP / C++、profiling 或底层实现，并把结果结算在触发它的单元中。

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
