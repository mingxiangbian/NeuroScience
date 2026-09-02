# EXP-086：Staged Discourse正式闭环

- 登记日期：2026-09-01；Tier：Minor；RQ：RQ-S3 / Phase C.1跨论坛系统闭环。
- Parent：EXP-085 attempt 2，九任务有界验收已完成并独立通过。
- 目标：在已审核的Python Help公开来源上完成一次确定性采集、Research推理和独立核验。
  本实验验证来源与系统链路，不验证外部准确率或泛化等级。

## 前提与版本绑定

开始前必须同时满足：EXP-085 attempt 2 run=Completed、verification=Passed、
`exp085_complete=true`、`safety.gate_passed=true`、`operational_state=safe-to-continue`，并核对：

- plan SHA `fc72df94b88315752c0e896af1636779391b4baeee01757041b5d1134faeb28a`；
- run SHA `3ec838fbfbc68867a98496f80ee0eb34c62cb74c2a3b7467a1554ce45f176b1d`；
- verification SHA `a33ba29be93e631074b07c140a4fdbad9566b4aa9483633ab31497dcd91af13a`；
- 33成员冻结代码archive SHA `56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435`。

Archive必须逐成员匹配EXP-085 attempt 2 plan的32个source hash和原协议。EXP-085 attempt 1的
Failed记录继续保留，不作为本次模型输入或成功证据。旧EXP-080未执行且绑定失败的EXP-079，
本次不修改、不冒充或运行该消费者。

## 来源与固定采样

仅访问`https://discuss.python.org`公开匿名JSON接口，固定Python Help category 7。
不使用账号、cookie、API key、搜索、登录、私信、隐藏内容或任意URL；403、429、字段缺失、
身份/许可不符或其他访问错误立即停止，不重试、不换论坛或扩大分类。

请求固定为：

```json
{"site":"discuss.python.org","category_id":7,"max_topics":100,"max_items":400}
```

按topic创建时间降序取公开、非置顶、regular前缀；topic内按`post_number`升序。
只使用`include_raw=true`返回的原生`raw`，不回填`cooked`、HTML、标题或其他上下文。
排除system/非普通/删除隐藏帖子并记数；不可得post ID和截断topic单列。每个请求结束后至少等待1秒，
最多160次请求、900秒；wire与解压后每响应≤2MiB，单文本≤64KiB，任务≤400条。

成功样本必须为300–400条公开普通post。保存topic/post/parent、原帖URL、作者显示名、创建时间、
原生输入SHA、采样请求和排除计数。许可固定记录为CC BY-NC-SA 3.0，仅供本地非商业研究；
私有原文和逐条结果Git-ignored，不上传或公开再发布。该前缀不是完整时间窗或论坛总体样本。

## 模型与执行

Research mode、max_qwen_calls=500、audit_rate=0、seed42。沿用EXP-066冻结RoBERTa、
Qwen3-4B BF16、LoRA、head、bundle、阈值0.31、router cutoff0.7796902005928844和token上限256/384。
不训练、适配、选择checkpoint或读取gold/train/validation/test；不改输入、模型、精度、预算或fallback规则。

网站使用已通过EXP-085的staged路径：完整M1阶段正常退出和进程消失后，取得新fresh安静窗口，
独立M3进程只复用本任务M1概率/token元数据。正常Research不得fallback。一个逻辑任务、最多两个
串行模型进程；采集、等待、推理、清理和封存总上限3600秒，无API费用。独立服务和DB固定在
`forum-topic-emotion-web/private/validation/exp-086/attempt-1/`，端口8790，create-only、0700/0600。

## 安全门与停止

模型阶段前各需10个fresh normal样本，九段swap均<10MiB/s且无已见模型/辅助进程存活。
父RSS≤1GiB、子RSS≤12GiB、MLX peak≤10,000,000,000字节、磁盘≥512MiB；critical、
连续三段≥100MiB/s swap、未知观测、并发模型、孤儿、身份/hash漂移、异常/nonzero、
Research fallback、来源不足300或总时间超限立即停止。取消/失败必须在15秒内确认任务终态、
全部已见进程消失和dispatcher锁释放；保留工件，不在本attempt修复、重试或更换采样规则。

## 独立核验与结论边界

服务和模型退出后，独立consumer从保存DB、results、dashboard、source manifest、phase receipts、
transfer、runtime/process events和系统样本复算：

1. 来源host/category/query、300–400条、topic/post顺序、raw hash、许可/署名/URL和排除计数；
2. snapshot与逐项输入身份、六标签schema、M1/Research阈值与router数学、无fallback；
3. 同任务M1至M3的float32概率/token精确一致，真实M1/M3/cache/transfer成本完整；
4. M3初始化和每次forward事件闭合，聚合、两种权重、日周、类型/路由分层、诊断和Dashboard一致；
5. 两阶段安静窗口、进程身份、资源、正常exit0、最终全部已见身份消失与时间预算。

没有外部gold，不计算Accuracy、F1或跨域性能；也不将路由率、标签比例或分歧解释为正确率、
模型机制或论坛总体情绪。只有run=Completed、source count 300–400、verification=Passed、
`exp086_complete=true`、`safety.gate_passed=true`，才可称Discourse本地正式闭环完成。
该通过仍不是SLA、商业许可、跨域准确率或总体Phase C完成。无commit、stage、push或公开部署。
