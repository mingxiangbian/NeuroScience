#!/usr/bin/env python3
"""Audit parent-text coverage using only the official GoEmotions release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


RAW_FILENAMES = (
    "goemotions_1.csv",
    "goemotions_2.csv",
    "goemotions_3.csv",
)
RAW_URL_PREFIX = (
    "https://storage.googleapis.com/gresearch/goemotions/"
    "data/full_dataset/"
)
REQUIRED_RAW_COLUMNS = {
    "text",
    "id",
    "subreddit",
    "link_id",
    "parent_id",
    "created_utc",
}
CONSISTENCY_FIELDS = ("text", "parent_id", "link_id", "subreddit", "created_utc")
UNUSABLE_PARENT_TEXT = {"", "[deleted]", "[removed]"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_comment_id(value: str) -> str:
    value = value.strip()
    return value[3:] if value.startswith("t1_") else value


def parent_kind(value: str) -> str:
    if not value:
        return "missing"
    if value.startswith("t1_"):
        return "comment"
    if value.startswith("t3_"):
        return "submission"
    return "unknown"


def load_raw(raw_dir: Path) -> tuple[dict[str, dict[str, str]], dict[str, object]]:
    comments: dict[str, dict[str, str]] = {}
    conflict_ids: set[str] = set()
    conflict_fields: Counter[str] = Counter()
    source_records: list[dict[str, object]] = []
    raw_rows = 0

    for filename in RAW_FILENAMES:
        path = raw_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        source_records.append(
            {
                "filename": filename,
                "source_url": RAW_URL_PREFIX + filename,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing_columns = REQUIRED_RAW_COLUMNS - set(reader.fieldnames or ())
            if missing_columns:
                raise ValueError(f"{filename}: missing columns {sorted(missing_columns)}")
            for row in reader:
                raw_rows += 1
                comment_id = normalize_comment_id(row["id"])
                if not comment_id:
                    raise ValueError(f"{filename}: empty comment id at row {raw_rows + 1}")
                record = {field: row[field].strip() for field in CONSISTENCY_FIELDS}
                previous = comments.get(comment_id)
                if previous is None:
                    comments[comment_id] = record
                    continue
                for field in CONSISTENCY_FIELDS:
                    if previous[field] != record[field]:
                        conflict_ids.add(comment_id)
                        conflict_fields[field] += 1

    critical_conflicts = conflict_fields["text"] + conflict_fields["parent_id"]
    if critical_conflicts:
        raise ValueError(
            "raw duplicate rows disagree on text or parent_id: "
            f"{critical_conflicts} conflicting field values"
        )

    metadata = {
        "files": source_records,
        "rater_annotation_rows": raw_rows,
        "unique_comments": len(comments),
        "duplicate_annotation_rows": raw_rows - len(comments),
        "conflicting_unique_ids": len(conflict_ids),
        "conflict_field_occurrences": dict(sorted(conflict_fields.items())),
    }
    return comments, metadata


def audit_split(path: Path, split: str, raw: dict[str, dict[str, str]]) -> dict[str, object]:
    counts: Counter[str] = Counter()
    target_ids: set[str] = set()
    parent_ids: set[str] = set()
    available_parent_ids: set[str] = set()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 3:
                raise ValueError(f"{path}: row {row_number} has {len(row)} columns")
            target_id = normalize_comment_id(row[2])
            if not target_id or target_id in target_ids:
                raise ValueError(f"{path}: empty or duplicate target id at row {row_number}")
            target_ids.add(target_id)
            counts["targets"] += 1

            target = raw.get(target_id)
            if target is None:
                counts["target_missing_from_raw"] += 1
                continue
            counts["target_matched_raw"] += 1

            parent_id = target["parent_id"]
            kind = parent_kind(parent_id)
            if kind == "missing":
                counts["missing_parent_id"] += 1
                continue
            if kind == "submission":
                counts["submission_parent"] += 1
                continue
            if kind == "unknown":
                counts["unknown_parent_type"] += 1
                continue

            counts["comment_parent"] += 1
            normalized_parent_id = normalize_comment_id(parent_id)
            parent_ids.add(normalized_parent_id)
            parent = raw.get(normalized_parent_id)
            if parent is None:
                counts["comment_parent_not_in_raw"] += 1
                continue
            if parent["text"].strip().lower() in UNUSABLE_PARENT_TEXT:
                counts["comment_parent_in_raw_unusable_text"] += 1
                continue
            counts["comment_parent_in_raw_text_available"] += 1
            available_parent_ids.add(normalized_parent_id)
            if normalized_parent_id == target_id:
                counts["self_parent"] += 1

    targets = counts["targets"]
    available = counts["comment_parent_in_raw_text_available"]
    counts["missing_parent_text_in_release"] = targets - available
    result = {key: counts[key] for key in (
        "targets",
        "target_matched_raw",
        "target_missing_from_raw",
        "missing_parent_id",
        "submission_parent",
        "comment_parent",
        "comment_parent_in_raw_text_available",
        "comment_parent_in_raw_unusable_text",
        "comment_parent_not_in_raw",
        "unknown_parent_type",
        "self_parent",
        "missing_parent_text_in_release",
    )}
    result.update(
        {
            "unique_comment_parent_ids": len(parent_ids),
            "unique_available_parent_ids": len(available_parent_ids),
            "parent_text_available_rate": available / targets if targets else 0.0,
            "missing_parent_text_rate": (targets - available) / targets if targets else 0.0,
        }
    )
    return {
        "split": split,
        "source": {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        },
        "counts": result,
    }


def aggregate(split_results: list[dict[str, object]]) -> dict[str, object]:
    integer_keys = (
        "targets",
        "target_matched_raw",
        "target_missing_from_raw",
        "missing_parent_id",
        "submission_parent",
        "comment_parent",
        "comment_parent_in_raw_text_available",
        "comment_parent_in_raw_unusable_text",
        "comment_parent_not_in_raw",
        "unknown_parent_type",
        "self_parent",
        "missing_parent_text_in_release",
    )
    combined = {
        key: sum(int(result["counts"][key]) for result in split_results)
        for key in integer_keys
    }
    targets = combined["targets"]
    available = combined["comment_parent_in_raw_text_available"]
    combined["parent_text_available_rate"] = available / targets if targets else 0.0
    combined["missing_parent_text_rate"] = (
        combined["missing_parent_text_in_release"] / targets if targets else 0.0
    )
    return combined


def main() -> None:
    args = parse_args()
    script_path = Path(__file__)
    raw, raw_metadata = load_raw(args.raw_dir)
    split_results = [
        audit_split(args.train, "train", raw),
        audit_split(args.dev, "dev", raw),
    ]
    report = {
        "protocol_id": "DATA-FCTX-CJ-V1",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "path": str(args.protocol),
            "sha256": sha256(args.protocol),
        },
        "implementation": {
            "filename": script_path.name,
            "sha256": sha256(script_path),
        },
        "raw_release": raw_metadata,
        "splits": {result["split"]: result for result in split_results},
        "aggregate": aggregate(split_results),
        "access_boundary": {
            "filtered_test_tsv_read": False,
            "filtered_test_membership_used": False,
            "raw_release_is_unpartitioned": True,
            "raw_emotion_labels_used": False,
            "reddit_api_called": False,
            "reddit_page_scraped": False,
            "third_party_archive_used": False,
            "missing_parents_backfilled": False,
        },
        "privacy": {
            "raw_text_processed_for_parent_availability": True,
            "contains_comment_text": False,
            "contains_target_ids": False,
            "contains_parent_ids": False,
            "contains_usernames": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
