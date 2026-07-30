#!/usr/bin/env python3
"""Independently recompute and verify the completed EXP-016 test gate."""

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


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-016-frozen-test"
METRIC_ATOL = 1e-9
PROBABILITY_SUM_ATOL = 2e-6


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


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT != path and PROJECT_ROOT not in path.parents:
        raise AssertionError(f"Path escapes project root: {path}")
    return path


def assert_close(name: str, actual: float, expected: float) -> None:
    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=1e-9,
        abs_tol=METRIC_ATOL,
    ):
        raise AssertionError(f"{name}: {actual} != {expected}")


def verify_artifact(artifact: dict[str, Any]) -> Path:
    path = project_path(artifact["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if "bytes" in artifact and path.stat().st_size != artifact["bytes"]:
        raise AssertionError(f"Artifact byte size changed: {path}")
    actual_hash = sha256(path)
    if actual_hash != artifact["sha256"]:
        raise AssertionError(
            f"Artifact hash mismatch: {path}: "
            f"{actual_hash} != {artifact['sha256']}"
        )
    return path


def read_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_predictions(
    path: Path,
    mapping: dict[int, str],
    score_type: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    prefix = "prob" if score_type == "softmax probability" else "decision"
    fields = [
        f"{prefix}_{mapping[label_id]}" for label_id in sorted(mapping)
    ]
    labels = []
    predictions = []
    scores = []
    for expected_row_id, row in enumerate(rows):
        row_id = int(row["row_id"])
        if row_id != expected_row_id:
            raise AssertionError(
                f"Prediction row order changed: {row_id}"
            )
        gold_id = int(row["gold_id"])
        prediction_id = int(row["prediction_id"])
        if row["gold_label"] != mapping[gold_id]:
            raise AssertionError("Gold label name mismatch")
        if row["prediction_label"] != mapping[prediction_id]:
            raise AssertionError("Prediction label name mismatch")
        row_scores = [float(row[field]) for field in fields]
        if not np.isfinite(row_scores).all():
            raise AssertionError(f"Non-finite scores at row {row_id}")
        if int(np.argmax(row_scores)) != prediction_id:
            raise AssertionError(f"Score argmax mismatch at row {row_id}")
        if prefix == "prob" and not math.isclose(
            sum(row_scores),
            1.0,
            rel_tol=0.0,
            abs_tol=PROBABILITY_SUM_ATOL,
        ):
            raise AssertionError(
                f"Probabilities do not sum to one at row {row_id}"
            )
        labels.append(gold_id)
        predictions.append(prediction_id)
        scores.append(row_scores)
    return (
        np.asarray(labels),
        np.asarray(predictions),
        np.asarray(scores),
    )


def recompute_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    mapping: dict[int, str],
) -> tuple[dict[str, Any], np.ndarray]:
    label_ids = sorted(mapping)
    macro = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average="macro",
        zero_division=0,
    )
    weighted = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average="weighted",
        zero_division=0,
    )
    per_class = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average=None,
        zero_division=0,
    )
    matrix = confusion_matrix(labels, predictions, labels=label_ids)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro": {
            "f1": float(macro[2]),
            "precision": float(macro[0]),
            "recall": float(macro[1]),
        },
        "per_class": {
            mapping[label_id]: {
                "f1": float(per_class[2][index]),
                "label_id": label_id,
                "precision": float(per_class[0][index]),
                "recall": float(per_class[1][index]),
                "support": int(per_class[3][index]),
            }
            for index, label_id in enumerate(label_ids)
        },
        "weighted": {
            "f1": float(weighted[2]),
            "precision": float(weighted[0]),
            "recall": float(weighted[1]),
        },
    }, matrix


def compare_metrics(
    prefix: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    assert_close(f"{prefix}.accuracy", actual["accuracy"], expected["accuracy"])
    for average in ("macro", "weighted"):
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{average}.{metric}",
                actual[average][metric],
                expected[average][metric],
            )
    for label, values in actual["per_class"].items():
        expected_values = expected["per_class"][label]
        for metric in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{label}.{metric}",
                values[metric],
                expected_values[metric],
            )
        if values["support"] != expected_values["support"]:
            raise AssertionError(f"{prefix}.{label}.support changed")


def read_confusion(path: Path) -> np.ndarray:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return np.asarray(
        [[int(value) for value in row[1:]] for row in rows[1:]]
    )


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": (
            float(statistics.stdev(values)) if len(values) > 1 else 0.0
        ),
        "values": [float(value) for value in values],
    }


def aggregate(
    results: list[dict[str, Any]],
    mapping: dict[int, str],
) -> dict[str, Any]:
    return {
        "accuracy": summarize(
            [result["metrics"]["accuracy"] for result in results]
        ),
        "macro_f1": summarize(
            [result["metrics"]["macro"]["f1"] for result in results]
        ),
        "macro_precision": summarize(
            [result["metrics"]["macro"]["precision"] for result in results]
        ),
        "macro_recall": summarize(
            [result["metrics"]["macro"]["recall"] for result in results]
        ),
        "per_class": {
            label: {
                metric: summarize(
                    [
                        result["metrics"]["per_class"][label][metric]
                        for result in results
                    ]
                )
                for metric in ("precision", "recall", "f1")
            }
            for label in mapping.values()
        },
        "weighted_f1": summarize(
            [result["metrics"]["weighted"]["f1"] for result in results]
        ),
    }


def compare_summary(
    prefix: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    if actual["count"] != expected["count"]:
        raise AssertionError(f"{prefix}.count changed")
    assert_close(f"{prefix}.mean", actual["mean"], expected["mean"])
    assert_close(
        f"{prefix}.sample_std",
        actual["sample_std"],
        expected["sample_std"],
    )
    if len(actual["values"]) != len(expected["values"]):
        raise AssertionError(f"{prefix}.values length changed")
    for index, (value, expected_value) in enumerate(
        zip(actual["values"], expected["values"], strict=True)
    ):
        assert_close(f"{prefix}.values[{index}]", value, expected_value)


def compare_aggregate(
    prefix: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for metric in (
        "accuracy",
        "macro_f1",
        "macro_precision",
        "macro_recall",
        "weighted_f1",
    ):
        compare_summary(
            f"{prefix}.{metric}",
            actual[metric],
            expected[metric],
        )
    for label, metrics in actual["per_class"].items():
        for metric, summary in metrics.items():
            compare_summary(
                f"{prefix}.{label}.{metric}",
                summary,
                expected["per_class"][label][metric],
            )


def paired_comparison(
    newer: list[dict[str, Any]],
    older: list[dict[str, Any]],
) -> dict[str, Any]:
    newer_by_seed = {int(item["seed"]): item for item in newer}
    older_by_seed = {int(item["seed"]): item for item in older}
    differences = [
        newer_by_seed[seed]["metrics"]["macro"]["f1"]
        - older_by_seed[seed]["metrics"]["macro"]["f1"]
        for seed in (42, 43, 44)
    ]
    return {
        "macro_f1_difference": summarize(differences),
        "positive_seed_count": sum(value > 0 for value in differences),
        "seed_differences": {
            str(seed): float(value)
            for seed, value in zip((42, 43, 44), differences, strict=True)
        },
    }


def compare_paired(
    name: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    compare_summary(
        f"{name}.macro_f1_difference",
        actual["macro_f1_difference"],
        expected["macro_f1_difference"],
    )
    if actual["positive_seed_count"] != expected["positive_seed_count"]:
        raise AssertionError(f"{name}.positive_seed_count changed")
    for seed, value in actual["seed_differences"].items():
        assert_close(
            f"{name}.seed-{seed}",
            value,
            expected["seed_differences"][seed],
        )


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    run_path = run_dir / "run.json"
    run = read_json(run_path)
    if run.get("experiment_id") != "EXP-016":
        raise AssertionError("Unexpected experiment ID")
    if run.get("status") != "Completed":
        raise AssertionError(f"Run is not completed: {run.get('status')}")
    if run.get("accessed_splits") != ["test"]:
        raise AssertionError("EXP-016 accessed an unexpected split")
    if run.get("test_split_accessed") is not True:
        raise AssertionError("Test access is not recorded")
    if run.get("validation_split_accessed") is not False:
        raise AssertionError("Validation was accessed during test inference")

    config_path = verify_artifact(run["config"])
    config = read_json(config_path)
    protocol_path = project_path(run["protocol"]["path"])
    if sha256(protocol_path) != run["protocol"]["sha256"]:
        raise AssertionError("Protocol hash changed")

    mapping = {
        int(label_id): label
        for label_id, label in config["data"]["label_mapping"].items()
    }
    test_labels_path = verify_artifact(
        config["data"]["files"]["test_labels"]
    )
    test_labels = np.asarray(
        [int(value) for value in read_lines(test_labels_path)]
    )
    verify_artifact(config["data"]["files"]["test_text"])
    verify_artifact(config["data"]["files"]["mapping"])

    recomputed_results: dict[str, list[dict[str, Any]]] = {}
    prediction_count = 0
    for condition in config["conditions"]:
        condition_id = condition["id"]
        recorded_results = run["condition_results"][condition_id]
        condition_results = []
        for recorded in recorded_results:
            predictions_path = verify_artifact(
                recorded["artifacts"]["predictions"]
            )
            metrics_path = verify_artifact(
                recorded["artifacts"]["metrics"]
            )
            confusion_path = verify_artifact(
                recorded["artifacts"]["confusion_matrix"]
            )
            stored_metrics = read_json(metrics_path)
            labels, predictions, _ = read_predictions(
                predictions_path,
                mapping,
                recorded["score_type"],
            )
            if len(labels) != int(config["data"]["test_sample_count"]):
                raise AssertionError("Prediction row count changed")
            if not np.array_equal(labels, test_labels):
                raise AssertionError("Prediction gold labels changed")
            metrics, matrix = recompute_metrics(
                labels,
                predictions,
                mapping,
            )
            compare_metrics(
                f"{condition_id}.seed-{recorded['seed']}",
                metrics,
                recorded["metrics"],
            )
            compare_metrics(
                f"{condition_id}.metrics-file",
                metrics,
                stored_metrics["metrics"],
            )
            if not np.array_equal(matrix, read_confusion(confusion_path)):
                raise AssertionError(
                    f"Confusion matrix changed: {condition_id}"
                )
            condition_results.append(
                {
                    **recorded,
                    "metrics": metrics,
                }
            )
            prediction_count += len(labels)
        recomputed_results[condition_id] = condition_results
        recomputed_aggregate = aggregate(condition_results, mapping)
        compare_aggregate(
            condition_id,
            recomputed_aggregate,
            run["condition_aggregates"][condition_id],
        )

    expected_comparisons = {
        "exp-014-minus-exp-011": paired_comparison(
            recomputed_results[
                "exp-014-generic-roberta-label-smoothing"
            ],
            recomputed_results["exp-011-generic-roberta"],
        ),
        "exp-015-minus-exp-014": paired_comparison(
            recomputed_results[
                "exp-015-twitter-roberta-label-smoothing"
            ],
            recomputed_results[
                "exp-014-generic-roberta-label-smoothing"
            ],
        ),
    }
    for name, comparison in expected_comparisons.items():
        compare_paired(name, comparison, run["paired_comparisons"][name])

    verify_artifact(run["artifacts"]["condition_summary"])
    verify_artifact(run["artifacts"]["seed_results"])
    ranking = sorted(
        [
            {
                "condition_id": condition["id"],
                "source_experiment_id": condition[
                    "source_experiment_id"
                ],
                "test_macro_f1_mean": run["condition_aggregates"][
                    condition["id"]
                ]["macro_f1"]["mean"],
            }
            for condition in config["conditions"]
        ],
        key=lambda item: item["test_macro_f1_mean"],
        reverse=True,
    )
    if ranking != run["ranking"]:
        raise AssertionError("Recorded ranking changed")

    verification = {
        "checks": {
            "aggregate_metrics_recomputed": True,
            "artifact_hashes_match": True,
            "confusion_matrices_recomputed": True,
            "gold_labels_match_official_test": True,
            "paired_comparisons_recomputed": True,
            "per_class_metrics_recomputed": True,
            "prediction_rows_verified": prediction_count,
            "score_argmax_verified": True,
            "test_input_hashes_match": True,
        },
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-016",
        "run": {
            "path": str(run_path.relative_to(PROJECT_ROOT)),
            "sha256": sha256(run_path),
        },
        "status": "Verified",
        "test_split_accessed": True,
    }
    output_path = run_dir / "verification.json"
    if output_path.exists():
        raise FileExistsError(f"Verification already exists: {output_path}")
    write_json(output_path, verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
