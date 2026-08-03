#!/usr/bin/env python3
"""Independently verify the frozen EXP-025/026 full-dev artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_MANIFEST_PATH = PROJECT_ROOT / "models" / "qwen3-1.7b" / "manifest.json"
RUNNER_PATH = SCRIPT_DIR / "run_full_dev.py"
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
VERIFIER_PATH = Path(__file__).resolve()
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint.py"
PARSER_PATH = SCRIPT_DIR / "run_resource_parser_trial.py"
CONFIG_PATHS = {
    "EXP-025": SCRIPT_DIR / "configs" / "exp-025-full-dev-zero-few-shot.json",
    "EXP-026": SCRIPT_DIR / "configs" / "exp-026-unconstrained-decoder-ablation.json",
}
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")
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
EXPECTED_RECORD_FIELDS = {
    "canonical_output",
    "condition",
    "constraint_intervened",
    "finish_reason",
    "first_blocked_step",
    "first_blocked_token_id",
    "generated_tokens",
    "generation_seconds",
    "generation_tps",
    "gold_label_ids",
    "gold_labels",
    "output_character_count",
    "output_sha256",
    "parser_error",
    "parser_valid",
    "peak_memory_gb",
    "predicted_label_ids",
    "predicted_labels",
    "prompt_tokens",
    "prompt_tps",
    "raw_argmax_blocked_steps",
    "row_number",
    "sequence_logprob_mean",
    "sequence_logprob_sum",
    "sequence_score_space",
}
PREDICTION_FIELDS = [
    "row_number",
    "gold_label_ids",
    "gold_labels",
    "predicted_label_ids",
    "predicted_labels",
    "parser_valid",
    "parser_error",
    "finish_reason",
    "canonical_output",
    "output_sha256",
    "output_character_count",
    "prompt_tokens",
    "generated_tokens",
    "generation_seconds",
    "prompt_tps",
    "generation_tps",
    "peak_memory_gb",
    "sequence_logprob_sum",
    "sequence_logprob_mean",
    "sequence_score_space",
    "constraint_intervened",
    "raw_argmax_blocked_steps",
    "first_blocked_step",
    "first_blocked_token_id",
]
TOLERANCE = 1e-10


class DifferenceTracker:
    def __init__(self) -> None:
        self.maximum = 0.0

    def close(self, name: str, actual: float, expected: float) -> None:
        difference = abs(float(actual) - float(expected))
        self.maximum = max(self.maximum, difference)
        if difference > TOLERANCE:
            raise ValueError(
                f"{name} differs: actual={actual}, expected={expected}, "
                f"difference={difference}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=tuple(CONFIG_PATHS))
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight and args.experiment is None:
        parser.error("--experiment is required unless --preflight is used")
    return args


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def resolve_project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def load_config(experiment_id: str) -> dict[str, Any]:
    config = json.loads(CONFIG_PATHS[experiment_id].read_text(encoding="utf-8"))
    if config.get("experiment_id") != experiment_id:
        raise ValueError("Config experiment ID mismatch")
    if config.get("tier") != "Major" or config.get("status") != "Registered":
        raise ValueError("Config is not a registered Major experiment")
    if tuple(item["name"] for item in config["conditions"]) != CONDITIONS:
        raise ValueError("Frozen condition order changed")
    return config


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")


def verify_static(experiment_id: str, config: dict[str, Any]) -> tuple[str, ...]:
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    verify_hash(DEV_PATH, config["data"]["dev_sha256"])
    verify_hash(LABELS_PATH, config["data"]["labels_sha256"])
    verify_hash(
        resolve_project_path(config["prompt"]["path"]),
        config["prompt"]["sha256"],
    )
    verify_hash(MODEL_MANIFEST_PATH, config["model"]["manifest_sha256"])
    if experiment_id == "EXP-025":
        verify_hash(CONSTRAINT_PATH, config["constraint"]["sha256"])
    else:
        verify_hash(PARSER_PATH, config["decoder"]["parser_source_sha256"])

    implementation = config.get("implementation")
    if not implementation:
        raise ValueError("Implementation hashes are not frozen")
    for key, path in (
        ("runner_sha256", RUNNER_PATH),
        ("metrics_sha256", METRICS_PATH),
        ("verifier_sha256", VERIFIER_PATH),
    ):
        verify_hash(path, implementation[key])

    exp018 = config["comparison_inputs"]["EXP-018"]
    verify_hash(
        resolve_project_path(exp018["predictions_path"]),
        exp018["predictions_sha256"],
    )
    verify_hash(resolve_project_path(exp018["run_path"]), exp018["run_sha256"])
    exp020 = config["comparison_inputs"]["EXP-020"]
    verify_hash(
        resolve_project_path(exp020["aggregate_metrics_path"]),
        exp020["aggregate_metrics_sha256"],
    )
    for record in exp020["seed_predictions"]:
        verify_hash(resolve_project_path(record["path"]), record["sha256"])

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order changed")
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest.get("repo_id") != config["model"]["repo_id"]
        or manifest.get("revision") != config["model"]["revision"]
        or manifest.get("conversion", {}).get("dtype") != "bfloat16"
        or manifest.get("conversion", {}).get("quantized") is not False
    ):
        raise ValueError("Model manifest differs from the frozen condition")
    return labels


def load_dev_gold(
    expected_rows: int, labels: tuple[str, ...]
) -> tuple[np.ndarray, list[list[int]]]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    seen_comment_ids: set[str] = set()
    with DEV_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle, delimiter="\t")):
            if row_index >= expected_rows:
                raise ValueError("dev.tsv contains too many rows")
            if len(row) != 3 or not all(row):
                raise ValueError(f"Invalid dev.tsv row {row_index + 1}")
            if row[2] in seen_comment_ids:
                raise ValueError("dev.tsv contains a repeated comment ID")
            seen_comment_ids.add(row[2])
            try:
                ids = [int(value) for value in row[1].split(",")]
            except ValueError as error:
                raise ValueError(f"Invalid labels at dev row {row_index + 1}") from error
            if (
                not ids
                or len(ids) != len(set(ids))
                or any(value < 0 or value >= len(labels) for value in ids)
            ):
                raise ValueError(f"Invalid label IDs at dev row {row_index + 1}")
            gold[row_index, ids] = 1
            gold_ids.append(ids)
    if len(gold_ids) != expected_rows:
        raise ValueError(f"dev.tsv has {len(gold_ids)} rows; expected {expected_rows}")
    return gold, gold_ids


def strict_parse(value: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(value.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict):
        return {"canonical_output": None, "error": "not-object", "labels": []}
    if set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-keys", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(item, str) for item in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(item not in labels for item in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    if "neutral" in values and len(values) > 1:
        return {"canonical_output": None, "error": "neutral-combined", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def expected_pairs(row_count: int) -> list[tuple[int, str]]:
    pairs: list[tuple[int, str]] = []
    for row_number in range(1, row_count + 1):
        order = CONDITIONS if row_number % 2 else tuple(reversed(CONDITIONS))
        pairs.extend((row_number, condition) for condition in order)
    return pairs


def require_finite(record: dict[str, Any], fields: Iterable[str], index: int) -> None:
    for field in fields:
        value = record[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Record {index} has nonnumeric {field}")
        if not math.isfinite(float(value)):
            raise ValueError(f"Record {index} has non-finite {field}")


def load_records(
    path: Path,
    experiment_id: str,
    labels: tuple[str, ...],
    gold_ids: list[list[int]],
) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pairs = expected_pairs(len(gold_ids))
    if len(rows) != len(pairs):
        raise ValueError(f"Generation record count {len(rows)} differs from {len(pairs)}")
    label_to_id = {label: index for index, label in enumerate(labels)}
    constrained = experiment_id == "EXP-025"
    for index, (record, pair) in enumerate(zip(rows, pairs, strict=True), start=1):
        if set(record) != EXPECTED_RECORD_FIELDS:
            raise ValueError(f"Generation record {index} schema changed")
        row_number, condition = pair
        if record["row_number"] != row_number or record["condition"] != condition:
            raise ValueError(f"Generation record order changed at line {index}")
        expected_gold = gold_ids[row_number - 1]
        if record["gold_label_ids"] != expected_gold:
            raise ValueError(f"Gold IDs differ at generation record {index}")
        if record["gold_labels"] != [labels[value] for value in expected_gold]:
            raise ValueError(f"Gold label names differ at generation record {index}")
        predicted_ids = record["predicted_label_ids"]
        predicted_labels = record["predicted_labels"]
        if (
            not isinstance(predicted_ids, list)
            or len(predicted_ids) != len(set(predicted_ids))
            or any(not isinstance(value, int) or value < 0 or value >= len(labels) for value in predicted_ids)
        ):
            raise ValueError(f"Invalid predicted IDs at generation record {index}")
        if predicted_ids != [label_to_id[label] for label in predicted_labels]:
            raise ValueError(f"Predicted names/IDs differ at generation record {index}")

        if record["parser_valid"]:
            if record["finish_reason"] != "stop" or record["parser_error"] is not None:
                raise ValueError(f"Valid record {index} has inconsistent parser metadata")
            if not isinstance(record["canonical_output"], str):
                raise ValueError(f"Valid record {index} lacks canonical output")
            parsed = strict_parse(record["canonical_output"], labels)
            if (
                parsed["error"] is not None
                or parsed["canonical_output"] != record["canonical_output"]
                or parsed["labels"] != predicted_labels
            ):
                raise ValueError(f"Canonical output differs at record {index}")
        else:
            if (
                record["canonical_output"] is not None
                or record["parser_error"] is None
                or predicted_ids
                or predicted_labels
            ):
                raise ValueError(f"Invalid-as-empty policy changed at record {index}")
            if record["finish_reason"] != "stop" and record["parser_error"] != "length-terminated":
                raise ValueError(f"Length policy changed at record {index}")

        require_finite(
            record,
            (
                "generated_tokens",
                "generation_seconds",
                "generation_tps",
                "output_character_count",
                "peak_memory_gb",
                "prompt_tokens",
                "prompt_tps",
                "sequence_logprob_mean",
                "sequence_logprob_sum",
            ),
            index,
        )
        if (
            record["generated_tokens"] < 0
            or record["generated_tokens"] > 64
            or record["generation_seconds"] <= 0
            or record["prompt_tokens"] <= 0
            or record["output_character_count"] < 0
        ):
            raise ValueError(f"Invalid resource value at generation record {index}")
        output_hash = record["output_sha256"]
        if not isinstance(output_hash, str) or len(output_hash) != 64:
            raise ValueError(f"Invalid output hash at generation record {index}")
        expected_space = "constrained" if constrained else "unconstrained"
        if record["sequence_score_space"] != expected_space:
            raise ValueError(f"Sequence-score space changed at record {index}")

        telemetry = (
            record["constraint_intervened"],
            record["raw_argmax_blocked_steps"],
            record["first_blocked_step"],
            record["first_blocked_token_id"],
        )
        if constrained:
            intervened, blocked, first_step, first_token = telemetry
            if not isinstance(intervened, bool) or not isinstance(blocked, int) or blocked < 0:
                raise ValueError(f"Invalid constraint telemetry at record {index}")
            if intervened != (blocked > 0):
                raise ValueError(f"Constraint telemetry disagrees at record {index}")
            if intervened:
                if not isinstance(first_step, int) or first_step < 0 or not isinstance(first_token, int):
                    raise ValueError(f"Missing first intervention at record {index}")
            elif first_step is not None or first_token is not None:
                raise ValueError(f"Unexpected first intervention at record {index}")
        elif any(value is not None for value in telemetry):
            raise ValueError(f"Unconstrained record {index} contains intervention telemetry")
    return rows


def records_for_condition(
    records: list[dict[str, Any]], condition: str
) -> list[dict[str, Any]]:
    selected = [record for record in records if record["condition"] == condition]
    if [record["row_number"] for record in selected] != list(range(1, len(selected) + 1)):
        raise ValueError(f"{condition} row order changed")
    return selected


def predictions_from_records(
    records: list[dict[str, Any]], label_count: int
) -> np.ndarray:
    predicted = np.zeros((len(records), label_count), dtype=np.uint8)
    for index, record in enumerate(records):
        predicted[index, record["predicted_label_ids"]] = 1
    return predicted


def compute_metrics(
    gold: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]
) -> tuple[dict[str, Any], np.ndarray]:
    averages: dict[str, dict[str, float]] = {}
    for average in ("macro", "micro", "weighted", "samples"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold, predicted, average=average, zero_division=0
        )
        averages[average] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }
    precision, recall, f1, support = precision_recall_fscore_support(
        gold, predicted, average=None, zero_division=0
    )
    predicted_support = np.sum(predicted, axis=0)
    per_label = {
        label: {
            "f1": float(f1[index]),
            "label_id": index,
            "precision": float(precision[index]),
            "predicted_support": int(predicted_support[index]),
            "recall": float(recall[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    subset = float(accuracy_score(gold, predicted))
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = np.sum(gold, axis=1)
    predicted_cardinality = np.sum(predicted, axis=1)
    neutral_index = labels.index("neutral") if "neutral" in labels else None
    neutral_coprediction_rows = (
        int(np.sum((predicted[:, neutral_index] == 1) & (predicted_cardinality > 1)))
        if neutral_index is not None
        else 0
    )
    metrics = {
        "accuracy": subset,
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": loss,
        "label_accuracy": 1.0 - loss,
        "label_cardinality": {
            "gold_mean": float(np.mean(gold_cardinality)),
            "predicted_mean": float(np.mean(predicted_cardinality)),
        },
        **averages,
        "per_label": per_label,
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(predicted_cardinality == 0)),
            "neutral_coprediction_rows": neutral_coprediction_rows,
        },
        "primary": {"name": "macro_f1", "value": averages["macro"]["f1"]},
        "subset_accuracy": subset,
    }
    return metrics, multilabel_confusion_matrix(gold, predicted)


def numeric_summary(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Cannot summarize empty or non-finite values")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "total": float(np.sum(array)),
    }


def summarize_generation(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid_count = sum(bool(record["parser_valid"]) for record in records)
    summary: dict[str, Any] = {
        "finish_reasons": dict(sorted(Counter(record["finish_reason"] for record in records).items())),
        "generated_tokens": numeric_summary(float(record["generated_tokens"]) for record in records),
        "generation_seconds": numeric_summary(float(record["generation_seconds"]) for record in records),
        "generation_tps": numeric_summary(float(record["generation_tps"]) for record in records),
        "parser_errors": dict(sorted(Counter(record["parser_error"] for record in records if record["parser_error"]).items())),
        "parser_valid_count": valid_count,
        "parser_valid_rate": valid_count / len(records),
        "peak_memory_gb_max": max(float(record["peak_memory_gb"]) for record in records),
        "prompt_tokens": numeric_summary(float(record["prompt_tokens"]) for record in records),
        "prompt_tps": numeric_summary(float(record["prompt_tps"]) for record in records),
        "sample_count": len(records),
        "sequence_logprob_mean": numeric_summary(float(record["sequence_logprob_mean"]) for record in records),
        "sequence_logprob_sum": numeric_summary(float(record["sequence_logprob_sum"]) for record in records),
    }
    if records[0]["constraint_intervened"] is not None:
        intervened = [bool(record["constraint_intervened"]) for record in records]
        blocked = [int(record["raw_argmax_blocked_steps"]) for record in records]
        first_steps = [
            int(record["first_blocked_step"])
            for record in records
            if record["first_blocked_step"] is not None
        ]
        summary["constraint_intervention"] = {
            "blocked_steps_total": int(sum(blocked)),
            "first_blocked_step_median": float(statistics.median(first_steps)) if first_steps else None,
            "rows": int(sum(intervened)),
            "rate": float(sum(intervened) / len(intervened)),
        }
    return summary


def compare_json(
    tracker: DifferenceTracker, actual: Any, expected: Any, path: str
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"{path} object keys differ")
        for key in expected:
            compare_json(tracker, actual[key], expected[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path} list differs")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            compare_json(tracker, left, right, f"{path}[{index}]")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            raise ValueError(f"{path} numeric type differs")
        tracker.close(path, actual, expected)
        return
    if actual != expected:
        raise ValueError(f"{path} differs: {actual!r} != {expected!r}")


def parse_pipe_ids(value: str, labels: tuple[str, ...], field: str) -> list[int]:
    if not value:
        return []
    try:
        values = [int(item) for item in value.split("|")]
    except ValueError as error:
        raise ValueError(f"Invalid {field}") from error
    if len(values) != len(set(values)) or any(value < 0 or value >= len(labels) for value in values):
        raise ValueError(f"Invalid {field}")
    return values


def verify_predictions_csv(
    path: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    tracker: DifferenceTracker,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PREDICTION_FIELDS:
            raise ValueError(f"Prediction schema changed: {path}")
        rows = list(reader)
    if len(rows) != len(records):
        raise ValueError(f"Prediction row count changed: {path}")
    float_fields = (
        "generation_seconds",
        "prompt_tps",
        "generation_tps",
        "peak_memory_gb",
        "sequence_logprob_sum",
        "sequence_logprob_mean",
    )
    int_fields = (
        "row_number",
        "output_character_count",
        "prompt_tokens",
        "generated_tokens",
    )
    optional_int_fields = (
        "raw_argmax_blocked_steps",
        "first_blocked_step",
        "first_blocked_token_id",
    )
    for index, (row, record) in enumerate(zip(rows, records, strict=True), start=1):
        if parse_pipe_ids(row["gold_label_ids"], labels, "gold_label_ids") != record["gold_label_ids"]:
            raise ValueError(f"Prediction gold IDs differ at row {index}")
        if parse_pipe_ids(row["predicted_label_ids"], labels, "predicted_label_ids") != record["predicted_label_ids"]:
            raise ValueError(f"Prediction IDs differ at row {index}")
        expected_strings = {
            "gold_labels": "|".join(record["gold_labels"]),
            "predicted_labels": "|".join(record["predicted_labels"]),
            "parser_valid": str(record["parser_valid"]).lower(),
            "parser_error": record["parser_error"] or "",
            "finish_reason": record["finish_reason"] or "",
            "canonical_output": record["canonical_output"] or "",
            "output_sha256": record["output_sha256"],
            "sequence_score_space": record["sequence_score_space"],
            "constraint_intervened": "" if record["constraint_intervened"] is None else str(record["constraint_intervened"]).lower(),
        }
        for field, expected in expected_strings.items():
            if row[field] != expected:
                raise ValueError(f"Prediction {field} differs at row {index}")
        for field in int_fields:
            if int(row[field]) != record[field]:
                raise ValueError(f"Prediction {field} differs at row {index}")
        for field in float_fields:
            tracker.close(f"predictions[{index}].{field}", float(row[field]), record[field])
        for field in optional_int_fields:
            expected = record[field]
            if ("" if expected is None else str(expected)) != row[field]:
                raise ValueError(f"Prediction {field} differs at row {index}")


def verify_per_label_csv(
    path: Path,
    expected: dict[str, Any],
    labels: tuple[str, ...],
    tracker: DifferenceTracker,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(labels):
        raise ValueError(f"Per-label row count changed: {path}")
    for index, row in enumerate(rows):
        label = labels[index]
        metric = expected["per_label"][label]
        if int(row["label_id"]) != index or row["label"] != label:
            raise ValueError(f"Per-label order changed at {label}")
        for field in ("precision", "recall", "f1"):
            tracker.close(f"{path.name}.{label}.{field}", float(row[field]), metric[field])
        for field in ("support", "predicted_support"):
            if int(row[field]) != metric[field]:
                raise ValueError(f"Per-label {field} changed at {label}")


def verify_confusion_csv(
    path: Path, expected: np.ndarray, labels: tuple[str, ...]
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(labels):
        raise ValueError(f"Confusion row count changed: {path}")
    for index, row in enumerate(rows):
        if int(row["label_id"]) != index or row["label"] != labels[index]:
            raise ValueError(f"Confusion label order changed at row {index + 1}")
        actual = [int(row[field]) for field in ("tn", "fp", "fn", "tp")]
        if actual != expected[index].ravel().astype(int).tolist():
            raise ValueError(f"Confusion values changed for {labels[index]}")


def verify_condition_summary(
    path: Path,
    task: dict[str, dict[str, Any]],
    generation: dict[str, dict[str, Any]],
    tracker: DifferenceTracker,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if [row["condition"] for row in rows] != list(CONDITIONS):
        raise ValueError("Condition summary order changed")
    for row in rows:
        condition = row["condition"]
        metric = task[condition]
        resource = generation[condition]
        expected = {
            "macro_f1": metric["macro"]["f1"],
            "micro_f1": metric["micro"]["f1"],
            "weighted_f1": metric["weighted"]["f1"],
            "samples_f1": metric["samples"]["f1"],
            "subset_accuracy": metric["subset_accuracy"],
            "parser_valid_rate": resource["parser_valid_rate"],
            "empty_prediction_rows": metric["prediction_diagnostics"]["empty_prediction_rows"],
            "predicted_label_cardinality": metric["label_cardinality"]["predicted_mean"],
            "generation_seconds_total": resource["generation_seconds"]["total"],
            "generation_seconds_median": resource["generation_seconds"]["median"],
            "generation_seconds_p95": resource["generation_seconds"]["p95"],
            "prompt_tokens_total": resource["prompt_tokens"]["total"],
            "generated_tokens_total": resource["generated_tokens"]["total"],
            "peak_memory_gb_max": resource["peak_memory_gb_max"],
        }
        for field, value in expected.items():
            tracker.close(f"condition-summary.{condition}.{field}", float(row[field]), value)
        intervention = resource.get("constraint_intervention")
        wanted = "" if intervention is None else intervention["rate"]
        if wanted == "":
            if row["constraint_intervention_rate"] != "":
                raise ValueError("Unexpected intervention rate in condition summary")
        else:
            tracker.close(
                f"condition-summary.{condition}.constraint_intervention_rate",
                float(row["constraint_intervention_rate"]),
                wanted,
            )


def read_prediction_matrix(
    path: Path, labels: tuple[str, ...], expected_rows: int
) -> tuple[np.ndarray, np.ndarray]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    predicted = np.zeros_like(gold)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_rows:
        raise ValueError(f"Prediction count changed: {path}")
    for index, row in enumerate(rows):
        if int(row["row_number"]) != index + 1:
            raise ValueError(f"Prediction order changed: {path}")
        for field, matrix in (("gold_label_ids", gold), ("predicted_label_ids", predicted)):
            matrix[index, parse_pipe_ids(row[field], labels, field)] = 1
    return gold, predicted


def macro_f1_samples(
    gold: np.ndarray, predicted: np.ndarray, indices: np.ndarray
) -> np.ndarray:
    gold_selected = gold[indices]
    predicted_selected = predicted[indices]
    gold_support = np.sum(gold_selected, axis=1, dtype=np.int32)
    predicted_support = np.sum(predicted_selected, axis=1, dtype=np.int32)
    true_positive = np.sum(gold_selected & predicted_selected, axis=1, dtype=np.int32)
    denominator = gold_support + predicted_support
    per_label = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=denominator != 0,
    )
    return np.mean(per_label, axis=1)


def bootstrap_inputs(
    experiment_id: str,
    config: dict[str, Any],
    labels: tuple[str, ...],
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], list[tuple[str, str, str]]]:
    prefix = "constrained" if experiment_id == "EXP-025" else "unconstrained"
    named = {f"{prefix}-{condition}": predictions[condition] for condition in CONDITIONS}
    comparisons = [
        (
            f"{prefix}-zero-shot-minus-{prefix}-few-shot-synthetic-3",
            f"{prefix}-zero-shot",
            f"{prefix}-few-shot-synthetic-3",
        )
    ]
    if experiment_id == "EXP-026":
        exp025_dir = resolve_project_path(config["comparison_inputs"]["EXP-025"]["run_dir"])
        verification = json.loads((exp025_dir / "verification.json").read_text(encoding="utf-8"))
        if verification.get("status") != "Passed":
            raise ValueError("EXP-025 verification did not pass")
        for condition in CONDITIONS:
            paired_gold, paired = read_prediction_matrix(
                exp025_dir / condition / "predictions.csv", labels, gold.shape[0]
            )
            if not np.array_equal(paired_gold, gold):
                raise ValueError("EXP-025 gold differs from EXP-026 dev")
            named[f"constrained-{condition}"] = paired
            comparisons.append(
                (
                    f"unconstrained-minus-constrained-{condition}",
                    f"unconstrained-{condition}",
                    f"constrained-{condition}",
                )
            )
    for seed_record in config["comparison_inputs"]["EXP-020"]["seed_predictions"]:
        seed = int(seed_record["seed"])
        baseline_gold, baseline = read_prediction_matrix(
            resolve_project_path(seed_record["path"]), labels, gold.shape[0]
        )
        if not np.array_equal(baseline_gold, gold):
            raise ValueError(f"EXP-020 seed {seed} gold differs from dev")
        named[f"bert-seed-{seed}"] = baseline
        for condition in CONDITIONS:
            comparisons.append(
                (
                    f"{prefix}-{condition}-minus-bert-seed-{seed}",
                    f"{prefix}-{condition}",
                    f"bert-seed-{seed}",
                )
            )
    return named, comparisons


def recompute_bootstrap(
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
    comparisons: list[tuple[str, str, str]],
    replicates: int,
    seed: int,
    practical_threshold: float,
) -> dict[str, Any]:
    samples = {name: np.empty(replicates, dtype=np.float64) for name in predictions}
    rng = np.random.default_rng(seed)
    batch_size = 100
    for start in range(0, replicates, batch_size):
        stop = min(replicates, start + batch_size)
        indices = rng.integers(0, gold.shape[0], size=(stop - start, gold.shape[0]), dtype=np.int32)
        for name, predicted in predictions.items():
            samples[name][start:stop] = macro_f1_samples(gold, predicted, indices)
    observed = {
        name: float(precision_recall_fscore_support(gold, predicted, average="macro", zero_division=0)[2])
        for name, predicted in predictions.items()
    }
    results = {}
    for comparison_name, left, right in comparisons:
        differences = samples[left] - samples[right]
        lower, upper = np.quantile(differences, [0.025, 0.975])
        difference = observed[left] - observed[right]
        results[comparison_name] = {
            "ci_95_percentile": {"lower": float(lower), "upper": float(upper)},
            "left": left,
            "observed_macro_f1_difference": float(difference),
            "practical_effect": abs(difference) >= practical_threshold,
            "practical_threshold": practical_threshold,
            "right": right,
            "two_sided_interval_excludes_zero": bool(lower > 0 or upper < 0),
        }
    return {
        "batch_size": batch_size,
        "confidence_interval": 0.95,
        "comparisons": results,
        "replicates": replicates,
        "resampling_unit": "dev row with replacement",
        "seed": seed,
        "statistic": "paired Macro-F1 difference",
    }


def selection_record(
    experiment_id: str,
    config: dict[str, Any],
    task: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if experiment_id == "EXP-026":
        return {
            "candidate_override_allowed": False,
            "reason": config["evaluation"]["selection_rule"],
            "selected_condition": None,
        }
    zero = task["zero-shot"]["macro"]["f1"]
    few = task["few-shot-synthetic-3"]["macro"]["f1"]
    threshold = config["evaluation"]["practical_tie_absolute_macro_f1"]
    difference = zero - few
    if abs(difference) < threshold:
        selected = "zero-shot"
        reason = "practical tie; zero-shot selected for lower cost and complexity"
    elif difference > 0:
        selected = "zero-shot"
        reason = "zero-shot has higher dev Macro-F1 beyond the practical threshold"
    else:
        selected = "few-shot-synthetic-3"
        reason = "few-shot has higher dev Macro-F1 beyond the practical threshold"
    return {
        "absolute_difference": abs(difference),
        "difference_zero_minus_few": difference,
        "practical_tie": abs(difference) < threshold,
        "practical_tie_threshold": threshold,
        "reason": reason,
        "selected_condition": selected,
    }


def aggregate_record(
    experiment_id: str,
    config: dict[str, Any],
    task: dict[str, dict[str, Any]],
    generation: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exp018 = config["comparison_inputs"]["EXP-018"]["dev_macro_f1"]
    exp020 = config["comparison_inputs"]["EXP-020"]["dev_macro_f1_mean"]
    comparisons = {
        condition: {
            "macro_f1": task[condition]["macro"]["f1"],
            "minus_exp_018": task[condition]["macro"]["f1"] - exp018,
            "minus_exp_020_mean": task[condition]["macro"]["f1"] - exp020,
        }
        for condition in CONDITIONS
    }
    return {
        "baseline_comparisons": comparisons,
        "conditions": {
            condition: {"generation": generation[condition], "task": task[condition]}
            for condition in CONDITIONS
        },
        "experiment_id": experiment_id,
        "selection": selection_record(experiment_id, config, task),
    }


def joint_decoder_analysis(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    task: dict[str, dict[str, Any]],
    generation: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exp025_dir = resolve_project_path(config["comparison_inputs"]["EXP-025"]["run_dir"])
    constrained_records = [
        json.loads(line)
        for line in (exp025_dir / "generation-records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(constrained_records) != len(records):
        raise ValueError("EXP-025 generation record count changed")
    constrained_by_key = {
        (record["row_number"], record["condition"]): record
        for record in constrained_records
    }
    conditions: dict[str, Any] = {}
    for condition in CONDITIONS:
        unrestricted = records_for_condition(records, condition)
        constrained = [constrained_by_key[(record["row_number"], condition)] for record in unrestricted]
        valid_pairs = [
            (left, right)
            for left, right in zip(unrestricted, constrained, strict=True)
            if left["parser_valid"] and right["parser_valid"]
        ]
        exact = sum(
            set(left["predicted_label_ids"]) == set(right["predicted_label_ids"])
            for left, right in valid_pairs
        )
        jaccards = []
        for left, right in valid_pairs:
            left_set = set(left["predicted_label_ids"])
            right_set = set(right["predicted_label_ids"])
            jaccards.append(len(left_set & right_set) / len(left_set | right_set))
        constrained_payload = json.loads((exp025_dir / condition / "metrics.json").read_text(encoding="utf-8"))
        constrained_task = constrained_payload["task"]
        constrained_generation = constrained_payload["generation"]
        resource_deltas = {
            "generated_tokens_total": generation[condition]["generated_tokens"]["total"] - constrained_generation["generated_tokens"]["total"],
            "generation_seconds": {
                key: generation[condition]["generation_seconds"][key] - constrained_generation["generation_seconds"][key]
                for key in ("total", "median", "p95")
            },
            "prompt_tokens_total": generation[condition]["prompt_tokens"]["total"] - constrained_generation["prompt_tokens"]["total"],
        }
        conditions[condition] = {
            "constrained_macro_f1": constrained_task["macro"]["f1"],
            "constrained_parser_valid_rate": constrained_generation["parser_valid_rate"],
            "constraint_intervention": constrained_generation.get("constraint_intervention"),
            "exact_label_set_agreement": {
                "count": exact,
                "denominator_both_valid": len(valid_pairs),
                "rate": exact / len(valid_pairs) if valid_pairs else None,
            },
            "label_set_jaccard_mean_on_both_valid": float(np.mean(jaccards)) if jaccards else None,
            "macro_f1_delta_unconstrained_minus_constrained": task[condition]["macro"]["f1"] - constrained_task["macro"]["f1"],
            "per_label": {
                label: {
                    "unconstrained_minus_constrained_predicted_support": task[condition]["per_label"][label]["predicted_support"] - constrained_task["per_label"][label]["predicted_support"]
                }
                for label in EXPECTED_LABELS
            },
            "predicted_cardinality_delta_unconstrained_minus_constrained": task[condition]["label_cardinality"]["predicted_mean"] - constrained_task["label_cardinality"]["predicted_mean"],
            "resource_deltas_unconstrained_minus_constrained": resource_deltas,
            "unconstrained_macro_f1": task[condition]["macro"]["f1"],
            "unconstrained_parser_valid_count": generation[condition]["parser_valid_count"],
            "unconstrained_parser_valid_rate": generation[condition]["parser_valid_rate"],
            "validity_rate_delta_unconstrained_minus_constrained": generation[condition]["parser_valid_rate"] - constrained_generation["parser_valid_rate"],
        }
    return {
        "analysis_scope": "paired full-dev decoder ablation",
        "conditions": conditions,
        "exp_025_artifacts": {
            "generation_records": artifact(exp025_dir / "generation-records.jsonl"),
            "verification": artifact(exp025_dir / "verification.json"),
        },
        "invalid_output_primary_policy": "invalid or length outputs are empty predictions",
        "valid_pair_metrics_are_diagnostic_only": True,
    }


def verify_source_artifacts(
    run: dict[str, Any], experiment_id: str, config: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    expected_paths = {
        "config": CONFIG_PATHS[experiment_id],
        "labels": LABELS_PATH,
        "metrics_implementation": METRICS_PATH,
        "model_manifest": MODEL_MANIFEST_PATH,
        "prompt": resolve_project_path(config["prompt"]["path"]),
        "runner": RUNNER_PATH,
        "verifier": VERIFIER_PATH,
        "constraint" if experiment_id == "EXP-025" else "parser_source": (
            CONSTRAINT_PATH if experiment_id == "EXP-025" else PARSER_PATH
        ),
    }
    if set(run["source_artifacts"]) != set(expected_paths):
        raise ValueError("run.json source artifact keys changed")
    checked = {}
    for name, path in expected_paths.items():
        expected = artifact(path)
        if run["source_artifacts"][name] != expected:
            raise ValueError(f"Source artifact changed: {name}")
        checked[f"source:{name}"] = expected
    return checked


def verify_generated_artifacts(
    run: dict[str, Any], config: dict[str, Any], run_dir: Path
) -> dict[str, dict[str, Any]]:
    required = set(config["artifacts"]["required"])
    expected_keys = required - {"run.json", "verification.json"}
    if set(run["generated_artifacts"]) != expected_keys:
        raise ValueError("run.json generated artifact keys changed")
    checked = {}
    for relative in config["artifacts"]["required"]:
        path = run_dir / relative
        if relative == "verification.json":
            if path.exists():
                raise FileExistsError("verification.json already exists; run is append-only")
            continue
        if not path.is_file():
            raise FileNotFoundError(path)
        current = artifact(path)
        checked[relative] = current
        if relative != "run.json" and run["generated_artifacts"][relative] != current:
            raise ValueError(f"Generated artifact changed: {relative}")
    return checked


def run_preflight() -> None:
    if TEST_PATH.exists():
        raise ValueError("test.tsv must remain absent")
    for experiment_id in CONFIG_PATHS:
        config = load_config(experiment_id)
        verify_static(experiment_id, config)
        run_dir = resolve_project_path(config["artifacts"]["output_dir"])
        if run_dir.exists():
            raise FileExistsError(f"Preflight requires absent run directory: {run_dir}")
    fixtures = {
        '{"labels":["joy"]}': True,
        ' {"labels":["joy","gratitude"]} ': True,
        '{"labels":["neutral","joy"]}': False,
        '```json\n{"labels":["joy"]}\n```': False,
    }
    for value, expected in fixtures.items():
        if (strict_parse(value, EXPECTED_LABELS)["error"] is None) != expected:
            raise ValueError(f"Independent parser fixture failed: {value!r}")
    fixture_gold = np.array([[1, 0], [1, 1], [0, 1]], dtype=np.uint8)
    fixture_predicted = np.array([[1, 0], [0, 1], [0, 0]], dtype=np.uint8)
    fixture_metrics, _ = compute_metrics(fixture_gold, fixture_predicted, ("a", "b"))
    if not math.isclose(fixture_metrics["macro"]["f1"], 2 / 3, abs_tol=1e-12):
        raise ValueError("Independent metric fixture failed")
    print(
        json.dumps(
            {
                "dev_accessed": False,
                "implementation_hashes_verified": True,
                "metric_library": "scikit-learn",
                "run_directories_absent": True,
                "status": "Passed",
                "test_absent": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


def verify_run(experiment_id: str) -> None:
    config = load_config(experiment_id)
    labels = verify_static(experiment_id, config)
    run_dir = resolve_project_path(config["artifacts"]["output_dir"])
    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("experiment_id") != experiment_id or run.get("status") != "Completed":
        raise ValueError("run.json is not a completed matching experiment")
    if (
        run.get("accessed_splits") != ["dev"]
        or run.get("validation_split_accessed") is not True
        or run.get("test_split_accessed") is not False
        or run.get("verification_status") != "Pending"
    ):
        raise ValueError("run.json split or verification state changed")
    if run.get("completed_generation_pairs") != config["resource_budget"]["measured_generations"]:
        raise ValueError("run.json generation count is incomplete")
    if run.get("api_cost_usd") != 0 or run["resource_usage"].get("api_cost_usd") != 0:
        raise ValueError("Unexpected API cost")
    if run["resource_usage"]["total_seconds"] > config["resource_budget"]["wall_time_minutes_max"] * 60:
        raise ValueError("Run exceeded frozen wall-time budget")
    if run["resource_usage"]["overall_peak_memory_gb"] > config["resource_budget"]["peak_mlx_memory_gb_max"]:
        raise ValueError("Run exceeded frozen memory budget")

    checked = verify_source_artifacts(run, experiment_id, config)
    checked.update(verify_generated_artifacts(run, config, run_dir))
    gold, gold_ids = load_dev_gold(config["data"]["dev_rows"], labels)
    records = load_records(
        run_dir / "generation-records.jsonl", experiment_id, labels, gold_ids
    )
    tracker = DifferenceTracker()
    task: dict[str, dict[str, Any]] = {}
    generation: dict[str, dict[str, Any]] = {}
    predictions: dict[str, np.ndarray] = {}
    for condition in CONDITIONS:
        condition_records = records_for_condition(records, condition)
        predicted = predictions_from_records(condition_records, len(labels))
        metrics, confusion = compute_metrics(gold, predicted, labels)
        resources = summarize_generation(condition_records)
        task[condition] = metrics
        generation[condition] = resources
        predictions[condition] = predicted
        condition_dir = run_dir / condition
        verify_predictions_csv(
            condition_dir / "predictions.csv", condition_records, labels, tracker
        )
        saved = json.loads((condition_dir / "metrics.json").read_text(encoding="utf-8"))
        compare_json(
            tracker,
            saved,
            {"condition": condition, "generation": resources, "task": metrics},
            f"{condition}.metrics",
        )
        verify_per_label_csv(
            condition_dir / "per-label-metrics.csv", metrics, labels, tracker
        )
        verify_confusion_csv(
            condition_dir / "multilabel-confusion-matrix.csv", confusion, labels
        )

    verify_condition_summary(
        run_dir / "condition-summary.csv", task, generation, tracker
    )
    expected_aggregate = aggregate_record(experiment_id, config, task, generation)
    saved_aggregate = json.loads((run_dir / "aggregate-metrics.json").read_text(encoding="utf-8"))
    compare_json(tracker, saved_aggregate, expected_aggregate, "aggregate")

    named, comparisons = bootstrap_inputs(experiment_id, config, labels, gold, predictions)
    bootstrap_config = config["evaluation"]["bootstrap"]
    expected_bootstrap = recompute_bootstrap(
        gold,
        named,
        comparisons,
        bootstrap_config["replicates"],
        bootstrap_config["seed"],
        config["evaluation"]["practical_tie_absolute_macro_f1"],
    )
    saved_bootstrap = json.loads((run_dir / "paired-bootstrap.json").read_text(encoding="utf-8"))
    compare_json(tracker, saved_bootstrap, expected_bootstrap, "paired-bootstrap")

    if experiment_id == "EXP-026":
        expected_joint = joint_decoder_analysis(config, records, task, generation)
        saved_joint = json.loads((run_dir / "joint-decoder-analysis.json").read_text(encoding="utf-8"))
        compare_json(tracker, saved_joint, expected_joint, "joint-decoder-analysis")

    verification = {
        "checked_artifacts": checked,
        "completed_generation_pairs": len(records),
        "dev_rows": gold.shape[0],
        "experiment_id": experiment_id,
        "independent_metric_library": "scikit-learn",
        "max_absolute_numeric_difference": tracker.maximum,
        "privacy": {
            "invalid_raw_generation_stored": False,
            "prompt_expanded_input_stored": False,
            "raw_input_text_stored": False,
            "upstream_comment_id_stored": False,
        },
        "status": "Passed",
        "test_split_absent": not TEST_PATH.exists(),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "verifier": artifact(VERIFIER_PATH),
    }
    (run_dir / "verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verification, indent=2, sort_keys=True))


def main() -> None:
    args = parse_args()
    if args.preflight:
        run_preflight()
    else:
        verify_run(args.experiment)


if __name__ == "__main__":
    main()
