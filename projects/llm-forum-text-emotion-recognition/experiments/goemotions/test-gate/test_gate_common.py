#!/usr/bin/env python3
"""Shared frozen-data and metric helpers for the EXP-038 runners."""

from __future__ import annotations

from collections import Counter
import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if path != PROJECT_ROOT and PROJECT_ROOT not in path.parents:
        raise ValueError(f"Path escapes project root: {value}")
    return path


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def verify_artifact(spec: dict[str, Any]) -> Path:
    path = resolve_project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"Artifact byte count changed: {path}")
    actual = sha256_file(path)
    if actual != spec["sha256"]:
        raise ValueError(
            f"Artifact SHA-256 changed: {path}: {actual} != {spec['sha256']}"
        )
    return path


def load_config(
    path: Path,
    expected_sha256: str | None = None,
    allow_unbound_test: bool = False,
) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_sha256 = sha256_file(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError("Frozen EXP-038 config SHA-256 mismatch")
    config = read_json(path)
    if config.get("experiment_id") != "EXP-038" or config.get("tier") != "Major":
        raise ValueError("Only the registered EXP-038 Major config is accepted")
    if config.get("authorization", {}).get("approved") is not True:
        raise ValueError("The one-time test gate is not authorized")
    if config.get("test_policy") != {
        "allow_checkpoint_selection": False,
        "allow_ensemble": False,
        "allow_post_result_tuning": False,
        "evaluate_every_listed_unit_once": True,
        "technical_resume_only": True,
    }:
        raise ValueError("Frozen test policy changed")
    units = config.get("units", [])
    expected_ids = [
        "exp018-tfidf",
        "exp020-bert-seed42",
        "exp020-bert-seed43",
        "exp020-bert-seed44",
        "exp025-qwen-few-shot",
        "exp029-qwen-seed42",
        "exp029-qwen-seed43",
        "exp029-qwen-seed44",
        "exp033-qwen-seed42-target-aligned",
    ]
    if [unit.get("id") for unit in units] != expected_ids:
        raise ValueError("Frozen EXP-038 evaluation-unit order changed")
    test = config.get("data", {}).get("test", {})
    if not allow_unbound_test:
        if test.get("sha256") in {None, "TO_BE_BOUND_AFTER_ACQUISITION"}:
            raise ValueError("Official test hash has not been bound")
        verify_artifact(test)
        verify_final_binding(config)
    for spec in config.get("registered_artifacts", {}).values():
        verify_artifact(spec)
    return config, actual_sha256


def verify_final_binding(config: dict[str, Any]) -> None:
    preregistration_spec = config.get("preregistered_config")
    if not preregistration_spec:
        raise ValueError("Final config does not bind the preregistered config")
    preregistration_path = verify_artifact(preregistration_spec)
    preregistration = read_json(preregistration_path)
    final_comparable = copy.deepcopy(config)
    preregistration_comparable = copy.deepcopy(preregistration)
    for key in ("preflight_gate", "preregistered_config", "test_binding"):
        final_comparable.pop(key, None)
    for value in (final_comparable, preregistration_comparable):
        test = value["data"]["test"]
        test.pop("bytes", None)
        test["sha256"] = "TO_BE_BOUND_AFTER_ACQUISITION"
    if final_comparable != preregistration_comparable:
        raise ValueError(
            "Final config changed scientific choices after test acquisition"
        )


def verify_formal_preflight(config: dict[str, Any]) -> None:
    preregistration_sha256 = config["preregistered_config"]["sha256"]
    for name in ("classical_bert", "qwen"):
        report_path = verify_artifact(config["preflight_gate"][name])
        report = read_json(report_path)
        if (
            report.get("status") != "Passed"
            or report.get("test_split_accessed") is not False
            or report.get("config_sha256") != preregistration_sha256
        ):
            raise ValueError(f"Invalid formal preflight report: {name}")
    binding_path = verify_artifact(config["test_binding"])
    binding = read_json(binding_path)
    if (
        binding.get("preregistered_config_sha256") != preregistration_sha256
        or binding.get("artifact", {}).get("sha256")
        != config["data"]["test"]["sha256"]
    ):
        raise ValueError("Official test binding does not match the frozen config")


def load_labels(spec: dict[str, Any]) -> tuple[str, ...]:
    path = verify_artifact(spec)
    labels = tuple(path.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order changed")
    return labels


def load_split(
    path: Path,
    expected_rows: int,
    labels: tuple[str, ...],
) -> tuple[list[str], np.ndarray, list[list[int]], dict[str, Any]]:
    texts: list[str] = []
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    comment_ids: set[str] = set()
    cardinality: Counter[int] = Counter()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle, delimiter="\t")):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError(f"{path.name} has too many rows")
            if len(row) != 3:
                raise ValueError(f"{path.name} row {row_number} has {len(row)} columns")
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"{path.name} row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError(f"{path.name} repeats a comment ID")
            comment_ids.add(comment_id)
            try:
                values = [int(value) for value in encoded_labels.split(",")]
            except ValueError as error:
                raise ValueError(f"{path.name} row {row_number} has invalid labels") from error
            if (
                not values
                or len(values) != len(set(values))
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"{path.name} row {row_number} has invalid labels")
            texts.append(text)
            gold[row_index, values] = 1
            gold_ids.append(values)
            cardinality[len(values)] += 1
    if len(texts) != expected_rows:
        raise ValueError(f"{path.name} has {len(texts)} rows; expected {expected_rows}")
    return texts, gold, gold_ids, {
        "label_cardinality": {
            str(key): value for key, value in sorted(cardinality.items())
        },
        "rows": len(texts),
        "unique_comment_ids": len(comment_ids),
    }


def _divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )


def compute_metrics(
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: tuple[str, ...],
) -> tuple[dict[str, Any], np.ndarray]:
    if gold.shape != predicted.shape or gold.shape[1] != len(labels):
        raise ValueError("Gold/prediction shape mismatch")
    gold_bool = gold.astype(bool)
    predicted_bool = predicted.astype(bool)
    tp = np.sum(gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fp = np.sum(~gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fn = np.sum(gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    tn = np.sum(~gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    support = tp + fn
    predicted_support = tp + fp
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    f1 = _divide(2 * tp, 2 * tp + fp + fn)
    total_support = int(np.sum(support))
    micro_tp, micro_fp, micro_fn = int(np.sum(tp)), int(np.sum(fp)), int(np.sum(fn))
    sample_tp = np.sum(gold_bool & predicted_bool, axis=1, dtype=np.int64)
    sample_gold = np.sum(gold_bool, axis=1, dtype=np.int64)
    sample_predicted = np.sum(predicted_bool, axis=1, dtype=np.int64)
    subset_accuracy = float(np.mean(np.all(gold_bool == predicted_bool, axis=1)))
    hamming = float(np.mean(gold_bool != predicted_bool))
    neutral_coprediction_rows = (
        int(
            np.sum(
                predicted_bool[:, labels.index("neutral")]
                & (sample_predicted > 1)
            )
        )
        if "neutral" in labels
        else 0
    )
    metrics = {
        "accuracy": subset_accuracy,
        "accuracy_definition": "strict subset/exact-match accuracy",
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
            "neutral_coprediction_rows": neutral_coprediction_rows,
        },
        "primary": {"name": "macro_f1", "value": float(np.mean(f1))},
        "samples": {
            "precision": float(np.mean(_divide(sample_tp, sample_predicted))),
            "recall": float(np.mean(_divide(sample_tp, sample_gold))),
            "f1": float(np.mean(_divide(2 * sample_tp, sample_gold + sample_predicted))),
        },
        "subset_accuracy": subset_accuracy,
        "weighted": {
            "precision": float(np.sum(precision * support) / total_support),
            "recall": float(np.sum(recall * support) / total_support),
            "f1": float(np.sum(f1 * support) / total_support),
        },
    }
    confusion = np.stack(
        [np.stack([tn, fp], axis=1), np.stack([fn, tp], axis=1)],
        axis=1,
    )
    return metrics, confusion


def write_per_label(path: Path, metrics: dict[str, Any], labels: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["label_id", "label", "precision", "recall", "f1", "support", "predicted_support"]
        )
        for label in labels:
            row = metrics["per_label"][label]
            writer.writerow(
                [
                    row["label_id"],
                    label,
                    format(row["precision"], ".17g"),
                    format(row["recall"], ".17g"),
                    format(row["f1"], ".17g"),
                    row["support"],
                    row["predicted_support"],
                ]
            )


def write_confusion(path: Path, confusion: np.ndarray, labels: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label_id", "label", "tn", "fp", "fn", "tp"])
        for index, label in enumerate(labels):
            tn, fp, fn, tp = confusion[index].ravel()
            writer.writerow([index, label, int(tn), int(fp), int(fn), int(tp)])


def write_score_predictions(
    path: Path,
    gold: np.ndarray,
    predicted: np.ndarray,
    scores: np.ndarray,
    labels: tuple[str, ...],
) -> None:
    fields = [
        "row_number",
        "gold_label_ids",
        "gold_labels",
        "predicted_label_ids",
        "predicted_labels",
        *[f"prob_{label}" for label in labels],
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(gold.shape[0]):
            gold_ids = np.flatnonzero(gold[index]).tolist()
            predicted_ids = np.flatnonzero(predicted[index]).tolist()
            row: dict[str, Any] = {
                "row_number": index + 1,
                "gold_label_ids": "|".join(str(value) for value in gold_ids),
                "gold_labels": "|".join(labels[value] for value in gold_ids),
                "predicted_label_ids": "|".join(str(value) for value in predicted_ids),
                "predicted_labels": "|".join(labels[value] for value in predicted_ids),
            }
            row.update(
                {
                    f"prob_{label}": format(float(scores[index, label_id]), ".17g")
                    for label_id, label in enumerate(labels)
                }
            )
            writer.writerow(row)


def finalize_bundle(
    output_dir: Path,
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: tuple[str, ...],
    extra_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics, confusion = compute_metrics(gold, predicted, labels)
    if extra_metrics:
        metrics.update(extra_metrics)
    write_json(output_dir / "metrics.json", metrics)
    write_per_label(output_dir / "per-label-metrics.csv", metrics, labels)
    write_confusion(output_dir / "multilabel-confusion-matrix.csv", confusion, labels)
    return metrics
