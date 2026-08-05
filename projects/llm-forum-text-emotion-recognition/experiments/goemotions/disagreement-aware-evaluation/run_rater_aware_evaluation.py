#!/usr/bin/env python3
"""Run EXP-036 without training or model inference."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import platform
import random
import statistics
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
        writer.writerows(
            {key: csv_value(row.get(key)) for key in fieldnames}
            for row in rows
        )


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
    if not stripped:
        return []
    return [int(item) for item in stripped.split("|")]


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


def verify_implementation(config: dict[str, Any]) -> None:
    for name, record in config["implementation"].items():
        path = resolve_project_path(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")


def load_dev(config: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], list[list[int]]]:
    selection = config["selection"]
    dev_path = resolve_project_path(selection["dev_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    test_path = resolve_project_path(selection["simplified_test_path"])
    if test_path.exists():
        raise RuntimeError("Simplified GoEmotions test.tsv exists; EXP-036 is not authorized")
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
            if 27 in label_ids and len(label_ids) > 1:
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
        or len({row["comment_id"] for row in selected}) != len(selected)
    ):
        raise RuntimeError("Frozen dev diagnostic slice changed")
    return labels, selected, all_gold


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


def load_predictions(
    config: dict[str, Any],
    all_gold: list[list[int]],
    selected_rows: set[int],
) -> tuple[dict[str, dict[int, set[int]]], list[dict[str, Any]]]:
    predictions: dict[str, dict[int, set[int]]] = {}
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

        selected_predictions: dict[int, set[int]] = {}
        rows = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"row_number", "gold_label_ids", "predicted_label_ids"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise RuntimeError(f"Unexpected prediction schema: {spec['run_id']}")
            for expected_row, row in enumerate(reader, start=1):
                rows = expected_row
                row_number = int(row["row_number"])
                if row_number != expected_row:
                    raise RuntimeError(f"Prediction row order changed: {spec['run_id']}")
                gold = parse_label_ids(row["gold_label_ids"])
                if gold != all_gold[row_number - 1]:
                    raise RuntimeError(f"Prediction gold mismatch: {spec['run_id']} row {row_number}")
                predicted = parse_label_ids(row["predicted_label_ids"])
                if predicted != sorted(set(predicted)) or any(
                    value < 0 or value >= len(config["labels"]) for value in predicted
                ):
                    raise RuntimeError(f"Invalid prediction labels: {spec['run_id']} row {row_number}")
                if row_number in selected_rows:
                    selected_predictions[row_number] = set(predicted)
        if rows != config["selection"]["dev_rows"] or len(selected_predictions) != len(selected_rows):
            raise RuntimeError(f"Prediction row count changed: {spec['run_id']}")
        predictions[spec["run_id"]] = selected_predictions
        manifests.append(
            {
                "condition": spec["condition"],
                "path": spec["path"],
                "rows": rows,
                "run_id": spec["run_id"],
                "seed": spec["seed"],
                "sha256": spec["sha256"],
                "verification_path": spec["verification_path"],
                "verification_sha256": spec["verification_sha256"],
                "verification_status": spec["verification_status"],
            }
        )
    if len(predictions) != len(config["predictions"]):
        raise RuntimeError("Duplicate prediction run IDs")
    return predictions, manifests


def stream_source(
    source: dict[str, Any],
    labels: list[str],
    target_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request = urllib.request.Request(
        source["url"],
        headers={"Accept-Encoding": "identity", "User-Agent": "NeuroScience-EXP-036/1"},
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
    duplicate_pairs = 0
    seen_pairs: set[tuple[str, str]] = set()
    for record in records:
        pair = (record["example_hash"], record["rater_hash"])
        duplicate_pairs += int(pair in seen_pairs)
        seen_pairs.add(pair)
        by_hash[record["example_hash"]].append(record)

    structures: list[dict[str, Any]] = []
    scoring_view: dict[int, dict[str, Any]] = {}
    rater_counts: Counter[int] = Counter()
    clear_counts: Counter[int] = Counter()
    unclear_rows = 0
    same_rater_rows = 0
    reproduction_mismatches = 0
    clear_empty_annotations = 0

    for target in selected:
        annotations = by_hash.get(target["example_hash"], [])
        if not annotations:
            raise RuntimeError(f"Missing raw annotations for dev row {target['source_dev_row']}")
        votes = [0] * label_count
        for annotation in annotations:
            for label_id in annotation["label_ids"]:
                votes[label_id] += 1
        derived_ids = [label_id for label_id, count in enumerate(votes) if count >= 2]
        derived_matches = derived_ids == target["gold_label_ids"]
        reproduction_mismatches += int(not derived_matches)

        clear_sets = [set(row["label_ids"]) for row in annotations if not row["unclear"]]
        all_labeled_sets = [set(row["label_ids"]) for row in annotations if row["label_ids"]]
        clear_empty_annotations += sum(
            int(not row["label_ids"]) for row in annotations if not row["unclear"]
        )
        if not clear_sets:
            raise RuntimeError(f"No clear raters for dev row {target['source_dev_row']}")
        if any(not labels for labels in clear_sets):
            raise RuntimeError(f"Empty clear-rater label set at dev row {target['source_dev_row']}")
        if not all_labeled_sets:
            raise RuntimeError(f"No labeled raters for dev row {target['source_dev_row']}")

        same_rater_count = sum(
            int(27 in set(row["label_ids"]) and bool(set(row["label_ids"]) - {27}))
            for row in annotations
        )
        unclear_count = sum(int(row["unclear"]) for row in annotations)
        same_rater_rows += int(same_rater_count > 0)
        unclear_rows += int(unclear_count > 0)
        rater_counts[len(annotations)] += 1
        clear_counts[len(clear_sets)] += 1
        structures.append(
            {
                "aggregation_only": same_rater_count == 0,
                "clear_rater_count": len(clear_sets),
                "derived_labels_match": derived_matches,
                "example_hash": target["example_hash"],
                "gold_cardinality": len(target["gold_label_ids"]),
                "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
                "labeled_rater_count": len(all_labeled_sets),
                "rater_count": len(annotations),
                "same_rater_coselection_count": same_rater_count,
                "source_dev_row": target["source_dev_row"],
                "unclear_count": unclear_count,
            }
        )
        scoring_view[target["source_dev_row"]] = {
            "all_labeled_sets": all_labeled_sets,
            "clear_sets": clear_sets,
            "gold": set(target["gold_label_ids"]),
        }

    if len(by_hash) != len(selected) or duplicate_pairs:
        raise RuntimeError("Raw annotation join contains missing or duplicate comment/rater keys")
    if reproduction_mismatches:
        raise RuntimeError("Official >=2-rater aggregation does not reproduce simplified dev labels")
    if clear_empty_annotations:
        raise RuntimeError("Clear-rater empty annotations unexpectedly reached summary")

    summary = {
        "aggregation_only_rate": (len(selected) - same_rater_rows) / len(selected),
        "aggregation_only_rows": len(selected) - same_rater_rows,
        "any_unclear_rate": unclear_rows / len(selected),
        "any_unclear_rows": unclear_rows,
        "clear_empty_annotations": clear_empty_annotations,
        "clear_rater_count_distribution": dict(sorted(clear_counts.items())),
        "duplicate_comment_rater_pairs": duplicate_pairs,
        "matched_annotation_rows": len(records),
        "official_threshold_reproduction_mismatches": reproduction_mismatches,
        "rater_count_distribution": dict(sorted(rater_counts.items())),
        "rows": len(selected),
        "same_rater_coselection_rate": same_rater_rows / len(selected),
        "same_rater_coselection_rows": same_rater_rows,
    }
    return structures, scoring_view, summary


PER_EXAMPLE_METRICS = [
    "official_set_f1",
    "official_jaccard",
    "official_exact",
    "clear_rater_expected_set_f1",
    "clear_rater_expected_jaccard",
    "clear_rater_expected_exact",
    "any_clear_rater_exact",
    "best_clear_rater_set_f1",
    "all_labeled_rater_expected_set_f1",
]


def score_runs(
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    scoring_view: dict[int, dict[str, Any]],
    predictions: dict[str, dict[int, set[int]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[int, dict[str, float]]]]:
    per_example: list[dict[str, Any]] = []
    run_metrics: list[dict[str, Any]] = []
    score_index: dict[str, dict[int, dict[str, float]]] = {}

    for spec in config["predictions"]:
        run_id = spec["run_id"]
        score_index[run_id] = {}
        for target in selected:
            row_number = target["source_dev_row"]
            prediction = predictions[run_id][row_number]
            view = scoring_view[row_number]
            gold = view["gold"]
            clear_sets = view["clear_sets"]
            all_labeled_sets = view["all_labeled_sets"]
            scores = {
                "official_set_f1": set_f1(prediction, gold),
                "official_jaccard": jaccard(prediction, gold),
                "official_exact": exact(prediction, gold),
                "clear_rater_expected_set_f1": statistics.mean(
                    set_f1(prediction, labels) for labels in clear_sets
                ),
                "clear_rater_expected_jaccard": statistics.mean(
                    jaccard(prediction, labels) for labels in clear_sets
                ),
                "clear_rater_expected_exact": statistics.mean(
                    exact(prediction, labels) for labels in clear_sets
                ),
                "any_clear_rater_exact": max(exact(prediction, labels) for labels in clear_sets),
                "best_clear_rater_set_f1": max(set_f1(prediction, labels) for labels in clear_sets),
                "all_labeled_rater_expected_set_f1": statistics.mean(
                    set_f1(prediction, labels) for labels in all_labeled_sets
                ),
            }
            score_index[run_id][row_number] = scores
            per_example.append(
                {
                    "condition": spec["condition"],
                    "example_hash": target["example_hash"],
                    "gold_cardinality": len(gold),
                    "predicted_cardinality": len(prediction),
                    "predicted_neutral_emotion": 27 in prediction and len(prediction) > 1,
                    "run_id": run_id,
                    "seed": spec["seed"],
                    "source_dev_row": row_number,
                    **scores,
                }
            )

        rows = [row for row in per_example if row["run_id"] == run_id]
        summary = {
            "condition": spec["condition"],
            "empty_prediction_count": sum(int(row["predicted_cardinality"] == 0) for row in rows),
            "mean_predicted_cardinality": statistics.mean(row["predicted_cardinality"] for row in rows),
            "neutral_emotion_prediction_count": sum(
                int(row["predicted_neutral_emotion"]) for row in rows
            ),
            "rows": len(rows),
            "run_id": run_id,
            "seed": spec["seed"],
        }
        for metric in PER_EXAMPLE_METRICS:
            summary[metric] = statistics.mean(float(row[metric]) for row in rows)
        summary["rater_minus_official_set_f1"] = (
            summary["clear_rater_expected_set_f1"] - summary["official_set_f1"]
        )
        run_metrics.append(summary)
    return per_example, run_metrics, score_index


def summarize_families(run_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_metrics:
        grouped[row["condition"]].append(row)
    output: list[dict[str, Any]] = []
    summary_metrics = [
        "official_set_f1",
        "official_exact",
        "clear_rater_expected_set_f1",
        "clear_rater_expected_exact",
        "any_clear_rater_exact",
        "rater_minus_official_set_f1",
        "mean_predicted_cardinality",
    ]
    for condition, rows in sorted(grouped.items()):
        summary: dict[str, Any] = {
            "condition": condition,
            "run_count": len(rows),
            "seeds": "|".join(str(row["seed"]) for row in sorted(rows, key=lambda item: item["seed"])),
        }
        for metric in summary_metrics:
            values = [float(row[metric]) for row in rows]
            summary[f"{metric}_mean"] = statistics.mean(values)
            summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else None
        output.append(summary)
    return output


def percentile(sorted_values: list[float], quantile: float) -> float:
    position = (len(sorted_values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def paired_bootstrap(
    official_delta: list[float],
    rater_delta: list[float],
    iterations: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    count = len(official_delta)
    sampled_official: list[float] = []
    sampled_rater: list[float] = []
    sampled_shift: list[float] = []
    for _ in range(iterations):
        official_total = 0.0
        rater_total = 0.0
        for _ in range(count):
            index = rng.randrange(count)
            official_total += official_delta[index]
            rater_total += rater_delta[index]
        official_mean = official_total / count
        rater_mean = rater_total / count
        sampled_official.append(official_mean)
        sampled_rater.append(rater_mean)
        sampled_shift.append(rater_mean - official_mean)
    result: dict[str, tuple[float, float]] = {}
    for name, values in (
        ("official", sampled_official),
        ("rater", sampled_rater),
        ("shift", sampled_shift),
    ):
        values.sort()
        result[name] = (percentile(values, 0.025), percentile(values, 0.975))
    return result


def operand_scores(
    operand: dict[str, Any],
    config: dict[str, Any],
    score_index: dict[str, dict[int, dict[str, float]]],
    selected_rows: list[int],
) -> dict[int, dict[str, float]]:
    matching_specs = [
        spec
        for spec in config["predictions"]
        if spec["condition"] == operand["condition"] and spec["seed"] in operand["seeds"]
    ]
    if len(matching_specs) != len(operand["seeds"]):
        raise RuntimeError(f"Comparison operand is incomplete: {operand}")
    result: dict[int, dict[str, float]] = {}
    for row_number in selected_rows:
        result[row_number] = {
            metric: statistics.mean(
                score_index[spec["run_id"]][row_number][metric] for spec in matching_specs
            )
            for metric in ("official_set_f1", "clear_rater_expected_set_f1")
        }
    return result


def compare_models(
    config: dict[str, Any],
    score_index: dict[str, dict[int, dict[str, float]]],
    selected_rows: list[int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    tie = config["statistics"]["practical_tie_threshold"]
    material = config["statistics"]["material_shift_threshold"]
    iterations = config["statistics"]["bootstrap_iterations"]
    base_seed = config["statistics"]["bootstrap_seed"]

    for comparison in config["comparisons"]:
        candidate = operand_scores(comparison["candidate"], config, score_index, selected_rows)
        reference = operand_scores(comparison["reference"], config, score_index, selected_rows)
        official_delta = [
            candidate[row]["official_set_f1"] - reference[row]["official_set_f1"]
            for row in selected_rows
        ]
        rater_delta = [
            candidate[row]["clear_rater_expected_set_f1"]
            - reference[row]["clear_rater_expected_set_f1"]
            for row in selected_rows
        ]
        seed = int(sha256_text(f"{base_seed}:{comparison['comparison_id']}")[:16], 16)
        cis = paired_bootstrap(official_delta, rater_delta, iterations, seed)
        official_mean = statistics.mean(official_delta)
        rater_mean = statistics.mean(rater_delta)
        shift = rater_mean - official_mean
        if rater_mean <= -tie and cis["rater"][1] < 0:
            decision = "gap_remains"
        elif rater_mean >= tie and cis["rater"][0] > 0:
            decision = "candidate_advantage"
        else:
            decision = "practical_tie_or_uncertain"
        output.append(
            {
                "aggregation_materially_shifts_comparison": (
                    shift >= material and cis["shift"][0] > 0
                ),
                "bootstrap_iterations": iterations,
                "bootstrap_seed": seed,
                "candidate": comparison["candidate"]["label"],
                "comparison_id": comparison["comparison_id"],
                "decision": decision,
                "official_set_f1_delta": official_mean,
                "official_set_f1_delta_ci_high": cis["official"][1],
                "official_set_f1_delta_ci_low": cis["official"][0],
                "rater_example_losses": sum(int(value < 0) for value in rater_delta),
                "rater_example_ties": sum(int(value == 0) for value in rater_delta),
                "rater_example_wins": sum(int(value > 0) for value in rater_delta),
                "rater_set_f1_delta": rater_mean,
                "rater_set_f1_delta_ci_high": cis["rater"][1],
                "rater_set_f1_delta_ci_low": cis["rater"][0],
                "reference": comparison["reference"]["label"],
                "rater_vs_official_shift": shift,
                "rater_vs_official_shift_ci_high": cis["shift"][1],
                "rater_vs_official_shift_ci_low": cis["shift"][0],
                "rows": len(selected_rows),
            }
        )
    return output


def render_report(
    structure: dict[str, Any],
    families: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    family_lines = [
        "| Condition | Runs | Official set-F1 | Clear-rater expected set-F1 | Any-rater exact |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in families:
        family_lines.append(
            "| {condition} | {run_count} | {official:.6f} | {rater:.6f} | {any_exact:.6f} |".format(
                condition=row["condition"],
                run_count=row["run_count"],
                official=row["official_set_f1_mean"],
                rater=row["clear_rater_expected_set_f1_mean"],
                any_exact=row["any_clear_rater_exact_mean"],
            )
        )
    comparison_lines = [
        "| Comparison (candidate - reference) | Official delta | Rater-aware delta | Relative shift | Decision |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in comparisons:
        comparison_lines.append(
            "| {comparison_id} | {official:+.6f} | {rater:+.6f} | {shift:+.6f} | {decision} |".format(
                comparison_id=row["comparison_id"],
                official=row["official_set_f1_delta"],
                rater=row["rater_set_f1_delta"],
                shift=row["rater_vs_official_shift"],
                decision=row["decision"],
            )
        )
    primary = comparisons[0]
    return "\n".join(
        [
            "# EXP-036: Dev Rater-aware Frozen-prediction Diagnostic",
            "",
            "## Boundary",
            "",
            "This validation-only diagnostic rescored seven frozen prediction files on the 174",
            "GoEmotions dev rows whose official target contains `neutral` plus another emotion.",
            "It performed no training, inference, checkpoint selection, or test access.",
            "",
            "## Annotation Integrity",
            "",
            f"- Rows joined and reproduced: {structure['rows']}; official aggregation mismatches: "
            f"{structure['official_threshold_reproduction_mismatches']}.",
            f"- Matched per-rater annotations: {structure['matched_annotation_rows']}.",
            f"- Aggregation-only rows: {structure['aggregation_only_rows']} "
            f"({structure['aggregation_only_rate']:.6f}).",
            f"- Rows with unclear annotations: {structure['any_unclear_rows']} "
            f"({structure['any_unclear_rate']:.6f}).",
            "",
            "## Frozen Predictions",
            "",
            *family_lines,
            "",
            "The clear-rater score is the expected set-F1 against a randomly selected annotator",
            "who did not mark the example unclear. It is not a replacement ground truth and is not",
            "comparable to full-dev Macro-F1.",
            "",
            "## Paired Comparisons",
            "",
            *comparison_lines,
            "",
            f"Primary classification: `{primary['decision']}`. Aggregation materially shifts the",
            f"primary comparison under the frozen rule: "
            f"`{str(primary['aggregation_materially_shifts_comparison']).lower()}`.",
            "",
            "## Limits",
            "",
            "- The analysis is restricted to a purposively defined 174-row label-conflict slice.",
            "- Annotator agreement is not semantic truth, and original raters saw only one comment.",
            "- Bootstrap intervals resample examples, not training seeds.",
            "- Official full-dev metrics remain the primary model-performance evidence.",
            "- The result is behavioral evidence and does not identify an internal model mechanism.",
            "",
            "Status: completed, pending independent artifact verification.",
            "",
        ]
    )


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
    if config["experiment_id"] != "EXP-036" or config["tier"] != "Major":
        raise RuntimeError("Unexpected experiment identity")
    verify_implementation(config)

    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError("Run directory is not empty")

    labels, selected, all_gold = load_dev(config)
    selected_rows = [row["source_dev_row"] for row in selected]
    predictions, prediction_manifest = load_predictions(
        config, all_gold, set(selected_rows)
    )

    target_by_id = {row["comment_id"]: row for row in selected}
    all_records: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []
    for source in config["raw_sources"]:
        records, manifest = stream_source(source, labels, target_by_id)
        all_records.extend(records)
        source_manifests.append(manifest)
    all_records.sort(key=lambda row: (row["source_dev_row"], row["rater_hash"]))

    structures, scoring_view, structure_summary = build_rater_view(
        selected, all_records, len(labels)
    )
    per_example, run_metrics, score_index = score_runs(
        config, selected, scoring_view, predictions
    )
    family_summary = summarize_families(run_metrics)
    comparisons = compare_models(config, score_index, selected_rows)

    run_dir.mkdir(parents=True, exist_ok=True)
    private_dir = run_dir / "private"
    private_dir.mkdir()
    write_jsonl(private_dir / "matched-annotations.private.jsonl", all_records)

    write_csv(
        run_dir / "row-structure.csv",
        structures,
        [
            "source_dev_row",
            "example_hash",
            "gold_label_ids",
            "gold_cardinality",
            "rater_count",
            "clear_rater_count",
            "labeled_rater_count",
            "unclear_count",
            "same_rater_coselection_count",
            "aggregation_only",
            "derived_labels_match",
        ],
    )
    write_csv(
        run_dir / "per-example-scores.csv",
        per_example,
        [
            "condition",
            "run_id",
            "seed",
            "source_dev_row",
            "example_hash",
            "gold_cardinality",
            "predicted_cardinality",
            "predicted_neutral_emotion",
            *PER_EXAMPLE_METRICS,
        ],
    )
    run_metric_fields = [
        "condition",
        "run_id",
        "seed",
        "rows",
        "empty_prediction_count",
        "neutral_emotion_prediction_count",
        "mean_predicted_cardinality",
        *PER_EXAMPLE_METRICS,
        "rater_minus_official_set_f1",
    ]
    write_csv(run_dir / "run-metrics.csv", run_metrics, run_metric_fields)
    family_fields = ["condition", "run_count", "seeds"]
    for metric in (
        "official_set_f1",
        "official_exact",
        "clear_rater_expected_set_f1",
        "clear_rater_expected_exact",
        "any_clear_rater_exact",
        "rater_minus_official_set_f1",
        "mean_predicted_cardinality",
    ):
        family_fields.extend([f"{metric}_mean", f"{metric}_std"])
    write_csv(run_dir / "family-summary.csv", family_summary, family_fields)
    comparison_fields = [
        "comparison_id",
        "candidate",
        "reference",
        "rows",
        "bootstrap_iterations",
        "bootstrap_seed",
        "official_set_f1_delta",
        "official_set_f1_delta_ci_low",
        "official_set_f1_delta_ci_high",
        "rater_set_f1_delta",
        "rater_set_f1_delta_ci_low",
        "rater_set_f1_delta_ci_high",
        "rater_vs_official_shift",
        "rater_vs_official_shift_ci_low",
        "rater_vs_official_shift_ci_high",
        "rater_example_wins",
        "rater_example_ties",
        "rater_example_losses",
        "aggregation_materially_shifts_comparison",
        "decision",
    ]
    write_csv(run_dir / "pairwise-comparisons.csv", comparisons, comparison_fields)

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
        "family_summary": family_summary,
        "metric_semantics": {
            "primary_diagnostic": "example-weighted expected set-F1 against a clear individual rater",
            "replacement_ground_truth": False,
            "selection_use_authorized": False,
        },
        "run_metrics": run_metrics,
        "structure": structure_summary,
        "test_accessed": False,
        "test_exists": False,
    }
    write_json(run_dir / "aggregate-summary.json", aggregate)
    report = render_report(structure_summary, family_summary, comparisons)
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")

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
            f"comparison={row['comparison_id']} official_delta={row['official_set_f1_delta']:.12f} "
            f"rater_delta={row['rater_set_f1_delta']:.12f} decision={row['decision']}"
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
        "per-example-scores.csv",
        "private/matched-annotations.private.jsonl",
        "row-structure.csv",
        "run-metrics.csv",
        "source-manifest.json",
        "stdout.log",
    ]
    ended_at = utc_now()
    run = {
        "accessed_splits": ["validation"],
        "artifacts": [artifact_record(run_dir / name) for name in artifact_names],
        "command": " ".join(sys.argv),
        "config": artifact_record(config_path),
        "data_protocol": config["data_protocol"],
        "ended_at_utc": ended_at,
        "environment": {
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

