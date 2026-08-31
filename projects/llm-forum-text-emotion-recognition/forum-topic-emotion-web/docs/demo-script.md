# Phase C 本地演示脚本

日期：2026-08-31。建议 6–8 分钟，只查看已完成任务，不提交新采集或真实推理。

这份脚本使用 EXP-076 的 Stack Overflow 来源任务和既有模型 smoke。当前 EXP-077 因 critical memory pressure 按规则停止：独立验证通过的是审计正确性，`exp077_complete=false`、`soak_gate_passed=false`，不是 Soak 成功。EXP-078 正式运行未继续。本演示只查看历史，不开启新的 Research、来源任务或重放。

## 演示前检查

1. 使用已恢复、仅用于查看历史的本机服务，不另开 dispatcher。若服务不可用，先展示封存元数据，不在演示中启动新计算。当前资源限制见 [使用手册](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/docs/user-guide.md)。
2. 在投屏或录屏前完成登录，不展示令牌文件、令牌内容或浏览器开发工具中的认证信息。
3. 确认下面的已有任务仍在保留期内。页面只列最近 100 个任务；若旧任务未列出或明细已清除，改用封存的元数据说明限制，不为恢复画面重跑模型。
4. 演示中不点击“创建并开始分析”“重放此快照”“清除全文”或“删除任务”。后两项只说明用途，不能删除正式证据。

| 演示对象 | 既有任务名称 | Job ID |
| --- | --- | --- |
| 真实来源闭环 | `EXP-076 / Stack Overflow / python / UTC week / source attempt 3` | `5ab3326150ee448ba326233264967d34` |
| Research 小批 | `EXP-076 / Research / same snapshot inputs` | `5e4fb878b68841e5ab342df83276375a` |
| M1 对照小批 | `EXP-076 / M1 / 8 authored inputs` | `b73e52ec61e542a4a95ab0ec9dcdfb04` |
| Demo 降级小批 | `EXP-076 / Demo / M3 budget zero` | `f4cb239b3c1445a299440a3789e7e478` |
| 既有新进程重放 | `EXP-076 / Research / same snapshot inputs` | `636a25ebe21a41538f29a3a1574a50ab` |

这些名称和 ID 已与现有数据库核对，不是预设的新任务。两个Research任务同名，列表中较新的是
重放任务，其replay_of指向原Research ID；下面用“Research小批”和“既有重放”区分。

## 0:00–1:00：说明系统解决什么问题

打开工作台，不提交任务。说明：

> 这是面向英语技术论坛的本地话题分析网站。它保存采样条件和原始输入，使用冻结的六标签系统，展示预测分布、来源和实际计算开销。这里展示的是模型预测，不是论坛总体情绪或新的准确率评价。

展示来源选项和三个模式的说明。Stack Overflow 使用新建问题队列；Python Help 使用已审核分类的创建时间降序前缀。来源接入与模型泛化是不同问题。CancerEmo 等外部金标评价和 context/C2 在本阶段仍暂停。

## 1:00–2:30：查看已验证的真实话题快照

选择 `Stack Overflow / python / UTC week`。指出已封存的条件为 `python`、UTC `[2026-08-23, 2026-08-30)`，原上限为 100 个问题和 500 个对象。

可核对的结果：46 个问题、46 条回答、248 条评论，共 340 条；340/340 完成，M1 实际计算 338 次、精确输入缓存命中 2 次、M3 实际调用 0。这个话题任务是 **M1 only**，不能把它讲成 340 条全部经过完整 Router/M3。

展开采样合同，解释“完成”只覆盖定义的 Question Cohort 和同窗口子内容，不是整个 Stack Overflow。查看一个来源条目，展示对象类型、日期、署名、原来源链接和 hash。评论的公开锚点后来做了展示修正；原封存地址留在 recorded_source_url，私有输入与预测没有改写。

不要把链接字段齐全说成匿名网页访问率 100%。来源站点可能限制匿名网页请求；演示可以只展示链接而不现场外跳。

## 2:30–4:00：切换统计口径

在同一已完成任务中依次切换：

1. Object-weighted → Unique-text：说明真实出现次数没有从底层删除，只有描述权重改变。组内不同预测平均，不取代表、不做 OR。
2. 标签出现率 → 阳性标签构成：前者分母是成功统计单位，后者是六标签总激活数；后者不是“有多少内容表达该情绪”。
3. UTC 日 → UTC 周：周一开始，桶内独立归组，缺日期不补。
4. 查看对象类型与 true/false/unknown 路由分层：每层有自己的分母，路由分组非随机，不能据此作模型准确率因果比较。

强调开关只读取已有记录，不启动模型。顶部对象覆盖率和路由成本保持真实 occurrence/forward 口径。旧任务的新视图是明细尚在时只读补算，不回填原封存 dashboard；若提示不可用，就说明保留期边界，不用零替代。

## 4:00–5:30：展示完整路由与降级边界

切换到 `Research / same snapshot inputs`，这是 8 条自编英文输入的既有 smoke，没有 gold。

可核对：8/8 完成；M1 计算 7 次、缓存命中 1 次；请求 M3 的对象有 4 条，其中 M3 计算 3 次、缓存命中 1 次。说明“路由对象数”“实际 forward”“最终路径”不是同一个数字。

再查看 `Demo / M3 budget zero`：8/8 完成，4 条请求路由的对象显式降级，M3 实际计算 0 次。这说明 Demo 的预算分支可用，不是 Research 模式的替代评价结果。

需要说明复现时，只引用上表的既有重放任务。原独立检查中输入和预测相同，M1/M3 概率最大差异为 0；不要点击按钮再做一次。配对分歧只覆盖同时有两模型决策的 4 条小批对象，不代表全话题分歧率。

## 5:30–6:30：查看运行诊断与数据控制

展示标签数分布、M1 熵/阈值距、token 长度与截断。说明它们帮助发现输入和运行差异，不能转成外域准确率。失败或取消缺少累计回执时，成本只是下界，未知部分不能补零。

指认 JSON/CSV 导出、取消、清除全文与删除控件，说明但不执行：CSV 不含全文或预览；清除全文保留元数据与预测，但之后不可重放；删除会移除整个任务。正式证据应保留，演示不是清理入口。

## 结束时的证据表述

> 已完成的 EXP-076 支持本机有限工作负载的采样、推理、统计和展示闭环。独立验证为 22/22 Passed，早期失败仍保留。它不单独支持长期 SLA、外部论坛准确率或人类情绪机制结论；后续运行验证按各自封存结果另行报告。

若被问到长期运行，明确补充：本轮 EXP-077 已触发内存安全停止，没有通过 Soak；不能把其审计 verification 的 Passed 简化成运行通过，也不能把已审核的 Python Help 接口说成 EXP-078 已完成。

本地证据入口：

- [EXP-076 source attempt 3](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/private/validation/exp-076/attempt-3/source.json)
- [EXP-076 独立验证](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/private/validation/exp-076/attempt-3/verification.json)
- [既有 smoke 元数据](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/private/validation/exp-076/attempt-1/smoke.json)
- [公开链接展示核对](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/private/validation/exp-076/attempt-3/presentation-verification.json)

这些工件留在本地 ignored 目录，不随演示上传或重新发布论坛语料。
