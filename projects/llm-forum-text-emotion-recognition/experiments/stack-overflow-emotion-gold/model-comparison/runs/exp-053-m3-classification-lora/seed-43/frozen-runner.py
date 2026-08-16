#!/usr/bin/env python3
"""Run the authorized EXP-053 seed-43 Classification LoRA train+validation gate."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gc
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
import subprocess
import sys
import time
from typing import Any, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np


EXPERIMENT_ID = "EXP-053"
SEED = 43
STAGE = "seed-43-train-validation"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
EXPECTED_FIELDS = {
    "component_id", "label_cardinality", "labels", "neutral",
    "protocol_id", "sample_id", "schema_version", "text",
}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-053-m3-seed-43.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-053-m3-classification-lora" / "seed-43"


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


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
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


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen source drift: {path}")
    return path


def load_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(require_record(record).read_text(encoding="utf-8"))


def dynamic_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_versions() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in ("mlx", "mlx-lm", "numpy", "safetensors", "transformers"):
        result[name] = importlib.metadata.version(name)
    return result


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


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("stage") != STAGE:
        raise ValueError("Unexpected EXP-053 formal contract identity")
    auth = config["authorization"]
    expected = {
        "seeds": [SEED], "splits": ["train", "validation"],
        "validation_access": True, "test_access": False,
        "formal_training": True, "seed_44_authorized": False,
        "exp_054_authorized": False,
    }
    for key, value in expected.items():
        if auth.get(key) != value:
            raise PermissionError(f"Authorization drift: {key}")
    if config.get("formal_execution_authorized") is not True:
        raise PermissionError("Formal EXP-053 seed 43 is not authorized")
    for record in config["implementation"].values():
        require_record(record)
    for group in config["prerequisites"].values():
        if isinstance(group, dict) and "path" in group:
            require_record(group)
        else:
            for record in group.values():
                require_record(record)
    shared = load_record(config["prerequisites"]["shared_config"])
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared test boundary drift")
    return config, shared


def require_passed_verification(result: dict[str, Any], expected_count: int, label: str) -> None:
    if result.get("status") != "Passed":
        raise RuntimeError(f"{label} is not verified")
    if result.get("check_count") != expected_count or len(result.get("checks", [])) != expected_count:
        raise RuntimeError(f"{label} verifier count drift")
    if result.get("failed_checks") != []:
        raise RuntimeError(f"{label} verifier has failures")


def validate_prerequisites(config: dict[str, Any], shared: dict[str, Any]) -> dict[str, Any]:
    resource_run = load_record(config["prerequisites"]["resource_preflight"]["run"])
    resource_verify = load_record(config["prerequisites"]["resource_preflight"]["verification"])
    if resource_run.get("status") != "Passed":
        raise RuntimeError("EXP-053 resource preflight run did not pass")
    require_passed_verification(resource_verify, 102, "EXP-053 resource preflight")
    if resource_run.get("validation_split_accessed") or resource_run.get("test_split_accessed"):
        raise PermissionError("Resource preflight split boundary drift")

    prior_m3_run = load_record(config["prerequisites"]["prior_m3_seed_42"]["run"])
    prior_m3_verify = load_record(config["prerequisites"]["prior_m3_seed_42"]["verification"])
    if prior_m3_run.get("status") != "Completed" or prior_m3_run.get("test_split_accessed"):
        raise RuntimeError("Prior EXP-053 seed 42 completion gate failed")
    if (
        prior_m3_verify.get("status") != "Passed"
        or prior_m3_verify.get("checks_total") != 148
        or len(prior_m3_verify.get("checks", [])) != 148
        or prior_m3_verify.get("failed_checks") != []
        or prior_m3_verify.get("test_split_accessed")
    ):
        raise RuntimeError("Prior EXP-053 seed 42 verification gate failed")

    m2_run = load_record(config["prerequisites"]["m2_seed_43"]["run"])
    m2_verify = load_record(config["prerequisites"]["m2_seed_43"]["verification"])
    if m2_run.get("status") != "Completed":
        raise RuntimeError("Matched EXP-052 seed 43 did not complete")
    require_passed_verification(m2_verify, 99, "Matched EXP-052 seed 43")
    if m2_run.get("test_split_accessed") or m2_verify.get("test_split_accessed"):
        raise PermissionError("Matched M2 test boundary drift")
    if m2_run["model_runtime"]["head_initial_sha256"] != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("Matched M2 head initialization drift")

    aggregate = load_record(config["prerequisites"]["m2_aggregate"]["aggregate"])
    aggregate_verify = load_record(config["prerequisites"]["m2_aggregate"]["verification"])
    if aggregate.get("status") != "Completed":
        raise RuntimeError("EXP-052 aggregate did not complete")
    require_passed_verification(aggregate_verify, 85, "EXP-052 aggregate")

    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    if spec["total_iterations_per_seed"] != 6720 or spec["epochs"] != 2:
        raise ValueError("Formal step/epoch contract drift")
    if lora["insertion_points"] != 112 or lora["trainable_parameters"] != 7340032:
        raise ValueError("LoRA contract drift")
    return {"resource_run": resource_run, "m2_run": m2_run}


def load_split(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise PermissionError(f"Split is not authorized: {split}")
    data = shared["data"]
    path = resolve_project(data[f"{split}_path"])
    if sha256(path) != data[f"{split}_sha256"]:
        raise ValueError(f"Frozen {split} hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != data[f"{split}_rows"]:
        raise ValueError(f"{split} row count drift")
    seen: set[str] = set()
    for row in rows:
        if set(row) != EXPECTED_FIELDS or row["protocol_id"] != data["protocol_id"]:
            raise ValueError(f"{split} schema/protocol drift")
        if row["sample_id"] in seen or not isinstance(row["text"], str) or not row["text"].strip():
            raise ValueError(f"{split} sample identity/text drift")
        seen.add(row["sample_id"])
        if len(row["labels"]) != len(LABELS) or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError(f"{split} label vector drift")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError(f"{split} derived fields drift")
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


def load_prompt(shared: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project(shared["prompt"]["path"])
    if sha256(path) != shared["prompt"]["sha256"]:
        raise ValueError("Frozen prompt hash drift")
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> tuple[list[int], int, bool]:
    def apply(value: str) -> list[int]:
        output = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user_prefix"] + value + prompt["user_suffix"]},
            ],
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if not isinstance(output, list) or any(type(token) is not int for token in output):
            raise TypeError("Tokenizer output contract drift")
        return output

    full = apply(text)
    raw_length = len(full)
    if raw_length <= limit:
        selected, truncated = full, False
    else:
        target_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high, selected = 0, len(target_ids), apply("")
        while low <= high:
            middle = (low + high) // 2
            candidate = apply(tokenizer.decode(target_ids[:middle], skip_special_tokens=False))
            if len(candidate) <= limit:
                selected, low = candidate, middle + 1
            else:
                high = middle - 1
        truncated = True
    if not selected or len(selected) > limit:
        raise ValueError("Unable to satisfy frozen Qwen length contract")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Frozen empty-think suffix drift")
    return selected, raw_length, truncated


def tokenize_rows(tokenizer: Any, prompt: dict[str, Any], rows: Sequence[dict[str, Any]], limit: int) -> tuple[list[list[int]], dict[str, Any]]:
    stream = hashlib.sha256()
    lengths: list[int] = []
    raw_lengths: list[int] = []
    truncated = 0
    output: list[list[int]] = []
    for index, row in enumerate(rows):
        ids, raw_length, was_truncated = prompt_ids(tokenizer, prompt, row["text"], limit)
        output.append(ids)
        lengths.append(len(ids))
        raw_lengths.append(raw_length)
        truncated += int(was_truncated)
        array = np.asarray(ids, dtype="<i4")
        stream.update((index + 1).to_bytes(8, "little"))
        stream.update(len(ids).to_bytes(4, "little"))
        stream.update(array.tobytes(order="C"))
    return output, {
        "rows": len(rows),
        "token_id_stream_sha256": stream.hexdigest(),
        "minimum": min(lengths),
        "maximum": max(lengths),
        "mean": float(np.mean(lengths)),
        "p95": float(np.quantile(lengths, 0.95)),
        "raw_maximum": max(raw_lengths),
        "truncated_rows": truncated,
    }


def sigmoid(logits: np.ndarray) -> np.ndarray:
    output = np.empty_like(logits, dtype=np.float32)
    positive = logits >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exp_value = np.exp(logits[~positive])
    output[~positive] = exp_value / (1.0 + exp_value)
    return output


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    precision = np.divide(tp, tp + fp, out=np.zeros(6), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros(6), where=(tp + fn) != 0)
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(6), where=(2 * tp + fp + fn) != 0)
    support = tp + fn
    micro_denominator = 2 * tp.sum() + fp.sum() + fn.sum()
    cardinality = predicted.sum(axis=1)
    without_surprise = [0, 1, 3, 4, 5]
    return {
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(np.mean(gold != predicted)),
        "macro": {"precision": float(precision.mean()), "recall": float(recall.mean()), "f1": float(f1.mean())},
        "micro_f1": float(2 * tp.sum() / micro_denominator) if micro_denominator else 0.0,
        "weighted_f1": float(np.sum(f1 * support) / support.sum()) if support.sum() else 0.0,
        "five_label_macro_f1_without_surprise": float(f1[without_surprise].mean()),
        "per_label": {
            label: {
                "label_id": index, "precision": float(precision[index]),
                "recall": float(recall[index]), "f1": float(f1[index]),
                "support": int(support[index]), "predicted_support": int(tp[index] + fp[index]),
                "tn": int(tn[index]), "fp": int(fp[index]), "fn": int(fn[index]), "tp": int(tp[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": float(f1.mean())},
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


def select_threshold(gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]) -> tuple[float, list[dict[str, float]]]:
    rows = [
        {"threshold": float(value), "macro_f1": metric_bundle(gold, (probabilities >= value).astype(np.uint8))["macro"]["f1"]}
        for value in grid
    ]
    selected = min(rows, key=lambda row: (-row["macro_f1"], abs(row["threshold"] - 0.5), row["threshold"]))
    return selected["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6), where=denominator != 0)


def bootstrap_summary(gold: np.ndarray, predicted: np.ndarray, component_ids: Sequence[str], seed: int, replicates: int, namespace: str, condition: str) -> dict[str, Any]:
    components = sorted(set(component_ids))
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    material = f"{namespace}|EXP-053|seed-{seed}|{condition}"
    rng_seed = int(hashlib.sha256(material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(rng_seed)
    values = np.zeros((replicates, 6))
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], predicted[indices])
    point = fast_f1(gold, predicted)

    def interval(series: np.ndarray, value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(value), "lower": float(lower), "upper": float(upper)}

    without_surprise = [0, 1, 3, 4, 5]
    return {
        "unit": "duplicate_component_id", "component_count": len(components),
        "row_count": len(component_ids), "replicates": replicates,
        "seed": rng_seed, "seed_material": material, "interval": "percentile_2.5_97.5",
        "macro_f1": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_without_surprise": interval(values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())),
        "per_label_f1": {label: interval(values[:, index], float(point[index])) for index, label in enumerate(LABELS)},
    }


def paired_bootstrap(gold: np.ndarray, m3_predicted: np.ndarray, m2_predicted: np.ndarray, component_ids: Sequence[str], seed: int, replicates: int, namespace: str, condition: str) -> dict[str, Any]:
    components = sorted(set(component_ids))
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    material = f"{namespace}|EXP-053|seed-{seed}|M3-minus-M2|{condition}"
    rng_seed = int(hashlib.sha256(material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(rng_seed)
    values = np.zeros((replicates, 6))
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], m3_predicted[indices]) - fast_f1(gold[indices], m2_predicted[indices])
    point = fast_f1(gold, m3_predicted) - fast_f1(gold, m2_predicted)

    def interval(series: np.ndarray, value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(value), "lower": float(lower), "upper": float(upper)}

    without_surprise = [0, 1, 3, 4, 5]
    return {
        "unit": "duplicate_component_id", "component_count": len(components),
        "row_count": len(component_ids), "replicates": replicates,
        "seed": rng_seed, "seed_material": material, "interval": "percentile_2.5_97.5",
        "macro_f1_delta": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_delta_without_surprise": interval(values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())),
        "per_label_f1_delta": {label: interval(values[:, index], float(point[index])) for index, label in enumerate(LABELS)},
    }


def write_history(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = (
        "seed", "epoch", "optimizer_steps", "train_loss", "validation_loss",
        "fixed_threshold", "fixed_macro_precision", "fixed_macro_recall", "fixed_macro_f1",
        "fixed_micro_f1", "fixed_weighted_f1", "fixed_subset_accuracy", "fixed_hamming_loss",
        "fixed_five_label_macro_f1_without_surprise", "batch_order_sha256", "epoch_seconds",
        "validation_seconds",
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
        writer.writerow(("label", "tn", "fp", "fn", "tp", "orientation"))
        for label in LABELS:
            row = metrics["per_label"][label]
            writer.writerow((label, row["tn"], row["fp"], row["fn"], row["tp"], "rows=true,columns=predicted"))


def save_checkpoint(directory: Path, model: Any, head: Any, primitives: Any) -> dict[str, Any]:
    import mlx.core as mx

    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    adapter_path = directory / "adapters.safetensors"
    head_path = directory / "head.safetensors"
    mx.save_safetensors(str(adapter_path), dict(primitives.mlx_trainable(model)))
    mx.save_safetensors(str(head_path), dict(primitives.mlx_trainable(head)))
    for path in (adapter_path, head_path):
        os.chmod(path, 0o600)
    return {"adapter": artifact(adapter_path), "head": artifact(head_path)}


def evaluate(wrapper: Any, token_ids: Sequence[list[int]], gold: np.ndarray, log_every: int, logger: logging.Logger) -> tuple[float, np.ndarray, float]:
    import mlx.core as mx

    logits = np.empty((len(token_ids), len(LABELS)), dtype=np.float32)
    started = time.perf_counter()
    for index, ids in enumerate(token_ids):
        value = wrapper(mx.array([ids], dtype=mx.int32)).astype(mx.float32)
        mx.eval(value)
        logits[index] = np.asarray(value)[0]
        if (index + 1) % log_every == 0 or index + 1 == len(token_ids):
            logger.info("Validation forward %d/%d", index + 1, len(token_ids))
        if (index + 1) % 100 == 0:
            mx.clear_cache()
    loss = float(np.mean(np.logaddexp(0.0, logits) - gold.astype(np.float32) * logits))
    probabilities = sigmoid(logits)
    if not math.isfinite(loss) or not np.isfinite(probabilities).all():
        raise ValueError("Invalid validation output")
    return loss, probabilities, time.perf_counter() - started


def initialize_model(shared: dict[str, Any], config: dict[str, Any], train_rows: Sequence[dict[str, Any]], validation_rows: Sequence[dict[str, Any]], logger: logging.Logger) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    primitives = dynamic_module("so_exp050_primitives_for_exp053_formal", require_record(config["implementation"]["primitives"]))
    helper = dynamic_module("so_exp053_preflight_helpers_for_formal", require_record(config["implementation"]["resource_runner_reference"]))
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    load_started = time.perf_counter()
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model_load_seconds = time.perf_counter() - load_started
    model.freeze()
    model.eval()
    prompt = load_prompt(shared)
    token_started = time.perf_counter()
    train_ids, train_token_summary = tokenize_rows(tokenizer, prompt, train_rows, int(shared["prompt"]["max_sequence_length"]))
    validation_ids, validation_token_summary = tokenize_rows(tokenizer, prompt, validation_rows, int(shared["prompt"]["max_sequence_length"]))
    tokenization_seconds = time.perf_counter() - token_started
    seed = SEED
    head = primitives.build_qwen_head(seed, int(spec["hidden_size"]))
    head_initial = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    if head_initial != config["execution"]["expected_head_initial_sha256"]:
        raise ValueError("Seed-43 head initialization does not match M2")
    wrapper = primitives.make_classification_wrapper(model, head)
    first_ids = mx.array([train_ids[0]], dtype=mx.int32)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)
    mx.random.seed(seed + 100000)
    linear_to_lora_layers(model, lora["num_layers"], {
        "rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"], "keys": lora["target_modules"],
    })
    observed = primitives.insertion_contract(model, shared)
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_delta = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    lora_items = primitives.mlx_trainable(model)
    trainable_items = primitives.mlx_trainable(wrapper)
    unexpected = [name for name, _ in trainable_items if not helper.trainable_name_allowed(name)]
    lora_count = sum(int(tensor.size) for _, tensor in lora_items)
    total_count = sum(int(tensor.size) for _, tensor in trainable_items)
    if zero_delta != 0.0 or len(observed) != 112 or lora_count != 7340032 or total_count != 7355398 or unexpected:
        raise ValueError("M3 zero-step/trainable contract failed")
    result = {
        "model": model, "tokenizer": tokenizer, "head": head, "wrapper": wrapper,
        "primitives": primitives, "helper": helper, "train_ids": train_ids,
        "validation_ids": validation_ids, "model_load_seconds": model_load_seconds,
        "tokenization_seconds": tokenization_seconds, "train_token_summary": train_token_summary,
        "validation_token_summary": validation_token_summary, "head_initial_sha256": head_initial,
        "lora_initial_sha256": primitives.mlx_tensor_digest(lora_items),
        "zero_step_max_abs_logit_difference": zero_delta, "insertion_count": len(observed),
        "lora_parameter_count": lora_count, "total_trainable_parameter_count": total_count,
        "base_sentinel_before": helper.frozen_parameter_sentinel(model),
    }
    del base_logits, converted_logits, first_ids, lora_items, trainable_items
    logger.info("Model initialized; tokenized %d train and %d validation rows", len(train_rows), len(validation_rows))
    return result


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    sources = {"config": {"path": display_path(config_path), "bytes": config_path.stat().st_size, "sha256": sha256(config_path)}, **config["implementation"], "shared_config": config["prerequisites"]["shared_config"]}
    frozen: dict[str, Any] = {}
    for name, record in sources.items():
        source = require_record(record)
        destination = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, destination)
        frozen[name] = artifact(destination)
    return frozen


def setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"exp-053-{run_dir.name}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    for handler in (logging.FileHandler(run_dir / "stdout.log", encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def run_preflight_only(config_path: Path) -> dict[str, Any]:
    config, shared = load_config(config_path)
    validate_prerequisites(config, shared)
    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("Architecture gate failed")
    train_rows = load_split(shared, "train")
    validation_rows = load_split(shared, "validation")
    if {row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}:
        raise ValueError("Train/validation component overlap")
    logger = logging.getLogger("exp-053-formal-preflight")
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler())
    initialized = initialize_model(shared, config, train_rows, validation_rows, logger)
    rng = np.random.default_rng(SEED)
    orders = np.stack([rng.permutation(len(train_rows)) for _ in range(2)]).astype(np.int32)
    result = {
        "status": "Passed", "stage": "formal-preflight-only", "accessed_splits": ["train", "validation"],
        "test_split_accessed": False, "train_rows": len(train_rows), "validation_rows": len(validation_rows),
        "head_initial_sha256": initialized["head_initial_sha256"],
        "zero_step_max_abs_logit_difference": initialized["zero_step_max_abs_logit_difference"],
        "insertion_count": initialized["insertion_count"],
        "batch_order_digests": [canonical_digest([train_rows[int(index)]["sample_id"] for index in order]) for order in orders],
    }
    del initialized
    gc.collect()
    import mlx.core as mx
    mx.clear_cache()
    return result


def run(config_path: Path, run_dir: Path) -> dict[str, Any]:
    config, shared = load_config(config_path)
    prerequisites = validate_prerequisites(config, shared)
    private_dir = resolve_project(config["execution"]["private_run_dir"])
    for path in (run_dir, private_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite append-only output: {path}")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    logger = setup_logger(run_dir)
    started_at = utc_now()
    started = time.perf_counter()
    frozen_sources = freeze_sources(run_dir, config_path, config)
    packages = package_versions()
    git = git_metadata()
    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("Architecture gate failed")

    train_rows = load_split(shared, "train")
    validation_rows = load_split(shared, "validation")
    if {row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}:
        raise ValueError("Train/validation component overlap")
    if {row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}:
        raise ValueError("Train/validation sample overlap")

    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm.tuner.trainer import grad_checkpoint

    mx.reset_peak_memory()
    initialized = initialize_model(shared, config, train_rows, validation_rows, logger)
    model = initialized["model"]
    tokenizer = initialized["tokenizer"]
    head = initialized["head"]
    wrapper = initialized["wrapper"]
    primitives = initialized["primitives"]
    helper = initialized["helper"]
    train_ids = initialized["train_ids"]
    validation_ids = initialized["validation_ids"]
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    train_gold = np.asarray([row["labels"] for row in train_rows], dtype=np.float32)
    validation_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    rng = np.random.default_rng(SEED)
    batch_orders = np.stack([rng.permutation(len(train_rows)) for _ in range(int(spec["epochs"]))]).astype(np.int32)
    batch_order_path = private_dir / "batch-orders.npy"
    np.save(batch_order_path, batch_orders, allow_pickle=False)
    os.chmod(batch_order_path, 0o600)

    grad_checkpoint(model.layers[0])
    model.train()
    head_optimizer = optim.AdamW(learning_rate=float(spec["head_learning_rate"]), weight_decay=float(spec["head_weight_decay"]))
    lora_optimizer = optim.AdamW(learning_rate=float(lora["learning_rate"]), weight_decay=float(lora["weight_decay"]))
    loss_and_grad = nn.value_and_grad(wrapper, primitives.classification_loss)
    checkpoint_root = private_dir / "checkpoints"
    checkpoint_root.mkdir(mode=0o700)
    history: list[dict[str, Any]] = []
    epoch_probabilities: list[np.ndarray] = []
    checkpoint_records: dict[str, Any] = {}
    global_step = 0
    training_started = time.perf_counter()
    for epoch, order in enumerate(batch_orders, start=1):
        epoch_started = time.perf_counter()
        loss_sum = 0.0
        for position, row_index in enumerate(order, start=1):
            ids = mx.array([train_ids[int(row_index)]], dtype=mx.int32)
            targets = mx.array(train_gold[int(row_index):int(row_index) + 1], dtype=mx.float32)
            loss, gradients = loss_and_grad(wrapper, ids, targets)
            lora_optimizer.update(wrapper.backbone, gradients["backbone"])
            head_optimizer.update(wrapper.head, gradients["head"])
            mx.eval(loss, wrapper.trainable_parameters(), lora_optimizer.state, head_optimizer.state)
            value = float(loss.item())
            if not math.isfinite(value):
                raise ValueError(f"Non-finite loss at epoch {epoch}, position {position}")
            loss_sum += value
            global_step += 1
            if position % int(config["execution"]["log_every_steps"]) == 0 or position == len(order):
                logger.info("Epoch %d train %d/%d mean_loss=%.6f peak=%.3fGB", epoch, position, len(order), loss_sum / position, float(mx.get_peak_memory()) / 1e9)
            if float(mx.get_peak_memory()) / 1e9 > float(config["execution"]["maximum_peak_memory_gb"]):
                raise MemoryError("Formal M3 exceeded frozen MLX memory budget")
            if time.perf_counter() - started > float(config["execution"]["maximum_total_wall_hours"]) * 3600:
                raise TimeoutError("Formal M3 exceeded frozen wall-time budget")
            if position % 250 == 0:
                mx.clear_cache()

        model.eval()
        validation_loss, probabilities, validation_seconds = evaluate(
            wrapper, validation_ids, validation_gold,
            int(config["execution"]["validation_log_every_rows"]), logger,
        )
        fixed_predictions = (probabilities >= float(shared["evaluation"]["fixed_threshold"])).astype(np.uint8)
        fixed_metrics = metric_bundle(validation_gold, fixed_predictions)
        checkpoint_records[f"epoch-{epoch}"] = save_checkpoint(checkpoint_root / f"epoch-{epoch}", model, head, primitives)
        epoch_probabilities.append(probabilities)
        order_digest = canonical_digest([train_rows[int(index)]["sample_id"] for index in order])
        history.append({
            "seed": SEED, "epoch": epoch, "optimizer_steps": global_step,
            "train_loss": loss_sum / len(order), "validation_loss": validation_loss,
            "fixed_threshold": float(shared["evaluation"]["fixed_threshold"]),
            "fixed_macro_precision": fixed_metrics["macro"]["precision"],
            "fixed_macro_recall": fixed_metrics["macro"]["recall"],
            "fixed_macro_f1": fixed_metrics["macro"]["f1"], "fixed_micro_f1": fixed_metrics["micro_f1"],
            "fixed_weighted_f1": fixed_metrics["weighted_f1"], "fixed_subset_accuracy": fixed_metrics["subset_accuracy"],
            "fixed_hamming_loss": fixed_metrics["hamming_loss"],
            "fixed_five_label_macro_f1_without_surprise": fixed_metrics["five_label_macro_f1_without_surprise"],
            "batch_order_sha256": order_digest, "epoch_seconds": time.perf_counter() - epoch_started,
            "validation_seconds": validation_seconds,
        })
        logger.info("Epoch %d complete train_loss=%.6f val_loss=%.6f fixed_macro_f1=%.6f", epoch, loss_sum / len(order), validation_loss, fixed_metrics["macro"]["f1"])
        model.train()

    if global_step != int(spec["total_iterations_per_seed"]) or len(epoch_probabilities) != int(spec["epochs"]):
        raise ValueError("Formal M3 completion-count drift")
    training_seconds = time.perf_counter() - training_started
    probability_array = np.stack(epoch_probabilities).astype(np.float32, copy=False)
    selection = select_checkpoint(history, float(shared["evaluation"]["practical_tie_delta"]))
    selected_epoch = int(selection["selected_epoch"])
    selected_probabilities = probability_array[selected_epoch - 1]
    selected_dir = private_dir / "selected-checkpoint"
    shutil.copytree(checkpoint_root / f"epoch-{selected_epoch}", selected_dir)
    selected_checkpoint = {
        "adapter": artifact(selected_dir / "adapters.safetensors"),
        "head": artifact(selected_dir / "head.safetensors"),
    }
    fixed_threshold = float(shared["evaluation"]["fixed_threshold"])
    selected_threshold, threshold_rows = select_threshold(validation_gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"])
    fixed_predictions = (selected_probabilities >= fixed_threshold).astype(np.uint8)
    shared_predictions = (selected_probabilities >= selected_threshold).astype(np.uint8)
    fixed_metrics = metric_bundle(validation_gold, fixed_predictions)
    shared_metrics = metric_bundle(validation_gold, shared_predictions)
    component_ids = [row["component_id"] for row in validation_rows]
    replicates = int(shared["evaluation"]["bootstrap"]["replicates"])
    namespace = shared["evaluation"]["bootstrap"]["seed_namespace"]
    bootstrap = {
        "fixed_0.5": bootstrap_summary(validation_gold, fixed_predictions, component_ids, SEED, replicates, namespace, "fixed-0.5"),
        "shared_threshold": bootstrap_summary(validation_gold, shared_predictions, component_ids, SEED, replicates, namespace, f"shared-{selected_threshold:.2f}"),
    }

    m2_run = prerequisites["m2_run"]
    m2_predictions_record = m2_run["artifacts"]["validation_predictions_private"]
    m2_predictions_path = require_record(m2_predictions_record)
    with np.load(m2_predictions_path, allow_pickle=False) as m2_private:
        if m2_private["sample_ids"].tolist() != [row["sample_id"] for row in validation_rows]:
            raise ValueError("Matched M2 validation order drift")
        if not np.array_equal(m2_private["gold"], validation_gold):
            raise ValueError("Matched M2 gold drift")
        m2_fixed_predictions = np.asarray(m2_private["fixed_predictions"], dtype=np.uint8)
        m2_shared_predictions = np.asarray(m2_private["shared_threshold_predictions"], dtype=np.uint8)
    paired = {
        "comparison": "EXP-053_M3_seed43_minus_EXP-052_M2_seed43",
        "fixed_0.5": paired_bootstrap(validation_gold, fixed_predictions, m2_fixed_predictions, component_ids, SEED, replicates, namespace, "fixed-0.5"),
        "shared_threshold": paired_bootstrap(validation_gold, shared_predictions, m2_shared_predictions, component_ids, SEED, replicates, namespace, f"M3-{selected_threshold:.2f}_M2-{m2_run['threshold_selection']['selected_threshold']:.2f}"),
        "metric_deltas": {
            "fixed_macro_f1": fixed_metrics["macro"]["f1"] - m2_run["metrics"]["fixed_0.5"]["macro"]["f1"],
            "shared_macro_f1": shared_metrics["macro"]["f1"] - m2_run["metrics"]["shared_threshold"]["macro"]["f1"],
            "fixed_micro_f1": fixed_metrics["micro_f1"] - m2_run["metrics"]["fixed_0.5"]["micro_f1"],
            "shared_micro_f1": shared_metrics["micro_f1"] - m2_run["metrics"]["shared_threshold"]["micro_f1"],
            "fixed_subset_accuracy": fixed_metrics["subset_accuracy"] - m2_run["metrics"]["fixed_0.5"]["subset_accuracy"],
            "shared_subset_accuracy": shared_metrics["subset_accuracy"] - m2_run["metrics"]["shared_threshold"]["subset_accuracy"],
        },
    }

    head_final = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    lora_final_items = primitives.mlx_trainable(model)
    lora_final = primitives.mlx_tensor_digest(lora_final_items)
    nonzero_lora_b = sum(bool(mx.any(value != 0).item()) for name, value in lora_final_items if name.endswith("lora_b"))
    base_after = helper.frozen_parameter_sentinel(model)
    if head_final == initialized["head_initial_sha256"] or lora_final == initialized["lora_initial_sha256"]:
        raise ValueError("Head or LoRA did not update")
    if nonzero_lora_b != 112 or base_after != initialized["base_sentinel_before"]:
        raise ValueError("LoRA update or frozen-base sentinel gate failed")

    predictions_path = private_dir / "validation-predictions.npz"
    np.savez_compressed(
        predictions_path, probabilities=probability_array, gold=validation_gold,
        fixed_predictions=fixed_predictions, shared_threshold_predictions=shared_predictions,
        sample_ids=np.asarray([row["sample_id"] for row in validation_rows]),
        component_ids=np.asarray(component_ids),
    )
    os.chmod(predictions_path, 0o600)
    private_manifest_path = private_dir / "private-manifest.json"
    atomic_json(private_manifest_path, {
        "experiment_id": EXPERIMENT_ID, "stage": STAGE, "seed": SEED,
        "contains_raw_text": False, "contains_row_identifiers": True,
        "batch_orders": artifact(batch_order_path), "validation_predictions": artifact(predictions_path),
        "checkpoints": checkpoint_records, "selected_checkpoint": selected_checkpoint,
    }, private=True)

    history_path = run_dir / "history.csv"
    threshold_path = run_dir / "threshold-grid.csv"
    fixed_path = run_dir / "metrics-fixed-0.5.json"
    shared_path = run_dir / "metrics-shared-threshold.json"
    bootstrap_path = run_dir / "bootstrap.json"
    paired_path = run_dir / "paired-m3-minus-m2.json"
    selection_path = run_dir / "selection.json"
    write_history(history_path, history)
    write_threshold_grid(threshold_path, threshold_rows)
    atomic_json(fixed_path, fixed_metrics)
    atomic_json(shared_path, shared_metrics)
    atomic_json(bootstrap_path, bootstrap)
    atomic_json(paired_path, paired)
    atomic_json(selection_path, selection)
    tables: dict[str, Any] = {}
    for name, metrics in (("fixed-0.5", fixed_metrics), ("shared-threshold", shared_metrics)):
        per_label_path = run_dir / f"per-label-{name}.csv"
        confusion_path = run_dir / f"multilabel-confusion-{name}.csv"
        write_per_label(per_label_path, metrics)
        write_confusion(confusion_path, metrics)
        tables[name] = {"per_label": artifact(per_label_path), "confusion": artifact(confusion_path)}

    peak_memory = float(mx.get_peak_memory()) / 1e9
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_gb = peak_rss / 1e9 if platform.system() == "Darwin" else peak_rss * 1024 / 1e9
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("Formal M3 exceeded frozen MLX memory budget")
    if time.perf_counter() - started > float(config["execution"]["maximum_total_wall_hours"]) * 3600:
        raise TimeoutError("Formal M3 exceeded frozen wall-time budget")
    logger.info("Formal seed 43 completed; independent verification is required")
    completed_at = utc_now()
    run_record = {
        "schema_version": "exp-053-m3-seed-run-v1", "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S1", "tier": "Major", "stage": STAGE, "status": "Completed",
        "started_at_utc": started_at, "completed_at_utc": completed_at,
        "invocation": " ".join(sys.argv), "working_directory": str(PROJECT_ROOT),
        "git": git, "environment": {"machine": platform.machine(), "platform": platform.platform(), "packages": packages, "executable": sys.executable},
        "authorization": config["authorization"], "accessed_splits": ["train", "validation"],
        "validation_split_accessed": True, "test_split_accessed": False,
        "performance_metrics_computed": True, "formal_training_authorized": True,
        "frozen_sources": frozen_sources, "prerequisites": config["prerequisites"],
        "data": {
            "protocol_id": shared["data"]["protocol_id"], "labels": list(LABELS),
            "train": {"sha256": shared["data"]["train_sha256"], "summary": split_summary(train_rows), "tokenization": initialized["train_token_summary"]},
            "validation": {"sha256": shared["data"]["validation_sha256"], "summary": split_summary(validation_rows), "tokenization": initialized["validation_token_summary"]},
            "cross_split_component_overlap": 0, "cross_split_sample_overlap": 0,
            "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
        },
        "model": {
            "repo_id": spec["repo_id"], "revision": spec["revision"], "precision": spec["precision"],
            "pooling": shared["prompt"]["pooling"], "head_initial_sha256": initialized["head_initial_sha256"],
            "head_final_sha256": head_final, "lora_initial_sha256": initialized["lora_initial_sha256"],
            "lora_final_sha256": lora_final, "zero_step_max_abs_logit_difference": initialized["zero_step_max_abs_logit_difference"],
            "insertion_count": initialized["insertion_count"], "lora_parameter_count": initialized["lora_parameter_count"],
            "head_parameter_count": int(spec["head_parameters"]), "total_trainable_parameter_count": initialized["total_trainable_parameter_count"],
            "nonzero_lora_b_tensors": nonzero_lora_b, "base_parameter_sentinel_before": initialized["base_sentinel_before"],
            "base_parameter_sentinel_after": base_after, "trainable_whitelist_passed": True,
        },
        "training": {
            "seed": SEED, "epochs": int(spec["epochs"]), "batch_size": int(spec["batch_size"]),
            "gradient_accumulation_steps": int(spec["gradient_accumulation_steps"]),
            "total_optimizer_steps": global_step, "loss": "unweighted_binary_cross_entropy_with_logits",
            "head_optimizer": {"name": "AdamW", "learning_rate": float(spec["head_learning_rate"]), "weight_decay": float(spec["head_weight_decay"])},
            "lora_optimizer": {"name": "AdamW", "learning_rate": float(lora["learning_rate"]), "weight_decay": float(lora["weight_decay"])},
            "separate_optimizers": True, "gradient_checkpointing": True,
            "batch_order_rng": config["execution"]["batch_order_rng"], "history": history,
        },
        "selection": selection,
        "threshold_selection": {"selected_threshold": selected_threshold, "grid": list(shared["evaluation"]["shared_threshold_grid"]), "rule": shared["evaluation"]["shared_threshold_rule"]},
        "metrics": {"fixed_0.5": fixed_metrics, "shared_threshold": shared_metrics},
        "bootstrap": bootstrap, "paired_m3_minus_m2": paired,
        "resources": {
            "api_cost_usd": 0, "wall_seconds": time.perf_counter() - started,
            "model_load_seconds": initialized["model_load_seconds"], "tokenization_seconds": initialized["tokenization_seconds"],
            "training_and_epoch_validation_seconds": training_seconds,
            "peak_mlx_memory_gb": peak_memory, "peak_process_rss_gb": peak_rss_gb,
        },
        "privacy": {"public_raw_text": False, "public_row_identifiers": False, "private_artifacts_gitignored": True},
        "warnings": [
            "This is the second of three planned seeds and does not establish the M3 family result.",
            "Validation selects the checkpoint and shared threshold; test remains sealed.",
            "Classification performance does not establish an internal emotion mechanism.",
        ],
        "artifacts": {
            "history": artifact(history_path), "threshold_grid": artifact(threshold_path),
            "metrics_fixed": artifact(fixed_path), "metrics_shared_threshold": artifact(shared_path),
            "bootstrap": artifact(bootstrap_path), "paired_m3_minus_m2": artifact(paired_path),
            "selection": artifact(selection_path), "tables": tables,
            "stdout_log": artifact(run_dir / "stdout.log"), "private_manifest": artifact(private_manifest_path),
            "batch_orders_private": artifact(batch_order_path), "validation_predictions_private": artifact(predictions_path),
            "epoch_checkpoints_private": checkpoint_records, "selected_checkpoint_private": selected_checkpoint,
        },
    }
    atomic_json(run_dir / "run.json", run_record)
    report = "\n".join([
        "# EXP-053 M3 Classification LoRA Seed 43", "",
        "- Status: `Completed`; independent verification pending",
        "- Accessed splits: train, validation", "- Test accessed: no",
        f"- Selected epoch: `{selected_epoch}`", f"- Fixed 0.5 Macro-F1: `{fixed_metrics['macro']['f1']:.6f}`",
        f"- Shared threshold: `{selected_threshold:.2f}`", f"- Shared-threshold Macro-F1: `{shared_metrics['macro']['f1']:.6f}`",
        f"- Shared-threshold Micro-F1: `{shared_metrics['micro_f1']:.6f}`",
        f"- Shared-threshold subset accuracy: `{shared_metrics['subset_accuracy']:.6f}`",
        f"- M3-M2 shared-threshold Macro-F1 delta: `{paired['metric_deltas']['shared_macro_f1']:+.6f}`",
        f"- Peak MLX memory: `{peak_memory:.3f} GB`", f"- Wall time: `{run_record['resources']['wall_seconds'] / 3600:.3f} h`", "",
        "This is the second of three seed validation results. Seed 44, EXP-054 and test remain sealed.", "",
    ])
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")
    return run_record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.preflight_only:
        print(json.dumps(run_preflight_only(config_path), indent=2, sort_keys=True))
        return
    run_dir = args.run_dir.resolve()
    try:
        result = run(config_path, run_dir)
    except Exception as exc:
        if run_dir.is_dir():
            atomic_json(run_dir / "attempt-failure.json", {
                "schema_version": "exp-053-m3-seed-failure-v1", "experiment_id": EXPERIMENT_ID,
                "stage": STAGE, "status": "Failed", "failed_at_utc": utc_now(),
                "exception_type": type(exc).__name__, "error": str(exc),
                "test_split_accessed": False,
            })
        raise
    print(json.dumps({"status": result["status"], "selected_epoch": result["selection"]["selected_epoch"], "macro_f1": result["metrics"]["shared_threshold"]["macro"]["f1"]}, sort_keys=True))


if __name__ == "__main__":
    main()
