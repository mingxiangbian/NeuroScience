#!/usr/bin/env python3
"""Run an authorized EXP-052 head stage from the verified read-only cache."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import site
import subprocess
import sys
import time
import traceback
from typing import Any, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def load_sibling(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load sibling module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


head_common = load_sibling("exp052_head_common", "run_exp052_m2.py")
LABELS = head_common.LABELS
ALLOWED_SPLITS = ("train", "validation")
EXPECTED_FIELDS = head_common.EXPECTED_FIELDS
PREFLIGHT_STAGE = "seed-43-cache-reuse-preflight"
FORMAL_STAGE = "seed-43-cache-reuse-train-validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--private-dir", type=Path)
    return parser.parse_args()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path escapes project root: {recorded}")
    return resolved


def project_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def compact_artifact(record: dict[str, Any]) -> dict[str, Any]:
    return {name: record[name] for name in ("bytes", "path", "sha256")}


def require_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Byte-size mismatch for {path}")
    observed = sha256_file(path)
    if observed != record["sha256"]:
        raise ValueError(f"Hash mismatch for {path}: {observed}")
    return path


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"exp-052-cached-{run_dir.name}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    for handler in (
        logging.FileHandler(run_dir / "stdout.log", encoding="utf-8"),
        logging.StreamHandler(),
    ):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
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


def load_config(path: Path, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != "EXP-052" or config.get("tier") != "Major":
        raise ValueError("Unexpected EXP-052 cached-head contract identity")
    if config.get("stage") not in (PREFLIGHT_STAGE, FORMAL_STAGE):
        raise ValueError("Unexpected EXP-052 cached-head stage")
    authorization = config["authorization"]
    if seed != 43 or authorization.get("seeds") != [43]:
        raise PermissionError("This contract authorizes exactly seed 43")
    if authorization.get("splits") != ["train", "validation"]:
        raise PermissionError("Only train and validation are authorized")
    if authorization.get("test_access") is not False:
        raise PermissionError("Test must remain sealed")
    if authorization.get("seed_44_authorized") is not False:
        raise PermissionError("Seed 44 remains sealed")
    if authorization.get("exp_053_054_authorized") is not False:
        raise PermissionError("M3 and M4 remain sealed")
    formal = config["stage"] == FORMAL_STAGE
    if authorization.get("training_authorized") is not formal:
        raise PermissionError("Training authorization does not match stage")
    if authorization.get("performance_metrics_authorized") is not formal:
        raise PermissionError("Metric authorization does not match stage")

    for name, record in config["implementation"].items():
        path_value = resolve_project(record["path"])
        if sha256_file(path_value) != record["sha256"]:
            raise ValueError(f"Implementation hash drift: {name}")
    shared_path = require_artifact(config["shared_contract"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    if shared["data"]["model_access_whitelist"] != ["train", "validation"]:
        raise PermissionError("Shared split allowlist drift")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared contract no longer seals test")
    if shared["evaluation"]["seeds"] != [42, 43, 44]:
        raise ValueError("Shared seed registry drift")
    return config, shared


def freeze_sources(
    run_dir: Path, config: dict[str, Any], config_path: Path
) -> dict[str, Any]:
    sources = {"config": config_path.resolve()}
    for name, record in config["implementation"].items():
        sources[name] = resolve_project(record["path"])
    frozen: dict[str, Any] = {}
    for name, source in sources.items():
        target = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, target)
        frozen[name] = artifact(target)
    return frozen


def verify_cache_gate(
    config: dict[str, Any], shared: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = config["cache_reuse_gate"]
    run_path = require_artifact(gate["run"])
    verification_path = require_artifact(gate["verification"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("status") != "Completed"
        or run.get("stage") != "feature-cache-reuse-integrity-gate"
        or run.get("training_performed") is not False
        or run.get("performance_metrics_computed") is not False
        or run.get("qwen_forward_executed") is not False
        or run.get("test_split_accessed") is not False
    ):
        raise RuntimeError("Feature-cache reuse gate run drift")
    if (
        verification.get("status") != "Passed"
        or verification.get("check_count") != 74
        or verification.get("failed_checks")
        or verification.get("test_split_accessed") is not False
    ):
        raise RuntimeError("Feature-cache reuse gate is not 74/74 Passed")
    if run["frozen_contract"]["data_protocol"] != shared["data"]["protocol_id"]:
        raise ValueError("Cache-gate data protocol drift")
    if run["frozen_contract"]["model_revision"] != shared["models"]["qwen_shared"]["revision"]:
        raise ValueError("Cache-gate model revision drift")
    return run, verification


def verify_consumer_preflight(config: dict[str, Any]) -> dict[str, Any] | None:
    gate = config.get("consumer_preflight")
    if config["stage"] == PREFLIGHT_STAGE:
        if gate is not None:
            raise PermissionError("Preflight cannot depend on itself")
        return None
    if gate is None:
        raise PermissionError("Formal cached-head training requires a verified preflight")
    run_path = require_artifact(gate["run"])
    verification_path = require_artifact(gate["verification"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("status") != "Completed"
        or run.get("stage") != PREFLIGHT_STAGE
        or run.get("seed") != 43
        or run.get("training_performed") is not False
        or run.get("performance_metrics_computed") is not False
        or run.get("test_split_accessed") is not False
    ):
        raise RuntimeError("Seed-43 consumer preflight run drift")
    if (
        verification.get("status") != "Passed"
        or verification.get("failed_checks")
        or verification.get("test_split_accessed") is not False
    ):
        raise RuntimeError("Seed-43 consumer preflight did not pass")
    if run["model_runtime"]["head_initial_sha256"] != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("Preflight head initialization drift")
    return {
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "verification_check_count": verification["check_count"],
        "test_split_accessed": False,
    }


def load_split_rows(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ALLOWED_SPLITS:
        raise PermissionError(f"Cached-head runner cannot access split: {split}")
    data = shared["data"]
    path = resolve_project(data[f"{split}_path"])
    if sha256_file(path) != data[f"{split}_sha256"]:
        raise ValueError(f"{split} data hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != int(data[f"{split}_rows"]):
        raise ValueError(f"{split} row-count drift")
    sample_ids: set[str] = set()
    for row in rows:
        if set(row) != EXPECTED_FIELDS:
            raise ValueError(f"{split} schema drift")
        if row["sample_id"] in sample_ids:
            raise ValueError(f"{split} repeats a sample ID")
        sample_ids.add(row["sample_id"])
        if len(row["labels"]) != len(LABELS) or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError(f"{split} label-vector drift")
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


def load_cache(
    record: dict[str, Any], expected: dict[str, Any]
) -> tuple[np.memmap, dict[str, Any]]:
    path = require_artifact(record)
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if tuple(array.shape) != tuple(expected["shape"]):
        raise ValueError(f"Cache shape drift: {path}")
    if array.dtype != np.float32:
        raise ValueError(f"Cache dtype drift: {path}")
    if array.flags.writeable:
        raise PermissionError(f"Cache is not read-only: {path}")
    if not np.isfinite(array).all():
        raise ValueError(f"Cache contains non-finite values: {path}")
    return array, {
        "artifact": artifact(path),
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "mmap_mode": "r",
        "writeable": False,
        "all_finite": True,
        "source_seed": 42,
        "provenance": "verified_seed_42_reuse",
    }


def make_batch_orders(seed: int, row_count: int, epochs: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.stack([rng.permutation(row_count) for _ in range(epochs)]).astype(np.int32)


def order_digests(
    rows: Sequence[dict[str, Any]], orders: np.ndarray
) -> list[str]:
    return [
        canonical_digest([rows[int(index)]["sample_id"] for index in order])
        for order in orders
    ]


def environment_gate(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1" or os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 and PYTHONNOUSERSITE=1 are required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user site is enabled")
    import mlx
    import mlx.core as mx

    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("Cached-head execution requires the registered architecture")
    prefix = Path(sys.prefix).resolve()
    package_paths = {
        "mlx": Path(mx.__file__).resolve(),
        "numpy": Path(np.__file__).resolve(),
    }
    if any(prefix not in path.parents for path in package_paths.values()):
        raise RuntimeError("Dependencies resolved outside the active environment")
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    freeze_path = run_dir / "environment-freeze.txt"
    freeze_path.write_text(freeze + "\n", encoding="utf-8")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    mx.reset_peak_memory()
    return {
        "architecture": platform.machine(),
        "backend": "MLX_Apple_Metal_head_only",
        "environment_prefix": str(prefix),
        "executable": sys.executable,
        "package_paths": {name: str(path) for name, path in package_paths.items()},
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("mlx", "numpy", "safetensors")
        },
        "pip_check": pip_check or "No broken requirements found.",
        "python": platform.python_version(),
        "python_no_user_site": True,
        "freeze": artifact(freeze_path),
    }


def base_validation(
    config: dict[str, Any], shared: dict[str, Any], seed: int
) -> dict[str, Any]:
    gate_run, gate_verification = verify_cache_gate(config, shared)
    train_rows = load_split_rows(shared, "train")
    validation_rows = load_split_rows(shared, "validation")
    if {row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}:
        raise ValueError("Train/validation duplicate-component overlap")
    if {row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}:
        raise ValueError("Train/validation sample overlap")

    cache_started = time.perf_counter()
    cache_values: dict[str, np.memmap] = {}
    cache_records: dict[str, dict[str, Any]] = {}
    for split, rows in (("train", train_rows), ("validation", validation_rows)):
        expected = config["feature_cache"][split]
        gate_record = gate_run["feature_cache"][split]
        gate_artifact = compact_artifact(gate_record)
        if expected["artifact"] != gate_artifact:
            raise ValueError(f"{split} cache artifact differs from verified gate")
        order = canonical_digest([row["sample_id"] for row in rows])
        if order != expected["sample_order_sha256"] or order != gate_record["sample_order_sha256"]:
            raise ValueError(f"{split} sample-order digest drift")
        if expected["token_id_stream_sha256"] != gate_record["token_id_stream_sha256"]:
            raise ValueError(f"{split} token-stream digest drift")
        values, record = load_cache(expected["artifact"], expected)
        cache_values[split] = values
        cache_records[split] = {
            **record,
            "sample_order_sha256": order,
            "token_id_stream_sha256": expected["token_id_stream_sha256"],
            "sha256_before_use": record["artifact"]["sha256"],
        }

    spec = shared["models"]["qwen_shared"]
    head = head_common.build_head(seed, int(spec["hidden_size"]))
    initial_digest = head_common.mlx_tensor_digest(head_common.mlx_items(head))
    if initial_digest != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("Seed-43 head initialization hash drift")
    trainable_count = sum(int(tensor.size) for _, tensor in head_common.mlx_items(head))
    if trainable_count != int(spec["head_parameters"]):
        raise ValueError("Head parameter-count drift")
    orders = make_batch_orders(seed, len(train_rows), int(spec["epochs"]))
    digests = order_digests(train_rows, orders)
    return {
        "gate_run": gate_run,
        "gate_verification": gate_verification,
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "train_features": cache_values["train"],
        "validation_features": cache_values["validation"],
        "cache_records": cache_records,
        "cache_validation_seconds": time.perf_counter() - cache_started,
        "head": head,
        "head_initial_sha256": initial_digest,
        "head_trainable_parameter_count": trainable_count,
        "batch_orders": orders,
        "batch_order_sha256": digests,
    }


def common_result(
    *,
    config: dict[str, Any],
    shared: dict[str, Any],
    seed: int,
    validated: dict[str, Any],
    started: float,
    environment: dict[str, Any],
    frozen_sources: dict[str, Any],
) -> dict[str, Any]:
    for split in ALLOWED_SPLITS:
        path = resolve_project(validated["cache_records"][split]["artifact"]["path"])
        after = sha256_file(path)
        if after != validated["cache_records"][split]["sha256_before_use"]:
            raise ValueError(f"{split} cache changed during consumer use")
        validated["cache_records"][split]["sha256_after_use"] = after
    return {
        "schema_version": "exp-052-m2-cached-head-run-v1",
        "experiment_id": "EXP-052",
        "rq_id": "RQ-S1",
        "tier": "Major",
        "stage": config["stage"],
        "status": "Completed",
        "completed_at_utc": head_common.utc_now(),
        "seed": seed,
        "authorization": config["authorization"],
        "accessed_splits": ["train", "validation"],
        "validation_split_accessed": True,
        "test_split_accessed": False,
        "qwen_model_loaded": False,
        "qwen_forward_executed": False,
        "feature_extraction_performed": False,
        "data": {
            "protocol_id": shared["data"]["protocol_id"],
            "labels": list(LABELS),
            "train": {
                "sha256": shared["data"]["train_sha256"],
                "summary": split_summary(validated["train_rows"]),
            },
            "validation": {
                "sha256": shared["data"]["validation_sha256"],
                "summary": split_summary(validated["validation_rows"]),
            },
            "cross_split_component_overlap": 0,
            "cross_split_sample_overlap": 0,
            "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
        },
        "model": {
            "repo_id": shared["models"]["qwen_shared"]["repo_id"],
            "revision": shared["models"]["qwen_shared"]["revision"],
            "backbone_execution": "not_executed_verified_seed_42_cache_reused",
        },
        "model_runtime": {
            "qwen_parameters_frozen": True,
            "qwen_trainable_parameter_count": 0,
            "head_trainable_parameter_count": validated["head_trainable_parameter_count"],
            "head_initial_sha256": validated["head_initial_sha256"],
            "pooling": shared["prompt"]["pooling"],
            "feature_dtype": "float32",
        },
        "feature_cache": validated["cache_records"],
        "batch_order": {
            "rng": config["execution"]["batch_order_rng"],
            "epoch_sha256": validated["batch_order_sha256"],
        },
        "cache_reuse_gate": {
            "run": artifact(require_artifact(config["cache_reuse_gate"]["run"])),
            "verification": artifact(require_artifact(config["cache_reuse_gate"]["verification"])),
            "verification_check_count": validated["gate_verification"]["check_count"],
            "test_split_accessed": False,
        },
        "environment": environment,
        "git": git_metadata(),
        "resource_usage": {
            "api_cost_usd": 0,
            "wall_seconds": time.perf_counter() - started,
            "model_load_seconds": 0,
            "qwen_forward_seconds": 0,
            "feature_extraction_seconds": 0,
            "cache_validation_seconds": validated["cache_validation_seconds"],
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "reused_features_and_new_row_level_predictions": "private_gitignored",
        },
        "artifacts": {"frozen_sources": frozen_sources},
    }


def run_preflight(
    *, config: dict[str, Any], shared: dict[str, Any], seed: int,
    started: float, environment: dict[str, Any], frozen_sources: dict[str, Any]
) -> dict[str, Any]:
    validated = base_validation(config, shared, seed)
    result = common_result(
        config=config, shared=shared, seed=seed, validated=validated,
        started=started, environment=environment, frozen_sources=frozen_sources,
    )
    result.update(
        {
            "training_performed": False,
            "performance_metrics_computed": False,
            "warnings": [
                "This preflight authorizes no training or performance conclusion.",
                "Linear decodability does not establish an internal emotion mechanism.",
            ],
        }
    )
    return result


def run_formal(
    *, config: dict[str, Any], shared: dict[str, Any], seed: int,
    run_dir: Path, private_dir: Path, logger: logging.Logger, started: float,
    environment: dict[str, Any], frozen_sources: dict[str, Any]
) -> dict[str, Any]:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim

    preflight = verify_consumer_preflight(config)
    validated = base_validation(config, shared, seed)
    train_rows = validated["train_rows"]
    validation_rows = validated["validation_rows"]
    train_features = validated["train_features"]
    validation_features = validated["validation_features"]
    head = validated["head"]
    orders = validated["batch_orders"]
    spec = shared["models"]["qwen_shared"]

    batch_order_path = private_dir / "batch-orders.npy"
    np.save(batch_order_path, orders, allow_pickle=False)
    os.chmod(batch_order_path, 0o600)
    train_gold = np.asarray([row["labels"] for row in train_rows], dtype=np.float32)
    validation_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)

    def loss_fn(module: Any, features: Any, targets: Any) -> Any:
        return nn.losses.binary_cross_entropy(
            module(features), targets, with_logits=True, reduction="mean"
        )

    optimizer = optim.AdamW(
        learning_rate=float(spec["head_learning_rate"]),
        weight_decay=float(spec["head_weight_decay"]),
    )
    loss_and_grad = nn.value_and_grad(head, loss_fn)
    checkpoints = private_dir / "head-checkpoints"
    checkpoints.mkdir(mode=0o700)
    history: list[dict[str, Any]] = []
    epoch_probabilities: list[np.ndarray] = []
    global_step = 0
    training_started = time.perf_counter()
    for epoch_index, order in enumerate(orders, start=1):
        epoch_started = time.perf_counter()
        loss_sum = 0.0
        for position, row_index in enumerate(order, start=1):
            feature = mx.array(
                np.asarray(train_features[row_index : row_index + 1]), dtype=mx.float32
            )
            target = mx.array(train_gold[row_index : row_index + 1], dtype=mx.float32)
            loss, gradients = loss_and_grad(head, feature, target)
            optimizer.update(head, gradients)
            mx.eval(loss, head.parameters(), optimizer.state)
            value = float(loss.item())
            if not math.isfinite(value):
                raise ValueError(f"Non-finite loss at epoch {epoch_index}, step {position}")
            loss_sum += value
            global_step += 1
            if position % int(config["execution"]["head_log_every_steps"]) == 0 or position == len(order):
                logger.info(
                    "Seed %d epoch %d head step %d/%d loss %.6f",
                    seed, epoch_index, position, len(order), loss_sum / position,
                )
            if (time.perf_counter() - training_started) / 60 > float(config["execution"]["maximum_head_training_minutes"]):
                raise TimeoutError("Cached-head training exceeded the frozen budget")

        validation_loss, probabilities = head_common.evaluate_head(
            head, validation_features, validation_gold
        )
        fixed_predictions = (
            probabilities >= float(shared["evaluation"]["fixed_threshold"])
        ).astype(np.uint8)
        fixed_metrics = head_common.metric_bundle(validation_gold, fixed_predictions)
        checkpoint_path = checkpoints / f"epoch-{epoch_index}.safetensors"
        head_common.save_head(checkpoint_path, head)
        epoch_probabilities.append(probabilities)
        history.append(
            {
                "seed": seed,
                "epoch": epoch_index,
                "optimizer_steps": global_step,
                "train_loss": loss_sum / len(order),
                "validation_loss": validation_loss,
                "fixed_threshold": float(shared["evaluation"]["fixed_threshold"]),
                "fixed_macro_precision": fixed_metrics["macro"]["precision"],
                "fixed_macro_recall": fixed_metrics["macro"]["recall"],
                "fixed_macro_f1": fixed_metrics["macro"]["f1"],
                "fixed_micro_f1": fixed_metrics["micro_f1"],
                "fixed_weighted_f1": fixed_metrics["weighted_f1"],
                "fixed_subset_accuracy": fixed_metrics["subset_accuracy"],
                "fixed_hamming_loss": fixed_metrics["hamming_loss"],
                "fixed_five_label_macro_f1_without_surprise": fixed_metrics["five_label_macro_f1_without_surprise"],
                "batch_order_sha256": validated["batch_order_sha256"][epoch_index - 1],
                "epoch_seconds": time.perf_counter() - epoch_started,
            }
        )
        logger.info(
            "Seed %d epoch %d complete: train_loss=%.6f val_loss=%.6f fixed_macro_f1=%.6f",
            seed, epoch_index, loss_sum / len(order), validation_loss,
            fixed_metrics["macro"]["f1"],
        )

    if global_step != int(spec["total_iterations_per_seed"]):
        raise ValueError("Head optimizer-step count drift")
    training_seconds = time.perf_counter() - training_started
    probabilities = np.stack(epoch_probabilities).astype(np.float32, copy=False)
    selection = head_common.select_checkpoint(
        history, float(shared["evaluation"]["practical_tie_delta"])
    )
    selected_epoch = int(selection["selected_epoch"])
    selected_probabilities = probabilities[selected_epoch - 1]
    selected_head = private_dir / "selected-head.safetensors"
    shutil.copy2(checkpoints / f"epoch-{selected_epoch}.safetensors", selected_head)
    os.chmod(selected_head, 0o600)
    fixed_threshold = float(shared["evaluation"]["fixed_threshold"])
    selected_threshold, threshold_rows = head_common.select_threshold(
        validation_gold,
        selected_probabilities,
        shared["evaluation"]["shared_threshold_grid"],
    )
    fixed_predictions = (selected_probabilities >= fixed_threshold).astype(np.uint8)
    calibrated_predictions = (selected_probabilities >= selected_threshold).astype(np.uint8)
    fixed_metrics = head_common.metric_bundle(validation_gold, fixed_predictions)
    calibrated_metrics = head_common.metric_bundle(validation_gold, calibrated_predictions)
    component_ids = [row["component_id"] for row in validation_rows]
    bootstrap = {
        "fixed_0.5": head_common.bootstrap_summary(
            validation_gold, fixed_predictions, component_ids, seed,
            int(shared["evaluation"]["bootstrap"]["replicates"]),
            shared["evaluation"]["bootstrap"]["seed_namespace"], "fixed-0.5",
        ),
        "shared_threshold": head_common.bootstrap_summary(
            validation_gold, calibrated_predictions, component_ids, seed,
            int(shared["evaluation"]["bootstrap"]["replicates"]),
            shared["evaluation"]["bootstrap"]["seed_namespace"],
            f"shared-{selected_threshold:.2f}",
        ),
    }

    predictions_path = private_dir / "validation-predictions.npz"
    np.savez_compressed(
        predictions_path,
        probabilities=probabilities,
        gold=validation_gold,
        fixed_predictions=fixed_predictions,
        shared_threshold_predictions=calibrated_predictions,
        sample_ids=np.asarray([row["sample_id"] for row in validation_rows]),
        component_ids=np.asarray(component_ids),
    )
    os.chmod(predictions_path, 0o600)

    history_path = run_dir / "history.csv"
    threshold_path = run_dir / "threshold-grid.csv"
    fixed_metrics_path = run_dir / "metrics-fixed-0.5.json"
    calibrated_metrics_path = run_dir / "metrics-shared-threshold.json"
    bootstrap_path = run_dir / "bootstrap.json"
    selection_path = run_dir / "selection.json"
    head_common.write_history(history_path, history)
    head_common.write_threshold_grid(threshold_path, threshold_rows)
    atomic_json(fixed_metrics_path, fixed_metrics)
    atomic_json(calibrated_metrics_path, calibrated_metrics)
    atomic_json(bootstrap_path, bootstrap)
    atomic_json(selection_path, selection)
    tables: dict[str, Any] = {}
    for name, metrics in (
        ("fixed-0.5", fixed_metrics),
        ("shared-threshold", calibrated_metrics),
    ):
        per_label = run_dir / f"per-label-{name}.csv"
        confusion = run_dir / f"multilabel-confusion-{name}.csv"
        head_common.write_per_label(per_label, metrics)
        head_common.write_confusion(confusion, metrics)
        tables[name] = {"per_label": artifact(per_label), "confusion": artifact(confusion)}

    final_digest = head_common.mlx_tensor_digest(head_common.mlx_items(head))
    if final_digest == validated["head_initial_sha256"]:
        raise ValueError("Seed-43 head did not update")
    private_manifest_path = private_dir / "private-manifest.json"
    private_manifest = {
        "experiment_id": "EXP-052",
        "stage": FORMAL_STAGE,
        "seed": seed,
        "contains_raw_text": False,
        "contains_reused_row_level_features": True,
        "contains_new_row_level_probabilities": True,
        "source_feature_cache": {
            split: validated["cache_records"][split]["artifact"]
            for split in ALLOWED_SPLITS
        },
        "batch_orders": artifact(batch_order_path),
        "validation_predictions": artifact(predictions_path),
        "selected_head": artifact(selected_head),
    }
    atomic_json(private_manifest_path, private_manifest, private=True)

    result = common_result(
        config=config, shared=shared, seed=seed, validated=validated,
        started=started, environment=environment, frozen_sources=frozen_sources,
    )
    result.update(
        {
            "training_performed": True,
            "performance_metrics_computed": True,
            "consumer_preflight": preflight,
            "model_runtime": {
                **result["model_runtime"],
                "head_final_in_memory_sha256": final_digest,
            },
            "training": {
                "epochs": int(spec["epochs"]),
                "batch_size": int(spec["batch_size"]),
                "gradient_accumulation_steps": int(spec["gradient_accumulation_steps"]),
                "optimizer": spec["head_optimizer"],
                "learning_rate": float(spec["head_learning_rate"]),
                "weight_decay": float(spec["head_weight_decay"]),
                "loss": "unweighted_binary_cross_entropy_with_logits",
                "scheduler": "none",
                "batch_order_rng": config["execution"]["batch_order_rng"],
                "total_optimizer_steps": global_step,
                "history": history,
            },
            "selection": selection,
            "threshold_selection": {
                "selected_threshold": selected_threshold,
                "grid": list(shared["evaluation"]["shared_threshold_grid"]),
                "rule": shared["evaluation"]["shared_threshold_rule"],
            },
            "metrics": {"fixed_0.5": fixed_metrics, "shared_threshold": calibrated_metrics},
            "bootstrap": bootstrap,
            "resource_usage": {
                **result["resource_usage"],
                "head_training_seconds": training_seconds,
                "peak_mlx_memory_gb": float(mx.get_peak_memory()) / 1e9,
                "peak_process_rss_gb": (
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
                    if platform.system() == "Darwin"
                    else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / 1e9
                ),
            },
            "warnings": [
                "Seed 43 is not a frozen three-seed M2 result.",
                "Linear-head performance supports decodability, not an internal emotion mechanism.",
                "The shared threshold is selected on validation and cannot be tuned on test.",
            ],
            "artifacts": {
                **result["artifacts"],
                "history": artifact(history_path),
                "threshold_grid": artifact(threshold_path),
                "metrics_fixed": artifact(fixed_metrics_path),
                "metrics_shared_threshold": artifact(calibrated_metrics_path),
                "bootstrap": artifact(bootstrap_path),
                "selection": artifact(selection_path),
                "tables": tables,
                "private_manifest": artifact(private_manifest_path),
                "train_features_private": validated["cache_records"]["train"]["artifact"],
                "validation_features_private": validated["cache_records"]["validation"]["artifact"],
                "batch_orders_private": artifact(batch_order_path),
                "validation_predictions_private": artifact(predictions_path),
                "selected_head_private": artifact(selected_head),
            },
        }
    )
    return result


def render_report(run: dict[str, Any]) -> str:
    if run["stage"] == PREFLIGHT_STAGE:
        lines = [
            "# EXP-052 Seed 43 Cache-reuse Preflight", "",
            f"- Status: `{run['status']}`; independent verification pending",
            "- Cache: verified seed-42 train/validation features, read-only",
            "- Training performed: no", "- Performance metrics computed: no",
            "- Qwen loaded or executed: no", "- Test accessed: no", "",
        ]
    else:
        lines = [
            "# EXP-052 M2 Cached Head - Seed 43", "",
            f"- Status: `{run['status']}`; independent verification pending",
            f"- Fixed 0.5 Macro-F1: `{run['metrics']['fixed_0.5']['macro']['f1']:.6f}`",
            f"- Shared-threshold Macro-F1: `{run['metrics']['shared_threshold']['macro']['f1']:.6f}`",
            f"- Selected threshold: `{run['threshold_selection']['selected_threshold']:.2f}`",
            "- Qwen loaded or executed: no; verified feature cache reused",
            "- Test accessed: no", "",
        ]
    return "\n".join(lines)


def run() -> dict[str, Any]:
    args = parse_args()
    config_path = args.config.resolve()
    config, shared = load_config(config_path, args.seed)
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_dir"])).resolve()
    private_dir = None
    if config["stage"] == FORMAL_STAGE:
        private_dir = (
            args.private_dir or resolve_project(config["execution"]["private_run_dir"])
        ).resolve()
    if run_dir.exists() or (private_dir is not None and private_dir.exists()):
        raise FileExistsError("Refusing to overwrite append-only cached-head output")
    run_dir.mkdir(parents=True)
    if private_dir is not None:
        private_dir.mkdir(parents=True, mode=0o700)
        os.chmod(private_dir, 0o700)
    logger = setup_logger(run_dir)
    run_path = run_dir / "run.json"
    started = time.perf_counter()
    initial = {
        "schema_version": "exp-052-m2-cached-head-run-v1",
        "experiment_id": "EXP-052",
        "stage": config["stage"],
        "seed": args.seed,
        "status": "Running",
        "started_at_utc": head_common.utc_now(),
        "accessed_splits": [],
        "test_split_accessed": False,
        "training_performed": False,
        "performance_metrics_computed": False,
        "qwen_model_loaded": False,
        "qwen_forward_executed": False,
    }
    atomic_json(run_path, initial)
    try:
        logger.info("EXP-052 %s started", config["stage"])
        frozen_sources = freeze_sources(run_dir, config, config_path)
        environment = environment_gate(run_dir, config)
        if config["stage"] == PREFLIGHT_STAGE:
            completed = run_preflight(
                config=config, shared=shared, seed=args.seed, started=started,
                environment=environment, frozen_sources=frozen_sources,
            )
        else:
            assert private_dir is not None
            completed = run_formal(
                config=config, shared=shared, seed=args.seed, run_dir=run_dir,
                private_dir=private_dir, logger=logger, started=started,
                environment=environment, frozen_sources=frozen_sources,
            )
        report_path = run_dir / "REPORT.md"
        report_path.write_text(render_report(completed), encoding="utf-8")
        completed["artifacts"]["report"] = artifact(report_path)
        flush_logger(logger)
        completed["artifacts"]["stdout_log"] = artifact(run_dir / "stdout.log")
        atomic_json(run_path, completed)
        logger.info("EXP-052 %s completed; test accessed: no", config["stage"])
        return completed
    except Exception as error:
        logger.exception("EXP-052 %s failed", config["stage"])
        initial.update(
            {
                "status": "Failed",
                "failed_at_utc": head_common.utc_now(),
                "failure": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
            }
        )
        atomic_json(run_path, initial)
        raise


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
