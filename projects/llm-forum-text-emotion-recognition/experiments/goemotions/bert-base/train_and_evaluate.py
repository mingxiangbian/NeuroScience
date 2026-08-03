#!/usr/bin/env python3
"""Run frozen EXP-020 BERT-base-cased training on GoEmotions train/dev."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import random
import site
import statistics
import subprocess
import sys
from time import perf_counter
import traceback
from typing import Any, Callable

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
import sklearn
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)
import torch
from torch.optim.lr_scheduler import LambdaLR
from torch.utils.data import DataLoader, Dataset
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer


EXPERIMENT_ID = "EXP-020"
RQ_ID = "RQ-G1"
DATA_PROTOCOL_ID = "DATA-GOE-V1"
SOURCE_REVISION = "8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0"
CONFIG_SHA256 = "8ec432ddecc8e400bed2e676bcfb36649f1f1a48ce8b9c811ebde60f525277d5"
MODEL_MANIFEST_SHA256 = (
    "795076f67146a80a2bd875d198305dcd663c84feccdf314b7b426354a1b6d75b"
)
REQUIREMENTS_LOCK_SHA256 = (
    "123e455840fb9e5e9230cd3eb7feda625a8819c4cd3dbf82b91068a7d60797fd"
)
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
EXP018_MACRO_F1 = 0.20364430957028798

EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXPERIMENT_DIR.parents[2]
REPO_DIR = PROJECT_DIR.parents[1]
DEFAULT_DATA_ROOT = PROJECT_DIR / "data" / "goemotions"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "runs" / "exp-020-bert-base-cased"
CONFIG_PATH = EXPERIMENT_DIR / "configs" / "exp-020-bert-base-cased.json"
PROTOCOL_PATH = (
    EXPERIMENT_DIR / "protocols" / "exp-020-bert-base-cased.md"
)
REQUIREMENTS_LOCK_PATH = EXPERIMENT_DIR / "requirements-lock.txt"
MODEL_ROOT = PROJECT_DIR / "models" / "bert-base-cased"
MODEL_DIR = MODEL_ROOT / "snapshot"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"


class EncodedDataset(Dataset):
    def __init__(
        self, encodings: dict[str, torch.Tensor], targets: np.ndarray
    ) -> None:
        self.encodings = encodings
        self.targets = torch.from_numpy(targets.astype(np.float32, copy=False))

    def __len__(self) -> int:
        return self.targets.shape[0]

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        item = {key: value[index] for key, value in self.encodings.items()}
        item["labels"] = self.targets[index]
        return item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def prepare_output_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {path}. EXP-020 is append-only."
        )
    path.mkdir(parents=True, exist_ok=True)


def setup_logger(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-020")
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


def git_metadata() -> dict[str, Any]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(REPO_DIR), *args],
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


def verify_hash(path: Path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected}, got {actual}"
        )
    return {"bytes": path.stat().st_size, "path": project_path(path), "sha256": actual}


def environment_gate() -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise RuntimeError("PYTHONNOUSERSITE=1 is required")
    if os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 is required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user site is enabled")
    user_site = str(Path(site.getusersitepackages()).resolve())
    resolved_sys_path = {
        str(Path(entry).resolve()) for entry in sys.path if entry
    }
    if user_site in resolved_sys_path:
        raise RuntimeError("Python user-site directory is present in sys.path")

    prefix = Path(sys.prefix).resolve()
    module_paths = {
        "numpy": Path(np.__file__).resolve(),
        "scikit-learn": Path(sklearn.__file__).resolve(),
        "torch": Path(torch.__file__).resolve(),
        "transformers": Path(transformers.__file__).resolve(),
    }
    outside_prefix = {
        name: str(path)
        for name, path in module_paths.items()
        if prefix not in path.parents
    }
    if outside_prefix:
        raise RuntimeError(f"Dependencies outside environment: {outside_prefix}")

    verify_hash(REQUIREMENTS_LOCK_PATH, REQUIREMENTS_LOCK_SHA256)
    frozen = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected_frozen = REQUIREMENTS_LOCK_PATH.read_text(
        encoding="utf-8"
    ).strip()
    if frozen != expected_frozen:
        raise RuntimeError("Runtime pip freeze differs from requirements-lock.txt")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    if not torch.backends.mps.is_built():
        raise RuntimeError("PyTorch was not built with MPS")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable in this process")

    return {
        "architecture": platform.machine(),
        "device": "mps",
        "environment_prefix": str(prefix),
        "executable": sys.executable,
        "mps_available": True,
        "mps_built": True,
        "package_paths": {
            name: str(path) for name, path in module_paths.items()
        },
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "numpy",
                "safetensors",
                "scikit-learn",
                "torch",
                "transformers",
            )
        },
        "pip_check": pip_check or "No broken requirements found.",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_no_user_site": True,
        "requirements_lock": verify_hash(
            REQUIREMENTS_LOCK_PATH, REQUIREMENTS_LOCK_SHA256
        ),
    }


def verify_model_manifest() -> dict[str, Any]:
    verify_hash(MODEL_MANIFEST_PATH, MODEL_MANIFEST_SHA256)
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest["repo_id"] != "google-bert/bert-base-cased":
        raise ValueError("Unexpected model repository")
    if manifest["revision"] != "cd5ef92a9fb2f889e972770a36d4ed042daf221e":
        raise ValueError("Unexpected model revision")
    verified = []
    for expected in manifest["files"]:
        path = MODEL_DIR / expected["path"]
        actual = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if actual != expected:
            raise ValueError(
                f"Model file differs from manifest: {expected['path']}"
            )
        verified.append(actual)
    return {
        "files": verified,
        "manifest": verify_hash(MODEL_MANIFEST_PATH, MODEL_MANIFEST_SHA256),
        "repo_id": manifest["repo_id"],
        "revision": manifest["revision"],
        "snapshot": project_path(MODEL_DIR),
    }


def verify_config() -> dict[str, Any]:
    record = verify_hash(CONFIG_PATH, CONFIG_SHA256)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != EXPERIMENT_ID:
        raise ValueError("Config experiment ID mismatch")
    if config["data"]["allowed_splits"] != ["train", "dev"]:
        raise ValueError("Config split allowlist changed")
    if config["data"]["forbidden_split"] != "test":
        raise ValueError("Config test boundary changed")
    return {"contents": config, "record": record}


def verify_data_manifest(data_root: Path) -> dict[str, Any]:
    manifest_path = data_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != DATA_PROTOCOL_ID:
        raise ValueError("GoEmotions data protocol mismatch")
    if manifest.get("status") != "verified":
        raise ValueError("GoEmotions data manifest is not verified")
    if manifest["source"]["revision"] != SOURCE_REVISION:
        raise ValueError("GoEmotions source revision mismatch")
    test = manifest["splits"]["test"]
    if test.get("status") != "not_acquired" or test.get("exists") is not False:
        raise ValueError("Manifest does not keep test unacquired")
    test_path = data_root / "official" / "test.tsv"
    if test_path.exists():
        raise RuntimeError("test.tsv exists; EXP-020 must stop before reading data")

    files = {}
    for name, expected in EXPECTED_HASHES.items():
        files[name] = verify_hash(data_root / "official" / name, expected)
    files["manifest.json"] = {
        "bytes": manifest_path.stat().st_size,
        "path": project_path(manifest_path),
        "sha256": sha256_file(manifest_path),
    }
    return {"contents": manifest, "files": files}


def load_labels(path: Path) -> tuple[str, ...]:
    labels = tuple(path.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order differs from EXP-020")
    return labels


def load_split(
    path: Path, expected_rows: int, label_count: int
) -> tuple[list[str], np.ndarray, set[str], dict[str, Any]]:
    texts: list[str] = []
    targets = np.zeros((expected_rows, label_count), dtype=np.uint8)
    comment_ids: set[str] = set()
    cardinality: Counter[int] = Counter()

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError(f"{path.name} has too many rows")
            if len(row) != 3:
                raise ValueError(
                    f"{path.name} row {row_number} has {len(row)} columns"
                )
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"{path.name} row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError(f"{path.name} repeats a comment ID")
            comment_ids.add(comment_id)
            try:
                label_ids = tuple(int(item) for item in encoded_labels.split(","))
            except ValueError as error:
                raise ValueError(
                    f"{path.name} row {row_number} has invalid labels"
                ) from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(
                    f"{path.name} row {row_number} has empty or duplicate labels"
                )
            if any(label_id < 0 or label_id >= label_count for label_id in label_ids):
                raise ValueError(
                    f"{path.name} row {row_number} has out-of-range labels"
                )
            texts.append(text)
            targets[row_index, list(label_ids)] = 1
            cardinality[len(label_ids)] += 1

    if len(texts) != expected_rows:
        raise ValueError(
            f"{path.name} has {len(texts)} rows; expected {expected_rows}"
        )
    return texts, targets, comment_ids, {
        "label_cardinality": {
            str(key): value for key, value in sorted(cardinality.items())
        },
        "rows": len(texts),
        "unique_comment_ids": len(comment_ids),
    }


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def compute_metrics(
    gold: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]
) -> tuple[dict[str, Any], np.ndarray]:
    averages: dict[str, dict[str, float]] = {}
    for average in ("macro", "micro", "weighted", "samples"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold, predicted, average=average, zero_division=0
        )
        averages[average] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }

    precision, recall, f1, support = precision_recall_fscore_support(
        gold, predicted, average=None, zero_division=0
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

    subset_accuracy = float(accuracy_score(gold, predicted))
    loss = float(hamming_loss(gold, predicted))
    gold_cardinality = gold.sum(axis=1)
    predicted_cardinality = predicted.sum(axis=1)
    metrics: dict[str, Any] = {
        "accuracy": subset_accuracy,
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
        "subset_accuracy": subset_accuracy,
    }
    return metrics, multilabel_confusion_matrix(gold, predicted)


def move_batch(
    batch: dict[str, torch.Tensor], device: torch.device
) -> dict[str, torch.Tensor]:
    return {key: value.to(device) for key, value in batch.items()}


def evaluate(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    gold: np.ndarray,
    labels: tuple[str, ...],
    threshold: float,
) -> tuple[float, np.ndarray, dict[str, Any], np.ndarray]:
    model.eval()
    losses = 0.0
    examples = 0
    probability_batches: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            moved = move_batch(batch, device)
            output = model(**moved)
            if output.loss is None:
                raise RuntimeError("Evaluation loss is missing")
            batch_size = moved["labels"].shape[0]
            losses += float(output.loss.detach().cpu()) * batch_size
            examples += batch_size
            probability_batches.append(
                torch.sigmoid(output.logits).detach().cpu().numpy()
            )
    torch.mps.synchronize()
    probabilities = np.concatenate(probability_batches, axis=0)
    if probabilities.shape != gold.shape:
        raise ValueError(
            f"Probability shape {probabilities.shape} != gold {gold.shape}"
        )
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("Evaluation probabilities contain NaN or Inf")
    predicted = (probabilities >= threshold).astype(np.uint8)
    metrics, confusion = compute_metrics(gold, predicted, labels)
    return losses / examples, probabilities, metrics, confusion


def write_predictions(
    path: Path,
    gold: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    labels: tuple[str, ...],
) -> None:
    predicted = (probabilities >= threshold).astype(np.uint8)
    header = [
        "row_number",
        "gold_label_ids",
        "gold_labels",
        "predicted_label_ids",
        "predicted_labels",
        *(f"prob_{label}" for label in labels),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
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
                    *(format(float(value), ".17g") for value in probabilities[row_index]),
                ]
            )


def write_per_label(
    path: Path, metrics: dict[str, Any], labels: tuple[str, ...]
) -> None:
    fields = [
        "label_id",
        "label",
        "precision",
        "recall",
        "f1",
        "support",
        "predicted_support",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label in labels:
            record = metrics["per_label"][label]
            writer.writerow(
                {
                    "label_id": record["label_id"],
                    "label": label,
                    "precision": format(record["precision"], ".17g"),
                    "recall": format(record["recall"], ".17g"),
                    "f1": format(record["f1"], ".17g"),
                    "support": record["support"],
                    "predicted_support": record["predicted_support"],
                }
            )


def write_confusion(
    path: Path, confusion: np.ndarray, labels: tuple[str, ...]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label_id", "label", "tn", "fp", "fn", "tp"])
        for index, label in enumerate(labels):
            tn, fp, fn, tp = confusion[index].ravel()
            writer.writerow(
                [index, label, int(tn), int(fp), int(fn), int(tp)]
            )


def write_history(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "seed",
        "epoch",
        "optimizer_steps",
        "train_loss",
        "dev_loss",
        "learning_rate_end",
        "macro_precision",
        "macro_recall",
        "macro_f1",
        "micro_f1",
        "weighted_f1",
        "samples_f1",
        "subset_accuracy",
        "hamming_loss",
        "predicted_label_cardinality",
        "empty_prediction_rows",
        "epoch_seconds",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def metric_value(metrics: dict[str, Any], path: str) -> float:
    value: Any = metrics
    for key in path.split("."):
        value = value[key]
    return float(value)


def summary_stats(values_by_seed: dict[str, float]) -> dict[str, Any]:
    values = list(values_by_seed.values())
    return {
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
        "values_by_seed": values_by_seed,
    }


def create_optimizer(
    model: torch.nn.Module, config: dict[str, Any]
) -> torch.optim.Optimizer:
    decay_parameters = []
    no_decay_parameters = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.endswith("bias") or "LayerNorm.weight" in name:
            no_decay_parameters.append(parameter)
        else:
            decay_parameters.append(parameter)
    groups = [
        {
            "params": decay_parameters,
            "weight_decay": config["weight_decay"],
        },
        {"params": no_decay_parameters, "weight_decay": 0.0},
    ]
    return torch.optim.AdamW(
        groups,
        lr=config["learning_rate"],
        betas=(config["adam_beta1"], config["adam_beta2"]),
        eps=config["adam_epsilon"],
    )


def create_scheduler(
    optimizer: torch.optim.Optimizer, total_steps: int, warmup_steps: int
) -> LambdaLR:
    def scale(step: int) -> float:
        if step < warmup_steps:
            return float(step) / float(max(1, warmup_steps))
        return max(
            0.0,
            float(total_steps - step)
            / float(max(1, total_steps - warmup_steps)),
        )

    return LambdaLR(optimizer, scale)


def train_seed(
    seed: int,
    config: dict[str, Any],
    train_dataset: EncodedDataset,
    dev_dataset: EncodedDataset,
    dev_gold: np.ndarray,
    labels: tuple[str, ...],
    output_dir: Path,
    logger: logging.Logger,
    global_started: float,
) -> dict[str, Any]:
    seed_started = perf_counter()
    seed_everything(seed)
    seed_dir = output_dir / f"seed-{seed}"
    seed_dir.mkdir(parents=True, exist_ok=False)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_DIR,
        attention_probs_dropout_prob=config["model"]["attention_dropout"],
        classifier_dropout=config["model"]["classifier_dropout"],
        hidden_dropout_prob=config["model"]["hidden_dropout"],
        id2label={index: label for index, label in enumerate(labels)},
        label2id={label: index for index, label in enumerate(labels)},
        local_files_only=True,
        num_labels=len(labels),
        problem_type="multi_label_classification",
    )
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    trainable_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    device = torch.device("mps")
    model.to(device)

    training = config["training"]
    generator = torch.Generator()
    generator.manual_seed(seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=training["train_batch_size"],
        drop_last=training["drop_last"],
        generator=generator,
        num_workers=training["num_workers"],
        pin_memory=False,
        shuffle=training["shuffle"],
    )
    dev_loader = DataLoader(
        dev_dataset,
        batch_size=training["evaluation_batch_size"],
        drop_last=False,
        num_workers=training["num_workers"],
        pin_memory=False,
        shuffle=False,
    )
    batches_per_epoch = len(train_loader)
    expected_batches = EXPECTED_ROWS["train"] // training["train_batch_size"]
    if batches_per_epoch != expected_batches:
        raise ValueError(
            f"Unexpected train batches: {batches_per_epoch} != {expected_batches}"
        )
    total_steps = batches_per_epoch * training["epochs"]
    warmup_steps = int(total_steps * training["warmup_ratio"])
    optimizer = create_optimizer(model, training)
    scheduler = create_scheduler(optimizer, total_steps, warmup_steps)

    logger.info(
        "Seed %d started: %d steps, %d warmup steps",
        seed,
        total_steps,
        warmup_steps,
    )
    history: list[dict[str, Any]] = []
    global_step = 0
    final_probabilities: np.ndarray | None = None
    final_metrics: dict[str, Any] | None = None
    final_confusion: np.ndarray | None = None
    final_dev_loss: float | None = None

    for epoch in range(1, training["epochs"] + 1):
        epoch_started = perf_counter()
        model.train()
        loss_sum = 0.0
        example_count = 0
        for batch_index, batch in enumerate(train_loader, start=1):
            if perf_counter() - global_started > (
                config["resource_budget"]["maximum_wall_minutes"] * 60
            ):
                raise TimeoutError("EXP-020 exceeded the 360-minute budget")
            moved = move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)
            output = model(**moved)
            if output.loss is None:
                raise RuntimeError("Training loss is missing")
            loss = output.loss
            loss_value = float(loss.detach().cpu())
            if not math.isfinite(loss_value):
                raise ValueError(
                    f"Non-finite loss at seed {seed}, step {global_step + 1}"
                )
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), training["max_grad_norm"]
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise ValueError(
                    f"Non-finite gradient norm at seed {seed}, "
                    f"step {global_step + 1}"
                )
            optimizer.step()
            scheduler.step()

            batch_size = moved["labels"].shape[0]
            loss_sum += loss_value * batch_size
            example_count += batch_size
            global_step += 1
            if batch_index % 250 == 0 or batch_index == batches_per_epoch:
                logger.info(
                    "Seed %d epoch %d step %d/%d loss %.6f lr %.8g",
                    seed,
                    epoch,
                    batch_index,
                    batches_per_epoch,
                    loss_sum / example_count,
                    optimizer.param_groups[0]["lr"],
                )

        torch.mps.synchronize()
        train_loss = loss_sum / example_count
        (
            dev_loss,
            probabilities,
            metrics,
            confusion,
        ) = evaluate(
            model,
            dev_loader,
            device,
            dev_gold,
            labels,
            config["evaluation"]["threshold"],
        )
        epoch_seconds = perf_counter() - epoch_started
        history.append(
            {
                "dev_loss": format(dev_loss, ".17g"),
                "empty_prediction_rows": metrics["prediction_diagnostics"][
                    "empty_prediction_rows"
                ],
                "epoch": epoch,
                "epoch_seconds": format(epoch_seconds, ".17g"),
                "hamming_loss": format(metrics["hamming_loss"], ".17g"),
                "learning_rate_end": format(
                    optimizer.param_groups[0]["lr"], ".17g"
                ),
                "macro_f1": format(metrics["macro"]["f1"], ".17g"),
                "macro_precision": format(
                    metrics["macro"]["precision"], ".17g"
                ),
                "macro_recall": format(metrics["macro"]["recall"], ".17g"),
                "micro_f1": format(metrics["micro"]["f1"], ".17g"),
                "optimizer_steps": global_step,
                "predicted_label_cardinality": format(
                    metrics["label_cardinality"]["predicted_mean"], ".17g"
                ),
                "samples_f1": format(metrics["samples"]["f1"], ".17g"),
                "seed": seed,
                "subset_accuracy": format(metrics["subset_accuracy"], ".17g"),
                "train_loss": format(train_loss, ".17g"),
                "weighted_f1": format(metrics["weighted"]["f1"], ".17g"),
            }
        )
        logger.info(
            "Seed %d epoch %d complete: train_loss=%.6f dev_loss=%.6f "
            "macro_f1=%.6f micro_f1=%.6f seconds=%.1f",
            seed,
            epoch,
            train_loss,
            dev_loss,
            metrics["macro"]["f1"],
            metrics["micro"]["f1"],
            epoch_seconds,
        )
        if epoch == training["epochs"]:
            final_probabilities = probabilities
            final_metrics = metrics
            final_confusion = confusion
            final_dev_loss = dev_loss

    if (
        final_probabilities is None
        or final_metrics is None
        or final_confusion is None
        or final_dev_loss is None
    ):
        raise RuntimeError("Final epoch outputs were not retained")

    final_model_dir = seed_dir / "final-model"
    model.save_pretrained(final_model_dir, safe_serialization=True)
    model_path = final_model_dir / "model.safetensors"
    if not model_path.is_file():
        raise FileNotFoundError("Final safetensors model was not written")

    history_path = seed_dir / "history.csv"
    predictions_path = seed_dir / "predictions.csv"
    per_label_path = seed_dir / "per_label_metrics.csv"
    confusion_path = seed_dir / "multilabel_confusion_matrix.csv"
    metrics_path = seed_dir / "metrics.json"
    write_history(history_path, history)
    write_predictions(
        predictions_path,
        dev_gold,
        final_probabilities,
        config["evaluation"]["threshold"],
        labels,
    )
    write_per_label(per_label_path, final_metrics, labels)
    write_confusion(confusion_path, final_confusion, labels)

    seed_seconds = perf_counter() - seed_started
    seed_payload = {
        "artifacts": {},
        "checkpoint_rule": config["evaluation"]["checkpoint_rule"],
        "dev_loss": final_dev_loss,
        "final_epoch": training["epochs"],
        "metrics": final_metrics,
        "model": {
            "classification_head": "newly initialized 28-label head",
            "final_model": artifact(model_path),
            "parameter_count": parameter_count,
            "trainable_parameter_count": trainable_count,
        },
        "optimizer_steps": total_steps,
        "runtime_seconds": seed_seconds,
        "seed": seed,
        "threshold": config["evaluation"]["threshold"],
        "train_examples_per_epoch": batches_per_epoch
        * training["train_batch_size"],
        "warmup_steps": warmup_steps,
    }
    atomic_json(metrics_path, seed_payload)
    seed_payload["artifacts"] = {
        "confusion_matrix": artifact(confusion_path),
        "history": artifact(history_path),
        "per_label_metrics": artifact(per_label_path),
        "predictions": artifact(predictions_path),
    }
    atomic_json(metrics_path, seed_payload)
    seed_payload["metrics_artifact"] = artifact(metrics_path)

    logger.info(
        "Seed %d complete: final macro_f1=%.6f model_sha=%s runtime=%.1fs",
        seed,
        final_metrics["macro"]["f1"],
        seed_payload["model"]["final_model"]["sha256"][:12],
        seed_seconds,
    )

    del optimizer, scheduler, model, train_loader, dev_loader
    gc.collect()
    torch.mps.empty_cache()
    return seed_payload


def aggregate_results(
    seed_results: list[dict[str, Any]], labels: tuple[str, ...]
) -> dict[str, Any]:
    metric_paths = {
        "hamming_loss": "hamming_loss",
        "label_accuracy": "label_accuracy",
        "macro_f1": "macro.f1",
        "macro_precision": "macro.precision",
        "macro_recall": "macro.recall",
        "micro_f1": "micro.f1",
        "predicted_label_cardinality": "label_cardinality.predicted_mean",
        "samples_f1": "samples.f1",
        "subset_accuracy": "subset_accuracy",
        "weighted_f1": "weighted.f1",
    }
    validation = {
        name: summary_stats(
            {
                str(result["seed"]): metric_value(result["metrics"], path)
                for result in seed_results
            }
        )
        for name, path in metric_paths.items()
    }
    validation["empty_prediction_rows"] = summary_stats(
        {
            str(result["seed"]): float(
                result["metrics"]["prediction_diagnostics"][
                    "empty_prediction_rows"
                ]
            )
            for result in seed_results
        }
    )
    per_label = {}
    for label in labels:
        per_label[label] = {
            metric: summary_stats(
                {
                    str(result["seed"]): float(
                        result["metrics"]["per_label"][label][metric]
                    )
                    for result in seed_results
                }
            )
            for metric in ("precision", "recall", "f1")
        }
        per_label[label]["support"] = seed_results[0]["metrics"]["per_label"][
            label
        ]["support"]

    delta = validation["macro_f1"]["mean"] - EXP018_MACRO_F1
    return {
        "comparison": {
            "baseline": "EXP-018",
            "baseline_dev_macro_f1": EXP018_MACRO_F1,
            "mean_macro_f1_delta": delta,
            "practical_improvement": delta >= 0.005,
            "practical_threshold": 0.005,
        },
        "external_reference": {
            "directly_comparable": False,
            "paper_bert_macro_f1": 0.46,
            "paper_split": "test",
            "reason": "EXP-020 evaluates dev; official 0.46 is a test result.",
        },
        "per_label": per_label,
        "sample_standard_deviation": True,
        "seeds": [result["seed"] for result in seed_results],
        "validation": validation,
    }


def write_seed_summary(
    path: Path, seed_results: list[dict[str, Any]]
) -> None:
    fields = [
        "seed",
        "macro_f1",
        "macro_precision",
        "macro_recall",
        "micro_f1",
        "weighted_f1",
        "samples_f1",
        "subset_accuracy",
        "hamming_loss",
        "predicted_label_cardinality",
        "empty_prediction_rows",
        "dev_loss",
        "runtime_seconds",
        "model_sha256",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in seed_results:
            metrics = result["metrics"]
            writer.writerow(
                {
                    "dev_loss": format(result["dev_loss"], ".17g"),
                    "empty_prediction_rows": metrics["prediction_diagnostics"][
                        "empty_prediction_rows"
                    ],
                    "hamming_loss": format(metrics["hamming_loss"], ".17g"),
                    "macro_f1": format(metrics["macro"]["f1"], ".17g"),
                    "macro_precision": format(
                        metrics["macro"]["precision"], ".17g"
                    ),
                    "macro_recall": format(
                        metrics["macro"]["recall"], ".17g"
                    ),
                    "micro_f1": format(metrics["micro"]["f1"], ".17g"),
                    "model_sha256": result["model"]["final_model"]["sha256"],
                    "predicted_label_cardinality": format(
                        metrics["label_cardinality"]["predicted_mean"], ".17g"
                    ),
                    "runtime_seconds": format(
                        result["runtime_seconds"], ".17g"
                    ),
                    "samples_f1": format(metrics["samples"]["f1"], ".17g"),
                    "seed": result["seed"],
                    "subset_accuracy": format(
                        metrics["subset_accuracy"], ".17g"
                    ),
                    "weighted_f1": format(
                        metrics["weighted"]["f1"], ".17g"
                    ),
                }
            )


def run() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    output_dir = args.output_dir.resolve()
    prepare_output_dir(output_dir)
    logger = setup_logger(output_dir)
    run_path = output_dir / "run.json"
    started_at = datetime.now(timezone.utc)
    started = perf_counter()

    run_record: dict[str, Any] = {
        "accessed_splits": [],
        "experiment_id": EXPERIMENT_ID,
        "invocation": [sys.executable, *sys.argv],
        "rq_id": RQ_ID,
        "stage": "train-dev",
        "started_at_utc": started_at.isoformat(),
        "status": "Running",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
    }
    atomic_json(run_path, run_record)

    try:
        logger.info("EXP-020 preflight started")
        environment = environment_gate()
        config_bundle = verify_config()
        config = config_bundle["contents"]
        model_record = verify_model_manifest()
        data_bundle = verify_data_manifest(data_root)
        data_manifest = data_bundle["contents"]
        logger.info("Environment, model, config, and data hashes verified")

        labels = load_labels(data_root / "official" / "emotions.txt")
        train_texts, train_targets, train_ids, train_stats = load_split(
            data_root / "official" / "train.tsv",
            EXPECTED_ROWS["train"],
            len(labels),
        )
        dev_texts, dev_targets, dev_ids, dev_stats = load_split(
            data_root / "official" / "dev.tsv",
            EXPECTED_ROWS["dev"],
            len(labels),
        )
        if train_ids & dev_ids:
            raise ValueError("Train/dev comment-ID overlap detected")
        del train_ids, dev_ids
        logger.info(
            "Loaded frozen train/dev: %d/%d rows, 28 labels",
            len(train_texts),
            len(dev_texts),
        )

        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_DIR, local_files_only=True
        )
        max_length = config["training"]["max_sequence_length"]
        tokenization_started = perf_counter()
        train_encodings = tokenizer(
            train_texts,
            max_length=max_length,
            padding="max_length",
            return_tensors="pt",
            truncation=True,
        )
        dev_encodings = tokenizer(
            dev_texts,
            max_length=max_length,
            padding="max_length",
            return_tensors="pt",
            truncation=True,
        )
        tokenization_seconds = perf_counter() - tokenization_started
        del train_texts, dev_texts
        train_dataset = EncodedDataset(train_encodings, train_targets)
        dev_dataset = EncodedDataset(dev_encodings, dev_targets)
        logger.info(
            "Tokenization complete in %.2fs; tensor shapes train=%s dev=%s",
            tokenization_seconds,
            tuple(train_encodings["input_ids"].shape),
            tuple(dev_encodings["input_ids"].shape),
        )

        seed_results = []
        for seed in config["training"]["seeds"]:
            seed_results.append(
                train_seed(
                    seed,
                    config,
                    train_dataset,
                    dev_dataset,
                    dev_targets,
                    labels,
                    output_dir,
                    logger,
                    started,
                )
            )

        aggregate = aggregate_results(seed_results, labels)
        aggregate_path = output_dir / "aggregate_metrics.json"
        seed_summary_path = output_dir / "seed_summary.csv"
        atomic_json(aggregate_path, aggregate)
        write_seed_summary(seed_summary_path, seed_results)

        finished_at = datetime.now(timezone.utc)
        run_record.update(
            {
                "accessed_splits": ["train", "dev"],
                "artifacts": {
                    "aggregate_metrics": artifact(aggregate_path),
                    "config": config_bundle["record"],
                    "implementation": artifact(Path(__file__).resolve()),
                    "model_manifest": model_record["manifest"],
                    "protocol": artifact(PROTOCOL_PATH),
                    "requirements_lock": environment["requirements_lock"],
                    "seed_summary": artifact(seed_summary_path),
                    "stdout_log": {
                        "path": project_path(output_dir / "stdout.log")
                    },
                },
                "comparison": aggregate["comparison"],
                "data": {
                    "cross_split": data_manifest["cross_split"],
                    "dev": dev_stats,
                    "files_read": data_bundle["files"],
                    "label_count": len(labels),
                    "labels": list(labels),
                    "protocol_id": DATA_PROTOCOL_ID,
                    "source_revision": SOURCE_REVISION,
                    "test": {
                        "exists": False,
                        "path": project_path(
                            data_root / "official" / "test.tsv"
                        ),
                        "status": "not_acquired",
                    },
                    "train": train_stats,
                },
                "environment": environment,
                "finished_at_utc": finished_at.isoformat(),
                "git": git_metadata(),
                "model": model_record,
                "resource_usage": {
                    "api_cost_usd": 0,
                    "device": "mps",
                    "tokenization_seconds": tokenization_seconds,
                    "total_seconds": perf_counter() - started,
                },
                "seed_runs": seed_results,
                "status": "Completed",
                "test_split_accessed": False,
                "validation_split_accessed": True,
                "warnings": [
                    "EXP-020 dev is not directly comparable to the paper's test Macro-F1 0.46.",
                    "This modern PyTorch/MPS reproduction is not bitwise identical to the original TensorFlow estimator.",
                    "The final epoch-4 checkpoint is fixed; dev history was not used for checkpoint selection.",
                ],
            }
        )
        atomic_json(run_path, run_record)
        logger.info(
            "EXP-020 completed: mean dev Macro-F1 %.6f +/- %.6f; "
            "total %.1fs",
            aggregate["validation"]["macro_f1"]["mean"],
            aggregate["validation"]["macro_f1"]["sample_std"],
            run_record["resource_usage"]["total_seconds"],
        )
    except Exception as error:
        run_record.update(
            {
                "error": {
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                    "type": type(error).__name__,
                },
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "resource_usage": {"total_seconds": perf_counter() - started},
                "status": "Failed",
                "test_split_accessed": False,
            }
        )
        atomic_json(run_path, run_record)
        logger.exception("EXP-020 failed")
        raise


if __name__ == "__main__":
    run()
