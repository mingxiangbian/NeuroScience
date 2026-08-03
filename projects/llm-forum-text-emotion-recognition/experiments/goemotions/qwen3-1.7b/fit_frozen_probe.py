#!/usr/bin/env python3
"""Fit and evaluate the registered EXP-028 matched linear probes."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import logging
import math
import platform
import subprocess
import sys
import time
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def setup_logger(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-028-fit")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(output_dir / "stdout.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def load_targets(
    path: Path,
    expected_rows: int,
    label_count: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    targets = np.zeros((expected_rows, label_count), dtype=np.uint8)
    comment_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source, delimiter="\t")
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError(f"{path.name} has more than {expected_rows} rows")
            if len(row) != 3:
                raise ValueError(f"{path.name} row {row_number} has {len(row)} columns")
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"{path.name} row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError(f"{path.name} row {row_number} repeats a comment ID")
            comment_ids.add(comment_id)
            try:
                label_ids = [int(value) for value in encoded_labels.split(",")]
            except ValueError as error:
                raise ValueError(f"{path.name} row {row_number} has a non-integer label") from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(f"{path.name} row {row_number} has empty or duplicate labels")
            if any(label_id < 0 or label_id >= label_count for label_id in label_ids):
                raise ValueError(f"{path.name} row {row_number} has an out-of-range label")
            targets[row_index, label_ids] = 1
    if len(comment_ids) != expected_rows:
        raise ValueError(f"{path.name} has {len(comment_ids)} rows; expected {expected_rows}")
    return targets, {
        "rows": expected_rows,
        "unique_comment_ids": len(comment_ids),
        "label_occurrences": [int(value) for value in targets.sum(axis=0)],
    }


def compute_metrics(
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: list[str],
) -> tuple[dict[str, Any], np.ndarray]:
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
            "f1": float(f1[index]),
            "label_id": index,
            "precision": float(precision[index]),
            "predicted_support": int(predicted_support[index]),
            "recall": float(recall[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = gold.sum(axis=1)
    predicted_cardinality = predicted.sum(axis=1)
    metrics = {
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
        "subset_accuracy": float(accuracy_score(gold, predicted)),
    }
    return metrics, multilabel_confusion_matrix(gold, predicted)


def save_predictions(
    path: Path,
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: list[str],
    probabilities: np.ndarray | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    probability_headers = [f"prob_{label}" for label in labels] if probabilities is not None else []
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(
            [
                "row_number",
                "gold_label_ids",
                "gold_labels",
                "predicted_label_ids",
                "predicted_labels",
                *probability_headers,
            ]
        )
        for row_index in range(gold.shape[0]):
            gold_ids = np.flatnonzero(gold[row_index]).tolist()
            predicted_ids = np.flatnonzero(predicted[row_index]).tolist()
            row: list[Any] = [
                row_index + 1,
                "|".join(str(value) for value in gold_ids),
                "|".join(labels[value] for value in gold_ids),
                "|".join(str(value) for value in predicted_ids),
                "|".join(labels[value] for value in predicted_ids),
            ]
            if probabilities is not None:
                row.extend(format(float(value), ".17g") for value in probabilities[row_index])
            writer.writerow(row)


def save_per_label(path: Path, metrics: dict[str, Any], labels: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(["label_id", "label", "precision", "recall", "f1", "support", "predicted_support"])
        for label_id, label in enumerate(labels):
            item = metrics["per_label"][label]
            writer.writerow(
                [
                    label_id,
                    label,
                    format(item["precision"], ".12f"),
                    format(item["recall"], ".12f"),
                    format(item["f1"], ".12f"),
                    item["support"],
                    item["predicted_support"],
                ]
            )


def save_confusion(path: Path, confusion: np.ndarray, labels: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(["label_id", "label", "tn", "fp", "fn", "tp"])
        for label_id, (label, matrix) in enumerate(zip(labels, confusion, strict=True)):
            tn, fp, fn, tp = (int(value) for value in matrix.ravel())
            writer.writerow([label_id, label, tn, fp, fn, tp])


def make_classifier(config: dict[str, Any]) -> OneVsRestClassifier:
    probe = config["probe"]
    return OneVsRestClassifier(
        LogisticRegression(
            C=float(probe["C"]),
            class_weight=probe["class_weight"],
            max_iter=int(probe["max_iter"]),
            penalty=probe["penalty"],
            random_state=int(probe["classifier_random_state"]),
            solver=probe["solver"],
            tol=float(probe["tol"]),
        ),
        n_jobs=int(probe["n_jobs"]),
    )


def fit_classifier(
    classifier: OneVsRestClassifier,
    train_features: np.ndarray,
    train_targets: np.ndarray,
) -> tuple[float, list[str]]:
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        classifier.fit(train_features, train_targets)
    convergence = [
        str(item.message)
        for item in captured
        if issubclass(item.category, ConvergenceWarning)
    ]
    if convergence:
        raise RuntimeError(f"Probe failed to converge: {convergence}")
    return time.perf_counter() - started, [
        f"{item.category.__name__}: {item.message}" for item in captured
    ]


def read_feature_metadata(
    cache_root: Path,
    condition: str,
    split: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    cache_dir = cache_root / condition / split
    metadata_path = cache_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_shape = [
        int(config["data"]["splits"][split]["rows"]),
        int(config["representation"]["hidden_size"]),
    ]
    if metadata["experiment_id"] != "EXP-028" or metadata["status"] != "Completed":
        raise ValueError(f"Incomplete feature cache: {cache_dir}")
    if metadata["condition"] != condition or metadata["split"]["name"] != split:
        raise ValueError(f"Feature cache identity mismatch: {cache_dir}")
    if metadata["config_sha256"] != sha256(Path(config["_config_path"])):
        raise ValueError(f"Feature cache config hash mismatch: {cache_dir}")
    if metadata["feature"]["shape"] != expected_shape:
        raise ValueError(f"Feature cache shape metadata mismatch: {cache_dir}")
    return metadata


def read_feature_cache(
    cache_root: Path,
    condition: str,
    split: str,
    config: dict[str, Any],
) -> tuple[np.memmap, dict[str, Any]]:
    cache_dir = cache_root / condition / split
    feature_path = cache_dir / "features.npy"
    metadata = read_feature_metadata(cache_root, condition, split, config)
    expected_shape = [
        int(config["data"]["splits"][split]["rows"]),
        int(config["representation"]["hidden_size"]),
    ]
    if sha256(feature_path) != metadata["feature"]["sha256"]:
        raise ValueError(f"Feature cache hash mismatch: {feature_path}")
    features = np.load(feature_path, mmap_mode="r")
    if list(features.shape) != expected_shape or features.dtype != np.float32:
        raise ValueError(f"Feature array mismatch: {feature_path}")
    return features, metadata


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


def paired_bootstrap(
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
    *,
    replicates: int,
    seed: int,
    batch_size: int,
    practical_threshold: float,
) -> dict[str, Any]:
    gold_u8 = gold.astype(np.uint8, copy=False)
    predicted_u8 = {name: value.astype(np.uint8, copy=False) for name, value in predictions.items()}
    tp_rows = {name: (gold_u8 & value).astype(np.uint8, copy=False) for name, value in predicted_u8.items()}
    samples = {name: np.empty(replicates, dtype=np.float64) for name in predicted_u8}
    rng = np.random.default_rng(seed)
    row_count = gold.shape[0]
    for start in range(0, replicates, batch_size):
        stop = min(start + batch_size, replicates)
        indices = rng.integers(0, row_count, size=(stop - start, row_count), dtype=np.int32)
        gold_support = np.sum(gold_u8[indices], axis=1, dtype=np.int32)
        for name, predicted in predicted_u8.items():
            predicted_support = np.sum(predicted[indices], axis=1, dtype=np.int32)
            true_positive = np.sum(tp_rows[name][indices], axis=1, dtype=np.int32)
            samples[name][start:stop] = macro_f1_from_counts(
                gold_support,
                true_positive,
                predicted_support,
            )

    observed = {
        name: float(compute_metrics(gold_u8, predicted, [str(index) for index in range(gold.shape[1])])[0]["macro"]["f1"])
        for name, predicted in predicted_u8.items()
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
        "observed_macro_f1": observed,
        "observed_macro_f1_difference": float(delta),
        "outcome": outcome,
        "practical_threshold": practical_threshold,
        "replicates": replicates,
        "seed": seed,
    }


def inventory_files(root: Path, *, exclude: set[str] | None = None) -> dict[str, dict[str, Any]]:
    excluded = exclude or set()
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in excluded:
            continue
        relative = path.relative_to(root).as_posix()
        records[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return records


def execute(args: argparse.Namespace, output_dir: Path, logger: logging.Logger) -> None:
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["_config_path"] = str(config_path)
    if config.get("experiment_id") != "EXP-028" or config.get("tier") != "Major":
        raise ValueError("Unexpected EXP-028 config identity")
    test_path = PROJECT_ROOT / config["data"]["test_path"]
    if test_path.exists():
        raise FileExistsError("GoEmotions test must remain absent")

    labels_path = PROJECT_ROOT / config["data"]["labels_path"]
    if sha256(labels_path) != config["data"]["labels_sha256"]:
        raise ValueError("Frozen label ontology hash mismatch")
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if len(labels) != int(config["data"]["label_count"]):
        raise ValueError("Frozen label count mismatch")
    targets: dict[str, np.ndarray] = {}
    split_summaries: dict[str, dict[str, Any]] = {}
    for split in ("train", "dev"):
        split_spec = config["data"]["splits"][split]
        split_path = PROJECT_ROOT / split_spec["path"]
        if sha256(split_path) != split_spec["sha256"]:
            raise ValueError(f"Frozen {split} hash mismatch")
        targets[split], split_summaries[split] = load_targets(
            split_path,
            int(split_spec["rows"]),
            len(labels),
        )
    logger.info("Loaded frozen train/dev targets; test remains absent")

    cache_root = PROJECT_ROOT / config["paths"]["private_cache_root"]
    model_root = cache_root / "probe-models"
    if model_root.exists():
        raise FileExistsError(f"Refusing to overwrite private probe models: {model_root}")
    model_root.mkdir(parents=True)

    feature_metadata: dict[str, dict[str, Any]] = {}
    for condition in ("base", "post-trained"):
        feature_metadata[condition] = {}
        for split in ("train", "dev"):
            feature_metadata[condition][split] = read_feature_metadata(
                cache_root,
                condition,
                split,
                config,
            )
    for split in ("train", "dev"):
        if feature_metadata["base"][split]["tokenization"]["token_id_stream_sha256"] != feature_metadata["post-trained"][split]["tokenization"]["token_id_stream_sha256"]:
            raise ValueError(f"Base/post-trained token streams differ for {split}")

    started_at = datetime.now(timezone.utc)
    total_started = time.perf_counter()
    predictions_by_condition: dict[str, np.ndarray] = {}
    condition_results: dict[str, Any] = {}
    condition_summary_rows: list[list[Any]] = []
    threshold = float(config["probe"]["threshold"])

    for condition in ("base", "post-trained"):
        logger.info("Preparing standardized features for %s", condition)
        train_features, _ = read_feature_cache(cache_root, condition, "train", config)
        dev_features, _ = read_feature_cache(cache_root, condition, "dev", config)
        scaler_started = time.perf_counter()
        scaler = StandardScaler(copy=True, with_mean=True, with_std=True)
        train_scaled = scaler.fit_transform(train_features).astype(np.float32, copy=False)
        dev_scaled = scaler.transform(dev_features).astype(np.float32, copy=False)
        scaler_seconds = time.perf_counter() - scaler_started
        if not np.isfinite(train_scaled).all() or not np.isfinite(dev_scaled).all():
            raise ValueError(f"Non-finite standardized feature for {condition}")

        classifier = make_classifier(config)
        fit_seconds, fit_warnings = fit_classifier(classifier, train_scaled, targets["train"])
        probability_started = time.perf_counter()
        probabilities = classifier.predict_proba(dev_scaled)
        prediction_seconds = time.perf_counter() - probability_started
        if probabilities.shape != targets["dev"].shape or not np.isfinite(probabilities).all():
            raise ValueError(f"Invalid real-probe probabilities for {condition}")
        predicted = (probabilities >= threshold).astype(np.uint8)
        metrics, confusion = compute_metrics(targets["dev"], predicted, labels)
        predictions_by_condition[condition] = predicted

        condition_dir = output_dir / condition
        condition_dir.mkdir(parents=True)
        save_predictions(condition_dir / "predictions.csv", targets["dev"], predicted, labels, probabilities)
        save_per_label(condition_dir / "per-label-metrics.csv", metrics, labels)
        save_confusion(condition_dir / "multilabel-confusion-matrix.csv", confusion, labels)
        write_json(condition_dir / "metrics.json", metrics)

        condition_model_dir = model_root / condition
        condition_model_dir.mkdir(parents=True)
        real_model_path = condition_model_dir / "real-probe.joblib"
        joblib.dump(
            {
                "classifier": classifier,
                "condition": condition,
                "labels": labels,
                "scaler": scaler,
                "threshold": threshold,
            },
            real_model_path,
            compress=3,
        )
        iterations = {
            labels[index]: int(estimator.n_iter_[0])
            for index, estimator in enumerate(classifier.estimators_)
        }

        shuffle_dir = condition_dir / "label-shuffle"
        shuffle_dir.mkdir()
        shuffle_results: list[dict[str, Any]] = []
        for seed in config["label_shuffle"]["seeds"]:
            rng = np.random.default_rng(int(seed))
            permutation = rng.permutation(targets["train"].shape[0])
            permutation_digest = hashlib.sha256(
                np.asarray(permutation, dtype="<i8").tobytes(order="C")
            ).hexdigest()
            shuffle_classifier = make_classifier(config)
            shuffle_fit_seconds, shuffle_warnings = fit_classifier(
                shuffle_classifier,
                train_scaled,
                targets["train"][permutation],
            )
            shuffle_probabilities = shuffle_classifier.predict_proba(dev_scaled)
            if shuffle_probabilities.shape != targets["dev"].shape or not np.isfinite(shuffle_probabilities).all():
                raise ValueError(f"Invalid label-shuffle probabilities for {condition} seed {seed}")
            shuffle_predicted = (shuffle_probabilities >= threshold).astype(np.uint8)
            shuffle_metrics, _ = compute_metrics(targets["dev"], shuffle_predicted, labels)
            shuffle_prediction_path = shuffle_dir / f"seed-{seed}-predictions.csv"
            save_predictions(
                shuffle_prediction_path,
                targets["dev"],
                shuffle_predicted,
                labels,
                probabilities=None,
            )
            shuffle_model_path = condition_model_dir / f"label-shuffle-seed-{seed}.joblib"
            joblib.dump(
                {
                    "classifier": shuffle_classifier,
                    "condition": condition,
                    "permutation_sha256": permutation_digest,
                    "seed": int(seed),
                    "threshold": threshold,
                },
                shuffle_model_path,
                compress=3,
            )
            shuffle_result = {
                "fit_seconds": shuffle_fit_seconds,
                "macro_f1": shuffle_metrics["macro"]["f1"],
                "metrics": shuffle_metrics,
                "model_path": str(shuffle_model_path.relative_to(PROJECT_ROOT)),
                "model_sha256": sha256(shuffle_model_path),
                "permutation_sha256": permutation_digest,
                "prediction_path": str(shuffle_prediction_path.relative_to(PROJECT_ROOT)),
                "prediction_sha256": sha256(shuffle_prediction_path),
                "seed": int(seed),
                "warnings": shuffle_warnings,
            }
            shuffle_results.append(shuffle_result)
            write_json(shuffle_dir / f"seed-{seed}-metrics.json", shuffle_metrics)
            logger.info(
                "%s label-shuffle seed %s Macro-F1 %.6f",
                condition,
                seed,
                shuffle_metrics["macro"]["f1"],
            )
            del shuffle_classifier, shuffle_probabilities, shuffle_predicted

        shuffle_macro = [float(item["macro_f1"]) for item in shuffle_results]
        real_minus_max_shuffle = float(metrics["macro"]["f1"] - max(shuffle_macro))
        condition_results[condition] = {
            "classifier_iterations_by_label": iterations,
            "feature_metadata_sha256": {
                split: sha256(cache_root / condition / split / "metadata.json")
                for split in ("train", "dev")
            },
            "fit_seconds": fit_seconds,
            "fit_warnings": fit_warnings,
            "label_shuffle": {
                "macro_f1_max": max(shuffle_macro),
                "macro_f1_mean": float(np.mean(shuffle_macro)),
                "macro_f1_min": min(shuffle_macro),
                "real_minus_max_shuffle_macro_f1": real_minus_max_shuffle,
                "runs": shuffle_results,
            },
            "metrics": metrics,
            "prediction_seconds": prediction_seconds,
            "private_real_model_path": str(real_model_path.relative_to(PROJECT_ROOT)),
            "private_real_model_sha256": sha256(real_model_path),
            "scaler_seconds": scaler_seconds,
        }
        condition_summary_rows.append(
            [
                condition,
                metrics["macro"]["f1"],
                metrics["micro"]["f1"],
                metrics["weighted"]["f1"],
                metrics["subset_accuracy"],
                float(np.mean(shuffle_macro)),
                max(shuffle_macro),
                real_minus_max_shuffle,
            ]
        )
        logger.info("%s real probe Macro-F1 %.6f", condition, metrics["macro"]["f1"])

        del train_features, dev_features, train_scaled, dev_scaled, scaler, classifier, probabilities
        gc.collect()

    bootstrap = paired_bootstrap(
        targets["dev"],
        predictions_by_condition,
        replicates=int(config["evaluation"]["bootstrap"]["replicates"]),
        seed=int(config["evaluation"]["bootstrap"]["seed"]),
        batch_size=int(config["evaluation"]["bootstrap"]["batch_size"]),
        practical_threshold=float(config["evaluation"]["practical_macro_f1_difference"]),
    )
    write_json(output_dir / "paired-bootstrap.json", bootstrap)
    write_json(output_dir / "aggregate-metrics.json", condition_results)
    with (output_dir / "condition-summary.csv").open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(
            [
                "condition",
                "macro_f1",
                "micro_f1",
                "weighted_f1",
                "subset_accuracy",
                "shuffle_macro_f1_mean",
                "shuffle_macro_f1_max",
                "real_minus_max_shuffle_macro_f1",
            ]
        )
        writer.writerows(condition_summary_rows)

    public_artifacts = inventory_files(output_dir, exclude={"run.json", "verification.json", "stdout.log"})
    private_models = inventory_files(model_root)
    runtime_seconds = time.perf_counter() - total_started
    if runtime_seconds > float(config["resource_budget"]["probe_wall_time_minutes_max"]) * 60:
        raise TimeoutError("Probe fitting exceeded the frozen wall-time budget")
    run = {
        "accessed_splits": ["train", "dev"],
        "artifacts": {
            "private_feature_metadata": {
                condition: {
                    split: {
                        "feature_sha256": feature_metadata[condition][split]["feature"]["sha256"],
                        "metadata_path": str((cache_root / condition / split / "metadata.json").relative_to(PROJECT_ROOT)),
                        "metadata_sha256": sha256(cache_root / condition / split / "metadata.json"),
                    }
                    for split in ("train", "dev")
                }
                for condition in ("base", "post-trained")
            },
            "private_probe_models": private_models,
            "public": public_artifacts,
            "stdout_log": {"path": str((output_dir / "stdout.log").relative_to(PROJECT_ROOT))},
        },
        "comparison": bootstrap,
        "conditions": condition_results,
        "config_path": str(config_path.relative_to(PROJECT_ROOT)),
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data": {
            "dataset_protocol": config["data"]["dataset_protocol"],
            "labels_sha256": config["data"]["labels_sha256"],
            "splits": split_summaries,
        },
        "experiment_id": "EXP-028",
        "git": git_metadata(),
        "implementation_sha256": sha256(Path(__file__).resolve()),
        "privacy": {
            "private_features_gitignored": True,
            "public_artifacts_contain_comment_ids": False,
            "public_artifacts_contain_raw_text": False,
        },
        "probe": config["probe"],
        "runtime": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "scipy": scipy.__version__,
            "total_seconds": runtime_seconds,
        },
        "started_at_utc": started_at.isoformat(),
        "status": "Completed",
        "test_absent_after_run": not test_path.exists(),
        "test_split_accessed": False,
        "tier": "Major",
    }
    write_json(output_dir / "run.json", run)
    logger.info(
        "EXP-028 complete: delta %.6f, outcome %s, test accessed: no",
        bootstrap["observed_macro_f1_difference"],
        bootstrap["outcome"],
    )


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite formal run directory: {output_dir}")
    output_dir.mkdir(parents=True)
    logger = setup_logger(output_dir)
    try:
        execute(args, output_dir, logger)
    except Exception as error:
        logger.exception("EXP-028 probe fitting failed")
        write_json(
            output_dir / "failure.json",
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": str(error),
                "error_type": type(error).__name__,
                "experiment_id": "EXP-028",
                "status": "Failed",
                "test_split_accessed": False,
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    main()
