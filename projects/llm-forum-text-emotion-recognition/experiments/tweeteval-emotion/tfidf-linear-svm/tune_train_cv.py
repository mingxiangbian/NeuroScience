#!/usr/bin/env python3
"""Run EXP-006 train-only cross-validation hyperparameter tuning."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import warnings

import joblib
import numpy as np
import sklearn
from sklearn.metrics import accuracy_score, f1_score, make_scorer
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from run_experiment import (
    DEFAULT_DATA_DIR,
    EXPERIMENT_DIR,
    PROJECT_DIR,
    build_pipeline,
    git_metadata,
    prepare_output_dir,
    read_label_mapping,
    read_labels,
    read_text_lines,
    relative_to_project,
    setup_logging,
    sha256,
)


EXPERIMENT_ID = "EXP-006"
RQ_ID = "RQ-B1"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "runs" / "exp-006-train-cv-tuning"
DEFAULT_BASELINE_RUN_DIR = (
    EXPERIMENT_DIR / "runs" / "exp-005-word-char-linear-svm"
)
DEFAULT_BASELINE_MODEL = DEFAULT_BASELINE_RUN_DIR / "model.joblib"
DEFAULT_BASELINE_METADATA = DEFAULT_BASELINE_RUN_DIR / "run.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Tune LinearSVC regularization and character n-grams using only "
            "TweetEval emotion train folds. Validation and test are not read."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--baseline-model", type=Path, default=DEFAULT_BASELINE_MODEL
    )
    parser.add_argument(
        "--baseline-metadata", type=Path, default=DEFAULT_BASELINE_METADATA
    )
    return parser.parse_args()


def load_training_data(
    data_dir: Path,
) -> tuple[list[str], list[int], dict[int, str], dict[str, Path]]:
    paths = {
        "mapping": data_dir / "mapping.txt",
        "train_text": data_dir / "train_text.txt",
        "train_labels": data_dir / "train_labels.txt",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required training files: {missing}")

    mapping = read_label_mapping(paths["mapping"])
    texts = read_text_lines(paths["train_text"])
    labels = read_labels(paths["train_labels"])
    if not texts or len(texts) != len(labels):
        raise ValueError(
            f"Invalid training rows: {len(texts)} texts, {len(labels)} labels"
        )
    unknown = sorted(set(labels) - set(mapping))
    if unknown:
        raise ValueError(f"Training labels missing from mapping: {unknown}")
    return texts, labels, mapping, paths


def load_baseline(
    model_path: Path,
    metadata_path: Path,
    training_paths: dict[str, Path],
) -> tuple[object, dict]:
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(
            f"Missing EXP-005 artifacts: {model_path}, {metadata_path}"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("experiment_id") != "EXP-005":
        raise ValueError("Baseline metadata is not EXP-005")
    if sha256(model_path) != metadata["artifacts"]["model"]["sha256"]:
        raise ValueError("EXP-005 model hash mismatch")
    for name, path in training_paths.items():
        recorded = metadata["data"]["files_read"][name]["sha256"]
        if sha256(path) != recorded:
            raise ValueError(f"EXP-005 input hash mismatch: {name}")
    return joblib.load(model_path), metadata


def serializable_params(params: dict[str, object]) -> dict[str, object]:
    return {
        "C": float(params["classifier__C"]),
        "class_weight": params["classifier__class_weight"],
        "character_ngram_range": list(
            params["features__character__ngram_range"]
        ),
        "word_ngram_range": [1, 2],
        "min_df": 2,
    }


def save_cv_results(path: Path, results: dict[str, object]) -> None:
    fieldnames = [
        "rank_macro_f1",
        "mean_train_macro_f1",
        "std_train_macro_f1",
        "mean_cv_macro_f1",
        "std_cv_macro_f1",
        "mean_train_accuracy",
        "std_train_accuracy",
        "mean_cv_accuracy",
        "std_cv_accuracy",
        "mean_fit_seconds",
        "std_fit_seconds",
        "params_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, params in enumerate(results["params"]):
            writer.writerow(
                {
                    "rank_macro_f1": int(
                        results["rank_test_macro_f1"][index]
                    ),
                    "mean_train_macro_f1": (
                        f"{results['mean_train_macro_f1'][index]:.12f}"
                    ),
                    "std_train_macro_f1": (
                        f"{results['std_train_macro_f1'][index]:.12f}"
                    ),
                    "mean_cv_macro_f1": (
                        f"{results['mean_test_macro_f1'][index]:.12f}"
                    ),
                    "std_cv_macro_f1": (
                        f"{results['std_test_macro_f1'][index]:.12f}"
                    ),
                    "mean_train_accuracy": (
                        f"{results['mean_train_accuracy'][index]:.12f}"
                    ),
                    "std_train_accuracy": (
                        f"{results['std_train_accuracy'][index]:.12f}"
                    ),
                    "mean_cv_accuracy": (
                        f"{results['mean_test_accuracy'][index]:.12f}"
                    ),
                    "std_cv_accuracy": (
                        f"{results['std_test_accuracy'][index]:.12f}"
                    ),
                    "mean_fit_seconds": (
                        f"{results['mean_fit_time'][index]:.6f}"
                    ),
                    "std_fit_seconds": (
                        f"{results['std_fit_time'][index]:.6f}"
                    ),
                    "params_json": json.dumps(
                        serializable_params(params), sort_keys=True
                    ),
                }
            )


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    baseline_model_path = args.baseline_model.resolve()
    baseline_metadata_path = args.baseline_metadata.resolve()
    prepare_output_dir(output_dir)
    logger = setup_logging(output_dir)

    started_at = datetime.now(timezone.utc)
    logger.info(
        "Starting %s train-only CV; validation/test access is prohibited",
        EXPERIMENT_ID,
    )
    texts, labels, mapping, input_paths = load_training_data(data_dir)
    baseline_model, baseline_metadata = load_baseline(
        baseline_model_path,
        baseline_metadata_path,
        input_paths,
    )

    baseline_predictions = baseline_model.predict(texts)
    baseline_train_accuracy = accuracy_score(labels, baseline_predictions)
    baseline_train_macro_f1 = f1_score(
        labels, baseline_predictions, average="macro", zero_division=0
    )
    logger.info(
        "EXP-005 full-train diagnostics: Accuracy %.6f, Macro-F1 %.6f",
        baseline_train_accuracy,
        baseline_train_macro_f1,
    )

    cross_validation = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )
    parameter_grid = {
        "classifier__C": [0.05, 0.1, 0.25, 0.5, 1.0],
        "classifier__class_weight": [None, "balanced"],
        "features__character__ngram_range": [
            (3, 5),
            (2, 5),
            (3, 6),
        ],
    }
    scoring = {
        "macro_f1": make_scorer(
            f1_score,
            average="macro",
            zero_division=0,
        ),
        "accuracy": "accuracy",
    }
    search = GridSearchCV(
        estimator=build_pipeline(),
        param_grid=parameter_grid,
        scoring=scoring,
        cv=cross_validation,
        refit=False,
        n_jobs=1,
        return_train_score=True,
        error_score="raise",
    )

    search_start = perf_counter()
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        search.fit(texts, labels)
    search_seconds = perf_counter() - search_start

    results = search.cv_results_
    best_index = int(np.nanargmax(results["mean_test_macro_f1"]))
    best_params = serializable_params(results["params"][best_index])
    best_summary = {
        "selection_rule": "maximum mean 5-fold train-CV Macro-F1",
        "params": best_params,
        "mean_train_macro_f1": float(
            results["mean_train_macro_f1"][best_index]
        ),
        "std_train_macro_f1": float(
            results["std_train_macro_f1"][best_index]
        ),
        "mean_cv_macro_f1": float(
            results["mean_test_macro_f1"][best_index]
        ),
        "std_cv_macro_f1": float(
            results["std_test_macro_f1"][best_index]
        ),
        "mean_train_accuracy": float(
            results["mean_train_accuracy"][best_index]
        ),
        "std_train_accuracy": float(
            results["std_train_accuracy"][best_index]
        ),
        "mean_cv_accuracy": float(
            results["mean_test_accuracy"][best_index]
        ),
        "std_cv_accuracy": float(
            results["std_test_accuracy"][best_index]
        ),
        "rank_macro_f1": int(
            results["rank_test_macro_f1"][best_index]
        ),
    }

    cv_results_path = output_dir / "cv_results.csv"
    best_config_path = output_dir / "best_config.json"
    metadata_path = output_dir / "run.json"
    save_cv_results(cv_results_path, results)
    best_config_path.write_text(
        json.dumps(best_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    label_counts = Counter(labels)
    metadata = {
        "experiment_id": EXPERIMENT_ID,
        "tier": "Minor",
        "rq_id": RQ_ID,
        "stage": "train-only-cross-validation",
        "status": "Completed",
        "created_at_utc": started_at.isoformat(),
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "question": (
            "Can stronger regularization, class weighting, or a different "
            "character n-gram range reduce EXP-005 overfitting?"
        ),
        "baseline_diagnostic": {
            "experiment_id": "EXP-005",
            "model_path": relative_to_project(baseline_model_path),
            "model_sha256": sha256(baseline_model_path),
            "metadata_path": relative_to_project(
                baseline_metadata_path
            ),
            "metadata_sha256": sha256(baseline_metadata_path),
            "full_train_accuracy": float(baseline_train_accuracy),
            "full_train_macro_f1": float(baseline_train_macro_f1),
            "validation_accuracy": float(
                baseline_metadata["metrics"]["accuracy"]
            ),
            "validation_macro_f1": float(
                baseline_metadata["metrics"]["macro"]["f1"]
            ),
        },
        "data": {
            "dataset": "TweetEval emotion",
            "upstream_commit": baseline_metadata["data"][
                "upstream_commit"
            ],
            "split": "train",
            "sample_count": len(texts),
            "label_mapping": {
                str(label_id): mapping[label_id]
                for label_id in sorted(mapping)
            },
            "class_distribution": {
                str(label_id): label_counts.get(label_id, 0)
                for label_id in sorted(mapping)
            },
            "files_read": {
                name: {
                    "path": relative_to_project(path),
                    "sha256": sha256(path),
                }
                for name, path in input_paths.items()
            },
        },
        "search": {
            "folds": 5,
            "splitter": "StratifiedKFold",
            "shuffle": True,
            "random_state": 42,
            "primary_metric": "macro_f1",
            "secondary_metric": "accuracy",
            "candidate_count": len(results["params"]),
            "total_cv_fits": len(results["params"]) * 5,
            "parameter_grid": {
                "C": parameter_grid["classifier__C"],
                "class_weight": parameter_grid[
                    "classifier__class_weight"
                ],
                "character_ngram_range": [
                    list(value)
                    for value in parameter_grid[
                        "features__character__ngram_range"
                    ]
                ],
                "fixed_word_ngram_range": [1, 2],
                "fixed_min_df": 2,
            },
            "best": best_summary,
        },
        "resource_budget": {
            "search_runs": 1,
            "candidate_count": 30,
            "total_cv_fits": 150,
            "wall_time_minutes": 5,
            "api_cost_usd": 0,
        },
        "runtime": {
            "search_seconds": round(search_seconds, 6),
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
            "cv_results": {
                "path": relative_to_project(cv_results_path),
                "sha256": sha256(cv_results_path),
            },
            "best_config": {
                "path": relative_to_project(best_config_path),
                "sha256": sha256(best_config_path),
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
        "Completed %d candidates and %d fits in %.3f seconds",
        len(results["params"]),
        len(results["params"]) * 5,
        search_seconds,
    )
    logger.info("Best config: %s", json.dumps(best_params, sort_keys=True))
    logger.info(
        "Best CV Macro-F1 %.6f +/- %.6f; Accuracy %.6f +/- %.6f",
        best_summary["mean_cv_macro_f1"],
        best_summary["std_cv_macro_f1"],
        best_summary["mean_cv_accuracy"],
        best_summary["std_cv_accuracy"],
    )
    logger.info("Validation/test split accessed: no")
    logger.info("Artifacts: %s", output_dir)


if __name__ == "__main__":
    main()
