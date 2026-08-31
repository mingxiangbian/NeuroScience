# EXP-076：Phase C 本地话题工作台实现验收

- Date：2026-08-30
- Tier：Minor，归属 RQ-S3 的系统实现；不单独支撑模型效果或部署效率结论。
- Status：真实运行前登记。
- 用户范围：暂不执行 CancerEmo、JIRA 或任何其他外部金标泛化；完成其余系统工作。

## 固定边界

复用 EXP-066 attempt-2 通过验证的 seed-42 模型、分类头、prompt、tokenizer、阈值与
router。只新增网站、采样与数据存储边界。原 Phase A/B config、代码、terminal 不改动。
不训练、不读取历史 train/validation/test 原文或标签、不访问外部 gold，不发布或上传数据。
本轮不宣称修复 EXP-067/068 的部署效率证据缺口。

实现位于 `../../../forum-topic-emotion-web/`（相对本协议目录）。HTTP 服务只监听
127.0.0.1:8787，令牌鉴权，模型在单个隔离子进程中运行；网站依赖在新 `.venv`，冻结
`phase-a-runtime` 环境不变。模型资产、冻结 source 与环境在加载前核验，运行中及退出前检查。

## 工作负载与先后顺序

1. 合成测试：适配器、精确输入缓存、计数、模式、任务取消/删除、重启、最终子进程退出门。
   假模型故障注入只验证控制流程，不作为真实模型稳定性证据。
2. 真实模型小批验收：`tests/fixtures/operational.jsonl` 的 8 条新编写英文输入，无 gold。
   固定包含一对完全重复文本、一条大小写/空白变体、一条 HTML 字符串与一条无日期记录。
   文件 SHA-256：`f7c8b88a658f42f8d5d3435383496c96dbc1fe2414bf4923c19dc5549953603f`。
   依次运行 M1 only、Research、Demo（M3 budget=0）、Research fresh-process snapshot replay。
   每条输入模型原文不归一化；相同文本的不同 occurrence 保留。
3. 只有上一步通过，执行真实 Stack Overflow `python` 标签、UTC
   `[2026-08-23T00:00:00Z, 2026-08-30T00:00:00Z)` Question Cohort，creation 升序，
   最多 100 questions / 500 records，包含同窗口内问题、回答、评论；M1 only。
   官方 API 自定义 Markdown filter 固定为 `nFzTOPGAOEckIq4Pwr_RZ8`，不把 HTML 重建成模型输入。
4. 浏览器检查：鉴权、新建/筛选/来源链接、纯文本呈现、进度与错误状态、桌面及窄屏布局。
   删除/取消的控制流用独立临时数据库与假子进程验证，不删除本次正式验收工件。
5. 独立检查只读已封存 jobs/records/results，复算覆盖率、六标签计数、neutral、缓存次数、
   路由请求与实际路径；Research replay 逐条比较预测与概率。它不是独立 backend 数值 parity。

命令：模块 `.venv/bin/python scripts/validate_local.py smoke`，通过后执行
`... scripts/validate_local.py source`。输入 SHA-256、实现/协议 SHA-256、Git commit/dirty、
命令、开始结束时间、job IDs、snapshot hashes 与 aggregate 写入 ignored
`private/validation/exp-076/attempt-1/`，各阶段另有独立 `smoke/run.json` 与 `source/run.json`。
各阶段结果 `smoke.json`、`source.json` 一次性写入，
失败停止，保留原工件。本轮最多这 5 个真实 jobs，不自动重跑失败 job。

## 判断与资源

成功条件是实际任务完成、退出码为零、最终身份/资源门通过、逐条预测和来源对齐、独立复算一致。
不是某种标签比例或某个 M3 路由数量。若这 8 条未触发 M3，明确记录覆盖不足，不挑选追加样本。
Research 的 M3 异常硬停；Demo 只有普通运行错误或预算耗尽可沿用已有 M1 结果；
身份、非有限输出与资源异常均硬停。不会将失败/缺失记录当 neutral，也不计算 accuracy/F1。

- 每任务最多 500 records，每文本 64 KiB；上传最多 5 MiB。
- 队列最多 8 个 waiting jobs；同一时刻 1 个模型子进程并持有项目 heavy lock。
- 总验收预算 5 jobs / 5,400 秒；每 job 最多 3,600 秒。Research 安全上限 500 M3 attempts，
  本次 authored 工作负载实际最多 7 次唯一输入调用/job；Demo 为 0。API cost=USD 0。
- 子进程 RSS ≤12 GiB，MLX peak ≤10 GB；任务启动磁盘 free ≥512 MiB。
- 每次 source fetch ≤30 请求、300 秒、单请求 15 秒、单响应 2 MiB；遵守 quota/backoff。
- source 或模型运行失败停止后续阶段；不得为得到通过结果修改旧运行。

仅支持“本机、该版本、该有限工作负载的实现检查”。不支持 99.5% 可用率、24 小时稳定性、
多用户 SLA、外部泛化、全论坛情绪估计，或 long-term deployment efficiency。
Discourse 未选择站点，live adapter fail-closed；context/C2 仍暂停。

## 2026-08-30：source-only attempt 2

用户以“下一步”继续采集修复及有界复测。Attempt 1 的四个 smoke jobs 已完成并做过
smoke-only 复算；source job 在 fetching 阶段 Failed，通用错误码不足以定位根因。
本次只补官方压缩合同兼容（gzip/deflate/已解压明文）与安全错误类别、阶段、响应元数据留痕。
这不是声称已经确定原失败根因，也不改变模型输入、标签、阈值、模型或 router。

原 attempt-1 的代码和协议在修改前保存在新目录 `attempt-2/`：

- `inherited-code.tar.gz` SHA256：`8e5e1fe64249ed0a42a37245b40c950f26bd5aa52cb277a96dd08746c44a79f4`。
- `inherited-protocol.md` SHA256：`5aefa0e0380b85615995669360334b2e842ba501d086a4e0f579e82e735c6d40`。
- 旧 smoke/source 的 38 项源码哈希已逐项匹配归档。旧终态、日志与数据库任务保持不变。

命令：`.venv/bin/python scripts/validate_local.py source --attempt 2`。
最多 **1 个新来源 job / 3,600 秒**，其余 100 questions、500 records、30 API requests、
300 秒 fetch、15 秒/request、2 MiB wire/expanded response、12 GiB RSS 等上限不变。
仍用原 `python` 标签与 `[2026-08-23,2026-08-30)` UTC 窗口，仍只运行 M1，不调整采样
以获取某种结果。不重复四个已通过 smoke，不执行训练、test、外部 gold 或新站点接入。

通过后运行 `.venv/bin/python scripts/verify_local.py --attempt 2`：复用旧 smoke 的四个
jobs，加入新 source job；旧源码/协议对归档核验，新 source 对当前源码/协议核验；
core、inference bridge、fixture 与继承版本必须一致。独立复算来源、快照、统计、成本与重放。
新结果只写 attempt-2；原 source Failed 不改写。任一实测失败即停，不自动第三次尝试。

## 2026-08-31：联合评论字段验证与 source-only attempt 3

用户再次“下一步”后，继续确认 comment.body 对 comment.body_markdown 返回的字段依赖。
Attempt2 已明确在 comments/page1 缺少 Markdown 时停止；两次失败和四个成功 smoke 保留。
本次唯一业务变化是 API filter 额外请求 `comment.body`，**模型仍只读取原生 body_markdown**。
HTML 字段不作为模型输入，也不进行 HTML-to-text 清洗、回填或改阈值。

### 小规模字段检查

用现有 `_get_json` 和原压缩/限流合同，最多5次API请求、120秒，不执行任何模型调用：

1. 读取旧 filter `nFzTOPGAOEckIq4Pwr_RZ8` 的字段 metadata。
2. 创建以旧 filter 为 base、仅增加 comment.body 的 unsafe filter，检查字段集合差异。
3. 取 Stack Overflow `[2026-08-23,2026-08-30)` UTC 内 creation 升序前三条评论的 IDs。
   这三条只用于 API 字段合同检查，不作为 Python 话题采样或准确率数据。
4. 先以旧 filter，再以新 filter 分别请求相同三条 comment IDs。

通过条件：ID、parent post、creation time 对齐，新 filter 三条均返回 string 类型的 body 和
body_markdown。旧 filter 的缺失数只作描述；若旧 filter 本次也返回 Markdown，则不能声称
本次对照复现了缺失依赖，但可确认新 filter 当前可返回原生 Markdown。
保留 filter metadata、字段存在性、响应hash及 Markdown hash/byte count，不保存正文或作者。
结果只写 ignored `private/validation/exp-076/attempt-3/field-probe.json`，0600、create-only。
若失败或超限即停，不换评论挑结果、不自动重试。

### 同范围来源复测与验收

字段检查通过后，才将新filter固定到collector；补合成回归，确认body字段从未被送入模型。
仅执行一个 source job，沿用原 `python` 标签、固定UTC窗口、100 questions / 500 records、
30 API requests / 300秒fetch、wire/expanded各2MiB、每job3600秒及原内存上限。仍为M1 only。
不重跑四个smoke、不训练、不访问validation/test/外部gold，也不执行Discourse或Soak V2。

原attempt2源码与协议在修改前保存在新attempt3目录：

- `previous-code.tar.gz` SHA256=`84fcd91d32649f076bd9508162caecea19bd8fda8aabecf822fc27a1fdc1b8ad`。
- `previous-protocol.md` SHA256=`da07395cf4311e1462effb3db92d1983d17e7a5f3a5af03a3bd681e05a3a349e`。
- 原source2 SHA256=`205778bf617dac7712010de0367ea544829c4a438bc518bd6f1d94b8a6083a37`，19项源码hash已对归档匹配。

命令：`scripts/probe_comment_fields.py --protocol <本协议绝对路径>` → 回归测试 →
`scripts/validate_local.py source --attempt 3` → 成功后 `scripts/verify_local.py --attempt 3`，
均使用模块 `.venv/bin/python`。新结果只写attempt3，完整验收复用旧四个smoke的已封存结果，
绑定旧归档、新代码、字段检查、新来源与两次旧失败。core、模型bridge、fixture保持原hash。
本次通过只支持有限工作负载的来源/推理/展示实现，不支持长时稳定性或模型外部泛化。
