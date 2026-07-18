---
id: evals-debugging
title: Evals & Diagnostics
status: learning
learning_progress: 0
last_updated: 2026-07-18
priority: high
plan_scope: long-term
navigation_group: practice
module_role: support
goal_role: 验证与诊断
subsystems: 1,2,3,4,5,6
---

## 目标

建立横跨六个子系统的验证与诊断能力：先定义“怎样算真的工作”，再用可重放运行、行为契约、trace 和对照实验定位失败。验证纪律不是贾维斯的一个部件，而是安装每个部件时都要使用的手艺。

## 当前状态

当前队列将用 U1–U3 的 causal mask 错误建立第一条完整证据链：先保存作弊基线，再修复、对照 teacher-forced loss 与自回归生成，最后解释指标为什么曾经给出假象。

已有 Cyrene eval case 审计和 benchmark 边界笔记可作为经验资产，但不会直接替代贾维斯 0.x 上的新验证结果。

## 核心知识

### 验证对象

- task success eval
- regression eval
- tool-use correctness eval
- latency/cost metrics
- human review sampling
- trace-based debugging
- golden set and adversarial set
- failure taxonomy

每项评估都要写清 workload、版本、环境、样本、阈值和未覆盖范围。一次成功运行不是成功率，一次计时不是 P95，低 loss 也不自动等于目标行为正确。

### 诊断链

1. 从系统目标或 policy 写出 expected behavior。
2. 保存真实 output、tool call、trace 和 state change。
3. 用 assertion 或 grader 直接检查这些观测。
4. 把失败归入可行动 taxonomy，而不是只记录“结果不好”。
5. 用对照、消融或 replay 缩小原因范围。
6. 记录结论会如何改变实现、接口或下一单元。

### 六子系统的验证焦点

- **① 基座模型**：训练目标、数据泄漏、生成行为与 benchmark 错位。
- **② 人格与情感**：行为一致性、情境适应、漂移与副作用。
- **③ 终身记忆**：写入精度、错误使用、冲突、陈旧与删除泄露。
- **④ 实时多模态**：端到端延迟、打断、轮次交接与体验劣化原因。
- **⑤ Agent 执行**：工具选择、参数、权限、循环、部分执行和恢复。
- **⑥ 系统层**：延迟分布、成本、资源、容量、降级和版本回归。

## 任务

### 最小 Eval Harness

围绕当前活动单元建立：

- versioned task set
- expected behavior 与禁止行为
- grader / assertion
- raw actual output 与 evidence
- pass / fail summary 和 failure tag
- model、prompt、code 与环境版本
- 可重放失败 case

### Trace Diagnostics

与 Agent Runtime 共用一套执行事实：

- trace id 与 span hierarchy
- prompt / model / retrieval / tool / state events
- latency、cost、error 与 cancellation
- sensitive-data redaction
- replay 与 runs diff
- 部分执行和恢复路径

Runtime 负责稳定发出事件；本模块负责用这些事件复核行为、聚合指标和定位回归。

### 对照与回归

- 为关键假设保存最简单基线。
- 一次只改变一个主要因素，或明确写出无法隔离的变量。
- golden set 保存必须持续成立的行为。
- adversarial set 覆盖越权、冲突、陈旧、打断和异常输入。
- flaky case 单独标记和调查，不把随机通过当作修复。

## 时间线

- 当前：未开始；U1–U3 完成错误基线、修复对照、两类指标和失败分析。
- 每个实现或实验单元：未开始；在结算前补齐最小测试、证据和失败解释。
- 跨子系统接入时：未开始；增加接口冲突、错误传播和恢复 case。
- 已知行为稳定后：未开始；把关键 case 固化为可重放 regression suite，并保留版本与原始 evidence。

## 知识笔记

### Eval Case 的六层结构

> 一个可信的 Eval case 不只是“输入加断言”，而是一条从测试条件、行为契约、真实观测到可复核证据的完整因果链。

`input` · `expected` · `actual` · `assertion` · `metric` · `evidence`

#### 核心定义

| 层 | 回答的问题 | 典型内容 |
| --- | --- | --- |
| Input | 运行前给了系统什么？ | fixture、请求、模式、配置、工具状态 |
| Expected | 系统应该或不应该做什么？ | 必须返回的内容、禁止泄露的内容、允许的动作 |
| Actual | 系统实际上做了什么？ | 返回文本、tool call、trace、状态变化、错误 |
| Assertion | 如何机械判断 actual 是否符合 expected？ | 相等、包含、不包含、schema、顺序或阈值检查 |
| Metric | 如何量化表现？ | success、leakage、latency sample、token count |
| Evidence | 人如何复核结论？ | 原始输出片段、trace ID、计时样本、失败原因 |

六层的关键边界是：`input` 是条件，`actual` 是观测。Fixture 里存在某条 Active Memory，只能证明测试准备了它，不能证明系统真的返回或使用了它。

#### 核心机制

一个 case 的可信度来自层与层之间的引用关系：

1. `expected` 必须由产品 Policy 或行为契约导出，不能由当前实现反推。
2. `assertion` 必须直接检查 `actual`，而不是检查 fixture 或测试名称。
3. `metric` 必须由同一组 actual observations 计算。
4. `evidence` 必须展示断言真正读取的事实，不能单独硬编码一套解释。

行为边界通常同时需要**正向断言**和**负向断言**。正向断言验证必须出现的行为；负向断言验证禁止行为没有发生。只有负向断言时，一个什么都不返回的系统也可能通过。

#### 程序流程

1. 固定 fixture、请求、模式和 Policy。
2. 从 Policy 写出 expected 的允许项与禁止项。
3. 运行系统并保存原始 actual output 与 trace。
4. 对同一 actual 执行正向和负向 assertions。
5. 从同一观测计算 metrics，并附上可定位 evidence。
6. 报告 pass、fail 与 case 本身尚未覆盖的边界。

#### 逐步示例

假设一个读取模式的 Policy 明确要求：返回 Active Memory，不返回 Pending Memory，也不返回 Fast Summary。

```python
case_input = {
    "mode": "balanced",
    "active_memory": "Prefer concise answers",
    "pending_memory": "Expose draft candidates",
    "fast_summary": "Temporary session summary",
}

actual = {
    "text": "User preference: Prefer concise answers",
    "latency_ms": 22,
}
```

Expected 可写成：

- `active_memory` 必须出现在返回文本中。
- `pending_memory` 不得出现在返回文本中。
- `fast_summary` 不得出现在返回文本中。

Assertions 直接读取 `actual["text"]`：

```python
text = actual["text"]

assert case_input["active_memory"] in text
assert case_input["pending_memory"] not in text
assert case_input["fast_summary"] not in text
```

Metrics 可以记录 `active_recall = 1`、`pending_leakage = 0`、`fast_summary_leakage = 0` 和 `latency_sample_ms = 22`。Evidence 则保存实际返回文本、三项布尔观测和本次计时。因为这里只运行一次，22 ms 只能叫 latency sample，不能叫 P95。

#### 概念对比

| 容易混淆的两项 | 区别 |
| --- | --- |
| Expected vs Assertion | Expected 是行为契约；Assertion 是把契约变成可执行判断的方法 |
| Actual vs Evidence | Actual 是原始观测；Evidence 是便于人复核该观测与结论的呈现 |
| Fixture presence vs Retrieval success | Fixture 只证明输入存在；retrieval success 必须在输出或 trace 中被观察到 |
| Metric vs Conclusion | Metric 是数值；结论还需要说明样本、阈值和覆盖范围 |

#### 边界与常见错误

- 测试名写着 `FAST` 或 `BALANCED`，不代表断言真的覆盖了对应 Policy。
- `not required` 不自动等于 `forbidden`；禁止项必须来自明确契约。
- Evidence 不能由单个条件触发后把其他指标全部写成 0，否则报告可能与 assertion 结果矛盾。
- 一条 case 的通过只能说明该 fixture 下的契约成立，不能外推成整个系统的准确率。
- 断言实现本身也可能有 bug，因此失败报告应保留 raw actual 和 trace，方便反向审计 evaluator。

#### 一句话总结

Eval case 的六层结构把输入条件、行为契约、真实观测、机器判断、数值指标和人工证据连成一条可审计链。

### Benchmark 与 Agent Behavior Eval

> Benchmark 衡量系统“跑得怎样”，Agent Behavior Eval 判断系统“做得对不对”；两者可以共享一次运行，但不能互相替代。

`latency` · `cost` · `percentile` · `behavior correctness` · `regression`

#### 核心定义

**System performance benchmark** 关注速度、成本和容量，例如 latency、throughput、token usage、memory footprint、并发能力。

**Agent Behavior Eval** 关注行为正确性与安全边界，例如是否选择正确工具、参数是否正确、是否完成目标、失败后是否恢复、是否泄露不应使用的 memory。

**Regression suite** 用固定 cases 检查已知行为是否被后续修改破坏。它证明的是“这些 case 在这个版本和配置下的结果”，不是生产流量上的总体准确率。

#### 核心机制

两类评估应共享同一批可重放运行，但分别回答问题：

1. 性能层记录每次运行的耗时、token、成本、资源和吞吐。
2. 行为层从 output、tool call、trace 和状态变化判断成功、错误与泄露。
3. 聚合层分别报告分布指标和行为通过率，并保留 case 级明细。
4. 结论层写清 workload、样本量、环境、scope 和未覆盖风险。

单次计时是 sample。P95 是一组可比较样本的第 95 百分位，需要重复运行、稳定环境以及明确的 warm-up 和异常值处理。把一次 22 ms 命名为 `p95`，不会让它自动获得分布意义。

字符数除以四可以作为粗略 token estimate，用于早期相对回归；它不能替代目标模型 tokenizer 的真实 token count，也不能直接当作账单成本。

#### 概念对比

| 问题 | Performance benchmark | Agent Behavior Eval |
| --- | --- | --- |
| 核心问题 | 多快、多贵、能承载多少 | 是否做对、是否越界 |
| 主要观测 | 时间、token、资源、吞吐 | output、tool call、trace、state |
| 常见聚合 | P50/P95、均值、QPS、成本 | success rate、error taxonomy、leakage |
| 典型失败 | 尾延迟、成本膨胀、容量不足 | 错工具、错参数、无恢复、信息泄露 |
| 能否互相替代 | 不能 | 不能 |

#### 逐步示例

比较“每轮回答后同步 summarization hook”和“周期性 maintenance”时，应回放同一组对话，而不是分别凭使用感受给出数字：

1. 固定对话、模型、配置、机器和缓存策略。
2. 每种方案先 warm up，再重复运行足够次数。
3. 记录前台新增 latency、总 token、调用次数和费用。
4. 分 scope 测量 time-to-availability：项目偏好可能按日维护，全局记忆可能按周或更长周期维护。
5. 用标注集测 Memory Precision、Recall、错误记忆泄露和下游任务成功率。
6. 同时报告性能分布、行为结果和 freshness tradeoff，而不是只挑一个有利指标。

同步 hook 的可能收益是 freshness 高，代价是把总结调用放进用户等待的关键路径。周期维护会移除这段同步等待和调用，但会引入记忆可用延迟。是否值得，必须由目标 scope 的 freshness 要求与完整测量共同决定。

#### 指标与公式

对 `n` 次可比较运行：

- `latency_samples = [t1, t2, ..., tn]`
- `P95 = latency_samples` 的 95% 分位值，而不是其中任意一次调用
- `behavior_success_rate = passed_behavior_cases / executed_behavior_cases`
- `memory_precision = retrieved_relevant / retrieved_total`
- `memory_recall = retrieved_relevant / relevant_expected`

Skipped case 不应放进 passed 的分母，也不应被当作成功。估算 token 时必须使用带 `estimated` 的字段名；只有 tokenizer 实算值才能使用 `token_count`。

#### 项目案例

Cyrene 的归档 deterministic full profile 为 67 cases：59 passed、8 skipped、0 failed。这个数字只描述该 regression suite 的归档结果，不代表生产准确率，也不代表每个 case 都已由项目负责人逐项审计。

从每轮同步 summarization hook 改为周期维护，依据是实际使用中观察到回答变慢和 token 消耗增加；没有保留改造前后的量化对照。因此可信表述是“改变了关键路径，并观察到定性问题”，而不是声称延迟或成本下降了某个百分比。

#### 边界与常见错误

- 用行为通过率回答 latency 问题，或用低 latency 证明行为正确，都是指标错位。
- 样本量为 1 时不能报告 P95；样本环境不同也不能直接比较分位数。
- `59/8/0` 必须同时带上 profile、总 case 数和 skipped 含义，不能简化成“准确率 100%”。
- 架构上移除同步调用可以说明关键路径发生变化，但没有 before/after 数据时不能虚构改善幅度。
- Freshness 必须按 scope 定义。项目级与全局级 memory 使用同一个可用时间阈值，会掩盖真实设计目标。

#### 一句话总结

可信评估把性能分布、行为正确性、数据 scope 和证据边界分开报告，再用同一批可重放运行解释它们之间的取舍。
