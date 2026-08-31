# Phase C 本地实现验收记录

Date：2026-08-30；更新：2026-08-31。EXP-076/077/078，RQ-S3。

## 结论

文件上传、冻结 M1 / Research / Demo 模式和本机结果工作台可运行。
**EXP-076 有限来源闭环已通过：第三次source完成340条采样与M1推理，独立验证22/22 Passed。**
前两次失败保留。最新代码212/212测试通过；新增统计与导出在5任务372条结果上只读核对通过。
EXP-077已触发critical pressure安全停止，独立审计Passed但Soak未通过；EXP-078正式运行阻塞。
本记录不是完整Phase C完成、外部泛化、长期稳定性或 Phase A 部署效率通过证据。

## 已完成检查

- 模块 tests：95/95 Passed，包含假后端、HTTP/DB 集成、真实合成子进程的取消/最终失败门。
- 仓库 `node tests/projects-requirements.mjs`、JS syntax、`pip check`、diff whitespace 检查通过。
- 本机浏览器：登录、上传/在线采样表单切换、Research/Demo 模式说明与预算、任务查看、
  标签筛选、错误状态、纯文本 HTML 字符串、桌面布局。390px 时 DOM 宽度等于内容宽度。
- Private 目录 0700，token/SQLite 0600；private 和独立 .venv 均被 Git ignore。

## 真实模型小批

8 条自编英文输入，无 gold。包含 7 个精确输入组，其中一对文本重复但 occurrence 不同。
另有归一化重复变体、HTML 字符串与缺日期项。没有读取历史数据 split 或训练。

| 任务 | 成功条数 | M1 实际计算 / 缓存命中 | M3 实际计算 / 缓存命中 | 降级条数 |
| --- | ---: | ---: | ---: | ---: |
| M1 only | 8/8 | 7 / 1 | 0 / 0 | 0 |
| Research | 8/8 | 7 / 1 | 3 / 1 | 0 |
| Demo，M3 budget=0 | 8/8 | 7 / 1 | 0 / 0 | 4 |
| Research 新进程快照重放 | 8/8 | 7 / 1 | 3 / 1 | 0 |

四任务总 wall time 46.26 秒。最大报告 RSS 为 4,086,579,200 bytes，MLX peak 为
8,347,038,272 bytes，均低于本次上限。这是很短的有限工作负载，不是内存 plateau/soak。
模型子进程均通过最终身份/资源检查并退出 0；模型输入、各自阈值与 router 未修改。

只读复算使用独立 `verify_local.py` 的 record/hash/统计函数，没有调用 producer aggregate，
覆盖四个已完成 jobs 的 snapshot、fixture、六标签计数、分母、neutral 和 component cache
成本。Research 重放逐条输入及预测相同，M1/M3 概率最大差异均为 0（门为 1e-6）。
这是 **smoke-only 检查**，不是整体 EXP-076 verification，也不是独立 backend 数值 parity。

本地工件位于 `private/validation/exp-076/attempt-1/`：`smoke.json`、
`smoke/run.json`、`smoke-stdout.log`、`smoke-only-check.json`。

## 未通过：Stack Overflow 实采

固定 `python`、UTC `[2026-08-23, 2026-08-30)`，上限 100 questions / 500 records。
Job `83dd3569136d42f1abedcfba135c0bd3` 在 fetching 阶段于约 4.03 秒停止，
`error_code=worker_failed`，manifest=null、sealed records=0；没有进入该任务的模型推理。
这不证明论坛没有内容，也不证明响应正文未曾抵达进程。

保留 `source.json`、`source/run.json`、`source-stdout.log` 和失败数据库 job。
完整 `verify_local.py` CLI 因前置 source Failed 而未执行；不存在整体 Passed verification。
未自动重复采样，未通过修改日期或挑选话题规避失败。

只读排查确认：网站 Python 可以正常读取官方 filter metadata；同参数 pagesize=0
返回 HTTP 200、has_more=true、无 API 参数错误；实际 `_get_json` 读取 filter 也成功。
这些检查不能排除原请求的瞬时连接问题或内容解析问题。原异常被归并成通用错误码，
目前证据不足以确定根因。

额外发现一个已合成复现的缺陷：decoder 只在 Content-Encoding=gzip 时解压，未覆盖
无 header gzip 与 deflate；[官方响应合同](https://api.stackexchange.com/docs/compression)
要求处理这些情形。这个缺陷与原失败的因果关系尚未建立，未在本次失败后改写代码。

## 后续边界

优先补采集安全错误留痕与压缩分支，再进行有界来源复测。不要重做已完成 Phase A/B，
不要把数据接入修复包装为新模型方法。后续还包括真实采样展示、Runtime Soak V2、
审核后的 Discourse、完整统计切换与最终答辩材料。
CancerEmo / JIRA / 其他外部 gold 按用户要求暂停，context/C2 也保持暂停。
当前没有 stage、commit、push、公开部署或外部数据上传。

## 2026-08-31：采集修复与 source attempt 2

用户“下一步”后，仅修改新网站的 collector、worker、验收入口及相关测试。原版本先归档，
38 个旧 smoke/source 源码哈希均匹配；旧成功/失败结果不变。模型 bridge、core 统计函数
和8条 authored fixture 的字节与继承版本一致。未修改 Phase A/B。

修复内容：gzip 有/无 header、zlib/raw deflate、代理明文、gzip多member；wire/expanded
各2MiB限制仍在。错误留痕只含白名单错误类别、HTTP状态、阶段、请求/字节计数、响应hash，
以及最多4个安全栈帧的文件/函数/行号；不保存异常原文、正文、query、token或locals。
回归测试 **112/112 Passed**，其中 adapter 26 项、backend 34 项。

唯一一次新 job 使用相同标签、UTC窗口和100/500上限，结果如下：

| 字段 | 观察结果 |
| --- | --- |
| Job | `3467697c6e954893a59d0c1e17fbaf2a` |
| Status | Failed |
| Error | `source_body_markdown_missing` |
| 失败阶段 | fetch → comments/page1 → record |
| API 请求数 | 3 |
| 最后响应 | HTTP200，gzip，4,229 wire bytes，返回100个对象，has_more=true |
| 失败前内存中解析记录 | 92条问题/回答，未封存 |
| sealed rows / predictions | 0 / 0 |
| Elapsed | 4.05秒 |

这次响应已成功解压并解析 JSON，随后评论原生 Markdown 字段检查失败。因此本次直接阻塞
可以定位为评论字段缺失，不是模型 forward 失败。不能由此反推首次失败具有完全相同原因。
只读核对 source.json 与数据库 job/progress 一致，源码与继承工件 hash 未变。
没有运行模型、完整 verifier 或第三次采样；旧四个 smoke jobs 没有重复执行。

Source terminal：`private/validation/exp-076/attempt-2/source.json`，SHA256
`205778bf617dac7712010de0367ea544829c4a438bc518bd6f1d94b8a6083a37`。
同目录保留 `source/run.json`、`source-stdout.log`、继承代码及协议；没有整体 Passed verification。

### 下一步候选修正与证据限制

[官方 comment 类型](https://api.stackexchange.com/docs/types/comment) 列出 body_markdown。
但 [2015年上游缺陷报告](https://meta.stackexchange.com/questions/247899/creating-an-api-filter-with-comment-body-markdown-but-without-comment-body)
及 [Stack Apps复现记录](https://stackapps.com/questions/4975/filter-doesnt-consistently-return-comment-bodies)
报告：仅请求 comment.body_markdown 可能不返回它；同时请求 comment.body 后可返回两者。
当前filter只额外选择Markdown字段，本次症状与该报告相符。这是有依据的候选解释，
不是已完成当前接口A/B验证的结论。

下一步保持模型输入不变，只在API filter额外请求 comment.body，并先做少量评论字段存在性
确认；HTML字段不送入模型、不作清洗回填。确认后再登记一次有界来源复测，保留两次失败。
无需重跑 Phase A/B、四个成功smoke，或引入外部gold泛化。

## 2026-08-31：字段依赖确认、source attempt 3 与完整有限验收

### 字段问题已在小规模对照中复现

固定三条评论，旧filter与新filter请求的comment ID、parent post和creation time对齐。
新filter只多选一个字段comment.body；旧filter的3条均缺Markdown，新filter的3条均返回
非空body及body_markdown。仅保存字段存在性、hash与字节数，没有保存正文、调用模型或访问gold。
共5次API请求、3.26秒。它支持这组字段兼容修正，不保证任意未来接口或缓存状态。

新filter：`nFzTOPGAOEckIq4PwsL9Jd`；field-probe SHA256：
`dfe0438fe73f2db5e220aa88359b42e5d620e01f5757220757c8c8a0186e92d7`。
模型仍只使用原生body_markdown，未采用HTML清洗或回填。新增毒性HTML合成测试明确检查这一点。

### 真实Python话题闭环

同原标签与UTC `[2026-08-23,2026-08-30)`，原100 questions / 500 records上限不变。

| 项目 | 已验证结果 |
| --- | ---: |
| 问题 / 回答 / 评论 | 46 / 46 / 248 |
| 总条数 / 成功预测 | 340 / 340 |
| API请求数 | 5 |
| 精确输入组 / M1缓存命中 | 338 / 2 |
| M1实际计算 / M3实际计算 | 338 / 0 |
| 缺失预测 / 降级 | 0 / 0 |
| Source job耗时 | 32.77秒 |
| 验收入口总耗时 | 34.16秒 |
| 最大报告RSS | 803,782,656 bytes |

Job `5ab3326150ee448ba326233264967d34` 已完成，sampling_complete=true，stop_reason=complete。
“完整”仅指所定义的Question Cohort及同窗口子内容，不是Stack Overflow全部Python讨论。
本次真实话题使用M1 only；完整Router/M3的既有小批证据来自原四个smoke，不混成新话题路由结果。

独立consumer复算包括源码/协议/失败继承、记录和输入hash、340条源文本与parent/time对齐、
标签统计/分母/neutral、缓存成本与原Research重放，共22/22 Passed，exp076_verified=true。
旧smoke只重读已保存结果，没有重跑推理；M1/M3原重放概率差仍为0。
本机网页显示340/340及338/2计算/缓存；340个源链接字段齐全。390px无横向溢出，
source preview未创建script节点，页面无控制台错误。

工件均在 `private/validation/exp-076/attempt-3/`：

- `source.json`：`3779713265e507787678e471320834e13f09f9a2a1a8683c69b03603eec9e272`。
- `verification.json`：`7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8`。
- 私有快照hash：`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
- 数值验收代码 `verified-code.tar.gz`：`09d4c2b771edb1920767fc61924a35777fa2c99919d199e4f0ae1225cab891e3`，21项源码hash与source记录匹配。

### 数值验收后的评论链接展示修正

原独立验收检查了source_url字段及构造规则，没有逐条做HTTP可达性检查。后续HEAD抽检发现
原评论 `/posts/{post_id}` 路径返回404。问题/回答短链能跳转到正确问题页，但匿名最终请求为403。
因此“链接字段100%覆盖”不应解释成“匿名HTTP100%可访问”。

只修公开projection：评论改用 `/questions/{thread_id}#comment{comment_id}_{parent_id}`，
原地址留为recorded_source_url。SQLite中的record、source snapshot、model input和预测都不改。
API和默认导出使用同一修正；不改变future/old模型行为，也不重跑source或数值verifier。
源码验收阶段134tests通过，展示修正新增13项回归后为147/147。
只读实际API核对了340条record/input hash与全部248条评论的URL映射，前后私有快照hash相同；
结果见 `presentation-verification.json`。它与已封存数值验收分开，不覆盖原verification.json。

当前结论：本机有限工作负载的采样、推理、统计和展示闭环可用。尚不支持长期Soak/SLA、
外域准确率或整体Phase C已完成。下一步仍是Runtime Soak V2，然后审核后的Discourse与系统收口。
本轮没有训练、validation/test、外部gold、stage/commit/push或公共部署。

## 2026-08-31：完整界面、Soak负结果与第二站点安全阻塞

本节替代上节的“下一步”状态。新增两种统计权重、UTC日/周、六标签构成、对象类型与实际
route_requested分层、cardinality/熵/阈值距/截断诊断、无全文CSV和单job全文清除。
原aggregate四参输出不变，旧任务只读补算，新成功任务保存derived直到90天聚合期。
全部212/212tests、JS syntax、pip依赖一致性与仓库要求检查通过。

功能故障覆盖包括：边界/Unicode/重复上传、来源压缩与分页/限流、取消与晚写、子进程继承锁、
最终退出失败、Research禁止回退、Demo预算和普通故障回退、非法值/资源/身份漂移硬停。
CSV公式前缀防护、未知计数留空、明细过期410和清除全文后replay拒绝均有合成测试。
这些是实现级证据，不假称已在真实设备上制造OOM、崩溃或攻击。

现有5个成功任务、372条结果通过独立derived复算与API/CSV对照：两权重、日周、类型/路由分层、
known_n、CSV行数、输入hash和公开URL一致；前后逻辑记录hash不变，没有新模型或来源采集。
本地工件 `private/validation/phase-c-views-qa.json`，复核脚本为同级`check_phase_c_views.py`。
浏览器已核对340条来源任务的默认/Unique-text、出现率/构成、日/周、类型分层与成本不变；
全文清除确认框可取消，本次没有清除任何正式记录。
本轮桌面1280px检查无页面横向溢出；早期MVP的390px检查不冒充新增分层视图的手机实机认证。

### EXP-077：运行停止与审核Passed必须分开

冻结协议为[EXP-077](../../experiments/stack-overflow-emotion-gold/protocols/exp-077-runtime-soak-v2.md)。
计划12轮三模式、36job、15,120事件。实际UTC02:35:03.764811至02:35:43.987598，40.221628秒：

- 第1个M1-only job `6c1f57fde85d4da2a5d322039fdd4d0c`完成420/420，338实际计算、82缓存命中。
  measured为322计算+18缓存；cache tail为0计算+64缓存。该job child plateau=1.037315≤1.05。
- 第2个Research job `a510bc76034e43dc97a5bbfdc7872485`已封存420输入，在0条结果回执时取消。
  其实际模型尝试、加载进度和峰值未知，不能记为0。其余34个job没有提交。
- 40系统样本中2个critical，间隔约22.7ms，不等于持续2秒；unknown和非法间隔均0。
  swap增量819,593,216B；最大376,159,627.826B/s；连续高阈值间隔最长2，未达到3的thrashing定义。
  本次停止原因是critical_memory_pressure；全机观测不足以单独归因M3、认定OOM或内存泄漏。
- run.status=Stopped，cancellation_status=terminal_confirmed，unhandled_errors=0。
  完整任务仅1/36，不能把这个计划执行比例当作生产服务成功率。

Independent verification为Passed，说明已有输入/回执/成本/采样和终态复核一致；
`exp077_complete=false`、`soak_gate_passed=false`、`operational_state=stop-required`。
整体within/cross-job门未建立；首个M1自身plateau通过不等于连续负载通过。
按协议分类为Runtime unstable on this workload，功能证据保留，不获得稳定原型或SLA结论。

工件在`private/validation/exp-077/attempt-1/`：
verification SHA=`339bd2da52e3bffa0cfe796239ecd857f80becead5f2b829c5cf3a3b03d61f13`；
run SHA=`69c7e18f1dd2664cdef170d9e899a7dd57b6748bbb902af222ad8e4613ddd81e`；
plan SHA=`94df1665d0eebc042820d4b199340f344263898edcc30e922777853d0eadb05c`。
隔离服务和模型子进程已停止，6项绑定工件在停服后hash仍一致。未重试、改门或覆盖结果。

### EXP-078与交付边界

审核站点为discuss.python.org / Python Help category7；原生raw、访问与非商业许可检查见
[来源审核](discourse-source-review.md)。adapter、固定分类入口、runner和独立consumer已完成并测试。
但EXP-077不满足safe-to-continue，故**EXP-078正式300–400条采样与Research任务未执行**。
不存在本次Discourse正式结果，不能把审核/代码完成写成跨平台运行验收通过。

用户手册、schema、模型清单、演示脚本已完成。中文系统报告和Final claims ledger位于
`private/reports/`，两者Git-ignored。报告明确保留稳定性失败和第二站点阻塞。
当前只查看已有任务，不再自动执行模型。外部gold、旧context/C2仍暂停；没有训练、
validation/test访问、stage/commit/push、外部上传或公开部署。
