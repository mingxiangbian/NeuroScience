#!/usr/bin/env python3
"""Extract frozen Qwen hidden-state features for one registered split."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import subprocess
import sys
import time
import traceback
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
    parser.add_argument("--condition", choices=("base", "post-trained"), required=True)
    parser.add_argument("--split", choices=("train", "dev"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def setup_logger(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"exp-028-extract-{output_dir.name}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(output_dir / "stdout.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


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


def load_texts(path: Path, expected_rows: int, label_count: int) -> tuple[list[str], int]:
    texts: list[str] = []
    comment_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source, delimiter="\t")
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError(f"{path.name} has more than {expected_rows} rows")
            if len(row) != 3:
                raise ValueError(f"{path.name} row {row_number} has {len(row)} columns")
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"{path.name} row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError(f"{path.name} row {row_number} repeats a comment ID")
            comment_ids.add(comment_id)
            try:
                label_ids = [int(value) for value in encoded_labels.split(",")]
            except ValueError as error:
                raise ValueError(f"{path.name} row {row_number} has a non-integer label") from error
            if not label_ids or len(label_ids) != len(set(label_ids)):
                raise ValueError(f"{path.name} row {row_number} has empty or duplicate labels")
            if any(label_id < 0 or label_id >= label_count for label_id in label_ids):
                raise ValueError(f"{path.name} row {row_number} has an out-of-range label")
            texts.append(text)
    if len(texts) != expected_rows:
        raise ValueError(f"{path.name} has {len(texts)} rows; expected {expected_rows}")
    return texts, len(comment_ids)


def encode_batch(
    tokenizer: Any,
    texts: list[str],
    *,
    max_length: int,
    pad_id: int,
    token_digest: Any,
    first_row_number: int,
) -> tuple[np.ndarray, np.ndarray, list[int], int]:
    token_rows: list[list[int]] = []
    lengths: list[int] = []
    truncated_count = 0
    for offset, text in enumerate(texts):
        full_ids = [int(value) for value in tokenizer.encode(text, add_special_tokens=False)]
        truncated_count += int(len(full_ids) > max_length)
        ids = full_ids[:max_length]
        if not ids:
            raise ValueError(f"Row {first_row_number + offset} encoded to zero tokens")
        canonical = np.asarray(ids, dtype="<i4")
        token_digest.update(int(first_row_number + offset).to_bytes(8, "little", signed=False))
        token_digest.update(len(ids).to_bytes(4, "little", signed=False))
        token_digest.update(canonical.tobytes(order="C"))
        token_rows.append(ids)
        lengths.append(len(ids))

    width = max(lengths)
    input_ids = np.full((len(texts), width), pad_id, dtype=np.int32)
    attention_mask = np.zeros((len(texts), width), dtype=np.float32)
    for row_index, ids in enumerate(token_rows):
        input_ids[row_index, : len(ids)] = ids
        attention_mask[row_index, : len(ids)] = 1.0
    return input_ids, attention_mask, lengths, truncated_count


def execute(args: argparse.Namespace, output_dir: Path, logger: logging.Logger) -> None:
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != "EXP-028" or config.get("tier") != "Major":
        raise ValueError("Unexpected EXP-028 config identity")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise RuntimeError("Formal extraction requires HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1")

    test_path = PROJECT_ROOT / config["data"]["test_path"]
    if test_path.exists():
        raise FileExistsError("GoEmotions test must remain absent")
    split_spec = config["data"]["splits"][args.split]
    split_path = PROJECT_ROOT / split_spec["path"]
    if sha256(split_path) != split_spec["sha256"]:
        raise ValueError(f"Frozen {args.split} hash mismatch")
    labels_path = PROJECT_ROOT / config["data"]["labels_path"]
    if sha256(labels_path) != config["data"]["labels_sha256"]:
        raise ValueError("Frozen label ontology hash mismatch")
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if len(labels) != config["data"]["label_count"]:
        raise ValueError("Frozen label count mismatch")

    model_specs = {item["condition"]: item for item in config["models"]}
    spec = model_specs[args.condition]
    manifest_path = PROJECT_ROOT / spec["manifest_path"]
    model_dir = PROJECT_ROOT / spec["local_path"]
    tokenizer_path = model_dir / config["tokenizer"]["asset"]
    if sha256(manifest_path) != spec["manifest_sha256"]:
        raise ValueError(f"Manifest hash mismatch for {args.condition}")
    if sha256(tokenizer_path) != config["tokenizer"]["asset_sha256"]:
        raise ValueError(f"Tokenizer hash mismatch for {args.condition}")

    logger.info("Reading frozen %s split; GoEmotions test remains absent", args.split)
    texts, unique_comment_ids = load_texts(
        split_path,
        int(split_spec["rows"]),
        int(config["data"]["label_count"]),
    )
    logger.info("Loaded %d rows and validated %d unique IDs", len(texts), unique_comment_ids)

    started_at = datetime.now(timezone.utc)
    total_started = time.perf_counter()
    mx.reset_peak_memory()
    load_started = time.perf_counter()
    model, tokenizer = load(str(model_dir))
    load_seconds = time.perf_counter() - load_started
    if int(model.args.hidden_size) != int(config["representation"]["hidden_size"]):
        raise ValueError("Model hidden size differs from frozen representation config")
    if tokenizer.convert_tokens_to_ids(config["tokenizer"]["padding_token"]) != config["tokenizer"]["padding_token_id"]:
        raise ValueError("Padding token ID differs from frozen tokenizer config")

    feature_path = output_dir / "features.npy"
    features = np.lib.format.open_memmap(
        feature_path,
        mode="w+",
        dtype=np.float32,
        shape=(len(texts), int(config["representation"]["hidden_size"])),
    )
    batch_size = int(config["extraction"]["batch_size"])
    max_length = int(config["tokenizer"]["max_length"])
    pad_id = int(config["tokenizer"]["padding_token_id"])
    token_digest = hashlib.sha256()
    token_lengths: list[int] = []
    truncated_row_count = 0
    norm_sum = 0.0
    norm_min = float("inf")
    norm_max = 0.0
    forward_seconds = 0.0

    for start in range(0, len(texts), batch_size):
        stop = min(start + batch_size, len(texts))
        input_ids, attention_mask, lengths, batch_truncated_count = encode_batch(
            tokenizer,
            texts[start:stop],
            max_length=max_length,
            pad_id=pad_id,
            token_digest=token_digest,
            first_row_number=start + 1,
        )
        forward_started = time.perf_counter()
        hidden = model.model(mx.array(input_ids, dtype=mx.int32))
        mask = mx.array(attention_mask, dtype=mx.float32)[..., None]
        pooled = (hidden.astype(mx.float32) * mask).sum(axis=1) / mask.sum(axis=1)
        mx.eval(pooled)
        forward_seconds += time.perf_counter() - forward_started
        batch_features = np.asarray(pooled, dtype=np.float32)
        if batch_features.shape != (stop - start, features.shape[1]):
            raise ValueError(f"Unexpected pooled feature shape: {batch_features.shape}")
        if not np.isfinite(batch_features).all():
            raise ValueError(f"Non-finite feature in rows {start + 1}-{stop}")
        features[start:stop] = batch_features
        norms = np.linalg.norm(batch_features, axis=1)
        norm_sum += float(norms.sum())
        norm_min = min(norm_min, float(norms.min()))
        norm_max = max(norm_max, float(norms.max()))
        token_lengths.extend(lengths)
        truncated_row_count += batch_truncated_count
        del hidden, mask, pooled, batch_features

        elapsed_minutes = (time.perf_counter() - total_started) / 60.0
        if elapsed_minutes > config["resource_budget"]["extraction_wall_time_minutes_max_per_condition_split"]:
            raise TimeoutError("Extraction exceeded the frozen wall-time budget")
        if mx.get_peak_memory() / 1e9 > config["resource_budget"]["peak_mlx_memory_gb_max"]:
            raise MemoryError("Extraction exceeded the frozen MLX memory budget")
        if start == 0 or stop == len(texts) or stop % (batch_size * 250) == 0:
            logger.info("Extracted %d/%d rows", stop, len(texts))

    features.flush()
    del features, model, tokenizer, texts
    gc.collect()
    mx.clear_cache()
    total_seconds = time.perf_counter() - total_started
    feature_sha256 = sha256(feature_path)
    metadata = {
        "accessed_splits": [args.split],
        "condition": args.condition,
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-028",
        "feature": {
            "dtype": "float32",
            "path": str(feature_path.relative_to(PROJECT_ROOT)),
            "sha256": feature_sha256,
            "shape": [int(split_spec["rows"]), int(config["representation"]["hidden_size"])],
        },
        "git": git_metadata(),
        "gold_labels_used_for_features": False,
        "implementation_sha256": sha256(Path(__file__).resolve()),
        "model": {
            "condition": args.condition,
            "manifest_sha256": spec["manifest_sha256"],
            "repo_id": spec["repo_id"],
            "revision": spec["revision"],
        },
        "packages": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx-lm": importlib.metadata.version("mlx-lm"),
            "numpy": importlib.metadata.version("numpy"),
            "transformers": importlib.metadata.version("transformers"),
        },
        "privacy": {
            "contains_comment_ids": False,
            "contains_raw_text": False,
            "gitignored": True,
            "representation_may_encode_source_text": True,
        },
        "representation": config["representation"],
        "runtime": {
            "forward_seconds": forward_seconds,
            "load_seconds": load_seconds,
            "peak_mlx_memory_gb": mx.get_peak_memory() / 1e9,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "total_seconds": total_seconds,
        },
        "split": {
            "file_sha256": split_spec["sha256"],
            "name": args.split,
            "rows": int(split_spec["rows"]),
            "unique_comment_ids_validated": unique_comment_ids,
        },
        "started_at_utc": started_at.isoformat(),
        "status": "Completed",
        "test_absent_after_run": not test_path.exists(),
        "test_split_accessed": False,
        "tokenization": {
            "max_length": max_length,
            "token_count_max": max(token_lengths),
            "token_count_mean": float(np.mean(token_lengths)),
            "token_count_min": min(token_lengths),
            "token_id_stream_sha256": token_digest.hexdigest(),
            "truncated_row_count": truncated_row_count,
        },
        "vector_diagnostics": {
            "all_finite": True,
            "norm_max": norm_max,
            "norm_mean": norm_sum / len(token_lengths),
            "norm_min": norm_min,
        },
    }
    write_json(output_dir / "metadata.json", metadata)
    logger.info("Feature SHA-256: %s", feature_sha256)
    logger.info("Extraction complete in %.3f seconds; test accessed: no", total_seconds)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite extraction directory: {output_dir}")
    output_dir.mkdir(parents=True)
    logger = setup_logger(output_dir)
    try:
        execute(args, output_dir, logger)
    except Exception as error:
        logger.exception("EXP-028 feature extraction failed")
        write_json(
            output_dir / "failure.json",
            {
                "condition": args.condition,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": str(error),
                "error_type": type(error).__name__,
                "experiment_id": "EXP-028",
                "split": args.split,
                "status": "Failed",
                "test_split_accessed": False,
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    main()
