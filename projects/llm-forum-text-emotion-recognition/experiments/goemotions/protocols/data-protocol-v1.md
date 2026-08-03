# DATA-GOE-V1: GoEmotions Public Benchmark Data Protocol

Registration date: 2026-07-30 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-GOE-V1`
- Status: `FROZEN`
- Dataset: GoEmotions
- Task: full-taxonomy multi-label text classification
- Test access: `NOT_ACQUIRED`

## 1. Purpose

本协议冻结 GoEmotions 公开基准分支的数据边界，为后续简单多标签基线、
BERT-base/RoBERTa 监督微调和 LLM 对照提供同一数据基础。

本协议只冻结公开基准数据，不等于：

- 已决定用 GoEmotions 取代最终的自建论坛数据。
- 已完成 Emotion Recognition in Conversation（ERC）任务。
- 已获得父回复、线程上下文、作者或 subreddit 元数据。
- 已冻结模型、tokenizer、阈值、prompt 或训练超参数。

是否需要额外采集论坛数据、使用何种语言以及是否纳入线程上下文，仍需导师确认。

## 2. Authoritative Sources

### Paper

- Demszky et al. (2020), "GoEmotions: A Dataset of Fine-Grained Emotions"
- ACL Anthology: <https://aclanthology.org/2020.acl-main.372/>
- DOI: <https://doi.org/10.18653/v1/2020.acl-main.372>

### Dataset repository

- Repository: <https://github.com/google-research/google-research/>
- Subdirectory: `goemotions/`
- Pinned repository revision:
  `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`
- Revision retrieved: 2026-07-30

All acquisition URLs must use the pinned revision rather than the moving
`master` branch:

```text
https://raw.githubusercontent.com/google-research/google-research/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/data/train.tsv
https://raw.githubusercontent.com/google-research/google-research/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/data/dev.tsv
https://raw.githubusercontent.com/google-research/google-research/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/data/test.tsv
https://raw.githubusercontent.com/google-research/google-research/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/data/emotions.txt
```

The Google Research repository states that its datasets are released under
CC BY 4.0 and its source code under Apache 2.0. Dataset attribution remains
mandatory. A public release does not remove the need to handle Reddit text,
offensive content and recoverable identifiers cautiously.

## 3. Frozen Dataset Variant

The first GoEmotions baseline uses only the official agreement-filtered files:

| Upstream file | Role | Expected rows | Current local access |
| --- | --- | ---: | --- |
| `train.tsv` | Training | 43,410 | Acquired and verified 2026-07-30 |
| `dev.tsv` | Validation and model selection | 5,426 | Acquired and verified 2026-07-30 |
| `test.tsv` | One-time frozen evaluation | 5,427 | Not acquired; test gate required |
| `emotions.txt` | Label ID order | 28 labels | Acquired and verified 2026-07-30 |

The three splits contain 54,263 examples in total. The raw 58,009-example CSV
release and its author, subreddit, parent and timestamp metadata are outside
`DATA-GOE-V1`.

No upstream split may be merged, resampled or reassigned in the reproduction
baseline.

### Local storage

Data and experiment code have separate project-level responsibilities:

```text
projects/llm-forum-text-emotion-recognition/
├── data/
│   ├── tweeteval-emotion/official/
│   └── goemotions/
│       ├── manifest.json
│       └── official/
│           ├── emotions.txt
│           ├── train.tsv
│           └── dev.tsv
└── experiments/
    ├── tweeteval-emotion/
    └── goemotions/
```

- Raw GoEmotions files belong only in `data/goemotions/official/`.
- `data/goemotions/official/` is ignored by Git.
- `data/goemotions/manifest.json` may be committed because it contains no text
  or upstream comment IDs.
- Protocols, acquisition code, model code and run artifacts belong in
  `experiments/goemotions/`.
- No duplicate raw snapshot may be created under `experiments/goemotions/`.

## 4. Frozen Task Definition

- Input: the single English Reddit comment in column 1 of the filtered TSV.
- Output: a 28-dimensional multi-hot label vector.
- Task type: multi-label classification.
- Each label is an independent binary target.
- Multi-label examples must remain multi-label.
- `neutral` remains label 27 and is not treated as absence of every label.
- No example may be removed because it has a rare, mixed or inconvenient label.
- No four-class filtering, Ekman grouping or sentiment grouping is allowed in
  the first reproduction baseline.
- No parent comment, thread, author or subreddit information is available in
  this task.

The exact label order is frozen to the upstream `emotions.txt` order:

| ID | Label | ID | Label |
| ---: | --- | ---: | --- |
| 0 | admiration | 14 | fear |
| 1 | amusement | 15 | gratitude |
| 2 | anger | 16 | grief |
| 3 | annoyance | 17 | joy |
| 4 | approval | 18 | love |
| 5 | caring | 19 | nervousness |
| 6 | confusion | 20 | optimism |
| 7 | curiosity | 21 | pride |
| 8 | desire | 22 | realization |
| 9 | disappointment | 23 | relief |
| 10 | disapproval | 24 | remorse |
| 11 | disgust | 25 | sadness |
| 12 | embarrassment | 26 | surprise |
| 13 | excitement | 27 | neutral |

Any label reordering, merging or mapping creates a new versioned data protocol.

## 5. Frozen File Schema

Each filtered TSV has no header and exactly three tab-separated columns:

1. `text`: masked Reddit comment text.
2. `label_ids`: comma-separated integer IDs indexing `emotions.txt`.
3. `comment_id`: upstream comment identifier.

Files must be read as UTF-8. Text, labels and IDs must not be silently stripped,
normalized or rewritten during acquisition. Model-specific normalization belongs
in a later experiment protocol and must be fitted or selected without test use.

## 6. Split Discipline

### Train

May be used to:

- fit tokenizers or trainable preprocessing;
- train model parameters;
- create train-only cross-validation folds;
- estimate class frequencies for a preregistered weighting method.

### Dev

May be used to:

- select checkpoints and model configurations;
- select global or per-label decision thresholds;
- select prompts, demonstrations and deterministic output parsers;
- decide whether a candidate advances to a frozen Major comparison.

Dev metrics are not final generalization estimates.

### Test

`test.tsv` is currently `NOT_ACQUIRED`.

Before acquisition or evaluation, a separate GoEmotions `TEST-READY` checklist
must:

- name every frozen model and LLM condition to be evaluated;
- freeze thresholds, prompts, parsing, seeds and metric implementations;
- verify train/dev predictions and hashes;
- confirm that no test example or label informed development;
- receive explicit user authorization.

One authorized test gate may evaluate all conditions frozen in that checklist.
Any later development is post-test development and cannot reuse this test as
validation.

## 7. Acquisition and Integrity Checks

The `experiments/goemotions/prepare_data.py` implementation may acquire only
train/dev and `emotions.txt`. It intentionally has no test-download option.
A later test-gate implementation must be separate and explicitly authorized.

After train/dev acquisition, create a manifest containing:

- protocol ID and pinned upstream revision;
- retrieval timestamp and exact source URL for each file;
- byte size, row count and SHA-256;
- parser version or code commit;
- label count and exact ordered label list;
- count of malformed rows, empty text, empty labels and out-of-range IDs;
- unique comment IDs and duplicate IDs within each acquired split;
- exact ID and exact-text overlap between train and dev;
- explicit test access state.

Expected validation requirements:

- `train.tsv` has 43,410 rows.
- `dev.tsv` has 5,426 rows.
- every row has exactly three TSV columns;
- every label ID is an integer from 0 through 27;
- every row has at least one label;
- `emotions.txt` exactly matches the frozen 28-label order;
- comment IDs are non-empty;
- cross-split comment ID overlap is a validation failure;
- an unreviewed or changed exact-text overlap profile triggers a stop and review.

The reproduction baseline preserves official rows. If an integrity check
reveals a problem, do not silently deduplicate or repair the data; record the
finding and create a new protocol if the split must change.

### 2026-07-30 train/dev overlap review

The first acquisition stopped because the pinned official split contains exact
text overlap. Review found:

- zero overlapping comment IDs;
- 41 unique exact texts represented by 84 train rows and 43 dev rows;
- 33 of those dev rows have a label set also observed with the same text in
  train;
- 10 dev rows have no matching train label set for the same text.

These are different upstream comments that reuse identical text, including
short generic expressions. `DATA-GOE-V1` preserves the official rows and split
for benchmark comparability. The acquisition script now validates this exact
reviewed profile and records it in `data/goemotions/manifest.json` as a data
quality warning. Any changed overlap profile stops validation. Deduplication,
grouped splitting or removal would require a new protocol and would no longer
be the official reproduction baseline.

## 8. Privacy, Publication and API Boundary

- Raw TSV files and copied Reddit text must remain under
  `data/goemotions/official/` and out of Git.
- Training logs, predictions and error-analysis files must not publish raw text.
- Public qualitative examples require a separate privacy review and should be
  paraphrased or locally isolated by default.
- Upstream comment IDs must not appear in public artifacts unless a later
  protocol establishes a concrete reproducibility need and privacy review.
- Dataset citation and CC BY 4.0 attribution must accompany redistributed
  derived data where applicable.
- No GoEmotions text may be sent to an external LLM API under this protocol.
  Provider terms, retention, model version, cost and upload boundary belong in
  the later LLM protocol.

## 9. Frozen Decisions

The following decisions are frozen for the first public-data reproduction:

- Google Research source pinned to the stated revision.
- Official agreement-filtered train/dev/test split.
- Full 28-label order.
- Multi-label task with preserved multi-label examples.
- Single-comment text input without reconstructed context.
- Train/dev/test roles and explicit test gate.
- No raw dataset or raw error text in public Git.

## 10. Deliberately Unfrozen Decisions

The following remain open and must not be inferred from this document:

- BERT or RoBERTa checkpoint and model revision.
- Maximum sequence length, optimizer, batch size and random seeds.
- BCE variant, class weights, focal loss or calibration method.
- Global versus per-label threshold strategy.
- Primary and secondary multi-label metrics.
- LLM provider, model, prompt, demonstrations and API budget.
- Whether a later experiment uses Ekman or sentiment mappings.
- Whether the final thesis adds a self-collected forum dataset or thread context.

These choices belong in later Major experiment protocols.

## 11. Change Control

Typographical corrections may be appended with a dated correction note.

Changing any of the following requires `DATA-GOE-V2` or a separate named dataset
protocol:

- upstream revision or dataset variant;
- label order, grouping or filtering;
- split membership;
- deduplication or resampling;
- inclusion of raw metadata or conversational context;
- test access rules.

No result has been produced by freezing this protocol. It is a research-design
artifact and must not be listed as a completed model experiment.
