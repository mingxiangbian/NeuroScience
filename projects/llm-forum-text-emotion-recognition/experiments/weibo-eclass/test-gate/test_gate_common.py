#!/usr/bin/env python3
"""Shared execution helpers for the frozen EXP-049 test gate."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
from typing import Any, Iterable, Sequence


INVALID_LABEL = "__invalid__"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def tree_artifact(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            item = artifact(path)
            item["path"] = path.relative_to(root).as_posix()
            files.append(item)
    return {
        "file_count": len(files),
        "files": files,
        "path": display_path(root),
        "total_bytes": sum(item["bytes"] for item in files),
    }


def verify_spec(spec: dict[str, Any]) -> Path:
    path = resolve_project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(spec["bytes"]) or sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {spec['path']}")
    return path


def verify_tree_spec(spec: dict[str, Any]) -> Path:
    root = resolve_project_path(spec["path"])
    observed = tree_artifact(root)
    if observed != spec:
        raise ValueError(f"Frozen artifact tree drift: {spec['path']}")
    return root


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)
    if private:
        path.chmod(0o600)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def append_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    if not path.exists():
        path.touch(mode=0o600)
    with path.open("a", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())
    path.chmod(0o600)


def verify_file_against_data_spec(spec: dict[str, Any]) -> Path:
    path = resolve_project_path(spec["path"])
    if path.stat().st_size != int(spec["bytes"]) or sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen data drift: {spec['path']}")
    return path


def validate_view_pair(row: dict[str, Any], index: int, split: str) -> None:
    target = row.get("views", {}).get("target_only", {}).get("target")
    paired = row.get("views", {}).get("previous_context", {})
    if not isinstance(target, str) or not target.strip() or paired.get("target") != target:
        raise ValueError(f"Paired target drift at {split}:{index}")
    previous = paired.get("previous")
    if bool(previous) != bool(row.get("context_available")):
        raise ValueError(f"Context flag drift at {split}:{index}")


def load_train_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    spec = contract["data"]["train"]
    rows = read_jsonl(verify_file_against_data_spec(spec))
    expected_keys = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "label",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    labels = set(contract["labels"])
    seen = set()
    for index, row in enumerate(rows):
        if set(row) != expected_keys:
            raise ValueError(f"Train schema drift at row {index}")
        if row["protocol_id"] != contract["data"]["protocol_id"] or row["label"] not in labels:
            raise ValueError(f"Train protocol or label drift at row {index}")
        if row["sample_id"] in seen:
            raise ValueError("Duplicate train sample_id")
        seen.add(row["sample_id"])
        validate_view_pair(row, index, "train")
    if len(rows) != int(spec["rows"]):
        raise ValueError("Train row-count drift")
    return rows


def load_test_inputs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    spec = contract["data"]["test_inputs"]
    rows = read_jsonl(verify_file_against_data_spec(spec))
    expected_keys = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    seen = set()
    for index, row in enumerate(rows):
        if set(row) != expected_keys or "label" in row:
            raise ValueError(f"Test-input schema drift at row {index}")
        if row["protocol_id"] != contract["data"]["protocol_id"]:
            raise ValueError(f"Test protocol drift at row {index}")
        if not isinstance(row.get("sample_id"), str) or row["sample_id"] in seen:
            raise ValueError("Duplicate or invalid test sample_id")
        if not isinstance(row.get("group_id"), str) or not row["group_id"]:
            raise ValueError("Invalid test group_id")
        seen.add(row["sample_id"])
        validate_view_pair(row, index, "test")
    if len(rows) != int(spec["rows"]):
        raise ValueError("Test-input row-count drift")
    return rows


def load_test_labels(contract: dict[str, Any]) -> list[dict[str, Any]]:
    spec = contract["data"]["test_labels"]
    rows = read_jsonl(verify_file_against_data_spec(spec))
    expected_keys = {"label", "protocol_id", "sample_id", "schema_version"}
    labels = set(contract["labels"])
    seen = set()
    for index, row in enumerate(rows):
        if set(row) != expected_keys:
            raise ValueError(f"Test-label schema drift at row {index}")
        if row["protocol_id"] != contract["data"]["protocol_id"] or row["label"] not in labels:
            raise ValueError(f"Test-label protocol or ontology drift at row {index}")
        if row["sample_id"] in seen:
            raise ValueError("Duplicate test-label sample_id")
        seen.add(row["sample_id"])
    if len(rows) != int(spec["rows"]):
        raise ValueError("Test-label row-count drift")
    return rows


def render_target_only(prompt: dict[str, Any], row: dict[str, Any]) -> str:
    return prompt["target_only_template"].format(
        target=row["views"]["target_only"]["target"]
    )


def classification_metrics(
    gold: Sequence[str], predictions: Sequence[str], labels: Sequence[str]
) -> dict[str, Any]:
    if len(gold) != len(predictions) or not gold:
        raise ValueError("Metrics require aligned non-empty vectors")
    allowed = set(labels) | {INVALID_LABEL}
    if any(value not in labels for value in gold) or any(value not in allowed for value in predictions):
        raise ValueError("Metric label outside frozen ontology")
    per_class = {}
    f1_values = []
    precision_values = []
    recall_values = []
    weighted_f1 = 0.0
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predictions))
        fp = sum(g != label and p == label for g, p in zip(gold, predictions))
        fn = sum(g == label and p != label for g, p in zip(gold, predictions))
        support = sum(g == label for g in gold)
        predicted_support = sum(p == label for p in predictions)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "f1": f1,
            "precision": precision,
            "predicted_support": predicted_support,
            "recall": recall,
            "support": support,
        }
        f1_values.append(f1)
        precision_values.append(precision)
        recall_values.append(recall)
        weighted_f1 += f1 * support
    columns = list(labels) + [INVALID_LABEL]
    confusion = [
        [
            sum(g == gold_label and p == predicted for g, p in zip(gold, predictions))
            for predicted in columns
        ]
        for gold_label in labels
    ]
    return {
        "accuracy": sum(g == p for g, p in zip(gold, predictions)) / len(gold),
        "confusion_columns": columns,
        "confusion_matrix": confusion,
        "macro_f1": statistics.fmean(f1_values),
        "macro_precision": statistics.fmean(precision_values),
        "macro_recall": statistics.fmean(recall_values),
        "per_class": per_class,
        "rows": len(gold),
        "weighted_f1": weighted_f1 / len(gold),
    }


def slice_masks(
    rows: Sequence[dict[str, Any]], gold: Sequence[str], contract: dict[str, Any]
) -> dict[str, list[bool]]:
    long_tail = set(contract["evaluation"]["long_tail_labels"])
    return {
        "all": [True] * len(rows),
        "context_available": [bool(row["context_available"]) for row in rows],
        "first_clause": [not bool(row["context_available"]) for row in rows],
        "ambiguous_target": [bool(row["ambiguous_target"]) for row in rows],
        "unambiguous_target": [not bool(row["ambiguous_target"]) for row in rows],
        "no_emotion": [label == "no_emotion" for label in gold],
        "emotion_label": [label != "no_emotion" for label in gold],
        "long_tail_label": [label in long_tail for label in gold],
    }


def metrics_by_slice(
    rows: Sequence[dict[str, Any]],
    gold: Sequence[str],
    predictions: Sequence[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    masks = slice_masks(rows, gold, contract)
    if tuple(masks) != tuple(contract["evaluation"]["slices"]):
        raise ValueError("Metric-slice order drift")
    result = {}
    for name, mask in masks.items():
        chosen_gold = [value for value, keep in zip(gold, mask) if keep]
        chosen_predictions = [value for value, keep in zip(predictions, mask) if keep]
        result[name] = classification_metrics(
            chosen_gold, chosen_predictions, contract["labels"]
        )
    return result


def quantile(values: Sequence[float | int], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot summarize an empty sequence")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty sequence")
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "p95": quantile(values, 0.95),
        "sum": sum(values),
    }


def family_macro_f1(
    gold: Sequence[str], predictions: dict[str, Sequence[str]], units: Sequence[str], labels: Sequence[str]
) -> float:
    return statistics.fmean(
        classification_metrics(gold, predictions[unit], labels)["macro_f1"] for unit in units
    )


def bootstrap_family_contrast(
    rows: Sequence[dict[str, Any]],
    gold: Sequence[str],
    predictions: dict[str, Sequence[str]],
    candidate_units: Sequence[str],
    reference_units: Sequence[str],
    labels: Sequence[str],
    repeats: int,
    namespace: str,
) -> dict[str, Any]:
    group_indices: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        group_indices.setdefault(row["group_id"], []).append(index)
    groups = sorted(group_indices)
    randomizer = random.Random(int(sha256_text(namespace)[:16], 16))
    deltas = []
    for _ in range(repeats):
        sampled_groups = [randomizer.choice(groups) for _ in groups]
        indices = [index for group in sampled_groups for index in group_indices[group]]
        sampled_gold = [gold[index] for index in indices]
        sampled_predictions = {
            unit: [predictions[unit][index] for index in indices]
            for unit in set(candidate_units) | set(reference_units)
        }
        deltas.append(
            family_macro_f1(sampled_gold, sampled_predictions, candidate_units, labels)
            - family_macro_f1(sampled_gold, sampled_predictions, reference_units, labels)
        )
    observed = family_macro_f1(gold, predictions, candidate_units, labels) - family_macro_f1(
        gold, predictions, reference_units, labels
    )
    return {
        "candidate_units": list(candidate_units),
        "ci95": [quantile(deltas, 0.025), quantile(deltas, 0.975)],
        "groups": len(groups),
        "observed_delta": observed,
        "probability_delta_gt_zero": sum(value > 0 for value in deltas) / len(deltas),
        "reference_units": list(reference_units),
        "repeats": repeats,
        "resampling_unit": "group_id",
    }


def primary_decision(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "material_improvement"
    if delta <= -threshold:
        return "material_degradation"
    return "practical_tie"


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def train_label_counts(rows: Sequence[dict[str, Any]], labels: Sequence[str]) -> dict[str, int]:
    counts = Counter(row["label"] for row in rows)
    return {label: counts[label] for label in labels}
