#!/usr/bin/env python3
"""Run EXP-007 with the train-CV-selected frozen configuration."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import warnings

import joblib
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from run_experiment import (
    DEFAULT_DATA_DIR,
    EXPERIMENT_DIR,
    git_metadata,
    load_data,
    prepare_output_dir,
    relative_to_project,
    save_confusion_csv,
    save_predictions,
    setup_logging,
    sha256,
)
import matplotlib.pyplot as plt


EXPERIMENT_ID = "EXP-007"
RQ_ID = "RQ-B1"
EXPECTED_CONFIG_SHA256 = (
    "8ddb3e3a479ebb53de8cee25401ff792a"
    "cff770a6e5a4cc8823352f03f4f475e"
)
DEFAULT_TUNING_RUN_DIR = (
    EXPERIMENT_DIR / "runs" / "exp-006-train-cv-tuning"
)
DEFAULT_TUNING_METADATA = DEFAULT_TUNING_RUN_DIR / "run.json"
DEFAULT_CONFIG_PATH = DEFAULT_TUNING_RUN_DIR / "best_config.json"
DEFAULT_COMPARISON_RUN = (
    EXPERIMENT_DIR
    / "runs"
    / "exp-005-word-char-linear-svm"
    / "run.json"
)
DEFAULT_OUTPUT_DIR = (
    EXPERIMENT_DIR / "runs" / "exp-007-tuned-linear-svm"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the EXP-006-selected LinearSVC configuration and evaluate "
            "once on TweetEval validation. Test is never read."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--tuning-metadata",
        type=Path,
        default=DEFAULT_TUNING_METADATA,
    )
    parser.add_argument(
        "--comparison-run",
        type=Path,
        default=DEFAULT_COMPARISON_RUN,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_frozen_config(config_path: Path, tuning_path: Path) -> dict:
    if not config_path.is_file() or not tuning_path.is_file():
        raise FileNotFoundError(
            f"Missing EXP-006 selection: {config_path}, {tuning_path}"
        )
    actual_hash = sha256(config_path)
    if actual_hash != EXPECTED_CONFIG_SHA256:
        raise ValueError(
            f"Frozen config hash mismatch: {actual_hash} != "
            f"{EXPECTED_CONFIG_SHA256}"
        )
    tuning = json.loads(tuning_path.read_text(encoding="utf-8"))
    if tuning.get("experiment_id") != "EXP-006":
        raise ValueError("Tuning metadata is not EXP-006")
    if tuning.get("accessed_splits") != ["train"]:
        raise ValueError("EXP-006 was not recorded as train-only")
    if tuning.get("validation_split_accessed") is not False:
        raise ValueError("EXP-006 validation exclusion is not recorded")
    if tuning.get("test_split_accessed") is not False:
        raise ValueError("EXP-006 test exclusion is not recorded")
    if (
        tuning["artifacts"]["best_config"]["sha256"]
        != EXPECTED_CONFIG_SHA256
    ):
        raise ValueError("EXP-006 metadata selection hash mismatch")

    selection = json.loads(config_path.read_text(encoding="utf-8"))
    params = selection["params"]
    expected = {
        "C": 0.25,
        "character_ngram_range": [3, 6],
        "class_weight": "balanced",
        "min_df": 2,
        "word_ngram_range": [1, 2],
    }
    if params != expected:
        raise ValueError(f"Unexpected frozen parameters: {params}")
    return {"selection": selection, "tuning": tuning}


def load_comparison(path: Path, data: dict[str, object]) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    comparison = json.loads(path.read_text(encoding="utf-8"))
    if comparison.get("experiment_id") != "EXP-005":
        raise ValueError("Comparison metadata is not EXP-005")
    if comparison.get("test_split_accessed") is not False:
        raise ValueError("EXP-005 test exclusion is not recorded")
    for name, source_path in data["paths"].items():
        if sha256(source_path) != comparison["data"]["files_read"][name][
            "sha256"
        ]:
            raise ValueError(f"EXP-005 data hash mismatch: {name}")
    return comparison


def build_pipeline(config: dict) -> Pipeline:
    features = FeatureUnion(
        transformer_list=[
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    lowercase=True,
                    min_df=config["min_df"],
                    ngram_range=tuple(config["word_ngram_range"]),
                    norm="l2",
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char",
                    lowercase=True,
                    min_df=config["min_df"],
                    ngram_range=tuple(config["character_ngram_range"]),
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
                    C=config["C"],
                    class_weight=config["class_weight"],
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
    axis.set_title("EXP-007 TweetEval Emotion Validation")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    config_path = args.config.resolve()
    tuning_path = args.tuning_metadata.resolve()
    comparison_path = args.comparison_run.resolve()
    output_dir = args.output_dir.resolve()
    prepare_output_dir(output_dir)
    logger = setup_logging(output_dir)

    started_at = datetime.now(timezone.utc)
    total_start = perf_counter()
    logger.info(
        "Starting %s; test split access is prohibited", EXPERIMENT_ID
    )
    frozen = load_frozen_config(config_path, tuning_path)
    config = frozen["selection"]["params"]
    data = load_data(data_dir)
    comparison = load_comparison(comparison_path, data)
    logger.info(
        "Loaded frozen EXP-006 config and %d train/%d validation rows",
        len(data["train_texts"]),
        len(data["validation_texts"]),
    )

    pipeline = build_pipeline(config)
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

    train_predictions = pipeline.predict(data["train_texts"])
    train_accuracy = accuracy_score(
        data["train_labels"], train_predictions
    )
    train_macro_f1 = f1_score(
        data["train_labels"],
        train_predictions,
        average="macro",
        zero_division=0,
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
            f"Model classes {class_ids} do not match {expected_classes}"
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
    train_counts = Counter(data["train_labels"])
    validation_counts = Counter(data["validation_labels"])
    baseline_macro_f1 = comparison["metrics"]["macro"]["f1"]
    baseline_accuracy = comparison["metrics"]["accuracy"]
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
        "selection": {
            "experiment_id": "EXP-006",
            "config_path": relative_to_project(config_path),
            "config_sha256": sha256(config_path),
            "tuning_metadata_path": relative_to_project(tuning_path),
            "tuning_metadata_sha256": sha256(tuning_path),
            "selection_rule": frozen["selection"]["selection_rule"],
            "train_cv_metrics": {
                key: value
                for key, value in frozen["selection"].items()
                if key not in {"params", "selection_rule"}
            },
        },
        "comparison": {
            "experiment_id": "EXP-005",
            "run_metadata": {
                "path": relative_to_project(comparison_path),
                "sha256": sha256(comparison_path),
            },
            "baseline_macro_f1": float(baseline_macro_f1),
            "baseline_accuracy": float(baseline_accuracy),
            "macro_f1_delta": float(macro_f1 - baseline_macro_f1),
            "accuracy_delta": float(accuracy - baseline_accuracy),
            "practical_improvement_threshold": 0.005,
            "primary_rule_passed": bool(
                macro_f1 - baseline_macro_f1 >= 0.005
            ),
        },
        "data": {
            "dataset": "TweetEval emotion",
            "upstream_commit": comparison["data"]["upstream_commit"],
            "train_sample_count": len(data["train_texts"]),
            "validation_sample_count": len(data["validation_texts"]),
            "label_mapping": {
                str(class_id): data["mapping"][class_id]
                for class_id in class_ids
            },
            "train_class_distribution": {
                str(class_id): train_counts.get(class_id, 0)
                for class_id in class_ids
            },
            "validation_class_distribution": {
                str(class_id): validation_counts.get(class_id, 0)
                for class_id in class_ids
            },
            "files_read": {
                name: {
                    "path": relative_to_project(path),
                    "sha256": sha256(path),
                }
                for name, path in data["paths"].items()
            },
        },
        "pipeline": {
            "feature_union": {
                "weights": {"word": 1.0, "character": 1.0},
                "word_tfidf": {
                    "ngram_range": config["word_ngram_range"],
                    "min_df": config["min_df"],
                    "vocabulary_size": word_features,
                },
                "character_tfidf": {
                    "ngram_range": config["character_ngram_range"],
                    "min_df": config["min_df"],
                    "vocabulary_size": character_features,
                },
                "combined_feature_count": word_features
                + character_features,
            },
            "linear_svc": {
                "C": config["C"],
                "class_weight": config["class_weight"],
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
            "train_diagnostic": {
                "accuracy": float(train_accuracy),
                "macro_f1": float(train_macro_f1),
            },
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
        "interpretation_boundary": (
            "Development validation confirmation; the untouched test split "
            "is required for the final generalization estimate."
        ),
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

    logger.info(
        "Train Accuracy %.6f; Train Macro-F1 %.6f",
        train_accuracy,
        train_macro_f1,
    )
    logger.info("Validation Macro-F1 %.6f", macro_f1)
    logger.info("Validation Accuracy %.6f", accuracy)
    logger.info(
        "Delta vs EXP-005: Macro-F1 %+.6f, Accuracy %+.6f",
        macro_f1 - baseline_macro_f1,
        accuracy - baseline_accuracy,
    )
    logger.info("Test split accessed: no")
    logger.info("Artifacts: %s", output_dir)


if __name__ == "__main__":
    main()
