#!/usr/bin/env python3
"""Run the contract-frozen EXP-033 seed-42 validation-only evaluation."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from typing import Any


os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EVALUATION_ID = "EXP-033-SEED42-VALIDATION-V1"
EXPERIMENT_ID = "EXP-033"
STAGE = "seed-42-validation-only"
CONDITION = "aligned-prompt-open-neutral"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
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
    parser.add_argument("--resume", action="store_true")
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


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(str(spec["path"]))
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {path}")
    if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact size drift: {path}")
    return observed


def absolute_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": str(path),
        "sha256": sha256_file(path),
    }


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
    file_count = 0
    total_bytes = 0
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
        file_count += 1
        total_bytes += observed["bytes"]
    inventory = manifest["mlx_bf16"]
    if file_count != int(inventory["file_count"]) or total_bytes != int(inventory["total_bytes"]):
        raise ValueError("Model inventory totals differ")
    return {
        "file_count": file_count,
        "manifest": observed_manifest,
        "total_bytes": total_bytes,
    }


def verify_training_verification(contract: dict[str, Any]) -> dict[str, Any]:
    spec = contract["inputs"]["training_verification"]
    observed = verify_spec(spec)
    report = load_json(resolve_project_path(spec["path"]))
    if (
        report.get("experiment_id") != EXPERIMENT_ID
        or report.get("verification_id") != "EXP-033-FORMAL-TRAIN-VERIFY-V2"
        or report.get("status") != "Passed"
        or report.get("seed") != 42
        or report.get("accessed_splits") != ["train"]
        or report.get("formal_training_verified") is not True
        or report.get("validation_evaluation_authorized") is not True
        or report.get("validation_split_accessed") is not False
        or report.get("test_split_accessed") is not False
        or report.get("test_split_absent") is not True
    ):
        raise ValueError("Formal training verification does not authorize validation")
    recalculated = report.get("recalculated", {}).get("adapter", {})
    for name, key in (("adapter_weights", "weights"), ("adapter_config", "config")):
        expected = verify_spec(contract["inputs"][name])
        if recalculated.get(key) != expected:
            raise ValueError(f"Training verification does not bind {name}")
    return observed


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
        raise ValueError("Validation contract policy differs from the registered protocol")

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
    recalculated: dict[str, Any] = {
        "contract": artifact(contract_path),
        "implementation": {
            name: verify_spec(spec) for name, spec in contract["implementation"].items()
        },
    }
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
    recalculated["inputs"] = {
        name: verify_spec(spec) for name, spec in contract["inputs"].items()
    }
    recalculated["training_verification"] = verify_training_verification(contract)

    test_gate = contract.get("test_gate", {})
    test_path = resolve_project_path(test_gate.get("path", ""))
    if test_path != EXPECTED_TEST_PATH.resolve():
        raise ValueError("Validation test-absence path drift")
    if test_gate.get("must_be_absent") is not True or test_path.exists():
        raise ValueError("Test-absence gate failed")
    prompt = load_json(resolve_project_path(contract["inputs"]["prompt"]["path"]))
    if set(prompt) != {"prompt_id", "system_template", "user_template"}:
        raise ValueError("Aligned prompt schema drift")
    labels = tuple(
        resolve_project_path(contract["inputs"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    if len(labels) != 28 or len(labels) != len(set(labels)) or "neutral" not in labels:
        raise ValueError("Ordered GoEmotions ontology differs")
    for name, comparison in comparisons.items():
        if (
            resolve_project_path(comparison["reference_predictions"]["path"])
            != EXPECTED_REFERENCE_PATHS[name].resolve()
        ):
            raise ValueError(f"{name} paired-reference path drift")
        verify_spec(comparison["reference_predictions"])
        full_precision = float(comparison["full_precision_reference_macro_f1"])
        rounded = float(comparison["registered_reference_macro_f1"])
        if round(full_precision, 6) != rounded:
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


def load_dev(
    path: Path, expected_rows: int, labels: tuple[str, ...]
) -> tuple[list[str], Any, list[list[int]]]:
    import numpy as np

    texts: list[str] = []
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle, delimiter="\t")):
            if row_index >= expected_rows or len(row) != 3:
                raise ValueError(f"Invalid dev row {row_index + 1}")
            text, encoded_labels, comment_id = row
            if comment_id in seen_ids:
                raise ValueError("dev.tsv repeats a comment ID")
            seen_ids.add(comment_id)
            values = [int(value) for value in encoded_labels.split(",")]
            if (
                not values
                or len(values) != len(set(values))
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"Invalid dev labels at row {row_index + 1}")
            texts.append(text)
            gold[row_index, values] = 1
            gold_ids.append(values)
    if len(texts) != expected_rows:
        raise ValueError(f"dev.tsv has {len(texts)} rows; expected {expected_rows}")
    return texts, gold, gold_ids


def build_prompt(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
) -> str:
    messages = [
        {
            "role": "system",
            "content": prompt_spec["system_template"].format(allowed_labels=", ".join(labels)),
        },
        {"role": "user", "content": prompt_spec["user_template"].format(text=text)},
    ]
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=False,
    )


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-object", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def make_record(
    row_number: int,
    gold_label_ids: list[int],
    labels: tuple[str, ...],
    generated: dict[str, Any],
) -> dict[str, Any]:
    raw_output = generated.pop("output")
    parsed = strict_parse(raw_output, labels)
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    return {
        "canonical_output": parsed["canonical_output"] if parser_valid else None,
        "condition": CONDITION,
        "constraint_intervened": generated["constraint_intervened"],
        "finish_reason": generated["finish_reason"],
        "first_blocked_step": generated["first_blocked_step"],
        "first_blocked_token_id": generated["first_blocked_token_id"],
        "generated_tokens": generated["generated_tokens"],
        "generation_seconds": generated["generation_seconds"],
        "generation_tps": generated["generation_tps"],
        "gold_label_ids": gold_label_ids,
        "gold_labels": [labels[value] for value in gold_label_ids],
        "output_character_count": len(raw_output),
        "output_sha256": sha256_text(raw_output),
        "parser_error": parser_error,
        "parser_valid": parser_valid,
        "peak_memory_gb": generated["peak_memory_gb"],
        "predicted_label_ids": [label_to_id[label] for label in predicted_labels],
        "predicted_labels": predicted_labels,
        "prompt_tokens": generated["prompt_tokens"],
        "prompt_tps": generated["prompt_tps"],
        "raw_argmax_blocked_steps": generated["raw_argmax_blocked_steps"],
        "raw_output": raw_output,
        "row_number": row_number,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": "open-neutral constrained label-name JSON",
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_record_prefix(
    records: list[dict[str, Any]],
    gold_ids: list[list[int]],
    labels: tuple[str, ...],
) -> None:
    if len(records) > len(gold_ids):
        raise ValueError("Prediction checkpoint has too many rows")
    label_to_id = {label: index for index, label in enumerate(labels)}
    for index, record in enumerate(records):
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raise ValueError(f"Prediction checkpoint has no raw output at row {index + 1}")
        parsed = strict_parse(raw_output, labels)
        parser_valid = parsed["error"] is None
        parser_error = parsed["error"]
        if record.get("finish_reason") != "stop":
            parser_valid = False
            parser_error = "length-terminated"
        expected_labels = parsed["labels"] if parser_valid else []
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
            or record.get("canonical_output")
            != (parsed["canonical_output"] if parser_valid else None)
            or record.get("output_sha256") != sha256_text(raw_output)
            or record.get("output_character_count") != len(raw_output)
            or record.get("sequence_score_space")
            != "open-neutral constrained label-name JSON"
        ):
            raise ValueError(f"Prediction checkpoint diverges at row {index + 1}")
        for key in (
            "generated_tokens",
            "generation_seconds",
            "generation_tps",
            "peak_memory_gb",
            "prompt_tokens",
            "prompt_tps",
            "raw_argmax_blocked_steps",
        ):
            value = record.get(key)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise ValueError(f"Invalid checkpoint {key} at row {index + 1}")
        for key in ("sequence_logprob_mean", "sequence_logprob_sum"):
            value = record.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"Invalid checkpoint {key} at row {index + 1}")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Validation attempt timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def close_active_attempt(
    run: dict[str, Any],
    ended_at: datetime,
    total_active_seconds: float,
    closure: str,
) -> None:
    started_value = run.pop("active_attempt_started_at_utc")
    base_seconds = float(run.pop("active_attempt_base_seconds"))
    charged_seconds = total_active_seconds - base_seconds
    if not math.isfinite(charged_seconds) or charged_seconds < 0:
        raise ValueError("Validation attempt duration is invalid")
    history = run.setdefault("attempt_history", [])
    history.append(
        {
            "attempt_index": len(history) + 1,
            "charged_duration_seconds": charged_seconds,
            "closure": closure,
            "ended_at_utc": ended_at.isoformat(),
            "started_at_utc": started_value,
        }
    )
    run["active_duration_seconds"] = total_active_seconds


def slice_masks(labels: tuple[str, ...], gold: Any) -> dict[str, Any]:
    import numpy as np

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
    metric_tools: Any,
    labels: tuple[str, ...],
    gold: Any,
    predicted: Any,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, mask in slice_masks(labels, gold).items():
        row_count = int(mask.sum())
        if row_count == 0:
            results[name] = {"metrics": None, "row_count": 0}
            continue
        metrics, _ = metric_tools.compute_metrics(gold[mask], predicted[mask], labels)
        results[name] = {"metrics": metrics, "row_count": row_count}
    return results


def finalize_outputs(
    contract: dict[str, Any],
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: Any,
) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPT_DIR))
    import llm_full_dev_metrics as metric_tools

    results_dir = run_dir / "results"
    if results_dir.exists():
        raise FileExistsError("Final validation results already exist")
    private_root = resolve_project_path(contract["outputs"]["private_finalization_root"])
    private_root.mkdir(parents=True, exist_ok=True)
    attempt = private_root / f"attempt-{time.time_ns()}"
    attempt.mkdir()
    try:
        predicted = metric_tools.records_to_prediction_matrix(records, labels)
        metrics, confusion = metric_tools.compute_metrics(gold, predicted, labels)
        generation = metric_tools.summarize_generation(records)
        metric_tools.write_predictions(attempt / "predictions.csv", records)
        metric_tools.write_per_label(attempt / "per-label-metrics.csv", metrics, labels)
        metric_tools.write_confusion(
            attempt / "multilabel-confusion-matrix.csv", confusion, labels
        )
        write_json(attempt / "metrics.json", {"generation": generation, "task": metrics})
        write_json(
            attempt / "slice-metrics.json",
            compute_slices(metric_tools, labels, gold, predicted),
        )

        baseline_predictions: dict[str, Any] = {"exp033": predicted}
        comparison_rows: dict[str, Any] = {}
        bootstrap_comparisons: list[tuple[str, str, str]] = []
        for name in ("exp025", "exp029"):
            spec = contract["comparisons"][name]
            baseline_gold, baseline = metric_tools.read_baseline_predictions(
                resolve_project_path(spec["reference_predictions"]["path"]),
                labels,
                gold.shape[0],
            )
            if not (baseline_gold == gold).all():
                raise ValueError(f"{name} paired reference gold differs from official dev")
            baseline_metrics, _ = metric_tools.compute_metrics(gold, baseline, labels)
            observed_reference = baseline_metrics["macro"]["f1"]
            if not math.isclose(
                observed_reference,
                float(spec["full_precision_reference_macro_f1"]),
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                raise ValueError(f"{name} full-precision reference Macro-F1 drift")
            baseline_predictions[name] = baseline
            bootstrap_comparisons.append((f"exp033-minus-{name}", "exp033", name))
            comparison_rows[name] = {
                "delta_macro_f1": metrics["macro"]["f1"] - observed_reference,
                "exp033_macro_f1": metrics["macro"]["f1"],
                "gate_passed": (
                    metrics["macro"]["f1"] - observed_reference
                    >= float(contract["bootstrap"]["practical_threshold"])
                ),
                "gate_threshold": float(spec["gate_threshold"]),
                "reference_macro_f1": observed_reference,
                "registered_reference_macro_f1": float(spec["registered_reference_macro_f1"]),
            }
        bootstrap = metric_tools.paired_bootstrap_macro_f1(
            gold,
            baseline_predictions,
            bootstrap_comparisons,
            int(contract["bootstrap"]["replicates"]),
            int(contract["bootstrap"]["seed"]),
            float(contract["bootstrap"]["practical_threshold"]),
            int(contract["bootstrap"].get("batch_size", 100)),
        )
        write_json(attempt / "paired-bootstrap.json", bootstrap)
        comparison_rows["bert"] = {
            "delta_macro_f1": metrics["macro"]["f1"]
            - float(contract["bert_reference"]["macro_f1_mean"]),
            "exp033_macro_f1": metrics["macro"]["f1"],
            "gate": None,
            "reference_macro_f1_mean": float(contract["bert_reference"]["macro_f1_mean"]),
            "role": "descriptive-only",
        }
        for name in ("exp025", "exp029"):
            comparison_rows[name]["paired_bootstrap"] = bootstrap["comparisons"][
                f"exp033-minus-{name}"
            ]
        write_json(attempt / "comparisons.json", comparison_rows)
        os.replace(attempt, results_dir)
        return {
            "comparisons": comparison_rows,
            "generation": generation,
            "results_directory": display_path(results_dir),
            "task": metrics,
        }
    finally:
        if attempt.exists():
            for child in attempt.iterdir():
                child.unlink()
            attempt.rmdir()


def append_log(path: Path, message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
    print(line, flush=True)


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
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def collect_artifacts(run_dir: Path) -> dict[str, dict[str, Any]]:
    excluded = {"run.json", "verification.json"}
    return {
        path.relative_to(run_dir).as_posix(): artifact(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name not in excluded
    }


def run_validation(
    contract: dict[str, Any],
    contract_path: Path,
    contract_sha256: str,
    recalculated: dict[str, Any],
    resume: bool,
) -> None:
    outputs = contract["outputs"]
    run_dir = resolve_project_path(outputs["run_dir"])
    run_path = run_dir / "run.json"
    records_path = run_dir / "predictions.jsonl"
    log_path = run_dir / "stdout.log"
    time_limit = float(contract["resource_budget"]["active_wall_time_hours_max"]) * 3600
    attempt_started_at = datetime.now(timezone.utc)
    if resume:
        if not run_path.is_file():
            raise FileNotFoundError("Resume requires an existing run")
        run = load_json(run_path)
        if run.get("status") not in {"Validation In Progress", "Failed"}:
            raise ValueError("Only an incomplete validation run may resume")
        if run.get("terminal_resource_violation") is not None:
            raise ValueError("A terminal resource-gate failure cannot resume")
        if run.get("contract_sha256") != contract_sha256:
            raise ValueError("Resume contract differs")
        if run.get("error") is not None:
            run.setdefault("attempt_failures", []).append(run.pop("error"))
        run.pop("completed_at_utc", None)
        prior_active = float(run.get("active_duration_seconds", 0.0))
        if "active_attempt_started_at_utc" in run:
            stale_started = parse_utc(run["active_attempt_started_at_utc"])
            stale_base = float(run["active_attempt_base_seconds"])
            conservative_total = max(
                prior_active,
                stale_base + max(0.0, (attempt_started_at - stale_started).total_seconds()),
            )
            close_active_attempt(
                run,
                attempt_started_at,
                conservative_total,
                "unclean-interruption-resumed",
            )
            prior_active = conservative_total
        if prior_active >= time_limit:
            error = {
                "message": "Validation active wall-time gate was exhausted before resume",
                "traceback": None,
                "type": "TimeoutError",
            }
            run.update(
                {
                    "active_duration_seconds": prior_active,
                    "completed_at_utc": attempt_started_at.isoformat(),
                    "error": error,
                    "status": "Failed",
                    "terminal_resource_violation": error,
                }
            )
            write_json(run_path, run)
            append_log(log_path, f"FAILED: {error['message']}")
            raise TimeoutError(error["message"])
        run["status"] = "Validation In Progress"
    else:
        if run_dir.exists():
            raise FileExistsError(f"Append-only validation output exists: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=False)
        run = {
            "accessed_splits": ["dev"],
            "active_duration_seconds": 0.0,
            "attempt_history": [],
            "api_cost_usd": 0,
            "command": [
                sys.executable,
                display_path(Path(__file__)),
                "--contract",
                display_path(contract_path),
                "--contract-sha256",
                contract_sha256,
            ],
            "condition": CONDITION,
            "contract": artifact(contract_path),
            "contract_sha256": contract_sha256,
            "evaluation_id": EVALUATION_ID,
            "experiment_id": EXPERIMENT_ID,
            "final_adapter_only": True,
            "git": git_metadata(),
            "pre_inference_recalculation": recalculated,
            "seed": 42,
            "stage": STAGE,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Validation In Progress",
            "test_split_accessed": False,
            "tier": "Major",
            "validation_split_accessed": True,
        }
        prior_active = 0.0
    run["active_attempt_base_seconds"] = prior_active
    run["active_attempt_started_at_utc"] = attempt_started_at.isoformat()
    run["active_duration_seconds"] = prior_active
    write_json(run_path, run)

    sys.path.insert(0, str(SCRIPT_DIR))
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from label_json_constraint_neutral_cooccurrence import (
        NeutralCooccurrenceLogitsProcessor,
    )
    import run_lora as generation_helper

    labels = tuple(
        resolve_project_path(contract["inputs"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    prompt_spec = load_json(resolve_project_path(contract["inputs"]["prompt"]["path"]))
    texts, gold, gold_ids = load_dev(
        resolve_project_path(contract["inputs"]["dev"]["path"]),
        5426,
        labels,
    )
    records = read_records(records_path) if resume else []
    verify_record_prefix(records, gold_ids, labels)
    memory_limit = float(contract["resource_budget"]["peak_mlx_memory_gb_max"])
    started = time.perf_counter()
    append_log(log_path, f"Starting {EVALUATION_ID}; completed prefix={len(records)}")
    try:
        adapter_weights = resolve_project_path(contract["inputs"]["adapter_weights"]["path"])
        adapter_config = resolve_project_path(contract["inputs"]["adapter_config"]["path"])
        if adapter_weights.parent != adapter_config.parent:
            raise ValueError("Adapter weights and config must share the final adapter directory")
        model_dir = resolve_project_path(contract["model"]["local_path"])
        mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = load(
            str(model_dir),
            adapter_path=str(adapter_weights.parent),
            lazy=False,
        )
        model_load_seconds = time.perf_counter() - load_started
        current_model_load_peak = float(mx.get_peak_memory()) / 1e9
        if current_model_load_peak > memory_limit:
            raise MemoryError("Validation exceeded its memory gate during model load")
        run.setdefault("model_load_attempts", []).append(
            {
                "peak_mlx_memory_gb": current_model_load_peak,
                "seconds": model_load_seconds,
            }
        )
        write_json(run_path, run)
        model_load_peak_memory = max(
            float(attempt["peak_mlx_memory_gb"])
            for attempt in run["model_load_attempts"]
        )
        model_load_seconds_total = sum(
            float(attempt["seconds"]) for attempt in run["model_load_attempts"]
        )
        constraint = generation_helper.TelemetryConstraint(
            NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx),
            mx,
        )
        elapsed = time.perf_counter() - started
        if prior_active + elapsed > time_limit:
            raise TimeoutError("Validation exceeded 4-hour gate during model load")
        append_log(
            log_path,
            f"Model loaded in {model_load_seconds:.3f}s; peak {current_model_load_peak:.3f} GB",
        )

        initial_count = len(records)
        with records_path.open("a" if resume else "x", encoding="utf-8") as output:
            for index in range(len(records), len(texts)):
                if prior_active + (time.perf_counter() - started) > time_limit:
                    raise TimeoutError("Validation exceeded its active wall-time gate")
                generated = generation_helper.generate_one(
                    model,
                    tokenizer,
                    build_prompt(tokenizer, prompt_spec, labels, texts[index]),
                    64,
                    constraint,
                    mx,
                    stream_generate,
                    make_sampler,
                )
                if float(generated["peak_memory_gb"]) > memory_limit:
                    raise MemoryError("Validation exceeded its peak MLX memory gate")
                record = make_record(index + 1, gold_ids[index], labels, generated)
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                records.append(record)
                if (index + 1) % 50 == 0 or index + 1 == len(texts):
                    os.fsync(output.fileno())
                if (index + 1) % 100 == 0 or index + 1 == len(texts):
                    elapsed = time.perf_counter() - started
                    completed_now = index + 1 - initial_count
                    rate = completed_now / elapsed if elapsed > 0 else 0.0
                    remaining = (len(texts) - index - 1) / rate if rate > 0 else None
                    run["active_duration_seconds"] = prior_active + elapsed
                    run["dev_progress"] = {
                        "completed": index + 1,
                        "estimated_remaining_seconds": remaining,
                        "total": len(texts),
                    }
                    write_json(run_path, run)
                    eta = "unknown" if remaining is None else f"{remaining / 60:.1f} min"
                    append_log(
                        log_path,
                        f"Dev {index + 1}/{len(texts)}; elapsed {elapsed / 60:.1f} min; ETA {eta}",
                    )
                if prior_active + (time.perf_counter() - started) > time_limit:
                    raise TimeoutError("Validation exceeded its wall-time gate after generation")
        verify_record_prefix(records, gold_ids, labels)
        if len(records) != 5426:
            raise ValueError("Validation prediction set is incomplete")
        summary = finalize_outputs(contract, run_dir, records, labels, gold)
        duration = prior_active + (time.perf_counter() - started)
        if duration > time_limit:
            raise TimeoutError("Validation exceeded its wall-time gate during finalization")
        generation_peak_memory = max(float(row["peak_memory_gb"]) for row in records)
        peak_memory = max(model_load_peak_memory, generation_peak_memory)
        if peak_memory > memory_limit:
            raise MemoryError("Validation exceeded its peak memory gate")
        append_log(
            log_path,
            f"Completed dev Macro-F1={summary['task']['macro']['f1']:.6f}",
        )
        completed_at = datetime.now(timezone.utc)
        close_active_attempt(run, completed_at, duration, "completed")
        run.update(
            {
                "active_duration_seconds": duration,
                "artifacts": collect_artifacts(run_dir),
                "completed_at_utc": completed_at.isoformat(),
                "dev_generation_count": len(records),
                "dev_generation_peak_mlx_memory_gb": generation_peak_memory,
                "dev_model_load_seconds": model_load_seconds_total,
                "dev_model_load_peak_mlx_memory_gb": model_load_peak_memory,
                "dev_peak_mlx_memory_gb": peak_memory,
                "primary_macro_f1": summary["task"]["macro"]["f1"],
                "raw_comment_ids_stored": False,
                "raw_input_text_stored": False,
                "raw_model_outputs_stored": True,
                "status": "Completed; pending independent verification",
                "test_rows_accessed": 0,
            }
        )
        write_json(run_path, run)
    except BaseException as error:
        duration = prior_active + (time.perf_counter() - started)
        completed_at = datetime.now(timezone.utc)
        if "active_attempt_started_at_utc" in run:
            close_active_attempt(run, completed_at, duration, "failed")
        terminal = isinstance(error, (MemoryError, TimeoutError))
        failure = {
            "message": str(error),
            "traceback": traceback.format_exc(),
            "type": type(error).__name__,
        }
        run.update(
            {
                "active_duration_seconds": duration,
                "completed_at_utc": completed_at.isoformat(),
                "error": failure,
                "status": "Failed",
            }
        )
        if terminal:
            run["terminal_resource_violation"] = failure
        write_json(run_path, run)
        append_log(log_path, f"FAILED: {error}")
        raise


def main() -> None:
    args = parse_args()
    contract, recalculated = validate_contract(args.contract, args.contract_sha256)
    run_validation(
        contract,
        args.contract.resolve(),
        args.contract_sha256,
        recalculated,
        args.resume,
    )


if __name__ == "__main__":
    main()
