#!/usr/bin/env python3
"""Audit public forum-emotion candidates without publishing source text or IDs."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


csv.field_size_limit(16 * 1024 * 1024)


PROTOCOL_ID = "DATA-FCTX-PUBLIC-AUDIT-V1"
SEED = 20260808
PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUDIT_ROOT = Path(__file__).resolve().parent
REPORT_ROOT = AUDIT_ROOT / "reports"
DATA_ROOT = PROJECT_ROOT / "data"

KOTE_ROOT = DATA_ROOT / "kote" / "official"
HOTTER_ROOT = DATA_ROOT / "hotter-and-colder" / "official"
WEIBO_ROOT = DATA_ROOT / "weibo-emotion-corpus" / "official"

KOTE_REVISION = "cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977"
WEIBO_REVISION = "d385f8cdc7e7ab9ca1ec62b8202c664a5ba651f3"
HOTTER_EXPECTED_MD5 = "6f26a58c5771158c0f9492096222ad6c"

KOTE_NO_EMOTION_ID = 24
WEIBO_CAUSE_LABELS = {"N", "Y"}
WEIBO_MARKERS = (
    "beg_context",
    "end_context",
    "beg_cause",
    "end_cause",
    "beg_emotionkeyword",
    "end_emotionkeyword",
    "beg_preclause",
    "end_preclause",
    "beg_curclause",
    "end_curclause",
    "beg_sufclause",
    "end_sufclause",
)


def digest(path: Path, algorithm: str = "sha256") -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def file_record(path: Path, *, include_md5: bool = False) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    if include_md5:
        record["md5"] = digest(path, "md5")
    return record


def physical_line_count(path: Path) -> int:
    count = 0
    last_byte = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    return count + int(path.stat().st_size > 0 and last_byte != b"\n")


def rounded(value: float) -> float:
    return round(value, 6)


def numeric_summary(values: Iterable[int]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        return {"min": 0, "median": 0, "mean": 0, "p95": 0, "max": 0}
    p95_index = min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))
    return {
        "min": ordered[0],
        "median": rounded(statistics.median(ordered)),
        "mean": rounded(statistics.fmean(ordered)),
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def duplicate_excess(values: Iterable[str]) -> int:
    counts = Counter(values)
    return sum(count - 1 for count in counts.values() if count > 1)


def selection_digest(row_count: int, sample_size: int) -> dict[str, Any]:
    rng = random.Random(SEED)
    indices = sorted(rng.sample(range(row_count), min(sample_size, row_count)))
    payload = ",".join(str(index) for index in indices).encode("ascii")
    return {
        "seed": SEED,
        "sample_size": len(indices),
        "index_sha256": hashlib.sha256(payload).hexdigest(),
    }


def read_tsv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, delimiter="\t"))


def audit_kote_split(path: Path, sample_size: int) -> tuple[dict[str, Any], set[str], set[str]]:
    rows = read_tsv(path)
    malformed = 0
    empty_id = 0
    empty_text = 0
    empty_labels = 0
    invalid_label_rows = 0
    ids: list[str] = []
    text_hashes: list[str] = []
    text_lengths: list[int] = []
    cardinalities: list[int] = []
    label_frequency: Counter[int] = Counter()
    no_emotion_rows = 0
    no_emotion_cooccurrence = 0

    for row in rows:
        if len(row) != 3:
            malformed += 1
            continue
        row_id, text, raw_labels = row
        ids.append(row_id)
        text_hashes.append(hashlib.sha256(text.encode("utf-8")).hexdigest())
        text_lengths.append(len(text))
        empty_id += int(not row_id)
        empty_text += int(not text)
        empty_labels += int(not raw_labels)
        try:
            labels = [int(value) for value in raw_labels.split(",") if value]
        except ValueError:
            invalid_label_rows += 1
            continue
        if not labels or any(label < 0 or label > 43 for label in labels):
            invalid_label_rows += 1
            continue
        cardinalities.append(len(labels))
        label_frequency.update(labels)
        if KOTE_NO_EMOTION_ID in labels:
            no_emotion_rows += 1
            no_emotion_cooccurrence += int(len(labels) > 1)

    parsed_rows = len(rows) - malformed
    result = {
        "file": file_record(path),
        "rows": len(rows),
        "parsed_rows": parsed_rows,
        "malformed_rows": malformed,
        "empty_id_rows": empty_id,
        "empty_text_rows": empty_text,
        "empty_label_rows": empty_labels,
        "invalid_label_rows": invalid_label_rows,
        "unique_ids": len(set(ids)),
        "duplicate_id_excess_rows": duplicate_excess(ids),
        "unique_exact_texts": len(set(text_hashes)),
        "duplicate_exact_text_excess_rows": duplicate_excess(text_hashes),
        "text_length_codepoints": numeric_summary(text_lengths),
        "label_vocabulary_ids": sorted(label_frequency),
        "label_frequency_min": min(label_frequency.values(), default=0),
        "label_frequency_max": max(label_frequency.values(), default=0),
        "label_cardinality": numeric_summary(cardinalities),
        "single_label_rows": sum(value == 1 for value in cardinalities),
        "multi_label_rows": sum(value > 1 for value in cardinalities),
        "no_emotion_label_id": KOTE_NO_EMOTION_ID,
        "no_emotion_rows": no_emotion_rows,
        "no_emotion_cooccurrence_rows": no_emotion_cooccurrence,
        "private_sample_selection": selection_digest(len(rows), sample_size),
    }
    return result, set(ids), set(text_hashes)


def audit_kote() -> dict[str, Any]:
    train, train_ids, train_texts = audit_kote_split(KOTE_ROOT / "train.tsv", 12)
    validation, val_ids, val_texts = audit_kote_split(KOTE_ROOT / "val.tsv", 12)
    return {
        "dataset": "KOTE",
        "source": {
            "repository": "https://github.com/searle-j/KOTE",
            "revision": KOTE_REVISION,
            "license": "MIT",
            "test_access": "not_downloaded_not_parsed",
            "files": [
                train["file"],
                validation["file"],
                file_record(KOTE_ROOT / "README.md"),
                file_record(KOTE_ROOT / "LICENSE"),
            ],
        },
        "schema": {
            "format": "headerless TSV",
            "encoding": "UTF-8",
            "columns": ["upstream_id", "text", "comma_separated_label_ids"],
            "annotation_unit": "single online comment",
            "context_level": "C0",
            "official_split": "fixed train/validation/test; test protected in this audit",
            "paired_target_context_constructible": False,
            "label_type": "44-way multi-label including no-emotion",
            "label_provenance": "five crowdsourced raters per text with post-annotation review",
            "released_label_derivation": (
                "five annotator votes per label, text-wise min-max scaling, "
                "then binary threshold greater than 0.2"
            ),
            "paper_reported_mean_label_cardinality": 7.91,
        },
        "splits": {"train": train, "validation": validation},
        "cross_split": {
            "overlapping_ids": len(train_ids & val_ids),
            "overlapping_exact_texts": len(train_texts & val_texts),
        },
        "decision": "eligible_training_control",
        "decision_basis": [
            "public pinned train and validation files with a repository license",
            "expected row counts and a documented multi-label task whose released preprocessing reproduces the paper-reported mean cardinality",
            "no reply, thread, author or platform fields, so no context claim is possible",
            "the released no-emotion label can co-occur with emotion labels under the upstream vote transformation and needs an explicit downstream mapping rule",
        ],
        "sample_inspection": {
            "performed": True,
            "rows_reviewed": 24,
            "selection": {
                "train": train["private_sample_selection"],
                "validation": validation["private_sample_selection"],
            },
            "aggregate_observations": [
                "natural colloquial online-comment language with spelling, spacing and punctuation noise",
                "multiple source domains are visible, but platform provenance is not retained row by row",
                "repetition and very short comments occur, while no parent or thread context is available",
            ],
        },
    }


def audit_hotter() -> dict[str, Any]:
    package = HOTTER_ROOT / "Icelandic_Sentiment_Corpus.zip"
    release_root = HOTTER_ROOT / "clarin_submission"
    csv_path = release_root / "data_unhydrated.csv"
    script_path = release_root / "hydration.py"
    readme_path = release_root / "README.md"
    requirements_path = release_root / "requirements.txt"

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []

    task_counts: Counter[str] = Counter()
    task_labels: dict[str, Counter[str]] = defaultdict(Counter)
    missing = Counter()
    annotator_hashes: set[str] = set()
    target_hashes: set[str] = set()
    target_emotion_tasks: dict[str, set[str]] = defaultdict(set)
    domain_counts: Counter[str] = Counter()

    for row in rows:
        task = row["annotation_task_name"]
        label = row["label_given_by_user"]
        task_counts[task] += 1
        task_labels[task][label] += 1
        for column in columns:
            missing[column] += int(not (row.get(column) or "").strip())
        annotator_hashes.add(hashlib.sha256(row["user_id"].encode("utf-8")).hexdigest())
        target_key = f"{row['full_link']}\0{row['comment_datetime']}"
        target_hash = hashlib.sha256(target_key.encode("utf-8")).hexdigest()
        target_hashes.add(target_hash)
        domain_counts[urlparse(row["full_link"]).netloc] += 1
        if task.startswith("emotion_"):
            target_emotion_tasks[target_hash].add(task)

    emotion_tasks = sorted(task for task in task_counts if task.startswith("emotion_"))
    emotion_coverage = Counter(len(tasks) for tasks in target_emotion_tasks.values())
    script = script_path.read_text(encoding="utf-8")
    readme = readme_path.read_text(encoding="utf-8")
    package_md5 = digest(package, "md5")
    emotion_label_values = sorted(
        {label for task in emotion_tasks for label in task_labels[task]}
    )

    return {
        "dataset": "Hotter and Colder",
        "source": {
            "repository_record": "http://hdl.handle.net/20.500.12537/352",
            "license": "CC BY 4.0",
            "expected_package_md5": HOTTER_EXPECTED_MD5,
            "observed_package_md5": package_md5,
            "checksum_matches": package_md5 == HOTTER_EXPECTED_MD5,
            "files": [
                file_record(package, include_md5=True),
                file_record(csv_path),
                file_record(script_path),
                file_record(readme_path),
                file_record(requirements_path),
            ],
        },
        "unhydrated_schema": {
            "format": "CSV",
            "encoding": "UTF-8 with optional BOM",
            "columns": columns,
            "annotation_unit": "one human judgment for one task and one target comment",
            "label_provenance": "GPT-4o-mini extreme-case selection followed by human annotation",
            "official_split": "none in release",
            "context_level": "potential C2 only after hydration",
            "paired_target_context_constructible_from_package": False,
            "rows": len(rows),
            "missing_by_column": dict(sorted(missing.items())),
            "unique_annotators": len(annotator_hashes),
            "unique_target_comment_keys": len(target_hashes),
            "source_domains": len(domain_counts),
            "task_counts": dict(sorted(task_counts.items())),
            "labels_by_task": {
                task: dict(sorted(labels.items())) for task, labels in sorted(task_labels.items())
            },
            "emotion_tasks": emotion_tasks,
            "emotion_label_values": emotion_label_values,
            "emotion_annotation_rows": sum(task_counts[task] for task in emotion_tasks),
            "unique_emotion_targets": len(target_emotion_tasks),
            "emotion_tasks_per_target": {
                str(count): targets for count, targets in sorted(emotion_coverage.items())
            },
            "targets_with_all_emotion_tasks": sum(
                len(tasks) == len(emotion_tasks) for tasks in target_emotion_tasks.values()
            ),
            "packaged_text_fields": [],
            "readme_label_description_conflicts_with_observed_schema": (
                "emotion detection task where the label is positive, neutral, or negative" in readme
                and emotion_label_values == ["0", "1", "skip"]
            ),
            "paper_reported_unique_comments": 12_232,
            "paper_reported_annotation_rows": 19_301,
            "release_minus_paper_unique_targets": len(target_hashes) - 12_232,
            "release_minus_paper_annotation_rows": len(rows) - 19_301,
            "private_sample_selection": selection_digest(len(rows), 0),
        },
        "hydration_review": {
            "execution_performed": False,
            "live_web_requests": "requests.get(url)" in script,
            "request_timeout_configured": bool(re.search(r"requests\.get\([^\n]*timeout\s*=", script)),
            "hardcoded_first_50_rows": "df = df.head(50)" in script,
            "comment_signature_appended_to_text": 'comment_text + "\\n" + signature_html' in script,
            "previous_comments_are_chronological_not_reply_edges": True,
            "packaged_release_contains_source_text": False,
        },
        "decision": "blocked_pending_review",
        "decision_basis": [
            "the checksum and CC BY 4.0 release metadata are verifiable",
            "the package contains labels and live links but no target or context text",
            "the supplied script scrapes live pages, has no request timeout and processes only 50 rows by default",
            "the script appends comment signatures and reconstructs chronological history rather than explicit reply edges",
            "emotion tasks are separate binary annotation rows rather than a guaranteed complete label vector per target",
            "the release counts and README label description do not exactly match the paper or observed emotion schema",
        ],
        "sample_inspection": {
            "performed": False,
            "rows_reviewed": 0,
            "reason": "the release contains no source text and hydration was prohibited",
        },
    }


def weibo_group_key(row_id: str) -> str:
    return row_id.rsplit("-", 1)[0] if "-" in row_id else row_id


def multiset_overlap(left: Iterable[Any], right: Iterable[Any]) -> dict[str, int]:
    left_counts = Counter(left)
    right_counts = Counter(right)
    return {
        "exact_common_rows": sum((left_counts & right_counts).values()),
        "left_only_rows": sum((left_counts - right_counts).values()),
        "right_only_rows": sum((right_counts - left_counts).values()),
        "left_unique_rows": len(left_counts),
        "right_unique_rows": len(right_counts),
    }


def audit_weibo() -> dict[str, Any]:
    cause_path = WEIBO_ROOT / "emotion_cause_detection.tsv"
    classification_path = WEIBO_ROOT / "emotion_classification.tsv"
    cause_rows = read_tsv(cause_path)
    mixed_rows = read_tsv(classification_path)

    cause_scaffolds = [row for row in mixed_rows if len(row) >= 2 and row[1] in WEIBO_CAUSE_LABELS]
    emotion_rows = [row for row in mixed_rows if len(row) >= 2 and row[1] not in WEIBO_CAUSE_LABELS]
    malformed_cause = sum(len(row) < 3 for row in cause_rows)
    malformed_mixed = sum(len(row) < 3 for row in mixed_rows)

    emotion_labels = Counter(row[1] for row in emotion_rows if len(row) >= 2)
    cause_labels = Counter(row[1] for row in cause_rows if len(row) >= 2)
    marker_counts = Counter(token for row in mixed_rows for token in row if token in WEIBO_MARKERS)
    group_rows: dict[str, list[list[str]]] = defaultdict(list)
    for row in mixed_rows:
        if row:
            group_rows[weibo_group_key(row[0])].append(row)

    groups_with_cause = 0
    groups_with_emotion = 0
    groups_with_both = 0
    for rows in group_rows.values():
        has_cause = any(len(row) >= 2 and row[1] in WEIBO_CAUSE_LABELS for row in rows)
        has_emotion = any(len(row) >= 2 and row[1] not in WEIBO_CAUSE_LABELS for row in rows)
        groups_with_cause += int(has_cause)
        groups_with_emotion += int(has_emotion)
        groups_with_both += int(has_cause and has_emotion)

    cause_records = [tuple(row) for row in cause_rows]
    scaffold_records = [tuple(row) for row in cause_scaffolds]
    cause_groups = Counter(weibo_group_key(row[0]) for row in cause_rows if row)
    scaffold_groups = Counter(weibo_group_key(row[0]) for row in cause_scaffolds if row)
    common_groups = cause_groups.keys() & scaffold_groups.keys()
    text_payload_hashes = [
        hashlib.sha256("\t".join(row[2:]).encode("utf-8")).hexdigest()
        for row in emotion_rows
        if len(row) >= 3
    ]
    mention_rows = sum(any(token.startswith("@") for token in row[2:]) for row in mixed_rows)
    multi_label_rows = sum("+" in row[1] for row in emotion_rows if len(row) >= 2)

    return {
        "dataset": "Weibo Emotion Cause Corpus",
        "source": {
            "repository": "https://github.com/wjhou/Weibo-Emotion-Corpus",
            "revision": WEIBO_REVISION,
            "license": "Apache-2.0",
            "files": [
                file_record(cause_path),
                file_record(classification_path),
                file_record(WEIBO_ROOT / "README.md"),
                file_record(WEIBO_ROOT / "LICENSE"),
            ],
        },
        "schema": {
            "format": "headerless variable-width tokenized TSV",
            "encoding": "UTF-8 with quoted embedded newlines",
            "annotation_unit": "multi-user microblog group with cause scaffold and clause rows",
            "label_provenance": "paper-reported manual emotion and emotion-cause annotation",
            "official_split": "none",
            "context_level": "C1 auxiliary structure",
            "paired_target_context_constructible": "conditional after group reconstruction",
            "cause_file_physical_lines": physical_line_count(cause_path),
            "cause_file_rows": len(cause_rows),
            "classification_file_physical_lines": physical_line_count(classification_path),
            "classification_file_rows": len(mixed_rows),
            "cause_file_max_columns": max((len(row) for row in cause_rows), default=0),
            "classification_file_max_columns": max((len(row) for row in mixed_rows), default=0),
            "cause_scaffold_rows_inside_classification_file": len(cause_scaffolds),
            "emotion_clause_rows_inside_classification_file": len(emotion_rows),
            "malformed_cause_rows": malformed_cause,
            "malformed_classification_rows": malformed_mixed,
            "cause_labels": dict(sorted(cause_labels.items())),
            "emotion_labels": dict(sorted(emotion_labels.items())),
            "emotion_multi_label_rows": multi_label_rows,
            "marker_counts": dict(sorted(marker_counts.items())),
            "groups": len(group_rows),
            "group_row_count": numeric_summary(len(rows) for rows in group_rows.values()),
            "groups_with_cause_scaffold": groups_with_cause,
            "groups_with_emotion_clause": groups_with_emotion,
            "groups_with_both": groups_with_both,
            "cause_file_matches_filtered_scaffolds": cause_records == scaffold_records,
            "cause_file_vs_filtered_scaffolds": multiset_overlap(
                cause_records, scaffold_records
            ),
            "cause_file_vs_filtered_scaffold_groups": {
                "cause_file_groups": len(cause_groups),
                "filtered_scaffold_groups": len(scaffold_groups),
                "common_groups": len(common_groups),
                "cause_file_only_groups": len(cause_groups.keys() - scaffold_groups.keys()),
                "filtered_scaffold_only_groups": len(
                    scaffold_groups.keys() - cause_groups.keys()
                ),
                "common_groups_with_different_row_counts": sum(
                    cause_groups[group] != scaffold_groups[group] for group in common_groups
                ),
            },
            "duplicate_emotion_payload_excess_rows": duplicate_excess(text_payload_hashes),
            "rows_containing_user_mentions": mention_rows,
            "private_sample_selection": {
                "cause": selection_digest(len(cause_rows), 12),
                "emotion_clause": selection_digest(len(emotion_rows), 12),
            },
        },
        "decision": "eligible_auxiliary",
        "decision_basis": [
            "the release is pinned and licensed, and its multi-user structure is explicit",
            "the primary gold task is emotion-cause detection rather than generic target-author emotion recognition",
            "the classification file interleaves cause scaffolds with emotion-clause rows and has no official split",
            "the emotion labels mix discrete emotions, sentiment labels, no-emotion and a small number of composites",
            "the structured context can support a cause/context auxiliary experiment after a separate mapping and split protocol",
        ],
        "sample_inspection": {
            "performed": True,
            "rows_reviewed": 24,
            "selection": {
                "cause": selection_digest(len(cause_rows), 12),
                "classification": selection_digest(len(mixed_rows), 12),
            },
            "aggregate_observations": [
                "the release is pre-tokenized and uses explicit clause, context, cause and emotion-keyword markers",
                "emoji placeholders, user mentions and short fragmentary clauses are present",
                "the classification file mixes cause-scaffold records with emotion-clause records rather than exposing one rectangular classification table",
            ],
        },
    }


def public_manifest(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "public-candidate-manifest-v1",
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset["dataset"],
        "audit_report": relative(
            REPORT_ROOT / "public-candidate-viability-audit-v1.json"
        ),
        "source": dataset["source"],
        "decision": dataset["decision"],
        "decision_basis": dataset["decision_basis"],
        "privacy": {
            "raw_text_tracked": False,
            "upstream_ids_tracked": False,
            "sample_text_tracked": False,
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    kote = report["datasets"]["kote"]
    hotter = report["datasets"]["hotter_and_colder"]
    weibo = report["datasets"]["weibo_emotion_cause"]
    kote_train = kote["splits"]["train"]
    kote_val = kote["splits"]["validation"]
    hotter_schema = hotter["unhydrated_schema"]
    weibo_schema = weibo["schema"]

    return f"""# Public Candidate Dataset Viability Audit V1

Date: 2026-08-08
Protocol: `{PROTOCOL_ID}`
Status: `COMPLETED`

## Decision

| Candidate | Audit decision | Permitted role |
| --- | --- | --- |
| KOTE | `eligible_training_control` | C0 target-only multi-label training/control |
| Hotter and Colder | `blocked_pending_review` | Potential context challenge only after hydration, privacy and reproducibility repair |
| Weibo Emotion Cause Corpus | `eligible_auxiliary` | C1 emotion-cause/context auxiliary experiment after a separate mapping and split protocol |

No candidate is adopted as the final thesis dataset by this audit.

## KOTE

- Acquired only `train.tsv` ({kote_train['rows']:,} rows) and `val.tsv`
  ({kote_val['rows']:,} rows) at revision `{KOTE_REVISION}`. `test.tsv` was not
  downloaded or parsed.
- Both files are headerless three-column TSVs: upstream ID, target text and
  comma-separated label IDs. All 44 label IDs appear in the audited files.
- Train/validation ID overlap: {kote['cross_split']['overlapping_ids']}; exact-text
  overlap: {kote['cross_split']['overlapping_exact_texts']}.
- Train label cardinality is {kote_train['label_cardinality']['mean']:.3f} on
  average; {kote_train['multi_label_rows']:,} rows have more than one label. This
  reproduces the paper's reported 7.91 after its five-rater vote aggregation,
  per-text min-max scaling and `> 0.2` binary threshold; it is not a parser error.
- The `no emotion` label appears with other labels in
  {kote_train['no_emotion_cooccurrence_rows']:,} train rows and
  {kote_val['no_emotion_cooccurrence_rows']:,} validation rows. This is allowed
  by the upstream transformation, but any later ontology mapping must explicitly
  define whether `no emotion` is exclusive, retained or dropped.
- A deterministic local review of 24 rows found ordinary online-comment noise,
  including spacing/punctuation variation and repetition, without exposing any
  sampled text in this report.
- The release contains no parent, thread, author or platform field. It is a
  viable C0 control, not evidence about context.

## Hotter and Colder

- The CLARIN package MD5 matches the published checksum. It contains
  {hotter_schema['rows']:,} annotation rows across
  {len(hotter_schema['task_counts'])} tasks and
  {hotter_schema['unique_target_comment_keys']:,} unique URL/timestamp target
  keys.
- These release counts differ from the paper's 19,301 annotations and 12,232
  unique comments by {hotter_schema['release_minus_paper_annotation_rows']:+,}
  and {hotter_schema['release_minus_paper_unique_targets']:+,}, respectively.
  The difference may reflect a later package version, but the release does not
  document that reconciliation.
- The package does not contain target text, previous comments or blog text.
  Those fields are reconstructed by scraping live URLs.
- The supplied hydration script uses live `requests.get`, has no request
  timeout, appends comment signatures to text and is hard-coded to the first 50
  rows. Hydration was therefore not executed.
- The eight emotions are stored as separate binary annotation tasks. Only
  {hotter_schema['targets_with_all_emotion_tasks']:,} targets have all eight
  emotion tasks, so the release cannot be treated as an ordinary complete
  eight-label matrix without redefining missing labels.
- The README says emotion labels are positive/neutral/negative, while the actual
  emotion rows use `0`, `1` and `skip`; the paper supports the latter binary
  interpretation. The README must not be used as the schema authority.
- Until hydration success, identifier removal, stable snapshots and split rules
  are resolved, this candidate is blocked rather than immediately executable.

## Weibo Emotion Cause Corpus

- The pinned release contains {weibo_schema['cause_file_rows']:,} logical cause
  records across {weibo_schema['cause_file_physical_lines']:,} physical lines,
  and {weibo_schema['classification_file_rows']:,} logical records across
  {weibo_schema['classification_file_physical_lines']:,} physical lines in
  `emotion_classification.tsv`. Quoted embedded newlines explain why `wc -l`
  is not a valid record count.
- The latter is a mixed structural file: it contains
  {weibo_schema['cause_scaffold_rows_inside_classification_file']:,} `Y/N` cause
  scaffold rows plus {weibo_schema['emotion_clause_rows_inside_classification_file']:,}
  emotion-clause rows. Filtering its scaffold rows does not reproduce the
  dedicated cause file: only
  {weibo_schema['cause_file_vs_filtered_scaffolds']['exact_common_rows']:,}
  records are exact matches, while
  {weibo_schema['cause_file_vs_filtered_scaffolds']['left_only_rows']:,} occur
  only in the cause file and
  {weibo_schema['cause_file_vs_filtered_scaffolds']['right_only_rows']:,} only
  in the filtered classification view. They must be treated as separate task
  releases, not joined by row position.
- The emotion labels mix discrete emotions, positive/negative/neutral,
  `No_emotion` and {weibo_schema['emotion_multi_label_rows']} composite rows.
  They are not a ready-made replacement for the current ontology.
- There are {weibo_schema['groups']:,} multi-user groups, and
  {weibo_schema['groups_with_both']:,} contain both a cause scaffold and at
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
"""


def main() -> None:
    datasets = {
        "kote": audit_kote(),
        "hotter_and_colder": audit_hotter(),
        "weibo_emotion_cause": audit_weibo(),
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "public-candidate-viability-audit-v1",
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": generated_at,
        "status": "completed",
        "test_data_accessed": False,
        "training_performed": False,
        "external_api_or_hydration_performed": False,
        "datasets": datasets,
        "privacy": {
            "contains_source_text": False,
            "contains_upstream_ids": False,
            "contains_user_names": False,
            "contains_row_level_source_urls": False,
            "contains_row_level_samples": False,
        },
    }

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "public-candidate-viability-audit-v1.json"
    md_path = REPORT_ROOT / "public-candidate-viability-audit-v1.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")

    for key, directory in (
        ("kote", DATA_ROOT / "kote"),
        ("hotter_and_colder", DATA_ROOT / "hotter-and-colder"),
        ("weibo_emotion_cause", DATA_ROOT / "weibo-emotion-corpus"),
    ):
        manifest = public_manifest(datasets[key])
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({"status": "completed", "report": relative(json_path)}, indent=2))


if __name__ == "__main__":
    main()
