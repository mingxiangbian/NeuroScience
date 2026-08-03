#!/usr/bin/env python3
"""Independently verify EXP-020 from saved GoEmotions dev probabilities."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)


EXPERIMENT_ID = "EXP-020"
EXPECTED_ROWS = 5_426
THRESHOLD = 0.3
TOLERANCE = 1e-10
EXP018_MACRO_F1 = 0.20364430957028798
EXPECTED_HASHES = {
    "train.tsv": "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5",
    "dev.tsv": "575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62",
    "emotions.txt": "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89",
}
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

EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXPERIMENT_DIR.parents[2]
REPO_DIR = PROJECT_DIR.parents[1]
DEFAULT_DATA_ROOT = PROJECT_DIR / "data" / "goemotions"
DEFAULT_RUN_DIR = EXPERIMENT_DIR / "runs" / "exp-020-bert-base-cased"


class DifferenceTracker:
    def __init__(self) -> None:
        self.maximum = 0.0

    def close(self, name: str, actual: float, expected: float) -> None:
        difference = abs(float(actual) - float(expected))
        self.maximum = max(self.maximum, difference)
        if difference > TOLERANCE:
            raise ValueError(
                f"{name} differs: actual={actual}, expected={expected}, "
                f"diff={difference}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else PROJECT_DIR / path


def verify_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project_path(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != record["bytes"]:
        raise ValueError(f"Artifact byte size changed: {path}")
    actual_hash = sha256_file(path)
    if actual_hash != record["sha256"]:
        raise ValueError(f"Artifact hash changed: {path}")
    return path


def parse_ids(value: str, row_number: int, field: str) -> list[int]:
    if not value:
        return []
    try:
        ids = [int(item) for item in value.split("|")]
    except ValueError as error:
        raise ValueError(
            f"Prediction row {row_number} has invalid {field}"
        ) from error
    if ids != sorted(set(ids)):
        raise ValueError(
            f"Prediction row {row_number} has unsorted or duplicate {field}"
        )
    if any(label_id < 0 or label_id >= len(EXPECTED_LABELS) for label_id in ids):
        raise ValueError(
            f"Prediction row {row_number} has out-of-range {field}"
        )
    return ids


def load_dev_gold(path: Path) -> np.ndarray:
    gold = np.zeros((EXPECTED_ROWS, len(EXPECTED_LABELS)), dtype=np.uint8)
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_index, row in enumerate(reader):
            if row_index >= EXPECTED_ROWS:
                raise ValueError("dev.tsv contains too many rows")
            if len(row) != 3:
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has {len(row)} columns"
                )
            try:
                label_ids = [int(item) for item in row[1].split(",")]
            except ValueError as error:
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has invalid labels"
                ) from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has invalid label cardinality"
                )
            if any(
                label_id < 0 or label_id >= len(EXPECTED_LABELS)
                for label_id in label_ids
            ):
                raise ValueError(
                    f"dev.tsv row {row_index + 1} has out-of-range labels"
                )
            gold[row_index, label_ids] = 1
            row_count += 1
    if row_count != EXPECTED_ROWS:
        raise ValueError(
            f"dev.tsv has {row_count} rows; expected {EXPECTED_ROWS}"
        )
    return gold


def load_predictions(
    path: Path, expected_gold: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    probability_columns = [f"prob_{label}" for label in EXPECTED_LABELS]
    expected_columns = [
        "row_number",
        "gold_label_ids",
        "gold_labels",
        "predicted_label_ids",
        "predicted_labels",
        *probability_columns,
    ]
    probabilities = np.zeros(expected_gold.shape, dtype=np.float64)
    recorded_predictions = np.zeros(expected_gold.shape, dtype=np.uint8)

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_columns:
            raise ValueError(f"Unexpected prediction schema in {path}")
        forbidden = {"text", "comment_id", "upstream_comment_id"}
        if forbidden.intersection(reader.fieldnames):
            raise ValueError("Predictions contain a forbidden raw-data column")
        row_count = 0
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= EXPECTED_ROWS:
                raise ValueError("Predictions contain too many rows")
            if int(row["row_number"]) != row_number:
                raise ValueError(f"Non-sequential prediction row {row_number}")
            gold_ids = parse_ids(
                row["gold_label_ids"], row_number, "gold_label_ids"
            )
            expected_ids = np.flatnonzero(expected_gold[row_index]).tolist()
            if gold_ids != expected_ids:
                raise ValueError(f"Gold mismatch at prediction row {row_number}")
            if row["gold_labels"] != "|".join(
                EXPECTED_LABELS[label_id] for label_id in gold_ids
            ):
                raise ValueError(
                    f"Gold label-name mismatch at prediction row {row_number}"
                )

            predicted_ids = parse_ids(
                row["predicted_label_ids"],
                row_number,
                "predicted_label_ids",
            )
            if row["predicted_labels"] != "|".join(
                EXPECTED_LABELS[label_id] for label_id in predicted_ids
            ):
                raise ValueError(
                    f"Prediction label-name mismatch at row {row_number}"
                )
            recorded_predictions[row_index, predicted_ids] = 1
            try:
                probabilities[row_index] = [
                    float(row[column]) for column in probability_columns
                ]
            except ValueError as error:
                raise ValueError(
                    f"Invalid probability at prediction row {row_number}"
                ) from error
            row_count += 1

    if row_count != EXPECTED_ROWS:
        raise ValueError(
            f"Predictions have {row_count} rows; expected {EXPECTED_ROWS}"
        )
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("Predictions contain NaN or Inf")
    if np.any((probabilities < 0.0) | (probabilities > 1.0)):
        raise ValueError("Predictions contain probabilities outside [0, 1]")
    threshold_predictions = (probabilities >= THRESHOLD).astype(np.uint8)
    if not np.array_equal(recorded_predictions, threshold_predictions):
        raise ValueError("Recorded labels do not match threshold 0.3")
    return probabilities, threshold_predictions


def compute_metrics(
    gold: np.ndarray, predicted: np.ndarray
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
    predicted_support = predicted.sum(axis=0)
    per_label = {
        label: {
            "f1": float(f1[index]),
            "label_id": index,
            "precision": float(precision[index]),
            "predicted_support": int(predicted_support[index]),
            "recall": float(recall[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(EXPECTED_LABELS)
    }
    subset_accuracy = float(accuracy_score(gold, predicted))
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = gold.sum(axis=1)
    predicted_cardinality = predicted.sum(axis=1)
    return {
        "accuracy": subset_accuracy,
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
            "neutral_coprediction_rows": int(
                np.sum((predicted[:, 27] == 1) & (predicted_cardinality > 1))
            ),
        },
        "primary": {"name": "macro_f1", "value": averages["macro"]["f1"]},
        "subset_accuracy": subset_accuracy,
    }, multilabel_confusion_matrix(gold, predicted)


def compare_metrics(
    tracker: DifferenceTracker,
    actual: dict[str, Any],
    expected: dict[str, Any],
    prefix: str,
) -> None:
    scalar_paths = [
        "accuracy",
        "hamming_loss",
        "label_accuracy",
        "subset_accuracy",
        "label_cardinality.gold_mean",
        "label_cardinality.predicted_mean",
        "macro.precision",
        "macro.recall",
        "macro.f1",
        "micro.precision",
        "micro.recall",
        "micro.f1",
        "weighted.precision",
        "weighted.recall",
        "weighted.f1",
        "samples.precision",
        "samples.recall",
        "samples.f1",
        "primary.value",
    ]
    for path in scalar_paths:
        left: Any = actual
        right: Any = expected
        for key in path.split("."):
            left = left[key]
            right = right[key]
        tracker.close(f"{prefix}.{path}", left, right)

    if actual["primary"]["name"] != expected["primary"]["name"]:
        raise ValueError(f"{prefix}.primary.name changed")
    if actual["accuracy_definition"] != expected["accuracy_definition"]:
        raise ValueError(f"{prefix}.accuracy_definition changed")
    if (
        actual["prediction_diagnostics"]
        != expected["prediction_diagnostics"]
    ):
        raise ValueError(f"{prefix}.prediction_diagnostics changed")

    for label in EXPECTED_LABELS:
        for field in ("precision", "recall", "f1"):
            tracker.close(
                f"{prefix}.per_label.{label}.{field}",
                actual["per_label"][label][field],
                expected["per_label"][label][field],
            )
        for field in ("label_id", "support", "predicted_support"):
            if (
                actual["per_label"][label][field]
                != expected["per_label"][label][field]
            ):
                raise ValueError(
                    f"{prefix}.per_label.{label}.{field} changed"
                )


def verify_per_label_csv(
    path: Path,
    expected: dict[str, Any],
    tracker: DifferenceTracker,
    seed: int,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(EXPECTED_LABELS):
        raise ValueError(f"Seed {seed} per-label row count changed")
    for index, row in enumerate(rows):
        label = EXPECTED_LABELS[index]
        metric = expected["per_label"][label]
        if int(row["label_id"]) != index or row["label"] != label:
            raise ValueError(f"Seed {seed} per-label order changed")
        for field in ("precision", "recall", "f1"):
            tracker.close(
                f"seed-{seed}.per_label_csv.{label}.{field}",
                float(row[field]),
                metric[field],
            )
        for field in ("support", "predicted_support"):
            if int(row[field]) != metric[field]:
                raise ValueError(
                    f"Seed {seed} per-label {label} {field} changed"
                )


def verify_confusion_csv(
    path: Path, expected: np.ndarray, seed: int
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(EXPECTED_LABELS):
        raise ValueError(f"Seed {seed} confusion row count changed")
    for index, row in enumerate(rows):
        if int(row["label_id"]) != index or row["label"] != EXPECTED_LABELS[index]:
            raise ValueError(f"Seed {seed} confusion label order changed")
        actual = [int(row[field]) for field in ("tn", "fp", "fn", "tp")]
        wanted = expected[index].ravel().astype(int).tolist()
        if actual != wanted:
            raise ValueError(
                f"Seed {seed} confusion differs for {EXPECTED_LABELS[index]}"
            )


def metric_value(metrics: dict[str, Any], path: str) -> float:
    value: Any = metrics
    for key in path.split("."):
        value = value[key]
    return float(value)


def summary_stats(values_by_seed: dict[str, float]) -> dict[str, Any]:
    values = list(values_by_seed.values())
    return {
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
        "values_by_seed": values_by_seed,
    }


def recompute_aggregate(seed_metrics: dict[int, dict[str, Any]]) -> dict[str, Any]:
    metric_paths = {
        "hamming_loss": "hamming_loss",
        "label_accuracy": "label_accuracy",
        "macro_f1": "macro.f1",
        "macro_precision": "macro.precision",
        "macro_recall": "macro.recall",
        "micro_f1": "micro.f1",
        "predicted_label_cardinality": "label_cardinality.predicted_mean",
        "samples_f1": "samples.f1",
        "subset_accuracy": "subset_accuracy",
        "weighted_f1": "weighted.f1",
    }
    validation = {
        name: summary_stats(
            {
                str(seed): metric_value(metrics, path)
                for seed, metrics in seed_metrics.items()
            }
        )
        for name, path in metric_paths.items()
    }
    validation["empty_prediction_rows"] = summary_stats(
        {
            str(seed): float(
                metrics["prediction_diagnostics"]["empty_prediction_rows"]
            )
            for seed, metrics in seed_metrics.items()
        }
    )
    per_label = {}
    for label in EXPECTED_LABELS:
        per_label[label] = {
            metric: summary_stats(
                {
                    str(seed): float(metrics["per_label"][label][metric])
                    for seed, metrics in seed_metrics.items()
                }
            )
            for metric in ("precision", "recall", "f1")
        }
        per_label[label]["support"] = next(iter(seed_metrics.values()))[
            "per_label"
        ][label]["support"]
    delta = validation["macro_f1"]["mean"] - EXP018_MACRO_F1
    return {
        "comparison": {
            "baseline": "EXP-018",
            "baseline_dev_macro_f1": EXP018_MACRO_F1,
            "mean_macro_f1_delta": delta,
            "practical_improvement": delta >= 0.005,
            "practical_threshold": 0.005,
        },
        "external_reference": {
            "directly_comparable": False,
            "paper_bert_macro_f1": 0.46,
            "paper_split": "test",
            "reason": "EXP-020 evaluates dev; official 0.46 is a test result.",
        },
        "per_label": per_label,
        "sample_standard_deviation": True,
        "seeds": list(seed_metrics),
        "validation": validation,
    }


def compare_aggregate(
    tracker: DifferenceTracker,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    if actual["seeds"] != expected["seeds"]:
        raise ValueError("Aggregate seed order changed")
    if actual["sample_standard_deviation"] is not True:
        raise ValueError("Aggregate no longer uses sample standard deviation")
    if actual["external_reference"] != expected["external_reference"]:
        raise ValueError("External reference boundary changed")
    if actual["comparison"]["baseline"] != expected["comparison"]["baseline"]:
        raise ValueError("Aggregate comparison baseline changed")
    if (
        actual["comparison"]["practical_improvement"]
        != expected["comparison"]["practical_improvement"]
    ):
        raise ValueError("Aggregate practical-improvement result changed")
    for field in (
        "baseline_dev_macro_f1",
        "mean_macro_f1_delta",
        "practical_threshold",
    ):
        tracker.close(
            f"aggregate.comparison.{field}",
            actual["comparison"][field],
            expected["comparison"][field],
        )

    for metric, expected_summary in expected["validation"].items():
        actual_summary = actual["validation"][metric]
        tracker.close(
            f"aggregate.{metric}.mean",
            actual_summary["mean"],
            expected_summary["mean"],
        )
        tracker.close(
            f"aggregate.{metric}.sample_std",
            actual_summary["sample_std"],
            expected_summary["sample_std"],
        )
        if actual_summary["values_by_seed"].keys() != expected_summary[
            "values_by_seed"
        ].keys():
            raise ValueError(f"Aggregate {metric} seed keys changed")
        for seed, value in expected_summary["values_by_seed"].items():
            tracker.close(
                f"aggregate.{metric}.seed-{seed}",
                actual_summary["values_by_seed"][seed],
                value,
            )

    for label in EXPECTED_LABELS:
        if (
            actual["per_label"][label]["support"]
            != expected["per_label"][label]["support"]
        ):
            raise ValueError(f"Aggregate support changed for {label}")
        for metric in ("precision", "recall", "f1"):
            actual_summary = actual["per_label"][label][metric]
            expected_summary = expected["per_label"][label][metric]
            tracker.close(
                f"aggregate.per_label.{label}.{metric}.mean",
                actual_summary["mean"],
                expected_summary["mean"],
            )
            tracker.close(
                f"aggregate.per_label.{label}.{metric}.sample_std",
                actual_summary["sample_std"],
                expected_summary["sample_std"],
            )


def verify_seed_summary(
    path: Path,
    run_seed_records: dict[int, dict[str, Any]],
    recomputed: dict[int, dict[str, Any]],
    tracker: DifferenceTracker,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if [int(row["seed"]) for row in rows] != list(recomputed):
        raise ValueError("seed_summary.csv seed order changed")
    metric_fields = {
        "hamming_loss": "hamming_loss",
        "macro_f1": "macro.f1",
        "macro_precision": "macro.precision",
        "macro_recall": "macro.recall",
        "micro_f1": "micro.f1",
        "predicted_label_cardinality": "label_cardinality.predicted_mean",
        "samples_f1": "samples.f1",
        "subset_accuracy": "subset_accuracy",
        "weighted_f1": "weighted.f1",
    }
    for row in rows:
        seed = int(row["seed"])
        metrics = recomputed[seed]
        for field, path_name in metric_fields.items():
            tracker.close(
                f"seed_summary.seed-{seed}.{field}",
                float(row[field]),
                metric_value(metrics, path_name),
            )
        if int(row["empty_prediction_rows"]) != metrics[
            "prediction_diagnostics"
        ]["empty_prediction_rows"]:
            raise ValueError(f"Seed {seed} empty-prediction count changed")
        if row["model_sha256"] != run_seed_records[seed]["model"][
            "final_model"
        ]["sha256"]:
            raise ValueError(f"Seed {seed} model hash changed in summary")


def ensure_gitignored(path: Path) -> None:
    relative = path.resolve().relative_to(REPO_DIR)
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), "check-ignore", "-q", str(relative)]
    )
    if result.returncode != 0:
        raise ValueError(f"Model artifact is not gitignored: {path}")


def run() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    run_dir = args.run_dir.resolve()
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("verification.json already exists; run is append-only")

    run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if run_record.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("run.json experiment ID mismatch")
    if run_record.get("status") != "Completed":
        raise ValueError("EXP-020 run is not completed")
    if run_record.get("accessed_splits") != ["train", "dev"]:
        raise ValueError("Unexpected accessed split list")
    if run_record.get("test_split_accessed") is not False:
        raise ValueError("run.json reports test access")
    test_path = data_root / "official" / "test.tsv"
    if test_path.exists():
        raise ValueError("test.tsv exists during verification")

    labels = tuple(
        (data_root / "official" / "emotions.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    if labels != EXPECTED_LABELS:
        raise ValueError("Label order changed")
    for name, expected_hash in EXPECTED_HASHES.items():
        path = data_root / "official" / name
        if sha256_file(path) != expected_hash:
            raise ValueError(f"Input hash changed: {name}")

    for key in (
        "aggregate_metrics",
        "config",
        "implementation",
        "model_manifest",
        "protocol",
        "requirements_lock",
        "seed_summary",
    ):
        verify_artifact(run_record["artifacts"][key])

    dev_gold = load_dev_gold(data_root / "official" / "dev.tsv")
    tracker = DifferenceTracker()
    recomputed: dict[int, dict[str, Any]] = {}
    run_seed_records: dict[int, dict[str, Any]] = {}
    verified_seed_artifacts: dict[str, Any] = {}

    for seed_record in run_record["seed_runs"]:
        seed = int(seed_record["seed"])
        if seed in recomputed:
            raise ValueError(f"Duplicate seed {seed}")
        run_seed_records[seed] = seed_record
        seed_dir = run_dir / f"seed-{seed}"
        metrics_path = verify_artifact(seed_record["metrics_artifact"])
        saved_seed_payload = json.loads(
            metrics_path.read_text(encoding="utf-8")
        )
        if saved_seed_payload["seed"] != seed:
            raise ValueError(f"Seed {seed} metrics.json identity changed")

        artifact_paths = {
            name: verify_artifact(record)
            for name, record in seed_record["artifacts"].items()
        }
        model_path = verify_artifact(seed_record["model"]["final_model"])
        ensure_gitignored(model_path)
        probabilities, predicted = load_predictions(
            artifact_paths["predictions"], dev_gold
        )
        metrics, confusion = compute_metrics(dev_gold, predicted)
        compare_metrics(
            tracker,
            metrics,
            seed_record["metrics"],
            f"seed-{seed}.run",
        )
        compare_metrics(
            tracker,
            metrics,
            saved_seed_payload["metrics"],
            f"seed-{seed}.metrics_file",
        )
        verify_per_label_csv(
            artifact_paths["per_label_metrics"], metrics, tracker, seed
        )
        verify_confusion_csv(
            artifact_paths["confusion_matrix"], confusion, seed
        )
        history_path = artifact_paths["history"]
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            history_rows = list(csv.DictReader(handle))
        if [int(row["epoch"]) for row in history_rows] != [1, 2, 3, 4]:
            raise ValueError(f"Seed {seed} history does not contain epochs 1-4")
        tracker.close(
            f"seed-{seed}.history.final_macro_f1",
            float(history_rows[-1]["macro_f1"]),
            metrics["macro"]["f1"],
        )
        if probabilities.shape != (EXPECTED_ROWS, len(EXPECTED_LABELS)):
            raise ValueError(f"Seed {seed} probability shape changed")
        recomputed[seed] = metrics
        verified_seed_artifacts[str(seed)] = {
            "model_sha256": sha256_file(model_path),
            "prediction_rows": probabilities.shape[0],
            "prediction_sha256": sha256_file(
                artifact_paths["predictions"]
            ),
        }

    if list(recomputed) != [42, 43, 44]:
        raise ValueError(f"Unexpected seeds: {list(recomputed)}")

    aggregate_path = resolve_project_path(
        run_record["artifacts"]["aggregate_metrics"]["path"]
    )
    saved_aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    expected_aggregate = recompute_aggregate(recomputed)
    compare_aggregate(tracker, saved_aggregate, expected_aggregate)
    compare_aggregate(
        tracker,
        {
            "comparison": run_record["comparison"],
            "external_reference": saved_aggregate["external_reference"],
            "per_label": saved_aggregate["per_label"],
            "sample_standard_deviation": saved_aggregate[
                "sample_standard_deviation"
            ],
            "seeds": saved_aggregate["seeds"],
            "validation": saved_aggregate["validation"],
        },
        expected_aggregate,
    )
    verify_seed_summary(
        resolve_project_path(run_record["artifacts"]["seed_summary"]["path"]),
        run_seed_records,
        recomputed,
        tracker,
    )

    verification = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "input_hashes_verified": EXPECTED_HASHES,
        "max_numeric_difference": tracker.maximum,
        "metrics_recomputed_from_probabilities": True,
        "privacy_checks": {
            "prediction_columns_exclude_comment_id": True,
            "prediction_columns_exclude_raw_text": True,
        },
        "seed_artifacts": verified_seed_artifacts,
        "seeds": list(recomputed),
        "status": "Verified",
        "test_split_accessed": False,
        "test_split_exists": False,
        "threshold": THRESHOLD,
        "verified_dev_rows_per_seed": EXPECTED_ROWS,
    }
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
