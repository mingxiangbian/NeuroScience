#!/usr/bin/env python3
"""Evaluate the EXP-016 preregistered frozen models on TweetEval test once."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter
import traceback
from typing import Any, TextIO

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import joblib
import numpy as np
import sklearn
import torch
import torch.nn.functional as functional
import transformers
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-016-frozen-test.json"


class Tee:
    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, value: str) -> int:
        for stream in self.streams:
            stream.write(value)
            stream.flush()
        return len(value)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return any(
            bool(getattr(stream, "isatty", lambda: False)())
            for stream in self.streams
        )

    @property
    def encoding(self) -> str:
        return getattr(self.streams[0], "encoding", None) or "utf-8"

    def fileno(self) -> int:
        return self.streams[0].fileno()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Verify the frozen gate without producing test predictions.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"{utc_now()} {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT != path and PROJECT_ROOT not in path.parents:
        raise ValueError(f"Path escapes project root: {path}")
    return path


def relative_to_project(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def verify_artifact(artifact: dict[str, str]) -> Path:
    path = project_path(artifact["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = sha256(path)
    if actual_hash != artifact["sha256"]:
        raise ValueError(
            f"Artifact hash mismatch: {path}: "
            f"{actual_hash} != {artifact['sha256']}"
        )
    return path


def read_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_mapping(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line in read_lines(path):
        label_id, label = line.split("\t", maxsplit=1)
        mapping[int(label_id)] = label
    return mapping


def load_config(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    config = read_json(path)
    if config.get("experiment_id") != "EXP-016":
        raise ValueError("Only the frozen EXP-016 config is accepted")
    if config.get("tier") != "Major":
        raise ValueError("EXP-016 must remain a Major experiment")
    if not config.get("authorization", {}).get("approved"):
        raise ValueError("Test access has not been authorized")
    if config["test_policy"] != {
        "allow_checkpoint_selection": False,
        "allow_ensemble": False,
        "allow_post_result_tuning": False,
        "evaluate_every_listed_model_once": True,
    }:
        raise ValueError("Frozen test policy changed")
    condition_ids = [item["id"] for item in config["conditions"]]
    expected_ids = [
        "exp-007-linear-svm",
        "exp-011-generic-roberta",
        "exp-014-generic-roberta-label-smoothing",
        "exp-015-twitter-roberta-label-smoothing",
    ]
    if condition_ids != expected_ids:
        raise ValueError(f"Frozen condition list changed: {condition_ids}")
    return config, sha256(path)


def verify_source_condition(condition: dict[str, Any]) -> dict[str, Any]:
    source_run_path = verify_artifact(condition["source_run"])
    source_run = read_json(source_run_path)
    expected_id = condition["source_experiment_id"]
    if source_run.get("experiment_id") != expected_id:
        raise ValueError(f"Source run mismatch for {condition['id']}")
    if source_run.get("test_split_accessed") is not False:
        raise ValueError(f"Source run already accessed test: {expected_id}")

    verification_path = verify_artifact(condition["source_verification"])
    verification = read_json(verification_path)
    if verification.get("experiment_id") != expected_id:
        raise ValueError(f"Verification mismatch for {condition['id']}")
    if verification.get("test_split_accessed") is not False:
        raise ValueError(f"Source verification accessed test: {expected_id}")

    checked = {
        "source_run": condition["source_run"],
        "source_verification": condition["source_verification"],
    }
    if condition["type"] == "sklearn_joblib":
        verify_artifact(condition["model"])
        checked["model"] = condition["model"]
        return checked

    expected_seeds = [42, 43, 44]
    actual_seeds = [item["seed"] for item in condition["checkpoints"]]
    if actual_seeds != expected_seeds:
        raise ValueError(
            f"Checkpoint seeds changed for {condition['id']}: {actual_seeds}"
        )
    for checkpoint in condition["checkpoints"]:
        model_path = verify_artifact(checkpoint["model"])
        metrics_path = verify_artifact(checkpoint["metrics"])
        metrics = read_json(metrics_path)
        if metrics.get("seed") != checkpoint["seed"]:
            raise ValueError(f"Seed metadata mismatch: {metrics_path}")
        selected = metrics["best_checkpoint"]["model_file"]
        if selected != checkpoint["model"]:
            raise ValueError(f"Selected checkpoint changed: {model_path}")
        checkpoint_dir = model_path.parent
        for required_name in ("config.json", "model.safetensors"):
            if not (checkpoint_dir / required_name).is_file():
                raise FileNotFoundError(checkpoint_dir / required_name)

    tokenizer_path = project_path(condition["tokenizer_snapshot"])
    if not tokenizer_path.is_dir():
        raise FileNotFoundError(tokenizer_path)
    checked["checkpoint_count"] = len(condition["checkpoints"])
    checked["tokenizer_snapshot"] = relative_to_project(tokenizer_path)
    return checked


def load_test_data(config: dict[str, Any]) -> dict[str, Any]:
    files = config["data"]["files"]
    paths = {name: verify_artifact(item) for name, item in files.items()}
    mapping = read_mapping(paths["mapping"])
    expected_mapping = {
        int(label_id): label
        for label_id, label in config["data"]["label_mapping"].items()
    }
    if mapping != expected_mapping:
        raise ValueError(f"Label mapping changed: {mapping}")
    texts = read_lines(paths["test_text"])
    labels = [int(value) for value in read_lines(paths["test_labels"])]
    expected_count = int(config["data"]["test_sample_count"])
    if len(texts) != expected_count or len(labels) != expected_count:
        raise ValueError(
            f"Test row count mismatch: {len(texts)}, {len(labels)}"
        )
    if sorted(set(labels)) != sorted(mapping):
        raise ValueError(f"Unexpected labels: {sorted(set(labels))}")
    return {
        "labels": labels,
        "mapping": mapping,
        "paths": paths,
        "row_ids": list(range(expected_count)),
        "texts": texts,
    }


def git_metadata() -> dict[str, Any]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        status = run_git("status", "--porcelain")
        return {
            "branch": run_git("branch", "--show-current") or "detached",
            "commit": run_git("rev-parse", "HEAD"),
            "dirty": bool(status),
            "dirty_path_count": len(status.splitlines()) if status else 0,
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return {"error": str(error)}


def environment_metadata() -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise RuntimeError("PYTHONNOUSERSITE=1 is required")
    if os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 is required")
    if not torch.backends.mps.is_built():
        raise RuntimeError("PyTorch was not built with MPS support")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable in this process")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PIP_USER": "0", "PYTHONNOUSERSITE": "1"},
    )
    return {
        "architecture": platform.machine(),
        "device": "mps",
        "executable": sys.executable,
        "git": git_metadata(),
        "packages": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "pip_check": pip_check.stdout.strip(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def detailed_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    mapping: dict[int, str],
) -> tuple[dict[str, Any], np.ndarray]:
    label_ids = sorted(mapping)
    macro = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average="macro",
        zero_division=0,
    )
    weighted = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average="weighted",
        zero_division=0,
    )
    per_class = precision_recall_fscore_support(
        labels,
        predictions,
        labels=label_ids,
        average=None,
        zero_division=0,
    )
    matrix = confusion_matrix(labels, predictions, labels=label_ids)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro": {
            "f1": float(macro[2]),
            "precision": float(macro[0]),
            "recall": float(macro[1]),
        },
        "per_class": {
            mapping[label_id]: {
                "f1": float(per_class[2][index]),
                "label_id": label_id,
                "precision": float(per_class[0][index]),
                "recall": float(per_class[1][index]),
                "support": int(per_class[3][index]),
            }
            for index, label_id in enumerate(label_ids)
        },
        "weighted": {
            "f1": float(weighted[2]),
            "precision": float(weighted[0]),
            "recall": float(weighted[1]),
        },
    }, matrix


def save_predictions(
    path: Path,
    row_ids: list[int],
    labels: np.ndarray,
    predictions: np.ndarray,
    scores: np.ndarray,
    mapping: dict[int, str],
    score_prefix: str,
) -> None:
    label_ids = sorted(mapping)
    score_fields = [
        f"{score_prefix}_{mapping[label_id]}" for label_id in label_ids
    ]
    fieldnames = [
        "row_id",
        "gold_id",
        "gold_label",
        "prediction_id",
        "prediction_label",
        *score_fields,
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, row_id in enumerate(row_ids):
            gold_id = int(labels[index])
            prediction_id = int(predictions[index])
            row: dict[str, Any] = {
                "row_id": row_id,
                "gold_id": gold_id,
                "gold_label": mapping[gold_id],
                "prediction_id": prediction_id,
                "prediction_label": mapping[prediction_id],
            }
            for score_index, field in enumerate(score_fields):
                row[field] = f"{float(scores[index, score_index]):.12f}"
            writer.writerow(row)


def save_confusion_matrix(
    path: Path,
    matrix: np.ndarray,
    mapping: dict[int, str],
) -> None:
    labels = [mapping[label_id] for label_id in sorted(mapping)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\predicted", *labels])
        for label, values in zip(labels, matrix, strict=True):
            writer.writerow([label, *[int(value) for value in values]])


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": relative_to_project(path),
        "sha256": sha256(path),
    }


def evaluate_svm(
    condition: dict[str, Any],
    data: dict[str, Any],
    condition_dir: Path,
) -> dict[str, Any]:
    condition_dir.mkdir(parents=True)
    model_path = verify_artifact(condition["model"])
    model = joblib.load(model_path)
    classes = [int(value) for value in model.classes_]
    if classes != sorted(data["mapping"]):
        raise ValueError(f"SVM class order changed: {classes}")
    started = perf_counter()
    predictions = np.asarray(model.predict(data["texts"]))
    decision_scores = np.asarray(model.decision_function(data["texts"]))
    inference_seconds = perf_counter() - started
    labels = np.asarray(data["labels"])
    metrics, matrix = detailed_metrics(
        labels,
        predictions,
        data["mapping"],
    )
    predictions_path = condition_dir / "predictions.csv"
    confusion_path = condition_dir / "confusion_matrix.csv"
    save_predictions(
        predictions_path,
        data["row_ids"],
        labels,
        predictions,
        decision_scores,
        data["mapping"],
        "decision",
    )
    save_confusion_matrix(confusion_path, matrix, data["mapping"])
    result = {
        "condition_id": condition["id"],
        "inference_seconds": inference_seconds,
        "metrics": metrics,
        "model": condition["model"],
        "score_type": "LinearSVC decision function",
        "seed": None,
        "source_experiment_id": condition["source_experiment_id"],
    }
    metrics_path = condition_dir / "metrics.json"
    write_json(metrics_path, result)
    result["artifacts"] = {
        "confusion_matrix": artifact(confusion_path),
        "metrics": artifact(metrics_path),
        "predictions": artifact(predictions_path),
    }
    return result


def tokenize_test(
    condition: dict[str, Any],
    texts: list[str],
) -> tuple[Any, dict[str, torch.Tensor]]:
    tokenizer_path = project_path(condition["tokenizer_snapshot"])
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path,
        local_files_only=True,
    )
    encoded = tokenizer(
        texts,
        add_special_tokens=True,
        max_length=int(condition["max_length"]),
        padding=True,
        return_tensors="pt",
        truncation=True,
    )
    return tokenizer, encoded


def transformer_inference(
    checkpoint_path: Path,
    encoded: dict[str, torch.Tensor],
    labels: np.ndarray,
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    device = torch.device("mps")
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint_path.parent,
        local_files_only=True,
    )
    model.to(device)
    model.eval()
    logits_parts = []
    started = perf_counter()
    with torch.inference_mode():
        for start in range(0, len(labels), batch_size):
            end = min(start + batch_size, len(labels))
            batch = {
                key: value[start:end].to(device)
                for key, value in encoded.items()
            }
            outputs = model(**batch)
            logits_parts.append(outputs.logits.detach().cpu())
    inference_seconds = perf_counter() - started
    logits = torch.cat(logits_parts, dim=0)
    probabilities = torch.softmax(logits, dim=1).numpy()
    predictions = np.argmax(probabilities, axis=1)
    del model
    gc.collect()
    torch.mps.empty_cache()
    return predictions, probabilities, inference_seconds


def evaluate_transformer_condition(
    condition: dict[str, Any],
    data: dict[str, Any],
    condition_dir: Path,
) -> list[dict[str, Any]]:
    condition_dir.mkdir(parents=True)
    tokenizer, encoded = tokenize_test(condition, data["texts"])
    del tokenizer
    labels = np.asarray(data["labels"])
    results = []
    for checkpoint in condition["checkpoints"]:
        seed = int(checkpoint["seed"])
        log(f"Evaluating {condition['id']} seed {seed}")
        checkpoint_path = verify_artifact(checkpoint["model"])
        seed_dir = condition_dir / f"seed-{seed}"
        seed_dir.mkdir()
        predictions, probabilities, inference_seconds = (
            transformer_inference(
                checkpoint_path,
                encoded,
                labels,
                int(condition["batch_size"]),
            )
        )
        metrics, matrix = detailed_metrics(
            labels,
            predictions,
            data["mapping"],
        )
        predictions_path = seed_dir / "predictions.csv"
        confusion_path = seed_dir / "confusion_matrix.csv"
        save_predictions(
            predictions_path,
            data["row_ids"],
            labels,
            predictions,
            probabilities,
            data["mapping"],
            "prob",
        )
        save_confusion_matrix(confusion_path, matrix, data["mapping"])
        result = {
            "checkpoint": checkpoint["model"],
            "condition_id": condition["id"],
            "inference_seconds": inference_seconds,
            "metrics": metrics,
            "score_type": "softmax probability",
            "seed": seed,
            "source_experiment_id": condition["source_experiment_id"],
            "validation_metrics": checkpoint["metrics"],
        }
        metrics_path = seed_dir / "metrics.json"
        write_json(metrics_path, result)
        result["artifacts"] = {
            "confusion_matrix": artifact(confusion_path),
            "metrics": artifact(metrics_path),
            "predictions": artifact(predictions_path),
        }
        results.append(result)
        log(
            f"Completed {condition['id']} seed {seed}: "
            f"test Macro-F1={metrics['macro']['f1']:.6f}"
        )
    del encoded
    gc.collect()
    torch.mps.empty_cache()
    return results


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": (
            float(statistics.stdev(values)) if len(values) > 1 else 0.0
        ),
        "values": [float(value) for value in values],
    }


def aggregate_results(
    condition: dict[str, Any],
    results: list[dict[str, Any]],
    mapping: dict[int, str],
) -> dict[str, Any]:
    if condition["type"] == "sklearn_joblib":
        metrics = results[0]["metrics"]
        return {
            "accuracy": summarize([metrics["accuracy"]]),
            "macro_f1": summarize([metrics["macro"]["f1"]]),
            "macro_precision": summarize([metrics["macro"]["precision"]]),
            "macro_recall": summarize([metrics["macro"]["recall"]]),
            "per_class": {
                label: {
                    metric: summarize(
                        [metrics["per_class"][label][metric]]
                    )
                    for metric in ("precision", "recall", "f1")
                }
                for label in mapping.values()
            },
            "weighted_f1": summarize([metrics["weighted"]["f1"]]),
        }
    return {
        "accuracy": summarize(
            [result["metrics"]["accuracy"] for result in results]
        ),
        "macro_f1": summarize(
            [result["metrics"]["macro"]["f1"] for result in results]
        ),
        "macro_precision": summarize(
            [result["metrics"]["macro"]["precision"] for result in results]
        ),
        "macro_recall": summarize(
            [result["metrics"]["macro"]["recall"] for result in results]
        ),
        "per_class": {
            label: {
                metric: summarize(
                    [
                        result["metrics"]["per_class"][label][metric]
                        for result in results
                    ]
                )
                for metric in ("precision", "recall", "f1")
            }
            for label in mapping.values()
        },
        "weighted_f1": summarize(
            [result["metrics"]["weighted"]["f1"] for result in results]
        ),
    }


def paired_comparison(
    newer: list[dict[str, Any]],
    older: list[dict[str, Any]],
) -> dict[str, Any]:
    newer_by_seed = {int(item["seed"]): item for item in newer}
    older_by_seed = {int(item["seed"]): item for item in older}
    if sorted(newer_by_seed) != [42, 43, 44]:
        raise ValueError("Newer condition seed set changed")
    if sorted(older_by_seed) != [42, 43, 44]:
        raise ValueError("Older condition seed set changed")
    differences = [
        newer_by_seed[seed]["metrics"]["macro"]["f1"]
        - older_by_seed[seed]["metrics"]["macro"]["f1"]
        for seed in (42, 43, 44)
    ]
    return {
        "macro_f1_difference": summarize(differences),
        "positive_seed_count": sum(value > 0 for value in differences),
        "seed_differences": {
            str(seed): float(value)
            for seed, value in zip((42, 43, 44), differences, strict=True)
        },
    }


def write_result_tables(
    output_dir: Path,
    conditions: list[dict[str, Any]],
    all_results: dict[str, list[dict[str, Any]]],
    aggregates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary_path = output_dir / "condition_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "condition_id",
                "source_experiment_id",
                "test_macro_f1_mean",
                "test_macro_f1_sample_std",
                "test_accuracy_mean",
                "test_accuracy_sample_std",
                "test_weighted_f1_mean",
                "test_weighted_f1_sample_std",
                "run_count",
            ],
        )
        writer.writeheader()
        for condition in conditions:
            aggregate = aggregates[condition["id"]]
            writer.writerow(
                {
                    "condition_id": condition["id"],
                    "source_experiment_id": condition[
                        "source_experiment_id"
                    ],
                    "test_macro_f1_mean": (
                        f"{aggregate['macro_f1']['mean']:.12f}"
                    ),
                    "test_macro_f1_sample_std": (
                        f"{aggregate['macro_f1']['sample_std']:.12f}"
                    ),
                    "test_accuracy_mean": (
                        f"{aggregate['accuracy']['mean']:.12f}"
                    ),
                    "test_accuracy_sample_std": (
                        f"{aggregate['accuracy']['sample_std']:.12f}"
                    ),
                    "test_weighted_f1_mean": (
                        f"{aggregate['weighted_f1']['mean']:.12f}"
                    ),
                    "test_weighted_f1_sample_std": (
                        f"{aggregate['weighted_f1']['sample_std']:.12f}"
                    ),
                    "run_count": aggregate["macro_f1"]["count"],
                }
            )

    seed_path = output_dir / "seed_results.csv"
    with seed_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "condition_id",
                "source_experiment_id",
                "seed",
                "test_macro_f1",
                "test_accuracy",
                "test_macro_precision",
                "test_macro_recall",
                "test_weighted_f1",
                "inference_seconds",
            ],
        )
        writer.writeheader()
        for condition in conditions:
            for result in all_results[condition["id"]]:
                metrics = result["metrics"]
                writer.writerow(
                    {
                        "condition_id": condition["id"],
                        "source_experiment_id": condition[
                            "source_experiment_id"
                        ],
                        "seed": (
                            "" if result["seed"] is None else result["seed"]
                        ),
                        "test_macro_f1": f"{metrics['macro']['f1']:.12f}",
                        "test_accuracy": f"{metrics['accuracy']:.12f}",
                        "test_macro_precision": (
                            f"{metrics['macro']['precision']:.12f}"
                        ),
                        "test_macro_recall": (
                            f"{metrics['macro']['recall']:.12f}"
                        ),
                        "test_weighted_f1": (
                            f"{metrics['weighted']['f1']:.12f}"
                        ),
                        "inference_seconds": (
                            f"{result['inference_seconds']:.6f}"
                        ),
                    }
                )
    return {
        "condition_summary": artifact(summary_path),
        "seed_results": artifact(seed_path),
    }


def validate_gate(
    config: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Append-only test output is not empty: {output_dir}"
        )
    protocol_path = project_path(config["protocol"]["path"])
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    source_checks = [
        {
            "condition_id": condition["id"],
            **verify_source_condition(condition),
        }
        for condition in config["conditions"]
    ]
    environment = environment_metadata()
    data = load_test_data(config)
    return environment, data, source_checks


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config, config_hash = load_config(config_path)
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else project_path(config["output_dir"])
    )

    environment, data, source_checks = validate_gate(config, output_dir)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "authorization": config["authorization"],
                    "checkpoint_evaluation_count": sum(
                        (
                            1
                            if condition["type"] == "sklearn_joblib"
                            else len(condition["checkpoints"])
                        )
                        for condition in config["conditions"]
                    ),
                    "condition_ids": [
                        condition["id"]
                        for condition in config["conditions"]
                    ],
                    "config_sha256": config_hash,
                    "output_dir_empty": True,
                    "source_checks": source_checks,
                    "status": "TEST-READY",
                    "test_row_count": len(data["labels"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    output_dir.mkdir(parents=True)
    stdout_handle = (output_dir / "stdout.log").open(
        "w",
        encoding="utf-8",
    )
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = Tee(original_stdout, stdout_handle)
    sys.stderr = Tee(original_stderr, stdout_handle)
    started_at = utc_now()
    started = perf_counter()
    run: dict[str, Any] = {
        "accessed_splits": ["test"],
        "authorization": config["authorization"],
        "command": [sys.executable, *sys.argv],
        "config": {
            "path": relative_to_project(config_path),
            "sha256": config_hash,
        },
        "data": {
            "files_read": config["data"]["files"],
            "label_mapping": config["data"]["label_mapping"],
            "test_class_distribution": {
                str(label_id): count
                for label_id, count in sorted(Counter(data["labels"]).items())
            },
            "test_sample_count": len(data["labels"]),
            "upstream_commit": config["data"]["upstream_commit"],
        },
        "environment": environment,
        "experiment_id": config["experiment_id"],
        "protocol": {
            "path": config["protocol"]["path"],
            "sha256": sha256(project_path(config["protocol"]["path"])),
        },
        "source_checks": source_checks,
        "stage": config["stage"],
        "started_at": started_at,
        "status": "Running",
        "test_split_accessed": True,
        "tier": config["tier"],
        "validation_split_accessed": False,
        "working_directory": str(Path.cwd()),
    }
    run_path = output_dir / "run.json"
    write_json(run_path, run)

    try:
        all_results: dict[str, list[dict[str, Any]]] = {}
        aggregates: dict[str, dict[str, Any]] = {}
        for condition in config["conditions"]:
            log(f"Starting frozen condition {condition['id']}")
            condition_dir = output_dir / "conditions" / condition["id"]
            if condition["type"] == "sklearn_joblib":
                results = [evaluate_svm(condition, data, condition_dir)]
                log(
                    f"Completed {condition['id']}: test Macro-F1="
                    f"{results[0]['metrics']['macro']['f1']:.6f}"
                )
            else:
                results = evaluate_transformer_condition(
                    condition,
                    data,
                    condition_dir,
                )
            all_results[condition["id"]] = results
            aggregates[condition["id"]] = aggregate_results(
                condition,
                results,
                data["mapping"],
            )

        comparisons = {
            "exp-014-minus-exp-011": paired_comparison(
                all_results[
                    "exp-014-generic-roberta-label-smoothing"
                ],
                all_results["exp-011-generic-roberta"],
            ),
            "exp-015-minus-exp-014": paired_comparison(
                all_results[
                    "exp-015-twitter-roberta-label-smoothing"
                ],
                all_results[
                    "exp-014-generic-roberta-label-smoothing"
                ],
            ),
        }
        table_artifacts = write_result_tables(
            output_dir,
            config["conditions"],
            all_results,
            aggregates,
        )
        ranking = sorted(
            [
                {
                    "condition_id": condition["id"],
                    "source_experiment_id": condition[
                        "source_experiment_id"
                    ],
                    "test_macro_f1_mean": aggregates[
                        condition["id"]
                    ]["macro_f1"]["mean"],
                }
                for condition in config["conditions"]
            ],
            key=lambda item: item["test_macro_f1_mean"],
            reverse=True,
        )
        run.update(
            {
                "artifacts": {
                    **table_artifacts,
                    "stdout_log": {
                        "path": relative_to_project(
                            output_dir / "stdout.log"
                        )
                    },
                },
                "completed_at": utc_now(),
                "condition_aggregates": aggregates,
                "condition_results": all_results,
                "external_references": config["external_references"],
                "paired_comparisons": comparisons,
                "ranking": ranking,
                "status": "Completed",
                "wall_time_seconds": perf_counter() - started,
            }
        )
        write_json(run_path, run)
        log(
            "EXP-016 completed; all preregistered frozen models were "
            "evaluated exactly once"
        )
    except Exception as error:
        run.update(
            {
                "completed_at": utc_now(),
                "error": {
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                    "type": type(error).__name__,
                },
                "status": "Failed",
                "wall_time_seconds": perf_counter() - started,
            }
        )
        write_json(run_path, run)
        raise
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        stdout_handle.close()


if __name__ == "__main__":
    main()
