#!/usr/bin/env python3
"""Run the authorized train-only EXP-053 Classification LoRA resource preflight."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any

import numpy as np


EXPERIMENT_ID = "EXP-053"
STAGE = "train-only-resource-preflight"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-053-m3-resource-preflight-seed-42.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-053-m3-classification-lora-resource-preflight-seed-42"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def write_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def source_record(path: Path) -> dict[str, Any]:
    return artifact(path)


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen source drift: {path}")
    return path


def load_json_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(require_record(record).read_text(encoding="utf-8"))


def load_primitives() -> Any:
    path = SCRIPT_DIR / "run_preflight.py"
    spec = importlib.util.spec_from_file_location("so_exp050_primitives_for_exp053", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_versions() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in ("mlx", "mlx-lm", "numpy", "safetensors", "transformers"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("stage") != STAGE:
        raise ValueError("Unexpected EXP-053 preflight identity")
    auth = config["authorization"]
    if auth.get("seeds") != [42] or auth.get("splits") != ["train"]:
        raise ValueError("EXP-053 preflight must authorize seed 42 and train only")
    if auth.get("validation_access") or auth.get("test_access") or auth.get("formal_training"):
        raise ValueError("EXP-053 preflight cannot authorize validation, test, or formal training")
    if config["execution"]["optimizer_steps"] != config["sampling"]["sample_rows"]:
        raise ValueError("One train-only optimizer step is required per sampled row")
    if config["execution"]["projection_safety_factor"] != 1.5:
        raise ValueError("Projection safety factor drift")
    for record in config["implementation"].values():
        require_record(record)
    require_record(config["prerequisites"]["shared_config"])
    for group in ("exp050", "m2_seed_42", "m2_aggregate"):
        for record in config["prerequisites"][group].values():
            require_record(record)
    return config


def validate_prerequisites(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    shared = load_json_record(config["prerequisites"]["shared_config"])
    if shared.get("formal_execution_authorized") is not False:
        raise ValueError("Shared model contract must keep formal execution sealed")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise ValueError("Stack Overflow test is not sealed")
    exp050_run = load_json_record(config["prerequisites"]["exp050"]["run"])
    exp050_verify = load_json_record(config["prerequisites"]["exp050"]["verification"])
    exp050_m2 = load_json_record(config["prerequisites"]["exp050"]["m2"])
    exp050_m3 = load_json_record(config["prerequisites"]["exp050"]["m3"])
    if exp050_run.get("status") != "Passed" or exp050_verify.get("status") != "Passed":
        raise ValueError("EXP-050 prerequisite is not verified")
    if (
        exp050_verify.get("checks_passed") != 77
        or exp050_verify.get("checks_total") != 77
        or exp050_verify.get("failed_checks") != []
    ):
        raise ValueError("EXP-050 verification count drift")
    if exp050_m2.get("head_initial_sha256") != exp050_m3.get("head_initial_sha256"):
        raise ValueError("EXP-050 no longer supports matched M2/M3 initialization")
    if exp050_m3.get("zero_step_max_abs_logit_difference") != 0.0:
        raise ValueError("EXP-050 zero-LoRA-delta gate drift")
    if exp050_m3.get("insertion_count") != 112 or not exp050_m3.get("separate_head_and_lora_optimizers"):
        raise ValueError("EXP-050 M3 implementation gate drift")

    m2_run = load_json_record(config["prerequisites"]["m2_seed_42"]["run"])
    m2_verify = load_json_record(config["prerequisites"]["m2_seed_42"]["verification"])
    if m2_run.get("status") != "Completed" or m2_verify.get("status") != "Passed":
        raise ValueError("EXP-052 seed-42 prerequisite is not verified")
    if m2_verify.get("check_count") != 70 or m2_run.get("test_split_accessed"):
        raise ValueError("EXP-052 seed-42 verification/test boundary drift")
    expected_head = config["execution"]["expected_head_initial_sha256"]
    if m2_run["model_runtime"]["head_initial_sha256"] != expected_head:
        raise ValueError("Matched M2 seed-42 head hash drift")

    aggregate = load_json_record(config["prerequisites"]["m2_aggregate"]["aggregate"])
    aggregate_verify = load_json_record(config["prerequisites"]["m2_aggregate"]["verification"])
    if aggregate.get("status") != "Completed" or aggregate_verify.get("status") != "Passed":
        raise ValueError("EXP-052 family settlement is not verified")
    if aggregate_verify.get("check_count") != 85 or aggregate_verify.get("test_split_accessed"):
        raise ValueError("EXP-052 aggregate verification/test boundary drift")
    return shared, m2_run


def rank_key(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode()).hexdigest()


def select_length_aware_rows(
    rows: list[dict[str, Any]],
    token_counts: dict[str, int],
    labels: list[str],
    namespace: str,
    sample_rows: int,
) -> list[dict[str, Any]]:
    if sample_rows < len(labels) + 8 or len(token_counts) != len(rows):
        raise ValueError("Invalid length-aware sample contract")
    selected: dict[str, dict[str, Any]] = {}

    for index, label in enumerate(labels):
        candidates = [row for row in rows if row["labels"][index] == 1]
        candidates.sort(key=lambda row: rank_key(namespace, f"label|{label}|{row['sample_id']}"))
        if not candidates:
            raise ValueError(f"No positive train row for {label}")
        selected.setdefault(candidates[0]["sample_id"], candidates[0])

    for criterion, candidates, required in (
        ("neutral", [row for row in rows if row["neutral"]], 4),
        ("multilabel", [row for row in rows if row["label_cardinality"] == 2], 4),
    ):
        candidates.sort(key=lambda row: rank_key(namespace, f"{criterion}|{row['sample_id']}"))
        added = 0
        for row in candidates:
            if row["sample_id"] in selected:
                continue
            selected[row["sample_id"]] = row
            added += 1
            if added == required:
                break
        if added != required:
            raise ValueError(f"Insufficient {criterion} rows")

    ordered = sorted(
        rows,
        key=lambda row: (token_counts[row["sample_id"]], rank_key(namespace, row["sample_id"])),
    )
    lower_end = ordered[: max(1, len(ordered) // 10)]
    upper_start = min(len(ordered) - 1, len(ordered) * 9 // 10)
    upper_end = ordered[upper_start:]
    for boundary, candidates in (("lower", lower_end), ("upper", upper_end)):
        candidates.sort(
            key=lambda row: rank_key(namespace, f"length-{boundary}|{row['sample_id']}")
        )
        selected.setdefault(candidates[0]["sample_id"], candidates[0])

    grid_size = sample_rows * 8
    quantile_candidates: list[tuple[int, dict[str, Any]]] = []
    for slot in range(grid_size):
        index = min(len(ordered) - 1, ((2 * slot + 1) * len(ordered)) // (2 * grid_size))
        quantile_candidates.append((slot, ordered[index]))
    quantile_candidates.sort(key=lambda item: rank_key(namespace, f"quantile|{item[0]}"))
    for _, row in quantile_candidates:
        selected.setdefault(row["sample_id"], row)
        if len(selected) == sample_rows:
            break
    if len(selected) < sample_rows:
        for row in sorted(rows, key=lambda row: rank_key(namespace, f"fill|{row['sample_id']}")):
            selected.setdefault(row["sample_id"], row)
            if len(selected) == sample_rows:
                break

    result = sorted(selected.values(), key=lambda row: rank_key(namespace, f"order|{row['sample_id']}"))
    if len(result) != sample_rows:
        raise ValueError("Length-aware sample size drift")
    positive_counts = [sum(row["labels"][i] for row in result) for i in range(len(labels))]
    selected_lengths = [token_counts[row["sample_id"]] for row in result]
    full_lengths = sorted(token_counts.values())
    if any(value < 1 for value in positive_counts):
        raise ValueError("Length-aware sample lost label coverage")
    if sum(row["neutral"] for row in result) < 4:
        raise ValueError("Length-aware sample lost neutral coverage")
    if sum(row["label_cardinality"] == 2 for row in result) < 4:
        raise ValueError("Length-aware sample lost multi-label coverage")
    if min(selected_lengths) > full_lengths[max(0, len(full_lengths) // 10)]:
        raise ValueError("Length-aware sample misses the lower token range")
    if max(selected_lengths) < full_lengths[min(len(full_lengths) - 1, len(full_lengths) * 9 // 10)]:
        raise ValueError("Length-aware sample misses the upper token range")
    return result


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    ordered = sorted(float(value) for value in values)

    def quantile(fraction: float) -> float:
        position = (len(ordered) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "count": len(ordered),
        "min": ordered[0],
        "p50": quantile(0.5),
        "p95": quantile(0.95),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def selection_summary(
    rows: list[dict[str, Any]], token_counts: dict[str, int], labels: list[str]
) -> dict[str, Any]:
    identities = [
        {"sample_id": row["sample_id"], "component_id": row["component_id"]} for row in rows
    ]
    return {
        "rows": len(rows),
        "selection_digest_sha256": canonical_digest(identities),
        "order_digest_sha256": canonical_digest([row["sample_id"] for row in rows]),
        "positive_counts": {
            label: sum(row["labels"][index] for row in rows) for index, label in enumerate(labels)
        },
        "neutral_rows": sum(row["neutral"] for row in rows),
        "cardinality_2_rows": sum(row["label_cardinality"] == 2 for row in rows),
        "token_lengths": numeric_summary([token_counts[row["sample_id"]] for row in rows]),
        "identities_public": False,
    }


def trainable_name_allowed(name: str) -> bool:
    return name in {"head.weight", "head.bias"} or (
        name.startswith("backbone.") and name.endswith((".lora_a", ".lora_b"))
    )


def frozen_parameter_sentinel(model: Any) -> dict[str, Any]:
    import mlx.core as mx
    from mlx.utils import tree_flatten

    base_items = [
        (name, tensor)
        for name, tensor in tree_flatten(model.parameters())
        if not name.endswith((".lora_a", ".lora_b"))
    ]
    base_items.sort(key=lambda item: item[0])
    positions = sorted({round(index * (len(base_items) - 1) / 15) for index in range(16)})
    digest = hashlib.sha256()
    names: list[str] = []
    for position in positions:
        name, tensor = base_items[position]
        names.append(name)
        size = int(tensor.size)
        indices = sorted({0, size // 3, (2 * size) // 3, size - 1})
        sample = np.asarray(tensor.reshape(-1)[mx.array(indices)].astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(sample.tobytes(order="C"))
    return {"sha256": digest.hexdigest(), "tensor_names": names, "tensor_count": len(names)}


def project_runtime(
    *,
    model_load_seconds: float,
    tokenization_seconds: float,
    train_step_seconds: list[float],
    forward_seconds: list[float],
    checkpoint_write_seconds: float,
    train_rows: int,
    validation_rows: int,
    formal_steps: int,
    safety_factor: float,
    warmup_steps: int,
) -> dict[str, Any]:
    steady = train_step_seconds[warmup_steps:]
    if not steady or not forward_seconds:
        raise ValueError("Insufficient timing observations")
    mean_train_step = statistics.fmean(steady)
    mean_forward = statistics.fmean(forward_seconds)
    projected_tokenization = tokenization_seconds * ((train_rows + validation_rows) / train_rows)
    raw_seconds = (
        model_load_seconds
        + projected_tokenization
        + mean_train_step * formal_steps
        + mean_forward * validation_rows
        + checkpoint_write_seconds
    )
    safe_seconds = raw_seconds * safety_factor
    return {
        "warmup_steps_excluded": warmup_steps,
        "steady_train_step_seconds": numeric_summary(steady),
        "forward_step_seconds": numeric_summary(forward_seconds),
        "raw_per_seed_seconds": raw_seconds,
        "safety_factor": safety_factor,
        "projected_per_seed_seconds_with_safety": safe_seconds,
        "projected_per_seed_hours_with_safety": safe_seconds / 3600,
        "projected_three_seed_hours_with_safety": safe_seconds * 3 / 3600,
    }


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    fields = ["step", "loss", "input_tokens", "step_seconds", "peak_mlx_memory_gb"]
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(history)


def write_environment(path: Path, packages: dict[str, str], git: dict[str, Any]) -> None:
    lines = [
        f"created_at_utc={utc_now()}",
        f"platform={platform.platform()}",
        f"machine={platform.machine()}",
        f"git_commit={git['commit']}",
        f"git_dirty={git['dirty']}",
    ]
    lines.extend(f"package_{name}={value}" for name, value in sorted(packages.items()))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(config_path: Path, run_dir: Path) -> dict[str, Any]:
    config = load_config(config_path)
    shared, m2_run = validate_prerequisites(config)
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {run_dir}")
    private_dir = resolve_project(config["execution"]["private_run_dir"])
    if private_dir.exists():
        raise FileExistsError(f"Refusing to overwrite private output: {private_dir}")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    log_path = run_dir / "stdout.log"

    def log(message: str) -> None:
        line = f"[{utc_now()}] {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as target:
            target.write(line + "\n")

    frozen: dict[str, Any] = {}
    freeze_records = {
        "config": source_record(config_path),
        **config["implementation"],
        "shared_config": config["prerequisites"]["shared_config"],
    }
    for name, record in freeze_records.items():
        source = require_record(record)
        destination = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, destination)
        frozen[name] = artifact(destination)

    started_at = utc_now()
    overall_started = time.perf_counter()
    packages = package_versions()
    git = git_metadata()
    write_environment(run_dir / "environment-freeze.txt", packages, git)
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )

    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint

    primitives = load_primitives()
    mx.reset_peak_memory()
    model_path = resolve_project(shared["models"]["qwen_shared"]["local_path"])
    load_started = time.perf_counter()
    model, tokenizer = load(str(model_path), lazy=False)
    model_load_seconds = time.perf_counter() - load_started
    log(f"base model loaded in {model_load_seconds:.3f}s")

    rows = primitives.load_train(shared)
    prompt = primitives.load_prompt(shared)
    tokenization_started = time.perf_counter()
    token_ids = {
        row["sample_id"]: primitives.qwen_prompt_ids(
            tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"]
        )
        for row in rows
    }
    tokenization_seconds = time.perf_counter() - tokenization_started
    token_counts = {sample_id: len(ids) for sample_id, ids in token_ids.items()}
    selected = select_length_aware_rows(
        rows,
        token_counts,
        shared["data"]["labels"],
        config["sampling"]["selection_namespace"],
        config["sampling"]["sample_rows"],
    )
    sample_summary = selection_summary(selected, token_counts, shared["data"]["labels"])
    full_token_summary = numeric_summary(list(token_counts.values()))
    private_selection_path = private_dir / "selection.json"
    write_json(
        private_selection_path,
        {
            "schema_version": "exp-053-m3-private-selection-v1",
            "rows": [
                {
                    "order": index,
                    "sample_id": row["sample_id"],
                    "component_id": row["component_id"],
                    "labels": row["labels"],
                    "neutral": row["neutral"],
                    "label_cardinality": row["label_cardinality"],
                    "input_tokens": token_counts[row["sample_id"]],
                }
                for index, row in enumerate(selected)
            ],
        },
        private=True,
    )
    log(f"tokenized {len(rows)} train rows and selected {len(selected)} private rows")

    seed = 42
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    model.freeze()
    model.eval()
    head = primitives.build_qwen_head(seed, spec["hidden_size"])
    head_initial_sha256 = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    if head_initial_sha256 != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("Seed-42 head initialization does not match EXP-052")
    wrapper = primitives.make_classification_wrapper(model, head)
    first_ids = mx.array([token_ids[selected[0]["sample_id"]]], dtype=mx.int32)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)

    mx.random.seed(seed + 100000)
    linear_to_lora_layers(
        model,
        lora["num_layers"],
        {
            "rank": lora["rank"],
            "scale": lora["scale"],
            "dropout": lora["dropout"],
            "keys": lora["target_modules"],
        },
    )
    observed_insertions = primitives.insertion_contract(model, shared)
    lora_initial_items = primitives.mlx_trainable(model)
    lora_initial_sha256 = primitives.mlx_tensor_digest(lora_initial_items)
    lora_parameter_count = sum(int(tensor.size) for _, tensor in lora_initial_items)
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_step_difference = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    if zero_step_difference != 0.0:
        raise ValueError("Initial LoRA delta is not exactly zero")
    trainable_items = primitives.mlx_trainable(wrapper)
    unexpected = [name for name, _ in trainable_items if not trainable_name_allowed(name)]
    total_trainable = sum(int(tensor.size) for _, tensor in trainable_items)
    if unexpected:
        raise ValueError(f"Trainable whitelist violation: {unexpected[:3]}")
    if len(observed_insertions) != lora["insertion_points"]:
        raise ValueError("LoRA insertion-count drift")
    if lora_parameter_count != lora["trainable_parameters"]:
        raise ValueError("LoRA parameter-count drift")
    if total_trainable != lora["classification_total_trainable_parameters"]:
        raise ValueError("Total trainable parameter-count drift")
    base_sentinel_before = frozen_parameter_sentinel(model)

    grad_checkpoint(model.layers[0])
    model.train()
    head_optimizer = optim.AdamW(
        learning_rate=spec["head_learning_rate"], weight_decay=spec["head_weight_decay"]
    )
    lora_optimizer = optim.AdamW(
        learning_rate=lora["learning_rate"], weight_decay=lora["weight_decay"]
    )
    loss_and_grad = nn.value_and_grad(wrapper, primitives.classification_loss)
    history: list[dict[str, Any]] = []
    train_started = time.perf_counter()
    for step, row in enumerate(selected, start=1):
        ids = mx.array([token_ids[row["sample_id"]]], dtype=mx.int32)
        targets = mx.array([row["labels"]], dtype=mx.float32)
        step_started = time.perf_counter()
        loss, grads = loss_and_grad(wrapper, ids, targets)
        lora_optimizer.update(wrapper.backbone, grads["backbone"])
        head_optimizer.update(wrapper.head, grads["head"])
        mx.eval(loss, wrapper.trainable_parameters(), lora_optimizer.state, head_optimizer.state)
        step_seconds = time.perf_counter() - step_started
        loss_value = float(loss.item())
        if not math.isfinite(loss_value):
            raise ValueError(f"Non-finite loss at step {step}")
        history.append(
            {
                "step": step,
                "loss": loss_value,
                "input_tokens": len(token_ids[row["sample_id"]]),
                "step_seconds": step_seconds,
                "peak_mlx_memory_gb": float(mx.get_peak_memory() / 1e9),
            }
        )
        if step % 8 == 0:
            log(f"completed train-only step {step}/{len(selected)}")
    measured_training_seconds = time.perf_counter() - train_started

    head_final_items = primitives.mlx_trainable(head)
    lora_final_items = primitives.mlx_trainable(model)
    head_final_sha256 = primitives.mlx_tensor_digest(head_final_items)
    lora_final_sha256 = primitives.mlx_tensor_digest(lora_final_items)
    nonzero_lora_b = sum(
        bool(mx.any(tensor != 0).item()) for name, tensor in lora_final_items if name.endswith("lora_b")
    )
    base_sentinel_after = frozen_parameter_sentinel(model)
    if head_final_sha256 == head_initial_sha256 or lora_final_sha256 == lora_initial_sha256:
        raise ValueError("Head or LoRA parameters did not update")
    if nonzero_lora_b != lora["insertion_points"]:
        raise ValueError("Not all lora_b tensors became nonzero")
    if base_sentinel_before != base_sentinel_after:
        raise ValueError("Frozen base-parameter sentinel changed")

    model.eval()
    forward_seconds: list[float] = []
    for row in selected[: config["execution"]["forward_timing_rows"]]:
        ids = mx.array([token_ids[row["sample_id"]]], dtype=mx.int32)
        forward_started = time.perf_counter()
        logits = wrapper(ids)
        mx.eval(logits)
        forward_seconds.append(time.perf_counter() - forward_started)
    reference_logits = wrapper(first_ids)
    mx.eval(reference_logits)

    adapter_path = private_dir / "adapters.safetensors"
    head_path = private_dir / "head.safetensors"
    reference_path = private_dir / "checkpoint-reference.safetensors"
    checkpoint_started = time.perf_counter()
    mx.save_safetensors(str(adapter_path), dict(lora_final_items))
    mx.save_safetensors(str(head_path), dict(head_final_items))
    mx.save_safetensors(str(reference_path), {"logits": reference_logits})
    for path in (adapter_path, head_path, reference_path):
        os.chmod(path, 0o600)
    checkpoint_write_seconds = time.perf_counter() - checkpoint_started
    reference_numpy = np.asarray(reference_logits.astype(mx.float32))

    del wrapper, head, model, tokenizer, base_logits, converted_logits, reference_logits
    gc.collect()
    mx.clear_cache()

    reload_started = time.perf_counter()
    reloaded_model, reloaded_tokenizer = load(str(model_path), lazy=False)
    reloaded_model.freeze()
    mx.random.seed(seed + 100000)
    linear_to_lora_layers(
        reloaded_model,
        lora["num_layers"],
        {
            "rank": lora["rank"],
            "scale": lora["scale"],
            "dropout": lora["dropout"],
            "keys": lora["target_modules"],
        },
    )
    reloaded_model.load_weights(str(adapter_path), strict=False)
    reloaded_head = primitives.build_qwen_head(seed, spec["hidden_size"])
    reloaded_head.load_weights(str(head_path), strict=True)
    reloaded_wrapper = primitives.make_classification_wrapper(reloaded_model, reloaded_head)
    reloaded_model.eval()
    reloaded_ids = mx.array([token_ids[selected[0]["sample_id"]]], dtype=mx.int32)
    reloaded_logits = reloaded_wrapper(reloaded_ids)
    mx.eval(reloaded_logits)
    reload_difference = float(
        np.max(np.abs(reference_numpy - np.asarray(reloaded_logits.astype(mx.float32))))
    )
    reload_seconds = time.perf_counter() - reload_started
    if reload_difference > config["execution"]["maximum_reload_logit_difference"]:
        raise ValueError("Checkpoint reload logit replay failed")

    history_path = run_dir / "history.csv"
    write_history(history_path, history)
    projection = project_runtime(
        model_load_seconds=model_load_seconds,
        tokenization_seconds=tokenization_seconds,
        train_step_seconds=[row["step_seconds"] for row in history],
        forward_seconds=forward_seconds,
        checkpoint_write_seconds=checkpoint_write_seconds,
        train_rows=shared["data"]["train_rows"],
        validation_rows=shared["data"]["validation_rows"],
        formal_steps=spec["total_iterations_per_seed"],
        safety_factor=config["execution"]["projection_safety_factor"],
        warmup_steps=config["execution"]["warmup_steps_excluded"],
    )
    peak_memory_gb = float(mx.get_peak_memory() / 1e9)
    resource_gate = {
        "memory_passed": peak_memory_gb <= config["execution"]["maximum_peak_memory_gb"],
        "per_seed_time_passed": projection["projected_per_seed_hours_with_safety"]
        <= config["execution"]["maximum_projected_hours_per_seed"],
        "three_seed_time_passed": projection["projected_three_seed_hours_with_safety"]
        <= config["execution"]["maximum_projected_hours_three_seeds"],
    }
    resource_gate["passed"] = all(resource_gate.values())
    if not resource_gate["passed"]:
        raise RuntimeError(f"EXP-053 resource gate failed: {resource_gate}")

    completed_at = utc_now()
    run_record = {
        "schema_version": "exp-053-m3-resource-preflight-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S1",
        "tier": "Major",
        "stage": STAGE,
        "status": "Passed",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "working_directory": str(PROJECT_ROOT),
        "invocation": " ".join(sys.argv),
        "git": git,
        "environment": {"packages": packages, "platform": platform.platform(), "machine": platform.machine()},
        "authorization": config["authorization"],
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
        "formal_training_authorized": False,
        "frozen_sources": frozen,
        "prerequisites": config["prerequisites"],
        "data": {
            "protocol_id": shared["data"]["protocol_id"],
            "train_rows_tokenized": len(rows),
            "sample": sample_summary,
            "full_train_token_lengths": full_token_summary,
            "private_selection": artifact(private_selection_path),
            "raw_text_stored_publicly": False,
            "sample_ids_stored_publicly": False,
        },
        "model": {
            "repo_id": spec["repo_id"],
            "revision": spec["revision"],
            "precision": spec["precision"],
            "pooling": shared["prompt"]["pooling"],
            "head_initial_sha256": head_initial_sha256,
            "head_final_sha256": head_final_sha256,
            "lora_initial_sha256": lora_initial_sha256,
            "lora_final_sha256": lora_final_sha256,
            "zero_step_max_abs_logit_difference": zero_step_difference,
            "insertion_count": len(observed_insertions),
            "lora_parameter_count": lora_parameter_count,
            "head_parameter_count": spec["head_parameters"],
            "total_trainable_parameter_count": total_trainable,
            "trainable_whitelist_passed": True,
            "nonzero_lora_b_tensors": nonzero_lora_b,
            "base_parameter_sentinel_before": base_sentinel_before,
            "base_parameter_sentinel_after": base_sentinel_after,
        },
        "training": {
            "seed": seed,
            "optimizer_steps": len(history),
            "finite_loss_count": len(history),
            "loss_min": min(row["loss"] for row in history),
            "loss_max": max(row["loss"] for row in history),
            "head_optimizer": {"name": "AdamW", "learning_rate": spec["head_learning_rate"], "weight_decay": spec["head_weight_decay"]},
            "lora_optimizer": {"name": "AdamW", "learning_rate": lora["learning_rate"], "weight_decay": lora["weight_decay"]},
            "separate_optimizers": True,
            "gradient_checkpointing": True,
            "measured_training_seconds": measured_training_seconds,
            "history": artifact(history_path),
        },
        "checkpoints": {
            "adapter": artifact(adapter_path),
            "head": artifact(head_path),
            "reference_logits": artifact(reference_path),
            "reload_max_abs_logit_difference": reload_difference,
            "reload_seconds": reload_seconds,
            "maximum_allowed_difference": config["execution"]["maximum_reload_logit_difference"],
            "private": True,
        },
        "resources": {
            "model_load_seconds": model_load_seconds,
            "tokenization_seconds": tokenization_seconds,
            "checkpoint_write_seconds": checkpoint_write_seconds,
            "peak_mlx_memory_gb": peak_memory_gb,
            "projection": projection,
            "gate": resource_gate,
            "api_cost_usd": 0.0,
            "network_access": False,
            "total_preflight_wall_seconds": time.perf_counter() - overall_started,
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_ids": False,
            "private_artifacts_gitignored_required": True,
        },
        "decision": "resource_preflight_passed_formal_training_still_requires_separate_seed_authorization",
        "m2_seed_42_head_reference": m2_run["model_runtime"]["head_initial_sha256"],
    }
    write_json(run_dir / "run.json", run_record)
    report = f"""# EXP-053 M3 Classification LoRA Resource Preflight

## Status

`Passed` as a train-only resource and checkpoint-integrity preflight. Independent
verification is still required. This run does not report classification performance
and does not authorize formal training.

## Gates

- Optimizer steps: `{len(history)}` on `{len(selected)}` private train rows
- LoRA insertions / parameters: `{len(observed_insertions)}` / `{lora_parameter_count}`
- Total trainable parameters: `{total_trainable}`
- Zero-step LoRA logit difference: `{zero_step_difference:.8f}`
- Nonzero `lora_b` tensors after training: `{nonzero_lora_b}`
- Checkpoint reload max absolute logit difference: `{reload_difference:.8g}`
- Peak MLX memory: `{peak_memory_gb:.3f} GB`
- Projected one-seed time with 1.5x safety: `{projection['projected_per_seed_hours_with_safety']:.3f} h`
- Projected three-seed sequential time with 1.5x safety: `{projection['projected_three_seed_hours_with_safety']:.3f} h`
- Validation accessed: no
- Test accessed: no

## Boundary

Passing means the frozen local MLX M3 implementation fits the registered resource
budget and its private checkpoints can be replayed. It is not evidence that M3
improves M2 or M1. Formal seed 42, seeds 43/44, EXP-054 and test remain sealed.
"""
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")
    log("train-only resource preflight completed; formal training remains sealed")
    return run_record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    try:
        result = run(config_path, run_dir)
    except Exception as exc:
        if run_dir.is_dir():
            failure = {
                "schema_version": "exp-053-m3-resource-preflight-failure-v1",
                "experiment_id": EXPERIMENT_ID,
                "stage": STAGE,
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "validation_split_accessed": False,
                "test_split_accessed": False,
                "performance_metrics_computed": False,
                "formal_training_authorized": False,
            }
            write_json(run_dir / "attempt-failure.json", failure)
        raise
    print(json.dumps({"status": result["status"], "decision": result["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
