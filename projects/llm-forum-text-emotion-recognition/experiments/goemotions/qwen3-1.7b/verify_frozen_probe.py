#!/usr/bin/env python3
"""Independently verify the formal EXP-028 frozen-probe run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    precision_recall_fscore_support,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_targets(path: Path, expected_rows: int, label_count: int) -> np.ndarray:
    targets = np.zeros((expected_rows, label_count), dtype=np.uint8)
    identifiers: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source, delimiter="\t")
        for row_index, row in enumerate(reader):
            if row_index >= expected_rows or len(row) != 3:
                raise ValueError(f"Malformed frozen split: {path}")
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id or comment_id in identifiers:
                raise ValueError(f"Invalid row {row_index + 1} in {path}")
            identifiers.add(comment_id)
            label_ids = [int(value) for value in encoded_labels.split(",")]
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(f"Invalid labels at row {row_index + 1} in {path}")
            if any(value < 0 or value >= label_count for value in label_ids):
                raise ValueError(f"Out-of-range label at row {row_index + 1} in {path}")
            targets[row_index, label_ids] = 1
    if len(identifiers) != expected_rows:
        raise ValueError(f"Unexpected row count in {path}")
    return targets


def parse_prediction_csv(
    path: Path,
    gold: np.ndarray,
    labels: list[str],
    *,
    require_probabilities: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    predicted = np.zeros_like(gold)
    probabilities = (
        np.zeros(gold.shape, dtype=np.float64) if require_probabilities else None
    )
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        prohibited = {"text", "raw_text", "comment_id", "input_text"}
        if prohibited.intersection(fieldnames):
            raise ValueError(f"Private field found in public prediction file: {path}")
        expected_probability_fields = [f"prob_{label}" for label in labels]
        if require_probabilities and not set(expected_probability_fields).issubset(fieldnames):
            raise ValueError(f"Missing probability columns in {path}")
        rows = list(reader)
    if len(rows) != gold.shape[0]:
        raise ValueError(f"Unexpected prediction row count in {path}")
    for row_index, row in enumerate(rows):
        if int(row["row_number"]) != row_index + 1:
            raise ValueError(f"Prediction order changed in {path}")
        saved_gold = [int(value) for value in row["gold_label_ids"].split("|") if value]
        if saved_gold != np.flatnonzero(gold[row_index]).tolist():
            raise ValueError(f"Saved gold differs at row {row_index + 1} in {path}")
        saved_predicted = [
            int(value) for value in row["predicted_label_ids"].split("|") if value
        ]
        if any(value < 0 or value >= len(labels) for value in saved_predicted):
            raise ValueError(f"Out-of-range prediction in {path}")
        predicted[row_index, saved_predicted] = 1
        if probabilities is not None:
            probabilities[row_index] = [
                float(row[field]) for field in expected_probability_fields
            ]
    return predicted, probabilities


def compute_metrics(gold: np.ndarray, predicted: np.ndarray, labels: list[str]) -> dict[str, Any]:
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
    predicted_cardinality = predicted.sum(axis=1)
    loss = float(hamming_loss(gold, predicted))
    return {
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": loss,
        "label_accuracy": 1.0 - loss,
        "label_cardinality": {
            "gold_mean": float(np.mean(gold.sum(axis=1))),
            "predicted_mean": float(np.mean(predicted_cardinality)),
        },
        **averages,
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
            "empty_prediction_rows": int(np.sum(predicted_cardinality == 0)),
            "neutral_coprediction_rows": int(
                np.sum((predicted[:, 27] == 1) & (predicted_cardinality > 1))
            ),
        },
        "primary": {"name": "macro_f1", "value": averages["macro"]["f1"]},
        "subset_accuracy": float(accuracy_score(gold, predicted)),
    }


def compare_nested(
    expected: Any,
    actual: Any,
    *,
    path: str,
    numeric_differences: list[float],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            raise ValueError(f"Key mismatch at {path}")
        for key in expected:
            compare_nested(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
                numeric_differences=numeric_differences,
            )
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise ValueError(f"List mismatch at {path}")
        for index, value in enumerate(expected):
            compare_nested(
                value,
                actual[index],
                path=f"{path}[{index}]",
                numeric_differences=numeric_differences,
            )
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        difference = abs(float(expected) - float(actual))
        numeric_differences.append(difference)
        if difference > 1e-12:
            raise ValueError(f"Numeric mismatch at {path}: {expected} != {actual}")
        return
    if expected != actual:
        raise ValueError(f"Value mismatch at {path}: {expected!r} != {actual!r}")


def macro_f1_from_counts(
    gold_support: np.ndarray,
    true_positive: np.ndarray,
    predicted_support: np.ndarray,
) -> np.ndarray:
    denominator = gold_support + predicted_support
    per_label = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=denominator != 0,
    )
    return np.mean(per_label, axis=1)


def recompute_bootstrap(
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
    config: dict[str, Any],
) -> dict[str, Any]:
    bootstrap = config["evaluation"]["bootstrap"]
    replicates = int(bootstrap["replicates"])
    batch_size = int(bootstrap["batch_size"])
    practical_threshold = float(config["evaluation"]["practical_macro_f1_difference"])
    gold_u8 = gold.astype(np.uint8, copy=False)
    predictions_u8 = {key: value.astype(np.uint8, copy=False) for key, value in predictions.items()}
    tp_rows = {key: (gold_u8 & value).astype(np.uint8, copy=False) for key, value in predictions_u8.items()}
    samples = {key: np.empty(replicates, dtype=np.float64) for key in predictions_u8}
    rng = np.random.default_rng(int(bootstrap["seed"]))
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        indices = rng.integers(0, gold.shape[0], size=(stop - start, gold.shape[0]), dtype=np.int32)
        gold_support = np.sum(gold_u8[indices], axis=1, dtype=np.int32)
        for key, predicted in predictions_u8.items():
            predicted_support = np.sum(predicted[indices], axis=1, dtype=np.int32)
            true_positive = np.sum(tp_rows[key][indices], axis=1, dtype=np.int32)
            samples[key][start:stop] = macro_f1_from_counts(
                gold_support,
                true_positive,
                predicted_support,
            )
    observed = {
        key: compute_metrics(gold, predicted, [str(index) for index in range(gold.shape[1])])["macro"]["f1"]
        for key, predicted in predictions_u8.items()
    }
    differences = samples["post-trained"] - samples["base"]
    lower, upper = np.quantile(differences, [0.025, 0.975])
    delta = observed["post-trained"] - observed["base"]
    if delta >= practical_threshold and lower > 0:
        outcome = "post-trained_more_linearly_decodable"
    elif delta <= -practical_threshold and upper < 0:
        outcome = "base_more_linearly_decodable"
    elif abs(delta) < practical_threshold:
        outcome = "practical_tie"
    else:
        outcome = "inconclusive"
    return {
        "comparison": "post-trained_minus_base",
        "ci_95_percentile": {"lower": float(lower), "upper": float(upper)},
        "observed_macro_f1": {key: float(value) for key, value in observed.items()},
        "observed_macro_f1_difference": float(delta),
        "outcome": outcome,
        "practical_threshold": practical_threshold,
        "replicates": replicates,
        "seed": int(bootstrap["seed"]),
    }


def verify_artifact_hashes(run: dict[str, Any], run_dir: Path, cache_root: Path) -> int:
    checked = 0
    for relative, record in run["artifacts"]["public"].items():
        path = run_dir / relative
        if sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"Public artifact mismatch: {path}")
        checked += 1
    model_root = cache_root / "probe-models"
    for relative, record in run["artifacts"]["private_probe_models"].items():
        path = model_root / relative
        if sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"Private model artifact mismatch: {path}")
        checked += 1
    for condition in ("base", "post-trained"):
        for split in ("train", "dev"):
            record = run["artifacts"]["private_feature_metadata"][condition][split]
            metadata_path = PROJECT_ROOT / record["metadata_path"]
            if sha256(metadata_path) != record["metadata_sha256"]:
                raise ValueError(f"Feature metadata mismatch: {metadata_path}")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            feature_path = cache_root / condition / split / "features.npy"
            if sha256(feature_path) != metadata["feature"]["sha256"]:
                raise ValueError(f"Feature file mismatch: {feature_path}")
            if metadata["feature"]["sha256"] != record["feature_sha256"]:
                raise ValueError(f"Recorded feature digest mismatch: {feature_path}")
            checked += 2
    return checked


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite: {verification_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-028" or run["experiment_id"] != "EXP-028":
        raise ValueError("EXP-028 identity mismatch")
    if run["status"] != "Completed" or run["config_sha256"] != sha256(config_path):
        raise ValueError("EXP-028 run or config freeze mismatch")
    if run["test_split_accessed"] or not run["test_absent_after_run"]:
        raise ValueError("EXP-028 test gate claim failed")
    test_path = PROJECT_ROOT / config["data"]["test_path"]
    if test_path.exists():
        raise FileExistsError("GoEmotions test must remain absent")

    labels_path = PROJECT_ROOT / config["data"]["labels_path"]
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if sha256(labels_path) != config["data"]["labels_sha256"] or len(labels) != config["data"]["label_count"]:
        raise ValueError("Frozen label ontology mismatch")
    train_spec = config["data"]["splits"]["train"]
    dev_spec = config["data"]["splits"]["dev"]
    train_path = PROJECT_ROOT / train_spec["path"]
    dev_path = PROJECT_ROOT / dev_spec["path"]
    if sha256(train_path) != train_spec["sha256"] or sha256(dev_path) != dev_spec["sha256"]:
        raise ValueError("Frozen split hash mismatch")
    train_gold = load_targets(train_path, int(train_spec["rows"]), len(labels))
    dev_gold = load_targets(dev_path, int(dev_spec["rows"]), len(labels))

    cache_root = PROJECT_ROOT / config["paths"]["private_cache_root"]
    checked_artifact_count = verify_artifact_hashes(run, run_dir, cache_root)
    numeric_differences: list[float] = []
    probability_differences: list[float] = []
    predictions_by_condition: dict[str, np.ndarray] = {}

    token_digests: dict[str, dict[str, str]] = {"base": {}, "post-trained": {}}
    for condition in ("base", "post-trained"):
        for split in ("train", "dev"):
            metadata = json.loads(
                (cache_root / condition / split / "metadata.json").read_text(encoding="utf-8")
            )
            token_digests[condition][split] = metadata["tokenization"]["token_id_stream_sha256"]
            if metadata["test_split_accessed"] or metadata["privacy"]["contains_raw_text"]:
                raise ValueError(f"Feature metadata privacy or test gate failed: {condition}/{split}")
    for split in ("train", "dev"):
        if token_digests["base"][split] != token_digests["post-trained"][split]:
            raise ValueError(f"Matched token stream differs for {split}")

    for condition in ("base", "post-trained"):
        dev_features = np.load(cache_root / condition / "dev" / "features.npy", mmap_mode="r")
        real_model_path = PROJECT_ROOT / run["conditions"][condition]["private_real_model_path"]
        bundle = joblib.load(real_model_path)
        dev_scaled = bundle["scaler"].transform(dev_features).astype(np.float32, copy=False)
        recomputed_probabilities = bundle["classifier"].predict_proba(dev_scaled)
        saved_predictions, saved_probabilities = parse_prediction_csv(
            run_dir / condition / "predictions.csv",
            dev_gold,
            labels,
            require_probabilities=True,
        )
        if saved_probabilities is None:
            raise ValueError("Missing saved real-probe probabilities")
        max_probability_difference = float(np.max(np.abs(recomputed_probabilities - saved_probabilities)))
        probability_differences.append(max_probability_difference)
        if max_probability_difference > 1e-12:
            raise ValueError(f"Probability mismatch for {condition}: {max_probability_difference}")
        recomputed_predictions = (
            recomputed_probabilities >= float(config["probe"]["threshold"])
        ).astype(np.uint8)
        if not np.array_equal(recomputed_predictions, saved_predictions):
            raise ValueError(f"Real-probe prediction mismatch for {condition}")
        predictions_by_condition[condition] = saved_predictions
        recomputed_metrics = compute_metrics(dev_gold, saved_predictions, labels)
        saved_metrics = json.loads((run_dir / condition / "metrics.json").read_text(encoding="utf-8"))
        compare_nested(
            recomputed_metrics,
            saved_metrics,
            path=f"{condition}.metrics",
            numeric_differences=numeric_differences,
        )

        for seed in config["label_shuffle"]["seeds"]:
            seed = int(seed)
            permutation = np.random.default_rng(seed).permutation(train_gold.shape[0])
            expected_permutation_hash = hashlib.sha256(
                np.asarray(permutation, dtype="<i8").tobytes(order="C")
            ).hexdigest()
            shuffle_model_path = cache_root / "probe-models" / condition / f"label-shuffle-seed-{seed}.joblib"
            shuffle_bundle = joblib.load(shuffle_model_path)
            if shuffle_bundle["permutation_sha256"] != expected_permutation_hash:
                raise ValueError(f"Label-shuffle permutation mismatch for {condition}/{seed}")
            shuffle_probabilities = shuffle_bundle["classifier"].predict_proba(dev_scaled)
            recomputed_shuffle = (
                shuffle_probabilities >= float(config["probe"]["threshold"])
            ).astype(np.uint8)
            saved_shuffle, _ = parse_prediction_csv(
                run_dir / condition / "label-shuffle" / f"seed-{seed}-predictions.csv",
                dev_gold,
                labels,
                require_probabilities=False,
            )
            if not np.array_equal(recomputed_shuffle, saved_shuffle):
                raise ValueError(f"Label-shuffle prediction mismatch for {condition}/{seed}")
            recomputed_shuffle_metrics = compute_metrics(dev_gold, saved_shuffle, labels)
            saved_shuffle_metrics = json.loads(
                (run_dir / condition / "label-shuffle" / f"seed-{seed}-metrics.json").read_text(encoding="utf-8")
            )
            compare_nested(
                recomputed_shuffle_metrics,
                saved_shuffle_metrics,
                path=f"{condition}.shuffle.{seed}",
                numeric_differences=numeric_differences,
            )

    recomputed_bootstrap = recompute_bootstrap(dev_gold, predictions_by_condition, config)
    saved_bootstrap = json.loads((run_dir / "paired-bootstrap.json").read_text(encoding="utf-8"))
    compare_nested(
        recomputed_bootstrap,
        saved_bootstrap,
        path="paired_bootstrap",
        numeric_differences=numeric_differences,
    )
    compare_nested(
        saved_bootstrap,
        run["comparison"],
        path="run.comparison",
        numeric_differences=numeric_differences,
    )

    verification = {
        "accessed_splits": ["train", "dev"],
        "checked_artifact_count": checked_artifact_count,
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-028",
        "max_metric_or_bootstrap_difference": max(numeric_differences, default=0.0),
        "max_probability_difference": max(probability_differences, default=0.0),
        "run_json_sha256": sha256(run_dir / "run.json"),
        "status": "Passed",
        "test_absent": not test_path.exists(),
        "test_split_accessed": False,
        "token_streams_identical_across_conditions": True,
        "verifier_sha256": sha256(Path(__file__).resolve()),
    }
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "max_metric_difference": verification["max_metric_or_bootstrap_difference"],
                "max_probability_difference": verification["max_probability_difference"],
                "status": verification["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
