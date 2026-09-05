# SQMA-003 Incident 001 与 Attempt 2 协议

日期：2026-09-04

Incident：`SQMA-003-INCIDENT-001`

状态：`Attempt 1 capability/format gate Failed / Attempt 2 prompt-only correction authorized under frozen gates / Not started`

## 1. 登记目的

SQMA-003 attempt 1 已完成全部 144 次 classifier-free Qwen 调用，但没有通过预登记的 capability/format gate。本文件 append-only 地登记该失败，并限定一次全局、机械性的 Prompt clarity revision。

本文件不修改或覆盖 attempt 1，不授权 Agent-Tune、fold 3、gold、准确率评价或其他正式实验。当前用户已经授权按本文件门禁执行 attempt 2；attempt 2 尚未执行。

## 2. Attempt 1 冻结身份

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `configs/sqma-003-classifier-free-agent-preflight.json` | 8,942 | `7b9f41d222558b4e57eba4d1d1167d28f7dadc797a6228a4fbd38f71b8cc9445` |
| `runs/sqma-003-classifier-free-agent-preflight/attempt-1/run-claim.json` | 458 | `680d12595c1ce1e318cdd156e799350bceb5391249258f7ad540bd09d3f38473` |
| `runs/sqma-003-classifier-free-agent-preflight/attempt-1/run.json` | 4,004 | `a2046b675a2251a4685fe4c35e6f9c16943a43fd86c25b1093aba043274c7d88` |

`run.json` 的机械状态保持 `CompletedAwaitingVerification`，但其 `gate_passed=false`、`next_gate=stop_capability_gate_failed`。因此 SQMA-003 attempt 1 的研究流程终态是 `Failed by preregistered capability/format gate`，不是通过、部分通过或等待自动晋级。

Attempt 1 没有 `verification.json` 或 `complete.json`；不得为其补写 Passed completion。

## 3. 允许使用的失败证据

### 3.1 Public locked aggregate

以下数值来自公开 `run.json`，分母为 locked 部分：

| Gate field | Observed |
| --- | ---: |
| Planned physical calls | 144 / 144 |
| Raw schema valid rate | 0.266667 |
| Evidence + Appraisal valid rate | 0.583333 |
| Pragmatics Critic valid rate | 0.000000 |
| Judge valid rate | 0.750000 |
| Single Agent valid rate | 0.000000 |
| Locked S3 technical fallback rows | 24 |
| Token-cap hits | 2 |
| Mean modal exact-label-set agreement | 1.000000 |
| Full-Tune conservative wall projection | 113,781.05 s（约 31.61 h） |

格式门要求 overall 至少 0.98、每角色至少 0.95、technical fallback 最多 1 行且 token-cap hit 为 0。因此 failure 是明确的 gate failure，不需要查看 locked raw output 才能成立。

### 3.2 Shakedown ranks 0–7 error categories

只使用 8 个 shakedown component、24 个 S3 calls 的错误类别聚合，不记录或推断任何逐条文本或 raw response：

| Role | Valid | Error categories |
| --- | ---: | --- |
| Evidence + Appraisal | 4 | `enum`: 2；`evidence_length`: 2 |
| Pragmatics Critic | 0 | `enum`: 1；`json_decode`: 7 |
| Judge | 7 | `evidence_refs`: 1 |

这些类别支持“当前 Prompt 的输出格式说明仍不够清晰”这一机械性修订理由；它们不足以证明模型不会完成任务，也不能用于增加情绪标签规则、针对特定文本写例外或推断错误样本语义。

### 3.3 Process-boundary incident

用于汇总 shakedown 错误类别的临时诊断脚本曾对整个 `calls.jsonl` 逐行执行 `json.loads`，再根据 selection rank 跳过 rank > 7。因此，诊断进程的地址空间技术上 decode 过 locked records；不能声称 locked raw 从未被任何进程读取，也不能声称该诊断是 process-blind。

边界同时限定如下：locked 内容没有被打印、写入新的公开或私有诊断工件、暴露给 Prompt revision author 或进入其可见上下文，也没有形成错误类别、示例、统计或规则并用于本次修订。修订依据仍严格限定为第 3.1 节 public aggregate 与第 3.2 节 shakedown ranks 0–7 的聚合错误类别。

该事件登记为 `process-boundary incident`，而不是 locked evidence use。它不恢复 attempt 1 的 gate，也不授权从 locked records 提取其他信息。后续性能结论只能由仍未访问的 fold 3 Agent-Tune 数据在独立 gold 隔离流程中评价；当前 attempt 2 仍只是 classifier-free capability/format recovery。

## 4. 已通过但不能覆盖失败的门

- 调用计划完整：144 次物理调用均完成。
- 采样一致性指标为 1.0，高于 0.85 门槛。
- Full-Tune wall projection 约 31.61 小时，低于 48 小时上限。
- Wall time 为 2,357.57 秒，低于 4 小时；model load 为 5.34 秒。
- MLX peak 为 8,439,465,188 bytes，低于 10 GB。
- Process RSS peak 为 1,367,998,464 bytes，低于 12 GiB。
- Private output 为 171,503 bytes，低于 512 MiB。
- Gold、classifier outputs、fold 3/4、validation、test 和 network access 均为 false；没有训练或 adapter load。

这些通过项只说明本次有限运行完成且资源门未触发。它们不能把 capability/format failure 降格为警告，也不能支持准确率、Agent 增益、角色协作或泛化结论。

## 5. Incident 判断

Evidence strength：`Direct run evidence`。

Claim type：`Engineering/capability gate failure`。

当前最窄判断是：

> 在冻结的 classifier-free Prompt bundle v1、schema v2、validator v2、采样参数和 32-component call plan 下，Qwen3-4B 没有达到预登记的结构化输出可靠性门槛。

不能据此得出：

- Multi-Agent 的预测性能低；
- 角色分工无效；
- Qwen3-4B 无法进行论坛情绪分析；
- 增加 token、角色、模型或训练一定能够修复；
- Full Agent-Tune 可以继续执行。

## 6. Attempt 2 唯一允许的修订

Attempt 2 只允许一次原子化、全局 Prompt clarity revision。允许修改的内容仅包括：

1. 更直接地说明“只输出一个 JSON object，不输出解释、Markdown 或前后缀”；
2. 将 schema 示例中的枚举候选写法改为“必须选择一个具体合法值”，避免原样复制 `a|b|c`；
3. 明确每个角色的 exact keys、嵌套层级和空数组条件；
4. 明确 evidence span 必须是 `analysis_text` 中长度不超过 160 字符的逐字 substring；
5. 明确 Critic 必须返回闭合且可解析的单个 JSON object；
6. 明确 Judge 的 `evidence_refs` 只能索引已经验证的 evidence spans；
7. 明确 Single Agent 必须一次返回完整的三层嵌套对象。

修订必须形成一个新的完整 Prompt bundle，并登记独立 bytes/SHA-256；不得在一次运行中混用 v1/v2 角色 Prompt。

### 6.1 禁止修改

Attempt 2 不得改变：

- ontology、标签含义或 neutral 规则；
- Qwen checkpoint/revision、BF16、adapter=null、thinking=false；
- temperature 0.6、top-p 0.95、top-k 20；
- schema v2、validator v2 及其语义门；
- 32-component selection、rank、shakedown/locked 划分或 input snapshots；
- seed namespace/material、调用顺序和 144-call physical cap；
- 每角色 max-new-token cap、context cap 或 analysis-text cap；
- zero Qwen repair、fallback、稳定性和资源门；
- public/private/access 边界；
- accuracy/gold 禁止项。

Prompt revision author 不得根据 locked raw、逐条标签或 gold 编写特殊规则，也不得为获得通过而放宽 0.98/0.95、fallback、token-cap 或 evidence 门。上述诊断进程的技术解码不构成 locked 内容的使用授权。

## 7. Attempt 2 执行合同

1. 使用与 attempt 1 完全相同的 32 个 component、selection ranks、analysis inputs 和 seed derivation。
2. 使用新的 `attempt-2` public/private namespace；attempt 1 工件保持只读且 hash 不变。
3. 重新执行完整 144-call plan，不复用 attempt 1 的模型输出或局部成功行。
4. 在加载模型前完成 Prompt bundle、config、runner、verifier、tests 和空输出门的静态验证。
5. 仍不读取 gold、train-capable、consumer-gold、fold 3/4、validation 或 test。
6. Independent verifier 必须重放 selection、seed、Prompt identity、validator、全部 locked gates、access 和资源。
7. 只有 verification Passed 后才允许生成 attempt-2 completion。

Attempt 2 使用 attempt 1 的原始 gate，不新增“改善幅度”替代门：

- planned-call terminal rate = 1.0；
- raw schema overall ≥ 0.98；
- 每角色 raw schema validity ≥ 0.95；
- locked S3 technical fallback rows ≤ 1；
- evidence exact-substring rate = 1.0；
- out-of-ontology labels = 0；
- token-cap hits = 0；
- mean modal exact-label-set agreement ≥ 0.85；
- 全部身份、访问和资源门通过。

## 8. 停止与下一门

- 如果 Prompt-only static checks 失败，不执行 attempt 2。
- 如果 attempt 2 任一 capability、format、access 或 resource gate 失败，SQMA-003 以可信负结果收口；不自动创建 attempt 3，不改 schema/validator/token cap，不升级模型或增加角色。
- 纯 verifier 实现错误只能通过另行登记的 append-only recovery 复用密封 attempt-2 run；不得重跑 runner。
- Attempt 2 通过也不产生准确率证据。它只恢复 classifier-free capability/resource readiness。
- SQMA-004 fold-3 materialization、完整 Agent-Tune matched comparison 和所有 formal 工作在 attempt-2 completion 独立通过前继续阻断。

当前允许的下一步是：冻结新的 Prompt bundle 与 attempt-2 config/runner/verifier/tests，完成 no-result static checks，然后按用户现有授权执行 attempt 2。任一 static、capability、format、access 或 resource gate 失败即停；只有 attempt-2 completion 独立通过后，才允许进入 SQMA-004 fold-3 materialization。
