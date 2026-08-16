#!/usr/bin/env python3
"""Run an authorized EXP-052 frozen-Qwen linear-head stage."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
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
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path escapes project root: {recorded}")
    return resolved


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def require_hash(path: Path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"Hash mismatch for {path}: expected {expected}, got {observed}")
    return artifact(path)


def setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"exp-052-{run_dir.name}")
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


def implementation_paths(config: dict[str, Any], config_path: Path) -> dict[str, Path]:
    paths = {"config": config_path.resolve()}
    for name, record in config["implementation"].items():
        if isinstance(record, dict) and "path" in record:
            paths[name] = resolve_project(record["path"])
    paths["shared-config"] = resolve_project(config["prerequisite"]["shared_config_path"])
    return paths


def load_config(path: Path, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != "EXP-052" or config.get("tier") != "Major":
        raise ValueError("Unexpected EXP-052 run contract identity")
    if config.get("stage") not in ("train-only-dry-run", "seed-42-train-validation-integrity-gate"):
        raise ValueError("Unknown EXP-052 stage")
    authorization = config["authorization"]
    if authorization["seeds"] != [seed] or seed != 42:
        raise PermissionError("This contract authorizes exactly seed 42")
    expected_splits = ["train"] if config["stage"] == "train-only-dry-run" else ["train", "validation"]
    if authorization["splits"] != expected_splits or authorization["test_access"] is not False:
        raise PermissionError("Split authorization does not match the requested stage")
    if authorization["seeds_43_44_authorized"] is not False:
        raise PermissionError("Unrequested EXP-052 seeds must remain sealed")
    if authorization["exp_053_054_authorized"] is not False:
        raise PermissionError("M3 and M4 must remain sealed")

    for name, record in config["implementation"].items():
        if isinstance(record, dict) and "path" in record:
            require_hash(resolve_project(record["path"]), record["sha256"])

    prerequisite = config["prerequisite"]
    shared_path = resolve_project(prerequisite["shared_config_path"])
    require_hash(shared_path, prerequisite["shared_config_sha256"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    if shared["models"]["m2"]["experiment_id"] != "EXP-052":
        raise ValueError("Shared M2 identity drift")
    if tuple(shared["evaluation"]["seeds"]) != (42, 43, 44):
        raise ValueError("Shared seed registry drift")
    if tuple(shared["data"]["model_access_whitelist"]) != ("train", "validation"):
        raise ValueError("Shared split allowlist drift")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared contract no longer seals test")
    return config, shared


def prepare_dirs(run_dir: Path, private_dir: Path) -> None:
    for path in (run_dir, private_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite append-only output: {path}")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)


def freeze_sources(
    run_dir: Path, config: dict[str, Any], config_path: Path
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name, source in implementation_paths(config, config_path).items():
        if not source.is_file():
            raise FileNotFoundError(source)
        target = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, target)
        records[name] = artifact(target)
    return records


def verify_exp050(config: dict[str, Any]) -> dict[str, Any]:
    prerequisite = config["prerequisite"]
    run_path = resolve_project(prerequisite["exp050_run_path"])
    verification_path = resolve_project(prerequisite["exp050_verification_path"])
    m2_path = resolve_project(prerequisite["exp050_m2_path"])
    require_hash(run_path, prerequisite["exp050_run_sha256"])
    require_hash(verification_path, prerequisite["exp050_verification_sha256"])
    require_hash(m2_path, prerequisite["exp050_m2_sha256"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    m2 = json.loads(m2_path.read_text(encoding="utf-8"))
    if run["status"] != "Passed" or verification["status"] != "Passed":
        raise RuntimeError("EXP-050 is not verified")
    if verification["checks_total"] != 77 or verification["failed_checks"]:
        raise RuntimeError("EXP-050 independent gate drift")
    if m2["status"] != "Passed" or m2["qwen_parameters_frozen"] is not True:
        raise RuntimeError("EXP-050 M2 gate drift")
    if m2["head_initial_sha256"] != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("EXP-050 head initialization hash drift")
    if run["test_split_accessed"] is not False or verification["test_split_accessed"] is not False:
        raise PermissionError("EXP-050 no longer proves the test remained sealed")
    return {
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "m2": artifact(m2_path),
        "check_count": verification["checks_total"],
        "head_initial_sha256": m2["head_initial_sha256"],
    }


def verify_dry_run_gate(config: dict[str, Any]) -> dict[str, Any] | None:
    gate = config.get("dry_run_gate")
    if gate is None:
        return None
    run_path = resolve_project(gate["run_path"])
    verification_path = resolve_project(gate["verification_path"])
    require_hash(run_path, gate["run_sha256"])
    require_hash(verification_path, gate["verification_sha256"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if run.get("stage") != "train-only-dry-run" or run.get("status") != "Completed":
        raise RuntimeError("EXP-052 dry-run did not complete")
    if verification.get("status") != "Passed" or verification.get("failed_checks"):
        raise RuntimeError("EXP-052 dry-run did not pass independent verification")
    if run["performance_metrics_computed"] is not False:
        raise RuntimeError("Dry-run computed a forbidden performance metric")
    if run["resource_projection"]["projected_feature_extraction_minutes_with_safety"] > config["execution"]["maximum_feature_extraction_minutes"]:
        raise TimeoutError("Dry-run projection exceeds the formal extraction budget")
    if run["resource_usage"]["peak_mlx_memory_gb"] > config["execution"]["maximum_peak_memory_gb"]:
        raise MemoryError("Dry-run exceeds the formal memory budget")
    return {
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "verification_check_count": verification["check_count"],
        "projected_feature_extraction_minutes_with_safety": run["resource_projection"]["projected_feature_extraction_minutes_with_safety"],
        "peak_mlx_memory_gb": run["resource_usage"]["peak_mlx_memory_gb"],
        "test_split_accessed": False,
    }


def environment_gate(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1" or os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PIP_USER=0 and PYTHONNOUSERSITE=1 are required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user site is enabled")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise RuntimeError("Offline model mode is required")

    import mlx
    import mlx.core as mx
    import mlx_lm
    import transformers

    prefix = Path(sys.prefix).resolve()
    package_paths = {
        "mlx": Path(mlx.__file__).resolve(),
        "mlx-lm": Path(mlx_lm.__file__).resolve(),
        "numpy": Path(np.__file__).resolve(),
        "transformers": Path(transformers.__file__).resolve(),
    }
    outside = {name: str(path) for name, path in package_paths.items() if prefix not in path.parents}
    if outside:
        raise RuntimeError(f"Dependencies outside active environment: {outside}")
    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("EXP-052 requires the registered Apple Silicon architecture")

    frozen = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True, text=True
    ).stdout.strip()
    freeze_path = run_dir / "environment-freeze.txt"
    freeze_path.write_text(frozen + "\n", encoding="utf-8")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"], check=True, capture_output=True, text=True
    ).stdout.strip()
    mx.reset_peak_memory()
    return {
        "architecture": platform.machine(),
        "backend": "MLX_Apple_Metal",
        "environment_prefix": str(prefix),
        "executable": sys.executable,
        "package_paths": {name: str(path) for name, path in package_paths.items()},
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("mlx", "mlx-lm", "numpy", "safetensors", "transformers")
        },
        "pip_check": pip_check or "No broken requirements found.",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_no_user_site": True,
        "freeze": artifact(freeze_path),
    }


def verify_model(shared: dict[str, Any]) -> dict[str, Any]:
    spec = shared["models"]["qwen_shared"]
    manifest_path = resolve_project(spec["manifest_path"])
    require_hash(manifest_path, spec["manifest_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != spec["repo_id"] or manifest["revision"] != spec["revision"]:
        raise ValueError("Qwen repository or revision drift")
    model_root = resolve_project(spec["local_path"])
    verified = []
    for expected in manifest["mlx_bf16"]["files"]:
        path = model_root / expected["path"]
        observed = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if observed != expected:
            raise ValueError(f"Qwen model file drift: {expected['path']}")
        verified.append(observed)
    return {
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "manifest": artifact(manifest_path),
        "snapshot": project_path(model_root),
        "file_count": len(verified),
        "total_bytes": sum(item["bytes"] for item in verified),
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


def select_dry_rows(
    rows: Sequence[dict[str, Any]], count: int, namespace: str
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )
    selected: dict[str, dict[str, Any]] = {}
    for label_index, label in enumerate(LABELS):
        positives = [row for row in ranked if row["labels"][label_index] == 1]
        for row in sorted(
            positives,
            key=lambda item: hashlib.sha256(
                f"{namespace}|positive|{label}|{item['sample_id']}".encode()
            ).hexdigest(),
        )[:2]:
            selected[row["sample_id"]] = row
    for row in ranked:
        selected.setdefault(row["sample_id"], row)
        if len(selected) == count:
            break
    output = sorted(
        selected.values(),
        key=lambda row: hashlib.sha256(
            f"{namespace}|final|{row['sample_id']}".encode()
        ).hexdigest(),
    )
    if len(output) != count:
        raise ValueError("Dry-run selection size drift")
    if any(sum(row["labels"][index] for row in output) < 2 for index in range(len(LABELS))):
        raise ValueError("Dry-run selection lacks label coverage")
    return output


def load_prompt(shared: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project(shared["prompt"]["path"])
    require_hash(path, shared["prompt"]["sha256"])
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_messages(prompt: dict[str, Any], text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]},
    ]


def _apply_chat(tokenizer: Any, prompt: dict[str, Any], text: str) -> list[int]:
    value = tokenizer.apply_chat_template(
        prompt_messages(prompt, text),
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise TypeError("Tokenizer must return a plain list of integer token IDs")
    return value


def qwen_prompt_ids(
    tokenizer: Any, prompt: dict[str, Any], text: str, limit: int
) -> tuple[list[int], int, bool]:
    full = _apply_chat(tokenizer, prompt, text)
    raw_length = len(full)
    if raw_length <= limit:
        selected = full
        truncated = False
    else:
        target_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high = 0, len(target_ids)
        selected = _apply_chat(tokenizer, prompt, "")
        while low <= high:
            middle = (low + high) // 2
            candidate_text = tokenizer.decode(target_ids[:middle], skip_special_tokens=False)
            candidate = _apply_chat(tokenizer, prompt, candidate_text)
            if len(candidate) <= limit:
                selected = candidate
                low = middle + 1
            else:
                high = middle - 1
        truncated = True
    if not selected or len(selected) > limit:
        raise ValueError("Unable to satisfy the frozen Qwen length contract")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Qwen prompt does not preserve the empty-think suffix")
    return selected, raw_length, truncated


def mlx_items(module: Any) -> list[tuple[str, Any]]:
    from mlx.utils import tree_flatten

    return list(tree_flatten(module.trainable_parameters()))


def mlx_tensor_digest(items: Sequence[tuple[str, Any]]) -> str:
    import mlx.core as mx

    digest = hashlib.sha256()
    for name, tensor in sorted(items):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def build_head(seed: int, hidden_size: int) -> Any:
    import mlx.core as mx
    import mlx.nn as nn

    mx.random.seed(seed)
    return nn.Linear(hidden_size, len(LABELS), bias=True)


def extract_features(
    *,
    rows: Sequence[dict[str, Any]],
    split: str,
    output_dir: Path,
    model: Any,
    tokenizer: Any,
    prompt: dict[str, Any],
    shared: dict[str, Any],
    logger: logging.Logger,
    extraction_started: float,
    maximum_minutes: float,
    maximum_peak_memory_gb: float,
    log_every: int,
) -> tuple[np.memmap, dict[str, Any]]:
    import mlx.core as mx

    hidden_size = int(shared["models"]["qwen_shared"]["hidden_size"])
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    feature_path = output_dir / "features.npy"
    features = np.lib.format.open_memmap(
        feature_path, mode="w+", dtype=np.float32, shape=(len(rows), hidden_size)
    )
    token_digest = hashlib.sha256()
    lengths: list[int] = []
    raw_lengths: list[int] = []
    truncated_rows = 0
    forward_seconds = 0.0
    norm_sum = 0.0
    norm_min = float("inf")
    norm_max = 0.0
    limit = int(shared["prompt"]["max_sequence_length"])

    for index, row in enumerate(rows):
        ids, raw_length, truncated = qwen_prompt_ids(
            tokenizer, prompt, row["text"], limit
        )
        canonical = np.asarray(ids, dtype="<i4")
        token_digest.update((index + 1).to_bytes(8, "little", signed=False))
        token_digest.update(len(ids).to_bytes(4, "little", signed=False))
        token_digest.update(canonical.tobytes(order="C"))
        forward_started = time.perf_counter()
        hidden = model.model(mx.array([ids], dtype=mx.int32))
        pooled = hidden[:, -1, :].astype(mx.float32)
        mx.eval(pooled)
        forward_seconds += time.perf_counter() - forward_started
        value = np.asarray(pooled, dtype=np.float32)
        if value.shape != (1, hidden_size) or not np.isfinite(value).all():
            raise ValueError(f"Invalid {split} feature at row {index + 1}")
        features[index] = value[0]
        norm = float(np.linalg.norm(value[0]))
        norm_sum += norm
        norm_min = min(norm_min, norm)
        norm_max = max(norm_max, norm)
        lengths.append(len(ids))
        raw_lengths.append(raw_length)
        truncated_rows += int(truncated)
        del hidden, pooled, value

        elapsed_minutes = (time.perf_counter() - extraction_started) / 60.0
        if elapsed_minutes > maximum_minutes:
            raise TimeoutError("Feature extraction exceeded the frozen wall-time budget")
        if float(mx.get_peak_memory()) / 1e9 > maximum_peak_memory_gb:
            raise MemoryError("Feature extraction exceeded the frozen MLX memory budget")
        completed = index + 1
        if completed == 1 or completed == len(rows) or completed % log_every == 0:
            features.flush()
            logger.info("Extracted %s features %d/%d", split, completed, len(rows))
        if completed % 100 == 0:
            mx.clear_cache()

    features.flush()
    os.chmod(feature_path, 0o600)
    order_digest = canonical_digest([row["sample_id"] for row in rows])
    metadata = {
        "split": split,
        "rows": len(rows),
        "feature": artifact(feature_path),
        "shape": [len(rows), hidden_size],
        "dtype": "float32",
        "gold_labels_used_for_features": False,
        "sample_order_sha256": order_digest,
        "token_id_stream_sha256": token_digest.hexdigest(),
        "token_lengths": {
            "minimum": min(lengths),
            "maximum": max(lengths),
            "mean": float(np.mean(lengths)),
            "p95": float(np.quantile(lengths, 0.95)),
            "raw_maximum": max(raw_lengths),
            "truncated_rows": truncated_rows,
        },
        "forward_seconds": forward_seconds,
        "vector_diagnostics": {
            "all_finite": True,
            "norm_min": norm_min,
            "norm_max": norm_max,
            "norm_mean": norm_sum / len(rows),
        },
        "privacy": {
            "contains_raw_text": False,
            "contains_row_identifiers": False,
            "representation_may_encode_source_text": True,
            "gitignored": True,
        },
    }
    atomic_json(output_dir / "metadata.json", metadata, private=True)
    return features, metadata


def head_arrays(head: Any) -> tuple[np.ndarray, np.ndarray]:
    values = {name: np.asarray(tensor, dtype=np.float32) for name, tensor in mlx_items(head)}
    if set(values) != {"weight", "bias"}:
        raise ValueError(f"Unexpected head tensor names: {sorted(values)}")
    if values["weight"].shape != (len(LABELS), 2560) or values["bias"].shape != (len(LABELS),):
        raise ValueError("Head tensor shape drift")
    return values["weight"], values["bias"]


def sigmoid(logits: np.ndarray) -> np.ndarray:
    output = np.empty_like(logits, dtype=np.float32)
    positive = logits >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exp_value = np.exp(logits[~positive])
    output[~positive] = exp_value / (1.0 + exp_value)
    return output


def evaluate_head(
    head: Any, features: np.ndarray, labels: np.ndarray
) -> tuple[float, np.ndarray]:
    weight, bias = head_arrays(head)
    logits = np.asarray(features, dtype=np.float32) @ weight.T + bias
    loss = float(np.mean(np.logaddexp(0.0, logits) - labels.astype(np.float32) * logits))
    probabilities = sigmoid(logits)
    if probabilities.shape != labels.shape or not np.isfinite(probabilities).all() or not math.isfinite(loss):
        raise ValueError("Invalid head evaluation")
    return loss, probabilities


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    precision = np.divide(tp, tp + fp, out=np.zeros(6, dtype=np.float64), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros(6, dtype=np.float64), where=(tp + fn) != 0)
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(6, dtype=np.float64), where=(2 * tp + fp + fn) != 0)
    micro_denominator = 2 * tp.sum() + fp.sum() + fn.sum()
    micro_f1 = float(2 * tp.sum() / micro_denominator) if micro_denominator else 0.0
    support = tp + fn
    weighted_f1 = float(np.sum(f1 * support) / support.sum()) if support.sum() else 0.0
    cardinality = predicted.sum(axis=1)
    without_surprise = [0, 1, 3, 4, 5]
    return {
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(np.mean(gold != predicted)),
        "macro": {
            "precision": float(np.mean(precision)),
            "recall": float(np.mean(recall)),
            "f1": float(np.mean(f1)),
        },
        "micro_f1": micro_f1,
        "weighted_f1": weighted_f1,
        "five_label_macro_f1_without_surprise": float(np.mean(f1[without_surprise])),
        "per_label": {
            label: {
                "label_id": index,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "predicted_support": int(tp[index] + fp[index]),
                "tn": int(tn[index]),
                "fp": int(fp[index]),
                "fn": int(fn[index]),
                "tp": int(tp[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": float(np.mean(f1))},
    }


def select_checkpoint(history: Sequence[dict[str, Any]], delta: float) -> dict[str, Any]:
    maximum = max(float(row["fixed_macro_f1"]) for row in history)
    eligible = [row for row in history if maximum - float(row["fixed_macro_f1"]) < delta]
    selected = min(eligible, key=lambda row: int(row["epoch"]))
    return {
        "maximum_fixed_macro_f1": maximum,
        "practical_tie_delta": delta,
        "selected_epoch": int(selected["epoch"]),
        "selected_fixed_macro_f1": float(selected["fixed_macro_f1"]),
        "selection_deficit_from_maximum": maximum - float(selected["fixed_macro_f1"]),
        "eligible_epochs": [int(row["epoch"]) for row in eligible],
    }


def select_threshold(
    gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]
) -> tuple[float, list[dict[str, float]]]:
    rows = [
        {
            "threshold": float(threshold),
            "macro_f1": metric_bundle(
                gold, (probabilities >= threshold).astype(np.uint8)
            )["macro"]["f1"],
        }
        for threshold in grid
    ]
    selected = min(
        rows,
        key=lambda row: (-row["macro_f1"], abs(row["threshold"] - 0.5), row["threshold"]),
    )
    return selected["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6, dtype=np.float64), where=denominator != 0)


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
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    seed_material = f"{namespace}|EXP-052|seed-{model_seed}|{condition}"
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(seed)
    values = np.zeros((replicates, len(LABELS)), dtype=np.float64)
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], predicted[indices])
    point = fast_f1(gold, predicted)

    def interval(series: np.ndarray, point_value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(point_value), "lower": float(lower), "upper": float(upper)}

    without_surprise = [0, 1, 3, 4, 5]
    return {
        "unit": "duplicate_component_id",
        "component_count": len(components),
        "row_count": len(component_ids),
        "replicates": replicates,
        "seed": seed,
        "seed_material": seed_material,
        "interval": "percentile_2.5_97.5",
        "macro_f1": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_without_surprise": interval(
            values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())
        ),
        "per_label_f1": {
            label: interval(values[:, index], float(point[index]))
            for index, label in enumerate(LABELS)
        },
    }


def write_history(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = (
        "seed", "epoch", "optimizer_steps", "train_loss", "validation_loss",
        "fixed_threshold", "fixed_macro_precision", "fixed_macro_recall",
        "fixed_macro_f1", "fixed_micro_f1", "fixed_weighted_f1",
        "fixed_subset_accuracy", "fixed_hamming_loss",
        "fixed_five_label_macro_f1_without_surprise", "batch_order_sha256",
        "epoch_seconds",
    )
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
            row = {key: metrics["per_label"][label][key] for key in fields if key != "label"}
            row["label"] = label
            writer.writerow(row)


def write_confusion(path: Path, metrics: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("label_id", "label", "tn", "fp", "fn", "tp"))
        for index, label in enumerate(LABELS):
            row = metrics["per_label"][label]
            writer.writerow((index, label, row["tn"], row["fp"], row["fn"], row["tp"]))


def save_head(path: Path, head: Any) -> dict[str, Any]:
    import mlx.core as mx

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    mx.save_safetensors(str(path), dict(mlx_items(head)))
    os.chmod(path, 0o600)
    return artifact(path)


def train_two_steps(head: Any, features: np.ndarray, labels: np.ndarray) -> tuple[list[float], str]:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim

    def loss_fn(module: Any, inputs: Any, targets: Any) -> Any:
        return nn.losses.binary_cross_entropy(
            module(inputs), targets, with_logits=True, reduction="mean"
        )

    optimizer = optim.AdamW(learning_rate=1e-4, weight_decay=0.01)
    loss_and_grad = nn.value_and_grad(head, loss_fn)
    losses: list[float] = []
    for index in range(2):
        loss, gradients = loss_and_grad(
            head,
            mx.array(np.asarray(features[index : index + 1]), dtype=mx.float32),
            mx.array(labels[index : index + 1], dtype=mx.float32),
        )
        optimizer.update(head, gradients)
        mx.eval(loss, head.parameters(), optimizer.state)
        value = float(loss.item())
        if not math.isfinite(value):
            raise ValueError("Dry-run head loss is non-finite")
        losses.append(value)
    return losses, mlx_tensor_digest(mlx_items(head))


def run_dry(
    *,
    config: dict[str, Any],
    shared: dict[str, Any],
    seed: int,
    run_dir: Path,
    private_dir: Path,
    logger: logging.Logger,
    started: float,
    common: dict[str, Any],
) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load

    train_rows = load_split(shared, "train")
    selected = select_dry_rows(
        train_rows,
        int(config["dry_run"]["sample_rows"]),
        config["dry_run"]["selection_namespace"],
    )
    prompt = load_prompt(shared)
    spec = shared["models"]["qwen_shared"]
    model_started = time.perf_counter()
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model_load_seconds = time.perf_counter() - model_started
    model.freeze()
    model.eval()
    if mlx_items(model):
        raise ValueError("Frozen Qwen exposes trainable parameters")
    if int(model.args.hidden_size) != int(spec["hidden_size"]):
        raise ValueError("Qwen hidden size drift")

    extraction_started = time.perf_counter()
    features, feature_metadata = extract_features(
        rows=selected,
        split="train-dry-run",
        output_dir=private_dir / "feature-cache" / "train-dry-run",
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        shared=shared,
        logger=logger,
        extraction_started=extraction_started,
        maximum_minutes=float(config["dry_run"]["maximum_wall_minutes"]),
        maximum_peak_memory_gb=float(config["execution"]["maximum_peak_memory_gb"]),
        log_every=int(config["dry_run"]["log_every_rows"]),
    )
    extraction_seconds = time.perf_counter() - extraction_started
    peak_memory = float(mx.get_peak_memory()) / 1e9
    del model, tokenizer
    gc.collect()
    mx.clear_cache()

    head = build_head(seed, int(spec["hidden_size"]))
    trainable_count = sum(int(tensor.size) for _, tensor in mlx_items(head))
    initial_digest = mlx_tensor_digest(mlx_items(head))
    if trainable_count != int(spec["head_parameters"]):
        raise ValueError("M2 head parameter count drift")
    if initial_digest != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("M2 seed-42 head initialization differs from EXP-050")
    labels = np.asarray([row["labels"] for row in selected], dtype=np.float32)
    losses, final_digest = train_two_steps(head, features, labels)
    if final_digest == initial_digest:
        raise ValueError("Dry-run head did not update")

    projected_base_seconds = model_load_seconds + (
        feature_metadata["forward_seconds"] / len(selected)
    ) * (shared["data"]["train_rows"] + shared["data"]["validation_rows"])
    projected_minutes = projected_base_seconds / 60.0
    projected_with_safety = projected_minutes * float(config["dry_run"]["projection_safety_factor"])
    if projected_with_safety > float(config["execution"]["maximum_feature_extraction_minutes"]):
        raise TimeoutError("Projected formal feature extraction exceeds four hours")
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("Dry-run exceeds the formal memory budget")

    private_manifest_path = private_dir / "private-manifest.json"
    private_manifest = {
        "experiment_id": "EXP-052",
        "stage": "train-only-dry-run",
        "seed": seed,
        "contains_raw_text": False,
        "contains_row_level_features": True,
        "feature_cache": feature_metadata["feature"],
    }
    atomic_json(private_manifest_path, private_manifest, private=True)
    return {
        **common,
        "status": "Completed",
        "completed_at_utc": utc_now(),
        "stage": "train-only-dry-run",
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
        "data": {
            "protocol_id": shared["data"]["protocol_id"],
            "labels": list(LABELS),
            "train": {"sha256": shared["data"]["train_sha256"], "summary": split_summary(train_rows)},
            "selection": {
                "rows": len(selected),
                "sample_order_sha256": canonical_digest([row["sample_id"] for row in selected]),
                "positive_counts": {
                    label: sum(row["labels"][index] for row in selected)
                    for index, label in enumerate(LABELS)
                },
                "identities_public": False,
            },
            "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
        },
        "model_runtime": {
            "qwen_parameters_frozen": True,
            "qwen_trainable_parameter_count": 0,
            "head_trainable_parameter_count": trainable_count,
            "head_initial_sha256": initial_digest,
            "head_final_sha256": final_digest,
            "optimizer_steps": 2,
            "finite_losses": losses,
            "pooling": shared["prompt"]["pooling"],
            "feature_dtype": "float32",
        },
        "feature_cache": {**feature_metadata, "public_row_level_data": False},
        "resource_projection": {
            "full_feature_rows": shared["data"]["train_rows"] + shared["data"]["validation_rows"],
            "sample_rows": len(selected),
            "model_load_seconds": model_load_seconds,
            "sample_extraction_seconds": extraction_seconds,
            "projected_feature_extraction_minutes": projected_minutes,
            "safety_factor": float(config["dry_run"]["projection_safety_factor"]),
            "projected_feature_extraction_minutes_with_safety": projected_with_safety,
        },
        "resource_usage": {
            "wall_seconds": time.perf_counter() - started,
            "peak_mlx_memory_gb": peak_memory,
            "api_cost_usd": 0,
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "row_level_features": "private_gitignored",
        },
        "artifacts": {
            "private_manifest": artifact(private_manifest_path),
            "feature_cache_private": feature_metadata["feature"],
        },
    }


def run_formal(
    *,
    config: dict[str, Any],
    shared: dict[str, Any],
    seed: int,
    run_dir: Path,
    private_dir: Path,
    logger: logging.Logger,
    started: float,
    common: dict[str, Any],
) -> dict[str, Any]:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load

    train_rows = load_split(shared, "train")
    validation_rows = load_split(shared, "validation")
    if {row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}:
        raise ValueError("Train/validation duplicate-component overlap")
    if {row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}:
        raise ValueError("Train/validation sample overlap")
    prompt = load_prompt(shared)
    spec = shared["models"]["qwen_shared"]
    model_started = time.perf_counter()
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model_load_seconds = time.perf_counter() - model_started
    model.freeze()
    model.eval()
    if mlx_items(model):
        raise ValueError("Frozen Qwen exposes trainable parameters")
    if int(model.args.hidden_size) != int(spec["hidden_size"]):
        raise ValueError("Qwen hidden size drift")

    extraction_started = time.perf_counter()
    train_features, train_feature_metadata = extract_features(
        rows=train_rows,
        split="train",
        output_dir=private_dir / "feature-cache" / "train",
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        shared=shared,
        logger=logger,
        extraction_started=extraction_started,
        maximum_minutes=float(config["execution"]["maximum_feature_extraction_minutes"]),
        maximum_peak_memory_gb=float(config["execution"]["maximum_peak_memory_gb"]),
        log_every=int(config["execution"]["feature_log_every_rows"]),
    )
    validation_features, validation_feature_metadata = extract_features(
        rows=validation_rows,
        split="validation",
        output_dir=private_dir / "feature-cache" / "validation",
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        shared=shared,
        logger=logger,
        extraction_started=extraction_started,
        maximum_minutes=float(config["execution"]["maximum_feature_extraction_minutes"]),
        maximum_peak_memory_gb=float(config["execution"]["maximum_peak_memory_gb"]),
        log_every=int(config["execution"]["feature_log_every_rows"]),
    )
    extraction_seconds = time.perf_counter() - extraction_started
    peak_memory = float(mx.get_peak_memory()) / 1e9
    del model, tokenizer
    gc.collect()
    mx.clear_cache()

    train_gold = np.asarray([row["labels"] for row in train_rows], dtype=np.float32)
    validation_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    rng = np.random.default_rng(seed)
    batch_orders = np.stack(
        [rng.permutation(len(train_rows)) for _ in range(int(spec["epochs"]))]
    ).astype(np.int32)
    batch_order_path = private_dir / "batch-orders.npy"
    np.save(batch_order_path, batch_orders, allow_pickle=False)
    os.chmod(batch_order_path, 0o600)

    head = build_head(seed, int(spec["hidden_size"]))
    initial_digest = mlx_tensor_digest(mlx_items(head))
    trainable_count = sum(int(tensor.size) for _, tensor in mlx_items(head))
    if trainable_count != int(spec["head_parameters"]):
        raise ValueError("M2 head parameter count drift")
    if initial_digest != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("M2 seed-42 head initialization differs from EXP-050")

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
    for epoch_index, order in enumerate(batch_orders, start=1):
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
                raise ValueError(f"Non-finite head loss at epoch {epoch_index}, step {position}")
            loss_sum += value
            global_step += 1
            if position % int(config["execution"]["head_log_every_steps"]) == 0 or position == len(order):
                logger.info(
                    "Seed %d epoch %d head step %d/%d loss %.6f",
                    seed, epoch_index, position, len(order), loss_sum / position,
                )
            if (time.perf_counter() - training_started) / 60.0 > float(config["execution"]["maximum_head_training_minutes"]):
                raise TimeoutError("Head training exceeded the frozen wall-time budget")

        validation_loss, probabilities = evaluate_head(
            head, validation_features, validation_gold
        )
        fixed_predictions = (
            probabilities >= float(shared["evaluation"]["fixed_threshold"])
        ).astype(np.uint8)
        fixed_metrics = metric_bundle(validation_gold, fixed_predictions)
        checkpoint_path = checkpoints / f"epoch-{epoch_index}.safetensors"
        save_head(checkpoint_path, head)
        epoch_probabilities.append(probabilities)
        order_digest = canonical_digest(
            [train_rows[int(index)]["sample_id"] for index in order]
        )
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
                "batch_order_sha256": order_digest,
                "epoch_seconds": time.perf_counter() - epoch_started,
            }
        )
        logger.info(
            "Seed %d epoch %d complete: train_loss=%.6f val_loss=%.6f fixed_macro_f1=%.6f",
            seed, epoch_index, loss_sum / len(order), validation_loss, fixed_metrics["macro"]["f1"],
        )

    expected_steps = int(spec["total_iterations_per_seed"])
    if global_step != expected_steps or len(epoch_probabilities) != int(spec["epochs"]):
        raise ValueError("Head training completion count drift")
    training_seconds = time.perf_counter() - training_started
    probability_array = np.stack(epoch_probabilities).astype(np.float32, copy=False)
    selection = select_checkpoint(history, float(shared["evaluation"]["practical_tie_delta"]))
    selected_epoch = int(selection["selected_epoch"])
    selected_probabilities = probability_array[selected_epoch - 1]
    selected_head = private_dir / "selected-head.safetensors"
    shutil.copy2(checkpoints / f"epoch-{selected_epoch}.safetensors", selected_head)
    os.chmod(selected_head, 0o600)
    fixed_threshold = float(shared["evaluation"]["fixed_threshold"])
    selected_threshold, threshold_rows = select_threshold(
        validation_gold,
        selected_probabilities,
        shared["evaluation"]["shared_threshold_grid"],
    )
    fixed_predictions = (selected_probabilities >= fixed_threshold).astype(np.uint8)
    calibrated_predictions = (selected_probabilities >= selected_threshold).astype(np.uint8)
    fixed_metrics = metric_bundle(validation_gold, fixed_predictions)
    calibrated_metrics = metric_bundle(validation_gold, calibrated_predictions)
    component_ids = [row["component_id"] for row in validation_rows]
    bootstrap = {
        "fixed_0.5": bootstrap_summary(
            validation_gold,
            fixed_predictions,
            component_ids,
            seed,
            int(shared["evaluation"]["bootstrap"]["replicates"]),
            shared["evaluation"]["bootstrap"]["seed_namespace"],
            "fixed-0.5",
        ),
        "shared_threshold": bootstrap_summary(
            validation_gold,
            calibrated_predictions,
            component_ids,
            seed,
            int(shared["evaluation"]["bootstrap"]["replicates"]),
            shared["evaluation"]["bootstrap"]["seed_namespace"],
            f"shared-{selected_threshold:.2f}",
        ),
    }

    predictions_path = private_dir / "validation-predictions.npz"
    np.savez_compressed(
        predictions_path,
        probabilities=probability_array,
        gold=validation_gold,
        fixed_predictions=fixed_predictions,
        shared_threshold_predictions=calibrated_predictions,
        sample_ids=np.asarray([row["sample_id"] for row in validation_rows]),
        component_ids=np.asarray(component_ids),
    )
    os.chmod(predictions_path, 0o600)
    private_manifest_path = private_dir / "private-manifest.json"
    private_manifest = {
        "experiment_id": "EXP-052",
        "stage": "seed-42-train-validation-integrity-gate",
        "seed": seed,
        "contains_raw_text": False,
        "contains_row_level_features": True,
        "contains_row_level_probabilities": True,
        "train_feature_cache": train_feature_metadata["feature"],
        "validation_feature_cache": validation_feature_metadata["feature"],
        "batch_orders": artifact(batch_order_path),
        "validation_predictions": artifact(predictions_path),
        "selected_head": artifact(selected_head),
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
    tables: dict[str, Any] = {}
    for name, metrics in (
        ("fixed-0.5", fixed_metrics),
        ("shared-threshold", calibrated_metrics),
    ):
        per_label_path = run_dir / f"per-label-{name}.csv"
        confusion_path = run_dir / f"multilabel-confusion-{name}.csv"
        write_per_label(per_label_path, metrics)
        write_confusion(confusion_path, metrics)
        tables[name] = {
            "per_label": artifact(per_label_path),
            "confusion": artifact(confusion_path),
        }

    final_digest = mlx_tensor_digest(mlx_items(head))
    if final_digest == initial_digest:
        raise ValueError("Formal M2 head did not update")
    peak_memory = max(peak_memory, float(mx.get_peak_memory()) / 1e9)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_gb = peak_rss / 1e9 if platform.system() == "Darwin" else peak_rss * 1024 / 1e9
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("Formal M2 exceeded the frozen MLX memory budget")
    if time.perf_counter() - started > float(config["execution"]["maximum_total_wall_minutes"]) * 60:
        raise TimeoutError("Formal M2 exceeded the total wall-time budget")

    return {
        **common,
        "status": "Completed",
        "completed_at_utc": utc_now(),
        "stage": "seed-42-train-validation-integrity-gate",
        "accessed_splits": ["train", "validation"],
        "validation_split_accessed": True,
        "test_split_accessed": False,
        "performance_metrics_computed": True,
        "data": {
            "protocol_id": shared["data"]["protocol_id"],
            "labels": list(LABELS),
            "train": {"sha256": shared["data"]["train_sha256"], "summary": split_summary(train_rows)},
            "validation": {"sha256": shared["data"]["validation_sha256"], "summary": split_summary(validation_rows)},
            "cross_split_component_overlap": 0,
            "cross_split_sample_overlap": 0,
            "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
        },
        "model_runtime": {
            "qwen_parameters_frozen": True,
            "qwen_trainable_parameter_count": 0,
            "head_trainable_parameter_count": trainable_count,
            "head_initial_sha256": initial_digest,
            "head_final_in_memory_sha256": final_digest,
            "pooling": shared["prompt"]["pooling"],
            "feature_dtype": "float32",
        },
        "feature_cache": {
            "train": {**train_feature_metadata, "public_row_level_data": False},
            "validation": {**validation_feature_metadata, "public_row_level_data": False},
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
            "api_cost_usd": 0,
            "wall_seconds": time.perf_counter() - started,
            "model_load_seconds": model_load_seconds,
            "feature_extraction_seconds": extraction_seconds,
            "head_training_seconds": training_seconds,
            "peak_mlx_memory_gb": peak_memory,
            "peak_process_rss_gb": peak_rss_gb,
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "row_level_features_and_predictions": "private_gitignored",
        },
        "warnings": [
            "This single seed is an integrity gate, not the frozen three-seed M2 result.",
            "Linear-head performance supports decodability, not an internal emotion mechanism.",
            "The shared threshold is selected on validation and cannot be tuned on test.",
        ],
        "artifacts": {
            "history": artifact(history_path),
            "threshold_grid": artifact(threshold_path),
            "metrics_fixed": artifact(fixed_metrics_path),
            "metrics_shared_threshold": artifact(calibrated_metrics_path),
            "bootstrap": artifact(bootstrap_path),
            "selection": artifact(selection_path),
            "tables": tables,
            "private_manifest": artifact(private_manifest_path),
            "train_features_private": train_feature_metadata["feature"],
            "validation_features_private": validation_feature_metadata["feature"],
            "batch_orders_private": artifact(batch_order_path),
            "validation_predictions_private": artifact(predictions_path),
            "selected_head_private": artifact(selected_head),
        },
    }


def render_report(run: dict[str, Any]) -> str:
    if run["stage"] == "train-only-dry-run":
        return "\n".join(
            [
                "# EXP-052 Seed 42 Train-only Dry-run",
                "",
                f"- Status: `{run['status']}`; independent verification pending",
                "- Accessed splits: train only",
                "- Validation performance computed: no",
                "- Test accessed: no",
                f"- Feature sample rows: `{run['resource_projection']['sample_rows']}`",
                f"- Projected extraction with safety: `{run['resource_projection']['projected_feature_extraction_minutes_with_safety']:.2f}` minutes",
                f"- Peak MLX memory: `{run['resource_usage']['peak_mlx_memory_gb']:.3f}` GB",
                f"- Head initialization matches EXP-050: `{run['model_runtime']['head_initial_sha256']}`",
                "",
                "This dry-run authorizes no validation result and no later seed or model condition.",
                "",
            ]
        )
    fixed = run["metrics"]["fixed_0.5"]
    calibrated = run["metrics"]["shared_threshold"]
    return "\n".join(
        [
            "# EXP-052 Seed 42 Validation",
            "",
            f"- Status: `{run['status']}`; independent verification pending",
            "- Accessed splits: train, validation",
            "- Test accessed: no",
            f"- Selected epoch: `{run['selection']['selected_epoch']}` from two epochs",
            f"- Fixed 0.5 Macro-F1: `{fixed['macro']['f1']:.6f}`",
            f"- Shared threshold: `{run['threshold_selection']['selected_threshold']:.2f}`",
            f"- Calibrated Macro-F1: `{calibrated['macro']['f1']:.6f}`",
            f"- Calibrated Micro-F1: `{calibrated['micro_f1']:.6f}`",
            f"- Calibrated subset accuracy: `{calibrated['subset_accuracy']:.6f}`",
            f"- Surprise F1: `{calibrated['per_label']['surprise']['f1']:.6f}`",
            "",
            "This is a single-seed integrity gate. It supports linear decodability only.",
            "Seeds 43/44, test, M3 and M4 remain unauthorized.",
            "",
        ]
    )


def run() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config, shared = load_config(config_path, args.seed)
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_dir"])).resolve()
    private_dir = (args.private_dir or resolve_project(config["execution"]["private_run_dir"])).resolve()
    prepare_dirs(run_dir, private_dir)
    logger = setup_logger(run_dir)
    started = time.perf_counter()
    started_at = utc_now()
    run_path = run_dir / "run.json"
    run_record: dict[str, Any] = {
        "schema_version": "exp-052-m2-run-v1",
        "experiment_id": "EXP-052",
        "rq_id": "RQ-S1",
        "tier": "Major",
        "stage": config["stage"],
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
        logger.info("EXP-052 %s preflight started", config["stage"])
        frozen_sources = freeze_sources(run_dir, config, config_path)
        exp050 = verify_exp050(config)
        dry_run_gate = verify_dry_run_gate(config)
        environment = environment_gate(run_dir, config)
        model = verify_model(shared)
        common = {
            "schema_version": "exp-052-m2-run-v1",
            "experiment_id": "EXP-052",
            "rq_id": "RQ-S1",
            "tier": "Major",
            "seed": args.seed,
            "started_at_utc": started_at,
            "invocation": [sys.executable, *sys.argv],
            "working_directory": str(Path.cwd()),
            "authorization": config["authorization"],
            "prerequisite": {"exp050": exp050, "dry_run_gate": dry_run_gate},
            "environment": environment,
            "git": git_metadata(),
            "model": model,
        }
        logger.info("Authorization, prerequisites, environment, and Qwen hashes verified")
        if config["stage"] == "train-only-dry-run":
            run_record.update(
                accessed_splits=["train"],
                validation_split_accessed=False,
                test_split_accessed=False,
            )
            atomic_json(run_path, run_record)
            completed = run_dry(
                config=config,
                shared=shared,
                seed=args.seed,
                run_dir=run_dir,
                private_dir=private_dir,
                logger=logger,
                started=started,
                common=common,
            )
        else:
            run_record.update(
                accessed_splits=["train", "validation"],
                validation_split_accessed=True,
                test_split_accessed=False,
            )
            atomic_json(run_path, run_record)
            completed = run_formal(
                config=config,
                shared=shared,
                seed=args.seed,
                run_dir=run_dir,
                private_dir=private_dir,
                logger=logger,
                started=started,
                common=common,
            )

        completed["artifacts"]["frozen_sources"] = frozen_sources
        report_path = run_dir / "REPORT.md"
        report_path.write_text(render_report(completed), encoding="utf-8")
        logger.info("EXP-052 %s completed; test accessed: no", config["stage"])
        flush_logger(logger)
        completed["artifacts"]["report"] = artifact(report_path)
        completed["artifacts"]["stdout_log"] = artifact(run_dir / "stdout.log")
        completed["artifacts"]["environment_freeze"] = environment["freeze"]
        atomic_json(run_path, completed)
    except Exception as error:
        logger.exception("EXP-052 %s failed", config["stage"])
        flush_logger(logger)
        run_record.update(
            {
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "failure": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
                "resource_usage": {"wall_seconds": time.perf_counter() - started},
                "test_split_accessed": False,
            }
        )
        atomic_json(run_path, run_record)
        raise


if __name__ == "__main__":
    run()
