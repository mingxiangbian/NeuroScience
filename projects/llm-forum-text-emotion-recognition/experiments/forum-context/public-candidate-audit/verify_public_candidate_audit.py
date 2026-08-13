#!/usr/bin/env python3
"""Independently verify aggregate public-candidate audit claims."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


csv.field_size_limit(16 * 1024 * 1024)

PROTOCOL_ID = "DATA-FCTX-PUBLIC-AUDIT-V1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUDIT_ROOT = Path(__file__).resolve().parent
REPORT_PATH = AUDIT_ROOT / "reports/public-candidate-viability-audit-v1.json"
OUTPUT_PATH = AUDIT_ROOT / "reports/public-candidate-viability-audit-v1-verification.json"
DATA_ROOT = PROJECT_ROOT / "data"


def read_tsv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, delimiter="\t"))


def digest(path: Path, algorithm: str = "sha256") -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def physical_lines(path: Path) -> int:
    count = 0
    last_byte = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    return count + int(path.stat().st_size > 0 and last_byte != b"\n")


def check(
    checks: list[dict[str, Any]],
    name: str,
    observed: Any,
    expected: Any,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": observed == expected,
            "observed": observed,
            "expected": expected,
        }
    )


def verify_kote(report: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    root = DATA_ROOT / "kote/official"
    train = read_tsv(root / "train.tsv")
    validation = read_tsv(root / "val.tsv")
    audited = report["datasets"]["kote"]

    check(checks, "kote.test_absent", (root / "test.tsv").exists(), False)
    check(checks, "kote.train_rows", len(train), audited["splits"]["train"]["rows"])
    check(
        checks,
        "kote.validation_rows",
        len(validation),
        audited["splits"]["validation"]["rows"],
    )
    check(checks, "kote.train_all_three_columns", all(len(row) == 3 for row in train), True)
    check(
        checks,
        "kote.validation_all_three_columns",
        all(len(row) == 3 for row in validation),
        True,
    )

    cardinalities = [len(row[2].split(",")) for row in train]
    check(
        checks,
        "kote.train_cardinality_mean",
        round(sum(cardinalities) / len(cardinalities), 6),
        audited["splits"]["train"]["label_cardinality"]["mean"],
    )
    check(
        checks,
        "kote.cross_split_id_overlap",
        len({row[0] for row in train} & {row[0] for row in validation}),
        audited["cross_split"]["overlapping_ids"],
    )


def verify_hotter(report: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    root = DATA_ROOT / "hotter-and-colder/official"
    package = root / "Icelandic_Sentiment_Corpus.zip"
    release = root / "clarin_submission"
    csv_path = release / "data_unhydrated.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    audited = report["datasets"]["hotter_and_colder"]
    schema = audited["unhydrated_schema"]
    task_counts = Counter(row["annotation_task_name"] for row in rows)
    target_keys = {(row["full_link"], row["comment_datetime"]) for row in rows}
    emotion_values = sorted(
        {
            row["label_given_by_user"]
            for row in rows
            if row["annotation_task_name"].startswith("emotion_")
        }
    )

    check(checks, "hotter.package_md5", digest(package, "md5"), audited["source"]["expected_package_md5"])
    check(checks, "hotter.annotation_rows", len(rows), schema["rows"])
    check(checks, "hotter.task_count", len(task_counts), len(schema["task_counts"]))
    check(checks, "hotter.unique_target_keys", len(target_keys), schema["unique_target_comment_keys"])
    check(checks, "hotter.emotion_label_values", emotion_values, schema["emotion_label_values"])
    check(
        checks,
        "hotter.no_hydrated_output",
        any(path.name.startswith("data_hydrated") for path in release.iterdir()),
        False,
    )


def verify_weibo(report: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    root = DATA_ROOT / "weibo-emotion-corpus/official"
    cause_path = root / "emotion_cause_detection.tsv"
    classification_path = root / "emotion_classification.tsv"
    cause = read_tsv(cause_path)
    mixed = read_tsv(classification_path)
    scaffolds = [row for row in mixed if len(row) >= 2 and row[1] in {"N", "Y"}]
    emotions = [row for row in mixed if len(row) >= 2 and row[1] not in {"N", "Y"}]
    audited = report["datasets"]["weibo_emotion_cause"]["schema"]

    cause_records = Counter(tuple(row) for row in cause)
    scaffold_records = Counter(tuple(row) for row in scaffolds)
    overlap = {
        "exact_common_rows": sum((cause_records & scaffold_records).values()),
        "left_only_rows": sum((cause_records - scaffold_records).values()),
        "right_only_rows": sum((scaffold_records - cause_records).values()),
        "left_unique_rows": len(cause_records),
        "right_unique_rows": len(scaffold_records),
    }

    check(checks, "weibo.cause_logical_records", len(cause), audited["cause_file_rows"])
    check(checks, "weibo.cause_physical_lines", physical_lines(cause_path), audited["cause_file_physical_lines"])
    check(
        checks,
        "weibo.classification_logical_records",
        len(mixed),
        audited["classification_file_rows"],
    )
    check(
        checks,
        "weibo.classification_physical_lines",
        physical_lines(classification_path),
        audited["classification_file_physical_lines"],
    )
    check(
        checks,
        "weibo.scaffold_records",
        len(scaffolds),
        audited["cause_scaffold_rows_inside_classification_file"],
    )
    check(
        checks,
        "weibo.emotion_records",
        len(emotions),
        audited["emotion_clause_rows_inside_classification_file"],
    )
    check(checks, "weibo.cross_file_multiset_overlap", overlap, audited["cause_file_vs_filtered_scaffolds"])


def verify_manifests_and_git(report: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    candidates = {
        "kote": "kote",
        "hotter-and-colder": "hotter_and_colder",
        "weibo-emotion-corpus": "weibo_emotion_cause",
    }
    for directory, report_key in candidates.items():
        manifest_path = DATA_ROOT / directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        audited = report["datasets"][report_key]
        check(checks, f"{directory}.manifest_protocol", manifest["protocol_id"], PROTOCOL_ID)
        check(checks, f"{directory}.manifest_decision", manifest["decision"], audited["decision"])

        raw_files = [
            path for path in (DATA_ROOT / directory / "official").rglob("*") if path.is_file()
        ]
        relative_raw_files = [str(path.relative_to(PROJECT_ROOT)) for path in raw_files]
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            input="\n".join(relative_raw_files) + "\n",
            text=True,
        )
        ignored_files = {line for line in result.stdout.splitlines() if line}
        check(
            checks,
            f"{directory}.all_raw_files_gitignored",
            len(ignored_files),
            len(relative_raw_files),
        )


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    check(checks, "report.protocol", report["protocol_id"], PROTOCOL_ID)
    check(checks, "report.status", report["status"], "completed")
    check(checks, "report.test_data_accessed", report["test_data_accessed"], False)
    check(checks, "report.training_performed", report["training_performed"], False)
    check(
        checks,
        "report.external_api_or_hydration_performed",
        report["external_api_or_hydration_performed"],
        False,
    )
    check(checks, "report.privacy", all(value is False for value in report["privacy"].values()), True)

    verify_kote(report, checks)
    verify_hotter(report, checks)
    verify_weibo(report, checks)
    verify_manifests_and_git(report, checks)

    failures = [item for item in checks if not item["passed"]]
    output = {
        "schema_version": "public-candidate-viability-audit-verification-v1",
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not failures else "failed",
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failures),
        "mismatches": failures,
        "checks": checks,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in ("status", "checks_total", "checks_passed")}, indent=2))
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
