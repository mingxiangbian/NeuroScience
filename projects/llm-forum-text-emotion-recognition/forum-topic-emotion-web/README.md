# 话题情绪工作台

Phase C 本地实现。上传 CSV / JSON / JSONL，或按标签与时间窗口采样 Stack Overflow，
查看六标签预测、内容来源、UTC 趋势与路由成本。已增加审核后的 Python Help Discourse adapter；
原 Phase A/B 实验保持不变。

当前交付：**Stack Overflow 来源闭环已通过 EXP-076 有限验收**。
原窗口内46个问题、46条回答、248条评论，共340条，M1推理340/340完成；独立验证22/22 Passed。
四个真实小批任务、32条预测的统计与新进程重放仍复用原结果，没有重复执行。
当前212/212合成与集成测试通过；两权重、日周、类型/路由分层、诊断、CSV和全文清除已补齐。
已有5个成功任务、372条结果的新视图与CSV只读QA Passed，原记录不改。前两次来源失败保留。
**EXP-077 Soak因critical memory pressure在40.22秒时停止：1/36计划任务完成。**
独立审计Passed，但exp077_complete=false、soak_gate_passed=false；不自动重试。
Discourse审核和实现完成，EXP-078正式任务因安全前提未满足而未执行。
功能和文档已交付，不代表完整Phase C、稳定运行或模型外部泛化已完成。
详细通过项、失败和下一步见 [验收记录](docs/acceptance.md)。

目前开发范围不含 CancerEmo、JIRA 等外部金标泛化，不含 context/C2。
Discourse只允许已审核的discuss.python.org / Python Help（category7），其他站点拒绝。
本轮停止新增模型任务，仅查看已有结果；不能绕过stop-required继续Research或正式采样。

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
不消耗调用次数。缓存仅在本任务子进程内使用；重放快照是新任务、新进程、新缓存。
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
[`EXP-078`](../experiments/stack-overflow-emotion-gold/protocols/exp-078-discourse-operational.md)。
合成测试通过不等于真实模型运行通过；通过的真实结果见本地 ignored
`private/validation/exp-076/attempt-3/verification.json`。原smoke与两次失败分别保留在attempt-1/2。
数值验收绑定的源码归档为attempt-3/verified-code.tar.gz；其后仅修正公开评论链接，
另有presentation-verification.json确认248个链接映射及私有数据不变。
有限验收不构成长期可用率、生产 SLA 或外部泛化证据。

详细合同见 [spec](docs/spec.md)，进度见 [plan](docs/plan.md)。
使用与交付材料：[用户手册](docs/user-guide.md)、[数据schema](docs/data-schema.md)、
[模型资产清单](docs/model-bundle.md)、[演示脚本](docs/demo-script.md)。
中文系统报告和Final claims ledger仅保存在本地ignored的`private/reports/`，不随代码上传。

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
