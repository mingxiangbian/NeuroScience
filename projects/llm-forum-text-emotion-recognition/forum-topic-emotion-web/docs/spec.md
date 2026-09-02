# Phase C 本地系统合同

Date：2026-08-31。只处理用户要求的系统部分，外部金标泛化暂停。

## 最小结构

浏览器 → loopback FastAPI → SQLite sealed snapshot → 单 dispatcher → 单模型子进程。
模型子进程复用冻结 runtime 算法与资产，不在 HTTP 请求进程中加载模型。
没有账户系统、分布式队列、远程模型 API 或公共部署。

`core.py` 管合同与描述统计；`adapters.py` 管来源；`store.py` 管持久化；
`worker.py` 管进程生命周期；`inference_process.py` 连接冻结运行时；
`app.py` 与 `static/` 提供本机 UI。

## 生命周期与身份

状态按 queued → fetching（上传可跳过）→ snapshot_sealed → inferencing → aggregating
→ completed / completed_with_fallback。异常保留 failed；取消经 cancel_requested → cancelled。
删除先标 deleting、拒绝读取和写入，精确子进程退出后清除。不使用运行中原地改写 snapshot。
重放从已封存原输入复制新任务；原记录未过全文保留期才可重放。

record identity = SHA-256(source, site, object_type, source_object_id) 的 canonical tuple。
上传 identity 用文件 SHA-256 + 行序号，不依赖不一定唯一的用户 id。
`source_payload_raw`、`model_input_text`、`display_text` 分离，展示层不改变模型输入。
所有趋势用来源 creation UTC；采集时间不冒充发布时间；source query 时间为 `[start,end)`。

模型资产 hash/mode/环境绑定 EXP-066 attempt-2，cache key 包含 bridge/source fingerprint
和精确输入 hash。M1/M3 cache 分开，降级不进入 M3 cache。每个新任务使用空缓存。
固定分类头、阈值、14 维 router features 与 router cutoff 不根据在线输入重调。

## 统计

每个 label 的 prevalence = 预测为该标签的 occurrence / 成功预测 occurrence。
positive share = 该 label 激活次数 / 六标签总激活次数；分母为零时 null，不伪造 0。
同时保留 eligible/success/missing/coverage，区分 object type、精确重复组与归一化重复组。
无日期不入趋势。M1 entropy 在同一模型尺度统计，不混合 M1/M3 数值。
route_requested、实际 attempts、succeeded、cache_hit、final path、fallback 独立记录。
失败进程能返回累计成本时采用该累计；被强制终止且无回执时只能显示已知下界。

网页提供 object-weighted 与 normalized unique-text 两个统计视图。前者每条来源对象权重为1；
后者按 NFKC、casefold、空白归一化后的文本分组，每组总权重为1，组内成功预测平均分配该权重。
后者是重复敏感性视图，不删除来源对象，不以标签取 OR，也不改变模型输入或实际计算成本。
同组若因Demo预算出现不同预测，保留平均权重结果；因此标签计数可以是小数。

日/周趋势以来源 creation UTC 分桶，周一为周起点。unique-text 在各时间桶内独立分组，
同一文本跨桶出现会在每桶计一次；不能把桶内去重数相加当作全任务唯一数。没有观测的日期
不补零，部分时间桶也不代表完整自然日/周。六标签均展示，可切换 prevalence 与 positive share。

对象类型和route_requested的true/false/unknown分层使用相同视图公式，各层独立分组、计算分母。
跨层unique数也不能相加当作全局unique数；路由分组取决于模型，不是随机对照。

derived v1 保存两种权重视图、日周趋势、标签基数及不确定性/截断/路由诊断。新完成任务将
derived 与基础聚合一起保存，随聚合保留90天。已有任务尚有逐条数据时可在读取时复算，
不回写旧任务；逐条数据已到期且没有保存 derived 的旧任务明确标记 unavailable。

诊断的 known_n 单独披露。截断率只在有相关token信息的预测上计算；没有运行M3不等于M3
输入未截断。M1 entropy/margin 是冻结路由信号的描述统计，不是校准后的正确率。

## 第二来源与验证范围

Discourse live 仅允许已审核的 discuss.python.org / Python Help（category 7）。选择最新创建的
公开非置顶话题前缀，按话题内post_number升序读原生 raw。它不是固定时间窗，也不是完整论坛
事件流。缺少原生raw时停止；不从cooked HTML生成输入。系统、隐藏/删除、非普通帖子排除，
不可访问stream IDs与因预算截断的topic IDs均显式记录。许可和采样限制见
[站点审核](discourse-source-review.md)。

EXP-076验证Stack Overflow有限来源闭环与既有smoke；EXP-077验证隔离服务上的固定连续负载；
EXP-078验证第二站点的无标签Research流程。三者都不生成accuracy/F1，不证明跨域模型质量。
EXP-077与EXP-078的最终状态只以独立verification和验收记录为准，代码实现完成不等于实测通过。

## 安全与限制

API 默认令牌 cookie（HttpOnly、SameSite Strict）或 Bearer，Origin/Host/client address
校验，无跨站 CORS；CSP 禁止 inline script，source text 只用 textContent 渲染。
外部采集 host allowlist，HTTPS、禁重定向、受限请求/响应/时长。Discourse其他未审核站点拒绝。
private 0700，文件 0600，Git ignored，运行日志不得含原文/令牌。

元数据JSON导出和逐条CSV导出都受同一鉴权保护。CSV只输出白名单来源/身份/预测/成本字段，
不含原文或预览，对可能成为电子表格公式的字符串做安全前缀处理，不改变数据库保存值。
单任务全文清除只接受终态，移除raw、模型输入、预览与request内潜在全文，保留metadata、预测、
aggregate及原snapshot hash作为历史标识；raw_expired=true后拒绝重放。运行中任务须先取消或等待，
不允许清除正被推理的输入。删除整个任务与仅清除全文是两个有确认提示的操作。

资源上限与真实验收以 EXP-076 为准。UI 表示的是采样内容模型预测，不能推出作者的真实
心理状态、全论坛总体或跨域识别质量；不上线个人情绪评分或高影响决策。
