#!/usr/bin/env python3
"""Verify the pinned BERT multi-label stack without reading project data."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


EXPERIMENT_ID = "EXP-019"
LABELS = [
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
]
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
MODEL_ROOT = PROJECT_ROOT / "models" / "bert-base-cased"
MODEL_DIR = MODEL_ROOT / "snapshot"
MANIFEST_PATH = MODEL_ROOT / "manifest.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-019-environment-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verified: list[dict[str, Any]] = []
    for expected in manifest["files"]:
        path = MODEL_DIR / expected["path"]
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
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def package_versions() -> dict[str, str]:
    names = ["numpy", "safetensors", "scikit-learn", "torch", "transformers"]
    return {name: importlib.metadata.version(name) for name in names}


def synthetic_batch(tokenizer: Any) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
    texts = [
        "I am furious that this happened again.",
        "This made my whole day brighter.",
        "I think tomorrow can still turn out well.",
        "I feel empty after hearing what happened.",
        "That response was confusing but also funny.",
        "I am grateful and relieved.",
        "Nothing special happened today.",
        "I cannot believe this wonderful surprise.",
    ] * 2
    encoded = tokenizer(
        texts,
        max_length=50,
        padding="max_length",
        return_tensors="pt",
        truncation=True,
    )
    targets = torch.zeros((len(texts), len(LABELS)), dtype=torch.float32)
    target_ids = [
        [2, 3],
        [1, 17],
        [20],
        [9, 25],
        [6, 1],
        [15, 23],
        [27],
        [13, 26],
    ] * 2
    for row, label_ids in enumerate(target_ids):
        targets[row, label_ids] = 1.0
    return encoded, targets


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    torch.manual_seed(42)

    if not torch.backends.mps.is_built():
        raise RuntimeError("This PyTorch build has no MPS support")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is not available in the current process")

    manifest, verified_files = verify_manifest()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_DIR,
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id={label: index for index, label in enumerate(LABELS)},
        local_files_only=True,
        num_labels=len(LABELS),
        problem_type="multi_label_classification",
    )
    device = torch.device("mps")
    model.to(device)
    model.train()

    encoded, targets = synthetic_batch(tokenizer)
    encoded = {key: value.to(device) for key, value in encoded.items()}
    targets = targets.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)

    losses: list[float] = []
    step_seconds: list[float] = []
    for _ in range(3):
        step_started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        output = model(**encoded, labels=targets)
        loss = output.loss
        if loss is None or not math.isfinite(float(loss.detach().cpu())):
            raise ValueError("Synthetic multi-label loss is missing or non-finite")
        loss.backward()
        optimizer.step()
        torch.mps.synchronize()
        losses.append(float(loss.detach().cpu()))
        step_seconds.append(time.perf_counter() - step_started)

    model.eval()
    with torch.inference_mode():
        logits = model(**encoded).logits
        probabilities = torch.sigmoid(logits)
    if tuple(probabilities.shape) != (16, len(LABELS)):
        raise ValueError(f"Unexpected prediction shape: {probabilities.shape}")
    if not bool(torch.isfinite(probabilities).all()):
        raise ValueError("Synthetic probabilities contain NaN or Inf")

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
            "label_count": len(LABELS),
            "sample_count": 16,
            "split": "N/A",
        },
        "experiment_id": EXPERIMENT_ID,
        "invocation": [sys.executable, *sys.argv],
        "model": {
            "classification_head": "newly initialized 28-label head",
            "local_files_only": True,
            "manifest_files_verified": verified_files,
            "parameter_count": sum(p.numel() for p in model.parameters()),
            "repo_id": manifest["repo_id"],
            "revision": manifest["revision"],
            "snapshot_path": str(MODEL_DIR.relative_to(PROJECT_ROOT)),
        },
        "parent_experiment": "N/A",
        "question": (
            "Can the pinned BERT stack complete multi-label BCE optimization "
            "and sigmoid inference on Apple MPS?"
        ),
        "resource_budget": {
            "api_cost_usd": 0,
            "dataset_rows": 0,
            "optimization_steps": 3,
            "wall_time_minutes": 3,
        },
        "rq_id": "RQ-G1 implementation check",
        "runtime": {
            "architecture": platform.machine(),
            "device": str(device),
            "environment": "emotion-roberta",
            "executable": sys.executable,
            "git": git_metadata(),
            "mps_available": torch.backends.mps.is_available(),
            "mps_built": torch.backends.mps.is_built(),
            "packages": package_versions(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "total_seconds": time.perf_counter() - started,
        },
        "smoke_result": {
            "final_synthetic_train_loss": losses[-1],
            "losses": losses,
            "median_step_seconds": statistics.median(step_seconds),
            "prediction_shape": list(probabilities.shape),
            "probability_max": float(probabilities.max().cpu()),
            "probability_min": float(probabilities.min().cpu()),
            "step_seconds": step_seconds,
        },
        "stage": "environment-and-model-smoke",
        "started_at_utc": started_at.isoformat(),
        "status": "Completed",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "warnings": [
            "The 28-label head is initialized from scratch.",
            "Synthetic loss and probabilities are implementation checks only.",
            "No project data split was read.",
        ],
    }
    (run_dir / "run.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["smoke_result"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
