#!/usr/bin/env python3
"""Run EXP-037 on frozen full-dev predictions without training or inference."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import platform
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path.resolve()
    return resolve_project_path(value).resolve()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.12f}"
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in fieldnames} for row in rows)


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


def parse_label_ids(value: str) -> list[int]:
    stripped = value.strip()
    return [] if not stripped else [int(item) for item in stripped.split("|")]


def set_f1(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    return 2.0 * len(left & right) / (len(left) + len(right))


def jaccard(left: set[int], right: set[int]) -> float:
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)


def exact(left: set[int], right: set[int]) -> float:
    return float(left == right)


class DigestingRawReader(io.RawIOBase):
    def __init__(self, response: Any) -> None:
        self.response = response
        self.sha256 = hashlib.sha256()
        self.md5 = hashlib.md5()  # noqa: S324 - source identity, not security.
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


def expected_raw_header(labels: list[str]) -> list[str]:
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


def recursively_find_true_test_access(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if "test" in normalized and "access" in normalized and nested is True:
                return True
            if recursively_find_true_test_access(nested):
                return True
    elif isinstance(value, list):
        return any(recursively_find_true_test_access(item) for item in value)
    return False


def verify_implementation(config: dict[str, Any]) -> None:
    for name, record in config["implementation"].items():
        path = resolve_project_path(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")


def load_dev(
    config: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[list[int]]]:
    selection = config["selection"]
    dev_path = resolve_project_path(selection["dev_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    test_path = resolve_project_path(selection["simplified_test_path"])
    if test_path.exists():
        raise RuntimeError("Simplified GoEmotions test.tsv exists; EXP-037 is not authorized")
    if sha256_file(dev_path) != selection["dev_sha256"]:
        raise RuntimeError("Frozen dev.tsv hash changed")
    if sha256_file(labels_path) != selection["labels_sha256"]:
        raise RuntimeError("Frozen emotions.txt hash changed")

    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if labels != config["labels"] or labels.index("neutral") != 27:
        raise RuntimeError("Frozen label order changed")

    selected: list[dict[str, Any]] = []
    all_gold: list[list[int]] = []
    with dev_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 3:
                raise RuntimeError(f"Malformed dev row {row_number}")
            text, encoded_labels, comment_id = row
            label_ids = [int(value) for value in encoded_labels.split(",")]
            if label_ids != sorted(set(label_ids)) or any(
                value < 0 or value >= len(labels) for value in label_ids
            ):
                raise RuntimeError(f"Invalid dev labels at row {row_number}")
            all_gold.append(label_ids)
            selected.append(
                {
                    "comment_id": comment_id,
                    "example_hash": sha256_text(comment_id),
                    "gold_label_ids": label_ids,
                    "source_dev_row": row_number,
                    "text": text,
                    "text_sha256": sha256_text(text),
                }
            )

    row_hash = sha256_text(",".join(str(row["source_dev_row"]) for row in selected))
    if (
        len(all_gold) != selection["dev_rows"]
        or len(selected) != selection["expected_rows"]
        or row_hash != selection["source_dev_rows_sha256"]
        or [row["source_dev_row"] for row in selected]
        != list(range(1, selection["expected_rows"] + 1))
        or len({row["comment_id"] for row in selected}) != len(selected)
    ):
        raise RuntimeError("Frozen full-dev allowlist changed")
    return labels, selected, all_gold


def load_predictions(
    config: dict[str, Any], all_gold: list[list[int]]
) -> tuple[dict[str, list[set[int]]], list[dict[str, Any]]]:
    predictions: dict[str, list[set[int]]] = {}
    manifests: list[dict[str, Any]] = []
    for spec in config["predictions"]:
        path = resolve_project_path(spec["path"])
        verification_path = resolve_project_path(spec["verification_path"])
        if sha256_file(path) != spec["sha256"]:
            raise RuntimeError(f"Prediction hash changed: {spec['run_id']}")
        if sha256_file(verification_path) != spec["verification_sha256"]:
            raise RuntimeError(f"Upstream verification hash changed: {spec['run_id']}")
        upstream = json.loads(verification_path.read_text(encoding="utf-8"))
        if upstream.get("status") != spec["verification_status"]:
            raise RuntimeError(f"Upstream verification status changed: {spec['run_id']}")
        if recursively_find_true_test_access(upstream):
            raise RuntimeError(f"Upstream test access detected: {spec['run_id']}")

        run_predictions: list[set[int]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"row_number", "gold_label_ids", "predicted_label_ids"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise RuntimeError(f"Unexpected prediction schema: {spec['run_id']}")
            for expected_row, row in enumerate(reader, start=1):
                row_number = int(row["row_number"])
                gold = parse_label_ids(row["gold_label_ids"])
                predicted = parse_label_ids(row["predicted_label_ids"])
                if row_number != expected_row or gold != all_gold[row_number - 1]:
                    raise RuntimeError(f"Prediction alignment failed: {spec['run_id']}")
                if predicted != sorted(set(predicted)) or any(
                    value < 0 or value >= len(config["labels"]) for value in predicted
                ):
                    raise RuntimeError(f"Invalid prediction labels: {spec['run_id']}")
                run_predictions.append(set(predicted))
        if len(run_predictions) != config["selection"]["dev_rows"]:
            raise RuntimeError(f"Prediction row count changed: {spec['run_id']}")
        if spec["run_id"] in predictions:
            raise RuntimeError(f"Duplicate prediction run ID: {spec['run_id']}")
        predictions[spec["run_id"]] = run_predictions
        manifests.append(
            {
                "condition": spec["condition"],
                "path": spec["path"],
                "rows": len(run_predictions),
                "run_id": spec["run_id"],
                "seed": spec["seed"],
                "sha256": spec["sha256"],
                "verification_path": spec["verification_path"],
                "verification_sha256": spec["verification_sha256"],
                "verification_status": spec["verification_status"],
            }
        )
    return predictions, manifests


def stream_source(
    source: dict[str, Any],
    labels: list[str],
    target_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = urllib.request.Request(
        source["url"],
        headers={"Accept-Encoding": "identity", "User-Agent": "NeuroScience-EXP-037/1"},
    )
    matched: list[dict[str, Any]] = []
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        content_length = int(response.headers.get("Content-Length", "-1"))
        etag = response.headers.get("ETag", "").strip('"')
        last_modified = response.headers.get("Last-Modified", "")
        if (
            content_length != source["content_length"]
            or etag != source["etag"]
            or last_modified != source["last_modified"]
        ):
            raise RuntimeError(f"HTTP identity changed for {source['name']}")

        raw = DigestingRawReader(response)
        buffered = io.BufferedReader(raw, buffer_size=1024 * 1024)
        text_stream = io.TextIOWrapper(buffered, encoding="utf-8", newline="")
        reader = csv.reader(text_stream)
        header = next(reader)
        if header != expected_raw_header(labels):
            raise RuntimeError(f"Unexpected raw schema in {source['name']}")
        index = {name: position for position, name in enumerate(header)}
        source_rows = 0
        for source_line, row in enumerate(reader, start=2):
            source_rows += 1
            if len(row) != len(header):
                raise RuntimeError(f"Malformed {source['name']} row {source_line}")
            target = target_by_id.get(row[index["id"]])
            if target is None:
                continue
            if row[index["text"]] != target["text"]:
                raise RuntimeError(f"Text mismatch for dev row {target['source_dev_row']}")
            label_ids: list[int] = []
            for label_id, label in enumerate(labels):
                value = row[index[label]]
                if value not in {"0", "1"}:
                    raise RuntimeError(f"Invalid raw label value in {source['name']}")
                if value == "1":
                    label_ids.append(label_id)
            unclear_raw = row[index["example_very_unclear"]].strip().lower()
            if unclear_raw not in {"true", "false"}:
                raise RuntimeError(f"Invalid unclear value in {source['name']}")
            matched.append(
                {
                    "example_hash": target["example_hash"],
                    "label_ids": label_ids,
                    "rater_hash": sha256_text(row[index["rater_id"]]),
                    "source_dev_row": target["source_dev_row"],
                    "source_file": source["name"],
                    "source_line": source_line,
                    "text_sha256": target["text_sha256"],
                    "unclear": unclear_raw == "true",
                }
            )
        text_stream.detach()

    observed_md5 = base64.b64encode(raw.md5.digest()).decode("ascii")
    observed_sha256 = raw.sha256.hexdigest()
    if (
        raw.bytes_read != source["content_length"]
        or observed_md5 != source["md5_base64"]
        or observed_sha256 != source["sha256"]
        or source_rows != source["raw_annotation_rows"]
    ):
        raise RuntimeError(f"Downloaded bytes changed for {source['name']}")
    manifest = {
        "bytes": raw.bytes_read,
        "etag": source["etag"],
        "last_modified": source["last_modified"],
        "matched_annotation_rows": len(matched),
        "md5_base64": observed_md5,
        "name": source["name"],
        "raw_annotation_rows": source_rows,
        "sha256": observed_sha256,
        "url": source["url"],
    }
    return matched, manifest


def build_rater_view(
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    label_count: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pairs: set[tuple[str, str]] = set()
    duplicate_pairs = 0
    for record in records:
        pair = (record["example_hash"], record["rater_hash"])
        duplicate_pairs += int(pair in pairs)
        pairs.add(pair)
        by_hash[record["example_hash"]].append(record)

    structures: list[dict[str, Any]] = []
    view: dict[int, dict[str, Any]] = {}
    rater_counts: Counter[int] = Counter()
    clear_counts: Counter[int] = Counter()
    unclear_rows = 0
    unclear_annotations = 0
    disagreement_rows = 0
    aggregate_not_individual_rows = 0
    reproduction_mismatches = 0
    clear_empty_annotations = 0

    for target in selected:
        row_number = target["source_dev_row"]
        annotations = by_hash.get(target["example_hash"], [])
        if not annotations:
            raise RuntimeError(f"Missing raw annotations for dev row {row_number}")
        votes = np.zeros(label_count, dtype=np.float64)
        for annotation in annotations:
            votes[annotation["label_ids"]] += 1.0
        derived_ids = [index for index, count in enumerate(votes) if count >= 2]
        derived_matches = derived_ids == target["gold_label_ids"]
        reproduction_mismatches += int(not derived_matches)

        clear_sets = [set(row["label_ids"]) for row in annotations if not row["unclear"]]
        all_labeled_sets = [set(row["label_ids"]) for row in annotations if row["label_ids"]]
        clear_empty_annotations += sum(
            int(not row["label_ids"]) for row in annotations if not row["unclear"]
        )
        if not clear_sets or any(not labels for labels in clear_sets):
            raise RuntimeError(f"Invalid clear-rater labels at dev row {row_number}")
        if not all_labeled_sets:
            raise RuntimeError(f"No labeled raters at dev row {row_number}")

        clear_probs = np.zeros(label_count, dtype=np.float64)
        for label_set in clear_sets:
            clear_probs[list(label_set)] += 1.0
        clear_probs /= len(clear_sets)
        all_labeled_probs = np.zeros(label_count, dtype=np.float64)
        for label_set in all_labeled_sets:
            all_labeled_probs[list(label_set)] += 1.0
        all_labeled_probs /= len(all_labeled_sets)

        unique_clear_sets = len({tuple(sorted(label_set)) for label_set in clear_sets})
        official_matches_individual = any(
            set(target["gold_label_ids"]) == label_set for label_set in clear_sets
        )
        unclear_count = sum(int(row["unclear"]) for row in annotations)
        disagreement_rows += int(unique_clear_sets > 1)
        aggregate_not_individual_rows += int(not official_matches_individual)
        unclear_rows += int(unclear_count > 0)
        unclear_annotations += unclear_count
        rater_counts[len(annotations)] += 1
        clear_counts[len(clear_sets)] += 1

        structures.append(
            {
                "source_dev_row": row_number,
                "example_hash": target["example_hash"],
                "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
                "gold_cardinality": len(target["gold_label_ids"]),
                "rater_count": len(annotations),
                "clear_rater_count": len(clear_sets),
                "labeled_rater_count": len(all_labeled_sets),
                "unclear_count": unclear_count,
                "unique_clear_label_set_count": unique_clear_sets,
                "clear_rater_disagreement": unique_clear_sets > 1,
                "official_target_matches_any_clear_rater": official_matches_individual,
                "derived_labels_match": derived_matches,
            }
        )
        view[row_number] = {
            "all_labeled_probs": all_labeled_probs,
            "all_labeled_sets": all_labeled_sets,
            "clear_probs": clear_probs,
            "clear_sets": clear_sets,
            "gold": set(target["gold_label_ids"]),
        }

    if len(by_hash) != len(selected) or duplicate_pairs:
        raise RuntimeError("Raw annotation join contains missing or duplicate comment/rater keys")
    if reproduction_mismatches:
        raise RuntimeError("Official >=2-rater aggregation does not reproduce full dev labels")
    if clear_empty_annotations:
        raise RuntimeError("Clear-rater empty annotations unexpectedly reached summary")

    summary = {
        "aggregate_target_not_any_clear_rater_rate": aggregate_not_individual_rows / len(selected),
        "aggregate_target_not_any_clear_rater_rows": aggregate_not_individual_rows,
        "any_unclear_rate": unclear_rows / len(selected),
        "any_unclear_rows": unclear_rows,
        "clear_empty_annotations": clear_empty_annotations,
        "clear_rater_count_distribution": dict(sorted(clear_counts.items())),
        "clear_rater_disagreement_rate": disagreement_rows / len(selected),
        "clear_rater_disagreement_rows": disagreement_rows,
        "duplicate_comment_rater_pairs": duplicate_pairs,
        "matched_annotation_rows": len(records),
        "official_threshold_reproduction_mismatches": reproduction_mismatches,
        "rater_count_distribution": dict(sorted(rater_counts.items())),
        "rows": len(selected),
        "unclear_annotation_rows": unclear_annotations,
    }
    return structures, view, summary


def binary_metric_summary(
    prediction: np.ndarray, target: np.ndarray
) -> tuple[dict[str, float], list[dict[str, float]]]:
    true_positive = np.sum(prediction * target, axis=0)
    predicted_mass = np.sum(prediction, axis=0)
    target_mass = np.sum(target, axis=0)
    false_positive = predicted_mass - true_positive
    false_negative = target_mass - true_positive
    precision = np.divide(
        true_positive,
        predicted_mass,
        out=np.zeros_like(true_positive),
        where=predicted_mass != 0,
    )
    recall = np.divide(
        true_positive,
        target_mass,
        out=np.zeros_like(true_positive),
        where=target_mass != 0,
    )
    denominator = predicted_mass + target_mass
    f1 = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator != 0,
    )
    micro_denominator = float(np.sum(denominator))
    summary = {
        "macro_f1": float(np.mean(f1)),
        "micro_f1": (
            0.0 if micro_denominator == 0 else float(2.0 * np.sum(true_positive) / micro_denominator)
        ),
    }
    rows = [
        {
            "false_negative": float(false_negative[index]),
            "false_positive": float(false_positive[index]),
            "f1": float(f1[index]),
            "precision": float(precision[index]),
            "predicted_positive_mass": float(predicted_mass[index]),
            "recall": float(recall[index]),
            "target_support": float(target_mass[index]),
            "true_positive": float(true_positive[index]),
        }
        for index in range(prediction.shape[1])
    ]
    return summary, rows


RUN_SUMMARY_METRICS = [
    "official_macro_f1",
    "official_micro_f1",
    "official_sample_set_f1",
    "official_sample_jaccard",
    "official_subset_accuracy",
    "clear_rater_soft_macro_f1",
    "clear_rater_soft_micro_f1",
    "clear_rater_expected_set_f1",
    "clear_rater_expected_jaccard",
    "clear_rater_expected_exact",
    "any_clear_rater_exact",
    "best_clear_rater_set_f1",
    "all_labeled_rater_soft_macro_f1",
    "all_labeled_rater_soft_micro_f1",
    "all_labeled_rater_expected_set_f1",
    "mean_predicted_cardinality",
]


def score_runs(
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    view: dict[int, dict[str, Any]],
    predictions: dict[str, list[set[int]]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, np.ndarray]],
]:
    row_count = len(selected)
    label_count = len(config["labels"])
    gold_matrix = np.zeros((row_count, label_count), dtype=np.float64)
    clear_matrix = np.zeros((row_count, label_count), dtype=np.float64)
    all_labeled_matrix = np.zeros((row_count, label_count), dtype=np.float64)
    for index, target in enumerate(selected):
        row_number = target["source_dev_row"]
        gold_matrix[index, target["gold_label_ids"]] = 1.0
        clear_matrix[index] = view[row_number]["clear_probs"]
        all_labeled_matrix[index] = view[row_number]["all_labeled_probs"]

    run_metrics: list[dict[str, Any]] = []
    per_label: list[dict[str, Any]] = []
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for spec in config["predictions"]:
        run_id = spec["run_id"]
        run_predictions = predictions[run_id]
        prediction_matrix = np.zeros((row_count, label_count), dtype=np.float64)
        official_set_scores = np.empty(row_count, dtype=np.float64)
        official_jaccard_scores = np.empty(row_count, dtype=np.float64)
        official_exact_scores = np.empty(row_count, dtype=np.float64)
        clear_set_scores = np.empty(row_count, dtype=np.float64)
        clear_jaccard_scores = np.empty(row_count, dtype=np.float64)
        clear_exact_scores = np.empty(row_count, dtype=np.float64)
        any_clear_exact_scores = np.empty(row_count, dtype=np.float64)
        best_clear_set_scores = np.empty(row_count, dtype=np.float64)
        all_labeled_set_scores = np.empty(row_count, dtype=np.float64)

        for index, target in enumerate(selected):
            row_number = target["source_dev_row"]
            prediction = run_predictions[index]
            prediction_matrix[index, list(prediction)] = 1.0
            gold = view[row_number]["gold"]
            clear_sets = view[row_number]["clear_sets"]
            all_labeled_sets = view[row_number]["all_labeled_sets"]
            official_set_scores[index] = set_f1(prediction, gold)
            official_jaccard_scores[index] = jaccard(prediction, gold)
            official_exact_scores[index] = exact(prediction, gold)
            clear_set_scores[index] = statistics.mean(
                set_f1(prediction, labels) for labels in clear_sets
            )
            clear_jaccard_scores[index] = statistics.mean(
                jaccard(prediction, labels) for labels in clear_sets
            )
            clear_exact_scores[index] = statistics.mean(
                exact(prediction, labels) for labels in clear_sets
            )
            any_clear_exact_scores[index] = max(
                exact(prediction, labels) for labels in clear_sets
            )
            best_clear_set_scores[index] = max(
                set_f1(prediction, labels) for labels in clear_sets
            )
            all_labeled_set_scores[index] = statistics.mean(
                set_f1(prediction, labels) for labels in all_labeled_sets
            )

        official_summary, official_labels = binary_metric_summary(
            prediction_matrix, gold_matrix
        )
        clear_summary, clear_labels = binary_metric_summary(prediction_matrix, clear_matrix)
        all_summary, all_labels = binary_metric_summary(
            prediction_matrix, all_labeled_matrix
        )
        summary = {
            "condition": spec["condition"],
            "run_id": run_id,
            "seed": spec["seed"],
            "rows": row_count,
            "empty_prediction_count": sum(int(not labels) for labels in run_predictions),
            "mean_predicted_cardinality": statistics.mean(
                len(labels) for labels in run_predictions
            ),
            "official_macro_f1": official_summary["macro_f1"],
            "official_micro_f1": official_summary["micro_f1"],
            "official_sample_set_f1": float(np.mean(official_set_scores)),
            "official_sample_jaccard": float(np.mean(official_jaccard_scores)),
            "official_subset_accuracy": float(np.mean(official_exact_scores)),
            "clear_rater_soft_macro_f1": clear_summary["macro_f1"],
            "clear_rater_soft_micro_f1": clear_summary["micro_f1"],
            "clear_rater_expected_set_f1": float(np.mean(clear_set_scores)),
            "clear_rater_expected_jaccard": float(np.mean(clear_jaccard_scores)),
            "clear_rater_expected_exact": float(np.mean(clear_exact_scores)),
            "any_clear_rater_exact": float(np.mean(any_clear_exact_scores)),
            "best_clear_rater_set_f1": float(np.mean(best_clear_set_scores)),
            "all_labeled_rater_soft_macro_f1": all_summary["macro_f1"],
            "all_labeled_rater_soft_micro_f1": all_summary["micro_f1"],
            "all_labeled_rater_expected_set_f1": float(np.mean(all_labeled_set_scores)),
        }
        run_metrics.append(summary)

        for target_type, rows in (
            ("official_hard", official_labels),
            ("clear_rater_soft", clear_labels),
            ("all_labeled_rater_soft", all_labels),
        ):
            for label_id, metrics in enumerate(rows):
                per_label.append(
                    {
                        "condition": spec["condition"],
                        "run_id": run_id,
                        "seed": spec["seed"],
                        "target_type": target_type,
                        "label_id": label_id,
                        "label": config["labels"][label_id],
                        **metrics,
                    }
                )
        arrays[run_id] = {
            "clear_rater_expected_set_f1": clear_set_scores,
            "official_sample_set_f1": official_set_scores,
            "prediction": prediction_matrix,
        }

    arrays["__targets__"] = {"clear": clear_matrix, "gold": gold_matrix}
    return run_metrics, per_label, arrays


def summarize_families(run_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_metrics:
        grouped[row["condition"]].append(row)
    output: list[dict[str, Any]] = []
    for condition, rows in sorted(grouped.items()):
        summary: dict[str, Any] = {
            "condition": condition,
            "run_count": len(rows),
            "seeds": "|".join(str(row["seed"]) for row in sorted(rows, key=lambda item: item["seed"])),
        }
        for metric in RUN_SUMMARY_METRICS:
            values = [float(row[metric]) for row in rows]
            summary[f"{metric}_mean"] = statistics.mean(values)
            summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else None
        output.append(summary)
    return output


def matching_run_ids(operand: dict[str, Any], config: dict[str, Any]) -> list[str]:
    matches = [
        spec
        for spec in config["predictions"]
        if spec["condition"] == operand["condition"] and spec["seed"] in operand["seeds"]
    ]
    matches.sort(key=lambda spec: spec["seed"])
    if len(matches) != len(operand["seeds"]):
        raise RuntimeError(f"Comparison operand is incomplete: {operand}")
    return [spec["run_id"] for spec in matches]


def derived_seed(base_seed: int, comparison_id: str, kind: str) -> int:
    return int(sha256_text(f"{base_seed}:{comparison_id}:{kind}")[:16], 16)


def confidence_interval(values: np.ndarray) -> tuple[float, float]:
    bounds = np.quantile(values, [0.025, 0.975], method="linear")
    return float(bounds[0]), float(bounds[1])


def bootstrap_sample_metrics(
    official_delta: np.ndarray,
    rater_delta: np.ndarray,
    iterations: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    row_count = len(official_delta)
    sampled_official = np.empty(iterations, dtype=np.float64)
    sampled_rater = np.empty(iterations, dtype=np.float64)
    batch_size = 100
    offset = 0
    while offset < iterations:
        size = min(batch_size, iterations - offset)
        indices = rng.integers(0, row_count, size=(size, row_count))
        sampled_official[offset : offset + size] = np.mean(official_delta[indices], axis=1)
        sampled_rater[offset : offset + size] = np.mean(rater_delta[indices], axis=1)
        offset += size
    return {
        "official": confidence_interval(sampled_official),
        "rater": confidence_interval(sampled_rater),
        "shift": confidence_interval(sampled_rater - sampled_official),
    }


def macro_f1_from_masses(
    predicted_mass: np.ndarray, target_mass: np.ndarray, true_positive: np.ndarray
) -> np.ndarray:
    denominator = predicted_mass + target_mass[:, None, :]
    f1 = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator != 0,
    )
    return np.mean(f1, axis=2)


def bootstrap_macro_metrics(
    candidate_predictions: np.ndarray,
    reference_predictions: np.ndarray,
    gold: np.ndarray,
    clear: np.ndarray,
    iterations: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    row_count = gold.shape[0]
    run_count_candidate = candidate_predictions.shape[0]
    combined = np.concatenate([candidate_predictions, reference_predictions], axis=0)
    combined_gold = combined * gold[None, :, :]
    combined_clear = combined * clear[None, :, :]
    sampled_official = np.empty(iterations, dtype=np.float64)
    sampled_soft = np.empty(iterations, dtype=np.float64)
    batch_size = 20
    offset = 0
    while offset < iterations:
        size = min(batch_size, iterations - offset)
        indices = rng.integers(0, row_count, size=(size, row_count))
        counts = np.stack(
            [np.bincount(row, minlength=row_count) for row in indices]
        ).astype(np.float64)
        predicted_mass = np.einsum("bn,rnl->brl", counts, combined, optimize=True)
        gold_mass = counts @ gold
        clear_mass = counts @ clear
        official_tp = np.einsum("bn,rnl->brl", counts, combined_gold, optimize=True)
        clear_tp = np.einsum("bn,rnl->brl", counts, combined_clear, optimize=True)
        official_macro = macro_f1_from_masses(predicted_mass, gold_mass, official_tp)
        soft_macro = macro_f1_from_masses(predicted_mass, clear_mass, clear_tp)
        candidate_official = np.mean(official_macro[:, :run_count_candidate], axis=1)
        reference_official = np.mean(official_macro[:, run_count_candidate:], axis=1)
        candidate_soft = np.mean(soft_macro[:, :run_count_candidate], axis=1)
        reference_soft = np.mean(soft_macro[:, run_count_candidate:], axis=1)
        sampled_official[offset : offset + size] = candidate_official - reference_official
        sampled_soft[offset : offset + size] = candidate_soft - reference_soft
        offset += size
    return {
        "official": confidence_interval(sampled_official),
        "soft": confidence_interval(sampled_soft),
        "shift": confidence_interval(sampled_soft - sampled_official),
    }


def compare_models(
    config: dict[str, Any],
    run_metrics: list[dict[str, Any]],
    arrays: dict[str, dict[str, np.ndarray]],
) -> list[dict[str, Any]]:
    metric_by_run = {row["run_id"]: row for row in run_metrics}
    gold = arrays["__targets__"]["gold"]
    clear = arrays["__targets__"]["clear"]
    tie = config["statistics"]["practical_tie_threshold"]
    material = config["statistics"]["material_shift_threshold"]
    base_seed = config["statistics"]["bootstrap_seed"]
    sample_iterations = config["statistics"]["sample_bootstrap_iterations"]
    macro_iterations = config["statistics"]["macro_bootstrap_iterations"]
    output: list[dict[str, Any]] = []

    for comparison in config["comparisons"]:
        candidate_ids = matching_run_ids(comparison["candidate"], config)
        reference_ids = matching_run_ids(comparison["reference"], config)
        candidate_official_samples = np.mean(
            np.stack([arrays[run_id]["official_sample_set_f1"] for run_id in candidate_ids]),
            axis=0,
        )
        reference_official_samples = np.mean(
            np.stack([arrays[run_id]["official_sample_set_f1"] for run_id in reference_ids]),
            axis=0,
        )
        candidate_rater_samples = np.mean(
            np.stack(
                [arrays[run_id]["clear_rater_expected_set_f1"] for run_id in candidate_ids]
            ),
            axis=0,
        )
        reference_rater_samples = np.mean(
            np.stack(
                [arrays[run_id]["clear_rater_expected_set_f1"] for run_id in reference_ids]
            ),
            axis=0,
        )
        official_sample_delta = candidate_official_samples - reference_official_samples
        rater_sample_delta = candidate_rater_samples - reference_rater_samples
        sample_seed = derived_seed(base_seed, comparison["comparison_id"], "sample")
        sample_cis = bootstrap_sample_metrics(
            official_sample_delta,
            rater_sample_delta,
            sample_iterations,
            sample_seed,
        )

        candidate_predictions = np.stack(
            [arrays[run_id]["prediction"] for run_id in candidate_ids]
        )
        reference_predictions = np.stack(
            [arrays[run_id]["prediction"] for run_id in reference_ids]
        )
        macro_seed = derived_seed(base_seed, comparison["comparison_id"], "macro")
        macro_cis = bootstrap_macro_metrics(
            candidate_predictions,
            reference_predictions,
            gold,
            clear,
            macro_iterations,
            macro_seed,
        )
        official_macro_delta = statistics.mean(
            metric_by_run[run_id]["official_macro_f1"] for run_id in candidate_ids
        ) - statistics.mean(
            metric_by_run[run_id]["official_macro_f1"] for run_id in reference_ids
        )
        soft_macro_delta = statistics.mean(
            metric_by_run[run_id]["clear_rater_soft_macro_f1"] for run_id in candidate_ids
        ) - statistics.mean(
            metric_by_run[run_id]["clear_rater_soft_macro_f1"] for run_id in reference_ids
        )
        macro_shift = soft_macro_delta - official_macro_delta
        if soft_macro_delta <= -tie and macro_cis["soft"][1] < 0:
            decision = "gap_remains"
        elif soft_macro_delta >= tie and macro_cis["soft"][0] > 0:
            decision = "candidate_advantage"
        else:
            decision = "practical_tie_or_uncertain"
        zero = np.isclose(rater_sample_delta, 0.0, rtol=0.0, atol=1e-15)
        output.append(
            {
                "comparison_id": comparison["comparison_id"],
                "candidate": comparison["candidate"]["label"],
                "reference": comparison["reference"]["label"],
                "rows": gold.shape[0],
                "macro_bootstrap_iterations": macro_iterations,
                "macro_bootstrap_seed": macro_seed,
                "official_macro_f1_delta": official_macro_delta,
                "official_macro_f1_delta_ci_low": macro_cis["official"][0],
                "official_macro_f1_delta_ci_high": macro_cis["official"][1],
                "clear_rater_soft_macro_f1_delta": soft_macro_delta,
                "clear_rater_soft_macro_f1_delta_ci_low": macro_cis["soft"][0],
                "clear_rater_soft_macro_f1_delta_ci_high": macro_cis["soft"][1],
                "soft_vs_official_macro_shift": macro_shift,
                "soft_vs_official_macro_shift_ci_low": macro_cis["shift"][0],
                "soft_vs_official_macro_shift_ci_high": macro_cis["shift"][1],
                "sample_bootstrap_iterations": sample_iterations,
                "sample_bootstrap_seed": sample_seed,
                "official_sample_set_f1_delta": float(np.mean(official_sample_delta)),
                "official_sample_set_f1_delta_ci_low": sample_cis["official"][0],
                "official_sample_set_f1_delta_ci_high": sample_cis["official"][1],
                "clear_rater_expected_set_f1_delta": float(np.mean(rater_sample_delta)),
                "clear_rater_expected_set_f1_delta_ci_low": sample_cis["rater"][0],
                "clear_rater_expected_set_f1_delta_ci_high": sample_cis["rater"][1],
                "rater_vs_official_sample_shift": float(
                    np.mean(rater_sample_delta - official_sample_delta)
                ),
                "rater_vs_official_sample_shift_ci_low": sample_cis["shift"][0],
                "rater_vs_official_sample_shift_ci_high": sample_cis["shift"][1],
                "rater_example_wins": int(np.sum((rater_sample_delta > 0) & ~zero)),
                "rater_example_ties": int(np.sum(zero)),
                "rater_example_losses": int(np.sum((rater_sample_delta < 0) & ~zero)),
                "aggregation_materially_shifts_macro_comparison": (
                    macro_shift >= material and macro_cis["shift"][0] > 0
                ),
                "decision": decision,
            }
        )
    return output


def render_report(
    structure: dict[str, Any],
    families: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    family_lines = [
        "| Condition | Runs | Official Macro-F1 | Clear-rater soft Macro-F1 | Expected rater set-F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in families:
        family_lines.append(
            "| {condition} | {runs} | {official:.6f} | {soft:.6f} | {expected:.6f} |".format(
                condition=row["condition"],
                runs=row["run_count"],
                official=row["official_macro_f1_mean"],
                soft=row["clear_rater_soft_macro_f1_mean"],
                expected=row["clear_rater_expected_set_f1_mean"],
            )
        )
    comparison_lines = [
        "| Comparison (candidate - reference) | Official Macro delta | Soft Macro delta | Macro shift | Decision |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in comparisons:
        comparison_lines.append(
            "| {comparison} | {official:+.6f} | {soft:+.6f} | {shift:+.6f} | {decision} |".format(
                comparison=row["comparison_id"],
                official=row["official_macro_f1_delta"],
                soft=row["clear_rater_soft_macro_f1_delta"],
                shift=row["soft_vs_official_macro_shift"],
                decision=row["decision"],
            )
        )
    primary = comparisons[0]
    return "\n".join(
        [
            "# EXP-037: Full-dev Rater-aware Frozen-prediction Diagnostic",
            "",
            "## Boundary",
            "",
            "This validation-only diagnostic rescored seven frozen prediction files on all 5,426",
            "official GoEmotions dev rows. It performed no training, model inference, checkpoint",
            "selection, threshold change, or test access.",
            "",
            "## Annotation Integrity",
            "",
            f"- Rows joined and reproduced: {structure['rows']}; official aggregation mismatches: "
            f"{structure['official_threshold_reproduction_mismatches']}.",
            f"- Matched per-rater annotations: {structure['matched_annotation_rows']}.",
            f"- Rows with disagreement among clear raters: {structure['clear_rater_disagreement_rows']} "
            f"({structure['clear_rater_disagreement_rate']:.6f}).",
            f"- Official targets matching no clear individual rater: "
            f"{structure['aggregate_target_not_any_clear_rater_rows']} "
            f"({structure['aggregate_target_not_any_clear_rater_rate']:.6f}).",
            f"- Rows with unclear annotations: {structure['any_unclear_rows']} "
            f"({structure['any_unclear_rate']:.6f}).",
            "",
            "## Frozen Predictions",
            "",
            *family_lines,
            "",
            "Soft Macro-F1 uses each clear annotator's vote fraction as the label target. Expected",
            "rater set-F1 instead averages set agreement against one clear annotator at a time.",
            "Neither diagnostic is replacement truth; official dev metrics remain the benchmark.",
            "",
            "## Paired Comparisons",
            "",
            *comparison_lines,
            "",
            f"Primary classification: `{primary['decision']}`. Annotation-aware soft scoring",
            f"materially shifts the primary Macro-F1 comparison under the frozen rule: "
            f"`{str(primary['aggregation_materially_shifts_macro_comparison']).lower()}`.",
            "",
            "## Limits",
            "",
            "- Annotator votes measure observed agreement, not latent human emotion.",
            "- Original raters saw isolated comments, so missing conversational context remains.",
            "- Bootstrap intervals resample dev examples, not training seeds.",
            "- Soft-label rescoring does not change the official benchmark target or model outputs.",
            "- The result is behavioral evidence and does not identify an internal mechanism.",
            "",
            "Status: completed, pending independent artifact verification.",
            "",
        ]
    )


ROW_FIELDS = [
    "source_dev_row",
    "example_hash",
    "gold_label_ids",
    "gold_cardinality",
    "rater_count",
    "clear_rater_count",
    "labeled_rater_count",
    "unclear_count",
    "unique_clear_label_set_count",
    "clear_rater_disagreement",
    "official_target_matches_any_clear_rater",
    "derived_labels_match",
]
RUN_FIELDS = [
    "condition",
    "run_id",
    "seed",
    "rows",
    "empty_prediction_count",
    *RUN_SUMMARY_METRICS,
]
FAMILY_FIELDS = ["condition", "run_count", "seeds"] + [
    field
    for metric in RUN_SUMMARY_METRICS
    for field in (f"{metric}_mean", f"{metric}_std")
]
PER_LABEL_FIELDS = [
    "condition",
    "run_id",
    "seed",
    "target_type",
    "label_id",
    "label",
    "target_support",
    "predicted_positive_mass",
    "true_positive",
    "false_positive",
    "false_negative",
    "precision",
    "recall",
    "f1",
]
COMPARISON_FIELDS = [
    "comparison_id",
    "candidate",
    "reference",
    "rows",
    "macro_bootstrap_iterations",
    "macro_bootstrap_seed",
    "official_macro_f1_delta",
    "official_macro_f1_delta_ci_low",
    "official_macro_f1_delta_ci_high",
    "clear_rater_soft_macro_f1_delta",
    "clear_rater_soft_macro_f1_delta_ci_low",
    "clear_rater_soft_macro_f1_delta_ci_high",
    "soft_vs_official_macro_shift",
    "soft_vs_official_macro_shift_ci_low",
    "soft_vs_official_macro_shift_ci_high",
    "sample_bootstrap_iterations",
    "sample_bootstrap_seed",
    "official_sample_set_f1_delta",
    "official_sample_set_f1_delta_ci_low",
    "official_sample_set_f1_delta_ci_high",
    "clear_rater_expected_set_f1_delta",
    "clear_rater_expected_set_f1_delta_ci_low",
    "clear_rater_expected_set_f1_delta_ci_high",
    "rater_vs_official_sample_shift",
    "rater_vs_official_sample_shift_ci_low",
    "rater_vs_official_sample_shift_ci_high",
    "rater_example_wins",
    "rater_example_ties",
    "rater_example_losses",
    "aggregation_materially_shifts_macro_comparison",
    "decision",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()

    started_at = utc_now()
    started_clock = time.monotonic()
    config_path = resolve_config_path(args.config)
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 does not match frozen command")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-037" or config["tier"] != "Major":
        raise RuntimeError("Unexpected experiment identity")
    verify_implementation(config)

    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError("Run directory is not empty")

    labels, selected, all_gold = load_dev(config)
    predictions, prediction_manifest = load_predictions(config, all_gold)
    target_by_id = {row["comment_id"]: row for row in selected}
    all_records: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []
    for source in config["raw_sources"]:
        records, manifest = stream_source(source, labels, target_by_id)
        all_records.extend(records)
        source_manifests.append(manifest)
    all_records.sort(key=lambda row: (row["source_dev_row"], row["rater_hash"]))

    structures, view, structure_summary = build_rater_view(
        selected, all_records, len(labels)
    )
    run_metrics, per_label, arrays = score_runs(config, selected, view, predictions)
    families = summarize_families(run_metrics)
    comparisons = compare_models(config, run_metrics, arrays)

    run_dir.mkdir(parents=True, exist_ok=True)
    private_dir = run_dir / "private"
    private_dir.mkdir()
    write_jsonl(private_dir / "matched-annotations.private.jsonl", all_records)
    write_csv(run_dir / "row-structure.csv", structures, ROW_FIELDS)
    write_csv(run_dir / "run-metrics.csv", run_metrics, RUN_FIELDS)
    write_csv(run_dir / "family-summary.csv", families, FAMILY_FIELDS)
    write_csv(run_dir / "per-label-metrics.csv", per_label, PER_LABEL_FIELDS)
    write_csv(run_dir / "pairwise-comparisons.csv", comparisons, COMPARISON_FIELDS)

    source_manifest = {
        "full_archive_transport": True,
        "nonmatching_raw_records_persisted": 0,
        "official_repository_revision": config["official_source"]["revision"],
        "prediction_files": prediction_manifest,
        "retained_annotation_rows": len(all_records),
        "retained_dev_rows": len(selected),
        "simplified_test_accessed": False,
        "simplified_test_exists": False,
        "sources": source_manifests,
    }
    write_json(run_dir / "source-manifest.json", source_manifest)

    aggregate = {
        "comparisons": comparisons,
        "family_summary": families,
        "metric_semantics": {
            "primary_diagnostic": "clear-rater vote-fraction soft-label Macro-F1",
            "secondary_diagnostic": "example-weighted expected set-F1 against a clear individual rater",
            "replacement_ground_truth": False,
            "selection_use_authorized": False,
        },
        "run_metrics": run_metrics,
        "structure": structure_summary,
        "test_accessed": False,
        "test_exists": False,
    }
    write_json(run_dir / "aggregate-summary.json", aggregate)
    (run_dir / "REPORT.md").write_text(
        render_report(structure_summary, families, comparisons), encoding="utf-8"
    )

    log_lines = [
        f"experiment_id={config['experiment_id']}",
        f"started_at_utc={started_at}",
        f"dev_rows={len(all_gold)} selected_rows={len(selected)}",
        f"matched_annotation_rows={len(all_records)}",
        *[
            f"source={source['name']} raw_rows={source['raw_annotation_rows']} "
            f"matched_rows={source['matched_annotation_rows']} sha256={source['sha256']}"
            for source in source_manifests
        ],
        *[
            f"comparison={row['comparison_id']} official_macro_delta="
            f"{row['official_macro_f1_delta']:.12f} soft_macro_delta="
            f"{row['clear_rater_soft_macro_f1_delta']:.12f} decision={row['decision']}"
            for row in comparisons
        ],
        "test_accessed=false test_exists=false",
    ]
    (run_dir / "stdout.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    artifact_names = [
        "REPORT.md",
        "aggregate-summary.json",
        "family-summary.csv",
        "pairwise-comparisons.csv",
        "per-label-metrics.csv",
        "private/matched-annotations.private.jsonl",
        "row-structure.csv",
        "run-metrics.csv",
        "source-manifest.json",
        "stdout.log",
    ]
    run = {
        "accessed_splits": ["validation"],
        "artifacts": [artifact_record(run_dir / name) for name in artifact_names],
        "command": " ".join(sys.argv),
        "config": artifact_record(config_path),
        "data_protocol": config["data_protocol"],
        "ended_at_utc": utc_now(),
        "environment": {
            "numpy": np.__version__,
            "platform": platform.platform(),
            "python": sys.version,
        },
        "experiment_id": config["experiment_id"],
        "git": git_state(),
        "model_inference_performed": False,
        "parent_experiment": config["parent_experiment"],
        "research_question": config["research_question"],
        "resource_budget": config["resource_budget"],
        "result_summary": aggregate,
        "stage": "validation-only-frozen-prediction-diagnostic",
        "started_at_utc": started_at,
        "status": "CompletedAwaitingVerification",
        "test_accessed": False,
        "test_exists": False,
        "tier": config["tier"],
        "training_performed": False,
        "wall_seconds": time.monotonic() - started_clock,
    }
    write_json(run_dir / "run.json", run)
    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "primary_decision": comparisons[0]["decision"],
                "status": run["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
