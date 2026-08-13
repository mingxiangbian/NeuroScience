# Public Candidate Dataset Viability Audit V1

Date: 2026-08-08
Protocol: `DATA-FCTX-PUBLIC-AUDIT-V1`
Status: `COMPLETED`

## Decision

| Candidate | Audit decision | Permitted role |
| --- | --- | --- |
| KOTE | `eligible_training_control` | C0 target-only multi-label training/control |
| Hotter and Colder | `blocked_pending_review` | Potential context challenge only after hydration, privacy and reproducibility repair |
| Weibo Emotion Cause Corpus | `eligible_auxiliary` | C1 emotion-cause/context auxiliary experiment after a separate mapping and split protocol |

No candidate is adopted as the final thesis dataset by this audit.

## KOTE

- Acquired only `train.tsv` (40,000 rows) and `val.tsv`
  (5,000 rows) at revision `cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977`. `test.tsv` was not
  downloaded or parsed.
- Both files are headerless three-column TSVs: upstream ID, target text and
  comma-separated label IDs. All 44 label IDs appear in the audited files.
- Train/validation ID overlap: 0; exact-text
  overlap: 0.
- Train label cardinality is 7.911 on
  average; 39,639 rows have more than one label. This
  reproduces the paper's reported 7.91 after its five-rater vote aggregation,
  per-text min-max scaling and `> 0.2` binary threshold; it is not a parser error.
- The `no emotion` label appears with other labels in
  6,261 train rows and
  763 validation rows. This is allowed
  by the upstream transformation, but any later ontology mapping must explicitly
  define whether `no emotion` is exclusive, retained or dropped.
- A deterministic local review of 24 rows found ordinary online-comment noise,
  including spacing/punctuation variation and repetition, without exposing any
  sampled text in this report.
- The release contains no parent, thread, author or platform field. It is a
  viable C0 control, not evidence about context.

## Hotter and Colder

- The CLARIN package MD5 matches the published checksum. It contains
  19,828 annotation rows across
  26 tasks and
  12,675 unique URL/timestamp target
  keys.
- These release counts differ from the paper's 19,301 annotations and 12,232
  unique comments by +527
  and +443, respectively.
  The difference may reflect a later package version, but the release does not
  document that reconciliation.
- The package does not contain target text, previous comments or blog text.
  Those fields are reconstructed by scraping live URLs.
- The supplied hydration script uses live `requests.get`, has no request
  timeout, appends comment signatures to text and is hard-coded to the first 50
  rows. Hydration was therefore not executed.
- The eight emotions are stored as separate binary annotation tasks. Only
  0 targets have all eight
  emotion tasks, so the release cannot be treated as an ordinary complete
  eight-label matrix without redefining missing labels.
- The README says emotion labels are positive/neutral/negative, while the actual
  emotion rows use `0`, `1` and `skip`; the paper supports the latter binary
  interpretation. The README must not be used as the schema authority.
- Until hydration success, identifier removal, stable snapshots and split rules
  are resolved, this candidate is blocked rather than immediately executable.

## Weibo Emotion Cause Corpus

- The pinned release contains 12,586 logical cause
  records across 12,600 physical lines,
  and 23,127 logical records across
  24,208 physical lines in
  `emotion_classification.tsv`. Quoted embedded newlines explain why `wc -l`
  is not a valid record count.
- The latter is a mixed structural file: it contains
  12,052 `Y/N` cause
  scaffold rows plus 11,075
  emotion-clause rows. Filtering its scaffold rows does not reproduce the
  dedicated cause file: only
  120
  records are exact matches, while
  12,466 occur
  only in the cause file and
  11,932 only
  in the filtered classification view. They must be treated as separate task
  releases, not joined by row position.
- The emotion labels mix discrete emotions, positive/negative/neutral,
  `No_emotion` and 45 composite rows.
  They are not a ready-made replacement for the current ontology.
- There are 3,386 multi-user groups, and
  2,809 contain both a cause scaffold and at
  least one emotion-clause row. This is useful context/cause structure, but its
  primary task is emotion-cause detection rather than general forum emotion
  recognition.
- A deterministic local review of 24 records confirmed tokenization artifacts,
  explicit structural markers, emoji placeholders, mentions and short clause
  fragments; no sampled text is retained in this report.

## Recommendation

1. Keep KOTE as the strongest immediately usable C0 training/control candidate.
2. Downgrade Hotter and Colder from “executable now” to a conditional context
   candidate; do not scrape or hydrate it under the current protocol.
3. Keep Weibo as an auxiliary C1 cause/context dataset, not the main benchmark.
4. The current three-source route still lacks a directly executable, fully
   packaged, human-labeled forum dataset with both author-emotion labels and
   stable thread context. RESEMO therefore remains the best-fit conditional
   candidate.

## Source Anchors

- KOTE label construction and model preprocessing:
  <https://aclanthology.org/2024.lrec-main.1499/>.
- Hotter and Colder task design, counts and context interface:
  <https://aclanthology.org/2025.nodalida-1.18/>.
- Weibo corpus task definition and pinned release:
  <https://doi.org/10.1145/3132684> and
  <https://github.com/wjhou/Weibo-Emotion-Corpus>.

## Evidence Boundary

- Counts, hashes and schema findings are local audit results.
- Task definitions, licenses and upstream annotation methods remain literature
  or repository claims.
- No source text, user identifier, URL or row-level sample is stored in this
  report.
- No training, label mapping, split construction or test evaluation occurred.
