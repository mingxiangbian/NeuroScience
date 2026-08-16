#!/usr/bin/env python3
"""Attempt-2 independent verification for EXP-053 seed-42 Classification LoRA."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
from safetensors.numpy import load_file as load_safetensors


EXPERIMENT_ID = "EXP-053"
STAGE = "seed-42-train-validation"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
EXPECTED_FIELDS = {
    "component_id", "label_cardinality", "labels", "neutral",
    "protocol_id", "sample_id", "schema_version", "text",
}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-053-m3-seed-42.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-053-m3-classification-lora" / "seed-42"
DEFAULT_CORRECTION_CONFIG = SCRIPT_DIR / "configs" / "exp-053-m3-seed-42-verification-attempt-2.json"


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
        raise ValueError(f"Path escapes project root: {value}")
    return path


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_matches(record: dict[str, Any]) -> bool:
    path = resolve_project(record["path"])
    return path.is_file() and path.stat().st_size == int(record["bytes"]) and sha256(path) == record["sha256"]


def load_record(record: dict[str, Any]) -> dict[str, Any]:
    if not record_matches(record):
        raise ValueError(f"Artifact drift: {record['path']}")
    return json.loads(resolve_project(record["path"]).read_text(encoding="utf-8"))


def load_split(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise PermissionError(f"Unauthorized split: {split}")
    path = resolve_project(shared["data"][f"{split}_path"])
    if sha256(path) != shared["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != shared["data"][f"{split}_rows"]:
        raise ValueError(f"{split} row count drift")
    seen: set[str] = set()
    for row in rows:
        if set(row) != EXPECTED_FIELDS or row["protocol_id"] != shared["data"]["protocol_id"]:
            raise ValueError(f"{split} schema/protocol drift")
        if row["sample_id"] in seen:
            raise ValueError(f"{split} duplicate sample ID")
        seen.add(row["sample_id"])
        if len(row["labels"]) != 6 or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError(f"{split} label drift")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError(f"{split} derived-field drift")
    return rows


def load_prompt(shared: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project(shared["prompt"]["path"])
    if sha256(path) != shared["prompt"]["sha256"]:
        raise ValueError("Prompt hash drift")
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> list[int]:
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
            raise TypeError("Tokenizer output drift")
        return output

    full = apply(text)
    if len(full) <= limit:
        selected = full
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
    if not selected or len(selected) > limit:
        raise ValueError("Length contract failed")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Empty-think suffix drift")
    return selected


def mlx_items(module: Any) -> list[tuple[str, Any]]:
    from mlx.utils import tree_flatten
    return list(tree_flatten(module.trainable_parameters()))


def mlx_digest(items: Sequence[tuple[str, Any]]) -> str:
    import mlx.core as mx
    digest = hashlib.sha256()
    for name, tensor in sorted(items):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def array_digest(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name, array in sorted(arrays.items()):
        value = np.asarray(array, dtype=np.float32)
        digest.update(name.encode())
        digest.update(str(tuple(value.shape)).encode())
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def build_head(seed: int, hidden_size: int) -> Any:
    import mlx.core as mx
    import mlx.nn as nn
    mx.random.seed(seed)
    return nn.Linear(hidden_size, 6, bias=True)


def make_wrapper(backbone: Any, head: Any) -> Any:
    import mlx.nn as nn

    class Wrapper(nn.Module):
        def __init__(self, base: Any, linear: Any):
            super().__init__()
            self.backbone = base
            self.head = linear

        def __call__(self, input_ids: Any) -> Any:
            hidden = self.backbone.model(input_ids)
            return self.head(hidden[:, -1, :].astype(self.head.weight.dtype))

    return Wrapper(backbone, head)


def insertion_set(model: Any) -> list[tuple[int, str]]:
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    return sorted(observed)


def frozen_sentinel(model: Any) -> dict[str, Any]:
    import mlx.core as mx
    from mlx.utils import tree_flatten
    items = [(name, tensor) for name, tensor in tree_flatten(model.parameters()) if not name.endswith((".lora_a", ".lora_b"))]
    items.sort(key=lambda item: item[0])
    positions = sorted({round(index * (len(items) - 1) / 15) for index in range(16)})
    digest = hashlib.sha256()
    names: list[str] = []
    for position in positions:
        name, tensor = items[position]
        names.append(name)
        size = int(tensor.size)
        indices = sorted({0, size // 3, (2 * size) // 3, size - 1})
        sample = np.asarray(tensor.reshape(-1)[mx.array(indices)].astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(sample.tobytes(order="C"))
    return {"sha256": digest.hexdigest(), "tensor_names": names, "tensor_count": len(names)}


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
                "label_id": index, "precision": float(precision[index]), "recall": float(recall[index]),
                "f1": float(f1[index]), "support": int(support[index]), "predicted_support": int(tp[index] + fp[index]),
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
        "maximum_fixed_macro_f1": maximum, "practical_tie_delta": delta,
        "selected_epoch": int(selected["epoch"]), "selected_fixed_macro_f1": float(selected["fixed_macro_f1"]),
        "selection_deficit_from_maximum": maximum - float(selected["fixed_macro_f1"]),
        "eligible_epochs": [int(row["epoch"]) for row in eligible],
    }


def select_threshold(gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]) -> tuple[float, list[dict[str, float]]]:
    rows = [{"threshold": float(value), "macro_f1": metric_bundle(gold, (probabilities >= value).astype(np.uint8))["macro"]["f1"]} for value in grid]
    selected = min(rows, key=lambda row: (-row["macro_f1"], abs(row["threshold"] - 0.5), row["threshold"]))
    return selected["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6), where=denominator != 0)


def bootstrap(gold: np.ndarray, first: np.ndarray, component_ids: Sequence[str], seed: int, replicates: int, namespace: str, condition: str, second: np.ndarray | None = None) -> dict[str, Any]:
    components = sorted(set(component_ids))
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    prefix = "M3-minus-M2|" if second is not None else ""
    material = f"{namespace}|EXP-053|seed-{seed}|{prefix}{condition}"
    rng_seed = int(hashlib.sha256(material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(rng_seed)
    values = np.zeros((replicates, 6))
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], first[indices])
        if second is not None:
            values[replicate] -= fast_f1(gold[indices], second[indices])
    point = fast_f1(gold, first)
    if second is not None:
        point -= fast_f1(gold, second)

    def interval(series: np.ndarray, value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(value), "lower": float(lower), "upper": float(upper)}

    without_surprise = [0, 1, 3, 4, 5]
    if second is None:
        return {
            "unit": "duplicate_component_id", "component_count": len(components), "row_count": len(component_ids),
            "replicates": replicates, "seed": rng_seed, "seed_material": material, "interval": "percentile_2.5_97.5",
            "macro_f1": interval(values.mean(axis=1), float(point.mean())),
            "five_label_macro_f1_without_surprise": interval(values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())),
            "per_label_f1": {label: interval(values[:, index], float(point[index])) for index, label in enumerate(LABELS)},
        }
    return {
        "unit": "duplicate_component_id", "component_count": len(components), "row_count": len(component_ids),
        "replicates": replicates, "seed": rng_seed, "seed_material": material, "interval": "percentile_2.5_97.5",
        "macro_f1_delta": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_delta_without_surprise": interval(values[:, without_surprise].mean(axis=1), float(point[without_surprise].mean())),
        "per_label_f1_delta": {label: interval(values[:, index], float(point[index])) for index, label in enumerate(LABELS)},
    }


def close_json(first: Any, second: Any, tolerance: float = 1e-10) -> bool:
    if isinstance(first, dict) and isinstance(second, dict):
        return set(first) == set(second) and all(close_json(first[key], second[key], tolerance) for key in first)
    if isinstance(first, list) and isinstance(second, list):
        return len(first) == len(second) and all(close_json(a, b, tolerance) for a, b in zip(first, second))
    if isinstance(first, (float, int)) and isinstance(second, (float, int)) and not isinstance(first, bool) and not isinstance(second, bool):
        return math.isclose(float(first), float(second), rel_tol=tolerance, abs_tol=tolerance)
    return first == second


def passed_verification(result: dict[str, Any], expected_count: int) -> bool:
    return (
        result.get("status") == "Passed"
        and result.get("check_count") == expected_count
        and len(result.get("checks", [])) == expected_count
        and result.get("failed_checks") == []
    )


def parse_history(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    integer_fields = {"seed", "epoch", "optimizer_steps"}
    text_fields = {"batch_order_sha256"}
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            rows.append({key: (int(value) if key in integer_fields else value if key in text_fields else float(value)) for key, value in row.items()})
    return rows


def verify(correction_config_path: Path) -> dict[str, Any]:
    correction = json.loads(correction_config_path.read_text(encoding="utf-8"))
    if correction.get("experiment_id") != EXPERIMENT_ID or correction.get("verification_attempt") != 2:
        raise ValueError("Unexpected verification correction identity")
    for record in correction["records"].values():
        if not record_matches(record):
            raise ValueError(f"Correction input drift: {record['path']}")
    config_path = resolve_project(correction["records"]["formal_config"]["path"])
    run_path = resolve_project(correction["records"]["formal_run"]["path"])
    run_dir = run_path.parent
    verification_path = run_dir / correction["output_filename"]
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite append-only verification: {verification_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run = json.loads(run_path.read_text(encoding="utf-8"))
    prior_verification = load_record(correction["records"]["prior_verification"])
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("attempt_2_identity", correction.get("stage") == "seed-42-verification-attempt-2")
    check("correction_scope", correction.get("scope") == "verification-schema-only")
    for name, record in correction["records"].items():
        check(f"correction_{name}_hash", record_matches(record))
    check(
        "prior_attempt_retained_failed",
        prior_verification.get("status") == "Failed"
        and prior_verification.get("checks_passed") == 135
        and prior_verification.get("checks_total") == 136
        and prior_verification.get("failed_checks") == ["resource_verifier_102"],
    )
    check("prior_attempt_replay_exact", prior_verification.get("selected_checkpoint_probability_replay_max_abs_error") == 0.0)
    check("prior_attempt_test_sealed", prior_verification.get("test_split_accessed") is False)
    check("identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("stage") == STAGE)
    check("status_completed", run.get("status") == "Completed")
    check("authorized_seed", config["authorization"].get("seeds") == [42])
    check("authorized_splits", config["authorization"].get("splits") == ["train", "validation"])
    check("formal_authorized", config.get("formal_execution_authorized") is True and run.get("formal_training_authorized") is True)
    check("accessed_splits", run.get("accessed_splits") == ["train", "validation"])
    check("validation_accessed", run.get("validation_split_accessed") is True)
    check("test_sealed", run.get("test_split_accessed") is False and run["data"]["test"]["status"] == "sealed_not_accessed")
    check("later_seeds_sealed", config["authorization"].get("seeds_43_44_authorized") is False)
    check("exp054_sealed", config["authorization"].get("exp_054_authorized") is False)

    for name, record in config["implementation"].items():
        check(f"source_{name}_hash", record_matches(record))
    for group_name, group in config["prerequisites"].items():
        if isinstance(group, dict) and "path" in group:
            check(f"prerequisite_{group_name}_hash", record_matches(group))
        else:
            for name, record in group.items():
                check(f"prerequisite_{group_name}_{name}_hash", record_matches(record))
    for name, record in run["frozen_sources"].items():
        check(f"frozen_{name}_hash", record_matches(record))

    shared = load_record(config["prerequisites"]["shared_config"])
    resource_run = load_record(config["prerequisites"]["resource_preflight"]["run"])
    resource_verify = load_record(config["prerequisites"]["resource_preflight"]["verification"])
    m2_run = load_record(config["prerequisites"]["m2_seed_42"]["run"])
    m2_verify = load_record(config["prerequisites"]["m2_seed_42"]["verification"])
    aggregate_verify = load_record(config["prerequisites"]["m2_aggregate"]["verification"])
    check("resource_preflight_passed", resource_run.get("status") == "Passed")
    check("resource_verifier_102", passed_verification(resource_verify, 102))
    check("m2_seed42_verified_70", passed_verification(m2_verify, 70))
    check("m2_aggregate_verified_85", passed_verification(aggregate_verify, 85))
    check("shared_test_sealed", shared["data"]["test_status"] == "sealed_not_authorized_for_model_access")

    train_rows = load_split(shared, "train")
    validation_rows = load_split(shared, "validation")
    check("train_rows", len(train_rows) == 3360)
    check("validation_rows", len(validation_rows) == 720)
    check("sample_disjoint", not ({row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}))
    check("component_disjoint", not ({row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}))
    check("train_hash_recorded", run["data"]["train"]["sha256"] == shared["data"]["train_sha256"])
    check("validation_hash_recorded", run["data"]["validation"]["sha256"] == shared["data"]["validation_sha256"])

    history_path = resolve_project(run["artifacts"]["history"]["path"])
    check("history_hash", record_matches(run["artifacts"]["history"]))
    history = parse_history(history_path)
    check("history_two_epochs", [row["epoch"] for row in history] == [1, 2])
    check("history_steps", [row["optimizer_steps"] for row in history] == [3360, 6720])
    check("history_finite", all(math.isfinite(value) for row in history for key, value in row.items() if key not in {"batch_order_sha256"} and isinstance(value, float)))
    rng = np.random.default_rng(42)
    orders = np.stack([rng.permutation(len(train_rows)) for _ in range(2)]).astype(np.int32)
    expected_order_digests = [canonical_digest([train_rows[int(index)]["sample_id"] for index in order]) for order in orders]
    check("batch_order_digests", [row["batch_order_sha256"] for row in history] == expected_order_digests)
    batch_record = run["artifacts"]["batch_orders_private"]
    check("batch_order_artifact_hash", record_matches(batch_record))
    saved_orders = np.load(resolve_project(batch_record["path"]), allow_pickle=False)
    check("batch_order_artifact_values", np.array_equal(saved_orders, orders))

    for name in ("metrics_fixed", "metrics_shared_threshold", "bootstrap", "paired_m3_minus_m2", "selection", "threshold_grid"):
        check(f"artifact_{name}_hash", record_matches(run["artifacts"][name]))
    for table_name, table in run["artifacts"]["tables"].items():
        for artifact_name, record in table.items():
            check(f"table_{table_name}_{artifact_name}_hash", record_matches(record))
    check("stdout_hash", record_matches(run["artifacts"]["stdout_log"]))
    check("private_manifest_hash", record_matches(run["artifacts"]["private_manifest"]))
    predictions_record = run["artifacts"]["validation_predictions_private"]
    check("predictions_hash", record_matches(predictions_record))
    predictions_path = resolve_project(predictions_record["path"])
    check("predictions_gitignored", subprocess.run(["git", "check-ignore", "-q", str(predictions_path)], cwd=REPO_ROOT).returncode == 0)
    check("private_manifest_gitignored", subprocess.run(["git", "check-ignore", "-q", str(resolve_project(run["artifacts"]["private_manifest"]["path"]))], cwd=REPO_ROOT).returncode == 0)

    with np.load(predictions_path, allow_pickle=False) as private:
        probabilities = np.asarray(private["probabilities"], dtype=np.float32)
        gold = np.asarray(private["gold"], dtype=np.uint8)
        fixed_predictions = np.asarray(private["fixed_predictions"], dtype=np.uint8)
        shared_predictions = np.asarray(private["shared_threshold_predictions"], dtype=np.uint8)
        sample_ids = private["sample_ids"].tolist()
        component_ids = private["component_ids"].tolist()
    check("probability_shape", probabilities.shape == (2, 720, 6))
    check("probabilities_finite", np.isfinite(probabilities).all())
    check("probabilities_bounded", bool(np.all((probabilities >= 0) & (probabilities <= 1))))
    check("gold_shape", gold.shape == (720, 6))
    check("gold_values", set(np.unique(gold)).issubset({0, 1}))
    check("gold_matches_data", np.array_equal(gold, np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)))
    check("sample_order", sample_ids == [row["sample_id"] for row in validation_rows])
    check("component_order", component_ids == [row["component_id"] for row in validation_rows])

    selection = select_checkpoint(history, float(shared["evaluation"]["practical_tie_delta"]))
    check("selection_recomputed", close_json(selection, run["selection"]))
    check("selection_artifact", close_json(selection, json.loads(resolve_project(run["artifacts"]["selection"]["path"]).read_text(encoding="utf-8"))))
    selected_probabilities = probabilities[int(selection["selected_epoch"]) - 1]
    selected_threshold, threshold_rows = select_threshold(gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"])
    check("threshold_recomputed", math.isclose(selected_threshold, run["threshold_selection"]["selected_threshold"], abs_tol=1e-12))
    with resolve_project(run["artifacts"]["threshold_grid"]["path"]).open(encoding="utf-8", newline="") as source:
        stored_threshold_rows = [{"threshold": float(row["threshold"]), "macro_f1": float(row["macro_f1"])} for row in csv.DictReader(source)]
    check("threshold_grid_recomputed", close_json(threshold_rows, stored_threshold_rows))
    expected_fixed = (selected_probabilities >= 0.5).astype(np.uint8)
    expected_shared = (selected_probabilities >= selected_threshold).astype(np.uint8)
    check("fixed_predictions", np.array_equal(fixed_predictions, expected_fixed))
    check("shared_predictions", np.array_equal(shared_predictions, expected_shared))
    fixed_metrics = metric_bundle(gold, expected_fixed)
    shared_metrics = metric_bundle(gold, expected_shared)
    check("fixed_metrics_recomputed", close_json(fixed_metrics, run["metrics"]["fixed_0.5"]))
    check("shared_metrics_recomputed", close_json(shared_metrics, run["metrics"]["shared_threshold"]))
    check("fixed_metrics_artifact", close_json(fixed_metrics, json.loads(resolve_project(run["artifacts"]["metrics_fixed"]["path"]).read_text(encoding="utf-8"))))
    check("shared_metrics_artifact", close_json(shared_metrics, json.loads(resolve_project(run["artifacts"]["metrics_shared_threshold"]["path"]).read_text(encoding="utf-8"))))

    replicates = int(shared["evaluation"]["bootstrap"]["replicates"])
    namespace = shared["evaluation"]["bootstrap"]["seed_namespace"]
    recomputed_bootstrap = {
        "fixed_0.5": bootstrap(gold, expected_fixed, component_ids, 42, replicates, namespace, "fixed-0.5"),
        "shared_threshold": bootstrap(gold, expected_shared, component_ids, 42, replicates, namespace, f"shared-{selected_threshold:.2f}"),
    }
    check("bootstrap_recomputed", close_json(recomputed_bootstrap, run["bootstrap"]))
    check("bootstrap_artifact", close_json(recomputed_bootstrap, json.loads(resolve_project(run["artifacts"]["bootstrap"]["path"]).read_text(encoding="utf-8"))))

    m2_predictions_record = m2_run["artifacts"]["validation_predictions_private"]
    check("m2_predictions_hash", record_matches(m2_predictions_record))
    with np.load(resolve_project(m2_predictions_record["path"]), allow_pickle=False) as m2_private:
        check("m2_sample_order", m2_private["sample_ids"].tolist() == sample_ids)
        check("m2_gold", np.array_equal(m2_private["gold"], gold))
        m2_fixed = np.asarray(m2_private["fixed_predictions"], dtype=np.uint8)
        m2_shared = np.asarray(m2_private["shared_threshold_predictions"], dtype=np.uint8)
    paired = {
        "comparison": "EXP-053_M3_seed42_minus_EXP-052_M2_seed42",
        "fixed_0.5": bootstrap(gold, expected_fixed, component_ids, 42, replicates, namespace, "fixed-0.5", m2_fixed),
        "shared_threshold": bootstrap(gold, expected_shared, component_ids, 42, replicates, namespace, f"M3-{selected_threshold:.2f}_M2-{m2_run['threshold_selection']['selected_threshold']:.2f}", m2_shared),
        "metric_deltas": {
            "fixed_macro_f1": fixed_metrics["macro"]["f1"] - m2_run["metrics"]["fixed_0.5"]["macro"]["f1"],
            "shared_macro_f1": shared_metrics["macro"]["f1"] - m2_run["metrics"]["shared_threshold"]["macro"]["f1"],
            "fixed_micro_f1": fixed_metrics["micro_f1"] - m2_run["metrics"]["fixed_0.5"]["micro_f1"],
            "shared_micro_f1": shared_metrics["micro_f1"] - m2_run["metrics"]["shared_threshold"]["micro_f1"],
            "fixed_subset_accuracy": fixed_metrics["subset_accuracy"] - m2_run["metrics"]["fixed_0.5"]["subset_accuracy"],
            "shared_subset_accuracy": shared_metrics["subset_accuracy"] - m2_run["metrics"]["shared_threshold"]["subset_accuracy"],
        },
    }
    check("paired_comparison_recomputed", close_json(paired, run["paired_m3_minus_m2"]))
    check("paired_artifact", close_json(paired, json.loads(resolve_project(run["artifacts"]["paired_m3_minus_m2"]["path"]).read_text(encoding="utf-8"))))

    selected_adapter = run["artifacts"]["selected_checkpoint_private"]["adapter"]
    selected_head = run["artifacts"]["selected_checkpoint_private"]["head"]
    check("selected_adapter_hash", record_matches(selected_adapter))
    check("selected_head_hash", record_matches(selected_head))
    for epoch_name, records in run["artifacts"]["epoch_checkpoints_private"].items():
        for kind, record in records.items():
            check(f"checkpoint_{epoch_name}_{kind}_hash", record_matches(record))
            check(f"checkpoint_{epoch_name}_{kind}_gitignored", subprocess.run(["git", "check-ignore", "-q", str(resolve_project(record["path"]))], cwd=REPO_ROOT).returncode == 0)
    adapter_arrays = load_safetensors(str(resolve_project(selected_adapter["path"])))
    head_arrays = load_safetensors(str(resolve_project(selected_head["path"])))
    check("adapter_tensor_count", len(adapter_arrays) == 224)
    check("adapter_lora_a_count", sum(name.endswith("lora_a") for name in adapter_arrays) == 112)
    check("adapter_lora_b_count", sum(name.endswith("lora_b") for name in adapter_arrays) == 112)
    check("adapter_parameter_count", sum(array.size for array in adapter_arrays.values()) == 7340032)
    check("adapter_lora_b_nonzero", all(np.any(value != 0) for name, value in adapter_arrays.items() if name.endswith("lora_b")))
    check("head_tensor_names", set(head_arrays) == {"weight", "bias"})
    check("head_shapes", head_arrays["weight"].shape == (6, 2560) and head_arrays["bias"].shape == (6,))
    final_epoch_adapter = load_safetensors(str(resolve_project(run["artifacts"]["epoch_checkpoints_private"]["epoch-2"]["adapter"]["path"])))
    final_epoch_head = load_safetensors(str(resolve_project(run["artifacts"]["epoch_checkpoints_private"]["epoch-2"]["head"]["path"])))
    check("final_lora_digest", array_digest(final_epoch_adapter) == run["model"]["lora_final_sha256"])
    check("final_head_digest", array_digest(final_epoch_head) == run["model"]["head_final_sha256"])

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model.freeze()
    head = build_head(42, int(spec["hidden_size"]))
    check("head_initial_digest", mlx_digest(mlx_items(head)) == run["model"]["head_initial_sha256"])
    wrapper = make_wrapper(model, head)
    first_ids = mx.array([prompt_ids(tokenizer, load_prompt(shared), train_rows[0]["text"], int(shared["prompt"]["max_sequence_length"]))], dtype=mx.int32)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)
    mx.random.seed(42 + 100000)
    linear_to_lora_layers(model, lora["num_layers"], {"rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"], "keys": lora["target_modules"]})
    expected_insertions = sorted((block, target) for block in lora["adapted_block_indices"] for target in lora["target_modules"])
    check("insertion_set", insertion_set(model) == expected_insertions)
    check("initial_lora_digest", mlx_digest(mlx_items(model)) == run["model"]["lora_initial_sha256"])
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_delta = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    check("zero_step_delta", zero_delta == 0.0 == run["model"]["zero_step_max_abs_logit_difference"])
    sentinel_before = frozen_sentinel(model)
    model.load_weights(str(resolve_project(selected_adapter["path"])), strict=False)
    head.load_weights(str(resolve_project(selected_head["path"])), strict=True)
    model.eval()
    check("base_sentinel_after_load", frozen_sentinel(model) == sentinel_before == run["model"]["base_parameter_sentinel_before"])
    check("selected_adapter_loaded", mlx_digest(mlx_items(model)) == array_digest(adapter_arrays))
    check("selected_head_loaded", mlx_digest(mlx_items(head)) == array_digest(head_arrays))

    prompt = load_prompt(shared)
    replay = np.empty((len(validation_rows), 6), dtype=np.float32)
    for index, row in enumerate(validation_rows):
        ids = prompt_ids(tokenizer, prompt, row["text"], int(shared["prompt"]["max_sequence_length"]))
        logits = wrapper(mx.array([ids], dtype=mx.int32)).astype(mx.float32)
        mx.eval(logits)
        replay[index] = sigmoid(np.asarray(logits))[0]
        if (index + 1) % 100 == 0:
            mx.clear_cache()
    replay_error = float(np.max(np.abs(replay - selected_probabilities)))
    check("selected_checkpoint_probability_replay", replay_error <= float(config["execution"]["maximum_replay_probability_difference"]), replay_error)
    replay_fixed = metric_bundle(gold, (replay >= 0.5).astype(np.uint8))
    replay_shared = metric_bundle(gold, (replay >= selected_threshold).astype(np.uint8))
    check("replay_fixed_metrics", close_json(replay_fixed, fixed_metrics, tolerance=1e-7))
    check("replay_shared_metrics", close_json(replay_shared, shared_metrics, tolerance=1e-7))

    check("optimizer_steps", run["training"]["total_optimizer_steps"] == 6720)
    check("separate_optimizers", run["training"]["separate_optimizers"] is True)
    check("head_optimizer", run["training"]["head_optimizer"] == {"name": "AdamW", "learning_rate": 0.0001, "weight_decay": 0.01})
    check("lora_optimizer", run["training"]["lora_optimizer"] == {"name": "AdamW", "learning_rate": 0.00001, "weight_decay": 0.01})
    check("gradient_checkpointing", run["training"]["gradient_checkpointing"] is True)
    check("head_updated", run["model"]["head_initial_sha256"] != run["model"]["head_final_sha256"])
    check("lora_updated", run["model"]["lora_initial_sha256"] != run["model"]["lora_final_sha256"])
    check("all_lora_b_updated", run["model"]["nonzero_lora_b_tensors"] == 112)
    check("base_sentinel_unchanged", run["model"]["base_parameter_sentinel_before"] == run["model"]["base_parameter_sentinel_after"])
    check("memory_gate", run["resources"]["peak_mlx_memory_gb"] <= float(config["execution"]["maximum_peak_memory_gb"]))
    check("wall_time_gate", run["resources"]["wall_seconds"] <= float(config["execution"]["maximum_total_wall_hours"]) * 3600)
    check("no_api_cost", run["resources"]["api_cost_usd"] == 0)
    check("no_public_raw_text", run["privacy"]["public_raw_text"] is False)
    check("no_public_row_ids", run["privacy"]["public_row_identifiers"] is False)

    del model, tokenizer, head, wrapper, base_logits, converted_logits, first_ids
    gc.collect()
    mx.clear_cache()

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema_version": "exp-053-m3-seed-verification-v1", "experiment_id": EXPERIMENT_ID,
        "stage": STAGE, "verification_attempt": 2,
        "correction_stage": correction["stage"], "verified_at_utc": utc_now(),
        "status": "Passed" if not failed else "Failed",
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks),
        "failed_checks": failed, "checks": checks,
        "selected_checkpoint_probability_replay_max_abs_error": replay_error,
        "validation_split_accessed": True, "test_split_accessed": False,
        "performance_metrics_recomputed": True,
        "correction_config_sha256": sha256(correction_config_path),
        "prior_failed_verification": correction["records"]["prior_verification"],
    }
    write_json(verification_path, result)
    summary = "\n".join([
        "# EXP-053 Seed-42 Verification Attempt 2", "",
        f"- Status: `{result['status']}`", f"- Checks: `{result['checks_passed']}/{result['checks_total']}`",
        f"- Selected checkpoint probability replay max abs error: `{replay_error:.8g}`",
        f"- Shared-threshold Macro-F1: `{shared_metrics['macro']['f1']:.6f}`",
        f"- M3-M2 shared-threshold Macro-F1 delta: `{paired['metric_deltas']['shared_macro_f1']:+.6f}`",
        "- Test accessed: no", "",
        "Attempt 1 remains append-only as Failed (135/136) because it read an obsolete resource-verifier field.",
        "This attempt applies only the registered schema correction and repeats the full independent replay.", "",
        "This verification covers one seed only. Seeds 43/44, EXP-054 and test remain sealed.", "",
    ])
    (run_dir / correction["summary_filename"]).write_text(summary, encoding="utf-8")
    if failed:
        raise RuntimeError(f"EXP-053 verification failed: {failed}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correction-config", type=Path, default=DEFAULT_CORRECTION_CONFIG)
    args = parser.parse_args()
    result = verify(args.correction_config.resolve())
    print(json.dumps({"status": result["status"], "checks": result["checks_total"], "failed": result["failed_checks"]}, sort_keys=True))


if __name__ == "__main__":
    main()
