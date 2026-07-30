#!/usr/bin/env python3
"""Independently verify TweetEval validation artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


PROJECT_DIR = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = (
    EXPERIMENT_DIR / "runs" / "exp-005-word-char-linear-svm"
)
DEFAULT_DATA_DIR = (
    PROJECT_DIR
    / "data"
    / "tweeteval-emotion"
    / "official"
    / "datasets"
    / "emotion"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute validation metrics without test access."
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--expected-experiment-id",
        help="Optional experiment ID that run.json must contain.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_integer_lines(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8") as handle:
        return [int(line.strip()) for line in handle]


def assert_close(name: str, actual: float, expected: float) -> None:
    if abs(actual - expected) > 1e-12:
        raise AssertionError(f"{name}: {actual} != {expected}")


def read_predictions(path: Path) -> tuple[list[int], list[int], int]:
    gold: list[int] = []
    predicted: list[int] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        decision_headers = [
            name for name in (reader.fieldnames or []) if name.startswith("decision_")
        ]
        if len(decision_headers) != 4:
            raise AssertionError(
                f"Expected 4 decision columns, found {decision_headers}"
            )
        for expected_row, row in enumerate(reader, start=1):
            if int(row["row_number"]) != expected_row:
                raise AssertionError(
                    f"Non-sequential row_number at {expected_row}"
                )
            gold.append(int(row["gold_label_id"]))
            predicted.append(int(row["predicted_label_id"]))
            for header in decision_headers:
                float(row[header])
    return gold, predicted, len(decision_headers)


def read_confusion_csv(path: Path) -> list[list[int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) != 5 or len(rows[0]) != 5:
        raise AssertionError("Unexpected confusion-matrix CSV shape")
    return [[int(value) for value in row[1:]] for row in rows[1:]]


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    data_dir = args.data_dir.resolve()
    run_path = run_dir / "run.json"
    predictions_path = run_dir / "predictions.csv"
    confusion_path = run_dir / "confusion_matrix.csv"

    for path in (run_path, predictions_path, confusion_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    run = json.loads(run_path.read_text(encoding="utf-8"))
    experiment_id = run.get("experiment_id")
    if not experiment_id:
        raise AssertionError("Missing experiment ID")
    if (
        args.expected_experiment_id
        and experiment_id != args.expected_experiment_id
    ):
        raise AssertionError(
            f"Unexpected experiment ID: {experiment_id} != "
            f"{args.expected_experiment_id}"
        )
    if run.get("test_split_accessed") is not False:
        raise AssertionError("run.json does not explicitly exclude test")
    if run.get("accessed_splits") != ["train", "validation"]:
        raise AssertionError("Unexpected accessed_splits")

    official_gold = read_integer_lines(data_dir / "val_labels.txt")
    saved_gold, predictions, decision_column_count = read_predictions(
        predictions_path
    )
    if saved_gold != official_gold:
        raise AssertionError(
            "Saved gold labels do not exactly match official validation labels"
        )

    class_ids = sorted(int(value) for value in run["data"]["label_mapping"])
    accuracy = accuracy_score(official_gold, predictions)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            official_gold,
            predictions,
            labels=class_ids,
            average="macro",
            zero_division=0,
        )
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            official_gold,
            predictions,
            labels=class_ids,
            average="weighted",
            zero_division=0,
        )
    )
    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            official_gold,
            predictions,
            labels=class_ids,
            average=None,
            zero_division=0,
        )
    )
    matrix = confusion_matrix(
        official_gold, predictions, labels=class_ids
    ).tolist()

    assert_close("accuracy", accuracy, run["metrics"]["accuracy"])
    assert_close(
        "macro precision",
        macro_precision,
        run["metrics"]["macro"]["precision"],
    )
    assert_close("macro recall", macro_recall, run["metrics"]["macro"]["recall"])
    assert_close("macro f1", macro_f1, run["metrics"]["macro"]["f1"])
    assert_close(
        "weighted precision",
        weighted_precision,
        run["metrics"]["weighted"]["precision"],
    )
    assert_close(
        "weighted recall",
        weighted_recall,
        run["metrics"]["weighted"]["recall"],
    )
    assert_close(
        "weighted f1", weighted_f1, run["metrics"]["weighted"]["f1"]
    )

    label_names = run["metrics"]["confusion_matrix"]["labels"]
    for index, label_name in enumerate(label_names):
        recorded = run["metrics"]["per_class"][label_name]
        assert_close(
            f"{label_name} precision",
            class_precision[index],
            recorded["precision"],
        )
        assert_close(
            f"{label_name} recall",
            class_recall[index],
            recorded["recall"],
        )
        assert_close(
            f"{label_name} f1", class_f1[index], recorded["f1"]
        )
        if int(class_support[index]) != recorded["support"]:
            raise AssertionError(f"{label_name} support mismatch")

    if matrix != run["metrics"]["confusion_matrix"]["values"]:
        raise AssertionError("run.json confusion matrix mismatch")
    if matrix != read_confusion_csv(confusion_path):
        raise AssertionError("confusion_matrix.csv mismatch")

    recorded_files = run["data"]["files_read"]
    checked_files = {
        "mapping": data_dir / "mapping.txt",
        "train_text": data_dir / "train_text.txt",
        "train_labels": data_dir / "train_labels.txt",
        "validation_text": data_dir / "val_text.txt",
        "validation_labels": data_dir / "val_labels.txt",
    }
    for name, path in checked_files.items():
        if sha256(path) != recorded_files[name]["sha256"]:
            raise AssertionError(f"Input hash mismatch: {name}")

    for name in (
        "model",
        "predictions",
        "confusion_matrix_csv",
        "confusion_matrix_png",
    ):
        artifact = run["artifacts"][name]
        artifact_path = PROJECT_DIR / artifact["path"]
        if sha256(artifact_path) != artifact["sha256"]:
            raise AssertionError(f"Artifact hash mismatch: {name}")

    verification = {
        "experiment_id": experiment_id,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Local independent validation metric and artifact verification; "
            "evidence remains Completed until durable commit or equivalent."
        ),
        "test_split_accessed": False,
        "checks": {
            "official_validation_gold_exact_match": True,
            "prediction_rows": len(predictions),
            "decision_columns": decision_column_count,
            "metrics_recomputed": True,
            "per_class_metrics_recomputed": True,
            "confusion_matrix_recomputed": True,
            "input_hashes_match": True,
            "artifact_hashes_match": True,
        },
        "recomputed": {
            "macro_f1": float(macro_f1),
            "accuracy": float(accuracy),
            "weighted_f1": float(weighted_f1),
        },
        "run_json_sha256": sha256(run_path),
        "predictions_sha256": sha256(predictions_path),
    }
    verification_path = run_dir / "verification.json"
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Verified {len(predictions)} validation predictions.")
    print(f"Macro-F1: {macro_f1:.6f}")
    print(f"Accuracy: {accuracy:.6f}")
    print("Test split accessed: no.")
    print(f"Verification: {verification_path}")


if __name__ == "__main__":
    main()
