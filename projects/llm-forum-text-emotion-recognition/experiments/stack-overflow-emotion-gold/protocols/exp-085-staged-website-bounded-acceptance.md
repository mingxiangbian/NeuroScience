# EXP-085：分时驻留网站运行路径的九任务有界验收

- 登记日期：2026-08-31；Tier：Major；RQ：RQ-S3，Phase C.1 本地系统闭环。
- 用户要求：继续既定步骤，不再逐门询问；不改变已暂停的外部 gold 泛化、context/C2。
- 状态：先实现与合成验证，冻结代码及本协议后仅运行一次。结果另存，不回写本协议。

## 问题与变更

EXP-084已证明本次M1回执可供独立M3进程使用，但只回放七项，尚不能证明完整网站稳定运行。
本次将该策略接入原上传/任务/API/结果流程，完整覆盖M1-only、Research和Demo。
Research/Demo先计算整个任务的M1，再正常退出并确认所有已见子进程消失；通过新安静窗口后，
独立子进程使用同任务M1概率/token元数据，按原公式运行路由和M3。不创建第二个M1模型。

固定原RoBERTa、Qwen3-4B BF16、LoRA、head、bundle、阈值0.31、路由cutoff
0.7796902005928844、最大token256/384与seed42，不改精度、权重、输入或缓存/预算数学。
原bridge与runtime文件不改。源文件校验仍可能读取M1权重并导入Torch，不能声称完全不读M1文件。
跨阶段transfer只在生产任务内存和父子管道中存在；本次私有验收observer保存无原文的回执/transfer证据。

新fingerprint绑定base fingerprint、策略`m1-receipt-transfer-v1`和transfer SHA。
成本分别记录真实M1/M3尝试、同阶段重复缓存、跨阶段transfer访问。后者不是额外forward或重复文本数。
预计算完成但最终结果尚未返回时，API显示已知累计成本下界；异常中未观测的调用不补零。

## 证据版本与历史

原EXP-079仍未通过，EXP-080仍未执行，不把本次作为旧尝试重跑或改写其结论。
EXP-084的39个代码依赖和原协议已在生产改动前逐一校验并封存为40成员archive：
`forum-topic-emotion-web/private/validation/exp-084/attempt-1/frozen-code.tar.gz`，
SHA-256 `91ed8d8b0d8d8b631c7ad440cc824cd7dde813c0dc6f997bb1b8839dbef751af`。
本次consumer核对archive与原plan及原证书/工件，不再要求修改后的生产文件仍等于旧版本。
全部旧结果、协议及冻结模型保留。EXP-082/084仅供独立对照，不能输入本次模型。

## 输入、序列与预算

使用已验证EXP-076任务`5ab3326150ee448ba326233264967d34`的原340项文本，只读原数据库。
原快照SHA `cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`；
原逻辑行SHA `8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4`。
340项对应338个精确输入组、25个route-eligible出现且全部为不同输入。保持原顺序、UTF-8全文；
通过真实loopback HTTP提交上传快照，记录新快照SHA及逐项输入对应关系。无新来源请求或gold访问。

固定三轮，每轮依次M1-only → Research → Demo，audit_rate=0；预算分别0、500、20。
共9个逻辑任务、3060条最终结果；最多15个串行推理进程、5100条阶段回执。
预期每任务338次M1与2次重复缓存，Research25次M3，Demo20次M3及5项预算回退；
每个Research/Demo还有340次transfer访问，六任务共2040。完整预期真实M1=3042、M3=135。
此预期用于核对，不得回填缺失回执或跳过失败任务。

最多一次完整序列，不选择最好轮次。总工作与清理/封存预算1800秒，其中最后30秒保留给清理。
每次新模型阶段之前：最多60秒取得10个fresh正常样本，九个相邻swap I/O速率均<10MiB/s，
且无任何已见模型/辅助进程存活。GPU/CPU为本机Apple M3 16GiB；无付费API，费用0。
推理子进程严格单实例，辅助进程按owned关系记录，不错误当成第二个推理模型。

## 验收与停止

合成/集成先验证1–500项边界、重复一致性、预算0、缓存优先、Research失败与Demo回退语义、
真实ready身份、成本下界、取消/删除/到期与late-write拒绝。所有原安全门保持：
父进程RSS≤1GiB、子进程RSS≤12GiB、MLX peak≤10,000,000,000字节、空余磁盘≥512MiB；
系统采样完成后至少间隔1秒，实际相邻系统样本dt≤3秒；未知监护也停止。
critical pressure或swap I/O≥100MiB/s连续三个间隔立即停止，warning单独记录。
identity/hash漂移、非预算fallback、异常/nonzero退出、时间超限均停止；保留工件，不自动修复重试。
资源错误闭锁dispatcher，后续排队任务不自动启动。取消后限定15秒确认终态和全部已见身份消失。

独立verifier从数据库及阶段日志复算：

1. 9/9终态、3060/3060最终结果，模式/输入/顺序/预算/计数及聚合一致。
2. 全部340项M1与原076相差≤1e-6；同次M1至第二阶段的float32概率及token元数据精确相同。
3. 路由/阈值/离散输出复算；M3仅ordinal6有082/084旧参考，其余24项不伪称有旧路径全量对照。
   其余M3检查冻结接入、结果schema与跨轮同输入一致性≤1e-6；Demo比较预算内相应Research结果。
4. 每个阶段正常退出和fresh安静窗口、全程进程身份/采样/资源门；审核通过与运行完成分别表示。

记录`verification.status`、`exp085_complete`、`safety.gate_passed`。只有全部为通过/true，
才允许在新版本绑定下继续已授权Discourse正式闭环；不直接运行绑定旧EXP-079的EXP-080消费者。
失败审核可以Passed，但不能据此标记运行通过或推进Discourse。

## 产物与论文边界

产物在`forum-topic-emotion-web/private/validation/exp-085/attempt-1/`，目录0700、文件0600并Git-ignore。
保存plan、run-claim、完整环境/命令/Git dirty、stdout、service身份、原始系统采样/owned进程行、
阶段事件、M1/回放回执、transfer来源、任务结果及独立verification；不公开原文或逐条数据。
生产功能代码和聚合结论可进入系统实现章节。时延、RSS、MLX与压力只作当前机器和固定负载的描述，
不宣称无压力、旧故障因果已修复、长期SLA、正式部署效率、外部准确率或总体Phase C已完成。
不训练、不访问旧train/validation/test、不上传、不commit/stage/push。
