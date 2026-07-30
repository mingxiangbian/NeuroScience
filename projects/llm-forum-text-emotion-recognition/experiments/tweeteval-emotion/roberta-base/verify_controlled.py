#!/usr/bin/env python3
"""Independently verify a completed controlled Major run."""

from __future__ import annotations

import argparse
import copy
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


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
PROBABILITY_SUM_ATOL = 2e-6
METRIC_ATOL = 1e-9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_close(name: str, actual: float, expected: float) -> None:
    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=1e-9,
        abs_tol=METRIC_ATOL,
    ):
        raise AssertionError(f"{name}: {actual} != {expected}")


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT not in path.parents:
        raise AssertionError(f"Artifact escapes project root: {path}")
    return path


def verify_artifact(artifact: dict[str, str]) -> Path:
    path = project_path(artifact["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = sha256(path)
    if actual_hash != artifact["sha256"]:
        raise AssertionError(
            f"Artifact hash mismatch: {path}: "
            f"{actual_hash} != {artifact['sha256']}"
        )
    return path


def verify_data_files(run: dict[str, Any]) -> list[dict[str, str]]:
    checks = []
    for name, artifact in sorted(run["data"]["files_read"].items()):
        if "test" in artifact["path"].lower():
            raise AssertionError(f"Prohibited test path in files_read: {name}")
        path = verify_artifact(artifact)
        checks.append(
            {
                "name": name,
                "path": artifact["path"],
                "sha256": sha256(path),
            }
        )
    return checks


def read_predictions(
    path: Path,
    mapping: dict[int, str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    probability_fields = [
        f"prob_{mapping[label_id]}" for label_id in sorted(mapping)
    ]
    labels: list[int] = []
    predictions: list[int] = []
    probabilities: list[list[float]] = []
    row_ids: list[int] = []
    for expected_row_id, row in enumerate(rows):
        row_id = int(row["row_id"])
        if row_id != expected_row_id:
            raise AssertionError(
                f"Prediction row ID changed: {row_id} != {expected_row_id}"
            )
        gold = int(row["gold_id"])
        prediction = int(row["prediction_id"])
        if row["gold_label"] != mapping[gold]:
            raise AssertionError("Gold label name mismatch")
        if row["prediction_label"] != mapping[prediction]:
            raise AssertionError("Prediction label name mismatch")
        row_probabilities = [
            float(row[field]) for field in probability_fields
        ]
        if not np.isfinite(row_probabilities).all():
            raise AssertionError(f"Non-finite probabilities at row {row_id}")
        if not math.isclose(
            sum(row_probabilities),
            1.0,
            rel_tol=0.0,
            abs_tol=PROBABILITY_SUM_ATOL,
        ):
            raise AssertionError(
                f"Probabilities do not sum to one at row {row_id}"
            )
        if int(np.argmax(row_probabilities)) != prediction:
            raise AssertionError(
                f"Prediction is not probability argmax at row {row_id}"
            )
        row_ids.append(row_id)
        labels.append(gold)
        predictions.append(prediction)
        probabilities.append(row_probabilities)
    return (
        np.asarray(labels),
        np.asarray(predictions),
        np.asarray(probabilities),
        row_ids,
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
        "confusion_matrix": matrix.tolist(),
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
        f"{prefix}.accuracy",
        actual["accuracy"],
        expected["accuracy"],
    )
    for average in ("macro", "weighted"):
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{average}.{metric}",
                actual[average][metric],
                expected[average][metric],
            )
    for label, actual_values in actual["per_class"].items():
        expected_values = expected["per_class"][label]
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{label}.{metric}",
                actual_values[metric],
                expected_values[metric],
            )
        if actual_values["support"] != expected_values["support"]:
            raise AssertionError(f"{prefix}.{label}.support mismatch")


def read_confusion_csv(path: Path) -> list[list[int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return [[int(value) for value in row[1:]] for row in rows[1:]]


def verify_history(
    path: Path,
    seed_result: dict[str, Any],
) -> dict[str, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    evaluation_rows = [row for row in rows if row["eval_macro_f1"]]
    training_rows = [row for row in rows if row["loss"]]
    expected_epochs = int(seed_result["training"]["num_train_epochs"])
    if len(evaluation_rows) != expected_epochs:
        raise AssertionError(
            f"Expected {expected_epochs} evaluations, "
            f"got {len(evaluation_rows)}"
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
    selected_rows = [
        row
        for row in evaluation_rows
        if int(float(row["step"])) == best_step
    ]
    if len(selected_rows) != 1:
        raise AssertionError("Selected checkpoint is absent from history")
    assert_close(
        "history.best_epoch",
        float(selected_rows[0]["epoch"]),
        seed_result["best_checkpoint"]["epoch"],
    )
    return {
        "evaluation_record_count": len(evaluation_rows),
        "training_loss_record_count": len(training_rows),
    }


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": (
            float(statistics.stdev(values)) if len(values) > 1 else 0.0
        ),
    }


def compare_summary(
    name: str,
    actual: dict[str, float | int],
    expected: dict[str, float | int],
) -> None:
    if actual["count"] != expected["count"]:
        raise AssertionError(f"{name}.count mismatch")
    assert_close(f"{name}.mean", actual["mean"], expected["mean"])
    assert_close(
        f"{name}.sample_std",
        actual["sample_std"],
        expected["sample_std"],
    )


def recompute_aggregate(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accuracy": summarize(
            [item["validation"]["accuracy"] for item in seed_results]
        ),
        "macro_f1": summarize(
            [item["validation"]["macro"]["f1"] for item in seed_results]
        ),
        "macro_precision": summarize(
            [
                item["validation"]["macro"]["precision"]
                for item in seed_results
            ]
        ),
        "macro_recall": summarize(
            [item["validation"]["macro"]["recall"] for item in seed_results]
        ),
        "per_class_f1": {
            label: summarize(
                [
                    item["validation"]["per_class"][label]["f1"]
                    for item in seed_results
                ]
            )
            for label in seed_results[0]["validation"]["per_class"]
        },
        "weighted_f1": summarize(
            [item["validation"]["weighted"]["f1"] for item in seed_results]
        ),
    }


def compare_aggregate(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for name in (
        "accuracy",
        "macro_f1",
        "macro_precision",
        "macro_recall",
        "weighted_f1",
    ):
        compare_summary(name, actual[name], expected[name])
    if set(actual["per_class_f1"]) != set(expected["per_class_f1"]):
        raise AssertionError("Aggregate per-class labels changed")
    for label in actual["per_class_f1"]:
        compare_summary(
            f"per_class_f1.{label}",
            actual["per_class_f1"][label],
            expected["per_class_f1"][label],
        )


def verify_comparison(
    run: dict[str, Any],
    seed_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparison = run["comparison"]
    parent_path = project_path(comparison["run_metadata"])
    if sha256(parent_path) != comparison["run_metadata_sha256"]:
        raise AssertionError("Parent run hash mismatch")
    parent = read_json(parent_path)
    parent_by_seed = {
        item["seed"]: item["validation"]["macro"]["f1"]
        for item in parent["seed_results"]
    }
    deltas = {
        str(item["seed"]): (
            item["validation"]["macro"]["f1"]
            - parent_by_seed[item["seed"]]
        )
        for item in seed_results
    }
    if set(deltas) != set(comparison["matched_seed_macro_f1_deltas"]):
        raise AssertionError("Comparison seed set changed")
    for seed, delta in deltas.items():
        assert_close(
            f"comparison.seed-{seed}",
            delta,
            comparison["matched_seed_macro_f1_deltas"][seed],
        )
    expected_count = sum(value > 0 for value in deltas.values())
    if expected_count != comparison["matched_seed_improvement_count"]:
        raise AssertionError("Matched-seed improvement count mismatch")
    expected_mean = float(statistics.fmean(deltas.values()))
    assert_close(
        "comparison.mean_macro_f1_delta",
        expected_mean,
        comparison["mean_macro_f1_delta"],
    )
    return {
        "matched_seed_improvement_count": expected_count,
        "matched_seed_macro_f1_deltas": deltas,
        "mean_macro_f1_delta": expected_mean,
        "parent_experiment_id": comparison["experiment_id"],
        "parent_run_sha256": sha256(parent_path),
        "practical_improvement_passed": (
            expected_mean
            >= comparison["practical_improvement_threshold"]
        ),
    }


def verify_model(run: dict[str, Any]) -> dict[str, Any]:
    manifest_path = project_path(run["model"]["manifest"])
    if sha256(manifest_path) != run["model"]["manifest_sha256"]:
        raise AssertionError("Model manifest hash mismatch")
    snapshot = project_path(run["model"]["local_snapshot"])
    checks = []
    for expected in run["model"]["verified_snapshot_files"]:
        path = snapshot / expected["path"]
        actual = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256(path),
        }
        if actual != expected:
            raise AssertionError(f"Model snapshot mismatch: {path}")
        checks.append(actual)
    return {
        "manifest_sha256": sha256(manifest_path),
        "snapshot_file_count": len(checks),
    }


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    run_path = run_dir / "run.json"
    run = read_json(run_path)
    if run["status"] != "Completed" or run["tier"] != "Major":
        raise AssertionError("Run is not a completed Major experiment")
    if run["accessed_splits"] != ["train", "validation"]:
        raise AssertionError("Unexpected accessed split list")
    if run["test_split_accessed"] is not False:
        raise AssertionError("run.json does not explicitly exclude test")
    if run["validation_split_accessed"] is not True:
        raise AssertionError("Validation access was not recorded")
    if len(run["seed_results"]) != 3:
        raise AssertionError("Expected exactly three Major-run seeds")

    config_path = verify_artifact(run["artifacts"]["config"])
    verify_artifact(run["artifacts"]["protocol"])
    verify_artifact(run["artifacts"]["runner"])
    config = read_json(config_path)
    expected_seeds = [int(seed) for seed in config["seeds"]]
    actual_seeds = [item["seed"] for item in run["seed_results"]]
    if actual_seeds != expected_seeds:
        raise AssertionError("Seed order or set changed")
    mapping = {
        int(label_id): label
        for label_id, label in run["data"]["label_mapping"].items()
    }
    expected_count = int(run["data"]["validation_sample_count"])

    seed_checks = []
    reference_gold: np.ndarray | None = None
    for seed_result in run["seed_results"]:
        seed = int(seed_result["seed"])
        artifacts = seed_result["artifacts"]
        predictions_path = verify_artifact(artifacts["predictions"])
        confusion_path = verify_artifact(artifacts["confusion_matrix"])
        history_path = verify_artifact(artifacts["history"])
        metrics_path = verify_artifact(artifacts["metrics"])
        checkpoint_path = verify_artifact(
            seed_result["best_checkpoint"]["model_file"]
        )

        labels, predictions, probabilities, row_ids = read_predictions(
            predictions_path,
            mapping,
        )
        if len(labels) != expected_count:
            raise AssertionError(
                f"Seed {seed} prediction count: "
                f"{len(labels)} != {expected_count}"
            )
        if reference_gold is None:
            reference_gold = labels
        elif not np.array_equal(reference_gold, labels):
            raise AssertionError("Gold labels differ between seeds")

        recomputed = recompute_metrics(labels, predictions, mapping)
        compare_metrics(
            f"seed-{seed}",
            recomputed,
            seed_result["validation"],
        )
        if (
            read_confusion_csv(confusion_path)
            != recomputed["confusion_matrix"]
        ):
            raise AssertionError(f"Seed {seed} confusion CSV mismatch")

        stored_metrics = read_json(metrics_path)
        expected_metrics = copy.deepcopy(seed_result)
        del expected_metrics["artifacts"]["metrics"]
        if stored_metrics != expected_metrics:
            raise AssertionError(f"Seed {seed} metrics.json mismatch")

        history_check = verify_history(history_path, seed_result)
        seed_checks.append(
            {
                "best_epoch": seed_result["best_checkpoint"]["epoch"],
                "checkpoint_sha256": sha256(checkpoint_path),
                "history": history_check,
                "prediction_count": len(row_ids),
                "prediction_sha256": sha256(predictions_path),
                "probabilities_finite": bool(
                    np.isfinite(probabilities).all()
                ),
                "seed": seed,
                "validation_accuracy": recomputed["accuracy"],
                "validation_macro_f1": recomputed["macro"]["f1"],
            }
        )

    recomputed_aggregate = recompute_aggregate(run["seed_results"])
    compare_aggregate(recomputed_aggregate, run["aggregate"])
    comparison = verify_comparison(run, run["seed_results"])
    data_checks = verify_data_files(run)
    model_check = verify_model(run)
    verification = {
        "accessed_splits_verified": ["train", "validation"],
        "aggregate": recomputed_aggregate,
        "artifact_hashes_verified": True,
        "comparison": comparison,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_file_checks": data_checks,
        "experiment_id": run["experiment_id"],
        "model_check": model_check,
        "run_json_sha256": sha256(run_path),
        "seed_checks": seed_checks,
        "status": "Verified",
        "test_split_accessed": False,
    }
    write_json(run_dir / "verification.json", verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
