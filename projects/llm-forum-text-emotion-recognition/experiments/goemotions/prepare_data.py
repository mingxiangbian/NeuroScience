#!/usr/bin/env python3
"""Acquire and verify the DATA-GOE-V1 train/dev snapshot.

This script intentionally has no test-download path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL_ID = "DATA-GOE-V1"
SOURCE_REVISION = "8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0"
SOURCE_ROOT = (
    "https://raw.githubusercontent.com/google-research/google-research/"
    f"{SOURCE_REVISION}/goemotions/data"
)
EXPECTED_LABELS = (
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "neutral",
)
DOWNLOADS = {
    "emotions.txt": None,
    "train.tsv": 43_410,
    "dev.tsv": 5_426,
}
EXPECTED_TRAIN_DEV_TEXT_OVERLAP = {
    "unique_exact_texts": 41,
    "train_rows": 84,
    "dev_rows": 43,
    "dev_rows_with_matching_train_label_set": 33,
    "dev_rows_without_matching_train_label_set": 10,
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data" / "goemotions"


@dataclass(frozen=True)
class SplitSummary:
    rows: int
    unique_comment_ids: int
    duplicate_comment_ids: int
    duplicate_texts: int
    multi_label_rows: int
    label_cardinality: dict[str, int]
    label_occurrences: dict[str, int]
    comment_ids: frozenset[str]
    text_hashes: frozenset[bytes]
    text_row_counts: dict[bytes, int]
    text_label_pair_counts: dict[tuple[bytes, tuple[int, ...]], int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download and verify GoEmotions train/dev files pinned by "
            f"{PROTOCOL_ID}. The test split is never downloaded."
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help=f"Local data root (default: {DEFAULT_DATA_ROOT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload train/dev/labels even when local files exist.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def download_file(url: str, target: Path) -> None:
    part = target.with_name(f"{target.name}.part")
    part.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NeuroScience-GoEmotions-DATA-GOE-V1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with part.open("wb") as output:
                shutil.copyfileobj(response, output)
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)


def validate_labels(path: Path) -> dict[str, Any]:
    labels = tuple(path.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError(
            "emotions.txt does not match the frozen 28-label DATA-GOE-V1 order"
        )
    return {
        "count": len(labels),
        "ordered": list(labels),
        "sha256": sha256_file(path),
    }


def validate_split(path: Path, expected_rows: int) -> SplitSummary:
    comment_ids: set[str] = set()
    text_hashes: set[bytes] = set()
    text_row_counts: Counter[bytes] = Counter()
    text_label_pair_counts: Counter[tuple[bytes, tuple[int, ...]]] = Counter()
    duplicate_comment_ids = 0
    duplicate_texts = 0
    multi_label_rows = 0
    cardinality: Counter[int] = Counter()
    occurrences: Counter[int] = Counter()
    rows = 0

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 3:
                raise ValueError(
                    f"{path.name} row {row_number} has {len(row)} columns; expected 3"
                )
            text, encoded_labels, comment_id = row
            if not text:
                raise ValueError(f"{path.name} row {row_number} has empty text")
            if not encoded_labels:
                raise ValueError(f"{path.name} row {row_number} has no labels")
            if not comment_id:
                raise ValueError(f"{path.name} row {row_number} has empty comment ID")

            try:
                label_ids = tuple(int(value) for value in encoded_labels.split(","))
            except ValueError as error:
                raise ValueError(
                    f"{path.name} row {row_number} has a non-integer label"
                ) from error

            if len(label_ids) != len(set(label_ids)):
                raise ValueError(
                    f"{path.name} row {row_number} repeats a label ID"
                )
            if any(label_id < 0 or label_id >= len(EXPECTED_LABELS) for label_id in label_ids):
                raise ValueError(
                    f"{path.name} row {row_number} has a label outside 0..27"
                )

            if comment_id in comment_ids:
                duplicate_comment_ids += 1
            comment_ids.add(comment_id)

            text_hash = hashlib.sha256(text.encode("utf-8")).digest()
            if text_hash in text_hashes:
                duplicate_texts += 1
            text_hashes.add(text_hash)
            text_row_counts[text_hash] += 1
            text_label_pair_counts[(text_hash, label_ids)] += 1

            cardinality[len(label_ids)] += 1
            occurrences.update(label_ids)
            if len(label_ids) > 1:
                multi_label_rows += 1
            rows += 1

    if rows != expected_rows:
        raise ValueError(
            f"{path.name} has {rows:,} rows; expected {expected_rows:,}"
        )
    if duplicate_comment_ids:
        raise ValueError(
            f"{path.name} contains {duplicate_comment_ids} duplicate comment IDs"
        )

    return SplitSummary(
        rows=rows,
        unique_comment_ids=len(comment_ids),
        duplicate_comment_ids=duplicate_comment_ids,
        duplicate_texts=duplicate_texts,
        multi_label_rows=multi_label_rows,
        label_cardinality={
            str(key): value for key, value in sorted(cardinality.items())
        },
        label_occurrences={
            EXPECTED_LABELS[label_id]: occurrences[label_id]
            for label_id in range(len(EXPECTED_LABELS))
        },
        comment_ids=frozenset(comment_ids),
        text_hashes=frozenset(text_hashes),
        text_row_counts=dict(text_row_counts),
        text_label_pair_counts=dict(text_label_pair_counts),
    )


def file_record(path: Path, source_url: str, expected_rows: int | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": display_path(path),
        "source_url": source_url,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if expected_rows is not None:
        record["expected_rows"] = expected_rows
    return record


def split_record(summary: SplitSummary) -> dict[str, Any]:
    return {
        "rows": summary.rows,
        "unique_comment_ids": summary.unique_comment_ids,
        "duplicate_comment_ids": summary.duplicate_comment_ids,
        "duplicate_texts_within_split": summary.duplicate_texts,
        "multi_label_rows": summary.multi_label_rows,
        "label_cardinality": summary.label_cardinality,
        "label_occurrences": summary.label_occurrences,
    }


def validate_train_dev_boundary(
    train: SplitSummary, dev: SplitSummary
) -> dict[str, Any]:
    id_overlap = len(train.comment_ids & dev.comment_ids)
    if id_overlap:
        raise ValueError(
            f"train/dev contains {id_overlap} overlapping comment IDs"
        )

    overlapping_texts = train.text_hashes & dev.text_hashes
    train_rows = sum(train.text_row_counts[text_hash] for text_hash in overlapping_texts)
    dev_rows = sum(dev.text_row_counts[text_hash] for text_hash in overlapping_texts)
    matching_label_rows = 0
    different_label_rows = 0

    for pair, count in dev.text_label_pair_counts.items():
        text_hash, _ = pair
        if text_hash not in overlapping_texts:
            continue
        if pair in train.text_label_pair_counts:
            matching_label_rows += count
        else:
            different_label_rows += count

    observed = {
        "unique_exact_texts": len(overlapping_texts),
        "train_rows": train_rows,
        "dev_rows": dev_rows,
        "dev_rows_with_matching_train_label_set": matching_label_rows,
        "dev_rows_without_matching_train_label_set": different_label_rows,
    }
    if observed != EXPECTED_TRAIN_DEV_TEXT_OVERLAP:
        raise ValueError(
            "train/dev exact-text overlap differs from the reviewed frozen profile: "
            f"observed={observed}, expected={EXPECTED_TRAIN_DEV_TEXT_OVERLAP}"
        )

    return {
        "train_dev_comment_id_overlap": 0,
        "train_dev_exact_text_overlap": {
            **observed,
            "review_status": "reviewed_preserve_official_split",
            "interpretation": (
                "Different upstream comments can share identical short text; "
                "the official split is preserved for benchmark comparability."
            ),
        },
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    part = path.with_name(f"{path.name}.part")
    part.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(part, path)


def main() -> int:
    args = parse_args()
    data_root = args.data_root.resolve()
    official_dir = data_root / "official"
    test_path = official_dir / "test.tsv"

    if test_path.exists():
        raise RuntimeError(
            f"{test_path} exists, but {PROTOCOL_ID} requires test to remain absent"
        )

    official_dir.mkdir(parents=True, exist_ok=True)
    acquired_at = datetime.now(timezone.utc).isoformat()
    file_records: dict[str, dict[str, Any]] = {}

    for filename, expected_rows in DOWNLOADS.items():
        target = official_dir / filename
        source_url = f"{SOURCE_ROOT}/{filename}"
        if args.force or not target.exists():
            print(f"Downloading {filename} from pinned revision...", flush=True)
            download_file(source_url, target)
        else:
            print(f"Reusing existing {filename}; validation still required.", flush=True)
        file_records[filename] = file_record(target, source_url, expected_rows)

    labels = validate_labels(official_dir / "emotions.txt")
    train = validate_split(official_dir / "train.tsv", DOWNLOADS["train.tsv"])
    dev = validate_split(official_dir / "dev.tsv", DOWNLOADS["dev.tsv"])
    cross_split = validate_train_dev_boundary(train, dev)

    manifest = {
        "protocol_id": PROTOCOL_ID,
        "status": "verified",
        "generated_at_utc": acquired_at,
        "source": {
            "repository": "https://github.com/google-research/google-research",
            "revision": SOURCE_REVISION,
            "subdirectory": "goemotions/data",
        },
        "storage": {
            "data_root": display_path(data_root),
            "official_dir": display_path(official_dir),
            "raw_data_gitignored": True,
        },
        "files": file_records,
        "labels": labels,
        "splits": {
            "train": split_record(train),
            "dev": split_record(dev),
            "test": {
                "status": "not_acquired",
                "exists": False,
                "expected_rows": 5_427,
                "path": display_path(test_path),
            },
        },
        "cross_split": cross_split,
        "privacy": {
            "contains_raw_text": False,
            "contains_upstream_comment_ids": False,
        },
    }
    write_manifest(data_root / "manifest.json", manifest)

    print(
        "Verified DATA-GOE-V1: "
        f"train={train.rows:,}, dev={dev.rows:,}, labels={len(EXPECTED_LABELS)}, "
        "test=not acquired"
    )
    print(
        "Recorded reviewed data-quality warning: "
        f"{EXPECTED_TRAIN_DEV_TEXT_OVERLAP['unique_exact_texts']} exact texts "
        "occur in both train and dev; comment_id overlap=0."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
