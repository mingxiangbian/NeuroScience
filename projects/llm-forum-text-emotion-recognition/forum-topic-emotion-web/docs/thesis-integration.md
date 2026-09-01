# Phase C 论文整合稿

日期：2026-09-01

本文件提供可并入论文的系统实现、系统验证和限制段落。仓库中没有可确认的论文主文档，
因此本文件不是论文正文，也不替代最终格式、图表编号或导师审阅。

## 系统实现章节

系统采用FastAPI提供仅监听本机回环地址的Web接口，使用SQLite保存任务、输入快照、逐条结果和聚合结果。
单一dispatcher按队列调度任务，HTTP进程不加载模型；推理在独立子进程中执行。系统保留三种模式：
M1-only仅运行RoBERTa，Research按冻结Router与cutoff决定是否调用M3，Demo使用同一Router但允许
登记的M3预算fallback。当前staged路径先完成同任务M1 prepass并确认进程退出，再由独立M3进程
复用同一任务的M1概率和token记录。Transfer reuse单独记账，不计作额外M1 forward或输入重复。

来源包括文件上传、Stack Overflow Question Cohort和经审核的`discuss.python.org` Python Help分类。
系统为来源对象保存输入hash、来源链接、署名和许可元数据，并区分真实内容出现次数与规范化文本组。
Dashboard展示的是采样内容中的模型预测分布、路由与实际计算成本，不把预测解释为作者真实情绪或
论坛总体情绪。

## 系统验证章节

系统验证应分为四类，不合并成“生产稳定性”：

| 验证层 | 证据 | 结果 | 解释边界 |
| --- | --- | --- | --- |
| Functional verification | 579项软件测试、EXP-076有限来源链 | Passed | 功能、状态机和计算口径，不替代真实长负载 |
| Bounded operational acceptance | EXP-085 attempt 2 | 9/9任务、15/15阶段、3060/3060最终结果、5100/5100阶段回执 | 当前16 GiB机器、冻结模型和固定有限负载 |
| Second-source portability | EXP-086 | 400条Python Help公开post、400次M1、46/46次M3 | 无gold来源到结果闭环，不是跨域准确率 |
| Release acceptance | 自动RC门和隔离浏览器smoke | Passed | 本地交付QA，不是公网、多用户或生产认证 |

EXP-085 attempt 2的完整物理成本为3042次M1、18次任务内真实重复缓存、135/135次M3和
2040次同任务transfer reuse。三轮Demo共有15个`m3_budget_exhausted`，均为预注册预算结果，
不是模型或服务崩溃。557个资源采样点包含12个warning、0个critical/unknown；最高swap区间为
778.938 MiB/s，最长连续高值为2段，未达到连续3段停止门。

EXP-086在69次请求/响应后接收400条公开regular post，来自64个selected topics。M1与M3阶段各有
400条回执，M3实际执行46次并全部成功，0 fallback/audit。213个资源采样点包含2个warning、
0个critical/unknown；最高swap区间为374.571 MiB/s，最长连续高值为2段。所有模型root正常退出，
已见身份在终态消失。

## 失败沿袭

EXP-077、EXP-079、EXP-083和EXP-085 attempt 1的失败或停止记录必须保留。EXP-085 attempt 1因
progress callback字段冲突停止，唯一完整verification为Failed；attempt 2只修复内部参数接口并补
端到端组合回归，不修改模型、Router、阈值或输入。后续通过不能把旧终态写成Passed。
EXP-078与EXP-080保持Not executed；EXP-086是独立新协议，不是对它们的等价重跑。

## 限制与未来工作

- EXP-086没有gold，accuracy、F1和跨域预测泛化未知。
- 400条达到item limit，最后一个topic被截断；`sampling_complete=false`且
  `collection_complete=false`。实验完成不等于平台内容采集完备。
- 11.5%的M3路由率是描述统计，不表示帖子更难、M3更正确或Router提高准确率。
- 通过运行仍观察到warning和短时高swap，不能写成无内存压力或长期SLA。
- Sampled RSS、回执RSS和MLX lifetime peak口径不同，不能相加。
- Staged设计没有完成只改变驻留策略的matched因果实验，不能声称因果修复旧内存问题。
- 多用户、并发、重启/故障恢复SLO、公网安全和商业再发布没有验证。
- Context/C2与外部gold被移出关闭的Phase C范围，未来重新开启需要独立协议。

## 可直接使用的总结

> 在当前16 GiB本地环境中，EXP-085完成9个逻辑任务、15个模型阶段和3060条最终结果；EXP-086在一个经审核的Python Help公开前缀上完成400条采样、400次M1推理和46次M3推理。该证据支持冻结有限负载下的本地系统运行与第二来源服务闭环，不支持Discourse预测准确率、长期SLA或论坛总体情绪。

## 证据入口

- [最终范围决策](../../experiments/stack-overflow-emotion-gold/protocols/dec-phase-c-final-scope-and-closeout-v1.md)
- [Phase C验收记录](acceptance.md)
- [Release acceptance](release-acceptance.md)
- [复现与离线交付包](reproducibility-package.md)
- `private/reports/final-claims-2026-09-01.md`
- `private/reports/phase-c-final-closeout-2026-09-01.md`
