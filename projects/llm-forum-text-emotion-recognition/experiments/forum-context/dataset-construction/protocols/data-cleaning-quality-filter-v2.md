# DATA-FCTX-CLEAN-V2: IAC 2.0 文本清洗与质量过滤协议

- Date frozen: 2026-08-05
- Source: IAC 2.0 `4forums_no_parse_2016_05_18.sql.gz`
- Stage: dataset construction, before annotation and split assignment
- External services: forbidden
- Public raw or derived text: forbidden
- Replaces: invalidated `DATA-FCTX-CLEAN-V1`

## 1. Purpose

把 IAC 2.0 4forums 中具有直接父回复关系的帖子转为可审计的
`parent -> target` 候选对。本阶段只回答哪些关系可解析、文本经过了什么确定性处理、
哪些样本存在质量风险。它不标注情绪，不确定 train/dev/test，也不进行模型筛选。

成功条件：

1. 每个候选都能追溯到私有源记录，但公开产物不含原文、源 ID 或可逆映射。
2. 每条排除都有 reason code，每个保留但可疑的样本都有 soft flag；不静默删除。
3. 按 IAC standoff schema 重建 quote 层级，并逐条验证 insertion offset。
4. 全量结果通过独立脚本复算，数据库 `integrity_check` 为 `ok`。

## 2. Input and candidate unit

输入只读取以下表和字段：

- `discussion`: `discussion_id`, `title`；不读取 URL 和发帖人。
- `post`: `discussion_id`, `post_id`, `creation_date`, `parent_post_id`,
  `parent_missing`, `text_id`；不读取 `author_id`。
- `quote`: quote 层级、插入位置、quote 文本 ID、来源位置及截断/改写标志。
- `text`: `text_id`, `longtext`。

候选全集是所有声明了非空 `parent_post_id` 的 target 帖子。根帖子不属于候选全集。
父帖不存在或 `parent_missing=1` 的记录仍进入私有候选表，但标记为 hard exclusion。

## 3. IAC quote semantics and reconstruction

IAC 将帖子作者自己的正文与引用文本存为不同 `text_id`。`quote.text_offset` 不是要
从帖子正文中删除的 span，而是 quote 对象在所属文本中的 insertion point：

- `parent_quote_index IS NULL`: offset 相对于该帖自己的 `post.text_id` 文本。
- `parent_quote_index IS NOT NULL`: offset 相对于父 quote 的文本。

V2 先验证每个 offset 位于所属文本的 `[0, len(text)]` 范围，再递归重建嵌套引用：

- `model_full`: 在有效位置插入 `[[QUOTE]] ... [[/QUOTE]]` 及实际 quote 文本。
- `model_body`: 在每个有效顶层 quote 位置只插入 `[[QUOTE]]`，帖子自己的正文原样
  保留。它用于识别当前发帖者情绪，避免把被引用者内容误当成目标表达。

Offset 状态逐条登记为 `valid_top_level`、`valid_nested`、`missing_offset`、
`missing_parent`、`out_of_bounds` 或 `cycle`。Quote 文本另记 `present`、`empty`、
`missing` 和 UTF-8 replacement。无效结构不通过正则猜测，不插入不确定内容，只加
soft flag。`truncated` 与 `altered` 是来源对应属性，不妨碍保留实际显示的 quote 文本。

## 4. Three text representations

私有库保留三种不同职责的表示：

1. `raw_bytes`: post 与 quote 的原始字段字节，只用于追溯。
2. `model_full` / `model_body`: 按第 3 节重建后进行最小规范化。
3. `dedup_body`: 仅用于精确去重的 key，不作为模型输入。

`model_*` 的确定性处理顺序：UTF-8 解码并记录 replacement、Unicode NFC、HTML entity
解码、可识别 HTML 标签转为可见文本、控制字符与空白规范化，然后掩码 URL、email、
IP 和 `@mention`。保留大小写、标点、重复字符、拼写、俚语、脏话、否定和反讽线索。
不得做 stopword removal、stemming、lemmatization 或拼写纠正。

`dedup_body` 在 `model_body` 基础上使用 Unicode NFKC、casefold 和空白折叠；不删除
标点，不回写模型输入。

## 5. Hard exclusions

Hard exclusion 只用于无法形成有效上下文样本的情况：

- `parent_unresolved`
- `{target,parent}_missing_text`
- `{target,parent}_empty`
- `{target,parent}_placeholder`
- `{target,parent}_quote_only`

Placeholder 仅匹配 `[deleted]`、`[removed]`、`deleted`、`removed`、`n/a` 和 `none`。
短句、纯标点、URL-only 和低 Latin 比例文本不作 hard exclusion。`eligible = 1` 当且
仅当 hard reason 列表为空。

## 6. Soft flags

每个帖子按确定性规则记录：

- `short`: ASCII word token 少于 3；`long`: 多于 512。
- `quote_heavy`: quote 文本字符占重建 full text 字符至少 50%。
- `url_only`, `html_present`, `decode_replacement`, `low_latin_ratio`, `all_caps`。
- `repeated_character`, `possible_signature`, `no_lexical_tokens`。
- `quote_structure_unverified`, `quote_text_missing`, `quote_decode_replacement`。
- `html_quote_unstructured`: 出现 HTML blockquote 但没有可用顶层 quote metadata。

候选表中的 flag 加 `target_` 或 `parent_` 前缀。创建时间早于父帖时另记
`timestamp_nonmonotonic`。Soft flags 不改变 `eligible`。

## 7. Exact duplication

V2 只登记精确重复，不执行自动删除：

- target duplicate key: target `dedup_body` 的 SHA-256。
- pair duplicate key: parent 与 target 两个 dedup hash 的有序组合。
- context variant: 同一 target key 对应多个不同 parent key。

重复统计只基于 eligible candidates。所有成员继续保留，供后续按 thread 分组抽样和
划分。MinHash、embedding 或编辑距离近重复检测留给单独协议。

## 8. De-identification and storage

`thread_uid`、`post_uid` 和 `sample_uid` 使用本机随机 32-byte key 的 HMAC-SHA256
生成。key 权限为 `0600`，只保存在 gitignored 私有目录。公开 JSON 不得包含帖子、
讨论或用户源 ID，原文或清洗文本，per-sample HMAC ID，文本/pair hash，或绝对路径。

私有 SQLite 可保留源 ID、原始字段和模型文本，用于本地标注与审计。不得读取或保存
`author` 表，不得保留 discussion URL。

## 9. Outputs and verification

Private, gitignored:

- `data/iac2/derived-private/dataset-construction/cleaning-v2.sqlite`
- `data/iac2/derived-private/dataset-construction/id-key.bin`

Trackable, aggregate only:

- `dataset-construction/reports/cleaning-preflight-v2.json`
- `dataset-construction/reports/cleaning-verification-v2.json`
- `data/iac2/manifests/cleaning-v2.json`

独立验证器必须复算 source/artifact hash、候选总数、eligible/excluded、hard reasons、
soft flags、quote offset/text 状态、长度分位数和精确重复统计，并检查私有路径受到
`.gitignore` 保护。任何不一致都使状态为 `failed`。

## 10. Out of scope and change control

本协议不决定 emotion ontology、人工/LLM 标注流程、样本量、topic 平衡、近重复阈值、
thread-disjoint split 或训练模型。改变 hard exclusion、quote 层级重建、去重 key 或
隐私边界时必须建立新版本。
