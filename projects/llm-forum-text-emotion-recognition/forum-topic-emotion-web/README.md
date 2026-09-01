# 话题情绪工作台

Phase C最终状态（2026-09-01）：`Closed / Completed within bounded local research scope`。
Phase C.1为`Completed / Verified Pass`。系统定级为“经过验证的有界本地研究原型，并完成两个
技术论坛来源的服务链路迁移”。最终范围见
[DEC-PHASE-C-FINAL-SCOPE-AND-CLOSEOUT-V1](../experiments/stack-overflow-emotion-gold/protocols/dec-phase-c-final-scope-and-closeout-v1.md)；
当前claims、closeout与发布QA见[验收记录](docs/acceptance.md)。旧失败和未执行实验继续保留。

最新状态（2026-09-01，EXP-086）：Python Help正式staged闭环已通过。固定公开前缀采集400条、
69次响应；M1 400次，46条路由至M3且46/46成功，0 fallback。独立verification=Passed、
`exp086_complete=true`、`safety.gate_passed=true`，所有进程已退出。
来源达到item limit，最后1个topic截断且`collection_complete=false`；这是一次无gold服务链路，
不代表论坛总体、外部准确率、完整线程、SLA或商业许可。结合EXP-085 attempt2，
Phase C.1最低目标“有界稳定运行＋Discourse正式闭环”已完成；外部gold/context和公网部署仍暂停。

最新状态（2026-09-01，EXP-085 attempt 2）：回调最小修复和真实组合回归后，九任务有界验收
9/9完成，独立verification=Passed、`exp085_complete=true`、`safety.gate_passed=true`。
三轮共3060条最终结果、5100条阶段回执；完整成本为3042次M1、135次成功M3、
2040次跨阶段复用和18次任务内重复缓存。557样本含12个warning、0 critical/unknown，
最长连续高swap为2段，未达停止门。它是本机固定负载的有限通过，不是无压力、SLA或外部准确率证据。
其后完成了[EXP-086 staged Discourse正式闭环](../experiments/stack-overflow-emotion-gold/protocols/exp-086-staged-discourse-formal.md)；
旧EXP-080保持Not executed，CancerEmo等外部gold和context/C2作为未来独立范围暂停。

历史记录（2026-09-01，EXP-085 attempt 1）：完整任务的M1/M3分时路径接入后，
首次真实验收因新增进度回调参数重名停止，完整verification也未通过。
Research/Demo先完成本任务M1，再经过退出与安静窗口，由独立M3进程复用本次M1结果。
新增阶段进度、两阶段实际成本与transfer分列，以及资源停止后禁止自动启动后续任务。
538项tests未覆盖真实进度回调的组合路径；实跑98.639秒，M1-only完成340，Research的M1预计算
完成340、回放6项后失败，后续7任务未启动。失败事件未入journal，完整核验为
`Failed/staged_lower_bound_range`，不能把它表述为网站或稳定性通过。
本次94次系统采样均normal、进程已全部退出，但没有完成M3负载，是否解决旧资源问题仍未验证。
该版本已停线并封存；在该历史终态中Discourse尚未执行。随后attempt 2只做最小回调修复并通过，
不改变本段Failed状态。详情见[当前交接](../experiments/stack-overflow-emotion-gold/HANDOFF.md)。
详见[EXP-085协议](../experiments/stack-overflow-emotion-gold/protocols/exp-085-staged-website-bounded-acceptance.md)。

当前追加（Phase C.1，2026-08-31晚）：用户关闭占用应用后，280项tests通过并执行EXP-079 attempt3。
仍在Research阶段触发critical pressure，1/9任务完成（M1 340条、Research 6回执后取消）。
本次完整记录独立审核Passed，但exp079_complete=false；旧attempt2的Failed保持不变。
EXP-080仍未执行，完整有界稳定性与第二平台正式闭环未建立。服务已停止，不再自动重试或降门。
新报告：[减少后台应用后的验证](private/reports/phase-c1-attempt3-reduced-background-report-2026-08-31.md)。

后续诊断：EXP-082七项短诊断通过；EXP-083增加完整M1前置负载后，340项M1完成、Research6/7
因连续高换页停止，触发时首次前向尚无结束回执。当前370项软件tests通过，资源验收仍未通过；
详见[实验交接](../experiments/stack-overflow-emotion-gold/HANDOFF.md)，不自动重试或推进Discourse。

最新独立EXP-084原型已完成同次M1回执转交，347/347结果、功能等价与本次资源门均通过（438项tests）。
EXP-084本身没有修改网站；上述EXP-085是独立的完整接入与验收，不能从短原型推断网站稳定或RSS下降。

Phase C 本地实现。上传 CSV / JSON / JSONL，或按标签与时间窗口采样 Stack Overflow，
查看六标签预测、内容来源、UTC 趋势与路由成本。已增加审核后的 Python Help Discourse adapter；
原 Phase A/B 实验保持不变。

当前交付：**Stack Overflow来源闭环、固定九任务staged验收和一次Python Help正式闭环均已通过各自独立验证**。
原窗口内46个问题、46条回答、248条评论，共340条，M1推理340/340完成；独立验证22/22 Passed。
四个真实小批任务、32条预测的统计与新进程重放仍复用原结果，没有重复执行。
两权重、日周、类型/路由分层、诊断、CSV和全文清除已补齐。
已有5个成功任务、372条结果的新视图与CSV只读QA Passed，原记录不改。前两次来源失败保留。
EXP-085 attempt 2完成9/9逻辑任务、3060最终结果和5100阶段回执；EXP-086完成400条
Python Help公开post、400次M1和46/46次M3。两者都通过资源与独立verification，
但仍观察到warning和短时高swap，不构成长期SLA或无压力证据。
**EXP-077的critical-memory负结果和EXP-078未执行状态继续保留**；后续成功不回写旧终态。
功能和文档已交付，不代表跨域预测泛化、生产服务或论坛总体情绪证据。
详细通过项、失败和下一步见 [验收记录](docs/acceptance.md)。

目前开发范围不含 CancerEmo、JIRA 等外部金标泛化，不含 context/C2。
Discourse只允许已审核的discuss.python.org / Python Help（category7），其他站点拒绝。
关闭范围不再要求外部gold、更多论坛、context/C2、生产SLA或公网部署；重新开启必须另立协议。

## 启动

本模块已有隔离的 `.venv`。在本目录运行：

```sh
.venv/bin/python start.py
```

打开 <http://127.0.0.1:8787>。从 `private/access-token` 读取本机令牌并登录。
不要将令牌放进 URL、截图、Git 或外部服务。服务仅允许 loopback，不要将其代理到公网。
启动不会立即加载模型，创建任务后才会启动独立模型进程。用 Ctrl-C 停止服务；
进行中的任务停止并保留为失败，不自动续跑。

如果重建环境，先用 Python 3.12 创建本目录 `.venv`，再运行
`.venv/bin/python -m pip --isolated install -r requirements-lock.txt`（本次验收的完整依赖版本）。
不要向 `phase-a-runtime` 安装网站依赖。推理固定使用其 Python 3.11 与已验证模型资产。

## 三种模式

| 模式 | 行为 | 失败处理 |
| --- | --- | --- |
| M1 only | 只加载 RoBERTa，不执行 M3 | 模型错误停止任务 |
| Research | 原冻结 router 决定是否调用 M3；不按当前批次重新取 top-k | 必需 M3 失败则停止，不回退 |
| Demo | 同一 router，任务 M3 调用预算可配置 | 普通 M3 失败或预算耗尽时复用本条 M1；显式标记 |

三者都对身份漂移、非有限输出与资源超限硬停。调用预算包含失败尝试，精确输入缓存命中
不消耗调用次数。缓存与跨阶段M1结果仅属于当前任务；重放快照是新任务、新进程、新缓存。
Research/Demo的M1预计算进度与最终预测进度分别显示。预计算已发生的调用进入已知累计成本，
跨阶段复用不增加forward计数；未收到完整终态的调用成本仍为下界。
分阶段Research/Demo的逐条`latency_ms`只含回放阶段，不含M1阶段或安静窗口；首次M3加载仍在相应回执内。
以`staged_latency_scope`标记，不可与旧路径逐条时延直接比较。验收另记完整任务/阶段耗时。
首版 audit rate 固定为 0，不运行额外模型抽检。

## 数据与解释

- 上传最多 5 MiB、500 条、每条 64 KiB，UTF-8。文本列默认 `text`；URL/日期可缺失。
- Stack Overflow 只取新建问题队列及其同窗口内回答/评论，不等于全站论坛事件流。
  请求参数、API filter、quota/backoff、上限、停止原因保存在 manifest。
- 模型输入保持原选定字符串；显示使用纯文本，预览最多 280 字符。
  `model_input_hash` 是精确 UTF-8 hash；`dedup_hash` 仅用于描述归一化重复组。
- 相同文本属于不同帖子时仍计为多个 occurrence，缓存不改变分母。
- 六标签 prevalence 的分母是成功预测条数；多标签比例可相加超过 100%。
  neutral 只是六标签均未触发。失败与缺失不是 neutral。
- 配对分歧只覆盖同时有 M1/M3 决策的路由子集；不代表全部内容。
  分数与不确定性不是校准后的正确概率，不能当作 accuracy。

全文与来源原始 payload 默认保留 7 天，逐条元数据与预测 30 天，聚合 90 天。
到期清理在服务启动及每小时执行，所以**未运行时不会后台自动清理**。
删除任务会先撤销读取/写入，再停止其子进程并清除数据库行。
SQLite 清理不等同于对系统备份或 SSD 介质作密码学擦除。
`private/`、环境、缓存全部 Git ignored；导出也只在本机，默认不含全文。

## 验证与剩余范围

```sh
.venv/bin/python -m pytest tests -q
node --check static/app.js
```

真实验收协议：
[`EXP-076`](../experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md)、
[`EXP-077`](../experiments/stack-overflow-emotion-gold/protocols/exp-077-runtime-soak-v2.md)、
[`EXP-078`](../experiments/stack-overflow-emotion-gold/protocols/exp-078-discourse-operational.md)、
[`EXP-085 attempt 2`](../experiments/stack-overflow-emotion-gold/protocols/exp-085-staged-website-bounded-acceptance-attempt-2.md)、
[`EXP-086`](../experiments/stack-overflow-emotion-gold/protocols/exp-086-staged-discourse-formal.md)。
合成测试通过不等于真实模型运行通过；通过的真实结果见本地 ignored
`private/validation/exp-076/attempt-3/verification.json`、
`private/validation/exp-085/attempt-2/verification.json`和
`private/validation/exp-086/attempt-1/verification.json`。原smoke与所有失败分别保留。
数值验收绑定的源码归档为attempt-3/verified-code.tar.gz；其后仅修正公开评论链接，
另有presentation-verification.json确认248个链接映射及私有数据不变。
这些有限验收不构成长期可用率、生产 SLA 或外部泛化证据。

详细合同见 [spec](docs/spec.md)，进度见 [plan](docs/plan.md)。
使用与交付材料：[用户手册](docs/user-guide.md)、[数据schema](docs/data-schema.md)、
[模型资产清单](docs/model-bundle.md)、[演示脚本](docs/demo-script.md)、
[Release acceptance](docs/release-acceptance.md)、[复现与离线交付包](docs/reproducibility-package.md)、
[论文整合稿](docs/thesis-integration.md)。
当前中文closeout和Final claims ledger仅保存在本地ignored的`private/reports/`；
2026-08-31两份报告是历史快照，不随代码上传。

## 来源接口

[Stack Exchange advanced search](https://api.stackexchange.com/docs/advanced-search)、
[answers on questions](https://api.stackexchange.com/docs/answers-on-questions)、
[comments on posts](https://api.stackexchange.com/docs/comments-on-posts)、
[custom filters](https://api.stackexchange.com/docs/create-filter)。
每条在线来源保留其 permalink、署名与 content license；本站不重新发布论坛原文。
官方 [API 署名要求](https://stackoverflow.com/legal/api-terms-of-use)、
[内容许可](https://stackoverflow.com/help/licensing) 和
[压缩响应合同](https://api.stackexchange.com/docs/compression) 已核查。
Decoder的压缩兼容已补齐。同3条评论的字段对照复现了
[上游报告](https://meta.stackexchange.com/questions/247899/creating-an-api-filter-with-comment-body-markdown-but-without-comment-body)
所述依赖：旧filter不返回Markdown，额外请求comment.body后3/3返回。
新filter固定为 `nFzTOPGAOEckIq4PwsL9Jd`，模型仍只使用body_markdown。
评论的公开source_url使用问题页锚点；recorded_source_url保留原封存地址，私有快照不改写。
链接字段全覆盖不等于匿名HTTP可访问保证，Stack Overflow可能限制匿名网页请求。
