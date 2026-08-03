#!/usr/bin/env python3
"""Independently verify EXP-018 from saved dev predictions."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)


EXPERIMENT_ID = "EXP-018"
EXPECTED_ROWS = 5_426
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
THRESHOLD = 0.5
TOLERANCE = 1e-12

PROJECT_DIR = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = PROJECT_DIR / "data" / "goemotions"
DEFAULT_RUN_DIR = EXPERIMENT_DIR / "runs" / "exp-018-tfidf-ovr-logreg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute EXP-018 metrics from saved predictions."
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(recorded_path: str) -> Path:
    path = Path(recorded_path)
    return path if path.is_absolute() else PROJECT_DIR / path


def parse_id_field(value: str, row_number: int, field: str) -> list[int]:
    if not value:
        return []
    try:
        ids = [int(item) for item in value.split("|")]
    except ValueError as error:
        raise ValueError(
            f"predictions row {row_number} has invalid {field}"
        ) from error
    if ids != sorted(set(ids)):
        raise ValueError(
            f"predictions row {row_number} has unsorted or duplicate {field}"
        )
    if any(value < 0 or value >= len(EXPECTED_LABELS) for value in ids):
        raise ValueError(
            f"predictions row {row_number} has out-of-range {field}"
        )
    return ids


def load_dev_gold(path: Path) -> np.ndarray:
    gold = np.zeros((EXPECTED_ROWS, len(EXPECTED_LABELS)), dtype=np.uint8)
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_index, row in enumerate(reader):
            if row_index >= EXPECTED_ROWS:
                raise ValueError("dev.tsv contains more rows than expected")
            if len(row) != 3:
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has {len(row)} columns"
                )
            encoded_labels = row[1]
            try:
                label_ids = [int(value) for value in encoded_labels.split(",")]
            except ValueError as error:
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has invalid labels"
                ) from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has empty or duplicate labels"
                )
            if any(value < 0 or value >= len(EXPECTED_LABELS) for value in label_ids):
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has out-of-range labels"
                )
            gold[row_index, label_ids] = 1
            row_count += 1
    if row_count != EXPECTED_ROWS:
        raise ValueError(f"dev.tsv has {row_count} rows; expected {EXPECTED_ROWS}")
    return gold


def load_predictions(
    path: Path, expected_gold: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    probabilities = np.zeros(expected_gold.shape, dtype=np.float64)
    recorded_predictions = np.zeros(expected_gold.shape, dtype=np.uint8)
    probability_columns = [f"prob_{label}" for label in EXPECTED_LABELS]
    expected_columns = [
        "row_number",
        "gold_label_ids",
        "gold_labels",
        "predicted_label_ids",
        "predicted_labels",
        *probability_columns,
    ]

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_columns:
            raise ValueError("predictions.csv columns differ from EXP-018 schema")
        row_count = 0
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= EXPECTED_ROWS:
                raise ValueError("predictions.csv contains too many rows")
            if int(row["row_number"]) != row_number:
                raise ValueError(f"non-sequential prediction row {row_number}")

            gold_ids = parse_id_field(
                row["gold_label_ids"], row_number, "gold_label_ids"
            )
            expected_ids = np.flatnonzero(expected_gold[row_index]).tolist()
            if gold_ids != expected_ids:
                raise ValueError(f"gold mismatch at prediction row {row_number}")
            expected_gold_names = "|".join(EXPECTED_LABELS[value] for value in gold_ids)
            if row["gold_labels"] != expected_gold_names:
                raise ValueError(f"gold label-name mismatch at row {row_number}")

            predicted_ids = parse_id_field(
                row["predicted_label_ids"], row_number, "predicted_label_ids"
            )
            expected_predicted_names = "|".join(
                EXPECTED_LABELS[value] for value in predicted_ids
            )
            if row["predicted_labels"] != expected_predicted_names:
                raise ValueError(
                    f"predicted label-name mismatch at row {row_number}"
                )
            recorded_predictions[row_index, predicted_ids] = 1

            try:
                probabilities[row_index] = [
                    float(row[column]) for column in probability_columns
                ]
            except ValueError as error:
                raise ValueError(
                    f"invalid probability at prediction row {row_number}"
                ) from error
            row_count += 1

    if row_count != EXPECTED_ROWS:
        raise ValueError(
            f"predictions.csv has {row_count} rows; expected {EXPECTED_ROWS}"
        )
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("predictions.csv contains non-finite probabilities")
    if np.any((probabilities < 0.0) | (probabilities > 1.0)):
        raise ValueError("predictions.csv contains probabilities outside [0, 1]")

    threshold_predictions = (probabilities >= THRESHOLD).astype(np.uint8)
    if not np.array_equal(recorded_predictions, threshold_predictions):
        raise ValueError("recorded predictions do not match threshold 0.5")
    return probabilities, threshold_predictions


def recompute_metrics(
    gold: np.ndarray, predicted: np.ndarray
) -> tuple[dict[str, object], np.ndarray]:
    averages: dict[str, dict[str, float]] = {}
    for average in ("macro", "micro", "weighted", "samples"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold,
            predicted,
            average=average,
            zero_division=0,
        )
        averages[average] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }

    precision, recall, f1, support = precision_recall_fscore_support(
        gold,
        predicted,
        average=None,
        zero_division=0,
    )
    predicted_support = predicted.sum(axis=0)
    per_label = {
        label: {
            "label_id": index,
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
            "predicted_support": int(predicted_support[index]),
        }
        for index, label in enumerate(EXPECTED_LABELS)
    }

    subset_accuracy = float(accuracy_score(gold, predicted))
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = gold.sum(axis=1)
    predicted_cardinality = predicted.sum(axis=1)
    metrics: dict[str, object] = {
        "primary": {"name": "macro_f1", "value": averages["macro"]["f1"]},
        "subset_accuracy": subset_accuracy,
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": loss,
        "label_accuracy": 1.0 - loss,
        **averages,
        "label_cardinality": {
            "gold_mean": float(np.mean(gold_cardinality)),
            "predicted_mean": float(np.mean(predicted_cardinality)),
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(predicted_cardinality == 0)),
            "neutral_coprediction_rows": int(
                np.sum((predicted[:, 27] == 1) & (predicted_cardinality > 1))
            ),
        },
        "per_label": per_label,
    }
    return metrics, multilabel_confusion_matrix(gold, predicted)


def assert_close(name: str, actual: float, expected: float) -> float:
    difference = abs(actual - expected)
    if difference > TOLERANCE:
        raise ValueError(
            f"Metric mismatch for {name}: {actual} != {expected} "
            f"(difference={difference})"
        )
    return difference


def compare_metrics(recomputed: dict, recorded: dict) -> float:
    maximum_difference = 0.0
    scalar_paths = [
        ("primary.value", recomputed["primary"]["value"], recorded["primary"]["value"]),
        ("subset_accuracy", recomputed["subset_accuracy"], recorded["subset_accuracy"]),
        ("hamming_loss", recomputed["hamming_loss"], recorded["hamming_loss"]),
        ("label_accuracy", recomputed["label_accuracy"], recorded["label_accuracy"]),
        (
            "label_cardinality.gold_mean",
            recomputed["label_cardinality"]["gold_mean"],
            recorded["label_cardinality"]["gold_mean"],
        ),
        (
            "label_cardinality.predicted_mean",
            recomputed["label_cardinality"]["predicted_mean"],
            recorded["label_cardinality"]["predicted_mean"],
        ),
    ]
    for average in ("macro", "micro", "weighted", "samples"):
        for metric in ("precision", "recall", "f1"):
            scalar_paths.append(
                (
                    f"{average}.{metric}",
                    recomputed[average][metric],
                    recorded[average][metric],
                )
            )
    for name, actual, expected in scalar_paths:
        maximum_difference = max(
            maximum_difference,
            assert_close(name, float(actual), float(expected)),
        )

    if recomputed["accuracy_definition"] != recorded["accuracy_definition"]:
        raise ValueError("accuracy definition mismatch")
    if recomputed["prediction_diagnostics"] != recorded["prediction_diagnostics"]:
        raise ValueError("prediction diagnostics mismatch")

    for label in EXPECTED_LABELS:
        actual = recomputed["per_label"][label]
        expected = recorded["per_label"][label]
        for key in ("label_id", "support", "predicted_support"):
            if actual[key] != expected[key]:
                raise ValueError(f"per-label mismatch for {label}.{key}")
        for key in ("precision", "recall", "f1"):
            maximum_difference = max(
                maximum_difference,
                assert_close(
                    f"per_label.{label}.{key}",
                    float(actual[key]),
                    float(expected[key]),
                ),
            )
    return maximum_difference


def verify_per_label_csv(path: Path, metrics: dict) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(EXPECTED_LABELS):
        raise ValueError("per_label_metrics.csv row count mismatch")
    for label_id, (label, row) in enumerate(zip(EXPECTED_LABELS, rows, strict=True)):
        expected = metrics["per_label"][label]
        if int(row["label_id"]) != label_id or row["label"] != label:
            raise ValueError(f"per-label CSV identity mismatch for {label}")
        for key in ("support", "predicted_support"):
            if int(row[key]) != expected[key]:
                raise ValueError(f"per-label CSV mismatch for {label}.{key}")
        for key in ("precision", "recall", "f1"):
            if abs(float(row[key]) - expected[key]) > 1e-11:
                raise ValueError(f"per-label CSV mismatch for {label}.{key}")


def verify_confusion_csv(path: Path, confusion: np.ndarray) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(EXPECTED_LABELS):
        raise ValueError("multilabel_confusion_matrix.csv row count mismatch")
    for label_id, (label, row, matrix) in enumerate(
        zip(EXPECTED_LABELS, rows, confusion, strict=True)
    ):
        if int(row["label_id"]) != label_id or row["label"] != label:
            raise ValueError(f"confusion CSV identity mismatch for {label}")
        actual = [int(row[key]) for key in ("tn", "fp", "fn", "tp")]
        expected = [int(value) for value in matrix.ravel()]
        if actual != expected:
            raise ValueError(f"confusion CSV values mismatch for {label}")


def verify_artifact_hashes(run: dict) -> dict[str, str]:
    verified: dict[str, str] = {}
    for key in (
        "model",
        "predictions",
        "per_label_metrics",
        "multilabel_confusion_matrix",
    ):
        record = run["artifacts"][key]
        path = resolve_project_path(record["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing recorded artifact: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != record["sha256"]:
            raise ValueError(f"Artifact hash mismatch for {key}")
        verified[key] = actual_hash
    return verified


def assert_model_gitignored(run: dict) -> None:
    model_path = resolve_project_path(run["artifacts"]["model"]["path"])
    result = subprocess.run(
        ["git", "-C", str(PROJECT_DIR), "check-ignore", "-q", str(model_path)],
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("model.joblib is not ignored by Git")


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    run_dir = args.run_dir.resolve()
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("verification.json already exists; run is append-only")

    test_path = data_root / "official" / "test.tsv"
    if test_path.exists():
        raise RuntimeError("GoEmotions test.tsv exists; verification stopped")

    run_path = run_dir / "run.json"
    predictions_path = run_dir / "predictions.csv"
    per_label_path = run_dir / "per_label_metrics.csv"
    confusion_path = run_dir / "multilabel_confusion_matrix.csv"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("run.json experiment ID mismatch")
    if run.get("status") != "Completed":
        raise ValueError("run.json is not Completed")
    if run.get("test_split_accessed") is not False:
        raise ValueError("run.json does not exclude test access")
    if run.get("accessed_splits") != ["train", "dev"]:
        raise ValueError("run.json split access differs from EXP-018")
    if run["model"]["decision_rule"]["threshold"] != THRESHOLD:
        raise ValueError("run.json threshold differs from EXP-018")
    if tuple(run["data"]["labels"]) != EXPECTED_LABELS:
        raise ValueError("run.json label order mismatch")

    labels_path = data_root / "official" / "emotions.txt"
    labels = tuple(labels_path.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("local emotions.txt label order mismatch")

    for record in run["data"]["files_read"].values():
        path = resolve_project_path(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"Input hash mismatch: {path}")
    for section in ("protocol", "implementation"):
        record = run[section]
        path = resolve_project_path(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"{section} hash mismatch")

    dev_gold = load_dev_gold(data_root / "official" / "dev.tsv")
    probabilities, predictions = load_predictions(predictions_path, dev_gold)
    recomputed, confusion = recompute_metrics(dev_gold, predictions)
    maximum_difference = compare_metrics(recomputed, run["metrics"])
    verify_per_label_csv(per_label_path, recomputed)
    verify_confusion_csv(confusion_path, confusion)
    artifact_hashes = verify_artifact_hashes(run)
    assert_model_gitignored(run)

    verification = {
        "experiment_id": EXPERIMENT_ID,
        "status": "Verified",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_method": (
            "Independent reconstruction from frozen dev labels and saved "
            "probabilities; training model was not loaded for metric recomputation."
        ),
        "checks": {
            "dev_rows": int(dev_gold.shape[0]),
            "labels": int(dev_gold.shape[1]),
            "probability_shape": list(probabilities.shape),
            "threshold": THRESHOLD,
            "predictions_match_threshold": True,
            "gold_matches_frozen_dev": True,
            "aggregate_metrics_match": True,
            "per_label_metrics_match": True,
            "confusion_matrices_match": True,
            "input_hashes_match": True,
            "artifact_hashes_match": True,
            "model_gitignored": True,
            "test_split_exists": False,
            "test_split_accessed": False,
            "maximum_metric_absolute_difference": maximum_difference,
        },
        "recomputed_metrics": {
            "macro_f1": recomputed["macro"]["f1"],
            "micro_f1": recomputed["micro"]["f1"],
            "weighted_f1": recomputed["weighted"]["f1"],
            "subset_accuracy": recomputed["subset_accuracy"],
            "hamming_loss": recomputed["hamming_loss"],
            "empty_prediction_rows": recomputed["prediction_diagnostics"][
                "empty_prediction_rows"
            ],
        },
        "verified_artifact_hashes": artifact_hashes,
        "verifier": {
            "path": str(Path(__file__).resolve().relative_to(PROJECT_DIR)),
            "sha256": sha256_file(Path(__file__)),
            "python": sys.version,
        },
    }
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Verified EXP-018: "
        f"Macro-F1={recomputed['macro']['f1']:.6f}, "
        f"Micro-F1={recomputed['micro']['f1']:.6f}, "
        f"subset accuracy={recomputed['subset_accuracy']:.6f}, "
        "test=not accessed"
    )


if __name__ == "__main__":
    main()

