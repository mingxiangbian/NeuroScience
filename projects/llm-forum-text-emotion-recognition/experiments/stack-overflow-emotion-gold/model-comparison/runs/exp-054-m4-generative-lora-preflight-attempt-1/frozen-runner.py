#!/usr/bin/env python3
"""Run the authorized EXP-054 generative LoRA preflight, training, and replay stages."""

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


EXPERIMENT_ID = "EXP-054"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
EXPECTED_FIELDS = {
    "component_id", "label_cardinality", "labels", "neutral",
    "protocol_id", "sample_id", "schema_version", "text",
}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-054-m4-three-seed.json"


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


def atomic_jsonl(path: Path, rows: Sequence[dict[str, Any]], *, private: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
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


def setup_logger(path: Path, name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    for handler in (logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Unexpected EXP-054 contract identity")
    if config.get("formal_execution_authorized") is not True:
        raise PermissionError("EXP-054 formal execution is not authorized")
    auth = config["authorization"]
    expected = {
        "seeds": [42, 43, 44],
        "splits": ["train", "validation"],
        "validation_access": True,
        "test_access": False,
        "formal_training": True,
        "fresh_process_replay_passes": 2,
    }
    for key, value in expected.items():
        if auth.get(key) != value:
            raise PermissionError(f"Authorization drift: {key}")
    for record in config["implementation"].values():
        require_record(record)
    for group in config["prerequisites"].values():
        if "path" in group:
            require_record(group)
        else:
            for record in group.values():
                require_record(record)
    shared = load_record(config["prerequisites"]["shared_config"])
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared test boundary drift")
    return config, shared


def validate_prerequisites(config: dict[str, Any], shared: dict[str, Any]) -> None:
    preflight = config["prerequisites"]["exp_050"]
    run = load_record(preflight["run"])
    verification = load_record(preflight["verification"])
    if run.get("status") != "Passed" or verification.get("status") != "Passed":
        raise RuntimeError("EXP-050 gate is not verified")
    if verification.get("failed_checks") or run.get("validation_split_accessed") or run.get("test_split_accessed"):
        raise RuntimeError("EXP-050 split or verification gate drift")
    for seed in (42, 43, 44):
        group = config["prerequisites"][f"m3_seed_{seed}"]
        m3_run = load_record(group["run"])
        m3_verify = load_record(group["verification"])
        if m3_run.get("status") != "Completed" or m3_verify.get("status") != "Passed":
            raise RuntimeError(f"Matched M3 seed {seed} is not verified")
        if m3_run.get("test_split_accessed") or m3_verify.get("test_split_accessed"):
            raise PermissionError(f"Matched M3 seed {seed} test boundary drift")
    aggregate = load_record(config["prerequisites"]["m3_aggregate"]["aggregate"])
    aggregate_verify = load_record(config["prerequisites"]["m3_aggregate"]["verification"])
    if aggregate.get("status") != "Completed" or aggregate_verify.get("status") != "Passed":
        raise RuntimeError("EXP-053 three-seed aggregate is not verified")
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    if spec["epochs"] != 2 or spec["total_iterations_per_seed"] != 6720:
        raise ValueError("Epoch/step contract drift")
    if lora["insertion_points"] != 112 or lora["trainable_parameters"] != 7340032:
        raise ValueError("LoRA contract drift")
    if shared["models"]["m4"]["generation"] != {
        "temperature": 0.0, "max_new_tokens": 48, "batch_size": 1, "retries": 0,
    }:
        raise ValueError("Generation contract drift")


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
            raise ValueError(f"{split} identity/text drift")
        seen.add(row["sample_id"])
        if len(row["labels"]) != 6 or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError(f"{split} label vector drift")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError(f"{split} derived-field drift")
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


def messages(prompt: dict[str, Any], text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]},
    ]


def normalize_token_ids(value: Any) -> list[int]:
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise TypeError("Tokenizer must return a plain list of integer token IDs")
    return value


def apply_prompt(tokenizer: Any, prompt: dict[str, Any], text: str) -> list[int]:
    return normalize_token_ids(tokenizer.apply_chat_template(
        messages(prompt, text), tokenize=True, return_dict=False,
        add_generation_prompt=True, enable_thinking=False,
    ))


def apply_full(tokenizer: Any, prompt: dict[str, Any], text: str, target: str) -> list[int]:
    return normalize_token_ids(tokenizer.apply_chat_template(
        messages(prompt, text) + [{"role": "assistant", "content": target}],
        tokenize=True, return_dict=False, enable_thinking=False,
    ))


def fit_text_for_full_sequence(
    tokenizer: Any, prompt: dict[str, Any], text: str, target: str, limit: int,
) -> tuple[str, list[int], list[int], int, bool]:
    prefix = apply_prompt(tokenizer, prompt, text)
    full = apply_full(tokenizer, prompt, text, target)
    raw_length = len(full)
    if len(full) <= limit:
        selected_text, truncated = text, False
    else:
        text_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high = 0, len(text_ids)
        selected_text = ""
        while low <= high:
            middle = (low + high) // 2
            candidate = tokenizer.decode(text_ids[:middle], skip_special_tokens=False)
            candidate_full = apply_full(tokenizer, prompt, candidate, target)
            if len(candidate_full) <= limit:
                selected_text, low = candidate, middle + 1
            else:
                high = middle - 1
        prefix = apply_prompt(tokenizer, prompt, selected_text)
        full = apply_full(tokenizer, prompt, selected_text, target)
        truncated = True
    if not prefix or len(full) > limit or full[:len(prefix)] != prefix:
        raise ValueError("M4 prompt/full sequence contract failed")
    if not tokenizer.decode(prefix).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Frozen empty-think suffix drift")
    return selected_text, prefix, full, raw_length, truncated


def m4_sequence(
    tokenizer: Any, prompt: dict[str, Any], row: dict[str, Any], limit: int, parser_module: Any,
) -> tuple[list[int], list[int], list[float], dict[str, Any]]:
    target = parser_module.canonical_target(row["labels"], LABELS)
    selected_text, prefix, full, raw_length, truncated = fit_text_for_full_sequence(
        tokenizer, prompt, row["text"], target, limit
    )
    inputs, targets = full[:-1], full[1:]
    weights = [0.0] * (len(prefix) - 1) + [1.0] * (len(full) - len(prefix))
    supervised = int(sum(weights))
    if len(inputs) != len(targets) or len(weights) != len(targets) or supervised <= 1:
        raise ValueError("Assistant-only supervision mask drift")
    if any(weights[index] for index in range(len(prefix) - 1)):
        raise ValueError("Prompt token received loss weight")
    return inputs, targets, weights, {
        "prompt_tokens": len(prefix), "full_tokens": len(full), "raw_full_tokens": raw_length,
        "supervised_tokens": supervised, "truncated": truncated,
        "selected_text_sha256": hashlib.sha256(selected_text.encode()).hexdigest(),
        "canonical_target": target,
    }


def prompt_ids(
    tokenizer: Any, prompt: dict[str, Any], text: str, limit: int,
) -> tuple[list[int], int, bool]:
    ids = apply_prompt(tokenizer, prompt, text)
    raw_length = len(ids)
    if len(ids) <= limit:
        selected = ids
        truncated = False
    else:
        text_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high, selected = 0, len(text_ids), apply_prompt(tokenizer, prompt, "")
        while low <= high:
            middle = (low + high) // 2
            candidate = apply_prompt(
                tokenizer, prompt, tokenizer.decode(text_ids[:middle], skip_special_tokens=False)
            )
            if len(candidate) <= limit:
                selected, low = candidate, middle + 1
            else:
                high = middle - 1
        truncated = True
    if not selected or len(selected) > limit:
        raise ValueError("Unable to satisfy frozen generation prompt length")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Frozen empty-think suffix drift")
    return selected, raw_length, truncated


def m4_loss(model: Any, inputs: Any, targets: Any, weights: Any) -> Any:
    import mlx.core as mx
    import mlx.nn as nn

    logits = model(inputs).astype(mx.float32)
    losses = nn.losses.cross_entropy(logits, targets, reduction="none")
    return mx.sum(losses * weights) / mx.sum(weights)


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
        "macro": {
            "precision": float(precision.mean()), "recall": float(recall.mean()),
            "f1": float(f1.mean()),
        },
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
            "empty_prediction_rate": float(np.mean(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
            "predicted_label_cardinality_median": float(np.median(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": float(f1.mean())},
    }


def select_checkpoint(history: Sequence[dict[str, Any]], delta: float) -> dict[str, Any]:
    maximum = max(float(row["macro_f1"]) for row in history)
    eligible = [row for row in history if maximum - float(row["macro_f1"]) < delta]
    selected = min(eligible, key=lambda row: int(row["epoch"]))
    return {
        "maximum_macro_f1": maximum,
        "practical_tie_delta": delta,
        "selected_epoch": int(selected["epoch"]),
        "selected_macro_f1": float(selected["macro_f1"]),
        "selection_deficit_from_maximum": maximum - float(selected["macro_f1"]),
        "eligible_epochs": [int(row["epoch"]) for row in eligible],
        "rule": "highest strict-parser validation six-label Macro-F1; within 0.005 choose earliest epoch",
    }


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6), where=denominator != 0)


def bootstrap_summary(
    gold: np.ndarray, predicted: np.ndarray, component_ids: Sequence[str], seed: int,
    replicates: int, namespace: str,
) -> dict[str, Any]:
    components = sorted(set(component_ids))
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    material = f"{namespace}|EXP-054|seed-{seed}|M4"
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
        "five_label_macro_f1_without_surprise": interval(
            values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())
        ),
        "per_label_f1": {
            label: interval(values[:, index], float(point[index]))
            for index, label in enumerate(LABELS)
        },
    }


def paired_bootstrap(
    gold: np.ndarray, m4_predicted: np.ndarray, m3_predicted: np.ndarray,
    component_ids: Sequence[str], seed: int, replicates: int, namespace: str,
) -> dict[str, Any]:
    components = sorted(set(component_ids))
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    material = f"{namespace}|EXP-054|seed-{seed}|M4-minus-M3-shared-threshold"
    rng_seed = int(hashlib.sha256(material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(rng_seed)
    values = np.zeros((replicates, 6))
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], m4_predicted[indices]) - fast_f1(gold[indices], m3_predicted[indices])
    point = fast_f1(gold, m4_predicted) - fast_f1(gold, m3_predicted)

    def interval(series: np.ndarray, value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(value), "lower": float(lower), "upper": float(upper)}

    without_surprise = [0, 1, 3, 4, 5]
    return {
        "comparison": f"EXP-054_M4_seed{seed}_minus_EXP-053_M3_seed{seed}_shared_threshold",
        "unit": "duplicate_component_id", "component_count": len(components),
        "row_count": len(component_ids), "replicates": replicates,
        "seed": rng_seed, "seed_material": material, "interval": "percentile_2.5_97.5",
        "macro_f1_delta": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_delta_without_surprise": interval(
            values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())
        ),
        "per_label_f1_delta": {
            label: interval(values[:, index], float(point[index]))
            for index, label in enumerate(LABELS)
        },
    }


def replay_subset(rows: Sequence[dict[str, Any]], size: int, namespace: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )[:size]


def preprocess_training_rows(
    tokenizer: Any, prompt: dict[str, Any], rows: Sequence[dict[str, Any]], limit: int,
    parser_module: Any, logger: logging.Logger | None = None,
) -> tuple[list[tuple[list[int], list[int], list[float]]], dict[str, Any]]:
    sequences: list[tuple[list[int], list[int], list[float]]] = []
    summaries: list[dict[str, Any]] = []
    stream = hashlib.sha256()
    for index, row in enumerate(rows):
        inputs, targets, weights, summary = m4_sequence(
            tokenizer, prompt, row, limit, parser_module
        )
        sequences.append((inputs, targets, weights))
        summaries.append(summary)
        stream.update((index + 1).to_bytes(8, "little"))
        for values, dtype in ((inputs, "<i4"), (targets, "<i4"), (weights, "<f4")):
            array = np.asarray(values, dtype=dtype)
            stream.update(len(array).to_bytes(4, "little"))
            stream.update(array.tobytes(order="C"))
        if logger and ((index + 1) % 500 == 0 or index + 1 == len(rows)):
            logger.info("Tokenized training rows %d/%d", index + 1, len(rows))
    return sequences, {
        "rows": len(rows),
        "token_id_and_mask_stream_sha256": stream.hexdigest(),
        "full_tokens": numeric_summary([row["full_tokens"] for row in summaries]),
        "prompt_tokens": numeric_summary([row["prompt_tokens"] for row in summaries]),
        "supervised_tokens": numeric_summary([row["supervised_tokens"] for row in summaries]),
        "total_supervised_tokens_per_epoch": sum(row["supervised_tokens"] for row in summaries),
        "truncated_rows": sum(row["truncated"] for row in summaries),
        "all_targets_canonical": all(
            row["canonical_target"].startswith('{"emotions":[') for row in summaries
        ),
    }


def preprocess_generation_rows(
    tokenizer: Any, prompt: dict[str, Any], rows: Sequence[dict[str, Any]], limit: int,
) -> tuple[list[list[int]], dict[str, Any]]:
    output: list[list[int]] = []
    raw_lengths: list[int] = []
    lengths: list[int] = []
    truncated = 0
    stream = hashlib.sha256()
    for index, row in enumerate(rows):
        ids, raw_length, was_truncated = prompt_ids(tokenizer, prompt, row["text"], limit)
        output.append(ids)
        raw_lengths.append(raw_length)
        lengths.append(len(ids))
        truncated += int(was_truncated)
        array = np.asarray(ids, dtype="<i4")
        stream.update((index + 1).to_bytes(8, "little"))
        stream.update(len(ids).to_bytes(4, "little"))
        stream.update(array.tobytes(order="C"))
    return output, {
        "rows": len(rows), "token_id_stream_sha256": stream.hexdigest(),
        "tokens": numeric_summary(lengths), "raw_tokens": numeric_summary(raw_lengths),
        "truncated_rows": truncated,
    }


def numeric_summary(values: Sequence[int | float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        raise ValueError("Cannot summarize an empty sequence")
    return {
        "minimum": float(array.min()), "maximum": float(array.max()),
        "mean": float(array.mean()), "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95, method="linear")),
        "total": float(array.sum()),
    }


def initialize_model(
    shared: dict[str, Any], config: dict[str, Any], seed: int,
) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    primitives = dynamic_module(
        f"exp054_primitives_seed_{seed}", require_record(config["implementation"]["primitives"])
    )
    sentinel = dynamic_module(
        f"exp054_sentinel_seed_{seed}", require_record(config["implementation"]["sentinel_helpers"])
    )
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    started = time.perf_counter()
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    load_seconds = time.perf_counter() - started
    model.freeze()
    model.eval()
    mx.random.seed(seed + 100000)
    linear_to_lora_layers(model, lora["num_layers"], {
        "rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"],
        "keys": lora["target_modules"],
    })
    observed = primitives.insertion_contract(model, shared)
    trainable = primitives.mlx_trainable(model)
    count = sum(int(tensor.size) for _, tensor in trainable)
    initial_digest = primitives.mlx_tensor_digest(trainable)
    expected = load_record(config["prerequisites"][f"m3_seed_{seed}"]["run"])["model"]["lora_initial_sha256"]
    if len(observed) != 112 or count != 7340032 or initial_digest != expected:
        raise ValueError(f"Seed {seed} matched LoRA initialization gate failed")
    base_sentinel = sentinel.frozen_parameter_sentinel(model)
    return {
        "model": model, "tokenizer": tokenizer, "primitives": primitives,
        "sentinel": sentinel, "model_load_seconds": load_seconds,
        "insertion_count": len(observed), "trainable_parameter_count": count,
        "lora_initial_sha256": initial_digest, "base_sentinel_before": base_sentinel,
    }


def save_adapter(path: Path, model: Any, primitives: Any) -> dict[str, Any]:
    import mlx.core as mx

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    mx.save_safetensors(str(path), dict(primitives.mlx_trainable(model)))
    os.chmod(path, 0o600)
    return artifact(path)


def generate_rows(
    model: Any, tokenizer: Any, prompt_token_ids: Sequence[list[int]],
    rows: Sequence[dict[str, Any]], parser_module: Any, max_new_tokens: int,
    logger: logging.Logger | None = None,
) -> tuple[list[dict[str, Any]], np.ndarray, dict[str, Any]]:
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    sampler = make_sampler(temp=0.0)
    predicted = np.zeros((len(rows), 6), dtype=np.uint8)
    outputs: list[dict[str, Any]] = []
    latencies: list[float] = []
    token_counts: list[int] = []
    parser_outcomes: Counter[str] = Counter()
    started = time.perf_counter()
    for index, (row, ids) in enumerate(zip(rows, prompt_token_ids)):
        row_started = time.perf_counter()
        raw = generate(
            model, tokenizer, prompt=ids, max_tokens=max_new_tokens,
            sampler=sampler, verbose=False,
        )
        latency = time.perf_counter() - row_started
        parsed = parser_module.parse_output(raw, LABELS)
        predicted[index] = np.asarray(parsed["vector"], dtype=np.uint8)
        generated_tokens = len(tokenizer.encode(raw, add_special_tokens=False))
        latencies.append(latency)
        token_counts.append(generated_tokens)
        parser_outcomes[parsed["error"] or "valid"] += 1
        outputs.append({
            "row_index": index, "sample_id": row["sample_id"],
            "component_id": row["component_id"], "gold": row["labels"],
            "raw_output": raw, "parsed": parsed,
            "generated_tokens_before_eos": generated_tokens,
            "generation_latency_seconds": latency,
        })
        if logger and ((index + 1) % 50 == 0 or index + 1 == len(rows)):
            logger.info("Validation generation %d/%d valid=%d", index + 1, len(rows), parser_outcomes["valid"])
    elapsed = time.perf_counter() - started
    valid_count = parser_outcomes["valid"]
    return outputs, predicted, {
        "rows": len(rows), "generation_seconds": elapsed,
        "throughput_rows_per_second": len(rows) / elapsed if elapsed else 0.0,
        "parser_valid_count": valid_count,
        "parser_valid_rate": valid_count / len(rows),
        "parser_outcome_counts": dict(sorted(parser_outcomes.items())),
        "generated_tokens": numeric_summary(token_counts),
        "latency_seconds": numeric_summary(latencies),
        "retries": 0, "temperature": 0.0, "max_new_tokens": max_new_tokens,
    }


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    sources = {
        "config": {
            "path": display_path(config_path), "bytes": config_path.stat().st_size,
            "sha256": sha256(config_path),
        },
        **config["implementation"],
        "shared_config": config["prerequisites"]["shared_config"],
    }
    frozen: dict[str, Any] = {}
    for name, record in sources.items():
        source = require_record(record)
        destination = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, destination)
        frozen[name] = artifact(destination)
    return frozen


def write_history(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = (
        "seed", "epoch", "optimizer_steps", "train_loss", "macro_precision",
        "macro_recall", "macro_f1", "micro_f1", "weighted_f1", "subset_accuracy",
        "hamming_loss", "five_label_macro_f1_without_surprise", "parser_valid_rate",
        "empty_prediction_rate", "predicted_label_cardinality_mean", "batch_order_sha256",
        "training_seconds", "validation_generation_seconds",
    )
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
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


def require_preflight_gate(config: dict[str, Any]) -> dict[str, Any]:
    public = resolve_project(config["execution"]["preflight_public_dir"])
    run_path = public / "run.json"
    verification_path = public / "verification.json"
    if not run_path.is_file() or not verification_path.is_file():
        raise RuntimeError("EXP-054 formal preflight is missing")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if run.get("status") != "Passed" or verification.get("status") != "Passed" or verification.get("failed_checks"):
        raise RuntimeError("EXP-054 formal preflight is not independently verified")
    if run.get("validation_split_accessed") or run.get("test_split_accessed"):
        raise PermissionError("EXP-054 preflight split gate drift")
    return {"run": artifact(run_path), "verification": artifact(verification_path)}


def require_prior_seed_gate(config: dict[str, Any], seed: int) -> dict[str, Any] | None:
    if seed == 42:
        return None
    previous = seed - 1
    path = resolve_project(
        config["execution"]["public_seed_dir_pattern"].format(seed=previous)
    ) / "verification.json"
    if not path.is_file():
        raise RuntimeError(f"EXP-054 seed {previous} verification is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "Passed" or value.get("failed_checks"):
        raise RuntimeError(f"EXP-054 seed {previous} did not pass verification")
    return artifact(path)


def run_preflight(config_path: Path) -> dict[str, Any]:
    config, shared = load_config(config_path)
    validate_prerequisites(config, shared)
    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("Architecture gate failed")
    public_dir = resolve_project(config["execution"]["preflight_public_dir"])
    private_dir = resolve_project(config["execution"]["preflight_private_dir"])
    for path in (public_dir, private_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite append-only preflight: {path}")
    public_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    logger = setup_logger(public_dir / "stdout.log", "exp-054-preflight")
    started_at, started = utc_now(), time.perf_counter()
    frozen_sources = freeze_sources(public_dir, config_path, config)
    train_rows = load_split(shared, "train")
    parser_module = dynamic_module(
        "exp054_preflight_parser", require_record(config["implementation"]["parser"])
    )
    namespace = config["execution"]["preflight_selection_namespace"]
    smoke_rows = sorted(
        train_rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )[:8]

    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm.tuner.trainer import grad_checkpoint

    mx.reset_peak_memory()
    initialized = initialize_model(shared, config, 42)
    model = initialized["model"]
    tokenizer = initialized["tokenizer"]
    prompt = load_prompt(shared)
    token_started = time.perf_counter()
    all_sequences, token_summary = preprocess_training_rows(
        tokenizer, prompt, train_rows, int(shared["prompt"]["max_sequence_length"]),
        parser_module, logger,
    )
    tokenization_seconds = time.perf_counter() - token_started
    smoke_index = {row["sample_id"]: index for index, row in enumerate(train_rows)}
    grad_checkpoint(model.layers[0])
    model.train()
    lora = shared["models"]["lora_shared"]
    optimizer = optim.AdamW(
        learning_rate=float(lora["learning_rate"]), weight_decay=float(lora["weight_decay"])
    )
    loss_and_grad = nn.value_and_grad(model, m4_loss)
    losses: list[float] = []
    supervised_counts: list[int] = []
    for row in smoke_rows[:2]:
        inputs, targets, weights = all_sequences[smoke_index[row["sample_id"]]]
        inputs_array = mx.array([inputs], dtype=mx.int32)
        targets_array = mx.array([targets], dtype=mx.int32)
        weights_array = mx.array([weights], dtype=mx.float32)
        loss, gradients = loss_and_grad(model, inputs_array, targets_array, weights_array)
        optimizer.update(model, gradients)
        mx.eval(loss, model.trainable_parameters(), optimizer.state)
        value = float(loss.item())
        if not math.isfinite(value):
            raise ValueError("Non-finite preflight M4 loss")
        losses.append(value)
        supervised_counts.append(int(sum(weights)))
    final_items = initialized["primitives"].mlx_trainable(model)
    final_digest = initialized["primitives"].mlx_tensor_digest(final_items)
    nonzero_b = sum(
        bool(mx.any(tensor != 0).item())
        for name, tensor in final_items if name.endswith("lora_b")
    )
    if final_digest == initialized["lora_initial_sha256"] or nonzero_b != 112:
        raise ValueError("Preflight LoRA update gate failed")
    adapter_path = private_dir / "preflight-adapters.safetensors"
    adapter_record = save_adapter(adapter_path, model, initialized["primitives"])
    del model, tokenizer, optimizer, loss_and_grad, all_sequences
    gc.collect()
    mx.clear_cache()

    reloaded = initialize_model(shared, config, 42)
    reloaded["model"].load_weights(str(adapter_path), strict=False)
    reloaded["model"].eval()
    if reloaded["primitives"].mlx_tensor_digest(
        reloaded["primitives"].mlx_trainable(reloaded["model"])
    ) != final_digest:
        raise ValueError("Preflight adapter reload digest mismatch")
    generation_ids, generation_token_summary = preprocess_generation_rows(
        reloaded["tokenizer"], prompt, smoke_rows[:4], int(shared["prompt"]["max_sequence_length"])
    )
    outputs, _, generation_summary = generate_rows(
        reloaded["model"], reloaded["tokenizer"], generation_ids, smoke_rows[:4],
        parser_module, int(shared["models"]["m4"]["generation"]["max_new_tokens"]), logger,
    )
    raw_path = private_dir / "preflight-generations.jsonl"
    atomic_jsonl(raw_path, outputs, private=True)
    peak_memory = float(mx.get_peak_memory()) / 1e9
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("EXP-054 preflight exceeded memory budget")
    run_record = {
        "schema_version": "exp-054-m4-preflight-run-v1",
        "experiment_id": EXPERIMENT_ID, "rq_id": "RQ-S1", "tier": "Minor",
        "stage": "formal-train-only-preflight", "status": "Passed",
        "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "invocation": " ".join(sys.argv), "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(), "environment": {
            "machine": platform.machine(), "platform": platform.platform(),
            "packages": package_versions(), "executable": sys.executable,
        },
        "authorization": {"splits": ["train"], "seed": 42, "optimizer_steps": 2},
        "accessed_splits": ["train"], "validation_split_accessed": False,
        "test_split_accessed": False, "performance_metrics_computed": False,
        "frozen_sources": frozen_sources,
        "data": {
            "train_sha256": shared["data"]["train_sha256"], "train_rows": len(train_rows),
            "smoke_rows": len(smoke_rows),
            "smoke_selection_digest_sha256": canonical_digest([row["sample_id"] for row in smoke_rows]),
            "identities_public": False,
        },
        "model": {
            "repo_id": shared["models"]["qwen_shared"]["repo_id"],
            "revision": shared["models"]["qwen_shared"]["revision"],
            "precision": shared["models"]["qwen_shared"]["precision"],
            "insertion_count": initialized["insertion_count"],
            "trainable_parameter_count": initialized["trainable_parameter_count"],
            "lora_initial_sha256": initialized["lora_initial_sha256"],
            "lora_final_sha256": final_digest,
            "nonzero_lora_b_tensors": nonzero_b,
        },
        "training": {
            "finite_losses": losses, "optimizer_steps": 2,
            "supervised_token_counts": supervised_counts,
            "prompt_loss_masked": True, "tokenization": token_summary,
        },
        "generation": generation_summary,
        "generation_tokenization": generation_token_summary,
        "resources": {
            "api_cost_usd": 0, "wall_seconds": time.perf_counter() - started,
            "model_load_seconds": initialized["model_load_seconds"] + reloaded["model_load_seconds"],
            "tokenization_seconds": tokenization_seconds,
            "peak_mlx_memory_gb": peak_memory,
        },
        "privacy": {
            "public_raw_text": False, "public_row_identifiers": False,
            "private_artifacts_gitignored": True,
        },
        "artifacts": {
            "stdout_log": artifact(public_dir / "stdout.log"),
            "adapter_private": adapter_record, "generation_private": artifact(raw_path),
        },
    }
    atomic_json(public_dir / "run.json", run_record)
    (public_dir / "REPORT.md").write_text(
        "\n".join([
            "# EXP-054 Formal Preflight", "", "- Status: `Passed`; independent verification pending",
            "- Accessed split: train only", "- Test accessed: no",
            f"- Full train sequences checked: `{len(train_rows)}`",
            f"- Finite optimizer updates: `{len(losses)}`",
            f"- Adapter reload: passed", f"- Peak MLX memory: `{peak_memory:.3f} GB`", "",
            "No validation metric was computed. This is an implementation gate only.", "",
        ]),
        encoding="utf-8",
    )
    del reloaded
    gc.collect()
    mx.clear_cache()
    return run_record


def run_train(config_path: Path, seed: int) -> dict[str, Any]:
    config, shared = load_config(config_path)
    validate_prerequisites(config, shared)
    if seed not in config["authorization"]["seeds"]:
        raise PermissionError(f"Seed {seed} is not authorized")
    if platform.machine() != config["execution"]["required_architecture"]:
        raise RuntimeError("Architecture gate failed")
    preflight_gate = require_preflight_gate(config)
    prior_seed_gate = require_prior_seed_gate(config, seed)
    run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
    private_dir = resolve_project(config["execution"]["private_seed_dir_pattern"].format(seed=seed))
    for path in (run_dir, private_dir):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite append-only output: {path}")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    logger = setup_logger(run_dir / "stdout.log", f"exp-054-seed-{seed}")
    started_at, started = utc_now(), time.perf_counter()
    frozen_sources = freeze_sources(run_dir, config_path, config)
    train_rows = load_split(shared, "train")
    validation_rows = load_split(shared, "validation")
    if {row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}:
        raise ValueError("Train/validation component overlap")
    if {row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}:
        raise ValueError("Train/validation sample overlap")
    parser_module = dynamic_module(
        f"exp054_train_parser_seed_{seed}", require_record(config["implementation"]["parser"])
    )

    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm.tuner.trainer import grad_checkpoint

    mx.reset_peak_memory()
    initialized = initialize_model(shared, config, seed)
    model = initialized["model"]
    tokenizer = initialized["tokenizer"]
    primitives = initialized["primitives"]
    prompt = load_prompt(shared)
    token_started = time.perf_counter()
    train_sequences, train_token_summary = preprocess_training_rows(
        tokenizer, prompt, train_rows, int(shared["prompt"]["max_sequence_length"]),
        parser_module, logger,
    )
    validation_ids, validation_token_summary = preprocess_generation_rows(
        tokenizer, prompt, validation_rows, int(shared["prompt"]["max_sequence_length"])
    )
    tokenization_seconds = time.perf_counter() - token_started
    validation_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    component_ids = [row["component_id"] for row in validation_rows]

    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    rng = np.random.default_rng(seed)
    batch_orders = np.stack([
        rng.permutation(len(train_rows)) for _ in range(int(spec["epochs"]))
    ]).astype(np.int32)
    batch_order_path = private_dir / "batch-orders.npy"
    np.save(batch_order_path, batch_orders, allow_pickle=False)
    os.chmod(batch_order_path, 0o600)

    grad_checkpoint(model.layers[0])
    model.train()
    optimizer = optim.AdamW(
        learning_rate=float(lora["learning_rate"]), weight_decay=float(lora["weight_decay"])
    )
    loss_and_grad = nn.value_and_grad(model, m4_loss)
    checkpoint_root = private_dir / "checkpoints"
    checkpoint_root.mkdir(mode=0o700)
    history: list[dict[str, Any]] = []
    epoch_metrics: dict[int, dict[str, Any]] = {}
    epoch_generation: dict[int, dict[str, Any]] = {}
    epoch_prediction_paths: dict[int, Path] = {}
    epoch_raw_paths: dict[int, Path] = {}
    checkpoint_records: dict[str, Any] = {}
    global_step = 0
    training_seconds = 0.0
    validation_generation_seconds = 0.0
    for epoch, order in enumerate(batch_orders, start=1):
        epoch_train_started = time.perf_counter()
        loss_sum = 0.0
        for position, row_index in enumerate(order, start=1):
            inputs, targets, weights = train_sequences[int(row_index)]
            input_array = mx.array([inputs], dtype=mx.int32)
            target_array = mx.array([targets], dtype=mx.int32)
            weight_array = mx.array([weights], dtype=mx.float32)
            loss, gradients = loss_and_grad(model, input_array, target_array, weight_array)
            optimizer.update(model, gradients)
            mx.eval(loss, model.trainable_parameters(), optimizer.state)
            value = float(loss.item())
            if not math.isfinite(value):
                raise ValueError(f"Non-finite loss at epoch {epoch}, position {position}")
            loss_sum += value
            global_step += 1
            if position % int(config["execution"]["log_every_steps"]) == 0 or position == len(order):
                logger.info(
                    "Epoch %d train %d/%d mean_loss=%.6f peak=%.3fGB",
                    epoch, position, len(order), loss_sum / position, float(mx.get_peak_memory()) / 1e9,
                )
            if float(mx.get_peak_memory()) / 1e9 > float(config["execution"]["maximum_peak_memory_gb"]):
                raise MemoryError("Formal M4 exceeded frozen MLX memory budget")
            if time.perf_counter() - epoch_train_started + training_seconds > float(config["execution"]["maximum_training_hours_per_seed"]) * 3600:
                raise TimeoutError("Formal M4 exceeded frozen training budget")
            if position % 250 == 0:
                mx.clear_cache()
        epoch_training_seconds = time.perf_counter() - epoch_train_started
        training_seconds += epoch_training_seconds
        checkpoint_path = checkpoint_root / f"epoch-{epoch}" / "adapters.safetensors"
        checkpoint_records[f"epoch-{epoch}"] = save_adapter(checkpoint_path, model, primitives)

        model.eval()
        outputs, predictions, generation_summary = generate_rows(
            model, tokenizer, validation_ids, validation_rows, parser_module,
            int(shared["models"]["m4"]["generation"]["max_new_tokens"]), logger,
        )
        validation_generation_seconds += generation_summary["generation_seconds"]
        if validation_generation_seconds > float(config["execution"]["maximum_validation_inference_hours_per_seed"]) * 3600:
            raise TimeoutError("Formal M4 exceeded frozen validation inference budget")
        metrics = metric_bundle(validation_gold, predictions)
        raw_path = private_dir / f"validation-generations-epoch-{epoch}.jsonl"
        prediction_path = private_dir / f"validation-predictions-epoch-{epoch}.npz"
        atomic_jsonl(raw_path, outputs, private=True)
        np.savez_compressed(
            prediction_path, predictions=predictions, gold=validation_gold,
            sample_ids=np.asarray([row["sample_id"] for row in validation_rows]),
            component_ids=np.asarray(component_ids),
            parser_valid=np.asarray([row["parsed"]["valid"] for row in outputs], dtype=np.uint8),
            generated_tokens=np.asarray([row["generated_tokens_before_eos"] for row in outputs], dtype=np.int16),
            latency_seconds=np.asarray([row["generation_latency_seconds"] for row in outputs], dtype=np.float64),
        )
        os.chmod(prediction_path, 0o600)
        epoch_metrics[epoch] = metrics
        epoch_generation[epoch] = generation_summary
        epoch_prediction_paths[epoch] = prediction_path
        epoch_raw_paths[epoch] = raw_path
        order_digest = canonical_digest([train_rows[int(index)]["sample_id"] for index in order])
        history.append({
            "seed": seed, "epoch": epoch, "optimizer_steps": global_step,
            "train_loss": loss_sum / len(order),
            "macro_precision": metrics["macro"]["precision"],
            "macro_recall": metrics["macro"]["recall"], "macro_f1": metrics["macro"]["f1"],
            "micro_f1": metrics["micro_f1"], "weighted_f1": metrics["weighted_f1"],
            "subset_accuracy": metrics["subset_accuracy"], "hamming_loss": metrics["hamming_loss"],
            "five_label_macro_f1_without_surprise": metrics["five_label_macro_f1_without_surprise"],
            "parser_valid_rate": generation_summary["parser_valid_rate"],
            "empty_prediction_rate": metrics["prediction_diagnostics"]["empty_prediction_rate"],
            "predicted_label_cardinality_mean": metrics["prediction_diagnostics"]["predicted_label_cardinality_mean"],
            "batch_order_sha256": order_digest, "training_seconds": epoch_training_seconds,
            "validation_generation_seconds": generation_summary["generation_seconds"],
        })
        logger.info(
            "Epoch %d complete train_loss=%.6f macro_f1=%.6f parser_valid=%.4f",
            epoch, loss_sum / len(order), metrics["macro"]["f1"], generation_summary["parser_valid_rate"],
        )
        model.train()

    if global_step != int(spec["total_iterations_per_seed"]) or len(history) != 2:
        raise ValueError("Formal M4 completion-count drift")
    selection = select_checkpoint(history, float(shared["evaluation"]["practical_tie_delta"]))
    selected_epoch = int(selection["selected_epoch"])
    selected_metrics = epoch_metrics[selected_epoch]
    selected_generation = epoch_generation[selected_epoch]
    selected_checkpoint_dir = private_dir / "selected-checkpoint"
    shutil.copytree(checkpoint_root / f"epoch-{selected_epoch}", selected_checkpoint_dir)
    selected_adapter = artifact(selected_checkpoint_dir / "adapters.safetensors")
    selected_predictions_path = private_dir / "selected-validation-predictions.npz"
    selected_raw_path = private_dir / "selected-validation-generations.jsonl"
    shutil.copy2(epoch_prediction_paths[selected_epoch], selected_predictions_path)
    shutil.copy2(epoch_raw_paths[selected_epoch], selected_raw_path)
    os.chmod(selected_predictions_path, 0o600)
    os.chmod(selected_raw_path, 0o600)

    with np.load(selected_predictions_path, allow_pickle=False) as selected_private:
        selected_predictions = np.asarray(selected_private["predictions"], dtype=np.uint8)
    replicates = int(shared["evaluation"]["bootstrap"]["replicates"])
    namespace = shared["evaluation"]["bootstrap"]["seed_namespace"]
    bootstrap = bootstrap_summary(
        validation_gold, selected_predictions, component_ids, seed, replicates, namespace
    )
    m3_run = load_record(config["prerequisites"][f"m3_seed_{seed}"]["run"])
    m3_predictions_path = require_record(m3_run["artifacts"]["validation_predictions_private"])
    with np.load(m3_predictions_path, allow_pickle=False) as m3_private:
        if m3_private["sample_ids"].tolist() != [row["sample_id"] for row in validation_rows]:
            raise ValueError("Matched M3 validation order drift")
        if not np.array_equal(m3_private["gold"], validation_gold):
            raise ValueError("Matched M3 gold drift")
        m3_predictions = np.asarray(m3_private["shared_threshold_predictions"], dtype=np.uint8)
    paired = paired_bootstrap(
        validation_gold, selected_predictions, m3_predictions, component_ids,
        seed, replicates, namespace,
    )
    paired["metric_deltas"] = {
        "macro_f1": selected_metrics["macro"]["f1"] - m3_run["metrics"]["shared_threshold"]["macro"]["f1"],
        "micro_f1": selected_metrics["micro_f1"] - m3_run["metrics"]["shared_threshold"]["micro_f1"],
        "weighted_f1": selected_metrics["weighted_f1"] - m3_run["metrics"]["shared_threshold"]["weighted_f1"],
        "subset_accuracy": selected_metrics["subset_accuracy"] - m3_run["metrics"]["shared_threshold"]["subset_accuracy"],
        "five_label_macro_f1_without_surprise": selected_metrics["five_label_macro_f1_without_surprise"] - m3_run["metrics"]["shared_threshold"]["five_label_macro_f1_without_surprise"],
    }

    final_items = primitives.mlx_trainable(model)
    lora_final = primitives.mlx_tensor_digest(final_items)
    nonzero_b = sum(
        bool(mx.any(tensor != 0).item())
        for name, tensor in final_items if name.endswith("lora_b")
    )
    base_after = initialized["sentinel"].frozen_parameter_sentinel(model)
    if lora_final == initialized["lora_initial_sha256"] or nonzero_b != 112:
        raise ValueError("Formal M4 LoRA did not update correctly")
    if base_after != initialized["base_sentinel_before"]:
        raise ValueError("Frozen base-model sentinel changed")

    private_manifest_path = private_dir / "private-manifest.json"
    atomic_json(private_manifest_path, {
        "experiment_id": EXPERIMENT_ID, "stage": "train-validation", "seed": seed,
        "contains_raw_text": False, "contains_row_identifiers": True,
        "batch_orders": artifact(batch_order_path), "checkpoints": checkpoint_records,
        "epoch_predictions": {
            f"epoch-{epoch}": artifact(epoch_prediction_paths[epoch]) for epoch in (1, 2)
        },
        "epoch_raw_generations": {
            f"epoch-{epoch}": artifact(epoch_raw_paths[epoch]) for epoch in (1, 2)
        },
        "selected_checkpoint": selected_adapter,
        "selected_predictions": artifact(selected_predictions_path),
        "selected_raw_generations": artifact(selected_raw_path),
    }, private=True)

    history_path = run_dir / "history.csv"
    metrics_path = run_dir / "metrics.json"
    parser_path = run_dir / "parser-and-generation.json"
    bootstrap_path = run_dir / "bootstrap.json"
    paired_path = run_dir / "paired-m4-minus-m3.json"
    selection_path = run_dir / "selection.json"
    per_label_path = run_dir / "per-label.csv"
    confusion_path = run_dir / "multilabel-confusion.csv"
    write_history(history_path, history)
    atomic_json(metrics_path, selected_metrics)
    atomic_json(parser_path, selected_generation)
    atomic_json(bootstrap_path, bootstrap)
    atomic_json(paired_path, paired)
    atomic_json(selection_path, selection)
    write_per_label(per_label_path, selected_metrics)
    write_confusion(confusion_path, selected_metrics)

    peak_memory = float(mx.get_peak_memory()) / 1e9
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_gb = peak_rss / 1e9 if platform.system() == "Darwin" else peak_rss * 1024 / 1e9
    wall_seconds = time.perf_counter() - started
    if training_seconds > float(config["execution"]["maximum_training_hours_per_seed"]) * 3600:
        raise TimeoutError("Formal M4 exceeded training budget")
    if validation_generation_seconds > float(config["execution"]["maximum_validation_inference_hours_per_seed"]) * 3600:
        raise TimeoutError("Formal M4 exceeded validation inference budget")
    if wall_seconds > float(config["execution"]["maximum_total_wall_hours_per_seed"]) * 3600:
        raise TimeoutError("Formal M4 exceeded per-seed wall budget")
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("Formal M4 exceeded memory budget")
    logger.info("Formal seed %d completed; two replay passes and verification are required", seed)
    run_record = {
        "schema_version": "exp-054-m4-seed-run-v1", "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S1", "tier": "Major", "stage": f"seed-{seed}-train-validation",
        "status": "Completed", "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "invocation": " ".join(sys.argv), "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(), "environment": {
            "machine": platform.machine(), "platform": platform.platform(),
            "packages": package_versions(), "executable": sys.executable,
        },
        "authorization": config["authorization"], "accessed_splits": ["train", "validation"],
        "validation_split_accessed": True, "test_split_accessed": False,
        "performance_metrics_computed": True, "formal_training_authorized": True,
        "frozen_sources": frozen_sources, "prerequisite_gates": {
            "exp_054_preflight": preflight_gate, "prior_seed_verification": prior_seed_gate,
            "matched_m3_run": config["prerequisites"][f"m3_seed_{seed}"]["run"],
            "matched_m3_verification": config["prerequisites"][f"m3_seed_{seed}"]["verification"],
        },
        "data": {
            "protocol_id": shared["data"]["protocol_id"], "labels": list(LABELS),
            "train": {
                "sha256": shared["data"]["train_sha256"], "summary": split_summary(train_rows),
                "tokenization": train_token_summary,
            },
            "validation": {
                "sha256": shared["data"]["validation_sha256"], "summary": split_summary(validation_rows),
                "tokenization": validation_token_summary,
            },
            "cross_split_component_overlap": 0, "cross_split_sample_overlap": 0,
            "test": {"status": "sealed_not_accessed", "rows": shared["data"]["test_rows"]},
        },
        "model": {
            "repo_id": spec["repo_id"], "revision": spec["revision"], "precision": spec["precision"],
            "formulation": "generative_label_only_json", "enable_thinking": False,
            "lora_initial_sha256": initialized["lora_initial_sha256"],
            "lora_final_sha256": lora_final, "insertion_count": initialized["insertion_count"],
            "trainable_parameter_count": initialized["trainable_parameter_count"],
            "nonzero_lora_b_tensors": nonzero_b,
            "base_parameter_sentinel_before": initialized["base_sentinel_before"],
            "base_parameter_sentinel_after": base_after,
        },
        "training": {
            "seed": seed, "epochs": int(spec["epochs"]), "batch_size": 1,
            "gradient_accumulation_steps": 1, "total_optimizer_steps": global_step,
            "loss": "assistant_only_next_token_cross_entropy", "prompt_loss_masked": True,
            "optimizer": {
                "name": "AdamW", "learning_rate": float(lora["learning_rate"]),
                "weight_decay": float(lora["weight_decay"]),
            },
            "gradient_checkpointing": True,
            "batch_order_rng": config["execution"]["batch_order_rng"], "history": history,
        },
        "selection": selection, "metrics": selected_metrics,
        "parser_and_generation": selected_generation,
        "bootstrap": bootstrap, "paired_m4_minus_m3": paired,
        "resources": {
            "api_cost_usd": 0, "wall_seconds": wall_seconds,
            "model_load_seconds": initialized["model_load_seconds"],
            "tokenization_seconds": tokenization_seconds, "training_seconds": training_seconds,
            "validation_generation_seconds": validation_generation_seconds,
            "peak_mlx_memory_gb": peak_memory, "peak_process_rss_gb": peak_rss_gb,
        },
        "privacy": {
            "public_raw_text": False, "public_row_identifiers": False,
            "private_artifacts_gitignored": True,
        },
        "warnings": [
            "M3-M4 jointly differ in head, loss, supervision tokens, and decoding.",
            "Validation selected the checkpoint; replay cannot alter the selection.",
            "Test remains sealed and no mechanism claim follows from classification performance.",
        ],
        "artifacts": {
            "history": artifact(history_path), "metrics": artifact(metrics_path),
            "parser_and_generation": artifact(parser_path), "bootstrap": artifact(bootstrap_path),
            "paired_m4_minus_m3": artifact(paired_path), "selection": artifact(selection_path),
            "per_label": artifact(per_label_path), "confusion": artifact(confusion_path),
            "stdout_log": artifact(run_dir / "stdout.log"),
            "private_manifest": artifact(private_manifest_path),
            "batch_orders_private": artifact(batch_order_path),
            "selected_adapter_private": selected_adapter,
            "selected_predictions_private": artifact(selected_predictions_path),
            "selected_raw_generations_private": artifact(selected_raw_path),
            "epoch_checkpoints_private": checkpoint_records,
        },
    }
    atomic_json(run_dir / "run.json", run_record)
    (run_dir / "REPORT.md").write_text(
        "\n".join([
            f"# EXP-054 M4 Generative LoRA Seed {seed}", "",
            "- Status: `Completed`; replay and independent verification pending",
            "- Accessed splits: train, validation", "- Test accessed: no",
            f"- Selected epoch: `{selected_epoch}`",
            f"- Macro-F1: `{selected_metrics['macro']['f1']:.6f}`",
            f"- Micro-F1: `{selected_metrics['micro_f1']:.6f}`",
            f"- Weighted-F1: `{selected_metrics['weighted_f1']:.6f}`",
            f"- Strict subset accuracy: `{selected_metrics['subset_accuracy']:.6f}`",
            f"- Parser-valid rate: `{selected_generation['parser_valid_rate']:.6f}`",
            f"- M4-M3 Macro-F1 delta: `{paired['metric_deltas']['macro_f1']:+.6f}`",
            f"- Peak MLX memory: `{peak_memory:.3f} GB`",
            f"- Wall time: `{wall_seconds / 3600:.3f} h`", "",
            "This is one validation seed. The test split remains sealed.", "",
        ]),
        encoding="utf-8",
    )
    del model, tokenizer, optimizer, loss_and_grad, train_sequences
    gc.collect()
    mx.clear_cache()
    return run_record


def run_replay(config_path: Path, seed: int, pass_index: int) -> dict[str, Any]:
    config, shared = load_config(config_path)
    validate_prerequisites(config, shared)
    if seed not in config["authorization"]["seeds"] or pass_index not in (1, 2):
        raise PermissionError("Replay seed/pass is not authorized")
    run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
    private_dir = resolve_project(config["execution"]["private_seed_dir_pattern"].format(seed=seed))
    run_path = run_dir / "run.json"
    if not run_path.is_file():
        raise RuntimeError("Formal train+validation run is missing")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("status") != "Completed" or run.get("test_split_accessed"):
        raise RuntimeError("Formal run is not replay-ready")
    public_path = run_dir / f"replay-pass-{pass_index}.json"
    private_path = private_dir / f"replay-pass-{pass_index}.jsonl"
    failure_path = run_dir / f"replay-failure-pass-{pass_index}.json"
    if public_path.exists() or private_path.exists() or failure_path.exists():
        raise FileExistsError("Refusing to overwrite append-only replay output")
    if pass_index == 2 and not (run_dir / "replay-pass-1.json").is_file():
        raise RuntimeError("Replay pass 1 must complete before pass 2")
    logger = setup_logger(
        run_dir / f"replay-pass-{pass_index}.log", f"exp-054-replay-{seed}-{pass_index}"
    )
    started_at, started = utc_now(), time.perf_counter()
    validation_rows = load_split(shared, "validation")
    namespace = config["execution"]["replay_selection_namespace"]
    subset = replay_subset(
        validation_rows, int(config["execution"]["replay_rows"]), namespace
    )
    subset_digest = canonical_digest([row["sample_id"] for row in subset])
    if subset_digest != config["execution"]["expected_replay_subset_digest_sha256"]:
        raise ValueError("Frozen replay subset digest drift")
    parser_module = dynamic_module(
        f"exp054_replay_parser_{seed}_{pass_index}", require_record(config["implementation"]["parser"])
    )

    import mlx.core as mx

    mx.reset_peak_memory()
    initialized = initialize_model(shared, config, seed)
    adapter_path = require_record(run["artifacts"]["selected_adapter_private"])
    initialized["model"].load_weights(str(adapter_path), strict=False)
    initialized["model"].eval()
    loaded_digest = initialized["primitives"].mlx_tensor_digest(
        initialized["primitives"].mlx_trainable(initialized["model"])
    )
    expected_digest = run["model"]["lora_final_sha256"]
    selected_checkpoint_digest = sha256(adapter_path)
    if loaded_digest != expected_digest:
        # The selected epoch can precede the final epoch. Compare against the serialized adapter.
        from safetensors import safe_open

        with safe_open(str(adapter_path), framework="numpy") as source:
            names = sorted(source.keys())
        if len(names) != 224:
            raise ValueError("Selected adapter tensor count drift")
    prompt = load_prompt(shared)
    prompt_token_ids, token_summary = preprocess_generation_rows(
        initialized["tokenizer"], prompt, subset, int(shared["prompt"]["max_sequence_length"])
    )
    outputs, predictions, generation_summary = generate_rows(
        initialized["model"], initialized["tokenizer"], prompt_token_ids, subset,
        parser_module, int(shared["models"]["m4"]["generation"]["max_new_tokens"]), logger,
    )
    atomic_jsonl(private_path, outputs, private=True)
    formal_raw_path = require_record(run["artifacts"]["selected_raw_generations_private"])
    formal_outputs = {
        row["sample_id"]: row
        for row in (
            json.loads(line) for line in formal_raw_path.read_text(encoding="utf-8").splitlines()
        )
    }
    formal_raw_matches = sum(
        output["raw_output"] == formal_outputs[output["sample_id"]]["raw_output"]
        for output in outputs
    )
    formal_vector_matches = sum(
        output["parsed"]["vector"] == formal_outputs[output["sample_id"]]["parsed"]["vector"]
        for output in outputs
    )
    cross_pass = None
    if pass_index == 2:
        pass_one_path = private_dir / "replay-pass-1.jsonl"
        pass_one = [json.loads(line) for line in pass_one_path.read_text(encoding="utf-8").splitlines()]
        cross_pass = {
            "rows": len(outputs),
            "sample_order_matches": [row["sample_id"] for row in pass_one] == [row["sample_id"] for row in outputs],
            "raw_output_matches": sum(a["raw_output"] == b["raw_output"] for a, b in zip(pass_one, outputs)),
            "parsed_vector_matches": sum(a["parsed"]["vector"] == b["parsed"]["vector"] for a, b in zip(pass_one, outputs)),
            "parser_validity_matches": sum(a["parsed"]["valid"] == b["parsed"]["valid"] for a, b in zip(pass_one, outputs)),
        }
    peak_memory = float(mx.get_peak_memory()) / 1e9
    if peak_memory > float(config["execution"]["maximum_peak_memory_gb"]):
        raise MemoryError("Replay exceeded memory budget")
    record = {
        "schema_version": "exp-054-m4-replay-pass-v1", "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S1", "tier": "Major", "stage": "selected-validation-replay",
        "status": "Completed", "seed": seed, "pass_index": pass_index,
        "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "invocation": " ".join(sys.argv), "fresh_process_required": True,
        "accessed_splits": ["validation"], "validation_split_accessed": True,
        "test_split_accessed": False, "checkpoint_selection_changed": False,
        "prompt_or_parser_changed": False, "retries": 0,
        "subset": {
            "namespace": namespace, "rows": len(subset),
            "selection_digest_sha256": subset_digest, "identities_public": False,
        },
        "model": {
            "selected_epoch": run["selection"]["selected_epoch"],
            "adapter_sha256": selected_checkpoint_digest,
            "loaded_trainable_sha256": loaded_digest,
        },
        "generation": generation_summary, "tokenization": token_summary,
        "agreement_with_formal_selected_validation": {
            "rows": len(outputs), "raw_output_matches": formal_raw_matches,
            "parsed_vector_matches": formal_vector_matches,
        },
        "agreement_with_pass_1": cross_pass,
        "prediction_digest_sha256": canonical_digest(predictions.tolist()),
        "resources": {
            "api_cost_usd": 0, "wall_seconds": time.perf_counter() - started,
            "model_load_seconds": initialized["model_load_seconds"],
            "peak_mlx_memory_gb": peak_memory,
        },
        "privacy": {
            "public_raw_text": False, "public_row_identifiers": False,
            "private_artifacts_gitignored": True,
        },
        "artifacts": {
            "private_generations": artifact(private_path),
            "stdout_log": artifact(run_dir / f"replay-pass-{pass_index}.log"),
        },
    }
    atomic_json(public_path, record)
    del initialized
    gc.collect()
    mx.clear_cache()
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", required=True, choices=("preflight", "train", "replay"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--pass-index", type=int)
    args = parser.parse_args()
    config_path = args.config.resolve()
    try:
        if args.mode == "preflight":
            if args.seed is not None or args.pass_index is not None:
                raise ValueError("Preflight does not accept seed/pass")
            result = run_preflight(config_path)
        elif args.mode == "train":
            if args.seed is None or args.pass_index is not None:
                raise ValueError("Train requires --seed only")
            result = run_train(config_path, args.seed)
        else:
            if args.seed is None or args.pass_index is None:
                raise ValueError("Replay requires --seed and --pass-index")
            result = run_replay(config_path, args.seed, args.pass_index)
    except Exception as exc:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if args.mode == "preflight":
                directory = resolve_project(config["execution"]["preflight_public_dir"])
                failure = directory / "attempt-failure.json"
            elif args.seed is not None:
                directory = resolve_project(
                    config["execution"]["public_seed_dir_pattern"].format(seed=args.seed)
                )
                suffix = f"-pass-{args.pass_index}" if args.mode == "replay" else ""
                failure = directory / f"attempt-failure-{args.mode}{suffix}.json"
            else:
                directory = Path()
                failure = Path()
            if directory.is_dir() and not failure.exists():
                atomic_json(failure, {
                    "schema_version": "exp-054-m4-failure-v1", "experiment_id": EXPERIMENT_ID,
                    "mode": args.mode, "seed": args.seed, "pass_index": args.pass_index,
                    "status": "Failed", "failed_at_utc": utc_now(),
                    "exception_type": type(exc).__name__, "error": str(exc),
                    "test_split_accessed": False,
                })
        except Exception:
            pass
        raise
    summary = {"status": result["status"], "stage": result["stage"]}
    if "seed" in result:
        summary["seed"] = result["seed"]
    if "metrics" in result:
        summary["macro_f1"] = result["metrics"]["macro"]["f1"]
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
