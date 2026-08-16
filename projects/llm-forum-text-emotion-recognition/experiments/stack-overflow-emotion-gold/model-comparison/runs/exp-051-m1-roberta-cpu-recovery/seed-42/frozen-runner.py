#!/usr/bin/env python3
"""Run one authorized EXP-051 RoBERTa seed on train and validation."""

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
import resource
import shutil
import site
import subprocess
import sys
import time
import traceback
from typing import Any, Iterable, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

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
from torch.utils.data import DataLoader, Dataset, Subset
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-051-m1-roberta-seed-42.json"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
EXPECTED_FIELDS = {
    "component_id",
    "label_cardinality",
    "labels",
    "neutral",
    "protocol_id",
    "sample_id",
    "schema_version",
    "text",
}
FROZEN_FILES = {
    "config": DEFAULT_CONFIG,
    "shared-config": SCRIPT_DIR / "config.json",
    "protocol": SCRIPT_DIR.parent / "protocols" / "exp-051-m1-roberta.md",
    "runner": SCRIPT_DIR / "run_exp051_m1.py",
    "verifier": SCRIPT_DIR / "verify_exp051_m1.py",
    "tests": SCRIPT_DIR / "tests" / "test_exp051_m1.py",
}


class EncodedDataset(Dataset):
    def __init__(self, encodings: dict[str, list[list[int]]], labels: np.ndarray) -> None:
        self.encodings = encodings
        self.labels = labels.astype(np.float32, copy=False)

    def __len__(self) -> int:
        return self.labels.shape[0]

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: value[index] for key, value in self.encodings.items()}
        item["labels"] = self.labels[index]
        return item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--private-dir", type=Path)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def tensor_digest(parameters: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(parameters.items()):
        array = tensor.detach().cpu().float().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else PROJECT_ROOT / path


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def tree_artifact(path: Path) -> dict[str, Any]:
    files = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        files.append(
            {
                "bytes": item.stat().st_size,
                "path": str(item.relative_to(path)),
                "sha256": sha256_file(item),
            }
        )
    return {
        "file_count": len(files),
        "path": project_path(path),
        "sha256": canonical_digest(files),
        "files": files,
    }


def require_hash(path: Path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"Hash mismatch for {path}: expected {expected}, got {observed}")
    return artifact(path)


def load_config(path: Path, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    run_config = json.loads(path.read_text(encoding="utf-8"))
    if run_config["experiment_id"] != "EXP-051":
        raise ValueError("Unexpected experiment identity")
    authorization = run_config["authorization"]
    if seed not in authorization["seeds"] or seed not in (42, 43, 44):
        raise PermissionError(f"Seed {seed} is not authorized")
    if authorization["splits"] != ["train", "validation"]:
        raise PermissionError("Only train and validation are authorized")
    if authorization["test_access"] is not False:
        raise PermissionError("EXP-051 run contract must deny test access")

    shared_path = resolve_project(run_config["prerequisite"]["shared_config_path"])
    require_hash(shared_path, run_config["prerequisite"]["shared_config_sha256"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    if tuple(shared["evaluation"]["seeds"]) != (42, 43, 44):
        raise ValueError("Shared seed contract drift")
    if tuple(shared["data"]["model_access_whitelist"]) != ("train", "validation"):
        raise ValueError("Shared split allowlist drift")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared contract no longer seals test")
    return run_config, shared


def prepare_dirs(run_dir: Path, private_dir: Path) -> None:
    for path in (run_dir, private_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite append-only output: {path}")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)


def setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-051")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(run_dir / "stdout.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def flush_logger(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def git_metadata() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()

    status = git("status", "--short")
    return {
        "branch": git("branch", "--show-current") or "detached",
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "dirty_path_count": len(status.splitlines()) if status else 0,
    }


def environment_gate(run_dir: Path, execution: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1" or os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 and PYTHONNOUSERSITE=1 are required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user site is enabled")
    prefix = Path(sys.prefix).resolve()
    package_paths = {
        "numpy": Path(np.__file__).resolve(),
        "scikit-learn": Path(sklearn.__file__).resolve(),
        "torch": Path(torch.__file__).resolve(),
        "transformers": Path(transformers.__file__).resolve(),
    }
    outside = {name: str(path) for name, path in package_paths.items() if prefix not in path.parents}
    if outside:
        raise RuntimeError(f"Dependencies outside active environment: {outside}")
    device = execution["required_device"]
    if device not in ("mps", "cpu"):
        raise ValueError("EXP-051 supports only the registered MPS or CPU backend")
    if device == "mps" and (
        not torch.backends.mps.is_built() or not torch.backends.mps.is_available()
    ):
        raise RuntimeError("MPS is unavailable in this process")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise RuntimeError("Offline model mode is required")

    frozen = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True, text=True
    ).stdout.strip()
    freeze_path = run_dir / "environment-freeze.txt"
    freeze_path.write_text(frozen + "\n", encoding="utf-8")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return {
        "architecture": platform.machine(),
        "device": device,
        "environment_prefix": str(prefix),
        "executable": sys.executable,
        "mps_available": True,
        "mps_built": True,
        "package_paths": {name: str(path) for name, path in package_paths.items()},
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "safetensors", "scikit-learn", "torch", "transformers")
        },
        "pip_check": pip_check or "No broken requirements found.",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_no_user_site": True,
        "freeze": artifact(freeze_path),
    }


def verify_prerequisite(run_config: dict[str, Any]) -> dict[str, Any]:
    prerequisite = run_config["prerequisite"]
    run_path = resolve_project(prerequisite["run_path"])
    verification_path = resolve_project(prerequisite["verification_path"])
    run_record = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    require_hash(run_path, prerequisite["run_sha256"])
    require_hash(verification_path, prerequisite["verification_sha256"])
    if run_record["status"] != "Passed" or verification["status"] != "Passed":
        raise RuntimeError("EXP-050 is not verified")
    if len(verification["checks"]) != prerequisite["check_count"]:
        raise ValueError("EXP-050 verification count drift")
    return {
        "experiment_id": prerequisite["experiment_id"],
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "verification_check_count": len(verification["checks"]),
    }


def verify_recovery_preflight(
    run_config: dict[str, Any], config_path: Path
) -> dict[str, Any] | None:
    recovery = run_config.get("recovery")
    if recovery is None:
        return None
    if run_config["execution"]["required_device"] != "cpu":
        raise ValueError("Recovery contract must use the registered CPU backend")
    failed_run_path = resolve_project(recovery["failed_run_path"])
    failed_log_path = resolve_project(recovery["failed_log_path"])
    require_hash(failed_run_path, recovery["failed_run_sha256"])
    require_hash(failed_log_path, recovery["failed_log_sha256"])
    failed = json.loads(failed_run_path.read_text(encoding="utf-8"))
    if failed["status"] != "Failed" or "out of memory" not in failed["failure"]["message"].lower():
        raise ValueError("Recorded MPS recovery incident drift")
    if failed["test_split_accessed"] is not False:
        raise PermissionError("Failed MPS attempt does not prove test remained sealed")

    preflight_dir = resolve_project(recovery["cpu_preflight_output"])
    preflight_path = preflight_dir / "run.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    required = {
        "status": "Passed",
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
    }
    for key, expected in required.items():
        if preflight.get(key) != expected:
            raise ValueError(f"CPU recovery preflight gate failed: {key}")
    if preflight["environment"]["device"] != "cpu":
        raise ValueError("CPU recovery preflight used the wrong device")
    if preflight["preflight"]["steps"] != recovery["cpu_train_only_preflight_steps"]:
        raise ValueError("CPU recovery preflight step count drift")
    if preflight["preflight"]["projected_training_minutes"] >= run_config["execution"]["maximum_wall_minutes"] * 0.9:
        raise TimeoutError("CPU recovery preflight projection exceeds the run budget")
    if preflight["preflight"]["peak_process_rss_gb"] > run_config["execution"]["maximum_peak_memory_gb"]:
        raise MemoryError("CPU recovery preflight exceeds the memory budget")
    if preflight["frozen_sources"]["config"]["sha256"] != sha256_file(config_path):
        raise ValueError("CPU recovery preflight config no longer matches this run")
    if preflight["frozen_sources"]["runner"]["sha256"] != sha256_file(Path(__file__).resolve()):
        raise ValueError("CPU recovery preflight runner no longer matches this run")
    return {
        "status": "Passed",
        "run": artifact(preflight_path),
        "steps": preflight["preflight"]["steps"],
        "projected_training_minutes": preflight["preflight"]["projected_training_minutes"],
        "peak_process_rss_gb": preflight["preflight"]["peak_process_rss_gb"],
        "failed_mps_run": artifact(failed_run_path),
        "failed_mps_log": artifact(failed_log_path),
    }


def verify_model(shared: dict[str, Any]) -> dict[str, Any]:
    spec = shared["models"]["m1"]
    manifest_path = resolve_project(spec["manifest_path"])
    require_hash(manifest_path, spec["manifest_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != spec["repo_id"] or manifest["revision"] != spec["revision"]:
        raise ValueError("RoBERTa repository or revision drift")
    snapshot = resolve_project(spec["local_path"])
    verified = []
    for expected in manifest["files"]:
        path = snapshot / expected["path"]
        observed = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if observed != expected:
            raise ValueError(f"Model file drift: {expected['path']}")
        verified.append(observed)
    return {
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "manifest": artifact(manifest_path),
        "snapshot": project_path(snapshot),
        "files": verified,
    }


def load_split(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise PermissionError(f"Split is not authorized: {split}")
    data = shared["data"]
    path = resolve_project(data[f"{split}_path"])
    require_hash(path, data[f"{split}_sha256"])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != data[f"{split}_rows"]:
        raise ValueError(f"{split} row count drift")
    sample_ids: set[str] = set()
    for row in rows:
        if set(row) != EXPECTED_FIELDS:
            raise ValueError(f"{split} schema drift")
        if row["schema_version"] != "so-emotion-c0-v1" or row["protocol_id"] != data["protocol_id"]:
            raise ValueError(f"{split} protocol drift")
        if not isinstance(row["text"], str) or not row["text"].strip():
            raise ValueError(f"{split} contains empty text")
        if row["sample_id"] in sample_ids:
            raise ValueError(f"{split} repeats a sample ID")
        sample_ids.add(row["sample_id"])
        if len(row["labels"]) != len(LABELS) or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError(f"{split} contains an invalid label vector")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError(f"{split} derived label fields drift")
    return rows


def split_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "components": len({row["component_id"] for row in rows}),
        "neutral_rows": sum(row["neutral"] for row in rows),
        "label_cardinality": dict(sorted(Counter(row["label_cardinality"] for row in rows).items())),
        "positive_counts": {
            label: sum(row["labels"][index] for row in rows)
            for index, label in enumerate(LABELS)
        },
    }


def seed_everything(seed: int, device: str) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "mps":
        torch.mps.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def encode_rows(
    tokenizer: Any, rows: Sequence[dict[str, Any]], max_length: int
) -> tuple[dict[str, list[list[int]]], dict[str, Any]]:
    raw_lengths = [len(tokenizer.encode(row["text"], add_special_tokens=True)) for row in rows]
    encodings = tokenizer(
        [row["text"] for row in rows],
        add_special_tokens=True,
        max_length=max_length,
        padding=False,
        return_attention_mask=True,
        truncation=True,
    )
    encoded_lengths = [len(value) for value in encodings["input_ids"]]
    return dict(encodings), {
        "minimum": min(raw_lengths),
        "maximum": max(raw_lengths),
        "mean": float(np.mean(raw_lengths)),
        "p95": float(np.quantile(raw_lengths, 0.95)),
        "truncated_rows": sum(value > max_length for value in raw_lengths),
        "encoded_maximum": max(encoded_lengths),
    }


def make_collator(tokenizer: Any):
    def collate(features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        labels = torch.tensor(np.stack([item["labels"] for item in features]), dtype=torch.float32)
        inputs = [{key: value for key, value in item.items() if key != "labels"} for item in features]
        batch = tokenizer.pad(inputs, padding=True, return_tensors="pt")
        batch["labels"] = labels
        return batch

    return collate


def move_batch(batch: dict[str, torch.Tensor], device: torch.device) -> dict[str, torch.Tensor]:
    return {key: value.to(device) for key, value in batch.items()}


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    averages: dict[str, dict[str, float]] = {}
    for average in ("macro", "micro", "weighted"):
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
    without_surprise = [index for index, label in enumerate(LABELS) if label != "surprise"]
    _, _, five_label_f1, _ = precision_recall_fscore_support(
        gold[:, without_surprise],
        predicted[:, without_surprise],
        average="macro",
        zero_division=0,
    )
    cardinality = predicted.sum(axis=1)
    return {
        "subset_accuracy": float(accuracy_score(gold, predicted)),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(hamming_loss(gold, predicted)),
        "macro": averages["macro"],
        "micro_f1": averages["micro"]["f1"],
        "weighted_f1": averages["weighted"]["f1"],
        "five_label_macro_f1_without_surprise": float(five_label_f1),
        "per_label": {
            label: {
                "label_id": index,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "predicted_support": int(predicted_support[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": averages["macro"]["f1"]},
    }


def evaluate(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    gold: np.ndarray,
) -> tuple[float, np.ndarray]:
    model.eval()
    loss_sum = 0.0
    examples = 0
    batches: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            moved = move_batch(batch, device)
            labels = moved.pop("labels")
            logits = model(**moved).logits
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite validation loss")
            batch_size = labels.shape[0]
            loss_sum += float(loss.detach().cpu()) * batch_size
            examples += batch_size
            batches.append(torch.sigmoid(logits).detach().cpu().numpy())
    if device.type == "mps":
        torch.mps.synchronize()
    probabilities = np.concatenate(batches, axis=0).astype(np.float32, copy=False)
    if probabilities.shape != gold.shape or not np.isfinite(probabilities).all():
        raise ValueError("Invalid validation probability array")
    return loss_sum / examples, probabilities


def select_checkpoint(history: Sequence[dict[str, Any]], practical_tie_delta: float) -> dict[str, Any]:
    maximum = max(float(row["fixed_macro_f1"]) for row in history)
    eligible = [
        row for row in history
        if maximum - float(row["fixed_macro_f1"]) < practical_tie_delta
    ]
    selected = min(eligible, key=lambda row: int(row["epoch"]))
    return {
        "maximum_fixed_macro_f1": maximum,
        "practical_tie_delta": practical_tie_delta,
        "selected_epoch": int(selected["epoch"]),
        "selected_fixed_macro_f1": float(selected["fixed_macro_f1"]),
        "selection_deficit_from_maximum": maximum - float(selected["fixed_macro_f1"]),
        "eligible_epochs": [int(row["epoch"]) for row in eligible],
    }


def select_threshold(
    gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]
) -> tuple[float, list[dict[str, float]]]:
    rows = []
    for threshold in grid:
        predicted = (probabilities >= threshold).astype(np.uint8)
        macro_f1 = metric_bundle(gold, predicted)["macro"]["f1"]
        rows.append({"threshold": float(threshold), "macro_f1": float(macro_f1)})
    selected = min(rows, key=lambda row: (-row["macro_f1"], abs(row["threshold"] - 0.5), row["threshold"]))
    return selected["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    true_positive = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    false_positive = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    false_negative = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * true_positive + false_positive + false_negative
    return np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros(len(LABELS), dtype=np.float64),
        where=denominator != 0,
    )


def bootstrap_summary(
    gold: np.ndarray,
    predicted: np.ndarray,
    component_ids: Sequence[str],
    model_seed: int,
    replicates: int,
    namespace: str,
    condition: str,
) -> dict[str, Any]:
    components = sorted(set(component_ids))
    groups = {
        component: np.asarray(
            [index for index, value in enumerate(component_ids) if value == component], dtype=np.int64
        )
        for component in components
    }
    seed_material = f"{namespace}|EXP-051|seed-{model_seed}|{condition}"
    bootstrap_seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(bootstrap_seed)
    values = np.zeros((replicates, len(LABELS)), dtype=np.float64)
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], predicted[indices])
    macro = values.mean(axis=1)
    without_surprise = [index for index, label in enumerate(LABELS) if label != "surprise"]
    five_label = values[:, without_surprise].mean(axis=1)

    def interval(series: np.ndarray, point: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(point), "lower": float(lower), "upper": float(upper)}

    point_f1 = fast_f1(gold, predicted)
    return {
        "unit": "duplicate_component_id",
        "component_count": len(components),
        "row_count": len(component_ids),
        "replicates": replicates,
        "seed": bootstrap_seed,
        "seed_material": seed_material,
        "interval": "percentile_2.5_97.5",
        "macro_f1": interval(macro, float(point_f1.mean())),
        "five_label_macro_f1_without_surprise": interval(
            five_label, float(point_f1[without_surprise].mean())
        ),
        "per_label_f1": {
            label: interval(values[:, index], float(point_f1[index]))
            for index, label in enumerate(LABELS)
        },
    }


def optimizer_groups(
    model: torch.nn.Module, weight_decay: float, exclusions: Sequence[str]
) -> list[dict[str, Any]]:
    decay: list[torch.nn.Parameter] = []
    no_decay: list[torch.nn.Parameter] = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if any(name.endswith(value) for value in exclusions):
            no_decay.append(parameter)
        else:
            decay.append(parameter)
    return [
        {"params": decay, "weight_decay": weight_decay},
        {"params": no_decay, "weight_decay": 0.0},
    ]


def linear_schedule(step: int, warmup_steps: int, total_steps: int) -> float:
    if step < warmup_steps:
        return float(step) / float(max(1, warmup_steps))
    return max(0.0, float(total_steps - step) / float(max(1, total_steps - warmup_steps)))


def write_history(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = [
        "seed", "epoch", "optimizer_steps", "train_loss", "validation_loss",
        "fixed_threshold", "fixed_macro_precision", "fixed_macro_recall",
        "fixed_macro_f1", "fixed_micro_f1", "fixed_weighted_f1",
        "fixed_subset_accuracy", "fixed_hamming_loss",
        "fixed_five_label_macro_f1_without_surprise", "learning_rate_end",
        "batch_order_sha256", "epoch_seconds",
    ]
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_threshold_grid(path: Path, rows: Sequence[dict[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=("threshold", "macro_f1"))
        writer.writeheader()
        writer.writerows(rows)


def write_per_label(path: Path, metrics: dict[str, Any]) -> None:
    fields = ("label_id", "label", "precision", "recall", "f1", "support", "predicted_support")
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for label in LABELS:
            row = dict(metrics["per_label"][label])
            row["label"] = label
            writer.writerow(row)


def write_confusion(path: Path, matrix: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("label_id", "label", "tn", "fp", "fn", "tp"))
        for index, label in enumerate(LABELS):
            tn, fp, fn, tp = matrix[index].ravel()
            writer.writerow((index, label, int(tn), int(fp), int(fn), int(tp)))


def freeze_sources(run_dir: Path, config_path: Path) -> dict[str, Any]:
    sources = dict(FROZEN_FILES)
    sources["config"] = config_path.resolve()
    records = {}
    for name, source in sources.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        suffix = source.suffix
        target = run_dir / f"frozen-{name}{suffix}"
        shutil.copy2(source, target)
        records[name] = artifact(target)
    return records


def render_report(run_record: dict[str, Any]) -> str:
    selection = run_record["selection"]
    fixed = run_record["metrics"]["fixed_0.5"]
    calibrated = run_record["metrics"]["shared_threshold"]
    return "\n".join(
        [
            "# EXP-051 Seed 42 Validation Integrity Gate",
            "",
            f"- Status: `{run_record['status']}`; independent verification pending",
            "- Accessed splits: train, validation",
            "- Test accessed: no",
            f"- Selected epoch: `{selection['selected_epoch']}` from five epochs",
            f"- Fixed 0.5 Macro-F1: `{fixed['macro']['f1']:.6f}`",
            f"- Shared threshold: `{run_record['threshold_selection']['selected_threshold']:.2f}`",
            f"- Calibrated Macro-F1: `{calibrated['macro']['f1']:.6f}`",
            f"- Calibrated Micro-F1: `{calibrated['micro_f1']:.6f}`",
            f"- Calibrated subset accuracy: `{calibrated['subset_accuracy']:.6f}`",
            f"- Surprise F1: `{calibrated['per_label']['surprise']['f1']:.6f}`",
            "",
            "This is a single-seed integrity gate, not the frozen three-seed M1 result.",
            "Seeds 43/44 and test remain unauthorized.",
            "",
        ]
    )


def run() -> None:
    args = parse_args()
    run_config, shared = load_config(args.config.resolve(), args.seed)
    public_root = resolve_project(run_config["execution"]["public_run_root"])
    private_root = resolve_project(run_config["execution"]["private_run_root"])
    run_dir = (args.run_dir or public_root / f"seed-{args.seed}").resolve()
    private_dir = (args.private_dir or private_root / f"seed-{args.seed}").resolve()
    prepare_dirs(run_dir, private_dir)
    logger = setup_logger(run_dir)
    started = time.perf_counter()
    started_at = utc_now()
    run_path = run_dir / "run.json"
    run_record: dict[str, Any] = {
        "experiment_id": "EXP-051",
        "rq_id": "RQ-S1",
        "tier": "Major",
        "stage": run_config["stage"],
        "seed": args.seed,
        "status": "Running",
        "started_at_utc": started_at,
        "invocation": [sys.executable, *sys.argv],
        "working_directory": str(Path.cwd()),
        "accessed_splits": [],
        "validation_split_accessed": False,
        "test_split_accessed": False,
    }
    atomic_json(run_path, run_record)

    try:
        logger.info("EXP-051 seed %d preflight started", args.seed)
        frozen_sources = freeze_sources(run_dir, args.config.resolve())
        protocol_path = resolve_project(run_config["protocol_path"])
        if sha256_file(protocol_path) != frozen_sources["protocol"]["sha256"]:
            raise ValueError("Protocol freeze mismatch")
        prerequisite = verify_prerequisite(run_config)
        recovery_preflight = verify_recovery_preflight(run_config, args.config.resolve())
        environment = environment_gate(run_dir, run_config["execution"])
        model_record = verify_model(shared)
        logger.info("Authorization, EXP-050, environment, and model hashes verified")

        train_rows = load_split(shared, "train")
        validation_rows = load_split(shared, "validation")
        train_components = {row["component_id"] for row in train_rows}
        validation_components = {row["component_id"] for row in validation_rows}
        if train_components & validation_components:
            raise ValueError("Train/validation duplicate-component overlap")
        if {row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}:
            raise ValueError("Train/validation sample overlap")
        run_record.update(
            accessed_splits=["train", "validation"],
            validation_split_accessed=True,
            test_split_accessed=False,
        )
        atomic_json(run_path, run_record)
        logger.info("Loaded frozen train/validation: %d/%d rows", len(train_rows), len(validation_rows))

        spec = shared["models"]["m1"]
        model_path = resolve_project(spec["local_path"])
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        train_encodings, train_lengths = encode_rows(tokenizer, train_rows, spec["max_sequence_length"])
        validation_encodings, validation_lengths = encode_rows(
            tokenizer, validation_rows, spec["max_sequence_length"]
        )
        train_gold = np.asarray([row["labels"] for row in train_rows], dtype=np.uint8)
        validation_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
        train_dataset = EncodedDataset(train_encodings, train_gold)
        validation_dataset = EncodedDataset(validation_encodings, validation_gold)
        collator = make_collator(tokenizer)
        validation_loader = DataLoader(
            validation_dataset,
            batch_size=run_config["execution"]["evaluation_batch_size"],
            shuffle=False,
            drop_last=False,
            num_workers=0,
            collate_fn=collator,
        )
        logger.info(
            "Tokenized train/validation; max raw lengths %d/%d; truncated rows %d/%d",
            train_lengths["maximum"], validation_lengths["maximum"],
            train_lengths["truncated_rows"], validation_lengths["truncated_rows"],
        )

        device_name = run_config["execution"]["required_device"]
        seed_everything(args.seed, device_name)
        if device_name == "mps":
            torch.mps.empty_cache()
        model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            local_files_only=True,
            num_labels=len(LABELS),
            id2label={index: label for index, label in enumerate(LABELS)},
            label2id={label: index for index, label in enumerate(LABELS)},
            problem_type="multi_label_classification",
            ignore_mismatched_sizes=True,
        )
        if type(model.classifier).__name__ != "RobertaClassificationHead" or model.classifier.out_proj.out_features != 6:
            raise ValueError("M1 classification head contract drift")
        initial_classifier_sha = tensor_digest(
            {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
        )
        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
        if parameter_count != trainable_count:
            raise ValueError("M1 must train all parameters")
        device = torch.device(device_name)
        model.to(device)

        optimizer = torch.optim.AdamW(
            optimizer_groups(model, spec["weight_decay"], run_config["execution"]["weight_decay_exclusions"]),
            lr=spec["learning_rate"],
            betas=(run_config["execution"]["adam_beta1"], run_config["execution"]["adam_beta2"]),
            eps=run_config["execution"]["adam_epsilon"],
        )
        steps_per_epoch = math.ceil(len(train_dataset) / spec["batch_size"])
        total_steps = steps_per_epoch * spec["epochs"]
        warmup_exact = total_steps * spec["warmup_ratio"]
        if not float(warmup_exact).is_integer():
            raise ValueError("Warmup step rule is not integral")
        warmup_steps = int(warmup_exact)
        scheduler = LambdaLR(
            optimizer,
            lambda step: linear_schedule(step, warmup_steps, total_steps),
        )
        logger.info(
            "Training started: %d epochs, %d steps/epoch, %d warmup steps",
            spec["epochs"], steps_per_epoch, warmup_steps,
        )

        epoch_checkpoint_root = private_dir / "checkpoints"
        epoch_checkpoint_root.mkdir(mode=0o700)
        history: list[dict[str, Any]] = []
        epoch_probabilities: list[np.ndarray] = []
        order_generator = torch.Generator().manual_seed(args.seed)
        global_step = 0
        peak_allocated = 0
        peak_driver = 0
        for epoch in range(1, spec["epochs"] + 1):
            if time.perf_counter() - started > run_config["execution"]["maximum_wall_minutes"] * 60:
                raise TimeoutError("EXP-051 seed exceeded its wall-time budget")
            epoch_started = time.perf_counter()
            order = torch.randperm(len(train_dataset), generator=order_generator).tolist()
            order_digest = canonical_digest([train_rows[index]["sample_id"] for index in order])
            train_loader = DataLoader(
                Subset(train_dataset, order),
                batch_size=spec["batch_size"],
                shuffle=False,
                drop_last=False,
                num_workers=0,
                collate_fn=collator,
            )
            model.train()
            loss_sum = 0.0
            examples = 0
            for batch_index, batch in enumerate(train_loader, start=1):
                moved = move_batch(batch, device)
                labels = moved.pop("labels")
                optimizer.zero_grad(set_to_none=True)
                logits = model(**moved).logits
                if tuple(logits.shape) != (labels.shape[0], len(LABELS)):
                    raise ValueError("M1 logit shape drift")
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
                if not torch.isfinite(loss):
                    raise ValueError(f"Non-finite train loss at epoch {epoch}, batch {batch_index}")
                loss.backward()
                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    model.parameters(), run_config["execution"]["max_grad_norm"]
                )
                if not torch.isfinite(gradient_norm):
                    raise ValueError(f"Non-finite gradient norm at epoch {epoch}, batch {batch_index}")
                optimizer.step()
                scheduler.step()
                batch_size = labels.shape[0]
                loss_sum += float(loss.detach().cpu()) * batch_size
                examples += batch_size
                global_step += 1
                if device.type == "mps":
                    peak_allocated = max(peak_allocated, int(torch.mps.current_allocated_memory()))
                    peak_driver = max(peak_driver, int(torch.mps.driver_allocated_memory()))
                if batch_index % 50 == 0 or batch_index == steps_per_epoch:
                    logger.info(
                        "Seed %d epoch %d step %d/%d loss %.6f lr %.8g",
                        args.seed, epoch, batch_index, steps_per_epoch,
                        loss_sum / examples, optimizer.param_groups[0]["lr"],
                    )
            if device.type == "mps":
                torch.mps.synchronize()
            validation_loss, probabilities = evaluate(model, validation_loader, device, validation_gold)
            fixed_predicted = (probabilities >= shared["evaluation"]["fixed_threshold"]).astype(np.uint8)
            fixed_metrics = metric_bundle(validation_gold, fixed_predicted)
            checkpoint_dir = epoch_checkpoint_root / f"epoch-{epoch}"
            model.save_pretrained(checkpoint_dir, safe_serialization=True)
            epoch_probabilities.append(probabilities)
            epoch_seconds = time.perf_counter() - epoch_started
            history.append(
                {
                    "seed": args.seed,
                    "epoch": epoch,
                    "optimizer_steps": global_step,
                    "train_loss": loss_sum / examples,
                    "validation_loss": validation_loss,
                    "fixed_threshold": shared["evaluation"]["fixed_threshold"],
                    "fixed_macro_precision": fixed_metrics["macro"]["precision"],
                    "fixed_macro_recall": fixed_metrics["macro"]["recall"],
                    "fixed_macro_f1": fixed_metrics["macro"]["f1"],
                    "fixed_micro_f1": fixed_metrics["micro_f1"],
                    "fixed_weighted_f1": fixed_metrics["weighted_f1"],
                    "fixed_subset_accuracy": fixed_metrics["subset_accuracy"],
                    "fixed_hamming_loss": fixed_metrics["hamming_loss"],
                    "fixed_five_label_macro_f1_without_surprise": fixed_metrics[
                        "five_label_macro_f1_without_surprise"
                    ],
                    "learning_rate_end": optimizer.param_groups[0]["lr"],
                    "batch_order_sha256": order_digest,
                    "epoch_seconds": epoch_seconds,
                }
            )
            logger.info(
                "Seed %d epoch %d complete: train_loss=%.6f val_loss=%.6f fixed_macro_f1=%.6f seconds=%.1f",
                args.seed, epoch, loss_sum / examples, validation_loss,
                fixed_metrics["macro"]["f1"], epoch_seconds,
            )

        if global_step != total_steps or len(epoch_probabilities) != spec["epochs"]:
            raise ValueError("Training completion count drift")
        probability_array = np.stack(epoch_probabilities, axis=0)
        selection = select_checkpoint(history, shared["evaluation"]["practical_tie_delta"])
        selected_epoch = selection["selected_epoch"]
        selected_probabilities = probability_array[selected_epoch - 1]
        fixed_threshold = shared["evaluation"]["fixed_threshold"]
        selected_threshold, threshold_rows = select_threshold(
            validation_gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"]
        )
        fixed_predictions = (selected_probabilities >= fixed_threshold).astype(np.uint8)
        calibrated_predictions = (selected_probabilities >= selected_threshold).astype(np.uint8)
        fixed_metrics = metric_bundle(validation_gold, fixed_predictions)
        calibrated_metrics = metric_bundle(validation_gold, calibrated_predictions)
        bootstrap = {
            "fixed_0.5": bootstrap_summary(
                validation_gold,
                fixed_predictions,
                [row["component_id"] for row in validation_rows],
                args.seed,
                shared["evaluation"]["bootstrap"]["replicates"],
                shared["evaluation"]["bootstrap"]["seed_namespace"],
                "fixed-0.5",
            ),
            "shared_threshold": bootstrap_summary(
                validation_gold,
                calibrated_predictions,
                [row["component_id"] for row in validation_rows],
                args.seed,
                shared["evaluation"]["bootstrap"]["replicates"],
                shared["evaluation"]["bootstrap"]["seed_namespace"],
                f"shared-{selected_threshold:.2f}",
            ),
        }

        selected_source = epoch_checkpoint_root / f"epoch-{selected_epoch}"
        selected_checkpoint = private_dir / "selected-checkpoint"
        selected_source.rename(selected_checkpoint)
        tokenizer.save_pretrained(selected_checkpoint)
        for candidate in epoch_checkpoint_root.iterdir():
            if candidate.is_dir():
                shutil.rmtree(candidate)
        epoch_checkpoint_root.rmdir()
        final_classifier_sha = tensor_digest(
            {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
        )
        if initial_classifier_sha == final_classifier_sha:
            raise ValueError("M1 classifier parameters did not change")

        predictions_path = private_dir / "validation-predictions.npz"
        np.savez_compressed(
            predictions_path,
            probabilities=probability_array,
            gold=validation_gold,
            fixed_predictions=fixed_predictions,
            shared_threshold_predictions=calibrated_predictions,
            sample_ids=np.asarray([row["sample_id"] for row in validation_rows]),
            component_ids=np.asarray([row["component_id"] for row in validation_rows]),
        )
        os.chmod(predictions_path, 0o600)
        private_manifest_path = private_dir / "private-manifest.json"
        private_manifest = {
            "experiment_id": "EXP-051",
            "seed": args.seed,
            "contains_raw_text": False,
            "contains_row_level_probabilities": True,
            "contains_row_identifiers": True,
            "validation_predictions": artifact(predictions_path),
            "selected_checkpoint": tree_artifact(selected_checkpoint),
        }
        atomic_json(private_manifest_path, private_manifest, private=True)

        history_path = run_dir / "history.csv"
        threshold_path = run_dir / "threshold-grid.csv"
        fixed_metrics_path = run_dir / "metrics-fixed-0.5.json"
        calibrated_metrics_path = run_dir / "metrics-shared-threshold.json"
        bootstrap_path = run_dir / "bootstrap.json"
        selection_path = run_dir / "selection.json"
        write_history(history_path, history)
        write_threshold_grid(threshold_path, threshold_rows)
        atomic_json(fixed_metrics_path, fixed_metrics)
        atomic_json(calibrated_metrics_path, calibrated_metrics)
        atomic_json(bootstrap_path, bootstrap)
        atomic_json(selection_path, selection)
        public_tables = {}
        for name, metrics, predictions in (
            ("fixed-0.5", fixed_metrics, fixed_predictions),
            ("shared-threshold", calibrated_metrics, calibrated_predictions),
        ):
            per_label_path = run_dir / f"per-label-{name}.csv"
            confusion_path = run_dir / f"multilabel-confusion-{name}.csv"
            write_per_label(per_label_path, metrics)
            write_confusion(confusion_path, multilabel_confusion_matrix(validation_gold, predictions))
            public_tables[name] = {
                "per_label": artifact(per_label_path),
                "confusion": artifact(confusion_path),
            }

        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_gb = peak_rss / 1e9 if platform.system() == "Darwin" else peak_rss * 1024 / 1e9
        run_record.update(
            {
                "status": "Completed",
                "completed_at_utc": utc_now(),
                "authorization": run_config["authorization"],
                "prerequisite": prerequisite,
                "recovery_preflight": recovery_preflight,
                "accessed_splits": ["train", "validation"],
                "validation_split_accessed": True,
                "test_split_accessed": False,
                "data": {
                    "protocol_id": shared["data"]["protocol_id"],
                    "labels": list(LABELS),
                    "train": {
                        "path": shared["data"]["train_path"],
                        "sha256": shared["data"]["train_sha256"],
                        "summary": split_summary(train_rows),
                        "token_lengths": train_lengths,
                    },
                    "validation": {
                        "path": shared["data"]["validation_path"],
                        "sha256": shared["data"]["validation_sha256"],
                        "summary": split_summary(validation_rows),
                        "token_lengths": validation_lengths,
                    },
                    "cross_split_component_overlap": 0,
                    "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
                },
                "environment": environment,
                "git": git_metadata(),
                "model": {
                    **model_record,
                    "head": spec["head"],
                    "parameter_count": parameter_count,
                    "trainable_parameter_count": trainable_count,
                    "classifier_initial_sha256": initial_classifier_sha,
                    "classifier_final_in_memory_sha256": final_classifier_sha,
                },
                "training": {
                    **spec,
                    **{
                        key: run_config["execution"][key]
                        for key in (
                            "evaluation_batch_size", "max_grad_norm", "adam_beta1", "adam_beta2",
                            "adam_epsilon", "weight_decay_exclusions", "padding", "shuffle",
                            "drop_last", "num_workers",
                        )
                    },
                    "steps_per_epoch": steps_per_epoch,
                    "total_optimizer_steps": total_steps,
                    "warmup_steps": warmup_steps,
                    "history": history,
                },
                "selection": selection,
                "threshold_selection": {
                    "selected_threshold": selected_threshold,
                    "grid": list(shared["evaluation"]["shared_threshold_grid"]),
                    "rule": shared["evaluation"]["shared_threshold_rule"],
                },
                "metrics": {
                    "fixed_0.5": fixed_metrics,
                    "shared_threshold": calibrated_metrics,
                },
                "bootstrap": bootstrap,
                "resource_usage": {
                    "api_cost_usd": 0,
                    "wall_seconds": time.perf_counter() - started,
                    "peak_mps_allocated_gb": peak_allocated / 1e9,
                    "peak_mps_driver_gb": peak_driver / 1e9,
                    "peak_rss_bytes": int(peak_rss),
                    "peak_process_rss_gb": peak_rss_gb,
                    "device": device_name,
                    "wall_budget_minutes": run_config["execution"]["maximum_wall_minutes"],
                    "peak_memory_budget_gb": run_config["execution"]["maximum_peak_memory_gb"],
                },
                "privacy": {
                    "public_raw_text": False,
                    "public_row_identifiers": False,
                    "row_level_validation_artifacts": "private_gitignored",
                },
                "warnings": [
                    "Seed 42 is an integrity gate and cannot form the three-seed M1 conclusion.",
                    "Deterministic algorithms are requested with warn_only; bitwise repeatability is not claimed.",
                    "The shared threshold is selected on validation and cannot be tuned on test.",
                ],
            }
        )
        observed_peak_gb = (
            run_record["resource_usage"]["peak_mps_driver_gb"]
            if device_name == "mps"
            else run_record["resource_usage"]["peak_process_rss_gb"]
        )
        if observed_peak_gb > run_config["execution"]["maximum_peak_memory_gb"]:
            raise MemoryError("EXP-051 exceeded the frozen peak-memory budget")

        logger.info(
            "Seed %d completed: selected_epoch=%d fixed_macro_f1=%.6f shared_threshold=%.2f calibrated_macro_f1=%.6f",
            args.seed, selected_epoch, fixed_metrics["macro"]["f1"], selected_threshold,
            calibrated_metrics["macro"]["f1"],
        )
        flush_logger(logger)
        report_path = run_dir / "REPORT.md"
        report_path.write_text(render_report(run_record), encoding="utf-8")
        run_record["artifacts"] = {
            "frozen_sources": frozen_sources,
            "history": artifact(history_path),
            "threshold_grid": artifact(threshold_path),
            "metrics_fixed": artifact(fixed_metrics_path),
            "metrics_shared_threshold": artifact(calibrated_metrics_path),
            "bootstrap": artifact(bootstrap_path),
            "selection": artifact(selection_path),
            "tables": public_tables,
            "report": artifact(report_path),
            "stdout_log": artifact(run_dir / "stdout.log"),
            "private_manifest": artifact(private_manifest_path),
            "validation_predictions_private": artifact(predictions_path),
            "selected_checkpoint_private": tree_artifact(selected_checkpoint),
        }
        atomic_json(run_path, run_record)
    except Exception as error:
        logger.exception("EXP-051 seed %d failed", args.seed)
        flush_logger(logger)
        run_record.update(
            {
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "failure": {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()},
                "resource_usage": {"wall_seconds": time.perf_counter() - started},
                "test_split_accessed": False,
            }
        )
        atomic_json(run_path, run_record)
        raise
    finally:
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()


if __name__ == "__main__":
    run()
