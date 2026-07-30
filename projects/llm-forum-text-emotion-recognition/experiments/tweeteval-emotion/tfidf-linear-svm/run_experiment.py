#!/usr/bin/env python3
"""Run EXP-005 on fixed TweetEval train and validation splits."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from time import perf_counter
import warnings

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "erc-matplotlib-cache")
)

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC


PROJECT_DIR = Path(__file__).resolve().parents[3]
EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    PROJECT_DIR
    / "data"
    / "tweeteval-emotion"
    / "official"
    / "datasets"
    / "emotion"
)
DEFAULT_OUTPUT_DIR = (
    EXPERIMENT_DIR / "runs" / "exp-005-word-char-linear-svm"
)
DEFAULT_COMPARISON_RUN = (
    PROJECT_DIR
    / "experiments"
    / "tweeteval-emotion"
    / "tfidf-logreg"
    / "runs"
    / "exp-004-balanced-validation"
    / "run.json"
)
UPSTREAM_COMMIT = "4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66"
EXPERIMENT_ID = "EXP-005"
RQ_ID = "RQ-B1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train word+character TF-IDF with LinearSVC on TweetEval emotion "
            "train and evaluate once on validation. Test is never read."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--comparison-run",
        type=Path,
        default=DEFAULT_COMPARISON_RUN,
        help="EXP-004 metadata used to verify the validation comparison.",
    )
    return parser.parse_args()


def read_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_labels(path: Path) -> list[int]:
    try:
        return [int(value.strip()) for value in read_text_lines(path)]
    except ValueError as error:
        raise ValueError(f"Non-integer label in {path}") from error


def read_label_mapping(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line_number, line in enumerate(read_text_lines(path), start=1):
        try:
            label_id, label_name = line.split("\t", maxsplit=1)
            mapping[int(label_id)] = label_name
        except ValueError as error:
            raise ValueError(
                f"Invalid mapping at {path}:{line_number}: {line!r}"
            ) from error
    return mapping


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_DIR))
    except ValueError:
        return str(path.resolve())


def prepare_output_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {path}. "
            "Choose a new directory to preserve existing evidence."
        )
    path.mkdir(parents=True, exist_ok=True)


def setup_logging(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-005")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
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


def load_data(data_dir: Path) -> dict[str, object]:
    paths = {
        "mapping": data_dir / "mapping.txt",
        "train_text": data_dir / "train_text.txt",
        "train_labels": data_dir / "train_labels.txt",
        "validation_text": data_dir / "val_text.txt",
        "validation_labels": data_dir / "val_labels.txt",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")

    mapping = read_label_mapping(paths["mapping"])
    train_texts = read_text_lines(paths["train_text"])
    train_labels = read_labels(paths["train_labels"])
    validation_texts = read_text_lines(paths["validation_text"])
    validation_labels = read_labels(paths["validation_labels"])

    for split, texts, labels in (
        ("train", train_texts, train_labels),
        ("validation", validation_texts, validation_labels),
    ):
        if not texts:
            raise ValueError(f"{split} split is empty")
        if len(texts) != len(labels):
            raise ValueError(
                f"{split} row mismatch: {len(texts)} texts and "
                f"{len(labels)} labels"
            )
        unknown = sorted(set(labels) - set(mapping))
        if unknown:
            raise ValueError(f"{split} labels missing from mapping: {unknown}")

    return {
        "paths": paths,
        "mapping": mapping,
        "train_texts": train_texts,
        "train_labels": train_labels,
        "validation_texts": validation_texts,
        "validation_labels": validation_labels,
    }


def load_comparison(path: Path, validation_paths: dict[str, Path]) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing comparison metadata: {path}")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("stage") != "validation":
        raise ValueError(f"Comparison is not a validation run: {path}")
    if metadata.get("test_split_accessed") is not False:
        raise ValueError(f"Comparison metadata does not exclude test: {path}")

    recorded_files = metadata["data"]["files_read"]
    for key in ("mapping", "validation_text", "validation_labels"):
        actual_hash = sha256(validation_paths[key])
        recorded_hash = recorded_files[key]["sha256"]
        if actual_hash != recorded_hash:
            raise ValueError(
                f"Comparison hash mismatch for {key}: "
                f"{actual_hash} != {recorded_hash}"
            )
    return metadata


def build_pipeline() -> Pipeline:
    features = FeatureUnion(
        transformer_list=[
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    lowercase=True,
                    min_df=2,
                    ngram_range=(1, 2),
                    norm="l2",
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char",
                    lowercase=True,
                    min_df=2,
                    ngram_range=(3, 5),
                    norm="l2",
                    sublinear_tf=True,
                ),
            ),
        ],
        transformer_weights={"word": 1.0, "character": 1.0},
    )
    return Pipeline(
        steps=[
            ("features", features),
            (
                "classifier",
                LinearSVC(
                    C=1.0,
                    class_weight=None,
                    dual="auto",
                    loss="squared_hinge",
                    max_iter=5000,
                    penalty="l2",
                    random_state=42,
                    tol=1e-4,
                ),
            ),
        ]
    )


def save_predictions(
    path: Path,
    gold_labels: list[int],
    predictions,
    decision_scores,
    class_ids: list[int],
    mapping: dict[int, str],
) -> None:
    headers = [f"decision_{mapping[class_id]}" for class_id in class_ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row_number",
                "gold_label_id",
                "gold_label",
                "predicted_label_id",
                "predicted_label",
                *headers,
            ]
        )
        for row_number, (gold, predicted, scores) in enumerate(
            zip(gold_labels, predictions, decision_scores, strict=True),
            start=1,
        ):
            writer.writerow(
                [
                    row_number,
                    gold,
                    mapping[gold],
                    int(predicted),
                    mapping[int(predicted)],
                    *[f"{float(score):.12f}" for score in scores],
                ]
            )


def save_confusion_csv(
    path: Path,
    matrix,
    class_ids: list[int],
    mapping: dict[int, str],
) -> None:
    names = [mapping[class_id] for class_id in class_ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true_label/predicted_label", *names])
        for name, row in zip(names, matrix, strict=True):
            writer.writerow([name, *[int(value) for value in row]])


def save_confusion_figure(
    path: Path,
    matrix,
    class_ids: list[int],
    mapping: dict[int, str],
) -> None:
    names = [mapping[class_id] for class_id in class_ids]
    figure, axis = plt.subplots(figsize=(7, 6))
    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=names,
    )
    display.plot(
        ax=axis,
        cmap="Blues",
        colorbar=False,
        values_format="d",
    )
    axis.set_title("EXP-005 TweetEval Emotion Validation")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    comparison_path = args.comparison_run.resolve()
    prepare_output_dir(output_dir)
    logger = setup_logging(output_dir)

    logger.info("Starting %s; test split access is prohibited", EXPERIMENT_ID)
    started_at = datetime.now(timezone.utc)
    total_start = perf_counter()
    data = load_data(data_dir)
    paths = data["paths"]
    comparison = load_comparison(
        comparison_path,
        {
            "mapping": paths["mapping"],
            "validation_text": paths["validation_text"],
            "validation_labels": paths["validation_labels"],
        },
    )
    logger.info(
        "Loaded %d train and %d validation rows",
        len(data["train_texts"]),
        len(data["validation_texts"]),
    )

    pipeline = build_pipeline()
    fit_start = perf_counter()
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        pipeline.fit(data["train_texts"], data["train_labels"])
    fit_seconds = perf_counter() - fit_start

    convergence_messages = [
        str(item.message)
        for item in captured_warnings
        if issubclass(item.category, ConvergenceWarning)
    ]
    if convergence_messages:
        raise RuntimeError(
            f"LinearSVC did not converge: {convergence_messages}"
        )

    evaluation_start = perf_counter()
    predictions = pipeline.predict(data["validation_texts"])
    decision_scores = pipeline.decision_function(data["validation_texts"])
    evaluation_seconds = perf_counter() - evaluation_start

    classifier = pipeline.named_steps["classifier"]
    class_ids = [int(value) for value in classifier.classes_]
    expected_classes = sorted(data["mapping"])
    if class_ids != expected_classes:
        raise ValueError(
            f"Model classes {class_ids} do not match mapping {expected_classes}"
        )

    accuracy = accuracy_score(data["validation_labels"], predictions)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            data["validation_labels"],
            predictions,
            labels=class_ids,
            average="macro",
            zero_division=0,
        )
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            data["validation_labels"],
            predictions,
            labels=class_ids,
            average="weighted",
            zero_division=0,
        )
    )
    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            data["validation_labels"],
            predictions,
            labels=class_ids,
            average=None,
            zero_division=0,
        )
    )
    matrix = confusion_matrix(
        data["validation_labels"], predictions, labels=class_ids
    )

    model_path = output_dir / "model.joblib"
    predictions_path = output_dir / "predictions.csv"
    matrix_csv_path = output_dir / "confusion_matrix.csv"
    matrix_png_path = output_dir / "confusion_matrix.png"
    metadata_path = output_dir / "run.json"

    joblib.dump(pipeline, model_path)
    save_predictions(
        predictions_path,
        data["validation_labels"],
        predictions,
        decision_scores,
        class_ids,
        data["mapping"],
    )
    save_confusion_csv(
        matrix_csv_path, matrix, class_ids, data["mapping"]
    )
    save_confusion_figure(
        matrix_png_path, matrix, class_ids, data["mapping"]
    )

    feature_union = pipeline.named_steps["features"]
    fitted_features = dict(feature_union.transformer_list)
    word_features = len(fitted_features["word"].vocabulary_)
    character_features = len(fitted_features["character"].vocabulary_)
    label_counts = Counter(data["train_labels"])
    validation_counts = Counter(data["validation_labels"])
    comparison_macro_f1 = comparison["metrics"]["macro"]["f1"]
    comparison_accuracy = comparison["metrics"]["accuracy"]
    total_seconds = perf_counter() - total_start

    per_class = {
        data["mapping"][class_id]: {
            "label_id": class_id,
            "precision": float(class_precision[index]),
            "recall": float(class_recall[index]),
            "f1": float(class_f1[index]),
            "support": int(class_support[index]),
        }
        for index, class_id in enumerate(class_ids)
    }
    metadata = {
        "experiment_id": EXPERIMENT_ID,
        "tier": "Major",
        "rq_id": RQ_ID,
        "stage": "train-validation",
        "status": "Completed",
        "created_at_utc": started_at.isoformat(),
        "accessed_splits": ["train", "validation"],
        "test_split_accessed": False,
        "comparison": {
            "experiment_id": "EXP-004",
            "run_metadata": {
                "path": relative_to_project(comparison_path),
                "sha256": sha256(comparison_path),
            },
            "baseline_macro_f1": float(comparison_macro_f1),
            "baseline_accuracy": float(comparison_accuracy),
            "macro_f1_delta": float(macro_f1 - comparison_macro_f1),
            "accuracy_delta": float(accuracy - comparison_accuracy),
            "practical_improvement_threshold": 0.005,
            "primary_rule_passed": bool(
                macro_f1 - comparison_macro_f1 >= 0.005
            ),
        },
        "data": {
            "dataset": "TweetEval emotion",
            "upstream_commit": UPSTREAM_COMMIT,
            "train_sample_count": len(data["train_texts"]),
            "validation_sample_count": len(data["validation_texts"]),
            "label_mapping": {
                str(class_id): data["mapping"][class_id]
                for class_id in class_ids
            },
            "train_class_distribution": {
                str(class_id): label_counts.get(class_id, 0)
                for class_id in class_ids
            },
            "validation_class_distribution": {
                str(class_id): validation_counts.get(class_id, 0)
                for class_id in class_ids
            },
            "exact_duplicate_checks": {
                "train_duplicate_rows": (
                    len(data["train_texts"])
                    - len(set(data["train_texts"]))
                ),
                "validation_duplicate_rows": (
                    len(data["validation_texts"])
                    - len(set(data["validation_texts"]))
                ),
                "train_validation_text_overlap": len(
                    set(data["train_texts"])
                    & set(data["validation_texts"])
                ),
            },
            "files_read": {
                name: {
                    "path": relative_to_project(path),
                    "sha256": sha256(path),
                }
                for name, path in paths.items()
            },
        },
        "pipeline": {
            "feature_union": {
                "weights": {"word": 1.0, "character": 1.0},
                "word_tfidf": {
                    "analyzer": "word",
                    "lowercase": True,
                    "min_df": 2,
                    "ngram_range": [1, 2],
                    "norm": "l2",
                    "sublinear_tf": True,
                    "vocabulary_size": word_features,
                },
                "character_tfidf": {
                    "analyzer": "char",
                    "lowercase": True,
                    "min_df": 2,
                    "ngram_range": [3, 5],
                    "norm": "l2",
                    "sublinear_tf": True,
                    "vocabulary_size": character_features,
                },
                "combined_feature_count": word_features
                + character_features,
            },
            "linear_svc": {
                "C": 1.0,
                "class_weight": None,
                "dual": "auto",
                "loss": "squared_hinge",
                "max_iter": 5000,
                "penalty": "l2",
                "random_state": 42,
                "tol": 1e-4,
                "classes": class_ids,
                "coefficient_shape": list(classifier.coef_.shape),
                "iterations": int(classifier.n_iter_),
                "convergence_warnings": convergence_messages,
            },
        },
        "metrics": {
            "primary": {"name": "macro_f1", "value": float(macro_f1)},
            "accuracy": float(accuracy),
            "macro": {
                "precision": float(macro_precision),
                "recall": float(macro_recall),
                "f1": float(macro_f1),
            },
            "weighted": {
                "precision": float(weighted_precision),
                "recall": float(weighted_recall),
                "f1": float(weighted_f1),
            },
            "per_class": per_class,
            "confusion_matrix": {
                "orientation": "rows=true, columns=predicted",
                "labels": [
                    data["mapping"][class_id] for class_id in class_ids
                ],
                "values": [
                    [int(value) for value in row] for row in matrix
                ],
            },
        },
        "source_alignment": {
            "paper": (
                "https://aclanthology.org/2020.findings-emnlp.148/"
            ),
            "official_validation_macro_f1": 0.638,
            "shared_design": "word and character n-gram features with SVM",
            "exact_reproduction": False,
            "reason": (
                "The paper and public repository do not disclose the "
                "complete n-gram and SVM hyperparameters."
            ),
        },
        "resource_budget": {
            "maximum_runs": 1,
            "wall_time_minutes": 5,
            "api_cost_usd": 0,
            "actual_run_number": 1,
        },
        "runtime": {
            "fit_seconds": round(fit_seconds, 6),
            "evaluation_seconds": round(evaluation_seconds, 6),
            "total_seconds": round(total_seconds, 6),
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
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
        "artifacts": {
            "model": {
                "path": relative_to_project(model_path),
                "sha256": sha256(model_path),
            },
            "predictions": {
                "path": relative_to_project(predictions_path),
                "sha256": sha256(predictions_path),
            },
            "confusion_matrix_csv": {
                "path": relative_to_project(matrix_csv_path),
                "sha256": sha256(matrix_csv_path),
            },
            "confusion_matrix_png": {
                "path": relative_to_project(matrix_png_path),
                "sha256": sha256(matrix_png_path),
            },
            "stdout_log": {
                "path": relative_to_project(output_dir / "stdout.log")
            },
            "metadata": {"path": relative_to_project(metadata_path)},
        },
        "invocation": [sys.executable, *sys.argv],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    logger.info("Fit time: %.6f seconds", fit_seconds)
    logger.info("Validation Macro-F1: %.6f", macro_f1)
    logger.info("Validation Accuracy: %.6f", accuracy)
    logger.info(
        "Delta vs EXP-004: Macro-F1 %+.6f, Accuracy %+.6f",
        macro_f1 - comparison_macro_f1,
        accuracy - comparison_accuracy,
    )
    logger.info("Test split accessed: no")
    logger.info("Artifacts: %s", output_dir)


if __name__ == "__main__":
    main()
