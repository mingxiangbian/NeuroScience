#!/usr/bin/env python3
"""Run controlled TweetEval emotion fine-tuning experiments."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
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

import accelerate
import datasets
import numpy as np
import sklearn
import torch
import torch.nn.functional as functional
import transformers
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
REQUIREMENTS_LOCK = SCRIPT_DIR / "requirements-lock.txt"


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


class WeightedTrainer(Trainer):
    def __init__(
        self,
        *args: Any,
        class_weights: torch.Tensor,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(
        self,
        model: torch.nn.Module,
        inputs: dict[str, Any],
        return_outputs: bool = False,
        num_items_in_batch: torch.Tensor | None = None,
    ) -> Any:
        del num_items_in_batch
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = functional.cross_entropy(
            outputs.logits,
            labels,
            weight=self.class_weights.to(outputs.logits.device),
            label_smoothing=float(self.args.label_smoothing_factor),
        )
        return (loss, outputs) if return_outputs else loss


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate frozen inputs and configuration without training.",
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


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def relative_to_project(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def project_path(value: str) -> Path:
    return (PROJECT_ROOT / value).resolve()


def prepare_output_dir(path: Path, validate_only: bool) -> None:
    if validate_only:
        return
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Append-only output directory is not empty: {path}"
        )
    path.mkdir(parents=True, exist_ok=True)


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
        env={
            **os.environ,
            "PIP_USER": "0",
            "PYTHONNOUSERSITE": "1",
        },
    )
    return {
        "architecture": platform.machine(),
        "device": "mps",
        "executable": sys.executable,
        "git": git_metadata(),
        "mps_available": torch.backends.mps.is_available(),
        "mps_built": torch.backends.mps.is_built(),
        "packages": {
            "accelerate": accelerate.__version__,
            "datasets": datasets.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "pip_check": pip_check.stdout.strip(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "requirements_lock": {
            "path": relative_to_project(REQUIREMENTS_LOCK),
            "sha256": sha256(REQUIREMENTS_LOCK),
        },
    }


def read_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle]


def read_labels(path: Path) -> list[int]:
    return [int(value) for value in read_lines(path)]


def read_mapping(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line_number, line in enumerate(read_lines(path), start=1):
        try:
            label_id, label = line.split("\t", maxsplit=1)
            mapping[int(label_id)] = label
        except ValueError as error:
            raise ValueError(
                f"Invalid mapping at {path}:{line_number}: {line!r}"
            ) from error
    return mapping


def verify_file(path: Path, expected_hash: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"Input hash changed for {path}: {actual_hash} != {expected_hash}"
        )


def load_config(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    config_hash = sha256(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"experiment_id", "tier", "rq_id", "stage", "data", "model"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"Config is missing required keys: {missing}")
    if config["tier"] not in {"Major", "Minor"}:
        raise ValueError(f"Unsupported tier: {config['tier']}")
    allowed_splits = config["data"]["allowed_splits"]
    if allowed_splits not in (["train"], ["train", "validation"]):
        raise ValueError(f"Unexpected allowed splits: {allowed_splits}")
    for item in config["data"]["files"].values():
        if "test" in item["path"].lower():
            raise ValueError("Config contains a test path")
    if config["tier"] == "Minor" and allowed_splits != ["train"]:
        raise ValueError("Minor screening may only access train")
    if config["tier"] == "Major":
        protocol_path = project_path(config["protocol"]["path"])
        if not protocol_path.is_file():
            raise FileNotFoundError(protocol_path)
    return config, config_hash


def verify_model(config: dict[str, Any]) -> dict[str, Any]:
    model_config = config["model"]
    manifest_path = project_path(model_config["manifest"])
    verify_file(manifest_path, model_config["manifest_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != model_config["repo_id"]:
        raise ValueError("Model repository mismatch")
    if manifest["revision"] != model_config["revision"]:
        raise ValueError("Model revision mismatch")

    snapshot = project_path(model_config["local_snapshot"])
    verified_files = []
    for expected in manifest["files"]:
        path = snapshot / expected["path"]
        actual = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256(path),
        }
        if actual != expected:
            raise ValueError(f"Model file integrity mismatch: {path}")
        verified_files.append(actual)
    return {
        "manifest_path": manifest_path,
        "snapshot": snapshot,
        "verified_files": verified_files,
    }


def load_data(config: dict[str, Any]) -> dict[str, Any]:
    file_config = config["data"]["files"]
    paths = {
        name: project_path(item["path"])
        for name, item in file_config.items()
    }
    for name, path in paths.items():
        verify_file(path, file_config[name]["sha256"])

    mapping = read_mapping(paths["mapping"])
    expected_mapping = {
        int(label_id): label
        for label_id, label in config["data"]["label_mapping"].items()
    }
    if mapping != expected_mapping:
        raise ValueError(f"Label mapping changed: {mapping}")

    train_texts = read_lines(paths["train_text"])
    train_labels = read_labels(paths["train_labels"])
    if (
        len(train_texts) != config["data"]["train_sample_count"]
        or len(train_labels) != config["data"]["train_sample_count"]
    ):
        raise ValueError("Train sample count changed")

    result = {
        "mapping": mapping,
        "paths": paths,
        "train_labels": train_labels,
        "train_row_ids": list(range(len(train_labels))),
        "train_texts": train_texts,
    }
    if config["data"]["allowed_splits"] == ["train", "validation"]:
        validation_texts = read_lines(paths["validation_text"])
        validation_labels = read_labels(paths["validation_labels"])
        if (
            len(validation_texts) != config["data"]["validation_sample_count"]
            or len(validation_labels)
            != config["data"]["validation_sample_count"]
        ):
            raise ValueError("Validation sample count changed")
        result.update(
            {
                "validation_labels": validation_labels,
                "validation_row_ids": list(range(len(validation_labels))),
                "validation_texts": validation_texts,
            }
        )
    return result


def normalize_tweet(text: str) -> tuple[str, int]:
    normalized = []
    changed = 0
    for token in text.split(" "):
        replacement = token
        if token.startswith("@") and len(token) > 1:
            replacement = "@user"
        elif token.startswith("http"):
            replacement = "http"
        if replacement != token:
            changed += 1
        normalized.append(replacement)
    return " ".join(normalized), changed


def apply_preprocessing(
    texts: list[str],
    normalize_mentions_urls: bool,
) -> tuple[list[str], dict[str, int]]:
    if not normalize_mentions_urls:
        return list(texts), {
            "changed_rows": 0,
            "changed_tokens": 0,
        }
    processed = []
    changed_rows = 0
    changed_tokens = 0
    for text in texts:
        value, token_changes = normalize_tweet(text)
        processed.append(value)
        changed_rows += int(value != text)
        changed_tokens += token_changes
    return processed, {
        "changed_rows": changed_rows,
        "changed_tokens": changed_tokens,
    }


def inner_train_split(
    data: dict[str, Any],
    split_config: dict[str, Any],
) -> dict[str, Any]:
    indices = np.arange(len(data["train_labels"]))
    train_indices, validation_indices = train_test_split(
        indices,
        test_size=float(split_config["validation_fraction"]),
        random_state=int(split_config["random_state"]),
        shuffle=True,
        stratify=np.asarray(data["train_labels"]),
    )
    return {
        "train_labels": [data["train_labels"][index] for index in train_indices],
        "train_row_ids": [int(index) for index in train_indices],
        "train_texts": [data["train_texts"][index] for index in train_indices],
        "validation_labels": [
            data["train_labels"][index] for index in validation_indices
        ],
        "validation_row_ids": [int(index) for index in validation_indices],
        "validation_texts": [
            data["train_texts"][index] for index in validation_indices
        ],
    }


def tokenize_dataset(
    tokenizer: Any,
    texts: list[str],
    labels: list[int],
    max_length: int,
) -> tuple[Dataset, dict[str, Any]]:
    raw = tokenizer(
        texts,
        add_special_tokens=True,
        padding=False,
        truncation=False,
    )
    raw_lengths = [len(input_ids) for input_ids in raw["input_ids"]]
    encoded = tokenizer(
        texts,
        add_special_tokens=True,
        max_length=max_length,
        padding=False,
        truncation=True,
    )
    encoded["labels"] = labels
    lengths = np.asarray(raw_lengths)
    return Dataset.from_dict(encoded), {
        "max": int(lengths.max()),
        "mean": float(lengths.mean()),
        "median": float(np.median(lengths)),
        "p95": float(np.percentile(lengths, 95)),
        "truncated_count": int(np.sum(lengths > max_length)),
    }


def compact_metrics(logits: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    predictions = np.argmax(logits, axis=-1)
    macro = precision_recall_fscore_support(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )
    weighted = precision_recall_fscore_support(
        labels,
        predictions,
        average="weighted",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(macro[2]),
        "macro_precision": float(macro[0]),
        "macro_recall": float(macro[1]),
        "weighted_f1": float(weighted[2]),
    }


def compute_metrics(eval_prediction: Any) -> dict[str, float]:
    return compact_metrics(
        np.asarray(eval_prediction.predictions),
        np.asarray(eval_prediction.label_ids),
    )


def detailed_metrics(
    logits: np.ndarray,
    labels: np.ndarray,
    mapping: dict[int, str],
    loss: float,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp_logits = np.exp(shifted)
    probabilities = exp_logits / exp_logits.sum(axis=1, keepdims=True)
    predictions = np.argmax(probabilities, axis=1)
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
    metrics = {
        "accuracy": float(accuracy_score(labels, predictions)),
        "loss": float(loss),
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
    }
    return metrics, predictions, probabilities, matrix


def save_predictions(
    path: Path,
    row_ids: list[int],
    labels: list[int],
    predictions: np.ndarray,
    probabilities: np.ndarray,
    mapping: dict[int, str],
) -> None:
    label_ids = sorted(mapping)
    fieldnames = [
        "row_id",
        "gold_id",
        "gold_label",
        "prediction_id",
        "prediction_label",
        *[f"prob_{mapping[label_id]}" for label_id in label_ids],
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
            for probability_index, label_id in enumerate(label_ids):
                row[f"prob_{mapping[label_id]}"] = (
                    f"{float(probabilities[index, probability_index]):.12f}"
                )
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


def save_history(path: Path, history: list[dict[str, Any]]) -> None:
    keys = sorted({key for row in history for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(history)


def class_weights(
    labels: list[int],
    mode: str,
    label_ids: list[int],
) -> torch.Tensor | None:
    if mode == "none":
        return None
    if mode != "inverse_sqrt":
        raise ValueError(f"Unsupported class weighting: {mode}")
    counts = Counter(labels)
    raw = np.asarray(
        [1.0 / math.sqrt(counts[label_id]) for label_id in label_ids],
        dtype=np.float32,
    )
    normalized = raw / raw.mean()
    return torch.tensor(normalized, dtype=torch.float32)


def merged_training(
    common: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    result = dict(common)
    result.update(overrides)
    return result


def retain_best_checkpoint(
    checkpoint_root: Path,
    best_checkpoint: Path,
) -> Path:
    for path in checkpoint_root.glob("checkpoint-*"):
        if path.resolve() != best_checkpoint.resolve():
            shutil.rmtree(path)
    files = list(best_checkpoint.glob("*.safetensors"))
    if len(files) != 1:
        raise ValueError(
            f"Expected one safetensors file in {best_checkpoint}: {files}"
        )
    return files[0]


def run_training(
    *,
    candidate: dict[str, Any],
    config: dict[str, Any],
    data: dict[str, Any],
    model_snapshot: Path,
    output_dir: Path,
    retain_checkpoint: bool,
    seed: int,
) -> dict[str, Any]:
    candidate_dir = output_dir / "candidates" / candidate["id"]
    seed_dir = candidate_dir / f"seed-{seed}"
    if seed_dir.exists():
        raise FileExistsError(f"Run already exists: {seed_dir}")
    seed_dir.mkdir(parents=True)
    checkpoint_root = seed_dir / "checkpoints"
    training = merged_training(
        config["common_training"], candidate.get("training", {})
    )
    normalize_enabled = bool(
        candidate.get("preprocessing", {}).get(
            "normalize_mentions_urls",
            False,
        )
    )
    processed_train, train_changes = apply_preprocessing(
        data["train_texts"], normalize_enabled
    )
    processed_validation, validation_changes = apply_preprocessing(
        data["validation_texts"], normalize_enabled
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_snapshot,
        local_files_only=True,
    )
    max_length = int(config["tokenization"]["max_length"])
    train_dataset, train_lengths = tokenize_dataset(
        tokenizer,
        processed_train,
        data["train_labels"],
        max_length,
    )
    validation_dataset, validation_lengths = tokenize_dataset(
        tokenizer,
        processed_validation,
        data["validation_labels"],
        max_length,
    )

    label_mapping = {
        int(label_id): label
        for label_id, label in config["data"]["label_mapping"].items()
    }
    label_ids = sorted(label_mapping)
    set_seed(seed)
    model_kwargs: dict[str, Any] = {
        "id2label": label_mapping,
        "label2id": {
            label: label_id for label_id, label in label_mapping.items()
        },
        "local_files_only": True,
        "num_labels": len(label_mapping),
    }
    classifier_dropout = candidate.get("classifier_dropout")
    if classifier_dropout is not None:
        model_kwargs["classifier_dropout"] = float(classifier_dropout)

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        model = AutoModelForSequenceClassification.from_pretrained(
            model_snapshot,
            **model_kwargs,
        )
        parameter_count = sum(
            parameter.numel() for parameter in model.parameters()
        )
        arguments = TrainingArguments(
            output_dir=str(checkpoint_root),
            per_device_train_batch_size=int(
                training["per_device_train_batch_size"]
            ),
            per_device_eval_batch_size=int(
                training["per_device_eval_batch_size"]
            ),
            num_train_epochs=float(training["num_train_epochs"]),
            learning_rate=float(training["learning_rate"]),
            lr_scheduler_type=training["lr_scheduler_type"],
            warmup_ratio=float(training["warmup_ratio"]),
            optim=training["optim"],
            weight_decay=float(training["weight_decay"]),
            gradient_accumulation_steps=int(
                training["gradient_accumulation_steps"]
            ),
            max_grad_norm=float(training["max_grad_norm"]),
            label_smoothing_factor=float(
                training["label_smoothing_factor"]
            ),
            bf16=False,
            fp16=False,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            save_only_model=True,
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            logging_strategy="steps",
            logging_steps=int(training["logging_steps"]),
            logging_first_step=True,
            report_to="none",
            disable_tqdm=True,
            dataloader_num_workers=0,
            dataloader_pin_memory=False,
            seed=seed,
            data_seed=seed,
            run_name=f"{config['experiment_id']}-{candidate['id']}-{seed}",
        )
        weights = class_weights(
            data["train_labels"],
            candidate.get("class_weighting", "none"),
            label_ids,
        )
        trainer_class = WeightedTrainer if weights is not None else Trainer
        trainer_kwargs: dict[str, Any] = {}
        if weights is not None:
            trainer_kwargs["class_weights"] = weights
        trainer = trainer_class(
            model=model,
            args=arguments,
            data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
            train_dataset=train_dataset,
            eval_dataset=validation_dataset,
            processing_class=tokenizer,
            compute_metrics=compute_metrics,
            **trainer_kwargs,
        )
        if str(trainer.args.device) != "mps":
            raise RuntimeError(
                f"Training did not select MPS: {trainer.args.device}"
            )
        log(
            f"{candidate['id']} seed {seed}: "
            f"lr={training['learning_rate']} "
            f"epochs={training['num_train_epochs']} "
            f"batch={training['per_device_train_batch_size']}"
        )
        started = perf_counter()
        train_result = trainer.train()
        train_seconds = perf_counter() - started
        validation_output = trainer.predict(
            validation_dataset,
            metric_key_prefix="validation_final",
        )
        train_output = None
        if bool(config.get("diagnose_train", False)):
            train_output = trainer.predict(
                train_dataset,
                metric_key_prefix="train_diagnostic",
            )

    logits = np.asarray(validation_output.predictions)
    validation_metrics, predictions, probabilities, matrix = detailed_metrics(
        logits,
        np.asarray(data["validation_labels"]),
        label_mapping,
        float(validation_output.metrics["validation_final_loss"]),
    )
    if not np.isfinite(logits).all():
        raise ValueError("Non-finite validation logits")

    history = list(trainer.state.log_history)
    history_path = seed_dir / "history.csv"
    predictions_path = seed_dir / "predictions.csv"
    confusion_path = seed_dir / "confusion_matrix.csv"
    metrics_path = seed_dir / "metrics.json"
    save_history(history_path, history)
    save_predictions(
        predictions_path,
        data["validation_row_ids"],
        data["validation_labels"],
        predictions,
        probabilities,
        label_mapping,
    )
    save_confusion_matrix(confusion_path, matrix, label_mapping)

    best_checkpoint = Path(trainer.state.best_model_checkpoint).resolve()
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
        raise ValueError("Best checkpoint is absent from training history")
    checkpoint_metadata: dict[str, Any] = {
        "epoch": float(best_history["epoch"]),
        "global_step": best_step,
        "metric": "Macro-F1",
        "metric_value": float(trainer.state.best_metric),
        "original_path": relative_to_project(best_checkpoint),
        "retained": retain_checkpoint,
    }
    if retain_checkpoint:
        model_file = retain_best_checkpoint(
            checkpoint_root, best_checkpoint
        )
        checkpoint_metadata["model_file"] = {
            "path": relative_to_project(model_file),
            "sha256": sha256(model_file),
        }
    else:
        shutil.rmtree(checkpoint_root)

    train_metrics = None
    if train_output is not None:
        train_metrics = detailed_metrics(
            np.asarray(train_output.predictions),
            np.asarray(data["train_labels"]),
            label_mapping,
            float(train_output.metrics["train_diagnostic_loss"]),
        )[0]

    result = {
        "artifacts": {
            "confusion_matrix": {
                "path": relative_to_project(confusion_path),
                "sha256": sha256(confusion_path),
            },
            "history": {
                "path": relative_to_project(history_path),
                "sha256": sha256(history_path),
            },
            "predictions": {
                "path": relative_to_project(predictions_path),
                "sha256": sha256(predictions_path),
            },
        },
        "best_checkpoint": checkpoint_metadata,
        "candidate_id": candidate["id"],
        "class_weighting": candidate.get("class_weighting", "none"),
        "parameter_count": parameter_count,
        "preprocessing": {
            "normalize_mentions_urls": normalize_enabled,
            "train": train_changes,
            "validation": validation_changes,
        },
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
        "token_lengths": {
            "train": train_lengths,
            "validation": validation_lengths,
        },
        "train_diagnostic": train_metrics,
        "training": training,
        "validation": validation_metrics,
        "warnings": [
            {
                "category": item.category.__name__,
                "message": str(item.message),
            }
            for item in captured_warnings
        ],
    }
    write_json(metrics_path, result)
    result["artifacts"]["metrics"] = {
        "path": relative_to_project(metrics_path),
        "sha256": sha256(metrics_path),
    }
    log(
        f"{candidate['id']} seed {seed}: "
        f"Macro-F1={validation_metrics['macro']['f1']:.6f}, "
        f"Accuracy={validation_metrics['accuracy']:.6f}"
    )
    del trainer, model, validation_output, train_output
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    return result


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": (
            float(statistics.stdev(values)) if len(values) > 1 else 0.0
        ),
    }


def aggregate_candidate(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accuracy": summarize(
            [item["validation"]["accuracy"] for item in results]
        ),
        "macro_f1": summarize(
            [item["validation"]["macro"]["f1"] for item in results]
        ),
        "macro_precision": summarize(
            [item["validation"]["macro"]["precision"] for item in results]
        ),
        "macro_recall": summarize(
            [item["validation"]["macro"]["recall"] for item in results]
        ),
        "per_class_f1": {
            label: summarize(
                [
                    item["validation"]["per_class"][label]["f1"]
                    for item in results
                ]
            )
            for label in results[0]["validation"]["per_class"]
        },
        "weighted_f1": summarize(
            [item["validation"]["weighted"]["f1"] for item in results]
        ),
    }


def select_minor_candidate(
    promoted: list[dict[str, Any]],
    results_by_candidate: dict[str, list[dict[str, Any]]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    control_id = selection["control_candidate_id"]
    threshold = float(selection["practical_improvement_threshold"])
    aggregates = {
        candidate["id"]: aggregate_candidate(results_by_candidate[candidate["id"]])
        for candidate in promoted
    }
    ranked = sorted(
        promoted,
        key=lambda candidate: (
            -aggregates[candidate["id"]]["macro_f1"]["mean"],
            int(candidate["complexity_rank"]),
            candidate["id"],
        ),
    )
    nominal = ranked[0]
    control = aggregates[control_id]
    nominal_aggregate = aggregates[nominal["id"]]
    delta = (
        nominal_aggregate["macro_f1"]["mean"]
        - control["macro_f1"]["mean"]
    )
    control_by_seed = {
        item["seed"]: item["validation"]["macro"]["f1"]
        for item in results_by_candidate[control_id]
    }
    matched_improvements = sum(
        item["validation"]["macro"]["f1"] > control_by_seed[item["seed"]]
        for item in results_by_candidate[nominal["id"]]
    )
    selected_id = nominal["id"]
    reason = "highest eligible three-seed mean Macro-F1"
    if nominal["id"] != control_id and (
        delta < threshold or matched_improvements < 2
    ):
        selected_id = control_id
        reason = (
            "nominal treatment did not pass the practical delta and "
            "matched-seed improvement gate"
        )
    return {
        "aggregates": aggregates,
        "control_candidate_id": control_id,
        "matched_seed_improvements_over_control": matched_improvements,
        "nominal_candidate_id": nominal["id"],
        "nominal_macro_f1_delta_over_control": float(delta),
        "practical_improvement_threshold": threshold,
        "reason": reason,
        "selected_candidate_id": selected_id,
    }


def run_minor(
    config: dict[str, Any],
    data: dict[str, Any],
    model_snapshot: Path,
    output_dir: Path,
    run_state: dict[str, Any],
) -> dict[str, Any]:
    screening = config["screening"]
    candidates = screening["candidates"]
    by_id = {candidate["id"]: candidate for candidate in candidates}
    control_id = screening["control_candidate_id"]
    if control_id not in by_id:
        raise ValueError("Control candidate is absent")
    planned_seed_runs = len(candidates) + (
        (1 + int(screening["promote_treatment_count"]))
        * len(screening["confirmation_seeds"])
    )
    if planned_seed_runs > int(
        config["resource_budget"]["maximum_seed_runs"]
    ):
        raise ValueError(
            f"Planned {planned_seed_runs} seed runs exceed the budget"
        )

    inner_data = inner_train_split(data, config["data"]["inner_split"])
    results_by_candidate: dict[str, list[dict[str, Any]]] = {
        candidate["id"]: [] for candidate in candidates
    }
    first_seed = int(screening["round_one_seed"])
    for candidate in candidates:
        result = run_training(
            candidate=candidate,
            config=config,
            data=inner_data,
            model_snapshot=model_snapshot,
            output_dir=output_dir,
            retain_checkpoint=False,
            seed=first_seed,
        )
        results_by_candidate[candidate["id"]].append(result)
        run_state["candidate_results"] = results_by_candidate
        write_json(output_dir / "run.json", run_state)

    treatments = [
        candidate for candidate in candidates if candidate["id"] != control_id
    ]
    treatments.sort(
        key=lambda candidate: (
            -results_by_candidate[candidate["id"]][0]["validation"]["macro"][
                "f1"
            ],
            int(candidate["complexity_rank"]),
            candidate["id"],
        )
    )
    promoted = [
        by_id[control_id],
        *treatments[: int(screening["promote_treatment_count"])],
    ]
    for seed in screening["confirmation_seeds"]:
        for candidate in promoted:
            result = run_training(
                candidate=candidate,
                config=config,
                data=inner_data,
                model_snapshot=model_snapshot,
                output_dir=output_dir,
                retain_checkpoint=False,
                seed=int(seed),
            )
            results_by_candidate[candidate["id"]].append(result)
            run_state["candidate_results"] = results_by_candidate
            write_json(output_dir / "run.json", run_state)

    selection = select_minor_candidate(
        promoted,
        results_by_candidate,
        {
            **config["selection"],
            "control_candidate_id": control_id,
        },
    )
    return {
        "candidate_results": results_by_candidate,
        "data_partition": {
            "inner_train_class_distribution": dict(
                sorted(Counter(inner_data["train_labels"]).items())
            ),
            "inner_train_count": len(inner_data["train_labels"]),
            "inner_validation_class_distribution": dict(
                sorted(Counter(inner_data["validation_labels"]).items())
            ),
            "inner_validation_count": len(
                inner_data["validation_labels"]
            ),
            "random_state": config["data"]["inner_split"]["random_state"],
            "validation_fraction": config["data"]["inner_split"][
                "validation_fraction"
            ],
        },
        "promoted_candidate_ids": [
            candidate["id"] for candidate in promoted
        ],
        "selection": selection,
    }


def compare_major(
    config: dict[str, Any],
    seed_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparison = config.get("comparison")
    if comparison is None:
        return {}
    path = project_path(comparison["run_metadata"])
    verify_file(path, comparison["run_metadata_sha256"])
    parent = json.loads(path.read_text(encoding="utf-8"))
    parent_by_seed = {
        item["seed"]: item["validation"]["macro"]["f1"]
        for item in parent["seed_results"]
    }
    deltas = {
        str(item["seed"]): (
            item["validation"]["macro"]["f1"]
            - parent_by_seed[item["seed"]]
        )
        for item in seed_results
    }
    return {
        "experiment_id": comparison["experiment_id"],
        "matched_seed_macro_f1_deltas": deltas,
        "matched_seed_improvement_count": sum(
            value > 0 for value in deltas.values()
        ),
        "mean_macro_f1_delta": float(statistics.fmean(deltas.values())),
        "practical_improvement_threshold": comparison[
            "practical_improvement_threshold"
        ],
        "run_metadata": relative_to_project(path),
        "run_metadata_sha256": sha256(path),
    }


def run_major(
    config: dict[str, Any],
    data: dict[str, Any],
    model_snapshot: Path,
    output_dir: Path,
    run_state: dict[str, Any],
) -> dict[str, Any]:
    formal_data = {
        "train_labels": data["train_labels"],
        "train_row_ids": data["train_row_ids"],
        "train_texts": data["train_texts"],
        "validation_labels": data["validation_labels"],
        "validation_row_ids": data["validation_row_ids"],
        "validation_texts": data["validation_texts"],
    }
    if len(config["seeds"]) > int(
        config["resource_budget"]["maximum_seed_runs"]
    ):
        raise ValueError("Major seed count exceeds the resource budget")
    candidate = {
        "class_weighting": config["training"].get(
            "class_weighting", "none"
        ),
        "classifier_dropout": config["training"].get(
            "classifier_dropout"
        ),
        "complexity_rank": 0,
        "id": config["model_variant_id"],
        "preprocessing": config["preprocessing"],
        "training": config["training"],
    }
    seed_results = []
    for seed in config["seeds"]:
        result = run_training(
            candidate=candidate,
            config=config,
            data=formal_data,
            model_snapshot=model_snapshot,
            output_dir=output_dir,
            retain_checkpoint=True,
            seed=int(seed),
        )
        seed_results.append(result)
        run_state["seed_results"] = seed_results
        write_json(output_dir / "run.json", run_state)
    return {
        "aggregate": aggregate_candidate(seed_results),
        "comparison": compare_major(config, seed_results),
        "seed_results": seed_results,
    }


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    config, config_hash = load_config(config_path)
    prepare_output_dir(output_dir, args.validate_only)
    environment = environment_metadata()
    model = verify_model(config)
    data = load_data(config)

    if args.validate_only:
        print(
            json.dumps(
                {
                    "config_sha256": config_hash,
                    "experiment_id": config["experiment_id"],
                    "model_file_count": len(model["verified_files"]),
                    "status": "Validated",
                    "train_sample_count": len(data["train_labels"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    started_at = utc_now()
    total_started = perf_counter()
    run_path = output_dir / "run.json"
    stdout_path = output_dir / "stdout.log"
    run_state: dict[str, Any] = {
        "accessed_splits": config["data"]["allowed_splits"],
        "created_at_utc": started_at,
        "experiment_id": config["experiment_id"],
        "rq_id": config["rq_id"],
        "stage": config["stage"],
        "status": "Running",
        "test_split_accessed": False,
        "tier": config["tier"],
        "validation_split_accessed": (
            "validation" in config["data"]["allowed_splits"]
        ),
    }
    write_json(run_path, run_state)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    with stdout_path.open("a", encoding="utf-8") as stdout_file:
        sys.stdout = Tee(original_stdout, stdout_file)
        sys.stderr = Tee(original_stderr, stdout_file)
        try:
            log(
                f"{config['experiment_id']} starting; "
                "test access is prohibited"
            )
            if config["tier"] == "Minor":
                result = run_minor(
                    config,
                    data,
                    model["snapshot"],
                    output_dir,
                    run_state,
                )
            else:
                result = run_major(
                    config,
                    data,
                    model["snapshot"],
                    output_dir,
                    run_state,
                )

            total_seconds = perf_counter() - total_started
            protocol_artifact = None
            if config["tier"] == "Major":
                protocol_path = project_path(config["protocol"]["path"])
                protocol_artifact = {
                    "path": relative_to_project(protocol_path),
                    "sha256": sha256(protocol_path),
                }
            final_run = {
                **run_state,
                **result,
                "artifacts": {
                    "config": {
                        "path": relative_to_project(config_path),
                        "sha256": config_hash,
                    },
                    "protocol": protocol_artifact,
                    "runner": {
                        "path": relative_to_project(Path(__file__)),
                        "sha256": sha256(Path(__file__)),
                    },
                    "stdout_log": {
                        "path": relative_to_project(stdout_path),
                    },
                },
                "completed_at_utc": utc_now(),
                "data": {
                    "files_read": {
                        name: {
                            "path": relative_to_project(path),
                            "sha256": sha256(path),
                        }
                        for name, path in data["paths"].items()
                    },
                    "label_mapping": config["data"]["label_mapping"],
                    "train_class_distribution": dict(
                        sorted(Counter(data["train_labels"]).items())
                    ),
                    "train_sample_count": len(data["train_labels"]),
                    "upstream_commit": config["data"]["upstream_commit"],
                    "validation_sample_count": (
                        len(data["validation_labels"])
                        if "validation_labels" in data
                        else 0
                    ),
                },
                "environment": environment,
                "invocation": [sys.executable, *sys.argv],
                "model": {
                    **config["model"],
                    "verified_snapshot_files": model["verified_files"],
                },
                "resource_budget": {
                    **config["resource_budget"],
                    "actual_total_seconds": total_seconds,
                },
                "status": "Completed",
            }
            write_json(run_path, final_run)
            log(
                f"{config['experiment_id']} completed in "
                f"{total_seconds:.1f} seconds"
            )
            log("Test split accessed: no")
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
            log(
                f"{config['experiment_id']} failed: "
                f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == "__main__":
    main()
