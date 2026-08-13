# DATA-FCTX-PUBLIC-AUDIT-V1: Public Candidate Viability Audit

Registration date: 2026-08-08 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-FCTX-PUBLIC-AUDIT-V1`
- Status: `FROZEN`
- Research dependency: Phase 5 forum-context data-source gate
- Tier: data preflight; not a model experiment
- Candidates: KOTE, Hotter and Colder, Weibo Emotion Cause Corpus
- Training: prohibited
- External LLM/API upload: prohibited
- Existing TweetEval, GoEmotions and IAC2 data: out of scope

## 1. Purpose

This audit determines whether each public candidate can support one of three
roles in the thesis:

1. target-only emotion training or control;
2. paired target-only versus target-plus-context evaluation;
3. emotion-cause or limited-context auxiliary analysis.

It does not select the final thesis dataset, merge label ontologies, create new
splits, train a model or authorize publication of source text.

Context is a strong preference rather than an admission requirement. A reliable
`C0` dataset may pass as a training/control source, but only a dataset with
usable `C1` or `C2` fields may support a claim about context.

## 2. Authoritative Sources and Acquisition Boundary

### KOTE

- Repository: <https://github.com/searle-j/KOTE>
- Paper: <https://aclanthology.org/2024.lrec-main.1499/>
- License reported by repository: MIT
- Permitted acquisition in this audit: `README.md`, `LICENSE`, `train.tsv` and
  `val.tsv` at one resolved commit.
- `test.tsv` must not be parsed, sampled or used in any decision.

### Hotter and Colder

- Repository record: <http://hdl.handle.net/20.500.12537/352>
- Paper: <https://aclanthology.org/2025.nodalida-1.18/>
- Release file: `Icelandic_Sentiment_Corpus.zip`
- Repository checksum: MD5 `6f26a58c5771158c0f9492096222ad6c`
- License reported by repository: CC BY 4.0
- The unhydrated CSV, README, requirements and hydration script may be
  inspected. The hydration script must not be executed until its endpoint,
  requested fields, identifier handling and output privacy have been reviewed.

### Weibo Emotion Cause Corpus

- Repository: <https://github.com/wjhou/Weibo-Emotion-Corpus>
- Paper: <https://doi.org/10.1145/3132684>
- Pinned repository commit:
  `d385f8cdc7e7ab9ca1ec62b8202c664a5ba651f3`
- License reported by repository: Apache-2.0
- Both released TSV files may be inspected. No external account or additional
  Weibo content may be recovered.

## 3. Local Storage

Raw text and upstream identifiers belong only in gitignored directories:

```text
data/
├── kote/official/
├── hotter-and-colder/official/
└── weibo-emotion-corpus/official/
```

Each dataset directory may expose a public `README.md` and aggregate
`manifest.json`, but those files must not contain source text, user names,
upstream post IDs or reversible row-level samples.

Audit code and privacy-safe reports belong under:

```text
experiments/forum-context/public-candidate-audit/
```

## 4. Frozen Audit Questions

For every candidate, record:

- exact acquired files, source revision, size, SHA-256 and license evidence;
- parser-visible columns, encoding, row counts and malformed rows;
- annotation unit, label provenance and whether labels are single- or
  multi-label;
- official split availability without reading a protected test split;
- empty text, empty label, duplicate ID and exact-text duplicate counts;
- label vocabulary, label cardinality and class-frequency range;
- available context fields and their observed non-null coverage;
- presence of author names, user IDs, URLs, timestamps or other identifiers;
- whether target-only and target-plus-context inputs can be constructed from
  the same labeled rows;
- limits that prevent the dataset from supporting a thesis claim.

## 5. Sample Inspection

Sample inspection is deterministic and local-only.

- Seed: `20260808`.
- KOTE: at most 12 train and 12 validation rows.
- Weibo: at most 12 rows from each released task file.
- Hotter and Colder: inspect only unhydrated records in the first pass. Text or
  reconstructed context may be sampled only after the hydration review passes.

Sample text, IDs and user fields must not be copied into public reports. Human
inspection may record only aggregate issue categories such as markup noise,
truncation, mixed-language text, label ambiguity or missing context.

## 6. Stop Conditions

Stop the affected candidate without repair or silent substitution if:

- the checksum or source revision cannot be established;
- the license or access route conflicts with the intended use;
- hydration requires an undocumented or unauthorized endpoint;
- a parser would need to infer undocumented label semantics;
- source text or identifiers would enter tracked files;
- `test.tsv` is accidentally parsed or sampled;
- an expected context field is absent or means something different from a
  parent/reply relation.

## 7. Decision States

Each candidate receives exactly one audit decision:

- `eligible_training_control`: usable C0 source, no context claim;
- `eligible_context_challenge`: usable paired context evaluation source;
- `eligible_auxiliary`: useful for cause, transfer or method analysis only;
- `blocked_pending_review`: potentially useful but a concrete access, privacy,
  schema or label issue remains;
- `reject_for_current_task`: the released target does not match author emotion.

The audit may recommend a role, but final dataset adoption and any label mapping
require a separate user-approved data protocol.

## 8. Required Outputs

- `reports/public-candidate-viability-audit-v1.json`: machine-readable aggregate
  findings and decision states.
- `reports/public-candidate-viability-audit-v1.md`: evidence, comparison and
  recommendation without source text.
- One privacy-safe manifest and storage README per acquired candidate.
- Verification that tracked outputs contain no sampled text or upstream IDs.
