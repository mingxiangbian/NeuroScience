#!/usr/bin/env python3
"""Train and evaluate the frozen EXP-018 GoEmotions baseline."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
import traceback
import warnings

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.multiclass import OneVsRestClassifier


EXPERIMENT_ID = "EXP-018"
RQ_ID = "RQ-G1"
PROTOCOL_ID = "DATA-GOE-V1"
SOURCE_REVISION = "8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0"
EXPECTED_HASHES = {
    "train.tsv": "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5",
    "dev.tsv": "575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62",
    "emotions.txt": "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89",
}
EXPECTED_ROWS = {"train": 43_410, "dev": 5_426}
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
RANDOM_STATE = 42

PROJECT_DIR = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = PROJECT_DIR / "data" / "goemotions"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "runs" / "exp-018-tfidf-ovr-logreg"
PROTOCOL_PATH = (
    EXPERIMENT_DIR
    / "protocols"
    / "exp-018-tfidf-ovr-logreg.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run frozen EXP-018 on GoEmotions train/dev. "
            "The test split is never read."
        )
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_DIR))
    except ValueError:
        return str(path.resolve())


def prepare_output_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {path}. EXP-018 is append-only."
        )
    path.mkdir(parents=True, exist_ok=True)


def setup_logger(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-018")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = __import__("time").gmtime

    file_handler = logging.FileHandler(
        output_dir / "stdout.log", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def git_metadata() -> dict[str, object]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        status = run_git("status", "--porcelain")
        return {
            "commit": run_git("rev-parse", "HEAD"),
            "branch": run_git("branch", "--show-current") or "detached",
            "dirty": bool(status),
            "dirty_path_count": len(status.splitlines()) if status else 0,
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return {
            "commit": "unavailable",
            "branch": "unavailable",
            "dirty": None,
            "error": str(error),
        }


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("GoEmotions manifest protocol ID mismatch")
    if manifest.get("status") != "verified":
        raise ValueError("GoEmotions manifest is not verified")
    if manifest["source"]["revision"] != SOURCE_REVISION:
        raise ValueError("GoEmotions source revision mismatch")
    test = manifest["splits"]["test"]
    if test.get("status") != "not_acquired" or test.get("exists") is not False:
        raise ValueError("GoEmotions manifest does not keep test unacquired")
    return manifest


def load_labels(path: Path) -> tuple[str, ...]:
    labels = tuple(path.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order differs from EXP-018 protocol")
    return labels


def load_split(
    path: Path, expected_rows: int, label_count: int
) -> tuple[list[str], np.ndarray, dict[str, object]]:
    texts: list[str] = []
    targets = np.zeros((expected_rows, label_count), dtype=np.uint8)
    comment_ids: set[str] = set()
    cardinality: Counter[int] = Counter()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError(f"{path.name} has more than {expected_rows} rows")
            if len(row) != 3:
                raise ValueError(
                    f"{path.name} row {row_number} has {len(row)} columns"
                )
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"{path.name} row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError(
                    f"{path.name} row {row_number} repeats a comment ID"
                )
            comment_ids.add(comment_id)

            try:
                label_ids = tuple(int(value) for value in encoded_labels.split(","))
            except ValueError as error:
                raise ValueError(
                    f"{path.name} row {row_number} has a non-integer label"
                ) from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(
                    f"{path.name} row {row_number} has empty or duplicate labels"
                )
            if any(value < 0 or value >= label_count for value in label_ids):
                raise ValueError(
                    f"{path.name} row {row_number} has an out-of-range label"
                )

            texts.append(text)
            targets[row_index, list(label_ids)] = 1
            cardinality[len(label_ids)] += 1

    if len(texts) != expected_rows:
        raise ValueError(
            f"{path.name} has {len(texts)} rows; expected {expected_rows}"
        )
    return texts, targets, {
        "rows": len(texts),
        "unique_comment_ids": len(comment_ids),
        "label_cardinality": {
            str(key): value for key, value in sorted(cardinality.items())
        },
    }


def compute_metrics(
    gold: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]
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
        for index, label in enumerate(labels)
    }

    subset_accuracy = float(accuracy_score(gold, predicted))
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = gold.sum(axis=1)
    predicted_cardinality = predicted.sum(axis=1)
    empty_predictions = int(np.sum(predicted_cardinality == 0))
    neutral_copredictions = int(
        np.sum((predicted[:, 27] == 1) & (predicted_cardinality > 1))
    )
    confusion = multilabel_confusion_matrix(gold, predicted)

    metrics: dict[str, object] = {
        "primary": {
            "name": "macro_f1",
            "value": averages["macro"]["f1"],
        },
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
            "empty_prediction_rows": empty_predictions,
            "neutral_coprediction_rows": neutral_copredictions,
        },
        "per_label": per_label,
    }
    return metrics, confusion


def save_predictions(
    path: Path,
    gold: np.ndarray,
    predicted: np.ndarray,
    probabilities: np.ndarray,
    labels: tuple[str, ...],
) -> None:
    probability_headers = [f"prob_{label}" for label in labels]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
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
            writer.writerow(
                [
                    row_index + 1,
                    "|".join(str(value) for value in gold_ids),
                    "|".join(labels[value] for value in gold_ids),
                    "|".join(str(value) for value in predicted_ids),
                    "|".join(labels[value] for value in predicted_ids),
                    *[format(float(value), ".17g") for value in probabilities[row_index]],
                ]
            )


def save_per_label_metrics(
    path: Path, metrics: dict[str, object], labels: tuple[str, ...]
) -> None:
    per_label = metrics["per_label"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "label_id",
                "label",
                "precision",
                "recall",
                "f1",
                "support",
                "predicted_support",
            ]
        )
        for label_id, label in enumerate(labels):
            values = per_label[label]
            writer.writerow(
                [
                    label_id,
                    label,
                    format(values["precision"], ".12f"),
                    format(values["recall"], ".12f"),
                    format(values["f1"], ".12f"),
                    values["support"],
                    values["predicted_support"],
                ]
            )


def save_confusion(
    path: Path, confusion: np.ndarray, labels: tuple[str, ...]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label_id", "label", "tn", "fp", "fn", "tp"])
        for label_id, (label, matrix) in enumerate(zip(labels, confusion, strict=True)):
            tn, fp, fn, tp = (int(value) for value in matrix.ravel())
            writer.writerow([label_id, label, tn, fp, fn, tp])


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute(args: argparse.Namespace, output_dir: Path, logger: logging.Logger) -> None:
    started_at = datetime.now(timezone.utc)
    total_start = perf_counter()
    data_root = args.data_root.resolve()
    official_dir = data_root / "official"
    test_path = official_dir / "test.tsv"
    if test_path.exists():
        raise RuntimeError(f"Test split exists and EXP-018 must stop: {test_path}")

    paths = {
        "manifest": data_root / "manifest.json",
        "labels": official_dir / "emotions.txt",
        "train": official_dir / "train.tsv",
        "dev": official_dir / "dev.tsv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required EXP-018 inputs: {missing}")
    for name, expected_hash in EXPECTED_HASHES.items():
        actual_hash = sha256_file(official_dir / name)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Hash mismatch for {name}: {actual_hash} != {expected_hash}"
            )

    manifest = load_manifest(paths["manifest"])
    labels = load_labels(paths["labels"])
    logger.info("Loading frozen GoEmotions train/dev; test access prohibited")
    train_texts, train_targets, train_summary = load_split(
        paths["train"], EXPECTED_ROWS["train"], len(labels)
    )
    dev_texts, dev_targets, dev_summary = load_split(
        paths["dev"], EXPECTED_ROWS["dev"], len(labels)
    )
    logger.info(
        "Loaded %d train and %d dev rows with %d labels",
        len(train_texts),
        len(dev_texts),
        len(labels),
    )

    vectorizer = TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        min_df=2,
        max_features=100_000,
        ngram_range=(1, 2),
        norm="l2",
        sublinear_tf=True,
    )
    vectorizer_start = perf_counter()
    train_features = vectorizer.fit_transform(train_texts)
    dev_features = vectorizer.transform(dev_texts)
    vectorizer_seconds = perf_counter() - vectorizer_start
    del train_texts, dev_texts
    logger.info(
        "Built %d train-fitted TF-IDF features in %.3f seconds",
        train_features.shape[1],
        vectorizer_seconds,
    )

    classifier = OneVsRestClassifier(
        LogisticRegression(
            C=1.0,
            class_weight=None,
            solver="liblinear",
            penalty="l2",
            max_iter=1000,
            tol=1e-4,
            random_state=RANDOM_STATE,
        ),
        n_jobs=1,
    )
    fit_start = perf_counter()
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        classifier.fit(train_features, train_targets)
    fit_seconds = perf_counter() - fit_start
    convergence_warnings = [
        str(item.message)
        for item in captured_warnings
        if issubclass(item.category, ConvergenceWarning)
    ]
    if convergence_warnings:
        raise RuntimeError(
            f"EXP-018 classifier did not converge: {convergence_warnings}"
        )

    evaluation_start = perf_counter()
    probabilities = classifier.predict_proba(dev_features)
    if probabilities.shape != dev_targets.shape:
        raise ValueError(
            f"Probability shape {probabilities.shape} != {dev_targets.shape}"
        )
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("Non-finite validation probability detected")
    predictions = (probabilities >= THRESHOLD).astype(np.uint8)
    metrics, confusion = compute_metrics(dev_targets, predictions, labels)
    evaluation_seconds = perf_counter() - evaluation_start

    model_path = output_dir / "model.joblib"
    predictions_path = output_dir / "predictions.csv"
    per_label_path = output_dir / "per_label_metrics.csv"
    confusion_path = output_dir / "multilabel_confusion_matrix.csv"
    run_path = output_dir / "run.json"

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "classifier": classifier,
            "labels": labels,
            "threshold": THRESHOLD,
        },
        model_path,
        compress=3,
    )
    save_predictions(
        predictions_path,
        dev_targets,
        predictions,
        probabilities,
        labels,
    )
    save_per_label_metrics(per_label_path, metrics, labels)
    save_confusion(confusion_path, confusion, labels)

    total_seconds = perf_counter() - total_start
    estimator_iterations = {
        labels[index]: int(estimator.n_iter_[0])
        for index, estimator in enumerate(classifier.estimators_)
    }
    file_records = {
        key: {
            "path": project_path(path),
            "sha256": sha256_file(path),
        }
        for key, path in paths.items()
    }
    metadata: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "tier": "Major",
        "rq_id": RQ_ID,
        "stage": "train-dev",
        "status": "Completed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "accessed_splits": ["train", "dev"],
        "test_split_accessed": False,
        "data": {
            "dataset": "GoEmotions agreement-filtered",
            "protocol_id": PROTOCOL_ID,
            "source_revision": SOURCE_REVISION,
            "train": train_summary,
            "dev": dev_summary,
            "labels": list(labels),
            "files_read": file_records,
            "reviewed_cross_split_quality": manifest["cross_split"],
            "test": {
                "status": "not_acquired",
                "exists": False,
                "path": project_path(test_path),
            },
        },
        "model": {
            "name": "word TF-IDF + One-vs-Rest Logistic Regression",
            "task": "28-label binary relevance multi-label classification",
            "tfidf": {
                "analyzer": "word",
                "lowercase": True,
                "min_df": 2,
                "max_features": 100_000,
                "ngram_range": [1, 2],
                "norm": "l2",
                "sublinear_tf": True,
                "vocabulary_size": len(vectorizer.vocabulary_),
                "train_matrix_shape": list(train_features.shape),
                "train_matrix_nnz": int(train_features.nnz),
                "dev_matrix_shape": list(dev_features.shape),
                "dev_matrix_nnz": int(dev_features.nnz),
            },
            "classifier": {
                "reduction": "OneVsRestClassifier",
                "base_estimator": "LogisticRegression",
                "C": 1.0,
                "class_weight": None,
                "solver": "liblinear",
                "penalty": "l2",
                "max_iter": 1000,
                "tol": 1e-4,
                "random_state": RANDOM_STATE,
                "n_jobs": 1,
                "iterations_by_label": estimator_iterations,
                "convergence_warnings": convergence_warnings,
            },
            "decision_rule": {
                "threshold": THRESHOLD,
                "per_label_tuning": False,
                "force_nonempty_prediction": False,
                "neutral_suppression": False,
            },
        },
        "metrics": metrics,
        "comparison": {
            "parent_experiment": None,
            "reason": "First GoEmotions simple multi-label baseline",
            "cross_dataset_comparison_prohibited": True,
        },
        "resource_budget": {
            "maximum_formal_runs": 1,
            "actual_run_number": 1,
            "wall_time_limit_minutes": 20,
            "api_cost_usd": 0,
        },
        "runtime": {
            "vectorizer_seconds": round(vectorizer_seconds, 6),
            "fit_seconds": round(fit_seconds, 6),
            "evaluation_seconds": round(evaluation_seconds, 6),
            "total_seconds": round(total_seconds, 6),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor() or "unavailable",
            "executable": sys.executable,
            "git": git_metadata(),
            "warnings": [
                {
                    "category": item.category.__name__,
                    "message": str(item.message),
                }
                for item in captured_warnings
            ],
        },
        "protocol": {
            "path": project_path(PROTOCOL_PATH),
            "sha256": sha256_file(PROTOCOL_PATH),
        },
        "implementation": {
            "path": project_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
        "artifacts": {
            "model": {
                "path": project_path(model_path),
                "sha256": sha256_file(model_path),
                "gitignored": True,
            },
            "predictions": {
                "path": project_path(predictions_path),
                "sha256": sha256_file(predictions_path),
            },
            "per_label_metrics": {
                "path": project_path(per_label_path),
                "sha256": sha256_file(per_label_path),
            },
            "multilabel_confusion_matrix": {
                "path": project_path(confusion_path),
                "sha256": sha256_file(confusion_path),
                "orientation": "per label [[TN, FP], [FN, TP]]",
            },
            "stdout_log": {
                "path": project_path(output_dir / "stdout.log"),
            },
            "run_metadata": {"path": project_path(run_path)},
        },
        "privacy": {
            "predictions_contain_text": False,
            "predictions_contain_comment_ids": False,
        },
        "invocation": [sys.executable, *sys.argv],
        "working_directory": str(Path.cwd()),
    }
    write_json(run_path, metadata)

    logger.info("Fit time: %.3f seconds", fit_seconds)
    logger.info("Dev Macro-F1: %.6f", metrics["macro"]["f1"])
    logger.info("Dev Micro-F1: %.6f", metrics["micro"]["f1"])
    logger.info("Dev subset accuracy: %.6f", metrics["subset_accuracy"])
    logger.info("Empty prediction rows: %d", metrics["prediction_diagnostics"]["empty_prediction_rows"])
    logger.info("Test split accessed: no")
    logger.info("Artifacts: %s", output_dir)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    prepare_output_dir(output_dir)
    logger = setup_logger(output_dir)
    try:
        execute(args, output_dir, logger)
    except Exception as error:
        logger.exception("EXP-018 failed")
        failure = {
            "experiment_id": EXPERIMENT_ID,
            "tier": "Major",
            "rq_id": RQ_ID,
            "stage": "train-dev",
            "status": "Failed",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            "test_split_accessed": False,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "invocation": [sys.executable, *sys.argv],
            "working_directory": str(Path.cwd()),
        }
        write_json(output_dir / "run.json", failure)
        raise


if __name__ == "__main__":
    main()
