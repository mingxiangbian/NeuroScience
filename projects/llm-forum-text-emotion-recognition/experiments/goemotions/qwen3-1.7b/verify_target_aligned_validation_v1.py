#!/usr/bin/env python3
"""Independently verify EXP-033 seed-42 validation-only artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Iterable

import numpy as np


EVALUATION_ID = "EXP-033-SEED42-VALIDATION-V1"
VERIFICATION_ID = "EXP-033-SEED42-VALIDATION-VERIFY-V1"
EXPERIMENT_ID = "EXP-033"
STAGE = "seed-42-validation-only"
CONDITION = "aligned-prompt-open-neutral"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
EXPECTED_SLICES = (
    "all",
    "single_label",
    "multi_label",
    "high_cardinality",
    "neutral_only",
    "neutral_cooccurrence",
    "any_neutral",
    "without_neutral",
)
EXPECTED_IMPLEMENTATION_PATHS = {
    "constraint": SCRIPT_DIR / "label_json_constraint_neutral_cooccurrence.py",
    "constraint_base": SCRIPT_DIR / "label_json_constraint.py",
    "generation_helper": SCRIPT_DIR / "run_lora.py",
    "metrics": SCRIPT_DIR / "llm_full_dev_metrics.py",
    "protocol": SCRIPT_DIR / "protocols" / "exp-033-seed42-validation-v1.md",
    "runner": SCRIPT_DIR / "run_target_aligned_validation_v1.py",
    "verifier": SCRIPT_DIR / "verify_target_aligned_validation_v1.py",
}
EXPECTED_DEV_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "dev.tsv"
EXPECTED_LABELS_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt"
EXPECTED_TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
EXPECTED_PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-031-neutral-cooccurrence-v1.json"
EXPECTED_REFERENCE_PATHS = {
    "exp025": SCRIPT_DIR
    / "runs"
    / "exp-025-full-dev-zero-few-shot"
    / "few-shot-synthetic-3"
    / "predictions.csv",
    "exp029": SCRIPT_DIR
    / "runs"
    / "exp-031-neutral-ontology-inference-ablation"
    / "seed-42"
    / "analysis"
    / "aligned-prompt-open-decoder"
    / "predictions.csv",
}
EXPECTED_RUN_DIR = (
    SCRIPT_DIR
    / "runs"
    / "exp-033-target-aligned-lora"
    / "validation-seed-42-v1"
)
EXPECTED_PRIVATE_ROOT = (
    SCRIPT_DIR / "private-cache" / "exp-033-target-aligned-validation" / "seed-42"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def absolute_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"bytes": path.stat().st_size, "path": str(path), "sha256": sha256_file(path)}


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    observed = artifact(resolve_project_path(str(spec["path"])))
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {spec['path']}")
    if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact size drift: {spec['path']}")
    return observed


def require_nested_close(actual: Any, expected: Any, context: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"{context} object keys differ")
        for key in expected:
            require_nested_close(actual[key], expected[key], f"{context}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{context} list shape differs")
        for index, value in enumerate(expected):
            require_nested_close(actual[index], value, f"{context}[{index}]")
        return
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-12, abs_tol=1e-15
        ):
            raise ValueError(f"{context} differs: {actual} != {expected}")
        return
    if actual != expected:
        raise ValueError(f"{context} differs: {actual} != {expected}")


def source_tree_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    if not root.is_dir():
        raise FileNotFoundError(root)
    paths = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
    aggregate = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest = sha256_file(path).encode("ascii")
        aggregate.update(
            relative
            + bytes([0])
            + str(size).encode("ascii")
            + bytes([0])
            + digest
            + bytes([10])
        )
        total_bytes += size
    observed = {
        "file_count": len(paths),
        "manifest_sha256": aggregate.hexdigest(),
        "total_bytes": total_bytes,
    }
    expected = {
        "file_count": int(spec["file_count"]),
        "manifest_sha256": spec["manifest_sha256"],
        "total_bytes": int(spec["total_bytes"]),
    }
    if observed != expected:
        raise ValueError(f"MLX-LM source tree drift: {observed}")
    return observed


def verify_environment(contract: dict[str, Any]) -> dict[str, Any]:
    runtime = contract["runtime"]
    python = Path(runtime["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError(f"Use the frozen Python executable: {python}")
    packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in runtime["packages"]
    }
    if packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {packages}")
    semantics: dict[str, Any] = {}
    for name, spec in runtime["semantics_sources"].items():
        path = Path(spec["path"])
        observed = absolute_artifact(path)
        if observed["sha256"] != spec["sha256"]:
            raise ValueError(f"Runtime semantics source drift: {path}")
        if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
            raise ValueError(f"Runtime semantics source size drift: {path}")
        semantics[name] = observed
    return {
        "mlx_lm_source_tree": source_tree_manifest(runtime["mlx_lm_source_tree"]),
        "packages": packages,
        "python_executable": str(python),
        "semantics_sources": semantics,
    }


def verify_model(contract: dict[str, Any]) -> dict[str, Any]:
    model = contract["model"]
    manifest_path = resolve_project_path(model["manifest"]["path"])
    observed_manifest = verify_spec(model["manifest"])
    manifest = load_json(manifest_path)
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity differs from the frozen contract")
    model_root = resolve_project_path(model["local_path"])
    count = 0
    total = 0
    for expected in manifest["mlx_bf16"]["files"]:
        relative = Path(expected["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe model-manifest path")
        path = model_root / relative
        observed = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if observed != expected:
            raise ValueError(f"Model file drift: {path}")
        count += 1
        total += observed["bytes"]
    inventory = manifest["mlx_bf16"]
    if count != int(inventory["file_count"]) or total != int(inventory["total_bytes"]):
        raise ValueError("Model inventory totals differ")
    return {"file_count": count, "manifest": observed_manifest, "total_bytes": total}


def validate_contract(
    contract_path: Path, expected_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = contract_path.resolve()
    if not contract_path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Validation contract must be project-local")
    if sha256_file(contract_path) != expected_sha256:
        raise ValueError("Validation contract SHA-256 mismatch")
    contract = load_json(contract_path)
    scope = contract.get("scope", {})
    decoding = contract.get("decoding", {})
    bootstrap = contract.get("bootstrap", {})
    resources = contract.get("resource_budget", {})
    comparisons = contract.get("comparisons", {})
    if (
        contract.get("contract_id") != EVALUATION_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != STAGE
        or contract.get("status") != "Frozen"
        or contract.get("seed") != 42
        or scope != {
            "dev_rows": 5426,
            "final_adapter_only": True,
            "split": "dev",
            "test_access": False,
        }
        or decoding != {
            "condition": CONDITION,
            "enable_thinking": False,
            "generation_per_sample": 1,
            "invalid_prediction": "empty",
            "max_new_tokens": 64,
            "repair": False,
            "retry": False,
            "sampler": "greedy",
            "temperature": 0.0,
        }
        or bootstrap.get("replicates") != 10000
        or bootstrap.get("seed") != 20260803
        or bootstrap.get("batch_size") != 100
        or bootstrap.get("resampling_unit") != "dev-row"
        or float(bootstrap.get("practical_threshold", -1)) != 0.005
        or float(resources.get("active_wall_time_hours_max", -1)) != 4.0
        or float(resources.get("peak_mlx_memory_gb_max", -1)) != 14.0
        or float(resources.get("api_cost_usd_max", -1)) != 0.0
        or tuple(contract.get("slices", ())) != EXPECTED_SLICES
        or set(comparisons) != {"exp025", "exp029"}
        or float(comparisons["exp025"].get("registered_reference_macro_f1", -1)) != 0.241164
        or float(comparisons["exp025"].get("gate_threshold", -1))
        != 0.2461641547489156
        or float(comparisons["exp029"].get("registered_reference_macro_f1", -1)) != 0.440637
        or float(comparisons["exp029"].get("gate_threshold", -1))
        != 0.4456373760273263
        or contract.get("bert_reference") != {
            "macro_f1_mean": 0.489435,
            "role": "descriptive-only",
        }
        or set(contract.get("outputs", {}))
        != {"private_finalization_root", "run_dir"}
        or set(contract.get("test_gate", {})) != {"must_be_absent", "path"}
    ):
        raise ValueError("Validation contract policy differs from registration")
    required_implementation = {
        "constraint",
        "constraint_base",
        "generation_helper",
        "metrics",
        "protocol",
        "runner",
        "verifier",
    }
    if set(contract.get("implementation", {})) != required_implementation:
        raise ValueError("Validation implementation artifact set differs")
    for name, expected_path in EXPECTED_IMPLEMENTATION_PATHS.items():
        if (
            resolve_project_path(contract["implementation"][name]["path"])
            != expected_path.resolve()
        ):
            raise ValueError(f"Validation implementation path drift: {name}")
    required_inputs = {
        "adapter_config",
        "adapter_weights",
        "dev",
        "labels",
        "prompt",
        "training_verification",
    }
    if set(contract.get("inputs", {})) != required_inputs:
        raise ValueError("Validation input artifact set differs")
    if (
        resolve_project_path(contract["inputs"]["dev"]["path"]) != EXPECTED_DEV_PATH.resolve()
        or resolve_project_path(contract["inputs"]["labels"]["path"])
        != EXPECTED_LABELS_PATH.resolve()
        or resolve_project_path(contract["inputs"]["prompt"]["path"])
        != EXPECTED_PROMPT_PATH.resolve()
    ):
        raise ValueError("Validation dev, label, or prompt path drift")
    recalculated: dict[str, Any] = {
        "contract": artifact(contract_path),
        "implementation": {
            name: verify_spec(spec) for name, spec in contract["implementation"].items()
        },
        "inputs": {name: verify_spec(spec) for name, spec in contract["inputs"].items()},
    }
    training = load_json(resolve_project_path(contract["inputs"]["training_verification"]["path"]))
    if (
        training.get("experiment_id") != EXPERIMENT_ID
        or training.get("verification_id") != "EXP-033-FORMAL-TRAIN-VERIFY-V2"
        or training.get("status") != "Passed"
        or training.get("seed") != 42
        or training.get("accessed_splits") != ["train"]
        or training.get("formal_training_verified") is not True
        or training.get("validation_evaluation_authorized") is not True
        or training.get("validation_split_accessed") is not False
        or training.get("test_split_accessed") is not False
        or training.get("test_split_absent") is not True
    ):
        raise ValueError("Formal training verification does not authorize validation")
    for name, key in (("adapter_weights", "weights"), ("adapter_config", "config")):
        if (
            training.get("recalculated", {}).get("adapter", {}).get(key)
            != recalculated["inputs"][name]
        ):
            raise ValueError(f"Formal training verification does not bind {name}")
    test_gate = contract.get("test_gate", {})
    test_path = resolve_project_path(test_gate.get("path", ""))
    if test_path != EXPECTED_TEST_PATH.resolve():
        raise ValueError("Validation test-absence path drift")
    if test_gate.get("must_be_absent") is not True or test_path.exists():
        raise ValueError("Test-absence gate failed")
    labels = tuple(
        resolve_project_path(contract["inputs"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    if len(labels) != 28 or len(labels) != len(set(labels)) or "neutral" not in labels:
        raise ValueError("Ordered GoEmotions ontology differs")
    prompt = load_json(resolve_project_path(contract["inputs"]["prompt"]["path"]))
    if set(prompt) != {"prompt_id", "system_template", "user_template"}:
        raise ValueError("Aligned prompt schema drift")
    for name, comparison in comparisons.items():
        if (
            resolve_project_path(comparison["reference_predictions"]["path"])
            != EXPECTED_REFERENCE_PATHS[name].resolve()
        ):
            raise ValueError(f"{name} paired-reference path drift")
        verify_spec(comparison["reference_predictions"])
        if round(float(comparison["full_precision_reference_macro_f1"]), 6) != float(
            comparison["registered_reference_macro_f1"]
        ):
            raise ValueError(f"{name} full-precision reference does not match registration")
    recalculated["environment"] = verify_environment(contract)
    recalculated["model"] = verify_model(contract)
    if (
        contract["model"].get("repo_id") != "Qwen/Qwen3-1.7B"
        or contract["model"].get("revision")
        != "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
        or resolve_project_path(contract["model"]["local_path"])
        != (PROJECT_ROOT / "models" / "qwen3-1.7b" / "mlx-bf16").resolve()
        or resolve_project_path(contract["outputs"]["run_dir"])
        != EXPECTED_RUN_DIR.resolve()
        or resolve_project_path(contract["outputs"]["private_finalization_root"])
        != EXPECTED_PRIVATE_ROOT.resolve()
    ):
        raise ValueError("Validation model or output path drift")
    return contract, recalculated


def read_dev_gold(
    path: Path, expected_rows: int, labels: tuple[str, ...]
) -> tuple[np.ndarray, list[list[int]]]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.reader(handle, delimiter="\t")
        for index, row in enumerate(rows):
            if index >= expected_rows or len(row) != 3:
                raise ValueError(f"Invalid dev row {index + 1}")
            _, encoded_labels, comment_id = row
            if comment_id in seen_ids:
                raise ValueError("dev.tsv repeats a comment ID")
            seen_ids.add(comment_id)
            values = [int(value) for value in encoded_labels.split(",")]
            if (
                not values
                or len(values) != len(set(values))
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"Invalid dev labels at row {index + 1}")
            gold[index, values] = 1
            gold_ids.append(values)
    if len(gold_ids) != expected_rows:
        raise ValueError(f"dev.tsv has {len(gold_ids)} rows; expected {expected_rows}")
    return gold, gold_ids


def strict_parse(output: str, labels: tuple[str, ...]) -> tuple[list[str], str | None, str | None]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return [], "invalid-json", None
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return [], "wrong-object", None
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return [], "labels-not-nonempty-list", None
    if not all(isinstance(value, str) for value in values):
        return [], "non-string-label", None
    if len(values) != len(set(values)):
        return [], "duplicate-label", None
    if any(value not in labels for value in values):
        return [], "unknown-label", None
    canonical = json.dumps({"labels": values}, separators=(",", ":"))
    return values, None, canonical


def read_and_verify_records(
    path: Path,
    labels: tuple[str, ...],
    gold_ids: list[list[int]],
    memory_limit: float,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(records) != len(gold_ids):
        raise ValueError("Prediction record count differs from dev")
    predicted = np.zeros((len(records), len(labels)), dtype=np.uint8)
    label_to_id = {label: index for index, label in enumerate(labels)}
    for index, record in enumerate(records):
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raise ValueError(f"Row {index + 1} has no raw output")
        parsed_labels, parser_error, canonical = strict_parse(raw_output, labels)
        parser_valid = parser_error is None
        if record.get("finish_reason") != "stop":
            parser_valid = False
            parser_error = "length-terminated"
        expected_labels = parsed_labels if parser_valid else []
        expected_ids = [label_to_id[label] for label in expected_labels]
        if (
            record.get("row_number") != index + 1
            or record.get("condition") != CONDITION
            or record.get("gold_label_ids") != gold_ids[index]
            or record.get("gold_labels") != [labels[value] for value in gold_ids[index]]
            or record.get("predicted_labels") != expected_labels
            or record.get("predicted_label_ids") != expected_ids
            or record.get("parser_valid") is not parser_valid
            or record.get("parser_error") != parser_error
            or record.get("canonical_output") != (canonical if parser_valid else None)
            or record.get("output_sha256") != sha256_text(raw_output)
            or record.get("output_character_count") != len(raw_output)
        ):
            raise ValueError(f"Prediction semantics drift at row {index + 1}")
        numeric_nonnegative = (
            "generated_tokens",
            "generation_seconds",
            "generation_tps",
            "peak_memory_gb",
            "prompt_tokens",
            "prompt_tps",
            "raw_argmax_blocked_steps",
        )
        for key in numeric_nonnegative:
            value = record.get(key)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise ValueError(f"Invalid {key} at row {index + 1}")
        for key in ("sequence_logprob_mean", "sequence_logprob_sum"):
            if not math.isfinite(float(record.get(key))):
                raise ValueError(f"Invalid {key} at row {index + 1}")
        if float(record["peak_memory_gb"]) > memory_limit:
            raise ValueError("Stored prediction exceeds the memory gate")
        predicted[index, expected_ids] = 1
    return records, predicted


def divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )


def compute_metrics(
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: tuple[str, ...],
) -> tuple[dict[str, Any], np.ndarray]:
    if gold.shape != predicted.shape or gold.shape[1] != len(labels):
        raise ValueError("Metric matrix shape differs")
    gold_bool = gold.astype(bool)
    predicted_bool = predicted.astype(bool)
    tp = np.sum(gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fp = np.sum(~gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fn = np.sum(gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    tn = np.sum(~gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    support = tp + fn
    predicted_support = tp + fp
    precision = divide(tp, tp + fp)
    recall = divide(tp, tp + fn)
    f1 = divide(2 * tp, 2 * tp + fp + fn)
    total_support = int(support.sum())
    macro = {
        "precision": float(precision.mean()),
        "recall": float(recall.mean()),
        "f1": float(f1.mean()),
    }
    micro_tp, micro_fp, micro_fn = int(tp.sum()), int(fp.sum()), int(fn.sum())
    micro = {
        "precision": micro_tp / (micro_tp + micro_fp) if micro_tp + micro_fp else 0.0,
        "recall": micro_tp / (micro_tp + micro_fn) if micro_tp + micro_fn else 0.0,
        "f1": 2 * micro_tp / (2 * micro_tp + micro_fp + micro_fn)
        if 2 * micro_tp + micro_fp + micro_fn
        else 0.0,
    }
    weighted = {
        "precision": float(np.sum(precision * support) / total_support),
        "recall": float(np.sum(recall * support) / total_support),
        "f1": float(np.sum(f1 * support) / total_support),
    }
    sample_tp = np.sum(gold_bool & predicted_bool, axis=1, dtype=np.int64)
    sample_gold = np.sum(gold_bool, axis=1, dtype=np.int64)
    sample_predicted = np.sum(predicted_bool, axis=1, dtype=np.int64)
    samples = {
        "precision": float(np.mean(divide(sample_tp, sample_predicted))),
        "recall": float(np.mean(divide(sample_tp, sample_gold))),
        "f1": float(np.mean(divide(2 * sample_tp, sample_gold + sample_predicted))),
    }
    subset = float(np.mean(np.all(gold_bool == predicted_bool, axis=1)))
    hamming = float(np.mean(gold_bool != predicted_bool))
    per_label = {
        label: {
            "f1": float(f1[index]),
            "label_id": index,
            "precision": float(precision[index]),
            "predicted_support": int(predicted_support[index]),
            "recall": float(recall[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    confusion = np.stack(
        [np.stack([tn, fp], axis=1), np.stack([fn, tp], axis=1)], axis=1
    )
    neutral_index = labels.index("neutral") if "neutral" in labels else None
    return {
        "accuracy": subset,
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": hamming,
        "label_accuracy": 1.0 - hamming,
        "label_cardinality": {
            "gold_mean": float(np.mean(sample_gold)),
            "predicted_mean": float(np.mean(sample_predicted)),
        },
        "macro": macro,
        "micro": micro,
        "per_label": per_label,
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(sample_predicted == 0)),
            "neutral_coprediction_rows": int(
                np.sum(predicted_bool[:, neutral_index] & (sample_predicted > 1))
            )
            if neutral_index is not None
            else 0,
        },
        "primary": {"name": "macro_f1", "value": macro["f1"]},
        "samples": samples,
        "subset_accuracy": subset,
        "weighted": weighted,
    }, confusion


def numeric_summary(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Cannot summarize empty or non-finite values")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "total": float(np.sum(array)),
    }


def summarize_generation(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid_count = sum(bool(row["parser_valid"]) for row in records)
    errors = Counter(row["parser_error"] for row in records if row["parser_error"])
    finishes = Counter(row["finish_reason"] for row in records)
    intervened = [bool(row["constraint_intervened"]) for row in records]
    blocked = [int(row["raw_argmax_blocked_steps"]) for row in records]
    first_steps = [
        int(row["first_blocked_step"])
        for row in records
        if row["first_blocked_step"] is not None
    ]
    return {
        "constraint_intervention": {
            "blocked_steps_total": int(sum(blocked)),
            "first_blocked_step_median": float(statistics.median(first_steps))
            if first_steps
            else None,
            "rate": float(sum(intervened) / len(intervened)),
            "rows": int(sum(intervened)),
        },
        "finish_reasons": dict(sorted(finishes.items())),
        "generated_tokens": numeric_summary(float(row["generated_tokens"]) for row in records),
        "generation_seconds": numeric_summary(float(row["generation_seconds"]) for row in records),
        "generation_tps": numeric_summary(float(row["generation_tps"]) for row in records),
        "parser_errors": dict(sorted(errors.items())),
        "parser_valid_count": valid_count,
        "parser_valid_rate": valid_count / len(records),
        "peak_memory_gb_max": max(float(row["peak_memory_gb"]) for row in records),
        "prompt_tokens": numeric_summary(float(row["prompt_tokens"]) for row in records),
        "prompt_tps": numeric_summary(float(row["prompt_tps"]) for row in records),
        "sample_count": len(records),
        "sequence_logprob_mean": numeric_summary(
            float(row["sequence_logprob_mean"]) for row in records
        ),
        "sequence_logprob_sum": numeric_summary(
            float(row["sequence_logprob_sum"]) for row in records
        ),
    }


def slice_masks(labels: tuple[str, ...], gold: np.ndarray) -> dict[str, np.ndarray]:
    cardinality = gold.sum(axis=1)
    neutral = gold[:, labels.index("neutral")].astype(bool)
    return {
        "all": np.ones(gold.shape[0], dtype=bool),
        "single_label": cardinality == 1,
        "multi_label": cardinality > 1,
        "high_cardinality": cardinality >= 3,
        "neutral_only": neutral & (cardinality == 1),
        "neutral_cooccurrence": neutral & (cardinality > 1),
        "any_neutral": neutral,
        "without_neutral": ~neutral,
    }


def compute_slices(
    labels: tuple[str, ...],
    gold: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, mask in slice_masks(labels, gold).items():
        count = int(mask.sum())
        results[name] = {
            "metrics": compute_metrics(gold[mask], predicted[mask], labels)[0]
            if count
            else None,
            "row_count": count,
        }
    return results


def read_baseline_predictions(
    path: Path, labels: tuple[str, ...], expected_rows: int
) -> tuple[np.ndarray, np.ndarray]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    predicted = np.zeros_like(gold)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_rows:
        raise ValueError(f"{path} row count differs")
    for index, row in enumerate(rows):
        if int(row["row_number"]) != index + 1:
            raise ValueError(f"{path} row order changed")
        for field, matrix in (("gold_label_ids", gold), ("predicted_label_ids", predicted)):
            for encoded in row[field].split("|") if row[field] else []:
                label_id = int(encoded)
                if not 0 <= label_id < len(labels):
                    raise ValueError(f"{path} has an invalid label")
                matrix[index, label_id] = 1
    return gold, predicted


def macro_f1_from_counts(
    gold_support: np.ndarray,
    true_positive: np.ndarray,
    predicted_support: np.ndarray,
) -> np.ndarray:
    denominator = gold_support + predicted_support
    per_label = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=denominator != 0,
    )
    return np.mean(per_label, axis=1)


def paired_bootstrap(
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
    replicates: int,
    seed: int,
    practical_threshold: float,
    batch_size: int,
) -> dict[str, Any]:
    names = tuple(predictions)
    gold_u8 = gold.astype(np.uint8, copy=False)
    predicted_u8 = {name: value.astype(np.uint8, copy=False) for name, value in predictions.items()}
    tp_rows = {
        name: (gold_u8 & value).astype(np.uint8, copy=False)
        for name, value in predicted_u8.items()
    }
    samples = {name: np.empty(replicates, dtype=np.float64) for name in names}
    rng = np.random.default_rng(seed)
    row_count = gold.shape[0]
    for start in range(0, replicates, batch_size):
        stop = min(replicates, start + batch_size)
        indices = rng.integers(0, row_count, size=(stop - start, row_count), dtype=np.int32)
        gold_support = np.sum(gold_u8[indices], axis=1, dtype=np.int32)
        for name in names:
            predicted_support = np.sum(predicted_u8[name][indices], axis=1, dtype=np.int32)
            true_positive = np.sum(tp_rows[name][indices], axis=1, dtype=np.int32)
            samples[name][start:stop] = macro_f1_from_counts(
                gold_support, true_positive, predicted_support
            )
    observed = {
        name: compute_metrics(
            gold,
            value,
            tuple(str(i) for i in range(gold.shape[1])),
        )[0]["macro"]["f1"]
        for name, value in predicted_u8.items()
    }
    results: dict[str, Any] = {}
    for baseline in ("exp025", "exp029"):
        comparison = f"exp033-minus-{baseline}"
        differences = samples["exp033"] - samples[baseline]
        lower, upper = np.quantile(differences, [0.025, 0.975])
        delta = observed["exp033"] - observed[baseline]
        results[comparison] = {
            "ci_95_percentile": {"lower": float(lower), "upper": float(upper)},
            "left": "exp033",
            "observed_macro_f1_difference": float(delta),
            "practical_effect": abs(delta) >= practical_threshold,
            "practical_threshold": practical_threshold,
            "right": baseline,
            "two_sided_interval_excludes_zero": bool(lower > 0 or upper < 0),
        }
    return {
        "batch_size": batch_size,
        "confidence_interval": 0.95,
        "comparisons": results,
        "replicates": replicates,
        "resampling_unit": "dev row with replacement",
        "seed": seed,
        "statistic": "paired Macro-F1 difference",
    }


def verify_csv_artifacts(
    results_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    metrics: dict[str, Any],
    confusion: np.ndarray,
) -> None:
    with (results_dir / "predictions.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(records):
        raise ValueError("predictions.csv row count differs")
    for index, row in enumerate(rows):
        record = records[index]
        expected = {
            "row_number": str(record["row_number"]),
            "gold_label_ids": "|".join(str(value) for value in record["gold_label_ids"]),
            "gold_labels": "|".join(record["gold_labels"]),
            "predicted_label_ids": "|".join(
                str(value) for value in record["predicted_label_ids"]
            ),
            "predicted_labels": "|".join(record["predicted_labels"]),
            "parser_valid": str(record["parser_valid"]).lower(),
            "parser_error": record["parser_error"] or "",
            "finish_reason": record["finish_reason"] or "",
            "canonical_output": record["canonical_output"] or "",
            "output_sha256": record["output_sha256"],
            "output_character_count": str(record["output_character_count"]),
            "prompt_tokens": str(record["prompt_tokens"]),
            "generated_tokens": str(record["generated_tokens"]),
            "generation_seconds": format(float(record["generation_seconds"]), ".17g"),
            "prompt_tps": format(float(record["prompt_tps"]), ".17g"),
            "generation_tps": format(float(record["generation_tps"]), ".17g"),
            "peak_memory_gb": format(float(record["peak_memory_gb"]), ".17g"),
            "sequence_logprob_sum": format(
                float(record["sequence_logprob_sum"]), ".17g"
            ),
            "sequence_logprob_mean": format(
                float(record["sequence_logprob_mean"]), ".17g"
            ),
            "sequence_score_space": record["sequence_score_space"],
            "constraint_intervened": ""
            if record["constraint_intervened"] is None
            else str(record["constraint_intervened"]).lower(),
            "raw_argmax_blocked_steps": ""
            if record["raw_argmax_blocked_steps"] is None
            else str(record["raw_argmax_blocked_steps"]),
            "first_blocked_step": ""
            if record["first_blocked_step"] is None
            else str(record["first_blocked_step"]),
            "first_blocked_token_id": ""
            if record["first_blocked_token_id"] is None
            else str(record["first_blocked_token_id"]),
        }
        if row != expected:
            raise ValueError(f"predictions.csv differs at row {index + 1}")
    with (results_dir / "per-label-metrics.csv").open("r", encoding="utf-8", newline="") as handle:
        per_label_rows = list(csv.DictReader(handle))
    if len(per_label_rows) != len(labels):
        raise ValueError("Per-label CSV row count differs")
    for index, row in enumerate(per_label_rows):
        expected = metrics["per_label"][labels[index]]
        if (
            int(row["label_id"]) != index
            or row["label"] != labels[index]
            or int(row["support"]) != expected["support"]
            or int(row["predicted_support"]) != expected["predicted_support"]
        ):
            raise ValueError(f"Per-label CSV identity differs at label {index}")
        for key in ("precision", "recall", "f1"):
            if not math.isclose(float(row[key]), expected[key], rel_tol=1e-12, abs_tol=1e-15):
                raise ValueError(f"Per-label CSV {key} differs at label {index}")
    with (results_dir / "multilabel-confusion-matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        confusion_rows = list(csv.DictReader(handle))
    if len(confusion_rows) != len(labels):
        raise ValueError("Confusion CSV row count differs")
    for index, row in enumerate(confusion_rows):
        tn, fp, fn, tp = confusion[index].ravel()
        expected = [int(tn), int(fp), int(fn), int(tp)]
        observed = [int(row[key]) for key in ("tn", "fp", "fn", "tp")]
        if int(row["label_id"]) != index or row["label"] != labels[index] or observed != expected:
            raise ValueError(f"Confusion CSV differs at label {index}")


def collect_artifacts(run_dir: Path) -> dict[str, dict[str, Any]]:
    excluded = {"run.json", "verification.json"}
    return {
        path.relative_to(run_dir).as_posix(): artifact(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name not in excluded
    }


def build_verification(contract: dict[str, Any], recalculated: dict[str, Any]) -> dict[str, Any]:
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    run_path = run_dir / "run.json"
    run = load_json(run_path)
    if (
        run.get("evaluation_id") != EVALUATION_ID
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("stage") != STAGE
        or run.get("seed") != 42
        or run.get("status") != "Completed; pending independent verification"
        or run.get("condition") != CONDITION
        or run.get("final_adapter_only") is not True
        or run.get("accessed_splits") != ["dev"]
        or run.get("validation_split_accessed") is not True
        or run.get("test_split_accessed") is not False
        or run.get("test_rows_accessed") != 0
        or run.get("dev_generation_count") != 5426
        or run.get("raw_model_outputs_stored") is not True
        or run.get("raw_input_text_stored") is not False
        or run.get("raw_comment_ids_stored") is not False
    ):
        raise ValueError("Validation run boundary fields differ")
    require_nested_close(run.get("contract"), recalculated["contract"], "run.contract")
    if run.get("contract_sha256") != recalculated["contract"]["sha256"]:
        raise ValueError("Run contract hash differs")
    duration = float(run["active_duration_seconds"])
    if not math.isfinite(duration) or duration > 4 * 3600:
        raise ValueError("Validation active duration exceeded 4 hours")
    if "active_attempt_started_at_utc" in run or "active_attempt_base_seconds" in run:
        raise ValueError("Completed validation retains an open attempt")
    attempt_history = run.get("attempt_history")
    if not isinstance(attempt_history, list) or not attempt_history:
        raise ValueError("Validation attempt history is absent")
    charged_total = 0.0
    for index, attempt in enumerate(attempt_history):
        charged = float(attempt.get("charged_duration_seconds", -1))
        try:
            started = datetime.fromisoformat(attempt["started_at_utc"])
            ended = datetime.fromisoformat(attempt["ended_at_utc"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Validation attempt timestamps are invalid") from error
        if (
            attempt.get("attempt_index") != index + 1
            or attempt.get("closure")
            not in {"completed", "failed", "unclean-interruption-resumed"}
            or started.tzinfo is None
            or ended.tzinfo is None
            or ended < started
            or not math.isfinite(charged)
            or charged < 0
        ):
            raise ValueError(f"Validation attempt history differs at attempt {index + 1}")
        if (
            attempt["closure"] == "unclean-interruption-resumed"
            and charged + 1e-6 < (ended - started).total_seconds()
        ):
            raise ValueError("Unclean interruption was not conservatively charged")
        charged_total += charged
    if not math.isclose(charged_total, duration, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("Validation attempt history does not account for active duration")
    run_artifacts = collect_artifacts(run_dir)
    require_nested_close(run.get("artifacts"), run_artifacts, "run.artifacts")
    expected_paths = {
        "predictions.jsonl",
        "stdout.log",
        "results/comparisons.json",
        "results/metrics.json",
        "results/multilabel-confusion-matrix.csv",
        "results/paired-bootstrap.json",
        "results/per-label-metrics.csv",
        "results/predictions.csv",
        "results/slice-metrics.json",
    }
    if set(run_artifacts) != expected_paths:
        raise ValueError("Validation output artifact inventory differs")

    labels = tuple(
        resolve_project_path(contract["inputs"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    gold, gold_ids = read_dev_gold(
        resolve_project_path(contract["inputs"]["dev"]["path"]), 5426, labels
    )
    records, predicted = read_and_verify_records(
        run_dir / "predictions.jsonl",
        labels,
        gold_ids,
        float(contract["resource_budget"]["peak_mlx_memory_gb_max"]),
    )
    task, confusion = compute_metrics(gold, predicted, labels)
    generation = summarize_generation(records)
    if generation["peak_memory_gb_max"] > 14.0:
        raise ValueError("Recomputed peak memory exceeded 14 GB")
    generation_peak = generation["peak_memory_gb_max"]
    model_load_peak = float(run["dev_model_load_peak_mlx_memory_gb"])
    model_load_attempts = run.get("model_load_attempts")
    if not isinstance(model_load_attempts, list) or not model_load_attempts:
        raise ValueError("Model-load attempt telemetry is absent")
    attempt_peaks: list[float] = []
    attempt_seconds: list[float] = []
    for attempt in model_load_attempts:
        peak = float(attempt["peak_mlx_memory_gb"])
        seconds = float(attempt["seconds"])
        if (
            not math.isfinite(peak)
            or not math.isfinite(seconds)
            or peak < 0
            or seconds < 0
            or peak > 14.0
        ):
            raise ValueError("Invalid model-load attempt telemetry")
        attempt_peaks.append(peak)
        attempt_seconds.append(seconds)
    if (
        not math.isfinite(model_load_peak)
        or model_load_peak < 0
        or model_load_peak > 14.0
        or not math.isclose(model_load_peak, max(attempt_peaks), rel_tol=0.0, abs_tol=1e-15)
        or not math.isclose(
            float(run["dev_model_load_seconds"]),
            sum(attempt_seconds),
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        or not math.isclose(
            float(run["dev_generation_peak_mlx_memory_gb"]),
            generation_peak,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        or not math.isclose(
            float(run["dev_peak_mlx_memory_gb"]),
            max(model_load_peak, generation_peak),
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise ValueError("Run peak-memory summary differs")
    if not math.isclose(
        float(run["primary_macro_f1"]),
        task["macro"]["f1"],
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ValueError("Run primary Macro-F1 differs")
    results_dir = run_dir / "results"
    require_nested_close(
        load_json(results_dir / "metrics.json"),
        {"generation": generation, "task": task},
        "results.metrics",
    )
    slices = compute_slices(labels, gold, predicted)
    require_nested_close(
        load_json(results_dir / "slice-metrics.json"), slices, "results.slices"
    )
    verify_csv_artifacts(results_dir, records, labels, task, confusion)

    predictions = {"exp033": predicted}
    comparisons: dict[str, Any] = {}
    for name in ("exp025", "exp029"):
        spec = contract["comparisons"][name]
        baseline_gold, baseline = read_baseline_predictions(
            resolve_project_path(spec["reference_predictions"]["path"]), labels, 5426
        )
        if not np.array_equal(baseline_gold, gold):
            raise ValueError(f"{name} paired reference gold differs")
        reference = compute_metrics(gold, baseline, labels)[0]["macro"]["f1"]
        if not math.isclose(
            reference,
            float(spec["full_precision_reference_macro_f1"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"{name} full-precision reference differs")
        predictions[name] = baseline
        comparisons[name] = {
            "delta_macro_f1": task["macro"]["f1"] - reference,
            "exp033_macro_f1": task["macro"]["f1"],
            "gate_passed": (
                task["macro"]["f1"] - reference
                >= float(contract["bootstrap"]["practical_threshold"])
            ),
            "gate_threshold": float(spec["gate_threshold"]),
            "reference_macro_f1": reference,
            "registered_reference_macro_f1": float(spec["registered_reference_macro_f1"]),
        }
    bootstrap_spec = contract["bootstrap"]
    bootstrap = paired_bootstrap(
        gold,
        predictions,
        int(bootstrap_spec["replicates"]),
        int(bootstrap_spec["seed"]),
        float(bootstrap_spec["practical_threshold"]),
        int(bootstrap_spec.get("batch_size", 100)),
    )
    require_nested_close(
        load_json(results_dir / "paired-bootstrap.json"),
        bootstrap,
        "results.bootstrap",
    )
    comparisons["bert"] = {
        "delta_macro_f1": task["macro"]["f1"]
        - float(contract["bert_reference"]["macro_f1_mean"]),
        "exp033_macro_f1": task["macro"]["f1"],
        "gate": None,
        "reference_macro_f1_mean": float(contract["bert_reference"]["macro_f1_mean"]),
        "role": "descriptive-only",
    }
    for name in ("exp025", "exp029"):
        comparisons[name]["paired_bootstrap"] = bootstrap["comparisons"][
            f"exp033-minus-{name}"
        ]
    require_nested_close(
        load_json(results_dir / "comparisons.json"),
        comparisons,
        "results.comparisons",
    )
    return {
        "accessed_splits": ["dev"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": recalculated["contract"],
        "evaluation_id": EVALUATION_ID,
        "experiment_id": EXPERIMENT_ID,
        "implementation": {
            "imports_runner": False,
            "verifier": artifact(Path(__file__).resolve()),
        },
        "recalculated": {
            **recalculated,
            "artifacts": run_artifacts,
            "comparisons": comparisons,
            "generation": generation,
            "paired_bootstrap": bootstrap,
            "run": artifact(run_path),
            "slices": slices,
            "task": task,
        },
        "seed": 42,
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_only_verified": True,
        "validation_split_accessed": True,
        "verification_id": VERIFICATION_ID,
    }


def main() -> None:
    args = parse_args()
    contract, recalculated = validate_contract(args.contract, args.contract_sha256)
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    verification_path = run_dir / "verification.json"
    expected = build_verification(contract, recalculated)
    if args.check:
        existing = load_json(verification_path)
        expected["completed_at_utc"] = existing.get("completed_at_utc")
        require_nested_close(existing, expected, "stored verification")
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, indent=2))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    write_json(verification_path, expected)
    print(json.dumps(expected, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
