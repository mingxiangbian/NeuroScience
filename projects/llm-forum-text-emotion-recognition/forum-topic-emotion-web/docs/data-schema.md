# Phase C 数据与统计合同

日期：2026-08-31。本文描述当前代码字段，不改写已经封存的数据库或实验产物。

数据流为 job → sealed records → per-item results → aggregate。原 `core.aggregate(records, results, manifest, mode)` 的四参输出保持原对象口径；新增视图使用 `derived.schema_version = topicweb-derived-v1`。

## Job

SQLite `jobs` 表的主键是随机任务 ID。公共 API 不返回保存的完整 request；上传内容也不会额外复制到 request 中。

| 字段 | 类型与含义 |
| --- | --- |
| `id`, `name`, `source`, `mode` | 任务 ID、显示名称、upload/stackexchange/discourse、m1_only/research/demo |
| `state` | queued、fetching、snapshot_sealed、inferencing、aggregating、completed、completed_with_fallback、failed、cancel_requested、cancelled、deleting |
| `created_at`, `updated_at` | Unix 秒；API 另给出 7/30/90 天到期时间 |
| `total_items`, `completed_items` | 已封存对象数、已收到并持久化成功预测的对象数；不是模型调用次数 |
| `snapshot_hash` | 按序完整 records 的 canonical JSON SHA-256；未封存时为 null |
| `manifest` | 采集参数、窗口或分类前缀、计数、来源版本与停止原因 |
| `dashboard` | 已封存对象聚合；默认聚合成功的新任务还包含 derived |
| `progress`, `error_code` | 安全进度与错误类别；不保存异常原文、token、响应正文或完整 traceback |
| `raw_expired`, `items_expired`, `replay_of` | 清理标志和新任务所复用的原快照 ID |

`items` 表以 `(job_id, ordinal)` 为主键，`record` 和 `result` 是 JSON 字符串。ordinal 从 0 开始；result 未完成时为 SQL NULL。结果写入要求 job 仍处于 inferencing，同一位置不重复写入。取消/删除会撤销晚到结果的写入权限。

## Record

| 字段组 | 内容 |
| --- | --- |
| 来源身份 | `source`, `site`, `object_type`, `source_object_id`, `record_id` |
| 关联与时间 | `thread_id`, `parent_object_id`, `created_at`, `updated_at`；来源日期统一为 UTC ISO 字符串或 null |
| 引用 | `source_url`, `author_display_name`, `author_id_hash`, `content_license`, `provenance` |
| 私有输入 | `source_payload_raw`, `model_input_text` |
| 展示与 hash | `display_text` 最多 280 字符；`model_input_hash` 为精确 UTF-8 SHA-256；`dedup_hash` 为规范化文本 SHA-256 |

record ID 绑定 source/site/object_type/source_object_id 的 canonical tuple。上传使用文件 hash 与行号构造身份，不因用户提供重复 id 而合并对象。

公开 items/export 视图去除完整原文、原始 payload 和 author_id_hash，仍可能含预览、署名与来源 ID，因此不是可任意公开的数据集。Stack Overflow 评论的公开 `source_url` 使用问题页锚点；`recorded_source_url` 保留原封存地址。私有 record 与 snapshot hash 不受这一展示修正影响。

规范化只用于描述分组：`NFKC → casefold → 空白压缩`。它不能用作模型输入替换，也不能用作推理缓存键。

## Result

六维向量顺序固定为 `love, joy, surprise, anger, sadness, fear`。

| 字段 | 语义 |
| --- | --- |
| `prediction` / `prediction6` | 六维 0/1 最终决策；别名保持相同 |
| `labels` / `active_labels`, `neutral` | 激活标签名与六标签均未触发标记；没有 gold |
| `used_path`, `actual_model` | 最终采用 m1 或 m3 |
| `m1_probabilities`, `m3_probabilities` | 模型分数；未取得 M3 输出时为 null，不补零 |
| `m1_prediction`, `m3_prediction` | 按各自冻结阈值产生的决策；M3 缺失时为 null |
| `route_requested`, `routed` | 当前模式实际请求 M3 的决策 |
| `route_eligible`, `hypothetical_route`, `route_score` | 冻结 router 的条件与分数；M1-only 可假设触发但不实际调用 |
| `fallback`, `fallback_reason`, `degraded` | Demo 降级及原因；Research 不允许把降级当成完整输出 |
| `counters`, `cumulative_counters` | 本条处理事件和截至该条的任务累计；缓存命中不是 forward |
| `tokenlengths`, `truncflags` | m1/m3 的 input_tokens、used_tokens、truncated；无记录时为 null |
| `threshold_margin`, `m1_entropy`, `latency_ms` | 冻结特征或运行观测，不是正确概率 |
| `resources`, `fingerprint` | 子进程资源快照与本次输入合同/bridge/父配置指纹 |

组件缓存只在一个 job 的子进程内存在，键绑定精确输入与运行指纹。相同输入的新任务会重新计算。普通 Demo M3 失败可能仍产生 M1 最终结果；该失败尝试仍属于成本。

## 原对象聚合

顶层 `summary`, `emotions`, `daily`, `object_types`, `routing`, `uncertainty`, `timing` 保留既有含义。`eligible_items` 是已封存对象总数，`successful_items` 是最终预测数，`coverage = successful / eligible`。

`emotions[*].count` 是标签激活对象数；`prevalence` 除以成功对象数，`positive_share` 除以六标签总激活数。空分母返回 null。缺失结果不计为全负预测。原 daily 只包含有日期的成功回执；新增时间桶还可显示只有缺失预测的来源日期，其比例保持 null。

## Derived v1

`GET /api/jobs/{id}/dashboard` 在明细存在时只读构建 derived；不更新旧 dashboard。默认 dispatcher 的新成功聚合会把 derived 一同写入，从而在明细清除后保留到任务第 90 天。

```text
derived
├─ schema_version: topicweb-derived-v1
├─ available: boolean
├─ weighting_contract / time_contract
├─ views
│  ├─ object_weighted
│  └─ normalized_unique_text
│     ├─ unit
│     ├─ summary
│     ├─ emotions[6]
│     ├─ strata.object_type[] / strata.route_requested[]
│     └─ trends.daily[] / trends.weekly[]
└─ diagnostics
```

两个 view 使用相同结构。`summary` 包括 eligible_units、successful_units、missing_units、coverage、eligible_occurrences、successful_occurrences、neutral_count/rate、cardinality、mixed_prediction_groups、partially_predicted_groups。

对象视图每条成功出现的权重为 1。Unique-text 的每组总权重为 1，组内每条成功出现权重为 `1 / 该组成功出现数`。该组没有成功预测时，保留 eligible unit，但不进入预测分母。组内预测不一致时平均激活值，不取代表、不做 OR；计数和 neutral_count 因而可以是小数。

例如同一组两条成功预测分别只触发 love 和 joy，该组贡献 love=0.5、joy=0.5，而不是各 1。组覆盖率表示至少一次成功的组比例，不能替代对象覆盖率。

`emotions` 仍包含 label/count/prevalence/positive_share。daily/weekly 中每个桶包含 date 与同样的 summary/emotions。日期取来源 UTC；周从周一开始；每个桶内部独立归组。同一组跨桶重复出现不会被全期预先扣除。没有日期的对象不进入桶，没有内容的桶不生成。

`strata.object_type` 按来源对象类型字符串排序；`strata.route_requested` 固定为字符串组 `false`、`true`、`unknown`，按此顺序返回，包括 n=0 的空层。只有 result.route_requested 为真正的布尔值时才进入前两层，不用 hypothetical_route 替代；无结果、缺字段或非布尔值进入 unknown。每层含 group、unit、summary、emotions，在层内重新分组并均分成功出现权重。空层比例为 null，路由分组不是随机对照，跨层唯一组数不可相加冒充全局唯一组数。

明细已清除且旧 dashboard 没有 derived 时，API 返回 `available=false`、`reason=item_retention_expired`，views/diagnostics 为 null；这与“观察到了零”不同。未到默认聚合阶段的失败/取消任务、使用自定义聚合器的任务，不保证拥有封存的 derived。

### 诊断口径

diagnostics 的 `basis=acknowledged_object_occurrences`，不随 Unique-text 切换。内容包括：

- 对象 coverage、成功/总数、undated_items。
- Cardinality 的 0–6 标签计数和分布；M1 二元熵、阈值距的 n/mean/median/p95/min/max。
- M1/M3 原输入、实际使用 token 长度分布与截断 n/count/rate。缓存命中的回执仍可有长度记录；不能将记录数当作计算次数。
- 实际请求与假设路由各自的 known_n/count/rate，最终使用 M3 数、降级数与比例。

分位数按排序后位置 `(n−1)q` 线性插值；缺少记录时 n=0，数值为 null。没有重新加载 tokenizer 或模型来补齐旧记录。

## 成本和未知调用

`routing.cost` 的字段为 m1_attempts、m3_attempts、m3_succeeded、m1_cache_hit、m3_cache_hit、audit_extra_calls。它们始终是对象/forward 口径，不使用 Unique-text 权重。

| `cost_scope` | `cost_complete` | 解释 |
| --- | --- | --- |
| `completed_job` | true | 正常完成任务的完整回执 |
| `job_cumulative` | true | 失败子进程返回有效完整累计；覆盖回执合计，不重复相加 |
| `acknowledged_items_lower_bound` | false | 运行中、取消或失败且没有有效累计；只知道成功回执所记录的下界 |

失败累计来自 `job.progress.failure_cost.cumulative_counters`；必须包含所有规定计数，均为非负整数且不低于已回执计数。强制终止可能发生在 forward 已开始、结果未返回时，所以缺失部分未知，不写成零。

`progress.source_error` 只含白名单采集元数据；`progress.worker_error` 只含阶段、受限异常类型和最多四个固定模块内的 file/function/line 栈帧。不含正文、locals、完整 traceback 或任意异常 message。

## CSV 与单任务全文清除

`GET /api/jobs/{id}/export.csv` 使用当前公开 record projection，含 ordinal、来源身份/链接/署名/许可、时间、hash、上传文件追溯字段、最终路径、实际/假设路由、降级原因、六个 prediction 字段与六种成本计数。不导出 display_text、model_input_text、source_payload_raw 或 author_id_hash。使用 UTF-8 BOM 与 CSV 引号规则；可能被电子表格解释为公式的前缀加单引号转义。空结果/缺失计数写空单元格。明细已过期返回 410，而不是一份暗示观察样本为零的 CSV。

`DELETE /api/jobs/{id}/raw` 仅接受终态任务。它删除记录中的全文/预览/payload 键，并清除 request 中可能遗留的 upload、records、content 和同类原文键，设置 raw_expired=1。元数据、result、dashboard 和原 snapshot_hash 不变，随后 replay 返回 409。排队和运行中调用返回 409；不存在的任务返回 404。此操作不清除系统备份或此前导出的副本，也不构成介质级密码学擦除。

保留期与删除行为见 [使用手册](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/docs/user-guide.md)。
