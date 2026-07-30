#!/usr/bin/env python3
"""Fit the frozen TF-IDF + Logistic Regression baseline on TweetEval train."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = (
    PROJECT_DIR
    / "data"
    / "tweeteval-emotion"
    / "official"
    / "datasets"
    / "emotion"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "runs" / "exp-001-train-only"
UPSTREAM_COMMIT = "4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fit TF-IDF + Logistic Regression using only the fixed TweetEval "
            "emotion training split. No validation or test files are read."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing mapping.txt and train_{text,labels}.txt.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="New directory for model.joblib and run.json.",
    )
    parser.add_argument(
        "--class-weight",
        choices=("none", "balanced"),
        default="none",
        help=(
            "Logistic Regression class weighting. Use 'balanced' only for "
            "the registered controlled variant."
        ),
    )
    return parser.parse_args()


def read_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_labels(path: Path) -> list[int]:
    labels = read_text_lines(path)
    try:
        return [int(label.strip()) for label in labels]
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
                f"Invalid label mapping at {path}:{line_number}: {line!r}"
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

    texts = read_text_lines(paths["train_text"])
    labels = read_labels(paths["train_labels"])
    label_mapping = read_label_mapping(paths["mapping"])

    if not texts:
        raise ValueError("Training split is empty.")
    if len(texts) != len(labels):
        raise ValueError(
            f"Training row mismatch: {len(texts)} texts and {len(labels)} labels."
        )
    unknown_labels = sorted(set(labels) - set(label_mapping))
    if unknown_labels:
        raise ValueError(f"Labels missing from mapping.txt: {unknown_labels}")

    return texts, labels, label_mapping, paths


def build_pipeline(class_weight: str | None) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight=class_weight,
                    max_iter=1000,
                    random_state=42,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {output_dir}. "
            "Choose a new --output-dir to preserve the existing run."
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    class_weight = None if args.class_weight == "none" else args.class_weight

    texts, labels, label_mapping, input_paths = load_training_data(data_dir)
    prepare_output_dir(output_dir)

    pipeline = build_pipeline(class_weight)
    started_at = datetime.now(timezone.utc)
    start_time = perf_counter()
    pipeline.fit(texts, labels)
    fit_seconds = perf_counter() - start_time

    model_path = output_dir / "model.joblib"
    metadata_path = output_dir / "run.json"
    joblib.dump(pipeline, model_path)

    tfidf = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["classifier"]
    label_counts = Counter(labels)
    effective_class_weights = {
        str(label_id): (
            len(labels) / (len(label_mapping) * label_counts[label_id])
            if class_weight == "balanced"
            else 1.0
        )
        for label_id in sorted(label_mapping)
    }
    metadata = {
        "experiment_id": output_dir.name,
        "stage": "train-only",
        "created_at_utc": started_at.isoformat(),
        "evaluation_performed": False,
        "data": {
            "dataset": "TweetEval emotion",
            "upstream_commit": UPSTREAM_COMMIT,
            "split": "train",
            "sample_count": len(texts),
            "label_mapping": {
                str(label_id): label_mapping[label_id]
                for label_id in sorted(label_mapping)
            },
            "class_distribution": {
                str(label_id): label_counts.get(label_id, 0)
                for label_id in sorted(label_mapping)
            },
            "files_read": {
                name: {
                    "path": relative_to_project(path),
                    "sha256": sha256(path),
                }
                for name, path in input_paths.items()
            },
        },
        "pipeline": {
            "tfidf": {
                "lowercase": True,
                "ngram_range": [1, 2],
                "min_df": 2,
                "sublinear_tf": True,
                "vocabulary_size": len(tfidf.vocabulary_),
            },
            "logistic_regression": {
                "C": 1.0,
                "class_weight": class_weight,
                "effective_class_weights": effective_class_weights,
                "max_iter": 1000,
                "random_state": 42,
                "solver": "lbfgs",
                "classes": [int(label) for label in classifier.classes_],
                "coefficient_shape": list(classifier.coef_.shape),
                "iterations": [int(value) for value in classifier.n_iter_],
            },
        },
        "runtime": {
            "fit_seconds": round(fit_seconds, 6),
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "artifacts": {
            "model": relative_to_project(model_path),
            "metadata": relative_to_project(metadata_path),
        },
        "invocation": [sys.executable, *sys.argv],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Trained on {len(texts)} examples.")
    print(f"TF-IDF vocabulary size: {len(tfidf.vocabulary_)}.")
    print(f"Class weight: {class_weight}.")
    print(f"Fit time: {fit_seconds:.3f} seconds.")
    print("Validation/test evaluation performed: no.")
    print(f"Model: {model_path}")
    print(f"Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
