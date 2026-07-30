#!/usr/bin/env python3
"""Independently verify EXP-011 metrics, hashes, and split discipline."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


EXPERIMENT_ID = "EXP-011"
FLOAT32_PROBABILITY_SUM_ATOL = 5e-7
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-011-roberta-base-finetuning"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_close(name: str, actual: float, expected: float) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{name}: {actual} != {expected}")


def resolve_artifact(artifact: dict[str, str]) -> Path:
    path = PROJECT_ROOT / artifact["path"]
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256(path) != artifact["sha256"]:
        raise AssertionError(f"Artifact hash mismatch: {path}")
    return path


def read_integer_lines(path: Path) -> list[int]:
    return [
        int(value)
        for value in path.read_text(encoding="utf-8").splitlines()
    ]


def read_predictions(
    path: Path,
    expected_seed: int,
    expected_mapping: dict[int, str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 374:
        raise AssertionError(f"Prediction row count: {len(rows)} != 374")

    labels = []
    predictions = []
    probabilities = []
    probability_fields = [
        f"probability_{expected_mapping[label_id]}"
        for label_id in sorted(expected_mapping)
    ]
    for expected_row, row in enumerate(rows, start=1):
        if int(row["row_number"]) != expected_row:
            raise AssertionError("Prediction row numbering changed")
        if int(row["seed"]) != expected_seed:
            raise AssertionError("Prediction seed mismatch")
        gold = int(row["gold_label_id"])
        predicted = int(row["predicted_label_id"])
        if row["gold_label"] != expected_mapping[gold]:
            raise AssertionError("Gold label name mismatch")
        if row["predicted_label"] != expected_mapping[predicted]:
            raise AssertionError("Predicted label name mismatch")
        row_probabilities = [
            float(row[field]) for field in probability_fields
        ]
        if not math.isclose(
            sum(row_probabilities),
            1.0,
            rel_tol=0.0,
            abs_tol=FLOAT32_PROBABILITY_SUM_ATOL,
        ):
            raise AssertionError("Probabilities do not sum to one")
        if int(np.argmax(row_probabilities)) != predicted:
            raise AssertionError("Predicted label is not probability argmax")
        labels.append(gold)
        predictions.append(predicted)
        probabilities.append(row_probabilities)
    return (
        np.asarray(labels),
        np.asarray(predictions),
        np.asarray(probabilities),
    )


def recompute_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    mapping: dict[int, str],
) -> dict[str, Any]:
    class_ids = sorted(mapping)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average="macro",
            zero_division=0,
        )
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average="weighted",
            zero_division=0,
        )
    )
    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average=None,
            zero_division=0,
        )
    )
    matrix = confusion_matrix(labels, predictions, labels=class_ids)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "confusion_matrix": {
            "labels": [mapping[label_id] for label_id in class_ids],
            "orientation": "rows=true, columns=predicted",
            "values": matrix.tolist(),
        },
        "macro": {
            "f1": float(macro_f1),
            "precision": float(macro_precision),
            "recall": float(macro_recall),
        },
        "per_class": {
            mapping[label_id]: {
                "f1": float(class_f1[index]),
                "label_id": label_id,
                "precision": float(class_precision[index]),
                "recall": float(class_recall[index]),
                "support": int(class_support[index]),
            }
            for index, label_id in enumerate(class_ids)
        },
        "weighted": {
            "f1": float(weighted_f1),
            "precision": float(weighted_precision),
            "recall": float(weighted_recall),
        },
    }


def compare_metrics(
    prefix: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    assert_close(
        f"{prefix}.accuracy", actual["accuracy"], expected["accuracy"]
    )
    for average in ("macro", "weighted"):
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{average}.{metric}",
                actual[average][metric],
                expected[average][metric],
            )
    for label, values in actual["per_class"].items():
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{label}.{metric}",
                values[metric],
                expected["per_class"][label][metric],
            )
        if values["support"] != expected["per_class"][label]["support"]:
            raise AssertionError(f"{prefix}.{label}.support mismatch")
    if actual["confusion_matrix"] != expected["confusion_matrix"]:
        raise AssertionError(f"{prefix} confusion matrix mismatch")


def read_confusion_csv(path: Path) -> list[list[int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return [[int(value) for value in row[1:]] for row in rows[1:]]


def verify_history(
    path: Path,
    seed_result: dict[str, Any],
) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    evaluation_rows = [row for row in rows if row["eval_macro_f1"]]
    training_rows = [row for row in rows if row["loss"]]
    if len(evaluation_rows) != 5:
        raise AssertionError(
            f"Expected five epoch evaluations, got {len(evaluation_rows)}"
        )
    if not training_rows:
        raise AssertionError("No training-loss records")
    best_value = max(float(row["eval_macro_f1"]) for row in evaluation_rows)
    assert_close(
        "history.best_macro_f1",
        best_value,
        seed_result["best_checkpoint"]["metric_value"],
    )
    best_step = seed_result["best_checkpoint"]["global_step"]
    selected = [
        row
        for row in evaluation_rows
        if int(float(row["step"])) == best_step
    ]
    if len(selected) != 1:
        raise AssertionError("Selected checkpoint is absent from history")
    return {
        "evaluation_record_count": len(evaluation_rows),
        "training_loss_record_count": len(training_rows),
    }


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
        "values": values,
    }


def compare_summary(
    name: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    if len(actual["values"]) != len(expected["values"]):
        raise AssertionError(f"{name}.values length mismatch")
    for index, (left, right) in enumerate(
        zip(actual["values"], expected["values"], strict=True)
    ):
        assert_close(f"{name}.values[{index}]", left, right)
    assert_close(f"{name}.mean", actual["mean"], expected["mean"])
    assert_close(
        f"{name}.sample_std",
        actual["sample_std"],
        expected["sample_std"],
    )


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    run_path = run_dir / "run.json"
    run = read_json(run_path)
    if run["experiment_id"] != EXPERIMENT_ID:
        raise AssertionError("Unexpected experiment ID")
    if run["status"] != "Completed" or run["tier"] != "Major":
        raise AssertionError("EXP-011 is not a completed Major run")
    if run["accessed_splits"] != ["train", "validation"]:
        raise AssertionError("Unexpected accessed split list")
    if run["test_split_accessed"] is not False:
        raise AssertionError("run.json does not explicitly exclude test")
    if run["validation_split_accessed"] is not True:
        raise AssertionError("Validation access was not recorded")
    if any("test" in value["path"].lower() for value in run["data"]["files_read"].values()):
        raise AssertionError("A test path appears in files_read")

    config_path = resolve_artifact(run["artifacts"]["config"])
    config = read_json(config_path)
    mapping = {
        int(label_id): label
        for label_id, label in run["data"]["label_mapping"].items()
    }
    validation_labels_path = (
        PROJECT_ROOT / run["data"]["files_read"]["validation_labels"]["path"]
    )
    if (
        sha256(validation_labels_path)
        != run["data"]["files_read"]["validation_labels"]["sha256"]
    ):
        raise AssertionError("Validation label hash mismatch")
    expected_validation_labels = np.asarray(
        read_integer_lines(validation_labels_path)
    )

    seed_checks = []
    for seed_result in run["seed_results"]:
        seed = seed_result["seed"]
        artifacts = seed_result["artifacts"]
        predictions_path = resolve_artifact(artifacts["predictions"])
        confusion_path = resolve_artifact(artifacts["confusion_matrix_csv"])
        resolve_artifact(artifacts["confusion_matrix_png"])
        history_path = resolve_artifact(artifacts["history"])
        metrics_path = resolve_artifact(artifacts["metrics"])
        model_path = resolve_artifact(
            seed_result["best_checkpoint"]["model_file"]
        )

        labels, predictions, probabilities = read_predictions(
            predictions_path, seed, mapping
        )
        if not np.array_equal(labels, expected_validation_labels):
            raise AssertionError(f"Seed {seed} validation gold labels changed")
        if not np.isfinite(probabilities).all():
            raise AssertionError(f"Seed {seed} has non-finite probabilities")

        recomputed = recompute_metrics(labels, predictions, mapping)
        compare_metrics(
            f"seed-{seed}", recomputed, seed_result["validation"]
        )
        if (
            read_confusion_csv(confusion_path)
            != recomputed["confusion_matrix"]["values"]
        ):
            raise AssertionError(f"Seed {seed} confusion CSV mismatch")

        stored_metrics = read_json(metrics_path)
        expected_metrics = {
            key: value
            for key, value in seed_result.items()
            if key != "artifacts"
        }
        if stored_metrics != expected_metrics:
            raise AssertionError(f"Seed {seed} metrics.json mismatch")

        history_check = verify_history(history_path, seed_result)
        seed_checks.append(
            {
                "history": history_check,
                "model_sha256": sha256(model_path),
                "prediction_count": len(labels),
                "seed": seed,
                "validation_accuracy": recomputed["accuracy"],
                "validation_macro_f1": recomputed["macro"]["f1"],
            }
        )

    if [item["seed"] for item in seed_checks] != config["training"]["seeds"]:
        raise AssertionError("Seed order or set changed")

    aggregate_path = resolve_artifact(run["artifacts"]["aggregate_metrics"])
    aggregate = read_json(aggregate_path)
    metric_specs = {
        "accuracy": ("accuracy",),
        "loss": ("loss",),
        "macro_f1": ("macro", "f1"),
        "macro_precision": ("macro", "precision"),
        "macro_recall": ("macro", "recall"),
        "weighted_f1": ("weighted", "f1"),
    }
    for summary_name, path in metric_specs.items():
        values = []
        for result in run["seed_results"]:
            current: Any = result["validation"]
            for key in path:
                current = current[key]
            values.append(float(current))
        compare_summary(
            f"validation.{summary_name}",
            summarize(values),
            aggregate["validation"][summary_name],
        )

    mean_macro_f1 = aggregate["validation"]["macro_f1"]["mean"]
    expected_delta = (
        mean_macro_f1
        - config["comparison"]["validation_macro_f1"]
    )
    assert_close(
        "comparison.mean_macro_f1_delta",
        expected_delta,
        aggregate["comparison"]["mean_macro_f1_delta"],
    )
    expected_pass = (
        expected_delta
        >= config["comparison"]["practical_improvement_threshold"]
    )
    if aggregate["comparison"]["practical_improvement_passed"] != expected_pass:
        raise AssertionError("Practical-improvement decision mismatch")
    if run["comparison"] != aggregate["comparison"]:
        raise AssertionError("run.json aggregate comparison mismatch")

    resolve_artifact(run["artifacts"]["seed_summary"])
    resolve_artifact(run["artifacts"]["learning_curves"])
    verification = {
        "accessed_splits_verified": ["train", "validation"],
        "aggregate_metrics_recomputed": True,
        "artifact_hashes_verified": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "run_json_sha256": sha256(run_path),
        "seed_checks": seed_checks,
        "status": "Verified",
        "test_split_accessed": False,
        "validation_gold_hash_verified": True,
    }
    verification_path = run_dir / "verification.json"
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
