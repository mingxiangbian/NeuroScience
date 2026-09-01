# DEC-PHASE-C1-BOUNDED-OPERATIONAL-VALIDATION-V1

Date：2026-08-31。用户要求：继续验证有界稳定运行和Discourse正式闭环，不恢复外部gold。

## 目的与历史边界

本阶段属于RQ-S3系统实现，回答个人本机网站能否在固定资源与有限任务数下完成真实输入处理。
它不改变模型研究问题，不训练、调阈值、换seed或访问历史train/validation/test。

原Phase C已有核心网站和Stack Overflow有限来源证据，但未达full operational completion。
EXP-077仍为Stopped / critical_memory_pressure，审核Passed而Soak未过；旧工件、代码与协议不改。
这不是把36任务缩减为9任务后重算旧实验，也不宣称任务数是原失败原因。原失败发生在第2任务，
本次额外规定任务前安静窗口和已拥有子进程退出证据，用于有限使用条件的验收。

评审中一处解释需纠正：EXP-076真实来源job使用M1-only，故实际M3=0；其假设路由触发为25/340，
不是已验证Router在这批数据上主动选择零调用。本次Research必须实际覆盖冻结路由的M3输入。

## 顺序

1. EXP-079 Bounded Runtime Acceptance：三轮M1-only → Research → Demo，9个fresh-process任务，
   每个完整340条已封存输入，合计3,060个事件。完成run与独立verify。
2. 只有EXP-079已验证全部安全/完成门后，执行EXP-080 Discourse Formal Topic Run。
   继承EXP-078的站点、分类、原生raw、采样与资源合同，仅将安全依赖改为新EXP-079。
   原EXP-078保持未执行；新编号避免覆写其EXP-077依赖或假称旧门通过。
3. EXP-081仅综合已封存终态、更新中文私有报告和claims ledger；成功、负结果、阻塞分别表达。

用户材料同时建议EXP-080和“再执行EXP-078”，这里固定采用EXP-080继承来源合同，不修改原编号。
这是记录命名和依赖澄清，不扩展采样范围。

## 成功与停止

EXP-079的目标是9/9完成、有效输出、模式/成本正确、无critical/thrashing/孤儿或身份漂移；
plateau按相同定义报告但非新主要成功门。9/9也不证明生产SLA或长期连续运行。
EXP-080成功只建立第二平台输入/服务可运行，不建立新论坛accuracy/F1或Router收益。

出现资源、身份、监测缺失或真实运行失败时停止后续模型负载，不自动重试、修复原attempt、
调低模型精度或修改gate。可继续只读核验与文档。不能未经用户要求关闭其他应用来腾内存。
若Research仍失败，M1-only是否已验证须看其本阶段实际完成数量，不能用1次成功声称3次通过。

本次不stage/commit/push、公开部署、上传原文或创建自动化。报告和逐条工件均在Git-ignored private。
