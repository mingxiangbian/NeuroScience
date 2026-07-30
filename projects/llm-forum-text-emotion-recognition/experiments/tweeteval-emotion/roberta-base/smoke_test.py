#!/usr/bin/env python3
"""Verify the pinned local RoBERTa stack without reading project data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import accelerate
import datasets
import evaluate
import sklearn
import torch
import transformers
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)


EXPERIMENT_ID = "EXP-008"
LABELS = ["anger", "joy", "optimism", "sadness"]
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
MODEL_ROOT = PROJECT_ROOT / "models" / "roberta-base"
MODEL_DIR = MODEL_ROOT / "snapshot"
MANIFEST_PATH = MODEL_ROOT / "manifest.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-008-environment-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        help="New append-only directory for run.json.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_verify_manifest() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verified: list[dict[str, Any]] = []
    for expected in manifest["files"]:
        path = MODEL_DIR / expected["path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing model file: {path}")
        actual = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256(path),
        }
        if actual != expected:
            raise ValueError(
                f"Model integrity mismatch for {expected['path']}: "
                f"expected {expected}, got {actual}"
            )
        verified.append(actual)
    return manifest, verified


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "branch": branch,
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def synthetic_dataset(tokenizer: Any) -> Dataset:
    texts = [
        "I am furious that this happened again.",
        "This news made my whole day brighter.",
        "I think tomorrow can still turn out well.",
        "I feel empty after hearing what happened.",
        "That response was completely unacceptable.",
        "I cannot stop smiling about the result.",
        "There is still a good chance we can recover.",
        "I miss how things used to be.",
    ]
    encoded = tokenizer(texts, truncation=True, max_length=64)
    encoded["labels"] = [0, 1, 2, 3, 0, 1, 2, 3]
    return Dataset.from_dict(encoded)


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    set_seed(42)

    if not torch.backends.mps.is_built():
        raise RuntimeError("This PyTorch build has no MPS support")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is not available in the current process")

    manifest, verified_files = load_and_verify_manifest()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    label2id = {label: index for index, label in enumerate(LABELS)}
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_DIR,
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id=label2id,
        local_files_only=True,
        num_labels=len(LABELS),
    )
    dataset = synthetic_dataset(tokenizer)

    with tempfile.TemporaryDirectory(
        prefix="emotion-roberta-exp-008-",
        dir="/private/tmp",
    ) as trainer_output:
        training_args = TrainingArguments(
            output_dir=trainer_output,
            per_device_train_batch_size=8,
            max_steps=1,
            learning_rate=5e-5,
            optim="adamw_torch",
            logging_strategy="steps",
            logging_steps=1,
            save_strategy="no",
            report_to="none",
            disable_tqdm=True,
            dataloader_pin_memory=False,
            seed=42,
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
            train_dataset=dataset,
            processing_class=tokenizer,
        )
        device = str(trainer.args.device)
        train_result = trainer.train()
        prediction = trainer.predict(dataset.select(range(4)))

    train_loss = float(train_result.metrics["train_loss"])
    if not math.isfinite(train_loss):
        raise ValueError(f"Non-finite synthetic train loss: {train_loss}")
    if prediction.predictions.shape != (4, len(LABELS)):
        raise ValueError(
            "Unexpected synthetic prediction shape: "
            f"{prediction.predictions.shape}"
        )
    if not bool(torch.isfinite(torch.from_numpy(prediction.predictions)).all()):
        raise ValueError("Synthetic predictions contain NaN or Inf")

    ended_at = datetime.now(timezone.utc)
    report = {
        "accessed_splits": [],
        "artifacts": {
            "model_manifest": {
                "path": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
                "sha256": sha256(MANIFEST_PATH),
            },
            "run_metadata": {
                "path": str((run_dir / "run.json").relative_to(PROJECT_ROOT))
            },
        },
        "created_at_utc": ended_at.isoformat(),
        "data": {
            "dataset": "synthetic smoke inputs only",
            "label_mapping": {
                str(index): label for index, label in enumerate(LABELS)
            },
            "sample_count": len(dataset),
            "split": "N/A",
        },
        "experiment_id": EXPERIMENT_ID,
        "invocation": [sys.executable, *sys.argv],
        "model": {
            "classification_head": "newly initialized four-label head",
            "local_files_only": True,
            "manifest_files_verified": verified_files,
            "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
            "repo_id": manifest["repo_id"],
            "revision": manifest["revision"],
            "snapshot_path": str(MODEL_DIR.relative_to(PROJECT_ROOT)),
            "trainable_parameter_count": sum(
                parameter.numel()
                for parameter in model.parameters()
                if parameter.requires_grad
            ),
        },
        "parent_experiment": "N/A",
        "question": (
            "Can the pinned local RoBERTa stack load offline and complete one "
            "Transformers Trainer step on Apple MPS?"
        ),
        "resource_budget": {
            "api_cost_usd": 0,
            "dataset_rows": 0,
            "optimization_steps": 1,
            "wall_time_minutes": 3,
        },
        "rq_id": "N/A (Phase 3 infrastructure)",
        "runtime": {
            "architecture": platform.machine(),
            "device": device,
            "environment": "emotion-roberta",
            "executable": sys.executable,
            "git": git_metadata(),
            "mps_available": torch.backends.mps.is_available(),
            "mps_built": torch.backends.mps.is_built(),
            "packages": {
                "accelerate": accelerate.__version__,
                "datasets": datasets.__version__,
                "evaluate": evaluate.__version__,
                "scikit_learn": sklearn.__version__,
                "torch": torch.__version__,
                "transformers": transformers.__version__,
            },
            "platform": platform.platform(),
            "python": platform.python_version(),
            "total_seconds": time.perf_counter() - started,
        },
        "smoke_result": {
            "prediction_shape": list(prediction.predictions.shape),
            "synthetic_train_loss": train_loss,
            "train_runtime_seconds": float(
                train_result.metrics.get("train_runtime", 0.0)
            ),
        },
        "stage": "environment-and-model-smoke",
        "started_at_utc": started_at.isoformat(),
        "status": "Completed",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "warnings": [
            "The four-label classification head is intentionally initialized "
            "from scratch; this is not a fine-tuned checkpoint.",
            "Synthetic loss and predictions are implementation checks, not "
            "research metrics.",
        ],
    }
    output_path = run_dir / "run.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
