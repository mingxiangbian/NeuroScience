# EXP-085 attempt 2：进度回调修复后的同合同验收

- 登记日期：2026-09-01；Tier：Major；RQ：RQ-S3 / Phase C.1。
- Parent：EXP-085 attempt 1，run=Stopped、verification=Failed。
- 目的：修复已确认的软件接线错误后，重新执行原九任务有界验收。研究问题、输入、模型和判定门均不变。

## 前次失败与唯一修复

Attempt 1在Research回放第7项首次M3进度事件时停止。冻结代码只读和无模型fixture确认：
`_event(self, kind, **fields)`的位置参数与进度payload的`kind=begin`重名，触发TypeError。
错误发生在事件写入前，所以不能补造缺失事件，也不能改写attempt 1的Failed结论。

修改仅限：

1. 将内部helper参数`kind`改为`event_type`，保留输出payload中的`kind`字段及其含义。
2. 增加一项组合回归，使真实JSONL进度帧经过`StagedProcessRunner`后调用绑定的
   `StagedRunner._phase_progress`，并核对runtime-event、成本下界和资源字段。
3. 为attempt 2更新runner/verifier的输出路径、attempt字段和前次失败绑定。

不改RoBERTa、Qwen3-4B BF16、LoRA、head、bundle、阈值0.31、router cutoff
0.7796902005928844、token上限256/384、seed42、输入字符串、预算、缓存数学、精度或资源门。
不把这次修复描述为新模型、新方法或旧资源问题的解决方案。

## 历史绑定

Attempt 1的32个计划源文件和原协议已在任何修复前封存为33成员archive：
`forum-topic-emotion-web/private/validation/exp-085/attempt-1/frozen-code.tar.gz`，
SHA-256 `76664bc9b6d532e2fc0e81a7b169d25d512f32a72380cd5982e4360c9ce49733`。
Attempt 2必须逐成员核对该archive与attempt 1 plan，并绑定：

- attempt 1 plan SHA `9de78c110ef9a078025df831138e5acd63d08a596e7c972d5bd13d52f04aec25`；
- run SHA `b9965aaa8340212a3e49b3d1290febe962c402aeb3e31de97a10dc336f7d4686`；
- verification SHA `426c3ba406ca42b13942275b8d87384a8e8e9fa71fc9629739ec6b1a0f75bf2f`。

原EXP-084及更早工件继续保留，旧079未通过、080未执行。Attempt 2不得读取attempt 1的
预测作为模型输入或选择依据；它只将前次失败用作版本和修复范围证明。

## 固定输入、序列与预算

输入仍为EXP-076任务`5ab3326150ee448ba326233264967d34`的340项原生文本：
snapshot SHA `cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`，
logical SHA `8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4`。
338个精确输入组、25个route-eligible出现，顺序与输入字节不变；不访问gold、旧train/validation/test。

固定三轮，每轮M1-only → Research → Demo；预算0/500/20，audit_rate=0，seed42。
计划9个逻辑任务、15个串行模型阶段、3060条最终结果、5100条阶段回执。
完整预期仍为3042次真实M1、18次任务内M1重复缓存、135次成功M3、2040次跨阶段复用，
Demo每轮5项`m3_budget_exhausted`。这些数值只作验收合同，不用于回填缺失结果。

本attempt最多执行一次完整序列，总上限1800秒，其中工作上限1770秒，清理与封存使用剩余预算。
无API费用，不安装或更新依赖。输出固定在
`forum-topic-emotion-web/private/validation/exp-085/attempt-2/`，create-only、0700/0600、Git-ignored。

## 运行前门与停止条件

运行前必须满足：修复版本源码和本协议冻结；完整测试通过；新增组合回归确实经过父回调；
attempt 2目录不存在；模型/runtime/config和原输入哈希无漂移；前次archive及终态绑定匹配。

沿用attempt 1全部监护门：每个模型阶段前10个fresh normal样本及低swap窗口；父RSS≤1GiB、
子RSS≤12GiB、MLX peak≤10,000,000,000字节、磁盘≥512MiB；critical、连续三段高swap、
未知观测、身份/hash漂移、异常/nonzero、Research fallback或时间超限立即停止。清理必须确认终态、
全部已见进程消失、dispatcher锁释放；失败保留工件，不在本attempt自动修复或重试。

## 独立核验与推进条件

独立verifier仍从保存的DB、结果、phase receipts、transfer、process events和系统样本复算原合同。
此外必须核对首次M3初始化有一对闭合的`m3_load`事件，每个成功M3尝试有一对闭合的
`m3_forward`事件；progress成本与阶段回执、Store和API的物理成本口径一致，
不得借用attempt 1缺失事件。

只有run=Completed、9/9任务与3060结果完整、verification=Passed、`exp085_complete=true`且
`safety.gate_passed=true`，才允许进入新版本绑定的Discourse正式闭环。任何一项不满足，
继续保持Discourse未执行。该通过最多支持当前机器、固定负载的有限有界运行，不支持SLA、
外部gold准确率、因果内存修复或总体Phase C完成。无训练、上传、commit、stage或push。
