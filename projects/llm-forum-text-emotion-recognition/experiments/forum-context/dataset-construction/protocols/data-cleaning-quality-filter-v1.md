# DATA-FCTX-CLEAN-V1: IAC 2.0 文本清洗与质量过滤协议

- Date frozen: 2026-08-05
- Status: invalidated before independent verification
- Superseded by: `DATA-FCTX-CLEAN-V2`
- Source: IAC 2.0 `4forums_no_parse_2016_05_18.sql.gz`
- Stage: dataset construction, before annotation and split assignment
- External services: forbidden
- Public raw or derived text: forbidden

## Invalidation note

V1 错把 `quote.text_offset` 解释为嵌在 `post.text_id` 正文中的引用 span 起点，并尝试
用引用文本长度做子串验证。全量预检只有 48/539,658 条记录通过该假设。进一步结构
审计确认：IAC 把帖子自身正文和 quote 文本存为不同 `text_id`，`text_offset` 是把
quote 对象插入所属帖子或父 quote 的位置。所有 537,778 条顶层 offset 都位于帖子
自身文本范围内，1,880 条嵌套 offset 也都位于父 quote 文本范围内。

因此 V1 私有数据库和聚合报告不得用于抽样、标注或论文结论；它们仅作为失败证据
保留。V2 改用 schema-correct 的层级引用重建。

## 1. Purpose

把 IAC 2.0 4forums 中具有直接父回复关系的帖子转为可审计的
`parent -> target` 候选对。本阶段只回答三件事：哪些关系可解析、文本经过了什么确定性
处理、哪些样本存在质量风险。它不标注情绪，不确定训练集划分，也不进行模型筛选。

成功条件：

1. 每个候选都能追溯到私有源记录，但公开产物不含原文、源 ID 或可逆映射。
2. 每条排除都有 reason code，每个保留但可疑的样本都有 soft flag；不静默删除。
3. 引用删除只使用 `quote` 表中经原文精确验证的 offset，不用正则猜测引用。
4. 全量结果通过独立脚本复算，数据库 `integrity_check` 为 `ok`。

## 2. Input and candidate unit

输入只读取以下表和字段：

- `discussion`: `discussion_id`, `title`；不读取 URL 和发帖人。
- `post`: `discussion_id`, `post_id`, `creation_date`, `parent_post_id`,
  `parent_missing`, `text_id`；不读取 `author_id`。
- `quote`: 引用位置、引用文本 ID、来源帖子位置及截断/改写标志。
- `text`: `text_id`, `longtext`。

候选全集是所有声明了非空 `parent_post_id` 的 target 帖子。根帖子不属于候选全集。
父帖不存在或 `parent_missing=1` 的记录仍进入私有候选表，但标记为 hard exclusion，
以保留完整审计账目。

## 3. Three text representations

私有库保留三种不同职责的文本表示：

1. `raw_bytes`: MySQL dump 中解码后的原始字段字节，只用于追溯，不作为公开产物。
2. `model_full` / `model_body`: 最小规范化文本。前者保留已验证引用并加边界标记，
   后者把已验证引用替换成 `[[QUOTE]]`，用于避免模型把被引用者情绪当成当前说话者。
3. `dedup_body`: 仅用于精确去重的规范化 key，不作为模型输入。

`model_*` 的确定性处理顺序：UTF-8 解码并记录 replacement、Unicode NFC、HTML entity
解码、可识别 HTML 标签转为可见文本、控制字符与空白规范化，然后掩码 URL、email、
IP 和 `@mention`。以下信号必须保留：大小写、标点、重复字符、拼写、俚语、脏话、
否定和反讽线索。不得做 stopword removal、stemming、lemmatization 或拼写纠正。

`dedup_body` 在 `model_body` 基础上使用 Unicode NFKC、casefold 和空白折叠；不删除
标点，不回写模型输入。

## 4. Quote validation

每条 quote 用 `text_offset` 和引用 `text_id` 的解码字符长度定位。只有当目标帖对应
子串与引用文本的 SHA-256 完全一致时，状态才是 `exact`，并允许插入引用边界或从
`model_body` 替换。重叠的 exact spans 合并后处理。

其他状态包括：`missing_offset`、`missing_quote_text`、`out_of_bounds`、`mismatch`。
这些情况均不删除疑似引用内容，只添加 `quote_span_unverified` soft flag。HTML
`blockquote` 也不能代替结构化 offset 证据。

## 5. Hard exclusions

Hard exclusion 只用于无法形成有效上下文样本的情况：

- `parent_unresolved`
- `{target,parent}_missing_text`
- `{target,parent}_empty`
- `{target,parent}_placeholder`
- `{target,parent}_quote_only`

Placeholder 仅匹配规范化后的明确占位内容，如 `[deleted]`、`[removed]`、`deleted`、
`removed`、`n/a` 和 `none`。短句、纯标点、URL-only 和低 Latin 比例文本不作 hard
exclusion，避免删除诸如 “No.”、“Why?!”、“Exactly!” 这样的有效情绪表达。

`eligible = 1` 当且仅当 hard reason 列表为空。

## 6. Soft flags

每个帖子按确定性规则记录：

- `short`: ASCII word token 少于 3。
- `long`: ASCII word token 多于 512。
- `quote_heavy`: exact 引用字符占原文非空字符至少 50%。
- `url_only`: 除 URL marker 和标点空白外没有其他内容。
- `html_present`, `decode_replacement`, `low_latin_ratio`, `all_caps`。
- `repeated_character`, `possible_signature`, `no_lexical_tokens`。
- `quote_span_unverified`, `html_quote_unverified`。

候选表中的 flag 加 `target_` 或 `parent_` 前缀。创建时间早于父帖时另记
`timestamp_nonmonotonic`。Soft flags 不改变 `eligible`。

## 7. Exact duplication

V1 只登记精确重复，不执行自动删除：

- target duplicate key: target `dedup_body` 的 SHA-256。
- pair duplicate key: parent 与 target 两个 dedup hash 的有序组合。
- context variant: 同一 target key 对应多个不同 parent key。

重复统计只基于 eligible candidates。所有成员继续保留，供后续按 thread 分组抽样和
划分。MinHash、embedding 或编辑距离近重复检测留给单独协议，避免在清洗阶段引入
未经审查的语义删除。

## 8. De-identification and storage

`thread_uid`、`post_uid` 和 `sample_uid` 使用本机随机 32-byte key 的 HMAC-SHA256
生成。key 权限为 `0600`，只保存在 gitignored 私有目录。公开 JSON 不得包含：

- 帖子、讨论或用户源 ID；
- 原文、标题、清洗文本或片段；
- per-sample HMAC ID；
- dedup/body/pair hash；
- 本机绝对路径。

私有 SQLite 可保留源 ID、原始字段和模型文本，用于本地标注与审计。不得读取或保存
`author` 表，不得保留讨论 URL。

## 9. Outputs and verification

Private, gitignored:

- `data/iac2/derived-private/dataset-construction/cleaning-v1.sqlite`
- `data/iac2/derived-private/dataset-construction/id-key.bin`

Trackable, aggregate only:

- `dataset-construction/reports/cleaning-preflight-v1.json`
- `dataset-construction/reports/cleaning-verification-v1.json`
- `data/iac2/manifests/cleaning-v1.json`

独立验证器必须复算 source/artifact hash、候选总数、eligible/excluded、hard reasons、
soft flags、引用状态、长度分位数和精确重复统计，并检查私有路径受到 `.gitignore`
保护。任何不一致都使状态为 `failed`。

## 10. Out of scope and change control

本协议不决定 emotion ontology、人工/LLM 标注流程、样本量、topic 平衡、近重复阈值、
thread-disjoint split 或训练模型。改变 hard exclusion、引用识别逻辑、去重 key 或隐私
边界时必须建立 V2；只修复不会改变样本语义的实现错误时，追加 correction note 并
重新生成全部聚合报告。
