# DATA-FCTX-CJ-V1: GoEmotions Closed-Corpus Parent Coverage Audit

Registration date: 2026-08-04 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-FCTX-CJ-V1`
- Status: `COMPLETED`
- Experiment class: data preflight
- Source: Google official GoEmotions raw release
- Scope: train/dev targets only
- Filtered GoEmotions `test.tsv`: `PROHIBITED_AND_NOT_READ`
- External parent recovery: `PROHIBITED`

## 1. Question

在不访问 Reddit 或第三方存档的条件下，GoEmotions 官方 raw release 内部能为多少
filtered train/dev targets 提供 parent comment text？缺失 parent 分别来自 parent 是
submission、parent comment 未被 GoEmotions 收录，还是 target 无法关联 raw metadata？

## 2. Inputs

Raw files must come only from the URLs published by the GoEmotions README:

```text
https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_1.csv
https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_2.csv
https://storage.googleapis.com/gresearch/goemotions/data/full_dataset/goemotions_3.csv
```

Local raw directory:

```text
data/goemotions/official/full_dataset/
```

Filtered targets:

```text
data/goemotions/official/train.tsv
data/goemotions/official/dev.tsv
```

`test.tsv` is intentionally absent from every command-line argument and may not be read. The raw
release is an unpartitioned corpus that necessarily contains comments later assigned to filtered
splits; this audit does not resolve or use test membership and does not read raw emotion-label
columns. Therefore, a parent with text in the raw release is not automatically a split-safe training
example.

## 3. Raw Deduplication

Raw CSV rows represent individual rater annotations, so the same comment `id` appears more than
once. Before joining:

- normalize raw `id` by removing an optional `t1_` prefix;
- group rows by normalized `id`;
- require `text`, `parent_id`, `link_id`, `subreddit` and `created_utc` to be consistent across
  repeated rater rows;
- report raw row count, unique comment count, duplicate annotation rows and conflict counts;
- do not emit any text, user name, target ID or parent ID in public output.

Any conflict in `text` or `parent_id` is a review stop rather than silently selecting one value.

## 4. Deterministic Categories

For every filtered target, first join `filtered.comment_id -> raw.id` and then classify:

| Category | Definition |
| --- | --- |
| `target_missing_from_raw` | filtered target ID is absent from all raw CSVs |
| `missing_parent_id` | target raw row has an empty parent field |
| `submission_parent` | parent fullname begins with `t3_`; submission text is not in the comment corpus |
| `comment_parent_in_raw_text_available` | parent begins with `t1_`, normalized ID exists in raw IDs, and text is non-empty/non-deleted |
| `comment_parent_in_raw_unusable_text` | parent comment exists in raw IDs but its text is empty, `[deleted]` or `[removed]` |
| `comment_parent_not_in_raw` | parent begins with `t1_` but normalized ID is absent from raw IDs |
| `unknown_parent_type` | non-empty parent value has an unrecognized prefix |

The missing-parent count requested by the user is:

```text
all train/dev targets - comment_parent_in_raw_text_available
```

The report must also show each component separately; one aggregate number is insufficient.

Here, `text_available` is a closed-corpus availability result only. It does not establish split
safety, authorization for a later model run, or suitability for Dataset A.

## 5. Outputs

Primary output:

```text
preflight/closed-corpus-parent-coverage.json
```

Independent verification:

```text
preflight/closed-corpus-parent-coverage-verification.json
```

Both outputs may contain only:

- source URLs, byte sizes and SHA-256 hashes;
- aggregate counts and rates;
- protocol and script hashes;
- explicit statements that test and external sources were not used.

## 6. Decision Boundary

This audit does not authorize annotation, model training or Dataset A construction. After the
coverage result is known:

- high enough coverage still requires representativeness and missingness-bias analysis;
- low coverage closes the GoEmotions closed-corpus context route;
- missing parents remain missing and are never fetched from Reddit under this protocol.

## 7. Execution Result

Executed: 2026-08-04 (Asia/Shanghai)

The three official raw CSVs contained 211,225 rater-annotation rows representing 58,011 unique
comments. All 48,836 filtered train/dev targets matched raw metadata, and every target had a
`parent_id`. Parent text availability was:

| Split | Targets | Parent text available in raw | Missing parent text | Missing rate |
| --- | ---: | ---: | ---: | ---: |
| train | 43,410 | 139 | 43,271 | 99.680% |
| dev | 5,426 | 18 | 5,408 | 99.668% |
| total | 48,836 | 157 | 48,679 | 99.679% |

The 48,679 missing cases consist of 19,987 submission parents whose post text is absent from the
comment corpus and 28,692 comment parents whose IDs are absent from the raw release. No available
parent text was empty, `[deleted]` or `[removed]`. The independent SQLite recomputation passed with
zero mismatches.

Decision: the official GoEmotions release alone cannot support the planned large-scale contextual
Dataset A. The 157 available pairs remain diagnostic candidates only and require a separate
split/leakage protocol before any use.
