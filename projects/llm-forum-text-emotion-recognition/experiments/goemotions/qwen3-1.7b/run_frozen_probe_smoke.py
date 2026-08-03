#!/usr/bin/env python3
"""Smoke-test matched hidden-state extraction without project data access."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlx.core as mx
import numpy as np
from mlx_lm import load


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def encode_batch(tokenizer: Any, texts: list[str], config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    max_length = int(config["input"]["max_length"])
    pad_id = int(config["input"]["padding_token_id"])
    token_rows: list[list[int]] = []
    for text in texts:
        ids = tokenizer.encode(text, add_special_tokens=False)[:max_length]
        if not ids:
            raise ValueError("Synthetic text encoded to zero tokens")
        token_rows.append([int(token_id) for token_id in ids])

    width = max(len(row) for row in token_rows)
    input_ids = np.full((len(token_rows), width), pad_id, dtype=np.int32)
    attention_mask = np.zeros((len(token_rows), width), dtype=np.float32)
    for row_index, ids in enumerate(token_rows):
        input_ids[row_index, : len(ids)] = ids
        attention_mask[row_index, : len(ids)] = 1.0
    return input_ids, attention_mask, token_rows


def extract_condition(
    spec: dict[str, Any],
    config: dict[str, Any],
    texts: list[str],
) -> tuple[dict[str, Any], np.ndarray, list[list[int]]]:
    model_dir = PROJECT_ROOT / spec["local_path"]
    manifest_path = PROJECT_ROOT / spec["manifest_path"]
    tokenizer_path = model_dir / config["tokenizer"]["asset"]
    if sha256(manifest_path) != spec["manifest_sha256"]:
        raise ValueError(f"Manifest hash mismatch for {spec['condition']}")
    if sha256(tokenizer_path) != config["tokenizer"]["asset_sha256"]:
        raise ValueError(f"Tokenizer hash mismatch for {spec['condition']}")

    mx.reset_peak_memory()
    load_started = time.perf_counter()
    model, tokenizer = load(str(model_dir))
    load_seconds = time.perf_counter() - load_started
    input_ids, attention_mask, token_rows = encode_batch(tokenizer, texts, config)

    if tokenizer.convert_tokens_to_ids(config["input"]["padding_token"]) != config["input"]["padding_token_id"]:
        raise ValueError(f"Padding token mismatch for {spec['condition']}")
    if int(model.args.hidden_size) != int(spec["hidden_size"]):
        raise ValueError(f"Hidden-size mismatch for {spec['condition']}")
    if int(model.args.num_hidden_layers) != int(spec["num_hidden_layers"]):
        raise ValueError(f"Layer-count mismatch for {spec['condition']}")

    forward_started = time.perf_counter()
    hidden = model.model(mx.array(input_ids, dtype=mx.int32))
    mask = mx.array(attention_mask, dtype=mx.float32)[..., None]
    pooled = (hidden.astype(mx.float32) * mask).sum(axis=1) / mask.sum(axis=1)
    mx.eval(pooled)
    forward_seconds = time.perf_counter() - forward_started
    features = np.asarray(pooled, dtype=np.float32)
    if features.shape != (len(texts), int(spec["hidden_size"])):
        raise ValueError(f"Unexpected feature shape for {spec['condition']}: {features.shape}")
    if not np.isfinite(features).all():
        raise ValueError(f"Non-finite features for {spec['condition']}")

    norms = np.linalg.norm(features, axis=1)
    report = {
        "condition": spec["condition"],
        "feature_digest_sha256": bytes_sha256(features.tobytes(order="C")),
        "feature_dtype": str(features.dtype),
        "feature_shape": list(features.shape),
        "finite": True,
        "forward_seconds": forward_seconds,
        "hidden_size": int(model.args.hidden_size),
        "load_seconds": load_seconds,
        "norm_max": float(norms.max()),
        "norm_mean": float(norms.mean()),
        "norm_min": float(norms.min()),
        "num_hidden_layers": int(model.args.num_hidden_layers),
        "peak_mlx_memory_gb": mx.get_peak_memory() / 1e9,
        "token_count_max": max(len(row) for row in token_rows),
        "token_count_min": min(len(row) for row in token_rows),
        "token_id_digest_sha256": bytes_sha256(
            json.dumps(token_rows, separators=(",", ":")).encode("utf-8")
        ),
    }

    del hidden, pooled, mask, model, tokenizer
    gc.collect()
    mx.clear_cache()
    return report, features, token_rows


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite run directory: {output_dir}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-027" or config["tier"] != "Minor":
        raise ValueError("Unexpected EXP-027 config identity")
    texts = list(config["data"]["synthetic_texts"])
    if len(texts) != 6 or len(set(texts)) != len(texts):
        raise ValueError("Expected six unique synthetic texts")

    test_path = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
    if test_path.exists():
        raise FileExistsError("GoEmotions test must remain absent")

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    condition_reports: list[dict[str, Any]] = []
    features_by_condition: dict[str, np.ndarray] = {}
    token_rows_reference: list[list[int]] | None = None
    for spec in config["models"]:
        report, features, token_rows = extract_condition(spec, config, texts)
        if token_rows_reference is None:
            token_rows_reference = token_rows
        elif token_rows != token_rows_reference:
            raise ValueError("Base and post-trained token IDs differ")
        condition_reports.append(report)
        features_by_condition[spec["condition"]] = features

    base = features_by_condition["base"]
    post_trained = features_by_condition["post-trained"]
    if np.array_equal(base, post_trained):
        raise ValueError("Base and post-trained features are unexpectedly identical")
    l2 = np.linalg.norm(base - post_trained, axis=1)
    denominator = np.linalg.norm(base, axis=1) * np.linalg.norm(post_trained, axis=1)
    cosine = np.sum(base * post_trained, axis=1) / denominator
    if not np.isfinite(l2).all() or not np.isfinite(cosine).all():
        raise ValueError("Non-finite paired representation diagnostic")

    run = {
        "accessed_splits": [],
        "config_path": str(config_path.relative_to(REPO_ROOT)),
        "config_sha256": sha256(config_path),
        "conditions": condition_reports,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": config["experiment_id"],
        "git": git_metadata(),
        "packages": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx-lm": importlib.metadata.version("mlx-lm"),
            "numpy": importlib.metadata.version("numpy"),
            "transformers": importlib.metadata.version("transformers"),
        },
        "paired_diagnostics": {
            "cosine_max": float(cosine.max()),
            "cosine_mean": float(cosine.mean()),
            "cosine_min": float(cosine.min()),
            "l2_difference_max": float(l2.max()),
            "l2_difference_mean": float(l2.mean()),
            "l2_difference_min": float(l2.min()),
        },
        "platform": platform.platform(),
        "project_rows_accessed": 0,
        "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).resolve()),
        "started_at_utc": started_at.isoformat(),
        "status": "completed",
        "synthetic_text_count": len(texts),
        "synthetic_text_stored_in_run": False,
        "test_absent_after_run": not test_path.exists(),
        "test_absent_before_run": True,
        "test_split_accessed": False,
        "tier": config["tier"],
        "total_seconds": time.perf_counter() - started,
        "validation_split_accessed": False,
    }
    if not math.isfinite(run["total_seconds"]):
        raise ValueError("Non-finite runtime")

    output_dir.mkdir(parents=True)
    (output_dir / "run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "cosine_mean": run["paired_diagnostics"]["cosine_mean"],
                "experiment_id": config["experiment_id"],
                "status": run["status"],
                "total_seconds": run["total_seconds"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
