#!/usr/bin/env python3
"""Independently recompute and verify the completed EXP-038 test gate."""

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


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-038-frozen-test.json"
ATOL = 1e-9


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if path != PROJECT_ROOT and PROJECT_ROOT not in path.parents:
        raise AssertionError(f"Path escapes project root: {value}")
    return path


def assert_close(name: str, actual: float, expected: float) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=ATOL):
        raise AssertionError(f"{name}: {actual} != {expected}")


def verify_artifact(spec: dict[str, Any]) -> Path:
    path = project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        raise AssertionError(f"Artifact byte count changed: {path}")
    actual = sha256_file(path)
    if actual != spec["sha256"]:
        raise AssertionError(f"Artifact hash changed: {path}")
    return path


def load_gold(path: Path, rows: int, labels: tuple[str, ...]) -> np.ndarray:
    gold = np.zeros((rows, len(labels)), dtype=np.uint8)
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        records = list(csv.reader(handle, delimiter="\t"))
    if len(records) != rows:
        raise AssertionError(f"Test row count changed: {len(records)}")
    for index, row in enumerate(records):
        if len(row) != 3 or not all(row):
            raise AssertionError(f"Malformed test row: {index + 1}")
        if row[2] in seen_ids:
            raise AssertionError("Test comment IDs are not unique")
        seen_ids.add(row[2])
        values = [int(value) for value in row[1].split(",")]
        if not values or len(values) != len(set(values)):
            raise AssertionError(f"Malformed test labels: {index + 1}")
        gold[index, values] = 1
    return gold


def parse_ids(value: str, label_count: int) -> list[int]:
    values = [] if not value else [int(item) for item in value.split("|")]
    if len(values) != len(set(values)) or any(
        item < 0 or item >= label_count for item in values
    ):
        raise AssertionError("Prediction label IDs are invalid")
    return values


def read_predictions(
    path: Path,
    unit: dict[str, Any],
    labels: tuple[str, ...],
    gold: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        forbidden = {"text", "comment_id", "raw_text", "upstream_comment_id"}
        if forbidden.intersection(fieldnames):
            raise AssertionError(f"Private data leaked into {path}")
        rows = list(reader)
    if len(rows) != gold.shape[0]:
        raise AssertionError(f"Prediction row count changed: {path}")
    predicted = np.zeros_like(gold)
    scores = (
        np.zeros(gold.shape, dtype=np.float64)
        if unit["type"] in {"sklearn_joblib", "bert_checkpoint"}
        else None
    )
    for index, row in enumerate(rows):
        if int(row["row_number"]) != index + 1:
            raise AssertionError(f"Prediction order changed: {path}")
        gold_ids = parse_ids(row["gold_label_ids"], len(labels))
        if gold_ids != np.flatnonzero(gold[index]).tolist():
            raise AssertionError(f"Prediction gold differs from test at row {index + 1}")
        prediction_ids = parse_ids(row["predicted_label_ids"], len(labels))
        predicted[index, prediction_ids] = 1
        if row["gold_labels"].split("|") != [labels[value] for value in gold_ids]:
            raise AssertionError("Gold label names changed")
        expected_names = [labels[value] for value in prediction_ids]
        observed_names = [] if not row["predicted_labels"] else row["predicted_labels"].split("|")
        if observed_names != expected_names:
            raise AssertionError("Predicted label names changed")
        if scores is not None:
            row_scores = np.asarray(
                [float(row[f"prob_{label}"]) for label in labels], dtype=np.float64
            )
            if not np.isfinite(row_scores).all() or np.any(
                (row_scores < 0.0) | (row_scores > 1.0)
            ):
                raise AssertionError("Probability scores are invalid")
            scores[index] = row_scores
        else:
            canonical = row["canonical_output"]
            if row["parser_valid"] == "true":
                decoded = json.loads(canonical)
                if decoded != {"labels": expected_names}:
                    raise AssertionError("Canonical generation differs from prediction")
            elif prediction_ids:
                raise AssertionError("Invalid generation produced non-empty prediction")
    if scores is not None:
        expected = (scores >= float(unit["threshold"])).astype(np.uint8)
        if not np.array_equal(expected, predicted):
            raise AssertionError(f"Frozen threshold mismatch: {unit['id']}")
    return predicted, scores


def verify_generation_records(
    path: Path,
    predicted: np.ndarray,
    gold: np.ndarray,
    unit: dict[str, Any],
) -> None:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(records) != gold.shape[0]:
        raise AssertionError(f"Generation row count changed: {unit['id']}")
    forbidden = {"text", "input_text", "comment_id", "upstream_comment_id"}
    for index, record in enumerate(records):
        if forbidden.intersection(record):
            raise AssertionError(f"Private data leaked into generation records: {unit['id']}")
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raise AssertionError(f"Raw generation missing: {unit['id']} row {index + 1}")
        predicted_ids = record.get("predicted_label_ids")
        if (
            not isinstance(predicted_ids, list)
            or any(not isinstance(value, int) for value in predicted_ids)
            or len(predicted_ids) != len(set(predicted_ids))
            or any(value < 0 or value >= predicted.shape[1] for value in predicted_ids)
        ):
            raise AssertionError(
                f"Generation prediction IDs are invalid: {unit['id']} row {index + 1}"
            )
        if (
            record.get("row_number") != index + 1
            or record.get("gold_label_ids") != np.flatnonzero(gold[index]).tolist()
            or record.get("condition") != unit["scientific_condition"]
            or record.get("output_sha256")
            != hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
            # Multi-label predictions are sets. The generation record preserves JSON
            # order, while the reconstructed multi-hot vector is label-ID ordered.
            or sorted(predicted_ids) != np.flatnonzero(predicted[index]).tolist()
        ):
            raise AssertionError(
                f"Generation record diverges from predictions: {unit['id']} row {index + 1}"
            )


def divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )


def recompute(
    gold: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]
) -> tuple[dict[str, Any], np.ndarray]:
    g, p = gold.astype(bool), predicted.astype(bool)
    tp = np.sum(g & p, axis=0, dtype=np.int64)
    fp = np.sum(~g & p, axis=0, dtype=np.int64)
    fn = np.sum(g & ~p, axis=0, dtype=np.int64)
    tn = np.sum(~g & ~p, axis=0, dtype=np.int64)
    support = tp + fn
    predicted_support = tp + fp
    precision = divide(tp, tp + fp)
    recall = divide(tp, tp + fn)
    f1 = divide(2 * tp, 2 * tp + fp + fn)
    sample_tp = np.sum(g & p, axis=1, dtype=np.int64)
    sample_gold = np.sum(g, axis=1, dtype=np.int64)
    sample_predicted = np.sum(p, axis=1, dtype=np.int64)
    micro_tp, micro_fp, micro_fn = int(tp.sum()), int(fp.sum()), int(fn.sum())
    total_support = int(support.sum())
    subset_accuracy = float(np.mean(np.all(g == p, axis=1)))
    hamming = float(np.mean(g != p))
    return {
        "accuracy": subset_accuracy,
        "hamming_loss": hamming,
        "label_accuracy": 1.0 - hamming,
        "label_cardinality": {
            "gold_mean": float(np.mean(sample_gold)),
            "predicted_mean": float(np.mean(sample_predicted)),
        },
        "macro": {
            "precision": float(np.mean(precision)),
            "recall": float(np.mean(recall)),
            "f1": float(np.mean(f1)),
        },
        "micro": {
            "precision": float(micro_tp / (micro_tp + micro_fp))
            if micro_tp + micro_fp
            else 0.0,
            "recall": float(micro_tp / (micro_tp + micro_fn))
            if micro_tp + micro_fn
            else 0.0,
            "f1": float(2 * micro_tp / (2 * micro_tp + micro_fp + micro_fn))
            if 2 * micro_tp + micro_fp + micro_fn
            else 0.0,
        },
        "per_label": {
            label: {
                "f1": float(f1[index]),
                "label_id": index,
                "precision": float(precision[index]),
                "predicted_support": int(predicted_support[index]),
                "recall": float(recall[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(labels)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(sample_predicted == 0)),
            "neutral_coprediction_rows": int(
                np.sum(p[:, labels.index("neutral")] & (sample_predicted > 1))
            ),
        },
        "samples": {
            "precision": float(np.mean(divide(sample_tp, sample_predicted))),
            "recall": float(np.mean(divide(sample_tp, sample_gold))),
            "f1": float(np.mean(divide(2 * sample_tp, sample_gold + sample_predicted))),
        },
        "subset_accuracy": subset_accuracy,
        "weighted": {
            "precision": float(np.sum(precision * support) / total_support),
            "recall": float(np.sum(recall * support) / total_support),
            "f1": float(np.sum(f1 * support) / total_support),
        },
    }, np.stack([np.stack([tn, fp], axis=1), np.stack([fn, tp], axis=1)], axis=1)


def compare_metrics(prefix: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in ("accuracy", "hamming_loss", "label_accuracy", "subset_accuracy"):
        assert_close(f"{prefix}.{key}", actual[key], expected[key])
    for group in ("label_cardinality", "macro", "micro", "samples", "weighted"):
        for key, value in actual[group].items():
            assert_close(f"{prefix}.{group}.{key}", value, expected[group][key])
    for label, values in actual["per_label"].items():
        for key in ("precision", "recall", "f1"):
            assert_close(
                f"{prefix}.{label}.{key}", values[key], expected["per_label"][label][key]
            )
        for key in ("support", "predicted_support", "label_id"):
            if values[key] != expected["per_label"][label][key]:
                raise AssertionError(f"{prefix}.{label}.{key} changed")
    if actual["prediction_diagnostics"] != expected["prediction_diagnostics"]:
        raise AssertionError(f"{prefix}.prediction_diagnostics changed")


def read_confusion(path: Path) -> np.ndarray:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return np.asarray([[int(value) for value in row[2:]] for row in rows[1:]]).reshape(28, 2, 2)


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)) if len(values) > 1 else 0.0,
        "values": values,
    }


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    if sha256_file(config_path) != args.config_sha256:
        raise AssertionError("Frozen config hash changed")
    config = read_json(config_path)
    output_root = project_path(config["output_dir"])
    verification_path = output_root / "verification.json"
    if verification_path.exists():
        raise FileExistsError("EXP-038 verification already exists")
    test_path = verify_artifact(config["data"]["test"])
    labels = tuple(verify_artifact(config["data"]["labels"]).read_text(encoding="utf-8").splitlines())
    if len(labels) != 28 or len(set(labels)) != 28:
        raise AssertionError("GoEmotions label ontology changed")
    gold = load_gold(test_path, 5427, labels)
    run = read_json(output_root / "run.json")
    if run.get("status") != "Completed; pending independent verification":
        raise AssertionError("EXP-038 run is incomplete")
    if run.get("post_test_tuning") is not False or run.get("model_selection_after_test") is not False:
        raise AssertionError("Frozen post-test policy changed")
    for spec in run["artifacts"].values():
        verify_artifact(spec)

    recomputed: dict[str, dict[str, Any]] = {}
    for unit in config["units"]:
        unit_dir = output_root / unit["id"]
        predicted, _ = read_predictions(unit_dir / "predictions.csv", unit, labels, gold)
        if unit["type"] == "qwen_generation":
            verify_generation_records(
                unit_dir / "generation-records.jsonl", predicted, gold, unit
            )
        metrics, confusion = recompute(gold, predicted, labels)
        stored = read_json(unit_dir / "metrics.json")
        compare_metrics(unit["id"], metrics, stored)
        observed_confusion = read_confusion(unit_dir / "multilabel-confusion-matrix.csv")
        if not np.array_equal(confusion, observed_confusion):
            raise AssertionError(f"Confusion matrix changed: {unit['id']}")
        recomputed[unit["id"]] = metrics

    aggregate = read_json(output_root / "aggregate-metrics.json")
    recomputed_groups: dict[str, Any] = {}
    for group in config["report_groups"]:
        rows = [recomputed[unit_id] for unit_id in group["unit_ids"]]
        values = {
            "macro_f1": summarize([row["macro"]["f1"] for row in rows]),
            "macro_precision": summarize([row["macro"]["precision"] for row in rows]),
            "macro_recall": summarize([row["macro"]["recall"] for row in rows]),
            "micro_f1": summarize([row["micro"]["f1"] for row in rows]),
            "samples_f1": summarize([row["samples"]["f1"] for row in rows]),
            "subset_accuracy": summarize([row["subset_accuracy"] for row in rows]),
            "weighted_f1": summarize([row["weighted"]["f1"] for row in rows]),
        }
        recomputed_groups[group["id"]] = values
        stored = aggregate["conditions"][group["id"]]
        for metric, summary in values.items():
            for key in ("mean", "sample_std"):
                assert_close(
                    f"aggregate.{group['id']}.{metric}.{key}",
                    summary[key],
                    stored[metric][key],
                )
            if summary["count"] != stored[metric]["count"]:
                raise AssertionError("Aggregate seed count changed")
    ranking = sorted(
        (
            (group_id, values["macro_f1"]["mean"])
            for group_id, values in recomputed_groups.items()
        ),
        key=lambda row: row[1],
        reverse=True,
    )
    if [row["group_id"] for row in aggregate["ranking"]] != [row[0] for row in ranking]:
        raise AssertionError("Aggregate ranking changed")

    verification = {
        "accessed_splits": ["test"],
        "checks": {
            "all_nine_units_recomputed": True,
            "artifact_hashes_match": True,
            "config_sha256_match": True,
            "confusion_matrices_match": True,
            "model_selection_after_test": False,
            "post_test_tuning": False,
            "private_text_or_comment_ids_in_predictions": False,
            "test_rows": 5427,
        },
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-038",
        "recomputed_groups": recomputed_groups,
        "status": "Verified",
        "test_split_accessed": True,
        "verifier_amendment": {
            "id": "EXP-038-VERIFY-V2",
            "reason": "The registered verifier compared ordered generated label IDs with a label-ID-sorted multi-hot reconstruction. V2 compares validated unique ID sets.",
            "registered_verifier_sha256": config["registered_artifacts"]["verifier"]["sha256"],
            "scientific_outputs_changed": False,
        },
        "verifier": {
            "path": str(Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    write_json(verification_path, verification)
    print("EXP-038 independently verified")


if __name__ == "__main__":
    main()
