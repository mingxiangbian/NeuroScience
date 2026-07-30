#!/usr/bin/env python3
"""Run the preregistered EXP-010 RoBERTa-base fine-tuning experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import site
import shutil
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter
import traceback
from typing import Any, TextIO
import warnings

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault(
    "HF_HOME", str(Path(tempfile.gettempdir()) / "erc-huggingface")
)
os.environ.setdefault(
    "HF_DATASETS_CACHE",
    str(Path(tempfile.gettempdir()) / "erc-huggingface-datasets"),
)
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "erc-matplotlib-cache")
)

import accelerate
import datasets
import evaluate
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import sklearn
import torch
import transformers
from datasets import Dataset
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)


EXPERIMENT_ID = "EXP-010"
RQ_ID = "RQ-B2"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-010-roberta-base.json"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "runs" / "exp-010-roberta-base-finetuning"
REQUIREMENTS_LOCK = SCRIPT_DIR / "requirements-lock.txt"
PROTOCOL_PATH = (
    SCRIPT_DIR
    / "protocols"
    / "exp-010-roberta-base-finetuning.md"
)
EXPECTED_CONFIG_SHA256 = (
    "db3b9c2772447d66bf0d83c69f7caedde43eba4fcf2b251574e7b121f0b327ee"
)
EXPECTED_LOCK_SHA256 = (
    "123e455840fb9e5e9230cd3eb7feda625a8819c4cd3dbf82b91068a7d60797fd"
)
EXPECTED_PROTOCOL_SHA256 = (
    "0ea7ab741f1c376ba7f24db3a2ebcd6a4933f2cb0a2ab6c25b46bd0f418775b0"
)


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
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
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


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def prepare_output_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Append-only output directory is not empty: {path}"
        )
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        return {
            "branch": "unavailable",
            "commit": "unavailable",
            "dirty": None,
            "error": str(error),
        }


def assert_dependency_isolation() -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise RuntimeError("PYTHONNOUSERSITE=1 is required")
    if os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 is required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user-site loading is enabled")

    user_site = Path(site.getusersitepackages()).resolve()
    resolved_sys_path = [
        Path(value or ".").resolve() for value in sys.path if value is not None
    ]
    if any(path == user_site or user_site in path.parents for path in resolved_sys_path):
        raise RuntimeError(f"User-site path leaked into sys.path: {user_site}")

    prefix = Path(sys.prefix).resolve()
    module_names = [
        "accelerate",
        "datasets",
        "evaluate",
        "matplotlib",
        "numpy",
        "pandas",
        "sklearn",
        "torch",
        "transformers",
    ]
    module_paths: dict[str, str] = {}
    for name in module_names:
        module = importlib.import_module(name)
        module_path = Path(module.__file__).resolve()
        if prefix != module_path and prefix not in module_path.parents:
            raise RuntimeError(
                f"Dependency {name} resolved outside {prefix}: {module_path}"
            )
        module_paths[name] = str(module_path)

    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PIP_USER": "0",
            "PYTHONNOUSERSITE": "1",
        },
    )
    if sha256(REQUIREMENTS_LOCK) != EXPECTED_LOCK_SHA256:
        raise ValueError("Runtime requirements lock hash changed")
    pip_freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PIP_USER": "0",
            "PYTHONNOUSERSITE": "1",
        },
    )
    bootstrap_prefixes = ("pip @ ", "setuptools==", "wheel==")
    installed_runtime = [
        line
        for line in pip_freeze.stdout.splitlines()
        if not line.startswith(bootstrap_prefixes)
    ]
    frozen_runtime = REQUIREMENTS_LOCK.read_text(
        encoding="utf-8"
    ).splitlines()
    if installed_runtime != frozen_runtime:
        raise ValueError("Installed runtime packages do not match the lock")
    if sha256(PROTOCOL_PATH) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Preregistered protocol hash changed")
    if not torch.backends.mps.is_built():
        raise RuntimeError("PyTorch was not built with MPS support")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable in this process")

    return {
        "conda_prefix": str(prefix),
        "module_paths": module_paths,
        "pip_check": pip_check.stdout.strip(),
        "pip_freeze_matches_lock": True,
        "python_no_user_site": os.environ.get("PYTHONNOUSERSITE"),
        "requirements_lock": {
            "path": relative_to_project(REQUIREMENTS_LOCK),
            "sha256": EXPECTED_LOCK_SHA256,
        },
        "runtime_package_count": len(installed_runtime),
        "user_site": str(user_site),
        "user_site_enabled": site.ENABLE_USER_SITE,
    }


def load_frozen_config(path: Path) -> dict[str, Any]:
    actual_hash = sha256(path)
    if actual_hash != EXPECTED_CONFIG_SHA256:
        raise ValueError(
            f"Frozen config hash changed: {actual_hash} "
            f"!= {EXPECTED_CONFIG_SHA256}"
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["experiment_id"] != EXPERIMENT_ID:
        raise ValueError("Unexpected experiment ID in config")
    if config["tier"] != "Major" or config["rq_id"] != RQ_ID:
        raise ValueError("Unexpected tier or RQ in config")
    if config["data"]["allowed_splits"] != ["train", "validation"]:
        raise ValueError("Allowed split list changed")
    if any(
        "test" in item["path"].lower()
        for item in config["data"]["files"].values()
    ):
        raise ValueError("Frozen config contains a test path")
    return config


def verify_external_inputs(config: dict[str, Any]) -> dict[str, Any]:
    model_config = config["model"]
    manifest_path = PROJECT_ROOT / model_config["manifest"]
    if sha256(manifest_path) != model_config["manifest_sha256"]:
        raise ValueError("Model manifest hash changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != model_config["repo_id"]:
        raise ValueError("Model repository mismatch")
    if manifest["revision"] != model_config["revision"]:
        raise ValueError("Model revision mismatch")

    snapshot = PROJECT_ROOT / model_config["local_snapshot"]
    verified_model_files = []
    for expected in manifest["files"]:
        path = snapshot / expected["path"]
        actual = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256(path),
        }
        if actual != expected:
            raise ValueError(f"Model file integrity mismatch: {path}")
        verified_model_files.append(actual)

    comparison_config = config["comparison"]
    comparison_path = PROJECT_ROOT / comparison_config["run_metadata"]
    if sha256(comparison_path) != comparison_config["run_metadata_sha256"]:
        raise ValueError("EXP-007 comparison metadata hash changed")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if comparison["experiment_id"] != comparison_config["experiment_id"]:
        raise ValueError("Comparison experiment ID mismatch")
    if comparison["test_split_accessed"] is not False:
        raise ValueError("Comparison metadata does not exclude test")
    if not math.isclose(
        comparison["metrics"]["macro"]["f1"],
        comparison_config["validation_macro_f1"],
        abs_tol=1e-12,
    ):
        raise ValueError("Comparison Macro-F1 mismatch")

    return {
        "comparison": comparison,
        "comparison_path": comparison_path,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "snapshot": snapshot,
        "verified_model_files": verified_model_files,
    }


def read_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_labels(path: Path) -> list[int]:
    try:
        return [int(value) for value in read_text_lines(path)]
    except ValueError as error:
        raise ValueError(f"Non-integer label in {path}") from error


def read_mapping(path: Path) -> dict[int, str]:
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


def load_data(config: dict[str, Any]) -> dict[str, Any]:
    file_config = config["data"]["files"]
    paths = {
        name: PROJECT_ROOT / value["path"]
        for name, value in file_config.items()
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing input {name}: {path}")
        if sha256(path) != file_config[name]["sha256"]:
            raise ValueError(f"Input hash changed: {name}")

    mapping = read_mapping(paths["mapping"])
    train_texts = read_text_lines(paths["train_text"])
    train_labels = read_labels(paths["train_labels"])
    validation_texts = read_text_lines(paths["validation_text"])
    validation_labels = read_labels(paths["validation_labels"])
    expected_mapping = {
        int(label_id): label
        for label_id, label in config["data"]["label_mapping"].items()
    }
    if mapping != expected_mapping:
        raise ValueError(f"Label mapping changed: {mapping}")

    for split, texts, labels, expected_count in (
        (
            "train",
            train_texts,
            train_labels,
            config["data"]["train_sample_count"],
        ),
        (
            "validation",
            validation_texts,
            validation_labels,
            config["data"]["validation_sample_count"],
        ),
    ):
        if len(texts) != expected_count or len(labels) != expected_count:
            raise ValueError(
                f"{split} count mismatch: {len(texts)} texts, "
                f"{len(labels)} labels, expected {expected_count}"
            )
        unknown = sorted(set(labels) - set(mapping))
        if unknown:
            raise ValueError(f"Unknown {split} labels: {unknown}")

    return {
        "mapping": mapping,
        "paths": paths,
        "train_labels": train_labels,
        "train_texts": train_texts,
        "validation_labels": validation_labels,
        "validation_texts": validation_texts,
    }


def tokenize_dataset(
    tokenizer: Any,
    texts: list[str],
    labels: list[int],
    max_length: int,
) -> tuple[Dataset, dict[str, float | int]]:
    encoded = tokenizer(
        texts,
        max_length=max_length,
        padding=False,
        truncation=True,
    )
    lengths = [len(values) for values in encoded["input_ids"]]
    encoded["labels"] = labels
    return Dataset.from_dict(encoded), {
        "max": max(lengths),
        "mean": float(statistics.fmean(lengths)),
        "median": float(statistics.median(lengths)),
        "p95": float(np.percentile(lengths, 95)),
        "truncated_count": sum(length == max_length for length in lengths),
    }


def compact_metrics(logits: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    predictions = np.argmax(logits, axis=-1)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=[0, 1, 2, 3],
            average="macro",
            zero_division=0,
        )
    )
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        labels,
        predictions,
        labels=[0, 1, 2, 3],
        average="weighted",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(macro_f1),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "weighted_f1": float(weighted_f1),
    }


def compute_metrics(eval_prediction: Any) -> dict[str, float]:
    logits, labels = eval_prediction
    if isinstance(logits, tuple):
        logits = logits[0]
    return compact_metrics(np.asarray(logits), np.asarray(labels))


def detailed_metrics(
    logits: np.ndarray,
    labels: np.ndarray,
    mapping: dict[int, str],
    loss: float,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    class_ids = sorted(mapping)
    predictions = np.argmax(logits, axis=-1)
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponentiated = np.exp(shifted)
    probabilities = exponentiated / exponentiated.sum(axis=1, keepdims=True)

    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average="macro",
            zero_division=0,
        )
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average="weighted",
            zero_division=0,
        )
    )
    class_precision, class_recall, class_f1, class_support = (
        precision_recall_fscore_support(
            labels,
            predictions,
            labels=class_ids,
            average=None,
            zero_division=0,
        )
    )
    matrix = confusion_matrix(labels, predictions, labels=class_ids)
    metrics = {
        "accuracy": float(accuracy_score(labels, predictions)),
        "confusion_matrix": {
            "labels": [mapping[class_id] for class_id in class_ids],
            "orientation": "rows=true, columns=predicted",
            "values": [
                [int(value) for value in row] for row in matrix.tolist()
            ],
        },
        "loss": float(loss),
        "macro": {
            "f1": float(macro_f1),
            "precision": float(macro_precision),
            "recall": float(macro_recall),
        },
        "per_class": {
            mapping[class_id]: {
                "f1": float(class_f1[index]),
                "label_id": class_id,
                "precision": float(class_precision[index]),
                "recall": float(class_recall[index]),
                "support": int(class_support[index]),
            }
            for index, class_id in enumerate(class_ids)
        },
        "weighted": {
            "f1": float(weighted_f1),
            "precision": float(weighted_precision),
            "recall": float(weighted_recall),
        },
    }
    return metrics, predictions, probabilities, matrix


def save_predictions(
    path: Path,
    seed: int,
    gold_labels: list[int],
    predictions: np.ndarray,
    probabilities: np.ndarray,
    mapping: dict[int, str],
) -> None:
    class_ids = sorted(mapping)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row_number",
                "seed",
                "gold_label_id",
                "gold_label",
                "predicted_label_id",
                "predicted_label",
                *[f"probability_{mapping[class_id]}" for class_id in class_ids],
            ]
        )
        for row_number, (gold, predicted, row_probabilities) in enumerate(
            zip(gold_labels, predictions, probabilities, strict=True),
            start=1,
        ):
            writer.writerow(
                [
                    row_number,
                    seed,
                    gold,
                    mapping[gold],
                    int(predicted),
                    mapping[int(predicted)],
                    *[
                        f"{float(probability):.12f}"
                        for probability in row_probabilities
                    ],
                ]
            )


def save_confusion_csv(
    path: Path,
    matrix: np.ndarray,
    mapping: dict[int, str],
) -> None:
    names = [mapping[class_id] for class_id in sorted(mapping)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true_label/predicted_label", *names])
        for name, row in zip(names, matrix, strict=True):
            writer.writerow([name, *[int(value) for value in row]])


def save_confusion_figure(
    path: Path,
    matrix: np.ndarray,
    mapping: dict[int, str],
    seed: int,
) -> None:
    names = [mapping[class_id] for class_id in sorted(mapping)]
    figure, axis = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=names,
    ).plot(
        ax=axis,
        cmap="Blues",
        colorbar=False,
        values_format="d",
    )
    axis.set_title(f"EXP-010 Seed {seed} Validation")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def save_history(path: Path, history: list[dict[str, Any]]) -> None:
    fields = [
        "step",
        "epoch",
        "loss",
        "grad_norm",
        "learning_rate",
        "eval_loss",
        "eval_accuracy",
        "eval_macro_precision",
        "eval_macro_recall",
        "eval_macro_f1",
        "eval_weighted_f1",
        "train_loss",
        "train_runtime",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in history:
            writer.writerow(record)


def find_model_file(checkpoint: Path) -> Path:
    candidates = [
        checkpoint / "model.safetensors",
        checkpoint / "pytorch_model.bin",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No model weight file in {checkpoint}")


def retain_only_best_checkpoint(
    checkpoint_root: Path,
    best_checkpoint: Path,
) -> None:
    for checkpoint in checkpoint_root.glob("checkpoint-*"):
        if checkpoint.resolve() != best_checkpoint.resolve():
            shutil.rmtree(checkpoint)


def run_seed(
    seed: int,
    config: dict[str, Any],
    output_dir: Path,
    model_snapshot: Path,
    tokenizer: Any,
    train_dataset: Dataset,
    validation_dataset: Dataset,
    data: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    seed_dir = output_dir / "seeds" / f"seed-{seed}"
    seed_dir.mkdir(parents=True)
    checkpoint_root = seed_dir / "checkpoints"
    training = config["training"]
    set_seed(seed)
    log(f"Seed {seed}: loading local model")

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        model = AutoModelForSequenceClassification.from_pretrained(
            model_snapshot,
            id2label={
                int(label_id): label
                for label_id, label in config["data"]["label_mapping"].items()
            },
            label2id={
                label: int(label_id)
                for label_id, label in config["data"]["label_mapping"].items()
            },
            local_files_only=True,
            num_labels=4,
        )
        parameter_count = sum(
            parameter.numel() for parameter in model.parameters()
        )
        args = TrainingArguments(
            output_dir=str(checkpoint_root),
            per_device_train_batch_size=training[
                "per_device_train_batch_size"
            ],
            per_device_eval_batch_size=training["per_device_eval_batch_size"],
            num_train_epochs=training["num_train_epochs"],
            learning_rate=training["learning_rate"],
            lr_scheduler_type=training["lr_scheduler_type"],
            warmup_ratio=training["warmup_ratio"],
            optim=training["optim"],
            weight_decay=training["weight_decay"],
            gradient_accumulation_steps=training[
                "gradient_accumulation_steps"
            ],
            max_grad_norm=training["max_grad_norm"],
            label_smoothing_factor=training["label_smoothing_factor"],
            bf16=training["bf16"],
            fp16=training["fp16"],
            eval_strategy=training["eval_strategy"],
            save_strategy=training["save_strategy"],
            save_total_limit=training["save_total_limit"],
            save_only_model=training["save_only_model"],
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            logging_strategy="steps",
            logging_steps=training["logging_steps"],
            logging_first_step=training["logging_first_step"],
            report_to="none",
            disable_tqdm=True,
            dataloader_num_workers=training["dataloader_num_workers"],
            dataloader_pin_memory=training["dataloader_pin_memory"],
            seed=seed,
            data_seed=seed,
            run_name=f"exp-010-seed-{seed}",
        )
        trainer = Trainer(
            model=model,
            args=args,
            data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
            train_dataset=train_dataset,
            eval_dataset=validation_dataset,
            processing_class=tokenizer,
            compute_metrics=compute_metrics,
        )
        if str(trainer.args.device) != "mps":
            raise RuntimeError(
                f"Seed {seed} did not select MPS: {trainer.args.device}"
            )
        log(f"Seed {seed}: starting five-epoch fine-tuning on MPS")
        train_started = perf_counter()
        train_result = trainer.train()
        train_seconds = perf_counter() - train_started
        log(f"Seed {seed}: selected checkpoint {trainer.state.best_model_checkpoint}")

        validation_output = trainer.predict(
            validation_dataset,
            metric_key_prefix="validation_final",
        )
        train_output = trainer.predict(
            train_dataset,
            metric_key_prefix="train_diagnostic",
        )

    validation_logits = np.asarray(validation_output.predictions)
    train_logits = np.asarray(train_output.predictions)
    validation_metrics, predictions, probabilities, matrix = detailed_metrics(
        validation_logits,
        np.asarray(data["validation_labels"]),
        data["mapping"],
        validation_output.metrics["validation_final_loss"],
    )
    train_metrics, _, _, _ = detailed_metrics(
        train_logits,
        np.asarray(data["train_labels"]),
        data["mapping"],
        train_output.metrics["train_diagnostic_loss"],
    )

    if not math.isfinite(validation_metrics["macro"]["f1"]):
        raise ValueError(f"Seed {seed} produced non-finite Macro-F1")
    if not np.isfinite(validation_logits).all():
        raise ValueError(f"Seed {seed} produced non-finite validation logits")

    best_checkpoint = Path(trainer.state.best_model_checkpoint).resolve()
    model_file = find_model_file(best_checkpoint)
    predictions_path = seed_dir / "predictions.csv"
    confusion_csv_path = seed_dir / "confusion_matrix.csv"
    confusion_png_path = seed_dir / "confusion_matrix.png"
    history_path = seed_dir / "history.csv"
    metrics_path = seed_dir / "metrics.json"

    save_predictions(
        predictions_path,
        seed,
        data["validation_labels"],
        predictions,
        probabilities,
        data["mapping"],
    )
    save_confusion_csv(confusion_csv_path, matrix, data["mapping"])
    save_confusion_figure(
        confusion_png_path, matrix, data["mapping"], seed
    )
    history = list(trainer.state.log_history)
    save_history(history_path, history)

    best_step = int(trainer.state.best_global_step)
    best_history = next(
        (
            item
            for item in history
            if item.get("step") == best_step and "eval_macro_f1" in item
        ),
        None,
    )
    if best_history is None:
        raise ValueError(f"Seed {seed} best checkpoint is absent from history")
    if not math.isclose(
        validation_metrics["macro"]["f1"],
        float(trainer.state.best_metric),
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"Seed {seed} loaded checkpoint metric mismatch: "
            f"{validation_metrics['macro']['f1']} "
            f"!= {trainer.state.best_metric}"
        )
    retain_only_best_checkpoint(checkpoint_root, best_checkpoint)
    retained_checkpoints = list(checkpoint_root.glob("checkpoint-*"))
    if [path.resolve() for path in retained_checkpoints] != [best_checkpoint]:
        raise ValueError(
            f"Seed {seed} retained unexpected checkpoints: "
            f"{retained_checkpoints}"
        )

    seed_metadata = {
        "best_checkpoint": {
            "epoch": float(best_history["epoch"]),
            "global_step": best_step,
            "metric": "validation Macro-F1",
            "metric_value": float(trainer.state.best_metric),
            "model_file": {
                "path": relative_to_project(model_file),
                "sha256": sha256(model_file),
            },
            "path": relative_to_project(best_checkpoint),
        },
        "parameter_count": parameter_count,
        "runtime": {
            "device": str(trainer.args.device),
            "train_seconds": train_seconds,
            "trainer_train_metrics": {
                key: float(value)
                for key, value in train_result.metrics.items()
                if isinstance(value, (int, float))
            },
        },
        "seed": seed,
        "train_diagnostic": train_metrics,
        "validation": validation_metrics,
        "warnings": [
            {
                "category": item.category.__name__,
                "message": str(item.message),
            }
            for item in captured_warnings
        ],
    }
    write_json(metrics_path, seed_metadata)
    seed_metadata["artifacts"] = {
        "confusion_matrix_csv": {
            "path": relative_to_project(confusion_csv_path),
            "sha256": sha256(confusion_csv_path),
        },
        "confusion_matrix_png": {
            "path": relative_to_project(confusion_png_path),
            "sha256": sha256(confusion_png_path),
        },
        "history": {
            "path": relative_to_project(history_path),
            "sha256": sha256(history_path),
        },
        "metrics": {
            "path": relative_to_project(metrics_path),
            "sha256": sha256(metrics_path),
        },
        "predictions": {
            "path": relative_to_project(predictions_path),
            "sha256": sha256(predictions_path),
        },
    }
    log(
        f"Seed {seed}: validation Macro-F1 "
        f"{validation_metrics['macro']['f1']:.6f}, "
        f"Accuracy {validation_metrics['accuracy']:.6f}"
    )

    del trainer, model, validation_output, train_output
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    return seed_metadata, history


def metric_series(
    seed_results: list[dict[str, Any]],
    section: str,
    path: tuple[str, ...],
) -> list[float]:
    values = []
    for result in seed_results:
        current: Any = result[section]
        for key in path:
            current = current[key]
        values.append(float(current))
    return values


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
        "values": values,
    }


def aggregate_results(
    seed_results: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    aggregate = {
        "train_diagnostic": {
            "accuracy": summarize(
                metric_series(seed_results, "train_diagnostic", ("accuracy",))
            ),
            "macro_f1": summarize(
                metric_series(
                    seed_results, "train_diagnostic", ("macro", "f1")
                )
            ),
        },
        "validation": {
            "accuracy": summarize(
                metric_series(seed_results, "validation", ("accuracy",))
            ),
            "loss": summarize(
                metric_series(seed_results, "validation", ("loss",))
            ),
            "macro_f1": summarize(
                metric_series(seed_results, "validation", ("macro", "f1"))
            ),
            "macro_precision": summarize(
                metric_series(
                    seed_results, "validation", ("macro", "precision")
                )
            ),
            "macro_recall": summarize(
                metric_series(
                    seed_results, "validation", ("macro", "recall")
                )
            ),
            "weighted_f1": summarize(
                metric_series(seed_results, "validation", ("weighted", "f1"))
            ),
        },
    }
    aggregate["validation"]["per_class_f1"] = {
        label: summarize(
            metric_series(
                seed_results, "validation", ("per_class", label, "f1")
            )
        )
        for label in config["data"]["label_mapping"].values()
    }
    baseline = config["comparison"]["validation_macro_f1"]
    delta = aggregate["validation"]["macro_f1"]["mean"] - baseline
    aggregate["comparison"] = {
        "baseline_experiment_id": config["comparison"]["experiment_id"],
        "baseline_validation_macro_f1": baseline,
        "mean_macro_f1_delta": float(delta),
        "practical_improvement_passed": bool(
            delta >= config["comparison"]["practical_improvement_threshold"]
        ),
        "practical_improvement_threshold": config["comparison"][
            "practical_improvement_threshold"
        ],
    }
    return aggregate


def save_seed_summary(
    path: Path,
    seed_results: list[dict[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "seed",
                "best_epoch",
                "best_global_step",
                "validation_loss",
                "validation_accuracy",
                "validation_macro_f1",
                "validation_weighted_f1",
                "train_accuracy",
                "train_macro_f1",
                "train_seconds",
                "checkpoint_model_sha256",
            ]
        )
        for result in seed_results:
            writer.writerow(
                [
                    result["seed"],
                    result["best_checkpoint"]["epoch"],
                    result["best_checkpoint"]["global_step"],
                    result["validation"]["loss"],
                    result["validation"]["accuracy"],
                    result["validation"]["macro"]["f1"],
                    result["validation"]["weighted"]["f1"],
                    result["train_diagnostic"]["accuracy"],
                    result["train_diagnostic"]["macro"]["f1"],
                    result["runtime"]["train_seconds"],
                    result["best_checkpoint"]["model_file"]["sha256"],
                ]
            )


def save_learning_curves(
    path: Path,
    histories: dict[int, list[dict[str, Any]]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for seed, history in histories.items():
        training_records = [item for item in history if "loss" in item]
        evaluation_records = [
            item for item in history if "eval_macro_f1" in item
        ]
        axes[0].plot(
            [item["step"] for item in training_records],
            [item["loss"] for item in training_records],
            label=f"seed {seed}",
        )
        axes[1].plot(
            [item["epoch"] for item in evaluation_records],
            [item["eval_macro_f1"] for item in evaluation_records],
            marker="o",
            label=f"seed {seed}",
        )
    axes[0].set_title("Training Loss")
    axes[0].set_xlabel("Step")
    axes[0].set_ylabel("Cross-Entropy Loss")
    axes[1].set_title("Validation Macro-F1")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Macro-F1")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    prepare_output_dir(output_dir)
    stdout_path = output_dir / "stdout.log"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    started_at = utc_now()
    total_started = perf_counter()
    run_path = output_dir / "run.json"
    run_state: dict[str, Any] = {
        "accessed_splits": [],
        "completed_seed_count": 0,
        "created_at_utc": started_at,
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "stage": "train-validation",
        "status": "Running",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
    }
    write_json(run_path, run_state)

    with stdout_path.open("a", encoding="utf-8") as stdout_file:
        sys.stdout = Tee(original_stdout, stdout_file)
        sys.stderr = Tee(original_stderr, stdout_file)
        try:
            log("EXP-010 starting; test access is prohibited")
            environment = assert_dependency_isolation()
            config = load_frozen_config(config_path)
            external = verify_external_inputs(config)
            log("Environment, config, model, and comparison gates passed")

            data = load_data(config)
            run_state["accessed_splits"] = ["train", "validation"]
            run_state["validation_split_accessed"] = True
            write_json(run_path, run_state)
            log(
                f"Loaded {len(data['train_texts'])} train and "
                f"{len(data['validation_texts'])} validation rows"
            )

            tokenizer = AutoTokenizer.from_pretrained(
                external["snapshot"],
                local_files_only=True,
            )
            train_dataset, train_lengths = tokenize_dataset(
                tokenizer,
                data["train_texts"],
                data["train_labels"],
                config["tokenization"]["max_length"],
            )
            validation_dataset, validation_lengths = tokenize_dataset(
                tokenizer,
                data["validation_texts"],
                data["validation_labels"],
                config["tokenization"]["max_length"],
            )

            seed_results = []
            histories: dict[int, list[dict[str, Any]]] = {}
            for seed in config["training"]["seeds"]:
                result, history = run_seed(
                    seed,
                    config,
                    output_dir,
                    external["snapshot"],
                    tokenizer,
                    train_dataset,
                    validation_dataset,
                    data,
                )
                seed_results.append(result)
                histories[seed] = history
                run_state["completed_seed_count"] = len(seed_results)
                run_state["seed_results"] = seed_results
                write_json(run_path, run_state)

            aggregate = aggregate_results(seed_results, config)
            aggregate_path = output_dir / "aggregate_metrics.json"
            seed_summary_path = output_dir / "seed_summary.csv"
            curves_path = output_dir / "learning_curves.png"
            write_json(aggregate_path, aggregate)
            save_seed_summary(seed_summary_path, seed_results)
            save_learning_curves(curves_path, histories)

            label_ids = sorted(data["mapping"])
            train_counts = Counter(data["train_labels"])
            validation_counts = Counter(data["validation_labels"])
            total_seconds = perf_counter() - total_started
            final_run = {
                "accessed_splits": ["train", "validation"],
                "artifacts": {
                    "aggregate_metrics": {
                        "path": relative_to_project(aggregate_path),
                        "sha256": sha256(aggregate_path),
                    },
                    "config": {
                        "path": relative_to_project(config_path),
                        "sha256": EXPECTED_CONFIG_SHA256,
                    },
                    "learning_curves": {
                        "path": relative_to_project(curves_path),
                        "sha256": sha256(curves_path),
                    },
                    "protocol": {
                        "path": relative_to_project(PROTOCOL_PATH),
                        "sha256": EXPECTED_PROTOCOL_SHA256,
                    },
                    "requirements_lock": {
                        "path": relative_to_project(REQUIREMENTS_LOCK),
                        "sha256": EXPECTED_LOCK_SHA256,
                    },
                    "training_script": {
                        "path": relative_to_project(Path(__file__)),
                        "sha256": sha256(Path(__file__)),
                    },
                    "seed_summary": {
                        "path": relative_to_project(seed_summary_path),
                        "sha256": sha256(seed_summary_path),
                    },
                    "stdout_log": {
                        "path": relative_to_project(stdout_path)
                    },
                },
                "comparison": aggregate["comparison"],
                "completed_at_utc": utc_now(),
                "created_at_utc": started_at,
                "data": {
                    "dataset": config["data"]["dataset"],
                    "exact_duplicate_checks": {
                        "train_duplicate_rows": (
                            len(data["train_texts"])
                            - len(set(data["train_texts"]))
                        ),
                        "train_validation_text_overlap": len(
                            set(data["train_texts"])
                            & set(data["validation_texts"])
                        ),
                        "validation_duplicate_rows": (
                            len(data["validation_texts"])
                            - len(set(data["validation_texts"]))
                        ),
                    },
                    "files_read": {
                        name: {
                            "path": relative_to_project(path),
                            "sha256": sha256(path),
                        }
                        for name, path in data["paths"].items()
                    },
                    "label_mapping": {
                        str(label_id): data["mapping"][label_id]
                        for label_id in label_ids
                    },
                    "token_lengths": {
                        "train": train_lengths,
                        "validation": validation_lengths,
                    },
                    "train_class_distribution": {
                        str(label_id): train_counts[label_id]
                        for label_id in label_ids
                    },
                    "train_sample_count": len(data["train_labels"]),
                    "upstream_commit": config["data"]["upstream_commit"],
                    "validation_class_distribution": {
                        str(label_id): validation_counts[label_id]
                        for label_id in label_ids
                    },
                    "validation_sample_count": len(
                        data["validation_labels"]
                    ),
                },
                "environment_gate": environment,
                "experiment_id": EXPERIMENT_ID,
                "invocation": [sys.executable, *sys.argv],
                "model": {
                    "classification_head": (
                        "newly initialized independently for each seed"
                    ),
                    "local_files_only": True,
                    "manifest": {
                        "path": relative_to_project(
                            external["manifest_path"]
                        ),
                        "sha256": config["model"]["manifest_sha256"],
                    },
                    "repo_id": config["model"]["repo_id"],
                    "revision": config["model"]["revision"],
                    "snapshot_path": relative_to_project(
                        external["snapshot"]
                    ),
                    "verified_snapshot_files": external[
                        "verified_model_files"
                    ],
                },
                "resource_budget": {
                    **config["resource_budget"],
                    "actual_seed_runs": len(seed_results),
                    "actual_total_seconds": total_seconds,
                },
                "rq_id": RQ_ID,
                "runtime": {
                    "architecture": platform.machine(),
                    "device": "mps",
                    "executable": sys.executable,
                    "git": git_metadata(),
                    "mps_available": torch.backends.mps.is_available(),
                    "mps_built": torch.backends.mps.is_built(),
                    "packages": {
                        "accelerate": accelerate.__version__,
                        "datasets": datasets.__version__,
                        "evaluate": evaluate.__version__,
                        "matplotlib": matplotlib.__version__,
                        "numpy": np.__version__,
                        "scikit_learn": sklearn.__version__,
                        "torch": torch.__version__,
                        "transformers": transformers.__version__,
                    },
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "total_seconds": total_seconds,
                },
                "seed_results": seed_results,
                "selection": config["selection"],
                "stage": "train-validation",
                "status": "Completed",
                "test_split_accessed": False,
                "tier": "Major",
                "training_config": config["training"],
                "validation_split_accessed": True,
            }
            write_json(run_path, final_run)
            log(
                "EXP-010 completed: mean validation Macro-F1 "
                f"{aggregate['validation']['macro_f1']['mean']:.6f} "
                "+/- "
                f"{aggregate['validation']['macro_f1']['sample_std']:.6f}"
            )
            log("Test split accessed: no")
            log(f"Artifacts: {output_dir}")
        except Exception as error:
            run_state.update(
                {
                    "completed_at_utc": utc_now(),
                    "error": {
                        "message": str(error),
                        "traceback": traceback.format_exc(),
                        "type": type(error).__name__,
                    },
                    "status": "Failed",
                    "test_split_accessed": False,
                }
            )
            write_json(run_path, run_state)
            log(f"EXP-010 failed: {type(error).__name__}: {error}")
            raise
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == "__main__":
    main()
