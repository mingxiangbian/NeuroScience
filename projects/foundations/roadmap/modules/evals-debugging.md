---
id: evals-debugging
title: Evals & Diagnostics
status: learning
learning_progress: 0
last_updated: 2026-08-14
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

U1 与 U2 已完成 causal / non-causal 的单变量训练对照、prefix-only 评估和未来 token 扰动实验，建立了第一条从信息边界到行为证据的完整链条。当前活动单元 U3 将把指标假象、失败原因与结论边界整理成完整分析。

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

- 当前：进行中；U1 已完成错误基线与修复对照，U2 已用 prefix-only 与未来扰动揭穿答案泄漏，U3 正在整理完整失败分析。
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

### Causal Mask：低 Loss 为什么可能是假象

> U1 通过一次只改变 `is_causal` 的对照实验确认了一个边界：decoder 在 next-token prediction 中看到未来输入时，teacher-forced loss 可能因标签泄漏而虚低。

`causal attention` · `teacher forcing` · `future-token leakage` · `autoregressive evaluation`

#### 核心定义

Decoder-only 模型在位置 \(t\) 的目标是根据已有前缀预测下一个 token：

\[
p(x_{t+1}\mid x_{\le t})
\]

**Causal attention** 只允许位置 \(t\) 读取位置 \(0\ldots t\)，使训练时的信息边界与自回归生成一致。**Non-causal attention** 允许读取左右上下文；它适用于目标已被遮住的 BERT 式 masked language modeling，但直接用于右移标签的 next-token prediction 时可能暴露答案。

#### 核心机制

本实验使用右移一位的 target：

```text
input:  [1, 2, 3, 4, ...]
target: [2, 3, 4, 5, ..., random]
```

当 `is_causal=False` 时，位置 \(t\) 能读取 `input[t+1]`，而它恰好等于 `target[t]`，形成 future-token leakage。当 `is_causal=True` 时，位置 \(t\) 只能读取当前及之前的输入，必须学习合法的 `x → x+1` 规律。修复的目的不是保证 loss 大幅升高，而是切断生成时不存在的信息通道。

#### 逐步示例

实验固定随机种子、数据生成方式、模型和训练超参数，只改变：

```python
is_causal=False  # 对照
is_causal=True   # 修复
```

| Epoch | Non-causal | Causal | Causal − Non-causal |
| --- | ---: | ---: | ---: |
| 1 | 5.1974 | 5.2715 | 0.0741 |
| 2 | 1.1752 | 1.2561 | 0.0809 |
| 3 | 0.7454 | 0.7540 | 0.0086 |
| 10 | 0.6956 | 0.6971 | 0.0015 |

Causal loss 每轮稍高，方向上支持“切断泄漏会失去训练捷径”，但没有出现预期中的巨大最终差距。递增规律很简单，causal 模型很快学会了合法解；同时，每条长度为 10 的 target 最后一个 token 从 1000 类中随机抽取，即使前 9 个位置全部预测正确，平均交叉熵下限仍约为：

\[
\frac{\ln(1000)}{10}\approx0.6908
\]

因此两条曲线最终接近 `0.69`，主要反映随机末位造成的不可约损失，而不是两种信息边界具有相同的生成能力。

#### 边界与常见错误

- 只有一个随机种子，不能把差距大小解释为稳定效应或统计显著性。
- 数据是重复的简单递增序列，不能推出 causal 模型在一般数据上总是更慢。
- 图中使用手动记录的 epoch averages；训练程序没有自动保存逐 step 原始日志。
- 低 training loss 不能证明模型会正确自回归生成。
- 换成 held-out split 仍不足以揭穿 non-causal teacher forcing：未见序列右侧依然包含答案。
- 真正的生成评估必须只提供前缀，让模型逐 token 生成；这是 U2 要检验的问题。
- 当前 toy decoder 不是标准 GPT，但两次运行共用同一实现，因此不破坏这次单变量对照。

本地产物位于 `Transformer-Decoder-Toy-Project` 工作区：`loss_mask_comparison.png` 保存 epoch-average 对比图，`plot_loss_comparison.py` 保存绘图数据和理论下限；两者目前尚未提交到远端仓库。

#### 一句话总结

Causal mask 的价值不是让 loss 更漂亮，而是让训练与生成遵守同一信息边界；未来答案一旦泄漏，低 loss 可能只证明模型会利用捷径，而不证明它会生成。

### Prefix-only 评估：怎样揭穿 Future-token Leakage

> U2 在没有可学习规律的 IID 随机序列上，把“模型有权看到什么”和“指标看起来多好”拆开验证：non-causal 模型可以在 teacher forcing 中复制右侧答案，但一旦只给真实前缀，它的生成能力就回到随机水平。

`prefix-only evaluation` · `future-token perturbation` · `NLL confidence` · `controlled experiment`

#### 核心定义

**Teacher-forced evaluation** 一次输入完整真实序列，并在各位置计算 next-token loss。对正确实现的 causal decoder，mask 会阻止位置 \(t\) 读取未来；但若错误关闭 causal mask，完整序列内部仍然放着 `target[t] = input[t+1]`，即使样本来自 held-out split，答案也没有消失。

**Prefix-only evaluation** 在每个位置只输入真实前缀 \(x_{\le t}\)，读取最后位置对 \(x_{t+1}\) 的预测。它复现了自回归生成时真正可用的信息边界。

**Future-token perturbation** 固定 \(x_{\le t}\)，只把未来的 `input[t+1]` 改成另一个 token，再比较位置 \(t\) 的输出分布。如果预测随未来 token 翻转，模型就实际利用了不该获得的信息。

#### 核心机制

1. 从 64 个 token 中独立均匀采样序列，使下一个 token 无法由前缀规律推出。合法 causal 模型的理论基线是 NLL \(\ln 64=4.1589\)、accuracy \(1/64=1.5625\%\)。
2. 两组模型加载同一份初始化，使用相同的训练 batch、随机种子与超参数，`dropout=0`；唯一改变的变量是 causal mask。
3. 在同一份新 eval set 上分别计算 teacher-forced、prefix-only 和 autoregressive rollout 指标。
4. 再修改每个位置右侧的答案 token，检查输出分布距离、预测翻转率以及模型是否跟随新 token。

#### 逐步示例

| 模型 | Teacher-forced NLL / Acc | Prefix-only NLL / Acc | 未来扰动 |
| --- | ---: | ---: | --- |
| Causal | `4.1636` / `1.481%` | `4.1636` / `1.481%` | TV `0`，flip `0%` |
| Non-causal | `0.00111` / `100%` | `11.1041` / `1.600%` | TV `0.99965`，flip/follow `100%` |

Causal 模型面对 IID 随机任务没有可学规律，因此 teacher-forced 与 prefix-only 表现一致，并且不受未来 token 改动影响。Non-causal 模型则在完整序列上几乎完美复制右侧答案；拿掉未来输入后，accuracy 回到随机水平，自回归 rollout accuracy 也只有约 `1.646%`。

Prefix-only accuracy 接近随机不代表 NLL 也应回到 `4.1589`。NLL 计算的是 \(-\log p(y)\)：只要模型给正确 token 的概率极低，即使 top-1 accuracy 同样很差，loss 也会显著高于均匀随机。`11.1041` 表明这个模型在泄漏答案缺席时仍然非常自信地猜错。

本地产物位于 `/Users/phoenix/DL/transformer`：`u2_leakage_experiment.py`、`u2_artifacts/u2_results.json`、`u2_artifacts/u2_leakage_comparison.png`，以及 causal / non-causal 两份 checkpoint。

#### 边界与常见错误

- 这是单 seed 的 toy experiment，足以演示当前实现中的泄漏机制，但不能说明效应大小具有统计普遍性。
- Non-causal 模型若没有学会复制未来 token，只能说明这次没有观察到它利用通道；不能证明泄漏通道不存在。
- BERT 式 masked language modeling 会把待预测目标遮住或扰动，双向上下文本身是其合法输入，不能把所有 non-causal 模型统称为作弊。
- Held-out split 防的是跨样本记忆，不会自动消除同一样本内部的 future-token leakage。
- 训练曲线每 50 step 只记录一个 batch，不应当作平滑后的 held-out learning curve。
- Future-token perturbation 能证明模型是否学会依赖未来信息；架构是否从根本上禁止访问，仍要结合 mask 实现检查。

#### 一句话总结

可信的自回归评估不只是换一份未见数据，而是必须让模型在评估时也只能看到生成时真正拥有的前缀；否则再漂亮的 held-out loss 也可能只是答案泄漏。
