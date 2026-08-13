#!/usr/bin/env python3
"""Run the authorized EXP-047 matched singleton validation comparison."""

from __future__ import annotations

import argparse
from collections import Counter
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
import random
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence


EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-MATCHED-VALIDATION-V1"
CONDITIONS = ("reference", "seed-42", "seed-43", "seed-44")
INVALID_LABEL = "__invalid__"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-matched-validation-contract-v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    infer = subparsers.add_parser("infer")
    infer.add_argument("--condition", choices=CONDITIONS, required=True)
    subparsers.add_parser("aggregate")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)
    if private:
        path.chmod(0o600)


def append_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)
    with path.open("a", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())
    path.chmod(0o600)


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    observed = artifact(resolve_project_path(spec["path"]))
    if observed["bytes"] != int(spec["bytes"]) or observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {spec['path']}")
    return observed


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    expected_generation = {
        "batch_size": 1,
        "completion_batch_size": 1,
        "do_sample": False,
        "enable_thinking": True,
        "max_input_tokens": 512,
        "max_new_tokens": 1024,
        "prefill_batch_size": 1,
        "prefill_step_size": 2048,
        "temperature": 0.0,
        "view": "target_only",
    }
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or tuple(contract.get("condition_order", ())) != CONDITIONS
        or contract.get("accessed_splits") != ["validation"]
        or contract.get("test_split_accessed") is not False
        or contract.get("labels")
        != ["anger", "joy", "negative", "neutral", "no_emotion", "positive", "sadness"]
        or contract.get("generation") != expected_generation
        or contract.get("data", {}).get("protocol_id") != "DATA-WEIBO-TASK-V1"
        or contract.get("data", {}).get("train_rows") != 5995
        or contract.get("data", {}).get("validation_rows") != 1272
        or contract.get("model", {}).get("repo_id") != "Qwen/Qwen3-4B"
        or contract.get("model", {}).get("revision")
        != "1cfa9a7208912126459214e8b04321603b3df60c"
        or contract.get("model", {}).get("precision") != "bfloat16"
        or contract.get("model", {}).get("quantized") is not False
    ):
        raise ValueError("Unexpected EXP-047 matched-validation contract")
    expected_seeds = {"reference": None, "seed-42": 42, "seed-43": 43, "seed-44": 44}
    if any(contract.get("conditions", {}).get(name, {}).get("seed") != seed for name, seed in expected_seeds.items()):
        raise ValueError("Matched-validation condition/seed drift")
    if contract["conditions"]["reference"].get("adapter") is not None:
        raise ValueError("Matched reference must not load an adapter")
    if contract["data"]["validation_path"] != contract["frozen_artifacts"]["validation"]["path"]:
        raise ValueError("Validation path/spec drift")
    if contract["data"]["train_path"] != contract["frozen_artifacts"]["train"]["path"]:
        raise ValueError("Train path/spec drift")
    if contract["model"]["manifest_path"] != contract["frozen_artifacts"]["model_manifest"]["path"]:
        raise ValueError("Model manifest path/spec drift")
    runner = resolve_project_path(contract["implementation"]["runner"]["path"])
    if runner != Path(__file__).resolve():
        raise ValueError("Matched-validation runner path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    for condition in CONDITIONS:
        condition_spec = contract["conditions"][condition]
        for name in ("adapter", "adapter_config"):
            spec = condition_spec.get(name)
            if spec is not None:
                verify_spec(spec)
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError("Matched validation must use the frozen Python environment")
    observed_packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in contract["runtime"]["packages"]
    }
    if observed_packages != contract["runtime"]["packages"]:
        raise ValueError("Matched-validation package-version drift")
    return contract


def load_parser(contract: dict[str, Any]):
    path = resolve_project_path(contract["frozen_artifacts"]["parser"]["path"])
    spec = importlib.util.spec_from_file_location("exp047_matched_validation_parser", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_final_label


def verify_authorization(contract: dict[str, Any]) -> dict[str, Any]:
    authorization = load_json(resolve_project_path(contract["frozen_artifacts"]["authorization"]["path"]))
    if (
        authorization.get("authorization_id") != "EXP-047-MATCHED-VALIDATION-AUTH-V1"
        or authorization.get("status") != "Authorized"
        or authorization.get("authorized_split") != "validation"
        or tuple(authorization.get("authorized_conditions_in_order", ())) != CONDITIONS
        or authorization.get("authorized_generations") != 5088
        or authorization.get("boundaries", {}).get("sealed_test_access") is not False
    ):
        raise ValueError("Matched-validation authorization is invalid")
    return authorization


def verify_training_and_replay_gates(contract: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for condition in CONDITIONS[1:]:
        seed = int(condition.split("-")[1])
        gate = contract["gates"][condition]
        training_path = resolve_project_path(gate["training_verification"]["path"])
        replay_path = resolve_project_path(gate["replay_verification"]["path"])
        verify_spec(gate["training_verification"])
        verify_spec(gate["replay_verification"])
        training = load_json(training_path)
        replay = load_json(replay_path)
        if (
            training.get("verification_id") != gate["training_verification_id"]
            or training.get("seed") != seed
            or training.get("status") != "Passed"
            or training.get("formal_training_verified") is not True
            or training.get("validation_split_accessed") is not False
            or training.get("test_split_accessed") is not False
        ):
            raise ValueError(f"Training gate is invalid: {condition}")
        expected_adapter = contract["conditions"][condition]["adapter"]
        expected_adapter_config = contract["conditions"][condition]["adapter_config"]
        observed_adapter = training.get("recalculated", {}).get("adapter", {}).get("weights")
        observed_adapter_config = training.get("recalculated", {}).get("adapter", {}).get("config")
        if observed_adapter != expected_adapter or observed_adapter_config != expected_adapter_config:
            raise ValueError(f"Training gate adapter identity drift: {condition}")
        comparison = replay.get("recalculated", {}).get("comparison", {})
        if (
            replay.get("verification_id") != gate["replay_verification_id"]
            or replay.get("seed") != seed
            or replay.get("status") != "Passed"
            or comparison
            != {
                "final_label_equal_count": 16,
                "parser_state_equal_count": 16,
                "raw_output_equal_count": 16,
                "rows": 16,
            }
            or replay.get("validation_split_accessed") is not False
            or replay.get("test_split_accessed") is not False
        ):
            raise ValueError(f"Replay gate is invalid: {condition}")
        results[condition] = {
            "replay_verification_id": replay["verification_id"],
            "training_verification_id": training["verification_id"],
        }
    return results


def verify_model_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    manifest = load_json(resolve_project_path(contract["frozen_artifacts"]["model_manifest"]["path"]))
    model = contract["model"]
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(model["local_path"])
    checked = []
    for expected in manifest["mlx_bf16"]["files"]:
        path = model_root / expected["path"]
        observed = artifact(path)
        if observed["bytes"] != expected["bytes"] or observed["sha256"] != expected["sha256"]:
            raise ValueError(f"Model file drift: {expected['path']}")
        checked.append(observed)
    return {"file_count": len(checked), "total_bytes": sum(row["bytes"] for row in checked)}


def load_validation(contract: dict[str, Any]) -> list[dict[str, Any]]:
    data = contract["data"]
    path = resolve_project_path(data["validation_path"])
    rows = read_jsonl(path)
    if len(rows) != int(data["validation_rows"]):
        raise ValueError("Validation row-count drift")
    labels = set(contract["labels"])
    sample_ids: set[str] = set()
    for row in rows:
        if row.get("protocol_id") != data["protocol_id"] or row.get("label") not in labels:
            raise ValueError("Validation schema or label drift")
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or sample_id in sample_ids:
            raise ValueError("Validation sample_id drift")
        sample_ids.add(sample_id)
        if not isinstance(row.get("group_id"), str) or not row["group_id"]:
            raise ValueError("Validation group_id drift")
        target = row.get("views", {}).get("target_only", {}).get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Validation target drift")
        if target != row.get("views", {}).get("previous_context", {}).get("target"):
            raise ValueError("Paired target drift")
        previous = row["views"]["previous_context"].get("previous")
        if bool(previous) != bool(row.get("context_available")):
            raise ValueError("context_available drift")
    return rows


def load_prompt(contract: dict[str, Any]) -> dict[str, Any]:
    prompt = load_json(resolve_project_path(contract["frozen_artifacts"]["prompt"]["path"]))
    if tuple(prompt["label_definitions"]) != tuple(contract["labels"]):
        raise ValueError("Prompt ontology order drift")
    return prompt


def prompt_messages(
    contract: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]
) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in contract["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    user = prompt["target_only_template"].format(target=row["views"]["target_only"]["target"])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def messages_sha256(messages: list[dict[str, str]]) -> str:
    return sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def require_token_ids(value: Any) -> list[int]:
    tokens = list(value)
    if not tokens or not all(isinstance(token, int) and not isinstance(token, bool) for token in tokens):
        raise TypeError("Chat template must return non-empty integer token IDs")
    return tokens


def output_token_counts(tokenizer: Any, output: str, generated_tokens: int) -> dict[str, int]:
    if "</think>" not in output:
        return {"final_tokens": 0, "thinking_tokens": generated_tokens}
    thinking, final = output.split("</think>", maxsplit=1)
    return {
        "final_tokens": len(tokenizer.encode(final, add_special_tokens=False)),
        "thinking_tokens": len(tokenizer.encode(thinking, add_special_tokens=False)),
    }


def quantile(values: Sequence[float | int], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot summarize an empty sequence")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty sequence")
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "p95": quantile(values, 0.95),
        "sum": sum(values),
    }


def classification_metrics(
    gold: Sequence[str],
    predictions: Sequence[str],
    labels: Sequence[str],
    invalid_label: str = INVALID_LABEL,
) -> dict[str, Any]:
    if len(gold) != len(predictions) or not gold:
        raise ValueError("Metrics require equal non-empty vectors")
    allowed_predictions = set(labels) | {invalid_label}
    if any(value not in labels for value in gold) or any(value not in allowed_predictions for value in predictions):
        raise ValueError("Metric label outside frozen ontology")
    per_class: dict[str, Any] = {}
    f1_values: list[float] = []
    precision_values: list[float] = []
    recall_values: list[float] = []
    weighted_sum = 0.0
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predictions))
        fp = sum(g != label and p == label for g, p in zip(gold, predictions))
        fn = sum(g == label and p != label for g, p in zip(gold, predictions))
        support = sum(g == label for g in gold)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"f1": f1, "precision": precision, "recall": recall, "support": support}
        f1_values.append(f1)
        precision_values.append(precision)
        recall_values.append(recall)
        weighted_sum += f1 * support
    columns = list(labels) + [invalid_label]
    confusion = [
        [sum(g == gold_label and p == predicted for g, p in zip(gold, predictions)) for predicted in columns]
        for gold_label in labels
    ]
    return {
        "accuracy": sum(g == p for g, p in zip(gold, predictions)) / len(gold),
        "confusion_columns": columns,
        "confusion_matrix": confusion,
        "macro_f1": statistics.fmean(f1_values),
        "macro_precision": statistics.fmean(precision_values),
        "macro_recall": statistics.fmean(recall_values),
        "per_class": per_class,
        "rows": len(gold),
        "weighted_f1": weighted_sum / len(gold),
    }


def metrics_by_slice(records: Sequence[dict[str, Any]], labels: Sequence[str]) -> dict[str, Any]:
    slices = {
        "all": list(records),
        "context_available": [row for row in records if row["context_available"]],
        "first_clause": [row for row in records if not row["context_available"]],
    }
    return {
        name: classification_metrics(
            [row["gold_label"] for row in values],
            [row["prediction"] for row in values],
            labels,
        )
        for name, values in slices.items()
    }


def macro_f1(records: Sequence[dict[str, Any]], labels: Sequence[str]) -> float:
    return classification_metrics(
        [row["gold_label"] for row in records],
        [row["prediction"] for row in records],
        labels,
    )["macro_f1"]


def validate_resume_prefix(
    existing: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]], condition: str
) -> None:
    if len(existing) > len(rows):
        raise ValueError("Private prediction file exceeds validation length")
    for index, record in enumerate(existing):
        if (
            record.get("condition") != condition
            or record.get("row_index") != index
            or record.get("sample_id") != rows[index]["sample_id"]
            or record.get("group_id") != rows[index]["group_id"]
        ):
            raise ValueError("Existing private rows are not an exact resumable prefix")


def bootstrap_pairwise(
    reference: Sequence[dict[str, Any]],
    candidate: Sequence[dict[str, Any]],
    labels: Sequence[str],
    repeats: int,
    namespace: str,
) -> dict[str, Any]:
    if len(reference) != len(candidate) or not reference:
        raise ValueError("Bootstrap requires aligned non-empty records")
    if any(
        left["sample_id"] != right["sample_id"]
        or left["group_id"] != right["group_id"]
        or left["gold_label"] != right["gold_label"]
        for left, right in zip(reference, candidate)
    ):
        raise ValueError("Bootstrap records are not aligned")
    group_indices: dict[str, list[int]] = {}
    for index, row in enumerate(reference):
        group_indices.setdefault(row["group_id"], []).append(index)
    groups = sorted(group_indices)
    randomizer = random.Random(int(sha256_text(namespace)[:16], 16))
    deltas: list[float] = []
    for _ in range(repeats):
        sampled_groups = [randomizer.choice(groups) for _ in groups]
        sampled_indices = [index for group in sampled_groups for index in group_indices[group]]
        ref_rows = [reference[index] for index in sampled_indices]
        candidate_rows = [candidate[index] for index in sampled_indices]
        deltas.append(macro_f1(candidate_rows, labels) - macro_f1(ref_rows, labels))
    observed = macro_f1(candidate, labels) - macro_f1(reference, labels)
    return {
        "ci95": [quantile(deltas, 0.025), quantile(deltas, 0.975)],
        "groups": len(groups),
        "observed_delta": observed,
        "probability_delta_gt_zero": sum(value > 0 for value in deltas) / len(deltas),
        "repeats": repeats,
        "resampling_unit": "group_id",
    }


def public_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["public_dir"])


def private_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["private_dir"])


def load_run(contract: dict[str, Any]) -> dict[str, Any]:
    path = public_dir(contract) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Matched validation is not initialized")
    return load_json(path)


def save_run(contract: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(public_dir(contract) / "run.json", run)


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def initialize(contract: dict[str, Any]) -> None:
    verify_authorization(contract)
    gates = verify_training_and_replay_gates(contract)
    rows = load_validation(contract)
    model_files = verify_model_manifest(contract)
    public = public_dir(contract)
    private = private_dir(contract)
    if public.exists() or private.exists():
        raise FileExistsError("Append-only matched-validation output already exists")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    private.chmod(0o700)
    initialized_at = utc_now()
    initialize_report = {
        "accessed_splits": ["validation"],
        "authorization": artifact(
            resolve_project_path(contract["frozen_artifacts"]["authorization"]["path"])
        ),
        "completed_at_utc": initialized_at,
        "condition_order": list(CONDITIONS),
        "experiment_id": EXPERIMENT_ID,
        "gates": gates,
        "model_files": model_files,
        "performance_metrics_computed": False,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_rows": len(rows),
        "validation_split_accessed": True,
    }
    atomic_json(public / "initialize.json", initialize_report)
    run = {
        "accessed_splits": ["validation"],
        "authorization": initialize_report["authorization"],
        "condition_order": list(CONDITIONS),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_state(),
        "raw_outputs_stored_publicly": False,
        "stages": {
            "initialize": {
                "artifact": artifact(public / "initialize.json"),
                "completed_at_utc": initialized_at,
                "status": "Passed",
            }
        },
        "status": "Initialized",
        "test_split_accessed": False,
        "validation_split_accessed": True,
    }
    save_run(contract, run)
    print(json.dumps({"rows": len(rows), "status": "Initialized"}, sort_keys=True))


def condition_summary(
    contract: dict[str, Any],
    condition: str,
    records: Sequence[dict[str, Any]],
    private_path: Path,
    command_elapsed: float,
    peak_memory_gb: float,
) -> dict[str, Any]:
    latencies = [float(row["generation_seconds"]) for row in records]
    final_tokens = [int(row["final_tokens"]) for row in records]
    generated = [int(row["generated_tokens"]) for row in records]
    prompt_tokens = [int(row["prompt_tokens"]) for row in records]
    thinking_tokens = [int(row["thinking_tokens"]) for row in records]
    valid = sum(bool(row["parse"]["valid"]) for row in records)
    return {
        "accessed_splits": ["validation"],
        "adapter": contract["conditions"][condition].get("adapter"),
        "completed_at_utc": utc_now(),
        "condition": condition,
        "experiment_id": EXPERIMENT_ID,
        "generation": {
            "api_cost_usd": 0,
            "batch_size": 1,
            "command_elapsed_seconds": command_elapsed,
            "final_tokens": numeric_summary(final_tokens),
            "generated_tokens": numeric_summary(generated),
            "generation_seconds": numeric_summary(latencies),
            "peak_memory_gb": peak_memory_gb,
            "prompt_tokens": numeric_summary(prompt_tokens),
            "thinking_tokens": numeric_summary(thinking_tokens),
            "throughput_generated_tokens_per_second": sum(generated) / sum(latencies),
        },
        "metrics": metrics_by_slice(records, contract["labels"]),
        "parser": {
            "error_counts": dict(
                sorted(Counter(row["parse"]["error"] for row in records if row["parse"]["error"]).items())
            ),
            "likely_truncated_count": sum(bool(row["likely_truncated"]) for row in records),
            "valid_count": valid,
            "valid_rate": valid / len(records),
        },
        "private_predictions_sha256": sha256_file(private_path),
        "raw_outputs_stored_publicly": False,
        "reasoning": True,
        "rows": len(records),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": True,
        "view": "target_only",
    }


def infer(contract: dict[str, Any], condition: str) -> None:
    run = load_run(contract)
    if run["stages"].get("initialize", {}).get("status") != "Passed":
        raise RuntimeError("Initialize must pass before matched validation")
    condition_index = CONDITIONS.index(condition)
    for prior in CONDITIONS[:condition_index]:
        if run["stages"].get(f"infer_{prior}", {}).get("status") != "Passed":
            raise RuntimeError(f"Prior condition must pass first: {prior}")
    for later in CONDITIONS[condition_index + 1 :]:
        if f"infer_{later}" in run["stages"]:
            raise RuntimeError("Condition-order drift")
    output = public_dir(contract) / f"condition-{condition}.json"
    if output.exists():
        raise FileExistsError(f"Condition already completed: {condition}")
    verify_authorization(contract)
    verify_training_and_replay_gates(contract)
    rows = load_validation(contract)
    prompt = load_prompt(contract)
    parse_final_label = load_parser(contract)
    private_path = private_dir(contract) / f"condition-{condition}-predictions.jsonl"
    existing = read_jsonl(private_path) if private_path.exists() else []
    validate_resume_prefix(existing, rows, condition)
    started = time.perf_counter()
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    import mlx.core as mx
    from mlx_lm import batch_generate, load
    from mlx_lm.sample_utils import make_sampler

    model_path = resolve_project_path(contract["model"]["local_path"])
    adapter = contract["conditions"][condition].get("adapter")
    mx.reset_peak_memory()
    if adapter is None:
        model, tokenizer = load(str(model_path), lazy=False)
    else:
        adapter_path = resolve_project_path(adapter["path"])
        model, tokenizer = load(str(model_path), adapter_path=str(adapter_path.parent), lazy=False)
    sampler = make_sampler(temp=float(contract["generation"]["temperature"]))
    for row_index in range(len(existing), len(rows)):
        source = rows[row_index]
        messages = prompt_messages(contract, prompt, source)
        prompt_ids = require_token_ids(
            tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
        )
        if len(prompt_ids) > int(contract["generation"]["max_input_tokens"]):
            raise RuntimeError(f"Rendered validation prompt exceeds token budget at row {row_index}")
        generation_started = time.perf_counter()
        generated = batch_generate(
            model,
            tokenizer,
            [prompt_ids],
            max_tokens=int(contract["generation"]["max_new_tokens"]),
            sampler=sampler,
            completion_batch_size=1,
            prefill_batch_size=1,
            prefill_step_size=int(contract["generation"]["prefill_step_size"]),
            verbose=False,
        )
        generation_seconds = time.perf_counter() - generation_started
        if not math.isfinite(generation_seconds) or generation_seconds <= 0:
            raise RuntimeError("Invalid singleton generation timing")
        output_text = generated.texts[0]
        parsed = parse_final_label(output_text, thinking=True, labels=contract["labels"])
        generated_tokens = len(tokenizer.encode(output_text, add_special_tokens=False))
        partitioned_tokens = output_token_counts(tokenizer, output_text, generated_tokens)
        record = {
            "condition": condition,
            "context_available": bool(source["context_available"]),
            "final_tokens": partitioned_tokens["final_tokens"],
            "generated_tokens": generated_tokens,
            "generation_seconds": generation_seconds,
            "gold_label": source["label"],
            "group_id": source["group_id"],
            "likely_truncated": generated_tokens >= int(contract["generation"]["max_new_tokens"]) - 2,
            "message_sha256": messages_sha256(messages),
            "parse": parsed.to_dict(),
            "prediction": parsed.label if parsed.valid else INVALID_LABEL,
            "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
            "prompt_tokens": len(prompt_ids),
            "raw_output": output_text,
            "raw_output_sha256": sha256_text(output_text),
            "reasoning": True,
            "row_index": row_index,
            "sample_id": source["sample_id"],
            "thinking_tokens": partitioned_tokens["thinking_tokens"],
            "view": "target_only",
        }
        append_private_jsonl(private_path, [record])
        completed = row_index + 1
        if completed % 10 == 0 or completed == len(rows):
            print(
                json.dumps(
                    {"completed": completed, "condition": condition, "total": len(rows)}, sort_keys=True
                ),
                flush=True,
            )
    records = read_jsonl(private_path)
    validate_resume_prefix(records, rows, condition)
    if len(records) != len(rows):
        raise RuntimeError("Matched-validation condition is incomplete")
    elapsed = time.perf_counter() - started
    peak_memory_gb = float(mx.get_peak_memory()) / 1e9
    if peak_memory_gb > float(contract["resource_budget"]["peak_memory_gb_max"]):
        raise RuntimeError("Matched validation exceeded the memory budget")
    if elapsed > float(contract["resource_budget"]["per_condition_hours_max"]) * 3600:
        raise RuntimeError("Matched validation exceeded the condition wall-time budget")
    summary = condition_summary(contract, condition, records, private_path, elapsed, peak_memory_gb)
    atomic_json(output, summary)
    run = load_run(contract)
    run["stages"][f"infer_{condition}"] = {
        "artifact": artifact(output),
        "completed_at_utc": utc_now(),
        "status": "Passed",
    }
    run["status"] = "Matched validation in progress"
    save_run(contract, run)
    del model, tokenizer
    gc.collect()
    mx.clear_cache()
    print(
        json.dumps(
            {
                "condition": condition,
                "macro_f1": summary["metrics"]["all"]["macro_f1"],
                "parser_valid_rate": summary["parser"]["valid_rate"],
                "status": "Passed",
            },
            sort_keys=True,
        )
    )


def primary_decision(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "material_improvement"
    if delta <= -threshold:
        return "material_degradation"
    return "practical_tie"


def render_report(aggregate: dict[str, Any]) -> str:
    rows = [
        "# EXP-047 Matched Validation Report",
        "",
        "Independent verification is required before this aggregate becomes Verified evidence.",
        "",
        "| Condition | Macro-F1 | Accuracy | Weighted-F1 | Parser valid | Duration (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition in CONDITIONS:
        summary = aggregate["conditions"][condition]
        metrics = summary["metrics"]["all"]
        rows.append(
            f"| {condition} | {metrics['macro_f1']:.6f} | {metrics['accuracy']:.6f} | "
            f"{metrics['weighted_f1']:.6f} | {summary['parser']['valid_rate']:.6f} | "
            f"{summary['generation']['command_elapsed_seconds']:.3f} |"
        )
    primary = aggregate["primary_contrast"]
    rows.extend(
        [
            "",
            "## Primary Contrast",
            "",
            f"- LoRA mean Macro-F1: `{primary['lora_macro_f1_mean']:.6f}`",
            f"- LoRA sample SD: `{primary['lora_macro_f1_sample_std']:.6f}`",
            f"- Matched reference Macro-F1: `{primary['reference_macro_f1']:.6f}`",
            f"- Mean delta: `{primary['mean_delta']:+.6f}`",
            f"- Frozen decision: `{primary['decision']}`",
            "",
            "Validation was accessed under explicit authorization. The sealed test was not accessed.",
            "Generated reasoning and row-level predictions remain private.",
            "",
        ]
    )
    return "\n".join(rows)


def aggregate(contract: dict[str, Any]) -> None:
    run = load_run(contract)
    if any(run["stages"].get(f"infer_{condition}", {}).get("status") != "Passed" for condition in CONDITIONS):
        raise RuntimeError("All four matched-validation conditions must pass before aggregation")
    output = public_dir(contract) / "aggregate.json"
    report_path = public_dir(contract) / "REPORT.md"
    if output.exists() or report_path.exists():
        raise FileExistsError("Matched-validation aggregate already exists")
    validation = load_validation(contract)
    records: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        private_path = private_dir(contract) / f"condition-{condition}-predictions.jsonl"
        condition_records = read_jsonl(private_path)
        validate_resume_prefix(condition_records, validation, condition)
        if len(condition_records) != len(validation):
            raise ValueError(f"Incomplete condition: {condition}")
        records[condition] = condition_records
        summaries[condition] = load_json(public_dir(contract) / f"condition-{condition}.json")
    labels = contract["labels"]
    macro_scores = {condition: macro_f1(values, labels) for condition, values in records.items()}
    lora_scores = [macro_scores[condition] for condition in CONDITIONS[1:]]
    lora_mean = statistics.fmean(lora_scores)
    lora_std = statistics.stdev(lora_scores)
    mean_delta = lora_mean - macro_scores["reference"]
    pairwise = {
        condition: bootstrap_pairwise(
            records["reference"],
            records[condition],
            labels,
            int(contract["evaluation"]["bootstrap_repeats"]),
            f"{contract['evaluation']['bootstrap_seed_namespace']}:{condition}",
        )
        for condition in CONDITIONS[1:]
    }
    aggregate_report = {
        "accessed_splits": ["validation"],
        "bootstrap_pairwise": pairwise,
        "completed_at_utc": utc_now(),
        "conditions": summaries,
        "experiment_id": EXPERIMENT_ID,
        "historical_comparators": contract["evaluation"]["historical_comparators"],
        "primary_contrast": {
            "decision": primary_decision(
                mean_delta, float(contract["evaluation"]["practical_tie_macro_f1"])
            ),
            "lora_macro_f1_mean": lora_mean,
            "lora_macro_f1_sample_std": lora_std,
            "mean_delta": mean_delta,
            "reference_macro_f1": macro_scores["reference"],
            "rule": "mean(seed-42,seed-43,seed-44)-reference",
            "threshold": float(contract["evaluation"]["practical_tie_macro_f1"]),
        },
        "raw_outputs_stored_publicly": False,
        "resource": {
            "api_cost_usd": 0,
            "condition_command_elapsed_seconds": {
                condition: summaries[condition]["generation"]["command_elapsed_seconds"]
                for condition in CONDITIONS
            },
            "peak_memory_gb_max": max(
                summaries[condition]["generation"]["peak_memory_gb"] for condition in CONDITIONS
            ),
            "total_command_elapsed_seconds": sum(
                summaries[condition]["generation"]["command_elapsed_seconds"]
                for condition in CONDITIONS
            ),
        },
        "status": "Completed; pending independent verification",
        "test_split_accessed": False,
        "validation_split_accessed": True,
    }
    if aggregate_report["resource"]["total_command_elapsed_seconds"] > float(
        contract["resource_budget"]["total_inference_hours_max"]
    ) * 3600:
        raise RuntimeError("Matched validation exceeded the total inference budget")
    atomic_json(output, aggregate_report)
    report_path.write_text(render_report(aggregate_report), encoding="utf-8")
    run["stages"]["aggregate"] = {
        "artifact": artifact(output),
        "completed_at_utc": utc_now(),
        "report": artifact(report_path),
        "status": "Passed",
    }
    run["status"] = "Completed; pending independent verification"
    save_run(contract, run)
    print(
        json.dumps(
            {
                "decision": aggregate_report["primary_contrast"]["decision"],
                "mean_delta": mean_delta,
                "status": aggregate_report["status"],
            },
            sort_keys=True,
        )
    )


def main() -> None:
    args = parse_args()
    contract = load_contract()
    if args.command == "initialize":
        initialize(contract)
    elif args.command == "infer":
        infer(contract, args.condition)
    elif args.command == "aggregate":
        aggregate(contract)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
