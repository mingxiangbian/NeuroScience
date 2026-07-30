#!/usr/bin/env python3
"""Evaluate EXP-001 on the fixed TweetEval emotion validation split."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
from time import perf_counter

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "erc-matplotlib-cache")
)

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import sklearn
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from train import (
    DEFAULT_DATA_DIR,
    PROJECT_DIR,
    prepare_output_dir,
    read_label_mapping,
    read_labels,
    read_text_lines,
    relative_to_project,
    sha256,
)


EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_TRAIN_RUN_DIR = EXPERIMENT_DIR / "runs" / "exp-001-train-only"
DEFAULT_MODEL_PATH = DEFAULT_TRAIN_RUN_DIR / "model.joblib"
DEFAULT_TRAIN_METADATA_PATH = DEFAULT_TRAIN_RUN_DIR / "run.json"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "runs" / "exp-002-validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the saved TF-IDF + Logistic Regression pipeline using "
            "only the fixed TweetEval emotion validation split. Test files "
            "are not read."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing mapping.txt and val_{text,labels}.txt.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Fitted EXP-001 model.joblib.",
    )
    parser.add_argument(
        "--train-metadata",
        type=Path,
        default=DEFAULT_TRAIN_METADATA_PATH,
        help="EXP-001 run.json used to verify model provenance.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="New directory for validation artifacts.",
    )
    return parser.parse_args()


def load_train_metadata(path: Path, model_path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing training metadata: {path}")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("stage") != "train-only":
        raise ValueError(f"Unexpected parent stage in {path}")
    if metadata.get("evaluation_performed") is not False:
        raise ValueError(f"Parent run is not marked train-only: {path}")

    recorded_model = metadata.get("artifacts", {}).get("model")
    if not recorded_model:
        raise ValueError(f"Parent metadata does not record a model path: {path}")
    expected_model_path = (PROJECT_DIR / recorded_model).resolve()
    if model_path.resolve() != expected_model_path:
        raise ValueError(
            f"Model path does not match parent metadata: "
            f"{model_path.resolve()} != {expected_model_path}"
        )
    return metadata


def load_validation_data(
    data_dir: Path,
) -> tuple[list[str], list[int], dict[int, str], dict[str, Path]]:
    paths = {
        "mapping": data_dir / "mapping.txt",
        "validation_text": data_dir / "val_text.txt",
        "validation_labels": data_dir / "val_labels.txt",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required validation files: {missing}")

    texts = read_text_lines(paths["validation_text"])
    labels = read_labels(paths["validation_labels"])
    label_mapping = read_label_mapping(paths["mapping"])

    if not texts:
        raise ValueError("Validation split is empty.")
    if len(texts) != len(labels):
        raise ValueError(
            f"Validation row mismatch: {len(texts)} texts and "
            f"{len(labels)} labels."
        )
    unknown_labels = sorted(set(labels) - set(label_mapping))
    if unknown_labels:
        raise ValueError(f"Labels missing from mapping.txt: {unknown_labels}")

    return texts, labels, label_mapping, paths


def save_predictions(
    path: Path,
    gold_labels: list[int],
    predictions,
    probabilities,
    class_ids: list[int],
    label_mapping: dict[int, str],
) -> None:
    probability_headers = [
        f"probability_{label_mapping[class_id]}" for class_id in class_ids
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row_number",
                "gold_label_id",
                "gold_label",
                "predicted_label_id",
                "predicted_label",
                *probability_headers,
            ]
        )
        for row_number, (gold, predicted, row_probabilities) in enumerate(
            zip(gold_labels, predictions, probabilities, strict=True),
            start=1,
        ):
            writer.writerow(
                [
                    row_number,
                    gold,
                    label_mapping[gold],
                    int(predicted),
                    label_mapping[int(predicted)],
                    *[f"{float(value):.12f}" for value in row_probabilities],
                ]
            )


def save_confusion_matrix_csv(
    path: Path,
    matrix,
    class_ids: list[int],
    label_mapping: dict[int, str],
) -> None:
    label_names = [label_mapping[class_id] for class_id in class_ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true_label/predicted_label", *label_names])
        for label_name, row in zip(label_names, matrix, strict=True):
            writer.writerow([label_name, *[int(value) for value in row]])


def save_confusion_matrix_figure(
    path: Path,
    matrix,
    class_ids: list[int],
    label_mapping: dict[int, str],
) -> None:
    label_names = [label_mapping[class_id] for class_id in class_ids]
    figure, axis = plt.subplots(figsize=(7, 6))
    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=label_names,
    )
    display.plot(
        ax=axis,
        cmap="Blues",
        colorbar=False,
        values_format="d",
    )
    axis.set_title("TweetEval Emotion Validation Confusion Matrix")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    model_path = args.model.resolve()
    train_metadata_path = args.train_metadata.resolve()
    output_dir = args.output_dir.resolve()

    if not model_path.is_file():
        raise FileNotFoundError(f"Missing trained model: {model_path}")
    parent_metadata = load_train_metadata(train_metadata_path, model_path)
    texts, gold_labels, label_mapping, input_paths = load_validation_data(data_dir)
    prepare_output_dir(output_dir)

    pipeline = joblib.load(model_path)
    classifier = pipeline.named_steps.get("classifier")
    if classifier is None or not hasattr(pipeline, "predict_proba"):
        raise ValueError("Saved artifact is not the expected probabilistic pipeline.")

    class_ids = [int(label) for label in classifier.classes_]
    expected_class_ids = sorted(label_mapping)
    if class_ids != expected_class_ids:
        raise ValueError(
            f"Model classes {class_ids} do not match mapping {expected_class_ids}."
        )

    started_at = datetime.now(timezone.utc)
    start_time = perf_counter()
    predictions = pipeline.predict(texts)
    probabilities = pipeline.predict_proba(texts)

    accuracy = accuracy_score(gold_labels, predictions)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            gold_labels,
            predictions,
            labels=class_ids,
            average="macro",
            zero_division=0,
        )
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            gold_labels,
            predictions,
            labels=class_ids,
            average="weighted",
            zero_division=0,
        )
    )
    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            gold_labels,
            predictions,
            labels=class_ids,
            average=None,
            zero_division=0,
        )
    )
    matrix = confusion_matrix(gold_labels, predictions, labels=class_ids)
    evaluation_seconds = perf_counter() - start_time

    predictions_path = output_dir / "predictions.csv"
    matrix_csv_path = output_dir / "confusion_matrix.csv"
    matrix_png_path = output_dir / "confusion_matrix.png"
    metadata_path = output_dir / "run.json"

    save_predictions(
        predictions_path,
        gold_labels,
        predictions,
        probabilities,
        class_ids,
        label_mapping,
    )
    save_confusion_matrix_csv(
        matrix_csv_path,
        matrix,
        class_ids,
        label_mapping,
    )
    save_confusion_matrix_figure(
        matrix_png_path,
        matrix,
        class_ids,
        label_mapping,
    )

    per_class = {
        label_mapping[class_id]: {
            "label_id": class_id,
            "precision": float(class_precision[index]),
            "recall": float(class_recall[index]),
            "f1": float(class_f1[index]),
            "support": int(class_support[index]),
        }
        for index, class_id in enumerate(class_ids)
    }
    metadata = {
        "experiment_id": output_dir.name,
        "parent_experiment_id": parent_metadata["experiment_id"],
        "stage": "validation",
        "created_at_utc": started_at.isoformat(),
        "test_split_accessed": False,
        "data": {
            "dataset": "TweetEval emotion",
            "upstream_commit": parent_metadata["data"]["upstream_commit"],
            "split": "validation",
            "sample_count": len(texts),
            "label_mapping": {
                str(class_id): label_mapping[class_id] for class_id in class_ids
            },
            "files_read": {
                name: {
                    "path": relative_to_project(path),
                    "sha256": sha256(path),
                }
                for name, path in input_paths.items()
            },
        },
        "model": {
            "path": relative_to_project(model_path),
            "sha256": sha256(model_path),
            "train_metadata_path": relative_to_project(train_metadata_path),
            "train_metadata_sha256": sha256(train_metadata_path),
        },
        "metrics": {
            "primary": {
                "name": "macro_f1",
                "value": float(macro_f1),
            },
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
                "labels": [label_mapping[class_id] for class_id in class_ids],
                "values": [
                    [int(value) for value in row]
                    for row in matrix
                ],
            },
        },
        "runtime": {
            "evaluation_seconds": round(evaluation_seconds, 6),
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "artifacts": {
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
            "metadata": {
                "path": relative_to_project(metadata_path),
            },
        },
        "invocation": [sys.executable, *sys.argv],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Evaluated {len(texts)} validation examples.")
    print(f"Macro-F1: {macro_f1:.6f}")
    print(f"Accuracy: {accuracy:.6f}")
    print("Test split accessed: no.")
    print(f"Artifacts: {output_dir}")


if __name__ == "__main__":
    main()
