#!/usr/bin/env python3
"""Independently verify closed-corpus parent counts with SQLite joins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


RAW_FILENAMES = ("goemotions_1.csv", "goemotions_2.csv", "goemotions_3.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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


def load_sqlite(connection: sqlite3.Connection, raw_dir: Path, split_paths: dict[str, Path]) -> None:
    connection.executescript(
        """
        CREATE TABLE raw_comments (
          id TEXT PRIMARY KEY,
          parent_id TEXT NOT NULL,
          usable_text INTEGER NOT NULL
        );
        CREATE TABLE filtered_targets (
          split TEXT NOT NULL,
          id TEXT NOT NULL,
          PRIMARY KEY (split, id)
        );
        """
    )
    for filename in RAW_FILENAMES:
        with (raw_dir / filename).open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                comment_id = normalize_comment_id(row["id"])
                text = row["text"].strip().lower()
                connection.execute(
                    "INSERT OR IGNORE INTO raw_comments VALUES (?, ?, ?)",
                    (comment_id, row["parent_id"].strip(), int(text not in {"", "[deleted]", "[removed]"})),
                )
    for split, path in split_paths.items():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle, delimiter="\t"):
                if len(row) != 3:
                    raise ValueError(f"{path}: expected 3 columns")
                connection.execute(
                    "INSERT INTO filtered_targets VALUES (?, ?)",
                    (split, normalize_comment_id(row[2])),
                )
    connection.commit()


def query_counts(connection: sqlite3.Connection, split: str) -> dict[str, int | float]:
    row = connection.execute(
        """
        SELECT
          COUNT(*) AS targets,
          SUM(r.id IS NOT NULL) AS target_matched_raw,
          SUM(r.id IS NULL) AS target_missing_from_raw,
          SUM(r.id IS NOT NULL AND r.parent_id = '') AS missing_parent_id,
          SUM(r.id IS NOT NULL AND r.parent_id LIKE 't3_%') AS submission_parent,
          SUM(r.id IS NOT NULL AND r.parent_id LIKE 't1_%') AS comment_parent,
          SUM(r.parent_id LIKE 't1_%' AND p.id IS NOT NULL AND p.usable_text = 1)
            AS comment_parent_in_raw_text_available,
          SUM(r.parent_id LIKE 't1_%' AND p.id IS NOT NULL AND p.usable_text = 0)
            AS comment_parent_in_raw_unusable_text,
          SUM(r.parent_id LIKE 't1_%' AND p.id IS NULL) AS comment_parent_not_in_raw,
          SUM(r.id IS NOT NULL AND r.parent_id <> ''
              AND r.parent_id NOT LIKE 't1_%' AND r.parent_id NOT LIKE 't3_%')
            AS unknown_parent_type,
          SUM(r.parent_id LIKE 't1_%' AND substr(r.parent_id, 4) = f.id) AS self_parent
        FROM filtered_targets f
        LEFT JOIN raw_comments r ON r.id = f.id
        LEFT JOIN raw_comments p
          ON r.parent_id LIKE 't1_%' AND p.id = substr(r.parent_id, 4)
        WHERE f.split = ?
        """,
        (split,),
    ).fetchone()
    keys = (
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
    )
    counts = {key: int(value or 0) for key, value in zip(keys, row)}
    counts["missing_parent_text_in_release"] = (
        counts["targets"] - counts["comment_parent_in_raw_text_available"]
    )
    counts["parent_text_available_rate"] = (
        counts["comment_parent_in_raw_text_available"] / counts["targets"]
    )
    counts["missing_parent_text_rate"] = (
        counts["missing_parent_text_in_release"] / counts["targets"]
    )
    return counts


def main() -> None:
    args = parse_args()
    script_path = Path(__file__)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    connection = sqlite3.connect(":memory:")
    load_sqlite(connection, args.raw_dir, {"train": args.train, "dev": args.dev})

    mismatches: list[dict[str, object]] = []
    verified: dict[str, dict[str, int | float]] = {}
    comparison_keys = (
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
    for split in ("train", "dev"):
        counts = query_counts(connection, split)
        verified[split] = counts
        reported = report["splits"][split]["counts"]
        for key in comparison_keys:
            if counts[key] != reported[key]:
                mismatches.append(
                    {"split": split, "field": key, "reported": reported[key], "verified": counts[key]}
                )

    output = {
        "status": "passed" if not mismatches else "failed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report": {"path": str(args.report), "sha256": sha256(args.report)},
        "implementation": {
            "filename": script_path.name,
            "sha256": sha256(script_path),
        },
        "method": "independent_sqlite_left_join",
        "verified_splits": verified,
        "mismatches": mismatches,
        "access_boundary": {
            "filtered_test_tsv_read": False,
            "filtered_test_membership_used": False,
            "raw_release_is_unpartitioned": True,
            "external_parent_source_used": False,
        },
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
