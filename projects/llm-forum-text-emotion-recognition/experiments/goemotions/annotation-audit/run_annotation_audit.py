#!/usr/bin/env python3
"""Stream and audit raw GoEmotions annotations for a frozen train-only slice."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {"commit": commit, "dirty": bool(dirty.strip())}


class DigestingRawReader(io.RawIOBase):
    def __init__(self, response: Any) -> None:
        self.response = response
        self.sha256 = hashlib.sha256()
        self.md5 = hashlib.md5()  # noqa: S324 - source integrity, not security.
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        chunk = self.response.read(len(buffer))
        if not chunk:
            return 0
        size = len(chunk)
        buffer[:size] = chunk
        self.sha256.update(chunk)
        self.md5.update(chunk)
        self.bytes_read += size
        return size


def load_frozen_slice(config: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    selection = config["selection"]
    train_path = resolve_project_path(selection["train_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    test_path = resolve_project_path(selection["simplified_test_path"])
    if test_path.exists():
        raise RuntimeError("Simplified GoEmotions test.tsv exists; EXP-035 is not authorized")
    if sha256_file(train_path) != selection["train_sha256"]:
        raise RuntimeError("Frozen train.tsv hash changed")
    if sha256_file(labels_path) != selection["labels_sha256"]:
        raise RuntimeError("Frozen emotions.txt hash changed")

    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if labels != config["labels"] or labels.index("neutral") != 27:
        raise RuntimeError("Frozen label order changed")

    selected: list[dict[str, Any]] = []
    row_count = 0
    with train_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            row_count = row_number
            if len(row) != 3:
                raise RuntimeError(f"Malformed train row {row_number}")
            text, encoded_labels, comment_id = row
            label_ids = [int(value) for value in encoded_labels.split(",")]
            if 27 in label_ids and len(label_ids) > 1:
                selected.append(
                    {
                        "comment_id": comment_id,
                        "example_hash": sha256_text(comment_id),
                        "gold_label_ids": label_ids,
                        "gold_labels": [labels[value] for value in label_ids],
                        "source_train_row": row_number,
                        "text": text,
                        "text_sha256": sha256_text(text),
                    }
                )
    row_hash = sha256_text(
        ",".join(str(record["source_train_row"]) for record in selected)
    )
    if (
        row_count != selection["train_rows"]
        or len(selected) != selection["expected_rows"]
        or row_hash != selection["source_train_rows_sha256"]
        or len({record["comment_id"] for record in selected}) != len(selected)
    ):
        raise RuntimeError("Frozen train audit slice changed")
    return labels, selected


def expected_header(labels: list[str]) -> list[str]:
    return [
        "text",
        "id",
        "author",
        "subreddit",
        "link_id",
        "parent_id",
        "created_utc",
        "rater_id",
        "example_very_unclear",
        *labels,
    ]


def stream_source(
    source: dict[str, Any],
    labels: list[str],
    target_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = urllib.request.Request(
        source["url"],
        headers={"Accept-Encoding": "identity", "User-Agent": "NeuroScience-EXP-035/1"},
    )
    matched: list[dict[str, Any]] = []
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        content_length = int(response.headers.get("Content-Length", "-1"))
        etag = response.headers.get("ETag", "").strip('"')
        if content_length != source["content_length"] or etag != source["etag"]:
            raise RuntimeError(f"HTTP identity changed for {source['name']}")

        raw = DigestingRawReader(response)
        buffered = io.BufferedReader(raw, buffer_size=1024 * 1024)
        text_stream = io.TextIOWrapper(buffered, encoding="utf-8", newline="")
        reader = csv.reader(text_stream)
        header = next(reader)
        if header != expected_header(labels):
            raise RuntimeError(f"Unexpected raw schema in {source['name']}")
        index = {name: position for position, name in enumerate(header)}
        source_rows = 0
        for source_line, row in enumerate(reader, start=2):
            source_rows += 1
            if len(row) != len(header):
                raise RuntimeError(f"Malformed {source['name']} row {source_line}")
            comment_id = row[index["id"]]
            target = target_by_id.get(comment_id)
            if target is None:
                continue
            if row[index["text"]] != target["text"]:
                raise RuntimeError(f"Text mismatch for train row {target['source_train_row']}")
            binary: list[int] = []
            for label in labels:
                value = row[index[label]]
                if value not in {"0", "1"}:
                    raise RuntimeError(f"Invalid raw label value in {source['name']}")
                binary.append(int(value))
            unclear_raw = row[index["example_very_unclear"]].strip().lower()
            if unclear_raw not in {"true", "false"}:
                raise RuntimeError(f"Invalid unclear value in {source['name']}")
            rater_hash = sha256_text(row[index["rater_id"]])
            matched.append(
                {
                    "comment_id": comment_id,
                    "example_hash": target["example_hash"],
                    "labels": binary,
                    "rater_hash": rater_hash,
                    "source_file": source["name"],
                    "source_line": source_line,
                    "source_train_row": target["source_train_row"],
                    "text_sha256": target["text_sha256"],
                    "unclear": unclear_raw == "true",
                }
            )
        text_stream.detach()

    observed_md5 = base64.b64encode(raw.md5.digest()).decode("ascii")
    if raw.bytes_read != source["content_length"] or observed_md5 != source["md5_base64"]:
        raise RuntimeError(f"Downloaded bytes changed for {source['name']}")
    manifest = {
        "bytes": raw.bytes_read,
        "etag": source["etag"],
        "last_modified": source["last_modified"],
        "matched_annotation_rows": len(matched),
        "md5_base64": observed_md5,
        "name": source["name"],
        "raw_annotation_rows": source_rows,
        "sha256": raw.sha256.hexdigest(),
        "url": source["url"],
    }
    return matched, manifest


def aggregate_rows(
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    labels: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_id[record["comment_id"]].append(record)

    row_audit: list[dict[str, Any]] = []
    rater_distribution: Counter[int] = Counter()
    unclear_distribution: Counter[int] = Counter()
    neutral_vote_distribution: Counter[int] = Counter()
    same_rater_distribution: Counter[int] = Counter()
    patterns: Counter[tuple[int, int, int, int, int]] = Counter()
    per_emotion: dict[str, Counter[str]] = defaultdict(Counter)
    duplicate_comment_rater = 0
    reproduction_mismatches = 0

    for target in selected:
        annotations = by_id.get(target["comment_id"], [])
        if not annotations:
            raise RuntimeError(f"Missing raw annotations for train row {target['source_train_row']}")
        rater_keys = [record["rater_hash"] for record in annotations]
        duplicate_comment_rater += len(rater_keys) - len(set(rater_keys))
        votes = [sum(record["labels"][index] for record in annotations) for index in range(len(labels))]
        derived_ids = [index for index, count in enumerate(votes) if count >= 2]
        derived_matches = derived_ids == target["gold_label_ids"]
        reproduction_mismatches += int(not derived_matches)
        same_rater_count = sum(
            1
            for record in annotations
            if record["labels"][27] == 1 and sum(record["labels"][:27]) > 0
        )
        unclear_count = sum(int(record["unclear"]) for record in annotations)
        rater_count = len(annotations)
        neutral_votes = votes[27]
        emotion_votes = [votes[index] for index in target["gold_label_ids"] if index != 27]
        max_emotion_votes = max(emotion_votes)
        aggregation_only = same_rater_count == 0
        row = {
            "aggregation_only": aggregation_only,
            "derived_labels_match": derived_matches,
            "example_hash": target["example_hash"],
            "gold_cardinality": len(target["gold_label_ids"]),
            "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
            "gold_labels": "|".join(target["gold_labels"]),
            "max_emotion_votes": max_emotion_votes,
            "neutral_votes": neutral_votes,
            "rater_count": rater_count,
            "same_rater_coselection_count": same_rater_count,
            "source_train_row": target["source_train_row"],
            "unclear_count": unclear_count,
        }
        row_audit.append(row)
        rater_distribution[rater_count] += 1
        unclear_distribution[unclear_count] += 1
        neutral_vote_distribution[neutral_votes] += 1
        same_rater_distribution[same_rater_count] += 1
        patterns[(rater_count, neutral_votes, max_emotion_votes, same_rater_count, unclear_count)] += 1
        for label_id in target["gold_label_ids"]:
            if label_id == 27:
                continue
            label = labels[label_id]
            per_emotion[label]["rows"] += 1
            per_emotion[label]["aggregation_only_rows"] += int(aggregation_only)
            per_emotion[label]["same_rater_coselection_rows"] += int(not aggregation_only)
            per_emotion[label]["any_unclear_rows"] += int(unclear_count > 0)

    if len(by_id) != len(selected) or duplicate_comment_rater:
        raise RuntimeError("Raw annotation join contains missing or duplicate comment/rater keys")
    if reproduction_mismatches:
        raise RuntimeError("Official >=2-rater aggregation does not reproduce simplified labels")

    aggregation_only_rows = sum(int(row["aggregation_only"]) for row in row_audit)
    same_rater_rows = len(row_audit) - aggregation_only_rows
    any_unclear_rows = sum(int(row["unclear_count"] > 0) for row in row_audit)
    decision = (
        "annotation_aggregation_is_primary_for_target_structure"
        if aggregation_only_rows / len(row_audit) > 0.5
        else "same_rater_coselection_is_not_a_minority"
    )
    summary = {
        "any_unclear_rows": any_unclear_rows,
        "any_unclear_rate": any_unclear_rows / len(row_audit),
        "decision": decision,
        "duplicate_comment_rater_pairs": duplicate_comment_rater,
        "official_threshold_reproduction_mismatches": reproduction_mismatches,
        "rows": len(row_audit),
        "aggregation_only_rows": aggregation_only_rows,
        "aggregation_only_rate": aggregation_only_rows / len(row_audit),
        "same_rater_coselection_rows": same_rater_rows,
        "same_rater_coselection_rate": same_rater_rows / len(row_audit),
        "rater_count_distribution": dict(sorted(rater_distribution.items())),
        "unclear_count_distribution": dict(sorted(unclear_distribution.items())),
        "neutral_vote_distribution": dict(sorted(neutral_vote_distribution.items())),
        "same_rater_coselection_count_distribution": dict(sorted(same_rater_distribution.items())),
        "transport_boundary": {
            "nonmatching_raw_records_persisted": 0,
            "raw_archive_objects_streamed": 3,
            "simplified_dev_accessed": False,
            "simplified_test_accessed": False,
            "simplified_test_exists": False,
            "train_allowlist_only_persisted": True,
        },
    }
    pattern_rows = [
        {
            "count": count,
            "max_emotion_votes": key[2],
            "neutral_votes": key[1],
            "rater_count": key[0],
            "same_rater_coselection_count": key[3],
            "unclear_count": key[4],
        }
        for key, count in sorted(patterns.items())
    ]
    emotion_rows = []
    for emotion, counts in sorted(per_emotion.items()):
        rows = counts["rows"]
        emotion_rows.append(
            {
                "aggregation_only_rate": counts["aggregation_only_rows"] / rows,
                "aggregation_only_rows": counts["aggregation_only_rows"],
                "any_unclear_rows": counts["any_unclear_rows"],
                "emotion": emotion,
                "rows": rows,
                "same_rater_coselection_rows": counts["same_rater_coselection_rows"],
            }
        )
    return row_audit, summary, emotion_rows, pattern_rows


def select_sample(
    row_audit: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    selected_rows: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    budget = config["qualitative_sample"]["maximum_rows"]
    role_specs = config["qualitative_sample"]["roles"]

    def eligible(role: str, row: dict[str, Any]) -> bool:
        if role == "aggregation_only":
            return bool(row["aggregation_only"])
        if role == "same_rater_coselection":
            return int(row["same_rater_coselection_count"]) > 0
        if role == "any_unclear":
            return int(row["unclear_count"]) > 0
        if role == "gold_cardinality_at_least_3":
            return int(row["gold_cardinality"]) >= 3
        if role == "residual_fill":
            return True
        raise RuntimeError(f"Unknown sample role: {role}")

    for spec in role_specs:
        role = spec["name"]
        limit = budget if spec["limit"] is None else spec["limit"]
        candidates = [
            row
            for row in row_audit
            if row["source_train_row"] not in selected_ids and eligible(role, row)
        ]
        candidates.sort(
            key=lambda row: sha256_text(
                f"{config['qualitative_sample']['ranking_salt']}:{role}:{row['source_train_row']}"
            )
        )
        remaining = budget - len(selected_rows)
        for row in candidates[: min(limit, remaining)]:
            selected_ids.add(row["source_train_row"])
            selected_rows.append({**row, "sample_role": role})
        if len(selected_rows) == budget:
            break

    for index, row in enumerate(selected_rows, start=1):
        row["sample_id"] = f"EXP-035-S{index:03d}"
    return selected_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 mismatch")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-035" or config["tier"] != "Major":
        raise RuntimeError("Unexpected experiment registration")
    for name, spec in config["implementation"].items():
        if sha256_file(resolve_project_path(spec["path"])) != spec["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")

    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {run_dir}")

    started_at = utc_now()
    start = time.monotonic()
    labels, selected = load_frozen_slice(config)
    target_by_id = {record["comment_id"]: record for record in selected}
    all_records: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []
    for source in config["raw_sources"]:
        matched, manifest = stream_source(source, labels, target_by_id)
        all_records.extend(matched)
        source_manifests.append(manifest)

    row_audit, summary, emotion_rows, pattern_rows = aggregate_rows(
        selected, all_records, labels
    )
    sample = select_sample(row_audit, config)
    if len(sample) != config["qualitative_sample"]["maximum_rows"]:
        raise RuntimeError("Frozen qualitative sample did not reach its expected budget")

    run_dir.mkdir(parents=True, exist_ok=True)
    private_dir = run_dir / "private"
    private_dir.mkdir()
    write_jsonl(private_dir / "matched-annotations.private.jsonl", all_records)
    target_by_row = {record["source_train_row"]: record for record in selected}
    private_sample = []
    for row in sample:
        target = target_by_row[row["source_train_row"]]
        private_sample.append(
            {
                "gold_labels": target["gold_labels"],
                "sample_id": row["sample_id"],
                "sample_role": row["sample_role"],
                "source_train_row": row["source_train_row"],
                "text": target["text"],
            }
        )
    write_jsonl(private_dir / "selected-text.private.jsonl", private_sample)
    write_csv(
        private_dir / "manual-review.private.csv",
        [
            {
                "annotation_interpretation": "",
                "context_trigger": "",
                "label_coherence": "",
                "private_note": "",
                "reviewer_confidence": "",
                "sample_id": row["sample_id"],
                "standalone_decidability": "",
            }
            for row in sample
        ],
        [
            "sample_id",
            "standalone_decidability",
            "label_coherence",
            "context_trigger",
            "annotation_interpretation",
            "reviewer_confidence",
            "private_note",
        ],
    )

    public_row_fields = [
        "source_train_row",
        "example_hash",
        "gold_label_ids",
        "gold_labels",
        "gold_cardinality",
        "rater_count",
        "unclear_count",
        "neutral_votes",
        "max_emotion_votes",
        "same_rater_coselection_count",
        "aggregation_only",
        "derived_labels_match",
    ]
    write_csv(run_dir / "row-audit.csv", row_audit, public_row_fields)
    write_csv(
        run_dir / "per-emotion-summary.csv",
        emotion_rows,
        [
            "emotion",
            "rows",
            "aggregation_only_rows",
            "aggregation_only_rate",
            "same_rater_coselection_rows",
            "any_unclear_rows",
        ],
    )
    write_csv(
        run_dir / "vote-patterns.csv",
        pattern_rows,
        [
            "rater_count",
            "neutral_votes",
            "max_emotion_votes",
            "same_rater_coselection_count",
            "unclear_count",
            "count",
        ],
    )
    sample_fields = ["sample_id", "sample_role", *public_row_fields]
    write_csv(run_dir / "sample-manifest.csv", sample, sample_fields)
    write_json(run_dir / "aggregate-summary.json", summary)
    write_json(
        run_dir / "source-manifest.json",
        {
            "data_protocol": config["data_protocol"],
            "nonmatching_raw_fields_persisted": False,
            "sources": source_manifests,
            "target_annotation_rows_retained": len(all_records),
            "target_comment_rows": len(selected),
        },
    )

    completed_at = utc_now()
    stdout_path = run_dir / "stdout.log"
    stdout_path.write_text(
        "\n".join(
            [
                f"{started_at} EXP-035 started",
                *[
                    (
                        f"{manifest['name']}: bytes={manifest['bytes']} "
                        f"raw_rows={manifest['raw_annotation_rows']} "
                        f"matched_rows={manifest['matched_annotation_rows']} "
                        f"sha256={manifest['sha256']}"
                    )
                    for manifest in source_manifests
                ],
                (
                    f"{completed_at} quantitative audit completed: "
                    f"rows={summary['rows']} "
                    f"aggregation_only={summary['aggregation_only_rows']} "
                    f"same_rater_coselection={summary['same_rater_coselection_rows']}"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    public_artifacts = {
        name: artifact_record(run_dir / name)
        for name in [
            "aggregate-summary.json",
            "per-emotion-summary.csv",
            "row-audit.csv",
            "sample-manifest.csv",
            "source-manifest.json",
            "stdout.log",
            "vote-patterns.csv",
        ]
    }
    run = {
        "accessed_splits": ["train"],
        "active_duration_seconds": time.monotonic() - start,
        "artifacts": public_artifacts,
        "command": [str(Path(__file__).resolve()), "--config", str(config_path), "--config-sha256", args.config_sha256],
        "completed_at_utc": completed_at,
        "config": {"path": str(config_path.relative_to(PROJECT_ROOT)), "sha256": args.config_sha256},
        "data_protocol": config["data_protocol"],
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": sys.version,
        },
        "experiment_id": "EXP-035",
        "git": git_state(),
        "parent_experiment": config["parent_experiment"],
        "research_question": config["research_question"],
        "resource_budget": config["resource_budget"],
        "result_summary": summary,
        "sample_rows": len(sample),
        "split": "train-neutral-cooccurrence-only",
        "stage": "annotation-audit",
        "started_at_utc": started_at,
        "status": "Quantitative audit completed; manual review pending",
        "test_boundary": summary["transport_boundary"],
        "tier": "Major",
        "warnings": [],
    }
    write_json(run_dir / "run.json", run)
    print(
        json.dumps(
            {
                "aggregation_only_rows": summary["aggregation_only_rows"],
                "rows": summary["rows"],
                "same_rater_coselection_rows": summary["same_rater_coselection_rows"],
                "status": run["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
