# EXP-084：同次 M1 回执驱动的独立 M3 内存原型

Date：2026-08-31。Tier：Minor。RQ-S3；用于处理EXP-079/083的资源约束。
用户要求下一步。本次实施模型分时驻留的有界原型，不修改生产网站或旧冻结文件。

## 改变与固定项

原Research进程同时持有M1和M3。本次先用原M1-only进程完成340项，再确认正常退出、
全部已见进程消失，封存同次前7条M1概率/token元数据；通过原安静窗口后，独立进程
预填这些M1缓存，只加载M3，不再实例化M1模型。

复用原JobInference的特征构造、router、M3 backend和最终阈值；模型权重、精度、prompt、
tokenizer、截断、seed42不改。第二阶段输入仍是原序前七项原文，前六项不请求M3，第七项请求。
缓存未命中必须在原predict前拒绝，禁止把回放伪装成一次M1 backend计算；M1构造/预测调用
设拒绝检查。ready/proof明确M1未实例化、概率来自本次前置回执。

仍执行原部署资产身份核验，因此可能读取M1权重文件计算hash；M3依赖也可能导入Torch相关包。
本原型只保证不创建第二个M1模型，不声称不读M1文件、不导入Torch或必然消除换页。
除驻留外，第二次M1加载/分词/计算被回放替代，新增封存读取；不是原执行过程或受控因果等价。

## 输入、封存与预算

唯一数据为source job `5ab3326150ee448ba326233264967d34` 的340项固定快照，
snapshot SHA=`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
M1读取并处理全部340项；第二进程仅处理ordinals0–6。旧gold、train/validation/test、其他原文不访问。
EXP-082已验证七项只作独立结果对照，不可提供给新模型作为M1回填数据。

两个进程串行，一次序列、347计划回执，M1预算0、第二阶段M3预算1、audit0。总180秒，
工作150秒、退出清理15秒、监控/封存余量15秒；封存校验也计时。每次启动前最多等60秒，
需10个连续normal、无已知活子进程、相邻swap<10MiB/s样本。原critical、连续3间隔
swap至少100MiB/s、RSS12GiB、MLX10GB、parent1GiB、磁盘512MiB、身份、孤儿及退出门不变。
必要计数未知或超限就停，不清缓存、不设置wired limit、不降低门限，不重试。

本次M1输出独立写入m1-results.jsonl，完整正常退出后不再追加；transfer.json只封存前七项，
绑定该文件完整hash、源job/phase/340数量、原fingerprint、各项ordinal/input hash、
六维float32保真概率、完整/使用token数、截断标记及对应原回执行hash。
第二阶段单独写replay-results.jsonl，不改变已封存来源。派生fingerprint绑定原fingerprint、
策略m1-receipt-transfer-v1和transfer hash，防止把不同执行来源当作同一缓存身份。

## 等价、成本与证据

先合成验证封存来源、缓存未命中、M1禁止调用、真实ready状态、阶段映射、错误/中断清理与预算，
再运行一次。独立消费者检查两个进程真实exit/absence、同次transfer来源和全部资源门。
第二阶段M1概率必须与同次回执的float32值精确一致，token元数据一致；保持原字符数和
使用token数重算路由。与EXP-082比较七项M1/M3概率（atol1e-6），路由分支、六标签、
fallback、token/截断元数据严格一致；latency、资源、fingerprint、cache/cost字段不是等价目标。

完整成功时成本分列：338次真实M1计算、2次第一阶段任务内重复缓存、7条跨阶段回执复用、
1次M3计算。第二阶段原始m1_cache_hit=7保留并标为prelude_transfer_reuse，不能说是7次
新M1计算，也不能把2+7称为9个重复输入。未确认结果和资源峰值保留未知，不以0补齐。

只写`forum-topic-emotion-web/private/validation/exp-084/attempt-1/`：计划/claim、
process/system/stage日志、两份结果、可选transfer和m3-ready证明、run与independent verification。
前段失败时transfer/ready可以不存在，必须明确缺失而非伪造空成功。
工件私有create-only，无原文/tensor值/异常文本进入公开日志。阶段观察重用既有算法并为
新工厂提供独立映射，标注观测开销，不据此宣称效率优势。

只有完整347回执、功能等价、模型分时证据和资源门都通过，才称本有限原型通过。
任何失败立即停止；即便通过，也不证明旧故障根因、不替代九任务验收、不自动改网站或启动Discourse。
不训练、不量化、不上传、不stage/commit/push；所有旧失败保持原样。
